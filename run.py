#!/usr/bin/env python3
"""
Captive Portal - Main Entry Point.

This is the only file that should be executed directly.
No other module should be run standalone.
"""

import atexit
import signal
import sys
import threading

from app import logger, get_settings
from app.web.web import create_app, auth_executor


_shutdown_lock = threading.Lock()
_shutdown_completed = False


def shutdown_handler() -> None:
    """
    Gracefully shut down background workers.

    The handler is idempotent: repeated calls from signal handlers,
    finally blocks and atexit do not stop the executor more than once.
    """
    global _shutdown_completed

    with _shutdown_lock:
        if _shutdown_completed:
            return

        _shutdown_completed = True

    logger.info("Shutting down authentication worker executor...")

    try:
        auth_executor.shutdown(
            wait=True,
            cancel_futures=False
        )
        logger.info(
            "Authentication worker executor stopped successfully."
        )
    except Exception:
        logger.exception(
            "Unexpected error while shutting down authentication executor."
        )


def signal_handler(signum, frame) -> None:
    """
    Handle operating-system termination signals.
    """
    logger.info(
        f"Received signal {signum}. Initiating graceful shutdown..."
    )

    shutdown_handler()
    raise SystemExit(0)


def main() -> None:
    """Main application entry point."""
    logger.info("Starting Captive Portal")

    atexit.register(shutdown_handler)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    settings = get_settings()
    logger.info("Configuration loaded")

    app = create_app()
    logger.info("Web application created")

    host = settings["host"]
    port = settings["port"]
    debug = settings["debug"]

    logger.info(
        f"Starting server on {host}:{port}; debug={debug}"
    )

    try:
        app.run(
            host=host,
            port=port,
            debug=debug,
            use_reloader=False
        )
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt caught in main loop.")
    finally:
        shutdown_handler()


if __name__ == "__main__":
    main()
