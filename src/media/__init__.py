"""Media library clients — Sonarr (TV) and Radarr (movies) factories.

Both are opt-in: returns None when mode is empty (unconfigured).
"""

from __future__ import annotations

from media.base import BaseRadarrClient, BaseSonarrClient


def get_sonarr_client(config: dict) -> BaseSonarrClient | None:
    """Create a Sonarr client based on configuration.

    Args:
        config: Application config dict. Uses 'sonarr_mode' to select backend.

    Returns:
        None if mode is empty (opt-in, unconfigured).
        MockSonarrClient for "mock" mode, SonarrClient for "live" mode.
    """
    mode = config.get("sonarr_mode", "")
    if not mode:
        return None

    if mode == "live":
        from media.sonarr_client import SonarrClient
        return SonarrClient(config)

    from media.mock_sonarr import MockSonarrClient
    return MockSonarrClient(config)


def get_radarr_client(config: dict) -> BaseRadarrClient | None:
    """Create a Radarr client based on configuration.

    Args:
        config: Application config dict. Uses 'radarr_mode' to select backend.

    Returns:
        None if mode is empty (opt-in, unconfigured).
        MockRadarrClient for "mock" mode, RadarrClient for "live" mode.
    """
    mode = config.get("radarr_mode", "")
    if not mode:
        return None

    if mode == "live":
        from media.radarr_client import RadarrClient
        return RadarrClient(config)

    from media.mock_radarr import MockRadarrClient
    return MockRadarrClient(config)
