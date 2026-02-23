# CLAUDE.md

## Project

Home HUD — a Raspberry Pi 5 voice assistant with an e-ink companion display. Listens for a wake word, processes spoken commands for built-in features (grocery lists, reminders, solar monitoring), and falls back to an LLM for general queries.

## Current Focus

Building the voice pipeline: audio I/O → wake word detection → speech-to-text → intent parsing → text-to-speech. The e-ink display is secondary and deferred until the voice pipeline is functional.

## Stack

- Python 3.13 (Pi) / 3.11+ (local dev)
- Voice stack: openWakeWord, Whisper, Anthropic Claude API, Kokoro/Piper
- Pillow for e-ink rendering (secondary)
- ruff for linting, pytest for tests

## Project Structure

```
src/
├── main.py              # Entry point & render loop
├── config.py             # Env-based config, reads .env
└── display/
    ├── base.py           # Abstract display interface (800x480)
    ├── mock_display.py   # Saves PNGs to output/ for local dev
    └── eink_display.py   # Waveshare driver stub
```

`config.py` loads from `.env` — see `.env.example` for available vars. The display backend is selected by `HUD_DISPLAY_MODE` (mock or eink).

## Commands

```bash
make dev          # Render single frame to output/latest.png
make run          # Run the main loop
make lint         # ruff check src/ tests/
make test         # pytest tests/ -v
```

## Deployment

- App: `/opt/homehud` on Pi, runs as `hud` system user
- Venv: `/opt/homehud/venv`
- Config: `/opt/homehud/.env`
- Service: `home-hud.service` (systemd)
- CI/CD: Push to `main` → lint/test on GitHub cloud → deploy via self-hosted runner on Pi
- Logs: `sudo journalctl -u home-hud -f`

## Conventions

- New features should follow the abstraction pattern — interfaces that can be mocked for local dev and swapped for real hardware on the Pi. This applies to audio I/O, speech engines, and display backends alike.
- Keep Pillow as the rendering layer; all UI is composed as PIL Images
- Config goes through environment variables loaded in `config.py`