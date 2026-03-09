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

    # -- Header (red bar) --
    draw.rectangle([(0, 0), (width, 56)], fill="red")
    draw.text((12, 12), "HOME HUD", fill="white", font=font_lg)

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

    # -- Timestamp --
    from datetime import datetime

    now = datetime.now().strftime("%B %d, %Y  %I:%M %p")
    draw.text((12, 68), now, fill="black", font=font_md)

    # -- Solar panel (full width) --
    draw.rectangle([(12, 100), (width - 12, 360)], outline="red", width=2)
    draw.text((20, 108), "Solar Production", fill="red", font=font_md)

    solar_storage = ctx.solar_storage if ctx else None
    if solar_storage is None:
        draw.text((20, 145), "-- kW", fill="black", font=font_lg)
        draw.text((20, 190), "Solar: not configured", fill="black", font=font_sm)
    else:
        reading = solar_storage.get_latest()
        if reading:
            prod_kw = reading["production_w"] / 1000
            cons_kw = reading["consumption_w"] / 1000
            net_w = reading["net_w"]
            draw.text((20, 145), f"{prod_kw:.1f} kW", fill="black", font=font_lg)
            draw.text((20, 190), f"Using {cons_kw:.1f} kW", fill="black", font=font_sm)
            if net_w >= 0:
                draw.text((20, 215), f"Exporting {net_w / 1000:.1f} kW", fill="black", font=font_sm)
            else:
                imp_kw = abs(net_w) / 1000
                draw.text((20, 215), f"Importing {imp_kw:.1f} kW", fill="red", font=font_sm)
        else:
            draw.text((20, 145), "-- kW", fill="black", font=font_lg)
            draw.text((20, 190), "Waiting for Enphase...", fill="black", font=font_sm)

    # -- Grocery list (full width, compact) --
    draw.rectangle([(12, 380), (width - 12, 600)], outline="red", width=2)
    draw.text((20, 388), "Grocery List", fill="red", font=font_md)

    grocery = ctx.grocery if ctx else None
    if grocery is None:
        draw.text((20, 420), "Not configured", fill="black", font=font_sm)
    else:
        items = grocery.get_items()
        if not items:
            draw.text((20, 420), "No items", fill="black", font=font_sm)
        else:
            max_visible = 8
            y = 416
            for item in items[:max_visible]:
                draw.text((20, y), f"- {item}", fill="black", font=font_sm)
                y += 22
            overflow = len(items) - max_visible
            if overflow > 0:
                draw.text((20, y), f"+{overflow} more", fill="black", font=font_sm)

    # -- Recommendations panel (full width) --
    draw.rectangle([(12, 620), (width - 12, 760)], outline="red", width=2)
    draw.text((20, 628), "Recommendations", fill="red", font=font_md)

    discovery_storage = ctx.discovery_storage if ctx else None
    if discovery_storage is None:
        draw.text((20, 656), "Not configured", fill="black", font=font_sm)
    else:
        try:
            recs = discovery_storage.get_active_recommendations()
        except Exception:
            recs = []
        if not recs:
            draw.text((20, 656), "No recommendations yet", fill="black", font=font_sm)
        else:
            y = 656
            for rec in recs[:3]:
                type_icon = "F" if rec["media_type"] == "movie" else "T"
                year_str = f" ({rec['year']})" if rec.get("year") else ""
                draw.text(
                    (20, y),
                    f"[{type_icon}] {rec['title']}{year_str}",
                    fill="black",
                    font=font_sm,
                )
                y += 22
            overflow = len(recs) - 3
            if overflow > 0:
                draw.text((20, y), f"+{overflow} more", fill="black", font=font_sm)

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
        if system_monitor:
            system_monitor.close()
        if audio:
            audio.close()
        display.close()
        log.info("Home HUD stopped.")


if __name__ == "__main__":
    main()
