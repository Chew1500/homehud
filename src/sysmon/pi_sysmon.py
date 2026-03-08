"""Pi system monitor — reads real hardware metrics via vcgencmd."""

from __future__ import annotations

import logging
import re
import subprocess
from collections import defaultdict

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
            if result.returncode != 0:
                log.warning(
                    "vcgencmd measure_temp failed (rc=%d): stdout=%r stderr=%r",
                    result.returncode,
                    result.stdout.strip(),
                    result.stderr.strip(),
                )
                return None
            # Output: "temp=45.2'C\n"
            match = re.search(r"temp=([\d.]+)", result.stdout)
            if match:
                return float(match.group(1))
            log.warning(
                "vcgencmd measure_temp output not parseable: %r",
                result.stdout.strip(),
            )
        except Exception:
            log.warning("Failed to read CPU temperature", exc_info=True)
        return None

    def _read_power(self) -> float | None:
        """Parse total power from `vcgencmd pmic_read_adc` (RPi5 only).

        Handles two output formats:
        - Same-line:     "VDD_CORE  0.8800V  1.2300A"
        - Separate-line: "VDD_CORE volt(V)=0.880V" / "VDD_CORE curr(A)=1.234A"
        """
        try:
            result = subprocess.run(
                ["vcgencmd", "pmic_read_adc"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode != 0:
                log.warning(
                    "vcgencmd pmic_read_adc failed (rc=%d): stdout=%r stderr=%r",
                    result.returncode,
                    result.stdout.strip(),
                    result.stderr.strip(),
                )
                return None

            log.debug("vcgencmd pmic_read_adc raw output:\n%s", result.stdout.rstrip())

            # Collect voltage and current per rail name, supporting both
            # same-line and separate-line formats.
            rails: dict[str, dict[str, float]] = defaultdict(dict)

            for line in result.stdout.splitlines():
                parts = line.split()
                if not parts:
                    continue
                rail = parts[0]
                # Strip _V/_A suffix so voltage and current lines share a key
                if rail.endswith(("_V", "_A")):
                    rail = rail[:-2]

                v_match = re.search(r"(?<![A-Za-z_])(\d+\.\d+)V\b", line)
                a_match = re.search(r"(?<![A-Za-z_])(\d+\.\d+)A\b", line)

                if v_match:
                    rails[rail]["v"] = float(v_match.group(1))
                if a_match:
                    rails[rail]["a"] = float(a_match.group(1))

            total_w = 0.0
            found = False
            for rail_data in rails.values():
                if "v" in rail_data and "a" in rail_data:
                    total_w += rail_data["v"] * rail_data["a"]
                    found = True

            if not found:
                log.warning(
                    "vcgencmd pmic_read_adc: no parseable V/A pairs in output: %r",
                    result.stdout.strip(),
                )
                return None

            return round(total_w, 1)
        except Exception:
            log.warning("Failed to read power consumption", exc_info=True)
        return None
