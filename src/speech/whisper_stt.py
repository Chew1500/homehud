"""Whisper STT backend for production use.

Uses faster-whisper for local speech-to-text transcription.
Optimized for Raspberry Pi 5 with int8 quantization.
"""

import logging

from speech.base import BaseSTT

log = logging.getLogger(__name__)


class WhisperSTT(BaseSTT):
    """Speech-to-text using a local Whisper model via faster-whisper."""

    def __init__(self, config: dict):
        super().__init__(config)

        try:
            from faster_whisper import WhisperModel
        except ImportError:
            raise ImportError(
                "faster-whisper is required for WhisperSTT. "
                "Install with: pip install faster-whisper"
            )

        model_name = config.get("stt_whisper_model", "base.en")
        self._prompt = config.get("stt_whisper_prompt", "")
        self._hotwords = config.get("stt_whisper_hotwords", "")
        log.info(f"Loading Whisper model: {model_name}")
        self._model = WhisperModel(model_name, device="cpu", compute_type="int8")

    def transcribe(self, audio: bytes) -> str:
        """Transcribe raw PCM audio bytes using Whisper.

        Converts int16 PCM bytes to float32 numpy array, then runs Whisper.
        """
        import numpy as np

        # Convert PCM int16 bytes to float32 array normalized to [-1.0, 1.0]
        audio_array = np.frombuffer(audio, dtype=np.int16).astype(np.float32) / 32768.0

        log.info(f"Transcribing {len(audio_array)} samples with Whisper")
        segments, _info = self._model.transcribe(
            audio_array,
            beam_size=5,
            language="en",
            initial_prompt=self._prompt or None,
            hotwords=self._hotwords or None,
        )
        text = " ".join(seg.text.strip() for seg in segments).strip()
        log.info(f"Whisper transcription: {text!r}")
        return text
