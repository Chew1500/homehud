"""Water balance algorithm for garden watering advisory.

Uses the "checkbook" model: tracks a running moisture deficit per plant zone.
Each day: deficit += ET0 * Kc - rainfall - manual_watering
Clamped at 0 minimum (soil can't be wetter than saturated).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from weather.base import DayForecast

MM_PER_INCH = 25.4


@dataclass(frozen=True)
class ZoneConfig:
    """Configuration for a single garden zone."""

    name: str
    label: str  # human-readable
    kc: float  # crop coefficient
    threshold_inches: float  # deficit threshold before alerting


# Default zone configurations for central Arkansas
DEFAULT_ZONES: dict[str, ZoneConfig] = {
    "lawn": ZoneConfig("lawn", "lawn", kc=0.80, threshold_inches=0.50),
    "vegetable_garden": ZoneConfig(
        "vegetable_garden", "vegetable garden", kc=1.05, threshold_inches=0.40,
    ),
    "young_trees": ZoneConfig(
        "young_trees", "young trees", kc=0.70, threshold_inches=0.75,
    ),
    "established_trees": ZoneConfig(
        "established_trees", "established trees", kc=0.60, threshold_inches=1.00,
    ),
}


@dataclass
class ZoneStatus:
    """Current water balance status for a single zone."""

    zone: str
    label: str
    deficit_inches: float
    threshold_inches: float
    urgency: str  # "ok", "monitor", "water_today", "urgent"
    forecast_rain_inches: float
    days_since_rain: int | None
    days_since_watered: int | None


def _mm_to_inches(mm: float) -> float:
    return mm / MM_PER_INCH


def _forecast_rain(forecast: list[DayForecast]) -> tuple[float, bool]:
    """Estimate upcoming rain from forecast.

    Returns (expected_inches, significant_rain_soon).
    significant_rain_soon is True if >60% probability and >0.25" expected
    within the next day.
    """
    total_inches = 0.0
    significant_soon = False

    for i, day in enumerate(forecast):
        # Weight forecast precipitation by probability
        expected_mm = day.precipitation_mm * day.precipitation_probability / 100.0
        total_inches += _mm_to_inches(expected_mm)

        if i == 0 and day.precipitation_probability > 60:
            day_inches = _mm_to_inches(expected_mm)
            if day_inches > 0.25:
                significant_soon = True

    return total_inches, significant_soon


def _days_since_last_rain(history: list[DayForecast], today: date) -> int | None:
    """Count days since last measurable rainfall (>1mm)."""
    for day in reversed(history):
        if day.precipitation_mm > 1.0:
            return (today - day.date).days
    return None


def _days_since_last_watering(
    watering_events: list[dict], zone: str, today: date,
) -> int | None:
    """Count days since last manual watering for a zone."""
    for event in reversed(watering_events):
        if event.get("zone") == zone or event.get("zone") == "all":
            event_date = date.fromisoformat(event["timestamp"][:10])
            return (today - event_date).days
    return None


def _classify_urgency(
    deficit: float, threshold: float, significant_rain_soon: bool,
) -> str:
    """Classify urgency level from deficit ratio."""
    if deficit <= 0:
        return "ok"

    ratio = deficit / threshold
    if ratio < 0.5:
        return "ok"
    if ratio < 0.8:
        return "monitor"
    if ratio >= 1.5:
        return "urgent"
    # ratio >= 0.8 and < 1.5
    if ratio >= 1.0 and not significant_rain_soon:
        return "water_today"
    return "monitor"


def compute_balance(
    history: list[DayForecast],
    forecast: list[DayForecast],
    watering_events: list[dict],
    zones: dict[str, ZoneConfig] | None = None,
) -> list[ZoneStatus]:
    """Compute water balance status for all zones.

    Args:
        history: Past weather days (up to 7 days + today) from Open-Meteo.
        forecast: Upcoming weather days (up to 3 days).
        watering_events: Manual watering events from WateringLog.
        zones: Zone configurations. Defaults to DEFAULT_ZONES.

    Returns:
        List of ZoneStatus, one per zone.
    """
    if zones is None:
        zones = DEFAULT_ZONES

    today = date.today()
    forecast_rain, significant_rain_soon = _forecast_rain(forecast)
    days_rain = _days_since_last_rain(history, today)

    results = []
    for zone_name, zc in zones.items():
        # Compute deficit from historical data
        deficit_inches = 0.0
        for day in history:
            et_loss = _mm_to_inches(day.et0_mm * zc.kc)
            rain_gain = _mm_to_inches(day.precipitation_mm)
            deficit_inches += et_loss - rain_gain

        # Subtract manual watering events
        for event in watering_events:
            event_date = date.fromisoformat(event["timestamp"][:10])
            # Only count events within the history window
            if any(d.date == event_date for d in history):
                if event.get("zone") in (zone_name, "all"):
                    deficit_inches -= event.get("amount_inches", 0.5)

        # Clamp: can't have negative deficit (surplus doesn't accumulate)
        deficit_inches = max(0.0, deficit_inches)

        urgency = _classify_urgency(
            deficit_inches, zc.threshold_inches, significant_rain_soon,
        )

        results.append(ZoneStatus(
            zone=zone_name,
            label=zc.label,
            deficit_inches=round(deficit_inches, 2),
            threshold_inches=zc.threshold_inches,
            urgency=urgency,
            forecast_rain_inches=round(forecast_rain, 2),
            days_since_rain=days_rain,
            days_since_watered=_days_since_last_watering(
                watering_events, zone_name, today,
            ),
        ))

    return results
