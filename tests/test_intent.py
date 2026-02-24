"""Tests for the intent router."""

import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from intent.router import IntentRouter


def _make_feature(name="TestFeature", matches=False, response="feature response"):
    """Create a mock feature."""
    feat = MagicMock()
    feat.__class__.__name__ = name
    feat.matches.return_value = matches
    feat.handle.return_value = response
    return feat


def _make_llm(response="LLM response"):
    """Create a mock LLM."""
    llm = MagicMock()
    llm.respond.return_value = response
    return llm


def test_routes_to_matching_feature():
    feat = _make_feature(matches=True, response="got it")
    llm = _make_llm()
    router = IntentRouter({}, [feat], llm)

    result = router.route("add milk to the grocery list")

    assert result == "got it"
    feat.handle.assert_called_with("add milk to the grocery list")
    llm.respond.assert_not_called()


def test_falls_back_to_llm():
    feat = _make_feature(matches=False)
    llm = _make_llm("LLM says hi")
    router = IntentRouter({}, [feat], llm)

    result = router.route("what time is it")

    assert result == "LLM says hi"
    llm.respond.assert_called_with("what time is it")
    feat.handle.assert_not_called()


def test_first_match_wins():
    feat1 = _make_feature(name="First", matches=True, response="first")
    feat2 = _make_feature(name="Second", matches=True, response="second")
    llm = _make_llm()
    router = IntentRouter({}, [feat1, feat2], llm)

    result = router.route("test")

    assert result == "first"
    feat1.handle.assert_called_once()
    feat2.matches.assert_not_called()


def test_empty_features_uses_llm():
    llm = _make_llm("fallback")
    router = IntentRouter({}, [], llm)

    result = router.route("hello")

    assert result == "fallback"
    llm.respond.assert_called_with("hello")


def test_close_cascades():
    feat1 = _make_feature()
    feat2 = _make_feature()
    llm = _make_llm()
    router = IntentRouter({}, [feat1, feat2], llm)

    router.close()

    feat1.close.assert_called_once()
    feat2.close.assert_called_once()
    llm.close.assert_called_once()
