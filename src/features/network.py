"""Network info feature — reports IP addresses on active interfaces."""

from __future__ import annotations

import json
import logging
import re
import socket
import subprocess
import sys

from features.base import BaseFeature

log = logging.getLogger("home-hud.features.network")

_ANY_NETWORK = re.compile(
    r"\b("
    r"(?:what(?:'s| is) (?:my|your) (?:ip|address))"
    r"|ip address"
    r"|network (?:info|status)"
    r"|what network"
    r")\b",
    re.IGNORECASE,
)


class NetworkFeature(BaseFeature):
    """Reports the device's IP addresses on active network interfaces."""

    @property
    def name(self) -> str:
        return "Network Info"

    @property
    def short_description(self) -> str:
        return "Check my IP address and network status"

    @property
    def description(self) -> str:
        return (
            "Network information: triggered by \"what's my IP\", \"IP address\", "
            "\"what's your address\", \"network info\", \"network status\", "
            "\"what network\". Reports active network interfaces and their IP addresses."
        )

    @property
    def action_schema(self) -> dict:
        return {"query": {}}

    def execute(self, action: str, parameters: dict) -> str:
        return self.handle("")

    def matches(self, text: str) -> bool:
        return bool(_ANY_NETWORK.search(text))

    def handle(self, text: str) -> str:
        interfaces = self._get_interfaces()
        if not interfaces:
            return "I couldn't detect any active network interfaces."
        return self._format_response(interfaces)

    def _get_interfaces(self) -> list[dict]:
        """Get active network interfaces with IPv4 addresses.

        Returns list of dicts with 'name' and 'addr' keys.
        """
        if sys.platform == "linux":
            return self._get_interfaces_linux()
        return self._get_interfaces_fallback()

    def _get_interfaces_linux(self) -> list[dict]:
        """Use `ip -j addr show` to get interface info on Linux."""
        try:
            result = subprocess.run(
                ["ip", "-j", "addr", "show"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode != 0:
                log.warning("ip addr show failed: %s", result.stderr)
                return self._get_interfaces_fallback()

            data = json.loads(result.stdout)
            interfaces = []
            for iface in data:
                name = iface.get("ifname", "")
                if name == "lo":
                    continue
                for addr_info in iface.get("addr_info", []):
                    if addr_info.get("family") == "inet":
                        interfaces.append({
                            "name": name,
                            "addr": addr_info["local"],
                        })
            return interfaces
        except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError) as exc:
            log.warning("Failed to get interfaces via ip command: %s", exc)
            return self._get_interfaces_fallback()

    def _get_interfaces_fallback(self) -> list[dict]:
        """Fallback using socket for non-Linux systems."""
        try:
            addr = socket.gethostbyname(socket.gethostname())
            if addr and addr != "127.0.0.1":
                return [{"name": "default", "addr": addr}]
        except socket.gaierror:
            pass
        return []

    def _format_response(self, interfaces: list[dict]) -> str:
        """Format a spoken response listing active interfaces."""
        _FRIENDLY_NAMES = {
            "wlan0": "WiFi",
            "wlan1": "WiFi",
            "eth0": "Ethernet",
            "eth1": "Ethernet",
        }

        if len(interfaces) == 1:
            iface = interfaces[0]
            friendly = _FRIENDLY_NAMES.get(iface["name"], iface["name"])
            return f"My {friendly} address is {iface['addr']} on {iface['name']}."

        parts = []
        for iface in interfaces:
            friendly = _FRIENDLY_NAMES.get(iface["name"], iface["name"])
            parts.append(f"{friendly} at {iface['addr']} on {iface['name']}")
        count = len(interfaces)
        connections = "connection" if count == 1 else "connections"
        return (
            f"I have {count} active {connections}: "
            + ", and ".join([", ".join(parts[:-1]), parts[-1]])
            + "."
        )
