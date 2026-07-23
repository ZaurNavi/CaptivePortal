#!/usr/bin/env python3
"""
Captive Portal - Main Entry Point.

This is the only file that should be executed directly.
All other modules are imported and used through this entry point.
"""

from app.logger import logger
from app.settings import settings


def main():
    """Main application entry point."""
    logger.info("Starting Captive Portal")
    
    # Load configuration
    settings.load()
    logger.info("Configuration loaded")
    
    # Logger is already initialized via import
    logger.info("Logger initialized")
    
    # Platform is ready for v1.0
    logger.info("Platform ready")


if __name__ == "__main__":
    main()
