"""HTTP routes for RFC 8908 CAPPORT state and portal entry."""

import json
import math
import time
from urllib.parse import urlencode

from flask import (
    Blueprint,
    current_app,
    jsonify,
    make_response,
    render_template,
    request,
    url_for,
)

from app.auth_telemetry import events
from app.logger import logger
from app.web.localization import PORTAL_TRANSLATIONS
from app.web.portal_entry import PortalClientContext, PortalEntryResult

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
        wants_json = _accepts_explicit_json()
        state = service.resolve_for_login(client_ip)
        if not state.allowed:
            if wants_json:
                return _no_store(
                    jsonify(_terminal_discovery_error(
                        "client_not_allowed"
                    )),
                    403,
                )
            return _no_store(
                jsonify({"error": "client_not_allowed"}),
                403,
            )

        if state.lookup_failed:
            if wants_json:
                discovery = _discovery_contract()
                discovery["error"] = "lookup_failed"
                return _no_store(jsonify(discovery), 503)
            return _no_store(_controlled_error(
                    "Сервис авторизации временно недоступен. "
                    "Попробуйте ещё раз.",
                    503,
                ))
        if not state.client_found or state.client is None:
            discovery = _discovery_contract()
            if wants_json:
                return _no_store(jsonify(discovery), 200)
            rendered = render_template(
                "portal.html",
                session_id=None,
                redirect_url=None,
                initial_status="DISCOVERING_CLIENT",
                initial_progress=5,
                error_message=None,
                initial_state={
                    "state": discovery["state"],
                    "status": discovery["status"],
                    "mode": discovery["mode"],
                    "progress": discovery["progress"],
                    "terminal": discovery["terminal"],
                    "retryable": discovery["retryable"],
                },
                portal_translations=PORTAL_TRANSLATIONS,
                retry_url=discovery["retry_url"],
                restart_url=discovery["restart_url"],
                auto_retry=discovery["auto_retry"],
                retry_interval_ms=discovery["retry_interval_ms"],
                remaining_seconds=discovery["remaining_seconds"],
            )
            return _no_store(current_app.response_class(
                rendered,
                status=200,
                mimetype="text/html",
            ))

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
            ssid=state.client.ssid,
        )
        if wants_json:
            result = portal_entry_handler.prepare_portal(context)
            return _no_store(
                jsonify(_entry_json(result)),
                result.status_code,
            )
        return _no_store(portal_entry_handler.open_portal(context))

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


def _accepts_explicit_json() -> bool:
    raw_accept = request.headers.get("Accept", "")
    for item in raw_accept.split(","):
        parts = [part.strip() for part in item.split(";")]
        if not parts or parts[0].lower() != "application/json":
            continue
        quality = 1.0
        for parameter in parts[1:]:
            name, separator, value = parameter.partition("=")
            if separator and name.strip().lower() == "q":
                try:
                    quality = float(value.strip())
                except (TypeError, ValueError):
                    quality = 0.0
                break
        if math.isfinite(quality) and quality > 0:
            return True
    return False


def _discovery_contract() -> dict:
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
    if parsed_deadline is None or parsed_deadline > maximum_deadline:
        wait_until = maximum_deadline
    else:
        wait_until = parsed_deadline
    auto_retry = wait_until > now_seconds

    original_query = [
        (key, value)
        for key, value in request.args.items(multi=True)
        if key != "wait_until"
    ]
    retry_query = urlencode(
        original_query + [("wait_until", str(wait_until))]
    )
    restart_query = urlencode(original_query)
    login_path = url_for("capport.login")
    retry_url = f"{login_path}?{retry_query}"
    restart_url = login_path
    if restart_query:
        restart_url = f"{login_path}?{restart_query}"

    return {
        "mode": "CAPPORT_DISCOVERY",
        "state": "DISCOVERING_CLIENT",
        "status": "DISCOVERING_CLIENT",
        "progress": 5,
        "terminal": False,
        "retryable": True,
        "auto_retry": auto_retry,
        "remaining_seconds": (
            max(0, wait_until - now_seconds) if auto_retry else 0
        ),
        "retry_interval_ms": 2000,
        "retry_url": retry_url,
        "restart_url": restart_url,
    }


def _terminal_discovery_error(error: str) -> dict:
    return {
        "mode": "CAPPORT_DISCOVERY",
        "state": "FAILED",
        "status": "FAILED",
        "progress": 100,
        "terminal": True,
        "retryable": False,
        "auto_retry": False,
        "remaining_seconds": 0,
        "retry_interval_ms": 2000,
        "retry_url": None,
        "restart_url": None,
        "error": error,
    }


def _entry_json(result: PortalEntryResult) -> dict:
    if result.session_id:
        payload = {
            "mode": "AUTH_SESSION",
            "session_id": result.session_id,
            "redirect_url": result.redirect_url,
            "initial_state": dict(result.initial_state),
        }
        if result.error_code:
            payload["error"] = result.error_code
        return payload
    return _terminal_discovery_error(
        "invalid_context"
        if result.status_code == 400
        else result.error_code or "session_preparation_failed"
    )


def _no_store(response, status_code: int | None = None):
    prepared = make_response(response)
    if status_code is not None:
        prepared.status_code = status_code
    prepared.headers["Cache-Control"] = "private, no-store"
    prepared.headers["Pragma"] = "no-cache"
    return prepared


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
