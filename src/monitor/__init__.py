"""Service monitoring — storage factory."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from monitor.storage import MonitorStorage


def get_monitor_storage(config: dict) -> MonitorStorage | None:
    """Create monitor storage if monitoring is enabled, else None."""
    if not config.get("monitor_enabled", False):
        return None

    from monitor.storage import MonitorStorage as _MonitorStorage

    return _MonitorStorage(config.get("monitor_db_path", "data/monitor.db"))
