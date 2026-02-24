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
- `base.py`: `BaseAudio` ABC — `record(duration) -> bytes`, `stream(chunk_duration_ms) -> Generator`, `play(data) -> None`, `close()`
- `mock_audio.py`: `MockAudio` — reads/writes WAV files for local dev
- `hardware_audio.py`: `HardwareAudio` — real mic/speaker via sounddevice
- `__init__.py`: factory function `get_audio(config) -> BaseAudio`
- Audio format: raw PCM bytes (16-bit int16, little-endian), 16kHz mono by default

**`src/voice_pipeline.py`** — Voice loop
- `start_voice_pipeline(audio, stt, wake, llm, tts, config, running) -> Thread`
- Daemon thread: stream audio → detect wake word → record → transcribe → LLM → TTS → play
- Wake-word-triggered recording via continuous audio streaming
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
- `base.py`: `BaseLLM` ABC — `respond(text) -> str`, `close()`
- `mock_llm.py`: `MockLLM` — canned responses for local dev
- `claude_llm.py`: `ClaudeLLM` — Anthropic Claude API
- `__init__.py`: factory function `get_llm(config) -> BaseLLM`

### Planned

**`src/intent/`** — Intent parsing and command routing
- Takes transcribed text, determines which feature handles it
- Routes to built-in features or LLM fallback
- Rule-based initially, can evolve to NLU

**`src/features/`** — Built-in features
- Submodules: `grocery.py`, `reminders.py`, `solar.py`
- Each feature has a consistent interface for the intent router to call
- Solar uses Enphase API (config already has keys)

**`src/utils/`** — Shared helpers
- Common logic used by 2+ packages goes here
- Examples: audio format conversion, logging helpers, retry logic
- Do not duplicate helpers across packages — extract to utils instead

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
