"""Tests for the network info feature."""

import json
from unittest.mock import patch

import pytest

from features.network import NetworkFeature


@pytest.fixture
def feature():
    return NetworkFeature({})


# --- Regex matching ---


@pytest.mark.parametrize(
    "text",
    [
        "what's my IP",
        "what's my ip address",
        "what is my IP",
        "what's your IP",
        "what's your address",
        "what is your address",
        "ip address",
        "network info",
        "network status",
        "what network are you on",
        "What's my IP address?",
    ],
)
def test_matches_positive(feature, text):
    assert feature.matches(text)


@pytest.mark.parametrize(
    "text",
    [
        "what's the weather",
        "add milk to the grocery list",
        "set a reminder",
        "hello",
    ],
)
def test_matches_negative(feature, text):
    assert not feature.matches(text)


# --- Response formatting ---

IP_JSON = json.dumps([
    {
        "ifname": "lo",
        "addr_info": [{"family": "inet", "local": "127.0.0.1"}],
    },
    {
        "ifname": "wlan0",
        "addr_info": [{"family": "inet", "local": "192.168.1.100"}],
    },
])

IP_JSON_MULTI = json.dumps([
    {
        "ifname": "lo",
        "addr_info": [{"family": "inet", "local": "127.0.0.1"}],
    },
    {
        "ifname": "wlan0",
        "addr_info": [{"family": "inet", "local": "192.168.1.100"}],
    },
    {
        "ifname": "eth0",
        "addr_info": [{"family": "inet", "local": "192.168.1.50"}],
    },
])


@patch("features.network.sys")
@patch("features.network.subprocess.run")
def test_handle_single_interface(mock_run, mock_sys, feature):
    mock_sys.platform = "linux"
    mock_run.return_value.returncode = 0
    mock_run.return_value.stdout = IP_JSON

    response = feature.handle("what's my IP")
    assert "192.168.1.100" in response
    assert "wlan0" in response
    assert "WiFi" in response


@patch("features.network.sys")
@patch("features.network.subprocess.run")
def test_handle_multiple_interfaces(mock_run, mock_sys, feature):
    mock_sys.platform = "linux"
    mock_run.return_value.returncode = 0
    mock_run.return_value.stdout = IP_JSON_MULTI

    response = feature.handle("what's my IP")
    assert "192.168.1.100" in response
    assert "192.168.1.50" in response
    assert "2 active connections" in response


@patch("features.network.sys")
@patch("features.network.subprocess.run")
def test_loopback_filtered(mock_run, mock_sys, feature):
    mock_sys.platform = "linux"
    mock_run.return_value.returncode = 0
    mock_run.return_value.stdout = json.dumps([
        {"ifname": "lo", "addr_info": [{"family": "inet", "local": "127.0.0.1"}]},
    ])

    response = feature.handle("what's my IP")
    assert "couldn't detect" in response


# --- Fallback ---


@patch("features.network.sys")
@patch("features.network.socket.gethostbyname", return_value="10.0.0.5")
@patch("features.network.socket.gethostname", return_value="devbox")
def test_fallback_non_linux(mock_hostname, mock_resolve, mock_sys, feature):
    mock_sys.platform = "darwin"

    response = feature.handle("what's my IP")
    assert "10.0.0.5" in response


@patch("features.network.sys")
@patch("features.network.subprocess.run", side_effect=OSError("no ip command"))
@patch("features.network.socket.gethostbyname", return_value="10.0.0.5")
@patch("features.network.socket.gethostname", return_value="devbox")
def test_fallback_when_ip_command_fails(
    mock_hostname, mock_resolve, mock_run, mock_sys, feature
):
    mock_sys.platform = "linux"

    response = feature.handle("what's my IP")
    assert "10.0.0.5" in response


# --- Action schema ---


def test_action_schema(feature):
    assert "query" in feature.action_schema


@patch("features.network.sys")
@patch("features.network.socket.gethostbyname", return_value="10.0.0.5")
@patch("features.network.socket.gethostname", return_value="devbox")
def test_execute(mock_hostname, mock_resolve, mock_sys, feature):
    mock_sys.platform = "darwin"
    response = feature.execute("query", {})
    assert "10.0.0.5" in response
