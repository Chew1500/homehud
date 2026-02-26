"""Grocery list feature — add, remove, list, and clear items via voice."""

import json
import logging
import re
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


class GroceryFeature(BaseFeature):
    """Manages a grocery list stored as a JSON file."""

    def __init__(self, config: dict):
        super().__init__(config)
        self._path = Path(config.get("grocery_file", "data/grocery.json"))

    @property
    def description(self) -> str:
        return (
            'Grocery/shopping list: triggered by "grocery list" or "shopping list". '
            'Commands: "add X to grocery list", "remove X from grocery list", '
            '"what\'s on the grocery list", "clear the grocery list".'
        )

    def matches(self, text: str) -> bool:
        return bool(_ANY_GROCERY.search(text))

    def handle(self, text: str) -> str:
        m = _ADD.search(text)
        if m:
            return self._add(m.group(1).strip())

        m = _REMOVE.search(text)
        if m:
            return self._remove(m.group(1).strip())

        if _CLEAR.search(text):
            return self._clear()

        if _LIST.search(text):
            return self._list()

        # Fallback: "grocery list" was mentioned but no sub-command matched
        return self._list()

    # -- Actions --

    def _add(self, item: str) -> str:
        items = self._load()
        # Dedup: case-insensitive
        if item.lower() in [i.lower() for i in items]:
            return f"{item} is already on the grocery list."
        items.append(item)
        self._save(items)
        count = len(items)
        s = "item" if count == 1 else "items"
        return f"Added {item} to the grocery list. You now have {count} {s}."

    def _remove(self, item: str) -> str:
        items = self._load()
        lower_items = [i.lower() for i in items]
        if item.lower() not in lower_items:
            return f"{item} is not on the grocery list."
        idx = lower_items.index(item.lower())
        removed = items.pop(idx)
        self._save(items)
        count = len(items)
        s = "item" if count == 1 else "items"
        return f"Removed {removed} from the grocery list. You now have {count} {s}."

    def _list(self) -> str:
        items = self._load()
        if not items:
            return "The grocery list is empty."
        if len(items) == 1:
            return f"You have one item on the grocery list: {items[0]}."
        joined = ", ".join(items[:-1]) + f", and {items[-1]}"
        return f"You have {len(items)} items on the grocery list: {joined}."

    def _clear(self) -> str:
        self._save([])
        return "The grocery list has been cleared."

    # -- Persistence --

    def _load(self) -> list[str]:
        if not self._path.exists():
            return []
        try:
            data = json.loads(self._path.read_text())
            if isinstance(data, list):
                return data
            log.warning("Grocery file has unexpected format, resetting")
            return []
        except (json.JSONDecodeError, OSError):
            log.warning("Grocery file corrupted or unreadable, resetting")
            return []

    def _save(self, items: list[str]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(items, indent=2) + "\n")
