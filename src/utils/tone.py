"""Tone generation for audio feedback (e.g. wake word acknowledgment)."""

import numpy as np


def generate_silence(duration_ms: int, sample_rate: int = 16000) -> bytes:
    """Return `duration_ms` of silence as PCM bytes."""
    num_samples = int(sample_rate * duration_ms / 1000)
    return np.zeros(num_samples, dtype=np.int16).tobytes()


def generate_alarm(
    sample_rate: int = 16000,
    beep_count: int = 4,
    beep_freq: int = 1000,
    beep_duration_ms: int = 220,
    gap_duration_ms: int = 150,
    volume: float = 0.55,
) -> bytes:
    """Generate a multi-beep alarm pattern for timer fires.

    Four short beeps with gaps — distinct from the single-beep wake ack and
    long enough to be noticed without being jarring.
    """
    beep = generate_tone(
        freq=beep_freq,
        duration_ms=beep_duration_ms,
        sample_rate=sample_rate,
        volume=volume,
    )
    gap = generate_silence(gap_duration_ms, sample_rate)
    parts: list[bytes] = []
    for i in range(beep_count):
        parts.append(beep)
        if i < beep_count - 1:
            parts.append(gap)
    return b"".join(parts)


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
