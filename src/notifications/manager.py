"""Reusable proactive notification manager with cooldowns and quiet hours."""

from __future__ import annotations

import logging
import threading
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, time

log = logging.getLogger("home-hud.notifications")


@dataclass
class Notification:
    """A pending proactive notification."""

    category: str  # e.g., "garden", "service_down"
    message: str  # TTS-ready text
    priority: int = 0  # 0=info, 1=advisory, 2=urgent
    cooldown_key: str = ""  # dedup key, e.g., "garden:water_today"
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    created_at: datetime = field(default_factory=datetime.now)


def _parse_time(s: str) -> time | None:
    """Parse HH:MM string to time object."""
    try:
        parts = s.strip().split(":")
        return time(int(parts[0]), int(parts[1]))
    except (ValueError, IndexError):
        return None


class NotificationManager:
    """Thread-safe notification queue with per-category cooldowns and quiet hours."""

    def __init__(self, config: dict) -> None:
        self._queue: deque[Notification] = deque()
        self._cooldowns: dict[str, datetime] = {}
        self._lock = threading.Lock()
        self._default_cooldown = config.get("notification_cooldown_seconds", 3600)
        self._quiet_start = _parse_time(
            config.get("notification_quiet_start", "22:00"),
        )
        self._quiet_end = _parse_time(
            config.get("notification_quiet_end", "07:00"),
        )

    def _in_quiet_hours(self) -> bool:
        if not self._quiet_start or not self._quiet_end:
            return False
        now = datetime.now().time()
        if self._quiet_start <= self._quiet_end:
            return self._quiet_start <= now <= self._quiet_end
        # Wraps midnight (e.g., 22:00 - 07:00)
        return now >= self._quiet_start or now <= self._quiet_end

    def _in_cooldown(self, key: str) -> bool:
        if not key:
            return False
        last = self._cooldowns.get(key)
        if last is None:
            return False
        elapsed = (datetime.now() - last).total_seconds()
        return elapsed < self._default_cooldown

    def submit(self, notification: Notification) -> bool:
        """Add notification to queue if not in cooldown. Returns True if queued."""
        with self._lock:
            if self._in_cooldown(notification.cooldown_key):
                log.debug(
                    "Notification %s in cooldown, skipping",
                    notification.cooldown_key,
                )
                return False

            # Deduplicate: don't queue if same cooldown_key already pending
            if notification.cooldown_key:
                for existing in self._queue:
                    if existing.cooldown_key == notification.cooldown_key:
                        return False

            self._queue.append(notification)
            log.info(
                "Notification queued: %s (priority=%d)",
                notification.category, notification.priority,
            )
            return True

    def peek(self) -> Notification | None:
        """Return next deliverable notification without removing it.

        Returns None during quiet hours or if queue is empty.
        """
        with self._lock:
            if self._in_quiet_hours():
                return None
            if not self._queue:
                return None
            # Return highest priority first
            best = max(self._queue, key=lambda n: n.priority)
            return best

    def deliver(self, notification_id: str) -> Notification | None:
        """Mark notification as delivered: remove from queue, start cooldown.

        Returns the delivered notification, or None if not found.
        """
        with self._lock:
            for i, n in enumerate(self._queue):
                if n.id == notification_id:
                    self._queue.remove(n)
                    if n.cooldown_key:
                        self._cooldowns[n.cooldown_key] = datetime.now()
                    log.info("Notification delivered: %s", n.category)
                    return n
            return None

    def dismiss(self, notification_id: str) -> None:
        """Remove notification without delivering (no cooldown reset)."""
        with self._lock:
            self._queue = deque(
                n for n in self._queue if n.id != notification_id
            )

    def pending_count(self) -> int:
        """Number of pending notifications."""
        with self._lock:
            return len(self._queue)
