"""ElevenLabs cloud TTS backend via the elevenlabs Python SDK."""

import logging
from collections.abc import Generator

from speech.base_tts import BaseTTS

log = logging.getLogger("home-hud.tts.elevenlabs")


class ElevenLabsTTS(BaseTTS):
    """Text-to-speech using ElevenLabs cloud API.

    Uses the Flash v2.5 model (~75ms synthesis latency) and requests
    PCM S16LE at 16kHz directly — no resampling needed.
    """

    def __init__(self, config: dict):
        super().__init__(config)

        api_key = config.get("elevenlabs_api_key")
        if not api_key:
            raise ValueError(
                "ELEVENLABS_API_KEY is required for elevenlabs TTS mode."
            )

        try:
            from elevenlabs.client import ElevenLabs
        except ImportError:
            raise ImportError(
                "elevenlabs is required for ElevenLabsTTS. "
                "Install it with: pip install elevenlabs"
            )

        self._client = ElevenLabs(api_key=api_key)
        self._voice = config.get("tts_elevenlabs_voice", "JBFqnCBsd6RMkjVDRZzb")
        self._model = config.get("tts_elevenlabs_model", "eleven_flash_v2_5")
        self._speed = config.get("tts_elevenlabs_speed", 1.0)

        log.info(
            "ElevenLabs TTS ready (model=%s, voice=%s, speed=%.1f)",
            self._model,
            self._voice,
            self._speed,
        )

    def synthesize(self, text: str) -> bytes:
        """Synthesize text to PCM int16 @ 16kHz mono via ElevenLabs API."""
        if not text or not text.strip():
            return b"\x00\x00" * 1600

        audio_iter = self._client.text_to_speech.convert(
            text=text,
            voice_id=self._voice,
            model_id=self._model,
            output_format="pcm_16000",
        )
        return b"".join(audio_iter)

    def synthesize_stream(self, text: str) -> Generator[bytes, None, None]:
        """Yield PCM chunks as they arrive from the ElevenLabs streaming API."""
        if not text or not text.strip():
            yield b"\x00\x00" * 1600
            return

        stream = self._client.text_to_speech.stream(
            text=text,
            voice_id=self._voice,
            model_id=self._model,
            output_format="pcm_16000",
        )
        for chunk in stream:
            if chunk:
                yield chunk
