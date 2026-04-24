"""Tests for the recipe-ingredient normalizer.

The failure cases below are lifted directly from the Dijon Salmon session
(one grocery-add produced 21 entries including section headers, embedded
units, and prep qualifiers).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from utils.ingredient_normalizer import normalize_ingredient, normalize_ingredients


def test_section_header_rejected():
    # "Dijon Salmon:" and "Mustard Vinaigrette:" are recipe section labels,
    # not ingredients.
    assert normalize_ingredient({"name": "Dijon Salmon:"}) is None
    assert normalize_ingredient({"name": "Mustard Vinaigrette:"}) is None


def test_to_taste_rejected():
    # "to taste salt and pepper" is malformed — the actual ingredient was lost.
    assert normalize_ingredient({"name": "to taste salt and pepper"}) is None
    assert normalize_ingredient({"name": "To taste"}) is None


def test_pure_stopwords_rejected():
    assert normalize_ingredient({"name": "optional"}) is None
    assert normalize_ingredient({"name": "For serving"}) is None
    assert normalize_ingredient({"name": "as needed"}) is None


def test_empty_rejected():
    assert normalize_ingredient({"name": ""}) is None
    assert normalize_ingredient({"name": "   "}) is None
    assert normalize_ingredient({}) is None


def test_leading_unit_moved_to_unit_field():
    out = normalize_ingredient({"name": "tablespoon Dijon mustard"})
    assert out == {
        "name": "Dijon mustard",
        "quantity": None,
        "unit": "tablespoon",
        "prep": None,
    }


def test_leading_unit_preserves_existing_unit():
    # If unit is already set, don't touch the name.
    out = normalize_ingredient(
        {"name": "tablespoon Dijon mustard", "unit": "cup"}
    )
    assert out["name"] == "tablespoon Dijon mustard"
    assert out["unit"] == "cup"


def test_leading_unit_multiword_wins():
    # "fluid ounces" should win over "ounces".
    out = normalize_ingredient({"name": "fluid ounces olive oil"})
    assert out["name"] == "olive oil"
    assert out["unit"] == "fluid ounces"


def test_prep_comma_split():
    out = normalize_ingredient({"name": "butter, melted"})
    assert out["name"] == "butter"
    assert out["prep"] == "melted"


def test_prep_only_for_known_words():
    # "for the sauce" is not a prep word — don't mangle.
    out = normalize_ingredient({"name": "olive oil, for the sauce"})
    assert out["name"] == "olive oil, for the sauce"
    assert out["prep"] is None


def test_prep_case_insensitive():
    out = normalize_ingredient({"name": "onion, Chopped"})
    assert out["name"] == "onion"
    assert out["prep"] == "chopped"


def test_leading_numeric_extracted():
    out = normalize_ingredient({"name": "2 jalapeños"})
    assert out["quantity"] == "2"
    assert out["name"] == "jalapeños"


def test_leading_numeric_preserves_existing_quantity():
    out = normalize_ingredient({"name": "2 jalapeños", "quantity": "3"})
    assert out["quantity"] == "3"
    assert out["name"] == "2 jalapeños"  # quantity already set, don't touch


def test_trailing_punctuation_stripped():
    out = normalize_ingredient({"name": "olive oil,"})
    assert out["name"] == "olive oil"


def test_whitespace_collapsed():
    out = normalize_ingredient({"name": "  olive   oil  "})
    assert out["name"] == "olive oil"


def test_clean_ingredient_passthrough():
    # Already-clean rows should round-trip cleanly.
    out = normalize_ingredient(
        {"name": "olive oil", "quantity": "2", "unit": "tablespoons"}
    )
    assert out == {
        "name": "olive oil",
        "quantity": "2",
        "unit": "tablespoons",
        "prep": None,
    }


def test_normalize_ingredients_drops_rejects():
    # Slice of real session data: 7 entries → 4 valid.
    raws = [
        {"name": "Dijon Salmon:"},
        {"name": "salmon fillet"},
        {"name": "Dijon mustard"},
        {"name": "to taste salt and pepper"},
        {"name": "Italian-style dry bread crumbs"},
        {"name": "butter, melted"},
        {"name": "Mustard Vinaigrette:"},
    ]
    cleaned = normalize_ingredients(raws)
    names = [c["name"] for c in cleaned]
    assert names == [
        "salmon fillet",
        "Dijon mustard",
        "Italian-style dry bread crumbs",
        "butter",
    ]
    # butter entry carries prep="melted"
    butter = next(c for c in cleaned if c["name"] == "butter")
    assert butter["prep"] == "melted"


def test_dijon_mustard_normalization():
    # Main observed failure: "tablespoon Dijon mustard" should become a clean
    # ingredient with unit lifted.
    out = normalize_ingredient({"name": "tablespoon Dijon mustard"})
    assert out["name"] == "Dijon mustard"
    assert out["unit"] == "tablespoon"
