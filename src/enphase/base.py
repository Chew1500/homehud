"""Abstract base class for Enphase IQ Gateway clients."""

from abc import ABC, abstractmethod


class BaseEnphaseClient(ABC):
    """Common interface for mock and real Enphase gateway clients."""

    @abstractmethod
    def get_production(self) -> dict:
        """Get current production/consumption data.

        Returns:
            Dict with keys: production_w, consumption_w, net_w,
            production_wh, consumption_wh
        """
        ...

    @abstractmethod
    def get_inverters(self) -> list[dict]:
        """Get per-inverter production data.

        Returns:
            List of dicts with keys: serial, watts, max_watts, last_report
        """
        ...

    @abstractmethod
    def check_health(self) -> bool:
        """Check if the gateway is reachable.

        Returns:
            True if gateway responds, False otherwise.
        """
        ...

    def close(self) -> None:
        """Clean up resources. Override if needed."""
        pass
