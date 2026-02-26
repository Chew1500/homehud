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

    def respond(self, text: str) -> str:
        """Return the configured canned response, ignoring input text."""
        log.info("Mock LLM called with: %r", text)
        response = self._response
        self._record_exchange(text, response)
        return response

    def classify_intent(self, text: str, feature_descriptions: list[str]) -> str | None:
        """Mock always returns None — no intent recovery in local dev."""
        return None
