"""Mock Sonarr client for local development."""

import logging

from media.base import BaseSonarrClient

log = logging.getLogger("home-hud.media.mock_sonarr")

_CANNED_LIBRARY = [
    {"tvdbId": 81189, "title": "Breaking Bad", "year": 2008},
    {"tvdbId": 305288, "title": "Severance", "year": 2022},
    {"tvdbId": 356546, "title": "Fallout", "year": 2024},
]

_CANNED_SEARCH = {
    "severance": [
        {
            "tvdbId": 305288,
            "title": "Severance",
            "year": 2022,
            "overview": "Mark leads a team of office workers whose memories have been "
            "surgically divided between their work and personal lives.",
        },
    ],
    "breaking bad": [
        {
            "tvdbId": 81189,
            "title": "Breaking Bad",
            "year": 2008,
            "overview": "A high school chemistry teacher turned methamphetamine manufacturer.",
        },
        {
            "tvdbId": 299061,
            "title": "Breaking Bad: Original Minisodes",
            "year": 2009,
            "overview": "A series of short webisodes.",
        },
    ],
    "the bear": [
        {
            "tvdbId": 396238,
            "title": "The Bear",
            "year": 2022,
            "overview": "A young chef from the fine dining world returns to Chicago "
            "to run his family's sandwich shop.",
        },
    ],
    "batman": [
        {
            "tvdbId": 76168,
            "title": "Batman: The Animated Series",
            "year": 1992,
            "overview": "The Dark Knight battles crime in Gotham City with the "
            "help of Robin and Batgirl.",
        },
        {
            "tvdbId": 403172,
            "title": "Batman: Caped Crusader",
            "year": 2024,
            "overview": "An all-new animated series following the Dark Knight.",
        },
    ],
}


class MockSonarrClient(BaseSonarrClient):
    """Returns canned TV show data for development."""

    def __init__(self, config: dict):
        self._config = config
        self._library = list(_CANNED_LIBRARY)

    def search_series(self, term: str) -> list[dict]:
        log.info("Mock: searching series for '%s'", term)
        key = term.lower().strip()
        for canned_key, results in _CANNED_SEARCH.items():
            if canned_key in key or key in canned_key:
                return results
        # Default: return a generic result
        return [
            {
                "tvdbId": 999999,
                "title": term.title(),
                "year": 2024,
                "overview": f"A show called {term.title()}.",
            },
        ]

    def get_series(self) -> list[dict]:
        log.info("Mock: returning %d tracked series", len(self._library))
        return list(self._library)

    def add_series(self, tvdb_id: int, title: str) -> dict:
        log.info("Mock: adding series '%s' (tvdbId=%d)", title, tvdb_id)
        entry = {"tvdbId": tvdb_id, "title": title, "year": 2024}
        self._library.append(entry)
        return entry

    def is_series_tracked(self, tvdb_id: int) -> bool:
        return any(s["tvdbId"] == tvdb_id for s in self._library)
