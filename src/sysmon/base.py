"""System monitor ABC and metrics dataclass."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class SystemMetrics:
    """Snapshot of system health metrics."""

    cpu_temp_c: float | None = None  # °C from vcgencmd measure_temp
    power_w: float | None = None  # Watts from vcgencmd pmic_read_adc (RPi5)


class BaseSystemMonitor(ABC):
    """ABC for reading system hardware metrics."""

    @abstractmethod
    def get_metrics(self) -> SystemMetrics:
        """Return current system metrics."""

    def close(self) -> None:
        """Release resources (no-op by default)."""
