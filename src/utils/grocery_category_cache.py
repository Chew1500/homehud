"""Persistent cache mapping grocery item names to categories.

Avoids re-calling Claude for items that have already been categorized once.
Keys are lowercased item names. Cache lives at `data/grocery_category_cache.json`.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

log = logging.getLogger("home-hud.utils.grocery_category_cache")


class GroceryCategoryCache:
    def __init__(self, path: str | Path = "data/grocery_category_cache.json"):
        self._path = Path(path)
        self._data: dict[str, str] = {}
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text())
            if isinstance(raw, dict):
                self._data = {
                    str(k).lower(): str(v)
                    for k, v in raw.items()
                    if isinstance(v, str)
                }
        except (json.JSONDecodeError, OSError):
            log.warning("Grocery category cache corrupted, resetting")

    def _save(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(json.dumps(self._data, indent=2) + "\n")
        except OSError:
            log.exception("Failed to write grocery category cache")

    def get(self, name: str) -> str | None:
        return self._data.get(name.lower())

    def put(self, name: str, category: str) -> None:
        self._data[name.lower()] = category
        self._save()

    def put_many(self, mapping: dict[str, str]) -> None:
        if not mapping:
            return
        for k, v in mapping.items():
            if isinstance(k, str) and isinstance(v, str):
                self._data[k.lower()] = v
        self._save()

    def lookup_many(self, names: list[str]) -> tuple[dict[str, str], list[str]]:
        """Split names into (hits, misses) against the cache."""
        hits: dict[str, str] = {}
        misses: list[str] = []
        for n in names:
            cat = self._data.get(n.lower())
            if cat:
                hits[n] = cat
            else:
                misses.append(n)
        return hits, misses
