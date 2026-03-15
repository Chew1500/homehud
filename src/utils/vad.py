"""Energy-based voice activity detection for dynamic recording."""

import logging
import statistics
import time
from collections.abc import Generator

import numpy as np

log = logging.getLogger(__name__)

# Minimum silence threshold floor — prevents threshold of 0 in truly silent rooms.
_MIN_FLOOR = 50.0


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
        self._speech_chunks_required = config.get("vad_speech_chunks_required", 3)
        self._adaptive = config.get("vad_adaptive", True)
        self._calibration_chunks = config.get("vad_calibration_chunks", 5)
        self._adaptive_multiplier = config.get("vad_adaptive_multiplier", 1.5)
        self.last_speech_detected = False
        self.last_ambient_rms: float | None = None

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

        When adaptive mode is enabled, the first few chunks are used to
        measure ambient noise and set the silence threshold dynamically.

        Returns:
            Concatenated PCM bytes from the recording.
        """
        chunks: list[bytes] = []
        start = time.monotonic()
        silence_start: float | None = None
        speech_chunks = 0
        speech_started = self._speech_chunks_required <= 0

        # Adaptive calibration state
        calibrating = self._adaptive
        calibration_energies: list[float] = []
        effective_threshold = self._silence_threshold

        try:
            for chunk in stream:
                elapsed = time.monotonic() - start
                chunks.append(chunk)

                # Enforce max duration (unconditional safety net)
                if elapsed >= self._max_duration:
                    log.info("VAD: max duration reached (%.1fs)", elapsed)
                    break

                energy = self.rms(chunk)

                # --- Adaptive calibration phase ---
                if calibrating:
                    calibration_energies.append(energy)
                    if len(calibration_energies) >= self._calibration_chunks:
                        ambient = statistics.median(calibration_energies)
                        effective_threshold = max(
                            ambient * self._adaptive_multiplier, _MIN_FLOOR
                        )
                        self.last_ambient_rms = ambient
                        calibrating = False
                        log.info(
                            "VAD: adaptive threshold=%.0f (ambient=%.0f, multiplier=%.1f)",
                            effective_threshold, ambient, self._adaptive_multiplier,
                        )
                    continue  # skip speech/silence logic during calibration

                if energy >= effective_threshold:
                    speech_chunks += 1
                    if not speech_started and speech_chunks >= self._speech_chunks_required:
                        speech_started = True
                        log.debug("VAD: speech started (%d chunks)", speech_chunks)
                    silence_start = None
                else:
                    # Only allow silence-triggered stop once speech has started
                    if speech_started:
                        if silence_start is None:
                            silence_start = time.monotonic()
                        silence_elapsed = time.monotonic() - silence_start
                        past_silence = silence_elapsed >= self._silence_duration
                        past_min = elapsed >= self._min_duration
                        if past_silence and past_min:
                            log.info(
                                "VAD: silence detected after %.1fs (silence=%.1fs)",
                                elapsed, silence_elapsed,
                            )
                            break
        finally:
            stream.close()

        self.last_speech_detected = speech_started
        total = time.monotonic() - start
        log.info("VAD: recorded %.1fs (%d chunks, speech=%s)", total, len(chunks), speech_started)
        return b"".join(chunks)
