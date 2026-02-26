"""Tests for the intent router."""

import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from intent.router import IntentRouter


def _make_feature(name="TestFeature", matches=False, response="feature response",
                  description=""):
    """Create a mock feature."""
    feat = MagicMock()
    feat.__class__.__name__ = name
    feat.matches.return_value = matches
    feat.handle.return_value = response
    feat.description = description
    return feat


def _make_llm(response="LLM response", classify_result=None):
    """Create a mock LLM."""
    llm = MagicMock()
    llm.respond.return_value = response
    llm.classify_intent.return_value = classify_result
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


# --- Intent recovery tests ---


def test_recovery_corrects_misheard_command():
    """When classify_intent returns corrected text that matches a feature, use it."""
    feat = _make_feature(
        name="Grocery", description="Grocery list feature"
    )
    # First call (original text) → no match; second call (corrected) → match
    feat.matches.side_effect = [False, True]
    feat.handle.return_value = "grocery list is empty"
    llm = _make_llm(classify_result="what is on the grocery list")
    router = IntentRouter({}, [feat], llm)

    result = router.route("what is on the gross free list")

    assert result == "grocery list is empty"
    feat.handle.assert_called_with("what is on the grocery list")
    llm.respond.assert_not_called()


def test_recovery_returns_none_falls_to_llm():
    """When classify_intent returns None, fall through to LLM."""
    feat = _make_feature(matches=False, description="Some feature")
    llm = _make_llm("LLM answer", classify_result=None)
    router = IntentRouter({}, [feat], llm)

    result = router.route("what is the capital of France")

    assert result == "LLM answer"
    llm.classify_intent.assert_called_once()
    llm.respond.assert_called_with("what is the capital of France")


def test_recovery_corrected_no_match_falls_to_llm():
    """When corrected text still doesn't match features, fall to LLM."""
    feat = _make_feature(matches=False, description="Some feature")
    llm = _make_llm("LLM answer", classify_result="some corrected text")
    router = IntentRouter({}, [feat], llm)

    result = router.route("garbled input")

    assert result == "LLM answer"
    llm.respond.assert_called_with("garbled input")


def test_recovery_disabled_skips_classification():
    """When intent_recovery_enabled is False, skip classify_intent entirely."""
    feat = _make_feature(matches=False, description="Some feature")
    llm = _make_llm("LLM answer")
    config = {"intent_recovery_enabled": False}
    router = IntentRouter(config, [feat], llm)

    result = router.route("what is on the gross free list")

    assert result == "LLM answer"
    llm.classify_intent.assert_not_called()
    llm.respond.assert_called_once()


def test_recovery_exception_falls_to_llm():
    """When classify_intent raises an exception, fall through to LLM."""
    feat = _make_feature(matches=False, description="Some feature")
    llm = _make_llm("LLM answer")
    llm.classify_intent.side_effect = RuntimeError("API error")
    router = IntentRouter({}, [feat], llm)

    result = router.route("garbled input")

    assert result == "LLM answer"
    llm.respond.assert_called_with("garbled input")


def test_recovery_skipped_when_no_descriptions():
    """When no features have descriptions, skip classification."""
    feat = _make_feature(matches=False, description="")
    llm = _make_llm("LLM answer")
    router = IntentRouter({}, [feat], llm)

    result = router.route("anything")

    assert result == "LLM answer"
    llm.classify_intent.assert_not_called()


# --- Follow-up mode tests ---


def test_expects_follow_up_false_by_default():
    """Router should report no follow-up when no feature has been matched."""
    llm = _make_llm()
    router = IntentRouter({}, [], llm)
    assert router.expects_follow_up is False


def test_expects_follow_up_delegates_to_feature():
    """Router should delegate expects_follow_up to the last matched feature."""
    feat = _make_feature(matches=True)
    feat.expects_follow_up = True
    llm = _make_llm()
    router = IntentRouter({}, [feat], llm)

    router.route("test")

    assert router.expects_follow_up is True


def test_expects_follow_up_cleared_on_llm_fallback():
    """LLM fallback should clear _last_feature, making expects_follow_up False."""
    feat = _make_feature(matches=True)
    feat.expects_follow_up = True
    llm = _make_llm()
    router = IntentRouter({}, [feat], llm)

    # First route matches feature
    router.route("test")
    assert router.expects_follow_up is True

    # Second route falls through to LLM
    feat.matches.return_value = False
    llm.classify_intent.return_value = None
    router.route("what is the weather")
    assert router.expects_follow_up is False
