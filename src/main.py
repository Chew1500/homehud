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
from display.renderer import render_frame

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

    # Service monitoring (independent of voice pipeline)
    from monitor import get_monitor_storage

    monitor_storage = get_monitor_storage(config)
    monitor_collector = None
    display_refresh = threading.Event()
    if monitor_storage:
        from monitor.collector import ServiceCollector

        monitor_collector = ServiceCollector(
            monitor_storage, config, refresh_event=display_refresh
        )
        monitor_collector.start()
        log.info("Service monitoring enabled")

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
    garden_feature = None
    notification_manager = None
    presence_tracker = None

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

            # Notification system (reusable for garden, future features)
            from notifications.manager import NotificationManager
            from notifications.presence import PresenceTracker

            notification_manager = NotificationManager(config)
            presence_tracker = PresenceTracker(config)

            # Garden watering advisory (opt-in)
            if config.get("garden_enabled", False):
                from features.garden import GardenFeature

                garden_feature = GardenFeature(
                    config,
                    weather_client=weather_client,
                    notification_manager=notification_manager,
                )

            features = [
                repeat_feature,
                VolumeFeature(config, audio=audio),
                grocery_feature,
                reminder_feature,
                SolarFeature(config, solar_storage, llm),
                MediaFeature(config, sonarr=sonarr_client, radarr=radarr_client, llm=llm),
                discovery_feature,
                NetworkFeature(config),
            ]
            if garden_feature:
                features.insert(-1, garden_feature)  # before last (Network)
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
                        monitor_storage=monitor_storage,
                        garden_feature=garden_feature,
                        weather_client=weather_client,
                    )
                    telemetry_web.start()

            router = get_router(config, features, llm)
            voice_thread = start_voice_pipeline(
                audio, stt, wake, router, tts, config, running,
                repeat_feature=repeat_feature,
                wake_prompts=wake_prompts,
                telemetry_store=telemetry_store,
                notification_manager=notification_manager,
                presence_tracker=presence_tracker,
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
        monitor_storage=monitor_storage,
        garden_feature=garden_feature,
        orientation=config.get("display_orientation", "portrait"),
    )

    _health_check_counter = 0
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
                if telemetry_web and not telemetry_web.is_alive:
                    log.warning(
                        "Telemetry web server died — restarting"
                    )
                    try:
                        telemetry_web.start()
                    except Exception:
                        log.exception("Failed to restart telemetry web server")
                        telemetry_web = None
                elif (
                    telemetry_web
                    and _health_check_counter % 30 == 0
                    and not telemetry_web.check_health(timeout=5)
                ):
                    log.warning(
                        "Telemetry web server unresponsive — restarting"
                    )
                    try:
                        telemetry_web.close()
                        telemetry_web.start()
                    except Exception:
                        log.exception("Failed to restart telemetry web server")
                        telemetry_web = None
                _health_check_counter += 1
                if display_refresh.is_set():
                    display_refresh.clear()
                    log.info("Display refresh triggered by monitor")
                    break
                time.sleep(1)
    finally:
        running.clear()
        if voice_thread:
            voice_thread.join(timeout=5)
        if library_collector:
            library_collector.close()
        if monitor_collector:
            monitor_collector.close()
        if monitor_storage:
            monitor_storage.close()
        if solar_collector:
            solar_collector.close()
        if garden_feature:
            garden_feature.close()
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
