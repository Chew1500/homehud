"""Tests for CookingSessionFeature — lifecycle, navigation, TTL, context."""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def _sample_recipe():
    return {
        "id": "test-id",
        "name": "Test Pasta",
        "ingredients": [
            {"name": "pasta", "quantity": "400", "unit": "g"},
            {"name": "olive oil", "quantity": "2", "unit": "tbsp"},
            {"name": "garlic", "quantity": "3", "unit": "cloves"},
        ],
        "directions": [
            "Boil water and cook pasta.",
            "Heat olive oil in a pan.",
            "Add garlic and saute.",
            "Combine pasta with sauce.",
            "Serve hot.",
        ],
    }


class TestCookingSessionLifecycle:

    def _make(self, config=None):
        from features.cooking_session import CookingSessionFeature
        return CookingSessionFeature(config or {}, llm=None)

    def test_no_session_initially(self):
        feat = self._make()
        assert not feat.is_active
        assert not feat.expects_follow_up
        assert feat.get_llm_context() is None

    def test_start_session(self):
        feat = self._make()
        result = feat.start(_sample_recipe())
        assert "Test Pasta" in result
        assert "Step 1" in result
        assert "Boil water" in result
        assert feat.is_active
        assert feat.expects_follow_up

    def test_start_session_no_directions(self):
        feat = self._make()
        result = feat.start({"name": "Empty", "directions": []})
        assert "no directions" in result.lower()
        assert not feat.is_active


class TestCookingSessionNavigation:

    def _make_active(self):
        from features.cooking_session import CookingSessionFeature
        feat = CookingSessionFeature({}, llm=None)
        feat.start(_sample_recipe())
        return feat

    def test_next_step(self):
        feat = self._make_active()
        result = feat.execute("next_step", {})
        assert "Step 2" in result
        assert "olive oil" in result.lower()

    def test_next_step_multiple(self):
        feat = self._make_active()
        feat.execute("next_step", {})
        feat.execute("next_step", {})
        result = feat.execute("next_step", {})
        assert "Step 4" in result

    def test_next_past_end(self):
        feat = self._make_active()
        for _ in range(4):
            feat.execute("next_step", {})
        result = feat.execute("next_step", {})
        assert "last step" in result.lower() or "done" in result.lower()
        assert not feat.is_active

    def test_previous_step(self):
        feat = self._make_active()
        feat.execute("next_step", {})
        result = feat.execute("previous_step", {})
        assert "Step 1" in result
        assert "Going back" in result

    def test_previous_at_start(self):
        feat = self._make_active()
        result = feat.execute("previous_step", {})
        assert "first step" in result.lower() or "Step 1" in result

    def test_current_step(self):
        feat = self._make_active()
        result = feat.execute("current_step", {})
        assert "Step 1" in result

    def test_repeat_step(self):
        feat = self._make_active()
        feat.execute("next_step", {})
        result = feat.execute("repeat_step", {})
        assert "Step 2" in result

    def test_what_step(self):
        feat = self._make_active()
        feat.execute("next_step", {})
        feat.execute("next_step", {})
        result = feat.execute("what_step", {})
        assert "Step 3" in result

    def test_stop_cooking(self):
        feat = self._make_active()
        feat.execute("next_step", {})
        result = feat.execute("stop_cooking", {})
        assert "ended" in result.lower()
        assert "Test Pasta" in result
        assert not feat.is_active


class TestCookingSessionContext:

    def _make_active(self):
        from features.cooking_session import CookingSessionFeature
        feat = CookingSessionFeature({}, llm=None)
        feat.start(_sample_recipe())
        return feat

    def test_context_has_recipe_name(self):
        feat = self._make_active()
        ctx = feat.get_llm_context()
        assert "Test Pasta" in ctx

    def test_context_has_step_info(self):
        feat = self._make_active()
        ctx = feat.get_llm_context()
        assert "step 1 of 5" in ctx.lower()
        assert "Boil water" in ctx

    def test_context_has_ingredients(self):
        feat = self._make_active()
        ctx = feat.get_llm_context()
        assert "pasta" in ctx.lower()
        assert "olive oil" in ctx.lower()

    def test_context_updates_on_next(self):
        feat = self._make_active()
        feat.execute("next_step", {})
        ctx = feat.get_llm_context()
        assert "step 2 of 5" in ctx.lower()
        assert "olive oil" in ctx

    def test_context_has_previous_step(self):
        feat = self._make_active()
        feat.execute("next_step", {})
        ctx = feat.get_llm_context()
        assert "Previous step" in ctx
        assert "Boil water" in ctx


class TestCookingSessionTTL:

    def test_session_expires(self):
        from features.cooking_session import CookingSessionFeature
        feat = CookingSessionFeature({"cooking_session_ttl": 1}, llm=None)
        feat.start(_sample_recipe())
        assert feat.is_active
        # Simulate time passing
        feat._session["last_interaction"] = time.time() - 2
        assert not feat.expects_follow_up

    def test_execute_no_session(self):
        from features.cooking_session import CookingSessionFeature
        feat = CookingSessionFeature({}, llm=None)
        result = feat.execute("next_step", {})
        assert "No cooking session" in result


class TestCookingSessionActionSchema:

    def test_schema_has_all_actions(self):
        from features.cooking_session import CookingSessionFeature
        feat = CookingSessionFeature({}, llm=None)
        schema = feat.action_schema
        assert "next_step" in schema
        assert "previous_step" in schema
        assert "repeat_step" in schema
        assert "current_step" in schema
        assert "ask_question" in schema
        assert "stop_cooking" in schema
        assert "what_step" in schema
