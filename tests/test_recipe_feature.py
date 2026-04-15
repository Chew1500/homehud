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


class TestFilterCandidates:
    def test_token_match_ranks_by_score(self):
        from features.recipe import _filter_candidates

        recipes = [
            {"name": "Veggie Chili", "tags": ["vegetarian", "dinner"], "ingredients": []},
            {"name": "Steak", "tags": ["beef"], "ingredients": []},
            {"name": "Tofu Stir Fry", "tags": ["vegetarian"], "ingredients": []},
        ]
        result = _filter_candidates("vegetarian dinner", recipes)
        names = [r["name"] for r in result]
        assert names[0] == "Veggie Chili"  # 2 token matches
        assert "Tofu Stir Fry" in names    # 1 token match
        assert "Steak" not in names

    def test_no_match_falls_back_to_all_capped(self):
        from features.recipe import MAX_CANDIDATES, _filter_candidates

        recipes = [
            {"name": f"Recipe {i}", "tags": ["thing"], "ingredients": []}
            for i in range(40)
        ]
        result = _filter_candidates("xyznothing qqqz", recipes)
        assert len(result) == MAX_CANDIDATES

    def test_stopwords_only_returns_capped_full_list(self):
        from features.recipe import MAX_CANDIDATES, _filter_candidates

        recipes = [
            {"name": f"Recipe {i}", "tags": [], "ingredients": []}
            for i in range(40)
        ]
        # "give me a recipe please" is all stopwords — no useful tokens
        result = _filter_candidates("give me a recipe please", recipes)
        assert len(result) == MAX_CANDIDATES

    def test_matches_ingredient_names(self):
        from features.recipe import _filter_candidates

        recipes = [
            {"name": "Bowl", "tags": [], "ingredients": [{"name": "rice"}]},
            {"name": "Toast", "tags": [], "ingredients": [{"name": "bread"}]},
        ]
        result = _filter_candidates("rice", recipes)
        assert [r["name"] for r in result] == ["Bowl"]

    def test_caps_at_max_candidates_with_strong_match(self):
        from features.recipe import MAX_CANDIDATES, _filter_candidates

        recipes = [
            {"name": f"Veg {i}", "tags": ["vegetarian"], "ingredients": []}
            for i in range(50)
        ]
        result = _filter_candidates("vegetarian", recipes)
        assert len(result) == MAX_CANDIDATES


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

    def test_two_recipes_share_flour(self, tmp_path):
        feat, storage, grocery = self._make(tmp_path)
        storage.add({
            "name": "Cake A",
            "source": "manual",
            "tags": ["test"],
            "prep_time_min": 10, "cook_time_min": 20, "servings": 4,
            "ingredients": [
                {"name": "flour", "quantity": "2", "unit": "cups"},
            ],
            "directions": ["mix"],
        })
        storage.add({
            "name": "Cake B",
            "source": "manual",
            "tags": ["test"],
            "prep_time_min": 10, "cook_time_min": 20, "servings": 4,
            "ingredients": [
                {"name": "flour", "quantity": "1", "unit": "cup"},
            ],
            "directions": ["mix"],
        })
        feat.execute("add_ingredients_to_grocery", {"recipe_name": "Cake A"})
        feat.execute("add_ingredients_to_grocery", {"recipe_name": "Cake B"})
        items = grocery.get_items_structured()
        assert len(items) == 1
        assert items[0]["quantity"] == 3.0
        assert items[0]["unit"] == "cup"

    def test_add_ingredients_recipe_not_found(self, tmp_path):
        feat, storage, grocery = self._make(tmp_path)
        result = feat.execute(
            "add_ingredients_to_grocery", {"recipe_name": "Nonexistent"}
        )
        assert "couldn't find" in result.lower()
