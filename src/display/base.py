"""Abstract base class for all display backends."""

from abc import ABC, abstractmethod

from PIL import Image

# Waveshare 7.5" v2 resolution
DEFAULT_WIDTH = 800
DEFAULT_HEIGHT = 480


class BaseDisplay(ABC):
    """Common interface for mock and e-ink displays."""

    def __init__(self, width: int = DEFAULT_WIDTH, height: int = DEFAULT_HEIGHT):
        self._width = width
        self._height = height

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
