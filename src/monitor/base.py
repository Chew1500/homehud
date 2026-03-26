"""Service monitor data models."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ServiceStatus:
    """Result of a single service health check."""

    service_id: int
    name: str
    url: str
    check_type: str  # "http" or "ping"
    is_up: bool
    response_time_ms: float | None
    status_code: int | None  # HTTP only
    error: str | None
    checked_at: str  # ISO timestamp
