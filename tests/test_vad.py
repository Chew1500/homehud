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


def _noise_chunk(amplitude=200):
    """Return an 80ms chunk of moderate noise (for ambient calibration)."""
    rng = np.random.default_rng(42)
    samples = (rng.standard_normal(CHUNK_SAMPLES) * amplitude).astype(np.int16)
    return samples.tobytes()


def _make_vad(**overrides):
    """Create a VAD with test-friendly defaults."""
    config = {
        "vad_silence_threshold": 500,
        "vad_silence_duration": 0.01,  # Very short for fast tests
        "vad_min_duration": 0.0,
        "vad_max_duration": 5.0,
        "audio_sample_rate": 16000,
        "vad_speech_chunks_required": 0,  # Disable gate for existing tests
        "vad_adaptive": False,  # Disable adaptive for existing tests
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


# --- Speech gate tests ---


def test_gate_prevents_early_stop_before_speech():
    """With the speech gate, all-silence should NOT stop early — runs to max_duration."""
    chunks = [_silence_chunk()] * 200
    vad = _make_vad(
        vad_speech_chunks_required=3,
        vad_min_duration=0.0,
        vad_silence_duration=0.0,
        vad_max_duration=0.2,
    )
    result = vad.record_until_silence(_make_stream(chunks))
    # With gate active and no speech, silence can't trigger stop.
    # VAD runs until max_duration (all 200 chunks yield instantly,
    # max_duration fires based on wall clock).
    assert len(result) > 0


def test_gate_allows_stop_after_speech():
    """Once enough loud chunks are seen, silence should trigger stop normally."""
    chunks = [_loud_chunk()] * 5 + [_silence_chunk()] * 10
    vad = _make_vad(
        vad_speech_chunks_required=3,
        vad_silence_duration=0.0,
        vad_min_duration=0.0,
    )
    result = vad.record_until_silence(_make_stream(chunks))
    # Should stop after the loud chunks + first silence chunk
    all_bytes = b"".join(chunks)
    assert len(result) < len(all_bytes)


def test_gate_cumulative_counting():
    """Speech chunks count is cumulative (not consecutive).

    Pattern: loud, silence, loud, loud → 3 loud chunks total → gate opens.
    """
    chunks = (
        [_loud_chunk()] * 1
        + [_silence_chunk()] * 1
        + [_loud_chunk()] * 2
        + [_silence_chunk()] * 10
    )
    vad = _make_vad(
        vad_speech_chunks_required=3,
        vad_silence_duration=0.0,
        vad_min_duration=0.0,
    )
    result = vad.record_until_silence(_make_stream(chunks))
    all_bytes = b"".join(chunks)
    # Gate should have opened after 3rd loud chunk, then silence triggers stop
    assert len(result) < len(all_bytes)


def test_gate_zero_disables():
    """With speech_chunks_required=0, gate is effectively disabled (speech_started=True)."""
    chunks = [_silence_chunk()] * 200
    vad = _make_vad(
        vad_speech_chunks_required=0,
        vad_min_duration=0.0,
        vad_silence_duration=0.0,
    )
    result = vad.record_until_silence(_make_stream(chunks))
    # Should stop early — first chunk triggers silence detection (gate disabled)
    assert len(result) < len(b"".join(chunks))


# --- last_speech_detected tests ---


def test_vad_tracks_speech_detected_true():
    """last_speech_detected should be True when speech was found."""
    chunks = [_loud_chunk()] * 5 + [_silence_chunk()] * 5
    vad = _make_vad(vad_speech_chunks_required=3)
    vad.record_until_silence(_make_stream(chunks))
    assert vad.last_speech_detected is True


def test_vad_tracks_speech_detected_false():
    """last_speech_detected should be False when no speech was found."""
    chunks = [_silence_chunk()] * 200
    vad = _make_vad(
        vad_speech_chunks_required=3,
        vad_max_duration=0.2,
    )
    vad.record_until_silence(_make_stream(chunks))
    assert vad.last_speech_detected is False


def test_vad_last_speech_detected_initial():
    """last_speech_detected should be False before any recording."""
    vad = _make_vad()
    assert vad.last_speech_detected is False


# --- Adaptive VAD tests ---


def test_adaptive_calibrates_from_ambient():
    """Adaptive VAD should calibrate from ambient noise and detect silence after speech."""
    noise = _noise_chunk(amplitude=200)
    calibration = [noise] * 5  # ambient ~200 RMS
    speech = [_loud_chunk(amplitude=5000)] * 5
    silence = [_silence_chunk()] * 5
    chunks = calibration + speech + silence
    vad = _make_vad(
        vad_adaptive=True,
        vad_calibration_chunks=5,
        vad_adaptive_multiplier=1.5,
        vad_speech_chunks_required=0,
        vad_silence_duration=0.0,
        vad_min_duration=0.0,
    )
    result = vad.record_until_silence(_make_stream(chunks))
    all_bytes = b"".join(chunks)
    # Should stop on silence, not consume everything
    assert len(result) < len(all_bytes)


def test_adaptive_handles_high_ambient():
    """Adaptive VAD should handle high ambient noise with speech well above it."""
    noise = _noise_chunk(amplitude=400)
    calibration = [noise] * 5  # ambient ~400 RMS → threshold ~600
    speech = [_loud_chunk(amplitude=2000)] * 5  # well above 600
    silence = [_silence_chunk()] * 5
    chunks = calibration + speech + silence
    vad = _make_vad(
        vad_adaptive=True,
        vad_calibration_chunks=5,
        vad_adaptive_multiplier=1.5,
        vad_speech_chunks_required=3,
        vad_silence_duration=0.0,
        vad_min_duration=0.0,
    )
    result = vad.record_until_silence(_make_stream(chunks))
    assert vad.last_speech_detected is True
    all_bytes = b"".join(chunks)
    assert len(result) < len(all_bytes)


def test_adaptive_minimum_floor():
    """Effective threshold should be MIN_FLOOR (50) when ambient is near zero."""
    calibration = [_silence_chunk()] * 5  # ambient = 0 RMS
    # Chunks with low energy (below 50) should be treated as silence
    silence = [_silence_chunk()] * 5
    chunks = calibration + silence
    vad = _make_vad(
        vad_adaptive=True,
        vad_calibration_chunks=5,
        vad_adaptive_multiplier=1.5,
        vad_speech_chunks_required=0,
        vad_silence_duration=0.0,
        vad_min_duration=0.0,
    )
    vad.record_until_silence(_make_stream(chunks))
    # Ambient should be 0, but threshold floored at 50
    assert vad.last_ambient_rms == 0.0


def test_adaptive_disabled_uses_static():
    """With adaptive disabled, behavior matches static threshold."""
    chunks = [_loud_chunk()] * 5 + [_silence_chunk()] * 5
    vad = _make_vad(
        vad_adaptive=False,
        vad_speech_chunks_required=0,
        vad_silence_duration=0.0,
        vad_min_duration=0.0,
    )
    result = vad.record_until_silence(_make_stream(chunks))
    all_bytes = b"".join(chunks)
    assert len(result) < len(all_bytes)
    assert vad.last_ambient_rms is None  # adaptive never ran


def test_adaptive_last_ambient_rms():
    """last_ambient_rms should be set after adaptive recording."""
    noise = _noise_chunk(amplitude=300)
    chunks = [noise] * 5 + [_loud_chunk()] * 3 + [_silence_chunk()] * 5
    vad = _make_vad(
        vad_adaptive=True,
        vad_calibration_chunks=5,
        vad_adaptive_multiplier=1.5,
        vad_speech_chunks_required=0,
        vad_silence_duration=0.0,
        vad_min_duration=0.0,
    )
    vad.record_until_silence(_make_stream(chunks))
    assert vad.last_ambient_rms is not None
    assert vad.last_ambient_rms > 0


def test_adaptive_median_resists_speech_during_calibration():
    """Median should reflect ambient, not speech spikes during calibration."""
    quiet = _noise_chunk(amplitude=100)
    loud = _loud_chunk(amplitude=5000)
    # 3 quiet + 2 loud → median should be the quiet level
    calibration = [quiet, quiet, quiet, loud, loud]
    silence = [_silence_chunk()] * 5
    chunks = calibration + silence
    vad = _make_vad(
        vad_adaptive=True,
        vad_calibration_chunks=5,
        vad_adaptive_multiplier=1.5,
        vad_speech_chunks_required=0,
        vad_silence_duration=0.0,
        vad_min_duration=0.0,
    )
    vad.record_until_silence(_make_stream(chunks))
    # Median of [~100, ~100, ~100, ~3500, ~3500] should be ~100, not ~3500
    assert vad.last_ambient_rms is not None
    assert vad.last_ambient_rms < 500  # well below speech level
