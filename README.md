# Hearth

A Raspberry Pi-powered voice assistant with an e-ink companion display. Responds to wake words, handles built-in commands (grocery lists, reminders, solar monitoring), and falls back to an LLM for general queries. Installed as a PWA on your phone via Tailscale.

_(Previously "Home HUD" — the repo directory, systemd unit, and some internal namespaces still use the old name for operational continuity.)_

## Hardware

- Raspberry Pi 5 (Pi OS Lite)
- Waveshare USB Sound Card (speaker + mic input)
- Waveshare 7.5" tri-color e-Paper HAT

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
│   ├── config.py            # Environment-based configuration
│   ├── voice_pipeline.py    # Wake word → record → transcribe loop
│   ├── display/
│   │   ├── base.py          # Abstract display interface
│   │   ├── mock_display.py  # PNG output for local dev
│   │   └── eink_display.py  # Waveshare e-ink driver
│   ├── audio/
│   │   ├── base.py          # Abstract audio interface
│   │   ├── mock_audio.py    # Silence/WAV files for local dev
│   │   └── hardware_audio.py # Real mic/speaker via sounddevice
│   ├── speech/
│   │   ├── base.py          # Abstract STT interface
│   │   ├── mock_stt.py      # Canned responses for local dev
│   │   ├── whisper_stt.py   # Local Whisper transcription
│   │   ├── base_tts.py      # Abstract TTS interface
│   │   └── mock_tts.py      # Silence output for local dev
│   ├── llm/
│   │   ├── base.py          # Abstract LLM interface
│   │   ├── mock_llm.py      # Canned responses for local dev
│   │   └── claude_llm.py    # Anthropic Claude API
│   ├── intent/
│   │   └── router.py        # Intent router (features → LLM fallback)
│   ├── features/
│   │   ├── base.py          # Abstract feature interface
│   │   └── grocery.py       # Grocery list management
│   └── wake/
│       ├── base.py          # Abstract wake word interface
│       ├── mock_wake.py     # Counter-based trigger for local dev
│       └── oww_wake.py      # openWakeWord detection
├── scripts/
│   ├── bootstrap-pi.sh
│   └── deploy.sh
├── systemd/
│   └── home-hud.service
├── tests/
└── .github/workflows/
    └── deploy.yml
```

## Roadmap

- [x] Phase 1: Project scaffolding, mock display, CI/CD
- [x] Phase 2: Audio I/O setup (mic input, speaker output)
- [x] Phase 3: Wake word detection (openWakeWord)
- [x] Phase 4: Speech-to-text (Whisper)
- [ ] Phase 5: Intent parsing & built-in commands
  - [x] Intent router (feature matching → LLM fallback)
  - [x] Grocery list management
  - [x] Reminders
  - Solar production queries
  - [x] General LLM fallback (Claude API)
- [x] Phase 6: Text-to-speech (Kokoro)
- [ ] Phase 7: Live Enphase energy data integration
- [ ] Phase 8: E-ink display UI
- [ ] Phase 9: Polish & enclosure

