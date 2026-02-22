"""Waveshare 7.5" tri-color e-Paper HAT display backend.

This will be fully implemented once the display hardware arrives.
Requires the Waveshare e-Paper library and SPI to be enabled on the Pi.
"""

import logging

from PIL import Image

from display.base import BaseDisplay

log = logging.getLogger(__name__)


class EinkDisplay(BaseDisplay):
    """Drives the Waveshare 7.5" tri-color e-Paper display."""

    def __init__(self, config: dict):
        super().__init__()
        try:
            from waveshare_epd import epd7in5b_V2  # noqa: F401
            self._epd = epd7in5b_V2.EPD()
            self._epd.init()
            log.info("E-ink display initialized.")
        except ImportError:
            raise RuntimeError(
                "Waveshare e-Paper library not found. "
                "Install it with: pip install waveshare-epd "
                "or run in mock mode (HUD_DISPLAY_MODE=mock)."
            )
        except Exception as e:
            raise RuntimeError(f"Failed to initialize e-ink display: {e}")

    def show(self, image: Image.Image) -> None:
        if image.size != self.size:
            image = image.resize(self.size)

        # The tri-color display expects separate black and red channel images.
        # For now, we convert to the black/white image. Tri-color support
        # will be added when we refine the UI.
        bw_image = image.convert("1")  # 1-bit black/white

        # TODO: Extract red channel for tri-color rendering
        # red_image = extract_red_channel(image)

        self._epd.display(self._epd.getbuffer(bw_image))
        log.info("E-ink frame rendered.")

    def clear(self) -> None:
        self._epd.Clear()
        log.info("E-ink display cleared.")

    def close(self) -> None:
        self._epd.sleep()
        log.info("E-ink display entering sleep mode.")
