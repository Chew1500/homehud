"""Hardware audio backend using sounddevice.

Captures audio from a real microphone and plays back through speakers.
Only used on the Raspberry Pi — sounddevice is not required for local dev.
"""

import logging
import queue
from collections.abc import Generator

from audio.base import BaseAudio

log = logging.getLogger(__name__)


class HardwareAudio(BaseAudio):
    """Real audio I/O via sounddevice."""

    def __init__(self, config: dict):
        super().__init__(
            sample_rate=config.get("audio_sample_rate", 16000),
            channels=config.get("audio_channels", 1),
        )
        try:
            import sounddevice  # noqa: F401
            self._sd = sounddevice
        except ImportError as e:
            raise RuntimeError(
                "sounddevice is required for hardware audio mode. "
                "Install it with: pip install sounddevice"
            ) from e
        log.info(
            f"HardwareAudio initialized: {self.sample_rate}Hz, "
            f"{self.channels}ch"
        )

    def stream(self, chunk_duration_ms: int = 80) -> Generator[bytes, None, None]:
        """Yield PCM chunks from the microphone continuously."""
        chunk_samples = self.sample_rate * chunk_duration_ms // 1000
        q: queue.Queue[bytes] = queue.Queue()

        def callback(indata, frames, time_info, status):
            if status:
                log.warning("Stream status: %s", status)
            q.put(bytes(indata))

        stream = self._sd.InputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype="int16",
            blocksize=chunk_samples,
            callback=callback,
        )
        log.info("Hardware audio stream started (%dms chunks)", chunk_duration_ms)
        try:
            stream.start()
            while True:
                try:
                    yield q.get(timeout=1.0)
                except queue.Empty:
                    continue
        finally:
            stream.stop()
            stream.close()
            log.info("Hardware audio stream stopped.")

    def record(self, duration: float) -> bytes:
        """Record from the microphone for the given duration."""
        num_frames = int(self.sample_rate * duration)
        log.info(f"Recording {duration}s from mic...")
        audio = self._sd.rec(
            num_frames,
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype="int16",
        )
        self._sd.wait()
        return audio.tobytes()

    def play(self, data: bytes) -> None:
        """Play raw PCM data through the speakers."""
        import numpy as np

        audio = np.frombuffer(data, dtype=np.int16)
        if self.channels > 1:
            audio = audio.reshape(-1, self.channels)
        log.info(f"Playing {len(data)} bytes of audio...")
        self._sd.play(audio, samplerate=self.sample_rate)
        self._sd.wait()

    def close(self) -> None:
        """Stop any active playback/recording."""
        self._sd.stop()
        log.info("HardwareAudio closed.")
