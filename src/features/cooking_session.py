"""Cooking session feature — step-by-step voice guidance through a recipe."""

from __future__ import annotations

import logging
import time

from features.base import BaseFeature

log = logging.getLogger("home-hud.features.cooking_session")


class CookingSessionFeature(BaseFeature):
    """Guides the user through a recipe step-by-step via voice.

    Maintains a long-running session (1-hour TTL) independent of the
    LLM conversation history. Context is injected fresh on every
    parse_intent call via get_llm_context().
    """

    def __init__(self, config: dict, llm=None):
        super().__init__(config)
        self._llm = llm
        self._ttl = config.get("cooking_session_ttl", 3600)
        self._session: dict | None = None

    @property
    def name(self) -> str:
        return "Cooking Session"

    @property
    def short_description(self) -> str:
        return "Step-by-step cooking guidance for active recipes"

    @property
    def description(self) -> str:
        return (
            'Cooking session: triggered when actively cooking. '
            'Commands: "next step", "previous step", "repeat that step", '
            '"where was I", "how many tablespoons in a cup", '
            '"can I substitute butter for oil", "I\'m done cooking".'
        )

    @property
    def expects_follow_up(self) -> bool:
        if not self._session:
            return False
        elapsed = time.time() - self._session.get("last_interaction", 0)
        return elapsed < self._ttl

    @property
    def action_schema(self) -> dict:
        return {
            "next_step": {},
            "previous_step": {},
            "repeat_step": {},
            "current_step": {},
            "ask_question": {"question": "str"},
            "stop_cooking": {},
            "what_step": {},
        }

    def matches(self, text: str) -> bool:
        # Only match when a session is active
        return self.expects_follow_up

    def execute(self, action: str, parameters: dict) -> str:
        if not self._session:
            return "No cooking session is active. Start one from a recipe."

        self._session["last_interaction"] = time.time()

        actions = {
            "next_step": self._next_step,
            "previous_step": self._previous_step,
            "repeat_step": self._current_step,
            "current_step": self._current_step,
            "what_step": self._current_step,
            "stop_cooking": self._stop,
            "ask_question": lambda: self._ask_question(
                parameters.get("question", "")
            ),
        }
        handler = actions.get(action)
        if handler is None:
            return self._current_step()
        return handler()

    def handle(self, text: str) -> str:
        if not self._session:
            return "No cooking session is active."
        self._session["last_interaction"] = time.time()
        # Regex fallback — handled primarily via LLM routing
        return self._current_step()

    def get_llm_context(self) -> str | None:
        if not self._session:
            return None
        if not self.expects_follow_up:
            self._session = None
            return None

        s = self._session
        directions = s["directions"]
        step_idx = s["current_step"]
        total = len(directions)
        current_text = directions[step_idx] if step_idx < total else "(done)"

        parts = [
            f'Cooking session active: "{s["recipe_name"]}", '
            f"step {step_idx + 1} of {total}.",
            f'Current step: "{current_text}"',
        ]

        # Include previous step for context
        if step_idx > 0:
            parts.append(f'Previous step: "{directions[step_idx - 1]}"')

        # Include ingredients for reference
        ingredients = s.get("ingredients", [])
        if ingredients:
            ing_strs = []
            for ing in ingredients[:15]:
                name = ing.get("name", "")
                qty = ing.get("quantity", "")
                unit = ing.get("unit", "")
                if qty and unit:
                    ing_strs.append(f"{qty} {unit} {name}")
                elif qty:
                    ing_strs.append(f"{qty} {name}")
                else:
                    ing_strs.append(name)
            parts.append(f"Ingredients: {', '.join(ing_strs)}")

        parts.append(
            "User can: next step, previous step, repeat step, "
            "ask a cooking question, or stop cooking."
        )

        return "\n".join(parts)

    # -- Public API (called by RecipeFeature) --

    def start(self, recipe: dict) -> str:
        """Start a cooking session for the given recipe."""
        directions = recipe.get("directions", [])
        if not directions:
            return f"{recipe.get('name', 'This recipe')} has no directions."

        self._session = {
            "recipe_id": recipe.get("id", ""),
            "recipe_name": recipe.get("name", "Unknown Recipe"),
            "directions": directions,
            "ingredients": recipe.get("ingredients", []),
            "current_step": 0,
            "started_at": time.time(),
            "last_interaction": time.time(),
        }

        name = recipe.get("name", "the recipe")
        total = len(directions)
        first_step = directions[0]
        return (
            f"Let's cook {name}! {total} steps total. "
            f"Step 1: {first_step}"
        )

    @property
    def is_active(self) -> bool:
        """Whether a cooking session is currently running."""
        return self.expects_follow_up

    # -- Step navigation --

    def _next_step(self) -> str:
        s = self._session
        directions = s["directions"]
        current = s["current_step"]

        if current >= len(directions) - 1:
            self._session = None
            return (
                "That was the last step! You're all done. Enjoy your meal!"
            )

        s["current_step"] = current + 1
        step_num = s["current_step"] + 1
        total = len(directions)
        step_text = directions[s["current_step"]]
        return f"Step {step_num} of {total}: {step_text}"

    def _previous_step(self) -> str:
        s = self._session
        directions = s["directions"]

        if s["current_step"] <= 0:
            return f"You're already at the first step. Step 1: {directions[0]}"

        s["current_step"] -= 1
        step_num = s["current_step"] + 1
        total = len(directions)
        step_text = directions[s["current_step"]]
        return f"Going back. Step {step_num} of {total}: {step_text}"

    def _current_step(self) -> str:
        s = self._session
        directions = s["directions"]
        step_idx = s["current_step"]

        if step_idx >= len(directions):
            return "You've completed all the steps!"

        step_num = step_idx + 1
        total = len(directions)
        step_text = directions[step_idx]
        return f"Step {step_num} of {total}: {step_text}"

    def _stop(self) -> str:
        name = self._session.get("recipe_name", "the recipe") if self._session else "the recipe"
        step = (self._session.get("current_step", 0) + 1) if self._session else 0
        self._session = None
        return f"Cooking session for {name} ended at step {step}."

    def _ask_question(self, question: str) -> str:
        if not self._llm:
            return "I can't answer questions without an LLM connection."

        context = self.get_llm_context()
        prompt = (
            f"The user is currently cooking and has a question.\n\n"
            f"Cooking context:\n{context}\n\n"
            f"Question: {question}\n\n"
            f"Answer concisely (1-2 sentences) in the context of "
            f"the recipe being prepared. Be practical and helpful."
        )

        try:
            return self._llm.respond(prompt)
        except Exception:
            log.exception("Cooking question LLM error")
            return "Sorry, I had trouble answering that."

    def close(self) -> None:
        self._session = None
