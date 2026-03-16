"""Tests for the volume control feature."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from audio.mock_audio import MockAudio
from features.volume import VolumeFeature


@pytest.fixture
def audio():
    return MockAudio({"audio_mock_dir": "/tmp/homehud_test_audio"})


@pytest.fixture
def feature(audio):
    return VolumeFeature({}, audio=audio)


# --- Regex matching ---


@pytest.mark.parametrize(
    "text",
    [
        "speak up",
        "speak up a bit",
        "a bit louder",
        "a little quieter",
        "turn it up",
        "turn it down",
        "too loud",
        "too quiet",
        "volume to 50%",
        "set volume to 80",
        "what's the volume",
        "way louder",
        "louder",
        "quieter",
        "turn down",
    ],
)
def test_matches_positive(feature, text):
    assert feature.matches(text)


@pytest.mark.parametrize(
    "text",
    [
        "what's the weather",
        "add milk to the grocery list",
        "set a reminder",
        "hello",
        "tell me a joke",
    ],
)
def test_matches_negative(feature, text):
    assert not feature.matches(text)


# --- Relative adjustments ---


def test_handle_up_medium(feature, audio):
    audio.set_volume(50)
    response = feature.handle("louder")
    assert "70%" in response
    assert audio.get_volume() == 70


def test_handle_down_medium(feature, audio):
    audio.set_volume(50)
    response = feature.handle("quieter")
    assert "30%" in response
    assert audio.get_volume() == 30


def test_handle_up_small(feature, audio):
    audio.set_volume(50)
    response = feature.handle("a bit louder")
    assert "60%" in response
    assert audio.get_volume() == 60


def test_handle_up_large(feature, audio):
    audio.set_volume(50)
    response = feature.handle("way louder")
    assert "80%" in response
    assert audio.get_volume() == 80


def test_handle_down_small(feature, audio):
    audio.set_volume(50)
    response = feature.handle("a little quieter")
    assert "40%" in response
    assert audio.get_volume() == 40


def test_handle_down_large(feature, audio):
    audio.set_volume(50)
    response = feature.handle("a lot quieter")
    assert "20%" in response
    assert audio.get_volume() == 20


# --- Absolute ---


def test_handle_set_absolute(feature, audio):
    response = feature.handle("volume to 75%")
    assert "75%" in response
    assert audio.get_volume() == 75


def test_handle_set_absolute_with_set(feature, audio):
    response = feature.handle("set volume to 30")
    assert "30%" in response
    assert audio.get_volume() == 30


# --- Edge cases ---


def test_at_max(feature, audio):
    audio.set_volume(100)
    response = feature.handle("louder")
    assert "max" in response.lower() or "100%" in response


def test_at_min(feature, audio):
    audio.set_volume(0)
    response = feature.handle("quieter")
    assert "quiet" in response.lower() or "0%" in response or "min" in response.lower()


def test_clamp_above_100(feature, audio):
    audio.set_volume(90)
    response = feature.handle("way louder")
    assert audio.get_volume() == 100
    assert "100%" in response


def test_clamp_below_0(feature, audio):
    audio.set_volume(10)
    response = feature.handle("way quieter")
    assert audio.get_volume() == 0
    assert "0%" in response


# --- Query ---


def test_handle_query(feature, audio):
    audio.set_volume(65)
    response = feature.handle("what's the volume")
    assert "65%" in response


# --- Execute (LLM intent path) ---


def test_execute_adjust_up(feature, audio):
    audio.set_volume(50)
    response = feature.execute("adjust_volume", {"direction": "up", "magnitude": "small"})
    assert "60%" in response
    assert audio.get_volume() == 60


def test_execute_adjust_down(feature, audio):
    audio.set_volume(50)
    response = feature.execute("adjust_volume", {"direction": "down", "magnitude": "large"})
    assert "20%" in response
    assert audio.get_volume() == 20


def test_execute_set_volume(feature, audio):
    response = feature.execute("set_volume", {"level": 42})
    assert "42%" in response
    assert audio.get_volume() == 42


def test_execute_query(feature, audio):
    audio.set_volume(55)
    response = feature.execute("query", {})
    assert "55%" in response


# --- Response variation ---


def test_small_delta_casual_tone(feature, audio):
    audio.set_volume(50)
    response = feature.handle("a bit louder")
    # Small delta responses should not contain "crank" or "big jump"
    assert "crank" not in response.lower()
    assert "big jump" not in response.lower()


def test_large_delta_expressive_tone(feature, audio):
    audio.set_volume(50)
    response = feature.handle("way louder")
    # Large delta response — just verify it has the right level
    assert "80%" in response


# --- Action schema ---


def test_action_schema(feature):
    schema = feature.action_schema
    assert "adjust_volume" in schema
    assert "set_volume" in schema
    assert "query" in schema


# --- speak up / too quiet direction detection ---


def test_speak_up(feature, audio):
    audio.set_volume(50)
    feature.handle("speak up")
    assert audio.get_volume() > 50


def test_too_loud_goes_down(feature, audio):
    audio.set_volume(50)
    feature.handle("too loud")
    assert audio.get_volume() < 50


def test_too_quiet_goes_up(feature, audio):
    audio.set_volume(50)
    feature.handle("too quiet")
    assert audio.get_volume() > 50
