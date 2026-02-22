"""Mock display backend for local development.

Saves rendered frames as PNG files so you can preview the layout
without the real e-ink hardware.
"""

import logging
from pathlib import Path

from PIL import Image

from display.base import BaseDisplay

log = logging.getLogger(__name__)


class MockDisplay(BaseDisplay):
    """Renders frames to PNG files in an output directory."""

    def __init__(self, config: dict):
        super().__init__()
        self._output_dir = Path(config.get("mock_output_dir", "output"))
        self._output_dir.mkdir(parents=True, exist_ok=True)

        # Always write to a stable filename for easy previewing
        self._latest_path = self._output_dir / "latest.png"

    def show(self, image: Image.Image) -> None:
        # Resize if needed to match display dimensions
        if image.size != self.size:
            image = image.resize(self.size)

        # Save as latest (overwrite) for quick preview
        image.save(self._latest_path)
        log.info(f"Mock frame saved to {self._latest_path}")

    def clear(self) -> None:
        blank = Image.new("RGB", self.size, "white")
        self.show(blank)
        log.info("Mock display cleared.")
