"""Tests for Enphase client, storage, and collector."""

import base64
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from enphase.client import EnphaseClient  # noqa: E402
from enphase.collector import SolarCollector  # noqa: E402
from enphase.mock_client import MockEnphaseClient  # noqa: E402
from enphase.storage import SolarStorage  # noqa: E402


def _make_jwt(exp_timestamp: int) -> str:
    """Build a minimal JWT with only an exp claim (no real signature)."""
    header = base64.urlsafe_b64encode(json.dumps({"alg": "none"}).encode()).rstrip(b"=")
    payload = base64.urlsafe_b64encode(json.dumps({"exp": exp_timestamp}).encode()).rstrip(b"=")
    return f"{header.decode()}.{payload.decode()}.fakesig"


def _make_config(tmp_path):
    return {
        "enphase_mode": "mock",
        "solar_db_path": str(tmp_path / "solar.db"),
        "enphase_poll_interval": 600,
        "solar_latitude": "",
        "solar_longitude": "",
    }


# -- MockEnphaseClient --


def test_mock_production():
    client = MockEnphaseClient({})
    data = client.get_production()
    assert "production_w" in data
    assert "consumption_w" in data
    assert "net_w" in data
    assert "production_wh" in data
    assert "consumption_wh" in data
    assert data["production_w"] > 0


def test_mock_inverters():
    client = MockEnphaseClient({})
    inverters = client.get_inverters()
    assert len(inverters) == 24
    assert "serial" in inverters[0]
    assert "watts" in inverters[0]
    assert "max_watts" in inverters[0]


def test_mock_health():
    client = MockEnphaseClient({})
    assert client.check_health() is True


# -- SolarStorage --


def test_storage_store_and_get_latest(tmp_path):
    storage = SolarStorage(str(tmp_path / "solar.db"))
    storage.store_reading(
        production_w=4200, consumption_w=1800, net_w=2400,
        production_wh=18500, consumption_wh=12300,
    )
    latest = storage.get_latest()
    assert latest is not None
    assert latest["production_w"] == 4200
    assert latest["consumption_w"] == 1800
    assert latest["net_w"] == 2400
    storage.close()


def test_storage_with_weather(tmp_path):
    storage = SolarStorage(str(tmp_path / "solar.db"))
    storage.store_reading(
        production_w=4200, consumption_w=1800, net_w=2400,
        production_wh=18500, consumption_wh=12300,
        temperature_c=25.0, cloud_cover_pct=10.0, weather_code=0,
    )
    latest = storage.get_latest()
    assert latest["temperature_c"] == 25.0
    assert latest["cloud_cover_pct"] == 10.0
    assert latest["weather_code"] == 0
    storage.close()


def test_storage_store_inverters(tmp_path):
    storage = SolarStorage(str(tmp_path / "solar.db"))
    inverters = [
        {"serial": "ABC001", "watts": 175, "max_watts": 295},
        {"serial": "ABC002", "watts": 180, "max_watts": 295},
    ]
    storage.store_inverter_readings(inverters)

    rows = storage._conn.execute("SELECT * FROM inverter_readings").fetchall()
    assert len(rows) == 2
    assert rows[0]["serial_number"] == "ABC001"
    storage.close()


def test_storage_daily_summary(tmp_path):
    storage = SolarStorage(str(tmp_path / "solar.db"))
    from datetime import datetime

    today = datetime.now().strftime("%Y-%m-%d")

    storage.store_reading(
        production_w=3000, consumption_w=1500, net_w=1500,
        production_wh=10000, consumption_wh=8000,
        temperature_c=20.0, cloud_cover_pct=30.0,
    )
    storage.store_reading(
        production_w=5000, consumption_w=2000, net_w=3000,
        production_wh=15000, consumption_wh=10000,
        temperature_c=25.0, cloud_cover_pct=10.0,
    )

    storage.update_daily_summary(today)
    summary = storage.get_today_summary()

    assert summary is not None
    assert summary["peak_production_w"] == 5000
    assert summary["total_production_wh"] == 15000  # MAX
    assert summary["reading_count"] == 2
    assert summary["avg_temperature_c"] == 22.5
    storage.close()


def test_storage_get_daily_summaries(tmp_path):
    storage = SolarStorage(str(tmp_path / "solar.db"))
    # Insert summaries directly
    storage._conn.execute(
        "INSERT INTO daily_summary VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("2026-02-23", 20000, 15000, 5500, 22.0, 20.0, 100),
    )
    storage._conn.execute(
        "INSERT INTO daily_summary VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("2026-02-24", 18000, 14000, 5000, 24.0, 30.0, 90),
    )
    storage._conn.commit()

    summaries = storage.get_daily_summaries(days=7)
    assert len(summaries) == 2
    assert summaries[0]["date"] == "2026-02-24"
    storage.close()


def test_storage_similar_days(tmp_path):
    storage = SolarStorage(str(tmp_path / "solar.db"))
    storage._conn.execute(
        "INSERT INTO daily_summary VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("2026-02-20", 20000, 15000, 5500, 22.0, 20.0, 100),
    )
    storage._conn.execute(
        "INSERT INTO daily_summary VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("2026-02-21", 18000, 14000, 5000, 35.0, 30.0, 90),
    )
    storage._conn.commit()

    # Should match first day (22C within 5C of 20C)
    similar = storage.get_similar_days(temp_c=20.0, tolerance=5.0)
    assert len(similar) == 1
    assert similar[0]["date"] == "2026-02-20"
    storage.close()


def test_storage_get_latest_empty(tmp_path):
    storage = SolarStorage(str(tmp_path / "solar.db"))
    assert storage.get_latest() is None
    storage.close()


def test_storage_get_today_summary_empty(tmp_path):
    storage = SolarStorage(str(tmp_path / "solar.db"))
    assert storage.get_today_summary() is None
    storage.close()


# -- SolarCollector lifecycle --


def test_collector_start_stop(tmp_path):
    config = _make_config(tmp_path)
    client = MockEnphaseClient(config)
    storage = SolarStorage(str(tmp_path / "solar.db"))
    collector = SolarCollector(client, storage, config)

    thread = collector.start()
    assert thread.is_alive()

    collector.close()
    assert not thread.is_alive()
    storage.close()


def test_collector_stores_reading(tmp_path):
    config = _make_config(tmp_path)
    config["enphase_poll_interval"] = 1
    client = MockEnphaseClient(config)
    storage = SolarStorage(str(tmp_path / "solar.db"))
    collector = SolarCollector(client, storage, config)

    collector.start()
    # Wait for at least one collection cycle
    time.sleep(2)
    collector.close()

    latest = storage.get_latest()
    assert latest is not None
    assert latest["production_w"] > 0
    storage.close()


# -- JWT expiry decoding --


def _make_client_for_token_tests(tmp_path) -> EnphaseClient:
    """Create a bare EnphaseClient without calling __init__ (no httpx needed)."""
    client = EnphaseClient.__new__(EnphaseClient)
    client._config = {
        "enphase_host": "127.0.0.1",
        "solar_db_path": str(tmp_path / "solar.db"),
        "enphase_token": "",
    }
    client._token_path = Path(tmp_path / ".enphase_token")
    return client


def test_decode_token_expiry_valid(tmp_path):
    client = _make_client_for_token_tests(tmp_path)
    future = datetime(2027, 2, 24, 12, 0, 0, tzinfo=timezone.utc)
    token = _make_jwt(int(future.timestamp()))

    expiry = client._decode_token_expiry(token)
    assert expiry is not None
    assert expiry.year == 2027
    assert expiry.month == 2
    assert expiry.day == 24


def test_decode_token_expiry_invalid(tmp_path):
    client = _make_client_for_token_tests(tmp_path)
    assert client._decode_token_expiry("not-a-jwt") is None
    assert client._decode_token_expiry("") is None
    assert client._decode_token_expiry("a.b") is None


def test_token_needs_refresh_expired(tmp_path):
    client = _make_client_for_token_tests(tmp_path)
    past = datetime.now(tz=timezone.utc) - timedelta(days=1)
    token = _make_jwt(int(past.timestamp()))
    assert client._token_needs_refresh(token) is True


def test_token_needs_refresh_expiring_soon(tmp_path):
    client = _make_client_for_token_tests(tmp_path)
    soon = datetime.now(tz=timezone.utc) + timedelta(days=3)
    token = _make_jwt(int(soon.timestamp()))
    assert client._token_needs_refresh(token) is True


def test_token_needs_refresh_fresh(tmp_path):
    client = _make_client_for_token_tests(tmp_path)
    far = datetime.now(tz=timezone.utc) + timedelta(days=300)
    token = _make_jwt(int(far.timestamp()))
    assert client._token_needs_refresh(token) is False


def test_load_token_uses_cached_when_fresh(tmp_path):
    client = _make_client_for_token_tests(tmp_path)
    far = datetime.now(tz=timezone.utc) + timedelta(days=300)
    token = _make_jwt(int(far.timestamp()))

    # Write a fresh token to cache
    client._token_path.parent.mkdir(parents=True, exist_ok=True)
    client._token_path.write_text(token)

    config = {"enphase_token": "", "solar_db_path": str(tmp_path / "solar.db")}
    loaded = client._load_token(config)
    assert loaded == token


def test_load_token_explicit_env_wins(tmp_path):
    client = _make_client_for_token_tests(tmp_path)
    far = datetime.now(tz=timezone.utc) + timedelta(days=300)
    explicit_token = _make_jwt(int(far.timestamp()))

    config = {
        "enphase_token": explicit_token,
        "solar_db_path": str(tmp_path / "solar.db"),
    }
    loaded = client._load_token(config)
    assert loaded == explicit_token
