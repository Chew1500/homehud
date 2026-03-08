"""Jellyfin media server client — opt-in via JELLYFIN_MODE.

Returns None when mode is empty (unconfigured).
"""

from __future__ import annotations

from jellyfin.base import BaseJellyfinClient


def get_jellyfin_client(config: dict) -> BaseJellyfinClient | None:
    """Create a Jellyfin client based on configuration.

    Args:
        config: Application config dict. Uses 'jellyfin_mode' to select backend.

    Returns:
        None if mode is empty (opt-in, unconfigured).
        MockJellyfinClient for "mock" mode, JellyfinClient for "live" mode.
    """
    mode = config.get("jellyfin_mode", "")
    if not mode:
        return None

    if mode == "live":
        from jellyfin.client import JellyfinClient
        return JellyfinClient(config)

    from jellyfin.mock_client import MockJellyfinClient
    return MockJellyfinClient(config)
