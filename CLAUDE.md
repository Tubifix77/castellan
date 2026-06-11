# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repository is

Castellan is the **architecture and design** for a fully local, single-host smart home (Home Assistant + local voice + a small local LLM). It is **documentation-only and in the design phase (v0.4) — there is no code yet.** No build, test, lint, or run tooling exists. Work here today means editing Markdown design docs, not programs; treat changes as spec edits that must stay internally consistent and well-reasoned.

## The documents (and which is canonical)

- **`ARCHITECTURE.md` — the source of truth (full spec, v0.4).** Read it before any design change or build work. Numbered sections; the voice flow and "gaps closed" tables tie it together. Hard constraints, build order, and all load-bearing claims live here.
- **`README.md` — public-facing summary.** Same facts, audience-facing tone.

These two overlap deliberately (hardware table, roadmap/build order, constraints, version). **A fact changed in one must be propagated to the other** — they drift otherwise.

## Discipline when editing the docs

- **Preserve the VERIFIED / REC legend.** Every load-bearing claim in `ARCHITECTURE.md` is tagged VERIFIED (cited in the Sources section) or REC (a design choice). Don't promote REC → VERIFIED without adding a real source; tag new claims accordingly.
- **Keep the header block current.** When the architecture changes, bump `Version`, `Last reviewed`, and add a Changelog entry at the top of `ARCHITECTURE.md` (and the version mention in README).
- **Facts drift — flag them, don't assert them.** Upstream specifics (`mcp-proxy` flags, `rkllm`/`rkllama` NPU setup, model throughput) change. The docs already carry "verify against upstream" caveats; keep that posture rather than stating volatile specifics as settled.
- **No personal details in committed docs.** The old chat-generated `architecture.html` is stale and contains personal data — do not reuse it; build any `docs/` artifact fresh from `ARCHITECTURE.md`.

## Architectural invariants (any future code must respect these)

These constrain everything that gets built; full reasoning in the cited `ARCHITECTURE.md` sections.

- **Single host.** Everything runs on the always-on Debian laptop. The gaming PC is build-time only and must **never** be a runtime dependency.
- **Local-first.** Everyday operation works with no internet. Only the optional tier-3 escalation may leave the LAN, and only through the **egress boundary** (`ARCHITECTURE.md` §4): text-only (never audio), general-knowledge only (never home state/security/control), redacted, opt-in, graceful fallback.
- **Portability seam (§7).** HA's conversation agent points at **one** OpenAI-compatible endpoint URL. Keep the model backend swappable (localhost CPU now, NPU/SoC later). Write **no** Pi/NPU-specific code — migration must stay "relocate the stack, repoint one URL."
- **Resource caps (§10).** The host shares the box with another always-on service. The local LLM is the heavy one — bound it (small model + CPU/RAM limits) so it can't starve the neighbor.
- **Self-heal is human-gated (§11):** detect → propose → human approves → apply. Never autonomous, and a separate channel from the voice escalation.
- **Validate-on-write.** Keep `/config` under git; run `ha core check` before anything goes live.

## Big picture (spans multiple sections)

Castellan separates **three concerns into three channels**, each optimized for a different variable:
1. **Running the home** — local, always-on, deterministic, instant (optimize for speed).
2. **Answering free-form speech** — the **slow-escalation path** (§3): hot deterministic intents (~95%, sub-100 ms) → warm local small LLM → optional cloud escalation, walking up only as far as needed (optimize for locality).
3. **Building/repairing** — cold-path Claude, two channels, never in the live loop (§9): the official HA **MCP server** (`mcp-proxy` + long-lived token) for live control, and **SSH** to `/config` for YAML editing (optimize for reliability — which is why self-heal is *not* the free-tier cloud rig).

## Commands / build

There are **no build, test, or lint commands** — nothing to run yet. The only established commands are git (work in small, reviewed commits) and, once HA exists, `ha core check` as the validate-on-write gate. The build itself starts with HA Container (Docker, `restart=always`) on the Linux laptop, `/config` under git — see the Roadmap (`ARCHITECTURE.md` §Roadmap), which ships the **deterministic voice core first** (step 4) as the MVP.

## Conventions

- Apache 2.0. Independent community project — **not** affiliated with Home Assistant or the Open Home Foundation.
- Secrets stay out of git; `.gitignore` guards `secrets.yaml`, `.env`, and `*.local`.
