"""HTTP routes for RFC 8908 CAPPORT state and portal entry."""

import json
import time
from urllib.parse import urlencode

from flask import (
    Blueprint,
    current_app,
    jsonify,
    render_template,
    request,
    url_for,
)

from app.auth_telemetry import events
from app.logger import logger
from app.web.localization import PORTAL_TRANSLATIONS
from app.web.portal_entry import PortalClientContext

from .models import CapportConfig
from .service import CapportService


CAPPORT_MEDIA_TYPE = "application/captive+json"


def create_capport_blueprint(
    service: CapportService,
    portal_entry_handler,
    config: CapportConfig,
    telemetry,
) -> Blueprint:
    blueprint = Blueprint("capport", __name__)

    def capport_api():
        client_ip = request.remote_addr
        telemetry.safe_emit_system(
            events.CAPPORT_API_REQUEST,
            client_ip=client_ip,
            scheme=request.scheme,
            host=request.host,
        )

        state = service.resolve(client_ip)
        if not state.allowed:
            return jsonify({"error": "client_not_allowed"}), 403

        payload = {
            "captive": state.captive,
            "user-portal-url": config.login_url,
        }
        response = current_app.response_class(
            json.dumps(payload, separators=(",", ":")),
            status=200,
            mimetype=CAPPORT_MEDIA_TYPE,
        )
        response.headers["Cache-Control"] = "private, no-store"
        response.headers["Pragma"] = "no-cache"
        return response

    def capport_login():
        client_ip = request.remote_addr
        state = service.resolve_for_login(client_ip)
        if not state.allowed:
            return jsonify({"error": "client_not_allowed"}), 403

        if state.lookup_failed:
            return _controlled_error(
                "Сервис авторизации временно недоступен. "
                "Попробуйте ещё раз.",
                503,
            )
        if not state.client_found or state.client is None:
            raw_deadline = request.args.get("wait_until")
            try:
                parsed_deadline = (
                    int(raw_deadline)
                    if raw_deadline is not None
                    else None
                )
            except (TypeError, ValueError):
                parsed_deadline = None

            now_seconds = int(time.time())
            maximum_deadline = now_seconds + 60
            if parsed_deadline is None:
                wait_until = maximum_deadline
                auto_retry = True
            elif parsed_deadline > maximum_deadline:
                wait_until = maximum_deadline
                auto_retry = True
            elif parsed_deadline > now_seconds:
                wait_until = parsed_deadline
                auto_retry = True
            else:
                wait_until = parsed_deadline
                auto_retry = False

            original_query = [
                (key, value)
                for key, value in request.args.items(multi=True)
                if key != "wait_until"
            ]
            retry_query = urlencode(
                original_query
                + [("wait_until", str(wait_until))]
            )
            restart_query = urlencode(original_query)
            login_path = url_for("capport.login")
            retry_url = f"{login_path}?{retry_query}"
            restart_url = login_path
            if restart_query:
                restart_url = f"{login_path}?{restart_query}"

            initial_state = {
                "state": "DISCOVERING_CLIENT",
                "status": "DISCOVERING_CLIENT",
                "mode": "CAPPORT_DISCOVERY",
                "progress": 5,
                "terminal": False,
                "retryable": True,
            }
            rendered = render_template(
                "portal.html",
                session_id=None,
                redirect_url=None,
                initial_status="DISCOVERING_CLIENT",
                initial_progress=5,
                error_message=None,
                initial_state=initial_state,
                portal_translations=PORTAL_TRANSLATIONS,
                retry_url=retry_url,
                restart_url=restart_url,
                auto_retry=auto_retry,
                retry_interval_ms=2000,
                remaining_seconds=(
                    max(0, wait_until - now_seconds)
                    if auto_retry
                    else 0
                ),
            )
            response = current_app.response_class(
                rendered,
                status=200,
                mimetype="text/html",
            )
            response.headers["Cache-Control"] = "private, no-store"
            response.headers["Pragma"] = "no-cache"
            return response

        telemetry.safe_emit_system(
            events.CAPPORT_PORTAL_OPENED,
            site_id=state.client.site_id,
            client_ip=state.client.client_ip,
            client_mac=state.client.client_mac,
            auth_status=state.client.auth_status,
            active=state.client.active,
            cache_hit=state.cache_hit,
        )
        context = PortalClientContext(
            site_id=state.client.site_id,
            client_mac=state.client.client_mac,
            client_ip=state.client.client_ip,
        )
        return portal_entry_handler.open_portal(context)

    blueprint.add_url_rule(
        config.api_path,
        endpoint="api",
        view_func=capport_api,
        methods=["GET"],
    )
    blueprint.add_url_rule(
        config.login_path,
        endpoint="login",
        view_func=capport_login,
        methods=["GET"],
    )
    return blueprint


def _controlled_error(message: str, status_code: int):
    try:
        initial_state = {
            "state": "FAILED",
            "status": "FAILED",
            "retryable": False,
            "progress": 100,
            "terminal": True,
        }
        return (
            render_template(
                "portal.html",
                session_id=None,
                redirect_url=None,
                initial_status="FAILED",
                initial_progress=100,
                error_message=message,
                initial_state=initial_state,
                portal_translations=PORTAL_TRANSLATIONS,
            ),
            status_code,
        )
    except Exception:
        logger.exception("capport.error_page_failed")
        return message, status_code
