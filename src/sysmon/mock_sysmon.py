"""Mock system monitor for local development."""

from sysmon.base import BaseSystemMonitor, SystemMetrics


class MockSystemMonitor(BaseSystemMonitor):
    """Returns static metrics for local dev."""

    def get_metrics(self) -> SystemMetrics:
        return SystemMetrics(cpu_temp_c=45.0, power_w=3.5)
