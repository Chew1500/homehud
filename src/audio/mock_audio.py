"""Mock audio backend for local development.

Records silence (or plays back a configured WAV file) and writes
played audio to WAV files in an output directory.
"""

import logging
import wave
from collections.abc import Generator
from pathlib import Path

from audio.base import BaseAudio

log = logging.getLogger(__name__)


class MockAudio(BaseAudio):
    """File-based audio backend for development without hardware."""

    def __init__(self, config: dict):
        super().__init__(
            sample_rate=config.get("audio_sample_rate", 16000),
            channels=config.get("audio_channels", 1),
        )
        self._output_dir = Path(config.get("audio_mock_dir", "output/audio"))
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._mock_input_file = config.get("audio_mock_input_file")

    def record(self, duration: float) -> bytes:
        """Return PCM from a mock input WAV file, or silence."""
        if self._mock_input_file:
            path = Path(self._mock_input_file)
            if path.exists():
                log.info(f"Mock recording from {path}")
                return _read_wav(path)
            log.warning(f"Mock input file not found: {path}, returning silence")

        num_samples = int(self.sample_rate * duration * self.channels)
        log.info(f"Mock recording {duration}s of silence ({num_samples} samples)")
        return b"\x00\x00" * num_samples

    def stream(self, chunk_duration_ms: int = 80) -> Generator[bytes, None, None]:
        """Yield silence chunks instantly (no sleeping — keeps tests fast)."""
        chunk_samples = self.sample_rate * chunk_duration_ms // 1000
        chunk = b"\x00\x00" * chunk_samples
        log.info("Mock audio stream started (%dms chunks, %d samples)",
                 chunk_duration_ms, chunk_samples)
        try:
            while True:
                yield chunk
        finally:
            log.info("Mock audio stream stopped.")

    def play(self, data: bytes) -> None:
        """Write PCM data to latest.wav in the output directory."""
        output_path = self._output_dir / "latest.wav"
        _write_wav(output_path, data, self.sample_rate, self.channels)
        log.info(f"Mock playback saved to {output_path}")


def _read_wav(path: Path) -> bytes:
    """Read a WAV file and return raw PCM bytes."""
    with wave.open(str(path), "rb") as wf:
        return wf.readframes(wf.getnframes())


def _write_wav(path: Path, data: bytes, sample_rate: int, channels: int) -> None:
    """Write raw PCM bytes to a WAV file (16-bit int16)."""
    sample_width = 2  # 16-bit
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(sample_rate)
        wf.writeframes(data)
