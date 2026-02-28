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

# -- Refining patterns (used during refining phase) --
_REFINE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
_REFINE_MOVIE = re.compile(r"\b(movie|film)\b", re.IGNORECASE)
_REFINE_SHOW = re.compile(r"\b(show|series|tv)\b", re.IGNORECASE)
_REFINE_RECENT = re.compile(r"\b(new|newest|latest|recent)\b", re.IGNORECASE)
_REFINE_ANY = re.compile(
    r"\b((?:19|20)\d{2}|movie|film|show|series|tv|new|newest|latest|recent)\b",
    re.IGNORECASE,
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

# Union of all new-command patterns (for detecting new commands during refining)
_NEW_COMMAND_PATTERNS = [
    _LIST_MOVIES, _LIST_SHOWS, _CHECK,
    _TRACK_MOVIE, _TRACK_SHOW, _TRACK_TO_MOVIES, _TRACK_TO_SHOWS, _TRACK_GENERIC,
]


def _clean_title(text: str) -> str:
    """Strip trailing punctuation that Whisper may add to transcribed titles."""
    return re.sub(r"[.!?,;:]+$", "", text)


def _title_relevance(title: str, search_term: str) -> float:
    """Score how well a result title matches the search term (0.0 to 1.0)."""
    t = title.lower()
    s = search_term.lower()
    if t == s:
        return 1.0
    if t.startswith(s):
        return 0.8
    if s in t:
        return 0.6
    # Word overlap — fraction of search words found in the title
    s_words = set(s.split())
    if s_words:
        t_words = set(t.split())
        overlap = len(t_words & s_words) / len(s_words)
        return 0.4 * overlap
    return 0.0


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
        # {results, index, phase, timestamp}
        # phase: "confirming" (one-by-one) or "refining" (summary + filter)
        # Each result has a "media_type" key ("movie" or "show").
        self._pending: dict | None = None

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

    @property
    def expects_follow_up(self) -> bool:
        return self._pending is not None and not self._is_expired()

    @property
    def action_schema(self) -> dict:
        return {
            "track": {"title": "str", "media_type": "str"},
            "list": {"media_type": "str"},
            "check": {"title": "str"},
            "confirm": {},
            "skip": {},
            "cancel": {},
            "select": {"index": "int"},
            "refine_year": {"year": "int"},
            "refine_type": {"media_type": "str"},
            "refine_recent": {},
        }

    def execute(self, action: str, parameters: dict) -> str:
        # Disambiguation actions
        if action == "confirm":
            if not self._pending or self._is_expired():
                return "There's nothing to confirm right now."
            return self._confirm_pending()
        if action == "skip":
            if not self._pending or self._is_expired():
                return "There's nothing to skip right now."
            return self._next_pending()
        if action == "cancel":
            if not self._pending or self._is_expired():
                return "Nothing to cancel."
            return self._cancel_pending()
        if action == "select":
            return self._select(parameters.get("index", 1))

        # Refining actions
        if action == "refine_year":
            if not self._pending or self._is_expired():
                return "There's no active search to refine."
            year = parameters.get("year", 0)
            return self._apply_refinement(str(year))
        if action == "refine_type":
            if not self._pending or self._is_expired():
                return "There's no active search to refine."
            media_type = parameters.get("media_type", "")
            return self._apply_refinement(media_type)
        if action == "refine_recent":
            if not self._pending or self._is_expired():
                return "There's no active search to refine."
            return self._apply_refinement("newest")

        # List actions
        if action == "list":
            media_type = parameters.get("media_type", "any")
            if media_type == "movie":
                return self._list_movies()
            if media_type == "show":
                return self._list_shows()
            # List both
            parts = []
            movies_resp = self._list_movies() if self._radarr else None
            shows_resp = self._list_shows() if self._sonarr else None
            if movies_resp:
                parts.append(movies_resp)
            if shows_resp:
                parts.append(shows_resp)
            return " ".join(parts) if parts else "Media tracking isn't configured."

        # Check action
        if action == "check":
            return self._check_title(parameters.get("title", ""))

        # Track action
        if action == "track":
            title = parameters.get("title", "")
            media_type = parameters.get("media_type", "any")
            if media_type == "movie":
                return self._track_movie(title)
            if media_type == "show":
                return self._track_show(title)
            return self._track_generic(title)

        return self._status()

    def _select(self, index: int) -> str:
        """Jump to a specific result by 1-based index."""
        if not self._pending or self._is_expired():
            return "There's no active search to select from."
        results = self._pending["results"]
        # Convert 1-based to 0-based
        idx = index - 1
        if idx < 0 or idx >= len(results):
            return f"Please pick a number between 1 and {len(results)}."
        self._pending["index"] = idx
        self._pending["phase"] = "confirming"
        self._pending["timestamp"] = time.time()
        result = results[idx]
        if self._is_result_tracked(result):
            self._pending = None
            return f"You're already tracking {result['title']} from {result['year']}."
        return self._describe_current()

    def get_llm_context(self) -> str | None:
        if not self._pending or self._is_expired():
            return None
        results = self._pending["results"]
        index = self._pending["index"]
        phase = self._pending.get("phase", "confirming")
        search_term = self._pending.get("search_term", "")

        lines = [f'Media disambiguation active for "{search_term}".']
        if phase == "confirming":
            lines.append(
                f"Showing result {index + 1} of {len(results)}:"
            )
        else:
            lines.append(f"{len(results)} results in refining phase:")

        for i, r in enumerate(results):
            marker = " [CURRENT]" if i == index and phase == "confirming" else ""
            tracked = " [TRACKED]" if self._is_result_tracked(r) else ""
            lines.append(
                f"{i + 1}. {r['title']} ({r['year']}) - {r['media_type']}{tracked}{marker}"
            )

        if phase == "confirming":
            lines.append("User can: confirm, skip, cancel, or say which one they want.")
        else:
            lines.append("User can: filter by year, type, recency, or cancel.")

        return "\n".join(lines)

    def matches(self, text: str) -> bool:
        # Fast path: active disambiguation captures yes/no/next/cancel/refinements
        if self._pending and not self._is_expired():
            phase = self._pending.get("phase", "confirming")
            if phase == "confirming":
                if _YES.search(text) or _NO_NEXT.search(text) or _CANCEL.search(text):
                    return True
            elif phase == "refining":
                if _REFINE_ANY.search(text) or _CANCEL.search(text) or _YES.search(text):
                    return True
                # Also match new commands so handle() can intercept them
                for pat in _NEW_COMMAND_PATTERNS:
                    if pat.search(text):
                        return True

        return bool(_ANY_MEDIA.search(text))

    def handle(self, text: str) -> str:
        # Disambiguation flow takes priority
        if self._pending and not self._is_expired():
            phase = self._pending.get("phase", "confirming")

            if phase == "confirming":
                if _YES.search(text):
                    return self._confirm_pending()
                if _NO_NEXT.search(text):
                    return self._next_pending()
                if _CANCEL.search(text):
                    return self._cancel_pending()
            elif phase == "refining":
                if _CANCEL.search(text):
                    return self._cancel_pending()
                # Check for new commands — clear pending and fall through
                for pat in _NEW_COMMAND_PATTERNS:
                    if pat.search(text):
                        self._pending = None
                        break
                else:
                    # Not a new command — handle as refinement
                    if _YES.search(text):
                        # "yes" in refining = switch to confirming
                        self._pending["phase"] = "confirming"
                        self._pending["index"] = 0
                        self._pending["timestamp"] = time.time()
                        return self._describe_current_with_skip()
                    return self._apply_refinement(text)

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
        self._pending = None
        if not self._radarr:
            return "Movie tracking isn't configured."
        movies = self._radarr.get_movies()
        if not movies:
            return "You don't have any movies being tracked."
        titles = [f"{m['title']} ({m['year']})" for m in movies]
        return self._format_title_list(titles, "movie", "movies")

    def _list_shows(self) -> str:
        self._pending = None
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
        self._pending = None
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
        self._pending = None
        title = _clean_title(title)
        if not self._radarr:
            return "Movie tracking isn't configured. Set up Radarr to enable it."
        results = self._radarr.search_movie(title)
        if not results:
            return f"I couldn't find any movies matching {title}."
        for r in results:
            r["media_type"] = "movie"
        return self._start_disambiguation(results, search_term=title)

    def _track_show(self, title: str) -> str:
        self._pending = None
        title = _clean_title(title)
        if not self._sonarr:
            return "TV show tracking isn't configured. Set up Sonarr to enable it."
        results = self._sonarr.search_series(title)
        if not results:
            return f"I couldn't find any shows matching {title}."
        for r in results:
            r["media_type"] = "show"
        return self._start_disambiguation(results, search_term=title)

    def _track_generic(self, title: str) -> str:
        self._pending = None
        title = _clean_title(title)
        all_results = []
        if self._radarr:
            movies = self._radarr.search_movie(title)
            for r in movies:
                r["media_type"] = "movie"
            all_results.extend(movies)
        if self._sonarr:
            shows = self._sonarr.search_series(title)
            for r in shows:
                r["media_type"] = "show"
            all_results.extend(shows)
        if not self._radarr and not self._sonarr:
            return "Media tracking isn't configured."
        if not all_results:
            return f"I couldn't find anything matching {title}."
        return self._start_disambiguation(all_results, search_term=title)

    # -- Disambiguation --

    def _start_disambiguation(
        self, results: list[dict], search_term: str = ""
    ) -> str:
        """Begin disambiguation flow with tagged search results."""
        # Sort by title relevance (desc), then year (desc) for ties
        results.sort(
            key=lambda r: (_title_relevance(r["title"], search_term), r["year"]),
            reverse=True,
        )

        top_score = (
            _title_relevance(results[0]["title"], search_term) if results else 0.0
        )

        if len(results) >= 4 and top_score < 0.8:
            # Many results with no strong match — enter refining phase
            self._pending = {
                "results": results,
                "index": 0,
                "phase": "refining",
                "search_term": search_term,
                "timestamp": time.time(),
            }
            return self._describe_refining_summary()

        # Few results or strong match — check if first is already tracked
        first = results[0]
        if self._is_result_tracked(first):
            if len(results) == 1:
                return (
                    f"You're already tracking {first['title']} from {first['year']}."
                )
            # Skip tracked results at the front
            for i, r in enumerate(results):
                if not self._is_result_tracked(r):
                    self._pending = {
                        "results": results,
                        "index": i,
                        "phase": "confirming",
                        "search_term": search_term,
                        "timestamp": time.time(),
                    }
                    already = f"You're already tracking {first['title']} from {first['year']}."
                    return already + " " + self._describe_current()
            # All tracked
            return (
                f"You're already tracking {first['title']} from {first['year']}."
            )

        self._pending = {
            "results": results,
            "index": 0,
            "phase": "confirming",
            "search_term": search_term,
            "timestamp": time.time(),
        }
        return self._describe_current()

    def _is_result_tracked(self, result: dict) -> bool:
        """Check if a single result is already tracked."""
        media_type = result["media_type"]
        if media_type == "movie" and self._radarr:
            return self._radarr.is_movie_tracked(result["tmdbId"])
        if media_type == "show" and self._sonarr:
            return self._sonarr.is_series_tracked(result["tvdbId"])
        return False

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

    def _describe_current_with_skip(self) -> str:
        """Describe current candidate, auto-skipping any that are tracked."""
        while self._pending["index"] < len(self._pending["results"]):
            result = self._pending["results"][self._pending["index"]]
            if not self._is_result_tracked(result):
                return self._describe_current()
            self._pending["index"] += 1
        self._pending = None
        return "All of those are already tracked."

    def _confirm_pending(self) -> str:
        """User confirmed the current candidate — add it."""
        result = self._pending["results"][self._pending["index"]]
        media_type = result["media_type"]
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

        # Check if next result is already tracked — auto-advance
        result = self._pending["results"][self._pending["index"]]
        if self._is_result_tracked(result):
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

    # -- Refining phase --

    def _describe_refining_summary(self) -> str:
        """Generate a summary prompt for the refining phase."""
        results = self._pending["results"]
        total = len(results)
        movies = [r for r in results if r["media_type"] == "movie"]
        shows = [r for r in results if r["media_type"] == "show"]
        years = sorted({r["year"] for r in results})

        parts = []
        if movies and shows:
            parts.append(f"{len(movies)} movie{'s' if len(movies) != 1 else ''}")
            parts.append(f"{len(shows)} show{'s' if len(shows) != 1 else ''}")
            type_desc = " and ".join(parts)
            summary = f"I found {total} results — {type_desc}"
        elif movies:
            summary = f"I found {total} movies"
        else:
            summary = f"I found {total} shows"

        if len(years) >= 2:
            summary += f", from {years[0]} to {years[-1]}"
        summary += "."

        hints = []
        if len(years) >= 2:
            hints.append("the year")
        if movies and shows:
            hints.append("whether it's a movie or a show")
        if not hints:
            hints.append("the year or say 'the newest one'")

        summary += " Can you tell me " + ", or ".join(hints) + "?"
        return summary

    def _apply_refinement(self, text: str) -> str:
        """Parse refinement input and filter results."""
        results = self._pending["results"]
        filtered = list(results)

        # Year filter
        m = _REFINE_YEAR.search(text)
        if m:
            year = int(m.group(1))
            filtered = [r for r in filtered if r["year"] == year]

        # Type filter
        if _REFINE_MOVIE.search(text):
            filtered = [r for r in filtered if r["media_type"] == "movie"]
        elif _REFINE_SHOW.search(text):
            filtered = [r for r in filtered if r["media_type"] == "show"]

        # Recency filter
        if _REFINE_RECENT.search(text):
            filtered.sort(key=lambda r: r["year"], reverse=True)
            filtered = filtered[:3]

        if not filtered:
            self._pending = None
            return "None of my results match that."

        # Re-sort filtered results by relevance
        search_term = self._pending.get("search_term", "")
        filtered.sort(
            key=lambda r: (_title_relevance(r["title"], search_term), r["year"]),
            reverse=True,
        )

        # Update pending with filtered results
        self._pending["results"] = filtered
        self._pending["index"] = 0
        self._pending["timestamp"] = time.time()

        if len(filtered) == 1:
            # Single result — check tracked, then confirm
            if self._is_result_tracked(filtered[0]):
                self._pending = None
                return (
                    f"You're already tracking {filtered[0]['title']} "
                    f"from {filtered[0]['year']}."
                )
            self._pending["phase"] = "confirming"
            return self._describe_current()

        if len(filtered) <= 3:
            self._pending["phase"] = "confirming"
            return self._describe_current_with_skip()

        # Still too many
        return (
            f"Still {len(filtered)} results. "
            "Try being more specific — a year, or movie vs show."
        )

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
