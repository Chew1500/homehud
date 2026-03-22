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


def _display_dimensions(config: dict) -> tuple[int, int]:
    """Return (width, height) for the configured orientation."""
    orientation = config.get("display_orientation", "portrait")
    if orientation == "landscape":
        return (800, 480)
    return (480, 800)
