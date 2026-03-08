"""Tests for discovery storage — upsert, dedup, taste profile, recommendations."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from discovery.storage import DiscoveryStorage  # noqa: E402


def _make_storage(tmp_path) -> DiscoveryStorage:
    return DiscoveryStorage(str(tmp_path / "test_discovery.db"))


def _sample_movie(external_id="tmdb-27205", title="Inception", **overrides):
    base = {
        "external_id": external_id,
        "title": title,
        "media_type": "movie",
        "year": 2010,
        "genres": ["Action", "Sci-Fi"],
        "rating_imdb": 8.4,
        "rating_tmdb": 8.4,
        "rating_rt": 87,
        "studio": "Warner Bros.",
        "runtime": 148,
        "certification": "PG-13",
        "overview": "Dream heist movie.",
        "played": True,
        "play_count": 3,
        "is_favorite": True,
        "source": "radarr",
    }
    base.update(overrides)
    return base


def _sample_series(external_id="tvdb-81189", title="Breaking Bad", **overrides):
    base = {
        "external_id": external_id,
        "title": title,
        "media_type": "series",
        "year": 2008,
        "genres": ["Drama", "Crime"],
        "rating_imdb": 9.5,
        "rating_tmdb": 8.9,
        "studio": "AMC",
        "runtime": 47,
        "certification": "TV-MA",
        "overview": "Chemistry teacher cooks meth.",
        "played": True,
        "play_count": 2,
        "is_favorite": True,
        "source": "sonarr",
    }
    base.update(overrides)
    return base


# -- Upsert & Dedup --


def test_upsert_inserts_new_item(tmp_path):
    storage = _make_storage(tmp_path)
    row_id = storage.upsert_library_item(_sample_movie())
    assert row_id is not None
    assert storage.get_library_count() == 1
    storage.close()


def test_upsert_deduplicates(tmp_path):
    storage = _make_storage(tmp_path)
    storage.upsert_library_item(_sample_movie())
    storage.upsert_library_item(_sample_movie(title="Inception (Updated)"))
    assert storage.get_library_count() == 1
    items = storage.get_library()
    assert items[0]["title"] == "Inception (Updated)"
    storage.close()


def test_upsert_same_title_different_type(tmp_path):
    storage = _make_storage(tmp_path)
    storage.upsert_library_item(_sample_movie(external_id="1"))
    storage.upsert_library_item(
        _sample_movie(external_id="1", media_type="series")
    )
    assert storage.get_library_count() == 2
    storage.close()


def test_library_titles(tmp_path):
    storage = _make_storage(tmp_path)
    storage.upsert_library_item(_sample_movie())
    storage.upsert_library_item(_sample_series())
    titles = storage.get_library_titles()
    assert "Breaking Bad" in titles
    assert "Inception" in titles
    storage.close()


# -- People --


def test_set_people(tmp_path):
    storage = _make_storage(tmp_path)
    storage.upsert_library_item(_sample_movie())
    lib_id = storage.get_library_item_id("tmdb-27205", "movie")
    storage.set_people(lib_id, [
        {"name": "Leonardo DiCaprio", "role": "Cobb", "type": "Actor"},
        {"name": "Christopher Nolan", "role": "", "type": "Director"},
    ])
    # Verify via taste profile rebuild
    storage.rebuild_taste_profile()
    profile = storage.get_taste_profile()
    actor_entries = [p for p in profile if p["dimension"] == "actor"]
    assert any(e["value"] == "Leonardo DiCaprio" for e in actor_entries)
    storage.close()


# -- Taste Profile --


def test_taste_profile_weighting(tmp_path):
    storage = _make_storage(tmp_path)
    # Played + favorite = 3.0
    storage.upsert_library_item(
        _sample_movie(played=True, is_favorite=True)
    )
    # Played only = 2.0
    storage.upsert_library_item(
        _sample_series(played=True, is_favorite=False)
    )
    # Tracked only = 1.0
    storage.upsert_library_item(
        _sample_movie(
            external_id="tmdb-999", title="Unwatched",
            played=False, is_favorite=False, genres=["Horror"],
        )
    )
    storage.rebuild_taste_profile()
    profile = storage.get_taste_profile()

    # Action genre from Inception (played+fav) should score 3.0
    action = next(
        (p for p in profile if p["dimension"] == "genre" and p["value"] == "Action"),
        None,
    )
    assert action is not None
    assert action["score"] == 3.0

    # Horror genre from Unwatched (tracked only) should score 1.0
    horror = next(
        (p for p in profile if p["dimension"] == "genre" and p["value"] == "Horror"),
        None,
    )
    assert horror is not None
    assert horror["score"] == 1.0
    storage.close()


def test_taste_summary(tmp_path):
    storage = _make_storage(tmp_path)
    storage.upsert_library_item(_sample_movie())
    storage.upsert_library_item(_sample_series())
    storage.rebuild_taste_profile()
    summary = storage.get_taste_summary()
    assert "genre:" in summary
    assert len(summary) > 10
    storage.close()


def test_taste_summary_empty(tmp_path):
    storage = _make_storage(tmp_path)
    summary = storage.get_taste_summary()
    assert "No taste profile" in summary
    storage.close()


def test_decade_profile(tmp_path):
    storage = _make_storage(tmp_path)
    storage.upsert_library_item(_sample_movie(year=2010))
    storage.rebuild_taste_profile()
    profile = storage.get_taste_profile()
    decades = [p for p in profile if p["dimension"] == "decade"]
    assert any(d["value"] == "2010s" for d in decades)
    storage.close()


# -- Recommendations --


def test_add_and_get_recommendations(tmp_path):
    storage = _make_storage(tmp_path)
    rec_id = storage.add_recommendation({
        "title": "Arrival",
        "media_type": "movie",
        "year": 2016,
        "reason": "Similar sci-fi themes",
        "genres": ["Sci-Fi", "Drama"],
        "confidence": 0.85,
    })
    assert rec_id is not None
    recs = storage.get_active_recommendations()
    assert len(recs) == 1
    assert recs[0]["title"] == "Arrival"
    assert recs[0]["status"] == "active"
    storage.close()


def test_dismiss_recommendation(tmp_path):
    storage = _make_storage(tmp_path)
    rec_id = storage.add_recommendation({
        "title": "Arrival",
        "media_type": "movie",
    })
    storage.dismiss_recommendation(rec_id)
    assert len(storage.get_active_recommendations()) == 0
    storage.close()


def test_track_recommendation(tmp_path):
    storage = _make_storage(tmp_path)
    rec_id = storage.add_recommendation({
        "title": "Arrival",
        "media_type": "movie",
    })
    storage.track_recommendation(rec_id)
    assert len(storage.get_active_recommendations()) == 0
    storage.close()


def test_clear_active_recommendations(tmp_path):
    storage = _make_storage(tmp_path)
    storage.add_recommendation({"title": "A", "media_type": "movie"})
    storage.add_recommendation({"title": "B", "media_type": "series"})
    storage.clear_active_recommendations()
    assert len(storage.get_active_recommendations()) == 0
    storage.close()


# -- Sync Meta --


def test_sync_meta(tmp_path):
    storage = _make_storage(tmp_path)
    assert storage.get_sync_time("radarr") is None
    storage.set_sync_time("radarr")
    assert storage.get_sync_time("radarr") is not None
    storage.close()
