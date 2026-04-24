"""Media discovery feature — voice-driven recommendations from taste profile."""

from __future__ import annotations

import logging
import re
import time

from features.base import BaseFeature

log = logging.getLogger("home-hud.features.discovery")

# -- Command patterns --
_RECOMMEND = re.compile(
    r"\b(?:recommend|suggestion|what\s+should\s+I\s+watch"
    r"|what.*(?:to|should)\s+watch"
    r"|anything\s+(?:good|new)\s+to\s+watch"
    r"|discover(?:y)?|find\s+(?:me\s+)?something)"
    r"\b",
    re.IGNORECASE,
)
_RECOMMEND_MOVIE = re.compile(
    r"\b(?:recommend\s+(?:a\s+)?movie|movie\s+recommendation"
    r"|suggest\s+(?:a\s+)?movie)\b",
    re.IGNORECASE,
)
_RECOMMEND_SHOW = re.compile(
    r"\b(?:recommend\s+(?:a\s+)?(?:show|series|tv)"
    r"|(?:show|series|tv)\s+recommendation"
    r"|suggest\s+(?:a\s+)?(?:show|series))\b",
    re.IGNORECASE,
)
_TASTE_PROFILE = re.compile(
    r"\b(?:taste\s+profile|my\s+taste|what.*(?:like|prefer|enjoy))\b",
    re.IGNORECASE,
)

# -- Follow-up patterns --
_ADD = re.compile(
    r"\b(?:add\s+(?:that|it)|track\s+(?:that|it)|yes|yeah|do\s+it|grab\s+it)\b",
    re.IGNORECASE,
)
_NEXT = re.compile(
    r"\b(?:next|another|another\s+one|skip|not\s+interested|pass)\b",
    re.IGNORECASE,
)
_DISMISS = re.compile(
    r"\b(?:not\s+interested|dismiss|no(?:\s+thanks)?|nah|nope)\b",
    re.IGNORECASE,
)
_CANCEL = re.compile(
    r"\b(?:cancel|never\s*mind|stop|done|forget\s*it|quit)\b",
    re.IGNORECASE,
)

_FOLLOW_UP_TTL = 60  # seconds


class DiscoveryFeature(BaseFeature):
    """Voice-driven media discovery and recommendation presentation.

    Presents cached recommendations one at a time. Users can add (track),
    dismiss, or skip. The feature stays active for follow-up commands
    while presenting recommendations.
    """

    def __init__(
        self,
        config: dict,
        discovery_storage=None,
        sonarr=None,
        radarr=None,
    ):
        super().__init__(config)
        self._storage = discovery_storage
        self._sonarr = sonarr
        self._radarr = radarr

        # Stateful presentation
        self._current_rec: dict | None = None
        self._rec_index: int = 0
        self._active_recs: list[dict] = []
        self._last_interaction: float = 0

    @property
    def name(self) -> str:
        return "Discovery"

    @property
    def short_description(self) -> str:
        return "Get personalized movie and TV show recommendations"

    @property
    def description(self) -> str:
        return (
            'Discovery: triggered by "recommend", "suggestion", "what should I watch", '
            '"anything good to watch", "taste profile". Commands: "recommend a movie", '
            '"what should I watch", "add that", "next", "not interested", '
            '"what\'s my taste profile".'
        )

    @property
    def expects_follow_up(self) -> bool:
        return (
            self._current_rec is not None
            and (time.time() - self._last_interaction) < _FOLLOW_UP_TTL
        )

    @property
    def action_schema(self) -> dict:
        return {
            "recommend": {"media_type": "str"},
            "add_recommendation": {},
            "dismiss_recommendation": {},
            "next_recommendation": {},
            "taste_profile": {},
        }

    def matches(self, text: str) -> bool:
        if not self._storage:
            return False
        # Active follow-up state captures add/next/dismiss/cancel
        if self.expects_follow_up:
            if (
                _ADD.search(text) or _NEXT.search(text)
                or _DISMISS.search(text) or _CANCEL.search(text)
            ):
                return True
        return bool(
            _RECOMMEND.search(text)
            or _RECOMMEND_MOVIE.search(text)
            or _RECOMMEND_SHOW.search(text)
            or _TASTE_PROFILE.search(text)
        )

    def handle(self, text: str) -> str:
        if not self._storage:
            return "Discovery isn't configured."

        self._last_interaction = time.time()

        # Follow-up actions when presenting a recommendation
        if self._current_rec:
            if _CANCEL.search(text):
                return self._cancel()
            if _ADD.search(text):
                return self._add_current()
            if _DISMISS.search(text):
                return self._dismiss_and_next()
            if _NEXT.search(text):
                return self._next_recommendation()

        # New commands
        if _TASTE_PROFILE.search(text):
            return self._show_taste_profile()

        # Determine media type filter
        media_type = None
        if _RECOMMEND_MOVIE.search(text):
            media_type = "movie"
        elif _RECOMMEND_SHOW.search(text):
            media_type = "series"

        return self._present_recommendation(media_type=media_type)

    def execute(self, action: str, parameters: dict) -> str:
        if not self._storage:
            return "Discovery isn't configured."

        self._last_interaction = time.time()

        if action == "recommend":
            media_type = parameters.get("media_type")
            if media_type == "show":
                media_type = "series"
            return self._present_recommendation(media_type=media_type)
        if action == "add_recommendation":
            return self._add_current()
        if action == "dismiss_recommendation":
            return self._dismiss_and_next()
        if action == "next_recommendation":
            return self._next_recommendation()
        if action == "taste_profile":
            return self._show_taste_profile()

        return self._present_recommendation()

    def get_llm_context(self) -> str | None:
        if not self.expects_follow_up or not self._current_rec:
            return None
        rec = self._current_rec
        return (
            f'Discovery active: presenting "{rec["title"]}" '
            f'({rec.get("year", "?")}), {rec["media_type"]}. '
            f"User can: add it, skip, dismiss, or hear another."
        )

    def _present_recommendation(self, media_type: str | None = None) -> str:
        """Load active recommendations and present the first matching one."""
        self._active_recs = self._storage.get_active_recommendations()

        if media_type:
            self._active_recs = [
                r for r in self._active_recs if r["media_type"] == media_type
            ]

        if not self._active_recs:
            type_label = f" {media_type}" if media_type else ""
            return (
                f"I don't have any{type_label} recommendations right now. "
                "Try again after the next discovery cycle."
            )

        self._rec_index = 0
        self._current_rec = self._active_recs[0]
        self._set_last_entity(
            "discovery", {"name": self._current_rec.get("title", "")}
        )
        return self._format_recommendation(self._current_rec)

    def _next_recommendation(self) -> str:
        """Advance to the next recommendation."""
        if not self._active_recs:
            self._current_rec = None
            return "No more recommendations. Check back later."

        self._rec_index += 1
        if self._rec_index >= len(self._active_recs):
            self._current_rec = None
            return "That's all the recommendations I have for now."

        self._current_rec = self._active_recs[self._rec_index]
        self._set_last_entity(
            "discovery", {"name": self._current_rec.get("title", "")}
        )
        return self._format_recommendation(self._current_rec)

    def _add_current(self) -> str:
        """Add the current recommendation to the media library."""
        if not self._current_rec:
            return "There's no recommendation to add right now."

        rec = self._current_rec
        title = rec["title"]
        media_type = rec["media_type"]

        # Try to add via Radarr/Sonarr
        added = False
        if media_type == "movie" and self._radarr:
            results = self._radarr.search_movie(title)
            if results:
                result = results[0]
                if not self._radarr.is_movie_tracked(result["tmdbId"]):
                    self._radarr.add_movie(result["tmdbId"], result["title"])
                    added = True
                else:
                    self._storage.track_recommendation(rec["id"])
                    self._current_rec = None
                    return f"{title} is already in your library."
        elif media_type == "series" and self._sonarr:
            results = self._sonarr.search_series(title)
            if results:
                result = results[0]
                if not self._sonarr.is_series_tracked(result["tvdbId"]):
                    self._sonarr.add_series(result["tvdbId"], result["title"])
                    added = True
                else:
                    self._storage.track_recommendation(rec["id"])
                    self._current_rec = None
                    return f"{title} is already in your library."

        if added:
            self._storage.track_recommendation(rec["id"])
            self._current_rec = None
            return f"Added {title} to your library. Want another recommendation?"

        # No matching client or search failed
        self._storage.track_recommendation(rec["id"])
        self._current_rec = None
        client_name = "Radarr" if media_type == "movie" else "Sonarr"
        return f"Couldn't find {title} in {client_name}. Marked as tracked."

    def _dismiss_and_next(self) -> str:
        """Dismiss current recommendation and show the next one."""
        if self._current_rec:
            self._storage.dismiss_recommendation(self._current_rec["id"])
            # Remove from active list
            self._active_recs = [
                r for r in self._active_recs if r["id"] != self._current_rec["id"]
            ]
            # Adjust index since we removed an item
            if self._rec_index >= len(self._active_recs):
                self._rec_index = max(0, len(self._active_recs) - 1)
        return self._next_recommendation()

    def _cancel(self) -> str:
        """Cancel the recommendation presentation."""
        self._current_rec = None
        self._active_recs = []
        return "Okay, no more recommendations."

    def _show_taste_profile(self) -> str:
        """Read the taste profile summary."""
        summary = self._storage.get_taste_summary()
        if "No taste profile" in summary:
            return (
                "I haven't built a taste profile yet. "
                "It'll be ready after the first library sync."
            )

        # Parse into a more spoken-friendly format
        parts = summary.split("; ")
        spoken = []
        for part in parts[:3]:  # Top 3 dimensions for voice
            spoken.append(part.split(":")[0].strip() + " favorites include " +
                         ", ".join(
                             v.split("(")[0].strip()
                             for v in part.split(":")[1].strip().split(", ")[:3]
                         ))
        return "Your taste profile: " + ". ".join(spoken) + "."

    def _format_recommendation(self, rec: dict) -> str:
        """Format a recommendation for TTS."""
        parts = [f"I'd recommend {rec['title']}"]
        if rec.get("year"):
            parts[0] += f" from {rec['year']}"
        parts[0] += f", a {rec['media_type']}."
        if rec.get("reason"):
            parts.append(rec["reason"] + ".")
        parts.append("Want to add it, or hear another?")
        return " ".join(parts)

    def close(self) -> None:
        pass
