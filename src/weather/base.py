"""Weather data models and base client ABC."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime


@dataclass
class CurrentWeather:
    """Current weather conditions."""

    temperature_c: float
    weather_code: int
    humidity_pct: int
    wind_speed_kmh: float
    feels_like_c: float


@dataclass
class DayForecast:
    """Single day forecast."""

    date: date
    weather_code: int
    temp_max_c: float
    temp_min_c: float
    precipitation_probability: int


@dataclass
class WeatherData:
    """Combined current conditions and forecast."""

    current: CurrentWeather
    forecast: list[DayForecast] = field(default_factory=list)
    fetched_at: datetime = field(default_factory=datetime.now)


class BaseWeatherClient(ABC):
    """ABC for weather data providers."""

    @abstractmethod
    def get_weather(self) -> WeatherData | None:
        """Fetch current conditions and forecast."""

    def close(self) -> None:
        """Release resources."""
