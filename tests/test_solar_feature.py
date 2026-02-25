"""Tests for the solar monitoring voice feature."""

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from enphase.storage import SolarStorage
from features.solar import SolarFeature


class FakeLLM:
    """Minimal LLM stub for testing complex query delegation."""

    def __init__(self):
        self.last_prompt = None

    def respond(self, text: str) -> str:
        self.last_prompt = text
        return "LLM analysis response"


def _make_feature(tmp_path):
    """Create a SolarFeature with in-memory storage and fake LLM."""
    db_path = str(tmp_path / "solar.db")
    storage = SolarStorage(db_path)
    llm = FakeLLM()
    config = {"solar_db_path": db_path}
    feature = SolarFeature(config, storage, llm)
    return feature, storage, llm


def _seed_reading(storage, production_w=4200, consumption_w=1800):
    """Add a production reading to storage."""
    storage.store_reading(
        production_w=production_w,
        consumption_w=consumption_w,
        net_w=production_w - consumption_w,
        production_wh=18500,
        consumption_wh=12300,
    )


def _seed_summary(storage):
    """Add a daily summary for today."""
    today = datetime.now().strftime("%Y-%m-%d")
    storage._conn.execute(
        "INSERT OR REPLACE INTO daily_summary VALUES (?, ?, ?, ?, ?, ?, ?)",
        (today, 18500, 12300, 5200, 22.0, 15.0, 50),
    )
    storage._conn.commit()


# -- matches() --


def test_matches_solar(tmp_path):
    feat, storage, _ = _make_feature(tmp_path)
    assert feat.matches("how much solar am I producing")
    storage.close()


def test_matches_power(tmp_path):
    feat, storage, _ = _make_feature(tmp_path)
    assert feat.matches("how much power am I generating")
    storage.close()


def test_matches_inverter(tmp_path):
    feat, storage, _ = _make_feature(tmp_path)
    assert feat.matches("how are my inverters")
    storage.close()


def test_matches_energy(tmp_path):
    feat, storage, _ = _make_feature(tmp_path)
    assert feat.matches("how much energy have I used today")
    storage.close()


def test_matches_grid(tmp_path):
    feat, storage, _ = _make_feature(tmp_path)
    assert feat.matches("am I exporting to the grid")
    storage.close()


def test_matches_enphase(tmp_path):
    feat, storage, _ = _make_feature(tmp_path)
    assert feat.matches("is the enphase system working")
    storage.close()


def test_no_match_unrelated(tmp_path):
    feat, storage, _ = _make_feature(tmp_path)
    assert not feat.matches("what time is it")
    storage.close()


def test_no_match_grocery(tmp_path):
    feat, storage, _ = _make_feature(tmp_path)
    assert not feat.matches("add milk to the grocery list")
    storage.close()


# -- Simple queries --


def test_current_production(tmp_path):
    feat, storage, _ = _make_feature(tmp_path)
    _seed_reading(storage)
    result = feat.handle("how much solar am I producing")
    assert "4.2" in result
    assert "kilowatt" in result
    storage.close()


def test_current_production_alt(tmp_path):
    feat, storage, _ = _make_feature(tmp_path)
    _seed_reading(storage)
    result = feat.handle("what's my solar production")
    assert "4.2" in result
    storage.close()


def test_current_production_exporting(tmp_path):
    feat, storage, _ = _make_feature(tmp_path)
    _seed_reading(storage, production_w=5000, consumption_w=2000)
    result = feat.handle("how much solar am I producing")
    assert "exporting" in result
    storage.close()


def test_current_production_importing(tmp_path):
    feat, storage, _ = _make_feature(tmp_path)
    _seed_reading(storage, production_w=1000, consumption_w=3000)
    result = feat.handle("how much solar am I producing")
    assert "importing" in result
    storage.close()


def test_today_consumption(tmp_path):
    feat, storage, _ = _make_feature(tmp_path)
    _seed_summary(storage)
    result = feat.handle("how much energy have I used today")
    assert "12.3" in result
    assert "kilowatt hour" in result
    storage.close()


def test_today_production(tmp_path):
    feat, storage, _ = _make_feature(tmp_path)
    _seed_summary(storage)
    result = feat.handle("how much solar have I generated today")
    assert "18.5" in result
    assert "kilowatt hour" in result
    storage.close()


def test_grid_status_exporting(tmp_path):
    feat, storage, _ = _make_feature(tmp_path)
    _seed_reading(storage, production_w=5000, consumption_w=2000)
    result = feat.handle("am I exporting to the grid")
    assert "exporting" in result
    storage.close()


def test_grid_status_importing(tmp_path):
    feat, storage, _ = _make_feature(tmp_path)
    _seed_reading(storage, production_w=1000, consumption_w=3000)
    result = feat.handle("am I exporting to the grid")
    assert "importing" in result
    storage.close()


def test_system_status_online(tmp_path):
    feat, storage, _ = _make_feature(tmp_path)
    _seed_reading(storage, production_w=4000, consumption_w=2000)
    result = feat.handle("is the solar system online")
    assert "online" in result
    assert "producing" in result
    storage.close()


def test_system_status_no_production(tmp_path):
    feat, storage, _ = _make_feature(tmp_path)
    _seed_reading(storage, production_w=0, consumption_w=2000)
    result = feat.handle("is the solar system online")
    assert "not currently producing" in result
    storage.close()


def test_panel_health_no_data(tmp_path):
    feat, storage, _ = _make_feature(tmp_path)
    _seed_reading(storage)
    result = feat.handle("how are my panels")
    assert "don't have individual inverter data" in result
    storage.close()


def test_panel_health_with_inverters(tmp_path):
    feat, storage, _ = _make_feature(tmp_path)
    _seed_reading(storage)
    inverters = [
        {"serial": "ABC001", "watts": 175, "max_watts": 295},
        {"serial": "ABC002", "watts": 180, "max_watts": 295},
    ]
    storage.store_inverter_readings(inverters)
    result = feat.handle("how are my panels")
    assert "2 inverters" in result
    assert "normally" in result
    storage.close()


def test_panel_health_underperformer(tmp_path):
    feat, storage, _ = _make_feature(tmp_path)
    _seed_reading(storage)
    inverters = [
        {"serial": "ABC001", "watts": 175, "max_watts": 295},
        {"serial": "ABC002", "watts": 10, "max_watts": 295},  # underperforming
    ]
    storage.store_inverter_readings(inverters)
    result = feat.handle("how are my panels")
    assert "underperforming" in result
    storage.close()


# -- Complex queries (LLM delegation) --


def test_complex_query_compare(tmp_path):
    feat, storage, llm = _make_feature(tmp_path)
    _seed_reading(storage)
    _seed_summary(storage)
    result = feat.handle("compare today's solar production to yesterday")
    assert result == "LLM analysis response"
    assert llm.last_prompt is not None
    assert "Solar data" in llm.last_prompt
    storage.close()


def test_complex_query_trend(tmp_path):
    feat, storage, llm = _make_feature(tmp_path)
    _seed_reading(storage)
    result = feat.handle("what's the trend in my solar production")
    assert result == "LLM analysis response"
    storage.close()


def test_complex_query_why(tmp_path):
    feat, storage, llm = _make_feature(tmp_path)
    _seed_reading(storage)
    result = feat.handle("why is my solar production low today")
    assert result == "LLM analysis response"
    storage.close()


# -- Edge cases --


def test_no_data_yet(tmp_path):
    feat, storage, _ = _make_feature(tmp_path)
    result = feat.handle("how much solar am I producing")
    assert "don't have any solar data" in result
    storage.close()


def test_no_summary_yet(tmp_path):
    feat, storage, _ = _make_feature(tmp_path)
    result = feat.handle("how much energy have I used today")
    assert "don't have enough data" in result
    storage.close()


def test_complex_no_data(tmp_path):
    feat, storage, llm = _make_feature(tmp_path)
    result = feat.handle("compare today to yesterday")
    assert "don't have enough solar data" in result
    assert llm.last_prompt is None  # LLM not called
    storage.close()


def test_fallback_to_current(tmp_path):
    """Generic solar mention without specific pattern falls back to current."""
    feat, storage, _ = _make_feature(tmp_path)
    _seed_reading(storage)
    result = feat.handle("tell me about my solar")
    assert "kilowatt" in result
    storage.close()
