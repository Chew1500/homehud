"""Open-Meteo weather helper for solar context."""

from __future__ import annotations

import logging

log = logging.getLogger("home-hud.enphase.weather")


def get_current_weather(lat: float, lon: float) -> dict | None:
    """Fetch current weather from the Open-Meteo API.

    Args:
        lat: Latitude
        lon: Longitude

    Returns:
        Dict with temperature_c, cloud_cover_pct, weather_code, or None on failure.
    """
    import httpx

    try:
        resp = httpx.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,cloud_cover,weather_code",
            },
            timeout=10.0,
        )
        resp.raise_for_status()
        current = resp.json().get("current", {})
        return {
            "temperature_c": current.get("temperature_2m"),
            "cloud_cover_pct": current.get("cloud_cover"),
            "weather_code": current.get("weather_code"),
        }
    except Exception:
        log.warning("Failed to fetch weather data from Open-Meteo")
        return None
