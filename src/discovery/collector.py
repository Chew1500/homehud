"""Background library sync — pulls from Radarr/Sonarr/Jellyfin into discovery storage."""

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING

from discovery.storage import DiscoveryStorage

if TYPE_CHECKING:
    from jellyfin.base import BaseJellyfinClient
    from media.base import BaseRadarrClient, BaseSonarrClient

log = logging.getLogger("home-hud.discovery.collector")


class LibraryCollector:
    """Daemon thread that syncs media libraries and rebuilds taste profiles.

    - Immediate first sync on start
    - Library sync: every library_sync_interval seconds (default 6h)
    - After each library sync, rebuilds taste profile
    - Discovery (LLM recommendations): every discovery_interval seconds (default 24h)
    """

    def __init__(
        self,
        storage: DiscoveryStorage,
        config: dict,
        radarr: BaseRadarrClient | None = None,
        sonarr: BaseSonarrClient | None = None,
        jellyfin: BaseJellyfinClient | None = None,
        engine=None,
    ):
        self._storage = storage
        self._radarr = radarr
        self._sonarr = sonarr
        self._jellyfin = jellyfin
        self._engine = engine
        self._library_sync_interval = config.get("discovery_library_sync_interval", 21600)
        self._discovery_interval = config.get("discovery_interval", 86400)
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._cycles_since_discovery = 0

    def start(self) -> threading.Thread:
        """Start the collector daemon thread."""
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        log.info(
            "Library collector started (sync every %ds, discover every %ds)",
            self._library_sync_interval,
            self._discovery_interval,
        )
        return self._thread

    def _loop(self) -> None:
        # Calculate how many library sync cycles equal one discovery cycle
        discovery_every_n = max(
            1, self._discovery_interval // self._library_sync_interval
        )

        while not self._stop_event.is_set():
            try:
                self._sync_library()
                self._storage.rebuild_taste_profile()
                log.info("Taste profile rebuilt")

                self._cycles_since_discovery += 1
                if self._engine and self._cycles_since_discovery >= discovery_every_n:
                    self._run_discovery()
                    self._cycles_since_discovery = 0
            except Exception:
                log.exception("Error in library collector cycle")

            self._stop_event.wait(timeout=self._library_sync_interval)

    def _sync_library(self) -> None:
        """Pull data from all configured sources into storage."""
        if self._radarr:
            self._sync_radarr()
        if self._sonarr:
            self._sync_sonarr()
        if self._jellyfin:
            self._sync_jellyfin()

    def _sync_radarr(self) -> None:
        try:
            movies = self._radarr.get_movies_detailed()
            for m in movies:
                ratings = m.get("ratings", {})
                self._storage.upsert_library_item({
                    "external_id": str(m["tmdbId"]),
                    "title": m["title"],
                    "media_type": "movie",
                    "year": m.get("year"),
                    "genres": m.get("genres", []),
                    "rating_imdb": ratings.get("imdb"),
                    "rating_tmdb": ratings.get("tmdb"),
                    "rating_rt": ratings.get("rottenTomatoes"),
                    "studio": m.get("studio", ""),
                    "runtime": m.get("runtime"),
                    "certification": m.get("certification", ""),
                    "overview": m.get("overview", ""),
                    "source": "radarr",
                })
            self._storage.set_sync_time("radarr")
            log.info("Synced %d movies from Radarr", len(movies))
        except Exception:
            log.exception("Failed to sync Radarr")

    def _sync_sonarr(self) -> None:
        try:
            series = self._sonarr.get_series_detailed()
            for s in series:
                ratings = s.get("ratings", {})
                self._storage.upsert_library_item({
                    "external_id": str(s["tvdbId"]),
                    "title": s["title"],
                    "media_type": "series",
                    "year": s.get("year"),
                    "genres": s.get("genres", []),
                    "rating_imdb": ratings.get("imdb"),
                    "rating_tmdb": ratings.get("tmdb"),
                    "rating_rt": ratings.get("rottenTomatoes"),
                    "studio": s.get("network", ""),
                    "runtime": s.get("runtime"),
                    "certification": s.get("certification", ""),
                    "overview": s.get("overview", ""),
                    "source": "sonarr",
                })
            self._storage.set_sync_time("sonarr")
            log.info("Synced %d series from Sonarr", len(series))
        except Exception:
            log.exception("Failed to sync Sonarr")

    def _sync_jellyfin(self) -> None:
        try:
            items = self._jellyfin.get_library_items()
            for item in items:
                provider_ids = item.get("provider_ids", {})
                # Use TMDB ID for movies, TVDB ID for series (to match Radarr/Sonarr)
                if item["media_type"] == "movie":
                    ext_id = provider_ids.get("Tmdb", item["id"])
                else:
                    ext_id = provider_ids.get("Tvdb", item["id"])

                # Update existing items with watch data, or insert if new
                existing_id = self._storage.get_library_item_id(
                    str(ext_id), item["media_type"]
                )

                lib_id = self._storage.upsert_library_item({
                    "external_id": str(ext_id),
                    "title": item["title"],
                    "media_type": item["media_type"],
                    "year": item.get("year"),
                    "genres": item.get("genres", []),
                    "rating_tmdb": item.get("rating"),
                    "studio": item.get("studio", ""),
                    "certification": item.get("certification", ""),
                    "overview": item.get("overview", ""),
                    "played": item.get("played", False),
                    "play_count": item.get("play_count", 0),
                    "is_favorite": item.get("is_favorite", False),
                    "source": "jellyfin",
                })

                # Store people (limit: top 10 actors + all directors)
                people = item.get("people", [])
                actors = [p for p in people if p.get("type") == "Actor"][:10]
                directors = [p for p in people if p.get("type") == "Director"]
                writers = [p for p in people if p.get("type") == "Writer"]
                filtered_people = actors + directors + writers

                if filtered_people:
                    # Use existing_id if we had a prior row, otherwise use
                    # the upsert return which may be 0 for updates
                    row_id = existing_id or lib_id
                    if row_id:
                        self._storage.set_people(row_id, filtered_people)

            self._storage.set_sync_time("jellyfin")
            log.info("Synced %d items from Jellyfin", len(items))
        except Exception:
            log.exception("Failed to sync Jellyfin")

    def _run_discovery(self) -> None:
        """Run the LLM discovery engine to generate recommendations."""
        try:
            self._engine.generate()
            log.info("Discovery engine generated new recommendations")
        except Exception:
            log.exception("Discovery engine error")

    def close(self) -> None:
        """Stop the collector thread."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
            log.info("Library collector stopped")
