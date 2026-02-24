"""Configuration management for Home HUD."""

import os
from pathlib import Path

from dotenv import load_dotenv

# Project root is one level up from src/
PROJECT_ROOT = Path(__file__).parent.parent
ENV_FILE = PROJECT_ROOT / ".env"


def load_config() -> dict:
    """Load configuration from environment variables and .env file."""
    load_dotenv(ENV_FILE)  # no-op if file doesn't exist; won't override existing env vars

    return {
        # Display settings
        "display_mode": os.getenv("HUD_DISPLAY_MODE", "mock"),  # "mock" or "eink"
        "mock_output_dir": os.getenv("HUD_MOCK_OUTPUT_DIR", str(PROJECT_ROOT / "output")),
        "mock_show_window": os.getenv("HUD_MOCK_SHOW_WINDOW", "false").lower() == "true",

        # Audio settings
        "audio_mode": os.getenv("HUD_AUDIO_MODE", "mock"),  # "mock" or "hardware"
        "audio_sample_rate": int(os.getenv("HUD_AUDIO_SAMPLE_RATE", "16000")),
        "audio_channels": int(os.getenv("HUD_AUDIO_CHANNELS", "1")),
        "audio_device": os.getenv("HUD_AUDIO_DEVICE"),  # device index or name
        "audio_mock_dir": os.getenv("HUD_AUDIO_MOCK_DIR", str(PROJECT_ROOT / "output" / "audio")),

        # Speech-to-text settings
        "stt_mode": os.getenv("HUD_STT_MODE", "mock"),
        "stt_whisper_model": os.getenv("HUD_STT_WHISPER_MODEL", "base.en"),
        "stt_mock_response": os.getenv("HUD_STT_MOCK_RESPONSE", "hello world"),

        # Text-to-speech settings
        "tts_mode": os.getenv("HUD_TTS_MODE", "mock"),
        "tts_piper_model": os.getenv("HUD_TTS_PIPER_MODEL", "en_US-lessac-medium"),
        "tts_piper_speaker": os.getenv("HUD_TTS_PIPER_SPEAKER"),
        "tts_mock_duration": float(os.getenv("HUD_TTS_MOCK_DURATION", "2.0")),

        # LLM settings
        "llm_mode": os.getenv("HUD_LLM_MODE", "mock"),
        "llm_model": os.getenv("HUD_LLM_MODEL", "claude-sonnet-4-5-20250929"),
        "llm_max_tokens": int(os.getenv("HUD_LLM_MAX_TOKENS", "1024")),
        "llm_system_prompt": os.getenv("HUD_LLM_SYSTEM_PROMPT", ""),
        "llm_mock_response": os.getenv("HUD_LLM_MOCK_RESPONSE", "This is a mock LLM response."),

        # Voice pipeline settings
        "voice_enabled": os.getenv("HUD_VOICE_ENABLED", "true").lower() == "true",
        "voice_record_duration": int(os.getenv("HUD_VOICE_RECORD_DURATION", "5")),

        # Wake word detection
        "wake_mode": os.getenv("HUD_WAKE_MODE", "mock"),
        "wake_model": os.getenv("HUD_WAKE_MODEL", "hey_jarvis"),
        "wake_threshold": float(os.getenv("HUD_WAKE_THRESHOLD", "0.5")),
        "wake_mock_trigger_after": int(os.getenv("HUD_WAKE_MOCK_TRIGGER_AFTER", "62")),

        # Feature settings
        "grocery_file": os.getenv("HUD_GROCERY_FILE", str(PROJECT_ROOT / "data" / "grocery.json")),

        # Refresh interval in seconds (e-ink shouldn't refresh too often)
        "refresh_interval": int(os.getenv("HUD_REFRESH_INTERVAL", "300")),

        # Logging
        "log_dir": os.getenv("HUD_LOG_DIR", str(PROJECT_ROOT / "logs")),
        "log_level": os.getenv("HUD_LOG_LEVEL", "INFO"),

        # Enphase API (Phase 2)
        "enphase_api_key": os.getenv("ENPHASE_API_KEY", ""),
        "enphase_system_id": os.getenv("ENPHASE_SYSTEM_ID", ""),

        # Anthropic API (Phase 6)
        "anthropic_api_key": os.getenv("ANTHROPIC_API_KEY", ""),
    }
