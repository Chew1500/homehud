#!/usr/bin/env bash
# Tailscale connectivity watchdog — run via cron every 5 minutes.
# Restarts tailscaled if Tailscale reports as disconnected.
#
# Install: */5 * * * * /opt/homehud/scripts/tailscale-watchdog.sh

set -euo pipefail

TAG="tailscale-watchdog"

log() {
    logger -t "$TAG" "$1"
}

# Check if tailscaled is running at all
if ! systemctl is-active --quiet tailscaled; then
    log "tailscaled not running — starting"
    sudo systemctl start tailscaled
    sleep 5
fi

# Check Tailscale backend state
BACKEND_STATE=$(tailscale status --json 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('BackendState',''))" 2>/dev/null || echo "")

if [ "$BACKEND_STATE" = "Running" ]; then
    # All good — silent unless DEBUG
    exit 0
fi

log "Tailscale state is '$BACKEND_STATE' — restarting tailscaled"
sudo systemctl restart tailscaled
sleep 10

# Verify recovery
BACKEND_STATE=$(tailscale status --json 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('BackendState',''))" 2>/dev/null || echo "")
if [ "$BACKEND_STATE" = "Running" ]; then
    log "Tailscale recovered — now Running"
else
    log "WARNING: Tailscale still not Running after restart (state: $BACKEND_STATE)"
fi
