"""Recipe feature — CRUD, recommendations, and grocery integration via voice."""

from __future__ import annotations

import logging
import re
import time

from features.base import BaseFeature

log = logging.getLogger("home-hud.features.recipe")

# -- Command patterns --
_ANY_RECIPE = re.compile(
    r"\b(recipe|recipes|recipe\s*book|cookbook)\b", re.IGNORECASE
)
_LIST = re.compile(
    r"\b(?:show|list|what(?:'s| are)?\s+(?:in|my))\s+"
    r"(?:the\s+)?(?:recipe|recipes|recipe\s*book|cookbook)\b",
    re.IGNORECASE,
)
_SEARCH = re.compile(
    r"\b(?:find|search|look\s+(?:for|up))\s+(?:a\s+)?(.+?)\s+recipe\b",
    re.IGNORECASE,
)
_DETAIL = re.compile(
    r"\b(?:show|read|open|tell\s+me\s+about)\s+(?:the\s+)?(.+?)\s+recipe\b",
    re.IGNORECASE,
)
_DELETE = re.compile(
    r"\b(?:delete|remove)\s+(?:the\s+)?(.+?)\s+recipe\b",
    re.IGNORECASE,
)
_RECOMMEND = re.compile(
    r"\b(?:recommend|suggest|what\s+should\s+I\s+(?:cook|make|eat)"
    r"|what(?:'s| is)\s+(?:good|nice)\s+(?:to|for)\s+(?:cook|dinner|lunch|eat)"
    r"|something\s+to\s+(?:cook|make|eat))\b",
    re.IGNORECASE,
)
_ADD_TO_GROCERY = re.compile(
    r"\badd\s+(?:the\s+)?ingredients?\s+(?:for|from)\s+(?:the\s+)?(.+?)"
    r"\s+(?:to\s+(?:the\s+)?(?:grocery|shopping)\s+list|recipe)\b",
    re.IGNORECASE,
)
_START_COOKING = re.compile(
    r"\b(?:let(?:'s)?\s+(?:cook|make|prepare)|start\s+cooking|cook\s+(?:the\s+)?)"
    r"(?:\s+(?:the\s+)?(.+?)\s+recipe)?\b",
    re.IGNORECASE,
)

# -- Recommendation follow-up patterns --
_REFINE_YES = re.compile(
    r"\b(?:yes|yeah|sure|sounds?\s+good|perfect|let(?:'s)?\s+(?:do|make)\s+(?:that|it))\b",
    re.IGNORECASE,
)
_REFINE_NO = re.compile(
    r"\b(?:no|nah|nope|something\s+else|another|different)\b",
    re.IGNORECASE,
)

_RECOMMENDATION_TTL = 120  # seconds

# Cap on how many recipe summaries we send to the LLM in one recommend call.
# Keeps prompt size bounded as the recipe book grows past a few hundred entries.
MAX_CANDIDATES = 25

_STOPWORDS = frozenset({
    "a", "an", "the", "give", "me", "some", "any", "with", "for",
    "something", "anything", "recipe", "recipes", "please", "i", "want",
    "would", "like", "to", "eat", "make", "cook", "have", "of", "and",
    "or", "that", "is", "good", "nice", "today", "tonight", "dinner",
    "lunch", "breakfast",
})


def _tokenize_preference(text: str) -> list[str]:
    """Lowercase, split on non-word chars, drop stopwords and short tokens."""
    tokens = re.findall(r"[a-zA-Z]+", text.lower())
    return [t for t in tokens if t not in _STOPWORDS and len(t) > 2]


def _recipe_haystack(recipe: dict) -> str:
    """Concatenate the searchable text of a recipe for token matching."""
    parts = [recipe.get("name", "")]
    parts.extend(recipe.get("tags", []) or [])
    parts.extend(
        (i.get("name") or "") for i in (recipe.get("ingredients") or [])
    )
    return " ".join(parts).lower()


def _filter_candidates(preference: str, recipes: list[dict]) -> list[dict]:
    """Pre-filter recipes by preference tokens, capped at MAX_CANDIDATES.

    Ranks by number of token matches (best fit first). Falls back to the
    full list (truncated) if no token matches anything.
    """
    tokens = _tokenize_preference(preference)
    if not tokens:
        return recipes[:MAX_CANDIDATES]

    scored: list[tuple[int, dict]] = []
    for r in recipes:
        hay = _recipe_haystack(r)
        score = sum(1 for tok in tokens if tok in hay)
        if score > 0:
            scored.append((score, r))

    if not scored:
        return recipes[:MAX_CANDIDATES]

    scored.sort(key=lambda s: s[0], reverse=True)
    return [r for _, r in scored[:MAX_CANDIDATES]]


class RecipeFeature(BaseFeature):
    """Manages recipes: CRUD, LLM-powered recommendations, grocery integration."""

    def __init__(
        self,
        config: dict,
        llm=None,
        recipe_storage=None,
        grocery_feature=None,
        cooking_session=None,
    ):
        super().__init__(config)
        self._llm = llm
        self._storage = recipe_storage
        self._grocery = grocery_feature
        self._cooking_session = cooking_session

        # Recommendation state
        self._active_recommendation: dict | None = None
        self._recommendation_context: str | None = None
        self._last_interaction: float = 0

    @property
    def name(self) -> str:
        return "Recipes"

    @property
    def short_description(self) -> str:
        return "Store, search, and get recipe recommendations"

    @property
    def description(self) -> str:
        return (
            'Recipes: triggered by "recipe", "recipes", "cookbook", "recommend something '
            'to cook", "what should I make". Commands: "show my recipes", '
            '"find a spicy recipe", "recommend something healthy", '
            '"add ingredients for tikka masala to grocery list", '
            '"let\'s cook the pasta recipe".'
        )

    @property
    def expects_follow_up(self) -> bool:
        return (
            self._active_recommendation is not None
            and (time.time() - self._last_interaction) < _RECOMMENDATION_TTL
        )

    @property
    def action_schema(self) -> dict:
        return {
            "list": {},
            "search": {"query": "str"},
            "detail": {"recipe_name": "str"},
            "delete": {"recipe_name": "str"},
            "recommend": {"preference": "str"},
            "refine_recommendation": {"feedback": "str"},
            "add_ingredients_to_grocery": {"recipe_name": "str"},
            "start_cooking": {"recipe_name": "str"},
        }

    def matches(self, text: str) -> bool:
        if self.expects_follow_up:
            if _REFINE_YES.search(text) or _REFINE_NO.search(text):
                return True
        return bool(
            _ANY_RECIPE.search(text)
            or _RECOMMEND.search(text)
            or _ADD_TO_GROCERY.search(text)
            or _START_COOKING.search(text)
        )

    def execute(self, action: str, parameters: dict) -> str:
        self._last_interaction = time.time()
        actions = {
            "list": lambda: self._list(),
            "search": lambda: self._search(parameters.get("query", "")),
            "detail": lambda: self._detail(parameters.get("recipe_name", "")),
            "delete": lambda: self._delete(parameters.get("recipe_name", "")),
            "recommend": lambda: self._recommend(parameters.get("preference", "")),
            "refine_recommendation": lambda: self._refine(
                parameters.get("feedback", "")
            ),
            "add_ingredients_to_grocery": lambda: self._add_to_grocery(
                parameters.get("recipe_name", "")
            ),
            "start_cooking": lambda: self._start_cooking(
                parameters.get("recipe_name", "")
            ),
        }
        handler = actions.get(action)
        if handler is None:
            return self._list()
        return handler()

    def handle(self, text: str) -> str:
        self._last_interaction = time.time()

        # Follow-up during recommendation
        if self.expects_follow_up and self._active_recommendation:
            if _REFINE_YES.search(text):
                name = self._active_recommendation.get("name", "")
                self._active_recommendation = None
                return (
                    f"Great choice! Say 'let's cook {name}' when "
                    f"you're ready, or 'add ingredients for "
                    f"{name} to grocery list'."
                )
            if _REFINE_NO.search(text):
                return self._refine(text)

        m = _ADD_TO_GROCERY.search(text)
        if m:
            return self._add_to_grocery(m.group(1).strip())

        m = _START_COOKING.search(text)
        if m and m.group(1):
            return self._start_cooking(m.group(1).strip())

        m = _DELETE.search(text)
        if m:
            return self._delete(m.group(1).strip())

        m = _SEARCH.search(text)
        if m:
            return self._search(m.group(1).strip())

        m = _DETAIL.search(text)
        if m:
            return self._detail(m.group(1).strip())

        if _RECOMMEND.search(text):
            return self._recommend(text)

        if _LIST.search(text):
            return self._list()

        return self._list()

    def get_llm_context(self) -> str | None:
        if not self.expects_follow_up or not self._active_recommendation:
            return None
        rec = self._active_recommendation
        return (
            f"Active recipe recommendation: \"{rec.get('name', 'unknown')}\". "
            f"User can accept (start cooking or add to grocery list), "
            f"ask for something different, or refine their preference."
        )

    # -- Actions --

    def _list(self) -> str:
        if not self._storage:
            return "Recipe storage is not available."
        recipes = self._storage.get_all()
        if not recipes:
            return (
                "Your recipe book is empty. Upload a recipe photo "
                "from the Recipes tab to get started."
            )
        names = [r.get("name", "Unnamed") for r in recipes]
        count = len(names)
        if count == 1:
            return f"You have one recipe: {names[0]}."
        joined = ", ".join(names[:-1]) + f", and {names[-1]}"
        return f"You have {count} recipes: {joined}."

    def _search(self, query: str) -> str:
        if not self._storage:
            return "Recipe storage is not available."
        if not query:
            return self._list()
        results = self._storage.search(query)
        if not results:
            return f"No recipes found matching '{query}'."
        names = [r.get("name", "Unnamed") for r in results]
        if len(names) == 1:
            return f"Found one recipe: {names[0]}."
        joined = ", ".join(names[:-1]) + f", and {names[-1]}"
        return f"Found {len(names)} recipes: {joined}."

    def _detail(self, recipe_name: str) -> str:
        if not self._storage:
            return "Recipe storage is not available."
        recipe = self._storage.get_by_name(recipe_name)
        if not recipe:
            return f"I couldn't find a recipe called '{recipe_name}'."
        ingredients = recipe.get("ingredients", [])
        ing_count = len(ingredients)
        directions = recipe.get("directions", [])
        step_count = len(directions)
        servings = recipe.get("servings")
        prep = recipe.get("prep_time_min")
        cook = recipe.get("cook_time_min")

        parts = [recipe["name"]]
        if servings:
            parts.append(f"serves {servings}")
        time_parts = []
        if prep:
            time_parts.append(f"{prep} minutes prep")
        if cook:
            time_parts.append(f"{cook} minutes cooking")
        if time_parts:
            parts.append(", ".join(time_parts))
        parts.append(f"{ing_count} ingredients, {step_count} steps")

        return ". ".join(parts) + ". Say 'let's cook it' to start, or ask me for more details."

    def _delete(self, recipe_name: str) -> str:
        if not self._storage:
            return "Recipe storage is not available."
        recipe = self._storage.get_by_name(recipe_name)
        if not recipe:
            return f"I couldn't find a recipe called '{recipe_name}'."
        self._storage.delete(recipe["id"])
        return f"Deleted {recipe['name']} from your recipe book."

    def _recommend(self, preference: str) -> str:
        if not self._storage or not self._llm:
            return "Recipe recommendations require both recipe storage and an LLM."
        recipes = self._storage.get_all()
        if not recipes:
            return "Your recipe book is empty. Add some recipes first."

        candidates = _filter_candidates(preference, recipes)
        prompt = self._build_recommend_prompt(
            preference, candidates, total=len(recipes)
        )

        try:
            response = self._llm.respond(prompt)
        except Exception:
            log.exception("Recipe recommendation LLM error")
            return "Sorry, I had trouble generating a recommendation."

        # Try to identify which recipe was recommended (search candidates first)
        for r in candidates:
            if r.get("name", "").lower() in response.lower():
                self._active_recommendation = r
                self._recommendation_context = preference
                break

        return response

    def _refine(self, feedback: str) -> str:
        if not self._storage or not self._llm:
            return "Recipe recommendations are not available."
        recipes = self._storage.get_all()
        if not recipes:
            return "Your recipe book is empty."

        prev_name = ""
        if self._active_recommendation:
            prev_name = self._active_recommendation.get("name", "")

        # Combine the original preference with the new feedback so the filter
        # still narrows by the original intent (e.g. "seafood" + "different one").
        combined = f"{self._recommendation_context or ''} {feedback}".strip()
        candidates = [
            r for r in _filter_candidates(combined, recipes)
            if r.get("name", "").lower() != prev_name.lower()
        ]
        if not candidates:
            candidates = [
                r for r in recipes
                if r.get("name", "").lower() != prev_name.lower()
            ][:MAX_CANDIDATES]

        prompt = self._build_refine_prompt(
            feedback, prev_name, candidates, total=len(recipes)
        )

        try:
            response = self._llm.respond(prompt)
        except Exception:
            log.exception("Recipe refinement LLM error")
            return "Sorry, I had trouble refining the recommendation."

        for r in candidates:
            if r.get("name", "").lower() in response.lower():
                self._active_recommendation = r
                break

        return response

    @staticmethod
    def _format_summary(recipe: dict, compact: bool) -> str:
        tags = ", ".join(recipe.get("tags", []) or [])
        if compact:
            return f"- {recipe.get('name', 'Unnamed')} [{tags}]"
        ing_names = [i.get("name", "") for i in (recipe.get("ingredients") or [])]
        return (
            f"- {recipe.get('name', 'Unnamed')} (tags: {tags}; "
            f"ingredients: {', '.join(ing_names[:8])}; "
            f"prep: {recipe.get('prep_time_min', '?')}min, "
            f"cook: {recipe.get('cook_time_min', '?')}min, "
            f"serves: {recipe.get('servings', '?')})"
        )

    def _build_recommend_prompt(
        self, preference: str, candidates: list[dict], total: int
    ) -> str:
        compact = total > MAX_CANDIDATES
        summaries = "\n".join(
            self._format_summary(r, compact=compact) for r in candidates
        )
        scope_note = (
            f"(showing {len(candidates)} of {total} recipes most relevant to the request)\n\n"
            if compact else ""
        )
        return (
            f"The user has these recipes:\n\n"
            f"{scope_note}{summaries}\n\n"
            f"The user wants: {preference}\n\n"
            f"Recommend ONE recipe from the list. Explain briefly why it matches. "
            f"Keep your response to 2-3 sentences, suitable for text-to-speech."
        )

    def _build_refine_prompt(
        self, feedback: str, prev_name: str, candidates: list[dict], total: int
    ) -> str:
        compact = total > MAX_CANDIDATES
        summaries = "\n".join(
            self._format_summary(r, compact=compact) for r in candidates
        )
        scope_note = (
            f"(showing {len(candidates)} of {total} recipes most relevant)\n\n"
            if compact else ""
        )
        return (
            f"The user has these recipes:\n\n"
            f"{scope_note}{summaries}\n\n"
            f"Previously recommended: {prev_name}\n"
            f"User feedback: {feedback}\n\n"
            f"Recommend a DIFFERENT recipe. Explain briefly why. "
            f"Keep to 2-3 sentences for text-to-speech."
        )

    def _add_to_grocery(self, recipe_name: str) -> str:
        if not self._storage:
            return "Recipe storage is not available."
        if not self._grocery:
            return "Grocery list is not available."

        recipe = self._storage.get_by_name(recipe_name)
        if not recipe:
            return f"I couldn't find a recipe called '{recipe_name}'."

        ingredients = recipe.get("ingredients", [])
        if not ingredients:
            return f"{recipe['name']} has no ingredients listed."

        entries = []
        for ing in ingredients:
            name = (ing.get("name") or "").strip()
            if not name:
                continue
            entries.append({
                "name": name,
                "quantity": ing.get("quantity"),
                "unit": ing.get("unit") or None,
            })
        if not entries:
            return f"No ingredients to add from {recipe['name']}."

        _, detail = self._grocery._add_many_detailed(entries)

        added_names = [a["name"] for a in detail["added"]] + [
            m["new"]["name"] for m in detail["mixed_units"]
        ]
        merged_names = [m["name"] for m in detail["merged"]]
        skipped_names = [s["name"] for s in detail["skipped_dup"]]
        pre_existing = merged_names + skipped_names

        parts = []
        if added_names:
            parts.append(
                f"Added {len(added_names)} items: {', '.join(added_names)}"
            )
        if pre_existing:
            parts.append(f"Already on list: {', '.join(pre_existing)}")
        if not parts:
            return f"No ingredients to add from {recipe['name']}."
        return ". ".join(parts) + "."

    def _start_cooking(self, recipe_name: str) -> str:
        if not self._storage:
            return "Recipe storage is not available."
        if not self._cooking_session:
            return "Cooking session is not available."

        recipe = self._storage.get_by_name(recipe_name)
        if not recipe:
            return f"I couldn't find a recipe called '{recipe_name}'."

        directions = recipe.get("directions", [])
        if not directions:
            return f"{recipe['name']} has no directions listed."

        self._active_recommendation = None
        return self._cooking_session.start(recipe)

    def close(self) -> None:
        self._active_recommendation = None
