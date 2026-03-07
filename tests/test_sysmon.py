"""Tests for PiSystemMonitor vcgencmd parsing."""

import logging
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sysmon.pi_sysmon import PiSystemMonitor


def _make_result(stdout="", stderr="", returncode=0):
    return subprocess.CompletedProcess(
        args=[], returncode=returncode, stdout=stdout, stderr=stderr
    )


# --- _read_temp ---


def test_temp_success():
    """Parses temperature from normal vcgencmd output."""
    mon = PiSystemMonitor()
    with patch("sysmon.pi_sysmon.subprocess.run", return_value=_make_result("temp=45.2'C\n")):
        assert mon._read_temp() == 45.2


def test_temp_nonzero_returncode(caplog):
    """Non-zero returncode returns None and logs warning."""
    mon = PiSystemMonitor()
    result = _make_result(stderr="VCHI initialization failed", returncode=1)
    with patch("sysmon.pi_sysmon.subprocess.run", return_value=result):
        with caplog.at_level(logging.WARNING):
            assert mon._read_temp() is None
    assert "measure_temp failed" in caplog.text


def test_temp_unparseable_output(caplog):
    """Output that doesn't match regex returns None and logs warning."""
    mon = PiSystemMonitor()
    with patch("sysmon.pi_sysmon.subprocess.run", return_value=_make_result("garbage")):
        with caplog.at_level(logging.WARNING):
            assert mon._read_temp() is None
    assert "not parseable" in caplog.text


def test_temp_permission_error(caplog):
    """PermissionError is caught (not just FileNotFoundError)."""
    mon = PiSystemMonitor()
    with patch("sysmon.pi_sysmon.subprocess.run", side_effect=PermissionError("nope")):
        with caplog.at_level(logging.WARNING):
            assert mon._read_temp() is None
    assert "Failed to read CPU temperature" in caplog.text


def test_temp_file_not_found():
    """FileNotFoundError (vcgencmd missing) returns None without crash."""
    mon = PiSystemMonitor()
    with patch("sysmon.pi_sysmon.subprocess.run", side_effect=FileNotFoundError):
        assert mon._read_temp() is None


# --- _read_power ---


SAME_LINE_OUTPUT = """\
VDD_CORE  0.8800V  1.2300A
VDD_SDRAM_P  1.1000V  0.3000A
"""

SEPARATE_LINE_OUTPUT = """\
VDD_CORE curr(A)=1.2300A
VDD_CORE volt(V)=0.8800V
VDD_SDRAM_P volt(V)=1.1000V
VDD_SDRAM_P curr(A)=0.3000A
"""


def _expected_power():
    """Expected total watts for both formats above."""
    return round(0.88 * 1.23 + 1.10 * 0.30, 1)


def test_power_same_line_format():
    """Parses original same-line V+A format."""
    mon = PiSystemMonitor()
    with patch("sysmon.pi_sysmon.subprocess.run", return_value=_make_result(SAME_LINE_OUTPUT)):
        assert mon._read_power() == _expected_power()


def test_power_separate_line_format():
    """Parses RPi5 separate-line V and A format."""
    mon = PiSystemMonitor()
    with patch("sysmon.pi_sysmon.subprocess.run", return_value=_make_result(SEPARATE_LINE_OUTPUT)):
        assert mon._read_power() == _expected_power()


def test_power_nonzero_returncode(caplog):
    """Non-zero returncode returns None and logs warning."""
    mon = PiSystemMonitor()
    result = _make_result(stderr="error", returncode=1)
    with patch("sysmon.pi_sysmon.subprocess.run", return_value=result):
        with caplog.at_level(logging.WARNING):
            assert mon._read_power() is None
    assert "pmic_read_adc failed" in caplog.text


def test_power_no_parseable_pairs(caplog):
    """Output with no V/A pairs returns None and logs warning."""
    mon = PiSystemMonitor()
    with patch("sysmon.pi_sysmon.subprocess.run", return_value=_make_result("no data here\n")):
        with caplog.at_level(logging.WARNING):
            assert mon._read_power() is None
    assert "no parseable V/A pairs" in caplog.text


def test_power_exception():
    """Unexpected exception returns None without crash."""
    mon = PiSystemMonitor()
    with patch("sysmon.pi_sysmon.subprocess.run", side_effect=OSError("blocked")):
        assert mon._read_power() is None
