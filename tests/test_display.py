"""Tests for the display abstraction layer."""

import sys
from pathlib import Path

# Add src to path so imports work
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from PIL import Image

from display.base import DEFAULT_HEIGHT, DEFAULT_WIDTH
from display.mock_display import MockDisplay


def test_mock_display_creates_output(tmp_path):
    """MockDisplay should save a PNG to the output directory."""
    config = {"mock_output_dir": str(tmp_path)}
    display = MockDisplay(config)

    assert display.size == (DEFAULT_WIDTH, DEFAULT_HEIGHT)

    # Render a test image
    img = Image.new("RGB", display.size, "red")
    display.show(img)

    output_file = tmp_path / "latest.png"
    assert output_file.exists()

    # Verify dimensions
    saved = Image.open(output_file)
    assert saved.size == (DEFAULT_WIDTH, DEFAULT_HEIGHT)


def test_mock_display_clear(tmp_path):
    """MockDisplay.clear() should produce a white image."""
    config = {"mock_output_dir": str(tmp_path)}
    display = MockDisplay(config)
    display.clear()

    saved = Image.open(tmp_path / "latest.png")
    # Check a pixel is white
    assert saved.getpixel((0, 0)) == (255, 255, 255)


def test_render_frame(tmp_path):
    """render_frame should produce valid output without crashing."""
    config = {
        "display_mode": "mock",
        "mock_output_dir": str(tmp_path),
    }
    display = MockDisplay(config)

    from main import render_frame
    render_frame(display)

    assert (tmp_path / "latest.png").exists()
