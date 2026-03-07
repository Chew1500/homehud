"""Pi system monitor — reads real hardware metrics via vcgencmd."""

from __future__ import annotations

import logging
import re
import subprocess

from sysmon.base import BaseSystemMonitor, SystemMetrics

log = logging.getLogger(__name__)


class PiSystemMonitor(BaseSystemMonitor):
    """Reads CPU temperature and power from vcgencmd on Raspberry Pi."""

    def get_metrics(self) -> SystemMetrics:
        return SystemMetrics(
            cpu_temp_c=self._read_temp(),
            power_w=self._read_power(),
        )

    def _read_temp(self) -> float | None:
        """Parse temperature from `vcgencmd measure_temp`."""
        try:
            result = subprocess.run(
                ["vcgencmd", "measure_temp"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            # Output: "temp=45.2'C\n"
            match = re.search(r"temp=([\d.]+)", result.stdout)
            if match:
                return float(match.group(1))
        except (FileNotFoundError, subprocess.TimeoutExpired, ValueError):
            log.debug("Failed to read CPU temperature", exc_info=True)
        return None

    def _read_power(self) -> float | None:
        """Parse total power from `vcgencmd pmic_read_adc` (RPi5 only)."""
        try:
            result = subprocess.run(
                ["vcgencmd", "pmic_read_adc"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode != 0:
                return None
            # Each line: "label  V_val A_val"  e.g. "VDD_CORE  0.8800V  1.2300A"
            total_w = 0.0
            found = False
            for line in result.stdout.splitlines():
                v_match = re.search(r"([\d.]+)V", line)
                a_match = re.search(r"([\d.]+)A", line)
                if v_match and a_match:
                    total_w += float(v_match.group(1)) * float(a_match.group(1))
                    found = True
            return round(total_w, 1) if found else None
        except (FileNotFoundError, subprocess.TimeoutExpired, ValueError):
            log.debug("Failed to read power consumption", exc_info=True)
        return None
