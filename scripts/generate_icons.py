#!/usr/bin/env python3
"""Generate Hearth PWA icons.

Produces the five PNG files the SPA manifest references, with a
stylised flame glyph centred on the warm-black app background:

    web/static/icons/
      192.png               (any-purpose, Android/Chrome)
      512.png               (any-purpose, high-dpi + splash)
      maskable-192.png      (Android adaptive — icon in inner 80%)
      maskable-512.png      (Android adaptive — icon in inner 80%)
      apple-touch-180.png   (iOS home-screen)

Idempotent: re-run any time the design changes. Pillow only.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

# App palette (mirrors web/src/app.css design tokens).
BG = (0x15, 0x13, 0x0F)         # warm-black
ACCENT = (0xE8, 0x74, 0x3F)     # terracotta — reads well at icon sizes
HIGHLIGHT = (0xFB, 0xB8, 0x7B)  # inner ember glow

# 4x oversample + LANCZOS downsample gives smooth curves without
# needing native anti-aliased drawing primitives.
OVERSAMPLE = 4

# Output root.
ICONS_DIR = Path(__file__).resolve().parent.parent / "web" / "static" / "icons"


def _bezier(
    p0: tuple[float, float],
    p1: tuple[float, float],
    p2: tuple[float, float],
    p3: tuple[float, float],
    steps: int = 60,
) -> list[tuple[float, float]]:
    """Sample a cubic Bezier curve into a list of points."""
    out: list[tuple[float, float]] = []
    for i in range(steps + 1):
        t = i / steps
        mt = 1 - t
        x = (
            mt**3 * p0[0]
            + 3 * mt**2 * t * p1[0]
            + 3 * mt * t**2 * p2[0]
            + t**3 * p3[0]
        )
        y = (
            mt**3 * p0[1]
            + 3 * mt**2 * t * p1[1]
            + 3 * mt * t**2 * p2[1]
            + t**3 * p3[1]
        )
        out.append((x, y))
    return out


def _flame(cx: float, cy: float, h: float) -> list[tuple[float, float]]:
    """Return a smooth flame silhouette (teardrop leaning slightly).

    Constructed from two cubic Bezier curves — one for each side —
    meeting at the top tip and the bottom centre.
    """
    w = h * 0.58  # flame aspect ratio
    tip_x = cx + w * 0.08  # slight lean to the right
    tip_y = cy - h * 0.50
    base_y = cy + h * 0.50

    # Right side: from top tip, bulging out to the right, down to base.
    right = _bezier(
        (tip_x, tip_y),
        (tip_x + w * 0.80, tip_y + h * 0.30),  # upper control — outward swing
        (cx + w * 0.60, base_y - h * 0.02),     # lower control
        (cx, base_y),                           # base centre
    )

    # Left side: from base centre back up to tip — bulges outward,
    # slightly less than the right side for asymmetric flame feel.
    left = _bezier(
        (cx, base_y),
        (cx - w * 0.62, base_y - h * 0.02),
        (cx - w * 0.55, tip_y + h * 0.28),
        (tip_x, tip_y),
    )

    return right + left


def _inner_flame(cx: float, cy: float, h: float) -> list[tuple[float, float]]:
    """Small inner flame for the ember highlight, offset down-and-in."""
    scale = 0.48
    inner_cy = cy + h * 0.12
    return _flame(cx, inner_cy, h * scale)


def _render(size: int, maskable: bool) -> Image.Image:
    """Render one icon at ``size`` px.

    Drawing happens at ``size * OVERSAMPLE`` and is then downsampled
    with LANCZOS — gives anti-aliased edges on the bezier curves
    without needing a heavier render pipeline.
    """
    big = size * OVERSAMPLE
    img = Image.new("RGB", (big, big), BG)
    draw = ImageDraw.Draw(img, "RGBA")

    cx = big / 2
    cy = big / 2
    # 62% of canvas for any-purpose; 50% for maskable (Android's mask
    # may crop ~10% off each edge — stay well inside the safe zone).
    glyph_h = big * (0.50 if maskable else 0.62)

    draw.polygon(_flame(cx, cy, glyph_h), fill=ACCENT)
    draw.polygon(_inner_flame(cx, cy, glyph_h), fill=HIGHLIGHT + (220,))

    return img.resize((size, size), Image.Resampling.LANCZOS)


def main() -> None:
    ICONS_DIR.mkdir(parents=True, exist_ok=True)

    targets = [
        ("192.png", 192, False),
        ("512.png", 512, False),
        ("maskable-192.png", 192, True),
        ("maskable-512.png", 512, True),
        ("apple-touch-180.png", 180, False),
    ]

    for filename, size, maskable in targets:
        img = _render(size, maskable)
        out = ICONS_DIR / filename
        img.save(out, format="PNG", optimize=True)
        rel = out.relative_to(ICONS_DIR.parent.parent.parent)
        print(f"wrote {rel} ({size}x{size})")


if __name__ == "__main__":
    main()
