"""Intent parsing and command routing."""

from features.base import BaseFeature
from intent.router import IntentRouter
from llm.base import BaseLLM


def get_router(config: dict, features: list[BaseFeature], llm: BaseLLM) -> IntentRouter:
    """Create an IntentRouter with the given features and LLM fallback."""
    return IntentRouter(config, features, llm)
