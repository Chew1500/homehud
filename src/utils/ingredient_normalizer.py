"""Normalize messy recipe ingredient rows into clean grocery entries.

Recipe ingredient data is dirty in practice — Claude vision and manually-entered
recipes both emit section headers ("Dijon Salmon:"), full phrases
("to taste salt and pepper"), embedded units ("tablespoon Dijon mustard"), and
prep qualifiers ("butter, melted"). This module is the single deterministic
post-pass for both import-time (`parse_recipe_image`) and grocery-add-time
(`recipe._add_to_grocery`), so either path alone recovers already-stored data.

Public API is one function; rules are kept small and conservative — a hairier
rule that mis-normalizes a real ingredient is worse than letting junk pass
through to the list.
"""

from __future__ import annotations

import re

# Full-name rejects: the row is unusable on its own. Checked case-insensitively
# against the stripped name.
_REJECT_EXACT = frozenset({
    "to taste",
    "as needed",
    "for serving",
    "for garnish",
    "optional",
    "salt and pepper",  # rarely useful on a grocery list; would dup "salt", "pepper"
    "salt and pepper to taste",
})

# If the name STARTS with one of these, the actual item has been lost to a
# malformed parse ("to taste salt and pepper"). Drop it.
_REJECT_PREFIX = (
    "to taste",
    "for serving",
    "for garnish",
    "as needed",
)

# Leading unit tokens to lift into the `unit` field when unit is missing.
# Ordered longest-first so multi-word units win (e.g. "fluid ounce" before
# "ounce"). Lowercase form only — matching strips case.
_LEADING_UNITS = (
    "fluid ounces", "fluid ounce", "fl oz",
    "tablespoons", "tablespoon", "tbsps", "tbsp",
    "teaspoons", "teaspoon", "tsps", "tsp",
    "milliliters", "milliliter",
    "kilograms", "kilogram",
    "pounds", "pound", "lbs", "lb",
    "ounces", "ounce", "oz",
    "grams", "gram",
    "cups", "cup",
    "pints", "pint",
    "quarts", "quart",
    "gallons", "gallon",
    "liters", "liter",
    "cloves", "clove",
    "pinches", "pinch",
    "dashes", "dash",
    "slices", "slice",
    "sticks", "stick",
    "cans", "can",
    "jars", "jar",
    "packages", "package", "packets", "packet",
    "handfuls", "handful",
    "sprigs", "sprig",
    "bunches", "bunch",
    "ml", "mg", "kg", "g", "l",
)

# Trailing ", <word>" qualifiers to move into a `prep` field. Conservative set
# — only common past-participle kitchen preps. "chopped" stays; "for the sauce"
# does not (we'd mangle it).
_PREP_WORDS = frozenset({
    "melted", "softened", "chopped", "diced", "sliced", "minced", "crumbled",
    "grated", "shredded", "peeled", "halved", "quartered", "rinsed", "drained",
    "crushed", "ground", "whole", "fresh", "dried", "frozen", "cooked",
    "cooled", "warmed", "toasted", "roasted", "beaten", "whisked", "cubed",
    "sifted", "zested", "juiced", "trimmed", "pitted", "seeded", "deveined",
    "boneless", "skinless", "uncooked", "unsalted", "salted", "divided",
    "packed", "to taste", "finely chopped", "coarsely chopped", "thinly sliced",
})

_WHITESPACE = re.compile(r"\s+")
_NUMERIC_PREFIX = re.compile(r"^(\d+(?:[./]\d+)?)\s+(.*)$")


def normalize_ingredient(raw: dict) -> dict | None:
    """Clean one ingredient dict. Returns None if the row is not an ingredient.

    Input shape: {"name": str, "quantity": str|None, "unit": str|None, ...}
    Output shape: {"name": str, "quantity": ..., "unit": str|None, "prep": str|None}
    The caller decides which fields to persist.
    """
    name = (raw.get("name") or "").strip()
    if not name:
        return None

    # Trim trailing punctuation that sneaks in from OCR/vision.
    name = name.rstrip(",;:.")
    name = _WHITESPACE.sub(" ", name).strip()
    if not name:
        return None

    # Section headers: "Dijon Salmon:", "Mustard Vinaigrette:"
    if (raw.get("name") or "").strip().endswith(":"):
        return None

    lower = name.lower()
    if lower in _REJECT_EXACT:
        return None
    for prefix in _REJECT_PREFIX:
        if lower == prefix or lower.startswith(prefix + " "):
            return None

    quantity = raw.get("quantity")
    unit = (raw.get("unit") or None)
    prep: str | None = None

    # "butter, melted" → name="butter", prep="melted"
    if "," in name:
        head, _, tail = name.partition(",")
        tail_clean = tail.strip().lower()
        if tail_clean in _PREP_WORDS:
            name = head.strip()
            prep = tail_clean
            lower = name.lower()

    # Leading unit token: "tablespoon Dijon mustard". Only lift when unit is
    # empty — if the LLM already set a unit, trust it.
    if unit is None:
        for tok in _LEADING_UNITS:
            prefix = tok + " "
            if lower.startswith(prefix):
                unit = tok
                name = name[len(prefix):].strip()
                lower = name.lower()
                break

    # Leading standalone numeric like "2 jalapeños" → quantity="2" if missing.
    if quantity in (None, "", 0):
        m = _NUMERIC_PREFIX.match(name)
        if m:
            quantity = m.group(1)
            name = m.group(2).strip()
            lower = name.lower()

    if not name:
        return None

    out = {
        "name": name,
        "quantity": quantity if quantity not in ("", 0) else None,
        "unit": unit,
        "prep": prep,
    }
    # Preserve the pantry-staple flag if present on the incoming record —
    # the normalizer's output is the persisted shape, so dropping the key here
    # would lose the marker on every storage repair pass.
    if raw.get("pantry_staple"):
        out["pantry_staple"] = True
    return out


def normalize_ingredients(raws: list[dict]) -> list[dict]:
    """Normalize a list, dropping rejects. Preserves input order."""
    out: list[dict] = []
    for raw in raws or []:
        cleaned = normalize_ingredient(raw)
        if cleaned is not None:
            out.append(cleaned)
    return out
