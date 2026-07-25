"""
Web Layer - Flask Application.

GET portal request creates or reuses a server-side AuthSession.
The browser only displays the session state and never controls
the Omada authorization process.
"""

import logging
import os
from concurrent.futures import ThreadPoolExecutor

from flask import Flask, jsonify, render_template, request

from app import create_controller, logger
from app.auth.manager import AuthSessionManager
from app.auth.session import AuthStatus
from app.auth.worker import AuthWorker, log_auth_event


MAX_WORKERS = 4


# Один менеджер и один executor на процесс приложения.
auth_manager = AuthSessionManager()

auth_executor = ThreadPoolExecutor(
    max_workers=MAX_WORKERS,
    thread_name_prefix="auth_worker_",
)


def create_app() -> Flask:
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

    controller = create_controller()

    auth_worker = AuthWorker(
        provider=controller,
        session_manager=auth_manager,
    )

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

            if created:
                log_auth_event(
                    "AUTH_SESSION_CREATED",
                    session,
                )
            else:
                log_auth_event(
                    "AUTH_SESSION_REUSED",
                    session,
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

                    log_auth_event(
                        "AUTH_WORKER_CLAIM_FAILED",
                        session,
                        level=logging.ERROR,
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
                    auth_executor.submit(
                        auth_worker.process,
                        session.session_id,
                    )

                    log_auth_event(
                        "AUTH_WORKER_SUBMITTED",
                        session,
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

                    log_auth_event(
                        "AUTH_WORKER_SUBMISSION_FAILED",
                        session,
                        level=logging.ERROR,
                        message=str(exc),
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
