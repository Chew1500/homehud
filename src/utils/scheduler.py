"""Shared wall-clock scheduler — min-heap + Event.wait loop.

One daemon thread fires callbacks at their due times. Registrants get sub-second
granularity near fire time without per-feature polling threads. Used by
ReminderFeature (long dated tasks) and TimerFeature (short kitchen countdowns).

Callbacks run on the scheduler thread. They must NOT mutate voice-lock-guarded
router state — dispatch back to the main thread via the audio / notification
channels instead.
"""

from __future__ import annotations

import heapq
import itertools
import logging
import threading
import time
import uuid
from typing import Callable

log = logging.getLogger("home-hud.scheduler")


class Scheduler:
    def __init__(self) -> None:
        # Heap of (due_ts, tiebreaker, entry_id). Cancelled ids are left in the
        # heap and skipped on pop — cheaper than O(n) removal.
        self._heap: list[tuple[float, int, str]] = []
        self._entries: dict[str, tuple[dict, Callable[[dict], None]]] = {}
        self._counter = itertools.count()
        self._lock = threading.Lock()
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._thread = threading.Thread(
            target=self._loop, daemon=True, name="Scheduler"
        )
        self._thread.start()

    def add(
        self,
        due_ts: float,
        payload: dict,
        on_fire: Callable[[dict], None],
    ) -> str:
        """Schedule `on_fire(payload)` at Unix timestamp `due_ts`.

        Returns an opaque id usable with `cancel()`. A due_ts in the past
        fires on the next loop iteration (effectively immediately).
        """
        entry_id = uuid.uuid4().hex
        with self._lock:
            heapq.heappush(self._heap, (due_ts, next(self._counter), entry_id))
            self._entries[entry_id] = (payload, on_fire)
        self._wake.set()
        return entry_id

    def cancel(self, entry_id: str) -> bool:
        """Cancel a pending entry. Returns True if found, False if unknown or
        already fired."""
        with self._lock:
            removed = self._entries.pop(entry_id, None) is not None
        if removed:
            # Wake the loop in case the cancelled entry was the earliest — it
            # will re-compute the next sleep duration.
            self._wake.set()
        return removed

    def list(self) -> list[dict]:
        """Snapshot of pending entries, earliest first."""
        with self._lock:
            out = [
                {"id": eid, "due_ts": due_ts, "payload": self._entries[eid][0]}
                for due_ts, _, eid in self._heap
                if eid in self._entries
            ]
        out.sort(key=lambda e: e["due_ts"])
        return out

    def close(self) -> None:
        self._stop.set()
        self._wake.set()
        self._thread.join(timeout=5)

    # -- internals --

    def _loop(self) -> None:
        while not self._stop.is_set():
            next_due, fire = self._pop_due()
            if fire is not None:
                payload, on_fire = fire
                try:
                    on_fire(payload)
                except Exception:
                    log.exception("Scheduler callback failed")
                continue  # drain further due entries immediately

            timeout = None if next_due is None else max(0.0, next_due - time.time())
            self._wake.wait(timeout=timeout)
            self._wake.clear()

    def _pop_due(
        self,
    ) -> tuple[float | None, tuple[dict, Callable[[dict], None]] | None]:
        now = time.time()
        with self._lock:
            while self._heap:
                due_ts, _, eid = self._heap[0]
                if eid not in self._entries:
                    heapq.heappop(self._heap)  # cancelled — drop
                    continue
                if due_ts > now:
                    return due_ts, None
                heapq.heappop(self._heap)
                entry = self._entries.pop(eid)
                return due_ts, entry
            return None, None
