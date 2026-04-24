"""Tests for grocery undo (trash buffer + restore) and destructive-action
confirmation gate.

Locks in the Issue B fix end-to-end:
  1. `clear` with >1 items goes through the router confirmation primitive.
  2. Removed items land in the trash and can be restored within the window.
"""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from features.grocery import GroceryFeature
from intent.router import IntentRouter


def _make(tmp_path):
    return GroceryFeature({"grocery_file": str(tmp_path / "g.json")})


# -- Trash / restore --

def test_remove_puts_item_in_trash(tmp_path):
    g = _make(tmp_path)
    g.execute("add", {"items": [{"name": "milk"}]})
    g.execute("remove", {"item": "milk"})
    assert len(g._trash) == 1
    assert g._trash[0][1]["name"] == "milk"


def test_restore_after_remove(tmp_path):
    g = _make(tmp_path)
    g.execute("add", {"items": [{"name": "milk"}, {"name": "bread"}]})
    g.execute("remove", {"item": "milk"})
    result = g.execute("restore", {})
    assert "milk" in result.lower() or "restored" in result.lower()
    stored = json.loads((tmp_path / "g.json").read_text())
    names = [i["name"] for i in stored["items"]]
    assert "milk" in names and "bread" in names


def test_restore_when_trash_empty(tmp_path):
    g = _make(tmp_path)
    result = g.execute("restore", {})
    assert "recent" in result.lower() or "don't" in result.lower()


def test_restore_specific_item(tmp_path):
    g = _make(tmp_path)
    g.execute("add", {"items": [{"name": "milk"}, {"name": "bread"}]})
    g.execute("remove", {"item": "milk"})
    g.execute("remove", {"item": "bread"})
    g.execute("restore", {"item": "milk"})
    stored = json.loads((tmp_path / "g.json").read_text())
    names = [i["name"] for i in stored["items"]]
    assert "milk" in names
    assert "bread" not in names  # still in trash, not restored


# -- Clear confirmation gate (Issue B) --

def test_clear_without_router_clears_directly(tmp_path):
    """No router wired → fall back to immediate clear (tests, display-only)."""
    g = _make(tmp_path)
    g.execute("add", {"items": [
        {"name": "milk"}, {"name": "bread"}, {"name": "eggs"},
    ]})
    result = g.execute("clear", {})
    assert "cleared" in result.lower()
    stored = json.loads((tmp_path / "g.json").read_text())
    assert stored["items"] == []


def test_clear_with_router_asks_for_confirmation(tmp_path):
    """With router attached, clear stages a confirmation instead of wiping."""
    g = _make(tmp_path)
    g.execute("add", {"items": [
        {"name": "milk"}, {"name": "bread"}, {"name": "eggs"},
    ]})

    # Wire a real router with a stub LLM (so record_exchange is a no-op).
    llm = MagicMock()
    llm.parse_intent.return_value = None
    llm._last_call_info = None
    router = IntentRouter({}, [g], llm)

    result = g.execute("clear", {})
    assert "confirm" in result.lower()
    # Items are still there until confirmed.
    stored = json.loads((tmp_path / "g.json").read_text())
    assert len(stored["items"]) == 3
    # Pending was staged on the router.
    assert router._pending_action is not None
    assert router._pending_action["action"] == "clear_confirmed"


def test_clear_confirmed_after_user_says_yes(tmp_path):
    g = _make(tmp_path)
    g.execute("add", {"items": [
        {"name": "milk"}, {"name": "bread"}, {"name": "eggs"},
    ]})
    llm = MagicMock()
    llm.parse_intent.return_value = None
    llm._last_call_info = None
    router = IntentRouter({}, [g], llm)

    # Stage the confirmation.
    g.execute("clear", {})
    # User confirms.
    result = router.route("confirm")
    assert "cleared" in result.lower()
    stored = json.loads((tmp_path / "g.json").read_text())
    assert stored["items"] == []


def test_clear_cancelled(tmp_path):
    g = _make(tmp_path)
    g.execute("add", {"items": [
        {"name": "milk"}, {"name": "bread"}, {"name": "eggs"},
    ]})
    llm = MagicMock()
    llm.parse_intent.return_value = None
    llm._last_call_info = None
    router = IntentRouter({}, [g], llm)

    g.execute("clear", {})
    router.route("cancel")
    stored = json.loads((tmp_path / "g.json").read_text())
    assert len(stored["items"]) == 3


def test_clear_single_item_skips_confirmation(tmp_path):
    """Single-item lists aren't worth gating — the user's intent is obvious."""
    g = _make(tmp_path)
    g.execute("add", {"items": [{"name": "milk"}]})
    llm = MagicMock()
    llm.parse_intent.return_value = None
    llm._last_call_info = None
    router = IntentRouter({}, [g], llm)

    result = g.execute("clear", {})
    assert "cleared" in result.lower()
    assert router._pending_action is None


def test_clear_restores_items_from_trash(tmp_path):
    """The full Issue B sequence: add → clear (confirmed) → restore → list
    back to normal."""
    g = _make(tmp_path)
    g.execute("add", {"items": [
        {"name": "milk"}, {"name": "bread"}, {"name": "eggs"},
    ]})
    # Clear directly (bypassing the router gate by using the internal action).
    g.execute("clear_confirmed", {})
    g.execute("restore", {})
    stored = json.loads((tmp_path / "g.json").read_text())
    names = {i["name"] for i in stored["items"]}
    assert names == {"milk", "bread", "eggs"}
