"""Background collector — polls Enphase gateway and stores readings."""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime

from enphase.base import BaseEnphaseClient
from enphase.storage import SolarStorage

log = logging.getLogger("home-hud.enphase.collector")


class SolarCollector:
    """Daemon thread that polls the Enphase gateway and stores readings in SQLite.

    - Polls production data every poll_interval seconds (default: 60)
    - Polls inverter data every 5 minutes
    - Polls weather every 15 minutes
    - Updates daily summary after each reading
    """

    def __init__(
        self,
        client: BaseEnphaseClient,
        storage: SolarStorage,
        config: dict,
    ):
        self._client = client
        self._storage = storage
        self._poll_interval = config.get("enphase_poll_interval", 60)
        self._lat = config.get("solar_latitude", "")
        self._lon = config.get("solar_longitude", "")
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

        # Cache weather between polls
        self._weather: dict | None = None
        self._weather_last_poll = 0.0
        self._inverter_last_poll = 0.0

    def start(self) -> threading.Thread:
        """Start the collector daemon thread."""
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        log.info(
            "Solar collector started (poll every %ds)", self._poll_interval
        )
        return self._thread

    def _loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._collect()
            except Exception:
                log.exception("Error in solar collector cycle")

            self._stop_event.wait(timeout=self._poll_interval)

    def _collect(self) -> None:
        """Run one collection cycle."""
        now = time.time()

        # Fetch production data
        production = self._client.get_production()
        if not production:
            return

        # Fetch weather (every 15 minutes)
        if self._lat and self._lon and (now - self._weather_last_poll > 900):
            from enphase.weather import get_current_weather
            self._weather = get_current_weather(
                float(self._lat), float(self._lon)
            )
            self._weather_last_poll = now

        # Store reading
        weather = self._weather or {}
        self._storage.store_reading(
            production_w=production["production_w"],
            consumption_w=production["consumption_w"],
            net_w=production["net_w"],
            production_wh=production["production_wh"],
            consumption_wh=production["consumption_wh"],
            temperature_c=weather.get("temperature_c"),
            cloud_cover_pct=weather.get("cloud_cover_pct"),
            weather_code=weather.get("weather_code"),
        )

        # Fetch inverters (every 5 minutes)
        if now - self._inverter_last_poll > 300:
            inverters = self._client.get_inverters()
            if inverters:
                self._storage.store_inverter_readings(inverters)
            self._inverter_last_poll = now

        # Update daily summary
        today = datetime.now().strftime("%Y-%m-%d")
        self._storage.update_daily_summary(today)

        log.debug(
            "Collected: %.0fW production, %.0fW consumption",
            production["production_w"],
            production["consumption_w"],
        )

    def close(self) -> None:
        """Stop the collector thread."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
            log.info("Solar collector stopped")
