"""Tests for the ElevenLabs cloud STT backend."""

import io
import sys
import wave
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest

from speech.elevenlabs_stt import _add_wav_header

# -- WAV header --


def test_wav_header_valid():
    """The generated WAV header should produce a valid file decodable by wave."""
    pcm = b"\x00\x00" * 16000  # 1 second of silence at 16kHz 16-bit mono
    wav_data = _add_wav_header(pcm)

    buf = io.BytesIO(wav_data)
    with wave.open(buf, "rb") as wf:
        assert wf.getnchannels() == 1
        assert wf.getsampwidth() == 2  # 16-bit = 2 bytes
        assert wf.getframerate() == 16000
        assert wf.getnframes() == 16000


def test_wav_header_length():
    """WAV header should be exactly 44 bytes."""
    pcm = b"\x01\x02" * 100
    wav_data = _add_wav_header(pcm)
    assert len(wav_data) == 44 + len(pcm)


def test_wav_header_empty_pcm():
    """WAV header should handle empty PCM data."""
    wav_data = _add_wav_header(b"")
    buf = io.BytesIO(wav_data)
    with wave.open(buf, "rb") as wf:
        assert wf.getnframes() == 0


# -- Init --


def test_missing_api_key_raises():
    """Should raise ValueError when ELEVENLABS_API_KEY is missing."""
    from speech.elevenlabs_stt import ElevenLabsSTT
    with pytest.raises(ValueError, match="ELEVENLABS_API_KEY"):
        ElevenLabsSTT({"elevenlabs_api_key": ""})


def test_missing_api_key_none_raises():
    from speech.elevenlabs_stt import ElevenLabsSTT
    with pytest.raises(ValueError, match="ELEVENLABS_API_KEY"):
        ElevenLabsSTT({})


def _mock_elevenlabs(monkeypatch):
    """Inject a mock elevenlabs SDK into sys.modules and return the mock client."""
    mock_client_instance = MagicMock()
    mock_elevenlabs_client = MagicMock()
    mock_elevenlabs_client.ElevenLabs.return_value = mock_client_instance

    fake_elevenlabs = MagicMock()
    fake_elevenlabs.client = mock_elevenlabs_client
    monkeypatch.setitem(sys.modules, "elevenlabs", fake_elevenlabs)
    monkeypatch.setitem(sys.modules, "elevenlabs.client", mock_elevenlabs_client)

    return mock_client_instance


def test_init_default_model(monkeypatch):
    """Default model should be scribe_v1."""
    _mock_elevenlabs(monkeypatch)
    from speech.elevenlabs_stt import ElevenLabsSTT
    stt = ElevenLabsSTT({"elevenlabs_api_key": "test-key"})
    assert stt._model == "scribe_v1"


def test_init_custom_model(monkeypatch):
    """Custom model should be configurable."""
    _mock_elevenlabs(monkeypatch)
    from speech.elevenlabs_stt import ElevenLabsSTT
    stt = ElevenLabsSTT({
        "elevenlabs_api_key": "test-key",
        "stt_elevenlabs_model": "scribe_v2",
    })
    assert stt._model == "scribe_v2"


# -- Transcription --


def test_transcribe_with_confidence(monkeypatch):
    """Should call the ElevenLabs API and return a TranscriptionResult."""
    mock_client = _mock_elevenlabs(monkeypatch)

    mock_result = MagicMock()
    mock_result.text = "  track the movie Pulp Fiction  "
    mock_client.speech_to_text.convert.return_value = mock_result

    from speech.elevenlabs_stt import ElevenLabsSTT
    stt = ElevenLabsSTT({"elevenlabs_api_key": "test-key"})
    pcm = b"\x00\x00" * 1600  # 0.1s of audio
    result = stt.transcribe_with_confidence(pcm)

    assert result.text == "track the movie Pulp Fiction"
    assert result.no_speech_prob == 0.0
    assert result.avg_logprob == 0.0

    # Verify API was called with correct model
    call_kwargs = mock_client.speech_to_text.convert.call_args
    assert call_kwargs.kwargs["model_id"] == "scribe_v1"
    assert call_kwargs.kwargs["file"] is not None


def test_transcribe_returns_text(monkeypatch):
    """transcribe() should return just the text string."""
    mock_client = _mock_elevenlabs(monkeypatch)

    mock_result = MagicMock()
    mock_result.text = "hello world"
    mock_client.speech_to_text.convert.return_value = mock_result

    from speech.elevenlabs_stt import ElevenLabsSTT
    stt = ElevenLabsSTT({"elevenlabs_api_key": "test-key"})
    text = stt.transcribe(b"\x00\x00" * 1600)
    assert text == "hello world"


# -- Factory integration --


def test_factory_returns_elevenlabs_stt(monkeypatch):
    """get_stt with mode=elevenlabs should return ElevenLabsSTT."""
    _mock_elevenlabs(monkeypatch)

    from speech import get_stt
    from speech.elevenlabs_stt import ElevenLabsSTT

    config = {"stt_mode": "elevenlabs", "elevenlabs_api_key": "test-key"}
    stt = get_stt(config)
    assert isinstance(stt, ElevenLabsSTT)
