"""Mock Enphase client for local development."""

import logging
import random

from enphase.base import BaseEnphaseClient

log = logging.getLogger("home-hud.enphase.mock")


class MockEnphaseClient(BaseEnphaseClient):
    """Returns canned solar production data for development."""

    def __init__(self, config: dict):
        self._config = config

    def get_production(self) -> dict:
        log.info("Mock: returning canned production data")
        production_w = 4200.0 + random.uniform(-200, 200)
        consumption_w = 1800.0 + random.uniform(-100, 100)
        return {
            "production_w": round(production_w, 1),
            "consumption_w": round(consumption_w, 1),
            "net_w": round(production_w - consumption_w, 1),
            "production_wh": 18500.0,
            "consumption_wh": 12300.0,
        }

    def get_inverters(self) -> list[dict]:
        log.info("Mock: returning canned inverter data")
        inverters = []
        for i in range(24):
            inverters.append({
                "serial": f"12210{i:04d}",
                "watts": 175 + random.randint(-10, 10),
                "max_watts": 295,
                "last_report": "2026-02-24T12:00:00",
            })
        return inverters

    def check_health(self) -> bool:
        return True
