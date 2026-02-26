"""Repeat feature — replays the last spoken response on request."""

import logging
import re
import threading

from features.base import BaseFeature

log = logging.getLogger("home-hud.features.repeat")

_TRIGGER = re.compile(
    r"\b("
    r"what did you(?: just)? say"
    r"|what was that"
    r"|repeat that"
    r"|say (?:that|it) again"
    r"|come again"
    r"|can you repeat that"
    r"|what did you tell me"
    r"|i didn'?t (?:catch|hear) that"
    r"|pardon"
    r")\b",
    re.IGNORECASE,
)


class RepeatFeature(BaseFeature):
    """Stores the last query/response pair and replays it on request.

    Thread-safe — the voice pipeline runs in a daemon thread while record()
    and handle() may be called from different contexts.
    """

    def __init__(self, config: dict):
        super().__init__(config)
        self._lock = threading.Lock()
        self._last_query: str | None = None
        self._last_response: str | None = None

    @property
    def name(self) -> str:
        return "Repeat"

    @property
    def short_description(self) -> str:
        return "Repeat the last thing I said"

    @property
    def description(self) -> str:
        return (
            'Repeat last response: triggered by "what did you say", "repeat that", '
            '"say that again", "I didn\'t catch that", "pardon".'
        )

    def matches(self, text: str) -> bool:
        return bool(_TRIGGER.search(text))

    def handle(self, text: str) -> str:
        with self._lock:
            if self._last_response is None:
                return "I haven't said anything yet this session."
            if self._last_query and self._last_query.startswith("("):
                # Synthetic query (e.g. reminder)
                return f"A reminder fired. I said: {self._last_response}."
            return (
                f"I heard: {self._last_query}. "
                f"And I responded: {self._last_response}."
            )

    def record(self, query: str, response: str) -> None:
        """Store the last query/response pair.

        Skips recording if the query itself is a repeat trigger, so asking
        "what did you say?" twice returns the same original answer.
        """
        if _TRIGGER.search(query):
            return
        with self._lock:
            self._last_query = query
            self._last_response = response
