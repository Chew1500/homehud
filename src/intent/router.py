"""Intent router — dispatches transcribed text to features or LLM fallback."""

from __future__ import annotations

import logging
import re
import time
from collections.abc import Generator

from features.base import BaseFeature
from llm.base import BaseLLM

# Cross-turn context lifetime. Long enough for a natural conversational
# follow-up ("add the second one") but short enough that stale state from an
# earlier task doesn't bleed into an unrelated query.
_CONTEXT_TTL_SEC = 60.0

# Pending-confirmation lifetime. User has this long to say "confirm" after
# being prompted "about to clear 17 items...". Tight window — if they wait
# half a minute, they probably changed their mind.
_PENDING_TTL_SEC = 30.0

# Confirmation lexicons. Deliberately small and unambiguous; anything else
# treats the pending action as cancelled and routes the new utterance normally.
_CONFIRM_RE = re.compile(
    r"^\s*(?:yes|yeah|yep|yup|confirm|confirmed|go ahead|do it|proceed|ok|okay|sure|please do)"
    r"\s*[.!,]?\s*$",
    re.IGNORECASE,
)
_CANCEL_RE = re.compile(
    r"^\s*(?:no|nope|cancel|nevermind|never mind|stop|don't|forget it|wait)"
    r"\s*[.!,]?\s*$",
    re.IGNORECASE,
)

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
        self._last_route_info: dict | None = None
        self._last_llm_calls: list[dict] = []
        # Cross-turn context for positional/pronoun references. Features that
        # render a list or name a specific entity write here so the LLM can
        # resolve "the second one", "add it", "what are the ingredients", etc.
        # See set_last_list / set_last_entity.
        self._last_list: dict | None = None      # {"source", "items", "ts"}
        self._last_entity: dict | None = None    # {"source", "entity", "ts"}
        # Pending destructive action awaiting yes/no confirmation.
        # {"feature", "action", "params", "summary", "ts"}
        self._pending_action: dict | None = None

        # Build feature lookup map: lowercase key → feature instance
        self._feature_map: dict[str, BaseFeature] = {}
        for f in features:
            key = f.name.lower().replace(" ", "_")
            self._feature_map[key] = f
            # Also map common aliases
            name_lower = f.name.lower()
            if name_lower not in self._feature_map:
                self._feature_map[name_lower] = f

        # Attach ourselves to each feature so they can record cross-turn
        # context (see BaseFeature._set_last_list / _set_last_entity).
        for f in features:
            try:
                f._router = self  # type: ignore[attr-defined]
            except Exception:
                pass

    def _collect_descriptions(self) -> list[str]:
        """Gather non-empty descriptions from all features."""
        return [f.description for f in self._features if f.description]

    # -- Cross-turn context (last_list / last_entity) --
    #
    # Contract: callers must invoke these synchronously from a feature's
    # execute()/handle() — i.e. while the voice lock is held. Background
    # threads (scheduler fires, reminder due callbacks) MUST NOT touch this
    # state, or the router's view of "what was just said" will desync from
    # what the user actually heard.

    def set_last_list(self, source: str, items: list[dict]) -> None:
        """Record a list the user just heard, for positional references.

        `items` should be a list of small dicts, each with at least a `name`
        key. The LLM sees them as "1=A, 2=B, 3=C" context on the next turn.
        """
        if not items:
            self._last_list = None
            return
        self._last_list = {
            "source": source,
            "items": list(items),
            "ts": time.monotonic(),
        }

    def set_last_entity(self, source: str, entity: dict) -> None:
        """Record the single entity the user just heard named (recipe, movie,
        etc). The LLM uses this to resolve 'it' / 'that' / 'the ingredients'."""
        if entity is None:
            self._last_entity = None
            return
        self._last_entity = {
            "source": source,
            "entity": dict(entity),
            "ts": time.monotonic(),
        }

    def clear_turn_context(self) -> None:
        """Drop any last_list / last_entity. Call when switching feature
        domains to prevent stale pointers (e.g. the Tortilla Soup bug)."""
        self._last_list = None
        self._last_entity = None

    # -- Pending-confirmation primitive --
    #
    # Features with destructive side effects (grocery.clear, bulk delete)
    # stage their action here instead of executing it, then return the
    # summary. The router replays the action on the next turn if the user
    # confirms, otherwise drops it.

    def request_confirmation(
        self,
        feature: BaseFeature,
        action: str,
        params: dict,
        summary: str,
    ) -> str:
        """Queue `feature.execute(action, params)` pending user confirmation.

        Returns the summary string (the feature returns this to the user).
        The router automatically picks up the next turn's yes/no via `route()`.
        """
        self._pending_action = {
            "feature": feature,
            "action": action,
            "params": dict(params),
            "summary": summary,
            "ts": time.monotonic(),
        }
        self._llm_expects_follow_up = True
        return summary

    def _pending_context(self) -> str | None:
        """Context line describing any pending confirmation, for the intent
        prompt. Expires stale pending on read."""
        if self._pending_action is None:
            return None
        age = time.monotonic() - self._pending_action["ts"]
        if age > _PENDING_TTL_SEC:
            self._pending_action = None
            return None
        return (
            f"[CONTEXT: pending_confirmation ({int(age)}s ago): "
            f"{self._pending_action['summary']}]"
        )

    def _resolve_pending_or_intercept(self, text: str) -> str | None:
        """If a confirmation is pending, resolve it and return a response.

        Returns a response string when handled (confirm/cancel), None when the
        caller should continue with normal routing (pending was stale or the
        utterance wasn't a confirmation-style phrase).
        """
        if self._pending_action is None:
            return None
        age = time.monotonic() - self._pending_action["ts"]
        if age > _PENDING_TTL_SEC:
            self._pending_action = None
            return None

        if _CONFIRM_RE.match(text):
            pending = self._pending_action
            self._pending_action = None
            self._llm_expects_follow_up = False
            self._last_route_info = {
                "path": "pending_confirm",
                "matched_feature": pending["feature"].name,
                "feature_action": pending["action"],
            }
            try:
                result = pending["feature"].execute(
                    pending["action"], pending["params"]
                )
            except Exception:
                log.exception(
                    "Pending action %s.%s failed on confirm",
                    pending["feature"].name, pending["action"],
                )
                result = "Something went wrong carrying that out."
            self._llm.record_exchange(text, result)
            return result

        if _CANCEL_RE.match(text):
            self._pending_action = None
            self._llm_expects_follow_up = False
            self._last_route_info = {
                "path": "pending_cancel",
                "matched_feature": None,
                "feature_action": None,
            }
            msg = "Okay, cancelled."
            self._llm.record_exchange(text, msg)
            return msg

        # Unrelated utterance: drop the pending so the user isn't stuck, then
        # let normal routing handle what they said.
        self._pending_action = None
        self._llm_expects_follow_up = False
        return None

    def _format_turn_context(self) -> list[str]:
        """Serialize last_list and last_entity into intent-prompt lines.

        Returns lines like:
            [CONTEXT: last_list(recipes, 12s ago): 1=Salmon, 2=Shakshuka]
            [CONTEXT: last_entity(recipes, 3s ago): Skillet Gnocchi]
        """
        out: list[str] = []
        now = time.monotonic()
        if self._last_list is not None:
            age = now - self._last_list["ts"]
            if age > _CONTEXT_TTL_SEC:
                self._last_list = None
            else:
                items = self._last_list["items"]
                preview = ", ".join(
                    f"{i + 1}={item.get('name', item)}"
                    for i, item in enumerate(items[:10])
                )
                out.append(
                    f"[CONTEXT: last_list({self._last_list['source']}, "
                    f"{int(age)}s ago): {preview}]"
                )
        if self._last_entity is not None:
            age = now - self._last_entity["ts"]
            if age > _CONTEXT_TTL_SEC:
                self._last_entity = None
            else:
                ent = self._last_entity["entity"]
                label = ent.get("name") or str(ent)
                out.append(
                    f"[CONTEXT: last_entity({self._last_entity['source']}, "
                    f"{int(age)}s ago): {label}]"
                )
        return out

    @property
    def expects_follow_up(self) -> bool:
        """Whether the last matched feature expects an immediate follow-up."""
        # Feature state takes priority (knows actual disambiguation state etc.)
        if self._last_feature is not None and self._last_feature.expects_follow_up:
            return True
        return self._llm_expects_follow_up

    def _try_features(self, text: str, path: str = "regex") -> str | None:
        """Try matching text against features. Returns response or None."""
        for feature in self._features:
            if feature.matches(text):
                log.info("Matched feature: %s", feature.__class__.__name__)
                self._last_feature = feature
                self._last_route_info = {
                    "path": path,
                    "matched_feature": feature.name,
                    "feature_action": None,
                }
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

        # Collect active context from features with state, plus the router's
        # cross-turn list/entity snapshots for resolving pronoun references.
        context_parts: list[str] = []
        for f in self._features:
            ctx = f.get_llm_context()
            if ctx:
                context_parts.append(ctx)
        context_parts.extend(self._format_turn_context())
        pending_line = self._pending_context()
        if pending_line:
            context_parts.append(pending_line)
        context = "\n".join(context_parts) if context_parts else None

        parsed = self._llm.parse_intent(text, schemas, context)
        self._collect_llm_call()
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
                self._last_route_info = {
                    "path": "llm_parse",
                    "matched_feature": feature_name,
                    "feature_action": action,
                }
                result = feature.execute(action, parameters)
                self._llm.record_exchange(text, result)
                return result
            except Exception:
                log.exception("Feature execute() failed for %s.%s", feature_name, action)
                # Use LLM's speech as fallback, but for mutating actions the
                # LLM's optimistic confirmation would mislead the user, so
                # append a failure note.
                if speech:
                    if action in {"add", "remove", "clear", "set", "delete"}:
                        speech = f"{speech} But something went wrong saving that."
                    self._llm.record_exchange(text, speech)
                    return speech
                return None

        if intent_type == "conversation":
            self._last_feature = None
            self._llm_expects_follow_up = parsed.get("expects_follow_up", False)
            if speech:
                self._last_route_info = {
                    "path": "llm_conversation",
                    "matched_feature": None,
                    "feature_action": None,
                }
                self._llm.record_exchange(text, speech)
                return speech
            return None  # Fall through to respond_stream()

        if intent_type == "clarification":
            self._last_feature = None
            self._llm_expects_follow_up = parsed.get("expects_follow_up", True)
            if speech:
                self._last_route_info = {
                    "path": "llm_clarification",
                    "matched_feature": None,
                    "feature_action": None,
                }
                self._llm.record_exchange(text, speech)
                return speech
            return None  # Fall through to respond_stream()

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

    def _collect_llm_call(self) -> None:
        """Append the LLM's last call info to _last_llm_calls if present."""
        if self._llm._last_call_info is not None:
            self._last_llm_calls.append(self._llm._last_call_info)

    def _wrap_stream(self, stream: Generator[str, None, None]) -> Generator[str, None, None]:
        """Wrap a sentence stream with post-completion bookkeeping."""
        try:
            yield from stream
        finally:
            self._collect_llm_call()

    def route(self, text: str) -> str | Generator[str, None, None]:
        """Route text to the appropriate handler and return a response."""
        self._last_route_info = None
        self._last_llm_calls = []

        # 0. Pending confirmation intercept — a staged destructive action from
        # the previous turn takes priority over normal routing.
        pending_result = self._resolve_pending_or_intercept(text)
        if pending_result is not None:
            return pending_result

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
                self._collect_llm_call()
                if corrected:
                    log.info("Intent recovery: %r → %r", text, corrected)
                    result = self._try_features(corrected, path="recovery")
                    if result is not None:
                        self._llm.record_exchange(text, result)
                        return result
                    log.info("Corrected text didn't match any feature, falling through")
            except Exception:
                log.exception("Intent recovery failed, falling through to LLM")

        # 4. Final fallback: conversational LLM (streamed)
        log.info("No feature matched, falling back to LLM")
        self._last_feature = None
        self._llm_expects_follow_up = False
        self._last_route_info = {
            "path": "llm_fallback",
            "matched_feature": None,
            "feature_action": None,
        }
        return self._wrap_stream(self._llm.respond_stream(text))

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
