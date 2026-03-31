"""ElevenLabs cloud STT backend via the elevenlabs Python SDK."""

import io
import logging
import struct

from speech.base import BaseSTT, TranscriptionResult

log = logging.getLogger("home-hud.stt.elevenlabs")


class ElevenLabsSTT(BaseSTT):
    """Speech-to-text using ElevenLabs cloud API.

    Accepts raw PCM int16 @ 16kHz mono, wraps in a WAV header,
    and sends to the ElevenLabs speech-to-text endpoint.
    """

    def __init__(self, config: dict):
        super().__init__(config)

        api_key = config.get("elevenlabs_api_key")
        if not api_key:
            raise ValueError(
                "ELEVENLABS_API_KEY is required for elevenlabs STT mode."
            )

        try:
            from elevenlabs.client import ElevenLabs
        except ImportError:
            raise ImportError(
                "elevenlabs is required for ElevenLabsSTT. "
                "Install it with: pip install elevenlabs"
            )

        self._client = ElevenLabs(api_key=api_key)
        self._model = config.get("stt_elevenlabs_model", "scribe_v1")

        log.info("ElevenLabs STT ready (model=%s)", self._model)

    def transcribe(self, audio: bytes) -> str:
        """Transcribe raw PCM audio bytes via ElevenLabs API."""
        return self.transcribe_with_confidence(audio).text

    def transcribe_with_confidence(self, audio: bytes) -> TranscriptionResult:
        """Transcribe with confidence metrics (always high for cloud API)."""
        wav_data = _add_wav_header(audio)
        wav_file = io.BytesIO(wav_data)
        wav_file.name = "audio.wav"

        log.info("Sending %d bytes to ElevenLabs STT (model=%s)", len(wav_data), self._model)
        result = self._client.speech_to_text.convert(
            file=wav_file,
            model_id=self._model,
        )

        text = result.text.strip()
        log.info("ElevenLabs transcription: %r", text)

        return TranscriptionResult(
            text=text,
            no_speech_prob=0.0,
            avg_logprob=0.0,
        )


def _add_wav_header(
    pcm: bytes, sample_rate: int = 16000, bits: int = 16, channels: int = 1,
) -> bytes:
    """Wrap raw PCM bytes in a minimal WAV (RIFF) header.

    Parameters match the project's standard audio format:
    16kHz, 16-bit signed int, mono.
    """
    data_size = len(pcm)
    byte_rate = sample_rate * channels * bits // 8
    block_align = channels * bits // 8

    header = struct.pack(
        "<4sI4s"     # RIFF chunk: "RIFF", file size, "WAVE"
        "4sIHHIIHH"  # fmt sub-chunk
        "4sI",       # data sub-chunk header
        b"RIFF",
        36 + data_size,  # file size minus 8
        b"WAVE",
        b"fmt ",
        16,              # fmt chunk size (PCM)
        1,               # audio format (1 = PCM)
        channels,
        sample_rate,
        byte_rate,
        block_align,
        bits,
        b"data",
        data_size,
    )
    return header + pcm
