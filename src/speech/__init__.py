"""Speech abstraction layer (STT and TTS).

Provides unified interfaces for:
- STT: MockSTT (dev) / WhisperSTT (production)
- TTS: MockTTS (dev) / PiperTTS / KokoroTTS (production)
"""

from speech.base import BaseSTT
from speech.base_tts import BaseTTS
from speech.mock_stt import MockSTT
from speech.mock_tts import MockTTS


def get_stt(config: dict) -> BaseSTT:
    """Factory: return the appropriate STT backend based on config."""
    mode = config.get("stt_mode", "mock")

    if mode == "whisper":
        from speech.whisper_stt import WhisperSTT
        return WhisperSTT(config)
    else:
        return MockSTT(config)


def get_tts(config: dict) -> BaseTTS:
    """Factory: return the appropriate TTS backend based on config."""
    mode = config.get("tts_mode", "mock")

    if mode == "piper":
        from speech.piper_tts import PiperTTS
        return PiperTTS(config)
    elif mode == "kokoro":
        from speech.kokoro_tts import KokoroTTS
        return KokoroTTS(config)
    else:
        return MockTTS(config)
