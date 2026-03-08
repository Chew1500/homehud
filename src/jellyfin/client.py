"""Real Jellyfin API client."""

from __future__ import annotations

import logging
import re

from jellyfin.base import BaseJellyfinClient

log = logging.getLogger("home-hud.jellyfin.client")


class JellyfinClient(BaseJellyfinClient):
    """Connects to a Jellyfin instance via REST API.

    Uses X-Emby-Token header for authentication.
    """

    def __init__(self, config: dict):
        import httpx

        self._config = config
        base_url = config.get("jellyfin_url", "http://localhost:8096")
        api_key = config.get("jellyfin_api_key", "")
        self._user_id = config.get("jellyfin_user_id", "")

        self._client = httpx.Client(
            base_url=base_url,
            timeout=30.0,
            headers={"X-Emby-Token": api_key},
        )
        self._resolve_user_id()

    def _resolve_user_id(self) -> None:
        """Translate a username (or empty string) into the Jellyfin internal UUID."""
        # Already a hex UUID (32+ hex chars) — no resolution needed.
        if re.fullmatch(r"[0-9a-fA-F]{32,}", self._user_id):
            return

        try:
            resp = self._client.get("/Users")
            resp.raise_for_status()
            users = resp.json()
        except Exception:
            log.warning(
                "Failed to resolve Jellyfin user ID — keeping '%s'",
                self._user_id,
            )
            return

        if not users:
            log.warning("Jellyfin returned no users — keeping '%s'", self._user_id)
            return

        if not self._user_id:
            # No user configured — pick the first one.
            resolved = users[0]
        else:
            # Match by username (case-insensitive).
            needle = self._user_id.lower()
            resolved = next(
                (u for u in users if u.get("Name", "").lower() == needle), None
            )

        if resolved:
            old = self._user_id or "(empty)"
            self._user_id = resolved["Id"]
            log.info(
                "Resolved Jellyfin user '%s' → %s", old, self._user_id[:8] + "..."
            )
        else:
            log.warning(
                "Jellyfin user '%s' not found — keeping as-is", self._user_id
            )

    def get_user_id(self) -> str:
        return self._user_id

    def get_library_items(self) -> list[dict]:
        try:
            resp = self._client.get(
                f"/Users/{self._user_id}/Items",
                params={
                    "Recursive": "true",
                    "IncludeItemTypes": "Movie,Series",
                    "Fields": "Genres,People,Overview,Studios,CommunityRating,"
                              "OfficialRating,ProviderIds",
                    "EnableUserData": "true",
                },
            )
            resp.raise_for_status()
            items = resp.json().get("Items", [])
            return [self._normalize_item(item) for item in items]
        except Exception:
            log.exception("Failed to fetch Jellyfin library items")
            return []

    def _normalize_item(self, item: dict) -> dict:
        user_data = item.get("UserData", {})
        studios = item.get("Studios", [])
        people = item.get("People", [])

        return {
            "id": item.get("Id", ""),
            "title": item.get("Name", ""),
            "media_type": "movie" if item.get("Type") == "Movie" else "series",
            "year": item.get("ProductionYear", 0),
            "genres": item.get("Genres", []),
            "rating": item.get("CommunityRating"),
            "certification": item.get("OfficialRating", ""),
            "overview": item.get("Overview", ""),
            "studio": studios[0].get("Name", "") if studios else "",
            "provider_ids": item.get("ProviderIds", {}),
            "people": [
                {
                    "name": p.get("Name", ""),
                    "role": p.get("Role", ""),
                    "type": p.get("Type", ""),
                }
                for p in people
            ],
            "played": user_data.get("Played", False),
            "play_count": user_data.get("PlayCount", 0),
            "is_favorite": user_data.get("IsFavorite", False),
        }

    def close(self) -> None:
        self._client.close()
