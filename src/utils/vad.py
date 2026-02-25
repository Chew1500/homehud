"""Energy-based voice activity detection for dynamic recording."""

import logging
import time
from collections.abc import Generator

import numpy as np

log = logging.getLogger(__name__)


class VoiceActivityDetector:
    """Detects end-of-speech using RMS energy of audio chunks.

    Accumulates audio from a stream and stops when silence is detected
    for a configurable duration, respecting min/max recording time.
    """

    def __init__(self, config: dict):
        self._silence_threshold = config.get("vad_silence_threshold", 500)
        self._silence_duration = config.get("vad_silence_duration", 1.5)
        self._min_duration = config.get("vad_min_duration", 0.5)
        self._max_duration = config.get("vad_max_duration", 15.0)
        self._sample_rate = config.get("audio_sample_rate", 16000)

    @staticmethod
    def rms(chunk: bytes) -> float:
        """Compute RMS energy of a PCM int16 chunk."""
        samples = np.frombuffer(chunk, dtype=np.int16)
        if len(samples) == 0:
            return 0.0
        return float(np.sqrt(np.mean(samples.astype(np.float64) ** 2)))

    def record_until_silence(self, stream: Generator[bytes, None, None]) -> bytes:
        """Record from a stream until silence is detected.

        Stops when:
        - Silence (RMS below threshold) persists for silence_duration seconds
          AND at least min_duration has elapsed
        - OR max_duration is reached

        Returns:
            Concatenated PCM bytes from the recording.
        """
        chunks: list[bytes] = []
        start = time.monotonic()
        silence_start: float | None = None

        try:
            for chunk in stream:
                elapsed = time.monotonic() - start
                chunks.append(chunk)

                # Enforce max duration
                if elapsed >= self._max_duration:
                    log.info("VAD: max duration reached (%.1fs)", elapsed)
                    break

                energy = self.rms(chunk)

                if energy < self._silence_threshold:
                    if silence_start is None:
                        silence_start = time.monotonic()
                    silence_elapsed = time.monotonic() - silence_start
                    if silence_elapsed >= self._silence_duration and elapsed >= self._min_duration:
                        log.info(
                            "VAD: silence detected after %.1fs (silence=%.1fs)",
                            elapsed, silence_elapsed,
                        )
                        break
                else:
                    silence_start = None
        finally:
            stream.close()

        total = time.monotonic() - start
        log.info("VAD: recorded %.1fs (%d chunks)", total, len(chunks))
        return b"".join(chunks)
