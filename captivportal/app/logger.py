"""
Logger initialization for Captive Portal.

Provides a single logger instance for the entire application.
No print() statements allowed - use logger methods only.
"""

import logging
from app.config import LOG_LEVEL


def get_logger(name: str = "captivportal") -> logging.Logger:
    """
    Create and configure a logger instance.
    
    Args:
        name: Logger name (default: "captivportal")
    
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, LOG_LEVEL.upper(), logging.INFO))
    
    # Clear existing handlers to avoid duplicates
    if logger.handlers:
        logger.handlers.clear()
    
    # Create console handler
    handler = logging.StreamHandler()
    handler.setLevel(getattr(logging, LOG_LEVEL.upper(), logging.INFO))
    
    # Create formatter
    formatter = logging.Formatter(
        "%(levelname)s  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    handler.setFormatter(formatter)
    
    # Add handler to logger
    logger.addHandler(handler)
    
    return logger


# Single logger instance for the application
logger = get_logger()
