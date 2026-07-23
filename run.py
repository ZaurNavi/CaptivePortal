#!/usr/bin/env python3
"""
Captive Portal - Main Entry Point.

This is the only file that should be executed directly.
No other module should be run standalone.
"""

from app import logger, get_settings, create_controller
from app.models import Result


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
    
    # Demonstrate Result Model (v1.2)
    logger.info("Result Model initialized")
    
    # Test successful result
    r_ok = Result.ok(message="Platform ready")
    logger.debug(f"Success result: {r_ok.to_dict()}")
    
    # Test failed result
    r_fail = Result.fail(error="TEST_ERROR", message="Something happened")
    logger.debug(f"Error result: {r_fail.to_dict()}")
    
    logger.info("Platform ready")


if __name__ == "__main__":
    main()