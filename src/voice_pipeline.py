"""Voice pipeline: wake word → record → transcribe → LLM response."""

import logging
import threading
import time

from audio.base import BaseAudio
from llm.base import BaseLLM
from speech.base import BaseSTT
from wake.base import BaseWakeWord

log = logging.getLogger("home-hud.voice")


def start_voice_pipeline(
    audio: BaseAudio,
    stt: BaseSTT,
    wake: BaseWakeWord,
    llm: BaseLLM,
    config: dict,
    running: threading.Event,
) -> threading.Thread:
    """Start the voice pipeline in a daemon thread.

    Streams audio chunks, waits for wake word detection, then records
    and transcribes a command. Repeats until running is cleared.

    Returns the started Thread so callers can join() if needed.
    """
    record_duration = config.get("voice_record_duration", 5)

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
                    pcm = audio.record(record_duration)
                    text = stt.transcribe(pcm)
                    log.info("Transcribed: %r", text)
                    try:
                        response = llm.respond(text)
                        log.info("LLM response: %r", response)
                    except Exception:
                        log.exception("LLM error (non-fatal)")
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
