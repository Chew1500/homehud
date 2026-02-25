"""Voice pipeline: wake word → record → transcribe → route → respond."""

import logging
import threading
import time

from audio.base import BaseAudio
from intent.router import IntentRouter
from speech.base import BaseSTT
from speech.base_tts import BaseTTS
from utils.tone import generate_tone
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
) -> threading.Thread:
    """Start the voice pipeline in a daemon thread.

    Streams audio chunks, waits for wake word detection, then records
    and transcribes a command. Repeats until running is cleared.

    Returns the started Thread so callers can join() if needed.
    """
    record_duration = config.get("voice_record_duration", 5)

    # Pre-generate wake feedback tone
    wake_feedback = config.get("voice_wake_feedback", True)
    wake_tone = None
    if wake_feedback:
        wake_tone = generate_tone(
            freq=config.get("voice_wake_tone_freq", 880),
            duration_ms=config.get("voice_wake_tone_duration", 150),
            sample_rate=audio.sample_rate,
        )

    # VAD setup
    vad_enabled = config.get("voice_vad_enabled", True)
    vad = VoiceActivityDetector(config) if vad_enabled else None

    # Barge-in setup
    bargein_enabled = config.get("voice_bargein_enabled", True)

    def _handle_command():
        """Record, transcribe, route, and respond to a single command."""
        if vad is not None:
            pcm = vad.record_until_silence(audio.stream())
        else:
            pcm = audio.record(record_duration)
        text = stt.transcribe(pcm)
        log.info("Transcribed: %r", text)
        try:
            response = router.route(text)
            log.info("Response: %r", response)
            if repeat_feature is not None:
                repeat_feature.record(text, response)
            try:
                speech = tts.synthesize(response)
                if bargein_enabled and hasattr(audio, "play_async"):
                    audio.play_async(speech)
                    # Monitor for wake word during playback
                    for chunk in audio.stream():
                        if not audio.is_playing():
                            break
                        if wake.detect(chunk):
                            log.info("Barge-in detected, stopping playback")
                            audio.stop_playback()
                            wake.reset()
                            _handle_command()
                            return
                    wake.reset()
                else:
                    audio.play(speech)
            except Exception:
                log.exception("TTS error (non-fatal)")
        except Exception:
            log.exception("Routing error (non-fatal)")

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
                    if wake_tone is not None:
                        audio.play(wake_tone)
                    _handle_command()
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
