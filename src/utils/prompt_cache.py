"""Pre-synthesized TTS prompt cache for instant playback."""

import logging
import random
import struct

from speech.base_tts import BaseTTS

log = logging.getLogger("home-hud.prompt-cache")


class PromptCache:
    """Pre-synthesizes a list of phrases into PCM bytes at construction time.

    Stores the results and exposes pick() for random selection.
    Gracefully skips phrases that fail TTS; falls back to silence if all fail.
    """

    def __init__(self, tts: BaseTTS, phrases: list[str], sample_rate: int = 16000):
        self._clips: list[bytes] = []
        for phrase in phrases:
            try:
                pcm = tts.synthesize(phrase)
                if pcm:
                    self._clips.append(pcm)
            except Exception:
                log.warning("Failed to pre-synthesize %r, skipping", phrase)
        if not self._clips:
            log.warning("All phrases failed, using silence fallback")
            # 0.1s of silence at the given sample rate (16-bit samples)
            silence_samples = int(sample_rate * 0.1)
            self._clips.append(struct.pack(f"<{silence_samples}h", *([0] * silence_samples)))

    def pick(self) -> bytes:
        """Return a random pre-synthesized clip."""
        return random.choice(self._clips)
