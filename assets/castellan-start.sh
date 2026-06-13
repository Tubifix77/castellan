#!/bin/bash
# Castellan — start all services
cd /home/boas/homeassistant

echo "Starting Castellan..."
docker compose up -d
sudo systemctl start ha-voice.service

sleep 3

echo ""
echo "=== Castellan Status ==="
docker ps --filter "name=homeassistant|wyoming|ollama" --format "{{.Names}}: {{.Status}}"
systemctl is-active ha-voice.service | xargs echo "ha-voice:"
echo ""
echo "Ready. Say 'computer' to activate."
read -p "Press Enter to close..."
