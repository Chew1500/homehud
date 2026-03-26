"""Background collector — polls monitored services and stores results."""

from __future__ import annotations

import logging
import threading

from monitor.checker import check_http, check_ping
from monitor.storage import MonitorStorage

log = logging.getLogger("home-hud.monitor.collector")


class ServiceCollector:
    """Daemon thread that checks monitored services on a configurable interval."""

    def __init__(
        self,
        storage: MonitorStorage,
        config: dict,
        refresh_event: threading.Event | None = None,
    ):
        self._storage = storage
        self._poll_interval = config.get("monitor_poll_interval", 600)
        self._timeout = config.get("monitor_check_timeout", 10)
        self._stop_event = threading.Event()
        self._refresh_event = refresh_event
        self._thread: threading.Thread | None = None
        self._prev_down_ids: set[int] = set()

    def start(self) -> threading.Thread:
        """Start the collector daemon thread."""
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        log.info(
            "Service collector started (poll every %ds)", self._poll_interval
        )
        return self._thread

    def _loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._collect()
            except Exception:
                log.exception("Error in service collector cycle")

            self._stop_event.wait(timeout=self._poll_interval)

    def _collect(self) -> None:
        """Run one collection cycle — check all enabled services."""
        services = self._storage.get_services(enabled_only=True)
        if not services:
            return

        for svc in services:
            try:
                if svc["check_type"] == "ping":
                    is_up, response_ms, status_code, error = check_ping(
                        svc["url"], self._timeout
                    )
                else:
                    is_up, response_ms, status_code, error = check_http(
                        svc["url"], self._timeout
                    )
            except Exception as exc:
                is_up, response_ms, status_code, error = (
                    False, None, None, str(exc)
                )

            self._storage.store_result(
                svc["id"], is_up, response_ms, status_code, error
            )

        # Prune results older than 90 days
        self._storage.prune_old_results(90)

        # Detect new outages and trigger display refresh
        down_services = self._storage.get_down_services()
        down_ids = {s["id"] for s in down_services}
        new_outages = down_ids - self._prev_down_ids
        self._prev_down_ids = down_ids

        if new_outages and self._refresh_event:
            log.info(
                "New outage(s) detected — triggering display refresh"
            )
            self._refresh_event.set()

        if down_services:
            names = [s["name"] for s in down_services]
            log.warning("Services DOWN: %s", ", ".join(names))
        else:
            log.debug("All %d monitored services up", len(services))

    def close(self) -> None:
        """Stop the collector thread."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
            log.info("Service collector stopped")
