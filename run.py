#!/usr/bin/env python3
"""
Captive Portal - Main Entry Point.

This is the only file that should be executed directly.
No other module should be run standalone.
"""

import atexit
import inspect
import signal
import sys
import threading

from werkzeug.serving import WSGIRequestHandler
from flask import Flask

from app import create_controller, logger, get_settings
from app.visitor_registry import (
    UnavailableVisitorRegistry,
    create_visitor_registry,
    create_visitor_snapshot_collector,
)
from app.visitor_registry.registry_read_service import (
    VisitorRegistryReadService,
)
from app.visit_lifecycle import create_visit_lifecycle
from app.pending_sessions import create_pending_session_cleaner
from app.observations import create_observation_foundation
from app.analytics import create_analytics_runtime
from app.analytics.api import API_PREFIX
from app.admin_web import create_admin_web_runtime
from app.web.web import create_app, auth_executor, auth_manager


_shutdown_lock = threading.Lock()
_shutdown_completed = False
_public_traffic_worker = None
_visitor_snapshot_collector = None
_visitor_registry = None
_pending_session_cleaner = None
_observation_foundation = None
_visit_lifecycle = None
_analytics_runtime = None
_admin_web_runtime = None


def _safe_access_requestline(requestline: str) -> str:
    """Strip sensitive namespace query strings from production access logs."""
    parts = requestline.split(" ", 2)
    if len(parts) != 3:
        return "<malformed request>"
    method, target, protocol = parts
    path = target.split("?", 1)[0]
    if (
        path == API_PREFIX
        or path.startswith(API_PREFIX + "/")
        or path == "/admin"
        or path.startswith("/admin/")
    ):
        return f"{method} {path} {protocol}"
    return requestline


class SecretSafeRequestHandler(WSGIRequestHandler):
    """Production handler that strips sensitive namespace query values."""

    def log_request(self, code="-", size="-") -> None:
        self.log(
            "info",
            '"%s" %s %s',
            _safe_access_requestline(self.requestline),
            code,
            size,
        )


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

    if _admin_web_runtime is not None:
        try:
            _admin_web_runtime.clear()
        except Exception:
            logger.exception("admin_runtime_clear_failed")

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

    if _observation_foundation is not None:
        try:
            _observation_foundation.stop()
        except Exception:
            logger.exception("observation_foundation_stop_failed")

    if _public_traffic_worker is not None:
        try:
            _public_traffic_worker.stop()
        except Exception:
            logger.exception(
                "Unexpected error while stopping public traffic worker."
            )

    if _visit_lifecycle is not None:
        try:
            _visit_lifecycle.stop_scheduling()
        except Exception:
            logger.exception("visit_lifecycle_scheduling_stop_failed")

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

    if _visit_lifecycle is not None:
        try:
            _visit_lifecycle.stop_accepting()
            _visit_lifecycle.close()
        except Exception:
            logger.exception("visit_lifecycle_stop_failed")

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


def _configure_analytics(app, settings, registry_read_service) -> None:
    """Attach the demand-only Analytics runtime after source composition."""
    global _analytics_runtime

    try:
        _analytics_runtime = create_analytics_runtime(
            settings,
            _observation_foundation,
            _visit_lifecycle,
            registry_read_service,
            logger,
        )
        app.extensions["analytics_runtime"] = _analytics_runtime
        if _analytics_runtime.blueprint is not None:
            app.register_blueprint(_analytics_runtime.blueprint)
    except Exception:
        _analytics_runtime = None
        app.extensions["analytics_runtime"] = None
        logger.exception("analytics_api_runtime_configuration_failed")


def _configure_admin_web(app, settings, registry_read_service) -> None:
    """Attach Admin Web after all existing read boundaries are composed."""
    global _admin_web_runtime

    try:
        source_services = getattr(_analytics_runtime, "_source_services", {})
        _admin_web_runtime = create_admin_web_runtime(
            settings,
            _analytics_runtime,
            registry_read_service,
            source_services.get("visits"),
            source_services.get("observations"),
            logger,
        )
        app.extensions["admin_web_runtime"] = _admin_web_runtime
        if _admin_web_runtime.blueprint is not None:
            app.register_blueprint(_admin_web_runtime.blueprint)
    except Exception:
        _admin_web_runtime = None
        app.extensions["admin_web_runtime"] = None
        logger.exception("admin_runtime_configuration_failed")


def main() -> None:
    """Main application entry point."""
    global _visitor_snapshot_collector, _visitor_registry
    global _pending_session_cleaner, _observation_foundation
    global _visit_lifecycle, _analytics_runtime, _admin_web_runtime

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
    _visit_lifecycle = create_visit_lifecycle(
        settings,
        logger=logger,
    )
    app_kwargs = {
        "controller": controller,
        "visitor_snapshot_collector": _visitor_snapshot_collector,
    }
    if "visit_start_submitter" in inspect.signature(
        create_app
    ).parameters:
        app_kwargs["visit_start_submitter"] = (
            _visit_lifecycle.start_submitter
        )
    app = create_app(**app_kwargs)
    logger.info("Web application created")
    _observation_foundation = create_observation_foundation(
        settings=settings,
        provider=controller,
        telemetry=app.extensions.get("auth_telemetry"),
        logger=logger,
    )
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
        _observation_foundation.start()
    except Exception:
        logger.exception("observation_foundation_start_failed")
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
    registry_read_service = None
    if (
        getattr(_visitor_registry, "available", False)
        and hasattr(_visitor_registry, "repository")
        and hasattr(_visitor_registry, "service")
    ):
        registry_read_service = VisitorRegistryReadService(
            _visitor_registry.repository,
            _visitor_registry.service,
            configured_enabled=True,
        )
    try:
        _visit_lifecycle.start_reconciliation(
            registry_read_service
        )
    except Exception:
        logger.exception("visit_lifecycle_reconciliation_start_failed")
    _configure_analytics(app, settings, registry_read_service)
    _configure_admin_web(app, settings, registry_read_service)
    _start_public_traffic_worker(app)

    host = settings["host"]
    port = settings["port"]
    debug = settings["debug"]

    logger.info(
        f"Starting server on {host}:{port}; debug={debug}"
    )

    try:
        production_options = (
            {"request_handler": SecretSafeRequestHandler}
            if isinstance(app, Flask)
            else {}
        )
        app.run(
            host=host,
            port=port,
            debug=debug,
            use_reloader=False,
            **production_options,
        )
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt caught in main loop.")
    finally:
        shutdown_handler()


if __name__ == "__main__":
    main()
