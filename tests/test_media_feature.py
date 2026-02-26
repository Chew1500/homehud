"""Tests for the media library voice feature."""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from features.media import MediaFeature
from media.mock_radarr import MockRadarrClient
from media.mock_sonarr import MockSonarrClient


def _make_feature(sonarr=True, radarr=True, ttl=60):
    """Create a MediaFeature with mock clients."""
    config = {"media_disambiguation_ttl": ttl}
    s = MockSonarrClient(config) if sonarr else None
    r = MockRadarrClient(config) if radarr else None
    return MediaFeature(config, sonarr=s, radarr=r)


# -- matches() --


def test_matches_movie():
    feat = _make_feature()
    assert feat.matches("what movies do I have")


def test_matches_show():
    feat = _make_feature()
    assert feat.matches("what shows am I tracking")


def test_matches_track():
    feat = _make_feature()
    assert feat.matches("track the movie Inception")


def test_matches_download():
    feat = _make_feature()
    assert feat.matches("download Dune")


def test_matches_library():
    feat = _make_feature()
    assert feat.matches("is Breaking Bad in my library")


def test_no_match_unrelated():
    feat = _make_feature()
    assert not feat.matches("what time is it")


def test_no_match_grocery():
    feat = _make_feature()
    assert not feat.matches("add milk to the grocery list")


# -- List commands --


def test_list_movies():
    feat = _make_feature()
    result = feat.handle("what movies do I have")
    assert "Inception" in result
    assert "Dune" in result
    assert "Oppenheimer" in result


def test_list_shows():
    feat = _make_feature()
    result = feat.handle("what shows am I tracking")
    assert "Breaking Bad" in result
    assert "Severance" in result


def test_list_movies_no_radarr():
    feat = _make_feature(radarr=False)
    result = feat.handle("what movies do I have")
    assert "isn't configured" in result


def test_list_shows_no_sonarr():
    feat = _make_feature(sonarr=False)
    result = feat.handle("what shows am I tracking")
    assert "isn't configured" in result


def test_list_my_movies():
    feat = _make_feature()
    result = feat.handle("list my movies")
    assert "Inception" in result


def test_show_me_my_shows():
    feat = _make_feature()
    result = feat.handle("show me my shows")
    assert "Breaking Bad" in result


# -- Check commands --


def test_check_tracked_movie():
    feat = _make_feature()
    result = feat.handle("do I have Inception")
    assert "Yes" in result
    assert "Inception" in result


def test_check_tracked_show():
    feat = _make_feature()
    result = feat.handle("is Breaking Bad in my library")
    assert "Yes" in result
    assert "Breaking Bad" in result


def test_check_not_tracked():
    feat = _make_feature()
    result = feat.handle("do I have The Matrix")
    assert "don't see" in result


# -- Track movie --


def test_track_movie_disambiguation():
    feat = _make_feature()
    result = feat.handle("track the movie Inception")
    # Inception is already tracked
    assert "already tracking" in result


def test_track_movie_new():
    """Track a movie not in the library — triggers disambiguation."""
    feat = _make_feature()
    # "The Bear" won't match Radarr's canned search, returns generic result
    result = feat.handle("track the movie The Matrix")
    assert "I found" in result
    assert "Should I add" in result


def test_track_show_new():
    feat = _make_feature()
    result = feat.handle("track the show The Bear")
    assert "I found" in result
    assert "Should I add" in result


def test_track_show_already_tracked():
    feat = _make_feature()
    result = feat.handle("add Severance to my shows")
    assert "already tracking" in result


# -- Track generic (no movie/show specified) --


def test_track_generic():
    feat = _make_feature()
    # "grab" with a title not in library — searches movies first
    result = feat.handle("grab The Matrix")
    assert "I found" in result or "already" in result


# -- Disambiguation flow --


def test_disambiguation_yes():
    feat = _make_feature()
    # Start disambiguation with a new movie
    feat.handle("track the movie The Matrix")
    assert feat._pending is not None

    # Confirm
    result = feat.handle("yes")
    assert "Done" in result or "added" in result
    assert feat._pending is None


def test_disambiguation_no_next():
    feat = _make_feature()
    feat.handle("track the movie Dune")
    # Dune is already tracked, so this returns "already tracking"
    # Try with something not tracked
    feat.handle("track the movie The Matrix")

    # Say no/next
    result = feat.handle("no")
    # Either shows next result or says that's all
    assert "I found" in result or "all the results" in result


def test_disambiguation_cancel():
    feat = _make_feature()
    feat.handle("track the movie The Matrix")
    assert feat._pending is not None

    result = feat.handle("cancel")
    assert "cancelled" in result.lower()
    assert feat._pending is None


def test_disambiguation_never_mind():
    feat = _make_feature()
    feat.handle("track the movie The Matrix")
    result = feat.handle("never mind")
    assert "cancelled" in result.lower()


def test_disambiguation_expires():
    feat = _make_feature(ttl=0)  # Immediate expiry
    feat.handle("track the movie The Matrix")
    time.sleep(0.1)
    # Pending should be expired now
    assert not feat.matches("yes")  # "yes" alone shouldn't match without pending


def test_disambiguation_matches_yes_no():
    """Disambiguation responses should match when pending is active."""
    feat = _make_feature()
    feat.handle("track the movie The Matrix")
    assert feat.matches("yes")
    assert feat.matches("no")
    assert feat.matches("cancel")


# -- Edge cases --


def test_no_clients():
    feat = _make_feature(sonarr=False, radarr=False)
    result = feat.handle("track Inception")
    assert "isn't configured" in result


def test_status_fallback():
    feat = _make_feature()
    result = feat.handle("tell me about my media library")
    assert "tracking" in result


def test_properties():
    feat = _make_feature()
    assert feat.name == "Media Library"
    assert "movies" in feat.short_description
    assert "TV shows" in feat.short_description
    assert feat.description != ""


def test_close():
    feat = _make_feature()
    feat.close()  # Should not raise


def test_feature_description_radarr_only():
    feat = _make_feature(sonarr=False)
    assert "movies" in feat.short_description
    assert "TV shows" not in feat.short_description


def test_feature_description_sonarr_only():
    feat = _make_feature(radarr=False)
    assert "TV shows" in feat.short_description
    assert "movies" not in feat.short_description


# -- Truncation for large libraries --


def test_list_movies_truncated():
    """Large movie library should show count and only recent titles."""
    feat = _make_feature()
    # Inject a large library into the mock radarr client
    feat._radarr._library = [
        {"tmdbId": i, "title": f"Movie {i}", "year": 2020 + (i % 5)}
        for i in range(1, 9)
    ]
    result = feat.handle("what movies do I have")
    assert "8 movies" in result
    assert "Some recent ones are" in result
    # Last 5 should be listed (Movie 4 through Movie 8)
    for i in range(4, 9):
        assert f"Movie {i}" in result
    # Earlier ones should NOT be listed
    for i in range(1, 4):
        assert f"Movie {i}" not in result


def test_list_shows_truncated():
    """Large show library should show count and only recent titles."""
    feat = _make_feature()
    # Use letter suffixes to avoid substring collisions (e.g. "Show A" in "Show AB")
    names = ["Alpha", "Bravo", "Charlie", "Delta", "Echo",
             "Foxtrot", "Golf", "Hotel", "India", "Juliet"]
    feat._sonarr._library = [
        {"tvdbId": i, "title": f"Show {names[i]}", "year": 2020}
        for i in range(10)
    ]
    result = feat.handle("what shows am I tracking")
    assert "10 shows" in result
    assert "Some recent ones are" in result
    # Last 5 should be listed
    for name in names[5:]:
        assert f"Show {name}" in result
    # Earlier ones should NOT be listed
    for name in names[:5]:
        assert f"Show {name}" not in result
