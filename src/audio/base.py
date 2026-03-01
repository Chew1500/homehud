"""Abstract base class for all audio backends."""

from abc import ABC, abstractmethod
from collections.abc import Generator

# Whisper's preferred input format
DEFAULT_SAMPLE_RATE = 16000
DEFAULT_CHANNELS = 1


class BaseAudio(ABC):
    """Common interface for mock and hardware audio backends.

    Audio data is raw PCM bytes (16-bit signed int16, little-endian).
    """

    def __init__(
        self,
        sample_rate: int = DEFAULT_SAMPLE_RATE,
        channels: int = DEFAULT_CHANNELS,
    ):
        self._sample_rate = sample_rate
        self._channels = channels

    @property
    def sample_rate(self) -> int:
        return self._sample_rate

    @property
    def channels(self) -> int:
        return self._channels

    @abstractmethod
    def record(self, duration: float) -> bytes:
        """Record audio for the given duration in seconds.

        Returns raw PCM bytes (int16, little-endian).
        """
        ...

    @abstractmethod
    def stream(self, chunk_duration_ms: int = 80) -> Generator[bytes, None, None]:
        """Yield PCM audio chunks continuously.

        Each chunk is chunk_duration_ms milliseconds of audio.
        Generator cleanup (close/break) stops the stream.
        """
        ...

    @abstractmethod
    def play(self, data: bytes) -> None:
        """Play raw PCM audio data (int16, little-endian)."""
        ...

    def play_async(self, data: bytes) -> None:
        """Start playing audio without blocking. Override for real async playback.

        Default implementation falls back to synchronous play().
        """
        self.play(data)

    def play_streamed(self, chunks: Generator[bytes, None, None]) -> None:
        """Play audio chunks as they arrive from a generator.

        Default implementation collects all chunks and falls back to
        play_async(). Override for true streaming playback.
        """
        data = b"".join(chunks)
        self.play_async(data)

    def stop_playback(self) -> None:
        """Stop any in-progress playback. Override for real implementation."""
        pass

    def is_playing(self) -> bool:
        """Return True if async playback is in progress. Override for real implementation."""
        return False

    def close(self) -> None:
        """Clean up resources. Override if needed."""
        pass
