"""Tests for RecipeFeature — action dispatch, matching, grocery integration."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def _sample_recipe(name="Test Recipe", tags=None):
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
            {"name": "eggs", "quantity": "3", "unit": ""},
        ],
        "directions": [
            "Mix dry ingredients.",
            "Add wet ingredients.",
            "Bake at 350F for 30 minutes.",
        ],
    }


class TestRecipeFeature:

    def _make(self, tmp_path, llm=None, grocery=None, cooking=None):
        from cooking.storage import RecipeStorage
        from features.recipe import RecipeFeature

        storage = RecipeStorage(tmp_path / "recipes.json")
        return RecipeFeature(
            config={},
            llm=llm,
            recipe_storage=storage,
            grocery_feature=grocery,
            cooking_session=cooking,
        ), storage

    def test_action_schema(self, tmp_path):
        feat, _ = self._make(tmp_path)
        schema = feat.action_schema
        assert "list" in schema
        assert "search" in schema
        assert "detail" in schema
        assert "delete" in schema
        assert "recommend" in schema
        assert "add_ingredients_to_grocery" in schema
        assert "start_cooking" in schema

    def test_name_and_description(self, tmp_path):
        feat, _ = self._make(tmp_path)
        assert feat.name == "Recipes"
        assert feat.short_description
        assert feat.description

    def test_execute_list_empty(self, tmp_path):
        feat, _ = self._make(tmp_path)
        result = feat.execute("list", {})
        assert "empty" in result.lower()

    def test_execute_list_with_recipes(self, tmp_path):
        feat, storage = self._make(tmp_path)
        storage.add(_sample_recipe("Pasta Carbonara"))
        storage.add(_sample_recipe("Chicken Tikka"))
        result = feat.execute("list", {})
        assert "Pasta Carbonara" in result
        assert "Chicken Tikka" in result
        assert "2 recipes" in result

    def test_execute_search(self, tmp_path):
        feat, storage = self._make(tmp_path)
        storage.add(_sample_recipe("Spicy Tacos", ["mexican", "spicy"]))
        storage.add(_sample_recipe("Mild Pasta", ["italian"]))
        result = feat.execute("search", {"query": "spicy"})
        assert "Spicy Tacos" in result
        assert "Mild Pasta" not in result

    def test_execute_search_no_results(self, tmp_path):
        feat, storage = self._make(tmp_path)
        storage.add(_sample_recipe("Pasta"))
        result = feat.execute("search", {"query": "sushi"})
        assert "No recipes found" in result

    def test_execute_detail(self, tmp_path):
        feat, storage = self._make(tmp_path)
        storage.add(_sample_recipe("Test Recipe"))
        result = feat.execute("detail", {"recipe_name": "Test Recipe"})
        assert "Test Recipe" in result
        assert "3 ingredients" in result
        assert "3 steps" in result

    def test_execute_detail_not_found(self, tmp_path):
        feat, _ = self._make(tmp_path)
        result = feat.execute("detail", {"recipe_name": "Nonexistent"})
        assert "couldn't find" in result.lower()

    def test_execute_delete(self, tmp_path):
        feat, storage = self._make(tmp_path)
        storage.add(_sample_recipe("To Delete"))
        result = feat.execute("delete", {"recipe_name": "To Delete"})
        assert "Deleted" in result
        assert storage.count() == 0

    def test_matches_recipe_keywords(self, tmp_path):
        feat, _ = self._make(tmp_path)
        assert feat.matches("show me my recipes")
        assert feat.matches("what's in the recipe book")
        assert feat.matches("find a spicy recipe")
        assert feat.matches("recommend something to cook")

    def test_no_match_unrelated(self, tmp_path):
        feat, _ = self._make(tmp_path)
        assert not feat.matches("what's the weather")
        assert not feat.matches("add milk to grocery list")


class TestRecipeGroceryIntegration:

    def _make(self, tmp_path):
        from cooking.storage import RecipeStorage
        from features.grocery import GroceryFeature
        from features.recipe import RecipeFeature

        storage = RecipeStorage(tmp_path / "recipes.json")
        grocery = GroceryFeature(
            {"grocery_file": str(tmp_path / "grocery.json")}
        )
        feat = RecipeFeature(
            config={},
            llm=None,
            recipe_storage=storage,
            grocery_feature=grocery,
        )
        return feat, storage, grocery

    def test_add_ingredients_to_grocery(self, tmp_path):
        feat, storage, grocery = self._make(tmp_path)
        storage.add(_sample_recipe("Test Recipe"))
        result = feat.execute(
            "add_ingredients_to_grocery", {"recipe_name": "Test Recipe"}
        )
        assert "Added 3 items" in result
        items = grocery.get_items()
        assert len(items) == 3
        # Check quantities are included
        assert any("flour" in i for i in items)

    def test_add_ingredients_dedup(self, tmp_path):
        feat, storage, grocery = self._make(tmp_path)
        grocery.execute("add", {"item": "flour"})
        storage.add(_sample_recipe("Test Recipe"))
        result = feat.execute(
            "add_ingredients_to_grocery", {"recipe_name": "Test Recipe"}
        )
        assert "Already on list" in result
        assert "flour" in result
        # Only 2 new items added (sugar and eggs), plus the original flour
        assert len(grocery.get_items()) == 3

    def test_add_ingredients_recipe_not_found(self, tmp_path):
        feat, storage, grocery = self._make(tmp_path)
        result = feat.execute(
            "add_ingredients_to_grocery", {"recipe_name": "Nonexistent"}
        )
        assert "couldn't find" in result.lower()
