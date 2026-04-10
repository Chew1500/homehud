#!/usr/bin/env bash
# Provision TLS certificates via Tailscale for the Home HUD dashboard.
#
# Usage:
#   sudo ./scripts/setup_tailscale_certs.sh <hostname>
#
# Example:
#   sudo ./scripts/setup_tailscale_certs.sh homehud
#
# This generates Let's Encrypt certs at /opt/homehud/certs/ using
# Tailscale's built-in HTTPS cert provisioning. The certs auto-renew
# when this script is re-run (e.g. via systemd timer or cron).
#
# After running, update .env:
#   HUD_WEB_TLS_CERT=/opt/homehud/certs/<hostname>.crt
#   HUD_WEB_TLS_KEY=/opt/homehud/certs/<hostname>.key

set -euo pipefail

HOSTNAME="${1:-}"
CERT_DIR="/opt/homehud/certs"

if [ -z "$HOSTNAME" ]; then
    echo "Usage: $0 <tailscale-hostname>"
    echo ""
    echo "Run 'tailscale status' to see your machine's hostname."
    exit 1
fi

# Ensure tailscale is available
if ! command -v tailscale &>/dev/null; then
    echo "Error: tailscale not installed"
    exit 1
fi

# Create cert directory
mkdir -p "$CERT_DIR"
chmod 750 "$CERT_DIR"

# Get the full domain name
FQDN=$(tailscale status --json | python3 -c "
import json, sys
data = json.load(sys.stdin)
dns = data.get('MagicDNSSuffix', '')
print(f'${HOSTNAME}.{dns}') if dns else print('${HOSTNAME}')
" 2>/dev/null || echo "$HOSTNAME")

echo "Provisioning certs for: $FQDN"

# Generate certs
tailscale cert \
    --cert-file "$CERT_DIR/$HOSTNAME.crt" \
    --key-file "$CERT_DIR/$HOSTNAME.key" \
    "$FQDN"

# Set permissions for the hud user
chown hud:hud "$CERT_DIR/$HOSTNAME.crt" "$CERT_DIR/$HOSTNAME.key"
chmod 640 "$CERT_DIR/$HOSTNAME.key"

echo ""
echo "Certs written to:"
echo "  Certificate: $CERT_DIR/$HOSTNAME.crt"
echo "  Private key: $CERT_DIR/$HOSTNAME.key"
echo ""
echo "Add to /opt/homehud/.env:"
echo "  HUD_WEB_TLS_CERT=$CERT_DIR/$HOSTNAME.crt"
echo "  HUD_WEB_TLS_KEY=$CERT_DIR/$HOSTNAME.key"
echo "  HUD_WEB_TAILSCALE_HOSTNAME=$FQDN"
echo ""
echo "Then restart: sudo systemctl restart home-hud"
