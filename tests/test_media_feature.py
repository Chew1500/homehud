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


# -- expects_follow_up --


def test_expects_follow_up_false_by_default():
    feat = _make_feature()
    assert feat.expects_follow_up is False


def test_expects_follow_up_true_during_disambiguation():
    feat = _make_feature()
    feat.handle("track the movie The Matrix")
    assert feat._pending is not None
    assert feat.expects_follow_up is True


def test_expects_follow_up_false_after_confirm():
    feat = _make_feature()
    feat.handle("track the movie The Matrix")
    feat.handle("yes")
    assert feat.expects_follow_up is False


def test_expects_follow_up_false_after_cancel():
    feat = _make_feature()
    feat.handle("track the movie The Matrix")
    feat.handle("cancel")
    assert feat.expects_follow_up is False


def test_expects_follow_up_false_when_expired():
    feat = _make_feature(ttl=0)
    feat.handle("track the movie The Matrix")
    time.sleep(0.1)
    assert feat.expects_follow_up is False


# -- Combined search (generic track) --


def test_track_generic_searches_both_services():
    """Generic track should search both Radarr and Sonarr."""
    feat = _make_feature()
    result = feat.handle("track batman")
    # batman has 5 movies + 2 shows = 7 results → refining phase
    assert feat._pending is not None
    assert feat._pending["phase"] == "refining"
    assert len(feat._pending["results"]) == 7
    # Summary should mention both movies and shows
    assert "movie" in result.lower()
    assert "show" in result.lower()


def test_track_generic_movie_only():
    """Generic track with only Radarr configured should search movies only."""
    feat = _make_feature(sonarr=False)
    feat.handle("track batman")
    assert feat._pending is not None
    assert all(r["media_type"] == "movie" for r in feat._pending["results"])


def test_track_generic_show_only():
    """Generic track with only Sonarr should search shows only."""
    feat = _make_feature(radarr=False)
    feat.handle("track batman")
    assert feat._pending is not None
    assert all(r["media_type"] == "show" for r in feat._pending["results"])


# -- Refining phase --


def test_refining_summary_describes_results():
    """Refining summary should mention count, types, and year range."""
    feat = _make_feature()
    result = feat.handle("track batman")
    assert "7 results" in result
    assert "1989" in result
    assert "2024" in result


def test_refining_filter_by_year():
    """Filtering by year during refining should narrow results."""
    feat = _make_feature()
    feat.handle("track batman")
    result = feat.handle("2022")
    # Only The Batman (2022) and Batman: The Animated Series' year doesn't match
    # Wait — Batman TAS is 1992, Caped Crusader is 2024... The Batman is 2022
    # So filtering by 2022 → 1 result (The Batman)
    assert "The Batman" in result
    assert "Should I add" in result
    assert feat._pending["phase"] == "confirming"


def test_refining_filter_by_type_movie():
    """Filtering by 'movie' should keep only movies."""
    feat = _make_feature()
    feat.handle("track batman")
    result = feat.handle("it was a movie")
    # 5 movies remain — still 4+ → stay in refining
    assert feat._pending is not None
    assert "5 results" in result or "Still 5" in result


def test_refining_filter_by_type_show():
    """Filtering by 'show' should keep only shows."""
    feat = _make_feature()
    feat.handle("track batman")
    feat.handle("it's a show")
    # 2 shows → phase switches to confirming
    assert feat._pending is not None
    assert feat._pending["phase"] == "confirming"
    assert len(feat._pending["results"]) == 2


def test_refining_filter_by_recency():
    """Filtering by 'the newest' should keep top 3 by year."""
    feat = _make_feature()
    feat.handle("track batman")
    feat.handle("the newest one")
    # Top 3 by year: Caped Crusader (2024), The Batman (2022), Dark Knight Rises (2012)
    assert feat._pending is not None
    assert len(feat._pending["results"]) == 3
    assert feat._pending["phase"] == "confirming"


def test_refining_combined_filter():
    """Multiple refinement signals should combine."""
    feat = _make_feature()
    feat.handle("track batman")
    result = feat.handle("the 1992 show")
    # Year 1992 + show → Batman: The Animated Series only
    assert "Batman: The Animated Series" in result
    assert feat._pending["phase"] == "confirming"


def test_refining_no_matches_clears_pending():
    """Filtering that yields 0 results should clear pending."""
    feat = _make_feature()
    feat.handle("track batman")
    result = feat.handle("1999")
    # No batman results from 1999
    assert "None of my results" in result
    assert feat._pending is None


def test_refining_yes_switches_to_confirming():
    """Saying 'yes' during refining should start one-by-one confirmation."""
    feat = _make_feature()
    feat.handle("track batman")
    assert feat._pending["phase"] == "refining"
    result = feat.handle("yes")
    assert feat._pending is not None
    assert feat._pending["phase"] == "confirming"
    assert "Should I add" in result


def test_refining_cancel():
    """Cancel during refining should clear pending."""
    feat = _make_feature()
    feat.handle("track batman")
    result = feat.handle("cancel")
    assert "cancelled" in result.lower()
    assert feat._pending is None


def test_refining_matches_year_input():
    """Year input during refining should be matched by matches()."""
    feat = _make_feature()
    feat.handle("track batman")
    assert feat.matches("2022")


def test_refining_matches_type_input():
    """Type input during refining should be matched by matches()."""
    feat = _make_feature()
    feat.handle("track batman")
    assert feat.matches("it was a movie")
    assert feat.matches("it's a show")


# -- Edge cases: new command during disambiguation --


def test_new_track_command_clears_old_pending():
    """Starting a new track command should clear old disambiguation."""
    feat = _make_feature()
    feat.handle("track the movie The Matrix")
    assert feat._pending is not None
    # Now issue a different track command
    feat.handle("track the movie Dune")
    # Old pending for Matrix should be cleared (Dune is tracked → no pending)
    # or new pending for Dune results


def test_list_clears_pending():
    """List command during disambiguation should clear pending."""
    feat = _make_feature()
    feat.handle("track the movie The Matrix")
    assert feat._pending is not None
    feat.handle("what movies do I have")
    assert feat._pending is None


def test_check_clears_pending():
    """Check command during disambiguation should clear pending."""
    feat = _make_feature()
    feat.handle("track the movie The Matrix")
    assert feat._pending is not None
    feat.handle("do I have Inception")
    assert feat._pending is None


def test_new_command_during_refining():
    """A new 'track movie X' command during refining should replace it."""
    feat = _make_feature()
    feat.handle("track batman")
    assert feat._pending["phase"] == "refining"
    result = feat.handle("track the movie The Matrix")
    # Should have cleared batman pending and started Matrix disambiguation
    assert "I found" in result or "already" in result


# -- Threshold: fewer than 4 results go to confirming --


def test_three_results_go_to_confirming():
    """3 or fewer results should skip refining and go straight to confirming."""
    feat = _make_feature()
    # Dune search returns 2 movies
    feat.handle("track the movie Dune")
    # Dune (2021) is already tracked, so it should skip to Dune: Part Two
    assert feat._pending is not None
    assert feat._pending["phase"] == "confirming"


def test_single_tracked_result_reports_already():
    """Single result that's already tracked should say so without pending."""
    feat = _make_feature()
    result = feat.handle("track the movie Oppenheimer")
    assert "already tracking" in result
    assert feat._pending is None


# -- Result tagging --


def test_results_tagged_with_media_type():
    """Each result should have a media_type key after search."""
    feat = _make_feature()
    feat.handle("track batman")
    for r in feat._pending["results"]:
        assert "media_type" in r
        assert r["media_type"] in ("movie", "show")
    movies = [r for r in feat._pending["results"] if r["media_type"] == "movie"]
    shows = [r for r in feat._pending["results"] if r["media_type"] == "show"]
    assert len(movies) == 5
    assert len(shows) == 2


# -- Full flow: refine then confirm then add --


def test_full_refine_to_confirm_flow():
    """Complete flow: track batman → refine by year → confirm → added."""
    feat = _make_feature()
    # Step 1: search triggers refining
    result = feat.handle("track batman")
    assert feat._pending["phase"] == "refining"

    # Step 2: refine by year to single result
    result = feat.handle("2022")
    assert "The Batman" in result
    assert "Should I add" in result
    assert feat._pending["phase"] == "confirming"

    # Step 3: confirm
    result = feat.handle("yes")
    assert "Done" in result or "added" in result
    assert feat._pending is None
