# Castellan

**A fully local smart home built on Home Assistant** — voice control, a small on-device LLM, and Claude as the build assistant. No cloud dependency in everyday operation, no internet exposure of the home.

> **Status:** Complete (v0.5) — running on a Debian laptop. Step 8 (SoC migration) deferred.

## What it does

Say **"computer"** → beep → speak a command → the house responds.

- **Light control:** "turn on the living room standing lamp", "dim the lights", "goodnight"
- **Free-form questions:** anything HA can't match falls through to a local LLM (Ollama qwen2.5:1.5b)
- **All local:** faster-whisper STT, Piper TTS, Ollama — nothing leaves the LAN in daily use

## Core design decisions

- **Single always-on host** — the whole stack runs on one Debian laptop. The gaming PC is excluded from the runtime entirely.
- **Three-path AI**, by how often each fires:
  - *Hot* (~95%): HA deterministic intents. Sub-100 ms, no LLM.
  - *Warm*: local qwen2.5:1.5b via Ollama for free-form speech. Fully local.
  - *Escalation* (optional, off by default): APEX-style free-tier cloud behind a strict egress boundary — text only, general knowledge only, never home state or audio.
- **Voice pipeline:** PulseAudio → parecord → 250 Hz HPF → faster-whisper base int8 → fuzzy entity match → HA Conversation API → Piper TTS → mpg123. ~12 s end-to-end.
- **Claude, two channels (build/repair only):** HA's official MCP server (`mcp-proxy` + long-lived token) for live control, SSH for editing `/config`.
- **Self-healing is human-gated** — detect → propose → approve. Never autonomous.
- **Portable by architecture:** one OpenAI-compatible endpoint. Move to an Orange Pi 5 Pro (RK3588S, 6 TOPS NPU) by relocating the stack and repointing one URL — no code changes.

## Reference hardware

| Role | Device | Notes |
|------|--------|-------|
| **The host** | Debian 12 laptop (x86, always-on) | Runs everything; shared with another service → resource caps |
| Future target | Orange Pi 5 Pro (RK3588S, 6 TOPS NPU) | Silent, ~10 W; NPU makes free-form fast; zero-rework migration |
| Gaming PC | Build-time only | Claude Desktop + testing; never runs the live house |
| Edge | ESP32 (×N) | BLE proxy, voice satellite, displays (future) |

## What's running

| Service | How | Port |
|---------|-----|------|
| Home Assistant | Docker (2025.6.3) | 8123 |
| wyoming-piper | Docker | 10200 |
| wyoming-speech-to-phrase | Docker | 10300 |
| Ollama (qwen2.5:1.5b) | Docker | 11434 |
| ha-voice | systemd | — |

Started and stopped manually via the desktop icons (not autostart).

## Devices

- Living room Standing Lamp — WiZ, `192.168.0.130`
- Livs lampe — WiZ, `192.168.86.234`
- Soveværelse Light — WiZ, `192.168.86.236`

## Documents and assets

- [`ARCHITECTURE.md`](ARCHITECTURE.md) — full spec (v0.5), VERIFIED / REC / DEPLOYED tags
- [`ha-config/`](ha-config/) — deployed HA config snapshot (docker-compose, ha_voice.py, systemd unit)
- [`assets/`](assets/) — desktop launcher icons and scripts (cyan = start, orange = stop)

## Roadmap

- ✅ Step 1 — HA on laptop, Docker, git-tracked config
- ✅ Step 2 — Claude MCP bridge
- ✅ Step 3 — WiZ bulbs (local, no cloud)
- ✅ Step 4 — Deterministic voice core
- ✅ Step 5 — Warm path (Ollama local LLM)
- ✅ Step 6 — Custom intents ("goodnight" etc.)
- ✅ Step 7 — Desktop launchers (start/stop icons)
- ⏳ Step 8 — Migrate to dedicated SoC; energy management

## Notes

- HA pinned to `2025.6.3` (Python 3.13.3) — do not upgrade to `stable`, Python 3.14 has an epoll/UDP regression that breaks WiZ and voice
- Token stored in `/home/boas/homeassistant/.env` on the laptop only — never in git
- ALC269VC audio chip: HDMI output and headphone jack are mutually exclusive (hardware limitation, not a bug)
- `ha-config/` is a snapshot — re-sync manually when laptop files change

## License

Apache 2.0 — see [LICENSE](LICENSE).

---

*Castellan is an independent community project. It is not affiliated with, endorsed by, or sponsored by Home Assistant or the Open Home Foundation. "Home Assistant" is a trademark of the Open Home Foundation.*
