"""Mock weather client for local development."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from weather.base import (
    BaseWeatherClient,
    CurrentWeather,
    DayForecast,
    WeatherData,
)


class MockWeatherClient(BaseWeatherClient):
    """Returns static weather data for make dev."""

    def get_weather(self) -> WeatherData:
        today = date.today()
        return WeatherData(
            current=CurrentWeather(
                temperature_f=72.0,
                weather_code=2,  # Partly cloudy
                humidity_pct=65,
                wind_speed_mph=7.0,
                feels_like_f=68.0,
            ),
            forecast=[
                DayForecast(
                    date=today + timedelta(days=1),
                    weather_code=0,
                    temp_max_f=77.0,
                    temp_min_f=57.0,
                    precipitation_probability=10,
                ),
                DayForecast(
                    date=today + timedelta(days=2),
                    weather_code=63,
                    temp_max_f=64.0,
                    temp_min_f=54.0,
                    precipitation_probability=80,
                ),
                DayForecast(
                    date=today + timedelta(days=3),
                    weather_code=2,
                    temp_max_f=72.0,
                    temp_min_f=59.0,
                    precipitation_probability=30,
                ),
            ],
            fetched_at=datetime.now(),
        )
