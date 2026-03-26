"""Background collector — polls monitored services and stores results."""

from __future__ import annotations

import logging
import subprocess
import threading
import time

import httpx

from monitor.storage import MonitorStorage

log = logging.getLogger("home-hud.monitor.collector")


class ServiceCollector:
    """Daemon thread that checks monitored services on a configurable interval."""

    def __init__(self, storage: MonitorStorage, config: dict):
        self._storage = storage
        self._poll_interval = config.get("monitor_poll_interval", 600)
        self._timeout = config.get("monitor_check_timeout", 10)
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

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
                    is_up, response_ms, status_code, error = self._check_ping(
                        svc["url"]
                    )
                else:
                    is_up, response_ms, status_code, error = self._check_http(
                        svc["url"]
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

        down = [s["name"] for s in self._storage.get_down_services()]
        if down:
            log.warning("Services DOWN: %s", ", ".join(down))
        else:
            log.debug("All %d monitored services up", len(services))

    def _check_http(
        self, url: str
    ) -> tuple[bool, float | None, int | None, str | None]:
        """Check an HTTP(S) endpoint. Any response = up."""
        try:
            start = time.monotonic()
            resp = httpx.get(
                url, timeout=self._timeout, follow_redirects=True
            )
            elapsed_ms = (time.monotonic() - start) * 1000
            return True, round(elapsed_ms, 1), resp.status_code, None
        except httpx.TimeoutException:
            return False, None, None, "timeout"
        except httpx.ConnectError as exc:
            return False, None, None, f"connect error: {exc}"
        except httpx.HTTPError as exc:
            return False, None, None, str(exc)

    def _check_ping(
        self, host: str
    ) -> tuple[bool, float | None, int | None, str | None]:
        """Check a host via ICMP ping. Exit code 0 = up."""
        try:
            start = time.monotonic()
            result = subprocess.run(
                ["ping", "-c", "1", "-W", str(self._timeout), host],
                capture_output=True,
                text=True,
                timeout=self._timeout + 5,
            )
            elapsed_ms = (time.monotonic() - start) * 1000
            if result.returncode == 0:
                return True, round(elapsed_ms, 1), None, None
            return False, None, None, "ping failed"
        except subprocess.TimeoutExpired:
            return False, None, None, "ping timeout"
        except FileNotFoundError:
            return False, None, None, "ping command not found"

    def close(self) -> None:
        """Stop the collector thread."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
            log.info("Service collector stopped")
