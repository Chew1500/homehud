"""Voice pipeline: wake word → record → transcribe → (future: intent parsing)."""

import logging
import threading

from audio.base import BaseAudio
from speech.base import BaseSTT
from wake.base import BaseWakeWord

log = logging.getLogger("home-hud.voice")


def start_voice_pipeline(
    audio: BaseAudio,
    stt: BaseSTT,
    wake: BaseWakeWord,
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
        while running.is_set():
            try:
                for chunk in audio.stream():
                    if not running.is_set():
                        break
                    if wake.detect(chunk):
                        pcm = audio.record(record_duration)
                        text = stt.transcribe(pcm)
                        log.info("Transcribed: %r", text)
                        wake.reset()
                        break
            except Exception:
                log.exception("Voice pipeline error (will retry next cycle)")

        log.info("Voice pipeline stopped.")

    thread = threading.Thread(target=loop, name="voice-pipeline", daemon=True)
    thread.start()
    return thread
