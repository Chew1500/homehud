"""Display abstraction layer.

Provides a unified interface for rendering to either:
- MockDisplay: saves PNGs locally (for development)
- EinkDisplay: drives the Waveshare 7.5" tri-color e-Paper HAT (for production)
"""

from display.base import BaseDisplay
from display.mock_display import MockDisplay


def get_display(config: dict) -> BaseDisplay:
    """Factory: return the appropriate display based on config."""
    mode = config.get("display_mode", "mock")

    if mode == "eink":
        from display.eink_display import EinkDisplay
        return EinkDisplay(config)
    else:
        return MockDisplay(config)
