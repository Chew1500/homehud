"""Speech abstraction layer (STT and TTS).

Provides unified interfaces for:
- STT: MockSTT (dev) / WhisperSTT (production)
- TTS: MockTTS (dev) / KokoroTTS (production)
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
    elif mode == "elevenlabs":
        from speech.elevenlabs_stt import ElevenLabsSTT
        return ElevenLabsSTT(config)
    else:
        return MockSTT(config)


def get_tts(config: dict) -> BaseTTS:
    """Factory: return the appropriate TTS backend based on config."""
    mode = config.get("tts_mode", "mock")

    if mode == "kokoro":
        from speech.kokoro_tts import KokoroTTS
        inner = KokoroTTS(config)
    elif mode == "elevenlabs":
        from speech.elevenlabs_tts import ElevenLabsTTS
        inner = ElevenLabsTTS(config)
    else:
        inner = MockTTS(config)

    if config.get("tts_cache_enabled", False):
        from speech.cached_tts import CachedTTS
        return CachedTTS(inner, config)

    return inner
