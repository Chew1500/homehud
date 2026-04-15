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


def _extract_names(parameters: dict) -> list[str]:
    """Pull a list of item names out of LLM-supplied parameters.

    Accepts `items: list[str]`, `item: str`, or `item: list[str]`. A single
    string may contain comma/and-separated items which are split out.
    """
    raw = parameters.get("items")
    if raw is None:
        raw = parameters.get("item")
    if raw is None:
        return []
    if isinstance(raw, str):
        return _split_item_phrase(raw)
    if isinstance(raw, list):
        names: list[str] = []
        for entry in raw:
            if isinstance(entry, str):
                names.extend(_split_item_phrase(entry))
        return names
    return []


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

    Storage shape (v2):
        {
          "items": [
            {"id": "...", "name": "milk", "category": "Dairy", "checked": false},
            ...
          ],
          "category_order": ["Produce", "Dairy", ...]
        }

    Legacy v1 was a bare list of strings; `_load_state` migrates transparently.
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
            "add": {"item": "str", "items": "list[str]"},
            "remove": {"item": "str"},
            "list": {},
            "clear": {},
        }

    def execute(self, action: str, parameters: dict) -> str:
        if action == "add":
            names = _extract_names(parameters)
            if not names:
                return self._list()
            return self._add_many(names)
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
            if names:
                return self._add_many(names)
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

    def _add(self, item: str) -> str:
        return self._add_many([item])

    def _add_many(self, names: list[str]) -> str:
        state = self._load_state()
        items = state["items"]
        existing_lower = {i["name"].lower() for i in items}

        added: list[str] = []
        duplicates: list[str] = []
        seen_in_batch: set[str] = set()
        for raw in names:
            name = raw.strip()
            if not name:
                continue
            key = name.lower()
            if key in seen_in_batch:
                continue
            seen_in_batch.add(key)
            if key in existing_lower:
                duplicates.append(name)
                continue
            items.append(self._new_item(name))
            existing_lower.add(key)
            added.append(name)

        if added:
            self._save_state(state)

        count = len(items)
        total_s = "item" if count == 1 else "items"

        if added and not duplicates:
            if len(added) == 1:
                return (
                    f"Added {added[0]} to the grocery list. "
                    f"You now have {count} {total_s}."
                )
            return (
                f"Added {_join_names(added)} to the grocery list. "
                f"You now have {count} {total_s}."
            )
        if added and duplicates:
            return (
                f"Added {_join_names(added)}. "
                f"{_join_names(duplicates)} "
                f"{'was' if len(duplicates) == 1 else 'were'} already on the list. "
                f"You now have {count} {total_s}."
            )
        if not added and duplicates:
            if len(duplicates) == 1:
                return f"{duplicates[0]} is already on the grocery list."
            return f"{_join_names(duplicates)} are already on the grocery list."
        return self._list()

    def _remove(self, item: str) -> str:
        state = self._load_state()
        items = state["items"]
        lower = [i["name"].lower() for i in items]
        if item.lower() not in lower:
            return f"{item} is not on the grocery list."
        idx = lower.index(item.lower())
        removed = items.pop(idx)["name"]
        self._save_state(state)
        count = len(items)
        s = "item" if count == 1 else "items"
        return f"Removed {removed} from the grocery list. You now have {count} {s}."

    def _list(self) -> str:
        names = [i["name"] for i in self._load_state()["items"]]
        if not names:
            return "The grocery list is empty."
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
        """Return the current grocery list item names (read-only snapshot)."""
        return [i["name"] for i in self._load_state()["items"]]

    # -- Web API surface --

    def get_state(self) -> dict:
        """Return the full list state for the web UI."""
        state = self._load_state()
        return {
            "items": [dict(i) for i in state["items"]],
            "category_order": list(state["category_order"]),
            "categories": list(DEFAULT_CATEGORIES),
        }

    def add_item(self, name: str, category: str | None = None) -> dict | None:
        """Add an item from the web UI. Returns the new item or None if dup."""
        name = name.strip()
        if not name:
            return None
        state = self._load_state()
        if name.lower() in [i["name"].lower() for i in state["items"]]:
            return None
        item = self._new_item(name, category)
        state["items"].append(item)
        self._save_state(state)
        return dict(item)

    def update_item(self, item_id: str, patch: dict) -> dict | None:
        """Update fields on an item (name, category, checked). Returns new item."""
        state = self._load_state()
        for it in state["items"]:
            if it["id"] == item_id:
                if "name" in patch and isinstance(patch["name"], str):
                    it["name"] = patch["name"].strip() or it["name"]
                if "category" in patch:
                    it["category"] = patch["category"] or UNCATEGORIZED
                if "checked" in patch:
                    it["checked"] = bool(patch["checked"])
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
    def _new_item(name: str, category: str | None = None) -> dict:
        return {
            "id": uuid.uuid4().hex,
            "name": name,
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

        # Legacy v1: bare list of strings
        if isinstance(data, list):
            state = self._default_state()
            state["items"] = [self._new_item(s) for s in data if isinstance(s, str)]
            return state

        if not isinstance(data, dict):
            log.warning("Grocery file has unexpected format, resetting")
            return self._default_state()

        items_raw = data.get("items", [])
        items: list[dict] = []
        for entry in items_raw:
            if isinstance(entry, str):
                items.append(self._new_item(entry))
            elif isinstance(entry, dict) and entry.get("name"):
                items.append({
                    "id": entry.get("id") or uuid.uuid4().hex,
                    "name": entry["name"],
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

        return {"items": items, "category_order": category_order}

    def _save_state(self, state: dict) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(state, indent=2) + "\n")
