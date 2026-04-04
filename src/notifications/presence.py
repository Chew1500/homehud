"""Presence detection via ambient RMS energy from audio stream.

Piggybacks on the idle wake-word audio stream. Tracks a rolling window
of RMS readings to estimate whether someone is in the room.
"""

from __future__ import annotations

import time
from collections import deque

import numpy as np


def rms(chunk: bytes) -> float:
    """Compute RMS energy of a PCM int16 audio chunk."""
    samples = np.frombuffer(chunk, dtype=np.int16)
    if len(samples) == 0:
        return 0.0
    return float(np.sqrt(np.mean(samples.astype(np.float64) ** 2)))


class PresenceTracker:
    """Tracks room occupancy via ambient RMS energy from audio chunks.

    Called per audio chunk (~80ms) during the idle wake-word listening loop.
    Uses a rolling window: if RMS exceeded a low threshold at any point
    in the last N seconds, the room is considered "occupied."

    The threshold (default 200) is well below the speech detection threshold
    (500+) but above the noise floor of an empty room (~50-100). This detects
    ambient human activity: footsteps, chair creaks, typing, breathing.
    """

    def __init__(self, config: dict) -> None:
        self._threshold = config.get("presence_rms_threshold", 200)
        self._window = config.get("presence_window_seconds", 300)
        self._active_timestamps: deque[float] = deque()

    def update(self, rms_value: float) -> None:
        """Record an RMS reading. Called per audio chunk."""
        now = time.monotonic()
        # Prune old entries
        cutoff = now - self._window
        while self._active_timestamps and self._active_timestamps[0] < cutoff:
            self._active_timestamps.popleft()
        # Record if above threshold
        if rms_value >= self._threshold:
            self._active_timestamps.append(now)

    def is_present(self) -> bool:
        """Return True if someone appears to be in the room."""
        now = time.monotonic()
        cutoff = now - self._window
        while self._active_timestamps and self._active_timestamps[0] < cutoff:
            self._active_timestamps.popleft()
        return len(self._active_timestamps) > 0
