#!/bin/bash
# Castellan — stop all services
echo "Stopping Castellan..."

sudo systemctl stop ha-voice.service 2>/dev/null
cd /home/boas/homeassistant && docker compose down

# Clean up any stray castellan containers
docker stop wyoming-openwakeword 2>/dev/null
docker rm wyoming-openwakeword 2>/dev/null

echo ""
echo "=== Castellan Status ==="
docker ps --filter "name=homeassistant|wyoming|ollama" --format "{{.Names}}: {{.Status}}" | grep -q . || echo "All containers stopped."
systemctl is-active ha-voice.service | xargs echo "ha-voice:"
echo ""
echo "Castellan stopped."
read -p "Press Enter to close..."
