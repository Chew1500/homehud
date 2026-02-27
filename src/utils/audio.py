"""Shared audio utilities used across speech backends."""

import numpy as np


def resample_to_16k(pcm: bytes, source_rate: int) -> bytes:
    """Resample PCM int16 from source_rate to 16kHz using linear interpolation.

    Args:
        pcm: Raw PCM bytes (int16, little-endian).
        source_rate: Source sample rate in Hz (e.g. 22050, 24000).

    Returns:
        Resampled PCM bytes at 16kHz.
    """
    samples = np.frombuffer(pcm, dtype=np.int16).astype(np.float32)
    duration = len(samples) / source_rate
    target_len = int(duration * 16000)

    source_times = np.linspace(0, duration, len(samples), endpoint=False)
    target_times = np.linspace(0, duration, target_len, endpoint=False)
    resampled = np.interp(target_times, source_times, samples)

    return resampled.clip(-32768, 32767).astype(np.int16).tobytes()
