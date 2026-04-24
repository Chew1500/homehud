"""Tests for grocery recipe-layer provenance and removal."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from features.grocery import GroceryFeature


def _make(tmp_path):
    grocery_file = tmp_path / "grocery.json"
    return GroceryFeature({"grocery_file": str(grocery_file)}), grocery_file


def _item_by_name(grocery, name: str):
    for it in grocery.get_items_structured():
        if it["name"].lower() == name.lower():
            return it
    return None


def test_add_with_source_records_layer(tmp_path):
    feat, _ = _make(tmp_path)
    feat.register_layer("r1", "Pancakes")
    feat._add_many_detailed(
        [{"name": "flour", "quantity": 2, "unit": "cup"}],
        source={"recipe_id": "r1", "recipe_name": "Pancakes"},
    )
    item = _item_by_name(feat, "flour")
    assert item["quantity"] == 2.0
    assert item["manual_quantity"] == 0.0
    assert item["sources"] == {"r1": {"quantity": 2.0, "recipe_name": "Pancakes"}}

    layers = feat.get_recipe_layers()
    assert len(layers) == 1
    assert layers[0]["recipe_id"] == "r1"


def test_overlap_between_two_recipes_sums(tmp_path):
    feat, _ = _make(tmp_path)
    feat.register_layer("r1", "Pancakes")
    feat._add_many_detailed(
        [{"name": "eggs", "quantity": 2}],
        source={"recipe_id": "r1", "recipe_name": "Pancakes"},
    )
    feat.register_layer("r2", "Carbonara")
    feat._add_many_detailed(
        [{"name": "eggs", "quantity": 3}],
        source={"recipe_id": "r2", "recipe_name": "Carbonara"},
    )
    item = _item_by_name(feat, "eggs")
    assert item["quantity"] == 5.0
    assert item["manual_quantity"] == 0.0
    assert item["sources"]["r1"]["quantity"] == 2.0
    assert item["sources"]["r2"]["quantity"] == 3.0


def test_remove_layer_subtracts_only_its_share(tmp_path):
    feat, _ = _make(tmp_path)
    feat.register_layer("r1", "Pancakes")
    feat._add_many_detailed(
        [
            {"name": "eggs", "quantity": 2},
            {"name": "flour", "quantity": 2, "unit": "cup"},
        ],
        source={"recipe_id": "r1", "recipe_name": "Pancakes"},
    )
    feat.register_layer("r2", "Carbonara")
    feat._add_many_detailed(
        [
            {"name": "eggs", "quantity": 3},
            {"name": "pasta", "quantity": 1, "unit": "lb"},
        ],
        source={"recipe_id": "r2", "recipe_name": "Carbonara"},
    )

    summary = feat.remove_recipe_layer("r1")
    assert summary["layer"]["recipe_id"] == "r1"

    # Eggs survives with Carbonara's contribution
    eggs = _item_by_name(feat, "eggs")
    assert eggs is not None
    assert eggs["quantity"] == 3.0
    assert "r1" not in eggs["sources"]
    assert eggs["sources"]["r2"]["quantity"] == 3.0

    # Flour is Pancakes-only → gone
    assert _item_by_name(feat, "flour") is None

    # Pasta is untouched
    pasta = _item_by_name(feat, "pasta")
    assert pasta is not None
    assert pasta["quantity"] == 1.0

    # Only Carbonara's layer remains
    layers = feat.get_recipe_layers()
    assert [layer["recipe_id"] for layer in layers] == ["r2"]


def test_remove_layer_preserves_manual_edit(tmp_path):
    feat, _ = _make(tmp_path)
    feat.register_layer("r1", "Pancakes")
    feat._add_many_detailed(
        [{"name": "eggs", "quantity": 2}],
        source={"recipe_id": "r1", "recipe_name": "Pancakes"},
    )
    # User manually bumps eggs from 2 → 5 (adds 3 manual).
    item = _item_by_name(feat, "eggs")
    feat.update_item(item["id"], {"quantity": 5})
    item = _item_by_name(feat, "eggs")
    assert item["quantity"] == 5.0
    assert item["manual_quantity"] == 3.0
    assert item["sources"]["r1"]["quantity"] == 2.0

    # Remove the layer → eggs drops to 3 (the manual portion).
    feat.remove_recipe_layer("r1")
    eggs = _item_by_name(feat, "eggs")
    assert eggs is not None
    assert eggs["quantity"] == 3.0
    assert eggs["manual_quantity"] == 3.0
    assert eggs["sources"] == {}


def test_mixed_units_tags_each_row(tmp_path):
    feat, _ = _make(tmp_path)
    feat.register_layer("r1", "A")
    feat._add_many_detailed(
        [{"name": "milk", "quantity": 1, "unit": "cup"}],
        source={"recipe_id": "r1", "recipe_name": "A"},
    )
    feat.register_layer("r2", "B")
    feat._add_many_detailed(
        [{"name": "milk", "quantity": 200, "unit": "ml"}],
        source={"recipe_id": "r2", "recipe_name": "B"},
    )
    items = [i for i in feat.get_items_structured() if i["name"] == "milk"]
    assert len(items) == 2
    units = sorted(i["unit"] for i in items)
    assert units == ["cup", "ml"]
    for it in items:
        # Each row tagged to exactly one recipe.
        assert len(it["sources"]) == 1

    # Removing r1 removes only the cup row.
    feat.remove_recipe_layer("r1")
    items = [i for i in feat.get_items_structured() if i["name"] == "milk"]
    assert len(items) == 1
    assert items[0]["unit"] == "ml"


def test_register_layer_idempotent(tmp_path):
    feat, _ = _make(tmp_path)
    feat.register_layer("r1", "Pancakes")
    feat._add_many_detailed(
        [{"name": "flour", "quantity": 1, "unit": "cup"}],
        source={"recipe_id": "r1", "recipe_name": "Pancakes"},
    )
    # Same recipe re-added: one layer, stacked quantity.
    feat.register_layer("r1", "Pancakes")
    feat._add_many_detailed(
        [{"name": "flour", "quantity": 1, "unit": "cup"}],
        source={"recipe_id": "r1", "recipe_name": "Pancakes"},
    )
    layers = feat.get_recipe_layers()
    assert len(layers) == 1
    item = _item_by_name(feat, "flour")
    assert item["quantity"] == 2.0
    assert item["sources"]["r1"]["quantity"] == 2.0


def test_unit_change_detaches_sources(tmp_path):
    feat, _ = _make(tmp_path)
    feat.register_layer("r1", "Pancakes")
    feat._add_many_detailed(
        [{"name": "flour", "quantity": 2, "unit": "cup"}],
        source={"recipe_id": "r1", "recipe_name": "Pancakes"},
    )
    item = _item_by_name(feat, "flour")
    # User changes unit to lb — sources are invalidated.
    feat.update_item(item["id"], {"unit": "lb"})
    item = _item_by_name(feat, "flour")
    assert item["unit"] == "lb"
    assert item["sources"] == {}
    assert item["manual_quantity"] == 2.0

    # remove_recipe_layer drops the layer but leaves the now-manual row.
    feat.remove_recipe_layer("r1")
    assert _item_by_name(feat, "flour") is not None
    assert feat.get_recipe_layers() == []


def test_remove_layer_not_found_returns_empty(tmp_path):
    feat, _ = _make(tmp_path)
    result = feat.remove_recipe_layer("nope")
    assert result["layer"] is None
    assert result["items_removed"] == []
    assert result["items_updated"] == []


def test_manual_add_bumps_manual_quantity(tmp_path):
    """Add via the user-facing `add_item` (no source) should record manual qty."""
    feat, _ = _make(tmp_path)
    feat.add_item("bananas", quantity=3)
    item = _item_by_name(feat, "bananas")
    assert item["quantity"] == 3.0
    assert item["manual_quantity"] == 3.0
    assert item["sources"] == {}


def test_legacy_items_migrated_on_load(tmp_path):
    import json
    gf = tmp_path / "grocery.json"
    gf.write_text(json.dumps({
        "items": [
            {
                "id": "abc",
                "name": "milk",
                "quantity": 2.0,
                "unit": "cup",
                "category": "Dairy",
                "checked": False,
            },
        ],
        "category_order": [],
    }))
    feat = GroceryFeature({"grocery_file": str(gf)})
    item = _item_by_name(feat, "milk")
    assert item["manual_quantity"] == 2.0
    assert item["sources"] == {}


def test_delete_item_leaves_layer_but_drops_provenance(tmp_path):
    feat, _ = _make(tmp_path)
    feat.register_layer("r1", "Pancakes")
    feat._add_many_detailed(
        [{"name": "flour", "quantity": 2, "unit": "cup"}],
        source={"recipe_id": "r1", "recipe_name": "Pancakes"},
    )
    item = _item_by_name(feat, "flour")
    feat.delete_item(item["id"])
    # Layer still present (ghost): removing it is a noop on items.
    assert len(feat.get_recipe_layers()) == 1
    summary = feat.remove_recipe_layer("r1")
    assert summary["layer"]["recipe_id"] == "r1"
    assert summary["items_updated"] == []
    assert summary["items_removed"] == []
