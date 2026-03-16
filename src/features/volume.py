"""Volume control feature — adjust speaker volume via voice commands."""

import logging
import random
import re

from audio.base import BaseAudio
from features.base import BaseFeature

log = logging.getLogger("home-hud.features.volume")

# Does the text mention volume/loudness at all?
_ANY_VOLUME = re.compile(
    r"\b(volume|loud(?:er|ness)?|quiet(?:er)?|speak\s+up|turn\s+(?:it\s+)?(?:up|down)"
    r"|too\s+(?:loud|quiet)|(?:a\s+(?:bit|little|lot)\s+)?(?:louder|quieter))\b",
    re.IGNORECASE,
)

# Absolute set: "volume to 50%", "set volume to 80"
_SET_ABSOLUTE = re.compile(
    r"\bvolume\s+(?:to|at)\s+(\d+)\s*%?\b", re.IGNORECASE
)
_SET_ABSOLUTE2 = re.compile(
    r"\bset\s+(?:the\s+)?volume\s+(?:to|at)\s+(\d+)\s*%?\b", re.IGNORECASE
)

# Query: "what's the volume"
_QUERY = re.compile(
    r"\b(?:what(?:'s| is)\s+(?:the\s+)?volume|volume\s+level|how\s+loud)\b",
    re.IGNORECASE,
)

# "too loud" / "too quiet" — these invert the obvious keyword
_TOO_LOUD = re.compile(r"\btoo\s+loud\b", re.IGNORECASE)
_TOO_QUIET = re.compile(r"\btoo\s+quiet\b", re.IGNORECASE)

# Direction patterns
_UP = re.compile(
    r"\b(?:speak\s+up|(?:turn\s+(?:it\s+)?)?up|loud(?:er)?)\b",
    re.IGNORECASE,
)
_DOWN = re.compile(
    r"\b(?:quiet(?:er)?|(?:turn\s+(?:it\s+)?)?down|softer)\b",
    re.IGNORECASE,
)

# Magnitude modifiers
_SMALL = re.compile(r"\b(?:a\s+(?:bit|little|touch)|slightly)\b", re.IGNORECASE)
_LARGE = re.compile(r"\b(?:a\s+lot|way|much|way\s+(?:more|less))\b", re.IGNORECASE)

# Response pools
_RESPONSES_UP_SMALL = [
    "Turned it up a notch. Volume's at {level}%.",
    "Bumped it up a bit to {level}%.",
    "A little louder now, at {level}%.",
]
_RESPONSES_UP_LARGE = [
    "Cranked it up to {level}%!",
    "Turned it way up to {level}%!",
    "That's a big jump — now at {level}%.",
]
_RESPONSES_DOWN_SMALL = [
    "Brought it down a bit to {level}%.",
    "A touch quieter now, at {level}%.",
    "Turned it down a notch to {level}%.",
]
_RESPONSES_DOWN_LARGE = [
    "Turned it way down to {level}%.",
    "Dropped it down to {level}%.",
    "Much quieter now at {level}%.",
]
_RESPONSES_AT_MAX = [
    "Already at maximum volume.",
    "Can't go any louder — already at 100%.",
]
_RESPONSES_AT_MIN = [
    "Can't go any quieter — already at 0%.",
    "Volume is already at minimum.",
]
_RESPONSES_QUERY = [
    "Volume is at {level}%.",
    "Currently at {level}%.",
]
_RESPONSES_SET = [
    "Volume set to {level}%.",
    "Set it to {level}%.",
]


class VolumeFeature(BaseFeature):
    """Adjusts speaker volume via voice commands."""

    def __init__(self, config: dict, audio: BaseAudio):
        super().__init__(config)
        self._audio = audio
        self._step_small = config.get("volume_step_small", 10)
        self._step_medium = config.get("volume_step_medium", 20)
        self._step_large = config.get("volume_step_large", 30)

    @property
    def name(self) -> str:
        return "Volume"

    @property
    def short_description(self) -> str:
        return "Adjust speaker volume up, down, or to a specific level"

    @property
    def description(self) -> str:
        return (
            'Volume control: triggered by "volume", "louder", "quieter", '
            '"speak up", "turn it up/down", "too loud/quiet". '
            'Commands: "speak up a bit", "turn it down", "volume to 50%", '
            '"what\'s the volume".'
        )

    def matches(self, text: str) -> bool:
        return bool(_ANY_VOLUME.search(text))

    @property
    def action_schema(self) -> dict:
        return {
            "adjust_volume": {"direction": "str", "magnitude": "str"},
            "set_volume": {"level": "int"},
            "query": {},
        }

    def execute(self, action: str, parameters: dict) -> str:
        if action == "adjust_volume":
            direction = parameters.get("direction", "up")
            magnitude = parameters.get("magnitude", "medium")
            return self._adjust(direction, magnitude)
        if action == "set_volume":
            level = int(parameters.get("level", 50))
            return self._set_absolute(level)
        if action == "query":
            return self._query()
        return self._query()

    def handle(self, text: str) -> str:
        # Absolute set
        m = _SET_ABSOLUTE.search(text) or _SET_ABSOLUTE2.search(text)
        if m:
            return self._set_absolute(int(m.group(1)))

        # Query
        if _QUERY.search(text):
            return self._query()

        # "too loud" → down, "too quiet" → up (inverted keywords)
        if _TOO_LOUD.search(text):
            direction = "down"
        elif _TOO_QUIET.search(text):
            direction = "up"
        elif _DOWN.search(text):
            direction = "down"
        elif _UP.search(text):
            direction = "up"
        else:
            direction = "up"
        magnitude = self._detect_magnitude(text)
        return self._adjust(direction, magnitude)

    def _detect_magnitude(self, text: str) -> str:
        if _SMALL.search(text):
            return "small"
        if _LARGE.search(text):
            return "large"
        return "medium"

    def _get_step(self, magnitude: str) -> int:
        if magnitude == "small":
            return self._step_small
        if magnitude == "large":
            return self._step_large
        return self._step_medium

    def _adjust(self, direction: str, magnitude: str) -> str:
        old = self._audio.get_volume()
        step = self._get_step(magnitude)

        if direction == "up":
            if old >= 100:
                return random.choice(_RESPONSES_AT_MAX)
            new = self._audio.set_volume(old + step)
        else:
            if old <= 0:
                return random.choice(_RESPONSES_AT_MIN)
            new = self._audio.set_volume(old - step)

        delta = abs(new - old)
        if direction == "up":
            pool = _RESPONSES_UP_LARGE if delta >= 25 else _RESPONSES_UP_SMALL
        else:
            pool = _RESPONSES_DOWN_LARGE if delta >= 25 else _RESPONSES_DOWN_SMALL

        return random.choice(pool).format(level=new)

    def _set_absolute(self, level: int) -> str:
        new = self._audio.set_volume(level)
        return random.choice(_RESPONSES_SET).format(level=new)

    def _query(self) -> str:
        level = self._audio.get_volume()
        return random.choice(_RESPONSES_QUERY).format(level=level)
