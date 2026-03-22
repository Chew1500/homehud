"""Tests for the display layout system."""

import sys
from pathlib import Path

import pytest

# Add src to path so imports work
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from display.layout import Rect, compute_layout


def test_rect_properties():
    """Rect convenience properties should be computed correctly."""
    r = Rect(10, 20, 100, 50)
    assert r.x2 == 110
    assert r.y2 == 70
    assert r.cx == 60
    assert r.cy == 45


def test_portrait_layout_matches_original_constants():
    """Portrait layout should produce the same values as the old hardcoded constants."""
    layout = compute_layout(480, 800, "portrait")

    assert layout.width == 480
    assert layout.height == 800
    assert layout.orientation == "portrait"
    assert layout.margin == 20

    assert layout.date_bar == Rect(0, 0, 480, 44)
    assert layout.weather_hero == Rect(0, 48, 480, 264)
    assert layout.forecast == Rect(0, 320, 480, 172)
    assert layout.solar == Rect(0, 504, 480, 160)
    assert layout.footer == Rect(0, 756, 480, 44)


def test_landscape_layout_dimensions():
    """Landscape layout should have valid dimensions for 800x480."""
    layout = compute_layout(800, 480, "landscape")

    assert layout.width == 800
    assert layout.height == 480
    assert layout.orientation == "landscape"
    assert layout.margin == 20


def test_landscape_rects_within_canvas():
    """All landscape section rects should fit within the canvas."""
    layout = compute_layout(800, 480, "landscape")

    for name in ("date_bar", "weather_hero", "forecast", "solar", "footer"):
        r = getattr(layout, name)
        assert r.x >= 0, f"{name}.x out of bounds"
        assert r.y >= 0, f"{name}.y out of bounds"
        assert r.x2 <= layout.width, f"{name}.x2 out of bounds"
        assert r.y2 <= layout.height, f"{name}.y2 out of bounds"
        assert r.w > 0, f"{name}.w must be positive"
        assert r.h > 0, f"{name}.h must be positive"


def test_portrait_rects_within_canvas():
    """All portrait section rects should fit within the canvas."""
    layout = compute_layout(480, 800, "portrait")

    for name in ("date_bar", "weather_hero", "forecast", "solar", "footer"):
        r = getattr(layout, name)
        assert r.x >= 0, f"{name}.x out of bounds"
        assert r.y >= 0, f"{name}.y out of bounds"
        assert r.x2 <= layout.width, f"{name}.x2 out of bounds"
        assert r.y2 <= layout.height, f"{name}.y2 out of bounds"


def _rects_overlap(a: Rect, b: Rect) -> bool:
    """Return True if two rects overlap (share interior area)."""
    if a.x >= b.x2 or b.x >= a.x2:
        return False
    if a.y >= b.y2 or b.y >= a.y2:
        return False
    return True


def test_portrait_rects_no_overlap():
    """Portrait section rects should not overlap each other."""
    layout = compute_layout(480, 800, "portrait")
    names = ["date_bar", "weather_hero", "forecast", "solar", "footer"]
    rects = [getattr(layout, n) for n in names]

    for i in range(len(rects)):
        for j in range(i + 1, len(rects)):
            assert not _rects_overlap(rects[i], rects[j]), (
                f"{names[i]} and {names[j]} overlap"
            )


def test_landscape_rects_no_overlap():
    """Landscape section rects should not overlap each other."""
    layout = compute_layout(800, 480, "landscape")
    names = ["date_bar", "weather_hero", "forecast", "solar", "footer"]
    rects = [getattr(layout, n) for n in names]

    for i in range(len(rects)):
        for j in range(i + 1, len(rects)):
            assert not _rects_overlap(rects[i], rects[j]), (
                f"{names[i]} and {names[j]} overlap"
            )


def test_invalid_orientation_raises():
    """compute_layout should raise ValueError for invalid orientation."""
    with pytest.raises(ValueError, match="Invalid orientation"):
        compute_layout(480, 800, "diagonal")
