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
    audio.sample_rate = 16000
    audio.record.return_value = b"\x00\x00" * 16000
    audio.is_playing.return_value = False

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


def _make_config(record=1, wake_feedback=False, vad_enabled=False, bargein_enabled=False):
    """Create a config dict with sensible test defaults.

    New features are disabled by default to keep existing tests stable.
    """
    return {
        "voice_record_duration": record,
        "voice_wake_feedback": wake_feedback,
        "voice_vad_enabled": vad_enabled,
        "voice_bargein_enabled": bargein_enabled,
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

    thread = start_voice_pipeline(
        audio, stt, wake, router, tts, _make_config(record=1), running,
    )
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


# --- Phase 1: Wake feedback tests ---


def test_pipeline_plays_tone_on_wake():
    """Pipeline should play a tone after wake word detection when feedback is enabled."""
    audio = _make_audio()
    stt = MagicMock()
    stt.transcribe.return_value = "hello"
    wake = _make_wake(trigger_on_chunk=1)
    router = _make_router()
    tts = _make_tts()

    running = threading.Event()
    running.set()

    config = _make_config(wake_feedback=True)
    thread = start_voice_pipeline(audio, stt, wake, router, tts, config, running)
    time.sleep(0.3)
    running.clear()
    thread.join(timeout=3)

    # play() should have been called at least twice: once for tone, once for TTS
    assert audio.play.call_count >= 2
    # First play call should be the tone (short PCM data)
    tone_data = audio.play.call_args_list[0][0][0]
    assert isinstance(tone_data, bytes)
    assert len(tone_data) > 0


def test_pipeline_skips_tone_when_feedback_disabled():
    """Pipeline should NOT play a tone when wake feedback is disabled."""
    audio = _make_audio()
    stt = MagicMock()
    stt.transcribe.return_value = "hello"
    # Use a wake that triggers exactly once then never again
    wake = MagicMock()
    wake_calls = {"n": 0}

    def detect_once(chunk):
        wake_calls["n"] += 1
        return wake_calls["n"] == 1

    wake.detect.side_effect = detect_once
    router = _make_router("response")
    speech_bytes = b"\x01\x00" * 16000
    tts = _make_tts(speech=speech_bytes)

    running = threading.Event()
    running.set()

    config = _make_config(wake_feedback=False)
    thread = start_voice_pipeline(audio, stt, wake, router, tts, config, running)
    time.sleep(0.3)
    running.clear()
    thread.join(timeout=3)

    # play() should be called exactly once (for TTS), no tone
    assert audio.play.call_count == 1
    audio.play.assert_called_with(speech_bytes)


# --- Phase 2: VAD tests ---


def test_pipeline_uses_vad_when_enabled():
    """Pipeline should use VAD streaming instead of audio.record() when VAD is enabled."""
    audio = _make_audio()
    stt = MagicMock()
    stt.transcribe.return_value = "hello"
    wake = _make_wake(trigger_on_chunk=1)
    router = _make_router()
    tts = _make_tts()

    running = threading.Event()
    running.set()

    config = _make_config(vad_enabled=True)
    # VAD needs silence threshold config
    config["vad_silence_threshold"] = 500
    config["vad_silence_duration"] = 0.01
    config["vad_min_duration"] = 0.0
    config["vad_max_duration"] = 0.1

    thread = start_voice_pipeline(audio, stt, wake, router, tts, config, running)
    time.sleep(0.5)
    running.clear()
    thread.join(timeout=3)

    # audio.record() should NOT be called when VAD is enabled
    audio.record.assert_not_called()
    # stt.transcribe should still be called
    stt.transcribe.assert_called()


def test_pipeline_uses_record_when_vad_disabled():
    """Pipeline should use audio.record() when VAD is disabled."""
    audio = _make_audio()
    stt = MagicMock()
    stt.transcribe.return_value = "hello"
    wake = _make_wake(trigger_on_chunk=1)
    router = _make_router()
    tts = _make_tts()

    running = threading.Event()
    running.set()

    config = _make_config(vad_enabled=False, record=2)
    thread = start_voice_pipeline(audio, stt, wake, router, tts, config, running)
    time.sleep(0.3)
    running.clear()
    thread.join(timeout=3)

    audio.record.assert_called_with(2)


# --- Phase 3: Barge-in tests ---


def test_pipeline_uses_async_playback_with_bargein():
    """Pipeline should use play_async when barge-in is enabled."""
    audio = _make_audio()
    audio.is_playing.return_value = False
    stt = MagicMock()
    stt.transcribe.return_value = "hello"
    wake = _make_wake(trigger_on_chunk=1)
    router = _make_router("response")
    speech_bytes = b"\x01\x00" * 16000
    tts = _make_tts(speech=speech_bytes)

    running = threading.Event()
    running.set()

    config = _make_config(bargein_enabled=True)
    thread = start_voice_pipeline(audio, stt, wake, router, tts, config, running)
    time.sleep(0.3)
    running.clear()
    thread.join(timeout=3)

    audio.play_async.assert_called_with(speech_bytes)


def test_pipeline_stops_playback_on_bargein():
    """Pipeline should stop playback and handle new command on barge-in."""
    audio = _make_audio()
    # is_playing returns True for enough chunks to pass debounce + 1
    play_count = {"n": 0}

    def is_playing():
        play_count["n"] += 1
        return play_count["n"] <= 20  # 15 debounce + a few more

    audio.is_playing.side_effect = is_playing

    stt = MagicMock()
    stt.transcribe.return_value = "hello"

    # Wake detector: triggers on 1st call (initial wake), then on the
    # first call after debounce during barge-in monitoring
    wake = MagicMock()
    wake_calls = {"n": 0}

    def wake_detect(chunk):
        wake_calls["n"] += 1
        # 1 = initial wake stream, 2 = first detect call after debounce
        return wake_calls["n"] in (1, 2)

    wake.detect.side_effect = wake_detect

    router = _make_router("response")
    tts = _make_tts()

    running = threading.Event()
    running.set()

    config = _make_config(bargein_enabled=True)
    thread = start_voice_pipeline(audio, stt, wake, router, tts, config, running)
    time.sleep(0.5)
    running.clear()
    thread.join(timeout=3)

    audio.stop_playback.assert_called()
