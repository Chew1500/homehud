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
VDD_CORE  0.8819V  0.8126A
1V8_SYS  1.8100V  0.1200A
3V3_SYS  3.3100V  0.1415A
"""

# Real Pi 5 format: rail names end in _A (current) or _V (voltage)
SEPARATE_LINE_OUTPUT = """\
3V3_SYS_A current(1)=0.14150990A
VDD_CORE_A current(7)=0.81262990A
1V8_SYS_A current(3)=0.12000000A
3V3_SYS_V volt(9)=3.31003300V
VDD_CORE_V volt(15)=0.88187950V
1V8_SYS_V volt(11)=1.81000000V
EXT5V_V volt(24)=5.15766000V
"""


def _expected_power():
    """Expected total watts for both formats above."""
    return round(0.8819 * 0.8126 + 1.81 * 0.12 + 3.31 * 0.1415, 1)


def test_power_same_line_format():
    """Parses original same-line V+A format."""
    mon = PiSystemMonitor()
    with patch("sysmon.pi_sysmon.subprocess.run", return_value=_make_result(SAME_LINE_OUTPUT)):
        assert mon._read_power() == _expected_power()


def test_power_separate_line_format():
    """Parses RPi5 separate-line _V/_A suffix format."""
    mon = PiSystemMonitor()
    with patch("sysmon.pi_sysmon.subprocess.run", return_value=_make_result(SEPARATE_LINE_OUTPUT)):
        result = mon._read_power()
        expected = round(
            3.31003300 * 0.14150990
            + 0.88187950 * 0.81262990
            + 1.81000000 * 0.12000000,
            1,
        )
        assert result == expected


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


def test_power_digit_in_rail_name():
    """Rails with digits in name (3V3_SYS, 1V8_SYS) don't false-match voltage from the name."""
    output = "3V3_SYS_A current(1)=0.14150990A\n3V3_SYS_V volt(9)=3.31003300V\n"
    mon = PiSystemMonitor()
    with patch("sysmon.pi_sysmon.subprocess.run", return_value=_make_result(output)):
        result = mon._read_power()
        expected = round(3.31003300 * 0.14150990, 1)
        assert result == expected


def test_power_v_a_suffix_pairing():
    """_V and _A suffixed lines for the same rail are correctly paired."""
    output = (
        "VDD_CORE_A current(7)=0.81262990A\n"
        "VDD_CORE_V volt(15)=0.88187950V\n"
    )
    mon = PiSystemMonitor()
    with patch("sysmon.pi_sysmon.subprocess.run", return_value=_make_result(output)):
        result = mon._read_power()
        expected = round(0.88187950 * 0.81262990, 1)
        assert result == expected
