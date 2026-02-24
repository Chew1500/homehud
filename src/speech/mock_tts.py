"""Mock TTS backend for local development."""

import logging

from speech.base_tts import BaseTTS

log = logging.getLogger("home-hud.tts.mock")


class MockTTS(BaseTTS):
    """Returns silence bytes of configurable duration."""

    def __init__(self, config: dict):
        super().__init__(config)
        self._duration = config.get("tts_mock_duration", 2.0)

    def synthesize(self, text: str) -> bytes:
        """Return silence PCM bytes. Logs input text for debugging."""
        log.debug("MockTTS synthesize: %r (%.1fs silence)", text, self._duration)
        # 16kHz mono, 2 bytes per sample
        num_samples = int(16000 * self._duration)
        return b"\x00\x00" * num_samples
