"""Real Sonarr v3 API client."""

from __future__ import annotations

import logging

from media.base import BaseSonarrClient

log = logging.getLogger("home-hud.media.sonarr")


class SonarrClient(BaseSonarrClient):
    """Connects to a Sonarr v3 instance via REST API.

    Uses httpx with X-Api-Key header authentication.
    Quality profile and root folder are lazily cached on first add.
    """

    def __init__(self, config: dict):
        import httpx

        self._config = config
        base_url = config.get("sonarr_url", "http://localhost:8989")
        api_key = config.get("sonarr_api_key", "")

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
                log.exception("Failed to fetch Sonarr quality profiles")

        if self._root_folder_path is None:
            try:
                resp = self._client.get("/api/v3/rootfolder")
                resp.raise_for_status()
                folders = resp.json()
                if folders:
                    self._root_folder_path = folders[0]["path"]
            except Exception:
                log.exception("Failed to fetch Sonarr root folders")

    def search_series(self, term: str) -> list[dict]:
        try:
            resp = self._client.get("/api/v3/series/lookup", params={"term": term})
            resp.raise_for_status()
            results = resp.json()
            return [
                {
                    "tvdbId": r.get("tvdbId", 0),
                    "title": r.get("title", ""),
                    "year": r.get("year", 0),
                    "overview": r.get("overview", ""),
                }
                for r in results
            ]
        except Exception:
            log.exception("Sonarr series search failed for '%s'", term)
            return []

    def get_series(self) -> list[dict]:
        try:
            resp = self._client.get("/api/v3/series")
            resp.raise_for_status()
            return [
                {
                    "tvdbId": s.get("tvdbId", 0),
                    "title": s.get("title", ""),
                    "year": s.get("year", 0),
                }
                for s in resp.json()
            ]
        except Exception:
            log.exception("Failed to fetch Sonarr series list")
            return []

    def add_series(self, tvdb_id: int, title: str) -> dict:
        self._ensure_defaults()
        payload = {
            "tvdbId": tvdb_id,
            "title": title,
            "qualityProfileId": self._quality_profile_id or 1,
            "rootFolderPath": self._root_folder_path or "/tv",
            "monitored": True,
            "addOptions": {"searchForMissingEpisodes": True},
        }
        try:
            resp = self._client.post("/api/v3/series", json=payload)
            resp.raise_for_status()
            data = resp.json()
            return {
                "tvdbId": data.get("tvdbId", tvdb_id),
                "title": data.get("title", title),
                "year": data.get("year", 0),
            }
        except Exception:
            log.exception("Failed to add series '%s' to Sonarr", title)
            return {"tvdbId": tvdb_id, "title": title, "error": True}

    def is_series_tracked(self, tvdb_id: int) -> bool:
        return any(s["tvdbId"] == tvdb_id for s in self.get_series())

    def close(self) -> None:
        self._client.close()
