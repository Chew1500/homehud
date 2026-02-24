"""Abstract base class for text-to-speech backends."""

from abc import ABC, abstractmethod


class BaseTTS(ABC):
    """Common interface for mock and real TTS backends.

    Output is raw PCM bytes (16-bit signed int16, little-endian, 16kHz mono),
    matching the format expected by audio.play().
    """

    def __init__(self, config: dict):
        self._config = config

    @abstractmethod
    def synthesize(self, text: str) -> bytes:
        """Synthesize text into raw PCM audio bytes.

        Args:
            text: Text string to synthesize.

        Returns:
            Raw PCM bytes (int16, little-endian, 16kHz mono).
        """
        ...

    def close(self) -> None:
        """Clean up resources. Override if needed."""
        pass
