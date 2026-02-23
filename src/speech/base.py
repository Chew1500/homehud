"""Abstract base class for speech-to-text backends."""

from abc import ABC, abstractmethod


class BaseSTT(ABC):
    """Common interface for mock and real STT backends.

    Input is raw PCM bytes (16-bit signed int16, little-endian) from audio.record().
    Output is the transcribed text string.
    """

    def __init__(self, config: dict):
        self._config = config

    @abstractmethod
    def transcribe(self, audio: bytes) -> str:
        """Transcribe raw PCM audio bytes to text.

        Args:
            audio: Raw PCM bytes (int16, little-endian, 16kHz mono).

        Returns:
            Transcribed text string.
        """
        ...

    def close(self) -> None:
        """Clean up resources. Override if needed."""
        pass
