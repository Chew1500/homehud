"""Display context — bundles all data sources needed for rendering."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from enphase.storage import SolarStorage
    from features.grocery import GroceryFeature
    from features.reminder import ReminderFeature
    from sysmon.base import BaseSystemMonitor


@dataclass
class DisplayContext:
    """All data sources the display needs, in one stable object."""

    solar_storage: SolarStorage | None = None
    grocery: GroceryFeature | None = None
    reminders: ReminderFeature | None = None
    system_monitor: BaseSystemMonitor | None = None
