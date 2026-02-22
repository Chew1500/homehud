#!/usr/bin/env bash
# deploy.sh — Called by GitHub Actions to deploy to the Pi.
# Expects SSH access to be configured via GH Actions secrets.

set -euo pipefail

PI_HOST="${PI_HOST:?Set PI_HOST environment variable}"
PI_USER="${PI_USER:-hud}"
APP_DIR="/opt/home-hud"

echo "==> Deploying to $PI_USER@$PI_HOST..."

ssh -o StrictHostKeyChecking=no "$PI_USER@$PI_HOST" << REMOTE
    set -euo pipefail

    echo "[1/4] Pulling latest code..."
    cd $APP_DIR
    git fetch origin main
    git reset --hard origin/main

    echo "[2/4] Updating dependencies..."
    $APP_DIR/venv/bin/pip install --quiet -r requirements.txt

    echo "[3/4] Running quick smoke test..."
    HUD_DISPLAY_MODE=mock $APP_DIR/venv/bin/python -c "from src.config import load_config; print('Config OK')"

    echo "[4/4] Restarting service..."
    sudo systemctl restart home-hud

    echo "==> Deploy complete!"
    systemctl status home-hud --no-pager -l
REMOTE
