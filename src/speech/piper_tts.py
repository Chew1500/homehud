"""Piper TTS backend for real speech synthesis on the Pi."""

import logging
import urllib.error
import urllib.request
from pathlib import Path

from config import PROJECT_ROOT
from speech.base_tts import BaseTTS
from utils.audio import resample_to_16k

log = logging.getLogger("home-hud.tts.piper")

_PIPER_HF_BASE = "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0"
_MODELS_DIR = PROJECT_ROOT / "models" / "tts"


def _is_model_name(value: str) -> bool:
    """Return True if value looks like a model name (not a file path)."""
    return "/" not in value and "\\" not in value and not value.endswith(".onnx")


def _model_name_to_hf_url(name: str) -> str:
    """Convert a Piper model name to a Hugging Face URL path.

    Example: en_US-lessac-medium → en/en_US/lessac/medium/en_US-lessac-medium
    """
    parts = name.split("-")
    if len(parts) < 3:
        raise ValueError(
            f"Invalid Piper model name '{name}'. "
            "Expected format: {{lang}}_{{REGION}}-{{voice}}-{{quality}} "
            "(e.g., en_US-lessac-medium)"
        )
    lang_region = parts[0]  # e.g. en_US
    voice = "-".join(parts[1:-1])  # e.g. lessac or amy-low (handles multi-part voices)
    quality = parts[-1]  # e.g. medium
    lang = lang_region.split("_")[0]  # e.g. en
    return f"{lang}/{lang_region}/{voice}/{quality}/{name}"


def _download_file(url: str, dest: Path) -> None:
    """Download a file with atomic rename and progress logging."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    try:
        log.info("Downloading %s", url)
        urllib.request.urlretrieve(url, str(tmp))
        tmp.rename(dest)
        log.info("Saved %s", dest)
    except urllib.error.HTTPError as e:
        tmp.unlink(missing_ok=True)
        if e.code == 404:
            raise FileNotFoundError(
                f"Piper model not found at {url} — check the model name. "
                "Browse available models: https://huggingface.co/rhasspy/piper-voices"
            ) from e
        raise
    except (urllib.error.URLError, OSError) as e:
        tmp.unlink(missing_ok=True)
        raise ConnectionError(
            f"Failed to download {url} — check your network connection."
        ) from e


def _ensure_model(value: str) -> Path:
    """Resolve a model value to a local .onnx path, downloading if needed."""
    if not value:
        raise ValueError("tts_piper_model config is required for PiperTTS")

    if _is_model_name(value):
        onnx_path = _MODELS_DIR / f"{value}.onnx"
        json_path = _MODELS_DIR / f"{value}.onnx.json"
        if not onnx_path.exists() or not json_path.exists():
            hf_path = _model_name_to_hf_url(value)
            if not onnx_path.exists():
                _download_file(f"{_PIPER_HF_BASE}/{hf_path}.onnx", onnx_path)
            if not json_path.exists():
                _download_file(f"{_PIPER_HF_BASE}/{hf_path}.onnx.json", json_path)
        return onnx_path

    # Treat as file path
    model_path = Path(value)
    if not model_path.is_absolute():
        model_path = PROJECT_ROOT / model_path
    if not model_path.exists():
        raise FileNotFoundError(f"Piper model not found: {model_path}")
    return model_path


class PiperTTS(BaseTTS):
    """Text-to-speech using Piper (ONNX voice models)."""

    def __init__(self, config: dict):
        super().__init__(config)

        try:
            from piper import PiperVoice
            from piper.config import SynthesisConfig
        except ImportError:
            raise ImportError(
                "piper-tts is required for PiperTTS. "
                "Install it with: pip install piper-tts"
            )

        model_path = _ensure_model(config.get("tts_piper_model", ""))

        self._speaker = config.get("tts_piper_speaker")
        speaker_id = int(self._speaker) if self._speaker else None

        log.info("Loading Piper model: %s", model_path)
        self._voice = PiperVoice.load(str(model_path))
        self._syn_config = SynthesisConfig(speaker_id=speaker_id)
        self._native_rate = self._voice.config.sample_rate
        log.info(
            "Piper ready (native rate=%dHz, speaker=%s)",
            self._native_rate, speaker_id,
        )

    def synthesize(self, text: str) -> bytes:
        """Synthesize text to PCM int16 @ 16kHz mono."""
        if not text or not text.strip():
            # Return 0.1s of silence for empty input
            return b"\x00\x00" * 1600

        chunks = []
        for audio_chunk in self._voice.synthesize(text, syn_config=self._syn_config):
            chunks.append(audio_chunk.audio_int16_bytes)
        raw = b"".join(chunks)

        if self._native_rate != 16000:
            raw = resample_to_16k(raw, self._native_rate)

        return raw
