"""Voice pipeline: wake word → record → transcribe → route → respond."""

import logging
import threading
import time

from audio.base import BaseAudio
from intent.router import IntentRouter
from speech.base import BaseSTT
from speech.base_tts import BaseTTS
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

    # Number of audio chunks to skip before monitoring for barge-in.
    # Prevents speaker-to-mic feedback from triggering a false wake word
    # immediately after playback starts. At 80ms/chunk, 15 chunks = 1.2s.
    BARGEIN_DEBOUNCE_CHUNKS = 15

    def _handle_command():
        """Record, transcribe, route, and respond to a single command.

        Returns True if barge-in was detected (caller should loop).
        """
        if vad is not None:
            pcm = vad.record_until_silence(audio.stream())
        else:
            pcm = audio.record(record_duration)
        text = stt.transcribe(pcm)
        log.info("Transcribed: %r", text)
        if not text or not text.strip():
            log.info("Empty transcription, skipping")
            return False
        try:
            response = router.route(text)
            log.info("Response: %r", response)
            if repeat_feature is not None:
                repeat_feature.record(text, response)
            try:
                if bargein_enabled:
                    audio.play_streamed(tts.synthesize_stream(response))
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
                    if not bargein:
                        wake.reset()
                    follow_up = router.expects_follow_up
                    if not bargein and follow_up:
                        log.info("Follow-up mode: continuing command loop")
                    return bargein or follow_up
                else:
                    audio.play(tts.synthesize(response))
                    follow_up = router.expects_follow_up
                    if follow_up:
                        log.info("Follow-up mode: continuing command loop")
                    return follow_up
            except Exception:
                log.exception("TTS error (non-fatal)")
        except Exception:
            log.exception("Routing error (non-fatal)")
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
                    if wake_feedback:
                        audio.play(wake_prompts.pick())
                    # Loop handles barge-in and follow-up: _handle_command
                    # returns True when wake word interrupts playback or
                    # when the router expects a follow-up response.
                    MAX_FOLLOW_UPS = 10
                    follow_ups = 0
                    while _handle_command():
                        follow_ups += 1
                        if follow_ups >= MAX_FOLLOW_UPS:
                            log.warning("Max follow-up iterations reached, exiting command loop")
                            break
                        if wake_feedback and not router.expects_follow_up:
                            audio.play(wake_prompts.pick())
                    wake.reset()
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
