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
    export CASTELLAN_ESCALATION=1
else
    echo "  Mode: LOCAL ONLY"
    export CASTELLAN_ESCALATION=0
fi

# Write mode flag for ha_voice.py to read
echo "$CASTELLAN_ESCALATION" > /tmp/castellan_escalation

echo ""
echo "  Starting services..."
cd /home/boas/homeassistant
docker compose up -d
sudo systemctl start ha-voice.service

sleep 4

echo ""
echo "  ═══════════════════════════════════"
echo "  Castellan Status"
echo "  ═══════════════════════════════════"
docker ps --filter "name=homeassistant|wyoming|ollama" --format "  {{.Names}}: {{.Status}}"
systemctl is-active ha-voice.service | xargs echo "  ha-voice:"
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
