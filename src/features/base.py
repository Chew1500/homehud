"""Abstract base class for built-in features."""

from abc import ABC, abstractmethod


class BaseFeature(ABC):
    """Common interface for all built-in features.

    Each feature self-selects via matches() and handles commands via handle().
    The intent router iterates features in order, dispatching to the first match.
    """

    def __init__(self, config: dict):
        self._config = config

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

    def close(self) -> None:
        """Clean up resources. Override if needed."""
        pass
