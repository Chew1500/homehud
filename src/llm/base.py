"""Abstract base class for LLM backends."""

from abc import ABC, abstractmethod


class BaseLLM(ABC):
    """Common interface for mock and real LLM backends.

    Input is a text string (from STT transcription).
    Output is the LLM's response string.
    """

    def __init__(self, config: dict):
        self._config = config

    @abstractmethod
    def respond(self, text: str) -> str:
        """Generate a response to the given text.

        Args:
            text: User's spoken text (from STT transcription).

        Returns:
            LLM response string.
        """
        ...

    def close(self) -> None:
        """Clean up resources. Override if needed."""
        pass
