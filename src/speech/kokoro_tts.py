"""Kokoro TTS backend for natural-sounding speech synthesis."""

import logging
import shutil

import numpy as np

from speech.base_tts import BaseTTS
from utils.audio import resample_to_16k

log = logging.getLogger("home-hud.tts.kokoro")

_KOKORO_NATIVE_RATE = 24000


class KokoroTTS(BaseTTS):
    """Text-to-speech using Kokoro (StyleTTS 2 + ISTFTNet).

    Requires the ``kokoro`` package and ``espeak-ng`` system dependency.
    Produces PCM int16 @ 16kHz mono (resampled from Kokoro's native 24kHz).
    """

    def __init__(self, config: dict):
        super().__init__(config)

        # Pre-flight: espeak-ng must be installed (phonemizer backend)
        if not shutil.which("espeak-ng"):
            raise RuntimeError(
                "espeak-ng is required for KokoroTTS but was not found. "
                "Install it with: sudo apt install espeak-ng"
            )

        try:
            from kokoro import KPipeline
        except ImportError:
            raise ImportError(
                "kokoro is required for KokoroTTS. "
                "Install it with: pip install kokoro"
            )

        self._voice = config.get("tts_kokoro_voice", "af_heart")
        self._speed = config.get("tts_kokoro_speed", 1.0)
        lang = config.get("tts_kokoro_lang", "a")

        log.info("Loading Kokoro pipeline (lang=%s, voice=%s)", lang, self._voice)
        self._pipeline = KPipeline(lang_code=lang)
        log.info("Kokoro ready (native rate=%dHz)", _KOKORO_NATIVE_RATE)

    def synthesize(self, text: str) -> bytes:
        """Synthesize text to PCM int16 @ 16kHz mono."""
        if not text or not text.strip():
            return b"\x00\x00" * 1600

        chunks = []
        for result in self._pipeline(
            text, voice=self._voice, speed=self._speed
        ):
            if result.audio is not None:
                chunks.append(result.audio.numpy())

        if not chunks:
            return b"\x00\x00" * 1600

        # Kokoro outputs float32 samples in [-1, 1] at 24kHz
        audio_f32 = np.concatenate(chunks)
        audio_int16 = (audio_f32 * 32767).clip(-32768, 32767).astype(np.int16)
        raw = audio_int16.tobytes()

        return resample_to_16k(raw, _KOKORO_NATIVE_RATE)

    def close(self) -> None:
        """Release pipeline resources."""
        self._pipeline = None
