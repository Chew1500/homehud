"""Kokoro TTS backend using ONNX Runtime for fast inference on ARM."""

import asyncio
import logging
import os
import queue
import shutil
import threading
from collections.abc import Generator

import numpy as np

from speech.base_tts import BaseTTS
from utils.audio import resample_to_16k

log = logging.getLogger("home-hud.tts.kokoro")

_KOKORO_NATIVE_RATE = 24000

# Map short lang codes to full codes accepted by kokoro-onnx
_LANG_ALIASES = {
    "a": "en-us",
    "b": "en-gb",
}


class KokoroTTS(BaseTTS):
    """Text-to-speech using Kokoro via ONNX Runtime (INT8 quantized).

    Requires the ``kokoro-onnx`` package and ``espeak-ng`` system dependency.
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
            import onnxruntime
            from kokoro_onnx import Kokoro
        except ImportError:
            raise ImportError(
                "kokoro-onnx is required for KokoroTTS. "
                "Install it with: pip install kokoro-onnx"
            )

        self._voice = config.get("tts_kokoro_voice", "af_heart")
        self._speed = config.get("tts_kokoro_speed", 1.0)
        lang = config.get("tts_kokoro_lang", "a")
        self._lang = _LANG_ALIASES.get(lang, lang)

        model_path = config.get("tts_kokoro_model", "models/kokoro-v1.0.int8.onnx")
        voices_path = config.get("tts_kokoro_voices", "models/voices-v1.0.bin")

        # Configure ONNX session for optimal Pi 5 performance
        session_opts = onnxruntime.SessionOptions()
        session_opts.intra_op_num_threads = os.cpu_count() or 4
        session_opts.graph_optimization_level = (
            onnxruntime.GraphOptimizationLevel.ORT_ENABLE_ALL
        )

        log.info(
            "Loading Kokoro ONNX model (model=%s, voices=%s, threads=%d)",
            model_path,
            voices_path,
            session_opts.intra_op_num_threads,
        )
        session = onnxruntime.InferenceSession(model_path, session_opts)
        self._kokoro = Kokoro.from_session(session, voices_path)
        log.info(
            "Kokoro ready (lang=%s, voice=%s, native rate=%dHz)",
            self._lang,
            self._voice,
            _KOKORO_NATIVE_RATE,
        )

    def synthesize(self, text: str) -> bytes:
        """Synthesize text to PCM int16 @ 16kHz mono."""
        if not text or not text.strip():
            return b"\x00\x00" * 1600

        samples, sample_rate = self._kokoro.create(
            text, voice=self._voice, speed=self._speed, lang=self._lang
        )

        if samples is None or len(samples) == 0:
            return b"\x00\x00" * 1600

        # Kokoro outputs float32 samples in [-1, 1]
        audio_int16 = (samples * 32767).clip(-32768, 32767).astype(np.int16)
        raw = audio_int16.tobytes()

        return resample_to_16k(raw, sample_rate)

    def synthesize_stream(self, text: str) -> Generator[bytes, None, None]:
        """Yield PCM chunks as Kokoro synthesizes each sentence/phrase.

        Uses a queue-based async-to-sync bridge so that audio chunks are
        yielded to the caller (and played back) as soon as each one is
        synthesized, rather than waiting for the entire text to finish.
        """
        if not text or not text.strip():
            yield b"\x00\x00" * 1600
            return

        chunk_queue: queue.Queue = queue.Queue()
        sentinel = object()

        def _producer():
            async def _stream():
                async for samples, sample_rate in self._kokoro.create_stream(
                    text, voice=self._voice, speed=self._speed, lang=self._lang
                ):
                    chunk_queue.put((samples, sample_rate))
                chunk_queue.put(sentinel)

            try:
                asyncio.run(_stream())
            except Exception as exc:
                chunk_queue.put(exc)

        thread = threading.Thread(target=_producer, daemon=True)
        thread.start()

        yielded = False
        while True:
            item = chunk_queue.get()
            if item is sentinel:
                break
            if isinstance(item, Exception):
                raise item
            samples, sample_rate = item
            if samples is not None and len(samples) > 0:
                audio_int16 = (samples * 32767).clip(-32768, 32767).astype(np.int16)
                raw = audio_int16.tobytes()
                yield resample_to_16k(raw, sample_rate)
                yielded = True

        if not yielded:
            yield b"\x00\x00" * 1600

    def close(self) -> None:
        """Release resources."""
        self._kokoro = None
