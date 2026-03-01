"""Tests for the audio abstraction layer."""

import struct
import sys
import wave
from pathlib import Path

# Add src to path so imports work
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from audio import get_audio
from audio.base import DEFAULT_CHANNELS, DEFAULT_SAMPLE_RATE
from audio.mock_audio import MockAudio


def test_mock_audio_default_config(tmp_path):
    """MockAudio should use default sample rate and channels."""
    config = {"audio_mock_dir": str(tmp_path)}
    audio = MockAudio(config)

    assert audio.sample_rate == DEFAULT_SAMPLE_RATE
    assert audio.channels == DEFAULT_CHANNELS


def test_mock_audio_record_silence(tmp_path):
    """record() without a mock input file should return correct-length silence."""
    config = {"audio_mock_dir": str(tmp_path)}
    audio = MockAudio(config)

    duration = 1.0
    data = audio.record(duration)

    # 16-bit (2 bytes) * sample_rate * channels * duration
    expected_bytes = int(2 * DEFAULT_SAMPLE_RATE * DEFAULT_CHANNELS * duration)
    assert len(data) == expected_bytes
    assert data == b"\x00\x00" * (expected_bytes // 2)


def test_mock_audio_play_saves_wav(tmp_path):
    """play() should write a valid WAV file."""
    config = {"audio_mock_dir": str(tmp_path)}
    audio = MockAudio(config)

    # Generate 0.5s of silence
    num_samples = int(DEFAULT_SAMPLE_RATE * 0.5)
    pcm_data = b"\x00\x00" * num_samples

    audio.play(pcm_data)

    wav_path = tmp_path / "latest.wav"
    assert wav_path.exists()

    # Verify WAV file is valid
    with wave.open(str(wav_path), "rb") as wf:
        assert wf.getnchannels() == DEFAULT_CHANNELS
        assert wf.getsampwidth() == 2  # 16-bit
        assert wf.getframerate() == DEFAULT_SAMPLE_RATE
        assert wf.readframes(wf.getnframes()) == pcm_data


def test_mock_audio_record_from_file(tmp_path):
    """record() with a mock input file should return that file's PCM data."""
    # Create a test WAV file
    input_path = tmp_path / "test_input.wav"
    num_samples = 800  # 0.05s at 16kHz
    pcm_data = struct.pack(f"<{num_samples}h", *range(num_samples))

    with wave.open(str(input_path), "wb") as wf:
        wf.setnchannels(DEFAULT_CHANNELS)
        wf.setsampwidth(2)
        wf.setframerate(DEFAULT_SAMPLE_RATE)
        wf.writeframes(pcm_data)

    config = {
        "audio_mock_dir": str(tmp_path),
        "audio_mock_input_file": str(input_path),
    }
    audio = MockAudio(config)
    result = audio.record(1.0)  # duration ignored when file exists

    assert result == pcm_data


def test_mock_audio_close(tmp_path):
    """close() should not raise."""
    config = {"audio_mock_dir": str(tmp_path)}
    audio = MockAudio(config)
    audio.close()  # should be a no-op


def test_mock_stream_yields_correct_size(tmp_path):
    """stream() should yield chunks of correct size (1280 samples * 2 bytes = 2560)."""
    config = {"audio_mock_dir": str(tmp_path)}
    audio = MockAudio(config)

    gen = audio.stream(chunk_duration_ms=80)
    chunk = next(gen)
    gen.close()

    # 16kHz * 80ms = 1280 samples, 2 bytes each
    assert len(chunk) == 1280 * 2


def test_mock_stream_cleanup_on_close(tmp_path):
    """stream() generator should clean up when closed."""
    config = {"audio_mock_dir": str(tmp_path)}
    audio = MockAudio(config)

    gen = audio.stream()
    next(gen)
    next(gen)
    gen.close()  # should not raise


def test_mock_async_playback(tmp_path):
    """play_async should set is_playing, stop_playback should clear it."""
    config = {"audio_mock_dir": str(tmp_path)}
    audio = MockAudio(config)

    assert not audio.is_playing()

    pcm_data = b"\x00\x00" * 800
    audio.play_async(pcm_data)
    assert audio.is_playing()

    audio.stop_playback()
    assert not audio.is_playing()


def test_mock_async_saves_wav(tmp_path):
    """play_async should still save the WAV file."""
    config = {"audio_mock_dir": str(tmp_path)}
    audio = MockAudio(config)

    pcm_data = b"\x00\x00" * 800
    audio.play_async(pcm_data)

    wav_path = tmp_path / "latest.wav"
    assert wav_path.exists()


def test_mock_play_streamed(tmp_path):
    """play_streamed should collect chunks and play via play_async."""
    config = {"audio_mock_dir": str(tmp_path)}
    audio = MockAudio(config)

    chunk1 = b"\x01\x00" * 400
    chunk2 = b"\x02\x00" * 400

    def gen():
        yield chunk1
        yield chunk2

    audio.play_streamed(gen())

    # Should have saved a WAV (via play_async → play)
    wav_path = tmp_path / "latest.wav"
    assert wav_path.exists()
    # Should be playing (play_async sets the flag)
    assert audio.is_playing()


def test_factory_returns_mock(tmp_path):
    """get_audio() should return MockAudio by default."""
    config = {
        "audio_mode": "mock",
        "audio_mock_dir": str(tmp_path),
    }
    audio = get_audio(config)
    assert isinstance(audio, MockAudio)
