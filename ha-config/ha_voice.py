#!/usr/bin/env python3
"""HA voice assistant — faster-whisper wake word + HA Conversation API.

Replaces wyoming-satellite + openWakeWord. Records via PulseAudio,
detects wake word "computer" with tiny model, transcribes command
with base model, sends to HA Conversation API, speaks reply via Piper.

Signal conditioning: the headset mic line carries constant noise
(~42 Hz hum + broadband hiss, idle RMS ~0.03 after filtering), so every
chunk is high-pass filtered at 250 Hz and all level decisions are made
against an adaptive noise floor (median RMS of recent quiet chunks)
rather than fixed thresholds.
"""
import json
import logging
import os
import difflib
import re
import statistics
import time
import subprocess
import tempfile
from collections import deque

import numpy as np
import urllib.request
from faster_whisper import WhisperModel

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logging.getLogger("faster_whisper").setLevel(logging.WARNING)
log = logging.getLogger(__name__)

RATE            = 16000
SAMPLE_WIDTH    = 2        # int16
WAKE_WORD       = "computer"   # spoken form
WAKE_TOKEN      = "comput"     # what we match in transcripts (tiny model garbles)
WAKE_CHUNK      = 2.0      # seconds per listen window
SILENCE_CHUNK   = 0.5      # seconds per command sub-chunk
SILENCE_NEEDED  = 3        # consecutive silent chunks (= 1.5 s) to stop
MAX_CMD_CHUNKS  = 30       # 15 s absolute max for a command
HPF_CUTOFF      = 250.0    # Hz — kills 42/84/210 Hz line hum

WAKE_GATE_RATIO    = 1.5   # transcribe only above floor * this
SILENCE_RATIO      = 1.35  # command chunk below floor * this = silence
GATE_MIN, GATE_MAX = 0.02, 0.15
FLOOR_SEED         = 0.033 # measured idle floor, used until enough samples

PA_MIC = "alsa_input.pci-0000_00_1b.0.analog-stereo"
PA_SPK = "alsa_output.pci-0000_00_1b.0.analog-stereo"
PA_ENV = {**os.environ, "PULSE_SERVER": "unix:/run/user/1000/pulse/native"}
HA_URL       = "http://localhost:8123"
OLLAMA_URL   = "http://localhost:11434/v1/chat/completions"  # portability seam
OLLAMA_MODEL = "qwen2.5:1.5b"

# Whisper mangles entity names ("standing lamp" -> "standing in length"),
# so transcripts get fuzzy-corrected against the real names afterwards.
ENTITIES = ["living room standing lamp", "livs lampe", "soveværelse light"]


def _token() -> str:
    with open("/home/boas/homeassistant/.env") as f:
        for line in f:
            if line.startswith("HASS_TOKEN="):
                return line.strip().split("=", 1)[1]
    raise RuntimeError("HASS_TOKEN not found in .env")


def _open_mic() -> subprocess.Popen:
    return subprocess.Popen(
        ["parecord", "--raw", "--channels=1",
         f"--rate={RATE}", "--format=s16le", f"--device={PA_MIC}"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        env=PA_ENV,
    )


def _read(proc: subprocess.Popen, secs: float) -> np.ndarray:
    n = int(secs * RATE) * SAMPLE_WIDTH   # whole samples — odd byte counts crash frombuffer
    buf = b""
    while len(buf) < n:
        chunk = proc.stdout.read(n - len(buf))
        if not chunk:
            break
        buf += chunk
    return np.frombuffer(buf, dtype=np.int16).astype(np.float32) / 32768.0


def _hpf(x: np.ndarray, fc: float = HPF_CUTOFF) -> np.ndarray:
    """FFT brick-wall high-pass — per-chunk, no state, pure numpy."""
    if len(x) < 2:
        return x
    X = np.fft.rfft(x)
    X[: int(fc * len(x) / RATE)] = 0
    return np.fft.irfft(X, n=len(x)).astype(np.float32)


def _rms(x: np.ndarray) -> float:
    return float(np.sqrt(np.mean(x ** 2))) if len(x) else 0.0


def _beep(freq: float = 880.0, dur: float = 0.12) -> None:
    """Short cue tone through the headset (wake ack / end-of-capture)."""
    t = np.linspace(0, dur, int(44100 * dur), endpoint=False)
    tone = (0.6 * np.sin(2 * np.pi * freq * t) * 32767).astype(np.int16)
    try:
        subprocess.run(
            ["paplay", "--raw", "--channels=1", "--rate=44100",
             "--format=s16le", f"--device={PA_SPK}"],
            input=tone.tobytes(), env=PA_ENV, timeout=5,
            stderr=subprocess.DEVNULL,
        )
    except Exception as exc:
        log.warning("beep failed: %s", exc)


def _transcribe(model: WhisperModel, audio: np.ndarray) -> str:
    segs, _ = model.transcribe(audio, beam_size=5, language="en")
    return " ".join(s.text for s in segs).strip().lower()


def _transcribe_biased(model: WhisperModel, audio: np.ndarray) -> str:
    """Wake-word check: bias decoding toward the word we're listening for."""
    segs, _ = model.transcribe(audio, beam_size=5, language="en",
                               initial_prompt="Computer.")
    return " ".join(s.text for s in segs).strip().lower()


def _fuzzy_fix(cmd: str) -> str:
    """Best entity match anywhere in the transcript + on/off intent,
    rebuilt as a canonical command."""
    cmd = re.sub(r"[^\wæøåÆØÅ ]", " ", cmd.lower())
    words = cmd.split()
    best_r, best_ent = 0.0, None
    for ent in ENTITIES:
        n = len(ent.split())
        for i in range(len(words)):
            hi = min(len(words) - i, n + 2)
            for span in range(max(1, n - 2), hi + 1):
                seg = " ".join(words[i:i + span])
                r = difflib.SequenceMatcher(None, seg, ent).ratio()
                if r > best_r:
                    best_r, best_ent = r, ent
    if best_ent and best_r > 0.6:
        action = "off" if re.search(r"\boff\b", cmd) else "on"
        return f"turn {action} {best_ent}"
    return " ".join(words)


def _converse(tok: str, text: str) -> str:
    req = urllib.request.Request(
        f"{HA_URL}/api/conversation/process",
        data=json.dumps({"text": text, "language": "en"}).encode(),
        headers={"Authorization": f"Bearer {tok}",
                 "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        d = json.loads(r.read())
    resp = d.get("response", {})
    if resp.get("response_type") == "error":
        log.info("HA error (%s) — escalating to local LLM",
                 resp.get("data", {}).get("code", "?"))
        return _converse_llm(text)
    return resp.get("speech", {}).get("plain", {}).get("speech", "")


def _converse_llm(text: str) -> str:
    """Warm-path fallback: direct Ollama call, no HA entity context."""
    req = urllib.request.Request(
        OLLAMA_URL,
        data=json.dumps({
            "model": OLLAMA_MODEL,
            "messages": [{"role": "user", "content": text}],
            "stream": False,
        }).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        d = json.loads(r.read())
    return d.get("choices", [{}])[0].get("message", {}).get("content", "").strip()


def _speak(tok: str, text: str) -> None:
    try:
        req = urllib.request.Request(
            f"{HA_URL}/api/tts_get_url",
            data=json.dumps({
                "message": text,
                "engine_id": "tts.piper",
                "options": {"voice": "en_US-lessac-medium"},
            }).encode(),
            headers={"Authorization": f"Bearer {tok}",
                     "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            result = json.loads(r.read())
        url = result.get("url", "")
        if not url:
            log.warning("TTS returned no URL")
            return
        if url.startswith("/"):
            url = f"{HA_URL}{url}"
        req2 = urllib.request.Request(
            url, headers={"Authorization": f"Bearer {tok}"})
        with urllib.request.urlopen(req2, timeout=15) as r:
            audio = r.read()
        fd, path = tempfile.mkstemp(suffix=".mp3")
        try:
            os.write(fd, audio)
            os.close(fd)
            subprocess.run(
                ["mpg123", "-q", "-o", "pulse", path],
                env=PA_ENV, timeout=30, stderr=subprocess.DEVNULL,
            )
        finally:
            os.unlink(path)
    except Exception as exc:
        log.warning("TTS failed: %s", exc)


def main() -> None:
    tok = _token()
    log.info("Loading faster-whisper base model…")
    cmd_model = WhisperModel("base", device="cpu", compute_type="int8")
    log.info("Ready — say '%s' to activate.", WAKE_WORD)

    floor: deque[float] = deque(maxlen=40)
    idle = 0
    tail = np.zeros(0, dtype=np.float32)
    mic = _open_mic()
    try:
        while True:
            chunk = _hpf(_read(mic, WAKE_CHUNK))
            t_read = time.monotonic()
            audio = np.concatenate([tail, chunk])
            tail = chunk[-int(0.75 * RATE):]
            rms = _rms(chunk)
            med = statistics.median(floor) if len(floor) >= 5 else FLOOR_SEED
            gate = min(max(med * WAKE_GATE_RATIO, GATE_MIN), GATE_MAX)
            if rms < gate:
                floor.append(rms)
                idle += 1
                if idle % 150 == 0:
                    log.info("idle — floor=%.3f gate=%.3f", med, gate)
                continue
            t = _transcribe_biased(cmd_model, audio)
            log.info("heard (rms=%.3f gate=%.3f): %r", rms, gate, t)
            if WAKE_TOKEN not in t:
                continue

            log.info("Wake word detected — listening for command…")
            tail = np.zeros(0, dtype=np.float32)
            _beep(880, 0.35)
            _read(mic, time.monotonic() - t_read + 0.2)

            silence_thresh = min(max(med * SILENCE_RATIO, GATE_MIN), GATE_MAX)
            chunks: list[np.ndarray] = []
            silent = 0
            started = False
            for i in range(MAX_CMD_CHUNKS):
                piece = _read(mic, SILENCE_CHUNK)
                chunks.append(piece)
                c = _hpf(piece)
                if _rms(c) >= silence_thresh:
                    started = True
                    silent = 0
                elif started:
                    silent += 1
                    if silent >= SILENCE_NEEDED:
                        break
                elif i >= 16:
                    break
            _beep(660, 0.1)
            t0 = time.monotonic()

            raw = _transcribe(cmd_model, _hpf(np.concatenate(chunks)))
            command = _fuzzy_fix(raw)
            log.info("Command: %r -> %r", raw, command)

            if command:
                reply = _converse(tok, command)
                log.info("Reply: %s", reply)
                if reply:
                    _speak(tok, reply)

            _read(mic, time.monotonic() - t0 + 0.3)
            tail = np.zeros(0, dtype=np.float32)

    finally:
        mic.terminate()
        mic.wait()


if __name__ == "__main__":
    main()
