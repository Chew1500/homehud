"""Tests for the speech-to-text abstraction layer."""

import sys
from pathlib import Path

# Add src to path so imports work
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from speech import get_stt
from speech.mock_stt import MockSTT


def test_mock_stt_default_response():
    """MockSTT should return 'hello world' by default."""
    stt = MockSTT({})
    result = stt.transcribe(b"\x00\x00" * 1600)
    assert result == "hello world"


def test_mock_stt_custom_response():
    """MockSTT should return a custom response when configured."""
    stt = MockSTT({"stt_mock_response": "add milk to groceries"})
    result = stt.transcribe(b"\x00\x00" * 1600)
    assert result == "add milk to groceries"


def test_mock_stt_ignores_audio():
    """MockSTT should return the same response regardless of audio content."""
    stt = MockSTT({})
    assert stt.transcribe(b"") == "hello world"
    assert stt.transcribe(b"\xff" * 10000) == "hello world"


def test_factory_returns_mock():
    """get_stt() should return MockSTT by default."""
    stt = get_stt({"stt_mode": "mock"})
    assert isinstance(stt, MockSTT)


def test_factory_returns_mock_when_unset():
    """get_stt() should return MockSTT when stt_mode is not set."""
    stt = get_stt({})
    assert isinstance(stt, MockSTT)


def test_mock_stt_close():
    """close() should not raise."""
    stt = MockSTT({})
    stt.close()
