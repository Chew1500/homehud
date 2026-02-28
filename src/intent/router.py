"""Intent router — dispatches transcribed text to features or LLM fallback."""

from __future__ import annotations

import logging

from features.base import BaseFeature
from llm.base import BaseLLM

log = logging.getLogger("home-hud.intent")


class IntentRouter:
    """Routes transcribed text via LLM-first structured parsing with regex fallback.

    Primary path: LLM parse_intent() returns structured {type, feature, action,
    parameters, speech} via tool_use. On LLM error or None, falls back to regex
    matching, then intent recovery, then conversational LLM.
    """

    def __init__(self, config: dict, features: list[BaseFeature], llm: BaseLLM):
        self._config = config
        self._features = features
        self._llm = llm
        self._recovery_enabled = config.get("intent_recovery_enabled", True)
        self._feature_descriptions = self._collect_descriptions()
        self._last_feature: BaseFeature | None = None
        self._llm_expects_follow_up = False

        # Build feature lookup map: lowercase key → feature instance
        self._feature_map: dict[str, BaseFeature] = {}
        for f in features:
            key = f.name.lower().replace(" ", "_")
            self._feature_map[key] = f
            # Also map common aliases
            name_lower = f.name.lower()
            if name_lower not in self._feature_map:
                self._feature_map[name_lower] = f

    def _collect_descriptions(self) -> list[str]:
        """Gather non-empty descriptions from all features."""
        return [f.description for f in self._features if f.description]

    @property
    def expects_follow_up(self) -> bool:
        """Whether the last matched feature expects an immediate follow-up."""
        # Feature state takes priority (knows actual disambiguation state etc.)
        if self._last_feature is not None and self._last_feature.expects_follow_up:
            return True
        return self._llm_expects_follow_up

    def _try_features(self, text: str) -> str | None:
        """Try matching text against features. Returns response or None."""
        for feature in self._features:
            if feature.matches(text):
                log.info("Matched feature: %s", feature.__class__.__name__)
                self._last_feature = feature
                return feature.handle(text)
        return None

    def _try_llm_parse(self, text: str) -> str | None:
        """Try LLM-first structured intent parsing.

        Returns the final response string, or None to trigger fallback.
        """
        # Collect feature schemas
        schemas = []
        for f in self._features:
            schema = f.action_schema
            if schema:
                key = f.name.lower().replace(" ", "_")
                schemas.append({"name": key, "actions": schema})

        # Collect active context from features with state
        context_parts = []
        for f in self._features:
            ctx = f.get_llm_context()
            if ctx:
                context_parts.append(ctx)
        context = "\n".join(context_parts) if context_parts else None

        parsed = self._llm.parse_intent(text, schemas, context)
        if parsed is None:
            return None

        intent_type = parsed.get("type")
        speech = parsed.get("speech", "")

        if intent_type == "action":
            feature_name = parsed.get("feature", "")
            action = parsed.get("action", "")
            parameters = parsed.get("parameters") or {}

            feature = self._find_feature(feature_name)
            if feature is None:
                log.warning("LLM referenced unknown feature: %s", feature_name)
                return None

            try:
                self._last_feature = feature
                self._llm_expects_follow_up = parsed.get("expects_follow_up", False)
                result = feature.execute(action, parameters)
                self._llm.record_exchange(text, result)
                return result
            except Exception:
                log.exception("Feature execute() failed for %s.%s", feature_name, action)
                # Use LLM's speech as fallback
                if speech:
                    self._llm.record_exchange(text, speech)
                    return speech
                return None

        if intent_type == "conversation":
            self._last_feature = None
            self._llm_expects_follow_up = parsed.get("expects_follow_up", False)
            self._llm.record_exchange(text, speech)
            return speech

        if intent_type == "clarification":
            self._llm_expects_follow_up = parsed.get("expects_follow_up", True)
            self._llm.record_exchange(text, speech)
            return speech

        log.warning("Unknown intent type: %s", intent_type)
        return None

    def _find_feature(self, name: str) -> BaseFeature | None:
        """Look up a feature by name (case-insensitive, supports aliases)."""
        if not name:
            return None
        key = name.lower().strip()
        # Direct lookup
        if key in self._feature_map:
            return self._feature_map[key]
        # Try with underscores replaced by spaces and vice versa
        alt = key.replace("_", " ")
        if alt in self._feature_map:
            return self._feature_map[alt]
        alt = key.replace(" ", "_")
        if alt in self._feature_map:
            return self._feature_map[alt]
        # Substring match as last resort
        for map_key, feature in self._feature_map.items():
            if key in map_key or map_key in key:
                return feature
        return None

    def route(self, text: str) -> str:
        """Route text to the appropriate handler and return a response."""
        # 1. Try LLM-first structured parsing
        parsed = self._try_llm_parse(text)
        if parsed is not None:
            return parsed

        # 2. Fallback: regex-based routing
        result = self._try_features(text)
        if result is not None:
            self._llm_expects_follow_up = False
            self._llm.record_exchange(text, result)
            return result

        # 3. Intent recovery — ask LLM if this is a misheard command
        if self._recovery_enabled and self._feature_descriptions:
            try:
                corrected = self._llm.classify_intent(
                    text, self._feature_descriptions
                )
                if corrected:
                    log.info("Intent recovery: %r → %r", text, corrected)
                    result = self._try_features(corrected)
                    if result is not None:
                        self._llm.record_exchange(text, result)
                        return result
                    log.info("Corrected text didn't match any feature, falling through")
            except Exception:
                log.exception("Intent recovery failed, falling through to LLM")

        # 4. Final fallback: conversational LLM
        log.info("No feature matched, falling back to LLM")
        self._last_feature = None
        self._llm_expects_follow_up = False
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
