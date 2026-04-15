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


def _names(grocery_file):
    """Return just the item names from the on-disk state."""
    data = json.loads(grocery_file.read_text())
    if isinstance(data, list):
        return list(data)
    return [i["name"] for i in data.get("items", [])]


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
    assert _names(gf) == ["milk"]


def test_add_duplicate(tmp_path):
    feat, gf = _make_feature(tmp_path)
    feat.handle("add milk to the grocery list")
    result = feat.handle("add milk to the grocery list")
    assert "already on" in result
    assert _names(gf) == ["milk"]


def test_add_duplicate_case_insensitive(tmp_path):
    feat, _ = _make_feature(tmp_path)
    feat.handle("add Milk to the grocery list")
    result = feat.handle("add milk to the grocery list")
    assert "already on" in result


def test_add_multi_word(tmp_path):
    feat, gf = _make_feature(tmp_path)
    result = feat.handle("add almond milk to the grocery list")
    assert "Added almond milk" in result
    assert _names(gf) == ["almond milk"]


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
    assert _names(gf) == []


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
    assert _names(gf) == []


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


# -- multi-item add (LLM path) --


def test_execute_add_items_list(tmp_path):
    feat, gf = _make_feature(tmp_path)
    result = feat.execute(
        "add",
        {"items": ["chicken wings", "salad mix", "ranch dressing", "lasagna"]},
    )
    assert "chicken wings" in result
    assert "4 items" in result
    assert _names(gf) == ["chicken wings", "salad mix", "ranch dressing", "lasagna"]


def test_execute_add_item_comma_string(tmp_path):
    feat, gf = _make_feature(tmp_path)
    result = feat.execute("add", {"item": "eggs, milk, and bread"})
    assert "3 items" in result
    assert _names(gf) == ["eggs", "milk", "bread"]


def test_execute_add_item_list_in_item_key(tmp_path):
    feat, gf = _make_feature(tmp_path)
    result = feat.execute("add", {"item": ["eggs", "milk"]})
    assert "2 items" in result
    assert _names(gf) == ["eggs", "milk"]


def test_execute_add_with_partial_duplicates(tmp_path):
    feat, gf = _make_feature(tmp_path)
    feat.handle("add milk to the grocery list")
    result = feat.execute("add", {"items": ["milk", "eggs", "bread"]})
    assert "eggs" in result
    assert "bread" in result
    assert "already on" in result
    assert _names(gf) == ["milk", "eggs", "bread"]


def test_handle_multi_item_voice(tmp_path):
    feat, gf = _make_feature(tmp_path)
    result = feat.handle(
        "add chicken wings, salad mix, ranch dressing, and lasagna to the grocery list"
    )
    assert "4 items" in result
    assert _names(gf) == [
        "chicken wings",
        "salad mix",
        "ranch dressing",
        "lasagna",
    ]


# -- structured quantities --


def _items(grocery_file):
    """Full item dicts from disk."""
    data = json.loads(grocery_file.read_text())
    return data.get("items", [])


def test_add_structured_quantity(tmp_path):
    feat, gf = _make_feature(tmp_path)
    feat.execute("add", {"items": [{"name": "cantaloupe", "quantity": 8}]})
    items = _items(gf)
    assert len(items) == 1
    assert items[0]["name"] == "cantaloupe"
    assert items[0]["quantity"] == 8.0
    assert items[0]["unit"] is None


def test_another_bumps_implicit(tmp_path):
    feat, gf = _make_feature(tmp_path)
    feat.execute("add", {"items": [{"name": "nascar", "quantity": 1}]})
    feat.execute("add", {"items": [{"name": "nascar", "quantity": 1}]})
    items = _items(gf)
    assert len(items) == 1
    assert items[0]["name"] == "nascar"
    assert items[0]["quantity"] == 2.0


def test_merge_same_unit_pluralization(tmp_path):
    feat, gf = _make_feature(tmp_path)
    feat.execute("add", {"items": [{"name": "flour", "quantity": 2, "unit": "cups"}]})
    feat.execute("add", {"items": [{"name": "flour", "quantity": 1, "unit": "cup"}]})
    items = _items(gf)
    assert len(items) == 1
    assert items[0]["quantity"] == 3.0
    assert items[0]["unit"] == "cup"


def test_merge_mixed_units_keeps_both(tmp_path):
    feat, gf = _make_feature(tmp_path)
    feat.execute("add", {"items": [{"name": "flour", "quantity": 2, "unit": "cup"}]})
    feat.execute("add", {"items": [{"name": "flour", "quantity": 1, "unit": "lb"}]})
    items = _items(gf)
    assert len(items) == 2
    units = sorted(i["unit"] for i in items)
    assert units == ["cup", "lb"]


def test_bare_existing_adopts_incoming_unit(tmp_path):
    feat, gf = _make_feature(tmp_path)
    feat.execute("add", {"items": [{"name": "flour"}]})
    feat.execute("add", {"items": [{"name": "flour", "quantity": 2, "unit": "cup"}]})
    items = _items(gf)
    assert len(items) == 1
    assert items[0]["unit"] == "cup"
    assert items[0]["quantity"] == 3.0  # bare existing treated as 1


def test_v2_migration_parses_leading_quantity(tmp_path):
    grocery_file = tmp_path / "grocery.json"
    grocery_file.write_text(json.dumps({
        "items": [
            {"id": "a", "name": "8 cantaloupes", "category": "Produce", "checked": False},
            {"id": "b", "name": "2 cups flour", "category": "Pantry", "checked": False},
            {"id": "c", "name": "milk", "category": "Dairy", "checked": False},
        ]
    }))
    config = {"grocery_file": str(grocery_file)}
    feat = GroceryFeature(config)
    state = feat.get_state()
    by_name = {i["name"]: i for i in state["items"]}
    assert by_name["cantaloupes"]["quantity"] == 8.0
    assert by_name["cantaloupes"]["unit"] is None
    assert by_name["flour"]["quantity"] == 2.0
    assert by_name["flour"]["unit"] == "cup"
    assert by_name["milk"]["quantity"] is None
    assert by_name["milk"]["unit"] is None


def test_legacy_string_items_still_work(tmp_path):
    feat, gf = _make_feature(tmp_path)
    feat.execute("add", {"items": ["milk"]})
    items = _items(gf)
    assert len(items) == 1
    assert items[0]["name"] == "milk"
    assert items[0]["quantity"] is None


def test_plain_dup_still_skipped(tmp_path):
    feat, _ = _make_feature(tmp_path)
    feat.execute("add", {"items": [{"name": "milk"}]})
    result = feat.execute("add", {"items": [{"name": "milk"}]})
    assert "already on" in result
