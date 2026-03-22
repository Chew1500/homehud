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
        from display import _display_dimensions

        width, height = _display_dimensions(config)
        self._orientation = config.get("display_orientation", "portrait")
        super().__init__(
            width=width,
            height=height,
            snapshot_path=config.get("display_snapshot_path"),
        )
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
            error_name = type(e).__name__
            if "BadPinFactory" in error_name or "lgpio" in str(e).lower():
                raise RuntimeError(
                    f"GPIO pin factory not available: {e}. "
                    "Ensure python3-lgpio is installed and the venv uses "
                    "--system-site-packages, or run in mock mode "
                    "(HUD_DISPLAY_MODE=mock)."
                ) from e
            raise RuntimeError(
                f"Failed to initialize e-ink display: {e}"
            ) from e

    def show(self, image: Image.Image) -> None:
        if image.size != self.size:
            image = image.resize(self.size)

        # Snapshot before rotation so dashboard gets the readable portrait image
        self._save_snapshot(image)

        # Portrait canvas (480x800) must be rotated to hardware buffer (800x480).
        # Landscape canvas (800x480) already matches the hardware buffer.
        if self._orientation == "portrait":
            image = image.transpose(Image.ROTATE_90)

        # Separate RGB image into black and red channels for tri-color display.
        import numpy as np

        pixels = np.array(image)
        r, g, b = pixels[:, :, 0], pixels[:, :, 1], pixels[:, :, 2]

        is_red = (r > 200) & (g < 50) & (b < 50)
        is_black = (r < 50) & (g < 50) & (b < 50)

        # Black channel: 0 = black ink, 255 = no ink.
        # Black pixels render as black; red pixels stay white (handled by red channel).
        black_data = np.full(r.shape, 255, dtype=np.uint8)
        black_data[is_black] = 0
        bw_image = Image.fromarray(black_data, mode="L").convert("1")

        # Red channel: 0 = red ink, 255 = no ink.
        red_data = np.full(r.shape, 255, dtype=np.uint8)
        red_data[is_red] = 0
        red_image = Image.fromarray(red_data, mode="L").convert("1")

        self._epd.display(self._epd.getbuffer(bw_image), self._epd.getbuffer(red_image))
        log.info("E-ink frame rendered (tri-color).")

    def clear(self) -> None:
        self._epd.Clear()
        log.info("E-ink display cleared.")

    def close(self) -> None:
        self._epd.sleep()
        log.info("E-ink display entering sleep mode.")
