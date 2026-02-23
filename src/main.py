"""Home HUD - Raspberry Pi e-ink dashboard."""

import logging
import logging.handlers
import signal
import threading
import time
from pathlib import Path

from config import load_config
from display import get_display

log = logging.getLogger("home-hud")


def setup_logging(config: dict) -> None:
    """Configure root logger with console and rotating file handlers."""
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    level = getattr(logging, config["log_level"].upper(), logging.INFO)

    root = logging.getLogger()
    root.setLevel(level)

    # Console handler (stderr) — keeps journald working on Pi
    console = logging.StreamHandler()
    console.setFormatter(fmt)
    root.addHandler(console)

    # Rotating file handler
    log_dir = Path(config["log_dir"])
    log_dir.mkdir(parents=True, exist_ok=True)
    file_handler = logging.handlers.RotatingFileHandler(
        log_dir / "homehud.log",
        maxBytes=1_000_000,
        backupCount=3,
    )
    file_handler.setFormatter(fmt)
    root.addHandler(file_handler)


def render_frame(display):
    """Render a single frame to the display."""
    from PIL import Image, ImageDraw, ImageFont

    width, height = display.size
    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)

    # -- Header --
    draw.rectangle([(0, 0), (width, 48)], fill="black")
    try:
        font_lg = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
        font_md = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
        font_sm = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12)
    except OSError:
        font_lg = ImageFont.load_default()
        font_md = font_lg
        font_sm = font_lg

    draw.text((12, 10), "HOME HUD", fill="white", font=font_lg)

    # -- Timestamp --
    from datetime import datetime

    now = datetime.now().strftime("%B %d, %Y  %I:%M %p")
    draw.text((12, 60), now, fill="black", font=font_md)

    # -- Placeholder panels --
    # Solar panel (left)
    draw.rectangle([(12, 100), (width // 2 - 6, 260)], outline="black", width=2)
    draw.text((20, 108), "Solar Production", fill="black", font=font_md)
    draw.text((20, 140), "-- kW", fill="black", font=font_lg)
    draw.text((20, 180), "Waiting for Enphase...", fill="black", font=font_sm)

    # Grocery list (right)
    draw.rectangle([(width // 2 + 6, 100), (width - 12, 260)], outline="black", width=2)
    draw.text((width // 2 + 14, 108), "Grocery List", fill="black", font=font_md)
    draw.text((width // 2 + 14, 140), "No items yet", fill="black", font=font_sm)

    # -- Footer --
    draw.line([(12, height - 40), (width - 12, height - 40)], fill="black", width=1)
    draw.text((12, height - 32), "home-hud v0.1.0", fill="black", font=font_sm)

    display.show(img)


def main():
    config = load_config()
    setup_logging(config)
    display = get_display(config)

    name = display.__class__.__name__
    log.info(f"Starting Home HUD with {name} ({display.size[0]}x{display.size[1]})")

    # Graceful shutdown — threading.Event is thread-safe
    running = threading.Event()
    running.set()

    def shutdown(signum, frame):
        log.info("Shutting down...")
        running.clear()

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    # Voice pipeline (optional)
    audio = None
    stt = None
    wake = None
    voice_thread = None

    if config.get("voice_enabled", True):
        try:
            from audio import get_audio
            from speech import get_stt
            from voice_pipeline import start_voice_pipeline
            from wake import get_wake

            audio = get_audio(config)
            stt = get_stt(config)
            wake = get_wake(config)
            voice_thread = start_voice_pipeline(audio, stt, wake, config, running)
            log.info("Voice pipeline enabled.")
        except Exception:
            log.exception("Voice pipeline failed to start — running without voice")

    refresh_interval = config.get("refresh_interval", 300)  # 5 min default

    try:
        while running.is_set():
            render_frame(display)
            log.info(f"Frame rendered. Next refresh in {refresh_interval}s.")

            # Sleep in small increments so we can catch signals
            for _ in range(refresh_interval):
                if not running.is_set():
                    break
                time.sleep(1)
    finally:
        running.clear()
        if voice_thread:
            voice_thread.join(timeout=5)
        if wake:
            wake.close()
        if stt:
            stt.close()
        if audio:
            audio.close()
        display.close()
        log.info("Home HUD stopped.")


if __name__ == "__main__":
    main()
