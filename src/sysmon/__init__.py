"""System monitor — factory function."""

from sysmon.base import BaseSystemMonitor
from sysmon.mock_sysmon import MockSystemMonitor


def get_system_monitor(config: dict) -> BaseSystemMonitor:
    """Create a system monitor based on config."""
    mode = config.get("sysmon_mode", "mock")
    if mode == "pi":
        from sysmon.pi_sysmon import PiSystemMonitor

        return PiSystemMonitor()
    return MockSystemMonitor()
