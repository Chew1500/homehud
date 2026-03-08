"""Abstract base class for Jellyfin API client."""

from abc import ABC, abstractmethod


class BaseJellyfinClient(ABC):
    """Common interface for mock and real Jellyfin clients."""

    @abstractmethod
    def get_user_id(self) -> str:
        """Get the configured user ID."""
        ...

    @abstractmethod
    def get_library_items(self) -> list[dict]:
        """Get all movies and series with metadata, people, and watch history.

        Returns:
            List of dicts with keys: id, title, media_type ("movie"/"series"),
            year, genres, rating, certification, overview, studio,
            provider_ids (dict with Tmdb/Tvdb/Imdb), people (list of
            {name, role, type}), played, play_count, is_favorite
        """
        ...

    def close(self) -> None:
        """Clean up resources. Override if needed."""
        pass
