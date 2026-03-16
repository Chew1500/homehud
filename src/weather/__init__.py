"""Weather package — current conditions + forecast via Open-Meteo."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from weather.base import BaseWeatherClient


def get_weather_client(config: dict) -> BaseWeatherClient | None:
    """Create a weather client based on config.

    Returns None if latitude/longitude are not configured.
    Reuses solar_latitude / solar_longitude config keys.
    """
    lat = config.get("solar_latitude", "")
    lon = config.get("solar_longitude", "")

    if config.get("display_mode") == "mock" or (not lat or not lon):
        from weather.mock_client import MockWeatherClient

        return MockWeatherClient()

    from weather.client import OpenMeteoWeatherClient

    ttl = config.get("weather_poll_interval", 900)
    return OpenMeteoWeatherClient(float(lat), float(lon), ttl=ttl)
