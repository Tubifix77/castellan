#!/bin/bash
# Claude bridge (ARCHITECTURE.md §9) — stdio <-> HA's /api/mcp over streamable HTTP.
#
# The deployed copy had the long-lived token pasted inline. It is read from
# .env here instead: that file is gitignored, so this script can live in the
# repo without carrying a credential. Create the token in HA under
# Profile -> Security -> Long-lived access tokens, then put it in
# /home/boas/homeassistant/.env as HASS_TOKEN=...
set -euo pipefail

ENV_FILE="${ENV_FILE:-/home/boas/homeassistant/.env}"
[ -r "$ENV_FILE" ] || { echo "ha-mcp-proxy: cannot read $ENV_FILE" >&2; exit 1; }

HASS_TOKEN="$(sed -n 's/^HASS_TOKEN=//p' "$ENV_FILE" | head -1)"
[ -n "$HASS_TOKEN" ] || { echo "ha-mcp-proxy: HASS_TOKEN not set in $ENV_FILE" >&2; exit 1; }

exec /home/boas/homeassistant/venv/bin/mcp-proxy \
  --transport streamablehttp \
  --headers Authorization "Bearer ${HASS_TOKEN}" \
  http://localhost:8123/api/mcp
