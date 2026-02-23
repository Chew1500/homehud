"""Mock wake word detector for local development.

Triggers after a configurable number of audio chunks (no actual
audio analysis). Useful for testing the pipeline without a real
wake word model.
"""

import logging

from wake.base import BaseWakeWord

log = logging.getLogger(__name__)


class MockWakeWord(BaseWakeWord):
    """Counter-based wake word detector for development."""

    def __init__(self, config: dict):
        self._trigger_after = config.get("wake_mock_trigger_after", 62)
        self._count = 0
        log.info("MockWakeWord initialized (trigger after %d chunks)", self._trigger_after)

    def detect(self, audio_chunk: bytes) -> bool:
        self._count += 1
        if self._count >= self._trigger_after:
            log.info("Mock wake word triggered after %d chunks", self._count)
            return True
        return False

    def reset(self) -> None:
        self._count = 0
