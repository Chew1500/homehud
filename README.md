# Home HUD

A Raspberry Pi-powered e-ink dashboard combining solar energy monitoring, grocery lists, reminders, and voice control.

## Hardware

- Raspberry Pi 5 (Pi OS Lite)
- Waveshare 7.5" tri-color e-Paper HAT
- Waveshare USB Sound Card + Speaker

## Local Development

```bash
# Clone and set up
git clone https://github.com/<your-username>/home-hud.git
cd home-hud

# Create virtual environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements-dev.txt

# Configure
cp .env.example .env

# Render a single frame
make dev
# -> Frame saved to output/latest.png

# Run the main loop
make run

# Lint & test
make lint
make test
```

## Deploy to Pi

### First-time Pi setup

```bash
ssh pi@<your-pi-ip> 'bash -s' < scripts/bootstrap-pi.sh
```

### CI/CD (GitHub Actions)

Pushes to `main` auto-deploy to the Pi. Set these GitHub repo secrets:

| Secret | Description |
|---|---|
| `PI_HOST` | Pi's IP or hostname |
| `PI_USER` | Deploy user (default: `hud`) |
| `PI_SSH_KEY` | Private SSH key for the deploy user |

### Manual deploy

```bash
PI_HOST=<pi-ip> bash scripts/deploy.sh
```

## Project Structure

```
home-hud/
├── src/
│   ├── main.py              # Entry point & render loop
│   ├── config.py             # Environment-based configuration
│   └── display/
│       ├── base.py           # Abstract display interface
│       ├── mock_display.py   # PNG output for local dev
│       └── eink_display.py   # Waveshare e-ink driver
├── scripts/
│   ├── bootstrap-pi.sh       # One-time Pi setup
│   └── deploy.sh             # Deployment script
├── systemd/
│   └── home-hud.service      # Auto-start on boot
├── tests/
└── .github/workflows/
    └── deploy.yml             # CI/CD pipeline
```

## Roadmap

- [x] Phase 1: Project scaffolding, mock display, CI/CD
- [ ] Phase 2: Live Enphase energy data
- [ ] Phase 3: Audio I/O setup
- [ ] Phase 4: Speech-to-text (Whisper)
- [ ] Phase 5: Text-to-speech (Kokoro/Piper)
- [ ] Phase 6: Intent parsing (Claude API)
- [ ] Phase 7: Wake word detection (openWakeWord)
- [ ] Phase 8: Polish & enclosure

