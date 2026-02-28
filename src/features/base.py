"""Abstract base class for built-in features."""

from __future__ import annotations

from abc import ABC, abstractmethod


class BaseFeature(ABC):
    """Common interface for all built-in features.

    Each feature self-selects via matches() and handles commands via handle().
    The intent router iterates features in order, dispatching to the first match.
    """

    def __init__(self, config: dict):
        self._config = config

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable feature name (e.g., 'Grocery List')."""
        ...

    @property
    @abstractmethod
    def short_description(self) -> str:
        """One-line summary of what this feature does."""
        ...

    @abstractmethod
    def matches(self, text: str) -> bool:
        """Return True if this feature should handle the given text.

        Args:
            text: User's spoken text (from STT transcription).
        """
        ...

    @abstractmethod
    def handle(self, text: str) -> str:
        """Handle the command and return a spoken response.

        Args:
            text: User's spoken text (from STT transcription).

        Returns:
            Response string suitable for TTS.
        """
        ...

    @property
    def description(self) -> str:
        """Human-readable description of trigger patterns for intent classification.

        Override in subclasses to help the LLM identify misheard commands.
        """
        return ""

    @property
    def expects_follow_up(self) -> bool:
        """Whether this feature expects an immediate follow-up response.

        When True, the voice pipeline stays in the command loop instead of
        returning to wake word listening. Override in subclasses that have
        multi-turn flows (e.g., disambiguation).
        """
        return False

    @property
    def action_schema(self) -> dict:
        """Schema of actions and their parameters for LLM intent parsing.

        Override in subclasses. Format: {"action_name": {"param": "type"}, ...}
        """
        return {}

    def execute(self, action: str, parameters: dict) -> str:
        """Execute a pre-parsed action with parameters.

        Called by the intent router when the LLM has parsed the user's intent
        into a structured action. Override in subclasses.

        Args:
            action: The action name (e.g., "add", "list").
            parameters: Parsed parameters (e.g., {"item": "milk"}).

        Returns:
            Response string suitable for TTS.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not implement execute()"
        )

    def get_llm_context(self) -> str | None:
        """Return current state context for multi-turn LLM interactions.

        Override in subclasses with stateful flows (e.g., media disambiguation).
        Returns None when no active state needs to be communicated.
        """
        return None

    def close(self) -> None:
        """Clean up resources. Override if needed."""
        pass
