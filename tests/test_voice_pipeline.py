"""Tests for the voice pipeline."""

import logging
import sys
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock

# Add src to path so imports work
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

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


def test_pipeline_streams_chunks_to_wake_detector():
    """Pipeline should pass audio chunks to wake.detect()."""
    audio = _make_audio()
    stt = MagicMock()
    stt.transcribe.return_value = "hello"
    wake = _make_wake(trigger_on_chunk=3)

    running = threading.Event()
    running.set()

    thread = start_voice_pipeline(audio, stt, wake, _make_config(), running)
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

    running = threading.Event()
    running.set()

    thread = start_voice_pipeline(audio, stt, wake, _make_config(record=1), running)
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

    running = threading.Event()
    running.set()

    thread = start_voice_pipeline(audio, stt, wake, _make_config(), running)
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

    running = threading.Event()
    running.set()

    thread = start_voice_pipeline(audio, stt, wake, _make_config(), running)
    time.sleep(0.1)
    running.clear()
    thread.join(timeout=3)

    assert not thread.is_alive()


def test_pipeline_survives_exceptions():
    """Pipeline should continue running even if STT raises an exception."""
    audio = _make_audio()
    stt = MagicMock()
    stt.transcribe.side_effect = [RuntimeError("model error"), "recovered"]
    # Trigger on first chunk each cycle
    wake = MagicMock()
    wake.detect.return_value = True

    running = threading.Event()
    running.set()

    thread = start_voice_pipeline(audio, stt, wake, _make_config(), running)
    time.sleep(0.5)
    running.clear()
    thread.join(timeout=3)

    assert stt.transcribe.call_count >= 2


def test_pipeline_logs_transcribed_text(caplog):
    """Pipeline should log the transcribed text."""
    audio = _make_audio()
    stt = MagicMock()
    stt.transcribe.return_value = "add milk to groceries"
    wake = _make_wake(trigger_on_chunk=1)

    running = threading.Event()
    running.set()

    with caplog.at_level(logging.INFO, logger="home-hud.voice"):
        thread = start_voice_pipeline(audio, stt, wake, _make_config(), running)
        time.sleep(0.3)
        running.clear()
        thread.join(timeout=3)

    assert any("add milk to groceries" in record.message for record in caplog.records)
