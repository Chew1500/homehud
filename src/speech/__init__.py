"""Speech-to-text abstraction layer.

Provides a unified interface for STT on either:
- MockSTT: returns canned responses (for development)
- WhisperSTT: local Whisper model (for production)
"""

from speech.base import BaseSTT
from speech.mock_stt import MockSTT


def get_stt(config: dict) -> BaseSTT:
    """Factory: return the appropriate STT backend based on config."""
    mode = config.get("stt_mode", "mock")

    if mode == "whisper":
        from speech.whisper_stt import WhisperSTT
        return WhisperSTT(config)
    else:
        return MockSTT(config)
