"""Configuration management for Home HUD."""

import os
from pathlib import Path

# Project root is one level up from src/
PROJECT_ROOT = Path(__file__).parent.parent
ENV_FILE = PROJECT_ROOT / ".env"


def load_config() -> dict:
    """Load configuration from environment variables and .env file."""
    # Load .env file if it exists (don't override existing env vars)
    if ENV_FILE.exists():
        with open(ENV_FILE) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                key, _, value = line.partition("=")
                key, value = key.strip(), value.strip().strip("\"'")
                if key not in os.environ:
                    os.environ[key] = value

    return {
        # Display settings
        "display_mode": os.getenv("HUD_DISPLAY_MODE", "mock"),  # "mock" or "eink"
        "mock_output_dir": os.getenv("HUD_MOCK_OUTPUT_DIR", str(PROJECT_ROOT / "output")),
        "mock_show_window": os.getenv("HUD_MOCK_SHOW_WINDOW", "false").lower() == "true",

        # Refresh interval in seconds (e-ink shouldn't refresh too often)
        "refresh_interval": int(os.getenv("HUD_REFRESH_INTERVAL", "300")),

        # Enphase API (Phase 2)
        "enphase_api_key": os.getenv("ENPHASE_API_KEY", ""),
        "enphase_system_id": os.getenv("ENPHASE_SYSTEM_ID", ""),

        # Anthropic API (Phase 6)
        "anthropic_api_key": os.getenv("ANTHROPIC_API_KEY", ""),
    }
