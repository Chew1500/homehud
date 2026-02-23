"""Tests for the wake word detection module."""

import sys
from pathlib import Path

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
