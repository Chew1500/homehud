# CLAUDE.md

## Project

Home HUD — a Raspberry Pi 5 voice assistant with an e-ink companion display. Listens for a wake word, processes spoken commands for built-in features (grocery lists, reminders, solar monitoring), and falls back to an LLM for general queries.

## Current Focus

Building the voice pipeline: audio I/O → wake word detection → speech-to-text → intent parsing → text-to-speech. The e-ink display is secondary and deferred until the voice pipeline is functional.

## Stack

- Python 3.12 (Pi) / 3.11+ (local dev)
- Voice stack: openWakeWord, faster-whisper, Anthropic Claude API, Kokoro/Piper
- Pillow for e-ink rendering (secondary)
- ruff for linting, pytest for tests

## Module Map

```
src/config.py    — All env-based configuration (single source of truth)
src/main.py      — Entry point, render loop, signal handling
src/display/     — Display backends (e-ink, mock) behind BaseDisplay ABC
src/audio/       — [planned] Audio I/O (mic capture, speaker playback)
src/wake/        — [planned] Wake word detection
src/speech/      — [planned] STT and TTS engines
src/intent/      — [planned] Intent parsing and command routing
src/features/    — [planned] Built-in features (grocery, reminders, solar)
src/llm/         — [planned] LLM fallback for general queries
src/utils/       — [planned] Shared helpers (avoid duplicating across modules)
```

## Code Principles

- **DRY**: Before writing a new helper, check `src/utils/` and existing modules for prior art.
- **File size**: Target max ~1000 lines per file. Split when approaching this.
- **Single responsibility**: One concern per module — no god files.
- **New subsystems**: Each gets its own package (directory with `__init__.py`).
- **Abstraction pattern**: ABC base class → mock impl (local dev) + real impl (Pi hardware). Applies to audio, speech, display, and any new hardware interface.
- **Shared utilities**: Common helpers go in `src/utils/`, not copied between packages.
- **Consult `ARCHITECTURE.md`** before creating new files or modules.

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

- Follow the abstraction pattern — interfaces that can be mocked for local dev and swapped for real hardware on the Pi. This applies to audio I/O, speech engines, and display backends alike.
- Keep Pillow as the rendering layer; all UI is composed as PIL Images.
- Config goes through environment variables loaded in `config.py`.
- `HUD_DISPLAY_MODE` (mock or eink) selects the display backend. See `.env.example` for all vars.

## Dependencies

- **Split requirements**: `requirements.txt` has core deps (CI + all environments). `requirements-pi.txt` adds voice/hardware deps (Pi only).
- **Python <3.13 on Pi**: Voice libs (`tflite-runtime` via openwakeword, `ctranslate2` via faster-whisper) don't support Python 3.13+. The Pi venv uses Python 3.12.
- When adding a new dependency, check its Python version support. Pi-only deps go in `requirements-pi.txt`.
