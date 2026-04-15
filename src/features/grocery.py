"""Grocery list feature — add, remove, list, and clear items via voice."""

from __future__ import annotations

import json
import logging
import re
import uuid
from pathlib import Path

from features.base import BaseFeature

log = logging.getLogger("home-hud.features.grocery")

# Fast check: does the text mention grocery/shopping list at all?
_ANY_GROCERY = re.compile(r"\b(grocery|shopping)\s+(list)\b", re.IGNORECASE)

# Specific action patterns
_ADD = re.compile(
    r"\badd\s+(.+?)\s+to\s+(?:the\s+)?(?:grocery|shopping)\s+list\b",
    re.IGNORECASE,
)
_REMOVE = re.compile(
    r"\b(?:remove|delete|take off)\s+(.+?)\s+(?:from|off)\s+"
    r"(?:the\s+)?(?:grocery|shopping)\s+list\b",
    re.IGNORECASE,
)
_CLEAR = re.compile(
    r"\b(?:clear|empty|reset)\s+(?:the\s+)?(?:grocery|shopping)\s+list\b",
    re.IGNORECASE,
)
_LIST = re.compile(
    r"\b(?:what(?:'s| is) on|show|read|list)\s+(?:the\s+)?(?:grocery|shopping)\s+list\b",
    re.IGNORECASE,
)

DEFAULT_CATEGORIES = [
    "Produce",
    "Dairy",
    "Meat & Seafood",
    "Bakery",
    "Pantry",
    "Frozen",
    "Beverages",
    "Household",
    "Uncategorized",
]

UNCATEGORIZED = "Uncategorized"

# -- Quantity / unit helpers ------------------------------------------------

# Aliases map any recognized form to a canonical singular.
_UNIT_ALIASES = {
    "cup": "cup", "cups": "cup",
    "tsp": "tsp", "teaspoon": "tsp", "teaspoons": "tsp",
    "tbsp": "tbsp", "tablespoon": "tbsp", "tablespoons": "tbsp",
    "lb": "lb", "lbs": "lb", "pound": "lb", "pounds": "lb",
    "oz": "oz", "ounce": "oz", "ounces": "oz",
    "g": "g", "gram": "g", "grams": "g",
    "kg": "kg", "kilogram": "kg", "kilograms": "kg",
    "ml": "ml", "milliliter": "ml", "milliliters": "ml",
    "l": "l", "liter": "l", "liters": "l", "litre": "l", "litres": "l",
    "clove": "clove", "cloves": "clove",
    "piece": "piece", "pieces": "piece",
    "slice": "slice", "slices": "slice",
    "can": "can", "cans": "can",
    "pack": "pack", "packs": "pack",
    "bottle": "bottle", "bottles": "bottle",
    "dozen": "dozen", "dozens": "dozen",
    "bunch": "bunch", "bunches": "bunch",
    "stick": "stick", "sticks": "stick",
    "head": "head", "heads": "head",
}

# Regex that recognizes a leading quantity optionally followed by a known unit.
# Used for v2 migration and legacy LLM string parsing.
_QTY_UNIT_RE = re.compile(
    r"^\s*(?P<qty>\d+\s+\d+/\d+|\d+/\d+|\d+(?:\.\d+)?)"
    r"(?:\s+(?P<unit>cups?|tsp|teaspoons?|tbsp|tablespoons?|lbs?|pounds?|"
    r"oz|ounces?|g|grams?|kg|kilograms?|ml|milliliters?|l|liters?|litres?|"
    r"cloves?|pieces?|slices?|cans?|packs?|bottles?|dozens?|bunch(?:es)?|"
    r"sticks?|heads?))?"
    r"\s+(?P<name>.+?)\s*$",
    re.IGNORECASE,
)


def _parse_quantity(value) -> float | None:
    """Parse numeric quantity from int, float, or string (incl. fractions)."""
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value) if value else None
    if not isinstance(value, str):
        return None
    s = value.strip()
    if not s:
        return None
    m = re.match(r"^(\d+)\s+(\d+)\s*/\s*(\d+)$", s)
    if m:
        whole, num, den = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if den == 0:
            return None
        return float(whole) + num / den
    m = re.match(r"^(\d+)\s*/\s*(\d+)$", s)
    if m:
        num, den = int(m.group(1)), int(m.group(2))
        if den == 0:
            return None
        return num / den
    try:
        f = float(s)
        return f if f else None
    except ValueError:
        return None


def _normalize_unit(unit) -> str | None:
    """Map any unit form to its canonical singular, or None."""
    if not unit:
        return None
    if not isinstance(unit, str):
        return None
    u = unit.strip().lower()
    if not u:
        return None
    return _UNIT_ALIASES.get(u, u)


def _normalize_name(name: str) -> str:
    """Lowercase + trailing-s strip for matching only (stored name unchanged)."""
    n = (name or "").strip().lower()
    if len(n) > 3 and n.endswith("s") and not n.endswith("ss"):
        n = n[:-1]
    return n


def _parse_entry_from_string(s: str) -> dict:
    """Parse '2 cups flour' → {name, quantity, unit}.

    Returns an entry dict. If the string has no recognizable leading
    quantity, quantity/unit are None and name is the raw string.
    """
    s = (s or "").strip()
    if not s:
        return {"name": "", "quantity": None, "unit": None}
    m = _QTY_UNIT_RE.match(s)
    if not m:
        return {"name": s, "quantity": None, "unit": None}
    qty = _parse_quantity(m.group("qty"))
    unit = _normalize_unit(m.group("unit"))
    name = (m.group("name") or "").strip()
    if not name:
        return {"name": s, "quantity": None, "unit": None}
    return {"name": name, "quantity": qty, "unit": unit}


def _split_item_phrase(phrase: str) -> list[str]:
    """Split a natural-language item phrase into individual item names.

    Handles "a, b, c", "a, b, and c", "a and b".
    """
    if not phrase:
        return []
    # Normalize " and " / " & " to commas, then split.
    normalized = re.sub(r"\s*,?\s+(?:and|&)\s+", ",", phrase, flags=re.IGNORECASE)
    parts = [p.strip() for p in normalized.split(",")]
    return [p for p in parts if p]


def _extract_entries(parameters: dict) -> list[dict]:
    """Pull structured entries out of LLM-supplied parameters.

    Accepts:
      - items: list[dict] where each dict has {name, quantity?, unit?}
      - items: list[str] (legacy) — each string parsed via _parse_entry_from_string
      - item: str or list[str] (legacy)
    Returns a list of {name, quantity, unit} dicts.
    """
    raw = parameters.get("items")
    if raw is None:
        raw = parameters.get("item")
    if raw is None:
        return []
    out: list[dict] = []

    def add_string(s: str) -> None:
        for piece in _split_item_phrase(s):
            entry = _parse_entry_from_string(piece)
            if entry["name"]:
                out.append(entry)

    if isinstance(raw, str):
        add_string(raw)
        return out
    if isinstance(raw, list):
        for entry in raw:
            if isinstance(entry, str):
                add_string(entry)
            elif isinstance(entry, dict):
                name = (entry.get("name") or "").strip()
                if not name:
                    continue
                out.append({
                    "name": name,
                    "quantity": _parse_quantity(entry.get("quantity")),
                    "unit": _normalize_unit(entry.get("unit")),
                })
    return out


def _format_qty(q: float | None) -> str:
    if q is None:
        return ""
    if q == int(q):
        return str(int(q))
    # Trim trailing zeros on floats
    s = f"{q:.2f}".rstrip("0").rstrip(".")
    return s


def _format_item_short(item: dict) -> str:
    """Render an item for display/voice: '2 cups flour', '8 cantaloupes', 'milk'."""
    name = item.get("name", "")
    q = item.get("quantity")
    u = item.get("unit")
    parts: list[str] = []
    if q is not None:
        parts.append(_format_qty(q))
    if u:
        if q is not None and q != 1 and not u.endswith("s"):
            parts.append(u + "s")
        else:
            parts.append(u)
        parts.append(name)
    else:
        if q is not None and q != 1 and name and not name.endswith("s"):
            parts.append(name + "s")
        else:
            parts.append(name)
    return " ".join(p for p in parts if p)


def _join_names(names: list[str]) -> str:
    if not names:
        return ""
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]} and {names[1]}"
    return ", ".join(names[:-1]) + f", and {names[-1]}"


class GroceryFeature(BaseFeature):
    """Manages a grocery list stored as a JSON file.

    Storage shape (v3):
        {
          "items": [
            {"id": "...", "name": "flour", "quantity": 2.0, "unit": "cup",
             "category": "Pantry", "checked": false},
            ...
          ],
          "category_order": ["Produce", "Dairy", ...]
        }

    Legacy v1 (bare list of strings) and v2 (item dicts without quantity/unit)
    are migrated transparently by `_load_state` — v2 item names with a leading
    quantity (e.g. "2 cups flour") get parsed into structured fields.
    """

    def __init__(self, config: dict):
        super().__init__(config)
        self._path = Path(config.get("grocery_file", "data/grocery.json"))

    @property
    def name(self) -> str:
        return "Grocery List"

    @property
    def short_description(self) -> str:
        return "Manage your grocery and shopping lists"

    @property
    def description(self) -> str:
        return (
            'Grocery/shopping list: triggered by "grocery list" or "shopping list". '
            'Commands: "add X to grocery list", "remove X from grocery list", '
            '"what\'s on the grocery list", "clear the grocery list".'
        )

    def matches(self, text: str) -> bool:
        return bool(_ANY_GROCERY.search(text))

    @property
    def action_schema(self) -> dict:
        return {
            "add": {"items": "list[{name, quantity?, unit?}] or list[str]"},
            "remove": {"item": "str"},
            "list": {},
            "clear": {},
        }

    def execute(self, action: str, parameters: dict) -> str:
        if action == "add":
            entries = _extract_entries(parameters)
            if not entries:
                return self._list()
            return self._add_many(entries)
        if action == "remove":
            return self._remove(parameters["item"])
        if action == "list":
            return self._list()
        if action == "clear":
            return self._clear()
        return self._list()

    def handle(self, text: str) -> str:
        m = _ADD.search(text)
        if m:
            names = _split_item_phrase(m.group(1))
            entries = [_parse_entry_from_string(n) for n in names if n]
            entries = [e for e in entries if e["name"]]
            if entries:
                return self._add_many(entries)
            return self._list()

        m = _REMOVE.search(text)
        if m:
            return self._remove(m.group(1).strip())

        if _CLEAR.search(text):
            return self._clear()

        if _LIST.search(text):
            return self._list()

        # Fallback: "grocery list" was mentioned but no sub-command matched
        return self._list()

    # -- Voice actions (operate on the dict model but return user-facing text) --

    def _add_many(self, entries: list[dict]) -> str:
        msg, _ = self._add_many_detailed(entries)
        return msg

    def _add_many_detailed(
        self, entries: list[dict]
    ) -> tuple[str, dict]:
        """Core add/merge logic. Returns (voice_response, detail_dict).

        detail_dict = {
          "added": [item, ...],        # brand-new rows
          "merged": [item, ...],        # existing rows whose qty was updated
          "mixed_units": [item, ...],   # appended because unit clashed
          "skipped_dup": [item, ...],   # plain None-unit duplicate, no change
        }
        """
        state = self._load_state()
        items = state["items"]
        added: list[dict] = []
        merged: list[dict] = []
        mixed: list[dict] = []
        skipped: list[dict] = []
        changed = False

        for entry in entries:
            name = (entry.get("name") or "").strip()
            if not name:
                continue
            in_qty = entry.get("quantity")
            if in_qty is not None and not isinstance(in_qty, (int, float)):
                in_qty = _parse_quantity(in_qty)
            in_unit = _normalize_unit(entry.get("unit"))
            in_cat = entry.get("category")
            key = _normalize_name(name)

            same_name = [
                it for it in items if _normalize_name(it.get("name", "")) == key
            ]

            # 1. Exact (name, unit) match — merge quantities.
            target = next(
                (
                    it for it in same_name
                    if _normalize_unit(it.get("unit")) == in_unit
                ),
                None,
            )
            if target is not None:
                ex_qty = target.get("quantity")
                ex_unit = _normalize_unit(target.get("unit"))
                if ex_unit is None and in_unit is None:
                    if in_qty is None:
                        # Plain bare dup — preserve legacy "already on" behavior.
                        skipped.append(dict(target))
                        continue
                    # Bump: treat existing None as 1 when incoming has qty.
                    base = 1.0 if ex_qty is None else float(ex_qty)
                    target["quantity"] = base + float(in_qty)
                else:
                    a = float(ex_qty) if ex_qty is not None else 0.0
                    b = float(in_qty) if in_qty is not None else 0.0
                    if (a + b) > 0:
                        target["quantity"] = a + b
                merged.append(dict(target))
                changed = True
                continue

            # 2. Same name but existing is bare (no unit) and incoming has a
            #    unit — adopt the incoming unit and sum quantities.
            bare = next(
                (
                    it for it in same_name
                    if _normalize_unit(it.get("unit")) is None
                ),
                None,
            )
            if bare is not None and in_unit is not None:
                ex_qty = bare.get("quantity")
                a = 1.0 if ex_qty is None else float(ex_qty)
                b = float(in_qty) if in_qty is not None else 1.0
                bare["quantity"] = a + b
                bare["unit"] = in_unit
                merged.append(dict(bare))
                changed = True
                continue

            # 3. Same name but units are incompatible — append as separate row.
            if same_name:
                new_item = self._new_item(
                    name, in_cat, quantity=in_qty, unit=in_unit,
                )
                items.append(new_item)
                mixed.append({
                    "new": dict(new_item),
                    "existing": [dict(it) for it in same_name],
                })
                changed = True
                continue

            # 4. Brand new.
            new_item = self._new_item(
                name, in_cat, quantity=in_qty, unit=in_unit,
            )
            items.append(new_item)
            added.append(dict(new_item))
            changed = True

        if changed:
            self._save_state(state)

        detail = {
            "added": added,
            "merged": merged,
            "mixed_units": mixed,
            "skipped_dup": skipped,
        }
        return self._format_add_response(detail, len(items)), detail

    def _format_add_response(self, detail: dict, total: int) -> str:
        added = detail["added"]
        merged = detail["merged"]
        mixed = detail["mixed_units"]
        skipped = detail["skipped_dup"]

        total_s = "item" if total == 1 else "items"

        created_names = (
            [_format_item_short(a) for a in added]
            + [_format_item_short(m["new"]) for m in mixed]
        )
        merged_names = [_format_item_short(m) for m in merged]
        skipped_names = [s["name"] for s in skipped]

        if created_names and not merged and not skipped:
            return (
                f"Added {_join_names(created_names)} to the grocery list. "
                f"You now have {total} {total_s}."
            )
        if created_names and (merged or skipped):
            parts = [f"Added {_join_names(created_names)}."]
            if merged:
                parts.append(
                    f"Updated {_join_names(merged_names)}."
                )
            if skipped:
                was = "was" if len(skipped_names) == 1 else "were"
                parts.append(
                    f"{_join_names(skipped_names)} {was} already on the list."
                )
            parts.append(f"You now have {total} {total_s}.")
            return " ".join(parts)
        if not created_names and merged and not skipped:
            return (
                f"Updated {_join_names(merged_names)}. "
                f"You now have {total} {total_s}."
            )
        if not created_names and merged and skipped:
            was = "was" if len(skipped_names) == 1 else "were"
            return (
                f"Updated {_join_names(merged_names)}. "
                f"{_join_names(skipped_names)} {was} already on the list."
            )
        if not created_names and not merged and skipped:
            if len(skipped_names) == 1:
                return f"{skipped_names[0]} is already on the grocery list."
            return f"{_join_names(skipped_names)} are already on the grocery list."
        return self._list()

    def _remove(self, item: str) -> str:
        state = self._load_state()
        items = state["items"]
        key = _normalize_name(item)
        idx = next(
            (i for i, it in enumerate(items)
             if _normalize_name(it.get("name", "")) == key),
            -1,
        )
        if idx < 0:
            return f"{item} is not on the grocery list."
        removed = items.pop(idx)["name"]
        self._save_state(state)
        count = len(items)
        s = "item" if count == 1 else "items"
        return f"Removed {removed} from the grocery list. You now have {count} {s}."

    def _list(self) -> str:
        items = self._load_state()["items"]
        if not items:
            return "The grocery list is empty."
        names = [_format_item_short(i) for i in items]
        if len(names) == 1:
            return f"You have one item on the grocery list: {names[0]}."
        joined = ", ".join(names[:-1]) + f", and {names[-1]}"
        return f"You have {len(names)} items on the grocery list: {joined}."

    def _clear(self) -> str:
        state = self._load_state()
        state["items"] = []
        self._save_state(state)
        return "The grocery list has been cleared."

    def get_items(self) -> list[str]:
        """Return the current grocery list items as formatted strings.

        Each string includes quantity/unit if present (e.g. "2 cups flour").
        """
        return [_format_item_short(i) for i in self._load_state()["items"]]

    def get_items_structured(self) -> list[dict]:
        """Return the current grocery list as structured dicts (read-only copy)."""
        return [dict(i) for i in self._load_state()["items"]]

    # -- Web API surface --

    def get_state(self) -> dict:
        """Return the full list state for the web UI."""
        state = self._load_state()
        return {
            "items": [dict(i) for i in state["items"]],
            "category_order": list(state["category_order"]),
            "categories": list(DEFAULT_CATEGORIES),
        }

    def add_item(
        self,
        name: str,
        category: str | None = None,
        quantity=None,
        unit: str | None = None,
    ) -> dict | None:
        """Add an item from the web UI. Routes through the merge logic.

        Returns the resulting (new or merged) item dict, or None if the add
        was a plain duplicate (None-unit, None-qty and the item already exists).
        """
        name = (name or "").strip()
        if not name:
            return None
        entry = {
            "name": name,
            "quantity": _parse_quantity(quantity),
            "unit": _normalize_unit(unit),
            "category": category,
        }
        _, detail = self._add_many_detailed([entry])
        if detail["added"]:
            return dict(detail["added"][0])
        if detail["merged"]:
            return dict(detail["merged"][0])
        if detail["mixed_units"]:
            return dict(detail["mixed_units"][0]["new"])
        return None

    def update_item(self, item_id: str, patch: dict) -> dict | None:
        """Update fields on an item (name, category, checked, quantity, unit)."""
        state = self._load_state()
        for it in state["items"]:
            if it["id"] == item_id:
                if "name" in patch and isinstance(patch["name"], str):
                    it["name"] = patch["name"].strip() or it["name"]
                if "category" in patch:
                    it["category"] = patch["category"] or UNCATEGORIZED
                if "checked" in patch:
                    it["checked"] = bool(patch["checked"])
                if "quantity" in patch:
                    it["quantity"] = _parse_quantity(patch["quantity"])
                if "unit" in patch:
                    it["unit"] = _normalize_unit(patch["unit"])
                self._save_state(state)
                return dict(it)
        return None

    def delete_item(self, item_id: str) -> bool:
        state = self._load_state()
        before = len(state["items"])
        state["items"] = [i for i in state["items"] if i["id"] != item_id]
        if len(state["items"]) == before:
            return False
        self._save_state(state)
        return True

    def reorder_items(self, ids: list[str]) -> None:
        """Reorder items to match the given id sequence; unknown ids are dropped,
        missing ids are appended in their original order."""
        state = self._load_state()
        by_id = {i["id"]: i for i in state["items"]}
        new_order = [by_id[i] for i in ids if i in by_id]
        seen = {i["id"] for i in new_order}
        new_order.extend(i for i in state["items"] if i["id"] not in seen)
        state["items"] = new_order
        self._save_state(state)

    def set_category_order(self, order: list[str]) -> list[str]:
        state = self._load_state()
        # Keep only known categories, append any missing defaults at the end
        filtered = [c for c in order if c in DEFAULT_CATEGORIES]
        for c in DEFAULT_CATEGORIES:
            if c not in filtered:
                filtered.append(c)
        state["category_order"] = filtered
        self._save_state(state)
        return filtered

    def clear_checked(self) -> int:
        state = self._load_state()
        before = len(state["items"])
        state["items"] = [i for i in state["items"] if not i.get("checked")]
        removed = before - len(state["items"])
        if removed:
            self._save_state(state)
        return removed

    def apply_categories(self, mapping: dict[str, str]) -> None:
        """Fill in category for any items whose name matches (case-insensitive)."""
        if not mapping:
            return
        lower = {k.lower(): v for k, v in mapping.items()}
        state = self._load_state()
        changed = False
        for it in state["items"]:
            if not it.get("category") or it["category"] == UNCATEGORIZED:
                cat = lower.get(it["name"].lower())
                if cat:
                    it["category"] = cat
                    changed = True
        if changed:
            self._save_state(state)

    def uncategorized_names(self) -> list[str]:
        """Return names of items still needing LLM categorization."""
        return [
            i["name"] for i in self._load_state()["items"]
            if not i.get("category") or i["category"] == UNCATEGORIZED
        ]

    # -- Persistence --

    @staticmethod
    def _new_item(
        name: str,
        category: str | None = None,
        quantity=None,
        unit: str | None = None,
    ) -> dict:
        q = quantity
        if q is not None and not isinstance(q, (int, float)):
            q = _parse_quantity(q)
        return {
            "id": uuid.uuid4().hex,
            "name": name,
            "quantity": q,
            "unit": _normalize_unit(unit),
            "category": category or UNCATEGORIZED,
            "checked": False,
        }

    def _default_state(self) -> dict:
        return {
            "items": [],
            "category_order": list(DEFAULT_CATEGORIES),
        }

    def _load_state(self) -> dict:
        if not self._path.exists():
            return self._default_state()
        try:
            data = json.loads(self._path.read_text())
        except (json.JSONDecodeError, OSError):
            log.warning("Grocery file corrupted or unreadable, resetting")
            return self._default_state()

        migrated = False

        # Legacy v1: bare list of strings
        if isinstance(data, list):
            state = self._default_state()
            state["items"] = []
            for s in data:
                if not isinstance(s, str):
                    continue
                parsed = _parse_entry_from_string(s)
                state["items"].append(self._new_item(
                    parsed["name"] or s,
                    quantity=parsed["quantity"],
                    unit=parsed["unit"],
                ))
            self._save_state(state)
            return state

        if not isinstance(data, dict):
            log.warning("Grocery file has unexpected format, resetting")
            return self._default_state()

        items_raw = data.get("items", [])
        items: list[dict] = []
        for entry in items_raw:
            if isinstance(entry, str):
                parsed = _parse_entry_from_string(entry)
                items.append(self._new_item(
                    parsed["name"] or entry,
                    quantity=parsed["quantity"],
                    unit=parsed["unit"],
                ))
                migrated = True
                continue
            if not isinstance(entry, dict) or not entry.get("name"):
                continue

            has_qty_key = "quantity" in entry
            has_unit_key = "unit" in entry
            name = entry["name"]
            qty = entry.get("quantity")
            unit = entry.get("unit")

            # v2 migration: parse leading qty/unit out of name string when
            # structured fields aren't present on the record yet.
            if not has_qty_key and not has_unit_key:
                parsed = _parse_entry_from_string(name)
                if parsed["quantity"] is not None or parsed["unit"]:
                    name = parsed["name"]
                    qty = parsed["quantity"]
                    unit = parsed["unit"]
                    migrated = True

            items.append({
                "id": entry.get("id") or uuid.uuid4().hex,
                "name": name,
                "quantity": _parse_quantity(qty),
                "unit": _normalize_unit(unit),
                "category": entry.get("category") or UNCATEGORIZED,
                "checked": bool(entry.get("checked", False)),
            })

        category_order = data.get("category_order")
        if not isinstance(category_order, list) or not category_order:
            category_order = list(DEFAULT_CATEGORIES)
        else:
            # Ensure all defaults are represented
            for c in DEFAULT_CATEGORIES:
                if c not in category_order:
                    category_order.append(c)

        state = {"items": items, "category_order": category_order}
        if migrated:
            self._save_state(state)
        return state

    def _save_state(self, state: dict) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(state, indent=2) + "\n")
