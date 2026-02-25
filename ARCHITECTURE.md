# Architecture Reference

Consult this file before creating new files or modules. Update it as planned packages become real.

## Module Boundaries

### Existing

**`src/config.py`** — Configuration (single source of truth)
- Loads all env vars via `load_config() -> dict`
- Reads from `.env` file, falls back to defaults
- Every new setting goes here — never read `os.getenv()` elsewhere

**`src/main.py`** — Entry point
- Sets up logging, initializes display, runs the render loop
- Signal handling and graceful shutdown
- Should stay thin — delegates to subsystem packages

**`src/display/`** — Display backends
- `base.py`: `BaseDisplay` ABC — `show(image)`, `clear()`, `close()`
- `mock_display.py`: `MockDisplay` — saves PNGs to `output/` for local dev
- `eink_display.py`: `EinkDisplay` — drives Waveshare 7.5" tri-color e-Paper HAT
- `__init__.py`: factory function `get_display(config) -> BaseDisplay`

**`src/audio/`** — Audio I/O
- `base.py`: `BaseAudio` ABC — `record(duration) -> bytes`, `stream(chunk_duration_ms) -> Generator`, `play(data) -> None`, `play_async(data)`, `stop_playback()`, `is_playing() -> bool`, `close()`
- `mock_audio.py`: `MockAudio` — reads/writes WAV files for local dev
- `hardware_audio.py`: `HardwareAudio` — real mic/speaker via sounddevice
- `__init__.py`: factory function `get_audio(config) -> BaseAudio`
- Audio format: raw PCM bytes (16-bit int16, little-endian), 16kHz mono by default
- Async playback methods (`play_async`, `stop_playback`, `is_playing`) are concrete with default fallbacks — override for real non-blocking playback

**`src/voice_pipeline.py`** — Voice loop
- `start_voice_pipeline(audio, stt, wake, router, tts, config, running) -> Thread`
- Daemon thread: stream audio → detect wake word → play feedback tone → record (VAD or fixed) → transcribe → route (feature or LLM) → TTS → play (with barge-in support)
- Wake-word-triggered recording via continuous audio streaming
- Optional wake feedback tone, VAD-based dynamic recording, barge-in interruption
- Per-cycle exception handling so one bad recording doesn't kill the pipeline

**`src/wake/`** — Wake word detection
- `base.py`: `BaseWakeWord` ABC — `detect(audio_chunk) -> bool`, `reset()`, `close()`
- `mock_wake.py`: `MockWakeWord` — counter-based trigger after N chunks for local dev
- `oww_wake.py`: `OWWWakeWord` — real wake word detection via openWakeWord
- `__init__.py`: factory function `get_wake(config) -> BaseWakeWord`
- Input: raw PCM chunks (int16, 1280 samples / 80ms at 16kHz)

**`src/speech/`** — Speech (STT & TTS)
- `base.py`: `BaseSTT` ABC — `transcribe(audio: bytes) -> str`, `close()`
- `mock_stt.py`: `MockSTT` — returns configurable canned response for local dev
- `whisper_stt.py`: `WhisperSTT` — local Whisper model, converts PCM int16 → float32 → transcription
- `base_tts.py`: `BaseTTS` ABC — `synthesize(text) -> bytes`, `close()`
- `mock_tts.py`: `MockTTS` — generates silence for local dev
- `piper_tts.py`: `PiperTTS` — Piper ONNX voice synthesis (requires piper-tts>=1.4)
- `__init__.py`: factory functions `get_stt(config) -> BaseSTT`, `get_tts(config) -> BaseTTS`
- Input: raw PCM bytes from `audio.record()` (int16, little-endian, 16kHz mono)

**`src/llm/`** — LLM fallback
- `base.py`: `BaseLLM` ABC — `respond(text) -> str`, `close()`, plus concrete history methods: `_get_messages(text)`, `_record_exchange(user, assistant)`, `_expire_history()`, `clear_history()`
- `mock_llm.py`: `MockLLM` — canned responses for local dev
- `claude_llm.py`: `ClaudeLLM` — Anthropic Claude API with multi-turn conversation history
- `__init__.py`: factory function `get_llm(config) -> BaseLLM`

**`src/intent/`** — Intent parsing and command routing
- `router.py`: `IntentRouter` — iterates features in order, falls back to LLM
- `__init__.py`: factory function `get_router(config, features, llm) -> IntentRouter`
- Concrete class (no ABC) — a single router tries features then LLM

**`src/features/`** — Built-in features
- `base.py`: `BaseFeature` ABC — `matches(text) -> bool`, `handle(text) -> str`, `close()`
- `grocery.py`: `GroceryFeature` — regex-based matching, JSON file persistence
- `reminder.py`: `ReminderFeature` — timed reminders with background checker thread and `on_due` callback
- `repeat.py`: `RepeatFeature` — replays the last spoken response
- `solar.py`: `SolarFeature` — solar production queries, simple answers + LLM-assisted analysis
- Each feature self-selects via `matches()`, intent router dispatches to first match

**`src/enphase/`** — Enphase solar monitoring
- `base.py`: `BaseEnphaseClient` ABC — `get_production()`, `get_inverters()`, `check_health()`, `close()`
- `mock_client.py`: `MockEnphaseClient` — canned production data for local dev
- `client.py`: `EnphaseClient` — real IQ Gateway client with JWT auth via httpx
- `storage.py`: `SolarStorage` — SQLite storage for readings, inverter data, daily summaries
- `weather.py`: `get_current_weather()` — Open-Meteo weather helper for solar context
- `collector.py`: `SolarCollector` — background daemon thread that polls gateway and stores readings
- `__init__.py`: factory function `get_enphase_client(config) -> BaseEnphaseClient`

**`src/utils/`** — Shared helpers
- `__init__.py`: Package marker
- `tone.py`: `generate_tone(freq, duration_ms, sample_rate, volume) -> bytes` — sine wave PCM tone with fade-in/out
- `vad.py`: `VoiceActivityDetector` — energy-based (RMS) voice activity detection for dynamic recording
- Common logic used by 2+ packages goes here
- Do not duplicate helpers across packages — extract to utils instead

### Planned

## Key Patterns

### Abstraction pattern (ABC + factory)

Every hardware-dependent subsystem follows this structure:

```
src/<package>/
├── __init__.py       # Factory function: get_<thing>(config) -> Base<Thing>
├── base.py           # ABC with abstract methods
├── mock_<thing>.py   # Local dev implementation
└── <thing>.py        # Real hardware implementation
```

The factory in `__init__.py` reads config to choose the implementation. Real hardware imports are deferred (inside `if` branch) so local dev never needs hardware libraries.

See `src/display/` for the reference implementation of this pattern.

### Config loading

All configuration flows through `src/config.py`:
1. Add the env var with a default to `load_config()`
2. Add the var name to `.env.example`
3. Access via the config dict passed to your module — never call `os.getenv()` directly

### Factory imports

Heavy or hardware-specific dependencies are imported lazily inside the factory function, not at module top level. This keeps `make dev` and `make test` working without Pi hardware libraries installed.

## Where New Logic Goes

| You're adding...                  | It goes in...                                      |
|-----------------------------------|----------------------------------------------------|
| New hardware abstraction          | Own package with ABC base + mock/real impls         |
| New built-in voice feature        | `src/features/<feature>.py`                         |
| New env-based config setting      | `src/config.py` + `.env.example`                    |
| Helper used by 2+ packages        | `src/utils/`                                        |
| Helper used by 1 package only     | Private function in that package                    |
| New external API integration      | Own package under `src/` if substantial; `utils/` if trivial |
