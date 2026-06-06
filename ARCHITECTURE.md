# Castellan — Architecture

**Version:** 0.3  
**Status:** Design phase — complete, not yet built.  
**Last reviewed:** 2026-06-06

## Legend

- ✅ **Verified** — confirmed against a cited source (see [Sources](#sources)).
- 🔷 **Recommendation** — a design choice derived from the reference hardware and the verified facts, not itself a sourced claim.

---

## 1. Overview

A fully local, open-source smart home with an AI layer. The design separates three concerns that are usually conflated:

1. **Running the home** — must be local, always-on, fast, reliable.
2. **Understanding free-form speech** — occasional; tolerates being slower.
3. **Building and maintaining the system** — rare, latency-insensitive, human-in-the-loop.

Each maps to a different engine, and the whole design follows from matching the engine to how often the task occurs. The home runs on a dedicated, low-power single-board computer. Everyday voice and control never leave the LAN. A larger AI assistant (Claude) is used only to build and repair the system, never in the live voice loop.

---

## 2. Physical topology

| Machine | Role | Runs |
|---|---|---|
| **Orange Pi 5 Pro** (RK3588S, 6 TOPS NPU, 16 GB, ~10 W) | Production brain, always on | HA Container (ARM64), Piper (TTS), Whisper.cpp / Speech-to-Phrase (STT), a ~3B LLM on the NPU, Zigbee USB coordinator, Mosquitto |
| **x86 Linux laptop** (Debian 12, always-on) | Testbed | The whole stack is built and validated here first, then promoted to the Pi |
| **Desktop with a discrete GPU** | Optional dev/batch only | Testing larger (e.g. 12B) models, batch generation, occasional camera AI. Never an always-on dependency. |
| **ESP32 ×N** (WiFi, ESPHome) | Edge / satellites | BLE proxy, voice satellite, CYD touch panel, e-ink status display |
| **Claude Desktop** | Build assistant (cold path) | `mcp-proxy` → HA `/api/mcp` for live control; SSH → `/config` for editing YAML |

**Dev → prod flow:** build and prove on the x86 laptop (more forgiving during development), then promote the verified configuration to the Orange Pi. The Pi is only touched once something works on the testbed.

---

## 3. The three-path AI model

The single idea the whole design rests on: **a command costs almost nothing if Home Assistant's grammar can match it — so let the grammar handle the 95%.** That is why no large GPU is needed.

### Hot path — deterministic intent (~95% of commands)
Home Assistant's sentence matcher plus **Speech-to-Phrase** handle known commands ("turn off the living-room lights") in well under 100 ms. No LLM, no GPU. Runs on the Pi. ✅ Speech-to-Phrase is HA's lightweight, grammar-based STT for known commands.

### Warm path — small local LLM (free-form speech, rare)
When speech doesn't match the grammar, a small ~3B model (Llama 3.2 3B / Qwen2.5 3B) on the RK3588 NPU handles it at ~15–20 tok/s — a usable voice assistant. Fully local, infrequently used. ✅ RK3588 NPU benchmarks.

### Cold path — Claude (rare, human-in-loop)
Building automations, dashboards, ESPHome firmware, debugging logs, proposing self-heal fixes. Latency-insensitive, always with a human present. A cloud call here is fine because it is rare and out of the live loop; it would be wrong in the hot path (slow, and it breaks "fully local").

**Routing principle:** optimise each path for its dominant constraint — hot for speed, warm for locality, cold for quality. Escalate upward only when the path below can't handle the request.

---

## 4. Home Assistant core

- **HA Container (Docker)** runs on the Pi in production and the laptop in test — the same image, two architectures (ARM64 / x86). On a Linux host, a USB Zigbee/Z-Wave dongle passes through directly with `--device`. ✅ Conversely, HA in Docker on Windows/WSL2 cannot pass USB through (WSL2 has no USB stack), so a dongle is unusable there without USB/IP hacks.
- **Automations** are Claude-generated YAML, validated with `ha core check` on the testbed before being promoted.
- **Dashboards** (Lovelace, YAML-mode) tailored to your rooms; Claude can generate cards. A floor-plan SVG dashboard is a later extension.
- **Mosquitto (MQTT)** as a separate container is the backbone for ESPHome, Zigbee2MQTT, and sensors.
- **`/config` is a git repo.** Claude commits before changing anything, so a broken automation can be rolled back.

**ARM gotcha to test for:** most HA components are architecture-neutral, but a custom add-on or Python wheel may lack an ARM64 build. The testbed→prod split surfaces those on the Pi in isolation instead of mid-deploy.

Example `docker-compose.yml` (works on both architectures; Docker selects the right image):

```yaml
services:
  homeassistant:
    image: ghcr.io/home-assistant/home-assistant:stable
    volumes: ["./config:/config"]
    devices: ["/dev/ttyUSB0:/dev/ttyUSB0"]   # Zigbee coordinator
    network_mode: host
    restart: unless-stopped
```

---

## 5. Voice pipeline (entirely on the Pi)

The Wyoming protocol glues the components together as network services that HA combines into one Assist pipeline.

- **openWakeWord** — wake-word detection; light enough to run on the Pi or on the ESP32 satellite itself.
- **Speech-to-Phrase** (hot) — grammar-based STT for known commands; very fast on modest hardware. ✅
- **Whisper.cpp** (warm) — free-form STT; runs on the RK3588 ARM cores (`base` / `small`). ✅ Only needed when Speech-to-Phrase doesn't match.
- **Piper** (TTS) — built for edge devices/SBCs, fast on the Pi; many voices. A GLaDOS voice is a community Piper model. ✅
- **Assist pipeline** — HA orchestrates wake → STT → intent/LLM → TTS. Two pipelines can coexist: a fast local one and one with the 3B fallback.

**Why no external GPU:** an earlier draft put GPU Whisper on a desktop, but that binds the hot path to a machine that isn't always on. On the Pi, Speech-to-Phrase handles known commands quickly, Whisper.cpp covers free speech, Piper replies — all local, all always-on. CPU Whisper-large is the 2–4 s latency people complain about; the grammar path avoids it entirely.

**The one fiddly bit:** getting the 3B model onto the NPU needs the `rkllm` toolkit and the right drivers — documented as finicky. Get it working on the laptop first with a simple CPU/Ollama setup, then do NPU tuning on the Pi as a separate, isolated step. If the NPU misbehaves, the 3B still runs (slower) on the Pi's CPU.

---

## 6. Edge layer — ESP32, displays, radios

- **ESP32 BLE proxy** — ESPHome's `bluetooth_proxy` turns a cheap ESP32 into a network BLE radio. **BLE only** (not Zigbee). HA aggregates all proxies. ✅
- **Zigbee coordinator** — a USB stick (e.g. SkyConnect / ZBT-1) in the Pi → ZHA or Zigbee2MQTT; Linux passes USB through directly. A networked coordinator is an option if the radio must live elsewhere.
- **CYD touch panel** — "Cheap Yellow Display" as a wall panel; Claude writes the ESPHome LVGL UI from your entities.
- **E-ink status display** — low-power info panel; ESPHome with deep-sleep between updates.
- **Voice satellite** — ESP32-S3 with mic + speaker as a room satellite (a DIY alternative to a dedicated voice puck).

**Important distinction:** `bluetooth_proxy` is BLE only — an ESP32 is **not** a Zigbee coordinator. Zigbee needs a USB stick or a dedicated networked coordinator. Don't conflate the two radios.

**Claude's role here:** describe the board → Claude generates complete ESPHome YAML with the correct pins; you flash it. A reusable ESPHome skill makes this repeatable.

---

## 7. Claude integration (the "Pro" layer)

Two separate channels, two purposes.

### Runtime control — official HA MCP Server ✅
Home Assistant ships an official **MCP Server** integration that exposes `/api/mcp` (Streamable HTTP) and lets MCP clients act through the Assist API. **You do not write a custom server.** Because the home stays local (no public URL), bridge it to Claude Desktop with a local **`mcp-proxy`** gateway and a **long-lived access token** — no internet exposure.

Add it alongside any other MCP server in `claude_desktop_config.json`:

```json
"homeassistant": {
  "command": "npx",
  "args": ["mcp-proxy", "http://<HA-IP>:8123/api/mcp"],
  "env": { "API_ACCESS_TOKEN": "<long-lived-token>" }
}
```

> Verify the current `mcp-proxy` flag/env-var names against its README — they drift between versions. The mechanism (stdio ↔ SSE + token) is verified; the exact CLI detail should be checked at build time.

### Config editing — SSH
The MCP controls running entities but does not edit YAML files. For writing automations and dashboards, Claude uses SSH: read/write `/config`, validate, restart — on the laptop (test) and the Pi (prod). This is the heavy "build the system" work.

### Skills
A Home Assistant skill and an ESPHome skill (`SKILL.md`) capture conventions — entity naming, automation patterns, board definitions — so Claude is consistent across sessions.

---

## 8. Self-healing — done right, not autonomous

Self-heal fires rarely (it's the exception). That single fact dictates the design:

- At low volume, **token cost is negligible** — an occasional paid Claude call for a broken automation costs pennies.
- So optimising self-heal for "free-tier token leeching" optimises the variable that doesn't matter (cost) at the expense of the one that does (**reliability**).
- **At low volume, reliability is king, not price.** A cheap-but-flaky pipeline trades away the only property you cared about.

And an autonomous agent is the wrong *shape*, not just overkill: you don't want something with its own goals rewriting your home while you sleep. The right model is a **human-gated approve loop**.

**Tiered design:**

- **Tier 0 — Prevent.** Most "healing" is hygiene: validate-on-write + git rollback catch breakage *before* it reaches prod. Prevention beats healing.
- **Tier 1 — Detect & notify.** A simple log watcher catches a failing automation + context and notifies you. No autonomy — just a heads-up.
- **Tier 2 — Human-gated fix.** You ask Claude to look; it reads the error (SSH/MCP), proposes a fix, you approve, it applies and validates. Reliable because you're in the loop.

No autonomous rewrites, no cross-provider routing rig. Keep that complexity for projects where it belongs.

---

## 9. Other future ideas

- **AI energy management** — spot-price-based control (e.g. via a free national grid-price API) shifting consumption to cheap hours; Claude builds the optimisation logic. Likely the highest-value addition.
- **Floor-plan dashboard** — sketch/upload a plan → Claude generates an interactive SVG floor plan with entities placed correctly.
- **Installer package** — a self-extracting script that stands up the whole compose stack + HA config on a fresh machine, with a wizard for IPs and dongles.

---

## 10. Deployment decision — where the brain lives

| Option | Verdict | Why |
|---|---|---|
| **x86 Linux laptop** | **Start / testbed** | Already on, SSH-ready, zero cost; x86 is forgiving during development. Build and prove the stack here. Not the final prod home (shared resources). |
| **Orange Pi 5 Pro (RK3588S)** | **Production target** 🔷 | Dedicated, always-on, ~10 W, silent, native USB; NPU runs the 3B and accelerates wake/vision. Cheap and future-proof. Trade-offs: NPU drivers are finicky; ARM may lack the odd wheel. |
| **Gaming PC in the hot path** | **No** | Not always on → the home dies when it's off; ~300 W to transcribe "turn off the lights"; competes with games for the GPU. Fine as an *optional* dev/batch box only. |

---

## 11. Voice flow example — "turn off the living-room lights"

```
Wake (ESP32 / Pi)
  -> Speech-to-Phrase (Pi, hot)
  -> Intent match (HA, Pi)
  -> [3B fallback only if free-form] (Pi, warm)
  -> Service call (HA, Pi)
  -> Zigbee (USB / proxy)
  -> Piper TTS reply (Pi)
```

---

## 12. Gaps this design closes

| Gap | How it's closed |
|---|---|
| Complex setup, YAML errors | Claude writes config via SSH, validates with `ha core check`, explains errors plainly |
| Voice latency (2–4 s) | Speech-to-Phrase on the Pi handles 95% instantly; 3B only for free speech; no GPU |
| Custom hardware firmware | ESPHome skill: describe the board → complete ESPHome YAML with correct pins |
| Always-on dependency on a PC | Dedicated ~10 W Orange Pi carries the whole hot path locally |
| Cost vs reliability for self-heal | Volume-aware routing: self-heal is rare → optimise reliability, keep it human-gated |
| Custom MCP server effort | HA's official `mcp_server` exists — only `mcp-proxy` + token needed |

---

## Sources

Retrieved 2026-06-06. The ✅ items above are backed by these.

1. Home Assistant — **MCP Server** integration (`/api/mcp`, `mcp-proxy`, OAuth / long-lived token, Claude Desktop example): https://www.home-assistant.io/integrations/mcp_server/
2. Home Assistant — **Ollama** integration (local conversation agent, Assist API control): https://www.home-assistant.io/integrations/ollama/
3. Home Assistant — **local voice / Assist** (Speech-to-Phrase or Whisper + Piper): https://www.home-assistant.io/voice_control/voice_remote_local_assistant/
4. RK3588 NPU / RKLLM throughput (~10–15 tok/s for 1.1B, ~15–20 tok/s for 3B; "fiddly" drivers): community reports incl. tinycomputers.io, xda-developers.com, forum.aqara.com, cnx-software.com
5. Whisper.cpp + Piper on ARM64 / RK3588 (Piper built for SBCs): turingpi.com and others
6. HA Container vs Supervised + WSL2 USB-passthrough limitation: reddit r/homeassistant, homeautomationguy.io
7. ESPHome **Bluetooth Proxy** (ESP32 BLE proxy, BLE only): https://esphome.io/components/bluetooth_proxy/
8. RK3588 vs RK3588S (the difference is I/O — PCIe / SATA / display / camera / Ethernet — not the NPU, CPU, GPU, or memory controller): Radxa wiki, Rock5/RK3588_vs_RK3588S

The topology choice (Pi = prod brain, laptop = testbed, gaming GPU out of the live path), the three-path model, and the self-heal tiering are 🔷 recommendations derived from the reference hardware and the verified facts — not sourced claims. Verify NPU setup and `mcp-proxy` flags against upstream when building.
