"""Abstract base class for all display backends."""

from __future__ import annotations

import logging
import threading
from abc import ABC, abstractmethod
from pathlib import Path

from PIL import Image

log = logging.getLogger(__name__)

# Canvas dimensions (portrait orientation for wall mount)
DEFAULT_WIDTH = 480
DEFAULT_HEIGHT = 800


class BaseDisplay(ABC):
    """Common interface for mock and e-ink displays."""

    def __init__(
        self,
        width: int = DEFAULT_WIDTH,
        height: int = DEFAULT_HEIGHT,
        snapshot_path: str | None = None,
    ):
        self._width = width
        self._height = height
        self._snapshot_path = Path(snapshot_path) if snapshot_path else None
        self._snapshot_lock = threading.Lock()

    @property
    def size(self) -> tuple[int, int]:
        return (self._width, self._height)

    @abstractmethod
    def show(self, image: Image.Image) -> None:
        """Render a PIL Image to the display."""
        ...

    @abstractmethod
    def clear(self) -> None:
        """Clear the display to white."""
        ...

    def close(self) -> None:
        """Clean up resources. Override if needed."""
        pass

    def _save_snapshot(self, image: Image.Image) -> None:
        """Save a PNG snapshot for the telemetry dashboard."""
        if not self._snapshot_path:
            return
        try:
            with self._snapshot_lock:
                self._snapshot_path.parent.mkdir(parents=True, exist_ok=True)
                image.save(self._snapshot_path)
            log.debug("Display snapshot saved to %s", self._snapshot_path)
        except Exception:
            log.debug("Failed to save display snapshot", exc_info=True)
