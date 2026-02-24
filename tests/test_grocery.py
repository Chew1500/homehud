"""Tests for the grocery list feature."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from features.grocery import GroceryFeature


def _make_feature(tmp_path):
    """Create a GroceryFeature with a temp JSON file."""
    grocery_file = tmp_path / "grocery.json"
    config = {"grocery_file": str(grocery_file)}
    return GroceryFeature(config), grocery_file


# -- matches() --


def test_matches_add(tmp_path):
    feat, _ = _make_feature(tmp_path)
    assert feat.matches("add milk to the grocery list")


def test_matches_remove(tmp_path):
    feat, _ = _make_feature(tmp_path)
    assert feat.matches("remove milk from the grocery list")


def test_matches_list(tmp_path):
    feat, _ = _make_feature(tmp_path)
    assert feat.matches("what's on the grocery list")


def test_matches_clear(tmp_path):
    feat, _ = _make_feature(tmp_path)
    assert feat.matches("clear the grocery list")


def test_matches_shopping_list(tmp_path):
    feat, _ = _make_feature(tmp_path)
    assert feat.matches("add eggs to the shopping list")


def test_no_match_unrelated(tmp_path):
    feat, _ = _make_feature(tmp_path)
    assert not feat.matches("what time is it")


def test_no_match_partial(tmp_path):
    feat, _ = _make_feature(tmp_path)
    assert not feat.matches("I need groceries")


# -- add --


def test_add_basic(tmp_path):
    feat, gf = _make_feature(tmp_path)
    result = feat.handle("add milk to the grocery list")
    assert "Added milk" in result
    assert "1 item" in result
    assert json.loads(gf.read_text()) == ["milk"]


def test_add_duplicate(tmp_path):
    feat, gf = _make_feature(tmp_path)
    feat.handle("add milk to the grocery list")
    result = feat.handle("add milk to the grocery list")
    assert "already on" in result
    assert json.loads(gf.read_text()) == ["milk"]


def test_add_duplicate_case_insensitive(tmp_path):
    feat, _ = _make_feature(tmp_path)
    feat.handle("add Milk to the grocery list")
    result = feat.handle("add milk to the grocery list")
    assert "already on" in result


def test_add_multi_word(tmp_path):
    feat, gf = _make_feature(tmp_path)
    result = feat.handle("add almond milk to the grocery list")
    assert "Added almond milk" in result
    assert json.loads(gf.read_text()) == ["almond milk"]


def test_add_persistence(tmp_path):
    """Items persist across feature instances."""
    feat1, gf = _make_feature(tmp_path)
    feat1.handle("add milk to the grocery list")

    config = {"grocery_file": str(gf)}
    feat2 = GroceryFeature(config)
    result = feat2.handle("what's on the grocery list")
    assert "milk" in result


# -- remove --


def test_remove_basic(tmp_path):
    feat, gf = _make_feature(tmp_path)
    feat.handle("add milk to the grocery list")
    result = feat.handle("remove milk from the grocery list")
    assert "Removed milk" in result
    assert "0 items" in result
    assert json.loads(gf.read_text()) == []


def test_remove_nonexistent(tmp_path):
    feat, _ = _make_feature(tmp_path)
    result = feat.handle("remove milk from the grocery list")
    assert "not on" in result


def test_remove_case_insensitive(tmp_path):
    feat, _ = _make_feature(tmp_path)
    feat.handle("add Milk to the grocery list")
    result = feat.handle("remove milk from the grocery list")
    assert "Removed Milk" in result


# -- list --


def test_list_empty(tmp_path):
    feat, _ = _make_feature(tmp_path)
    result = feat.handle("what's on the grocery list")
    assert "empty" in result


def test_list_items(tmp_path):
    feat, _ = _make_feature(tmp_path)
    feat.handle("add milk to the grocery list")
    feat.handle("add eggs to the grocery list")
    feat.handle("add bread to the grocery list")
    result = feat.handle("what's on the grocery list")
    assert "3 items" in result
    assert "milk" in result
    assert "eggs" in result
    assert "bread" in result


def test_list_single_item(tmp_path):
    feat, _ = _make_feature(tmp_path)
    feat.handle("add milk to the grocery list")
    result = feat.handle("what's on the grocery list")
    assert "one item" in result
    assert "milk" in result


# -- clear --


def test_clear(tmp_path):
    feat, gf = _make_feature(tmp_path)
    feat.handle("add milk to the grocery list")
    feat.handle("add eggs to the grocery list")
    result = feat.handle("clear the grocery list")
    assert "cleared" in result
    assert json.loads(gf.read_text()) == []


# -- edge cases --


def test_missing_file(tmp_path):
    """Listing with no file should report empty, not crash."""
    feat, _ = _make_feature(tmp_path)
    result = feat.handle("what's on the grocery list")
    assert "empty" in result


def test_corrupted_json(tmp_path):
    """Corrupted JSON should be treated as empty."""
    feat, gf = _make_feature(tmp_path)
    gf.write_text("not valid json{{{")
    result = feat.handle("what's on the grocery list")
    assert "empty" in result


def test_ambiguous_command_falls_back_to_list(tmp_path):
    """Mentioning grocery list without a clear action should list items."""
    feat, _ = _make_feature(tmp_path)
    feat.handle("add milk to the grocery list")
    result = feat.handle("tell me about the grocery list")
    assert "milk" in result


def test_show_grocery_list(tmp_path):
    feat, _ = _make_feature(tmp_path)
    feat.handle("add bread to the grocery list")
    result = feat.handle("show the grocery list")
    assert "bread" in result


def test_delete_from_grocery_list(tmp_path):
    """'delete X from grocery list' should work like remove."""
    feat, _ = _make_feature(tmp_path)
    feat.handle("add milk to the grocery list")
    result = feat.handle("delete milk from the grocery list")
    assert "Removed milk" in result
