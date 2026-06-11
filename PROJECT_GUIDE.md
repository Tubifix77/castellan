# Castellan — project guide for Claude Code

Castellan is a fully local, single-host smart-home system: Home Assistant + voice + a small local LLM, all running as background services on one always-on Linux box (the Debian laptop). This file orients you. **The full spec is `ARCHITECTURE.md` (v0.4) — read it before building.**

## Status
Design phase complete (architecture v0.4). **No code yet.** Next step is the build, starting with the deterministic voice core (Roadmap step 4 in ARCHITECTURE.md).

## Hard constraints — do not violate without asking
- **Single host.** Everything runs on the always-on Debian laptop. The gaming PC is NEVER a runtime dependency (build-time only).
- **Local-first.** Everyday operation must work with no internet. Only the optional tier-3 escalation may leave the LAN, and only under the egress boundary (ARCHITECTURE.md section 4): text only (never audio), general-knowledge only (never home state / security / control), redacted, opt-in, graceful fallback.
- **Portability seam.** HA's conversation agent points at ONE OpenAI-compatible endpoint URL. Keep the model backend swappable (localhost CPU now, NPU/SoC later). No Pi/NPU-specific code yet.
- **Resource caps.** The host also runs another always-on service. Cap the LLM (small model + CPU/RAM limits) so it can't starve it.
- **Self-heal is human-gated** (propose -> approve), never autonomous; a separate channel from the voice escalation.
- **Validate-on-write.** Run `ha core check` before anything goes live; keep `/config` under git.

## Build order (see ARCHITECTURE.md Roadmap)
1. HA on the laptop (Docker), `/config` under git, as a background service (restart-on-boot).
2. Claude bridge: HA `mcp_server` + `mcp-proxy` + long-lived token.
3. One radio + a few devices (Zigbee USB or an ESP32 BLE proxy).
4. Deterministic voice core (Speech-to-Phrase + Piper + wake word) — the first usable MVP. Build this first.
5. Warm path: local small LLM behind the endpoint seam, resource-capped.
6. Escalation (optional): APEX-style cloud behind the egress boundary; a toggle.
7. Skills + first automations.
8. Later: migrate to a dedicated SoC (repoint one URL); energy management.

## Conventions
- License Apache 2.0. Not affiliated with Home Assistant / the Open Home Foundation.
- Secrets stay out of git (`.gitignore` guards `secrets.yaml`, `.env`).
- Work in small, reviewed commits.

## Not yet in the repo
- `docs/architecture.html` — an optional visual version of the architecture. Not generated yet; build it fresh from ARCHITECTURE.md v0.4 if wanted (do not reuse the old chat artifact — it is stale and contains personal details).
