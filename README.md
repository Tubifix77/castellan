# Castellan

**A fully local smart home built on Home Assistant** — voice control, a small on-device LLM, and Claude as the build assistant. No cloud dependency in everyday operation, no internet exposure of the home.

> **Status: Archived — decommissioned 2026-09-05.** Castellan was built to completion (v0.7) and
> ran on a Debian laptop from June to August 2026. It was removed from that host because it went
> unused, not because it failed. This repo is the complete record and is sufficient to rebuild it;
> see [`ha-config/README.md`](ha-config/README.md#rebuilding-from-this-repo).

## What it does

Say **"computer"** → beep → speak a command → the house responds.

- **Light control:** "turn on the living room standing lamp", "dim the lights", "goodnight"
- **Free-form questions:** anything HA can't match falls through to a local LLM (Ollama qwen2.5:1.5b)
- **Optional cloud escalation:** press E at startup for a 5-second opt-in window — routes hard questions to a free-tier cloud LLM behind a strict egress boundary. Off by default, fails closed, and lasts one launch only.
- **All local by default:** faster-whisper STT, Piper TTS, Ollama — nothing leaves the LAN unless you opted in

## Core design decisions

- **Single always-on host** — the whole stack runs on one Debian laptop. The gaming PC is excluded from the runtime entirely.
- **Three-path AI**, by how often each fires:
  - *Hot* (~95%): HA deterministic intents. Sub-100 ms, no LLM.
  - *Warm*: local qwen2.5:1.5b via Ollama for free-form speech. Fully local.
  - *Escalation* (opt-in): free-tier cloud LLM behind a strict egress boundary — text only, general knowledge only, never home state or audio. Opted into per launch via the 5-second countdown; a reboot resets it to local-only.
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

## What ran

Nothing runs now — the host was wiped on 2026-09-05. This is what the deployment consisted of:

| Service | How | Port |
|---------|-----|------|
| Home Assistant | Docker (2025.6.3) | 8123 |
| wyoming-piper | Docker | 10200 |
| wyoming-speech-to-phrase | Docker | 10300 |
| Ollama (qwen2.5:1.5b) | Docker | 11434 |
| ha-voice | systemd | — |

It was started and stopped via the desktop icons, which were the **only** lifecycle entry points — they own both halves (compose stack *and* the `ha-voice` unit) together.

"Stopped" is persistent: stop runs `systemctl disable --now`, so nothing returns on the next boot. "Started" is likewise persistent — start runs `enable --now`, matching `docker compose up -d`, so a reboot brings Castellan back up until you actually stop it. Cloud escalation is the exception and resets to local-only on every boot (see Notes).

## Devices

- Living room Standing Lamp — WiZ, `REDACTED-LAN-IP`
- Reading Lamp — WiZ, `REDACTED-LAN-IP`
- Bedroom Light — WiZ, `REDACTED-LAN-IP`

## Desktop launchers

Two icons sat on the Debian desktop (xfce4-terminal). The scripts and SVGs are kept in
[`assets/`](assets/); only the installed copies were removed:

| Icon | Colour | Action |
|------|--------|--------|
| Castellan | Cyan castle, glowing orb | Starts all services. 5-second countdown — press **E** to enable cloud escalation, anything else (or timeout) = local only. |
| Castellan Stop | Orange castle, power symbol | Stops all services cleanly. |

## Documents and assets

- [`ARCHITECTURE.md`](ARCHITECTURE.md) — full spec (v0.7), VERIFIED / REC / DEPLOYED tags
- [`ha-config/`](ha-config/) — the deployed HA config, plus what to re-create by hand when rebuilding
- [`assets/`](assets/) — desktop launcher icons (SVG) and the start/stop scripts

## Roadmap

- ✅ Step 1 — HA on laptop, Docker, git-tracked config
- ✅ Step 2 — Claude MCP bridge
- ✅ Step 3 — WiZ bulbs (local, no cloud)
- ✅ Step 4 — Deterministic voice core
- ✅ Step 5 — Warm path (Ollama local LLM)
- ✅ Step 6 — Custom intents ("goodnight" etc.)
- ✅ Step 7 — Desktop launchers + opt-in cloud escalation at startup
- ✅ Step 7.1 *(2026-08-06)* — Escalation opt-in actually wired into `ha_voice.py` (fail-closed); start/stop own the systemd unit so "stopped" survives a reboot
- ⛔ Step 8 — Migrate to dedicated SoC; energy management. Never started; the SoC was never bought
  and the project was archived first.

## Notes

- HA pinned to `2025.6.3` (Python 3.13.3) — do not upgrade to `stable`, Python 3.14 has an epoll/UDP regression that breaks WiZ and voice
- Secrets lived only in `/home/boas/homeassistant/.env` on the laptop, never in git. That file is
  gone with the host. `HASS_TOKEN` died with the deployment and a rebuild needs a fresh one; the
  OpenRouter key is the only reusable secret and is held separately by the owner
- ALC269VC audio chip: HDMI output and headphone jack are mutually exclusive (hardware limitation, not a bug)
- `ha-config/` was a manually re-synced snapshot; at decommission it was verified byte-identical to
  the host, so it is now a faithful final archive rather than a drifting copy
- Cloud escalation opt-in is written to `/run/castellan/escalation` and read by `ha_voice.py` at startup. It fails closed — missing, `0`, empty, or anything but a literal `1` means local-only — and when off the API key is blanked in memory, so there is no key to reach the network with. `/run` is tmpfs, so **the opt-in lasts one launch**: after a reboot Castellan is local-only until you press **E** again
- Both halves must be started/stopped together; never `systemctl start ha-voice` by hand. A bare `stop` is transient, and that defect once left the voice loop running ~7 weeks after Castellan was "stopped" (fixed 2026-08-06 — see ARCHITECTURE.md §10)

## Decommissioning (2026-09-05)

Removed from the laptop: the four Castellan Docker images (~6.6 GB), `/home/boas/homeassistant`
(1.4 GB), the voice venv `/home/boas/ha-voice-venv` (447 MB), the `ha-voice` systemd unit, and the
desktop launchers, icons and start/stop scripts.

Deliberately left alone: Docker itself, and the unrelated services sharing the host — **Pi-hole**
(the LAN's DNS) and **growing-spine**, along with their images and data.

Before the wipe, the repo was verified against the host: all eight shared files were byte-identical,
and the files the host had that the repo lacked were added (`ha-mcp-proxy.sh`, sanitised of its
inline token; the three empty HA `!include` stubs; `voice-requirements.txt`). What could not be
committed — `.storage/`, which carries auth tokens and password hashes — is instead written up as a
rebuild checklist in [`ha-config/README.md`](ha-config/README.md#rebuilding-from-this-repo).

There was also a second, local-only git repo on the laptop (`/home/boas/homeassistant/.git`) with
no remote, holding a parallel history that was never pushed anywhere. Its content matched this
repo's, so nothing unique was lost when the directory was removed.

## License

Apache 2.0 — see [LICENSE](LICENSE).

---

*Castellan is an independent community project. It is not affiliated with, endorsed by, or sponsored by Home Assistant or the Open Home Foundation. "Home Assistant" is a trademark of the Open Home Foundation.*
