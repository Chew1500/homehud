"""Tests for TTS backends."""

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from unittest.mock import MagicMock

from speech.cached_tts import CachedTTS
from speech.mock_tts import MockTTS


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
        """Resampling 22050Hz to 16kHz should produce correct sample count."""
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


# --- ElevenLabsTTS tests ---


class TestElevenLabsTTS:
    """Tests for ElevenLabsTTS with mocked elevenlabs SDK."""

    def _build(self, monkeypatch, config_overrides=None, convert_chunks=None,
               stream_chunks=None):
        """Helper: construct an ElevenLabsTTS with mocked SDK."""
        if convert_chunks is None:
            convert_chunks = [b"\x01\x00" * 1600]
        if stream_chunks is None:
            stream_chunks = [b"\x01\x00" * 800, b"\x02\x00" * 800]

        mock_client_instance = MagicMock()
        mock_client_instance.text_to_speech.convert.return_value = iter(convert_chunks)
        mock_client_instance.text_to_speech.stream.return_value = iter(stream_chunks)

        mock_elevenlabs_client = MagicMock()
        mock_elevenlabs_client.ElevenLabs.return_value = mock_client_instance

        fake_elevenlabs = MagicMock()
        fake_elevenlabs.client = mock_elevenlabs_client
        monkeypatch.setitem(sys.modules, "elevenlabs", fake_elevenlabs)
        monkeypatch.setitem(sys.modules, "elevenlabs.client", mock_elevenlabs_client)

        config = _make_config(
            tts_mode="elevenlabs",
            elevenlabs_api_key="test-key",
            tts_elevenlabs_voice="2EiwWnXFnvU5JabPnv8n",
            tts_elevenlabs_model="eleven_flash_v2_5",
            tts_elevenlabs_speed=1.0,
        )
        if config_overrides:
            config.update(config_overrides)

        from speech.elevenlabs_tts import ElevenLabsTTS
        tts = ElevenLabsTTS(config)
        return tts, mock_client_instance

    def test_synthesize_returns_pcm_bytes(self, monkeypatch):
        """ElevenLabsTTS.synthesize returns PCM bytes from the API."""
        tts, _ = self._build(monkeypatch)
        pcm = tts.synthesize("hello world")
        assert isinstance(pcm, bytes)
        assert len(pcm) > 0

    def test_synthesize_calls_convert_with_correct_params(self, monkeypatch):
        """ElevenLabsTTS.synthesize passes correct parameters to the SDK."""
        tts, mock_client = self._build(monkeypatch)
        tts.synthesize("test text")
        mock_client.text_to_speech.convert.assert_called_once_with(
            text="test text",
            voice_id="2EiwWnXFnvU5JabPnv8n",
            model_id="eleven_flash_v2_5",
            output_format="pcm_16000",
        )

    def test_synthesize_stream_yields_chunks(self, monkeypatch):
        """ElevenLabsTTS.synthesize_stream() yields chunks from the API."""
        tts, _ = self._build(monkeypatch)
        chunks = list(tts.synthesize_stream("hello world"))
        assert len(chunks) == 2
        for chunk in chunks:
            assert isinstance(chunk, bytes)
            assert len(chunk) > 0

    def test_synthesize_stream_calls_stream_with_correct_params(self, monkeypatch):
        """ElevenLabsTTS.synthesize_stream passes correct parameters to the SDK."""
        tts, mock_client = self._build(monkeypatch)
        list(tts.synthesize_stream("test text"))
        mock_client.text_to_speech.stream.assert_called_once_with(
            text="test text",
            voice_id="2EiwWnXFnvU5JabPnv8n",
            model_id="eleven_flash_v2_5",
            output_format="pcm_16000",
        )

    def test_empty_input_returns_silence(self, monkeypatch):
        """ElevenLabsTTS returns 0.1s silence for empty input."""
        tts, _ = self._build(monkeypatch)
        pcm = tts.synthesize("")
        assert pcm == b"\x00\x00" * 1600

    def test_whitespace_input_returns_silence(self, monkeypatch):
        """ElevenLabsTTS returns 0.1s silence for whitespace-only input."""
        tts, _ = self._build(monkeypatch)
        pcm = tts.synthesize("   ")
        assert pcm == b"\x00\x00" * 1600

    def test_stream_empty_input_yields_silence(self, monkeypatch):
        """ElevenLabsTTS.synthesize_stream() yields silence for empty text."""
        tts, _ = self._build(monkeypatch)
        chunks = list(tts.synthesize_stream(""))
        assert len(chunks) == 1
        assert chunks[0] == b"\x00\x00" * 1600

    def test_missing_api_key_raises(self, monkeypatch):
        """ElevenLabsTTS raises ValueError if API key is missing."""
        from speech.elevenlabs_tts import ElevenLabsTTS
        with pytest.raises(ValueError, match="ELEVENLABS_API_KEY is required"):
            ElevenLabsTTS(_make_config(tts_mode="elevenlabs", elevenlabs_api_key=""))

    def test_close_is_noop(self, monkeypatch):
        """ElevenLabsTTS.close() doesn't raise."""
        tts, _ = self._build(monkeypatch)
        tts.close()

    def test_factory_returns_elevenlabs(self, monkeypatch):
        """get_tts returns ElevenLabsTTS for 'elevenlabs' mode."""
        mock_client_instance = MagicMock()
        mock_elevenlabs_client = MagicMock()
        mock_elevenlabs_client.ElevenLabs.return_value = mock_client_instance

        fake_elevenlabs = MagicMock()
        fake_elevenlabs.client = mock_elevenlabs_client
        monkeypatch.setitem(sys.modules, "elevenlabs", fake_elevenlabs)
        monkeypatch.setitem(sys.modules, "elevenlabs.client", mock_elevenlabs_client)

        from speech import get_tts
        from speech.elevenlabs_tts import ElevenLabsTTS
        tts = get_tts(_make_config(
            tts_mode="elevenlabs",
            elevenlabs_api_key="test-key",
        ))
        assert isinstance(tts, ElevenLabsTTS)


# --- CachedTTS tests ---


class TestCachedTTS:
    """Tests for CachedTTS disk-caching wrapper."""

    def _build(self, tmp_path, inner=None, **config_overrides):
        """Helper: construct a CachedTTS wrapping a mock inner TTS."""
        if inner is None:
            inner = MagicMock(spec=MockTTS)
            inner.synthesize.return_value = b"\x01\x00" * 1600
            inner.synthesize_stream.return_value = iter(
                [b"\x01\x00" * 800, b"\x02\x00" * 800]
            )
            inner.close.return_value = None
        config = _make_config(
            tts_cache_enabled=True,
            tts_cache_dir=str(tmp_path / "cache"),
            **config_overrides,
        )
        cached = CachedTTS(inner, config)
        return cached, inner

    def test_cache_miss_delegates_to_inner(self, tmp_path):
        """First call delegates to inner TTS."""
        cached, inner = self._build(tmp_path)
        result = cached.synthesize("hello world")
        inner.synthesize.assert_called_once_with("hello world")
        assert result == b"\x01\x00" * 1600

    def test_cache_hit_skips_inner(self, tmp_path):
        """Second call returns from disk without calling inner TTS again."""
        cached, inner = self._build(tmp_path)
        cached.synthesize("hello world")
        inner.synthesize.reset_mock()

        result = cached.synthesize("hello world")
        inner.synthesize.assert_not_called()
        assert result == b"\x01\x00" * 1600

    def test_pcm_file_created_on_disk(self, tmp_path):
        """A .pcm file is created in the cache dir after first synthesis."""
        cached, _ = self._build(tmp_path)
        cached.synthesize("test phrase")
        cache_dir = tmp_path / "cache"
        pcm_files = list(cache_dir.glob("*.pcm"))
        assert len(pcm_files) == 1

    def test_different_text_different_cache_files(self, tmp_path):
        """Different text produces different cache files."""
        cached, _ = self._build(tmp_path)
        cached.synthesize("hello")
        cached.synthesize("goodbye")
        cache_dir = tmp_path / "cache"
        pcm_files = list(cache_dir.glob("*.pcm"))
        assert len(pcm_files) == 2

    def test_different_voice_different_cache_key(self, tmp_path):
        """Different voice config produces a different cache key."""
        cached1, _ = self._build(tmp_path, tts_elevenlabs_voice="voice_a")
        cached2, _ = self._build(tmp_path, tts_elevenlabs_voice="voice_b")
        key1 = cached1._cache_key("hello")
        key2 = cached2._cache_key("hello")
        assert key1 != key2

    def test_different_model_different_cache_key(self, tmp_path):
        """Different model config produces a different cache key."""
        cached1, _ = self._build(tmp_path, tts_elevenlabs_model="model_a")
        cached2, _ = self._build(tmp_path, tts_elevenlabs_model="model_b")
        key1 = cached1._cache_key("hello")
        key2 = cached2._cache_key("hello")
        assert key1 != key2

    def test_stream_cache_miss_yields_and_caches(self, tmp_path):
        """Stream cache miss yields chunks from inner and writes cache."""
        cached, inner = self._build(tmp_path)
        chunks = list(cached.synthesize_stream("hello stream"))
        assert len(chunks) == 2
        assert chunks[0] == b"\x01\x00" * 800
        assert chunks[1] == b"\x02\x00" * 800
        # File should exist on disk
        cache_dir = tmp_path / "cache"
        assert len(list(cache_dir.glob("*.pcm"))) == 1

    def test_stream_cache_hit_yields_single_chunk(self, tmp_path):
        """Stream cache hit yields full file as single chunk."""
        cached, inner = self._build(tmp_path)
        # First call: cache miss
        list(cached.synthesize_stream("hello stream"))
        inner.synthesize_stream.reset_mock()

        # Second call: cache hit
        chunks = list(cached.synthesize_stream("hello stream"))
        inner.synthesize_stream.assert_not_called()
        assert len(chunks) == 1
        # Full accumulated result
        assert chunks[0] == b"\x01\x00" * 800 + b"\x02\x00" * 800

    def test_empty_text_bypasses_cache(self, tmp_path):
        """Empty/whitespace text delegates directly without caching."""
        cached, inner = self._build(tmp_path)
        cached.synthesize("")
        cached.synthesize("   ")
        cache_dir = tmp_path / "cache"
        assert len(list(cache_dir.glob("*.pcm"))) == 0

    def test_close_delegates_to_inner(self, tmp_path):
        """close() calls inner TTS close()."""
        cached, inner = self._build(tmp_path)
        cached.close()
        inner.close.assert_called_once()

    def test_cache_dir_auto_created(self, tmp_path):
        """Cache dir is created automatically if it doesn't exist."""
        cache_dir = tmp_path / "deep" / "nested" / "cache"
        assert not cache_dir.exists()
        config = _make_config(tts_cache_enabled=True, tts_cache_dir=str(cache_dir))
        inner = MagicMock(spec=MockTTS)
        CachedTTS(inner, config)
        assert cache_dir.exists()

    def test_factory_wraps_with_cache_when_enabled(self):
        """get_tts wraps with CachedTTS when tts_cache_enabled=True."""
        from speech import get_tts
        tts = get_tts(_make_config(tts_cache_enabled=True))
        assert isinstance(tts, CachedTTS)

    def test_factory_returns_raw_when_cache_disabled(self):
        """get_tts returns raw TTS when cache not enabled."""
        from speech import get_tts
        tts = get_tts(_make_config(tts_cache_enabled=False))
        assert isinstance(tts, MockTTS)
