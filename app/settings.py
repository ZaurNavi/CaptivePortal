"""
Settings module.

Currently reads settings from config.py.
Designed to be extended in future versions to read from files or environment.
"""

from app.config import HOST, PORT, DEBUG, VERIFY_SSL, LOG_LEVEL
from app.logger import logger


def get_settings() -> dict:
    """
    Retrieve application settings.
    
    Returns:
        dict: Dictionary containing all application settings.
    """
    logger.debug("Loading settings from config")
    return {
        "host": HOST,
        "port": PORT,
        "debug": DEBUG,
        "verify_ssl": VERIFY_SSL,
        "log_level": LOG_LEVEL,
    }