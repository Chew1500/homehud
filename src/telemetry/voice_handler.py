"""Browser voice handler: accepts PCM audio, returns TTS audio via the
existing voice pipeline components (STT → IntentRouter → TTS)."""

from __future__ import annotations

import logging
import struct
import threading
import types

from speech.base import BaseSTT, TranscriptionResult
from speech.base_tts import BaseTTS
from telemetry.models import LLMCallInfo, Session

log = logging.getLogger("home-hud.telemetry.voice")


def _pcm_to_wav(
    pcm: bytes, sample_rate: int = 16000, channels: int = 1, bits: int = 16,
) -> bytes:
    """Prepend a 44-byte WAV header to raw PCM data (int16 LE)."""
    data_size = len(pcm)
    byte_rate = sample_rate * channels * bits // 8
    block_align = channels * bits // 8
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        36 + data_size,
        b"WAVE",
        b"fmt ",
        16,
        1,
        channels,
        sample_rate,
        byte_rate,
        block_align,
        bits,
        b"data",
        data_size,
    )
    return header + pcm


class BrowserVoiceHandler:
    """Handles voice requests from the browser.

    Reuses the same STT, IntentRouter, and TTS instances as the hardware
    voice pipeline.  A shared lock serialises access to the router to
    prevent concurrent conversation-state corruption.
    """

    def __init__(
        self,
        stt: BaseSTT,
        router: object,  # IntentRouter
        tts: BaseTTS,
        telemetry_store: object | None = None,
        voice_lock: threading.Lock | None = None,
    ):
        self._stt = stt
        self._router = router
        self._tts = tts
        self._telemetry_store = telemetry_store
        self._lock = voice_lock or threading.Lock()

    @property
    def voice_lock(self) -> threading.Lock:
        return self._lock

    def handle_voice_request(
        self, pcm_bytes: bytes, user_id: str = "browser",
    ) -> tuple[bytes, dict]:
        """Process a voice request end-to-end.

        Args:
            pcm_bytes: Raw PCM int16, 16 kHz mono audio.
            user_id: Identifier for the requesting user (for telemetry).

        Returns:
            (wav_bytes, metadata_dict) where metadata contains transcription,
            response text, and timing information.
        """
        session = Session(wake_model="browser")
        exchange = session.create_exchange()

        metadata: dict = {"user_id": user_id}

        with self._lock:
            # --- STT phase ---
            exchange.start_phase("stt")
            result = self._stt.transcribe_with_confidence(pcm_bytes)
            if not isinstance(result, TranscriptionResult):
                result = TranscriptionResult(text=str(result) if result else "")
            exchange.end_phase("stt")
            exchange.transcription = result.text
            exchange.stt_no_speech_prob = result.no_speech_prob
            exchange.stt_avg_logprob = result.avg_logprob

            text = result.text
            metadata["transcription"] = text or ""
            metadata["stt_no_speech_prob"] = result.no_speech_prob
            metadata["stt_avg_logprob"] = result.avg_logprob

            if not text or not text.strip():
                metadata["response_text"] = ""
                metadata["error"] = "empty_transcription"
                self._persist(session)
                return _pcm_to_wav(b""), metadata

            # --- Routing phase ---
            exchange.start_phase("routing")
            response = self._router.route(text)

            # Consume generator if streaming
            if isinstance(response, types.GeneratorType):
                response = " ".join(response)

            exchange.end_phase("routing")

            # Capture routing metadata
            if hasattr(self._router, "_last_route_info") and self._router._last_route_info:
                exchange.routing_path = self._router._last_route_info.get("path")
                exchange.matched_feature = self._router._last_route_info.get("matched_feature")
                exchange.feature_action = self._router._last_route_info.get("feature_action")

            exchange.response_text = response
            metadata["response_text"] = response or ""

            # Capture LLM call info
            if hasattr(self._router, "_last_llm_calls"):
                for call_dict in self._router._last_llm_calls:
                    exchange.llm_calls.append(LLMCallInfo(
                        call_type=call_dict.get("call_type", ""),
                        model=call_dict.get("model"),
                        system_prompt=call_dict.get("system_prompt"),
                        user_message=call_dict.get("user_message"),
                        response_text=call_dict.get("response_text"),
                        input_tokens=call_dict.get("input_tokens"),
                        output_tokens=call_dict.get("output_tokens"),
                        stop_reason=call_dict.get("stop_reason"),
                        duration_ms=call_dict.get("duration_ms"),
                        error=call_dict.get("error"),
                    ))

            # --- TTS phase ---
            exchange.start_phase("tts")
            tts_pcm = self._tts.synthesize(response) if response else b""
            exchange.end_phase("tts")

        # Build WAV outside the lock (pure data transform)
        wav_bytes = _pcm_to_wav(tts_pcm) if tts_pcm else _pcm_to_wav(b"")

        session.finish()
        self._persist(session)

        return wav_bytes, metadata

    def _persist(self, session: Session) -> None:
        """Save session telemetry if a store is configured."""
        if self._telemetry_store is not None:
            try:
                self._telemetry_store.save_session(session)
            except Exception:
                log.exception("Failed to persist browser voice session")
