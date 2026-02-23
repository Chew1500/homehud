"""Audio abstraction layer.

Provides a unified interface for audio I/O on either:
- MockAudio: file-based recording/playback (for development)
- HardwareAudio: real mic/speaker via sounddevice (for production)
"""

from audio.base import BaseAudio
from audio.mock_audio import MockAudio


def get_audio(config: dict) -> BaseAudio:
    """Factory: return the appropriate audio backend based on config."""
    mode = config.get("audio_mode", "mock")

    if mode == "hardware":
        from audio.hardware_audio import HardwareAudio
        return HardwareAudio(config)
    else:
        return MockAudio(config)
