"""Tests for PromptCache."""

import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from utils.prompt_cache import PromptCache


def _make_tts(speech=b"\x01\x00" * 100):
    tts = MagicMock()
    tts.synthesize.return_value = speech
    return tts


def test_synthesizes_all_phrases():
    tts = _make_tts()
    phrases = ["Hello.", "Hi.", "Hey."]
    PromptCache(tts, phrases)
    assert tts.synthesize.call_count == len(phrases)


def test_pick_returns_bytes():
    tts = _make_tts()
    cache = PromptCache(tts, ["Hello."])
    result = cache.pick()
    assert isinstance(result, bytes)
    assert len(result) > 0


def test_survives_partial_tts_failure():
    """Cache should still work when some phrases fail to synthesize."""
    tts = MagicMock()
    tts.synthesize.side_effect = [
        RuntimeError("fail"),
        b"\x01\x00" * 100,
        RuntimeError("fail"),
    ]
    cache = PromptCache(tts, ["A", "B", "C"])
    result = cache.pick()
    assert result == b"\x01\x00" * 100


def test_all_failure_fallback():
    """Cache should produce silence bytes when all phrases fail."""
    tts = MagicMock()
    tts.synthesize.side_effect = RuntimeError("fail")
    cache = PromptCache(tts, ["A", "B"])
    result = cache.pick()
    assert isinstance(result, bytes)
    assert len(result) > 0


def test_pick_varies():
    """pick() should return different clips over many calls."""
    tts = MagicMock()
    clips = [b"\x01\x00" * 100, b"\x02\x00" * 100, b"\x03\x00" * 100]
    tts.synthesize.side_effect = clips
    cache = PromptCache(tts, ["A", "B", "C"])
    results = {cache.pick() for _ in range(50)}
    assert len(results) > 1
