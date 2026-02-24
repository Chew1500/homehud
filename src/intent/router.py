"""Intent router — dispatches transcribed text to features or LLM fallback."""

import logging

from features.base import BaseFeature
from llm.base import BaseLLM

log = logging.getLogger("home-hud.intent")


class IntentRouter:
    """Routes transcribed text to the first matching feature, or falls back to LLM.

    Features are tried in order. The first feature whose matches() returns True
    gets to handle the text. If no feature matches, the LLM handles it.
    """

    def __init__(self, config: dict, features: list[BaseFeature], llm: BaseLLM):
        self._config = config
        self._features = features
        self._llm = llm

    def route(self, text: str) -> str:
        """Route text to the appropriate handler and return a response."""
        for feature in self._features:
            if feature.matches(text):
                log.info("Matched feature: %s", feature.__class__.__name__)
                return feature.handle(text)

        log.info("No feature matched, falling back to LLM")
        return self._llm.respond(text)

    def close(self) -> None:
        """Close all features and the LLM."""
        for feature in self._features:
            try:
                feature.close()
            except Exception:
                log.exception("Error closing feature %s", feature.__class__.__name__)
        try:
            self._llm.close()
        except Exception:
            log.exception("Error closing LLM")
