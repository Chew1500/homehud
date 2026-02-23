"""Hardware audio backend using sounddevice.

Captures audio from a real microphone and plays back through speakers.
Only used on the Raspberry Pi — sounddevice is not required for local dev.
"""

import logging
import queue
import sys
from collections.abc import Generator

from audio.base import BaseAudio

log = logging.getLogger(__name__)


def _import_sounddevice():
    """Import sounddevice with aarch64 Python 3.11 find_library workaround.

    ctypes.util.find_library is broken on aarch64 Python <3.12.4 — the
    ldconfig parser regex doesn't match the AArch64 tag format.
    See: https://github.com/python/cpython/issues/112417
    """
    import ctypes.util
    import platform

    if platform.machine() != "aarch64" or sys.version_info >= (3, 12, 4):
        import sounddevice

        return sounddevice

    _orig = ctypes.util.find_library

    def _patched(name):
        result = _orig(name)
        if result is None and name == "portaudio":
            return "libportaudio.so.2"
        return result

    ctypes.util.find_library = _patched
    try:
        import sounddevice

        return sounddevice
    finally:
        ctypes.util.find_library = _orig


class HardwareAudio(BaseAudio):
    """Real audio I/O via sounddevice."""

    def __init__(self, config: dict):
        super().__init__(
            sample_rate=config.get("audio_sample_rate", 16000),
            channels=config.get("audio_channels", 1),
        )
        try:
            self._sd = _import_sounddevice()
        except (ImportError, OSError) as e:
            raise RuntimeError(
                "sounddevice is required for hardware audio mode. "
                "Install it with: pip install sounddevice\n"
                "On Raspberry Pi, also ensure: sudo apt-get install libportaudio2"
            ) from e
        self._device = self._parse_device(config.get("audio_device"))

        # Validate device at startup — fail fast with helpful message
        try:
            info = self._sd.query_devices(self._device, kind="input")
        except (self._sd.PortAudioError, ValueError) as e:
            try:
                available = str(self._sd.query_devices())
            except Exception:
                available = "(unable to list devices)"
            raise RuntimeError(
                f"No usable audio input device (queried {self._device!r}): {e}\n"
                f"Available devices:\n{available}\n"
                "Set HUD_AUDIO_DEVICE in .env to a valid device index. "
                "Run 'python -m sounddevice' to list devices."
            ) from e

        log.info(
            "HardwareAudio initialized: %dHz, %dch, device=%r (%s)",
            self.sample_rate, self.channels, self._device, info["name"],
        )

    @staticmethod
    def _parse_device(value):
        """Parse device config: None, integer index, or string name."""
        if value is None:
            return None
        try:
            return int(value)
        except ValueError:
            return value  # string name/substring for sounddevice

    def stream(self, chunk_duration_ms: int = 80) -> Generator[bytes, None, None]:
        """Yield PCM chunks from the microphone continuously."""
        chunk_samples = self.sample_rate * chunk_duration_ms // 1000
        q: queue.Queue[bytes] = queue.Queue()

        def callback(indata, frames, time_info, status):
            if status:
                log.warning("Stream status: %s", status)
            q.put(bytes(indata))

        stream = self._sd.InputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype="int16",
            blocksize=chunk_samples,
            callback=callback,
            device=self._device,
        )
        log.info("Hardware audio stream started (%dms chunks)", chunk_duration_ms)
        try:
            stream.start()
            while True:
                try:
                    yield q.get(timeout=1.0)
                except queue.Empty:
                    continue
        finally:
            stream.stop()
            stream.close()
            log.info("Hardware audio stream stopped.")

    def record(self, duration: float) -> bytes:
        """Record from the microphone for the given duration."""
        num_frames = int(self.sample_rate * duration)
        log.info(f"Recording {duration}s from mic...")
        audio = self._sd.rec(
            num_frames,
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype="int16",
            device=self._device,
        )
        self._sd.wait()
        return audio.tobytes()

    def play(self, data: bytes) -> None:
        """Play raw PCM data through the speakers."""
        import numpy as np

        audio = np.frombuffer(data, dtype=np.int16)
        if self.channels > 1:
            audio = audio.reshape(-1, self.channels)
        log.info(f"Playing {len(data)} bytes of audio...")
        self._sd.play(audio, samplerate=self.sample_rate, device=self._device)
        self._sd.wait()

    def close(self) -> None:
        """Stop any active playback/recording."""
        self._sd.stop()
        log.info("HardwareAudio closed.")
