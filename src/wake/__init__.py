"""Wake word detection — factory function selects mock or real backend."""

from wake.base import BaseWakeWord


def get_wake(config: dict) -> BaseWakeWord:
    """Create a wake word detector based on config."""
    mode = config.get("wake_mode", "mock")
    if mode == "oww":
        from wake.oww_wake import OWWWakeWord

        return OWWWakeWord(config)
    else:
        from wake.mock_wake import MockWakeWord

        return MockWakeWord(config)
