"""Abstract base class for speech-to-text backends."""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class TranscriptionResult:
    """STT result with optional confidence metrics."""

    text: str
    no_speech_prob: float = 0.0   # 0=speech, 1=non-speech
    avg_logprob: float = 0.0      # closer to 0=confident, <-1.0=low confidence


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

    def transcribe_with_confidence(self, audio: bytes) -> TranscriptionResult:
        """Transcribe with confidence metrics. Override for real metrics."""
        return TranscriptionResult(text=self.transcribe(audio))

    def close(self) -> None:
        """Clean up resources. Override if needed."""
        pass
