#!/usr/bin/env bash
# bootstrap-pi.sh — Run this once on a fresh Raspberry Pi OS Lite install.
# Usage: curl -sSL <raw github url> | bash
#   or:  ssh pi@<ip> 'bash -s' < scripts/bootstrap-pi.sh

set -euo pipefail

APP_DIR="/opt/home-hud"
APP_USER="hud"
REPO="https://github.com/$(whoami)/home-hud.git"  # Update with your GitHub username

echo "==> Home HUD Pi Bootstrap"
echo ""

# --- System packages ---
echo "[1/6] Installing system packages..."
sudo apt-get update -qq
sudo apt-get install -y -qq \
    python3 python3-venv python3-pip python3-dev \
    python3.12 python3.12-venv python3.12-dev \
    git \
    libopenjp2-7 libtiff6 libatlas-base-dev \
    libportaudio2 ffmpeg \
    fonts-dejavu-core \
    > /dev/null

# --- Enable SPI (required for e-ink display) ---
echo "[2/6] Enabling SPI interface..."
if ! grep -q "^dtparam=spi=on" /boot/firmware/config.txt 2>/dev/null; then
    echo "dtparam=spi=on" | sudo tee -a /boot/firmware/config.txt > /dev/null
    echo "  SPI enabled (reboot required for hardware access)"
else
    echo "  SPI already enabled"
fi

# --- Create app user ---
echo "[3/6] Setting up app user..."
if ! id "$APP_USER" &>/dev/null; then
    sudo useradd -r -m -s /bin/bash "$APP_USER"
    sudo usermod -aG spi,gpio,audio "$APP_USER"
    echo "  Created user: $APP_USER"
else
    echo "  User $APP_USER already exists"
fi

# --- Clone / update repo ---
echo "[4/6] Setting up application directory..."
if [ -d "$APP_DIR" ]; then
    echo "  $APP_DIR already exists, pulling latest..."
    sudo -u "$APP_USER" git -C "$APP_DIR" pull --ff-only
else
    sudo mkdir -p "$APP_DIR"
    sudo chown "$APP_USER:$APP_USER" "$APP_DIR"
    sudo -u "$APP_USER" git clone "$REPO" "$APP_DIR"
fi

# --- Python venv ---
echo "[5/6] Setting up Python virtual environment..."
sudo -u "$APP_USER" python3.12 -m venv "$APP_DIR/venv"
sudo -u "$APP_USER" "$APP_DIR/venv/bin/pip" install --quiet --upgrade pip
sudo -u "$APP_USER" "$APP_DIR/venv/bin/pip" install --quiet -r "$APP_DIR/requirements-pi.txt"

# --- Install systemd service ---
echo "[6/6] Installing systemd service..."
sudo cp "$APP_DIR/systemd/home-hud.service" /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable home-hud.service

echo ""
echo "==> Bootstrap complete!"
echo ""
echo "Next steps:"
echo "  1. Copy .env.example to $APP_DIR/.env and configure it"
echo "     sudo -u $APP_USER cp $APP_DIR/.env.example $APP_DIR/.env"
echo "     sudo -u $APP_USER nano $APP_DIR/.env"
echo "     (set HUD_DISPLAY_MODE=eink when display is connected)"
echo ""
echo "  2. For voice pipeline, set in .env:"
echo "     HUD_AUDIO_MODE=hardware"
echo "     HUD_WAKE_MODE=oww"
echo "     HUD_STT_MODE=whisper"
echo ""
echo "  3. Reboot to activate SPI and audio group:"
echo "     sudo reboot"
echo ""
echo "  4. After reboot, start the service:"
echo "     sudo systemctl start home-hud"
echo "     sudo journalctl -u home-hud -f"
echo ""
