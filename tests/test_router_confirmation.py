"""Tests for the router's pending-confirmation primitive.

Locks in the Issue B fix: destructive actions (clear, bulk remove) stage a
summary and only execute after an explicit yes/confirm.
"""

import sys
import time
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from intent.router import IntentRouter


def _feat(name="TestFeature"):
    f = MagicMock()
    f.__class__.__name__ = name
    f.name = name
    f.matches.return_value = False
    f.description = ""
    f.action_schema = {}
    f.get_llm_context.return_value = None
    f.expects_follow_up = False
    f.execute.return_value = "done"
    return f


def _llm():
    m = MagicMock()
    m.parse_intent.return_value = None
    m.respond_stream.side_effect = lambda t: iter([""])
    m.classify_intent.return_value = None
    m._last_call_info = None
    return m


def _make_router():
    f = _feat()
    llm = _llm()
    return IntentRouter({}, [f], llm), llm, f


def test_request_confirmation_returns_summary():
    router, _, feature = _make_router()
    msg = router.request_confirmation(
        feature, "clear", {}, "About to clear 17 items. Say confirm."
    )
    assert "confirm" in msg.lower()
    assert router._pending_action is not None
    assert router.expects_follow_up is True
    # Action was NOT executed yet.
    feature.execute.assert_not_called()


def test_confirm_replays_action():
    router, _, feature = _make_router()
    router.request_confirmation(feature, "clear", {}, "About to clear 17 items.")
    result = router.route("yes")
    feature.execute.assert_called_once_with("clear", {})
    assert result == "done"
    assert router._pending_action is None


def test_cancel_drops_action():
    router, _, feature = _make_router()
    router.request_confirmation(feature, "clear", {}, "About to clear 17 items.")
    result = router.route("cancel")
    feature.execute.assert_not_called()
    assert "cancel" in result.lower()
    assert router._pending_action is None


def test_unrelated_utterance_drops_pending_and_falls_through():
    router, llm, feature = _make_router()
    router.request_confirmation(feature, "clear", {}, "...")
    # parse_intent returns a normal conversation response for the new query.
    llm.parse_intent.return_value = {"type": "conversation", "speech": "OK"}
    result = router.route("what's the weather")
    feature.execute.assert_not_called()
    assert router._pending_action is None
    assert result == "OK"


def test_ttl_expires_pending():
    router, _, feature = _make_router()
    router.request_confirmation(feature, "clear", {}, "...")
    router._pending_action["ts"] = time.monotonic() - 9999
    # The next route should treat this as no-pending.
    # Make parse_intent return something so route returns a value.
    router._llm.parse_intent.return_value = {
        "type": "conversation", "speech": "ok"
    }
    router.route("yes")
    feature.execute.assert_not_called()
    assert router._pending_action is None


def test_pending_appears_in_intent_context():
    """parse_intent must see the pending action as context."""
    router, llm, feature = _make_router()
    router.request_confirmation(feature, "clear", {}, "About to clear 17 items.")
    llm.parse_intent.return_value = {"type": "conversation", "speech": "hi"}
    # Trigger a route that won't match yes/no/cancel so normal flow runs.
    router.route("what's the weather")
    # The first call would include context; but since we cleared pending on
    # non-match, we need to test it a different way: request, then look at
    # the prepared context directly.
    router.request_confirmation(feature, "clear", {}, "About to clear 17 items.")
    line = router._pending_context()
    assert line is not None
    assert "pending_confirmation" in line
    assert "clear 17 items" in line
