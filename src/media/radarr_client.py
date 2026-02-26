"""Real Radarr v3 API client."""

from __future__ import annotations

import logging

from media.base import BaseRadarrClient

log = logging.getLogger("home-hud.media.radarr")


class RadarrClient(BaseRadarrClient):
    """Connects to a Radarr v3 instance via REST API.

    Uses httpx with X-Api-Key header authentication.
    Quality profile and root folder are lazily cached on first add.
    """

    def __init__(self, config: dict):
        import httpx

        self._config = config
        base_url = config.get("radarr_url", "http://localhost:7878")
        api_key = config.get("radarr_api_key", "")

        self._client = httpx.Client(
            base_url=base_url,
            timeout=15.0,
            headers={"X-Api-Key": api_key},
        )
        self._quality_profile_id: int | None = None
        self._root_folder_path: str | None = None

    def _ensure_defaults(self) -> None:
        """Lazily fetch and cache quality profile ID and root folder path."""
        if self._quality_profile_id is None:
            try:
                resp = self._client.get("/api/v3/qualityprofile")
                resp.raise_for_status()
                profiles = resp.json()
                if profiles:
                    self._quality_profile_id = profiles[0]["id"]
            except Exception:
                log.exception("Failed to fetch Radarr quality profiles")

        if self._root_folder_path is None:
            try:
                resp = self._client.get("/api/v3/rootfolder")
                resp.raise_for_status()
                folders = resp.json()
                if folders:
                    self._root_folder_path = folders[0]["path"]
            except Exception:
                log.exception("Failed to fetch Radarr root folders")

    def search_movie(self, term: str) -> list[dict]:
        try:
            resp = self._client.get("/api/v3/movie/lookup", params={"term": term})
            resp.raise_for_status()
            results = resp.json()
            return [
                {
                    "tmdbId": r.get("tmdbId", 0),
                    "title": r.get("title", ""),
                    "year": r.get("year", 0),
                    "overview": r.get("overview", ""),
                }
                for r in results
            ]
        except Exception:
            log.exception("Radarr movie search failed for '%s'", term)
            return []

    def get_movies(self) -> list[dict]:
        try:
            resp = self._client.get("/api/v3/movie")
            resp.raise_for_status()
            return [
                {
                    "tmdbId": m.get("tmdbId", 0),
                    "title": m.get("title", ""),
                    "year": m.get("year", 0),
                }
                for m in resp.json()
            ]
        except Exception:
            log.exception("Failed to fetch Radarr movie list")
            return []

    def add_movie(self, tmdb_id: int, title: str) -> dict:
        self._ensure_defaults()
        payload = {
            "tmdbId": tmdb_id,
            "title": title,
            "qualityProfileId": self._quality_profile_id or 1,
            "rootFolderPath": self._root_folder_path or "/movies",
            "monitored": True,
            "addOptions": {"searchForMovie": True},
        }
        try:
            resp = self._client.post("/api/v3/movie", json=payload)
            resp.raise_for_status()
            data = resp.json()
            return {
                "tmdbId": data.get("tmdbId", tmdb_id),
                "title": data.get("title", title),
                "year": data.get("year", 0),
            }
        except Exception:
            log.exception("Failed to add movie '%s' to Radarr", title)
            return {"tmdbId": tmdb_id, "title": title, "error": True}

    def is_movie_tracked(self, tmdb_id: int) -> bool:
        return any(m["tmdbId"] == tmdb_id for m in self.get_movies())

    def close(self) -> None:
        self._client.close()
