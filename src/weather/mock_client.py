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
            history=[
                DayForecast(
                    date=today - timedelta(days=7),
                    weather_code=63, temp_max_f=70.0, temp_min_f=55.0,
                    precipitation_probability=90,
                    precipitation_mm=12.0, et0_mm=3.5,
                ),
                DayForecast(
                    date=today - timedelta(days=6),
                    weather_code=3, temp_max_f=72.0, temp_min_f=56.0,
                    precipitation_probability=20,
                    precipitation_mm=0.5, et0_mm=4.0,
                ),
                DayForecast(
                    date=today - timedelta(days=5),
                    weather_code=0, temp_max_f=78.0, temp_min_f=58.0,
                    precipitation_probability=5,
                    precipitation_mm=0.0, et0_mm=5.2,
                ),
                DayForecast(
                    date=today - timedelta(days=4),
                    weather_code=0, temp_max_f=80.0, temp_min_f=60.0,
                    precipitation_probability=5,
                    precipitation_mm=0.0, et0_mm=5.5,
                ),
                DayForecast(
                    date=today - timedelta(days=3),
                    weather_code=2, temp_max_f=76.0, temp_min_f=59.0,
                    precipitation_probability=15,
                    precipitation_mm=0.0, et0_mm=4.8,
                ),
                DayForecast(
                    date=today - timedelta(days=2),
                    weather_code=0, temp_max_f=82.0, temp_min_f=62.0,
                    precipitation_probability=5,
                    precipitation_mm=0.0, et0_mm=5.8,
                ),
                DayForecast(
                    date=today - timedelta(days=1),
                    weather_code=2, temp_max_f=79.0, temp_min_f=61.0,
                    precipitation_probability=10,
                    precipitation_mm=0.0, et0_mm=5.0,
                ),
                DayForecast(
                    date=today,
                    weather_code=2, temp_max_f=77.0, temp_min_f=60.0,
                    precipitation_probability=10,
                    precipitation_mm=0.0, et0_mm=4.5,
                ),
            ],
            forecast=[
                DayForecast(
                    date=today + timedelta(days=1),
                    weather_code=0,
                    temp_max_f=77.0,
                    temp_min_f=57.0,
                    precipitation_probability=10,
                    precipitation_mm=0.0, et0_mm=5.0,
                ),
                DayForecast(
                    date=today + timedelta(days=2),
                    weather_code=63,
                    temp_max_f=64.0,
                    temp_min_f=54.0,
                    precipitation_probability=80,
                    precipitation_mm=8.0, et0_mm=2.5,
                ),
                DayForecast(
                    date=today + timedelta(days=3),
                    weather_code=2,
                    temp_max_f=72.0,
                    temp_min_f=59.0,
                    precipitation_probability=30,
                    precipitation_mm=1.0, et0_mm=4.0,
                ),
            ],
            fetched_at=datetime.now(),
        )
