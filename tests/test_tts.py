"""Tests for TTS backends."""

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from speech.mock_tts import MockTTS
from speech.piper_tts import _ensure_model, _is_model_name, _model_name_to_hf_url


def _make_config(**overrides):
    config = {"tts_mode": "mock", "tts_mock_duration": 2.0}
    config.update(overrides)
    return config


# --- MockTTS tests ---


class TestMockTTS:
    def test_default_duration(self):
        """MockTTS returns 2 seconds of silence by default."""
        tts = MockTTS(_make_config())
        pcm = tts.synthesize("hello world")
        # 16kHz * 2s * 2 bytes = 64000
        assert len(pcm) == 64000
        assert pcm == b"\x00\x00" * 32000

    def test_custom_duration(self):
        """MockTTS respects custom duration config."""
        tts = MockTTS(_make_config(tts_mock_duration=0.5))
        pcm = tts.synthesize("short")
        # 16kHz * 0.5s * 2 bytes = 16000
        assert len(pcm) == 16000

    def test_empty_string(self):
        """MockTTS handles empty string input."""
        tts = MockTTS(_make_config())
        pcm = tts.synthesize("")
        assert len(pcm) == 64000

    def test_close_is_noop(self):
        """MockTTS.close() doesn't raise."""
        tts = MockTTS(_make_config())
        tts.close()


class TestTTSFactory:
    def test_factory_returns_mock_by_default(self):
        """get_tts returns MockTTS for 'mock' mode."""
        from speech import get_tts
        tts = get_tts(_make_config())
        assert isinstance(tts, MockTTS)

    def test_factory_returns_mock_for_unknown_mode(self):
        """get_tts falls back to MockTTS for unknown modes."""
        from speech import get_tts
        tts = get_tts(_make_config(tts_mode="unknown"))
        assert isinstance(tts, MockTTS)


# --- Resampling tests ---


class TestPiperResampling:
    def _get_resample(self):
        """Import the static resampling method."""
        from speech.piper_tts import PiperTTS
        return PiperTTS._resample_to_16k

    def test_22050_to_16000_produces_correct_length(self):
        """Resampling 22050Hz to 16kHz should produce correct sample count."""
        resample = self._get_resample()
        source_rate = 22050
        duration = 1.0  # 1 second
        num_samples = int(source_rate * duration)
        # Generate a simple sine wave
        t = np.linspace(0, duration, num_samples, endpoint=False)
        samples = (np.sin(2 * np.pi * 440 * t) * 16000).astype(np.int16)
        pcm_in = samples.tobytes()

        pcm_out = resample(pcm_in, source_rate)

        # Output should be ~16000 samples * 2 bytes = 32000 bytes
        expected_samples = int(duration * 16000)
        assert len(pcm_out) == expected_samples * 2

    def test_identity_resample_at_16k(self):
        """Resampling from 16kHz to 16kHz should preserve length."""
        resample = self._get_resample()
        num_samples = 16000
        samples = np.zeros(num_samples, dtype=np.int16)
        pcm_in = samples.tobytes()

        pcm_out = resample(pcm_in, 16000)

        assert len(pcm_out) == len(pcm_in)


# --- Piper model resolution tests ---


class TestPiperModelResolution:
    """Tests for model name detection and URL construction."""

    def test_is_model_name_simple(self):
        assert _is_model_name("en_US-lessac-medium") is True

    def test_is_model_name_underscore_voice(self):
        assert _is_model_name("en_GB-alba-medium") is True

    def test_is_model_name_onnx_extension(self):
        assert _is_model_name("model.onnx") is False

    def test_is_model_name_relative_path(self):
        assert _is_model_name("models/tts/model.onnx") is False

    def test_is_model_name_absolute_path(self):
        assert _is_model_name("/opt/homehud/models/model.onnx") is False

    def test_url_standard(self):
        result = _model_name_to_hf_url("en_US-lessac-medium")
        assert result == "en/en_US/lessac/medium/en_US-lessac-medium"

    def test_url_different_language(self):
        result = _model_name_to_hf_url("de_DE-thorsten-high")
        assert result == "de/de_DE/thorsten/high/de_DE-thorsten-high"

    def test_url_multi_part_voice(self):
        result = _model_name_to_hf_url("en_US-amy-low-medium")
        assert result == "en/en_US/amy-low/medium/en_US-amy-low-medium"

    def test_url_invalid_too_few_parts(self):
        with pytest.raises(ValueError, match="Invalid Piper model name"):
            _model_name_to_hf_url("en_US-lessac")

    def test_url_invalid_single_part(self):
        with pytest.raises(ValueError, match="Invalid Piper model name"):
            _model_name_to_hf_url("lessac")


class TestEnsureModelFilePath:
    """Tests for _ensure_model with file paths."""

    def test_nonexistent_file_raises(self):
        with pytest.raises(FileNotFoundError, match="Piper model not found"):
            _ensure_model("/nonexistent/path/model.onnx")

    def test_existing_absolute_path(self, tmp_path):
        model_file = tmp_path / "voice.onnx"
        model_file.write_bytes(b"fake")
        result = _ensure_model(str(model_file))
        assert result == model_file

    def test_empty_value_raises(self):
        with pytest.raises(ValueError, match="tts_piper_model config is required"):
            _ensure_model("")


class TestEnsureModelDownload:
    """Tests for _ensure_model with model names (mocked downloads)."""

    def test_cached_model_skips_download(self, tmp_path, monkeypatch):
        """If both .onnx and .onnx.json exist, no download happens."""
        monkeypatch.setattr("speech.piper_tts._MODELS_DIR", tmp_path)
        onnx = tmp_path / "en_US-lessac-medium.onnx"
        json = tmp_path / "en_US-lessac-medium.onnx.json"
        onnx.write_bytes(b"model")
        json.write_bytes(b"config")

        # Should not attempt any download
        result = _ensure_model("en_US-lessac-medium")
        assert result == onnx

    def test_missing_json_triggers_download(self, tmp_path, monkeypatch):
        """If .onnx exists but .onnx.json is missing, download the json."""
        monkeypatch.setattr("speech.piper_tts._MODELS_DIR", tmp_path)
        onnx = tmp_path / "en_US-lessac-medium.onnx"
        onnx.write_bytes(b"model")

        downloads = []

        def fake_download(url, dest):
            downloads.append(url)
            dest.write_bytes(b"downloaded")

        monkeypatch.setattr("speech.piper_tts._download_file", fake_download)

        result = _ensure_model("en_US-lessac-medium")
        assert result == onnx
        assert len(downloads) == 1
        assert downloads[0].endswith(".onnx.json")

    def test_missing_both_triggers_two_downloads(self, tmp_path, monkeypatch):
        """If neither file exists, download both."""
        monkeypatch.setattr("speech.piper_tts._MODELS_DIR", tmp_path)

        downloads = []

        def fake_download(url, dest):
            downloads.append(url)
            dest.write_bytes(b"downloaded")

        monkeypatch.setattr("speech.piper_tts._download_file", fake_download)

        result = _ensure_model("en_US-lessac-medium")
        assert result == tmp_path / "en_US-lessac-medium.onnx"
        assert len(downloads) == 2
        assert any(u.endswith(".onnx") and not u.endswith(".onnx.json") for u in downloads)
        assert any(u.endswith(".onnx.json") for u in downloads)
