#!/bin/bash
# Castellan — stop all services
echo "Stopping Castellan..."

# disable, not stop: a plain stop is transient, so the unit came back on the
# next boot and ran unattended for weeks. Mirrors `compose down`.
sudo systemctl disable --now ha-voice.service 2>/dev/null
sudo rm -f /run/castellan/escalation
cd /home/boas/homeassistant && docker compose down

# Clean up any stray castellan containers
docker stop wyoming-openwakeword 2>/dev/null
docker rm wyoming-openwakeword 2>/dev/null

echo ""
echo "=== Castellan Status ==="
docker ps --filter "name=homeassistant|wyoming|ollama" --format "{{.Names}}: {{.Status}}" | grep -q . || echo "All containers stopped."
echo "ha-voice: $(systemctl is-active ha-voice.service) ($(systemctl is-enabled ha-voice.service) — will not return on boot)"
echo ""
echo "Castellan stopped."
read -p "Press Enter to close..."
