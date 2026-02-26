"""Abstract base classes for Sonarr and Radarr API clients."""

from abc import ABC, abstractmethod


class BaseSonarrClient(ABC):
    """Common interface for mock and real Sonarr clients."""

    @abstractmethod
    def search_series(self, term: str) -> list[dict]:
        """Search for TV series by name.

        Returns:
            List of dicts with keys: tvdbId, title, year, overview, remotePoster
        """
        ...

    @abstractmethod
    def get_series(self) -> list[dict]:
        """Get all tracked series.

        Returns:
            List of dicts with keys: tvdbId, title, year
        """
        ...

    @abstractmethod
    def add_series(self, tvdb_id: int, title: str) -> dict:
        """Add a series to Sonarr for monitoring.

        Args:
            tvdb_id: TVDB identifier.
            title: Series title (for logging/confirmation).

        Returns:
            Dict with added series info.
        """
        ...

    @abstractmethod
    def is_series_tracked(self, tvdb_id: int) -> bool:
        """Check if a series is already being tracked.

        Args:
            tvdb_id: TVDB identifier.
        """
        ...

    def close(self) -> None:
        """Clean up resources. Override if needed."""
        pass


class BaseRadarrClient(ABC):
    """Common interface for mock and real Radarr clients."""

    @abstractmethod
    def search_movie(self, term: str) -> list[dict]:
        """Search for movies by name.

        Returns:
            List of dicts with keys: tmdbId, title, year, overview, remotePoster
        """
        ...

    @abstractmethod
    def get_movies(self) -> list[dict]:
        """Get all tracked movies.

        Returns:
            List of dicts with keys: tmdbId, title, year
        """
        ...

    @abstractmethod
    def add_movie(self, tmdb_id: int, title: str) -> dict:
        """Add a movie to Radarr for monitoring.

        Args:
            tmdb_id: TMDB identifier.
            title: Movie title (for logging/confirmation).

        Returns:
            Dict with added movie info.
        """
        ...

    @abstractmethod
    def is_movie_tracked(self, tmdb_id: int) -> bool:
        """Check if a movie is already being tracked.

        Args:
            tmdb_id: TMDB identifier.
        """
        ...

    def close(self) -> None:
        """Clean up resources. Override if needed."""
        pass
