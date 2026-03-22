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


def test_snapshot_saved_when_configured(tmp_path):
    """MockDisplay should save a display snapshot when display_snapshot_path is set."""
    snapshot_path = tmp_path / "snapshot.png"
    config = {
        "mock_output_dir": str(tmp_path),
        "display_snapshot_path": str(snapshot_path),
    }
    display = MockDisplay(config)
    img = Image.new("RGB", display.size, "blue")
    display.show(img)

    assert snapshot_path.exists()
    saved = Image.open(snapshot_path)
    assert saved.size == (DEFAULT_WIDTH, DEFAULT_HEIGHT)


def test_snapshot_skipped_when_not_configured(tmp_path):
    """MockDisplay should not create a snapshot when display_snapshot_path is absent."""
    config = {"mock_output_dir": str(tmp_path)}
    display = MockDisplay(config)
    img = Image.new("RGB", display.size, "green")
    display.show(img)

    # No snapshot file should exist (only latest.png)
    assert not (tmp_path / "display_snapshot.png").exists()


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


def test_mock_display_landscape_size(tmp_path):
    """MockDisplay with landscape orientation should report 800x480."""
    config = {
        "mock_output_dir": str(tmp_path),
        "display_orientation": "landscape",
    }
    display = MockDisplay(config)
    assert display.size == (800, 480)


def test_render_frame_landscape(tmp_path):
    """render_frame in landscape should produce a valid 800x480 PNG."""
    config = {
        "display_mode": "mock",
        "mock_output_dir": str(tmp_path),
        "display_orientation": "landscape",
    }
    display = MockDisplay(config)

    from display.context import DisplayContext
    from main import render_frame

    ctx = DisplayContext(orientation="landscape")
    render_frame(display, ctx=ctx)

    assert (tmp_path / "latest.png").exists()
    saved = Image.open(tmp_path / "latest.png")
    assert saved.size == (800, 480)
