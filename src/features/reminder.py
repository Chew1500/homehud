"""Reminder feature — set, list, cancel, and fire timed reminders via voice."""

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
# 9. List: "what are/show/list [my] reminders"
_LIST = re.compile(
    r"\b(?:what\s+are|show|list)\s+(?:my\s+)?reminders\b",
    re.IGNORECASE,
)


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
    def description(self) -> str:
        return (
            'Reminders: triggered by "remind" or "reminder". '
            'Commands: "remind me to X in Y minutes", "remind me to X at 3pm", '
            '"what are my reminders", "cancel reminder to X", "clear all reminders".'
        )

    def matches(self, text: str) -> bool:
        return bool(_ANY_REMINDER.search(text))

    def handle(self, text: str) -> str:
        # 1. Prefix: "at TIME [tomorrow] remind me to TASK"
        m = _PREFIX_AT.search(text)
        if m:
            hour, minute, ampm, tomorrow, task = (
                m.group(1), m.group(2), m.group(3), m.group(4), m.group(5),
            )
            due = self._parse_absolute(hour, minute, ampm, tomorrow is not None)
            return self._set(task.strip(), due)

        # 2. Prefix: "tomorrow at TIME remind me to TASK"
        m = _PREFIX_TOMORROW_AT.search(text)
        if m:
            hour, minute, ampm, task = m.group(1), m.group(2), m.group(3), m.group(4)
            due = self._parse_absolute(hour, minute, ampm, tomorrow=True)
            return self._set(task.strip(), due)

        # 3. Relative time-first: "remind me in 10 minutes to TASK"
        m = _SET_RELATIVE_FIRST.search(text)
        if m:
            delta = self._parse_relative(m.group(1), m.group(2))
            return self._set(m.group(3).strip(), datetime.now() + delta)

        # 4. Set at-time: "remind me to TASK at TIME [tomorrow]"
        m = _SET_AT.search(text)
        if m:
            task, hour, minute, ampm, tomorrow = (
                m.group(1), m.group(2), m.group(3), m.group(4), m.group(5),
            )
            due = self._parse_absolute(hour, minute, ampm, tomorrow is not None)
            return self._set(task.strip(), due)

        # 5. Set relative: "remind me to TASK in N UNITS"
        m = _SET_RELATIVE.search(text)
        if m:
            delta = self._parse_relative(m.group(2), m.group(3))
            return self._set(m.group(1).strip(), datetime.now() + delta)

        # 6. Set tomorrow: "remind me to TASK tomorrow"
        m = _SET_TOMORROW.search(text)
        if m:
            tomorrow_9am = (datetime.now() + timedelta(days=1)).replace(
                hour=9, minute=0, second=0, microsecond=0
            )
            return self._set(m.group(1).strip(), tomorrow_9am)

        # 7. Cancel specific
        m = _CANCEL.search(text)
        if m:
            return self._cancel(m.group(1).strip())

        # 8. Clear all
        if _CLEAR.search(text):
            return self._clear()

        # 9. List
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
