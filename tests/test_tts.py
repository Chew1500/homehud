"""Tests for TTS backends."""

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from unittest.mock import MagicMock

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

    def test_synthesize_stream_yields_single_chunk(self):
        """MockTTS.synthesize_stream() yields entire result as one chunk (default impl)."""
        tts = MockTTS(_make_config())
        chunks = list(tts.synthesize_stream("hello"))
        assert len(chunks) == 1
        assert chunks[0] == tts.synthesize("hello")


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


class TestResampling:
    def test_22050_to_16000_produces_correct_length(self):
        """Resampling 22050Hz (Piper) to 16kHz should produce correct sample count."""
        from utils.audio import resample_to_16k
        source_rate = 22050
        duration = 1.0  # 1 second
        num_samples = int(source_rate * duration)
        t = np.linspace(0, duration, num_samples, endpoint=False)
        samples = (np.sin(2 * np.pi * 440 * t) * 16000).astype(np.int16)
        pcm_in = samples.tobytes()

        pcm_out = resample_to_16k(pcm_in, source_rate)

        expected_samples = int(duration * 16000)
        assert len(pcm_out) == expected_samples * 2

    def test_24000_to_16000_produces_correct_length(self):
        """Resampling 24000Hz (Kokoro) to 16kHz should produce correct sample count."""
        from utils.audio import resample_to_16k
        source_rate = 24000
        duration = 1.0
        num_samples = int(source_rate * duration)
        t = np.linspace(0, duration, num_samples, endpoint=False)
        samples = (np.sin(2 * np.pi * 440 * t) * 16000).astype(np.int16)
        pcm_in = samples.tobytes()

        pcm_out = resample_to_16k(pcm_in, source_rate)

        expected_samples = int(duration * 16000)
        assert len(pcm_out) == expected_samples * 2

    def test_identity_resample_at_16k(self):
        """Resampling from 16kHz to 16kHz should preserve length."""
        from utils.audio import resample_to_16k
        num_samples = 16000
        samples = np.zeros(num_samples, dtype=np.int16)
        pcm_in = samples.tobytes()

        pcm_out = resample_to_16k(pcm_in, 16000)

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


# --- KokoroTTS tests ---


class _FakeResult:
    """Mimics a kokoro pipeline result with a .audio tensor."""

    def __init__(self, audio_np):
        self.audio = MagicMock()
        self.audio.numpy.return_value = audio_np


class _FakeResultNoAudio:
    """Mimics a kokoro pipeline result with audio=None."""

    audio = None


def _make_fake_pipeline(results):
    """Return a mock KPipeline class whose instances yield results when called."""
    pipeline_instance = MagicMock()
    pipeline_instance.side_effect = lambda *a, **kw: iter(results)
    pipeline_cls = MagicMock(return_value=pipeline_instance)
    return pipeline_cls, pipeline_instance


class TestKokoroTTS:
    """Tests for KokoroTTS with mocked kokoro.KPipeline."""

    def _build(self, monkeypatch, config_overrides=None, pipeline_results=None):
        """Helper: construct a KokoroTTS with mocked dependencies."""
        # Mock espeak-ng as present
        monkeypatch.setattr("shutil.which", lambda cmd: "/usr/bin/espeak-ng")

        # Build fake pipeline
        if pipeline_results is None:
            # 0.5s of sine wave at 24kHz
            t = np.linspace(0, 0.5, 12000, endpoint=False)
            audio_np = (np.sin(2 * np.pi * 440 * t)).astype(np.float32)
            pipeline_results = [_FakeResult(audio_np)]

        pipeline_cls, pipeline_instance = _make_fake_pipeline(pipeline_results)

        # Mock the kokoro module
        fake_kokoro = MagicMock()
        fake_kokoro.KPipeline = pipeline_cls
        monkeypatch.setitem(sys.modules, "kokoro", fake_kokoro)

        config = _make_config(
            tts_mode="kokoro",
            tts_kokoro_voice="af_heart",
            tts_kokoro_speed=1.0,
            tts_kokoro_lang="a",
        )
        if config_overrides:
            config.update(config_overrides)

        from speech.kokoro_tts import KokoroTTS
        tts = KokoroTTS(config)
        return tts, pipeline_instance

    def test_synthesize_returns_16k_pcm(self, monkeypatch):
        """KokoroTTS.synthesize returns PCM int16 at 16kHz."""
        tts, pipeline = self._build(monkeypatch)
        pcm = tts.synthesize("hello world")

        # Should be non-empty PCM bytes
        assert isinstance(pcm, bytes)
        assert len(pcm) > 0
        # Length should be even (int16 = 2 bytes per sample)
        assert len(pcm) % 2 == 0

        # Verify resampled: 0.5s at 24kHz → 0.5s at 16kHz = 8000 samples * 2 bytes
        expected_bytes = 8000 * 2
        assert len(pcm) == expected_bytes

    def test_empty_input_returns_silence(self, monkeypatch):
        """KokoroTTS returns 0.1s silence for empty input."""
        tts, _ = self._build(monkeypatch)
        pcm = tts.synthesize("")
        assert pcm == b"\x00\x00" * 1600

    def test_whitespace_input_returns_silence(self, monkeypatch):
        """KokoroTTS returns 0.1s silence for whitespace-only input."""
        tts, _ = self._build(monkeypatch)
        pcm = tts.synthesize("   ")
        assert pcm == b"\x00\x00" * 1600

    def test_no_audio_results_returns_silence(self, monkeypatch):
        """KokoroTTS returns silence when pipeline yields no audio chunks."""
        tts, _ = self._build(monkeypatch, pipeline_results=[_FakeResultNoAudio()])
        pcm = tts.synthesize("hello")
        assert pcm == b"\x00\x00" * 1600

    def test_close_clears_pipeline(self, monkeypatch):
        """KokoroTTS.close() sets pipeline to None."""
        tts, _ = self._build(monkeypatch)
        tts.close()
        assert tts._pipeline is None

    def test_missing_espeak_raises(self, monkeypatch):
        """KokoroTTS raises RuntimeError if espeak-ng is not installed."""
        monkeypatch.setattr("shutil.which", lambda cmd: None)

        fake_kokoro = MagicMock()
        monkeypatch.setitem(sys.modules, "kokoro", fake_kokoro)

        from speech.kokoro_tts import KokoroTTS
        with pytest.raises(RuntimeError, match="espeak-ng is required"):
            KokoroTTS(_make_config(tts_mode="kokoro"))

    def test_missing_kokoro_package_raises(self, monkeypatch):
        """KokoroTTS raises ImportError if kokoro package is not installed."""
        monkeypatch.setattr("shutil.which", lambda cmd: "/usr/bin/espeak-ng")

        # Remove kokoro from sys.modules if cached, and make import fail
        monkeypatch.delitem(sys.modules, "kokoro", raising=False)
        import builtins
        real_import = builtins.__import__

        def fail_kokoro(name, *args, **kwargs):
            if name == "kokoro":
                raise ImportError("No module named 'kokoro'")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fail_kokoro)

        from speech.kokoro_tts import KokoroTTS
        with pytest.raises(ImportError, match="kokoro is required"):
            KokoroTTS(_make_config(tts_mode="kokoro"))

    def test_synthesize_stream_yields_per_result(self, monkeypatch):
        """KokoroTTS.synthesize_stream() yields one chunk per pipeline result."""
        # Two separate 0.25s audio segments
        t = np.linspace(0, 0.25, 6000, endpoint=False)
        audio1 = (np.sin(2 * np.pi * 440 * t)).astype(np.float32)
        audio2 = (np.sin(2 * np.pi * 880 * t)).astype(np.float32)
        results = [_FakeResult(audio1), _FakeResult(audio2)]

        tts, _ = self._build(monkeypatch, pipeline_results=results)
        chunks = list(tts.synthesize_stream("hello world"))

        assert len(chunks) == 2
        for chunk in chunks:
            assert isinstance(chunk, bytes)
            assert len(chunk) > 0
            assert len(chunk) % 2 == 0

    def test_synthesize_stream_empty_text(self, monkeypatch):
        """KokoroTTS.synthesize_stream() yields silence for empty text."""
        tts, _ = self._build(monkeypatch)
        chunks = list(tts.synthesize_stream(""))
        assert len(chunks) == 1
        assert chunks[0] == b"\x00\x00" * 1600

    def test_synthesize_stream_no_audio_yields_silence(self, monkeypatch):
        """KokoroTTS.synthesize_stream() yields silence when pipeline has no audio."""
        tts, _ = self._build(monkeypatch, pipeline_results=[_FakeResultNoAudio()])
        chunks = list(tts.synthesize_stream("hello"))
        assert len(chunks) == 1
        assert chunks[0] == b"\x00\x00" * 1600

    def test_factory_returns_kokoro(self, monkeypatch):
        """get_tts returns KokoroTTS for 'kokoro' mode."""
        # Mock espeak-ng
        monkeypatch.setattr("shutil.which", lambda cmd: "/usr/bin/espeak-ng")

        # Mock kokoro module
        pipeline_cls = MagicMock(return_value=MagicMock())
        fake_kokoro = MagicMock()
        fake_kokoro.KPipeline = pipeline_cls
        monkeypatch.setitem(sys.modules, "kokoro", fake_kokoro)

        from speech import get_tts
        from speech.kokoro_tts import KokoroTTS
        tts = get_tts(_make_config(tts_mode="kokoro"))
        assert isinstance(tts, KokoroTTS)
