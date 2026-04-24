"""Voice pipeline: wake word → record → transcribe → route → respond."""

from __future__ import annotations

import logging
import threading
import time
import types

from audio.base import AudioStreamStaleError, BaseAudio
from intent.router import IntentRouter
from notifications.presence import rms as compute_rms
from speech.base import BaseSTT, TranscriptionResult
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
    notification_manager=None,
    presence_tracker=None,
    voice_lock: threading.Lock | None = None,
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

    # STT confidence thresholds
    no_speech_threshold = config.get("stt_no_speech_threshold", 0.6)
    confidence_threshold = config.get("stt_confidence_threshold", -1.0)

    # Follow-up limits
    max_follow_ups = config.get("voice_max_follow_ups", 5)
    max_consecutive_low = config.get("voice_max_consecutive_low_confidence", 2)

    # Number of audio chunks to skip before monitoring for barge-in.
    # Prevents speaker-to-mic feedback from triggering a false wake word
    # immediately after playback starts. At 80ms/chunk, 15 chunks = 1.2s.
    BARGEIN_DEBOUNCE_CHUNKS = 15

    # Shared lock with browser voice handler (if present) to serialise
    # access to the IntentRouter which has conversation state.
    _voice_lock = voice_lock

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

        # Layer 4: VAD gate — skip STT if no speech detected during follow-up
        if is_follow_up and vad is not None and not vad.last_speech_detected:
            log.info("Follow-up VAD gate: no speech detected, skipping STT")
            if exchange is not None:
                try:
                    exchange.routing_path = "rejected_vad_no_speech"
                except Exception:
                    pass
            return False

        # --- STT phase ---
        if exchange is not None:
            try:
                exchange.start_phase("stt")
            except Exception:
                pass
        result = stt.transcribe_with_confidence(pcm)
        if not isinstance(result, TranscriptionResult):
            # Fallback for mocks that don't return TranscriptionResult
            result = TranscriptionResult(text=str(result) if result else "")
        text = result.text
        if exchange is not None:
            try:
                exchange.end_phase("stt")
                exchange.transcription = text
                exchange.stt_no_speech_prob = result.no_speech_prob
                exchange.stt_avg_logprob = result.avg_logprob
            except Exception:
                pass

        log.info("Transcribed: %r", text)
        if not text or not text.strip():
            log.info("Empty transcription, skipping")
            return False

        # Layer 0: Text-pattern noise filter (brackets, short non-Latin).
        # Runs before confidence gates so rejections record a specific reason.
        from speech.noise_filter import is_noise

        noise = is_noise(text)
        if noise.rejected:
            log.info("Rejected: noise_%s (%r)", noise.reason, text)
            if exchange is not None:
                try:
                    exchange.routing_path = f"rejected_noise_{noise.reason}"
                except Exception:
                    pass
            return False

        # Layer 1: STT confidence gate
        if result.no_speech_prob > no_speech_threshold:
            log.info(
                "Rejected: high no_speech_prob=%.3f (threshold=%.3f)",
                result.no_speech_prob, no_speech_threshold,
            )
            if exchange is not None:
                try:
                    exchange.routing_path = "rejected_no_speech"
                except Exception:
                    pass
            return False

        if result.avg_logprob < confidence_threshold:
            log.info(
                "Rejected: low avg_logprob=%.3f (threshold=%.3f)",
                result.avg_logprob, confidence_threshold,
            )
            if exchange is not None:
                try:
                    exchange.routing_path = "rejected_low_confidence"
                except Exception:
                    pass
            return False
        try:
            # Acquire shared lock to serialise with browser voice handler
            if _voice_lock is not None:
                _voice_lock.acquire()
            # --- Routing phase ---
            if exchange is not None:
                try:
                    exchange.start_phase("routing")
                except Exception:
                    pass
            response = router.route(text)
            is_streaming = isinstance(response, types.GeneratorType)

            if exchange is not None:
                try:
                    exchange.end_phase("routing")
                    # Routing metadata is available for both paths
                    if router._last_route_info:
                        exchange.routing_path = router._last_route_info.get("path")
                        exchange.matched_feature = router._last_route_info.get("matched_feature")
                        exchange.feature_action = router._last_route_info.get("feature_action")
                    if not is_streaming:
                        exchange.response_text = response
                        # LLM call info available immediately for non-streaming
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

            if is_streaming:
                # --- Streaming LLM fallback ---
                # Chain: LLM sentences → per-sentence TTS → PCM chunks.
                # Playback starts as the first sentence is synthesized.
                sentences = []

                def _chained_tts():
                    for sentence in response:
                        sentences.append(sentence)
                        yield from tts.synthesize_stream(sentence)

                try:
                    # --- TTS phase (iterator creation) ---
                    if exchange is not None:
                        try:
                            exchange.start_phase("tts")
                        except Exception:
                            pass
                    stream_iter = _chained_tts()
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

                    if bargein_enabled:
                        wake.reset()
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
                    else:
                        bargein = False
                        if exchange is not None:
                            try:
                                exchange.end_phase("playback")
                            except Exception:
                                pass

                    # Post-playback: collect telemetry from consumed generator
                    full_response = " ".join(sentences)
                    log.info("Response: %r", full_response)
                    if exchange is not None:
                        try:
                            exchange.response_text = full_response
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
                    if repeat_feature is not None:
                        repeat_feature.record(text, full_response)

                    follow_up = router.expects_follow_up
                    if bargein_enabled:
                        if not bargein and follow_up:
                            log.info("Follow-up mode: continuing command loop")
                        return bargein or follow_up
                    else:
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

            else:
                # --- Non-streaming path (string response) ---
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
                        wake.reset()
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
        finally:
            if _voice_lock is not None and _voice_lock.locked():
                try:
                    _voice_lock.release()
                except RuntimeError:
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

                    # Presence tracking + proactive notification delivery
                    if presence_tracker is not None and notification_manager is not None:
                        energy = compute_rms(chunk)
                        presence_tracker.update(energy)

                        if (
                            notification_manager.pending_count() > 0
                            and presence_tracker.is_present()
                            and not audio.is_playing()
                        ):
                            notif = notification_manager.peek()
                            if notif:
                                notification_manager.deliver(notif.id)
                                try:
                                    speech = tts.synthesize(notif.message)
                                    audio.play(speech)
                                except Exception:
                                    log.exception(
                                        "Notification playback failed (non-fatal)"
                                    )
                                wake.reset()

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
                    follow_ups = 0
                    consecutive_low = 0
                    should_continue = True
                    while should_continue:
                        result = _handle_command(
                            session=session, is_follow_up=follow_ups > 0,
                        )
                        if result:
                            consecutive_low = 0
                            follow_ups += 1
                            if follow_ups >= max_follow_ups:
                                log.warning(
                                    "Max follow-up iterations reached, exiting command loop",
                                )
                                break
                            if wake_feedback and not router.expects_follow_up:
                                audio.play(wake_prompts.pick())
                        else:
                            if follow_ups > 0:
                                consecutive_low += 1
                                if consecutive_low >= max_consecutive_low:
                                    log.info(
                                        "Follow-up aborted: %d consecutive "
                                        "low-confidence results",
                                        consecutive_low,
                                    )
                                    break
                                # Still in follow-up, try again
                            else:
                                break
                    wake.reset()

                    # Persist telemetry
                    if session is not None and telemetry_store is not None:
                        try:
                            session.finish()
                            telemetry_store.save_session(session)
                        except Exception:
                            log.exception("Telemetry save failed (non-fatal)")
            except AudioStreamStaleError:
                consecutive_errors += 1
                backoff = min(2 ** consecutive_errors, 30)
                log.warning(
                    "Audio stream stale (%d consecutive, retrying in %ds)",
                    consecutive_errors, backoff,
                )
                time.sleep(backoff)
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
