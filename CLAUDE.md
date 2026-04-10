# CLAUDE.md

## Project

Home HUD — a Raspberry Pi 5 voice assistant with an e-ink companion display. Listens for a wake word, processes spoken commands for built-in features (grocery lists, reminders, solar monitoring), and falls back to an LLM for general queries.

## Current Focus

The voice pipeline is functional end-to-end. Current focus is on the mobile PWA experience — the primary way users interact with Home HUD is through the browser voice interface on their phones via Tailscale, not directly at the Pi.

## Stack

- Python 3.11 (Pi) / 3.11+ (local dev)
- Voice stack: openWakeWord, ElevenLabs (STT/TTS), Anthropic Claude API
- Pillow for e-ink rendering
- Web: stdlib `http.server` with TLS, PWA (manifest + service worker)
- Network: Tailscale for remote access + HTTPS certs
- ruff for linting, pytest for tests

## Module Map

```
src/config.py        — All env-based configuration (single source of truth)
src/main.py          — Entry point, render loop, signal handling
src/display/         — Display backends (e-ink, mock) behind BaseDisplay ABC
src/audio/           — Audio I/O (mic capture, speaker playback)
src/wake/            — Wake word detection (openWakeWord)
src/speech/          — STT and TTS engines (ElevenLabs, Whisper, Kokoro)
src/intent/          — Intent parsing and command routing
src/features/        — Built-in features (grocery, reminders, solar, garden)
src/llm/             — LLM fallback for general queries (Claude)
src/telemetry/       — Web dashboard, API, telemetry storage
src/telemetry/ui/    — Dashboard UI modules (one file per tab)
src/telemetry/auth.py    — Authentication (pairing codes, Tailscale identity)
src/telemetry/voice_handler.py — Browser voice endpoint
src/telemetry/pwa.py     — PWA manifest, service worker, icon generation
src/utils/           — Shared helpers (VAD, prompt cache, tone gen)
```

## Code Principles

- **DRY**: Before writing a new helper, check `src/utils/` and existing modules for prior art.
- **File size**: Target max ~1000 lines per file. Split when approaching this.
- **Single responsibility**: One concern per module — no god files.
- **New subsystems**: Each gets its own package (directory with `__init__.py`).
- **Abstraction pattern**: ABC base class → mock impl (local dev) + real impl (Pi hardware). Applies to audio, speech, display, and any new hardware interface.
- **Shared utilities**: Common helpers go in `src/utils/`, not copied between packages.
- **Consult `ARCHITECTURE.md`** before creating new files or modules.
- **New features**: When adding a new feature to `src/features/`, also add it to the hardcoded `_INTENT_SYSTEM_PROMPT` in `src/llm/claude_llm.py` so the LLM intent parser knows it exists. The prompt is not auto-generated.

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
- SSH: `ssh dchew@homehud.local` — passwordless key auth, useful for troubleshooting the Pi directly
- Tailscale: Pi is on a Tailscale network; HTTPS via `tailscale cert`
- TLS certs: `/opt/homehud/certs/` (provisioned by `scripts/setup_tailscale_certs.sh`)

## Web Dashboard & PWA

The Pi serves a web dashboard as a PWA, accessible via Tailscale at `https://homehud.tail5593cb.ts.net:8080`. This is the **primary user interface** — most users interact with Home HUD through the browser voice tab on their phones, not directly at the Pi.

### User model

- **Admin**: The first user to connect (auto-registered via Tailscale identity). Sees all tabs: Voice, Garden, Overview, Sessions, Logs, Config, Voice Cache, Services.
- **Regular user**: Anyone added after the first user. Sees only **Voice** and **Garden** tabs. Admin-only API endpoints return 403.
- Auth is managed by `src/telemetry/auth.py`. User records are stored in `data/auth.json` on the Pi. The first registered user gets `"admin": true` automatically.
- Tailscale users are auto-registered on first visit (no pairing code needed). Non-Tailscale users pair via a 6-digit code.
- Auth is opt-in (`web_auth_enabled` config param). When disabled, everyone is treated as admin.

### Design principles for the web UI

- **Mobile-first**: The Voice tab is the default landing page. UI is optimized for phone screens (large touch targets, vertically centered layout, safe area insets for notches).
- **Voice tab is the hero**: Regular users see a clean mic button + transcript — no telemetry clutter. The header is hidden on the Voice tab.
- **Dashboard UI is modular**: Each tab is a separate file in `src/telemetry/ui/` exporting `TAB_HTML` and `TAB_JS` string constants. The `build_dashboard_html()` function in `__init__.py` composes them. No build step, no external static files.
- **New tabs**: Add a file in `src/telemetry/ui/`, export `TAB_HTML`/`TAB_JS`, import in `__init__.py`, add a button to `TAB_BAR` in `shell.py`, add a loader to `TAB_LOADERS`. If the tab is admin-only, add its ID to the `ADMIN_TABS` array in `shell.py`.

### Browser voice endpoint

`POST /api/voice` accepts raw PCM audio (int16, 16kHz mono), runs it through the same STT → IntentRouter → TTS pipeline as the hardware wake word, and returns WAV audio with `X-Transcription` and `X-Response-Text` headers. A shared `threading.Lock` serializes browser and hardware voice requests to prevent router state corruption.

### Telemetry API (admin-only)

Claude Code can access the API via `curl` from the dev machine (do NOT use `WebFetch` — it cannot resolve `.local` addresses):
  - `curl http://homehud.local:8080/api/stats` — aggregate stats
  - `curl http://homehud.local:8080/api/sessions?limit=10` — recent sessions
  - `curl http://homehud.local:8080/api/sessions/<uuid>` — full session detail
  - `curl http://homehud.local:8080/api/config` — active config settings
  - `curl http://homehud.local:8080/api/logs?lines=50&level=WARNING` — recent logs

## Conventions

- Follow the abstraction pattern — interfaces that can be mocked for local dev and swapped for real hardware on the Pi. This applies to audio I/O, speech engines, and display backends alike.
- Keep Pillow as the rendering layer; all display UI is composed as PIL Images.
- Config goes through the `ConfigParam` registry in `config.py`. To add a new setting, add a `ConfigParam` entry to `CONFIG_REGISTRY` — it will automatically appear in the dashboard Config tab.
- Priority: `data/config.json` > env vars (`.env`) > defaults. The config file is editable from the dashboard.
- `HUD_DISPLAY_MODE` (mock or eink) selects the display backend. See `.env.example` for all vars.
- **Web UI changes should be tested on a phone.** The primary audience is mobile users accessing via Tailscale, not desktop browsers. Test with the Voice tab as the landing page.

## Dependencies

- **Split requirements**: `requirements.txt` has core deps (CI + all environments). `requirements-pi.txt` adds voice/hardware deps (Pi only).
- **Python 3.11 on Pi**: `tflite-runtime` (via openwakeword) has no aarch64 wheels for 3.12+; `ctranslate2` (via faster-whisper) also caps at 3.11. The Pi venv uses Python 3.11.
- When adding a new dependency, check its Python version support. Pi-only deps go in `requirements-pi.txt`.
