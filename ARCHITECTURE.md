# Castellan — Architecture

**Version:** 0.6
**Status:** Build phase — roadmap steps 1–5 deployed and working on the host; step 6+ (escalation) remains design.
**Last reviewed:** 2026-06-13

## Changelog

**v0.6 (2026-06-13):**
- **Step 5 shipped — warm path.** Ollama (Docker, `restart=always`, 2 CPU / 1.5 GB RAM cap) serves `qwen2.5:1.5b` at `localhost:11434`. `ha_voice.py` escalates to Ollama directly (OpenAI `/v1/chat/completions`) whenever HA's conversation API returns `response_type: error` — this covers both `no_intent_match` and `no_valid_targets`. Portability seam: `OLLAMA_URL` + `OLLAMA_MODEL` constants in `ha_voice.py`, one-line swap when the backend changes. Cold-start ~22 s on CPU, warm ~4 s.

**v0.5 (2026-06-13):**
- **Steps 1–4 shipped.** HA Container, the Claude bridge (MCP + SSH), three WiZ bulbs, and the voice core run on the laptop. A snapshot of the working config lives in [`ha-config/`](ha-config/).
- **Voice core as-built diverges from the v0.4 design (§6).** openWakeWord and wyoming-satellite are out — the wake word never triggered reliably on this hardware/accent. Wake + STT now run in one custom loop (`ha-config/ha_voice.py`) on faster-whisper `base` (int8, CPU): biased decoding for the wake word, fuzzy entity normalization for commands, HA Conversation REST for intent, Wyoming Piper for TTS. Speech-to-Phrase stays deployed for HA's own Assist pipeline but the live loop bypasses it.
- **Latency honesty (§3, §15).** Deterministic intent matching is still LLM-free and instant, but as-built STT costs seconds of CPU; wake-to-action measures ~12 s. Speech-to-Phrase remains the documented sub-100 ms upgrade path for known phrases.
- **Legend extended** with DEPLOYED for as-built facts of the running system.

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
- DEPLOYED — as-built fact of the running system (config tracked in [`ha-config/`](ha-config/)).

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
| **Debian laptop** (x86, always-on) — *the host* | Everything | HA, Piper (TTS), faster-whisper (wake word + STT, as deployed), Speech-to-Phrase (HA Assist pipeline), the local small LLM (CPU, step 5), all as background services; Mosquitto when the first MQTT device arrives |
| **Gaming PC (RTX)** | **Build-time only — never runtime** | Where you sit to build Castellan: Claude Desktop, testing. Must not run any part of the live house. |
| **ESP32 xN** (WiFi, ESPHome) | Edge / satellites | BLE proxy, voice satellite, displays. Wake-word can run on the satellite. |
| **Cloud free-tier LLM** (APEX-style) | Escalation only, optional | Reached only for hard free-form queries that pass the egress boundary (section 4). Off -> house still works. |
| **Claude Desktop** | Build and human-gated repair | `mcp-proxy` -> HA `/api/mcp` (live control) + SSH -> `/config` (editing). Cold path. |

**Why one host, and why not the gaming PC:** a smart home must be always-on and predictable. A gaming PC is neither — it powers down, gets busy, or reboots at random, and you've ruled it out for running the house. The Debian laptop is the always-on box, so everything lives there.

**Future (documented, not built): a dedicated SoC.** An Orange Pi 5 Pro (RK3588S, 6 TOPS NPU) or similar would be the ideal permanent home — silent, ~10 W, and its NPU makes the slow part fast. Migrating = move the stack to the SoC and repoint one URL (section 7). No Castellan code is SoC-specific today.

---

## 3. The query path — slow escalation

A spoken request walks up only as far as it needs to:

1. **Hot — deterministic (~95%).** HA's sentence matcher resolves known commands ("turn off the lights") with no LLM and no network. **VERIFIED** As deployed, the STT in front of it is faster-whisper on CPU, so wake-to-action measures ~12 s — the intent match is instant, the transcription isn't. **DEPLOYED** Speech-to-Phrase (grammar-based, sub-100 ms on modest hardware **VERIFIED**) remains the latency upgrade path for known phrases.
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

**As deployed (step 4):** one custom loop — [`ha-config/ha_voice.py`](ha-config/ha_voice.py), a systemd service — owns the mic and does wake word + STT with **faster-whisper `base`** (int8, CPU). **DEPLOYED**
- **Wake** ("computer"): 2 s sliding windows with overlap, decoding biased toward the wake word. (openWakeWord never triggered reliably here, and whisper-`tiny` mangles the accent — `base` + bias is what works.)
- **Command capture:** adaptive noise floor — the mic line carries constant hum/hiss, so chunks are high-passed at 250 Hz and silence is detected relative to a rolling floor, with a single filter pass over the whole utterance before transcription.
- **Intent:** fuzzy entity normalization (rebuild the garbled transcript as a canonical "turn on/off \<entity\>"), then HA's Conversation REST API — deterministic, no LLM.
- **Reply:** Wyoming **Piper** TTS (`en_US-lessac-medium`), played locally; the mic is drained afterwards so the loop can't wake on its own voice.

**Still deployed alongside (Wyoming):** **Piper** (TTS, above — fast on CPU/SBC, many voices; a GLaDOS voice is a community model **VERIFIED**) and **Speech-to-Phrase**, wired into HA's own Assist pipeline (UI/companion voice) but bypassed by the live loop; it remains the sub-100 ms STT option for known phrases. **VERIFIED**

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
Wake "computer" (laptop mic, faster-whisper)        [as deployed]
  -> chime; capture until silence (adaptive floor)
  -> faster-whisper base STT + fuzzy entity normalization
  -> HA Conversation API intent match  -> act (deterministic, local)
     | (only if free-form / no match — step 5, not yet built)
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
| Voice latency (2-4 s) | Deterministic intents stay LLM-free; as-built whisper STT costs seconds — Speech-to-Phrase is the documented instant path for known phrases |
| Custom hardware firmware | ESPHome skill: describe board -> complete YAML |
| Random always-on dependency | Single always-on host (laptop); gaming PC excluded |
| Hard free-form on weak hardware | Slow-escalation: local first, optional bounded cloud burst |
| Cloud privacy/availability | Egress boundary (section 4): text-only, knowledge-only, opt-in, graceful fallback |
| Cost vs reliability for faults | Self-heal stays human-gated Claude, not a free-tier rig |

---

## Roadmap

1. **HA on the laptop** (Docker), `/config` under git. Background service, restart-on-boot. ✅ *shipped 2026-06*
2. **Claude bridge:** HA MCP server + `mcp-proxy` + long-lived token. ✅ *shipped 2026-06*
3. **One radio + a few devices.** ✅ *shipped 2026-06 — three WiZ WiFi bulbs; no Zigbee radio yet*
4. **Deterministic voice core** — the usable MVP: voice control + status. ✅ *shipped 2026-06-13, as-built per §6 (faster-whisper loop + Piper; Speech-to-Phrase held in reserve)*
5. **Warm path** — local small LLM behind the OpenAI-compatible seam; resource-capped. ✅ *shipped 2026-06-13 — Ollama + qwen2.5:1.5b; ha_voice.py escalates to Ollama on any HA intent error*
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

Host model (single laptop; SoC as future), the slow-escalation query path, the egress boundary, and the background-service/resource design are REC items derived from the setup and verified facts. The as-built voice loop (§6) is DEPLOYED fact, tracked in `ha-config/`, not a sourced claim. Verify NPU setup and `mcp-proxy` flags against upstream when building.
