"""Abstract base class for built-in features."""

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

    def close(self) -> None:
        """Clean up resources. Override if needed."""
        pass
