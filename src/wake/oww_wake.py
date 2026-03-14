"""Wake word detection using openWakeWord.

Only used on the Raspberry Pi — openwakeword is not required for local dev.
Expects 16kHz mono int16 PCM in 1280-sample chunks (80ms).
"""

import logging
import time

from wake.base import BaseWakeWord

log = logging.getLogger(__name__)


class OWWWakeWord(BaseWakeWord):
    """Real wake word detection via openWakeWord."""

    def __init__(self, config: dict):
        import numpy as np
        from openwakeword.model import Model

        self._np = np
        self._wake_model = config.get("wake_model", "hey_jarvis")
        self._threshold = config.get("wake_threshold", 0.6)
        self._confirm_frames = config.get("wake_confirm_frames", 3)
        self._cooldown = config.get("wake_cooldown", 2.0)
        self._model = Model(
            wakeword_models=[self._wake_model],
            inference_framework="onnx",
        )
        self._last_detection_time: float = 0.0
        log.info(
            "OWWWakeWord initialized: model=%s, threshold=%.2f, "
            "confirm_frames=%d, cooldown=%.1fs",
            self._wake_model,
            self._threshold,
            self._confirm_frames,
            self._cooldown,
        )

    def detect(self, audio_chunk: bytes) -> bool:
        audio = self._np.frombuffer(audio_chunk, dtype=self._np.int16)
        self._model.predict(audio)
        scores = list(self._model.prediction_buffer[self._wake_model])
        score = scores[-1] if scores else 0.0

        # Debug logging for scores approaching threshold
        if score > self._threshold * 0.5:
            log.debug(
                "Wake score warm: %.3f (threshold=%.2f)", score, self._threshold
            )

        if score <= self._threshold:
            return False

        # Multi-frame confirmation: require N consecutive frames above threshold
        if len(scores) < self._confirm_frames:
            return False
        recent = scores[-self._confirm_frames :]
        if not all(s > self._threshold for s in recent):
            return False

        # Cooldown: suppress rapid re-triggers
        now = time.monotonic()
        if now - self._last_detection_time < self._cooldown:
            log.debug(
                "Wake detection suppressed by cooldown (%.1fs remaining)",
                self._cooldown - (now - self._last_detection_time),
            )
            return False

        self._last_detection_time = now
        log.info(
            "Wake word detected (score=%.3f, confirmed %d frames)",
            score,
            self._confirm_frames,
        )
        return True

    def reset(self) -> None:
        self._model.reset()

    def close(self) -> None:
        log.info("OWWWakeWord closed.")
