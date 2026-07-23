#!/usr/bin/env python3
"""
Captive Portal - Main Entry Point.

This is the only file that should be executed directly.
No other module should be run standalone.
"""

from app import logger, get_settings
from app.web.web import create_app


def main():
    """Main application entry point."""
    logger.info("Starting Captive Portal")

    # Load configuration
    settings = get_settings()
    logger.info("Configuration loaded")

    # Create Flask application
    app = create_app()
    logger.info("Web application created")

    # Run Flask server
    logger.info(f"Starting server on {settings['host']}:{settings['port']}")
    app.run(
        host=settings["host"],
        port=settings["port"],
        debug=settings["debug"]
    )


if __name__ == "__main__":
    main()
