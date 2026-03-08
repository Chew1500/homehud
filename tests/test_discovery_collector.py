"""Tests for library collector — sync behavior, taste rebuild, shutdown."""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from discovery.collector import LibraryCollector  # noqa: E402
from discovery.storage import DiscoveryStorage  # noqa: E402
from jellyfin.mock_client import MockJellyfinClient  # noqa: E402
from media.mock_radarr import MockRadarrClient  # noqa: E402
from media.mock_sonarr import MockSonarrClient  # noqa: E402


def _make_collector(tmp_path, **kwargs):
    storage = DiscoveryStorage(str(tmp_path / "test.db"))
    config = {
        "discovery_library_sync_interval": 3600,
        "discovery_interval": 86400,
    }
    radarr = kwargs.get("radarr", MockRadarrClient({}))
    sonarr = kwargs.get("sonarr", MockSonarrClient({}))
    jellyfin = kwargs.get("jellyfin", MockJellyfinClient({}))
    engine = kwargs.get("engine")
    collector = LibraryCollector(
        storage, config,
        radarr=radarr, sonarr=sonarr, jellyfin=jellyfin,
        engine=engine,
    )
    return collector, storage


def test_sync_populates_library(tmp_path):
    collector, storage = _make_collector(tmp_path)
    collector._sync_library()
    # Should have movies from Radarr + series from Sonarr + items from Jellyfin
    count = storage.get_library_count()
    assert count >= 3  # At least the canned data
    storage.close()


def test_sync_radarr(tmp_path):
    collector, storage = _make_collector(tmp_path, sonarr=None, jellyfin=None)
    collector._sync_library()
    titles = storage.get_library_titles()
    assert "Inception" in titles
    storage.close()


def test_sync_sonarr(tmp_path):
    collector, storage = _make_collector(tmp_path, radarr=None, jellyfin=None)
    collector._sync_library()
    titles = storage.get_library_titles()
    assert "Breaking Bad" in titles
    storage.close()


def test_sync_jellyfin_with_people(tmp_path):
    collector, storage = _make_collector(tmp_path, radarr=None, sonarr=None)
    collector._sync_library()
    storage.rebuild_taste_profile()
    profile = storage.get_taste_profile()
    actor_entries = [p for p in profile if p["dimension"] == "actor"]
    assert len(actor_entries) > 0
    storage.close()


def test_rebuild_taste_after_sync(tmp_path):
    collector, storage = _make_collector(tmp_path)
    collector._sync_library()
    storage.rebuild_taste_profile()
    profile = storage.get_taste_profile()
    assert len(profile) > 0
    storage.close()


def test_sync_sets_sync_time(tmp_path):
    collector, storage = _make_collector(tmp_path)
    collector._sync_library()
    assert storage.get_sync_time("radarr") is not None
    assert storage.get_sync_time("sonarr") is not None
    assert storage.get_sync_time("jellyfin") is not None
    storage.close()


def test_collector_clean_shutdown(tmp_path):
    collector, storage = _make_collector(tmp_path)
    # Use a very short interval so it runs quickly
    collector._library_sync_interval = 0.1
    thread = collector.start()
    time.sleep(0.3)
    collector.close()
    thread.join(timeout=2)
    assert not thread.is_alive()
    storage.close()


def test_dedup_across_sources(tmp_path):
    """Items from Radarr and Jellyfin with same external_id should dedup."""
    collector, storage = _make_collector(tmp_path)
    collector._sync_library()
    # Inception appears in both Radarr (tmdbId=27205) and Jellyfin (Tmdb=27205)
    # Should be deduped via UNIQUE(external_id, media_type)
    titles = storage.get_library_titles()
    inception_count = sum(1 for t in titles if t == "Inception")
    assert inception_count == 1
    storage.close()


def test_collector_with_no_clients(tmp_path):
    """Collector should handle no clients gracefully."""
    collector, storage = _make_collector(
        tmp_path, radarr=None, sonarr=None, jellyfin=None
    )
    collector._sync_library()
    assert storage.get_library_count() == 0
    storage.close()
