"""Voice pipeline: wake word → record → transcribe → route → respond."""

from __future__ import annotations

import logging
import threading
import time

from audio.base import BaseAudio
from intent.router import IntentRouter
from speech.base import BaseSTT
from speech.base_tts import BaseTTS
from telemetry.models import LLMCallInfo, Session
from utils.vad import VoiceActivityDetector
from wake.base import BaseWakeWord

log = logging.getLogger("home-hud.voice")


def start_voice_pipeline(
    audio: BaseAudio,
    stt: BaseSTT,
    wake: BaseWakeWord,
    router: IntentRouter,
    tts: BaseTTS,
    config: dict,
    running: threading.Event,
    repeat_feature=None,
    wake_prompts=None,
    telemetry_store=None,
) -> threading.Thread:
    """Start the voice pipeline in a daemon thread.

    Streams audio chunks, waits for wake word detection, then records
    and transcribes a command. Repeats until running is cleared.

    Returns the started Thread so callers can join() if needed.
    """
    record_duration = config.get("voice_record_duration", 5)

    wake_feedback = config.get("voice_wake_feedback", True) and wake_prompts is not None

    # VAD setup
    vad_enabled = config.get("voice_vad_enabled", True)
    vad = VoiceActivityDetector(config) if vad_enabled else None

    # Barge-in setup
    bargein_enabled = config.get("voice_bargein_enabled", True)

    wake_model = config.get("wake_model")

    # Number of audio chunks to skip before monitoring for barge-in.
    # Prevents speaker-to-mic feedback from triggering a false wake word
    # immediately after playback starts. At 80ms/chunk, 15 chunks = 1.2s.
    BARGEIN_DEBOUNCE_CHUNKS = 15

    def _handle_command(session=None, is_follow_up=False):
        """Record, transcribe, route, and respond to a single command.

        Returns True if barge-in was detected (caller should loop).
        """
        exchange = None
        if session is not None:
            try:
                exchange = session.create_exchange(is_follow_up=is_follow_up)
                exchange.used_vad = vad is not None
            except Exception:
                log.exception("Telemetry exchange creation failed (non-fatal)")

        # --- Recording phase ---
        if exchange is not None:
            try:
                exchange.start_phase("recording")
            except Exception:
                pass
        if vad is not None:
            pcm = vad.record_until_silence(audio.stream())
        else:
            pcm = audio.record(record_duration)
        if exchange is not None:
            try:
                exchange.end_phase("recording")
            except Exception:
                pass

        # --- STT phase ---
        if exchange is not None:
            try:
                exchange.start_phase("stt")
            except Exception:
                pass
        text = stt.transcribe(pcm)
        if exchange is not None:
            try:
                exchange.end_phase("stt")
                exchange.transcription = text
            except Exception:
                pass

        log.info("Transcribed: %r", text)
        if not text or not text.strip():
            log.info("Empty transcription, skipping")
            return False
        try:
            # --- Routing phase ---
            if exchange is not None:
                try:
                    exchange.start_phase("routing")
                except Exception:
                    pass
            response = router.route(text)
            if exchange is not None:
                try:
                    exchange.end_phase("routing")
                    exchange.response_text = response
                    # Collect routing metadata
                    if router._last_route_info:
                        exchange.routing_path = router._last_route_info.get("path")
                        exchange.matched_feature = router._last_route_info.get("matched_feature")
                        exchange.feature_action = router._last_route_info.get("feature_action")
                    # Collect LLM call info
                    for call_dict in router._last_llm_calls:
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
                except Exception:
                    pass

            log.info("Response: %r", response)
            if repeat_feature is not None:
                repeat_feature.record(text, response)
            try:
                if bargein_enabled:
                    # --- TTS phase ---
                    if exchange is not None:
                        try:
                            exchange.start_phase("tts")
                        except Exception:
                            pass
                    stream_iter = tts.synthesize_stream(response)
                    if exchange is not None:
                        try:
                            exchange.end_phase("tts")
                        except Exception:
                            pass

                    # --- Playback phase ---
                    if exchange is not None:
                        try:
                            exchange.start_phase("playback")
                        except Exception:
                            pass
                    audio.play_streamed(stream_iter)
                    # Reset wake detector state to clear any residual
                    # audio patterns from the tone or prior detection.
                    wake.reset()
                    # Monitor for wake word during playback.
                    # Skip initial chunks to avoid speaker-to-mic feedback.
                    bargein = False
                    chunks_heard = 0
                    stream = audio.stream()
                    try:
                        for chunk in stream:
                            if not audio.is_playing():
                                break
                            chunks_heard += 1
                            if chunks_heard <= BARGEIN_DEBOUNCE_CHUNKS:
                                continue
                            if wake.detect(chunk):
                                log.info("Barge-in detected, stopping playback")
                                audio.stop_playback()
                                wake.reset()
                                bargein = True
                                break
                    finally:
                        stream.close()
                    if exchange is not None:
                        try:
                            exchange.end_phase("playback")
                            exchange.had_bargein = bargein
                        except Exception:
                            pass
                    if not bargein:
                        wake.reset()
                    follow_up = router.expects_follow_up
                    if not bargein and follow_up:
                        log.info("Follow-up mode: continuing command loop")
                    return bargein or follow_up
                else:
                    # --- TTS phase ---
                    if exchange is not None:
                        try:
                            exchange.start_phase("tts")
                        except Exception:
                            pass
                    speech = tts.synthesize(response)
                    if exchange is not None:
                        try:
                            exchange.end_phase("tts")
                        except Exception:
                            pass

                    # --- Playback phase ---
                    if exchange is not None:
                        try:
                            exchange.start_phase("playback")
                        except Exception:
                            pass
                    audio.play(speech)
                    if exchange is not None:
                        try:
                            exchange.end_phase("playback")
                        except Exception:
                            pass

                    follow_up = router.expects_follow_up
                    if follow_up:
                        log.info("Follow-up mode: continuing command loop")
                    return follow_up
            except Exception:
                log.exception("TTS error (non-fatal)")
                if exchange is not None:
                    try:
                        exchange.error = "TTS error"
                    except Exception:
                        pass
        except Exception:
            log.exception("Routing error (non-fatal)")
            if exchange is not None:
                try:
                    exchange.error = "Routing error"
                except Exception:
                    pass
        return False

    def loop():
        log.info("Voice pipeline started (wake-word triggered, record=%ds)", record_duration)
        consecutive_errors = 0
        max_errors = 3

        while running.is_set():
            try:
                wake_detected = False
                for chunk in audio.stream():
                    consecutive_errors = 0
                    if not running.is_set():
                        break
                    if wake.detect(chunk):
                        wake_detected = True
                        break  # stream's finally block frees the mic device
                if wake_detected:
                    # Create telemetry session
                    session = None
                    if telemetry_store is not None:
                        try:
                            session = Session(wake_model=wake_model)
                        except Exception:
                            log.exception("Telemetry session creation failed (non-fatal)")

                    if wake_feedback:
                        audio.play(wake_prompts.pick())
                    # Loop handles barge-in and follow-up: _handle_command
                    # returns True when wake word interrupts playback or
                    # when the router expects a follow-up response.
                    MAX_FOLLOW_UPS = 10
                    follow_ups = 0
                    while _handle_command(session=session, is_follow_up=follow_ups > 0):
                        follow_ups += 1
                        if follow_ups >= MAX_FOLLOW_UPS:
                            log.warning("Max follow-up iterations reached, exiting command loop")
                            break
                        if wake_feedback and not router.expects_follow_up:
                            audio.play(wake_prompts.pick())
                    wake.reset()

                    # Persist telemetry
                    if session is not None and telemetry_store is not None:
                        try:
                            session.finish()
                            telemetry_store.save_session(session)
                        except Exception:
                            log.exception("Telemetry save failed (non-fatal)")
            except Exception:
                consecutive_errors += 1
                if consecutive_errors >= max_errors:
                    log.exception(
                        "Voice pipeline giving up after %d consecutive errors",
                        consecutive_errors,
                    )
                    break
                backoff = min(2 ** consecutive_errors, 30)
                log.exception(
                    "Voice pipeline error (%d/%d, retrying in %ds)",
                    consecutive_errors, max_errors, backoff,
                )
                time.sleep(backoff)

        log.info("Voice pipeline stopped.")

    thread = threading.Thread(target=loop, name="voice-pipeline", daemon=True)
    thread.start()
    return thread
