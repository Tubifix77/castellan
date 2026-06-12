# Castellan

**A local-AI architecture for Home Assistant** — a fully local, single-host smart home with an AI layer. Everyday operation never leaves the LAN; the internet is touched only as an optional, bounded last resort for hard free-form questions.

> **Status:** Build phase (architecture v0.5). Roadmap steps 1–4 are deployed — the voice core works end-to-end on the host. Steps 5+ (warm path, escalation) remain design.

## The idea

Home Assistant is powerful but remains a DIY project: complex setup, no one-click installer, and voice assistants that lag. Modern local AI plus an AI coding assistant close most of those gaps without giving up local control or privacy. Castellan captures the architecture for doing that on one cheap, always-on machine — built to migrate to a dedicated low-power SoC later with no rework.

## Core design decisions

- **Single always-on host.** The whole stack runs on one Debian laptop. The gaming PC is **excluded from the runtime** (a house can't depend on a machine that's off or busy at random) — it's build-time only.
- **Slow-escalation query path**, by how hard the request is:
  - *Hot* (~95%): HA deterministic intents — no LLM, no network. (As deployed, the whisper STT in front costs seconds; Speech-to-Phrase is the documented instant path for known phrases.)
  - *Warm*: a small local LLM (CPU now, NPU later). Free-form, local, slow-ish on old hardware.
  - *Escalation* (optional): an APEX-style free-tier cloud model for the rare hard question — behind a strict egress boundary.
- **Egress boundary** for the one path that leaves the LAN: text only (never audio), general-knowledge only (never home state, security, or control), redacted, opt-in, with graceful fallback so the house never breaks when the internet is down.
- **Voice runs entirely locally.** As deployed: a faster-whisper wake-word + STT loop with Piper TTS replies; Speech-to-Phrase stays wired into HA's own Assist pipeline (see ARCHITECTURE.md §6).
- **Portable by architecture:** HA's conversation agent points at one OpenAI-compatible endpoint. Localhost CPU model now; an Orange Pi 5 Pro (RK3588S, 6 TOPS NPU) is a documented, zero-rework future migration — relocate the stack, repoint one URL.
- **Claude, two channels (build/repair only, never the live loop):** HA's official MCP server (`mcp-proxy` + token) for live control, SSH for editing `/config`.
- **Self-healing is human-gated** (detect → propose → you approve) — a separate channel from the voice escalation, deliberately not a free-tier rig.
- **Runs as a background service:** auto-start, headless, restart-on-failure, resource-capped to coexist with another always-on workload on the same box.

## Reference hardware

| Role | Device | Notes |
|------|--------|-------|
| **The host (now)** | Debian laptop (x86, always-on) | Runs everything; shared with another service → resource caps |
| Build-time only | Gaming PC (RTX) | Claude Desktop + testing; never runs the live house |
| Future target | Orange Pi 5 Pro (RK3588S, 6 TOPS NPU) | Silent, ~10 W; NPU makes free-form fast; zero-rework migration |
| Edge / satellites | ESP32 (×N) | BLE proxy, voice satellite, displays |
| Build assistant | Claude Desktop | `mcp-proxy` → HA + SSH to `/config` |

## Documents

- [`ARCHITECTURE.md`](ARCHITECTURE.md) — the full architecture (v0.5), section by section, with verified facts, recommendations, and as-built deployment marked.
- [`ha-config/`](ha-config/) — snapshot of the working deployment: compose file, the voice loop (`ha_voice.py`), systemd unit, HA config. Secrets stay on the host (see its README).

A visual, single-file HTML version of the architecture also exists and can be added under `docs/` if wanted.

## Roadmap

1. Home Assistant on the laptop (Docker), `/config` under git; running as a background service. ✅
2. The Claude bridge: HA MCP server + `mcp-proxy` + long-lived token. ✅
3. One radio + a few real devices. ✅ *(three WiZ WiFi bulbs; no Zigbee radio yet)*
4. **Deterministic voice core** — the usable MVP: voice control + status. ✅ *shipped 2026-06-13* (as-built: faster-whisper wake+STT loop + Piper; see ARCHITECTURE.md §6)
5. Warm path — local small LLM behind the OpenAI-compatible seam, resource-capped. ← *next*
6. Escalation (optional) — APEX-style cloud tier behind the egress boundary; a toggle.
7. Skills + the first real automations and dashboard.
8. Later: migrate to a dedicated SoC (repoint one URL); energy management.

## Notes

Steps 1–4 are a real, running deployment (snapshot in `ha-config/`); the later tiers are still design. Hardware specifics drift — verify NPU driver setup (`rkllm` / `rkllama`) and the current `mcp-proxy` flags against upstream when you build. Sources for the verified claims are listed in `ARCHITECTURE.md`.

## License

Apache 2.0 — see [LICENSE](LICENSE).

---

*Castellan is an independent community project. It is not affiliated with, endorsed by, or sponsored by Home Assistant or the Open Home Foundation. "Home Assistant" is a trademark of the Open Home Foundation.*
