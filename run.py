#!/usr/bin/env python3
"""
Captive Portal - Main Entry Point.

This is the only file that should be executed directly.
No other module should be run standalone.
"""

from app import logger, get_settings, create_controller


def main():
    """Main application entry point."""
    logger.info("Starting Captive Portal")
    
    # Load configuration
    settings = get_settings()
    logger.info("Configuration loaded")
    
    # Initialize logger (already done via import, but confirming)
    logger.info("Logger initialized")
    
    # Create controller provider via factory
    controller = create_controller()
    logger.debug(f"Controller provider created: {type(controller).__name__}")
    
    logger.info("Platform ready")


if __name__ == "__main__":
    main()