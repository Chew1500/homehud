# Cooking & Recipe Feature — Implementation Plan

## Context

Users want to manage recipes from their phones via the PWA. The feature covers the full lifecycle: capture a recipe from a photo, store it, get voice-powered recommendations, add ingredients to the grocery list, and get step-by-step cooking guidance via voice. This is a new subsystem touching the LLM layer (vision), features layer (two new features), web layer (API + UI tab), and integration with the existing grocery feature.

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Data format | JSON (`data/recipes.json`) | Matches grocery/reminders pattern; small collection; easy to debug |
| Feature split | `RecipeFeature` + `CookingSessionFeature` | Keeps each under ~500 lines; separates CRUD/recs from step-by-step state machine |
| Image upload | Base64 in JSON POST | Simpler with stdlib http.server; image needs base64 for Anthropic vision API anyway |
| Grocery integration | Call existing `GroceryFeature` methods | No changes to GroceryFeature itself; quantities embedded in item strings (e.g. "2 lbs chicken") |
| Cooking session TTL | 3600s (1 hour), independent of LLM history | Cooking sessions outlast the 300s LLM history; context injected fresh via `get_llm_context()` |
| Vision model | Claude Sonnet (not Haiku) | Vision quality matters for recipe parsing |
| Recipes tab visibility | Regular users (not admin-only) | Recipes are a user-facing feature like Voice and Garden |

---

## Recipe Data Model

```python
{
    "id": "uuid4",
    "name": "Chicken Tikka Masala",
    "source": "image_upload" | "manual" | "voice",
    "tags": ["spicy", "indian", "chicken", "dinner"],
    "prep_time_min": 15,
    "cook_time_min": 30,
    "servings": 4,
    "ingredients": [
        {"name": "chicken breast", "quantity": "2", "unit": "lbs"},
        {"name": "yogurt", "quantity": "1", "unit": "cup"}
    ],
    "directions": [
        "Marinate chicken in yogurt and spices for 30 minutes.",
        "Heat oil in a large skillet over medium-high heat.",
        "Cook chicken until browned, about 5 minutes per side."
    ],
    "raw_text": "Original extracted text from image...",
    "created_at": "2026-04-10T12:00:00"
}
```

---

## Implementation Phases

### Phase 1: Data Layer — Recipe Storage
- [ ] `src/cooking/__init__.py` — package marker
- [ ] `src/cooking/storage.py` — RecipeStorage class (~150 lines)
- [ ] Add `ConfigParam("recipe_file", ...)` to `src/config.py`

### Phase 2: Vision API — Recipe Image Parsing
- [ ] `src/llm/base.py` — add abstract `parse_recipe_image()`
- [ ] `src/llm/claude_llm.py` — implement with Anthropic vision API + tool_use
- [ ] `src/llm/mock_llm.py` — canned recipe dict for dev

### Phase 3: RecipeFeature (CRUD + Recommendations + Grocery Integration)
- [ ] `src/features/recipe.py` (~500 lines)
- [ ] Actions: list, search, detail, delete, recommend, refine_recommendation, add_ingredients_to_grocery, start_cooking
- [ ] Multi-turn recommendation via `expects_follow_up` + `get_llm_context()`
- [ ] Grocery integration: cross-reference ingredients, smart dedup, add missing items

### Phase 4: CookingSessionFeature (Step-by-Step Voice Guidance)
- [ ] `src/features/cooking_session.py` (~450 lines)
- [ ] Actions: next_step, previous_step, repeat_step, current_step, ask_question, stop_cooking, what_step
- [ ] 3600s session TTL, independent of LLM history
- [ ] Rich `get_llm_context()` for mid-cooking questions

### Phase 5: API Endpoints
- [ ] `GET /api/recipes` — list all
- [ ] `GET /api/recipes/<id>` — detail
- [ ] `POST /api/recipes/upload-image` — parse from photo
- [ ] `POST /api/recipes` — create manually
- [ ] `PUT /api/recipes/<id>` — update
- [ ] `DELETE /api/recipes/<id>` — delete

### Phase 6: PWA Recipes Tab
- [ ] `src/telemetry/ui/recipes.py` — list view, detail view, upload flow, edit view
- [ ] Wire into `shell.py` (TAB_BAR, TAB_LOADERS, visible to regular users)
- [ ] Wire into `__init__.py`

### Phase 7: Intent System Wiring
- [ ] Add recipes + cooking_session to `_INTENT_SYSTEM_PROMPT` in `claude_llm.py`
- [ ] Wire RecipeStorage, RecipeFeature, CookingSessionFeature in `main.py`
- [ ] Pass recipe_storage + llm to TelemetryWeb

### Phase 8: Tests
- [ ] `tests/test_recipe_storage.py` — CRUD, search, persistence, corruption
- [ ] `tests/test_recipe_feature.py` — action_schema, execute, matches, grocery integration
- [ ] `tests/test_cooking_session.py` — lifecycle, navigation, TTL, context

---

## File Change Summary

| File | Change |
|------|--------|
| `src/cooking/__init__.py` | **New** — package marker |
| `src/cooking/storage.py` | **New** — RecipeStorage class |
| `src/features/recipe.py` | **New** — RecipeFeature |
| `src/features/cooking_session.py` | **New** — CookingSessionFeature |
| `src/telemetry/ui/recipes.py` | **New** — Recipes tab HTML/JS |
| `tests/test_recipe_storage.py` | **New** |
| `tests/test_recipe_feature.py` | **New** |
| `tests/test_cooking_session.py` | **New** |
| `src/llm/base.py` | Add `parse_recipe_image` abstract method |
| `src/llm/claude_llm.py` | Implement vision method + update intent prompt |
| `src/llm/mock_llm.py` | Add mock `parse_recipe_image` |
| `src/config.py` | Add `recipe_file` ConfigParam |
| `src/main.py` | Instantiate and wire RecipeStorage, RecipeFeature, CookingSessionFeature |
| `src/telemetry/web.py` | Add recipe API endpoints |
| `src/telemetry/ui/shell.py` | Add Recipes tab button + loader |
| `src/telemetry/ui/__init__.py` | Import and compose recipes tab |

---

## Verification

1. `make test` — all new test files pass
2. `make lint` — no ruff violations
3. `make dev` — app starts without errors in mock mode
4. Image upload: PWA on phone -> Recipes tab -> upload photo -> verify parsed
5. Voice CRUD: "Show my recipes", "Find a spicy recipe", "Delete the pasta recipe"
6. Recommendations: "Recommend something healthy" -> refine with "something lighter"
7. Grocery integration: "Add ingredients for tikka masala to grocery list" -> verify items
8. Cooking session: "Let's cook the pasta recipe" -> "next step" -> "how many cups in a liter?" -> "I'm done cooking"
9. Mobile UI: Test all views on phone via Tailscale
