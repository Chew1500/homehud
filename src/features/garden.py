"""Garden watering advisory — water balance tracking with proactive alerts."""

from __future__ import annotations

import logging
import re
import threading

from features.base import BaseFeature
from garden.balance import (
    DEFAULT_ZONES,
    ZoneStatus,
    compute_balance,
)
from garden.watering_log import WateringLog
from notifications.manager import Notification, NotificationManager
from weather.base import BaseWeatherClient

log = logging.getLogger("home-hud.features.garden")

# --- Regex patterns ---

_STATUS = re.compile(
    r"\b(?:garden|watering|water)\s*(?:status|report|update)\b"
    r"|\bdo\s+i\s+need\s+to\s+water\b"
    r"|\bshould\s+i\s+water\b"
    r"|\bhow(?:'s| is)\s+the\s+garden\b",
    re.IGNORECASE,
)

_LOG_WATER = re.compile(
    r"\bi\s+(?:just\s+)?watered\s+(?:the\s+)?(.+)"
    r"|\blog\s+watering\s+(?:for\s+)?(?:the\s+)?(.+)",
    re.IGNORECASE,
)

_ZONE_STATUS = re.compile(
    r"\b(?:how(?:'s| is| are)\s+the\s+(.+?))\s*\??\s*$"
    r"|\bdoes?\s+(?:the\s+)?(.+?)\s+need\s+water",
    re.IGNORECASE,
)

_HISTORY = re.compile(
    r"\b(?:watering|water)\s*history\b"
    r"|\bwhen\s+did\s+i\s+(?:last\s+)?water\b",
    re.IGNORECASE,
)

# Fuzzy zone name mapping
_ZONE_ALIASES: dict[str, str] = {
    "lawn": "lawn",
    "grass": "lawn",
    "yard": "lawn",
    "vegetable garden": "vegetable_garden",
    "vegetables": "vegetable_garden",
    "veggie garden": "vegetable_garden",
    "veggies": "vegetable_garden",
    "garden": "vegetable_garden",
    "young trees": "young_trees",
    "new trees": "young_trees",
    "saplings": "young_trees",
    "established trees": "established_trees",
    "old trees": "established_trees",
    "mature trees": "established_trees",
    "trees": "_all_trees",  # maps to both tree zones
    "everything": "all",
    "all": "all",
    "all zones": "all",
}


def _resolve_zone(text: str) -> list[str]:
    """Resolve user text to one or more zone names."""
    text = text.strip().lower()
    alias = _ZONE_ALIASES.get(text)
    if alias == "_all_trees":
        return ["young_trees", "established_trees"]
    if alias == "all":
        return list(DEFAULT_ZONES.keys())
    if alias:
        return [alias]
    # Try partial match
    for key, value in _ZONE_ALIASES.items():
        if key in text:
            if value == "_all_trees":
                return ["young_trees", "established_trees"]
            if value == "all":
                return list(DEFAULT_ZONES.keys())
            return [value]
    return list(DEFAULT_ZONES.keys())  # default to all


def _format_status(statuses: list[ZoneStatus]) -> str:
    """Format zone statuses into a TTS-friendly response."""
    needs_water = [s for s in statuses if s.urgency in ("water_today", "urgent")]
    monitoring = [s for s in statuses if s.urgency == "monitor"]

    parts = []

    if not needs_water and not monitoring:
        parts.append("Your garden looks good right now.")
        if statuses and statuses[0].days_since_rain is not None:
            days = statuses[0].days_since_rain
            if days == 0:
                parts.append("It rained today.")
            elif days == 1:
                parts.append("It rained yesterday.")
            else:
                parts.append(f"Last rain was {days} days ago.")
        if statuses and statuses[0].forecast_rain_inches > 0.1:
            parts.append("Rain is in the forecast.")
        return " ".join(parts)

    if needs_water:
        urgent = [s for s in needs_water if s.urgency == "urgent"]
        regular = [s for s in needs_water if s.urgency == "water_today"]

        if urgent:
            labels = ", ".join(s.label for s in urgent)
            parts.append(f"Your {labels} urgently need water.")
        if regular:
            labels = ", ".join(s.label for s in regular)
            parts.append(f"Your {labels} should be watered today.")

        # Add context
        sample = needs_water[0]
        if sample.days_since_rain is not None:
            if sample.days_since_rain > 2:
                parts.append(
                    f"It's been {sample.days_since_rain} days since the last rain."
                )
        if sample.deficit_inches > 0:
            parts.append(
                f"The moisture deficit is about {sample.deficit_inches:.1f} inches."
            )

    if monitoring:
        labels = ", ".join(s.label for s in monitoring)
        if needs_water:
            parts.append(f"Your {labels} should be fine for another day or two.")
        else:
            parts.append(
                f"Your {labels} are getting dry but don't need water yet."
            )

    if statuses and statuses[0].forecast_rain_inches > 0.1:
        parts.append(
            f"About {statuses[0].forecast_rain_inches:.1f} inches of rain "
            "is expected in the next few days."
        )

    return " ".join(parts)


def _format_zone_status(status: ZoneStatus) -> str:
    """Format a single zone status for TTS."""
    if status.urgency == "ok":
        msg = f"Your {status.label} looks fine."
    elif status.urgency == "monitor":
        msg = f"Your {status.label} is getting a bit dry but should be okay for now."
    elif status.urgency == "water_today":
        msg = (
            f"Your {status.label} needs water today. "
            f"The deficit is about {status.deficit_inches:.1f} inches."
        )
    else:  # urgent
        msg = (
            f"Your {status.label} urgently needs water. "
            f"The deficit is {status.deficit_inches:.1f} inches."
        )

    if status.days_since_watered is not None:
        if status.days_since_watered == 0:
            msg += " You watered it today."
        elif status.days_since_watered == 1:
            msg += " You last watered it yesterday."
        else:
            msg += f" You last watered it {status.days_since_watered} days ago."

    return msg


class GardenFeature(BaseFeature):
    """Garden watering advisory with background monitoring."""

    def __init__(
        self,
        config: dict,
        weather_client: BaseWeatherClient,
        notification_manager: NotificationManager | None = None,
    ) -> None:
        super().__init__(config)
        self._weather = weather_client
        self._notifier = notification_manager
        self._watering_log = WateringLog(
            config.get("garden_watering_file", "data/watering.json"),
        )
        self._default_amount = config.get("garden_default_water_inches", 0.5)
        self._check_interval = config.get("garden_check_interval", 3600)

        # Parse enabled zones
        zone_str = config.get(
            "garden_zones", "lawn,vegetable_garden,young_trees,established_trees",
        )
        zone_names = [z.strip() for z in zone_str.split(",") if z.strip()]
        self._zones = {
            name: DEFAULT_ZONES[name]
            for name in zone_names
            if name in DEFAULT_ZONES
        }

        # Background checker
        self._stop_event = threading.Event()
        self._checker = threading.Thread(
            target=self._checker_loop, daemon=True, name="garden-checker",
        )
        self._checker.start()

    @property
    def name(self) -> str:
        return "Garden Watering"

    @property
    def short_description(self) -> str:
        return "Tracks soil moisture and advises when to water your garden."

    @property
    def description(self) -> str:
        return (
            "Handles garden watering queries: 'do I need to water', "
            "'garden status', 'I watered the lawn', 'watering history', "
            "'how are the trees'. Also accepts logging of manual watering events."
        )

    @property
    def action_schema(self) -> dict:
        return {
            "status": {},
            "zone_status": {"zone": "str"},
            "log_watering": {"zone": "str"},
            "history": {},
        }

    def matches(self, text: str) -> bool:
        return bool(
            _STATUS.search(text)
            or _LOG_WATER.search(text)
            or _HISTORY.search(text)
        )

    def handle(self, text: str) -> str:
        if _LOG_WATER.search(text):
            m = _LOG_WATER.search(text)
            zone_text = (m.group(1) or m.group(2) or "all").strip()
            return self._log_watering(zone_text)

        if _HISTORY.search(text):
            return self._get_history()

        if _ZONE_STATUS.search(text):
            m = _ZONE_STATUS.search(text)
            zone_text = (m.group(1) or m.group(2) or "").strip()
            return self._zone_status(zone_text)

        return self._full_status()

    def execute(self, action: str, parameters: dict) -> str:
        if action == "status":
            return self._full_status()
        if action == "zone_status":
            return self._zone_status(parameters.get("zone", ""))
        if action == "log_watering":
            return self._log_watering(parameters.get("zone", "all"))
        if action == "history":
            return self._get_history()
        raise NotImplementedError(f"Unknown action: {action}")

    def get_status(self) -> list[ZoneStatus]:
        """Get current zone statuses. Used by display renderer."""
        weather = self._weather.get_weather()
        if not weather:
            return []
        events = self._watering_log.get_events(days=14)
        return compute_balance(
            weather.history, weather.forecast, events, self._zones,
        )

    def _full_status(self) -> str:
        statuses = self.get_status()
        if not statuses:
            return "I can't check the garden right now. Weather data is unavailable."
        return _format_status(statuses)

    def _zone_status(self, zone_text: str) -> str:
        zone_names = _resolve_zone(zone_text)
        statuses = self.get_status()
        if not statuses:
            return "I can't check the garden right now. Weather data is unavailable."
        matching = [s for s in statuses if s.zone in zone_names]
        if not matching:
            return _format_status(statuses)
        if len(matching) == 1:
            return _format_zone_status(matching[0])
        return _format_status(matching)

    def _log_watering(self, zone_text: str) -> str:
        zone_names = _resolve_zone(zone_text)
        for zone_name in zone_names:
            self._watering_log.log_watering(zone_name, self._default_amount)
        if len(zone_names) == 1 and zone_names[0] in self._zones:
            label = self._zones[zone_names[0]].label
        elif len(zone_names) == len(self._zones):
            label = "everything"
        else:
            labels = []
            for z in zone_names:
                if z in self._zones:
                    labels.append(self._zones[z].label)
            label = " and ".join(labels)
        return f"Got it, I've logged that you watered the {label}."

    def _get_history(self) -> str:
        events = self._watering_log.get_events(days=14)
        if not events:
            return "I don't have any watering events recorded."
        latest = events[-1]
        zone_label = latest.get("zone", "garden")
        if zone_label in self._zones:
            zone_label = self._zones[zone_label].label
        ts = latest["timestamp"][:10]
        count = len(events)
        if count == 1:
            return f"Your last watering was on {ts} for the {zone_label}."
        return (
            f"You've watered {count} times in the past two weeks. "
            f"The most recent was on {ts} for the {zone_label}."
        )

    def _checker_loop(self) -> None:
        """Background thread: periodically check zones and submit notifications."""
        while not self._stop_event.wait(timeout=self._check_interval):
            if not self._notifier:
                continue
            try:
                statuses = self.get_status()
                needs_water = [
                    s for s in statuses
                    if s.urgency in ("water_today", "urgent")
                ]
                if needs_water:
                    labels = ", ".join(s.label for s in needs_water)
                    urgent = any(s.urgency == "urgent" for s in needs_water)
                    message = (
                        f"Your {labels} {'urgently need' if urgent else 'could use'} "
                        f"some water. It's been "
                        f"{needs_water[0].days_since_rain or 'several'} days "
                        f"since the last rain."
                    )
                    self._notifier.submit(Notification(
                        category="garden",
                        message=message,
                        priority=2 if urgent else 1,
                        cooldown_key="garden:water_needed",
                    ))
            except Exception:
                log.exception("Garden checker failed")

    def close(self) -> None:
        self._stop_event.set()
        self._checker.join(timeout=5)
