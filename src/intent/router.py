"""Intent router — dispatches transcribed text to features or LLM fallback."""

from __future__ import annotations

import logging

from features.base import BaseFeature
from llm.base import BaseLLM

log = logging.getLogger("home-hud.intent")


class IntentRouter:
    """Routes transcribed text to the first matching feature, or falls back to LLM.

    Features are tried in order. The first feature whose matches() returns True
    gets to handle the text. If no feature matches, intent recovery is attempted
    via the LLM before falling back to the LLM for a general response.
    """

    def __init__(self, config: dict, features: list[BaseFeature], llm: BaseLLM):
        self._config = config
        self._features = features
        self._llm = llm
        self._recovery_enabled = config.get("intent_recovery_enabled", True)
        self._feature_descriptions = self._collect_descriptions()
        self._last_feature: BaseFeature | None = None

    def _collect_descriptions(self) -> list[str]:
        """Gather non-empty descriptions from all features."""
        return [f.description for f in self._features if f.description]

    @property
    def expects_follow_up(self) -> bool:
        """Whether the last matched feature expects an immediate follow-up."""
        if self._last_feature is None:
            return False
        return self._last_feature.expects_follow_up

    def _try_features(self, text: str) -> str | None:
        """Try matching text against features. Returns response or None."""
        for feature in self._features:
            if feature.matches(text):
                log.info("Matched feature: %s", feature.__class__.__name__)
                self._last_feature = feature
                return feature.handle(text)
        return None

    def route(self, text: str) -> str:
        """Route text to the appropriate handler and return a response."""
        # 1. Try features (regex match)
        result = self._try_features(text)
        if result is not None:
            return result

        # 2. Intent recovery — ask LLM if this is a misheard command
        if self._recovery_enabled and self._feature_descriptions:
            try:
                corrected = self._llm.classify_intent(
                    text, self._feature_descriptions
                )
                if corrected:
                    log.info("Intent recovery: %r → %r", text, corrected)
                    result = self._try_features(corrected)
                    if result is not None:
                        return result
                    log.info("Corrected text didn't match any feature, falling through")
            except Exception:
                log.exception("Intent recovery failed, falling through to LLM")

        # 3. LLM fallback
        log.info("No feature matched, falling back to LLM")
        self._last_feature = None
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
