"""Tests for the router's cross-turn context (last_list / last_entity).

These lock in the contract that fixes Issue A (stale Tortilla Soup pointer)
and the "add the second" positional-reference case.
"""

import sys
import time
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from intent.router import IntentRouter


def _make_feature(name="TestFeature"):
    feat = MagicMock()
    feat.__class__.__name__ = name
    feat.name = name
    feat.matches.return_value = False
    feat.description = ""
    feat.action_schema = {}
    feat.get_llm_context.return_value = None
    feat.expects_follow_up = False
    return feat


def _make_llm():
    llm = MagicMock()
    llm.parse_intent.return_value = None
    llm.respond_stream.side_effect = lambda text: iter([""])
    llm.classify_intent.return_value = None
    llm._last_call_info = None
    return llm


def _make_router():
    feature = _make_feature()
    llm = _make_llm()
    return IntentRouter({}, [feature], llm), llm, feature


def test_router_attaches_itself_to_features():
    router, _, feature = _make_router()
    assert feature._router is router


def test_set_last_list_stores_items():
    router, _, _ = _make_router()
    router.set_last_list("recipes", [{"name": "A"}, {"name": "B"}])
    assert router._last_list is not None
    assert router._last_list["source"] == "recipes"
    assert len(router._last_list["items"]) == 2


def test_set_last_list_empty_clears():
    router, _, _ = _make_router()
    router.set_last_list("recipes", [{"name": "A"}])
    router.set_last_list("recipes", [])
    assert router._last_list is None


def test_format_turn_context_empty():
    router, _, _ = _make_router()
    assert router._format_turn_context() == []


def test_format_turn_context_serializes_list():
    router, _, _ = _make_router()
    router.set_last_list("recipes", [{"name": "A"}, {"name": "B"}])
    lines = router._format_turn_context()
    assert len(lines) == 1
    assert "last_list(recipes" in lines[0]
    assert "1=A" in lines[0] and "2=B" in lines[0]


def test_format_turn_context_serializes_entity():
    router, _, _ = _make_router()
    router.set_last_entity("recipes", {"name": "Skillet Gnocchi"})
    lines = router._format_turn_context()
    assert len(lines) == 1
    assert "last_entity(recipes" in lines[0]
    assert "Skillet Gnocchi" in lines[0]


def test_context_expires_after_ttl():
    router, _, _ = _make_router()
    router.set_last_list("recipes", [{"name": "A"}])
    router.set_last_entity("recipes", {"name": "A"})
    # Force expiry by back-dating the timestamps.
    router._last_list["ts"] = time.monotonic() - 9999
    router._last_entity["ts"] = time.monotonic() - 9999
    assert router._format_turn_context() == []
    # Stale state should be cleared on read.
    assert router._last_list is None
    assert router._last_entity is None


def test_clear_turn_context():
    router, _, _ = _make_router()
    router.set_last_list("recipes", [{"name": "A"}])
    router.set_last_entity("recipes", {"name": "A"})
    router.clear_turn_context()
    assert router._last_list is None
    assert router._last_entity is None


def test_feature_writes_reach_router():
    """Feature's _set_last_list helper must route through to the router."""
    router, _, feature = _make_router()
    # Use BaseFeature's helper (via MagicMock auto-spec behaviour).
    # Attach the real method dynamically.
    from features.base import BaseFeature

    BaseFeature._set_last_list(feature, "recipes", [{"name": "A"}])
    assert router._last_list is not None
    assert router._last_list["items"][0]["name"] == "A"


def test_context_included_in_parse_intent_call():
    """The context lines must flow into parse_intent() as the context arg."""
    router, llm, _ = _make_router()
    router.set_last_entity("recipes", {"name": "Skillet Gnocchi"})
    llm.parse_intent.return_value = {
        "type": "conversation", "speech": "ok",
    }
    router.route("add it to the grocery list")
    # parse_intent called with positional (text, schemas, context)
    args, _ = llm.parse_intent.call_args
    context = args[2]
    assert context is not None
    assert "Skillet Gnocchi" in context
