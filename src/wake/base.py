"""Abstract base class for wake word detectors."""

from abc import ABC, abstractmethod


class BaseWakeWord(ABC):
    """Common interface for wake word detection backends.

    Processes audio chunks (raw PCM int16 bytes) and signals when
    the wake word is detected.
    """

    @abstractmethod
    def detect(self, audio_chunk: bytes) -> bool:
        """Process one audio chunk and return True if wake word detected."""
        ...

    @abstractmethod
    def reset(self) -> None:
        """Clear internal state after a detection."""
        ...

    def close(self) -> None:
        """Clean up resources. Override if needed."""
        pass
