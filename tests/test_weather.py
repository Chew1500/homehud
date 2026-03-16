"""Tests for the weather package."""

from datetime import date

from weather.base import CurrentWeather, DayForecast, WeatherData
from weather.codes import describe_weather
from weather.mock_client import MockWeatherClient


class TestWMOCodes:
    """Test WMO weather code descriptions."""

    def test_clear_sky(self):
        assert describe_weather(0) == "Clear sky"

    def test_rain(self):
        assert describe_weather(63) == "Rain"

    def test_thunderstorm(self):
        assert describe_weather(95) == "Thunderstorm"

    def test_unknown_code(self):
        assert describe_weather(999) == "Unknown"

    def test_all_known_codes_return_strings(self):
        known_codes = [0, 1, 2, 3, 45, 48, 51, 53, 55, 56, 57, 61, 63, 65,
                       66, 67, 71, 73, 75, 77, 80, 81, 82, 85, 86, 95, 96, 99]
        for code in known_codes:
            result = describe_weather(code)
            assert isinstance(result, str)
            assert result != "Unknown"


class TestMockClient:
    """Test MockWeatherClient returns valid data."""

    def test_returns_weather_data(self):
        client = MockWeatherClient()
        data = client.get_weather()
        assert isinstance(data, WeatherData)

    def test_current_conditions(self):
        client = MockWeatherClient()
        data = client.get_weather()
        cur = data.current
        assert isinstance(cur, CurrentWeather)
        assert cur.temperature_c == 22.0
        assert cur.humidity_pct == 65
        assert cur.weather_code == 2

    def test_forecast_has_three_days(self):
        client = MockWeatherClient()
        data = client.get_weather()
        assert len(data.forecast) == 3

    def test_forecast_dates_are_future(self):
        client = MockWeatherClient()
        data = client.get_weather()
        today = date.today()
        for day in data.forecast:
            assert isinstance(day, DayForecast)
            assert day.date > today

    def test_forecast_temperatures_valid(self):
        client = MockWeatherClient()
        data = client.get_weather()
        for day in data.forecast:
            assert day.temp_max_c >= day.temp_min_c

    def test_precipitation_probability_range(self):
        client = MockWeatherClient()
        data = client.get_weather()
        for day in data.forecast:
            assert 0 <= day.precipitation_probability <= 100


class TestAPIResponseParsing:
    """Test parsing of Open-Meteo API response format."""

    def test_parse_current_weather(self):
        """Verify CurrentWeather can be constructed from API-like values."""
        cur = CurrentWeather(
            temperature_c=18.5,
            weather_code=61,
            humidity_pct=82,
            wind_speed_kmh=25.3,
            feels_like_c=16.0,
        )
        assert cur.temperature_c == 18.5
        assert cur.weather_code == 61
        assert cur.feels_like_c == 16.0

    def test_parse_day_forecast(self):
        """Verify DayForecast can be constructed from API-like values."""
        day = DayForecast(
            date=date(2026, 3, 16),
            weather_code=3,
            temp_max_c=20.0,
            temp_min_c=10.0,
            precipitation_probability=45,
        )
        assert day.temp_max_c == 20.0
        assert day.precipitation_probability == 45

    def test_weather_data_defaults(self):
        """WeatherData should have sensible defaults."""
        cur = CurrentWeather(
            temperature_c=0.0, weather_code=0,
            humidity_pct=0, wind_speed_kmh=0.0, feels_like_c=0.0,
        )
        data = WeatherData(current=cur)
        assert data.forecast == []
        assert data.fetched_at is not None
