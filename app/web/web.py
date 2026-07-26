"""
Web Layer - Flask application composition root.

Both Omada External Portal and RFC 8908 CAPPORT login enter the same
server-side AuthSession/AuthWorker flow.
"""

import os
from concurrent.futures import ThreadPoolExecutor

from flask import Flask, jsonify, render_template, request
from werkzeug.middleware.proxy_fix import ProxyFix

from app import create_controller, get_settings, logger
from app.auth.manager import AuthSessionManager
from app.auth.worker import AuthWorker
from app.auth_telemetry import configure_auth_telemetry
from app.capport import (
    CapportConfig,
    CapportService,
    create_capport_blueprint,
)
from app.portal_counter import (
    PortalCounterRepository,
    PortalCounterService,
)
from app.portal_counter.routes import (
    create_portal_counter_blueprint,
)
from app.web.portal_entry import (
    PortalClientContext,
    PortalEntryHandler,
)


MAX_WORKERS = 4
_AUTO_COUNTER = object()


# One manager and one bounded executor per application process.
auth_manager = AuthSessionManager()
auth_executor = ThreadPoolExecutor(
    max_workers=MAX_WORKERS,
    thread_name_prefix="auth_worker_",
)


def create_app(
    portal_counter_service=_AUTO_COUNTER,
) -> Flask:
    """Create and configure the Flask application."""
    template_dir = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "templates")
    )
    app = Flask(__name__, template_folder=template_dir)

    # Exactly one trusted local Nginx hop. Flask is bound to loopback.
    app.wsgi_app = ProxyFix(
        app.wsgi_app,
        x_for=1,
        x_proto=1,
        x_host=1,
        x_port=1,
    )

    settings = get_settings()
    auth_telemetry = configure_auth_telemetry(settings)
    app.extensions["auth_telemetry"] = auth_telemetry

    if portal_counter_service is _AUTO_COUNTER:
        portal_counter_service = None
        if settings["portal_counter_enabled"]:
            portal_counter_service = PortalCounterService(
                repository=PortalCounterRepository(
                    settings["portal_counter_db_path"]
                ),
                timezone_name=settings["portal_counter_timezone"],
                logger=logger,
            )
            portal_counter_service.initialize()

    counter_configured = (
        settings["portal_counter_enabled"]
        and portal_counter_service is not None
    )
    counter_recording_enabled = (
        counter_configured and portal_counter_service.available
    )
    counter_api_enabled = (
        counter_configured
        and settings["portal_counter_api_enabled"]
    )
    counter_visible = (
        counter_recording_enabled
        and settings["portal_counter_api_enabled"]
    )
    app.extensions["portal_counter_service"] = portal_counter_service

    @app.context_processor
    def inject_portal_counter_settings():
        return {"portal_counter_visible": counter_visible}

    if counter_api_enabled:
        app.register_blueprint(
            create_portal_counter_blueprint(
                portal_counter_service
            )
        )

    controller = create_controller()
    auth_worker = AuthWorker(
        provider=controller,
        session_manager=auth_manager,
    )
    portal_entry_handler = PortalEntryHandler(
        session_manager=auth_manager,
        auth_worker=auth_worker,
        executor=auth_executor,
        auth_telemetry=auth_telemetry,
        portal_counter_service=portal_counter_service,
        counter_recording_enabled=counter_recording_enabled,
    )
    app.extensions["portal_entry_handler"] = portal_entry_handler

    if settings.get("capport_enabled", False):
        capport_config = CapportConfig.from_settings(settings)
        capport_service = CapportService(
            controller=controller,
            config=capport_config,
            telemetry=auth_telemetry,
        )
        app.extensions["capport_service"] = capport_service
        app.register_blueprint(
            create_capport_blueprint(
                service=capport_service,
                portal_entry_handler=portal_entry_handler,
                config=capport_config,
                telemetry=auth_telemetry,
            )
        )

    @app.route("/", methods=["GET"])
    def index():
        """Existing Omada External Portal entry contract."""
        client_mac = request.args.get("clientMac")
        site_id = request.args.get("site")
        client_ip = request.args.get("clientIp") or request.remote_addr
        ap_mac = request.args.get("apMac")
        ssid = request.args.get("ssid")
        redirect_url = request.args.get("redirectUrl")
        radio_id = request.args.get("radioId")

        logger.info(
            "GET / - Portal request: site=%s, mac=%s, ip=%s",
            site_id,
            client_mac,
            client_ip,
        )
        if not site_id or not client_mac:
            logger.warning(
                "GET / - Missing required Omada parameters: "
                "site=%s, mac=%s",
                site_id,
                client_mac,
            )
            return render_template(
                "portal.html",
                session_id=None,
                redirect_url=redirect_url,
                initial_status="FAILED",
                initial_progress=100,
                error_message=(
                    "Не удалось определить параметры подключения."
                ),
            ), 400

        context = PortalClientContext(
            site_id=site_id,
            client_mac=client_mac,
            client_ip=client_ip,
            ap_mac=ap_mac,
            ssid=ssid,
            redirect_url=redirect_url,
            radio_id=radio_id,
        )
        return portal_entry_handler.open_portal(context)

    @app.route(
        "/auth/session/<session_id>",
        methods=["GET"],
    )
    def get_auth_session(session_id: str):
        """
        Return AuthSession state without creating or extending a session.
        """
        snapshot = auth_manager.snapshot(session_id)
        if snapshot is None:
            return jsonify(
                {
                    "sessionId": session_id,
                    "status": "FAILED",
                    "attempt": 0,
                    "progress": 100,
                    "authorized": False,
                    "terminal": True,
                    "message": (
                        "Authorization session not found."
                    ),
                }
            ), 404

        response = jsonify(snapshot)
        response.headers["Cache-Control"] = (
            "no-store, no-cache, must-revalidate, max-age=0"
        )
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response

    @app.route("/success", methods=["GET"])
    def success():
        return render_template("success.html")

    return app
