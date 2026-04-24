# CLAUDE.md

## Project

Hearth (formerly Home HUD — systemd unit and logger namespace still use the old name for operational continuity) — a Raspberry Pi 5 voice assistant with an e-ink companion display. Listens for a wake word, processes spoken commands for built-in features (grocery lists, reminders, solar monitoring), and falls back to an LLM for general queries.

## Current Focus

The voice pipeline is functional end-to-end. Most interaction happens through the mobile PWA (Hearth) via Tailscale — the Pi itself is headless beyond the e-ink display.

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
src/telemetry/       — REST API + SPA static-asset serving
src/telemetry/auth.py         — Authentication (pairing codes, Tailscale identity)
src/telemetry/voice_handler.py — Browser voice endpoint
src/telemetry/static_assets.py — Loads + resolves web/dist/ for the SPA shell
src/utils/           — Shared helpers (VAD, prompt cache, tone gen)
web/                 — SvelteKit frontend (source) — see "Web frontend" below
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

The Pi serves the Hearth PWA via Tailscale at `https://homehud.tail5593cb.ts.net:8080` (hostname unchanged — the Tailscale machine is still named `homehud`). This is the **primary user interface** — most users interact through the browser voice tab on their phones, not directly at the Pi.

### User model

- **Admin**: first user to connect (auto-registered via Tailscale). Sees all five bottom-nav tabs (Voice · Grocery · Recipes · Garden · Admin) plus the admin console at `/admin/*`.
- **Regular user**: anyone added after the first user. Sees only the four user tabs (Voice · Grocery · Recipes · Garden). Admin-only API endpoints return 403.
- Auth is managed by `src/telemetry/auth.py`. User records in `data/auth.json`. First registered user gets `"admin": true` automatically.
- Tailscale users are auto-registered on first visit (no pairing code needed). Non-Tailscale users pair via a 6-digit code.
- Auth is opt-in (`web_auth_enabled` config param). When disabled, everyone is treated as admin.

### Design principles for the web UI

- **Mobile-first**: the Voice tab is the default landing page. UI is optimised for phone screens (large touch targets, safe-area insets, dvh heights).
- **Voice tab is the hero**: clean mic button + transcript, no telemetry clutter. No page header.
- **Two surfaces, one app**: user-facing at `/` (bottom nav), admin console at `/admin/*` (side nav on desktop, horizontal tab strip on mobile). One-tap exit "Back to app" link sits at the top of the admin nav.

### Web frontend (`web/`)

- **Stack**: SvelteKit 2 (adapter-static, SPA mode) · TypeScript · Tailwind v4 · Lucide icons · Vitest · Playwright.
- **Run locally**: `make web-dev` (Vite at :5173, proxies `/api` to `http://127.0.0.1:8080`). In another terminal: `make run`.
- **Build**: `make web-build` emits `web/dist/`. The Python server loads it on startup (look for "Loaded SPA shell" in logs). If `web/dist/` is missing, the server returns HTTP 503 for any non-API request with a hint to run the build.
- **Deploy**: CI builds the SPA in the cloud (`build-web` job runs in parallel with `lint-and-test`). The self-hosted Pi runner cleans `/tmp/web-dist`, downloads the artifact fresh, stages it at `/opt/homehud/web/dist.new/`, atomic-swaps it into `/opt/homehud/web/dist/` (keeping the previous build at `dist.prev/` for rollback), restarts the service, and probes `/api/health`. Rollback runs automatically on restart failure. The Pi has no Node.
- **Runtime config**: passed to the SPA via a `<script id="hud-config" type="application/json">{}</script>` tag that the Python server rewrites on every HTML response (see `_inject_runtime_config` in `web.py`). Read client-side via `$lib/config`.
- **Auth**: `$lib/auth/store` hydrates from `GET /api/auth/status` (auth-exempt). Bearer tokens in `localStorage.hud_auth_token`; `$lib/api/client.apiFetch` injects the header. Route guards in `$lib/auth/guard` gate authenticated routes and `/admin/*`.
- **Mobile testing**: web changes must be smoke-tested on a real phone via Tailscale before merge. The primary audience is mobile, not desktop browsers.
- **Adding a route**: create `web/src/routes/<path>/+page.svelte` (+ optional `+page.ts` for auth guard). Add a nav item to `web/src/lib/components/BottomNav.svelte` (user surface) or `AdminNav.svelte` (admin).

### Browser voice endpoint

`POST /api/voice` accepts raw PCM audio (int16, 16kHz mono), runs it through the same STT → IntentRouter → TTS pipeline as the hardware wake word, and returns WAV audio with `X-Transcription` and `X-Response-Text` headers. A shared `threading.Lock` serializes browser and hardware voice requests to prevent router state corruption.

### Telemetry API (admin-only)

Port 8080 is **HTTPS-only** (plain `http://` gets a connection reset). The dev machine is not on the Tailnet, so the `.ts.net` hostname does not resolve here — use `homehud.local` (mDNS) for reachability and `-k` to skip cert validation on the Tailscale-issued cert. Do **not** use `WebFetch` — it cannot resolve `.local`.

Two troubleshooting paths, depending on whether the endpoint needs auth:

**Public endpoints** (health only) — curl directly from the dev machine:
  - `curl -sk https://homehud.local:8080/api/health` — liveness probe

**Admin endpoints** (everything else) — require a bearer token over the wire, but requests originating from `127.0.0.1` on the Pi are auto-authenticated as the `"localhost"` user (`src/telemetry/web.py:94`). So the simplest path is SSH + loopback curl:
  - `ssh dchew@homehud.local 'curl -sk https://127.0.0.1:8080/api/stats'` — aggregate stats
  - `ssh dchew@homehud.local 'curl -sk https://127.0.0.1:8080/api/sessions?limit=10'` — recent sessions
  - `ssh dchew@homehud.local 'curl -sk https://127.0.0.1:8080/api/sessions/<uuid>'` — full session detail
  - `ssh dchew@homehud.local 'curl -sk https://127.0.0.1:8080/api/config'` — active config settings
  - `ssh dchew@homehud.local 'curl -sk https://127.0.0.1:8080/api/logs?lines=50&level=WARNING'` — recent logs

For anything the API does not expose, SSH gives direct access to logs (`sudo journalctl -u home-hud -f`) and the on-disk state (`/opt/homehud/data/{sessions.json,auth.json,config.json}`).

## Conventions

- Follow the abstraction pattern — interfaces that can be mocked for local dev and swapped for real hardware on the Pi. This applies to audio I/O, speech engines, and display backends alike.
- Keep Pillow as the rendering layer; all display UI is composed as PIL Images.
- Config goes through the `ConfigParam` registry in `config.py`. To add a new setting, add a `ConfigParam` entry to `CONFIG_REGISTRY` — it will automatically appear in the admin Config tab (served dynamically from `/api/config`).
- Priority: `data/config.json` > env vars (`.env`) > defaults. The config file is editable from the dashboard.
- `HUD_DISPLAY_MODE` (mock or eink) selects the display backend. See `.env.example` for all vars.
- **Web UI changes should be tested on a phone.** The primary audience is mobile users accessing via Tailscale, not desktop browsers. Test with the Voice tab as the landing page.

## Dependencies

- **Split requirements**: `requirements.txt` has core deps (CI + all environments). `requirements-pi.txt` adds voice/hardware deps (Pi only).
- **Python 3.11 on Pi**: `tflite-runtime` (via openwakeword) has no aarch64 wheels for 3.12+; `ctranslate2` (via faster-whisper) also caps at 3.11. The Pi venv uses Python 3.11.
- When adding a new dependency, check its Python version support. Pi-only deps go in `requirements-pi.txt`.
