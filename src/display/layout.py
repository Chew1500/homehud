"""Layout computation for the e-ink display.

Provides a Layout dataclass that computes section bounding rectangles
from canvas dimensions and orientation. Section renderers use Layout
instead of hardcoded pixel constants.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Rect:
    """Bounding rectangle for a display section."""

    x: int
    y: int
    w: int
    h: int

    @property
    def x2(self) -> int:
        return self.x + self.w

    @property
    def y2(self) -> int:
        return self.y + self.h

    @property
    def cx(self) -> int:
        return self.x + self.w // 2

    @property
    def cy(self) -> int:
        return self.y + self.h // 2


@dataclass(frozen=True)
class Layout:
    """Computed layout for all display sections.

    Use ``compute_layout()`` to build an instance — do not construct directly.
    """

    width: int
    height: int
    orientation: str  # "portrait" | "landscape"
    margin: int

    date_bar: Rect
    weather_hero: Rect
    forecast: Rect
    solar: Rect
    footer: Rect


def compute_layout(width: int, height: int, orientation: str) -> Layout:
    """Build a Layout from canvas dimensions and orientation.

    Portrait (480x800): vertical stack matching the original fixed layout.
    Landscape (800x480): two-column — weather+forecast left, solar right.

    Raises ``ValueError`` for unrecognised orientations.
    """
    margin = 20

    if orientation == "portrait":
        date_bar_h = 44
        footer_h = 44
        weather_hero_h = 264
        forecast_h = 172
        solar_h = 160

        date_bar = Rect(0, 0, width, date_bar_h)
        weather_hero = Rect(0, date_bar_h + 4, width, weather_hero_h)
        forecast = Rect(0, weather_hero.y2 + 8, width, forecast_h)
        solar = Rect(0, forecast.y2 + 12, width, solar_h)
        footer = Rect(0, height - footer_h, width, footer_h)

    elif orientation == "landscape":
        date_bar_h = 40
        footer_h = 40

        date_bar = Rect(0, 0, width, date_bar_h)
        footer = Rect(0, height - footer_h, width, footer_h)

        body_y = date_bar_h + 4
        body_h = height - date_bar_h - footer_h - 8  # 4px gap top + 4px gap bottom

        col_w = width // 2

        # Left column: weather hero + forecast stacked
        weather_hero_h = int(body_h * 0.56)
        forecast_h = body_h - weather_hero_h - 4  # 4px gap between
        weather_hero = Rect(0, body_y, col_w, weather_hero_h)
        forecast = Rect(0, weather_hero.y2 + 4, col_w, forecast_h)

        # Right column: solar takes full height
        solar = Rect(col_w, body_y, col_w, body_h)

    else:
        raise ValueError(
            f"Invalid orientation {orientation!r}. Must be 'portrait' or 'landscape'."
        )

    return Layout(
        width=width,
        height=height,
        orientation=orientation,
        margin=margin,
        date_bar=date_bar,
        weather_hero=weather_hero,
        forecast=forecast,
        solar=solar,
        footer=footer,
    )
