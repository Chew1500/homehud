"""Configuration management for Home HUD.

Config values are loaded with this priority (highest wins):
  1. Local config file (data/config.json)
  2. Environment variables (from .env or shell)
  3. Defaults defined in CONFIG_REGISTRY
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

log = logging.getLogger("home-hud.config")

# Project root is one level up from src/
PROJECT_ROOT = Path(__file__).parent.parent
ENV_FILE = PROJECT_ROOT / ".env"
CONFIG_FILE = PROJECT_ROOT / "data" / "config.json"


@dataclass(frozen=True)
class ConfigParam:
    """Definition of a single configuration parameter."""

    key: str  # dict key, e.g. "display_mode"
    env_var: str  # env var name, e.g. "HUD_DISPLAY_MODE"
    default: str | None  # default as string (None = no default)
    type: str  # "str" | "int" | "float" | "bool"
    group: str  # UI group name
    description: str  # human-readable description
    sensitive: bool = False  # if True, mask in API responses


# fmt: off
CONFIG_REGISTRY: list[ConfigParam] = [
    # --- Display ---
    ConfigParam("display_mode", "HUD_DISPLAY_MODE", "mock", "str", "Display",
                "Display backend: mock or eink"),
    ConfigParam("mock_output_dir", "HUD_MOCK_OUTPUT_DIR",
                str(PROJECT_ROOT / "output"), "str", "Display",
                "Directory for mock display output"),
    ConfigParam("mock_show_window", "HUD_MOCK_SHOW_WINDOW", "false", "bool", "Display",
                "Show mock display in a window"),
    ConfigParam("display_snapshot_path", "HUD_DISPLAY_SNAPSHOT_PATH",
                str(PROJECT_ROOT / "output" / "display_snapshot.png"), "str", "Display",
                "Path to display snapshot PNG"),
    ConfigParam("display_orientation", "HUD_DISPLAY_ORIENTATION", "portrait", "str",
                "Display", "Display orientation: portrait or landscape"),

    # --- Audio ---
    ConfigParam("audio_mode", "HUD_AUDIO_MODE", "mock", "str", "Audio",
                "Audio backend: mock or hardware"),
    ConfigParam("audio_sample_rate", "HUD_AUDIO_SAMPLE_RATE", "16000", "int", "Audio",
                "Audio sample rate in Hz"),
    ConfigParam("audio_channels", "HUD_AUDIO_CHANNELS", "1", "int", "Audio",
                "Number of audio channels"),
    ConfigParam("audio_device", "HUD_AUDIO_DEVICE", None, "str", "Audio",
                "Audio device index or name"),
    ConfigParam("audio_mock_dir", "HUD_AUDIO_MOCK_DIR",
                str(PROJECT_ROOT / "output" / "audio"), "str", "Audio",
                "Directory for mock audio output"),
    ConfigParam("audio_stale_timeout", "HUD_AUDIO_STALE_TIMEOUT", "30", "int", "Audio",
                "Seconds before audio is considered stale"),

    # --- STT ---
    ConfigParam("stt_mode", "HUD_STT_MODE", "mock", "str", "STT",
                "STT backend: mock or whisper"),
    ConfigParam("stt_whisper_model", "HUD_STT_WHISPER_MODEL", "base.en", "str", "STT",
                "Whisper model size"),
    ConfigParam("stt_whisper_prompt", "HUD_STT_WHISPER_PROMPT", "", "str", "STT",
                "Initial prompt for Whisper"),
    ConfigParam("stt_whisper_hotwords", "HUD_STT_WHISPER_HOTWORDS", "", "str", "STT",
                "Hotwords for Whisper"),
    ConfigParam("stt_mock_response", "HUD_STT_MOCK_RESPONSE", "hello world", "str",
                "STT", "Mock STT response text"),
    ConfigParam("stt_no_speech_threshold", "HUD_STT_NO_SPEECH_THRESHOLD", "0.6",
                "float", "STT", "No-speech probability threshold"),
    ConfigParam("stt_confidence_threshold", "HUD_STT_CONFIDENCE_THRESHOLD", "-1.0",
                "float", "STT", "Minimum confidence threshold (-1 to disable)"),

    # --- TTS ---
    ConfigParam("tts_mode", "HUD_TTS_MODE", "mock", "str", "TTS",
                "TTS backend: mock, kokoro, or elevenlabs"),
    ConfigParam("tts_kokoro_voice", "HUD_TTS_KOKORO_VOICE", "af_heart", "str", "TTS",
                "Kokoro voice name"),
    ConfigParam("tts_kokoro_speed", "HUD_TTS_KOKORO_SPEED", "1.0", "float", "TTS",
                "Kokoro speech speed"),
    ConfigParam("tts_kokoro_lang", "HUD_TTS_KOKORO_LANG", "a", "str", "TTS",
                "Kokoro language code"),
    ConfigParam("tts_kokoro_model", "HUD_TTS_KOKORO_MODEL",
                str(PROJECT_ROOT / "models" / "kokoro-v1.0.int8.onnx"), "str", "TTS",
                "Path to Kokoro ONNX model"),
    ConfigParam("tts_kokoro_voices", "HUD_TTS_KOKORO_VOICES",
                str(PROJECT_ROOT / "models" / "voices-v1.0.bin"), "str", "TTS",
                "Path to Kokoro voices file"),
    ConfigParam("elevenlabs_api_key", "ELEVENLABS_API_KEY", "", "str", "TTS",
                "ElevenLabs API key", sensitive=True),
    ConfigParam("tts_elevenlabs_voice", "HUD_TTS_ELEVENLABS_VOICE",
                "N2lVS1w4EtoT3dr4eOWO", "str", "TTS", "ElevenLabs voice ID"),
    ConfigParam("tts_elevenlabs_model", "HUD_TTS_ELEVENLABS_MODEL",
                "eleven_flash_v2_5", "str", "TTS", "ElevenLabs model ID"),
    ConfigParam("tts_elevenlabs_speed", "HUD_TTS_ELEVENLABS_SPEED", "1.0", "float",
                "TTS", "ElevenLabs speech speed"),
    ConfigParam("tts_cache_enabled", "HUD_TTS_CACHE_ENABLED", "false", "bool", "TTS",
                "Enable TTS disk cache"),
    ConfigParam("tts_cache_dir", "HUD_TTS_CACHE_DIR",
                str(PROJECT_ROOT / "data" / "tts_cache"), "str", "TTS",
                "TTS cache directory"),
    ConfigParam("tts_mock_duration", "HUD_TTS_MOCK_DURATION", "2.0", "float", "TTS",
                "Mock TTS duration in seconds"),

    # --- LLM ---
    ConfigParam("llm_mode", "HUD_LLM_MODE", "mock", "str", "LLM",
                "LLM backend: mock or claude"),
    ConfigParam("llm_model", "HUD_LLM_MODEL", "claude-sonnet-4-5-20250929", "str",
                "LLM", "Claude model for conversations"),
    ConfigParam("llm_max_tokens", "HUD_LLM_MAX_TOKENS", "1024", "int", "LLM",
                "Max tokens for LLM responses"),
    ConfigParam("llm_system_prompt", "HUD_LLM_SYSTEM_PROMPT", "", "str", "LLM",
                "Custom system prompt override"),
    ConfigParam("llm_intent_model", "HUD_LLM_INTENT_MODEL",
                "claude-haiku-4-5-20251001", "str", "LLM",
                "Claude model for intent parsing"),
    ConfigParam("llm_mock_response", "HUD_LLM_MOCK_RESPONSE",
                "This is a mock LLM response.", "str", "LLM",
                "Mock LLM response text"),
    ConfigParam("llm_intent_max_tokens", "HUD_LLM_INTENT_MAX_TOKENS", "300", "int",
                "LLM", "Max tokens for intent responses"),
    ConfigParam("llm_max_history", "HUD_LLM_MAX_HISTORY", "10", "int", "LLM",
                "Max conversation history entries"),
    ConfigParam("llm_history_ttl", "HUD_LLM_HISTORY_TTL", "300", "int", "LLM",
                "Conversation history TTL in seconds"),
    ConfigParam("llm_personality", "HUD_LLM_PERSONALITY", "", "str", "LLM",
                "LLM personality description"),
    ConfigParam("intent_recovery_enabled", "HUD_INTENT_RECOVERY_ENABLED", "true",
                "bool", "LLM", "Enable LLM-powered misheard command correction"),

    # --- Voice Pipeline ---
    ConfigParam("voice_enabled", "HUD_VOICE_ENABLED", "true", "bool",
                "Voice Pipeline", "Enable voice pipeline"),
    ConfigParam("voice_record_duration", "HUD_VOICE_RECORD_DURATION", "5", "int",
                "Voice Pipeline", "Max recording duration in seconds"),
    ConfigParam("voice_wake_feedback", "HUD_VOICE_WAKE_FEEDBACK", "true", "bool",
                "Voice Pipeline", "Play audio feedback on wake word"),
    ConfigParam("voice_startup_announcement", "HUD_VOICE_STARTUP_ANNOUNCEMENT", "true",
                "bool", "Voice Pipeline", "Announce when voice pipeline starts"),
    ConfigParam("voice_deploy_announcement", "HUD_VOICE_DEPLOY_ANNOUNCEMENT", "true",
                "bool", "Voice Pipeline", "Announce new deployments"),
    ConfigParam("voice_vad_enabled", "HUD_VOICE_VAD_ENABLED", "true", "bool",
                "Voice Pipeline", "Enable voice activity detection"),
    ConfigParam("vad_silence_threshold", "HUD_VAD_SILENCE_THRESHOLD", "300", "int",
                "Voice Pipeline", "VAD silence threshold (RMS amplitude)"),
    ConfigParam("vad_silence_duration", "HUD_VAD_SILENCE_DURATION", "2.5", "float",
                "Voice Pipeline", "Seconds of silence to end recording"),
    ConfigParam("vad_speech_chunks_required", "HUD_VAD_SPEECH_CHUNKS_REQUIRED", "3",
                "int", "Voice Pipeline", "Speech chunks required before recording"),
    ConfigParam("vad_min_duration", "HUD_VAD_MIN_DURATION", "0.5", "float",
                "Voice Pipeline", "Minimum recording duration in seconds"),
    ConfigParam("vad_max_duration", "HUD_VAD_MAX_DURATION", "15.0", "float",
                "Voice Pipeline", "Maximum recording duration in seconds"),
    ConfigParam("vad_adaptive", "HUD_VAD_ADAPTIVE", "true", "bool",
                "Voice Pipeline", "Enable adaptive VAD threshold"),
    ConfigParam("vad_calibration_chunks", "HUD_VAD_CALIBRATION_CHUNKS", "5", "int",
                "Voice Pipeline", "Chunks for adaptive threshold calibration"),
    ConfigParam("vad_adaptive_multiplier", "HUD_VAD_ADAPTIVE_MULTIPLIER", "1.5",
                "float", "Voice Pipeline", "Multiplier for adaptive threshold"),
    ConfigParam("voice_bargein_enabled", "HUD_VOICE_BARGEIN_ENABLED", "true", "bool",
                "Voice Pipeline", "Allow barge-in during playback"),
    ConfigParam("voice_max_follow_ups", "HUD_VOICE_MAX_FOLLOW_UPS", "5", "int",
                "Voice Pipeline", "Max follow-up exchanges per session"),
    ConfigParam("voice_max_consecutive_low_confidence",
                "HUD_VOICE_MAX_CONSECUTIVE_LOW_CONFIDENCE", "2", "int",
                "Voice Pipeline", "Max consecutive low-confidence results before stopping"),

    # --- Wake ---
    ConfigParam("wake_mode", "HUD_WAKE_MODE", "mock", "str", "Wake",
                "Wake word backend: mock or openwakeword"),
    ConfigParam("wake_model", "HUD_WAKE_MODEL", "hey_jarvis", "str", "Wake",
                "Wake word model name"),
    ConfigParam("wake_threshold", "HUD_WAKE_THRESHOLD", "0.6", "float", "Wake",
                "Wake word detection threshold"),
    ConfigParam("wake_confirm_frames", "HUD_WAKE_CONFIRM_FRAMES", "3", "int", "Wake",
                "Frames to confirm wake word"),
    ConfigParam("wake_cooldown", "HUD_WAKE_COOLDOWN", "2.0", "float", "Wake",
                "Seconds between wake word triggers"),
    ConfigParam("wake_mock_trigger_after", "HUD_WAKE_MOCK_TRIGGER_AFTER", "62", "int",
                "Wake", "Mock: trigger after N iterations"),

    # --- Volume ---
    ConfigParam("volume_mixer", "HUD_VOLUME_MIXER", "Master", "str", "Volume",
                "ALSA mixer name"),
    ConfigParam("volume_step_small", "HUD_VOLUME_STEP_SMALL", "10", "int", "Volume",
                "Small volume step percentage"),
    ConfigParam("volume_step_medium", "HUD_VOLUME_STEP_MEDIUM", "20", "int", "Volume",
                "Medium volume step percentage"),
    ConfigParam("volume_step_large", "HUD_VOLUME_STEP_LARGE", "30", "int", "Volume",
                "Large volume step percentage"),

    # --- Features ---
    ConfigParam("weather_poll_interval", "HUD_WEATHER_POLL_INTERVAL", "900", "int",
                "Features", "Weather poll interval in seconds"),
    ConfigParam("grocery_file", "HUD_GROCERY_FILE",
                str(PROJECT_ROOT / "data" / "grocery.json"), "str", "Features",
                "Path to grocery list file"),
    ConfigParam("reminder_file", "HUD_REMINDER_FILE",
                str(PROJECT_ROOT / "data" / "reminders.json"), "str", "Features",
                "Path to reminders file"),
    ConfigParam("reminder_check_interval", "HUD_REMINDER_CHECK_INTERVAL", "15", "int",
                "Features", "Reminder check interval in seconds"),
    ConfigParam("refresh_interval", "HUD_REFRESH_INTERVAL", "3600", "int", "Features",
                "Display refresh interval in seconds"),
    ConfigParam("media_disambiguation_ttl", "HUD_MEDIA_DISAMBIGUATION_TTL", "60",
                "int", "Features", "Media disambiguation TTL in seconds"),

    # --- Solar ---
    ConfigParam("enphase_mode", "ENPHASE_MODE", "mock", "str", "Solar",
                "Enphase backend: mock or live"),
    ConfigParam("enphase_host", "ENPHASE_HOST", "192.168.1.67", "str", "Solar",
                "Enphase IQ Gateway IP address"),
    ConfigParam("enphase_serial", "ENPHASE_SERIAL", "", "str", "Solar",
                "Enphase gateway serial number"),
    ConfigParam("enphase_token", "ENPHASE_TOKEN", "", "str", "Solar",
                "Enphase API token", sensitive=True),
    ConfigParam("enphase_email", "ENPHASE_EMAIL", "", "str", "Solar",
                "Enphase account email", sensitive=True),
    ConfigParam("enphase_password", "ENPHASE_PASSWORD", "", "str", "Solar",
                "Enphase account password", sensitive=True),
    ConfigParam("enphase_poll_interval", "ENPHASE_POLL_INTERVAL", "600", "int",
                "Solar", "Enphase poll interval in seconds"),
    ConfigParam("solar_db_path", "SOLAR_DB_PATH",
                str(PROJECT_ROOT / "data" / "solar.db"), "str", "Solar",
                "Path to solar database"),
    ConfigParam("solar_latitude", "SOLAR_LATITUDE", "", "str", "Solar",
                "Solar location latitude"),
    ConfigParam("solar_longitude", "SOLAR_LONGITUDE", "", "str", "Solar",
                "Solar location longitude"),

    # --- Monitor ---
    ConfigParam("monitor_enabled", "HUD_MONITOR_ENABLED", "false", "bool", "Monitor",
                "Enable service uptime monitoring"),
    ConfigParam("monitor_poll_interval", "HUD_MONITOR_POLL_INTERVAL", "600", "int",
                "Monitor", "Service check interval in seconds"),
    ConfigParam("monitor_check_timeout", "HUD_MONITOR_CHECK_TIMEOUT", "10", "int",
                "Monitor", "HTTP/ping check timeout in seconds"),
    ConfigParam("monitor_db_path", "HUD_MONITOR_DB_PATH",
                str(PROJECT_ROOT / "data" / "monitor.db"), "str", "Monitor",
                "Path to monitor database"),

    # --- Media ---
    ConfigParam("sonarr_mode", "SONARR_MODE", "", "str", "Media",
                "Sonarr backend: empty (disabled), mock, or live"),
    ConfigParam("sonarr_url", "SONARR_URL", "http://localhost:8989", "str", "Media",
                "Sonarr API URL"),
    ConfigParam("sonarr_api_key", "SONARR_API_KEY", "", "str", "Media",
                "Sonarr API key", sensitive=True),
    ConfigParam("radarr_mode", "RADARR_MODE", "", "str", "Media",
                "Radarr backend: empty (disabled), mock, or live"),
    ConfigParam("radarr_url", "RADARR_URL", "http://localhost:7878", "str", "Media",
                "Radarr API URL"),
    ConfigParam("radarr_api_key", "RADARR_API_KEY", "", "str", "Media",
                "Radarr API key", sensitive=True),
    ConfigParam("jellyfin_mode", "JELLYFIN_MODE", "", "str", "Media",
                "Jellyfin backend: empty (disabled), mock, or live"),
    ConfigParam("jellyfin_url", "JELLYFIN_URL", "http://localhost:8096", "str",
                "Media", "Jellyfin API URL"),
    ConfigParam("jellyfin_api_key", "JELLYFIN_API_KEY", "", "str", "Media",
                "Jellyfin API key", sensitive=True),
    ConfigParam("jellyfin_user_id", "JELLYFIN_USER_ID", "", "str", "Media",
                "Jellyfin user ID"),
    ConfigParam("discovery_db_path", "DISCOVERY_DB_PATH",
                str(PROJECT_ROOT / "data" / "discovery.db"), "str", "Media",
                "Path to discovery database"),
    ConfigParam("discovery_library_sync_interval", "DISCOVERY_LIBRARY_SYNC_INTERVAL",
                "21600", "int", "Media", "Library sync interval in seconds"),
    ConfigParam("discovery_interval", "DISCOVERY_INTERVAL", "86400", "int", "Media",
                "Discovery generation interval in seconds"),
    ConfigParam("discovery_llm_model", "DISCOVERY_LLM_MODEL",
                "claude-haiku-4-5-20251001", "str", "Media",
                "LLM model for media recommendations"),
    ConfigParam("discovery_max_recommendations", "DISCOVERY_MAX_RECOMMENDATIONS", "10",
                "int", "Media", "Max recommendations per run"),

    # --- Telemetry ---
    ConfigParam("telemetry_enabled", "HUD_TELEMETRY_ENABLED", "true", "bool",
                "Telemetry", "Enable telemetry collection"),
    ConfigParam("telemetry_db_path", "HUD_TELEMETRY_DB_PATH",
                str(PROJECT_ROOT / "data" / "telemetry.db"), "str", "Telemetry",
                "Path to telemetry database"),
    ConfigParam("telemetry_max_size_mb", "HUD_TELEMETRY_MAX_SIZE_MB", "10240", "int",
                "Telemetry", "Max telemetry database size in MB"),
    ConfigParam("telemetry_web_enabled", "HUD_TELEMETRY_WEB_ENABLED", "true", "bool",
                "Telemetry", "Enable telemetry web dashboard"),
    ConfigParam("telemetry_web_host", "HUD_TELEMETRY_WEB_HOST", "0.0.0.0", "str",
                "Telemetry", "Web dashboard bind address"),
    ConfigParam("telemetry_web_port", "HUD_TELEMETRY_WEB_PORT", "8080", "int",
                "Telemetry", "Web dashboard port"),

    # --- System ---
    ConfigParam("log_dir", "HUD_LOG_DIR", str(PROJECT_ROOT / "logs"), "str", "System",
                "Log file directory"),
    ConfigParam("log_level", "HUD_LOG_LEVEL", "INFO", "str", "System",
                "Logging level"),
    ConfigParam("sysmon_mode", "HUD_SYSMON_MODE", "mock", "str", "System",
                "System monitor backend: mock or pi"),
    ConfigParam("anthropic_api_key", "ANTHROPIC_API_KEY", "", "str", "System",
                "Anthropic API key", sensitive=True),
]
# fmt: on

# Build a lookup for quick access
_REGISTRY_BY_KEY = {p.key: p for p in CONFIG_REGISTRY}


def _convert(raw: str | None, type_str: str) -> str | int | float | bool | None:
    """Convert a raw string value to the appropriate Python type."""
    if raw is None:
        return None
    if type_str == "int":
        if raw == "":
            return None
        return int(raw)
    if type_str == "float":
        if raw == "":
            return None
        return float(raw)
    if type_str == "bool":
        return str(raw).lower() == "true"
    return raw


def _load_config_file() -> dict:
    """Load overrides from the local config file. Returns empty dict if missing."""
    if not CONFIG_FILE.is_file():
        return {}
    try:
        with open(CONFIG_FILE) as f:
            data = json.load(f)
        if not isinstance(data, dict):
            log.warning("Config file %s is not a JSON object, ignoring", CONFIG_FILE)
            return {}
        return data
    except (json.JSONDecodeError, OSError) as e:
        log.warning("Failed to read config file %s: %s", CONFIG_FILE, e)
        return {}


def save_config_file(changes: dict) -> None:
    """Merge changes into the local config file. Creates the file if needed."""
    current = _load_config_file()
    current.update(changes)
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(current, f, indent=2)
        f.write("\n")


def load_config() -> dict:
    """Load configuration with priority: config file > env vars > defaults."""
    load_dotenv(ENV_FILE)  # no-op if file doesn't exist; won't override existing env vars
    file_overrides = _load_config_file()

    config = {}
    for param in CONFIG_REGISTRY:
        # Priority: config file > env var > default
        if param.key in file_overrides:
            raw = str(file_overrides[param.key])
        else:
            env_val = os.getenv(param.env_var)
            if env_val is not None:
                raw = env_val
            elif param.default is not None:
                raw = param.default
            else:
                raw = None

        config[param.key] = _convert(raw, param.type)

    return config


def get_config_metadata(config: dict) -> dict:
    """Return config params with metadata for the dashboard API."""
    file_overrides = _load_config_file()

    params = []
    for p in CONFIG_REGISTRY:
        # Determine which layer provided the current value
        if p.key in file_overrides:
            source = "file"
        elif os.getenv(p.env_var) is not None:
            source = "env"
        else:
            source = "default"

        params.append({
            "key": p.key,
            "value": "********" if p.sensitive else config.get(p.key),
            "type": p.type,
            "group": p.group,
            "description": p.description,
            "default": "********" if p.sensitive else p.default,
            "env_var": p.env_var,
            "source": source,
            "sensitive": p.sensitive,
        })

    # Derive ordered group list from registry order
    groups = list(dict.fromkeys(p.group for p in CONFIG_REGISTRY))
    return {"params": params, "groups": groups}
