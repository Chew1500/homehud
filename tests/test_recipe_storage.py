"""Tests for RecipeStorage — CRUD, search, and persistence."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class TestRecipeStorage:

    def _make(self, tmp_path):
        from cooking.storage import RecipeStorage
        return RecipeStorage(tmp_path / "recipes.json")

    def _sample_recipe(self, name="Test Recipe", tags=None):
        return {
            "name": name,
            "source": "manual",
            "tags": tags or ["test"],
            "prep_time_min": 10,
            "cook_time_min": 20,
            "servings": 4,
            "ingredients": [
                {"name": "flour", "quantity": "2", "unit": "cups"},
                {"name": "sugar", "quantity": "1", "unit": "cup"},
            ],
            "directions": [
                "Mix dry ingredients.",
                "Add wet ingredients.",
                "Bake at 350F for 30 minutes.",
            ],
        }

    def test_empty_storage(self, tmp_path):
        storage = self._make(tmp_path)
        assert storage.get_all() == []
        assert storage.count() == 0

    def test_add_and_get(self, tmp_path):
        storage = self._make(tmp_path)
        recipe = self._sample_recipe()
        rid = storage.add(recipe)
        assert rid
        assert storage.count() == 1
        loaded = storage.get_by_id(rid)
        assert loaded is not None
        assert loaded["name"] == "Test Recipe"
        assert loaded["id"] == rid
        assert "created_at" in loaded

    def test_get_by_name(self, tmp_path):
        storage = self._make(tmp_path)
        storage.add(self._sample_recipe("Chicken Tikka"))
        assert storage.get_by_name("chicken tikka") is not None
        assert storage.get_by_name("CHICKEN TIKKA") is not None
        assert storage.get_by_name("nonexistent") is None

    def test_search(self, tmp_path):
        storage = self._make(tmp_path)
        storage.add(self._sample_recipe("Spicy Tacos", ["mexican", "spicy"]))
        storage.add(self._sample_recipe("Mild Pasta", ["italian", "mild"]))
        assert len(storage.search("spicy")) == 1
        assert len(storage.search("tacos")) == 1
        assert len(storage.search("italian")) == 1
        assert len(storage.search("nonexistent")) == 0

    def test_search_matches_ingredient_names(self, tmp_path):
        storage = self._make(tmp_path)
        # The sample has flour + sugar in its ingredients but no matching tag
        storage.add(self._sample_recipe("Birthday Cake", ["dessert"]))
        storage.add(self._sample_recipe("Salad", ["healthy"]))
        flour_results = storage.search("flour")
        assert len(flour_results) == 2  # both samples have flour
        # Ingredient with substring match works case-insensitive
        assert len(storage.search("FLOUR")) == 2
        assert len(storage.search("dessert")) == 1  # tag match still works
        assert storage.search("") == []

    def test_update(self, tmp_path):
        storage = self._make(tmp_path)
        rid = storage.add(self._sample_recipe())
        assert storage.update(rid, {"name": "Updated Recipe"})
        loaded = storage.get_by_id(rid)
        assert loaded["name"] == "Updated Recipe"
        assert loaded["id"] == rid  # ID preserved

    def test_update_nonexistent(self, tmp_path):
        storage = self._make(tmp_path)
        assert not storage.update("nonexistent-id", {"name": "Nope"})

    def test_delete(self, tmp_path):
        storage = self._make(tmp_path)
        rid = storage.add(self._sample_recipe())
        assert storage.delete(rid)
        assert storage.count() == 0
        assert storage.get_by_id(rid) is None

    def test_delete_nonexistent(self, tmp_path):
        storage = self._make(tmp_path)
        assert not storage.delete("nonexistent-id")

    def test_persistence(self, tmp_path):
        from cooking.storage import RecipeStorage
        path = tmp_path / "recipes.json"
        storage1 = RecipeStorage(path)
        storage1.add(self._sample_recipe("Persistent Recipe"))

        storage2 = RecipeStorage(path)
        assert storage2.count() == 1
        assert storage2.get_all()[0]["name"] == "Persistent Recipe"

    def test_corrupted_file(self, tmp_path):
        path = tmp_path / "recipes.json"
        path.write_text("not valid json{{{")
        from cooking.storage import RecipeStorage
        storage = RecipeStorage(path)
        assert storage.get_all() == []

    def test_wrong_format_file(self, tmp_path):
        path = tmp_path / "recipes.json"
        path.write_text(json.dumps({"not": "a list"}))
        from cooking.storage import RecipeStorage
        storage = RecipeStorage(path)
        assert storage.get_all() == []

    def test_multiple_recipes(self, tmp_path):
        storage = self._make(tmp_path)
        storage.add(self._sample_recipe("Recipe A"))
        storage.add(self._sample_recipe("Recipe B"))
        storage.add(self._sample_recipe("Recipe C"))
        assert storage.count() == 3
        names = [r["name"] for r in storage.get_all()]
        assert "Recipe A" in names
        assert "Recipe B" in names
        assert "Recipe C" in names
