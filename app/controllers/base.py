"""
Base Controller Interface.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any
from app.models import Result


class ControllerInterface(ABC):
    """Abstract base class for Controller Providers."""

    @abstractmethod
    def connect(self) -> None:
        """Establish connection to the controller."""
        pass

    @abstractmethod
    def get_sites(self) -> List[Dict[str, Any]]:
        """Retrieve list of sites from the controller."""
        pass

    @abstractmethod
    def get_clients(self, site_id: str) -> Result:
        """Retrieve a normalized client snapshot for a specific site."""
        pass

    @abstractmethod
    def get_client_by_ip(
        self,
        site_id: str,
        client_ip: str,
    ) -> Result:
        """Find one unambiguous client by its normalized IP address."""
        pass

    @abstractmethod
    def authorize(self, site_id: str, client_mac: str) -> Result:
        """Authorize a client on the specified site."""
        pass

    @abstractmethod
    def unauthorize(self, site_id: str, client_mac: str) -> Result:
        """Unauthorize (revoke) a client on the specified site."""
        pass

    @abstractmethod
    def get_client(self, site_id: str, client_mac: str) -> Result:
        """Get status of a specific client (for authStatus verification)."""
        pass
