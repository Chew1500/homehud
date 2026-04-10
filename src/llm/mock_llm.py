"""Mock LLM backend for local development.

Returns a configurable canned response, ignoring actual input text.
"""

from __future__ import annotations

import logging

from llm.base import BaseLLM

log = logging.getLogger(__name__)


class MockLLM(BaseLLM):
    """Fake LLM that returns a fixed string for development."""

    def __init__(self, config: dict):
        super().__init__(config)
        self._response = config.get("llm_mock_response", "This is a mock LLM response.")

    def parse_intent(
        self, text: str, feature_schemas: list[dict], context: str | None = None
    ) -> dict | None:
        """Mock always returns None — no structured parsing in local dev."""
        return None

    def respond(self, text: str) -> str:
        """Return the configured canned response, ignoring input text."""
        log.info("Mock LLM called with: %r", text)
        response = self._response
        self._record_exchange(text, response)
        return response

    def classify_intent(self, text: str, feature_descriptions: list[str]) -> str | None:
        """Mock always returns None — no intent recovery in local dev."""
        return None

    def parse_recipe_image(
        self, image_b64: str, media_type: str = "image/jpeg"
    ) -> dict | None:
        """Return a canned recipe for local dev testing."""
        return {
            "name": "Mock Recipe",
            "source": "image_upload",
            "tags": ["mock", "testing"],
            "prep_time_min": 10,
            "cook_time_min": 20,
            "servings": 4,
            "ingredients": [
                {"name": "ingredient one", "quantity": "1", "unit": "cup"},
                {"name": "ingredient two", "quantity": "2", "unit": "tbsp"},
            ],
            "directions": [
                "Step one: prepare ingredients.",
                "Step two: cook everything together.",
                "Step three: serve and enjoy.",
            ],
            "raw_text": "Mock extracted text from image.",
        }
