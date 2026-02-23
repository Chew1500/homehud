"""Wake word detection using openWakeWord.

Only used on the Raspberry Pi — openwakeword is not required for local dev.
Expects 16kHz mono int16 PCM in 1280-sample chunks (80ms).
"""

import logging

from wake.base import BaseWakeWord

log = logging.getLogger(__name__)


class OWWWakeWord(BaseWakeWord):
    """Real wake word detection via openWakeWord."""

    def __init__(self, config: dict):
        import numpy as np
        from openwakeword.model import Model

        self._np = np
        self._wake_model = config.get("wake_model", "hey_jarvis")
        self._threshold = config.get("wake_threshold", 0.5)
        self._model = Model(wakeword_models=[self._wake_model])
        log.info(
            "OWWWakeWord initialized: model=%s, threshold=%.2f",
            self._wake_model,
            self._threshold,
        )

    def detect(self, audio_chunk: bytes) -> bool:
        audio = self._np.frombuffer(audio_chunk, dtype=self._np.int16)
        self._model.predict(audio)
        scores = self._model.get_prediction(self._wake_model)
        score = scores[-1] if hasattr(scores, "__len__") else scores
        if score > self._threshold:
            log.info("Wake word detected (score=%.3f)", score)
            return True
        return False

    def reset(self) -> None:
        self._model.reset()

    def close(self) -> None:
        log.info("OWWWakeWord closed.")
