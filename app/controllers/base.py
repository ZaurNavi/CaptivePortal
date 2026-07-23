"""
Base Controller Interface.

Defines the contract for all controller providers.
No implementation details here, only the public API.
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
    def get_clients(self, site_id: str) -> List[Dict[str, Any]]:
        """Retrieve list of clients for a specific site."""
        pass

    @abstractmethod
    def authorize(self, site_id: str, client_mac: str) -> Result:
        """Authorize a client on the specified site."""
        pass

    @abstractmethod
    def unauthorize(self, site_id: str, client_mac: str) -> Result:
        """Unauthorize (revoke) a client on the specified site."""
        pass
