# "Repeat Last Response" Voice Command

## Context

When the wake word misfires, the HomHUD records ambient audio, transcribes it, routes it to a feature or the LLM, and speaks a response. The user has no way to find out what was said after the fact. This adds a voice command ("what did you say?", "repeat that", etc.) that replays the last response.

## Design

`RepeatFeature` stores the last query/response pair in memory. The voice pipeline calls `repeat_feature.record(text, response)` after each successful route. The feature skips recording when the query itself is a repeat trigger (so asking "what did you say?" twice returns the same original answer).

No file persistence needed — this is session-scoped by nature.

## Files

### 1. `src/features/repeat.py` (new)

New `RepeatFeature(BaseFeature)`:

- **`matches(text)`** — regex for trigger phrases:
  - "what did you (just) say", "what was that", "repeat that", "say that again"
  - "come again", "can you repeat that", "what did you tell me", "say it again"
  - "I didn't catch/hear that", "pardon"
- **`handle(text)`** — returns `"I heard: {query}. And I responded: {response}."` or `"I haven't said anything yet this session."` (for reminders: `"A reminder fired. I said: {response}."` since the query is synthetic)
- **`record(query, response)`** — stores the pair; skips if query matches a repeat trigger
- Thread-safe via `threading.Lock` (pipeline runs in a daemon thread)

### 2. `src/voice_pipeline.py` (modify)

- Add optional `repeat_feature=None` parameter to `start_voice_pipeline()`
- After `response = router.route(text)` (line 54), add:
  ```python
  if repeat_feature is not None:
      repeat_feature.record(text, response)
  ```
- Placed inside the routing `try` block, after route succeeds but before TTS — so if TTS fails, the response is still recorded (which is exactly when the user would ask "what did you say?")

### 3. `src/main.py` (modify)

- Import `RepeatFeature` (line ~125, inside voice_enabled block)
- Create `repeat_feature = RepeatFeature(config)` before features list
- Add it first in the features list (meta-command, should match before other features)
- Pass `repeat_feature=repeat_feature` to `start_voice_pipeline()`
- Update `on_reminder_due` to also call `repeat_feature.record("(reminder)", response)` so reminder-fired speech is captured too

### 4. `tests/test_repeat.py` (new)

- `matches()`: all trigger phrases, case insensitivity, embedded in sentence
- `matches()` negatives: unrelated text, partial matches
- `handle()` with no history → "I haven't said anything yet"
- `record()` + `handle()` → returns stored response
- `record()` overwrites previous
- `record()` skips repeat-trigger queries (consecutive repeats return original)
- `record()` captures synthetic `(reminder)` queries
- Thread safety smoke test

### 5. `tests/test_voice_pipeline.py` (modify)

- Add test: pipeline calls `repeat_feature.record()` after routing
- Add test: pipeline works without `repeat_feature` (backward compat)

### 6. `ARCHITECTURE.md` (modify)

Add under `src/features/`:
```
- `repeat.py`: `RepeatFeature` — replays the last spoken response
```

## Verification

1. `make lint` — clean
2. `make test` — all pass
3. Manual: `HUD_STT_MOCK_RESPONSE="what did you say"` → should get "I haven't said anything yet this session."