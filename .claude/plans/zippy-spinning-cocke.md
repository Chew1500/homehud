# Fix ENPHASE_POLL_INTERVAL parsing crash + change default to 10 min

## Context

Setting `ENPHASE_POLL_INTERVAL=` (empty) in `.env` causes a startup crash: `int("")` raises `ValueError: invalid literal for int() with base 10`. The default should also change from 60s to 600s (10 minutes).

## Changes

### `src/config.py` (line 79)
Handle empty string gracefully and change default to 600:
```python
# Before:
"enphase_poll_interval": int(os.getenv("ENPHASE_POLL_INTERVAL", "60")),

# After:
"enphase_poll_interval": int(os.getenv("ENPHASE_POLL_INTERVAL", "") or "600"),
```
The `or "600"` catches both unset (empty default) and explicitly empty env var.

### `.env.example` (line 84)
Update the comment to reflect the new default:
```
# ENPHASE_POLL_INTERVAL=600        # Seconds between production polls (default: 600)
```

### `tests/test_enphase.py`
Update the test helper `_make_config` to use 600 instead of 60 for consistency (line 29).

## Verification

1. `make lint` — clean
2. `make test` — all pass
3. Confirm: setting `ENPHASE_POLL_INTERVAL=` (empty) no longer crashes
