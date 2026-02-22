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
