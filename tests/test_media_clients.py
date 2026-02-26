"""Tests for media clients — mock shape validation and factory functions."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from media import get_radarr_client, get_sonarr_client  # noqa: E402
from media.mock_radarr import MockRadarrClient  # noqa: E402
from media.mock_sonarr import MockSonarrClient  # noqa: E402

# -- MockSonarrClient --


def test_mock_sonarr_get_series():
    client = MockSonarrClient({})
    series = client.get_series()
    assert len(series) >= 1
    assert "tvdbId" in series[0]
    assert "title" in series[0]
    assert "year" in series[0]


def test_mock_sonarr_search():
    client = MockSonarrClient({})
    results = client.search_series("breaking bad")
    assert len(results) >= 1
    assert results[0]["title"] == "Breaking Bad"
    assert "overview" in results[0]


def test_mock_sonarr_search_unknown():
    client = MockSonarrClient({})
    results = client.search_series("xyznonexistent")
    assert len(results) >= 1  # Returns generic result


def test_mock_sonarr_add_series():
    client = MockSonarrClient({})
    initial_count = len(client.get_series())
    result = client.add_series(396238, "The Bear")
    assert result["title"] == "The Bear"
    assert len(client.get_series()) == initial_count + 1


def test_mock_sonarr_is_tracked():
    client = MockSonarrClient({})
    assert client.is_series_tracked(81189)  # Breaking Bad
    assert not client.is_series_tracked(999)


def test_mock_sonarr_close():
    client = MockSonarrClient({})
    client.close()  # Should not raise


# -- MockRadarrClient --


def test_mock_radarr_get_movies():
    client = MockRadarrClient({})
    movies = client.get_movies()
    assert len(movies) >= 1
    assert "tmdbId" in movies[0]
    assert "title" in movies[0]
    assert "year" in movies[0]


def test_mock_radarr_search():
    client = MockRadarrClient({})
    results = client.search_movie("inception")
    assert len(results) >= 1
    assert results[0]["title"] == "Inception"
    assert "overview" in results[0]


def test_mock_radarr_search_unknown():
    client = MockRadarrClient({})
    results = client.search_movie("xyznonexistent")
    assert len(results) >= 1  # Returns generic result


def test_mock_radarr_add_movie():
    client = MockRadarrClient({})
    initial_count = len(client.get_movies())
    result = client.add_movie(693134, "Dune: Part Two")
    assert result["title"] == "Dune: Part Two"
    assert len(client.get_movies()) == initial_count + 1


def test_mock_radarr_is_tracked():
    client = MockRadarrClient({})
    assert client.is_movie_tracked(27205)  # Inception
    assert not client.is_movie_tracked(999)


def test_mock_radarr_close():
    client = MockRadarrClient({})
    client.close()  # Should not raise


# -- Factory functions --


def test_sonarr_factory_empty_mode():
    """Empty mode (default) returns None — opt-in."""
    assert get_sonarr_client({"sonarr_mode": ""}) is None
    assert get_sonarr_client({}) is None


def test_sonarr_factory_mock():
    client = get_sonarr_client({"sonarr_mode": "mock"})
    assert isinstance(client, MockSonarrClient)


def test_radarr_factory_empty_mode():
    """Empty mode (default) returns None — opt-in."""
    assert get_radarr_client({"radarr_mode": ""}) is None
    assert get_radarr_client({}) is None


def test_radarr_factory_mock():
    client = get_radarr_client({"radarr_mode": "mock"})
    assert isinstance(client, MockRadarrClient)
