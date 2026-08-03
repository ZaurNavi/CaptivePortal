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

from app import create_controller, logger, get_settings
from app.visitor_registry import (
    UnavailableVisitorRegistry,
    create_visitor_registry,
    create_visitor_snapshot_collector,
)
from app.pending_sessions import create_pending_session_cleaner
from app.web.web import create_app, auth_executor, auth_manager


_shutdown_lock = threading.Lock()
_shutdown_completed = False
_public_traffic_worker = None
_visitor_snapshot_collector = None
_visitor_registry = None
_pending_session_cleaner = None


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

    if _pending_session_cleaner is not None:
        try:
            config = getattr(
                _pending_session_cleaner,
                "config",
                None,
            )
            timeout_seconds = getattr(
                config,
                "shutdown_timeout_seconds",
                20.0,
            )
            _pending_session_cleaner.stop(timeout_seconds)
        except Exception:
            logger.exception("pending_session_cleaner_stop_failed")

    if _public_traffic_worker is not None:
        try:
            _public_traffic_worker.stop()
        except Exception:
            logger.exception(
                "Unexpected error while stopping public traffic worker."
            )

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

    if _visitor_snapshot_collector is not None:
        try:
            _visitor_snapshot_collector.stop_accepting()
            config = getattr(
                _visitor_snapshot_collector,
                "config",
                None,
            )
            timeout_seconds = getattr(
                config,
                "shutdown_timeout_seconds",
                90.0,
            )
            _visitor_snapshot_collector.drain_and_stop(
                timeout_seconds
            )
        except Exception:
            logger.exception("visitor_snapshot_stop_failed")

    if _visitor_registry is not None:
        try:
            config = getattr(_visitor_registry, "config", None)
            timeout_seconds = getattr(
                config,
                "shutdown_timeout_seconds",
                10.0,
            )
            _visitor_registry.stop(
                timeout_seconds,
                final_scan=True,
            )
        except Exception:
            logger.exception("visitor_registry_stop_failed")


def signal_handler(signum, frame) -> None:
    """
    Handle operating-system termination signals.
    """
    logger.info(
        f"Received signal {signum}. Initiating graceful shutdown..."
    )

    shutdown_handler()
    raise SystemExit(0)


def _start_public_traffic_worker(app) -> None:
    global _public_traffic_worker

    _public_traffic_worker = app.extensions.get(
        "public_traffic_worker"
    )
    if _public_traffic_worker is None:
        return
    try:
        _public_traffic_worker.start()
    except Exception:
        logger.exception("public_traffic_counter_start_failed")
        traffic_service = app.extensions.get(
            "public_traffic_service"
        )
        if traffic_service is not None:
            try:
                traffic_service.available = False
            except Exception:
                logger.exception(
                    "public_traffic_counter_disable_failed"
                )
        _public_traffic_worker = None


def main() -> None:
    """Main application entry point."""
    global _visitor_snapshot_collector, _visitor_registry
    global _pending_session_cleaner

    logger.info("Starting Captive Portal")

    atexit.register(shutdown_handler)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    settings = get_settings()
    logger.info("Configuration loaded")

    controller = create_controller()
    _visitor_snapshot_collector = create_visitor_snapshot_collector(
        settings=settings,
        provider=controller,
    )
    app = create_app(
        controller=controller,
        visitor_snapshot_collector=(
            _visitor_snapshot_collector
        ),
    )
    logger.info("Web application created")
    _pending_session_cleaner = create_pending_session_cleaner(
        settings=settings,
        provider=controller,
        auth_manager=auth_manager,
        telemetry=app.extensions.get("auth_telemetry"),
    )
    try:
        _pending_session_cleaner.start()
    except Exception:
        logger.exception("pending_session_cleaner_start_failed")
    try:
        _visitor_snapshot_collector.start()
    except Exception:
        logger.exception("visitor_snapshot_start_failed")
    try:
        _visitor_registry = create_visitor_registry(settings)
    except Exception:
        logger.exception("visitor_registry_create_failed")
        _visitor_registry = UnavailableVisitorRegistry()
    try:
        _visitor_registry.start()
    except Exception:
        logger.exception("visitor_registry_start_failed")
    _start_public_traffic_worker(app)

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
