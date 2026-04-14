"""Recipe storage — JSON-backed recipe collection management."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger("home-hud.cooking.storage")


class RecipeStorage:
    """Manages a collection of recipes stored as a JSON file.

    Each recipe is a dict with structured ingredients and step-by-step
    directions.  See COOKING_PLAN.md for the full data model.
    """

    def __init__(self, path: Path | str):
        self._path = Path(path)

    # -- Read operations --

    def get_all(self) -> list[dict]:
        """Return all recipes."""
        return self._load()

    def get_by_id(self, recipe_id: str) -> dict | None:
        """Return a single recipe by ID, or None."""
        for r in self._load():
            if r.get("id") == recipe_id:
                return r
        return None

    def get_by_name(self, name: str) -> dict | None:
        """Return the first recipe whose name matches (case-insensitive)."""
        target = name.lower()
        for r in self._load():
            if r.get("name", "").lower() == target:
                return r
        return None

    def search(self, query: str) -> list[dict]:
        """Search recipes by name, tags, and ingredient names (case-insensitive substring)."""
        q = query.lower().strip()
        if not q:
            return []
        results = []
        for r in self._load():
            if q in r.get("name", "").lower():
                results.append(r)
                continue
            if any(q in t.lower() for t in r.get("tags", [])):
                results.append(r)
                continue
            if any(q in (i.get("name") or "").lower() for i in r.get("ingredients", [])):
                results.append(r)
                continue
        return results

    # -- Write operations --

    def add(self, recipe: dict) -> str:
        """Add a recipe and return its assigned ID."""
        recipes = self._load()
        recipe_id = recipe.get("id") or str(uuid.uuid4())
        recipe["id"] = recipe_id
        if "created_at" not in recipe:
            recipe["created_at"] = datetime.now(timezone.utc).isoformat()
        recipes.append(recipe)
        self._save(recipes)
        log.info("Added recipe %r (id=%s)", recipe.get("name"), recipe_id)
        return recipe_id

    def update(self, recipe_id: str, updates: dict) -> bool:
        """Update fields on an existing recipe. Returns True if found."""
        recipes = self._load()
        for i, r in enumerate(recipes):
            if r.get("id") == recipe_id:
                r.update(updates)
                r["id"] = recipe_id  # prevent ID overwrite
                recipes[i] = r
                self._save(recipes)
                log.info("Updated recipe %s", recipe_id)
                return True
        return False

    def delete(self, recipe_id: str) -> bool:
        """Delete a recipe by ID. Returns True if found and removed."""
        recipes = self._load()
        before = len(recipes)
        recipes = [r for r in recipes if r.get("id") != recipe_id]
        if len(recipes) == before:
            return False
        self._save(recipes)
        log.info("Deleted recipe %s", recipe_id)
        return True

    def count(self) -> int:
        """Return the number of stored recipes."""
        return len(self._load())

    # -- Persistence --

    def _load(self) -> list[dict]:
        if not self._path.exists():
            return []
        try:
            data = json.loads(self._path.read_text())
            if isinstance(data, list):
                return data
            log.warning("Recipe file has unexpected format, resetting")
            return []
        except (json.JSONDecodeError, OSError):
            log.warning("Recipe file corrupted or unreadable, resetting")
            return []

    def _save(self, recipes: list[dict]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(recipes, indent=2) + "\n")
