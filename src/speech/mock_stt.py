"""Mock STT backend for local development.

Returns a configurable canned response, ignoring actual audio input.
"""

import logging

from speech.base import BaseSTT

log = logging.getLogger(__name__)


class MockSTT(BaseSTT):
    """Fake STT that returns a fixed string for development."""

    def __init__(self, config: dict):
        super().__init__(config)
        self._response = config.get("stt_mock_response", "hello world")

    def transcribe(self, audio: bytes) -> str:
        """Return the configured canned response, ignoring audio."""
        log.info(f"Mock transcribe called with {len(audio)} bytes of audio")
        return self._response
