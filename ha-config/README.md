# ha-config

Live Home Assistant configuration — deployed on the Debian laptop at `192.168.0.77`.

## Structure

| File | Purpose |
|------|---------|
| `docker-compose.yml` | HA + Wyoming services (pinned to 2025.6.3 — do not upgrade to `stable`, Python 3.14 has epoll/UDP regression) |
| `ha_voice.py` | Custom voice assistant — faster-whisper wake word ("computer") + HA Conversation API + Piper TTS |
| `ha-voice.service` | systemd unit for `ha_voice.py` |
| `config/configuration.yaml` | HA core config (DK locale, metric, CET) |

## What is NOT in git

- `config/.storage/` — HA runtime state (entity registry, integrations, tokens)
- `config/home-assistant_v2.db` — history database
- `.env` — contains `HASS_TOKEN` (never commit)
- `venv/`, `ha-voice-venv/` — Python virtual environments
- `piper-data/`, `stp-models/`, `stp-train/` — downloaded model files

## Voice assistant notes

Wake word: **"computer"** (say it clearly, the script uses biased Whisper decoding)  
After wake: beep → speak command → beep → HA executes → Piper TTS reply  
Signal chain: PulseAudio → parecord → 250 Hz HPF → faster-whisper base int8 → fuzzy entity match → HA Conversation API → Piper TTS → mpg123

Known entities for fuzzy matching (update `ENTITIES` in `ha_voice.py` when adding devices):
- `living room standing lamp`
- `livs lampe`
- `soveværelse light`

## Deployment notes

- HA pinned to `2025.6.3` (Python 3.13.3) — Python 3.14 breaks asyncio UDP (WiZ integration would fail)
- Mic: dedicated 3.5mm mic jack (ALC269VC, `alsa_input.pci-0000_00_1b.0.analog-stereo`, port `analog-input-mic`)
- HDMI output disappears when headphones are plugged in — hardware limitation of ALC269VC, not a bug
- Token stored in `/home/boas/homeassistant/.env` on the laptop only
