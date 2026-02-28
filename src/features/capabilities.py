"""Capabilities feature — lists what the assistant can do."""

from __future__ import annotations

import re

from features.base import BaseFeature

# List-all triggers: "what can you do", "what are your features", "help me", etc.
_LIST_ALL = re.compile(
    r"\b("
    r"what can you do"
    r"|what are your (?:features|capabilities|skills|abilities)"
    r"|what do you know how to do"
    r"|list your (?:features|capabilities|skills|abilities)"
    r"|help me"
    r"|what are you capable of"
    r")\b",
    re.IGNORECASE,
)

# Describe-one triggers: "tell me about X", "describe X", "what is X"
_DESCRIBE_ONE = re.compile(
    r"\b(?:tell me about|describe|what is)\s+(?:the\s+)?(.+?)\s*(?:feature)?\s*$",
    re.IGNORECASE,
)


class CapabilitiesFeature(BaseFeature):
    """Lists available features and describes individual ones on request."""

    def __init__(self, config: dict, features: list[BaseFeature]):
        super().__init__(config)
        self._features = features

    @property
    def name(self) -> str:
        return "Help"

    @property
    def short_description(self) -> str:
        return "Learn what I can help you with"

    @property
    def description(self) -> str:
        return (
            'Capabilities/help: triggered by "what can you do", "what are your features", '
            '"help me", "tell me about <feature>", "describe <feature>".'
        )

    @property
    def action_schema(self) -> dict:
        return {"list": {}, "describe": {"feature": "str"}}

    def execute(self, action: str, parameters: dict) -> str:
        if action == "list":
            return self._list_all()
        if action == "describe":
            feature = self._find_feature(parameters.get("feature", ""))
            if feature:
                return self._describe_one(feature)
            return self._list_all()
        return self._list_all()

    def matches(self, text: str) -> bool:
        if _LIST_ALL.search(text):
            return True
        m = _DESCRIBE_ONE.search(text)
        if m:
            return self._find_feature(m.group(1)) is not None
        return False

    def handle(self, text: str) -> str:
        if _LIST_ALL.search(text):
            return self._list_all()
        m = _DESCRIBE_ONE.search(text)
        if m:
            feature = self._find_feature(m.group(1))
            if feature:
                return self._describe_one(feature)
        return self._list_all()

    def _list_all(self) -> str:
        others = [f for f in self._features if f is not self]
        count = len(others)
        parts = [f"{f.name}: {f.short_description}" for f in others]
        listing = ". ".join(parts)
        thing = "thing" if count == 1 else "things"
        return (
            f"I can help you with {count} {thing}. {listing}. "
            "You can say 'tell me about' any of these for more details."
        )

    def _describe_one(self, feature: BaseFeature) -> str:
        desc = feature.description or feature.short_description
        return f"{feature.name}: {desc}"

    def _find_feature(self, query: str) -> BaseFeature | None:
        query_lower = query.lower().strip()
        for f in self._features:
            if f is self:
                continue
            if f.name.lower() == query_lower:
                return f
        return None
