"""Tests for the voice pipeline."""

import logging
import sys
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock

# Add src to path so imports work
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from features.repeat import RepeatFeature
from voice_pipeline import start_voice_pipeline

CHUNK = b"\x00\x00" * 1280


def _make_audio(trigger_on_chunk=3):
    """Create a mock audio that streams chunks and records silence."""
    audio = MagicMock()
    audio.record.return_value = b"\x00\x00" * 16000

    def fake_stream(chunk_duration_ms=80):
        i = 0
        while True:
            i += 1
            yield CHUNK

    audio.stream.side_effect = fake_stream
    return audio


def _make_wake(trigger_on_chunk=3):
    """Create a mock wake detector that triggers after N chunks."""
    wake = MagicMock()
    call_count = {"n": 0}

    def fake_detect(chunk):
        call_count["n"] += 1
        return call_count["n"] >= trigger_on_chunk

    wake.detect.side_effect = fake_detect
    return wake


def _make_config(record=1):
    return {
        "voice_record_duration": record,
    }


def _make_router(response="Mock router response."):
    """Create a mock router that returns a fixed response."""
    router = MagicMock()
    router.route.return_value = response
    return router


def _make_tts(speech=b"\x00\x00" * 16000):
    """Create a mock TTS that returns fixed PCM bytes."""
    tts = MagicMock()
    tts.synthesize.return_value = speech
    return tts


def test_pipeline_streams_chunks_to_wake_detector():
    """Pipeline should pass audio chunks to wake.detect()."""
    audio = _make_audio()
    stt = MagicMock()
    stt.transcribe.return_value = "hello"
    wake = _make_wake(trigger_on_chunk=3)
    router = _make_router()
    tts = _make_tts()

    running = threading.Event()
    running.set()

    thread = start_voice_pipeline(audio, stt, wake, router, tts, _make_config(), running)
    time.sleep(0.3)
    running.clear()
    thread.join(timeout=3)

    assert wake.detect.call_count >= 3
    wake.detect.assert_called_with(CHUNK)


def test_pipeline_records_and_transcribes_after_wake():
    """Pipeline should record + transcribe when wake word is detected."""
    audio = _make_audio()
    stt = MagicMock()
    stt.transcribe.return_value = "add milk"
    wake = _make_wake(trigger_on_chunk=2)
    router = _make_router()
    tts = _make_tts()

    running = threading.Event()
    running.set()

    thread = start_voice_pipeline(audio, stt, wake, router, tts, _make_config(record=1), running)
    time.sleep(0.3)
    running.clear()
    thread.join(timeout=3)

    audio.record.assert_called_with(1)
    stt.transcribe.assert_called_with(b"\x00\x00" * 16000)


def test_pipeline_calls_wake_reset_after_detection():
    """Pipeline should call wake.reset() after successful detection."""
    audio = _make_audio()
    stt = MagicMock()
    stt.transcribe.return_value = "test"
    wake = _make_wake(trigger_on_chunk=2)
    router = _make_router()
    tts = _make_tts()

    running = threading.Event()
    running.set()

    thread = start_voice_pipeline(audio, stt, wake, router, tts, _make_config(), running)
    time.sleep(0.3)
    running.clear()
    thread.join(timeout=3)

    wake.reset.assert_called()


def test_pipeline_exits_when_running_cleared():
    """Pipeline should exit promptly when running is cleared during streaming."""
    audio = _make_audio()
    stt = MagicMock()
    stt.transcribe.return_value = ""
    # Wake never triggers — pipeline should still exit via running check
    wake = MagicMock()
    wake.detect.return_value = False
    router = _make_router()
    tts = _make_tts()

    running = threading.Event()
    running.set()

    thread = start_voice_pipeline(audio, stt, wake, router, tts, _make_config(), running)
    time.sleep(0.1)
    running.clear()
    thread.join(timeout=3)

    assert not thread.is_alive()


def test_pipeline_survives_exceptions():
    """Pipeline should retry with backoff after an exception and recover."""
    audio = _make_audio()
    stt = MagicMock()
    stt.transcribe.side_effect = [RuntimeError("model error"), "recovered"]
    # Trigger on first chunk each cycle
    wake = MagicMock()
    wake.detect.return_value = True
    router = _make_router()
    tts = _make_tts()

    running = threading.Event()
    running.set()

    thread = start_voice_pipeline(audio, stt, wake, router, tts, _make_config(), running)
    # First error triggers 2s backoff, so wait long enough for retry
    time.sleep(3.0)
    running.clear()
    thread.join(timeout=3)

    assert stt.transcribe.call_count >= 2


def test_pipeline_logs_transcribed_text(caplog):
    """Pipeline should log the transcribed text."""
    audio = _make_audio()
    stt = MagicMock()
    stt.transcribe.return_value = "add milk to groceries"
    wake = _make_wake(trigger_on_chunk=1)
    router = _make_router()
    tts = _make_tts()

    running = threading.Event()
    running.set()

    with caplog.at_level(logging.INFO, logger="home-hud.voice"):
        thread = start_voice_pipeline(audio, stt, wake, router, tts, _make_config(), running)
        time.sleep(0.3)
        running.clear()
        thread.join(timeout=3)

    assert any("add milk to groceries" in record.message for record in caplog.records)


def test_pipeline_sends_transcription_to_router():
    """Pipeline should pass transcribed text to router.route()."""
    audio = _make_audio()
    stt = MagicMock()
    stt.transcribe.return_value = "what time is it"
    wake = _make_wake(trigger_on_chunk=1)
    router = _make_router("It is 3pm.")
    tts = _make_tts()

    running = threading.Event()
    running.set()

    thread = start_voice_pipeline(audio, stt, wake, router, tts, _make_config(), running)
    time.sleep(0.3)
    running.clear()
    thread.join(timeout=3)

    router.route.assert_called_with("what time is it")


def test_pipeline_survives_routing_errors(caplog):
    """Pipeline should continue running even if routing raises an exception."""
    audio = _make_audio()
    stt = MagicMock()
    stt.transcribe.return_value = "hello"
    wake = _make_wake(trigger_on_chunk=1)
    router = MagicMock()
    router.route.side_effect = RuntimeError("API down")
    tts = _make_tts()

    running = threading.Event()
    running.set()

    with caplog.at_level(logging.ERROR, logger="home-hud.voice"):
        thread = start_voice_pipeline(audio, stt, wake, router, tts, _make_config(), running)
        time.sleep(0.3)
        running.clear()
        thread.join(timeout=3)

    # Pipeline should have called router and survived the error
    router.route.assert_called()
    assert any("Routing error" in record.message for record in caplog.records)


def test_pipeline_synthesizes_and_plays_response():
    """Pipeline should synthesize response via TTS and play it."""
    audio = _make_audio()
    stt = MagicMock()
    stt.transcribe.return_value = "hello"
    wake = _make_wake(trigger_on_chunk=1)
    router = _make_router("Hi there!")
    speech_bytes = b"\x01\x00" * 16000
    tts = _make_tts(speech=speech_bytes)

    running = threading.Event()
    running.set()

    thread = start_voice_pipeline(audio, stt, wake, router, tts, _make_config(), running)
    time.sleep(0.3)
    running.clear()
    thread.join(timeout=3)

    tts.synthesize.assert_called_with("Hi there!")
    audio.play.assert_called_with(speech_bytes)


def test_pipeline_survives_tts_errors(caplog):
    """Pipeline should continue running even if TTS raises an exception."""
    audio = _make_audio()
    stt = MagicMock()
    stt.transcribe.return_value = "hello"
    wake = _make_wake(trigger_on_chunk=1)
    router = _make_router("response text")
    tts = MagicMock()
    tts.synthesize.side_effect = RuntimeError("TTS model failed")

    running = threading.Event()
    running.set()

    with caplog.at_level(logging.ERROR, logger="home-hud.voice"):
        thread = start_voice_pipeline(audio, stt, wake, router, tts, _make_config(), running)
        time.sleep(0.3)
        running.clear()
        thread.join(timeout=3)

    # Router should have been called successfully
    router.route.assert_called()
    # TTS error should be logged but pipeline survives
    assert any("TTS error" in record.message for record in caplog.records)


def test_pipeline_calls_repeat_feature_record():
    """Pipeline should call repeat_feature.record() after routing."""
    audio = _make_audio()
    stt = MagicMock()
    stt.transcribe.return_value = "what time is it"
    wake = _make_wake(trigger_on_chunk=1)
    router = _make_router("It is 3pm.")
    tts = _make_tts()
    repeat = RepeatFeature({})

    running = threading.Event()
    running.set()

    thread = start_voice_pipeline(
        audio, stt, wake, router, tts, _make_config(), running,
        repeat_feature=repeat,
    )
    time.sleep(0.3)
    running.clear()
    thread.join(timeout=3)

    result = repeat.handle("what did you say")
    assert "what time is it" in result
    assert "It is 3pm." in result


def test_pipeline_works_without_repeat_feature():
    """Pipeline should work fine when repeat_feature is not provided."""
    audio = _make_audio()
    stt = MagicMock()
    stt.transcribe.return_value = "hello"
    wake = _make_wake(trigger_on_chunk=1)
    router = _make_router("Hi there!")
    tts = _make_tts()

    running = threading.Event()
    running.set()

    thread = start_voice_pipeline(
        audio, stt, wake, router, tts, _make_config(), running,
    )
    time.sleep(0.3)
    running.clear()
    thread.join(timeout=3)

    router.route.assert_called_with("hello")
