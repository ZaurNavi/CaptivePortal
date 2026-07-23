#!/usr/bin/env python3
"""
Captive Portal - Main Entry Point.

This is the only file that should be executed directly.
No other module should be run standalone.
"""

from app import logger, get_settings, create_controller
from app.models import Result
from app.engine import PortalEngine


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
    
    # Demonstrate Portal Engine (v1.0)
    logger.info("Portal Engine initialized")
    
    engine = PortalEngine(controller)
    logger.debug(f"Portal Engine created with controller: {type(controller).__name__}")
    
    # Test authorization flow through Engine
    test_site_id = "test_site"
    test_client_mac = "AA-BB-CC-DD-EE-FF"
    
    logger.info(f"Testing authorize_client for site={test_site_id}, mac={test_client_mac}")
    result = engine.authorize_client(test_site_id, test_client_mac)
    
    logger.info(f"Authorization result: {result.to_dict()}")
    
    # Test validation with empty parameters
    logger.info("Testing validation with empty site_id")
    invalid_result = engine.authorize_client("", test_client_mac)
    logger.info(f"Validation result: {invalid_result.to_dict()}")
    
    logger.info("Platform ready")


if __name__ == "__main__":
    main()