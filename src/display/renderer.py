"""E-ink display renderer — all layout and drawing logic."""

from __future__ import annotations

import logging
import math
from datetime import datetime
from typing import TYPE_CHECKING

from PIL import Image, ImageDraw, ImageFont

if TYPE_CHECKING:
    from display.base import BaseDisplay
    from display.context import DisplayContext

log = logging.getLogger(__name__)

# Layout constants (480 x 800 portrait)
WIDTH = 480
HEIGHT = 800

# Section Y positions
DATE_BAR_Y = 0
DATE_BAR_H = 44
ACCENT_Y = DATE_BAR_H
WEATHER_HERO_Y = 48
WEATHER_HERO_H = 232
FORECAST_Y = 288
FORECAST_H = 172
SOLAR_Y = 472
SOLAR_H = 228
FOOTER_Y = HEIGHT - 44
FOOTER_H = 44

# Margins
MARGIN = 20

# Colors
RED = "red"
BLACK = "black"
WHITE = "white"


def _load_fonts() -> dict[int, ImageFont.FreeTypeFont]:
    """Load DejaVuSans-Bold at all needed sizes, with fallback."""
    sizes = [12, 14, 16, 18, 20, 24, 28, 48, 64]
    fonts: dict[int, ImageFont.FreeTypeFont] = {}
    for s in sizes:
        try:
            fonts[s] = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", s
            )
        except OSError:
            fonts[s] = ImageFont.load_default()
    return fonts


# ---------------------------------------------------------------------------
# Weather icons — all drawn with PIL primitives
# ---------------------------------------------------------------------------


def _draw_sun(draw: ImageDraw.ImageDraw, cx: int, cy: int, s: float) -> None:
    """Filled circle + 8 radiating lines."""
    r = int(22 * s)
    draw.ellipse(
        [cx - r, cy - r, cx + r, cy + r], fill=BLACK
    )
    ray_inner = int(30 * s)
    ray_outer = int(46 * s)
    for i in range(8):
        angle = math.radians(i * 45)
        x1 = cx + int(ray_inner * math.cos(angle))
        y1 = cy + int(ray_inner * math.sin(angle))
        x2 = cx + int(ray_outer * math.cos(angle))
        y2 = cy + int(ray_outer * math.sin(angle))
        draw.line([(x1, y1), (x2, y2)], fill=BLACK, width=max(1, int(3 * s)))


def _draw_cloud(
    draw: ImageDraw.ImageDraw, cx: int, cy: int, s: float, color: str = BLACK
) -> None:
    """Three overlapping ellipses forming a cumulus cloud."""
    # Main body
    w1, h1 = int(44 * s), int(26 * s)
    draw.ellipse([cx - w1, cy - h1 // 2, cx + w1, cy + h1 // 2], fill=color)
    # Left bump
    w2, h2 = int(24 * s), int(22 * s)
    draw.ellipse(
        [cx - int(30 * s) - w2, cy - h2, cx - int(30 * s) + w2, cy + int(4 * s)],
        fill=color,
    )
    # Right-top bump
    w3, h3 = int(28 * s), int(28 * s)
    draw.ellipse(
        [cx + int(4 * s) - w3, cy - h3 - int(4 * s), cx + int(4 * s) + w3, cy],
        fill=color,
    )


def _draw_rain_lines(
    draw: ImageDraw.ImageDraw, cx: int, cy: int, s: float
) -> None:
    """Angled rain lines below cloud center."""
    lw = max(1, int(2 * s))
    length = int(16 * s)
    spacing = int(14 * s)
    start_y = cy + int(18 * s)
    for i in range(4):
        x = cx - int(24 * s) + i * spacing
        draw.line(
            [(x, start_y), (x - int(6 * s), start_y + length)],
            fill=BLACK,
            width=lw,
        )


def _draw_snow_flakes(
    draw: ImageDraw.ImageDraw, cx: int, cy: int, s: float
) -> None:
    """Small asterisk snowflakes below cloud."""
    size = int(5 * s)
    lw = max(1, int(2 * s))
    start_y = cy + int(20 * s)
    positions = [
        (cx - int(20 * s), start_y),
        (cx, start_y + int(10 * s)),
        (cx + int(20 * s), start_y),
    ]
    for fx, fy in positions:
        for angle in [0, 60, 120]:
            rad = math.radians(angle)
            dx = int(size * math.cos(rad))
            dy = int(size * math.sin(rad))
            draw.line([(fx - dx, fy - dy), (fx + dx, fy + dy)], fill=BLACK, width=lw)


def _draw_lightning(
    draw: ImageDraw.ImageDraw, cx: int, cy: int, s: float
) -> None:
    """Red lightning bolt polygon below cloud."""
    # Bolt shape relative to cx, cy
    points = [
        (cx - int(4 * s), cy + int(10 * s)),
        (cx + int(8 * s), cy + int(10 * s)),
        (cx + int(2 * s), cy + int(24 * s)),
        (cx + int(14 * s), cy + int(24 * s)),
        (cx - int(6 * s), cy + int(48 * s)),
        (cx, cy + int(30 * s)),
        (cx - int(10 * s), cy + int(30 * s)),
    ]
    draw.polygon(points, fill=RED)


def _draw_fog_lines(
    draw: ImageDraw.ImageDraw, cx: int, cy: int, s: float
) -> None:
    """Three horizontal dashed lines."""
    lw = max(1, int(3 * s))
    dash_w = int(12 * s)
    gap = int(6 * s)
    total_w = int(80 * s)
    for row in range(3):
        y = cy - int(16 * s) + row * int(16 * s)
        x = cx - total_w // 2
        while x < cx + total_w // 2:
            draw.line([(x, y), (x + dash_w, y)], fill=BLACK, width=lw)
            x += dash_w + gap


def _draw_drizzle_dots(
    draw: ImageDraw.ImageDraw, cx: int, cy: int, s: float
) -> None:
    """Scattered dots below cloud center."""
    dot_r = max(1, int(2 * s))
    start_y = cy + int(18 * s)
    positions = [
        (cx - int(18 * s), start_y),
        (cx - int(6 * s), start_y + int(12 * s)),
        (cx + int(8 * s), start_y + int(4 * s)),
        (cx + int(20 * s), start_y + int(10 * s)),
        (cx - int(12 * s), start_y + int(20 * s)),
    ]
    for dx, dy in positions:
        draw.ellipse([dx - dot_r, dy - dot_r, dx + dot_r, dy + dot_r], fill=BLACK)


def _draw_weather_icon(
    draw: ImageDraw.ImageDraw, code: int, cx: int, cy: int, size: int = 120
) -> None:
    """Dispatch to the right icon based on WMO weather code."""
    s = size / 120

    if code == 0:
        # Clear sky — sun
        _draw_sun(draw, cx, cy, s)
    elif code == 1:
        # Mainly clear — sun + small cloud bottom-right
        _draw_sun(draw, cx - int(12 * s), cy - int(8 * s), s * 0.7)
        _draw_cloud(draw, cx + int(18 * s), cy + int(16 * s), s * 0.5)
    elif code == 2:
        # Partly cloudy — sun upper-left + cloud lower-right
        _draw_sun(draw, cx - int(18 * s), cy - int(16 * s), s * 0.6)
        _draw_cloud(draw, cx + int(10 * s), cy + int(10 * s), s * 0.7)
    elif code == 3:
        # Overcast — big cloud
        _draw_cloud(draw, cx, cy, s)
    elif code in (45, 48):
        # Fog
        _draw_fog_lines(draw, cx, cy, s)
    elif 51 <= code <= 57:
        # Drizzle — cloud + dots
        _draw_cloud(draw, cx, cy - int(10 * s), s * 0.8)
        _draw_drizzle_dots(draw, cx, cy, s)
    elif (61 <= code <= 67) or (80 <= code <= 82):
        # Rain — cloud + angled lines
        _draw_cloud(draw, cx, cy - int(10 * s), s * 0.8)
        _draw_rain_lines(draw, cx, cy, s)
    elif (71 <= code <= 77) or (85 <= code <= 86):
        # Snow — cloud + snowflakes
        _draw_cloud(draw, cx, cy - int(10 * s), s * 0.8)
        _draw_snow_flakes(draw, cx, cy, s)
    elif 95 <= code <= 99:
        # Thunderstorm — cloud + red lightning
        _draw_cloud(draw, cx, cy - int(14 * s), s * 0.8)
        _draw_lightning(draw, cx, cy, s)
    else:
        # Unknown — just draw a cloud
        _draw_cloud(draw, cx, cy, s * 0.7)


# ---------------------------------------------------------------------------
# Solar energy bar
# ---------------------------------------------------------------------------


def _draw_solar_bar(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    w: int,
    h: int,
    prod_kw: float,
    cons_kw: float,
) -> None:
    """Energy flow bar: black fill for production, red marker for consumption."""
    max_val = max(prod_kw, cons_kw) * 1.2
    if max_val <= 0:
        # Nighttime — empty bar outline
        draw.rectangle([x, y, x + w, y + h], outline=BLACK, width=1)
        return

    # Bar background
    draw.rectangle([x, y, x + w, y + h], outline=BLACK, width=1)

    # Production fill (black)
    prod_px = int((prod_kw / max_val) * w)
    if prod_px > 0:
        draw.rectangle([x, y, x + prod_px, y + h], fill=BLACK)

    # Consumption marker (red vertical line)
    cons_px = int((cons_kw / max_val) * w)
    if cons_px > 0:
        marker_x = x + cons_px
        draw.line(
            [(marker_x, y - 3), (marker_x, y + h + 3)], fill=RED, width=3
        )


# ---------------------------------------------------------------------------
# Section renderers
# ---------------------------------------------------------------------------


def _render_date_bar(
    draw: ImageDraw.ImageDraw,
    fonts: dict,
    ctx: DisplayContext | None,
) -> None:
    """Top bar: date on left, system metrics on right, thin red accent below."""
    now = datetime.now()
    date_str = now.strftime("%A, %B %-d")
    draw.text((MARGIN, 10), date_str, fill=BLACK, font=fonts[24])

    # System metrics (right-aligned)
    system_monitor = ctx.system_monitor if ctx else None
    if system_monitor:
        metrics = system_monitor.get_metrics()
        parts = []
        if metrics.cpu_temp_c is not None:
            parts.append(f"{metrics.cpu_temp_c:.1f}\u00b0C")
        if metrics.power_w is not None:
            parts.append(f"{metrics.power_w:.1f}W")
        if parts:
            metrics_text = "  ".join(parts)
            bbox = draw.textbbox((0, 0), metrics_text, font=fonts[14])
            text_w = bbox[2] - bbox[0]
            draw.text(
                (WIDTH - text_w - MARGIN, 14),
                metrics_text,
                fill=BLACK,
                font=fonts[14],
            )

    # Thin red accent line
    draw.line([(0, ACCENT_Y), (WIDTH, ACCENT_Y)], fill=RED, width=2)


def _render_weather_hero(
    draw: ImageDraw.ImageDraw,
    fonts: dict,
    weather_data,
) -> None:
    """Large weather icon + hero temperature + details."""
    if weather_data is None:
        # Centered "no data" message
        text = "No weather data"
        bbox = draw.textbbox((0, 0), text, font=fonts[24])
        text_w = bbox[2] - bbox[0]
        y_center = WEATHER_HERO_Y + WEATHER_HERO_H // 2 - 12
        draw.text(
            ((WIDTH - text_w) // 2, y_center), text, fill=BLACK, font=fonts[24]
        )
        return

    cur = weather_data.current

    # Weather icon (left side)
    icon_cx = 80
    icon_cy = WEATHER_HERO_Y + 100
    _draw_weather_icon(draw, cur.weather_code, icon_cx, icon_cy, size=120)

    # Hero temperature (red, 64pt) — right of icon
    temp_x = 170
    temp_y = WEATHER_HERO_Y + 40
    temp_str = f"{cur.temperature_f:.0f}"
    draw.text((temp_x, temp_y), temp_str, fill=RED, font=fonts[64])

    # Degree + F suffix in smaller font, aligned to top-right of temp
    temp_bbox = draw.textbbox((temp_x, temp_y), temp_str, font=fonts[64])
    suffix_x = temp_bbox[2] + 2
    draw.text((suffix_x, temp_y + 8), "\u00b0F", fill=RED, font=fonts[28])

    # Weather description
    from weather.codes import describe_weather

    desc = describe_weather(cur.weather_code)
    draw.text((temp_x, temp_y + 80), desc, fill=BLACK, font=fonts[24])

    # Feels like
    draw.text(
        (temp_x, temp_y + 112),
        f"Feels like {cur.feels_like_f:.0f}\u00b0F",
        fill=BLACK,
        font=fonts[20],
    )

    # Humidity + wind
    detail = f"{cur.humidity_pct}% humidity \u00b7 {cur.wind_speed_mph:.0f} mph"
    draw.text((temp_x, temp_y + 140), detail, fill=BLACK, font=fonts[16])


def _render_forecast(
    draw: ImageDraw.ImageDraw,
    fonts: dict,
    weather_data,
) -> None:
    """3-day forecast strip with mini weather icons."""
    if weather_data is None or not weather_data.forecast:
        return

    # Thin divider above forecast
    draw.line(
        [(MARGIN, FORECAST_Y - 4), (WIDTH - MARGIN, FORECAST_Y - 4)],
        fill=BLACK,
        width=1,
    )

    col_count = min(3, len(weather_data.forecast))
    col_width = (WIDTH - 2 * MARGIN) // col_count

    for i, day in enumerate(weather_data.forecast[:3]):
        col_x = MARGIN + i * col_width
        col_cx = col_x + col_width // 2  # center of column

        # Day name
        day_name = day.date.strftime("%a")
        bbox = draw.textbbox((0, 0), day_name, font=fonts[18])
        name_w = bbox[2] - bbox[0]
        draw.text(
            (col_cx - name_w // 2, FORECAST_Y + 4),
            day_name,
            fill=BLACK,
            font=fonts[18],
        )

        # Mini weather icon
        _draw_weather_icon(
            draw, day.weather_code, col_cx, FORECAST_Y + 68, size=56
        )

        # High / Low temps
        temps = f"{day.temp_max_f:.0f}\u00b0/{day.temp_min_f:.0f}\u00b0"
        bbox = draw.textbbox((0, 0), temps, font=fonts[18])
        tw = bbox[2] - bbox[0]
        draw.text(
            (col_cx - tw // 2, FORECAST_Y + 105),
            temps,
            fill=BLACK,
            font=fonts[18],
        )

        # Precipitation — red if >= 50%
        rain_text = f"{day.precipitation_probability}% rain"
        rain_color = RED if day.precipitation_probability >= 50 else BLACK
        bbox = draw.textbbox((0, 0), rain_text, font=fonts[16])
        rw = bbox[2] - bbox[0]
        draw.text(
            (col_cx - rw // 2, FORECAST_Y + 132),
            rain_text,
            fill=rain_color,
            font=fonts[16],
        )


def _render_solar(
    draw: ImageDraw.ImageDraw,
    fonts: dict,
    solar_storage,
) -> None:
    """Solar section with hero kW numbers and energy flow bar."""
    # Thin divider above solar
    draw.line(
        [(MARGIN, SOLAR_Y - 4), (WIDTH - MARGIN, SOLAR_Y - 4)],
        fill=BLACK,
        width=1,
    )

    # Section label
    draw.text((MARGIN, SOLAR_Y + 4), "SOLAR", fill=BLACK, font=fonts[14])

    if solar_storage is None:
        draw.text(
            (MARGIN, SOLAR_Y + 30),
            "Not configured",
            fill=BLACK,
            font=fonts[20],
        )
        return

    reading = solar_storage.get_latest()
    if not reading:
        draw.text(
            (MARGIN, SOLAR_Y + 30),
            "Waiting for data...",
            fill=BLACK,
            font=fonts[20],
        )
        return

    prod_kw = reading["production_w"] / 1000
    cons_kw = reading["consumption_w"] / 1000
    net_w = reading["net_w"]

    # Hero numbers — production left, consumption right
    prod_str = f"{prod_kw:.1f}"
    cons_str = f"{cons_kw:.1f}"

    # Production (left)
    draw.text((MARGIN, SOLAR_Y + 28), prod_str, fill=BLACK, font=fonts[48])
    prod_bbox = draw.textbbox((MARGIN, SOLAR_Y + 28), prod_str, font=fonts[48])
    draw.text(
        (prod_bbox[2] + 4, SOLAR_Y + 40), "kW", fill=BLACK, font=fonts[20]
    )
    draw.text(
        (MARGIN, SOLAR_Y + 84), "producing", fill=BLACK, font=fonts[14]
    )

    # Consumption (right-aligned)
    kw_bbox = draw.textbbox((0, 0), "kW", font=fonts[20])
    kw_w = kw_bbox[2] - kw_bbox[0]
    cons_bbox = draw.textbbox((0, 0), cons_str, font=fonts[48])
    cons_w = cons_bbox[2] - cons_bbox[0]
    cons_x = WIDTH - MARGIN - cons_w - kw_w - 4
    draw.text((cons_x, SOLAR_Y + 28), cons_str, fill=BLACK, font=fonts[48])
    draw.text(
        (cons_x + cons_w + 4, SOLAR_Y + 40), "kW", fill=BLACK, font=fonts[20]
    )
    # Right-align "using" label
    using_bbox = draw.textbbox((0, 0), "using", font=fonts[14])
    using_w = using_bbox[2] - using_bbox[0]
    draw.text(
        (WIDTH - MARGIN - using_w, SOLAR_Y + 84),
        "using",
        fill=BLACK,
        font=fonts[14],
    )

    # Energy flow bar
    bar_y = SOLAR_Y + 110
    bar_h = 20
    bar_x = MARGIN
    bar_w = WIDTH - 2 * MARGIN
    _draw_solar_bar(draw, bar_x, bar_y, bar_w, bar_h, prod_kw, cons_kw)

    # Net status
    status_y = SOLAR_Y + 145
    if net_w >= 0:
        net_text = f"Exporting {net_w / 1000:.1f} kW"
        draw.text((MARGIN, status_y), net_text, fill=BLACK, font=fonts[20])
    else:
        imp_kw = abs(net_w) / 1000
        net_text = f"Importing {imp_kw:.1f} kW"
        draw.text((MARGIN, status_y), net_text, fill=RED, font=fonts[20])


def _render_footer(
    draw: ImageDraw.ImageDraw,
    fonts: dict,
) -> None:
    """Footer with version and last updated time."""
    # Thin divider
    draw.line(
        [(MARGIN, FOOTER_Y), (WIDTH - MARGIN, FOOTER_Y)],
        fill=BLACK,
        width=1,
    )

    draw.text(
        (MARGIN, FOOTER_Y + 12), "home-hud v0.1.0", fill=BLACK, font=fonts[14]
    )

    # Last updated time (right-aligned)
    updated = datetime.now().strftime("Updated %-I:%M%p").lower()
    bbox = draw.textbbox((0, 0), updated, font=fonts[14])
    tw = bbox[2] - bbox[0]
    draw.text(
        (WIDTH - MARGIN - tw, FOOTER_Y + 12),
        updated,
        fill=BLACK,
        font=fonts[14],
    )


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def render_frame(display: BaseDisplay, ctx: DisplayContext | None = None) -> None:
    """Render a complete frame and push it to the display."""
    width, height = display.size
    img = Image.new("RGB", (width, height), WHITE)
    draw = ImageDraw.Draw(img)

    fonts = _load_fonts()

    # Get weather data once for hero + forecast
    weather_client = ctx.weather_client if ctx else None
    weather_data = weather_client.get_weather() if weather_client else None

    solar_storage = ctx.solar_storage if ctx else None

    _render_date_bar(draw, fonts, ctx)
    _render_weather_hero(draw, fonts, weather_data)
    _render_forecast(draw, fonts, weather_data)
    _render_solar(draw, fonts, solar_storage)
    _render_footer(draw, fonts)

    display.show(img)
