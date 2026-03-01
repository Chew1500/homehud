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
        "stt_whisper_prompt": os.getenv("HUD_STT_WHISPER_PROMPT", ""),
        "stt_whisper_hotwords": os.getenv("HUD_STT_WHISPER_HOTWORDS", ""),
        "stt_mock_response": os.getenv("HUD_STT_MOCK_RESPONSE", "hello world"),

        # Text-to-speech settings
        "tts_mode": os.getenv("HUD_TTS_MODE", "mock"),
        "tts_piper_model": os.getenv("HUD_TTS_PIPER_MODEL", "en_US-lessac-medium"),
        "tts_piper_speaker": os.getenv("HUD_TTS_PIPER_SPEAKER"),
        "tts_kokoro_voice": os.getenv("HUD_TTS_KOKORO_VOICE", "af_heart"),
        "tts_kokoro_speed": float(os.getenv("HUD_TTS_KOKORO_SPEED", "1.0")),
        "tts_kokoro_lang": os.getenv("HUD_TTS_KOKORO_LANG", "a"),
        "tts_mock_duration": float(os.getenv("HUD_TTS_MOCK_DURATION", "2.0")),

        # LLM settings
        "llm_mode": os.getenv("HUD_LLM_MODE", "mock"),
        "llm_model": os.getenv("HUD_LLM_MODEL", "claude-sonnet-4-5-20250929"),
        "llm_max_tokens": int(os.getenv("HUD_LLM_MAX_TOKENS", "1024")),
        "llm_system_prompt": os.getenv("HUD_LLM_SYSTEM_PROMPT", ""),
        "llm_mock_response": os.getenv("HUD_LLM_MOCK_RESPONSE", "This is a mock LLM response."),
        "llm_intent_max_tokens": int(os.getenv("HUD_LLM_INTENT_MAX_TOKENS", "300")),
        "llm_max_history": int(os.getenv("HUD_LLM_MAX_HISTORY", "10")),
        "llm_history_ttl": int(os.getenv("HUD_LLM_HISTORY_TTL", "300")),

        # Voice pipeline settings
        "voice_enabled": os.getenv("HUD_VOICE_ENABLED", "true").lower() == "true",
        "voice_record_duration": int(os.getenv("HUD_VOICE_RECORD_DURATION", "5")),
        "voice_wake_feedback": os.getenv("HUD_VOICE_WAKE_FEEDBACK", "true").lower() == "true",
        "voice_startup_announcement": (
            os.getenv("HUD_VOICE_STARTUP_ANNOUNCEMENT", "true").lower() == "true"
        ),
        "voice_deploy_announcement": (
            os.getenv("HUD_VOICE_DEPLOY_ANNOUNCEMENT", "true").lower() == "true"
        ),
        "voice_vad_enabled": os.getenv("HUD_VOICE_VAD_ENABLED", "true").lower() == "true",
        "vad_silence_threshold": int(os.getenv("HUD_VAD_SILENCE_THRESHOLD", "300")),
        "vad_silence_duration": float(os.getenv("HUD_VAD_SILENCE_DURATION", "2.5")),
        "vad_speech_chunks_required": int(
            os.getenv("HUD_VAD_SPEECH_CHUNKS_REQUIRED", "3")
        ),
        "vad_min_duration": float(os.getenv("HUD_VAD_MIN_DURATION", "0.5")),
        "vad_max_duration": float(os.getenv("HUD_VAD_MAX_DURATION", "15.0")),
        "voice_bargein_enabled": os.getenv("HUD_VOICE_BARGEIN_ENABLED", "true").lower() == "true",

        # Wake word detection
        "wake_mode": os.getenv("HUD_WAKE_MODE", "mock"),
        "wake_model": os.getenv("HUD_WAKE_MODEL", "hey_jarvis"),
        "wake_threshold": float(os.getenv("HUD_WAKE_THRESHOLD", "0.5")),
        "wake_mock_trigger_after": int(os.getenv("HUD_WAKE_MOCK_TRIGGER_AFTER", "62")),

        # Intent recovery (LLM-powered misheard command correction)
        "intent_recovery_enabled": (
            os.getenv("HUD_INTENT_RECOVERY_ENABLED", "true").lower() == "true"
        ),

        # Feature settings
        "grocery_file": os.getenv("HUD_GROCERY_FILE", str(PROJECT_ROOT / "data" / "grocery.json")),
        "reminder_file": os.getenv(
            "HUD_REMINDER_FILE", str(PROJECT_ROOT / "data" / "reminders.json")
        ),
        "reminder_check_interval": int(os.getenv("HUD_REMINDER_CHECK_INTERVAL", "15")),

        # Refresh interval in seconds (e-ink shouldn't refresh too often)
        "refresh_interval": int(os.getenv("HUD_REFRESH_INTERVAL", "300")),

        # Logging
        "log_dir": os.getenv("HUD_LOG_DIR", str(PROJECT_ROOT / "logs")),
        "log_level": os.getenv("HUD_LOG_LEVEL", "INFO"),

        # Enphase solar monitoring
        "enphase_mode": os.getenv("ENPHASE_MODE", "mock"),  # "mock" or "live"
        "enphase_host": os.getenv("ENPHASE_HOST", "192.168.1.67"),
        "enphase_serial": os.getenv("ENPHASE_SERIAL", ""),
        "enphase_token": os.getenv("ENPHASE_TOKEN", ""),
        "enphase_email": os.getenv("ENPHASE_EMAIL", ""),
        "enphase_password": os.getenv("ENPHASE_PASSWORD", ""),
        "enphase_poll_interval": int(os.getenv("ENPHASE_POLL_INTERVAL", "") or "600"),
        "solar_db_path": os.getenv("SOLAR_DB_PATH", str(PROJECT_ROOT / "data" / "solar.db")),
        "solar_latitude": os.getenv("SOLAR_LATITUDE", ""),
        "solar_longitude": os.getenv("SOLAR_LONGITUDE", ""),

        # Sonarr (TV shows) — opt-in: leave SONARR_MODE empty to disable
        "sonarr_mode": os.getenv("SONARR_MODE", ""),  # "" | "mock" | "live"
        "sonarr_url": os.getenv("SONARR_URL", "http://localhost:8989"),
        "sonarr_api_key": os.getenv("SONARR_API_KEY", ""),

        # Radarr (Movies) — opt-in: leave RADARR_MODE empty to disable
        "radarr_mode": os.getenv("RADARR_MODE", ""),  # "" | "mock" | "live"
        "radarr_url": os.getenv("RADARR_URL", "http://localhost:7878"),
        "radarr_api_key": os.getenv("RADARR_API_KEY", ""),

        # Media feature
        "media_disambiguation_ttl": int(os.getenv("HUD_MEDIA_DISAMBIGUATION_TTL", "60")),

        # Anthropic API (Phase 6)
        "anthropic_api_key": os.getenv("ANTHROPIC_API_KEY", ""),
    }
