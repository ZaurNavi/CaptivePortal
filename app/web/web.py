"""
Web Layer - Flask application composition root.

Both Omada External Portal and RFC 8908 CAPPORT login enter the same
server-side AuthSession/AuthWorker flow.
"""

import os
import uuid
from concurrent.futures import ThreadPoolExecutor

from flask import Flask, jsonify, render_template, request
from werkzeug.middleware.proxy_fix import ProxyFix

from app import create_controller, get_settings, logger
from app.auth.manager import (
    AuthSessionManager,
    RetryOutcome,
)
from app.auth.worker import AuthWorker
from app.auth_telemetry import configure_auth_telemetry
from app.auth_telemetry import events as telemetry_events
from app.capport import (
    CapportConfig,
    CapportService,
    create_capport_blueprint,
)
from app.integrations.omada import (
    OmadaWebhookConfig,
    OmadaWebhookJournal,
    OmadaWebhookNormalizedJournal,
    OmadaWebhookProcessor,
    OmadaWebhookReceiver,
    create_omada_webhook_blueprint,
)
from app.integrations.omada.webhook_site_mapping import (
    load_webhook_site_id_mapping,
    log_invalid_webhook_site_id_mapping,
)
from app.portal_counter import (
    PortalCounterRepository,
    PortalCounterService,
)
from app.portal_counter.routes import (
    create_portal_counter_blueprint,
)
from app.public_traffic import (
    PublicTrafficConfig,
    PublicTrafficConfigError,
    PublicTrafficRepository,
    PublicTrafficService,
    PublicTrafficWorker,
    UnavailablePublicTrafficService,
)
from app.public_traffic.reader import PublicTrafficReader
from app.visitor_registry import DISABLED_VISITOR_SNAPSHOT_COLLECTOR
from app.web.portal_entry import (
    PortalClientContext,
    PortalEntryHandler,
)
from app.web.localization import PORTAL_TRANSLATIONS


MAX_WORKERS = 4
_AUTO_COUNTER = object()
_AUTO_TRAFFIC = object()


def _normalize_external_portal_ssid(value):
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        return None
    if "\x00" in value:
        return None
    return value


def _external_portal_ssid(args):
    canonical = _normalize_external_portal_ssid(args.get("ssidName"))
    legacy = _normalize_external_portal_ssid(args.get("ssid"))
    if (
        canonical is not None
        and legacy is not None
        and canonical != legacy
    ):
        return None
    return canonical if canonical is not None else legacy


# One manager and one bounded executor per application process.
# Auth sessions and locks are in memory, so the WSGI process count must
# remain exactly one. The executor threads below are supported.
auth_manager = AuthSessionManager()
auth_executor = ThreadPoolExecutor(
    max_workers=MAX_WORKERS,
    thread_name_prefix="auth_worker_",
)


def create_app(
    portal_counter_service=_AUTO_COUNTER,
    *,
    public_traffic_service=_AUTO_TRAFFIC,
    public_traffic_worker=_AUTO_TRAFFIC,
    controller=None,
    visitor_snapshot_collector=None,
    visit_start_submitter=None,
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

    webhook_config = OmadaWebhookConfig.from_settings(settings)
    app.extensions["omada_webhook_config"] = webhook_config
    webhook_receiver = None
    if webhook_config.enabled:
        webhook_journal = OmadaWebhookJournal(
            webhook_config.log_file
        )
        normalized_journal = OmadaWebhookNormalizedJournal(
            webhook_config.normalized_log_file
        )
        webhook_site_id_mapping = load_webhook_site_id_mapping(
            settings.get("omada_webhook_site_id_map_json", "{}")
        )
        log_invalid_webhook_site_id_mapping(
            logger,
            webhook_site_id_mapping,
        )
        webhook_processor = OmadaWebhookProcessor(
            normalized_journal,
            site_id_mapping=webhook_site_id_mapping,
        )
        webhook_receiver = OmadaWebhookReceiver(
            config=webhook_config,
            journal=webhook_journal,
            logger=logger,
            processor=webhook_processor,
        )
        app.extensions["omada_webhook_journal"] = webhook_journal
        app.extensions[
            "omada_webhook_normalized_journal"
        ] = normalized_journal
        app.extensions[
            "omada_webhook_processor"
        ] = webhook_processor
        app.extensions["omada_webhook_receiver"] = webhook_receiver
    app.register_blueprint(
        create_omada_webhook_blueprint(
            config=webhook_config,
            receiver=webhook_receiver,
            logger=logger,
        )
    )

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

    traffic_config = None
    if public_traffic_service is _AUTO_TRAFFIC:
        try:
            traffic_config = PublicTrafficConfig.from_settings(
                settings
            )
        except PublicTrafficConfigError:
            logger.exception("public_traffic_configuration_error")
            public_traffic_service = (
                UnavailablePublicTrafficService(
                    ssid=_safe_public_traffic_ssid(settings)
                )
            )
            public_traffic_worker = None
        else:
            if not traffic_config.enabled:
                public_traffic_service = (
                    UnavailablePublicTrafficService(
                        ssid=traffic_config.ssid,
                        frontend_refresh_seconds=(
                            traffic_config.frontend_refresh_seconds
                        ),
                    )
                )
                public_traffic_worker = None
            else:
                repository = PublicTrafficRepository(
                    traffic_config.db_path
                )
                service = PublicTrafficService(
                    config=traffic_config,
                    repository=repository,
                    logger=logger,
                )
                public_traffic_service = service
                if service.initialize():
                    if public_traffic_worker is _AUTO_TRAFFIC:
                        public_traffic_worker = PublicTrafficWorker(
                            reader=PublicTrafficReader(
                                source_path=(
                                    traffic_config.source_log_path
                                ),
                                repository=repository,
                                service=service,
                                logger=logger,
                            ),
                            repository=repository,
                            service=service,
                            logger=logger,
                            scan_interval_seconds=(
                                traffic_config.scan_interval_seconds
                            ),
                        )
                else:
                    public_traffic_worker = None
    elif public_traffic_service is None:
        public_traffic_service = UnavailablePublicTrafficService()
        public_traffic_worker = None
    elif public_traffic_worker is _AUTO_TRAFFIC:
        public_traffic_worker = None

    app.extensions[
        "public_traffic_service"
    ] = public_traffic_service
    app.extensions[
        "public_traffic_worker"
    ] = public_traffic_worker
    traffic_refresh_seconds = getattr(
        public_traffic_service,
        "frontend_refresh_seconds",
        60,
    )

    @app.context_processor
    def inject_portal_counter_settings():
        return {
            "portal_counter_visible": counter_visible,
            "public_traffic_frontend_refresh_seconds": (
                traffic_refresh_seconds
            ),
        }

    if counter_api_enabled:
        app.register_blueprint(
            create_portal_counter_blueprint(
                portal_counter_service,
                public_traffic_service,
            )
        )

    if controller is None:
        controller = create_controller()
    if visitor_snapshot_collector is None:
        visitor_snapshot_collector = (
            DISABLED_VISITOR_SNAPSHOT_COLLECTOR
        )
    app.extensions[
        "visitor_snapshot_collector"
    ] = visitor_snapshot_collector
    auth_worker = AuthWorker(
        provider=controller,
        session_manager=auth_manager,
        snapshot_collector=visitor_snapshot_collector,
        visit_start_submitter=visit_start_submitter,
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
        ssid = _external_portal_ssid(request.args)
        redirect_url = request.args.get("redirectUrl")
        radio_id = request.args.get("radioId")

        logger.info(
            "GET / - Portal request: site=%s, mac=%s, ip=%s",
            site_id,
            client_mac,
            client_ip,
        )
        if not site_id or (not client_mac and not client_ip):
            logger.warning(
                    "GET / - Missing required Omada parameters: "
                    "site=%s, mac=%s, ip=%s",
                    site_id,
                    client_mac,
                    client_ip,
            )
            return render_template(
                "portal.html",
                session_id=None,
                redirect_url=redirect_url,
                initial_status="FAILED",
                initial_progress=100,
                initial_state={
                    "state": "FAILED",
                    "status": "FAILED",
                    "retryable": False,
                    "progress": 100,
                    "terminal": True,
                },
                portal_translations=PORTAL_TRANSLATIONS,
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
        was_expired = auth_manager.expire_if_needed(session_id)
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
                    "retryable": False,
                    "current_run_number": 0,
                    "final_reason": "INVALID_SESSION",
                    "expires_at": None,
                    "message": (
                        "Authorization session not found."
                    ),
                }
            ), 404

        if was_expired:
            auth_telemetry.safe_emit_once(
                telemetry_events.SESSION_FINISHED,
                session_id,
                "warning",
                site_id=auth_manager.get(session_id).site_id,
                client_ip=auth_manager.get(session_id).client_ip,
                client_mac=auth_manager.get(session_id).client_mac,
                run_number=snapshot["current_run_number"],
                auth_attempt=snapshot["attempt"],
                final_state="EXPIRED",
                final_reason="SESSION_EXPIRED",
                retryable=False,
            )

        response = jsonify(snapshot)
        response.headers["Cache-Control"] = (
            "no-store, no-cache, must-revalidate, max-age=0"
        )
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response

    @app.route(
        "/auth/session/<session_id>/retry",
        methods=["POST"],
    )
    def retry_auth_session(session_id: str):
        payload = request.get_json(silent=True)
        raw_request_id = (
            payload.get("retry_request_id")
            if isinstance(payload, dict)
            else None
        )
        try:
            if not isinstance(raw_request_id, str):
                raise ValueError
            retry_request_id = str(uuid.UUID(raw_request_id.strip()))
        except (ValueError, AttributeError):
            auth_telemetry.safe_emit(
                telemetry_events.RETRY_REJECTED,
                session_id,
                "warning",
                client_ip=request.remote_addr,
                reason="INVALID_REQUEST",
            )
            return jsonify({
                "session_id": session_id,
                "error": "INVALID_REQUEST",
                "message": (
                    "retry_request_id must be a valid UUID."
                ),
            }), 400

        session = auth_manager.get(session_id)
        if session is None:
            auth_telemetry.safe_emit(
                telemetry_events.RETRY_REQUESTED,
                session_id,
                "warning",
                retry_request_id=retry_request_id,
                client_ip=request.remote_addr,
                run_number=0,
                auth_attempt=0,
            )
            auth_telemetry.safe_emit(
                telemetry_events.RETRY_REJECTED,
                session_id,
                "warning",
                retry_request_id=retry_request_id,
                client_ip=request.remote_addr,
                reason="SESSION_NOT_FOUND",
                run_number=0,
                auth_attempt=0,
            )
            return jsonify({
                "session_id": session_id,
                "error": "SESSION_NOT_FOUND",
            }), 404

        if not auth_manager.owns_session(
            session,
            request.remote_addr,
        ):
            auth_telemetry.safe_emit(
                telemetry_events.RETRY_REJECTED,
                session_id,
                "warning",
                retry_request_id=retry_request_id,
                client_ip=request.remote_addr,
                client_mac=session.client_mac,
                run_number=session.current_run_number,
                auth_attempt=session.attempt,
                reason="SESSION_OWNERSHIP_MISMATCH",
            )
            return jsonify({
                "session_id": session_id,
                "error": "SESSION_OWNERSHIP_MISMATCH",
            }), 403

        auth_telemetry.safe_emit(
            telemetry_events.RETRY_REQUESTED,
            session_id,
            "info",
            retry_request_id=retry_request_id,
            client_ip=session.client_ip,
            client_mac=session.client_mac,
            run_number=session.current_run_number,
            auth_attempt=session.attempt,
            previous_final_state=session.status.value,
            previous_final_reason=session.final_reason,
        )

        preparation = auth_manager.prepare_retry(
            session_id,
            retry_request_id,
        )
        session = preparation.session or session
        snapshot = auth_manager.snapshot(session)

        if preparation.outcome == RetryOutcome.DUPLICATE:
            response = dict(snapshot)
            response.update({
                "duplicate": True,
                "request_run_number": (
                    preparation.request_run_number
                ),
            })
            return jsonify(response), 200

        if preparation.outcome == RetryOutcome.ACTIVE:
            auth_telemetry.safe_emit(
                telemetry_events.RETRY_REJECTED,
                session_id,
                "info",
                retry_request_id=retry_request_id,
                client_ip=session.client_ip,
                client_mac=session.client_mac,
                run_number=session.current_run_number,
                auth_attempt=session.attempt,
                reason="RUN_ALREADY_ACTIVE",
            )
            response = dict(snapshot)
            response["duplicate"] = False
            return jsonify(response), 200

        if preparation.outcome == RetryOutcome.EXPIRED:
            auth_telemetry.safe_emit(
                telemetry_events.RETRY_REJECTED,
                session_id,
                "warning",
                retry_request_id=retry_request_id,
                client_ip=session.client_ip,
                client_mac=session.client_mac,
                run_number=session.current_run_number,
                auth_attempt=session.attempt,
                reason="SESSION_EXPIRED",
            )
            auth_telemetry.safe_emit_once(
                telemetry_events.SESSION_FINISHED,
                session_id,
                "warning",
                client_ip=session.client_ip,
                client_mac=session.client_mac,
                run_number=session.current_run_number,
                auth_attempt=session.attempt,
                final_state="EXPIRED",
                final_reason="SESSION_EXPIRED",
                retryable=False,
            )
            return jsonify(snapshot), 410

        if preparation.outcome == RetryOutcome.NOT_RETRYABLE:
            reason = (
                "SESSION_ALREADY_AUTHORIZED"
                if session.authorized
                else "STATE_NOT_RETRYABLE"
            )
            auth_telemetry.safe_emit(
                telemetry_events.RETRY_REJECTED,
                session_id,
                "warning",
                retry_request_id=retry_request_id,
                client_ip=session.client_ip,
                client_mac=session.client_mac,
                run_number=session.current_run_number,
                auth_attempt=session.attempt,
                reason=reason,
            )
            return jsonify(snapshot), 409

        if preparation.outcome == RetryOutcome.NOT_FOUND:
            return jsonify({
                "session_id": session_id,
                "error": "SESSION_NOT_FOUND",
            }), 404

        started, failure_reason, failure_message = (
            portal_entry_handler.submit_worker(
                session,
                preparation.run_number,
                preparation.run_token,
            )
        )
        snapshot = auth_manager.snapshot(session)
        if not started:
            auth_telemetry.safe_emit(
                telemetry_events.RETRY_FAILED,
                session_id,
                (
                    "warning"
                    if snapshot["retryable"]
                    else "error"
                ),
                retry_request_id=retry_request_id,
                client_ip=session.client_ip,
                client_mac=session.client_mac,
                run_number=preparation.run_number,
                auth_attempt=0,
                final_state=snapshot["state"],
                final_reason=failure_reason,
                retryable=snapshot["retryable"],
                error=failure_message,
            )
            return jsonify(snapshot), (
                503
                if failure_reason == "WORKER_START_FAILED"
                else 500
            )

        response = dict(snapshot)
        response["duplicate"] = False
        return jsonify(response), 202

    @app.route("/success", methods=["GET"])
    def success():
        return render_template("success.html")

    return app


def _safe_public_traffic_ssid(settings: dict) -> str:
    value = settings.get("public_traffic_ssid", "")
    return value.strip() if isinstance(value, str) else ""
