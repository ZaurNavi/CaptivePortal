"""
Logging module.

Provides a unified logger for the entire application.
No print() statements allowed - use logger instead.
"""

import logging
from app.config import LOG_LEVEL


def setup_logger(name: str = "captivportal") -> logging.Logger:
    """
    Create and configure a logger instance.
    
    Args:
        name: Logger name (default: "captivportal")
    
    Returns:
        logging.Logger: Configured logger instance.
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, LOG_LEVEL.upper(), logging.INFO))
    
    # Avoid adding multiple handlers if logger already exists
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "%(levelname)-7s %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    
    return logger


# Global logger instance
logger = setup_logger()