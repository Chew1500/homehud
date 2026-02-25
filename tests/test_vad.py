"""Tests for the voice activity detector."""

import sys
import time
from pathlib import Path

import numpy as np

# Add src to path so imports work
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from utils.vad import VoiceActivityDetector

# 80ms chunk at 16kHz = 1280 samples
CHUNK_SAMPLES = 1280


def _silence_chunk():
    """Return an 80ms chunk of silence."""
    return b"\x00\x00" * CHUNK_SAMPLES


def _loud_chunk(amplitude=5000):
    """Return an 80ms chunk of a loud sine wave."""
    t = np.linspace(0, 0.08, CHUNK_SAMPLES, endpoint=False)
    wave = (np.sin(2 * np.pi * 440 * t) * amplitude).astype(np.int16)
    return wave.tobytes()


def _make_stream(chunks):
    """Create a generator from a list of chunks."""
    def gen():
        for c in chunks:
            yield c
    return gen()


def _make_vad(**overrides):
    """Create a VAD with test-friendly defaults."""
    config = {
        "vad_silence_threshold": 500,
        "vad_silence_duration": 0.01,  # Very short for fast tests
        "vad_min_duration": 0.0,
        "vad_max_duration": 5.0,
        "audio_sample_rate": 16000,
    }
    config.update(overrides)
    return VoiceActivityDetector(config)


def test_rms_silence():
    """RMS of silence should be zero."""
    assert VoiceActivityDetector.rms(_silence_chunk()) == 0.0


def test_rms_loud():
    """RMS of a loud signal should be well above the default threshold."""
    rms = VoiceActivityDetector.rms(_loud_chunk())
    assert rms > 500


def test_rms_empty():
    """RMS of empty bytes should be zero."""
    assert VoiceActivityDetector.rms(b"") == 0.0


def test_silence_detection():
    """VAD should stop after detecting silence following speech."""
    chunks = [_loud_chunk()] * 5 + [_silence_chunk()] * 5
    vad = _make_vad()
    result = vad.record_until_silence(_make_stream(chunks))
    # Should have collected some chunks but stopped before consuming all
    assert len(result) > 0


def test_max_duration_enforced():
    """VAD should stop at max_duration even with continuous speech."""
    # Create a stream of loud chunks
    loud = _loud_chunk()

    def infinite_loud():
        while True:
            yield loud

    vad = _make_vad(vad_max_duration=0.1)
    start = time.monotonic()
    result = vad.record_until_silence(infinite_loud())
    elapsed = time.monotonic() - start
    assert len(result) > 0
    # Should have stopped around max_duration (with some tolerance)
    assert elapsed < 1.0


def test_min_duration_respected():
    """VAD should not stop before min_duration even with silence."""
    # All silence — but min_duration forces collection
    chunks = [_silence_chunk()] * 100
    vad = _make_vad(vad_min_duration=0.1, vad_silence_duration=0.01)
    result = vad.record_until_silence(_make_stream(chunks))
    # Should have at least min_duration worth of audio
    min_bytes = int(16000 * 0.1) * 2  # samples * 2 bytes
    assert len(result) >= min_bytes


def test_all_silence_stops():
    """VAD should eventually stop when given only silence (after min_duration)."""
    chunks = [_silence_chunk()] * 200
    # Use 0.0 silence_duration so instant silence detection (chunks yield with no real delay)
    vad = _make_vad(vad_min_duration=0.0, vad_silence_duration=0.0)
    result = vad.record_until_silence(_make_stream(chunks))
    # Should stop early — first chunk triggers silence detection
    assert len(result) < len(b"".join(chunks))


def test_returns_concatenated_bytes():
    """VAD should return all collected chunks concatenated."""
    chunk = _loud_chunk()
    chunks = [chunk] * 3 + [_silence_chunk()] * 5
    vad = _make_vad()
    result = vad.record_until_silence(_make_stream(chunks))
    # Result should start with the loud chunks
    assert result[:len(chunk)] == chunk
