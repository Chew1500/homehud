"""Tests for the wake word detection module."""

import sys
import time
from collections import defaultdict
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add src to path so imports work
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from wake import get_wake
from wake.mock_wake import MockWakeWord


def test_mock_triggers_after_n_chunks():
    """MockWakeWord should trigger after the configured number of chunks."""
    config = {"wake_mock_trigger_after": 5}
    wake = MockWakeWord(config)
    chunk = b"\x00\x00" * 1280

    for _ in range(4):
        assert wake.detect(chunk) is False

    assert wake.detect(chunk) is True


def test_mock_reset_clears_counter():
    """reset() should allow re-triggering after the same number of chunks."""
    config = {"wake_mock_trigger_after": 3}
    wake = MockWakeWord(config)
    chunk = b"\x00\x00" * 1280

    for _ in range(3):
        wake.detect(chunk)
    assert wake._count == 3

    wake.reset()
    assert wake._count == 0

    # Should need another 3 chunks to trigger
    for _ in range(2):
        assert wake.detect(chunk) is False
    assert wake.detect(chunk) is True


def test_mock_default_trigger_count():
    """Default trigger count should be 62 (~5s at 80ms chunks)."""
    config = {}
    wake = MockWakeWord(config)
    assert wake._trigger_after == 62


def test_factory_returns_mock():
    """get_wake() should return MockWakeWord by default."""
    config = {"wake_mode": "mock"}
    wake = get_wake(config)
    assert isinstance(wake, MockWakeWord)


def test_close_does_not_raise():
    """close() should be a safe no-op."""
    config = {"wake_mock_trigger_after": 10}
    wake = MockWakeWord(config)
    wake.close()


# --- OWWWakeWord tests (mocked openwakeword) ---


def _make_oww(config_overrides=None, prediction_buffer=None):
    """Create an OWWWakeWord instance with mocked openwakeword internals."""
    config = {
        "wake_model": "hey_jarvis",
        "wake_threshold": 0.6,
        "wake_confirm_frames": 3,
        "wake_cooldown": 2.0,
    }
    if config_overrides:
        config.update(config_overrides)

    # Mock openwakeword.model.Model
    mock_model_cls = MagicMock()
    mock_model_instance = MagicMock()
    # prediction_buffer is a dict of model_name -> list of scores
    if prediction_buffer is None:
        prediction_buffer = defaultdict(list)
    mock_model_instance.prediction_buffer = prediction_buffer
    mock_model_cls.return_value = mock_model_instance

    # Mock numpy
    mock_np = MagicMock()
    mock_np.int16 = "int16"
    mock_np.frombuffer.return_value = MagicMock()

    # Patch imports inside oww_wake
    mock_oww_module = MagicMock()
    mock_oww_module.model.Model = mock_model_cls

    with patch.dict(sys.modules, {
        "openwakeword": mock_oww_module,
        "openwakeword.model": mock_oww_module.model,
        "numpy": mock_np,
    }):
        from wake.oww_wake import OWWWakeWord
        oww = OWWWakeWord(config)

    # Replace numpy ref so detect() works
    oww._np = mock_np
    return oww, mock_model_instance, prediction_buffer


def test_oww_requires_consecutive_frames():
    """Detection requires N consecutive frames above threshold."""
    buf = defaultdict(list)
    oww, model, _ = _make_oww(
        config_overrides={"wake_confirm_frames": 3, "wake_threshold": 0.6},
        prediction_buffer=buf,
    )
    chunk = b"\x00\x00" * 1280

    # 1 frame above threshold — not enough
    buf["hey_jarvis"] = [0.8]
    assert oww.detect(chunk) is False

    # 2 frames above threshold — not enough
    buf["hey_jarvis"] = [0.8, 0.7]
    assert oww.detect(chunk) is False

    # 3 consecutive frames above threshold — fires
    buf["hey_jarvis"] = [0.8, 0.7, 0.9]
    assert oww.detect(chunk) is True


def test_oww_sub_threshold_frame_resets_confirmation():
    """A frame below threshold in the window prevents detection."""
    buf = defaultdict(list)
    oww, model, _ = _make_oww(
        config_overrides={"wake_confirm_frames": 3, "wake_threshold": 0.6},
        prediction_buffer=buf,
    )
    chunk = b"\x00\x00" * 1280

    # Middle frame below threshold — should not fire
    buf["hey_jarvis"] = [0.8, 0.4, 0.9]
    assert oww.detect(chunk) is False

    # Last frame below threshold — should not fire
    buf["hey_jarvis"] = [0.8, 0.7, 0.3]
    assert oww.detect(chunk) is False


def test_oww_cooldown_suppresses_rapid_retrigger():
    """Second detection within cooldown window is suppressed."""
    buf = defaultdict(list)
    oww, model, _ = _make_oww(
        config_overrides={
            "wake_confirm_frames": 2,
            "wake_threshold": 0.6,
            "wake_cooldown": 2.0,
        },
        prediction_buffer=buf,
    )
    chunk = b"\x00\x00" * 1280

    # First detection fires
    buf["hey_jarvis"] = [0.8, 0.9]
    assert oww.detect(chunk) is True

    # Immediate second detection is suppressed
    buf["hey_jarvis"] = [0.8, 0.9]
    assert oww.detect(chunk) is False


def test_oww_cooldown_allows_detection_after_expiry():
    """Detection is allowed again after cooldown expires."""
    buf = defaultdict(list)
    oww, model, _ = _make_oww(
        config_overrides={
            "wake_confirm_frames": 2,
            "wake_threshold": 0.6,
            "wake_cooldown": 0.1,  # Very short for testing
        },
        prediction_buffer=buf,
    )
    chunk = b"\x00\x00" * 1280

    # First detection fires
    buf["hey_jarvis"] = [0.8, 0.9]
    assert oww.detect(chunk) is True

    # Wait for cooldown to expire
    time.sleep(0.15)

    # Should fire again
    buf["hey_jarvis"] = [0.8, 0.9]
    assert oww.detect(chunk) is True


def test_oww_reset_clears_model_state():
    """reset() delegates to the underlying model."""
    buf = defaultdict(list)
    oww, model, _ = _make_oww(prediction_buffer=buf)
    oww.reset()
    model.reset.assert_called_once()
