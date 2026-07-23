"""
Controller Factory.

Provides a single point of creation for controller providers.
Ensures loose coupling by hiding concrete implementation details.
"""

from app.controllers.base import ControllerInterface
from app.controllers.omada import OmadaProvider
from app.logger import logger


def create_controller() -> ControllerInterface:
    """
    Create and return a controller provider instance.
    
    Currently returns OmadaProvider by default.
    In the future, this can be configured to return different providers
    (UniFi, MikroTik, Mock, etc.) without changing the calling code.
    
    Returns:
        ControllerInterface: An instance of a controller provider.
    """
    logger.info("Creating controller provider...")
    controller = OmadaProvider()
    logger.debug("Controller provider created successfully")
    return controller
