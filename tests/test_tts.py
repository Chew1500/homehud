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


def _make_audio_samples(duration=0.5, rate=24000):
    """Generate a float32 sine wave for testing."""
    num_samples = int(rate * duration)
    t = np.linspace(0, duration, num_samples, endpoint=False)
    return (np.sin(2 * np.pi * 440 * t)).astype(np.float32)


class TestKokoroTTS:
    """Tests for KokoroTTS with mocked kokoro_onnx.Kokoro."""

    def _build(self, monkeypatch, config_overrides=None, create_return=None,
               stream_chunks=None):
        """Helper: construct a KokoroTTS with mocked dependencies."""
        # Mock espeak-ng as present
        monkeypatch.setattr("shutil.which", lambda cmd: "/usr/bin/espeak-ng")

        # Default: 0.5s of sine wave at 24kHz
        if create_return is None:
            create_return = (_make_audio_samples(0.5), 24000)

        # Default stream: same as create but as async generator chunks
        if stream_chunks is None:
            stream_chunks = [create_return]

        # Build mock Kokoro instance
        mock_kokoro_instance = MagicMock()
        mock_kokoro_instance.create.return_value = create_return

        async def _fake_stream(*args, **kwargs):
            for chunk in stream_chunks:
                yield chunk

        mock_kokoro_instance.create_stream = _fake_stream

        # Mock from_session class method
        mock_kokoro_cls = MagicMock()
        mock_kokoro_cls.from_session.return_value = mock_kokoro_instance

        # Mock onnxruntime
        mock_ort = MagicMock()
        mock_session_opts = MagicMock()
        mock_ort.SessionOptions.return_value = mock_session_opts
        mock_ort.GraphOptimizationLevel.ORT_ENABLE_ALL = 99
        mock_ort.InferenceSession.return_value = MagicMock()

        # Mock the kokoro_onnx module
        fake_kokoro_onnx = MagicMock()
        fake_kokoro_onnx.Kokoro = mock_kokoro_cls
        monkeypatch.setitem(sys.modules, "kokoro_onnx", fake_kokoro_onnx)
        monkeypatch.setitem(sys.modules, "onnxruntime", mock_ort)

        config = _make_config(
            tts_mode="kokoro",
            tts_kokoro_voice="af_heart",
            tts_kokoro_speed=1.0,
            tts_kokoro_lang="a",
            tts_kokoro_model="models/kokoro-v1.0.int8.onnx",
            tts_kokoro_voices="models/voices-v1.0.bin",
        )
        if config_overrides:
            config.update(config_overrides)

        from speech.kokoro_tts import KokoroTTS
        tts = KokoroTTS(config)
        return tts, mock_kokoro_instance

    def test_synthesize_returns_16k_pcm(self, monkeypatch):
        """KokoroTTS.synthesize returns PCM int16 at 16kHz."""
        tts, _ = self._build(monkeypatch)
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
        """KokoroTTS returns silence when create() returns empty samples."""
        tts, _ = self._build(
            monkeypatch,
            create_return=(np.array([], dtype=np.float32), 24000),
        )
        pcm = tts.synthesize("hello")
        assert pcm == b"\x00\x00" * 1600

    def test_close_clears_kokoro(self, monkeypatch):
        """KokoroTTS.close() sets _kokoro to None."""
        tts, _ = self._build(monkeypatch)
        tts.close()
        assert tts._kokoro is None

    def test_missing_espeak_raises(self, monkeypatch):
        """KokoroTTS raises RuntimeError if espeak-ng is not installed."""
        monkeypatch.setattr("shutil.which", lambda cmd: None)

        fake_kokoro_onnx = MagicMock()
        monkeypatch.setitem(sys.modules, "kokoro_onnx", fake_kokoro_onnx)
        monkeypatch.setitem(sys.modules, "onnxruntime", MagicMock())

        from speech.kokoro_tts import KokoroTTS
        with pytest.raises(RuntimeError, match="espeak-ng is required"):
            KokoroTTS(_make_config(tts_mode="kokoro"))

    def test_missing_kokoro_onnx_package_raises(self, monkeypatch):
        """KokoroTTS raises ImportError if kokoro-onnx package is not installed."""
        monkeypatch.setattr("shutil.which", lambda cmd: "/usr/bin/espeak-ng")

        # Remove from sys.modules if cached, and make import fail
        monkeypatch.delitem(sys.modules, "kokoro_onnx", raising=False)
        monkeypatch.delitem(sys.modules, "onnxruntime", raising=False)
        import builtins
        real_import = builtins.__import__

        def fail_kokoro_onnx(name, *args, **kwargs):
            if name in ("kokoro_onnx", "onnxruntime"):
                raise ImportError(f"No module named '{name}'")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fail_kokoro_onnx)

        from speech.kokoro_tts import KokoroTTS
        with pytest.raises(ImportError, match="kokoro-onnx is required"):
            KokoroTTS(_make_config(tts_mode="kokoro"))

    def test_synthesize_stream_yields_per_chunk(self, monkeypatch):
        """KokoroTTS.synthesize_stream() yields one chunk per stream result."""
        # Two separate 0.25s audio segments
        audio1 = _make_audio_samples(0.25)
        audio2 = _make_audio_samples(0.25)
        stream_chunks = [(audio1, 24000), (audio2, 24000)]

        tts, _ = self._build(monkeypatch, stream_chunks=stream_chunks)
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
        """KokoroTTS.synthesize_stream() yields silence when stream has no audio."""
        empty = np.array([], dtype=np.float32)
        tts, _ = self._build(
            monkeypatch,
            stream_chunks=[(empty, 24000)],
        )
        chunks = list(tts.synthesize_stream("hello"))
        assert len(chunks) == 1
        assert chunks[0] == b"\x00\x00" * 1600

    def test_lang_alias_mapping(self, monkeypatch):
        """KokoroTTS maps short lang codes to full codes."""
        tts, mock_kokoro = self._build(monkeypatch, config_overrides={"tts_kokoro_lang": "b"})
        tts.synthesize("test")
        _, kwargs = mock_kokoro.create.call_args
        assert kwargs["lang"] == "en-gb"

    def test_factory_returns_kokoro(self, monkeypatch):
        """get_tts returns KokoroTTS for 'kokoro' mode."""
        # Mock espeak-ng
        monkeypatch.setattr("shutil.which", lambda cmd: "/usr/bin/espeak-ng")

        # Mock kokoro_onnx and onnxruntime modules
        mock_kokoro_cls = MagicMock()
        mock_kokoro_cls.from_session.return_value = MagicMock()
        fake_kokoro_onnx = MagicMock()
        fake_kokoro_onnx.Kokoro = mock_kokoro_cls
        monkeypatch.setitem(sys.modules, "kokoro_onnx", fake_kokoro_onnx)

        mock_ort = MagicMock()
        mock_ort.SessionOptions.return_value = MagicMock()
        mock_ort.GraphOptimizationLevel.ORT_ENABLE_ALL = 99
        mock_ort.InferenceSession.return_value = MagicMock()
        monkeypatch.setitem(sys.modules, "onnxruntime", mock_ort)

        from speech import get_tts
        from speech.kokoro_tts import KokoroTTS
        tts = get_tts(_make_config(tts_mode="kokoro"))
        assert isinstance(tts, KokoroTTS)
