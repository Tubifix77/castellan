# Castellan — Architecture

**Version:** 0.4
**Status:** Design phase — nearly build-ready. No code yet.
**Last reviewed:** 2026-06-11

## Changelog

**v0.4 (2026-06-11):**
- **Single host.** Castellan runs entirely on one always-on machine — the Debian laptop. The gaming PC is explicitly **out of the runtime** (it must not be a dependency that runs the house at random times); its only role is build-time (Claude Desktop, testing).
- **Slow-escalation query path.** Free-form queries walk up: deterministic -> local small LLM -> an APEX-style free-tier cloud model for the hard ones. Automatic, with a strict egress boundary (section 4).
- **Escalation boundary added** (section 4) — the one path that leaves the LAN, deliberately fenced: text-only, general-knowledge-only, graceful fallback, opt-in.
- **Background-service design added** (section 10) — daemon, auto-start, headless, resource caps for coexisting with another always-on service on the same box.
- **Self-heal unchanged and clarified:** stays human-gated Claude — a *different channel* from the voice escalation, and deliberately not an APEX-style free-tier rig (reliability beats cost when something fires rarely).
- **NPU/SoC stays a documented, zero-rework migration** via the endpoint seam (section 7), not code maintained now.

**v0.3:** dedicated-brain framing, three-path AI, voice fully local, official HA MCP server, human-gated self-heal.

## Legend
- VERIFIED — confirmed against a cited source (see Sources).
- REC — recommendation / design choice derived from the reference setup and the verified facts.

---

## 1. Overview

A fully local, single-host smart home with an AI layer. Everyday operation never leaves the LAN. The internet is touched only as an *optional* last resort for the rare free-form question the local model can't handle (section 4). One machine runs everything; the design is portable by architecture, so it can later move to a dedicated low-power SoC with an NPU by changing one address and no code (section 7).

Three concerns, deliberately separated:
1. **Running the home** — local, always-on, instant, scripted.
2. **Answering free-form speech** — occasional; local first, cloud only if it must, bounded.
3. **Building and repairing the system** — rare, human-in-the-loop (Claude).

---

## 2. Host and topology

| Where | Role | Runs |
|---|---|---|
| **Debian laptop** (x86, always-on) — *the host* | Everything | HA, Mosquitto, Piper (TTS), Whisper.cpp / Speech-to-Phrase (STT), the local small LLM (CPU), all as background services |
| **Gaming PC (RTX)** | **Build-time only — never runtime** | Where you sit to build Castellan: Claude Desktop, testing. Must not run any part of the live house. |
| **ESP32 xN** (WiFi, ESPHome) | Edge / satellites | BLE proxy, voice satellite, displays. Wake-word can run on the satellite. |
| **Cloud free-tier LLM** (APEX-style) | Escalation only, optional | Reached only for hard free-form queries that pass the egress boundary (section 4). Off -> house still works. |
| **Claude Desktop** | Build and human-gated repair | `mcp-proxy` -> HA `/api/mcp` (live control) + SSH -> `/config` (editing). Cold path. |

**Why one host, and why not the gaming PC:** a smart home must be always-on and predictable. A gaming PC is neither — it powers down, gets busy, or reboots at random, and you've ruled it out for running the house. The Debian laptop is the always-on box, so everything lives there.

**Future (documented, not built): a dedicated SoC.** An Orange Pi 5 Pro (RK3588S, 6 TOPS NPU) or similar would be the ideal permanent home — silent, ~10 W, and its NPU makes the slow part fast. Migrating = move the stack to the SoC and repoint one URL (section 7). No Castellan code is SoC-specific today.

---

## 3. The query path — slow escalation

A spoken request walks up only as far as it needs to:

1. **Hot — deterministic (~95%).** HA's sentence matcher + Speech-to-Phrase handle known commands ("turn off the lights") in under 100 ms. No LLM, no network. Scripted, local, instant. **VERIFIED**
2. **Warm — local small LLM.** Free-form the local model can manage. A small model on the laptop CPU (NPU later). Local, private; on old hardware, *slow* — seconds, not instant. That's acceptable: free-form is the "ask and wait a moment" feature, not the daily driver.
3. **Escalation — APEX-style cloud, optional.** When the local model can't answer a hard free-form question well, escalate to a free-tier cloud LLM (APEX-style key/provider rotation). Subject to the egress boundary (section 4) and graceful fallback. **REC**

**Routing principle:** escalate only when the tier below can't cope. Most input never leaves tier 1; most of the rest is handled by tier 2; tier 3 is the rare hard question. Optimise hot for speed, warm for locality, escalation for capability.

**Distinct from self-heal (section 11):** this escalation is for *voice knowledge queries*. Operational faults (a broken automation) are a different channel — human-gated Claude, not the free-tier rig.

---

## 4. The escalation boundary — the one thing that leaves the LAN

Tier-3 escalation is the only part of Castellan that touches the internet, so it is deliberately fenced. **REC**

- **Text only, never audio.** Speech-to-text happens locally; only the transcribed query (plus minimal, scrubbed context) is ever sent. Raw home audio never leaves the house.
- **General knowledge only — never home state, control, or security.** "What can I cook with chicken and rice?" may escalate. "Is the back door unlocked?", "who's home?", anything revealing occupancy/security/personal data, and all control commands stay local (control is deterministic anyway). An allow/deny classification decides what is escalatable.
- **Redaction.** Names, addresses, and identifiers are stripped before egress.
- **Graceful fallback.** If the cloud tier is rate-limited, down, or offline, fall back to the local model's best attempt or an honest "I can't answer that right now." The house never breaks because the internet is unavailable — only the rare hard query degrades.
- **Opt-in and configurable.** Escalation is a toggle. Off -> Castellan is 100% local and simply gives smaller answers to hard questions. Provider(s) and keys via an APEX-style keychain.
- **Provider terms are a config-time choice.** Free tiers differ on whether they train on inputs; pick accordingly, knowing only non-sensitive general-knowledge text ever leaves.

This is the deliberate trade Castellan makes: locality is the default and the principle; the cloud is a bounded, optional escape hatch for capability on hard questions — not a pipe for the room's audio.

---

## 5. Home Assistant core

- **HA Container (Docker)** on the laptop. Native Linux -> a USB Zigbee/Z-Wave dongle passes through with `--device`. **VERIFIED** (HA in Docker on Windows/WSL2 can't pass USB through — WSL2 has no USB stack — one more reason the house lives on the Linux laptop, not the Windows gaming PC.)
- **Automations** — Claude-generated YAML, validated with `ha core check` before going live; `/config` under git for rollback.
- **Dashboards** — Lovelace (YAML-mode) + custom cards; floor-plan SVG later.
- **Mosquitto (MQTT)** — backbone for ESPHome, Zigbee2MQTT, sensors.

(ARM note for the future SoC: most HA components are arch-neutral, but a custom add-on or Python wheel may lack an ARM64 build — surfaces at migration, in isolation.)

---

## 6. Voice pipeline (local on the laptop)

Wyoming protocol glues these as local services HA combines into one Assist pipeline:
- **openWakeWord** — wake word; light, can also run on the ESP32 satellite.
- **Speech-to-Phrase** (hot STT) — grammar-based, fast on modest hardware; carries tier 1. **VERIFIED**
- **Whisper.cpp** (warm STT) — free-form transcription on the laptop CPU (`base`/`small`). **VERIFIED**
- **Piper** (TTS) — fast on CPU/SBC, many voices; a GLaDOS voice is a community model. **VERIFIED**

All STT/TTS stays local regardless of escalation — only *text* from tier 2/3 ever leaves (section 4).

---

## 7. The portability seam — one endpoint, any host

The mechanism behind "runs everywhere, best on an NPU": **HA's conversation agent points at an OpenAI-compatible URL.** What serves that URL is the only host-specific choice. **REC**

- **Now (laptop):** `localhost` CPU Ollama (or llama.cpp) serving a small model.
- **Later (SoC):** rkllm serving a 3B on the RK3588 NPU (~15-20 tok/s **VERIFIED**). Same URL, faster answers.
- **Escalation (tier 3):** a separate cloud endpoint, gated by section 4.

Migration to a dedicated SoC = relocate the stack and repoint one address. No Castellan code is NPU- or Pi-specific today; the NPU is the upgrade that turns tier-2 from slow to snappy.

---

## 8. Edge layer — ESP32, displays, radios

- **ESP32 BLE proxy** — ESPHome `bluetooth_proxy` turns a cheap ESP32 into a network BLE radio. **BLE only**, not Zigbee. HA aggregates all proxies. **VERIFIED**
- **Zigbee coordinator** — a USB stick in the laptop -> ZHA or Zigbee2MQTT; Linux passes USB through directly. (A networked coordinator if the radio must sit elsewhere.)
- **CYD touch panel** / **e-ink status** / **ESP32-S3 voice satellite** — ESPHome firmware Claude generates from your entities; you flash it.

Reminder: `bluetooth_proxy` is BLE only — an ESP32 is **not** a Zigbee coordinator. Don't conflate the radios.

---

## 9. Claude integration (build and repair — cold path)

Two channels, both human-driven, never in the live loop:
- **Runtime control — official HA MCP Server.** **VERIFIED** HA's `mcp_server` exposes `/api/mcp`; bridge it to Claude Desktop with local `mcp-proxy` + a long-lived token (no public URL). Claude reads live state and calls services via the Assist API.
- **Config editing — SSH.** MCP controls entities but doesn't edit YAML; Claude edits `/config`, validates, restarts over SSH.

> Verify the current `mcp-proxy` flag/env names against its README — they drift. Mechanism (stdio<->SSE + token) is verified.

---

## 10. Background service and resources

Castellan runs as a **dedicated background service**, not something you launch. **REC**
- **Auto-start, headless, restart-on-failure** — Docker `restart=always` (and/or systemd units for non-container pieces). Survives reboots, runs with no one logged in.
- **Resource caps — load-bearing, not an afterthought.** The laptop already runs another always-on service (a separate creature project). Two always-on workloads on old hardware is fine *if* bounded: the small LLM is the heavy one, so it gets a small model + CPU/RAM limits so it can't starve the other service. The deterministic hot path is cheap and unaffected.
- **The real limiter is RAM/cores, not CUDA.** HA + Whisper + Piper + a small LLM + the other service on an old box is doable with discipline; the LLM size is the dial that matters.

---

## 11. Self-heal — human-gated (unchanged)

Operational faults are rare, so **reliability beats cost** — which is exactly why this is *not* an APEX-style free-tier rig (that would optimise the variable that doesn't matter here). It's human-gated Claude:
- **Tier 0 — Prevent:** validate-on-write + git rollback catch most breakage before it goes live.
- **Tier 1 — Notify:** a log watcher flags a failing automation + context. No autonomy.
- **Tier 2 — Human-gated fix:** you ask Claude; it reads the error, proposes a fix, you approve, it applies and validates.

No autonomous rewrites. (The voice escalation in sections 3-4 is a separate channel with separate reasoning.)

---

## 12. Future

- **Dedicated SoC (Pi 5 Pro / RK3588S, 6 TOPS NPU):** the natural permanent home; makes tier-2 free-form fast. Zero-rework migration via section 7.
- **AI energy management:** spot-price control via a free national grid API -> shift load to cheap hours. Likely the highest-value automation.
- **Floor-plan dashboard, installer package** as later polish.

---

## 13. Deployment decision

| Option | Verdict | Why |
|---|---|---|
| **Debian laptop** | **The host (now)** | Always-on, x86, zero cost, already in use. Runs the whole stack. Shared with another service -> resource caps (section 10). |
| **Dedicated SoC (Pi 5 Pro)** | **Future target** | Silent, ~10 W, NPU makes free-form fast. Zero-rework migration. Buy when it's worth a dedicated box. |
| **Gaming PC in the runtime** | **Excluded** | Not always-on; busy/rebooting at random; ruled out. Build-time only (Claude Desktop, testing). |

---

## 14. Voice flow — "turn off the living-room lights"

```
Wake (ESP32 / laptop)
  -> Speech-to-Phrase (laptop, hot)
  -> Intent match (HA, laptop)         -> done (instant, local)
     | (only if free-form / no match)
  -> local small LLM (laptop, warm)    -> answer if it can
     | (only if too hard AND passes egress boundary, section 4)
  -> cloud free-tier LLM (escalation)  -> answer, else graceful fallback
  -> Piper TTS reply (laptop)
```

---

## 15. Gaps this design closes

| Gap | How |
|---|---|
| Complex setup, YAML errors | Claude writes/validates config via SSH |
| Voice latency (2-4 s) | Speech-to-Phrase handles ~95% instantly; LLM only for free-form |
| Custom hardware firmware | ESPHome skill: describe board -> complete YAML |
| Random always-on dependency | Single always-on host (laptop); gaming PC excluded |
| Hard free-form on weak hardware | Slow-escalation: local first, optional bounded cloud burst |
| Cloud privacy/availability | Egress boundary (section 4): text-only, knowledge-only, opt-in, graceful fallback |
| Cost vs reliability for faults | Self-heal stays human-gated Claude, not a free-tier rig |

---

## Roadmap

1. **HA on the laptop** (Docker), `/config` under git. Background service, restart-on-boot.
2. **Claude bridge:** HA MCP server + `mcp-proxy` + long-lived token.
3. **One radio + a few devices** (Zigbee USB or an ESP32 BLE proxy).
4. **Deterministic voice core** — Speech-to-Phrase + Piper + wake word. The usable MVP: instant control + status. *Ship this first.*
5. **Warm path** — local small LLM behind the OpenAI-compatible seam; resource-capped.
6. **Escalation (optional)** — APEX-style cloud tier behind the egress boundary; toggle.
7. **Skills + automations** — HA/ESPHome skills; first real automations via Claude.
8. **Later:** migrate to a dedicated SoC (repoint one URL); energy management.

---

## Sources

Retrieved 2026-06-06. VERIFIED items are backed by these.
1. HA **MCP Server** integration: https://www.home-assistant.io/integrations/mcp_server/
2. HA **Ollama** integration (local conversation agent): https://www.home-assistant.io/integrations/ollama/
3. HA **local voice / Assist** (Speech-to-Phrase or Whisper + Piper): https://www.home-assistant.io/voice_control/voice_remote_local_assistant/
4. RK3588 NPU / RKLLM throughput (~15-20 tok/s for 3B; fiddly drivers): tinycomputers.io, xda-developers.com, forum.aqara.com, cnx-software.com
5. Whisper.cpp + Piper on ARM64 / RK3588: turingpi.com and others
6. HA Container vs Supervised + WSL2 USB-passthrough limit: reddit r/homeassistant, homeautomationguy.io
7. ESPHome **Bluetooth Proxy** (BLE only): https://esphome.io/components/bluetooth_proxy/
8. RK3588 vs RK3588S (difference is I/O, not NPU/CPU/GPU/memory): Radxa wiki

Host model (single laptop; SoC as future), the slow-escalation query path, the egress boundary, and the background-service/resource design are REC items derived from the setup and verified facts. Verify NPU setup and `mcp-proxy` flags against upstream when building.
