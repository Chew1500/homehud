"""Mock Jellyfin client for local development."""

import logging

from jellyfin.base import BaseJellyfinClient

log = logging.getLogger("home-hud.jellyfin.mock")

_CANNED_ITEMS = [
    {
        "id": "jf-001",
        "title": "Inception",
        "media_type": "movie",
        "year": 2010,
        "genres": ["Action", "Science Fiction", "Adventure"],
        "rating": 8.4,
        "certification": "PG-13",
        "overview": "A skilled thief who steals corporate secrets through dream "
        "infiltration is given the inverse task of planting an idea.",
        "studio": "Warner Bros. Pictures",
        "provider_ids": {"Tmdb": "27205", "Imdb": "tt1375666"},
        "people": [
            {"name": "Leonardo DiCaprio", "role": "Cobb", "type": "Actor"},
            {"name": "Joseph Gordon-Levitt", "role": "Arthur", "type": "Actor"},
            {"name": "Ellen Page", "role": "Ariadne", "type": "Actor"},
            {"name": "Tom Hardy", "role": "Eames", "type": "Actor"},
            {"name": "Christopher Nolan", "role": "", "type": "Director"},
        ],
        "played": True,
        "play_count": 3,
        "is_favorite": True,
    },
    {
        "id": "jf-002",
        "title": "Dune",
        "media_type": "movie",
        "year": 2021,
        "genres": ["Science Fiction", "Adventure"],
        "rating": 7.8,
        "certification": "PG-13",
        "overview": "Paul Atreides unites with the Fremen.",
        "studio": "Legendary Pictures",
        "provider_ids": {"Tmdb": "438631", "Imdb": "tt1160419"},
        "people": [
            {"name": "Timothée Chalamet", "role": "Paul Atreides", "type": "Actor"},
            {"name": "Zendaya", "role": "Chani", "type": "Actor"},
            {"name": "Denis Villeneuve", "role": "", "type": "Director"},
        ],
        "played": True,
        "play_count": 2,
        "is_favorite": False,
    },
    {
        "id": "jf-003",
        "title": "Oppenheimer",
        "media_type": "movie",
        "year": 2023,
        "genres": ["Drama", "History"],
        "rating": 8.1,
        "certification": "R",
        "overview": "The story of J. Robert Oppenheimer.",
        "studio": "Universal Pictures",
        "provider_ids": {"Tmdb": "872585", "Imdb": "tt15398776"},
        "people": [
            {"name": "Cillian Murphy", "role": "Oppenheimer", "type": "Actor"},
            {"name": "Robert Downey Jr.", "role": "Strauss", "type": "Actor"},
            {"name": "Christopher Nolan", "role": "", "type": "Director"},
        ],
        "played": False,
        "play_count": 0,
        "is_favorite": False,
    },
    {
        "id": "jf-004",
        "title": "Breaking Bad",
        "media_type": "series",
        "year": 2008,
        "genres": ["Drama", "Crime", "Thriller"],
        "rating": 8.9,
        "certification": "TV-MA",
        "overview": "A high school chemistry teacher turned methamphetamine manufacturer.",
        "studio": "AMC",
        "provider_ids": {"Tvdb": "81189", "Tmdb": "1396", "Imdb": "tt0903747"},
        "people": [
            {"name": "Bryan Cranston", "role": "Walter White", "type": "Actor"},
            {"name": "Aaron Paul", "role": "Jesse Pinkman", "type": "Actor"},
            {"name": "Vince Gilligan", "role": "", "type": "Director"},
        ],
        "played": True,
        "play_count": 2,
        "is_favorite": True,
    },
    {
        "id": "jf-005",
        "title": "Severance",
        "media_type": "series",
        "year": 2022,
        "genres": ["Drama", "Mystery", "Science Fiction", "Thriller"],
        "rating": 8.4,
        "certification": "TV-MA",
        "overview": "Mark leads a team of office workers whose memories have been "
        "surgically divided between their work and personal lives.",
        "studio": "Apple TV+",
        "provider_ids": {"Tvdb": "305288", "Tmdb": "95396", "Imdb": "tt11280740"},
        "people": [
            {"name": "Adam Scott", "role": "Mark Scout", "type": "Actor"},
            {"name": "Britt Lower", "role": "Helly R.", "type": "Actor"},
            {"name": "Ben Stiller", "role": "", "type": "Director"},
        ],
        "played": True,
        "play_count": 1,
        "is_favorite": True,
    },
]


class MockJellyfinClient(BaseJellyfinClient):
    """Returns canned library data with people and watch history for development."""

    def __init__(self, config: dict):
        self._config = config
        self._user_id = config.get("jellyfin_user_id", "mock-user-id")

    def get_user_id(self) -> str:
        return self._user_id

    def get_library_items(self) -> list[dict]:
        log.info("Mock: returning %d Jellyfin library items", len(_CANNED_ITEMS))
        return list(_CANNED_ITEMS)
