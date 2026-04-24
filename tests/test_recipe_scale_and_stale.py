"""Tests for recipe scaling and the stale-pointer fix (Issue A + #5).

Covers:
  - _parse_scale string/word/number handling
  - _apply_scale numeric and fractional forms
  - _active_recommendation is cleared on any non-recommendation execute()
    (prevents the Tortilla Soup bug from recurring)
"""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cooking.storage import RecipeStorage
from features.grocery import GroceryFeature
from features.recipe import (
    RecipeFeature,
    _apply_scale,
    _parse_scale,
)

# -- _parse_scale --

def test_parse_scale_numeric():
    assert _parse_scale(2) == 2.0
    assert _parse_scale(2.5) == 2.5
    assert _parse_scale("2") == 2.0
    assert _parse_scale("1.5") == 1.5


def test_parse_scale_words():
    assert _parse_scale("double") == 2.0
    assert _parse_scale("triple") == 3.0
    assert _parse_scale("half") == 0.5


def test_parse_scale_fraction():
    assert _parse_scale("1/2") == 0.5
    assert _parse_scale("3/4") == 0.75


def test_parse_scale_defaults_on_junk():
    assert _parse_scale(None) == 1.0
    assert _parse_scale("") == 1.0
    assert _parse_scale("gibberish") == 1.0


# -- _apply_scale --

def test_apply_scale_numeric():
    assert _apply_scale(2, 2.0) == ("4", False)
    assert _apply_scale("2", 2.0) == ("4", False)
    assert _apply_scale("1.5", 2.0) == ("3", False)


def test_apply_scale_fraction():
    result, needs_suffix = _apply_scale("1/2", 2.0)
    assert result == "1"
    assert needs_suffix is False


def test_apply_scale_none_quantity():
    # A quantityless ingredient can't be numerically doubled — caller should
    # tag "×2" onto the name so the user sees the scale.
    result, needs_suffix = _apply_scale(None, 2.0)
    assert result is None
    assert needs_suffix is True


def test_apply_scale_identity_is_no_op():
    assert _apply_scale("2", 1.0) == ("2", False)
    assert _apply_scale(None, 1.0) == (None, False)


def test_apply_scale_non_numeric_string():
    # "a pinch" can't be scaled numerically — needs suffix.
    result, needs_suffix = _apply_scale("a pinch", 2.0)
    assert needs_suffix is True


# -- Stale pointer fix (Issue A) --

def _recipe_storage(tmp_path, recipes):
    path = tmp_path / "recipes.json"
    path.write_text(json.dumps(recipes))
    return RecipeStorage(path)


def test_active_recommendation_cleared_on_search(tmp_path):
    """Calling search after recommend must drop the stale active pointer.

    Regression guard for Issue A: the user said "what gnocchi recipes do I
    have?" and the stale Tortilla Soup recommendation pointer caused "add it"
    to dump the wrong recipe's ingredients.
    """
    storage = _recipe_storage(tmp_path, [
        {"id": "1", "name": "Tortilla Soup", "ingredients": []},
        {"id": "2", "name": "Skillet Gnocchi", "ingredients": []},
    ])
    recipe = RecipeFeature(
        {}, llm=MagicMock(), recipe_storage=storage,
        grocery_feature=None, cooking_session=None,
    )
    # Simulate an active recommendation lingering from a prior turn.
    recipe._active_recommendation = {"id": "1", "name": "Tortilla Soup"}
    recipe._recommendation_context = "something warm"

    # User pivots to a search — this is the exact sequence from the bug.
    recipe.execute("search", {"query": "gnocchi"})

    assert recipe._active_recommendation is None
    assert recipe._recommendation_context is None


def test_active_recommendation_kept_across_refine(tmp_path):
    """Refinement of a recommendation shouldn't clear the pointer."""
    storage = _recipe_storage(tmp_path, [
        {"id": "1", "name": "A", "ingredients": [], "tags": []},
        {"id": "2", "name": "B", "ingredients": [], "tags": []},
    ])
    llm = MagicMock()
    llm.respond.return_value = "B"
    recipe = RecipeFeature(
        {}, llm=llm, recipe_storage=storage,
        grocery_feature=None, cooking_session=None,
    )
    recipe._active_recommendation = {"id": "1", "name": "A"}

    recipe.execute("refine_recommendation", {"feedback": "different"})

    # refine may update the pointer but shouldn't blank it out.
    assert recipe._active_recommendation is not None


# -- End-to-end scaling through _add_to_grocery --

def test_add_ingredients_with_scale_doubles_quantities(tmp_path):
    storage = _recipe_storage(tmp_path, [{
        "id": "1", "name": "Pasta", "ingredients": [
            {"name": "pasta", "quantity": "200", "unit": "grams"},
            {"name": "olive oil", "quantity": "2", "unit": "tbsp"},
            {"name": "garlic", "quantity": None, "unit": None},
        ],
    }])
    grocery = GroceryFeature({"grocery_file": str(tmp_path / "groc.json")})
    recipe = RecipeFeature(
        {}, llm=MagicMock(), recipe_storage=storage,
        grocery_feature=grocery, cooking_session=None,
    )

    recipe.execute(
        "add_ingredients_to_grocery",
        {"recipe_name": "Pasta", "scale": 2.0},
    )

    stored = json.loads((tmp_path / "groc.json").read_text())
    # Flatten to names/quantities for comparison
    items = stored.get("items") if isinstance(stored, dict) else stored
    by_name = {i["name"]: i for i in items}
    # Grocery may coerce quantity to float; compare numerically.
    assert float(by_name["pasta"]["quantity"]) == 400.0
    assert float(by_name["olive oil"]["quantity"]) == 4.0
    # Quantity-less ingredient gets ×2 suffix on name.
    assert any("garlic" in n and "×2" in n for n in by_name)
