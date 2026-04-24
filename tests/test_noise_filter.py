"""Tests for the STT noise filter.

Most inputs below are real transcriptions lifted from recent session logs
that reached the intent LLM and wasted tokens.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from speech.noise_filter import is_noise


def test_empty_rejected():
    assert is_noise("").rejected
    assert is_noise("   ").rejected
    assert is_noise(None).rejected


def test_bracket_captions_rejected():
    # Whisper emits these for background audio.
    assert is_noise("(music)").rejected
    assert is_noise("[applause]").rejected
    assert is_noise("(clicking sound)").rejected
    assert is_noise("♪ music ♪").rejected
    assert is_noise("(音楽)").rejected  # Japanese "music"


def test_bracket_captions_reason():
    result = is_noise("(music)")
    assert result.reason == "bracket_only"


def test_short_non_latin_rejected():
    # Russian and Korean one-word transcriptions from the session logs.
    assert is_noise("Можно.").rejected
    assert is_noise("마비요.").rejected


def test_short_non_latin_reason():
    assert is_noise("Можно.").reason == "non_latin_short"


def test_long_mixed_phrase_allowed():
    # Long enough that a mostly-non-Latin phrase could be real content.
    text = "これは長い日本語の文章です that includes some English"
    assert not is_noise(text).rejected


def test_legit_short_phrase_allowed():
    # "Hi" alone is borderline but "Hi there" should pass.
    assert not is_noise("Hi there").rejected
    assert not is_noise("Yes").rejected  # 3 chars after stripping


def test_too_short_rejected():
    assert is_noise("a").rejected
    assert is_noise("hi").rejected  # 2 chars — under threshold


def test_confidence_gates():
    # Low confidence should reject.
    result = is_noise("This is a valid command", no_speech_prob=0.8)
    assert result.rejected
    assert result.reason == "high_no_speech_prob"

    result = is_noise("This is a valid command", avg_logprob=-1.5)
    assert result.rejected
    assert result.reason == "low_confidence"


def test_confidence_gates_when_good():
    result = is_noise(
        "What are my reminders", no_speech_prob=0.1, avg_logprob=-0.3
    )
    assert not result.rejected


def test_real_commands_pass():
    # These are real commands from session logs that must keep routing.
    commands = [
        "what gnocchi recipes do i have",
        "add it to the grocery list",
        "set a timer for seven minutes",
        "remind me to take out the trash in 10 minutes",
        "yes, please",
        "can you recommend a gnocchi recipe",
        "clear the shopping list",
        "remove those ingredients from the grocery list",
    ]
    for cmd in commands:
        result = is_noise(cmd)
        assert not result.rejected, f"False reject on {cmd!r}: {result.reason}"


def test_interjection_not_rejected():
    # "Wupi!" is short and punctuated — we decided NOT to reject these (risk
    # of catching "Recipes!" or product names). This test locks in that call.
    assert not is_noise("Wupi!").rejected
