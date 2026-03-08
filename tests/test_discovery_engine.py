"""Tests for discovery engine — mock LLM, JSON parsing, library dedup."""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from discovery.engine import DiscoveryEngine  # noqa: E402
from discovery.storage import DiscoveryStorage  # noqa: E402


def _make_engine(tmp_path, llm_response="[]"):
    storage = DiscoveryStorage(str(tmp_path / "test.db"))
    llm = MagicMock()
    llm.respond.return_value = llm_response
    config = {"discovery_max_recommendations": 10}
    engine = DiscoveryEngine(storage, llm, config)
    return engine, storage, llm


def _seed_library(storage):
    """Seed with some items so taste profile can be built."""
    storage.upsert_library_item({
        "external_id": "1", "title": "Inception", "media_type": "movie",
        "year": 2010, "genres": ["Action", "Sci-Fi"],
        "played": True, "is_favorite": True, "source": "radarr",
    })
    storage.upsert_library_item({
        "external_id": "2", "title": "Breaking Bad", "media_type": "series",
        "year": 2008, "genres": ["Drama", "Crime"],
        "played": True, "is_favorite": True, "source": "sonarr",
    })
    storage.rebuild_taste_profile()


def test_generate_parses_json_response(tmp_path):
    recs_json = json.dumps([
        {
            "title": "Arrival", "media_type": "movie", "year": 2016,
            "reason": "Sci-fi like Inception", "genres": ["Sci-Fi"],
            "confidence": 0.85,
        },
        {
            "title": "Better Call Saul", "media_type": "series", "year": 2015,
            "reason": "Same universe as Breaking Bad", "genres": ["Drama"],
            "confidence": 0.9,
        },
    ])
    engine, storage, llm = _make_engine(tmp_path, recs_json)
    _seed_library(storage)
    result = engine.generate()
    assert len(result) == 2
    assert result[0]["title"] == "Arrival"
    assert result[1]["title"] == "Better Call Saul"
    # Should be saved to storage
    active = storage.get_active_recommendations()
    assert len(active) == 2
    storage.close()


def test_generate_handles_code_fences(tmp_path):
    response = (
        '```json\n[{"title": "Arrival", "media_type": "movie",'
        ' "year": 2016, "reason": "test", "confidence": 0.8}]\n```'
    )
    engine, storage, llm = _make_engine(tmp_path, response)
    _seed_library(storage)
    result = engine.generate()
    assert len(result) == 1
    assert result[0]["title"] == "Arrival"
    storage.close()


def test_generate_filters_existing_library(tmp_path):
    recs_json = json.dumps([
        {"title": "Inception", "media_type": "movie", "year": 2010,
         "reason": "test", "confidence": 0.8},
        {"title": "Arrival", "media_type": "movie", "year": 2016,
         "reason": "test", "confidence": 0.8},
    ])
    engine, storage, llm = _make_engine(tmp_path, recs_json)
    _seed_library(storage)
    result = engine.generate()
    assert len(result) == 1
    assert result[0]["title"] == "Arrival"
    storage.close()


def test_generate_skips_empty_profile(tmp_path):
    engine, storage, llm = _make_engine(tmp_path)
    result = engine.generate()
    assert result == []
    llm.respond.assert_not_called()
    storage.close()


def test_generate_clears_old_active(tmp_path):
    engine, storage, llm = _make_engine(tmp_path)
    _seed_library(storage)
    storage.add_recommendation({"title": "Old Rec", "media_type": "movie"})
    assert len(storage.get_active_recommendations()) == 1

    recs_json = json.dumps([
        {"title": "New Rec", "media_type": "movie", "confidence": 0.8},
    ])
    llm.respond.return_value = recs_json
    engine.generate()

    active = storage.get_active_recommendations()
    assert len(active) == 1
    assert active[0]["title"] == "New Rec"
    storage.close()


def test_parse_handles_invalid_json(tmp_path):
    engine, storage, llm = _make_engine(tmp_path, "not json at all")
    _seed_library(storage)
    result = engine.generate()
    assert result == []
    storage.close()


def test_parse_handles_embedded_json(tmp_path):
    response = 'Here are my recommendations:\n[{"title": "Arrival", "media_type": "movie"}]\nEnjoy!'
    engine, storage, llm = _make_engine(tmp_path, response)
    _seed_library(storage)
    result = engine.generate()
    assert len(result) == 1
    storage.close()


def test_confidence_clamped(tmp_path):
    recs_json = json.dumps([
        {"title": "A", "media_type": "movie", "confidence": 1.5},
        {"title": "B", "media_type": "movie", "confidence": -0.5},
    ])
    engine, storage, llm = _make_engine(tmp_path, recs_json)
    _seed_library(storage)
    result = engine.generate()
    assert result[0]["confidence"] == 1.0
    assert result[1]["confidence"] == 0.0
    storage.close()


def test_format_library_titles_truncation(tmp_path):
    engine, storage, llm = _make_engine(tmp_path)
    for i in range(60):
        storage.upsert_library_item({
            "external_id": str(i), "title": f"Movie {i}",
            "media_type": "movie", "source": "test",
        })
    result = engine._format_library_titles()
    assert "... and" in result
    storage.close()


def test_format_library_titles_empty(tmp_path):
    engine, storage, llm = _make_engine(tmp_path)
    result = engine._format_library_titles()
    assert result == "(empty library)"
    storage.close()
