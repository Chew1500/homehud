#!/usr/bin/env bash
# Set up hardware watchdog on Raspberry Pi.
# The bcm2835_wdt module triggers a hard reboot if the system hangs.
#
# Run once during Pi setup (or via bootstrap-pi.sh).
# Requires: sudo

set -euo pipefail

echo "=== Hardware Watchdog Setup ==="

# 1. Ensure the watchdog kernel module loads at boot
if ! grep -q "bcm2835_wdt" /etc/modules 2>/dev/null; then
    echo "bcm2835_wdt" | sudo tee -a /etc/modules > /dev/null
    echo "Added bcm2835_wdt to /etc/modules"
fi

# Load it now
sudo modprobe bcm2835_wdt 2>/dev/null || true

# 2. Install watchdog daemon
if ! command -v watchdog &> /dev/null; then
    sudo apt-get update -qq
    sudo apt-get install -y -qq watchdog
    echo "Installed watchdog package"
fi

# 3. Configure watchdog
# Get default gateway for ping check
GATEWAY=$(ip route show default | awk '/default/ {print $3}' | head -1)

sudo tee /etc/watchdog.conf > /dev/null << EOF
# Hardware watchdog device
watchdog-device = /dev/watchdog
watchdog-timeout = 15

# Reboot if system is unresponsive
realtime = yes
priority = 1

# Ping the default gateway to detect network hangs
ping = ${GATEWAY:-192.168.1.1}
ping-count = 3
interval = 10

# Temperature limit (85C is Pi throttle point)
temperature-sensor = /sys/class/thermal/thermal_zone0/temp
max-temperature = 80000

# Memory check — reboot if allocator is completely stuck
min-memory = 1
EOF

echo "Wrote /etc/watchdog.conf (gateway ping: ${GATEWAY:-192.168.1.1})"

# 4. Prevent systemd from claiming /dev/watchdog (let watchdog daemon handle it)
if grep -q "^#RuntimeWatchdogSec=" /etc/systemd/system.conf 2>/dev/null; then
    sudo sed -i 's/^#RuntimeWatchdogSec=.*/RuntimeWatchdogSec=0/' /etc/systemd/system.conf
    echo "Disabled systemd RuntimeWatchdog (requires reboot to release /dev/watchdog)"
fi

# 5. Enable and start
sudo systemctl enable watchdog
if sudo systemctl restart watchdog 2>&1; then
    echo "Hardware watchdog active."
else
    echo "Watchdog daemon could not start (device may be busy until reboot)."
    echo "It will start automatically on next boot."
fi

echo "After reboot, hardware watchdog will auto-reboot the Pi on:"
echo "  - OS hang (watchdog timer expires after 15s)"
echo "  - Network unreachable for ~30s (gateway ping fails)"
echo "  - CPU temp > 80C"

# 5. Enable persistent journal (so we can see previous boot logs)
if [ ! -d /var/log/journal ] || [ -z "$(ls -A /var/log/journal 2>/dev/null)" ]; then
    sudo mkdir -p /var/log/journal
    sudo systemd-tmpfiles --create --prefix /var/log/journal
    sudo systemctl restart systemd-journald
    echo "Enabled persistent journal — previous boot logs now preserved"
fi

echo "=== Watchdog setup complete ==="
