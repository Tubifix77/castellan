# ha-config

Home Assistant configuration as deployed on the Debian laptop.

> **Archived.** The deployment was decommissioned on 2026-09-05 and the laptop wiped
> of Castellan. This directory is the full record of what ran, kept so the system can
> be rebuilt. See "Rebuilding from this repo" below.

## Structure

| File | Purpose |
|------|---------|
| `docker-compose.yml` | HA + Wyoming services (pinned to 2025.6.3 — do not upgrade to `stable`, Python 3.14 has epoll/UDP regression) |
| `ha_voice.py` | Custom voice assistant — faster-whisper wake word ("computer") + HA Conversation API + Piper TTS |
| `ha-voice.service` | systemd unit for `ha_voice.py` |
| `config/configuration.yaml` | HA core config (DK locale, metric, CET) |
| `config/automations.yaml`, `scripts.yaml`, `scenes.yaml` | Empty stubs — no automations were ever written, but `configuration.yaml` `!include`s them, so HA will not start without them |
| `config/custom_sentences/en/goodnight.yaml` | The one custom voice command |
| `config/ui-lovelace.yaml` | YAML-mode dashboard (three lights) |
| `ha-mcp-proxy.sh` | Claude bridge (§9). Sanitised — the deployed copy had the token inline; this reads it from `.env` |
| `voice-requirements.txt` | The two direct deps of the voice venv |

## What is NOT in git

- `config/.storage/` — HA runtime state (entity registry, integrations, tokens)
- `config/home-assistant_v2.db` — history database
- `.env` — contains `HASS_TOKEN` (never commit)
- `venv/`, `ha-voice-venv/` — Python virtual environments
- `piper-data/`, `stp-models/`, `stp-train/`, `ollama-data/` — downloaded model files (re-pulled on demand)

`.storage/` is the consequential omission: it held the 18 UI-configured integrations, and it
cannot be committed because it also holds auth refresh tokens and password hashes. Everything
in it that mattered is written down under "Rebuilding from this repo" instead.

## Rebuilding from this repo

`docker compose up -d` restores the containers, but the integrations below were configured
through HA's UI and live only in `.storage/`, so they must be re-added by hand:

| Integration | Settings as deployed |
|---|---|
| WiZ (x3) | Auto-discovered on the LAN — no addresses needed. Give each bulb a friendly name, then make `ENTITIES` in `ha_voice.py` match those names (see below) |
| Ollama | `http://localhost:11434`, model `qwen2.5:1.5b` |
| Wyoming | `piper` :10200, `speech-to-phrase` :10300, `openwakeword` :10400 |
| MCP Server | Domain `mcp_server`, exposed at `/api/mcp` |
| Assist pipeline | stt `stt.speech_to_phrase`, tts `tts.piper` (voice `da_DK-talesyntese-medium`), conversation `conversation.qwen2_5_1_5b`, wake `wake_word.openwakeword` |

Note the pipeline's conversation agent is only used by HA's own Assist UI — `ha_voice.py`
calls `/api/conversation/process` directly and does its own Ollama fallback, so the voice
loop works regardless of that setting.

Two secrets are needed in `/home/boas/homeassistant/.env`, neither of which is in git:
`HASS_TOKEN` (create a fresh long-lived token — the old one died with the deployment) and
`OPENROUTER_API_KEY`.

Then: `pip install -r voice-requirements.txt` into a venv, install `ha-voice.service`, and
use the launchers in `../assets/`.

## Voice assistant notes

Wake word: **"computer"** (say it clearly, the script uses biased Whisper decoding)  
After wake: beep → speak command → beep → HA executes → Piper TTS reply  
Signal chain: PulseAudio → parecord → 250 Hz HPF → faster-whisper base int8 → fuzzy entity match → HA Conversation API → Piper TTS → mpg123

`ENTITIES` in `ha_voice.py` is the fuzzy-matching vocabulary and **must match the friendly names you
give your bulbs in HA**, or spoken commands will not resolve. The deployed set was:
- `living room standing lamp`
- `reading lamp`
- `bedroom light`

## Deployment notes

- HA pinned to `2025.6.3` (Python 3.13.3) — Python 3.14 breaks asyncio UDP (WiZ integration would fail)
- Mic: dedicated 3.5mm mic jack (ALC269VC, `alsa_input.pci-0000_00_1b.0.analog-stereo`, port `analog-input-mic`)
- HDMI output disappears when headphones are plugged in — hardware limitation of ALC269VC, not a bug
- Token stored in `/home/boas/homeassistant/.env` on the laptop only
