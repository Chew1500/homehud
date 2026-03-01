"""Abstract base class for text-to-speech backends."""

from abc import ABC, abstractmethod
from collections.abc import Generator


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

    def synthesize_stream(self, text: str) -> Generator[bytes, None, None]:
        """Yield PCM audio chunks as they are synthesized.

        Default implementation wraps synthesize() — yields the entire
        result as a single chunk. Subclasses override for true streaming.

        Args:
            text: Text string to synthesize.

        Yields:
            Raw PCM bytes (int16, little-endian, 16kHz mono) per chunk.
        """
        yield self.synthesize(text)

    def close(self) -> None:
        """Clean up resources. Override if needed."""
        pass
