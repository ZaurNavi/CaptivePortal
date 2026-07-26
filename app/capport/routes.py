"""HTTP routes for RFC 8908 CAPPORT state and portal entry."""

import json

from flask import Blueprint, current_app, jsonify, render_template, request

from app.auth_telemetry import events
from app.logger import logger
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
            return _controlled_error(
                "Не удалось определить устройство. "
                "Отключитесь от Wi-Fi и подключитесь повторно.",
                404,
            )

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
        return render_template(
            "portal.html",
            session_id=None,
            redirect_url=None,
            initial_status="FAILED",
            initial_progress=100,
            error_message=message,
        ), status_code
    except Exception:
        logger.exception("capport.error_page_failed")
        return message, status_code
