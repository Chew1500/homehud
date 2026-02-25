"""Tone generation for audio feedback (e.g. wake word acknowledgment)."""

import numpy as np


def generate_tone(
    freq: int = 880,
    duration_ms: int = 150,
    sample_rate: int = 16000,
    volume: float = 0.5,
) -> bytes:
    """Generate a sine wave tone as raw PCM bytes (int16, little-endian).

    Includes a short fade-in/out to avoid audible clicks.

    Args:
        freq: Tone frequency in Hz.
        duration_ms: Tone duration in milliseconds.
        sample_rate: Audio sample rate in Hz.
        volume: Volume level 0.0–1.0.

    Returns:
        Raw PCM bytes (int16, little-endian).
    """
    num_samples = int(sample_rate * duration_ms / 1000)
    t = np.linspace(0, duration_ms / 1000, num_samples, endpoint=False)
    wave = np.sin(2 * np.pi * freq * t)

    # Apply fade-in/out (10ms each) to avoid clicks
    fade_samples = int(sample_rate * 0.010)
    if fade_samples > 0 and num_samples >= 2 * fade_samples:
        fade_in = np.linspace(0, 1, fade_samples)
        fade_out = np.linspace(1, 0, fade_samples)
        wave[:fade_samples] *= fade_in
        wave[-fade_samples:] *= fade_out

    # Scale to int16 range and apply volume
    scaled = (wave * volume * 32767).astype(np.int16)
    return scaled.tobytes()
