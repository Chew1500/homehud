"""Media library feature — query and track movies/shows via Sonarr and Radarr."""

from __future__ import annotations

import logging
import re
import time

from features.base import BaseFeature
from media.base import BaseRadarrClient, BaseSonarrClient

log = logging.getLogger("home-hud.features.media")

# -- Disambiguation responses --
_YES = re.compile(r"\b(yes|yeah|yep|sure|do it|go ahead|add it|confirm)\b", re.IGNORECASE)
_NO_NEXT = re.compile(r"\b(no|nope|nah|next|skip|not that one)\b", re.IGNORECASE)
_CANCEL = re.compile(
    r"\b(cancel|never\s*mind|forget\s*it|stop|quit|done)\b", re.IGNORECASE
)

# -- Command patterns --

# List: "what movies do I have", "what shows am I tracking", "list my movies"
_LIST_MOVIES = re.compile(
    r"\b(?:what\s+movies?\s+(?:do\s+I\s+have|am\s+I\s+tracking)"
    r"|list\s+(?:my\s+)?movies?"
    r"|show\s+(?:me\s+)?my\s+movies?)\b",
    re.IGNORECASE,
)
_LIST_SHOWS = re.compile(
    r"\b(?:what\s+(?:shows?|series|tv)\s+(?:do\s+I\s+have|am\s+I\s+tracking)"
    r"|list\s+(?:my\s+)?(?:shows?|series|tv)"
    r"|show\s+(?:me\s+)?my\s+(?:shows?|series|tv))\b",
    re.IGNORECASE,
)

# Check: "is Breaking Bad in my library", "do I have Inception"
_CHECK = re.compile(
    r"\b(?:is\s+(.+?)\s+in\s+my\s+(?:library|collection)"
    r"|do\s+I\s+have\s+(.+?))\s*\??$",
    re.IGNORECASE,
)

# Track: "track the movie Inception", "add Severance to my shows", "download Dune"
_TRACK_MOVIE = re.compile(
    r"\b(?:track|add|download|grab|get)\s+(?:the\s+)?movie\s+(.+)",
    re.IGNORECASE,
)
_TRACK_SHOW = re.compile(
    r"\b(?:track|add|download|grab|get)\s+(?:the\s+)?(?:show|series|tv\s+show)\s+(.+)",
    re.IGNORECASE,
)
# "add X to my shows/movies"
_TRACK_TO_MOVIES = re.compile(
    r"\b(?:track|add|download|grab|get)\s+(.+?)\s+to\s+(?:my\s+)?movies?\b",
    re.IGNORECASE,
)
_TRACK_TO_SHOWS = re.compile(
    r"\b(?:track|add|download|grab|get)\s+(.+?)\s+to\s+(?:my\s+)?(?:shows?|series|tv)\b",
    re.IGNORECASE,
)
# Generic track without specifying movie/show: "track Inception", "download Dune"
_TRACK_GENERIC = re.compile(
    r"\b(?:track|download|grab)\s+(?:the\s+)?(.+)",
    re.IGNORECASE,
)

# Broad match for routing — any media-related mention
_ANY_MEDIA = re.compile(
    r"\b(movie|movies|show|shows|series|tv|track|download|library|radarr|sonarr)\b",
    re.IGNORECASE,
)


class MediaFeature(BaseFeature):
    """Voice-controlled media library management via Sonarr and Radarr.

    Handles listing, checking, and tracking movies/shows. When a search
    returns multiple results, enters a disambiguation flow where the user
    can confirm, skip, or cancel.
    """

    def __init__(
        self,
        config: dict,
        sonarr: BaseSonarrClient | None = None,
        radarr: BaseRadarrClient | None = None,
    ):
        super().__init__(config)
        self._sonarr = sonarr
        self._radarr = radarr
        self._ttl = config.get("media_disambiguation_ttl", 60)

        # Disambiguation state
        self._pending: dict | None = None  # {type, results, index, timestamp}

    @property
    def name(self) -> str:
        return "Media Library"

    @property
    def short_description(self) -> str:
        parts = []
        if self._radarr:
            parts.append("movies")
        if self._sonarr:
            parts.append("TV shows")
        media = " and ".join(parts) or "media"
        return f"Search, track, and manage your {media}"

    @property
    def description(self) -> str:
        return (
            'Media library: triggered by "movie", "show", "series", "track", '
            '"download", "library". Commands: "what movies do I have", '
            '"is Breaking Bad in my library", "track the movie Inception", '
            '"add Severance to my shows", "download Dune".'
        )

    def matches(self, text: str) -> bool:
        # Fast path: active disambiguation captures yes/no/next/cancel
        if self._pending and not self._is_expired():
            if _YES.search(text) or _NO_NEXT.search(text) or _CANCEL.search(text):
                return True

        return bool(_ANY_MEDIA.search(text))

    def handle(self, text: str) -> str:
        # Disambiguation flow takes priority
        if self._pending and not self._is_expired():
            if _YES.search(text):
                return self._confirm_pending()
            if _NO_NEXT.search(text):
                return self._next_pending()
            if _CANCEL.search(text):
                return self._cancel_pending()

        # Expire stale pending state
        if self._pending and self._is_expired():
            self._pending = None

        # List commands
        if _LIST_MOVIES.search(text):
            return self._list_movies()
        if _LIST_SHOWS.search(text):
            return self._list_shows()

        # Check commands
        m = _CHECK.search(text)
        if m:
            title = (m.group(1) or m.group(2)).strip()
            return self._check_title(title)

        # Track commands (specific type first, then generic)
        m = _TRACK_MOVIE.search(text) or _TRACK_TO_MOVIES.search(text)
        if m:
            return self._track_movie(m.group(1).strip())

        m = _TRACK_SHOW.search(text) or _TRACK_TO_SHOWS.search(text)
        if m:
            return self._track_show(m.group(1).strip())

        m = _TRACK_GENERIC.search(text)
        if m:
            return self._track_generic(m.group(1).strip())

        # Fallback
        return self._status()

    # -- List handlers --

    def _list_movies(self) -> str:
        if not self._radarr:
            return "Movie tracking isn't configured."
        movies = self._radarr.get_movies()
        if not movies:
            return "You don't have any movies being tracked."
        titles = [f"{m['title']} ({m['year']})" for m in movies]
        return self._format_title_list(titles, "movie", "movies")

    def _list_shows(self) -> str:
        if not self._sonarr:
            return "TV show tracking isn't configured."
        shows = self._sonarr.get_series()
        if not shows:
            return "You don't have any shows being tracked."
        titles = [f"{s['title']} ({s['year']})" for s in shows]
        return self._format_title_list(titles, "show", "shows")

    @staticmethod
    def _format_title_list(titles: list[str], singular: str, plural: str) -> str:
        """Format a title list for TTS, truncating to 5 for large libraries."""
        count = len(titles)
        if count == 1:
            return f"You have one {singular}: {titles[0]}."
        if count <= 5:
            joined = ", ".join(titles[:-1]) + f", and {titles[-1]}"
            return f"You have {count} {plural}: {joined}."
        # Large library: count + last 5 (most recently added)
        recent = titles[-5:]
        joined = ", ".join(recent[:-1]) + f", and {recent[-1]}"
        return f"You have {count} {plural}. Some recent ones are {joined}."

    # -- Check handler --

    def _check_title(self, title: str) -> str:
        found = []
        if self._radarr:
            movies = self._radarr.get_movies()
            for m in movies:
                if title.lower() in m["title"].lower():
                    found.append(f"{m['title']} ({m['year']})")
        if self._sonarr:
            shows = self._sonarr.get_series()
            for s in shows:
                if title.lower() in s["title"].lower():
                    found.append(f"{s['title']} ({s['year']})")

        if not found:
            return f"I don't see {title} in your library."
        if len(found) == 1:
            return f"Yes, you have {found[0]} in your library."
        joined = " and ".join(found)
        return f"Yes, you have {joined} in your library."

    # -- Track handlers --

    def _track_movie(self, title: str) -> str:
        if not self._radarr:
            return "Movie tracking isn't configured. Set up Radarr to enable it."
        results = self._radarr.search_movie(title)
        if not results:
            return f"I couldn't find any movies matching {title}."
        return self._start_disambiguation("movie", results)

    def _track_show(self, title: str) -> str:
        if not self._sonarr:
            return "TV show tracking isn't configured. Set up Sonarr to enable it."
        results = self._sonarr.search_series(title)
        if not results:
            return f"I couldn't find any shows matching {title}."
        return self._start_disambiguation("show", results)

    def _track_generic(self, title: str) -> str:
        # Try movies first, then shows
        if self._radarr:
            results = self._radarr.search_movie(title)
            if results:
                return self._start_disambiguation("movie", results)
        if self._sonarr:
            results = self._sonarr.search_series(title)
            if results:
                return self._start_disambiguation("show", results)
        if not self._radarr and not self._sonarr:
            return "Media tracking isn't configured."
        return f"I couldn't find anything matching {title}."

    # -- Disambiguation --

    def _start_disambiguation(self, media_type: str, results: list[dict]) -> str:
        """Begin disambiguation flow with search results."""
        first = results[0]
        id_key = "tmdbId" if media_type == "movie" else "tvdbId"

        # Check if already tracked
        if media_type == "movie" and self._radarr:
            if self._radarr.is_movie_tracked(first[id_key]):
                return (
                    f"You're already tracking {first['title']} from {first['year']}."
                )
        elif media_type == "show" and self._sonarr:
            if self._sonarr.is_series_tracked(first[id_key]):
                return (
                    f"You're already tracking {first['title']} from {first['year']}."
                )

        self._pending = {
            "type": media_type,
            "results": results,
            "index": 0,
            "timestamp": time.time(),
        }
        return self._describe_current()

    def _describe_current(self) -> str:
        """Describe the current disambiguation candidate."""
        result = self._pending["results"][self._pending["index"]]
        title = result["title"]
        year = result["year"]
        overview = result.get("overview", "")

        desc = f"I found {title} from {year}."
        if overview:
            # Truncate long overviews for TTS
            if len(overview) > 150:
                overview = overview[:147] + "..."
            desc += f" {overview}"
        desc += " Should I add this one?"
        return desc

    def _confirm_pending(self) -> str:
        """User confirmed the current candidate — add it."""
        result = self._pending["results"][self._pending["index"]]
        media_type = self._pending["type"]
        self._pending = None

        if media_type == "movie" and self._radarr:
            added = self._radarr.add_movie(result["tmdbId"], result["title"])
            if added.get("error"):
                return f"Sorry, there was a problem adding {result['title']}."
            return f"Done! I've added {result['title']} ({result['year']}) to your movies."

        if media_type == "show" and self._sonarr:
            added = self._sonarr.add_series(result["tvdbId"], result["title"])
            if added.get("error"):
                return f"Sorry, there was a problem adding {result['title']}."
            return f"Done! I've added {result['title']} ({result['year']}) to your shows."

        return "Something went wrong — the media service isn't available."

    def _next_pending(self) -> str:
        """User rejected the current candidate — show the next one."""
        self._pending["index"] += 1
        self._pending["timestamp"] = time.time()  # reset TTL

        if self._pending["index"] >= len(self._pending["results"]):
            self._pending = None
            return (
                "That's all the results I found. "
                "You can try searching again with different words."
            )

        # Check if next result is already tracked
        result = self._pending["results"][self._pending["index"]]
        media_type = self._pending["type"]
        id_key = "tmdbId" if media_type == "movie" else "tvdbId"

        if media_type == "movie" and self._radarr:
            if self._radarr.is_movie_tracked(result[id_key]):
                already = f"You're already tracking {result['title']} from {result['year']}."
                # Auto-advance to next
                self._pending["index"] += 1
                if self._pending["index"] >= len(self._pending["results"]):
                    self._pending = None
                    return already + " That's all the results."
                return already + " " + self._describe_current()
        elif media_type == "show" and self._sonarr:
            if self._sonarr.is_series_tracked(result[id_key]):
                already = f"You're already tracking {result['title']} from {result['year']}."
                self._pending["index"] += 1
                if self._pending["index"] >= len(self._pending["results"]):
                    self._pending = None
                    return already + " That's all the results."
                return already + " " + self._describe_current()

        return self._describe_current()

    def _cancel_pending(self) -> str:
        """User cancelled disambiguation."""
        self._pending = None
        return "Okay, cancelled."

    def _is_expired(self) -> bool:
        """Check if pending disambiguation has timed out."""
        if not self._pending:
            return True
        return (time.time() - self._pending["timestamp"]) > self._ttl

    # -- Status --

    def _status(self) -> str:
        """General status when no specific command matched."""
        parts = []
        if self._radarr:
            count = len(self._radarr.get_movies())
            parts.append(f"{count} movie{'s' if count != 1 else ''}")
        if self._sonarr:
            count = len(self._sonarr.get_series())
            parts.append(f"{count} show{'s' if count != 1 else ''}")
        if parts:
            tracking = " and ".join(parts)
            return f"You're tracking {tracking}. You can ask me to list, check, or track titles."
        return "Media tracking isn't configured."

    def close(self) -> None:
        if self._sonarr:
            self._sonarr.close()
        if self._radarr:
            self._radarr.close()
