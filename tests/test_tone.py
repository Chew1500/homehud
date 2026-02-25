"""Tests for tone generation utility."""

import sys
from pathlib import Path

import numpy as np

# Add src to path so imports work
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from utils.tone import generate_tone


def test_tone_byte_length():
    """Generated tone should have correct byte length for duration and sample rate."""
    data = generate_tone(freq=880, duration_ms=150, sample_rate=16000)
    expected_samples = int(16000 * 150 / 1000)  # 2400
    expected_bytes = expected_samples * 2  # int16 = 2 bytes
    assert len(data) == expected_bytes


def test_tone_valid_int16_pcm():
    """Generated tone should be valid int16 PCM data."""
    data = generate_tone(freq=440, duration_ms=100, sample_rate=16000)
    samples = np.frombuffer(data, dtype=np.int16)
    # All values should be within int16 range
    assert samples.max() <= 32767
    assert samples.min() >= -32768
    # Should not be all zeros (it's a sine wave)
    assert np.any(samples != 0)


def test_tone_fade_envelope():
    """Generated tone should have fade-in/out (first and last samples near zero)."""
    data = generate_tone(freq=880, duration_ms=150, sample_rate=16000, volume=1.0)
    samples = np.frombuffer(data, dtype=np.int16)
    # First sample should be near zero (fade-in starts at 0)
    assert abs(samples[0]) < 100
    # Last sample should be near zero (fade-out ends at 0)
    assert abs(samples[-1]) < 100
    # Middle region should have significant amplitude (check a window to avoid zero-crossings)
    mid = len(samples) // 2
    window = samples[mid - 10 : mid + 10]
    assert np.abs(window).max() > 1000


def test_tone_volume_scaling():
    """Lower volume should produce smaller amplitude."""
    loud = generate_tone(freq=440, duration_ms=100, volume=1.0)
    quiet = generate_tone(freq=440, duration_ms=100, volume=0.25)
    loud_samples = np.frombuffer(loud, dtype=np.int16)
    quiet_samples = np.frombuffer(quiet, dtype=np.int16)
    assert np.abs(loud_samples).max() > np.abs(quiet_samples).max()


def test_tone_different_sample_rates():
    """Tone should work with different sample rates."""
    for sr in [8000, 16000, 44100]:
        data = generate_tone(freq=440, duration_ms=100, sample_rate=sr)
        expected_samples = int(sr * 100 / 1000)
        assert len(data) == expected_samples * 2
