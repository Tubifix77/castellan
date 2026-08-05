#!/bin/bash
# Castellan — start all services

echo ""
echo "  ╔═══════════════════════════════════╗"
echo "  ║         C A S T E L L A N         ║"
echo "  ╚═══════════════════════════════════╝"
echo ""
echo "  [E] Enable cloud escalation (free-tier LLM)"
echo "  [any / timeout] Local only — default"
echo ""

ESCALATION=false
for i in 5 4 3 2 1; do
    printf "\r  Local only in %s... (press E to enable cloud)  " "$i"
    if read -r -s -n 1 -t 1 key; then
        if [[ "$key" == "e" || "$key" == "E" ]]; then
            ESCALATION=true
            break
        fi
    fi
done
echo ""
echo ""

if [ "$ESCALATION" = true ]; then
    echo "  Mode: LOCAL + CLOUD ESCALATION"
    FLAG=1
else
    echo "  Mode: LOCAL ONLY"
    FLAG=0
fi

# ha_voice.py reads this at startup, so it must be written before the unit
# starts. /run is tmpfs — a reboot drops the opt-in back to local-only.
sudo mkdir -p /run/castellan
printf '%s\n' "$FLAG" | sudo tee /run/castellan/escalation >/dev/null

echo ""
echo "  Starting services..."
cd /home/boas/homeassistant
docker compose up -d
# enable, not start: matches `compose up -d`, which also survives a reboot
sudo systemctl enable --now ha-voice.service

sleep 4

echo ""
echo "  ═══════════════════════════════════"
echo "  Castellan Status"
echo "  ═══════════════════════════════════"
docker ps --filter "name=homeassistant|wyoming|ollama" --format "  {{.Names}}: {{.Status}}"
echo "  ha-voice: $(systemctl is-active ha-voice.service) ($(systemctl is-enabled ha-voice.service))"
echo "  ───────────────────────────────────"
if [ "$ESCALATION" = true ]; then
    echo "  Cloud escalation: ENABLED"
else
    echo "  Cloud escalation: disabled"
fi
echo "  ═══════════════════════════════════"
echo ""
echo "  Ready. Say 'computer' to activate."
echo ""
read -p "  Press Enter to close..."
