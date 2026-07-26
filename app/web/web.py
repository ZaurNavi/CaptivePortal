"""
Web Layer - Flask Application.

GET portal request creates or reuses a server-side AuthSession.
The browser only displays the session state and never controls
the Omada authorization process.
"""

import logging
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from flask import Flask, jsonify, render_template, request

from app import create_controller, get_settings, logger
from app.auth.manager import AuthSessionManager
from app.auth.session import AuthStatus
from app.auth.worker import AuthWorker, log_auth_event
from app.auth_telemetry import configure_auth_telemetry
from app.auth_telemetry import events as telemetry_events
from app.portal_counter import (
    PortalCounterRepository,
    PortalCounterService,
)
from app.portal_counter.routes import (
    create_portal_counter_blueprint,
)


MAX_WORKERS = 4
_AUTO_COUNTER = object()


# Один менеджер и один executor на процесс приложения.
auth_manager = AuthSessionManager()

auth_executor = ThreadPoolExecutor(
    max_workers=MAX_WORKERS,
    thread_name_prefix="auth_worker_",
)


def create_app(
    portal_counter_service=_AUTO_COUNTER,
) -> Flask:
    """Создать и настроить Flask-приложение."""

    template_dir = os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            "templates",
        )
    )

    app = Flask(
        __name__,
        template_folder=template_dir,
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
                timezone_name=(
                    settings["portal_counter_timezone"]
                ),
                logger=logger,
            )
            portal_counter_service.initialize()

    counter_configured = (
        settings["portal_counter_enabled"]
        and portal_counter_service is not None
    )
    counter_recording_enabled = (
        counter_configured
        and portal_counter_service.available
    )
    counter_api_enabled = (
        counter_configured
        and settings["portal_counter_api_enabled"]
    )
    counter_visible = (
        counter_recording_enabled
        and settings["portal_counter_api_enabled"]
    )
    app.extensions["portal_counter_service"] = (
        portal_counter_service
    )

    @app.context_processor
    def inject_portal_counter_settings():
        return {
            "portal_counter_visible": counter_visible,
        }

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
    executor = auth_executor

    @app.route("/", methods=["GET"])
    def index():
        """
        Основной маршрут Captive Portal.

        Первый GET:
        - получает параметры Omada;
        - создаёт AuthSession;
        - закрепляет за ней worker;
        - помещает worker в общий executor;
        - возвращает страницу progress bar.

        Повторный GET активной сессии:
        - возвращает существующую AuthSession;
        - не запускает второй worker.
        """

        client_mac = request.args.get("clientMac")
        site_id = request.args.get("site")

        client_ip = (
            request.args.get("clientIp")
            or request.remote_addr
        )

        ap_mac = request.args.get("apMac")
        ssid = request.args.get("ssid")
        redirect_url = request.args.get("redirectUrl")
        radio_id = request.args.get("radioId")

        logger.info(
            "GET / - Portal request: "
            f"site={site_id}, "
            f"mac={client_mac}, "
            f"ip={client_ip}"
        )

        if not site_id or not client_mac:
            logger.warning(
                "GET / - Missing required Omada parameters: "
                f"site={site_id}, mac={client_mac}"
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

        try:
            session, created = auth_manager.create_or_get(
                site_id=site_id,
                client_mac=client_mac,
                client_ip=client_ip,
                ap_mac=ap_mac,
                ssid=ssid,
                redirect_url=redirect_url,
                radio_id=radio_id,
            )

            if created and counter_recording_enabled:
                try:
                    portal_counter_service.record_open(
                        session_id=session.session_id,
                        opened_at=datetime.now(timezone.utc),
                    )
                except Exception:
                    logger.exception(
                        "portal_counter.write_failed "
                        "session_id=%s",
                        session.session_id,
                    )

            if created:
                log_auth_event(
                    telemetry_events.SESSION_CREATED,
                    session,
                    state=session.status.value,
                    created_at=session.created_at,
                    client_mac=session.client_mac,
                    client_ip=session.client_ip,
                    site_id=session.site_id,
                )
            else:
                log_auth_event(
                    telemetry_events.SESSION_REUSED,
                    session,
                    state=session.status.value,
                    client_mac=session.client_mac,
                    client_ip=session.client_ip,
                    site_id=session.site_id,
                    reuse_reason=(
                        "active_session"
                        if session.is_active()
                        else "retry_cooldown"
                    ),
                )

            if created:
                worker_claimed = auth_manager.claim_worker(
                    session
                )

                if not worker_claimed:
                    auth_manager.fail(
                        session,
                        error=(
                            "Unable to claim authorization worker."
                        ),
                    )

                    auth_telemetry.safe_emit_once(
                        telemetry_events.SESSION_FINISHED,
                        session.session_id,
                        "error",
                        site_id=session.site_id,
                        client_mac=session.client_mac,
                        client_ip=session.client_ip,
                        final_state=session.status.value,
                        final_reason="INTERNAL_ERROR",
                        duration_ms=0,
                        readiness_checks=0,
                        auth_attempts=0,
                    )

                    return render_template(
                        "portal.html",
                        session_id=session.session_id,
                        redirect_url=session.redirect_url,
                        initial_status=session.status.value,
                        initial_progress=session.progress,
                        error_message=(
                            "Не удалось запустить процесс подключения."
                        ),
                    ), 500

                try:
                    executor.submit(
                        auth_worker.process,
                        session.session_id,
                    )

                except Exception as exc:
                    auth_manager.fail(
                        session,
                        error=(
                            f"Worker submission failed: {exc}"
                        ),
                    )

                    auth_manager.mark_worker_finished(
                        session
                    )

                    auth_telemetry.safe_emit_once(
                        telemetry_events.SESSION_FINISHED,
                        session.session_id,
                        "error",
                        site_id=session.site_id,
                        client_mac=session.client_mac,
                        client_ip=session.client_ip,
                        final_state=session.status.value,
                        final_reason="INTERNAL_ERROR",
                        duration_ms=0,
                        readiness_checks=0,
                        auth_attempts=0,
                        error=str(exc),
                    )

                    return render_template(
                        "portal.html",
                        session_id=session.session_id,
                        redirect_url=session.redirect_url,
                        initial_status=session.status.value,
                        initial_progress=session.progress,
                        error_message=(
                            "Системная ошибка запуска подключения."
                        ),
                    ), 500

            snapshot = auth_manager.snapshot(session)

            if snapshot is None:
                return render_template(
                    "portal.html",
                    session_id=None,
                    redirect_url=redirect_url,
                    initial_status="FAILED",
                    initial_progress=100,
                    error_message=(
                        "Сессия подключения не найдена."
                    ),
                ), 500

            return render_template(
                "portal.html",
                session_id=session.session_id,
                redirect_url=session.redirect_url,
                initial_status=snapshot["status"],
                initial_progress=snapshot["progress"],
                error_message=None,
            )

        except ValueError as exc:
            logger.warning(
                "GET / - Invalid client parameters: "
                f"site={site_id}, "
                f"mac={client_mac}, "
                f"error={exc}"
            )

            return render_template(
                "portal.html",
                session_id=None,
                redirect_url=redirect_url,
                initial_status="FAILED",
                initial_progress=100,
                error_message="Неверные данные клиента.",
            ), 400

        except Exception as exc:
            logger.exception(
                "GET / - Unexpected portal error: "
                f"{exc}"
            )

            return render_template(
                "portal.html",
                session_id=None,
                redirect_url=redirect_url,
                initial_status="FAILED",
                initial_progress=100,
                error_message="Внутренняя ошибка сервера.",
            ), 500

    @app.route(
        "/auth/session/<session_id>",
        methods=["GET"],
    )
    def get_auth_session(session_id: str):
        """
        Только возвращает состояние AuthSession.

        Endpoint не создаёт сессию, не запускает worker,
        не продлевает TTL и не вызывает Omada.
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
