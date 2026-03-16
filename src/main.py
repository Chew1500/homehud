"""Home HUD - Raspberry Pi e-ink dashboard."""

import logging
import logging.handlers
import signal
import sys
import threading
import time
from pathlib import Path

from config import load_config
from display import get_display
from display.context import DisplayContext

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


def render_frame(display, ctx=None):
    """Render a single frame to the display."""
    from PIL import Image, ImageDraw, ImageFont

    width, height = display.size
    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)

    # -- Fonts (bold for e-ink clarity) --
    try:
        font_lg = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 28)
        font_md = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 18)
        font_sm = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 14)
    except OSError:
        font_lg = ImageFont.load_default()
        font_md = font_lg
        font_sm = font_lg

    # -- Header (red bar with date) --
    from datetime import datetime

    draw.rectangle([(0, 0), (width, 56)], fill="red")
    date_str = datetime.now().strftime("%B %d, %Y")
    draw.text((12, 12), date_str, fill="white", font=font_lg)

    # System metrics (right-aligned in header)
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
            bbox = draw.textbbox((0, 0), metrics_text, font=font_sm)
            text_w = bbox[2] - bbox[0]
            draw.text((width - text_w - 12, 20), metrics_text, fill="white", font=font_sm)

    # -- Solar panel (full width) --
    draw.rectangle([(12, 68), (width - 12, 328)], outline="red", width=2)
    draw.text((20, 76), "Solar Production", fill="red", font=font_md)

    solar_storage = ctx.solar_storage if ctx else None
    if solar_storage is None:
        draw.text((20, 113), "-- kW", fill="black", font=font_lg)
        draw.text((20, 158), "Solar: not configured", fill="black", font=font_sm)
    else:
        reading = solar_storage.get_latest()
        if reading:
            prod_kw = reading["production_w"] / 1000
            cons_kw = reading["consumption_w"] / 1000
            net_w = reading["net_w"]
            draw.text((20, 113), f"{prod_kw:.1f} kW", fill="black", font=font_lg)
            draw.text((20, 158), f"Using {cons_kw:.1f} kW", fill="black", font=font_sm)
            if net_w >= 0:
                draw.text((20, 183), f"Exporting {net_w / 1000:.1f} kW", fill="black", font=font_sm)
            else:
                imp_kw = abs(net_w) / 1000
                draw.text((20, 183), f"Importing {imp_kw:.1f} kW", fill="red", font=font_sm)
        else:
            draw.text((20, 113), "-- kW", fill="black", font=font_lg)
            draw.text((20, 158), "Waiting for Enphase...", fill="black", font=font_sm)

    # -- Weather panel (replaces grocery + recommendations) --
    from weather.codes import describe_weather

    draw.rectangle([(12, 348), (width - 12, 728)], outline="red", width=2)
    draw.text((20, 356), "Weather", fill="red", font=font_md)

    weather_client = ctx.weather_client if ctx else None
    weather = weather_client.get_weather() if weather_client else None
    if weather is None:
        draw.text((20, 390), "No weather data", fill="black", font=font_sm)
    else:
        cur = weather.current
        # Current conditions (large)
        draw.text(
            (20, 390),
            f"{cur.temperature_f:.0f}\u00b0F  {describe_weather(cur.weather_code)}",
            fill="black",
            font=font_lg,
        )
        # Details line
        draw.text(
            (20, 430),
            (
                f"Feels like {cur.feels_like_f:.0f}\u00b0F  \u00b7  "
                f"{cur.humidity_pct}% humidity  \u00b7  "
                f"{cur.wind_speed_mph:.0f} mph"
            ),
            fill="black",
            font=font_sm,
        )

        # Divider
        draw.line([(20, 465), (width - 20, 465)], fill="black", width=1)

        # 3-day forecast columns
        if weather.forecast:
            col_count = min(3, len(weather.forecast))
            panel_left = 20
            panel_right = width - 20
            col_width = (panel_right - panel_left) // col_count

            for i, day in enumerate(weather.forecast[:3]):
                x = panel_left + i * col_width
                day_name = day.date.strftime("%a")
                draw.text((x, 485), day_name, fill="black", font=font_md)
                draw.text(
                    (x, 515), describe_weather(day.weather_code), fill="black", font=font_sm
                )
                draw.text(
                    (x, 540),
                    f"{day.temp_max_f:.0f}\u00b0 / {day.temp_min_f:.0f}\u00b0",
                    fill="black",
                    font=font_sm,
                )
                draw.text(
                    (x, 565),
                    f"{day.precipitation_probability}% rain",
                    fill="black",
                    font=font_sm,
                )

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

    # Weather client (independent of voice pipeline — works for display-only mode too)
    from weather import get_weather_client

    weather_client = get_weather_client(config)
    if weather_client:
        log.info(f"Weather client: {weather_client.__class__.__name__}")

    # System monitor (independent of voice pipeline)
    from sysmon import get_system_monitor

    system_monitor = get_system_monitor(config)
    log.info(f"System monitor: {system_monitor.__class__.__name__}")

    # Voice pipeline (optional)
    audio = None
    stt = None
    wake = None
    router = None
    tts = None
    voice_thread = None
    enphase_client = None
    solar_storage = None
    solar_collector = None
    sonarr_client = None
    radarr_client = None
    jellyfin_client = None
    discovery_storage = None
    library_collector = None
    telemetry_store = None
    telemetry_web = None
    grocery_feature = None
    reminder_feature = None

    if config.get("voice_enabled", True):
        try:
            from audio import get_audio
            from discovery.collector import LibraryCollector
            from discovery.engine import DiscoveryEngine
            from discovery.storage import DiscoveryStorage
            from enphase import get_enphase_client
            from enphase.collector import SolarCollector
            from enphase.storage import SolarStorage
            from features.capabilities import CapabilitiesFeature
            from features.discovery import DiscoveryFeature
            from features.grocery import GroceryFeature
            from features.media import MediaFeature
            from features.network import NetworkFeature
            from features.reminder import ReminderFeature
            from features.repeat import RepeatFeature
            from features.solar import SolarFeature
            from features.volume import VolumeFeature
            from intent import get_router
            from jellyfin import get_jellyfin_client
            from llm import get_llm
            from media import get_radarr_client, get_sonarr_client
            from speech import get_stt, get_tts
            from utils.phrases import DEPLOY_PHRASES, STARTUP_PHRASES, WAKE_PHRASES, pick_phrase
            from utils.prompt_cache import PromptCache
            from utils.version import is_new_deploy
            from voice_pipeline import start_voice_pipeline
            from wake import get_wake

            audio = get_audio(config)
            stt = get_stt(config)
            wake = get_wake(config)
            llm = get_llm(config)
            tts = get_tts(config)

            # Pre-synthesize wake prompts for instant playback
            wake_prompts = PromptCache(tts, WAKE_PHRASES, audio.sample_rate)

            repeat_feature = RepeatFeature(config)

            def on_reminder_due(text):
                response = f"Reminder: {text}"
                repeat_feature.record("(reminder)", response)
                speech = tts.synthesize(response)
                audio.play(speech)

            # Solar monitoring
            enphase_client = get_enphase_client(config)
            solar_storage = SolarStorage(config["solar_db_path"])
            solar_collector = SolarCollector(enphase_client, solar_storage, config)
            solar_collector.start()

            # Media library (opt-in)
            sonarr_client = get_sonarr_client(config)
            radarr_client = get_radarr_client(config)

            # Jellyfin + Discovery (opt-in)
            jellyfin_client = get_jellyfin_client(config)
            if sonarr_client or radarr_client or jellyfin_client:
                discovery_storage = DiscoveryStorage(config["discovery_db_path"])
                discovery_engine = DiscoveryEngine(discovery_storage, llm, config)
                library_collector = LibraryCollector(
                    discovery_storage, config,
                    radarr=radarr_client, sonarr=sonarr_client,
                    jellyfin=jellyfin_client, engine=discovery_engine,
                )
                library_collector.start()

            grocery_feature = GroceryFeature(config)
            reminder_feature = ReminderFeature(config, on_due=on_reminder_due)
            discovery_feature = DiscoveryFeature(
                config, discovery_storage=discovery_storage,
                sonarr=sonarr_client, radarr=radarr_client,
            )
            features = [
                repeat_feature,
                VolumeFeature(config, audio=audio),
                grocery_feature,
                reminder_feature,
                SolarFeature(config, solar_storage, llm),
                MediaFeature(config, sonarr=sonarr_client, radarr=radarr_client),
                discovery_feature,
                NetworkFeature(config),
            ]
            capabilities_feature = CapabilitiesFeature(config, features)
            features.append(capabilities_feature)
            # Telemetry
            if config.get("telemetry_enabled", True):
                from telemetry.store import TelemetryStore

                telemetry_store = TelemetryStore(
                    config["telemetry_db_path"],
                    max_size_mb=config.get("telemetry_max_size_mb", 10240),
                )
                if config.get("telemetry_web_enabled", True):
                    from telemetry.web import TelemetryWeb

                    telemetry_web = TelemetryWeb(
                        config["telemetry_db_path"],
                        host=config.get("telemetry_web_host", "0.0.0.0"),
                        port=config.get("telemetry_web_port", 8080),
                        display_snapshot_path=config.get("display_snapshot_path"),
                        log_dir=config.get("log_dir"),
                        config=config,
                        tts_cache_dir=config.get("tts_cache_dir"),
                    )
                    telemetry_web.start()

            router = get_router(config, features, llm)
            voice_thread = start_voice_pipeline(
                audio, stt, wake, router, tts, config, running,
                repeat_feature=repeat_feature,
                wake_prompts=wake_prompts,
                telemetry_store=telemetry_store,
            )
            log.info("Voice pipeline enabled.")

            # Startup / deploy announcements
            try:
                if config.get("voice_deploy_announcement", True) and is_new_deploy():
                    audio.play(tts.synthesize(pick_phrase(DEPLOY_PHRASES)))
                elif config.get("voice_startup_announcement", True):
                    audio.play(tts.synthesize(pick_phrase(STARTUP_PHRASES)))
            except Exception:
                log.exception("Announcement playback failed (non-fatal)")
        except Exception:
            log.exception("Voice pipeline failed to start — running without voice")

    refresh_interval = config.get("refresh_interval", 300)  # 5 min default

    # Build display context from whatever data sources are available
    display_ctx = DisplayContext(
        solar_storage=solar_storage,
        grocery=grocery_feature,
        reminders=reminder_feature,
        system_monitor=system_monitor,
        discovery_storage=discovery_storage,
        weather_client=weather_client,
    )

    try:
        while running.is_set():
            render_frame(display, ctx=display_ctx)
            log.info(f"Frame rendered. Next refresh in {refresh_interval}s.")

            # Sleep in small increments so we can catch signals
            for _ in range(refresh_interval):
                if not running.is_set():
                    break
                if voice_thread and not voice_thread.is_alive():
                    log.critical(
                        "Voice pipeline thread died — exiting for systemd restart"
                    )
                    sys.exit(1)
                time.sleep(1)
    finally:
        running.clear()
        if voice_thread:
            voice_thread.join(timeout=5)
        if library_collector:
            library_collector.close()
        if solar_collector:
            solar_collector.close()
        if router:
            router.close()  # cascades to features + LLM
        if telemetry_web:
            telemetry_web.close()
        if telemetry_store:
            telemetry_store.close()
        if discovery_storage:
            discovery_storage.close()
        if solar_storage:
            solar_storage.close()
        if jellyfin_client:
            jellyfin_client.close()
        if enphase_client:
            enphase_client.close()
        if sonarr_client:
            sonarr_client.close()
        if radarr_client:
            radarr_client.close()
        if tts:
            tts.close()
        if wake:
            wake.close()
        if stt:
            stt.close()
        if weather_client:
            weather_client.close()
        if system_monitor:
            system_monitor.close()
        if audio:
            audio.close()
        display.close()
        log.info("Home HUD stopped.")


if __name__ == "__main__":
    main()
