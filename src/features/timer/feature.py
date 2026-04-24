"""TimerFeature — start, cancel, list, extend short countdown timers."""

from __future__ import annotations

import json
import logging
import re
import threading
import time
import uuid
from pathlib import Path
from typing import Callable, Optional

from features.base import BaseFeature
from utils.scheduler import Scheduler

log = logging.getLogger("home-hud.features.timer")

# Fast match: any mention of "timer" or "countdown" is this feature's domain.
# Narrower than ReminderFeature's _ANY_REMINDER to avoid cross-matching "remind".
_ANY_TIMER = re.compile(r"\b(?:timer|countdown)\b", re.IGNORECASE)

_UNIT_SEC = {
    "second": 1, "seconds": 1, "sec": 1, "secs": 1,
    "minute": 60, "minutes": 60, "min": 60, "mins": 60,
    "hour": 3600, "hours": 3600, "hr": 3600, "hrs": 3600,
}

_WORD_TO_NUM = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
    "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
    "nineteen": 19, "twenty": 20, "thirty": 30, "forty": 40,
    "fifty": 50, "sixty": 60, "ninety": 90,
}

# "5 minutes", "5min", "five minutes", "two and a half hours" (best effort)
_DURATION_RE = re.compile(
    r"(\d+(?:\.\d+)?|" + "|".join(_WORD_TO_NUM.keys()) + r")"
    r"\s*(seconds?|secs?|minutes?|mins?|hours?|hrs?)",
    re.IGNORECASE,
)

# "set a timer for X [called|named|for] LABEL"
_START_WITH_LABEL = re.compile(
    r"(?:set|start|make|create)\s+(?:a\s+|an\s+)?timer\s+"
    r"(?:for|of)\s+(.+?)(?:\s+(?:called|named|for)\s+(.+))?$",
    re.IGNORECASE,
)


def parse_duration(text: str) -> Optional[int]:
    """Parse '5 minutes', 'two hours', '30 seconds' into seconds. Returns
    None if nothing recognizable is found.
    """
    if not text:
        return None
    total = 0
    for m in _DURATION_RE.finditer(text):
        raw, unit = m.group(1).lower(), m.group(2).lower()
        if raw in _WORD_TO_NUM:
            amount = _WORD_TO_NUM[raw]
        else:
            try:
                amount = float(raw)
            except ValueError:
                continue
        unit_sec = _UNIT_SEC.get(unit.rstrip("s"), None)
        if unit_sec is None:
            unit_sec = _UNIT_SEC.get(unit, None)
        if unit_sec is None:
            continue
        total += int(amount * unit_sec)
    return total or None


def _format_duration(seconds: int) -> str:
    if seconds < 60:
        s = "second" if seconds == 1 else "seconds"
        return f"{seconds} {s}"
    if seconds < 3600:
        minutes, sec = divmod(seconds, 60)
        base = f"{minutes} {'minute' if minutes == 1 else 'minutes'}"
        if sec:
            base += f" and {sec} seconds"
        return base
    hours, rem = divmod(seconds, 3600)
    minutes = rem // 60
    base = f"{hours} {'hour' if hours == 1 else 'hours'}"
    if minutes:
        base += f" and {minutes} minutes"
    return base


class TimerFeature(BaseFeature):
    """Kitchen/exercise countdown timers with audible alarm on fire."""

    def __init__(
        self,
        config: dict,
        scheduler: Optional[Scheduler] = None,
        on_fire: Optional[Callable[[dict], None]] = None,
    ):
        super().__init__(config)
        self._path = Path(config.get("timer_file", "data/timers.json"))
        self._lock = threading.Lock()
        self._on_fire = on_fire
        self._scheduler_ids: dict[str, str] = {}  # timer_id -> scheduler entry id
        self._scheduler = scheduler if scheduler is not None else Scheduler()
        self._owns_scheduler = scheduler is None
        self._reschedule_all()

    @property
    def name(self) -> str:
        return "Timer"

    @property
    def short_description(self) -> str:
        return "Short-duration countdown timers with alarm"

    @property
    def description(self) -> str:
        return (
            'Timers: triggered by "timer" or "countdown". '
            'Commands: "set a timer for 5 minutes", "start a 10 minute timer", '
            '"cancel the timer", "how much time is left".'
        )

    @property
    def action_schema(self) -> dict:
        return {
            "start": {"duration": "str", "label": "str"},
            "cancel": {"label": "str"},
            "list": {},
            "extend": {"duration": "str", "label": "str"},
        }

    def execute(self, action: str, parameters: dict) -> str:
        if action == "start":
            seconds = parse_duration(parameters.get("duration", ""))
            if seconds is None or seconds <= 0:
                return "I didn't catch the duration. Try 'set a timer for 5 minutes'."
            return self._start(seconds, parameters.get("label"))
        if action == "cancel":
            return self._cancel(parameters.get("label"))
        if action == "list":
            return self._list()
        if action == "extend":
            seconds = parse_duration(parameters.get("duration", ""))
            if seconds is None or seconds <= 0:
                return "I didn't catch the duration."
            return self._extend(seconds, parameters.get("label"))
        return self._list()

    def matches(self, text: str) -> bool:
        return bool(_ANY_TIMER.search(text))

    def handle(self, text: str) -> str:
        # Regex fallback — the LLM path covers most phrasings; this catches
        # the happy case "set a timer for 5 minutes".
        m = _START_WITH_LABEL.search(text)
        if m:
            dur_text, label = m.group(1), m.group(2)
            seconds = parse_duration(dur_text)
            if seconds:
                return self._start(seconds, label)

        seconds = parse_duration(text)
        start_re = r"(?:set|start|make|create|begin).*\btimer\b"
        if seconds and re.search(start_re, text, re.IGNORECASE):
            return self._start(seconds, None)

        if re.search(r"\bcancel\b", text, re.IGNORECASE):
            return self._cancel(None)

        return self._list()

    # -- Actions --

    def _start(self, seconds: int, label: Optional[str]) -> str:
        now = time.time()
        timer_id = uuid.uuid4().hex
        item = {
            "id": timer_id,
            "label": (label or "").strip() or None,
            "duration_sec": seconds,
            "started_at": int(now),
            "due_at": int(now + seconds),
        }
        items = self._load()
        items.append(item)
        self._save(items)
        self._schedule(item)
        spoken = f"Timer set for {_format_duration(seconds)}"
        if item["label"]:
            spoken += f" ({item['label']})"
        return spoken + "."

    def _cancel(self, label: Optional[str]) -> str:
        items = self._load()
        if not items:
            return "You don't have any timers running."

        if label:
            label_lower = label.strip().lower()
            matches = [
                i for i in items
                if i.get("label") and i["label"].lower() == label_lower
            ]
            if not matches:
                return f"I don't see a timer called {label}."
            for item in matches:
                self._unschedule(item)
            remaining = [i for i in items if i not in matches]
            self._save(remaining)
            return f"Cancelled the {label} timer."

        # No label: cancel all.
        for item in items:
            self._unschedule(item)
        self._save([])
        if len(items) == 1:
            return "Cancelled the timer."
        return f"Cancelled all {len(items)} timers."

    def _list(self) -> str:
        items = self._load()
        if not items:
            return "You don't have any timers running."
        now = time.time()
        parts = []
        for item in items:
            remaining = max(0, int(item["due_at"] - now))
            desc = _format_duration(remaining) + " left"
            if item.get("label"):
                desc = f"{item['label']}: {desc}"
            parts.append(desc)
        if len(parts) == 1:
            return f"One timer: {parts[0]}."
        return f"{len(parts)} timers. " + ". ".join(parts) + "."

    def _extend(self, seconds: int, label: Optional[str]) -> str:
        items = self._load()
        if not items:
            return "You don't have any timers running."

        target = None
        if label:
            lower = label.strip().lower()
            for item in items:
                if item.get("label") and item["label"].lower() == lower:
                    target = item
                    break
        elif len(items) == 1:
            target = items[0]

        if target is None:
            return "Which timer should I extend?"

        # Re-schedule at the new time.
        self._unschedule(target)
        target["due_at"] = int(target["due_at"] + seconds)
        target["duration_sec"] = target.get("duration_sec", 0) + seconds
        self._save(items)
        self._schedule(target)
        lbl = f" ({target['label']})" if target.get("label") else ""
        return f"Added {_format_duration(seconds)} to the timer{lbl}."

    def get_timers(self) -> list[dict]:
        """Read-only snapshot — used by display / web."""
        return self._load()

    # -- Scheduler integration --

    def _reschedule_all(self) -> None:
        if self._on_fire is None:
            return
        for item in self._load():
            self._schedule(item)

    def _schedule(self, item: dict) -> None:
        if self._on_fire is None:
            return
        entry_id = self._scheduler.add(
            float(item["due_at"]),
            {"timer_id": item["id"]},
            self._on_scheduler_fire,
        )
        self._scheduler_ids[item["id"]] = entry_id

    def _unschedule(self, item: dict) -> None:
        entry_id = self._scheduler_ids.pop(item.get("id"), None)
        if entry_id is not None:
            self._scheduler.cancel(entry_id)

    def _on_scheduler_fire(self, payload: dict) -> None:
        timer_id = payload.get("timer_id")
        if timer_id is None:
            return
        self._scheduler_ids.pop(timer_id, None)

        items = self._load()
        fired = None
        remaining = []
        for item in items:
            if item.get("id") == timer_id:
                fired = item
            else:
                remaining.append(item)
        if fired is None:
            return
        self._save(remaining)

        log.info("Timer due: %s", fired.get("label") or "(unlabeled)")
        if self._on_fire is not None:
            try:
                self._on_fire(fired)
            except Exception:
                log.exception("Error firing timer callback")

    # -- Persistence --

    def _load(self) -> list[dict]:
        with self._lock:
            if not self._path.exists():
                return []
            try:
                data = json.loads(self._path.read_text())
                return data if isinstance(data, list) else []
            except (json.JSONDecodeError, OSError):
                log.warning("Timer file unreadable, resetting")
                return []

    def _save(self, items: list[dict]) -> None:
        with self._lock:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(json.dumps(items, indent=2) + "\n")

    def close(self) -> None:
        if self._owns_scheduler:
            self._scheduler.close()
