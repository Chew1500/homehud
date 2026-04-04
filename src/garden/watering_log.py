"""JSON persistence for manual watering events."""

from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timedelta
from pathlib import Path

log = logging.getLogger("home-hud.garden")


class WateringLog:
    """Thread-safe JSON-backed log of manual watering events."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._lock = threading.Lock()

    def log_watering(
        self,
        zone: str,
        amount_inches: float = 0.5,
        timestamp: datetime | None = None,
    ) -> None:
        """Record a manual watering event."""
        ts = timestamp or datetime.now()
        event = {
            "zone": zone,
            "timestamp": ts.isoformat(),
            "amount_inches": amount_inches,
        }
        with self._lock:
            events = self._load()
            events.append(event)
            self._save(events)
        log.info("Logged watering: zone=%s amount=%.2f in", zone, amount_inches)

    def get_events(self, days: int = 14) -> list[dict]:
        """Return watering events from the last N days, sorted by timestamp."""
        cutoff = datetime.now() - timedelta(days=days)
        with self._lock:
            events = self._load()
        return [
            e for e in events
            if datetime.fromisoformat(e["timestamp"]) >= cutoff
        ]

    def get_last_watering(self, zone: str) -> dict | None:
        """Return the most recent watering event for a zone."""
        with self._lock:
            events = self._load()
        for event in reversed(events):
            if event.get("zone") in (zone, "all"):
                return event
        return None

    def _load(self) -> list[dict]:
        if not self._path.is_file():
            return []
        try:
            with open(self._path) as f:
                data = json.load(f)
            return data if isinstance(data, list) else []
        except (json.JSONDecodeError, OSError):
            log.warning("Failed to read watering log %s", self._path)
            return []

    def _save(self, events: list[dict]) -> None:
        # Prune events older than 30 days
        cutoff = datetime.now() - timedelta(days=30)
        events = [
            e for e in events
            if datetime.fromisoformat(e["timestamp"]) >= cutoff
        ]
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._path, "w") as f:
            json.dump(events, f, indent=2)
            f.write("\n")
