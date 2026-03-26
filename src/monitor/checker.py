"""Service health check functions — shared by collector and web API."""

from __future__ import annotations

import subprocess
import time

import httpx

CheckResult = tuple[bool, float | None, int | None, str | None]


def check_http(url: str, timeout: int = 10) -> CheckResult:
    """Check an HTTP(S) endpoint. Any response = up.

    Returns (is_up, response_time_ms, status_code, error).
    """
    try:
        start = time.monotonic()
        resp = httpx.get(
            url, timeout=timeout, follow_redirects=True
        )
        elapsed_ms = (time.monotonic() - start) * 1000
        return True, round(elapsed_ms, 1), resp.status_code, None
    except httpx.TimeoutException:
        return False, None, None, "timeout"
    except httpx.ConnectError as exc:
        return False, None, None, f"connect error: {exc}"
    except httpx.HTTPError as exc:
        return False, None, None, str(exc)


def check_ping(host: str, timeout: int = 10) -> CheckResult:
    """Check a host via ICMP ping. Exit code 0 = up.

    Returns (is_up, response_time_ms, None, error).
    """
    try:
        start = time.monotonic()
        result = subprocess.run(
            ["ping", "-c", "1", "-W", str(timeout), host],
            capture_output=True,
            text=True,
            timeout=timeout + 5,
        )
        elapsed_ms = (time.monotonic() - start) * 1000
        if result.returncode == 0:
            return True, round(elapsed_ms, 1), None, None
        return False, None, None, "ping failed"
    except subprocess.TimeoutExpired:
        return False, None, None, "ping timeout"
    except FileNotFoundError:
        return False, None, None, "ping command not found"
