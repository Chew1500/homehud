"""Live Open-Meteo weather client with TTL caching."""

from __future__ import annotations

import logging
import time
from datetime import date, datetime

import httpx

from weather.base import (
    BaseWeatherClient,
    CurrentWeather,
    DayForecast,
    WeatherData,
)

log = logging.getLogger("home-hud.weather")


class OpenMeteoWeatherClient(BaseWeatherClient):
    """Fetches weather from the Open-Meteo free API."""

    def __init__(self, lat: float, lon: float, ttl: int = 900) -> None:
        self._lat = lat
        self._lon = lon
        self._ttl = ttl
        self._client = httpx.Client(timeout=10.0)
        self._cache: WeatherData | None = None
        self._cache_time: float = 0.0

    def get_weather(self) -> WeatherData | None:
        now = time.monotonic()
        if self._cache and (now - self._cache_time) < self._ttl:
            return self._cache

        try:
            resp = self._client.get(
                "https://api.open-meteo.com/v1/forecast",
                params={
                    "latitude": self._lat,
                    "longitude": self._lon,
                    "current": (
                        "temperature_2m,relative_humidity_2m,"
                        "apparent_temperature,weather_code,wind_speed_10m"
                    ),
                    "daily": (
                        "weather_code,temperature_2m_max,"
                        "temperature_2m_min,precipitation_probability_max"
                    ),
                    "forecast_days": 4,
                    "temperature_unit": "fahrenheit",
                    "wind_speed_unit": "mph",
                    "timezone": "auto",
                },
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception:
            log.warning("Failed to fetch weather from Open-Meteo")
            return self._cache  # stale cache better than nothing

        cur = data.get("current", {})
        current = CurrentWeather(
            temperature_f=cur.get("temperature_2m", 0.0),
            weather_code=cur.get("weather_code", 0),
            humidity_pct=int(cur.get("relative_humidity_2m", 0)),
            wind_speed_mph=cur.get("wind_speed_10m", 0.0),
            feels_like_f=cur.get("apparent_temperature", 0.0),
        )

        daily = data.get("daily", {})
        dates = daily.get("time", [])
        codes = daily.get("weather_code", [])
        maxes = daily.get("temperature_2m_max", [])
        mins = daily.get("temperature_2m_min", [])
        precip = daily.get("precipitation_probability_max", [])

        # Skip today (index 0), take next 3 days
        forecast = []
        for i in range(1, min(4, len(dates))):
            forecast.append(
                DayForecast(
                    date=date.fromisoformat(dates[i]),
                    weather_code=codes[i] if i < len(codes) else 0,
                    temp_max_f=maxes[i] if i < len(maxes) else 0.0,
                    temp_min_f=mins[i] if i < len(mins) else 0.0,
                    precipitation_probability=int(precip[i]) if i < len(precip) else 0,
                )
            )

        result = WeatherData(current=current, forecast=forecast, fetched_at=datetime.now())
        self._cache = result
        self._cache_time = now
        log.info("Weather data refreshed from Open-Meteo")
        return result

    def close(self) -> None:
        self._client.close()
