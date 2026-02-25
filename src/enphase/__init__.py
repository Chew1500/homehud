"""Enphase solar monitoring — client factory."""

from enphase.base import BaseEnphaseClient


def get_enphase_client(config: dict) -> BaseEnphaseClient:
    """Create an Enphase client based on configuration.

    Args:
        config: Application config dict. Uses 'enphase_mode' to select backend.

    Returns:
        MockEnphaseClient for "mock" mode, EnphaseClient for "live" mode.
    """
    mode = config.get("enphase_mode", "mock")

    if mode == "live":
        from enphase.client import EnphaseClient
        return EnphaseClient(config)

    from enphase.mock_client import MockEnphaseClient
    return MockEnphaseClient(config)
