# Home Assistant Pro Setup

A reference architecture for a **fully local, open-source smart home** built around Home Assistant, a local LLM for voice, and Claude as the configuration and build assistant. No cloud dependency in everyday operation, and no internet exposure of the home.

> **Status:** Design phase — architecture complete, not yet built.

## The idea

Home Assistant is powerful but remains a DIY project: complex setup, no one-click installer, and voice assistants that lag. Modern local AI plus an AI coding assistant close most of those gaps without giving up local control or privacy. This repo captures the architecture for doing that on cheap, dedicated, always-on hardware.

## Core design decisions

- **Dedicated always-on brain on an Orange Pi 5 Pro** (RK3588S, 6 TOPS NPU) — not a gaming PC. Low power (~10 W), silent, native USB for radios.
- **Three-path AI model**, chosen by how often each path fires:
  - *Hot* (~95% of commands): Home Assistant's deterministic intent matching + Speech-to-Phrase. No LLM, no GPU, sub-100 ms.
  - *Warm* (free-form speech, rare): a small ~3B local model (e.g. Llama 3.2 3B) on the NPU, ~15–20 tok/s.
  - *Cold* (rare, human-in-loop): Claude builds automations, dashboards, ESPHome firmware, and proposes fixes.
- **Voice runs entirely locally** on the Pi (Speech-to-Phrase + Whisper.cpp + Piper) — no external GPU in the hot path.
- **Claude integrates two ways:** Home Assistant's official MCP Server (`/api/mcp` via `mcp-proxy` + a long-lived token) for runtime entity control, and SSH for editing `/config` YAML.
- **Self-healing is human-gated** (detect → propose → you approve), never an autonomous agent rewriting the home.

## Reference hardware

| Role | Device | Notes |
|------|--------|-------|
| Prod brain (always-on) | Orange Pi 5 Pro (RK3588S, 6 TOPS NPU, 16 GB) | HA + voice + 3B model + Zigbee USB |
| Testbed | x86 Linux laptop (Debian 12) | Build & validate here, then promote to the Pi |
| Optional dev/batch GPU | Desktop with a discrete GPU | Test larger models / batch work; never an always-on dependency |
| Edge / satellites | ESP32 (×N) | BLE proxy, voice satellite, displays |
| Build assistant | Claude Desktop | `mcp-proxy` → HA + SSH to `/config` |

## Documents

- [`ARCHITECTURE.md`](ARCHITECTURE.md) — the full architecture, section by section, with verified facts vs. recommendations marked.

A visual, single-file HTML version of the architecture also exists and can be added under `docs/` if wanted.

## Roadmap

1. Home Assistant on the testbed laptop (Docker), git-track `/config`.
2. The Claude bridge: HA MCP Server + `mcp-proxy` + long-lived token.
3. One radio + a few real devices.
4. Voice + the three paths; measure latency.
5. Skills + the first real automations and dashboard.
6. Promote the proven config to the Orange Pi 5 Pro; tune the NPU as a separate step.

## Notes

This is a design document, not a tested deployment. Hardware specifics drift — verify NPU driver setup (`rkllm` / `rkllama`) and the current `mcp-proxy` flags against upstream when you build. Sources for the verified claims are listed in `ARCHITECTURE.md`.

## License

Not yet specified.
