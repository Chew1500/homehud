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
from speech.base import TranscriptionResult
from voice_pipeline import start_voice_pipeline

CHUNK = b"\x00\x00" * 1280


def _patch_stt(stt, text="hello", no_speech_prob=0.0, avg_logprob=0.0):
    """Configure a mock STT to return a TranscriptionResult from transcribe_with_confidence."""
    if isinstance(text, list):
        results = [
            TranscriptionResult(t, no_speech_prob, avg_logprob) if t else TranscriptionResult("")
            for t in text
        ]
        stt.transcribe_with_confidence.side_effect = results
        stt.transcribe.side_effect = text
    else:
        result = TranscriptionResult(text, no_speech_prob, avg_logprob)
        stt.transcribe_with_confidence.return_value = result
        stt.transcribe.return_value = text
    return stt


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
    router.expects_follow_up = False
    return router


def _make_tts(speech=b"\x00\x00" * 16000):
    """Create a mock TTS that returns fixed PCM bytes."""
    tts = MagicMock()
    tts.synthesize.return_value = speech
    tts.synthesize_stream.return_value = iter([speech])
    return tts


def test_pipeline_streams_chunks_to_wake_detector():
    """Pipeline should pass audio chunks to wake.detect()."""
    audio = _make_audio()
    stt = _patch_stt(MagicMock(), "hello")
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
    stt = _patch_stt(MagicMock(), "add milk")
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
    stt.transcribe_with_confidence.assert_called_with(b"\x00\x00" * 16000)


def test_pipeline_calls_wake_reset_after_detection():
    """Pipeline should call wake.reset() after successful detection."""
    audio = _make_audio()
    stt = _patch_stt(MagicMock(), "test")
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
    stt = _patch_stt(MagicMock(), "")
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
    stt.transcribe_with_confidence.side_effect = [
        RuntimeError("model error"),
        TranscriptionResult("recovered"),
    ]
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

    assert stt.transcribe_with_confidence.call_count >= 2


def test_pipeline_logs_transcribed_text(caplog):
    """Pipeline should log the transcribed text."""
    audio = _make_audio()
    stt = _patch_stt(MagicMock(), "add milk to groceries")
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
    stt = _patch_stt(MagicMock(), "what time is it")
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
    stt = _patch_stt(MagicMock(), "hello")
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
    stt = _patch_stt(MagicMock(), "hello")
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
    stt = _patch_stt(MagicMock(), "hello")
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
    stt = _patch_stt(MagicMock(), "what time is it")
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
    stt = _patch_stt(MagicMock(), "hello")
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


def test_pipeline_plays_prompt_on_wake():
    """Pipeline should play a TTS prompt after wake word detection when feedback is enabled."""
    audio = _make_audio()
    stt = _patch_stt(MagicMock(), "hello")
    wake = _make_wake(trigger_on_chunk=1)
    router = _make_router()
    tts = _make_tts()

    prompt_bytes = b"\x05\x00" * 100
    wake_prompts = MagicMock()
    wake_prompts.pick.return_value = prompt_bytes

    running = threading.Event()
    running.set()

    config = _make_config(wake_feedback=True)
    thread = start_voice_pipeline(
        audio, stt, wake, router, tts, config, running, wake_prompts=wake_prompts,
    )
    time.sleep(0.3)
    running.clear()
    thread.join(timeout=3)

    # play() should have been called at least twice: once for prompt, once for TTS
    assert audio.play.call_count >= 2
    # First play call should be the wake prompt
    audio.play.assert_any_call(prompt_bytes)
    wake_prompts.pick.assert_called()


def test_pipeline_skips_prompt_when_feedback_disabled():
    """Pipeline should NOT play a prompt when wake feedback is disabled."""
    audio = _make_audio()
    stt = _patch_stt(MagicMock(), "hello")
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
    thread = start_voice_pipeline(
        audio, stt, wake, router, tts, config, running, wake_prompts=None,
    )
    time.sleep(0.3)
    running.clear()
    thread.join(timeout=3)

    # play() should be called exactly once (for TTS), no prompt
    assert audio.play.call_count == 1
    audio.play.assert_called_with(speech_bytes)


def test_pipeline_skips_prompt_when_no_wake_prompts():
    """Pipeline should NOT play a prompt when wake_prompts is None even if feedback enabled."""
    audio = _make_audio()
    stt = _patch_stt(MagicMock(), "hello")
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

    config = _make_config(wake_feedback=True)
    thread = start_voice_pipeline(
        audio, stt, wake, router, tts, config, running, wake_prompts=None,
    )
    time.sleep(0.3)
    running.clear()
    thread.join(timeout=3)

    # play() should be called exactly once (for TTS), no prompt
    assert audio.play.call_count == 1
    audio.play.assert_called_with(speech_bytes)


# --- Phase 2: VAD tests ---


def test_pipeline_uses_vad_when_enabled():
    """Pipeline should use VAD streaming instead of audio.record() when VAD is enabled."""
    audio = _make_audio()
    stt = _patch_stt(MagicMock(), "hello")
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
    config["vad_speech_chunks_required"] = 0  # Disable gate for mock silence stream

    thread = start_voice_pipeline(audio, stt, wake, router, tts, config, running)
    time.sleep(0.5)
    running.clear()
    thread.join(timeout=3)

    # audio.record() should NOT be called when VAD is enabled
    audio.record.assert_not_called()
    # stt.transcribe_with_confidence should still be called
    stt.transcribe_with_confidence.assert_called()


def test_pipeline_uses_record_when_vad_disabled():
    """Pipeline should use audio.record() when VAD is disabled."""
    audio = _make_audio()
    stt = _patch_stt(MagicMock(), "hello")
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


def test_pipeline_uses_streamed_playback_with_bargein():
    """Pipeline should use play_streamed + synthesize_stream when barge-in is enabled."""
    audio = _make_audio()
    audio.is_playing.return_value = False
    stt = _patch_stt(MagicMock(), "hello")
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

    tts.synthesize_stream.assert_called_with("response")
    audio.play_streamed.assert_called()


def test_pipeline_stops_playback_on_bargein():
    """Pipeline should stop playback and handle new command on barge-in."""
    audio = _make_audio()
    # is_playing returns True for enough chunks to pass debounce + 1
    play_count = {"n": 0}

    def is_playing():
        play_count["n"] += 1
        return play_count["n"] <= 20  # 15 debounce + a few more

    audio.is_playing.side_effect = is_playing

    stt = _patch_stt(MagicMock(), "hello")

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


# --- Phase 4: Follow-up mode tests ---


def test_pipeline_follow_up_loops_without_wake_word():
    """When router.expects_follow_up is True, pipeline should loop
    back to record another command without waiting for wake word."""
    audio = _make_audio()
    stt = _patch_stt(MagicMock(), ["track batman", "yes", ""])
    wake = _make_wake(trigger_on_chunk=1)
    router = MagicMock()
    # First call: router.expects_follow_up True, second: False
    follow_up_values = [True, False, False]
    follow_up_iter = iter(follow_up_values)
    type(router).expects_follow_up = property(lambda self: next(follow_up_iter, False))
    router.route.side_effect = [
        "I found 7 results. Can you tell me the year?",
        "Done! Added The Batman to your movies.",
        "",
    ]
    tts = _make_tts()

    running = threading.Event()
    running.set()

    config = _make_config(bargein_enabled=False)
    thread = start_voice_pipeline(audio, stt, wake, router, tts, config, running)
    time.sleep(0.5)
    running.clear()
    thread.join(timeout=3)

    # Router should have been called at least twice (follow-up looped)
    assert router.route.call_count >= 2
    router.route.assert_any_call("track batman")
    router.route.assert_any_call("yes")


def test_pipeline_follow_up_suppresses_wake_prompt():
    """When follow-up is active with wake feedback, the wake prompt should
    NOT play between follow-up turns (the bot's question is the indicator)."""
    audio = _make_audio()
    stt = _patch_stt(MagicMock(), ["track batman", "2022", ""])

    # Wake triggers exactly once
    wake = MagicMock()
    wake_calls = {"n": 0}

    def detect_once(chunk):
        wake_calls["n"] += 1
        return wake_calls["n"] == 1

    wake.detect.side_effect = detect_once

    router = MagicMock()
    # expects_follow_up is read at two points: once in _handle_command (return)
    # and once in the loop (prompt decision). Values must cover all reads:
    #   read 1 (after route #1 return): True  → loop continues
    #   read 2 (loop prompt check):     True  → prompt suppressed
    #   read 3 (after route #2 return): False → loop exits
    follow_up_values = [True, True, False]
    follow_up_iter = iter(follow_up_values)
    type(router).expects_follow_up = property(lambda self: next(follow_up_iter, False))
    router.route.side_effect = [
        "I found 7 results.",
        "Done!",
        "",
    ]
    tts = _make_tts()

    prompt_bytes = b"\x05\x00" * 100
    wake_prompts = MagicMock()
    wake_prompts.pick.return_value = prompt_bytes

    running = threading.Event()
    running.set()

    config = _make_config(bargein_enabled=False, wake_feedback=True)
    thread = start_voice_pipeline(
        audio, stt, wake, router, tts, config, running, wake_prompts=wake_prompts,
    )
    time.sleep(0.5)
    running.clear()
    thread.join(timeout=3)

    # Prompt should play only once: for the initial wake word detection.
    # Follow-up turns should NOT get a wake prompt.
    assert wake_prompts.pick.call_count == 1


def test_pipeline_follow_up_empty_transcription_exits():
    """If user stays silent during follow-up, empty transcription should
    exit the command loop after max consecutive low-confidence attempts."""
    audio = _make_audio()
    stt = _patch_stt(MagicMock(), ["track batman", "", ""])
    wake = _make_wake(trigger_on_chunk=1)
    router = MagicMock()
    type(router).expects_follow_up = property(lambda self: True)
    router.route.return_value = "I found 7 results."
    tts = _make_tts()

    running = threading.Event()
    running.set()

    config = _make_config(bargein_enabled=False)
    thread = start_voice_pipeline(audio, stt, wake, router, tts, config, running)
    time.sleep(0.5)
    running.clear()
    thread.join(timeout=3)

    # Router should only be called once (second transcription was empty)
    assert router.route.call_count == 1


def test_pipeline_follow_up_with_bargein():
    """Follow-up should also work when barge-in is enabled but no barge-in occurs."""
    audio = _make_audio()
    audio.is_playing.return_value = False  # Playback ends immediately
    stt = _patch_stt(MagicMock(), ["track batman", "yes", ""])
    wake = _make_wake(trigger_on_chunk=1)
    router = MagicMock()
    follow_up_values = [True, False, False]
    follow_up_iter = iter(follow_up_values)
    type(router).expects_follow_up = property(lambda self: next(follow_up_iter, False))
    router.route.side_effect = [
        "I found 7 results.",
        "Done!",
        "",
    ]
    speech_bytes = b"\x01\x00" * 16000
    tts = _make_tts(speech=speech_bytes)

    running = threading.Event()
    running.set()

    config = _make_config(bargein_enabled=True)
    thread = start_voice_pipeline(audio, stt, wake, router, tts, config, running)
    time.sleep(0.5)
    running.clear()
    thread.join(timeout=3)

    # Router should have been called at least twice
    assert router.route.call_count >= 2


def test_pipeline_follow_up_max_iterations(caplog):
    """Pipeline should break out of follow-up loop after max_follow_ups iterations."""
    audio = _make_audio()
    stt = _patch_stt(MagicMock(), "yes")

    # Wake triggers exactly once so the outer loop doesn't restart
    wake = MagicMock()
    wake_calls = {"n": 0}

    def detect_once(chunk):
        wake_calls["n"] += 1
        return wake_calls["n"] == 1

    wake.detect.side_effect = detect_once

    router = MagicMock()
    # Router always expects follow-up (would loop forever without cap)
    type(router).expects_follow_up = property(lambda self: True)
    router.route.return_value = "Still going..."
    tts = _make_tts()

    running = threading.Event()
    running.set()

    config = _make_config(bargein_enabled=False)
    with caplog.at_level(logging.WARNING, logger="home-hud.voice"):
        thread = start_voice_pipeline(audio, stt, wake, router, tts, config, running)
        time.sleep(1.0)
        running.clear()
        thread.join(timeout=3)

    # Default max_follow_ups=5: 1 initial + 4 more before follow_ups reaches 5 = 5 total
    assert router.route.call_count == 5
    assert any("Max follow-up iterations" in record.message for record in caplog.records)


# --- STT confidence filtering tests ---


def test_pipeline_rejects_high_no_speech_prob(caplog):
    """Pipeline should reject transcriptions with high no_speech_prob."""
    audio = _make_audio()
    stt = _patch_stt(MagicMock(), "some noise", no_speech_prob=0.8)
    wake = _make_wake(trigger_on_chunk=1)
    router = _make_router()
    tts = _make_tts()

    running = threading.Event()
    running.set()

    config = _make_config(bargein_enabled=False)
    with caplog.at_level(logging.INFO, logger="home-hud.voice"):
        thread = start_voice_pipeline(audio, stt, wake, router, tts, config, running)
        time.sleep(0.3)
        running.clear()
        thread.join(timeout=3)

    # Router should NOT be called — transcription was rejected
    router.route.assert_not_called()
    assert any("high no_speech_prob" in record.message for record in caplog.records)


def test_pipeline_rejects_low_avg_logprob(caplog):
    """Pipeline should reject transcriptions with very low avg_logprob."""
    audio = _make_audio()
    stt = _patch_stt(MagicMock(), "garbled text", avg_logprob=-1.5)
    wake = _make_wake(trigger_on_chunk=1)
    router = _make_router()
    tts = _make_tts()

    running = threading.Event()
    running.set()

    config = _make_config(bargein_enabled=False)
    with caplog.at_level(logging.INFO, logger="home-hud.voice"):
        thread = start_voice_pipeline(audio, stt, wake, router, tts, config, running)
        time.sleep(0.3)
        running.clear()
        thread.join(timeout=3)

    # Router should NOT be called — transcription was rejected
    router.route.assert_not_called()
    assert any("low avg_logprob" in record.message for record in caplog.records)


def test_pipeline_accepts_confident_transcription():
    """Pipeline should accept transcriptions with good confidence metrics."""
    audio = _make_audio()
    stt = _patch_stt(MagicMock(), "add milk", no_speech_prob=0.1, avg_logprob=-0.3)
    wake = _make_wake(trigger_on_chunk=1)
    router = _make_router()
    tts = _make_tts()

    running = threading.Event()
    running.set()

    config = _make_config(bargein_enabled=False)
    thread = start_voice_pipeline(audio, stt, wake, router, tts, config, running)
    time.sleep(0.3)
    running.clear()
    thread.join(timeout=3)

    router.route.assert_called_with("add milk")


# --- Consecutive low-confidence follow-up tests ---


def test_pipeline_follow_up_aborts_on_consecutive_low_confidence(caplog):
    """Follow-up loop should abort after max_consecutive_low_confidence empty results."""
    audio = _make_audio()
    # First call succeeds, then 2 consecutive empties (default threshold=2)
    stt = _patch_stt(MagicMock(), ["track batman", "", ""])
    wake = _make_wake(trigger_on_chunk=1)
    router = MagicMock()
    type(router).expects_follow_up = property(lambda self: True)
    router.route.return_value = "Which year?"
    tts = _make_tts()

    running = threading.Event()
    running.set()

    config = _make_config(bargein_enabled=False)
    with caplog.at_level(logging.INFO, logger="home-hud.voice"):
        thread = start_voice_pipeline(audio, stt, wake, router, tts, config, running)
        time.sleep(0.5)
        running.clear()
        thread.join(timeout=3)

    # Router called once for initial command, then 2 empty follow-ups hit the cap
    assert router.route.call_count == 1
    assert any("consecutive" in record.message.lower() for record in caplog.records)


# --- Follow-up VAD gate tests ---


def test_pipeline_follow_up_skips_when_vad_no_speech(caplog):
    """During follow-up, if VAD detects no speech, STT should be skipped."""
    audio = _make_audio()
    # First call succeeds, subsequent calls get skipped by VAD gate
    stt = _patch_stt(MagicMock(), ["track batman", "should not reach", "should not reach"])

    # Wake triggers exactly once so the outer loop doesn't restart
    wake = MagicMock()
    wake_calls = {"n": 0}

    def detect_once(chunk):
        wake_calls["n"] += 1
        return wake_calls["n"] == 1

    wake.detect.side_effect = detect_once

    router = MagicMock()
    type(router).expects_follow_up = property(lambda self: True)
    router.route.return_value = "Which year?"
    tts = _make_tts()

    running = threading.Event()
    running.set()

    config = _make_config(bargein_enabled=False, vad_enabled=True)
    config["vad_silence_threshold"] = 500
    config["vad_silence_duration"] = 0.01
    config["vad_min_duration"] = 0.0
    config["vad_max_duration"] = 0.1
    # With speech_chunks_required=3 and all-silence stream, VAD will set
    # last_speech_detected=False, triggering the follow-up VAD gate
    config["vad_speech_chunks_required"] = 3

    with caplog.at_level(logging.INFO, logger="home-hud.voice"):
        thread = start_voice_pipeline(audio, stt, wake, router, tts, config, running)
        time.sleep(0.5)
        running.clear()
        thread.join(timeout=3)

    # Router called once for initial command; follow-ups skipped by VAD gate
    assert router.route.call_count == 1
    assert any("VAD gate" in record.message for record in caplog.records)
