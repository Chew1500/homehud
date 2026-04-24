"""Grocery list feature — add, remove, list, and clear items via voice."""

from __future__ import annotations

import json
import logging
import re
import time
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

    Storage shape (v4):
        {
          "items": [
            {"id": "...", "name": "flour", "quantity": 2.0, "unit": "cup",
             "category": "Pantry", "checked": false,
             "sources": {"<recipe_id>": {"quantity": 2.0, "recipe_name": "..."}},
             "manual_quantity": 0.0},
            ...
          ],
          "category_order": ["Produce", "Dairy", ...],
          "recipe_layers": [
            {"recipe_id": "...", "recipe_name": "...", "added_at": "iso8601"}
          ]
        }

    Layer invariant (when units align): item.quantity ==
        manual_quantity + sum(sources[*].quantity). Manual edits to the top-level
        quantity are captured by the manual_quantity delta, so a later
        remove_recipe_layer still pulls the exact recipe-contributed amount.

    Legacy v1 (bare list of strings) and v2 (item dicts without quantity/unit)
    are migrated transparently by `_load_state`. v3 records (no sources /
    manual_quantity) are upgraded on load by seeding manual_quantity=quantity.
    """

    def __init__(self, config: dict):
        super().__init__(config)
        self._path = Path(config.get("grocery_file", "data/grocery.json"))
        # In-memory trash for undo. Bounded at 20 entries; each entry carries
        # a monotonic timestamp. A 10-minute window is enforced on restore.
        # Deliberately not persisted — covers the observed "oops, put those
        # back" case without adding another file to manage.
        from collections import deque
        self._trash: deque = deque(maxlen=20)

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
            "restore": {"item": "str"},
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
            return self._clear_with_confirmation()
        # Internal action the router replays after the user confirms. Not in
        # the LLM-facing schema — no way for a stray intent to call it.
        if action == "clear_confirmed":
            return self._clear()
        if action == "restore":
            return self._restore(parameters.get("item"))
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
        self, entries: list[dict], *, source: dict | None = None
    ) -> tuple[str, dict]:
        """Core add/merge logic. Returns (voice_response, detail_dict).

        When `source={"recipe_id", "recipe_name"}` is given, the contributed
        quantity is recorded per-item under `sources[recipe_id]` (and does NOT
        touch `manual_quantity`). When `source` is None, the contribution lands
        in `manual_quantity` — matching legacy single-item add semantics.

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

        src_id = source.get("recipe_id") if source else None
        src_name = (source.get("recipe_name") or "") if source else ""

        def record_contribution(item: dict, qty: float) -> None:
            """Attribute `qty` on `item` to the active source (recipe or manual)."""
            if src_id:
                entry = item["sources"].get(src_id)
                if entry is None:
                    item["sources"][src_id] = {
                        "quantity": float(qty),
                        "recipe_name": src_name,
                    }
                else:
                    entry["quantity"] = float(entry.get("quantity") or 0.0) + float(qty)
                    if src_name and not entry.get("recipe_name"):
                        entry["recipe_name"] = src_name
            else:
                item["manual_quantity"] = float(item.get("manual_quantity") or 0.0) + float(qty)

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
                added_qty: float = 0.0
                if ex_unit is None and in_unit is None:
                    if in_qty is None:
                        # Plain bare dup — preserve legacy "already on" behavior.
                        skipped.append(dict(target))
                        continue
                    # Bump: treat existing None as 1 when incoming has qty.
                    base = 1.0 if ex_qty is None else float(ex_qty)
                    target["quantity"] = base + float(in_qty)
                    added_qty = float(in_qty)
                else:
                    a = float(ex_qty) if ex_qty is not None else 0.0
                    b = float(in_qty) if in_qty is not None else 0.0
                    if (a + b) > 0:
                        target["quantity"] = a + b
                    added_qty = b
                record_contribution(target, added_qty)
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
                record_contribution(bare, b)
                merged.append(dict(bare))
                changed = True
                continue

            # 3. Same name but units are incompatible — append as separate row.
            if same_name:
                new_item = self._new_item(
                    name, in_cat, quantity=in_qty, unit=in_unit, source=source,
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
                name, in_cat, quantity=in_qty, unit=in_unit, source=source,
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
        removed = items.pop(idx)
        self._save_state(state)
        self._push_trash([removed])
        count = len(items)
        s = "item" if count == 1 else "items"
        return f"Removed {removed['name']} from the grocery list. You now have {count} {s}."

    def _list(self) -> str:
        items = self._load_state()["items"]
        if not items:
            return "The grocery list is empty."
        names = [_format_item_short(i) for i in items]
        if len(names) == 1:
            return f"You have one item on the grocery list: {names[0]}."
        joined = ", ".join(names[:-1]) + f", and {names[-1]}"
        return f"You have {len(names)} items on the grocery list: {joined}."

    def _clear_with_confirmation(self) -> str:
        """Route `clear` through the router's pending-confirmation primitive.

        Regression guard for Issue B: the user said "remove those ingredients"
        and the LLM mapped it to `clear()`, wiping the entire list. Now any
        clear prompts 'say confirm' first. Single-item lists and empty lists
        skip the gate — no dangerous ambiguity there.
        """
        state = self._load_state()
        count = len(state["items"])
        if count == 0:
            return "The grocery list is already empty."
        if count == 1:
            # Too trivial to gate — just clear.
            return self._clear()

        router = getattr(self, "_router", None)
        if router is None or not hasattr(router, "request_confirmation"):
            # No router wired (tests, display-only mode) — fall back to
            # immediate clear. The trash buffer still lets the user undo.
            return self._clear()
        item_preview = ", ".join(
            i.get("name", "") for i in state["items"][:3]
        )
        if count > 3:
            item_preview += f", and {count - 3} more"
        summary = (
            f"About to clear {count} items from the grocery list "
            f"({item_preview}). Say confirm to proceed, or cancel to keep them."
        )
        return router.request_confirmation(self, "clear_confirmed", {}, summary)

    def _clear(self) -> str:
        state = self._load_state()
        items = state["items"]
        if items:
            self._push_trash(items)
        state["items"] = []
        self._save_state(state)
        return "The grocery list has been cleared."

    def _restore(self, item_hint=None) -> str:
        """Restore recently-removed items from the trash buffer."""
        now = time.monotonic()
        window = 600.0  # 10 minutes
        fresh = [
            (ts, it) for ts, it in self._trash
            if now - ts <= window
        ]
        if not fresh:
            return "I don't have any recently removed items to restore."

        if item_hint:
            key = _normalize_name(item_hint)
            match = next(
                ((ts, it) for ts, it in fresh
                 if _normalize_name(it.get("name", "")) == key),
                None,
            )
            if match is None:
                return f"I don't see {item_hint} in the recently removed items."
            to_restore = [match[1]]
        else:
            to_restore = [it for _, it in fresh]

        state = self._load_state()
        # Re-add restored entries, skipping duplicates by normalized name+unit.
        existing_keys = {
            (_normalize_name(it.get("name", "")), it.get("unit"))
            for it in state["items"]
        }
        added = []
        for it in to_restore:
            key = (_normalize_name(it.get("name", "")), it.get("unit"))
            if key in existing_keys:
                continue
            state["items"].append(it)
            existing_keys.add(key)
            added.append(it.get("name", ""))

        # Drop only the restored entries from trash.
        restored_names = {_normalize_name(it.get("name", "")) for it in to_restore}
        self._trash = type(self._trash)(
            (ts, it) for ts, it in self._trash
            if _normalize_name(it.get("name", "")) not in restored_names
        )
        self._save_state(state)

        if not added:
            return "Those items are already back on the list."
        if len(added) == 1:
            return f"Restored {added[0]} to the grocery list."
        return f"Restored {len(added)} items: {_join_names(added)}."

    def _push_trash(self, items: list[dict]) -> None:
        """Record removed items so a subsequent `restore` can undo."""
        now = time.monotonic()
        for it in items:
            # Store a shallow copy so in-place edits in the live list don't
            # pollute the trash.
            self._trash.append((now, dict(it)))

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
            "recipe_layers": [dict(layer) for layer in state.get("recipe_layers", [])],
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
        """Update fields on an item (name, category, checked, quantity, unit).

        Quantity deltas are absorbed by `manual_quantity` so recipe-sourced
        contributions stay intact for a later layer removal. A unit change
        detaches the item from its recipe sources — the whole quantity moves
        into `manual_quantity` and sources are wiped, because we can't safely
        translate e.g. "cups" → "lb" per source.
        """
        state = self._load_state()
        for it in state["items"]:
            if it["id"] == item_id:
                if "name" in patch and isinstance(patch["name"], str):
                    it["name"] = patch["name"].strip() or it["name"]
                if "category" in patch:
                    it["category"] = patch["category"] or UNCATEGORIZED
                if "checked" in patch:
                    it["checked"] = bool(patch["checked"])
                unit_changed = False
                if "unit" in patch:
                    new_unit = _normalize_unit(patch["unit"])
                    if new_unit != _normalize_unit(it.get("unit")):
                        unit_changed = True
                    it["unit"] = new_unit
                if "quantity" in patch:
                    new_q = _parse_quantity(patch["quantity"])
                    old_q = it.get("quantity")
                    old_f = float(old_q) if old_q is not None else 0.0
                    new_f = float(new_q) if new_q is not None else 0.0
                    delta = new_f - old_f
                    it["quantity"] = new_q
                    manual_f = float(it.get("manual_quantity") or 0.0)
                    manual_f += delta
                    # Clamp manual_quantity floor to 0; negative would mean the
                    # user trimmed below what recipes contributed. Keep the
                    # recipe sources intact — a later remove_recipe_layer will
                    # underflow the total, which is expected.
                    it["manual_quantity"] = max(0.0, manual_f)
                if unit_changed and it.get("sources"):
                    # Sources are unit-specific; a unit swap invalidates them.
                    # Dump everything into manual_quantity so remove-layer on
                    # affected recipes is a cheap noop.
                    q = it.get("quantity")
                    it["manual_quantity"] = float(q) if q is not None else 0.0
                    it["sources"] = {}
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

    # -- Recipe layers --

    def register_layer(self, recipe_id: str, recipe_name: str) -> dict:
        """Record that a recipe contributed to the list. Idempotent.

        If the recipe is already a layer, refresh its `added_at` and
        `recipe_name` (in case the recipe was renamed) but don't duplicate
        the entry. Returns the resulting layer dict.
        """
        if not recipe_id:
            raise ValueError("recipe_id required")
        from datetime import datetime, timezone
        state = self._load_state()
        layers = state.setdefault("recipe_layers", [])
        now = datetime.now(timezone.utc).isoformat()
        for layer in layers:
            if layer.get("recipe_id") == recipe_id:
                layer["added_at"] = now
                if recipe_name:
                    layer["recipe_name"] = recipe_name
                self._save_state(state)
                return dict(layer)
        layer = {
            "recipe_id": str(recipe_id),
            "recipe_name": str(recipe_name or ""),
            "added_at": now,
        }
        layers.append(layer)
        self._save_state(state)
        return dict(layer)

    def remove_recipe_layer(self, recipe_id: str) -> dict:
        """Pull back a recipe's contribution from every item on the list.

        For each item with `sources[recipe_id]`:
          - Subtract that source's quantity from the item's top-level quantity.
          - Drop the source key.
          - If the item's quantity is now <= 0 AND manual_quantity == 0 AND no
            other recipe sources remain, delete the row (push to trash for undo).

        Also removes the layer entry from `recipe_layers`. Returns a summary.
        """
        state = self._load_state()
        items = state["items"]
        layers = state.setdefault("recipe_layers", [])
        removed_layer: dict | None = None
        for layer in list(layers):
            if layer.get("recipe_id") == recipe_id:
                removed_layer = dict(layer)
                layers.remove(layer)
                break

        items_removed: list[dict] = []
        items_updated: list[dict] = []
        kept: list[dict] = []
        for it in items:
            srcs = it.get("sources") or {}
            contrib = srcs.get(recipe_id)
            if contrib is None:
                kept.append(it)
                continue
            amount = float(contrib.get("quantity") or 0.0)
            new_srcs = {k: v for k, v in srcs.items() if k != recipe_id}
            it["sources"] = new_srcs
            cur_q = it.get("quantity")
            if cur_q is not None:
                new_q = float(cur_q) - amount
                it["quantity"] = new_q if new_q > 0 else None
            # Drop the item if nothing is left to shop for.
            qty_left = float(it["quantity"]) if it["quantity"] is not None else 0.0
            manual_q = float(it.get("manual_quantity") or 0.0)
            if qty_left <= 0 and manual_q <= 0 and not new_srcs:
                items_removed.append(dict(it))
                continue
            items_updated.append(dict(it))
            kept.append(it)

        state["items"] = kept
        self._save_state(state)
        if items_removed:
            self._push_trash(items_removed)
        return {
            "layer": removed_layer,
            "items_removed": items_removed,
            "items_updated": items_updated,
        }

    def get_recipe_layers(self) -> list[dict]:
        """Return the currently-active recipe layers (read-only copy)."""
        return [dict(layer) for layer in self._load_state().get("recipe_layers", [])]

    # -- Persistence --

    @staticmethod
    def _new_item(
        name: str,
        category: str | None = None,
        quantity=None,
        unit: str | None = None,
        source: dict | None = None,
    ) -> dict:
        q = quantity
        if q is not None and not isinstance(q, (int, float)):
            q = _parse_quantity(q)
        sources: dict[str, dict] = {}
        manual_q = 0.0
        if source and source.get("recipe_id"):
            sources[source["recipe_id"]] = {
                "quantity": float(q) if q is not None else 0.0,
                "recipe_name": source.get("recipe_name", ""),
            }
        else:
            manual_q = float(q) if q is not None else 0.0
        return {
            "id": uuid.uuid4().hex,
            "name": name,
            "quantity": q,
            "unit": _normalize_unit(unit),
            "category": category or UNCATEGORIZED,
            "checked": False,
            "sources": sources,
            "manual_quantity": manual_q,
        }

    def _default_state(self) -> dict:
        return {
            "items": [],
            "category_order": list(DEFAULT_CATEGORIES),
            "recipe_layers": [],
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

            parsed_qty = _parse_quantity(qty)
            raw_sources = entry.get("sources")
            sources: dict[str, dict] = {}
            if isinstance(raw_sources, dict):
                for rid, src in raw_sources.items():
                    if not isinstance(src, dict):
                        continue
                    sources[str(rid)] = {
                        "quantity": float(src.get("quantity") or 0.0),
                        "recipe_name": str(src.get("recipe_name") or ""),
                    }
            if "sources" not in entry or "manual_quantity" not in entry:
                # v3 → v4 migration: no recipe provenance means the whole
                # quantity is manual.
                manual_q = float(parsed_qty) if parsed_qty is not None else 0.0
                migrated = True
            else:
                manual_q = float(entry.get("manual_quantity") or 0.0)
            items.append({
                "id": entry.get("id") or uuid.uuid4().hex,
                "name": name,
                "quantity": parsed_qty,
                "unit": _normalize_unit(unit),
                "category": entry.get("category") or UNCATEGORIZED,
                "checked": bool(entry.get("checked", False)),
                "sources": sources,
                "manual_quantity": manual_q,
            })

        category_order = data.get("category_order")
        if not isinstance(category_order, list) or not category_order:
            category_order = list(DEFAULT_CATEGORIES)
        else:
            # Ensure all defaults are represented
            for c in DEFAULT_CATEGORIES:
                if c not in category_order:
                    category_order.append(c)

        raw_layers = data.get("recipe_layers")
        recipe_layers: list[dict] = []
        if isinstance(raw_layers, list):
            for layer in raw_layers:
                if not isinstance(layer, dict):
                    continue
                rid = layer.get("recipe_id")
                if not rid:
                    continue
                recipe_layers.append({
                    "recipe_id": str(rid),
                    "recipe_name": str(layer.get("recipe_name") or ""),
                    "added_at": str(layer.get("added_at") or ""),
                })

        state = {
            "items": items,
            "category_order": category_order,
            "recipe_layers": recipe_layers,
        }
        if migrated:
            self._save_state(state)
        return state

    def _save_state(self, state: dict) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "items": state.get("items", []),
            "category_order": state.get("category_order", list(DEFAULT_CATEGORIES)),
            "recipe_layers": state.get("recipe_layers", []),
        }
        self._path.write_text(json.dumps(payload, indent=2) + "\n")
