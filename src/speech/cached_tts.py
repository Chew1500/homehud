"""Disk-caching TTS wrapper — saves synthesized audio to avoid repeated API calls."""

import hashlib
import logging
import threading
from collections.abc import Generator
from pathlib import Path

from speech.base_tts import BaseTTS

logger = logging.getLogger(__name__)


class CachedTTS(BaseTTS):
    """Decorator that wraps any BaseTTS with persistent disk caching.

    Cache key: SHA-256 of "{text_lower}|{voice}|{model}".
    Storage: raw .pcm files (int16 LE 16kHz mono — no headers needed).
    """

    def __init__(self, inner: BaseTTS, config: dict):
        super().__init__(config)
        self._inner = inner
        self._cache_dir = Path(config.get("tts_cache_dir", "data/tts_cache"))
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

        # Include voice/model in cache key so switching invalidates
        self._voice = config.get("tts_elevenlabs_voice", "") or config.get(
            "tts_kokoro_voice", ""
        )
        self._model = config.get("tts_elevenlabs_model", "") or config.get(
            "tts_kokoro_model", ""
        )
        logger.info("TTS cache enabled: %s", self._cache_dir)

    def _cache_key(self, text: str) -> str:
        raw = f"{text.strip().lower()}|{self._voice}|{self._model}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def _cache_path(self, text: str) -> Path:
        return self._cache_dir / f"{self._cache_key(text)}.pcm"

    def synthesize(self, text: str) -> bytes:
        if not text or not text.strip():
            return self._inner.synthesize(text)

        path = self._cache_path(text)

        with self._lock:
            if path.exists():
                logger.debug("TTS cache hit: %s", text[:40])
                return path.read_bytes()

        # Call inner TTS outside the lock (no blocking during API calls)
        pcm = self._inner.synthesize(text)

        with self._lock:
            path.write_bytes(pcm)
            logger.debug("TTS cache write: %s (%d bytes)", text[:40], len(pcm))

        return pcm

    def synthesize_stream(self, text: str) -> Generator[bytes, None, None]:
        if not text or not text.strip():
            yield from self._inner.synthesize_stream(text)
            return

        path = self._cache_path(text)

        with self._lock:
            if path.exists():
                logger.debug("TTS stream cache hit: %s", text[:40])
                yield path.read_bytes()
                return

        # Stream from inner, accumulate, then write to disk
        accumulated = bytearray()
        for chunk in self._inner.synthesize_stream(text):
            accumulated.extend(chunk)
            yield chunk

        with self._lock:
            path.write_bytes(bytes(accumulated))
            logger.debug(
                "TTS stream cache write: %s (%d bytes)", text[:40], len(accumulated)
            )

    def close(self) -> None:
        self._inner.close()
