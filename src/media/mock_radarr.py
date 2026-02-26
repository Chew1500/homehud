"""Mock Radarr client for local development."""

import logging

from media.base import BaseRadarrClient

log = logging.getLogger("home-hud.media.mock_radarr")

_CANNED_LIBRARY = [
    {"tmdbId": 27205, "title": "Inception", "year": 2010},
    {"tmdbId": 438631, "title": "Dune", "year": 2021},
    {"tmdbId": 872585, "title": "Oppenheimer", "year": 2023},
]

_CANNED_SEARCH = {
    "inception": [
        {
            "tmdbId": 27205,
            "title": "Inception",
            "year": 2010,
            "overview": "A skilled thief who steals corporate secrets through dream "
            "infiltration is given the inverse task of planting an idea.",
        },
        {
            "tmdbId": 991234,
            "title": "Inception: The Cobol Job",
            "year": 2010,
            "overview": "An animated prequel comic to the film Inception.",
        },
    ],
    "dune": [
        {
            "tmdbId": 438631,
            "title": "Dune",
            "year": 2021,
            "overview": "Paul Atreides unites with the Fremen to seek revenge against "
            "those who destroyed his family.",
        },
        {
            "tmdbId": 693134,
            "title": "Dune: Part Two",
            "year": 2024,
            "overview": "Paul Atreides unites with the Fremen while on a warpath of "
            "revenge against the conspirators.",
        },
    ],
    "oppenheimer": [
        {
            "tmdbId": 872585,
            "title": "Oppenheimer",
            "year": 2023,
            "overview": "The story of American scientist J. Robert Oppenheimer "
            "and his role in the development of the atomic bomb.",
        },
    ],
}


class MockRadarrClient(BaseRadarrClient):
    """Returns canned movie data for development."""

    def __init__(self, config: dict):
        self._config = config
        self._library = list(_CANNED_LIBRARY)

    def search_movie(self, term: str) -> list[dict]:
        log.info("Mock: searching movies for '%s'", term)
        key = term.lower().strip()
        for canned_key, results in _CANNED_SEARCH.items():
            if canned_key in key or key in canned_key:
                return results
        # Default: return a generic result
        return [
            {
                "tmdbId": 999999,
                "title": term.title(),
                "year": 2024,
                "overview": f"A movie called {term.title()}.",
            },
        ]

    def get_movies(self) -> list[dict]:
        log.info("Mock: returning %d tracked movies", len(self._library))
        return list(self._library)

    def add_movie(self, tmdb_id: int, title: str) -> dict:
        log.info("Mock: adding movie '%s' (tmdbId=%d)", title, tmdb_id)
        entry = {"tmdbId": tmdb_id, "title": title, "year": 2024}
        self._library.append(entry)
        return entry

    def is_movie_tracked(self, tmdb_id: int) -> bool:
        return any(m["tmdbId"] == tmdb_id for m in self._library)
