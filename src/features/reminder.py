"""Reminder feature — set, list, cancel, and fire timed reminders via voice."""

from __future__ import annotations

import json
import logging
import re
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from features.base import BaseFeature

log = logging.getLogger("home-hud.features.reminder")

# Fast check: does the text mention remind/reminder at all?
_ANY_REMINDER = re.compile(r"\b(?:remind|reminders?)\b", re.IGNORECASE)

# --- Time components ---

_TIME = r"(\d{1,2})(?::(\d{2}))?\s*(am|pm|a\.m\.|p\.m\.)?"
_RELATIVE = r"(?:in\s+)?(\d+|an?|half(?:\s+an?)?)\s+(seconds?|minutes?|hours?|days?)"

# --- Action patterns (checked in order) ---

# 1. Prefix: "at 3pm [tomorrow] remind me to TASK"
_PREFIX_AT = re.compile(
    rf"\bat\s+{_TIME}\s+(?:(tomorrow)\s+)?remind\s+me\s+to\s+(.+)",
    re.IGNORECASE,
)
# 2. Prefix: "tomorrow at 3pm remind me to TASK"
_PREFIX_TOMORROW_AT = re.compile(
    rf"\btomorrow\s+at\s+{_TIME}\s+remind\s+me\s+to\s+(.+)",
    re.IGNORECASE,
)
# 3. Relative time-first: "remind me in 10 minutes to TASK"
_SET_RELATIVE_FIRST = re.compile(
    r"\bremind\s+me\s+in\s+(\d+|an?|half(?:\s+an?)?)\s+(seconds?|minutes?|hours?|days?)\s+to\s+(.+)",
    re.IGNORECASE,
)
# 4. Set at-time (task first): "remind me to TASK at TIME [tomorrow]"
_SET_AT = re.compile(
    rf"\bremind\s+me\s+to\s+(.+?)\s+at\s+{_TIME}(?:\s+(tomorrow))?\s*$",
    re.IGNORECASE,
)
# 5. Set relative (task first): "remind me to TASK in N UNITS"
_SET_RELATIVE = re.compile(
    r"\bremind\s+me\s+to\s+(.+?)\s+in\s+(\d+|an?|half(?:\s+an?)?)\s+(seconds?|minutes?|hours?|days?)\s*$",
    re.IGNORECASE,
)
# 6. Set tomorrow (task first): "remind me to TASK tomorrow"
_SET_TOMORROW = re.compile(
    r"\bremind\s+me\s+to\s+(.+?)\s+tomorrow\s*$",
    re.IGNORECASE,
)
# 7. Cancel specific: "cancel [my] reminder to TASK"
_CANCEL = re.compile(
    r"\bcancel\s+(?:my\s+)?reminder\s+to\s+(.+)",
    re.IGNORECASE,
)
# 8. Clear all: "clear/cancel/delete all [my] reminders"
_CLEAR = re.compile(
    r"\b(?:clear|cancel|delete)\s+all\s+(?:my\s+)?reminders\b",
    re.IGNORECASE,
)
# 3b. Reverse at-time: "remind me at TIME [tomorrow] to TASK"
_SET_AT_REVERSE = re.compile(
    rf"\bremind\s+me\s+at\s+{_TIME}(?:\s+(tomorrow))?\s+to\s+(.+)",
    re.IGNORECASE,
)
# 9. List: "what are/show/list [my] reminders"
_LIST = re.compile(
    r"\b(?:what\s+are|show|list)\s+(?:my\s+)?reminders\b",
    re.IGNORECASE,
)

# --- Input normalization for voice phrasing ---

_TRAILING_PUNCT = re.compile(r"[.?!]+$")
_BROKEN_AMPM = re.compile(r"\b((?:a|p)\.m)$", re.IGNORECASE)
_CONVERSATIONAL_PREFIX = re.compile(
    r"^(?:can|could|would)\s+you\s+(?:please\s+)?|^please\s+",
    re.IGNORECASE,
)
_REMINDER_FOR_TOMORROW_AT = re.compile(
    r"(?:set|create)\s+a\s+reminder\s+for\s+tomorrow\s+at\s+(.+?)\s+to\s+(.+)",
    re.IGNORECASE,
)
_REMINDER_FOR_TOMORROW = re.compile(
    r"(?:set|create)\s+a\s+reminder\s+for\s+tomorrow\s+to\s+(.+)",
    re.IGNORECASE,
)
_REMINDER_TO = re.compile(
    r"(?:set|create)\s+a\s+reminder\s+to\s+",
    re.IGNORECASE,
)
_REMINDER_FOR = re.compile(
    r"(?:set|create)\s+a\s+reminder\s+for\s+",
    re.IGNORECASE,
)


def _normalize(text: str) -> str:
    """Clean voice input before pattern matching.

    Strips trailing punctuation, conversational prefixes, and rewrites
    "set/create a reminder" forms into canonical "remind me" phrasing.
    """
    # Strip trailing punctuation, then restore broken a.m./p.m.
    text = _TRAILING_PUNCT.sub("", text).strip()
    text = _BROKEN_AMPM.sub(r"\1.", text)

    # Strip conversational prefixes
    text = _CONVERSATIONAL_PREFIX.sub("", text).strip()

    # Rewrite "set/create a reminder for tomorrow at TIME to TASK"
    m = _REMINDER_FOR_TOMORROW_AT.search(text)
    if m:
        return f"tomorrow at {m.group(1)} remind me to {m.group(2)}"

    # Rewrite "set/create a reminder for tomorrow to TASK"
    m = _REMINDER_FOR_TOMORROW.search(text)
    if m:
        return f"remind me to {m.group(1)} tomorrow"

    # Rewrite "set/create a reminder to" → "remind me to"
    text = _REMINDER_TO.sub("remind me to ", text)

    # Rewrite "set/create a reminder for" → "remind me at"
    text = _REMINDER_FOR.sub("remind me at ", text)

    return text


class ReminderFeature(BaseFeature):
    """Manages timed reminders with background checking and TTS callbacks."""

    def __init__(self, config: dict, on_due=None):
        super().__init__(config)
        self._path = Path(config.get("reminder_file", "data/reminders.json"))
        self._lock = threading.Lock()
        self._on_due = on_due
        self._check_interval = config.get("reminder_check_interval", 15)
        self._stop_event = threading.Event()
        self._checker_thread = None

        if on_due is not None:
            self._checker_thread = threading.Thread(
                target=self._checker_loop, daemon=True
            )
            self._checker_thread.start()

    @property
    def name(self) -> str:
        return "Reminders"

    @property
    def short_description(self) -> str:
        return "Set, list, and cancel timed reminders"

    @property
    def description(self) -> str:
        return (
            'Reminders: triggered by "remind" or "reminder". '
            'Commands: "remind me to X in Y minutes", "remind me to X at 3pm", '
            '"what are my reminders", "cancel reminder to X", "clear all reminders".'
        )

    @property
    def action_schema(self) -> dict:
        return {
            "set": {"task": "str", "time": "str"},
            "list": {},
            "cancel": {"task": "str"},
            "clear": {},
        }

    def execute(self, action: str, parameters: dict) -> str:
        if action == "set":
            due = self._parse_time_expression(parameters.get("time", ""))
            if due is None:
                return (
                    "I didn't understand the time. "
                    "Try something like 'in 5 minutes' or 'at 3pm'."
                )
            return self._set(parameters["task"], due)
        if action == "list":
            return self._list()
        if action == "cancel":
            return self._cancel(parameters["task"])
        if action == "clear":
            return self._clear()
        return self._list()

    def _parse_time_expression(self, expr: str) -> datetime | None:
        """Parse a natural language time expression into a datetime.

        Supports relative ("in 5 minutes", "5 minutes") and absolute
        ("at 3pm", "3pm", "tomorrow", "tomorrow at 3pm") expressions.
        """
        if not expr:
            return None

        expr = expr.strip().lower()

        # "tomorrow at TIME" or "tomorrow TIME"
        m = re.match(
            rf"(?:tomorrow\s+(?:at\s+)?){_TIME}", expr, re.IGNORECASE
        )
        if m:
            return self._parse_absolute(m.group(1), m.group(2), m.group(3), tomorrow=True)

        # "tomorrow" alone → 9am tomorrow
        if expr == "tomorrow":
            return (datetime.now() + timedelta(days=1)).replace(
                hour=9, minute=0, second=0, microsecond=0
            )

        # Relative: "in N units" or just "N units"
        m = re.match(
            r"(?:in\s+)?(\d+|an?|half(?:\s+an?)?)\s+(seconds?|minutes?|hours?|days?)\s*$",
            expr, re.IGNORECASE,
        )
        if m:
            delta = self._parse_relative(m.group(1), m.group(2))
            return datetime.now() + delta

        # Absolute: "at TIME" or just "TIME"
        m = re.match(rf"(?:at\s+)?{_TIME}\s*$", expr, re.IGNORECASE)
        if m:
            return self._parse_absolute(m.group(1), m.group(2), m.group(3))

        return None

    def matches(self, text: str) -> bool:
        return bool(_ANY_REMINDER.search(text))

    def handle(self, text: str) -> str:
        text = _normalize(text)

        # 1. Prefix: "tomorrow at TIME remind me to TASK"
        m = _PREFIX_TOMORROW_AT.search(text)
        if m:
            hour, minute, ampm, task = m.group(1), m.group(2), m.group(3), m.group(4)
            due = self._parse_absolute(hour, minute, ampm, tomorrow=True)
            return self._set(task.strip(), due)

        # 2. Prefix: "at TIME [tomorrow] remind me to TASK"
        m = _PREFIX_AT.search(text)
        if m:
            hour, minute, ampm, tomorrow, task = (
                m.group(1), m.group(2), m.group(3), m.group(4), m.group(5),
            )
            due = self._parse_absolute(hour, minute, ampm, tomorrow is not None)
            return self._set(task.strip(), due)

        # 3. Relative time-first: "remind me in 10 minutes to TASK"
        m = _SET_RELATIVE_FIRST.search(text)
        if m:
            delta = self._parse_relative(m.group(1), m.group(2))
            return self._set(m.group(3).strip(), datetime.now() + delta)

        # 4. Reverse at-time: "remind me at TIME [tomorrow] to TASK"
        m = _SET_AT_REVERSE.search(text)
        if m:
            hour, minute, ampm, tomorrow, task = (
                m.group(1), m.group(2), m.group(3), m.group(4), m.group(5),
            )
            due = self._parse_absolute(hour, minute, ampm, tomorrow is not None)
            return self._set(task.strip(), due)

        # 5. Set at-time: "remind me to TASK at TIME [tomorrow]"
        m = _SET_AT.search(text)
        if m:
            task, hour, minute, ampm, tomorrow = (
                m.group(1), m.group(2), m.group(3), m.group(4), m.group(5),
            )
            due = self._parse_absolute(hour, minute, ampm, tomorrow is not None)
            return self._set(task.strip(), due)

        # 6. Set relative: "remind me to TASK in N UNITS"
        m = _SET_RELATIVE.search(text)
        if m:
            delta = self._parse_relative(m.group(2), m.group(3))
            return self._set(m.group(1).strip(), datetime.now() + delta)

        # 7. Set tomorrow: "remind me to TASK tomorrow"
        m = _SET_TOMORROW.search(text)
        if m:
            tomorrow_9am = (datetime.now() + timedelta(days=1)).replace(
                hour=9, minute=0, second=0, microsecond=0
            )
            return self._set(m.group(1).strip(), tomorrow_9am)

        # 8. Cancel specific
        m = _CANCEL.search(text)
        if m:
            return self._cancel(m.group(1).strip())

        # 9. Clear all
        if _CLEAR.search(text):
            return self._clear()

        # 10. List
        if _LIST.search(text):
            return self._list()

        # Fallback: "remind" mentioned but no pattern matched → list
        return self._list()

    # -- Actions --

    def _set(self, task: str, due: datetime) -> str:
        items = self._load()
        item = {
            "text": task,
            "due": due.replace(microsecond=0).isoformat(),
            "created": datetime.now().replace(microsecond=0).isoformat(),
        }
        items.append(item)
        self._save(items)
        desc = self._describe_due(due)
        return f"I'll remind you to {task} {desc}."

    def _list(self) -> str:
        items = self._load()
        if not items:
            return "You don't have any reminders."
        if len(items) == 1:
            desc = self._describe_due(datetime.fromisoformat(items[0]["due"]))
            return f"You have one reminder: {items[0]['text']}, {desc}."
        parts = []
        for item in items:
            desc = self._describe_due(datetime.fromisoformat(item["due"]))
            parts.append(f"{item['text']}, {desc}")
        return f"You have {len(items)} reminders. " + ". ".join(parts) + "."

    def _cancel(self, target: str) -> str:
        items = self._load()
        target_lower = target.lower()

        # Try exact match first
        for i, item in enumerate(items):
            if item["text"].lower() == target_lower:
                items.pop(i)
                self._save(items)
                return f"Cancelled your reminder to {item['text']}."

        # Try substring match
        matches = [(i, item) for i, item in enumerate(items)
                   if target_lower in item["text"].lower()]
        if len(matches) == 1:
            idx, item = matches[0]
            items.pop(idx)
            self._save(items)
            return f"Cancelled your reminder to {item['text']}."
        if len(matches) > 1:
            return (
                f"I found {len(matches)} reminders matching that. "
                "Can you be more specific?"
            )

        return f"I don't see a reminder about {target}."

    def _clear(self) -> str:
        self._save([])
        return "All reminders have been cleared."

    # -- Time parsing --

    def _parse_relative(self, amount_str: str, unit: str) -> timedelta:
        lower = amount_str.lower()
        if lower in ("a", "an"):
            amount = 1
        elif lower.startswith("half"):
            # "half an hour" → 30 minutes
            unit_base = unit.rstrip("s")
            if unit_base == "hour":
                return timedelta(minutes=30)
            if unit_base == "minute":
                return timedelta(seconds=30)
            # fallback: half a day = 12 hours
            return timedelta(hours=12)
        else:
            amount = int(amount_str)

        unit_base = unit.rstrip("s")
        if unit_base == "second":
            return timedelta(seconds=amount)
        if unit_base == "minute":
            return timedelta(minutes=amount)
        if unit_base == "hour":
            return timedelta(hours=amount)
        if unit_base == "day":
            return timedelta(days=amount)
        return timedelta(minutes=amount)  # fallback

    def _parse_absolute(self, hour_str: str, minute_str: Optional[str],
                        ampm: Optional[str], tomorrow: bool = False) -> datetime:
        hour = int(hour_str)
        minute = int(minute_str) if minute_str else 0

        if ampm:
            ampm_clean = ampm.replace(".", "").lower()
            if ampm_clean == "pm" and hour != 12:
                hour += 12
            elif ampm_clean == "am" and hour == 12:
                hour = 0
        else:
            # No AM/PM: 1-6 → PM, 7-11 → AM, 12 → PM
            if 1 <= hour <= 6:
                hour += 12
            elif hour == 12:
                pass  # noon

        now = datetime.now()
        if tomorrow:
            day = now + timedelta(days=1)
        else:
            day = now

        due = day.replace(hour=hour, minute=minute, second=0, microsecond=0)

        # If not explicitly tomorrow and the time is past, bump to tomorrow
        if not tomorrow and due <= now:
            due += timedelta(days=1)

        return due

    def _describe_due(self, due: datetime) -> str:
        now = datetime.now()
        diff = due - now

        # If due in the past, say "overdue"
        if diff.total_seconds() < 0:
            return "overdue"

        total_minutes = int(diff.total_seconds() / 60)

        # Less than 1 minute
        if total_minutes < 1:
            secs = max(1, int(diff.total_seconds()))
            return f"in {secs} second{'s' if secs != 1 else ''}"

        # Less than 60 minutes
        if total_minutes < 60:
            return f"in {total_minutes} minute{'s' if total_minutes != 1 else ''}"

        # Less than 24 hours
        if total_minutes < 1440:
            hours = total_minutes // 60
            if hours < 24:
                time_str = due.strftime("%-I:%M %p")
                if due.date() == now.date():
                    return f"today at {time_str}"
                return f"tomorrow at {time_str}"

        # More than 24 hours
        time_str = due.strftime("%-I:%M %p")
        if due.date() == (now + timedelta(days=1)).date():
            return f"tomorrow at {time_str}"
        day_name = due.strftime("%A")
        return f"on {day_name} at {time_str}"

    # -- Persistence --

    def _load(self) -> list[dict]:
        with self._lock:
            if not self._path.exists():
                return []
            try:
                data = json.loads(self._path.read_text())
                if isinstance(data, list):
                    return data
                log.warning("Reminder file has unexpected format, resetting")
                return []
            except (json.JSONDecodeError, OSError):
                log.warning("Reminder file corrupted or unreadable, resetting")
                return []

    def _save(self, items: list[dict]) -> None:
        with self._lock:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(json.dumps(items, indent=2) + "\n")

    # -- Background checker --

    def _checker_loop(self) -> None:
        while not self._stop_event.wait(timeout=self._check_interval):
            self._check_due()

    def _check_due(self) -> None:
        now = datetime.now()
        items = self._load()
        due_items = []
        remaining = []

        for item in items:
            try:
                due_time = datetime.fromisoformat(item["due"])
            except (KeyError, ValueError):
                remaining.append(item)
                continue

            if due_time <= now:
                due_items.append(item)
            else:
                remaining.append(item)

        if due_items:
            self._save(remaining)
            for item in due_items:
                log.info(f"Reminder due: {item['text']}")
                if self._on_due:
                    try:
                        self._on_due(item["text"])
                    except Exception:
                        log.exception(f"Error firing reminder: {item['text']}")

    def close(self) -> None:
        self._stop_event.set()
        if self._checker_thread is not None:
            self._checker_thread.join(timeout=5)
