"""Tests for discovery feature — matching, recommend flow, add/dismiss, taste profile."""

import sys
import time
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from discovery.storage import DiscoveryStorage  # noqa: E402
from features.discovery import DiscoveryFeature  # noqa: E402


def _make_storage(tmp_path):
    return DiscoveryStorage(str(tmp_path / "test.db"))


def _make_feature(tmp_path, sonarr=True, radarr=True, seed_recs=True):
    storage = _make_storage(tmp_path)
    mock_sonarr = MagicMock() if sonarr else None
    mock_radarr = MagicMock() if radarr else None

    if mock_sonarr:
        mock_sonarr.search_series.return_value = [
            {"tvdbId": 123, "title": "Test Series", "year": 2023, "overview": ""},
        ]
        mock_sonarr.is_series_tracked.return_value = False
        mock_sonarr.add_series.return_value = {"tvdbId": 123, "title": "Test Series"}

    if mock_radarr:
        mock_radarr.search_movie.return_value = [
            {"tmdbId": 456, "title": "Test Movie", "year": 2023, "overview": ""},
        ]
        mock_radarr.is_movie_tracked.return_value = False
        mock_radarr.add_movie.return_value = {"tmdbId": 456, "title": "Test Movie"}

    if seed_recs:
        storage.add_recommendation({
            "title": "Arrival", "media_type": "movie", "year": 2016,
            "reason": "Similar sci-fi themes", "genres": ["Sci-Fi"],
            "confidence": 0.9,
        })
        storage.add_recommendation({
            "title": "Better Call Saul", "media_type": "series", "year": 2015,
            "reason": "Great drama", "genres": ["Drama"],
            "confidence": 0.85,
        })

    feat = DiscoveryFeature(
        {}, discovery_storage=storage, sonarr=mock_sonarr, radarr=mock_radarr,
    )
    return feat, storage


# -- Matching --


def test_matches_recommend(tmp_path):
    feat, storage = _make_feature(tmp_path)
    assert feat.matches("recommend a movie")
    assert feat.matches("what should I watch")
    assert feat.matches("anything good to watch")
    assert feat.matches("suggest a show")
    storage.close()


def test_matches_taste_profile(tmp_path):
    feat, storage = _make_feature(tmp_path)
    assert feat.matches("what's my taste profile")
    assert feat.matches("what do I like")
    storage.close()


def test_no_match_without_storage(tmp_path):
    feat = DiscoveryFeature({})
    assert not feat.matches("recommend a movie")


def test_no_match_unrelated(tmp_path):
    feat, storage = _make_feature(tmp_path)
    assert not feat.matches("what is the weather")
    storage.close()


# -- Recommend flow --


def test_present_recommendation(tmp_path):
    feat, storage = _make_feature(tmp_path)
    response = feat.handle("recommend a movie")
    assert "Arrival" in response
    assert "2016" in response
    assert feat.expects_follow_up
    storage.close()


def test_present_series_recommendation(tmp_path):
    feat, storage = _make_feature(tmp_path)
    response = feat.handle("recommend a show")
    assert "Better Call Saul" in response
    storage.close()


def test_no_recommendations(tmp_path):
    feat, storage = _make_feature(tmp_path, seed_recs=False)
    response = feat.handle("what should I watch")
    assert "don't have any" in response
    assert not feat.expects_follow_up
    storage.close()


def test_next_recommendation(tmp_path):
    feat, storage = _make_feature(tmp_path)
    feat.handle("what should I watch")
    response = feat.handle("next")
    assert "Better Call Saul" in response or "That's all" in response
    storage.close()


def test_next_past_end(tmp_path):
    feat, storage = _make_feature(tmp_path)
    feat.handle("what should I watch")
    feat.handle("next")
    response = feat.handle("next")
    assert "all" in response.lower() or "no more" in response.lower()
    assert not feat.expects_follow_up
    storage.close()


# -- Add recommendation --


def test_add_movie_recommendation(tmp_path):
    feat, storage = _make_feature(tmp_path)
    feat.handle("recommend a movie")
    response = feat.handle("add that")
    assert "Added" in response or "already" in response.lower()
    storage.close()


def test_add_series_recommendation(tmp_path):
    feat, storage = _make_feature(tmp_path)
    feat.handle("recommend a show")
    response = feat.handle("add it")
    assert "Added" in response or "already" in response.lower()
    storage.close()


def test_add_already_tracked(tmp_path):
    feat, storage = _make_feature(tmp_path)
    feat._radarr.is_movie_tracked.return_value = True
    feat.handle("recommend a movie")
    response = feat.handle("add it")
    assert "already" in response.lower()
    storage.close()


# -- Dismiss --


def test_dismiss_recommendation(tmp_path):
    feat, storage = _make_feature(tmp_path)
    feat.handle("what should I watch")
    response = feat.handle("not interested")
    # Should show the next one or say no more
    assert (
        "Better Call Saul" in response
        or "all" in response.lower()
        or "no more" in response.lower()
    )
    storage.close()


# -- Cancel --


def test_cancel_recommendation(tmp_path):
    feat, storage = _make_feature(tmp_path)
    feat.handle("what should I watch")
    response = feat.handle("cancel")
    assert "no more" in response.lower() or "okay" in response.lower()
    assert not feat.expects_follow_up
    storage.close()


# -- Taste profile --


def test_taste_profile_empty(tmp_path):
    feat, storage = _make_feature(tmp_path)
    response = feat.handle("what's my taste profile")
    assert "haven't built" in response or "taste profile" in response.lower()
    storage.close()


def test_taste_profile_with_data(tmp_path):
    feat, storage = _make_feature(tmp_path)
    storage.upsert_library_item({
        "external_id": "1", "title": "Inception", "media_type": "movie",
        "year": 2010, "genres": ["Action", "Sci-Fi"],
        "played": True, "is_favorite": True, "source": "test",
    })
    storage.rebuild_taste_profile()
    response = feat.handle("what's my taste profile")
    assert "taste profile" in response.lower()
    storage.close()


# -- Follow-up state --


def test_expects_follow_up_while_presenting(tmp_path):
    feat, storage = _make_feature(tmp_path)
    assert not feat.expects_follow_up
    feat.handle("what should I watch")
    assert feat.expects_follow_up
    storage.close()


def test_follow_up_expires(tmp_path):
    feat, storage = _make_feature(tmp_path)
    feat.handle("what should I watch")
    feat._last_interaction = time.time() - 120  # Expired
    assert not feat.expects_follow_up
    storage.close()


def test_follow_up_matches_add(tmp_path):
    feat, storage = _make_feature(tmp_path)
    feat.handle("what should I watch")
    assert feat.matches("add that")
    assert feat.matches("yes")
    storage.close()


def test_follow_up_matches_next(tmp_path):
    feat, storage = _make_feature(tmp_path)
    feat.handle("what should I watch")
    assert feat.matches("next")
    assert feat.matches("another one")
    storage.close()


# -- Execute (structured action) --


def test_execute_recommend(tmp_path):
    feat, storage = _make_feature(tmp_path)
    response = feat.execute("recommend", {"media_type": "movie"})
    assert "Arrival" in response
    storage.close()


def test_execute_add(tmp_path):
    feat, storage = _make_feature(tmp_path)
    feat.execute("recommend", {})
    response = feat.execute("add_recommendation", {})
    assert "Added" in response or "already" in response.lower() or "Couldn't" in response
    storage.close()


def test_execute_dismiss(tmp_path):
    feat, storage = _make_feature(tmp_path)
    feat.execute("recommend", {})
    response = feat.execute("dismiss_recommendation", {})
    assert response  # Should return something
    storage.close()


def test_execute_taste_profile(tmp_path):
    feat, storage = _make_feature(tmp_path)
    response = feat.execute("taste_profile", {})
    assert "taste" in response.lower() or "haven't" in response.lower()
    storage.close()


# -- LLM context --


def test_llm_context_while_active(tmp_path):
    feat, storage = _make_feature(tmp_path)
    feat.handle("what should I watch")
    ctx = feat.get_llm_context()
    assert ctx is not None
    assert "Discovery active" in ctx
    storage.close()


def test_llm_context_when_inactive(tmp_path):
    feat, storage = _make_feature(tmp_path)
    assert feat.get_llm_context() is None
    storage.close()


# -- Not configured --


def test_handle_not_configured(tmp_path):
    feat = DiscoveryFeature({})
    response = feat.handle("recommend a movie")
    assert "configured" in response.lower()
