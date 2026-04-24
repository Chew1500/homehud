"""Reject transcriptions that are noise, not commands.

STT backends happily transcribe background sounds (music/applause captions,
clicks, single-word interjections, short non-Latin text) into words that then
get routed to the LLM — wasting tokens and occasionally triggering actions.

This filter fires BEFORE routing at both entry points (hardware voice pipeline
and browser /api/voice). Heuristics are deliberately conservative: a false
reject is more annoying than a wasted LLM call, so the rules only match
patterns that are clearly not speech-addressed-to-the-assistant.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional  # noqa: F401

# Rejection thresholds. Centralized so the hardware and browser paths apply
# identical gates. The hardware path historically used config-overridable
# thresholds; those still work — pass them in explicitly if needed.
DEFAULT_NO_SPEECH_THRESHOLD = 0.6
DEFAULT_LOGPROB_THRESHOLD = -1.0

# Bracket-only captions: "(music)", "[applause]", "♪ music ♪", "(音楽)".
# Match any sequence of bracketed content with nothing meaningful outside.
_BRACKET_ONLY = re.compile(
    r"^\s*(?:[(\[{♪].*?[)\]}♪]\s*)+\s*$"
)

# Punctuation to strip when measuring "effective length".
_STRIPPABLE = re.compile(r"[\s\(\)\[\]\{\}.,!?♪♫♬•·…\"'`]")


@dataclass(frozen=True)
class NoiseResult:
    rejected: bool
    reason: str = ""  # empty when not rejected; telemetry-friendly slug otherwise


def _is_ascii(ch: str) -> bool:
    return ord(ch) < 128


def is_noise(
    text: str,
    no_speech_prob: Optional[float] = None,
    avg_logprob: Optional[float] = None,
    no_speech_threshold: float = DEFAULT_NO_SPEECH_THRESHOLD,
    logprob_threshold: float = DEFAULT_LOGPROB_THRESHOLD,
) -> NoiseResult:
    """Decide whether `text` should be rejected as noise.

    Confidence scores are optional — callers that don't have them (e.g. STT
    backends that don't expose logprobs) still get the text-level heuristics.
    """
    if text is None:
        return NoiseResult(True, "empty")

    stripped = text.strip()
    if not stripped:
        return NoiseResult(True, "empty")

    # Bracket-only captions: "(music)", "[applause]", etc.
    if _BRACKET_ONLY.match(stripped):
        return NoiseResult(True, "bracket_only")

    # Effective-length test: drop brackets and punctuation, then check length.
    effective = _STRIPPABLE.sub("", stripped)
    if len(effective) < 3:
        return NoiseResult(True, "too_short")

    # Short non-Latin fragments ("Можно", "마비요"). Long multilingual phrases
    # (≥20 chars effective) pass through — they might be real content.
    if len(effective) < 20:
        non_ascii = sum(1 for ch in effective if not _is_ascii(ch))
        if non_ascii / len(effective) > 0.5:
            return NoiseResult(True, "non_latin_short")

    # STT confidence gates — mirror the hardware-path thresholds so the
    # browser path applies them too.
    if no_speech_prob is not None and no_speech_prob > no_speech_threshold:
        return NoiseResult(True, "high_no_speech_prob")
    if avg_logprob is not None and avg_logprob < logprob_threshold:
        return NoiseResult(True, "low_confidence")

    return NoiseResult(False)
