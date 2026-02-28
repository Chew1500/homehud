"""Tests for the intent router."""

import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from intent.router import IntentRouter


def _make_feature(name="TestFeature", matches=False, response="feature response",
                  description="", action_schema=None, execute_response=None,
                  expects_follow_up=False):
    """Create a mock feature."""
    feat = MagicMock()
    feat.__class__.__name__ = name
    feat.name = name
    feat.matches.return_value = matches
    feat.handle.return_value = response
    feat.description = description
    feat.action_schema = action_schema or {}
    feat.get_llm_context.return_value = None
    feat.expects_follow_up = expects_follow_up
    if execute_response is not None:
        feat.execute.return_value = execute_response
    return feat


def _make_llm(response="LLM response", classify_result=None, parse_result=None):
    """Create a mock LLM."""
    llm = MagicMock()
    llm.respond.return_value = response
    llm.classify_intent.return_value = classify_result
    llm.parse_intent.return_value = parse_result
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


# --- LLM-first intent parsing tests ---


def test_llm_first_action_routes_to_feature():
    """parse_intent returning an action should call feature.execute()."""
    feat = _make_feature(
        name="Grocery List",
        action_schema={"add": {"item": "str"}},
        execute_response="Added milk to the grocery list.",
    )
    llm = _make_llm(parse_result={
        "type": "action",
        "feature": "grocery_list",
        "action": "add",
        "parameters": {"item": "milk"},
        "speech": "Adding milk.",
        "expects_follow_up": False,
    })
    router = IntentRouter({}, [feat], llm)

    result = router.route("add milk to the gross free list")

    assert result == "Added milk to the grocery list."
    feat.execute.assert_called_once_with("add", {"item": "milk"})
    llm.record_exchange.assert_called_once()
    llm.respond.assert_not_called()


def test_llm_first_conversation_returns_speech():
    """parse_intent returning conversation should return speech directly."""
    feat = _make_feature(name="Grocery List")
    llm = _make_llm(parse_result={
        "type": "conversation",
        "speech": "The time is 3pm.",
        "expects_follow_up": False,
    })
    router = IntentRouter({}, [feat], llm)

    result = router.route("what time is it")

    assert result == "The time is 3pm."
    llm.record_exchange.assert_called_once_with("what time is it", "The time is 3pm.")
    feat.execute.assert_not_called()
    llm.respond.assert_not_called()


def test_llm_first_clarification_sets_follow_up():
    """parse_intent returning clarification should set expects_follow_up."""
    feat = _make_feature(name="Grocery List")
    llm = _make_llm(parse_result={
        "type": "clarification",
        "speech": "Did you mean the grocery list?",
        "expects_follow_up": True,
    })
    router = IntentRouter({}, [feat], llm)

    result = router.route("the list")

    assert result == "Did you mean the grocery list?"
    assert router.expects_follow_up is True


def test_llm_first_clarification_cleared_on_next_action():
    """Clarification follow-up should clear on next non-clarification response."""
    feat = _make_feature(
        name="Grocery List",
        action_schema={"list": {}},
        execute_response="List is empty.",
    )
    llm = _make_llm()

    # First call: clarification
    llm.parse_intent.return_value = {
        "type": "clarification",
        "speech": "Did you mean the grocery list?",
        "expects_follow_up": True,
    }
    router = IntentRouter({}, [feat], llm)
    router.route("the list")
    assert router.expects_follow_up is True

    # Second call: action
    llm.parse_intent.return_value = {
        "type": "action",
        "feature": "grocery_list",
        "action": "list",
        "parameters": {},
        "speech": "Listing groceries.",
        "expects_follow_up": False,
    }
    router.route("yes the grocery list")
    assert router.expects_follow_up is False


def test_llm_first_none_falls_to_regex():
    """When parse_intent returns None, regex routing should handle the request."""
    feat = _make_feature(matches=True, response="regex handled it")
    llm = _make_llm(parse_result=None)
    router = IntentRouter({}, [feat], llm)

    result = router.route("add milk to the grocery list")

    assert result == "regex handled it"
    feat.handle.assert_called_with("add milk to the grocery list")


def test_llm_first_unknown_feature_falls_to_regex():
    """When parse_intent references an unknown feature, fall to regex."""
    feat = _make_feature(name="Grocery List", matches=True, response="regex got it")
    llm = _make_llm(parse_result={
        "type": "action",
        "feature": "nonexistent",
        "action": "do_something",
        "parameters": {},
        "speech": "Doing something.",
        "expects_follow_up": False,
    })
    router = IntentRouter({}, [feat], llm)

    result = router.route("test")

    assert result == "regex got it"
    feat.execute.assert_not_called()


def test_llm_first_execute_error_uses_speech_fallback():
    """When feature.execute() raises, use LLM's speech as fallback."""
    feat = _make_feature(
        name="Grocery List",
        action_schema={"add": {"item": "str"}},
    )
    feat.execute.side_effect = RuntimeError("DB error")
    llm = _make_llm(parse_result={
        "type": "action",
        "feature": "grocery_list",
        "action": "add",
        "parameters": {"item": "milk"},
        "speech": "Adding milk to your list.",
        "expects_follow_up": False,
    })
    router = IntentRouter({}, [feat], llm)

    result = router.route("add milk")

    assert result == "Adding milk to your list."
    llm.record_exchange.assert_called_once()


def test_llm_first_passes_feature_context():
    """parse_intent should receive context from features with active state."""
    feat = _make_feature(
        name="Media Library",
        action_schema={"confirm": {}},
        execute_response="Added Dune.",
    )
    feat.get_llm_context.return_value = "Media disambiguation active for Dune."

    llm = _make_llm(parse_result={
        "type": "action",
        "feature": "media_library",
        "action": "confirm",
        "parameters": {},
        "speech": "Confirmed.",
        "expects_follow_up": False,
    })
    router = IntentRouter({}, [feat], llm)
    router.route("yes")

    # Verify context was passed to parse_intent
    call_args = llm.parse_intent.call_args
    context_arg = call_args[0][2] if len(call_args[0]) > 2 else call_args.kwargs.get("context")
    assert context_arg is not None
    assert "Dune" in context_arg


def test_feature_lookup_by_name():
    """Router should find features by various name formats."""
    feat = _make_feature(name="Grocery List")
    llm = _make_llm()
    router = IntentRouter({}, [feat], llm)

    assert router._find_feature("grocery_list") is feat
    assert router._find_feature("Grocery List") is feat
    assert router._find_feature("grocery list") is feat
    assert router._find_feature("grocery") is feat  # substring match
    assert router._find_feature("nonexistent") is None
    assert router._find_feature("") is None


def test_llm_first_action_sets_last_feature():
    """LLM-first action should set _last_feature for follow-up tracking."""
    feat = _make_feature(
        name="Media Library",
        action_schema={"track": {"title": "str"}},
        execute_response="Found Dune.",
    )
    feat.expects_follow_up = True
    llm = _make_llm(parse_result={
        "type": "action",
        "feature": "media_library",
        "action": "track",
        "parameters": {"title": "Dune"},
        "speech": "Searching for Dune.",
        "expects_follow_up": False,
    })
    router = IntentRouter({}, [feat], llm)
    router.route("track dune")

    assert router._last_feature is feat
    assert router.expects_follow_up is True


def test_llm_first_conversation_clears_last_feature():
    """Conversation response should clear _last_feature."""
    feat = _make_feature(name="Grocery List", matches=True)
    feat.expects_follow_up = True
    llm = _make_llm()
    router = IntentRouter({}, [feat], llm)

    # First: match a feature
    router.route("test")
    assert router._last_feature is feat

    # Second: conversation
    llm.parse_intent.return_value = {
        "type": "conversation",
        "speech": "It's 3pm.",
        "expects_follow_up": False,
    }
    router.route("what time is it")
    assert router._last_feature is None
    assert router.expects_follow_up is False


# --- New follow-up and history recording tests ---


def test_regex_fallback_records_exchange():
    """Regex path should record the exchange in LLM history."""
    feat = _make_feature(matches=True, response="grocery list is empty")
    llm = _make_llm(parse_result=None)
    router = IntentRouter({}, [feat], llm)

    router.route("what is on the grocery list")

    llm.record_exchange.assert_called_once_with(
        "what is on the grocery list", "grocery list is empty"
    )


def test_intent_recovery_records_exchange():
    """Intent recovery path should record the exchange in LLM history."""
    feat = _make_feature(
        name="Grocery", description="Grocery list feature"
    )
    feat.matches.side_effect = [False, True]
    feat.handle.return_value = "grocery list is empty"
    llm = _make_llm(parse_result=None, classify_result="what is on the grocery list")
    router = IntentRouter({}, [feat], llm)

    router.route("what is on the gross free list")

    # Should record with original user text, not corrected
    llm.record_exchange.assert_called_once_with(
        "what is on the gross free list", "grocery list is empty"
    )


def test_llm_expects_follow_up_from_parse_result():
    """Conversation with expects_follow_up: true should keep listening."""
    feat = _make_feature(name="Grocery List")
    llm = _make_llm(parse_result={
        "type": "conversation",
        "speech": "What kind of joke would you like?",
        "expects_follow_up": True,
    })
    router = IntentRouter({}, [feat], llm)

    router.route("tell me a joke")

    assert router.expects_follow_up is True


def test_llm_expects_follow_up_false_clears():
    """Conversation with expects_follow_up: false should not keep listening."""
    feat = _make_feature(name="Grocery List")
    llm = _make_llm()

    # First: set follow-up via clarification
    llm.parse_intent.return_value = {
        "type": "clarification",
        "speech": "Did you mean the grocery list?",
        "expects_follow_up": True,
    }
    router = IntentRouter({}, [feat], llm)
    router.route("the list")
    assert router.expects_follow_up is True

    # Second: conversation clears it
    llm.parse_intent.return_value = {
        "type": "conversation",
        "speech": "Here's a joke.",
        "expects_follow_up": False,
    }
    router.route("tell me a joke")
    assert router.expects_follow_up is False


def test_feature_follow_up_takes_priority_over_llm():
    """Feature expects_follow_up should win over LLM's false."""
    feat = _make_feature(
        name="Media Library",
        action_schema={"track": {"title": "str"}},
        execute_response="Found 109 results for Batman. What year?",
        expects_follow_up=True,
    )
    llm = _make_llm(parse_result={
        "type": "action",
        "feature": "media_library",
        "action": "track",
        "parameters": {"title": "Batman"},
        "speech": "Searching for Batman.",
        "expects_follow_up": False,
    })
    router = IntentRouter({}, [feat], llm)
    router.route("track batman")

    # Feature says follow-up needed (disambiguation), LLM said false
    # Feature should win
    assert router.expects_follow_up is True
