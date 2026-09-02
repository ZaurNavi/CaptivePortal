"""Admin Security + Site Context HTTP boundary for Web Foundation 01A."""

from __future__ import annotations

import hmac
import ipaddress
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from functools import wraps
from typing import Any, Callable
from urllib.parse import urlsplit

from flask import (
    Blueprint,
    Response,
    g,
    jsonify,
    make_response,
    redirect,
    render_template,
    request,
)
from werkzeug.security import check_password_hash

from .config import USERNAME_PATTERN
from .models import AdminPrincipal
from .pages import (
    DEVICE,
    DEVICES,
    HOME,
    OBSERVATIONS,
    TRAFFIC,
    VISITS,
    canonical_device_id,
    render_admin_page,
)
from .policy import AdminAccessDenied, AdminSiteContextError
from .tokens import is_canonical_token, token_matches
from .query_service import (
    AdminQueryBusy,
    AdminQueryCursorExpired,
    AdminQueryDeadline,
    AdminQueryError,
    AdminQueryForbidden,
    AdminQueryIntegrityUnavailable,
    AdminQueryNotFound,
    AdminQueryUnavailable,
    AdminQueryValidationError,
)
from .home_activity_ranges import (
    HomeActivityRangeError,
    next_site_midnight_utc,
    resolve_custom,
    resolve_selected,
    resolve_today,
)


ADMIN_PREFIX = "/admin"
ADMIN_API_PREFIX = "/admin/api/v1"
SESSION_COOKIE = "captivportal_admin_session"
PREAUTH_COOKIE = "captivportal_admin_preauth"
API_VERSION = "admin.read.v1"


def create_admin_web_blueprint(runtime: Any, *, logger: logging.Logger) -> Blueprint:
    config = runtime.config
    sessions = runtime.session_store
    preauth = runtime.preauth_store
    limiter = runtime.rate_limiter
    resolver = runtime.site_resolver
    policy = runtime.access_policy
    if any(value is None for value in (config, sessions, preauth, limiter, resolver, policy)):
        raise ValueError("active Admin Web runtime is incomplete")
    blueprint = Blueprint(
        "admin_web_v1",
        __name__,
        template_folder="templates",
        static_folder="static",
        static_url_path="/admin/static",
    )

    @blueprint.before_app_request
    def admin_boundary():
        if not _is_admin_path(request.path):
            return None
        g.admin_request_id = str(uuid.uuid4())
        g.admin_started_at = time.monotonic()
        if config.require_https and not request.is_secure:
            return _error("https_required", 403)
        source_ip = _canonical_source_ip(request.remote_addr)
        if source_ip is None or not _source_allowed(source_ip, config.allowed_networks):
            return _error("source_network_forbidden", 403)
        g.admin_source_ip = source_ip
        if len(request.query_string) > config.max_query_string_bytes:
            return _error("invalid_request", 400)
        if (
            not (
                _is_current_state_path(request.path)
                or _is_current_traffic_path(request.path)
                or _is_home_activity_path(request.path)
            )
            and any(len(request.args.getlist(key)) != 1 for key in request.args)
        ):
            return _error("invalid_request", 400)
        if request.method == "POST":
            if request.content_length is None:
                return _error("length_required", 411)
            if request.content_length > config.max_post_bytes:
                return _error("request_too_large", 413)
            if request.mimetype != "application/x-www-form-urlencoded":
                return _error("unsupported_media_type", 415)
            if any(len(request.form.getlist(key)) != 1 for key in request.form):
                return _error("invalid_request", 400)
        return None

    @blueprint.after_app_request
    def admin_headers(response: Response) -> Response:
        if not _is_admin_path(request.path):
            return response
        if request.path == "/admin/login" and request.method == "POST":
            response.delete_cookie(PREAUTH_COOKIE, path="/admin/login")
        response.headers["Cache-Control"] = "no-store"
        response.headers["Pragma"] = "no-cache"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        if response.mimetype == "text/html":
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; script-src 'self'; style-src 'self'; "
                "img-src 'self' data:; connect-src 'self'; object-src 'none'; "
                "base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
            )
        return response

    def authenticated(view: Callable[..., Response]):
        @wraps(view)
        def wrapped(*args, **kwargs):
            values = _cookie_values(SESSION_COOKIE)
            session = (
                sessions.get(values[0])
                if len(values) == 1 and is_canonical_token(values[0])
                else None
            )
            if session is None:
                _event(logger, "admin.session_expired", reason="missing_or_expired")
                if _is_api_path(request.path):
                    return _error("authentication_required", 401)
                return redirect(_login_url(request.path), code=302)
            g.admin_session = session
            g.admin_session_token = values[0]
            g.admin_principal = session.principal
            return view(*args, **kwargs)

        return wrapped

    @blueprint.get("/admin/login")
    def login_form() -> Response:
        if set(request.args) - {"next"}:
            return _error("invalid_request", 400)
        next_value = _validated_next(request.args.get("next"), config.max_next_chars)
        issued = preauth.issue()
        if issued is None:
            return _error("temporary_unavailable", 503)
        handle, csrf_token = issued
        response = make_response(
            render_template(
                "admin_login.html",
                csrf_token=csrf_token,
                form_action=_login_url(next_value),
                error_message=None,
            )
        )
        response.set_cookie(
            PREAUTH_COOKIE,
            handle,
            max_age=config.preauth_csrf_ttl_seconds,
            httponly=True,
            secure=True,
            samesite="Strict",
            path="/admin/login",
        )
        return response

    @blueprint.post("/admin/login")
    def login_submit() -> Response:
        if set(request.args) - {"next"} or set(request.form) != {
            "username", "password", "csrf_token"
        }:
            return _delete_preauth(_error("invalid_request", 400))
        next_value = _validated_next(request.args.get("next"), config.max_next_chars)
        username = request.form["username"]
        password = request.form["password"]
        csrf_token = request.form["csrf_token"]
        if (
            len(username) > config.max_username_chars
            or len(password) > config.max_password_chars
            or len(csrf_token) > config.max_csrf_chars
            or USERNAME_PATTERN.fullmatch(username) is None
        ):
            return _delete_preauth(_error("invalid_request", 400))

        source_ip = g.admin_source_ip
        limiter_status = limiter.begin_attempt(source_ip)
        if limiter_status != "allowed":
            _event(logger, "admin.auth_login_rate_limited", reason=limiter_status)
            return _delete_preauth(_error("rate_limited", 429))
        attempt_outcome = "neutral"
        try:
            handles = _cookie_values(PREAUTH_COOKIE)
            stored_csrf = (
                preauth.consume(handles[0])
                if len(handles) == 1 and is_canonical_token(handles[0])
                else None
            )
            if not token_matches(csrf_token, stored_csrf):
                return _delete_preauth(_error("invalid_csrf", 400))

            reservation = sessions.reserve()
            if reservation is None:
                return _delete_preauth(_error("temporary_unavailable", 503))
            committed = False
            try:
                try:
                    username_match = hmac.compare_digest(
                        username.encode("ascii"),
                        config.username.encode("ascii"),
                    )
                    password_match = check_password_hash(config.password_hash, password)
                    if not (username_match and password_match):
                        attempt_outcome = "failure"
                        _event(logger, "admin.auth_login_failed", reason="invalid_credential")
                        return _delete_preauth(_login_failure(next_value, csrf_token=""))

                    old_tokens = _cookie_values(SESSION_COOKIE)
                    if len(old_tokens) == 1:
                        sessions.revoke(old_tokens[0])
                    token, _session = sessions.commit(
                        reservation,
                        AdminPrincipal(username=config.username),
                    )
                    committed = True
                    attempt_outcome = "success"
                    _event(logger, "admin.auth_login_succeeded", principal_type="platform_operator")
                    response = redirect(next_value or f"/admin/sites/{config.default_site_id}/")
                    response.set_cookie(
                        SESSION_COOKIE,
                        token,
                        httponly=True,
                        secure=True,
                        samesite="Strict",
                        path="/admin",
                    )
                    return _delete_preauth(response)
                except Exception:
                    logger.error(
                        "admin.auth_login_failed",
                        extra={
                            "event": "admin.auth_login_failed",
                            "reason": "internal_error",
                        },
                    )
                    return _delete_preauth(_error("internal_error", 500))
            finally:
                if not committed:
                    sessions.release(reservation)
        finally:
            limiter.finish_attempt(source_ip, attempt_outcome)

    @blueprint.post("/admin/logout")
    @authenticated
    def logout() -> Response:
        if set(request.form) != {"csrf_token"}:
            return _error("invalid_request", 400)
        submitted = request.form["csrf_token"]
        if len(submitted) > config.max_csrf_chars or not token_matches(
            submitted,
            g.admin_session.csrf_token,
        ):
            return _error("invalid_csrf", 400)
        sessions.revoke(g.admin_session_token)
        _event(logger, "admin.auth_logout", principal_type="platform_operator")
        response = redirect("/admin/login")
        response.delete_cookie(SESSION_COOKIE, path="/admin")
        return response

    @blueprint.get("/admin/")
    @authenticated
    def admin_home() -> Response:
        return redirect(f"/admin/sites/{resolver.default()}/")

    @blueprint.get("/admin/sites/<site_id>/")
    @authenticated
    def site_home(site_id: str) -> Response:
        return _site_page(site_id, HOME)

    @blueprint.get("/admin/sites/<site_id>/devices")
    @authenticated
    def site_devices(site_id: str) -> Response:
        return _site_page(site_id, DEVICES)

    @blueprint.get("/admin/sites/<site_id>/devices/<device_id>")
    @authenticated
    def site_device(site_id: str, device_id: str) -> Response:
        selected_device = canonical_device_id(device_id)
        if selected_device is None:
            return _error("invalid_request", 400)
        return _site_page(site_id, DEVICE, device_id=selected_device)

    @blueprint.get("/admin/sites/<site_id>/visits")
    @authenticated
    def site_visits(site_id: str) -> Response:
        return _site_page(site_id, VISITS)

    @blueprint.get("/admin/sites/<site_id>/observations")
    @authenticated
    def site_observations(site_id: str) -> Response:
        return _site_page(site_id, OBSERVATIONS)

    @blueprint.get("/admin/sites/<site_id>/traffic")
    @authenticated
    def site_traffic(site_id: str) -> Response:
        return _site_page(site_id, TRAFFIC)

    def _site_page(site_id: str, page, *, device_id: str | None = None) -> Response:
        try:
            selected = resolver.resolve(site_id)
        except AdminSiteContextError:
            return _error("invalid_request", 400)
        except AdminAccessDenied:
            return _error("site_forbidden", 403)
        if not policy.authorize(g.admin_principal, "admin.read.context", selected):
            return _error("site_forbidden", 403)
        if page.key == "traffic" and not config.traffic_enabled:
            return _error("not_found", 404)
        online_guests_allowed = False
        if page.key == "traffic" and config.traffic_online_guests_enabled:
            try:
                online_guests_allowed = policy.authorize(
                    g.admin_principal, "admin.read.devices", selected
                )
            except Exception:
                online_guests_allowed = False
        return render_admin_page(
            page,
            site_id=selected,
            username=g.admin_principal.username,
            csrf_token=g.admin_session.csrf_token,
            runtime_state=runtime.state,
            device_id=device_id,
            home_live_enabled=config.home_live_enabled,
            home_live_refresh_seconds=config.home_live_refresh_seconds,
            home_live_request_timeout_seconds=config.home_live_request_timeout_seconds,
            current_state_page_size=config.current_state_page_size,
            home_traffic_enabled=config.home_traffic_enabled,
            home_traffic_refresh_seconds=config.home_traffic_refresh_seconds,
            home_traffic_request_timeout_seconds=config.home_traffic_request_timeout_seconds,
            home_traffic_page_size=config.home_traffic_page_size,
            traffic_enabled=config.traffic_enabled,
            traffic_history_enabled=config.traffic_history_enabled,
            traffic_statistics_enabled=config.traffic_statistics_enabled,
            traffic_peak_enabled=config.traffic_peak_enabled,
            traffic_by_ap_enabled=config.traffic_by_ap_enabled,
            traffic_independent_ranges_enabled=(
                config.traffic_independent_ranges_enabled
            ),
            traffic_ap_share_enabled=config.traffic_ap_share_enabled,
            traffic_online_guests_state=(
                runtime.traffic_online_guests_state
                if config.traffic_online_guests_enabled else "disabled"
            ),
            traffic_online_guests_allowed=online_guests_allowed,
            traffic_refresh_seconds=config.traffic_refresh_seconds,
            traffic_request_timeout_seconds=config.traffic_request_timeout_seconds,
            home_activity_state=runtime.home_activity_state,
            home_activity_config=runtime.home_activity_config,
            home_health_state=runtime.home_health_state,
            home_health_config=runtime.home_health_config,
            home_ap_24h_state=runtime.home_ap_24h_state,
            home_ap_24h_config=runtime.home_ap_24h_config,
        )

    @blueprint.get("/admin/api/v1/session")
    @authenticated
    def api_session() -> Response:
        if request.args:
            return _error("invalid_request", 400)
        return _success(
            None,
            {
                "authenticated": True,
                "principal_type": g.admin_principal.principal_type,
                "username": g.admin_principal.username,
                "csrf_token": g.admin_session.csrf_token,
            },
        )

    @blueprint.get("/admin/api/v1/sites")
    @authenticated
    def api_sites() -> Response:
        if request.args:
            return _error("invalid_request", 400)
        return _success(
            None,
            {
                "default_site_id": config.default_site_id,
                "site_ids": sorted(config.allowed_site_ids),
            },
        )

    @blueprint.get("/admin/api/v1/health")
    @authenticated
    def api_health() -> Response:
        if request.args:
            return _error("invalid_request", 400)
        code = 200 if runtime.state == "active" else 503
        return _success(None, {"status": runtime.state}, status_code=code)

    @blueprint.get("/admin/api/v1/sites/<site_id>/home/health")
    @authenticated
    def api_home_health(site_id: str) -> Response:
        if request.args:
            return _error("invalid_request", 400)
        try:
            selected = resolver.resolve(site_id)
        except AdminSiteContextError:
            return _error("invalid_request", 400)
        except AdminAccessDenied:
            return _error("site_forbidden", 403)
        if not policy.authorize(
            g.admin_principal, "admin.read.overview", selected
        ):
            return _error("site_forbidden", 403)
        if runtime.home_health_state == "disabled":
            return _error("not_found", 404)
        service = runtime.home_health_query_service
        if runtime.home_health_state != "active" or service is None:
            return _error("source_unavailable", 503)
        try:
            result = service.home_health(g.admin_principal, selected)
        except AdminQueryValidationError:
            return _error("invalid_request", 400)
        except AdminQueryForbidden:
            return _error("site_forbidden", 403)
        except AdminQueryBusy:
            response = make_response(_error("concurrency_limit", 429))
            response.headers["Retry-After"] = "1"
            return response
        except AdminQueryDeadline:
            return _error("query_deadline", 503)
        except AdminQueryUnavailable:
            return _error("source_unavailable", 503)
        except Exception:
            logger.error(
                "admin.home_health_evaluation_failed",
                extra={
                    "event": "admin.home_health_evaluation_failed",
                    "failure_category": "evaluation_error",
                },
            )
            return _error("source_unavailable", 503)
        return _success(selected, result.result, enforce_size=True)

    @blueprint.get("/admin/api/v1/sites/<site_id>/home/ap-24h")
    @authenticated
    def api_home_ap_24h(site_id: str) -> Response:
        allowed = frozenset({"limit", "cursor"})
        if any(key not in allowed or len(request.args.getlist(key)) != 1 for key in request.args):
            return _error("invalid_request", 400)
        try:
            selected = resolver.resolve(site_id)
        except AdminSiteContextError:
            return _error("invalid_request", 400)
        except AdminAccessDenied:
            return _error("site_forbidden", 403)
        if not policy.authorize(g.admin_principal, "admin.read.overview", selected):
            return _error("site_forbidden", 403)
        if runtime.home_ap_24h_state == "disabled":
            return _error("not_found", 404)
        service = runtime.query_service
        if runtime.home_ap_24h_state != "active" or service is None:
            return _error("source_unavailable", 503)
        started = time.monotonic()
        status_code = 200
        outcome = "success"
        reason = None
        result = None
        try:
            result = service.home_ap_24h(
                g.admin_principal,
                selected,
                limit=request.args.get("limit"),
                cursor=request.args.get("cursor"),
            )
        except AdminQueryValidationError:
            status_code, outcome, reason = 400, "rejected", "invalid_request"
        except AdminQueryForbidden:
            status_code, outcome, reason = 403, "rejected", "site_forbidden"
        except AdminQueryBusy:
            status_code, outcome, reason = 429, "unavailable", "concurrency_limit"
        except AdminQueryDeadline:
            status_code, outcome, reason = 503, "unavailable", "query_deadline"
        except AdminQueryUnavailable:
            status_code, outcome, reason = 503, "unavailable", "source_unavailable"
        except Exception:
            logger.exception("admin.home_ap_24h_query_failed")
            status_code, outcome, reason = 503, "unavailable", "source_unavailable"
        if status_code != 200:
            response = make_response(_error(reason or "source_unavailable", status_code))
            if status_code == 429:
                response.headers["Retry-After"] = "1"
        else:
            response = make_response(
                _success(selected, result.result, enforce_size=True)
            )
            if response.status_code != 200:
                status_code = response.status_code
                outcome = "unavailable"
                reason = "response_too_large"
        try:
            payload = None if result is None else result.result
            logger.info(
                "admin.home_ap_24h_query_completed",
                extra={
                    "event": "admin.home_ap_24h_query_completed",
                    "site_id": selected,
                    "status_code": status_code,
                    "outcome": outcome,
                    "reason": reason,
                    "duration_ms": max(0, int((time.monotonic() - started) * 1000)),
                    "block_status": None if payload is None else payload.get("block_status"),
                    "current_state_source_status": None if payload is None else payload.get("sources", {}).get("current_state", {}).get("status"),
                    "observation_source_status": None if payload is None else payload.get("sources", {}).get("observations", {}).get("status"),
                    "ap_count": None if payload is None else payload.get("summary", {}).get("ap_count_in_window"),
                    "returned_count": None if payload is None else len(payload.get("items", [])),
                    "has_next_page": None if payload is None else payload.get("page", {}).get("next_cursor") is not None,
                    "response_size_category": None if payload is None else (
                        "small" if len(payload.get("items", [])) <= 5 else
                        "medium" if len(payload.get("items", [])) <= 10 else "large"
                    ),
                },
            )
        except Exception:
            pass
        return response

    @blueprint.get("/admin/api/v1/sites/<site_id>/summary/visits")
    @authenticated
    def api_visit_summary(site_id: str) -> Response:
        if set(request.args) != {"from_utc", "to_utc"}:
            return _error("invalid_request", 400)
        return _site_query(
            site_id,
            lambda service, selected: service.visit_summary(
                g.admin_principal,
                selected,
                request.args["from_utc"],
                request.args["to_utc"],
            ),
        )

    @blueprint.get("/admin/api/v1/sites/<site_id>/summary/devices")
    @authenticated
    def api_device_summary(site_id: str) -> Response:
        if set(request.args) != {"from_utc", "to_utc"}:
            return _error("invalid_request", 400)
        return _site_query(
            site_id,
            lambda service, selected: service.device_summary(
                g.admin_principal,
                selected,
                request.args["from_utc"],
                request.args["to_utc"],
            ),
        )

    @blueprint.get("/admin/api/v1/sites/<site_id>/devices")
    @authenticated
    def api_devices(site_id: str) -> Response:
        if set(request.args) - {"limit", "cursor", "mac"}:
            return _error("invalid_request", 400)
        return _site_query(
            site_id,
            lambda service, selected: service.list_devices(
                g.admin_principal,
                selected,
                limit=request.args.get("limit"),
                cursor=request.args.get("cursor"),
                mac=request.args.get("mac"),
            ),
        )

    @blueprint.get("/admin/api/v1/sites/<site_id>/devices/<device_id>")
    @authenticated
    def api_device(site_id: str, device_id: str) -> Response:
        if request.args:
            return _error("invalid_request", 400)
        return _site_query(
            site_id,
            lambda service, selected: service.device_detail(
                g.admin_principal, selected, device_id
            ),
        )

    @blueprint.get("/admin/api/v1/sites/<site_id>/visits")
    @authenticated
    def api_visits(site_id: str) -> Response:
        allowed = {
            "from_utc", "to_utc", "status", "client_mac", "device_id",
            "ssid", "ap_mac", "limit", "cursor",
        }
        if set(request.args) - allowed:
            return _error("invalid_request", 400)
        return _site_query(
            site_id,
            lambda service, selected: service.list_visits(
                g.admin_principal,
                selected,
                **{key: request.args.get(key) for key in allowed},
            ),
        )

    @blueprint.get("/admin/api/v1/sites/<site_id>/visits/<visit_id>")
    @authenticated
    def api_visit(site_id: str, visit_id: str) -> Response:
        if request.args:
            return _error("invalid_request", 400)
        return _site_query(
            site_id,
            lambda service, selected: service.visit_detail(
                g.admin_principal, selected, visit_id
            ),
        )

    @blueprint.get("/admin/api/v1/sites/<site_id>/observations/clients")
    @authenticated
    def api_client_observations(site_id: str) -> Response:
        required = {"client_mac", "from_utc", "to_utc"}
        allowed = required | {"limit", "cursor"}
        if set(request.args) - allowed or not required.issubset(request.args):
            return _error("invalid_request", 400)
        return _site_query(
            site_id,
            lambda service, selected: service.client_observations(
                g.admin_principal,
                selected,
                **{key: request.args.get(key) for key in allowed},
            ),
        )

    @blueprint.get("/admin/api/v1/sites/<site_id>/observations/aps")
    @authenticated
    def api_ap_observations(site_id: str) -> Response:
        required = {"ap_mac", "from_utc", "to_utc"}
        allowed = required | {"limit", "cursor"}
        if set(request.args) - allowed or not required.issubset(request.args):
            return _error("invalid_request", 400)
        return _site_query(
            site_id,
            lambda service, selected: service.ap_observations(
                g.admin_principal,
                selected,
                **{key: request.args.get(key) for key in allowed},
            ),
        )

    @blueprint.get("/admin/api/v1/sites/<site_id>/current-state/clients/summary")
    @authenticated
    def api_current_client_summary(site_id: str) -> Response:
        return _current_state_query(
            site_id,
            route_name="current_client_summary",
            source_kind="client",
            capability="admin.read.overview",
            allowed_parameters=frozenset(),
            operation=lambda service, selected: service.current_client_summary(
                g.admin_principal, selected
            ),
        )

    @blueprint.get("/admin/api/v1/sites/<site_id>/current-state/clients")
    @authenticated
    def api_current_clients(site_id: str) -> Response:
        allowed = frozenset({
            "cycle_id", "limit", "cursor", "sort", "auth_classification",
            "ap_mac", "ssid",
        })
        return _current_state_query(
            site_id,
            route_name="current_client_page",
            source_kind="client",
            capability="admin.read.devices",
            allowed_parameters=allowed,
            operation=lambda service, selected: service.list_current_clients(
                g.admin_principal,
                selected,
                **{key: request.args.get(key) for key in allowed},
            ),
        )

    @blueprint.get("/admin/api/v1/sites/<site_id>/current-state/aps/summary")
    @authenticated
    def api_current_ap_summary(site_id: str) -> Response:
        return _current_state_query(
            site_id,
            route_name="current_ap_summary",
            source_kind="ap",
            capability="admin.read.overview",
            allowed_parameters=frozenset(),
            operation=lambda service, selected: service.current_ap_summary(
                g.admin_principal, selected
            ),
        )

    @blueprint.get("/admin/api/v1/sites/<site_id>/current-state/aps")
    @authenticated
    def api_current_aps(site_id: str) -> Response:
        allowed = frozenset({"cycle_id", "limit", "cursor"})
        return _current_state_query(
            site_id,
            route_name="current_ap_page",
            source_kind="ap",
            capability="admin.read.overview",
            allowed_parameters=allowed,
            operation=lambda service, selected: service.list_current_aps(
                g.admin_principal,
                selected,
                **{key: request.args.get(key) for key in allowed},
            ),
        )

    @blueprint.get("/admin/api/v1/sites/<site_id>/current-traffic/summary")
    @authenticated
    def api_current_traffic_summary(site_id: str) -> Response:
        return _current_traffic_query(
            site_id,
            route_name="current_traffic_summary",
            capability="admin.read.overview",
            feature_enabled=config.home_traffic_enabled,
            allowed_parameters=frozenset(),
            required_parameters=frozenset(),
            operation=lambda service, selected: service.current_traffic_summary(
                g.admin_principal, selected
            ),
        )

    @blueprint.get("/admin/api/v1/sites/<site_id>/current-traffic/aps")
    @authenticated
    def api_current_traffic_aps(site_id: str) -> Response:
        allowed = frozenset({"cycle_id", "limit", "cursor"})
        return _current_traffic_query(
            site_id,
            route_name="current_traffic_ap_page",
            capability="admin.read.observations",
            feature_enabled=config.home_traffic_enabled,
            allowed_parameters=allowed,
            required_parameters=frozenset({"cycle_id"}),
            operation=lambda service, selected: service.list_current_ap_traffic(
                g.admin_principal,
                selected,
                **{key: request.args.get(key) for key in allowed},
            ),
        )

    @blueprint.get("/admin/api/v1/sites/<site_id>/traffic/current")
    @authenticated
    def api_traffic_current(site_id: str) -> Response:
        return _current_traffic_query(
            site_id,
            route_name="traffic_current",
            capability="admin.read.context",
            feature_enabled=config.traffic_enabled,
            allowed_parameters=frozenset(),
            required_parameters=frozenset(),
            operation=lambda service, selected: service.current_traffic_summary(
                g.admin_principal, selected
            ),
        )

    @blueprint.get("/admin/api/v1/sites/<site_id>/traffic/history")
    @authenticated
    def api_traffic_history(site_id: str) -> Response:
        return _traffic_history_query(site_id)

    @blueprint.get(
        "/admin/api/v1/sites/<site_id>/traffic/online-guests/current"
    )
    @authenticated
    def api_traffic_online_guests(site_id: str) -> Response:
        allowed = frozenset({"limit", "cursor"})
        return _current_traffic_query(
            site_id,
            route_name="traffic_online_guests",
            capability="admin.read.devices",
            feature_enabled=config.traffic_online_guests_enabled,
            allowed_parameters=allowed,
            required_parameters=frozenset(),
            operation=lambda service, selected: service.current_guest_traffic(
                g.admin_principal,
                selected,
                **{key: request.args.get(key) for key in allowed},
            ),
        )

    @blueprint.get("/admin/api/v1/sites/<site_id>/home-activity/today")
    @authenticated
    def api_home_activity_today(site_id: str) -> Response:
        return _home_activity_query(
            site_id,
            route_name="today",
            allowed_parameters=frozenset(),
            required_parameters=frozenset(),
            resolver_operation=lambda context, evaluated: resolve_today(
                context, evaluated
            ),
            include_midnight=True,
        )

    @blueprint.get("/admin/api/v1/sites/<site_id>/home-activity/selected")
    @authenticated
    def api_home_activity_selected(site_id: str) -> Response:
        allowed = frozenset({
            "period", "from_date", "from_time", "to_date", "to_time"
        })
        return _home_activity_query(
            site_id,
            route_name="selected",
            allowed_parameters=allowed,
            required_parameters=frozenset({"period"}),
            resolver_operation=lambda context, evaluated: resolve_selected(
                context,
                {key: request.args.get(key) for key in request.args},
                evaluated,
            ),
            include_midnight=False,
        )

    @blueprint.get("/admin/api/v1/sites/<site_id>/home-activity/range-preview")
    @authenticated
    def api_home_activity_range_preview(site_id: str) -> Response:
        started = time.monotonic()
        authorized_site = None
        reason = "internal_error"
        response: Response
        try:
            selected, context, failure = _home_activity_gate(
                site_id,
                allowed_parameters=frozenset({
                    "from_date", "from_time", "to_date", "to_time"
                }),
                required_parameters=frozenset({"from_date", "to_date"}),
            )
            if failure is not None:
                response, reason = failure
                return response
            authorized_site = selected
            evaluated = datetime.now(timezone.utc)
            try:
                resolved = resolve_custom(
                    context,
                    {key: request.args.get(key) for key in request.args},
                    evaluated,
                    reject_future=False,
                )
            except HomeActivityRangeError:
                response = make_response(_error("invalid_request", 400))
                reason = "invalid_request"
                return response
            payload = resolved.public_range()
            response = make_response(_success(
                selected,
                {
                    "timezone": context.timezone,
                    "requested": payload["requested"],
                    "resolved": payload["resolved"],
                    "can_apply": resolved.to_utc <= evaluated,
                    "validation_reason": (
                        None if resolved.to_utc <= evaluated else "end_in_future"
                    ),
                },
                enforce_size=True,
            ))
            reason = "ok" if response.status_code == 200 else "response_too_large"
            return response
        finally:
            try:
                _event(
                    logger,
                    "admin.home_activity_range_preview_completed",
                    request_id=getattr(g, "admin_request_id", None),
                    site_id=authorized_site,
                    status_code=(response.status_code if "response" in locals() else 500),
                    outcome=("success" if "response" in locals() and response.status_code == 200 else "error"),
                    reason=reason,
                    duration_ms=max(0, int((time.monotonic() - started) * 1000)),
                )
            except Exception:
                pass

    def _home_activity_query(
        site_id: str,
        *,
        route_name: str,
        allowed_parameters: frozenset[str],
        required_parameters: frozenset[str],
        resolver_operation: Callable[..., Any],
        include_midnight: bool,
    ) -> Response:
        started = time.monotonic()
        authorized_site = None
        reason = "internal_error"
        period = None
        range_duration_category = None
        visits_coverage_status = None
        traffic_coverage_status = None
        response: Response
        try:
            selected, context, failure = _home_activity_gate(
                site_id,
                allowed_parameters=allowed_parameters,
                required_parameters=required_parameters,
            )
            if failure is not None:
                response, reason = failure
                return response
            authorized_site = selected
            evaluated = datetime.now(timezone.utc)
            try:
                resolved = resolver_operation(context, evaluated)
                period = resolved.kind
                range_duration_category = _activity_duration_category(resolved)
            except HomeActivityRangeError:
                response = make_response(_error("invalid_request", 400))
                reason = "invalid_request"
                return response
            service = runtime.query_service
            if service is None:
                response = make_response(_error("source_unavailable", 503))
                reason = "source_unavailable"
                return response
            try:
                result = service.home_activity(
                    g.admin_principal,
                    selected,
                    resolved_range=resolved,
                    evaluated_at=evaluated,
                    next_site_midnight_utc=(
                        next_site_midnight_utc(context, evaluated)
                        if include_midnight else None
                    ),
                )
                response = make_response(_success(
                    selected, result.result, enforce_size=True
                ))
                reason = "ok" if response.status_code == 200 else "response_too_large"
                return response
            except AdminQueryValidationError:
                response = make_response(_error("invalid_request", 400))
                reason = "invalid_request"
                return response
            except AdminQueryForbidden:
                response = make_response(_error("site_forbidden", 403))
                reason = "forbidden"
                return response
            except AdminQueryBusy:
                response = make_response(_error("concurrency_limit", 429))
                response.headers["Retry-After"] = "1"
                reason = "busy"
                return response
            except AdminQueryDeadline:
                response = make_response(_error("query_deadline", 503))
                reason = "query_deadline"
                return response
            except AdminQueryUnavailable:
                response = make_response(_error("source_unavailable", 503))
                reason = "source_unavailable"
                return response
            except AdminQueryError:
                response = make_response(_error("internal_error", 500))
                return response
            except Exception:
                logger.exception("admin.home_activity_query_failed")
                response = make_response(_error("internal_error", 500))
                return response
        finally:
            status_code = response.status_code if "response" in locals() else 500
            result_value = None
            if "result" in locals() and isinstance(result.result, dict):
                result_value = result.result
                visits_value = result_value.get("authorized_visits")
                traffic_value = result_value.get("traffic")
                if isinstance(visits_value, dict):
                    coverage_value = visits_value.get("coverage")
                    if isinstance(coverage_value, dict):
                        visits_coverage_status = coverage_value.get("status")
                if isinstance(traffic_value, dict):
                    coverage_value = traffic_value.get("coverage")
                    if isinstance(coverage_value, dict):
                        traffic_coverage_status = coverage_value.get("status")
            try:
                _event(
                    logger,
                    f"admin.home_activity_{route_name}_query_completed",
                    request_id=getattr(g, "admin_request_id", None),
                    site_id=authorized_site,
                    status_code=status_code,
                    outcome="success" if status_code == 200 else "error",
                    reason=reason,
                    period=period,
                    range_duration_category=range_duration_category,
                    visits_coverage_status=visits_coverage_status,
                    traffic_coverage_status=traffic_coverage_status,
                    visit_status=(result_value or {}).get("authorized_visits", {}).get("status") if isinstance((result_value or {}).get("authorized_visits"), dict) else None,
                    traffic_status=(result_value or {}).get("traffic", {}).get("status") if isinstance((result_value or {}).get("traffic"), dict) else None,
                    duration_ms=max(0, int((time.monotonic() - started) * 1000)),
                )
            except Exception:
                pass

    def _home_activity_gate(
        site_id: str,
        *,
        allowed_parameters: frozenset[str],
        required_parameters: frozenset[str],
    ):
        try:
            selected = resolver.resolve(site_id)
        except AdminSiteContextError:
            return None, None, (make_response(_error("invalid_request", 400)), "invalid_request")
        except AdminAccessDenied:
            return None, None, (make_response(_error("site_forbidden", 403)), "forbidden")
        try:
            authorized = policy.authorize(
                g.admin_principal, "admin.read.overview", selected
            )
        except Exception:
            return None, None, (make_response(_error("internal_error", 500)), "internal_error")
        if not authorized:
            return None, None, (make_response(_error("site_forbidden", 403)), "forbidden")
        if runtime.home_activity_state == "disabled":
            return selected, None, (make_response(_error("not_found", 404)), "feature_disabled")
        activity = runtime.home_activity_config
        context = None if activity is None else activity.site(selected)
        if runtime.home_activity_state != "active" or context is None:
            return selected, None, (make_response(_error("source_unavailable", 503)), "source_unavailable")
        keys = set(request.args)
        if (
            keys - allowed_parameters
            or not required_parameters.issubset(keys)
            or any(len(request.args.getlist(key)) != 1 for key in request.args)
        ):
            return selected, context, (make_response(_error("invalid_request", 400)), "invalid_request")
        return selected, context, None

    def _current_traffic_query(
        site_id: str,
        *,
        route_name: str,
        capability: str,
        feature_enabled: bool,
        allowed_parameters: frozenset[str],
        required_parameters: frozenset[str],
        operation: Callable[..., Any],
    ) -> Response:
        started = time.monotonic()
        authorized_site = None
        item_count = 0
        coverage_status = None
        freshness_status = None
        product_status = None
        product_source_health_status = None
        product_rate_evidence_status = None
        product_population_complete = None
        product_counts: dict[str, Any] = {}
        product_has_next_page = None
        response_bytes = None
        response: Response
        reason = "internal_error"
        try:
            try:
                selected = resolver.resolve(site_id)
            except AdminSiteContextError:
                response = make_response(_error("invalid_request", 400))
                reason = "invalid_request"
                return response
            except AdminAccessDenied:
                response = make_response(_error("site_forbidden", 403))
                reason = "forbidden"
                return response
            except Exception:
                response = make_response(_error("internal_error", 500))
                return response
            try:
                authorized = policy.authorize(
                    g.admin_principal, capability, selected
                )
            except Exception:
                response = make_response(_error("internal_error", 500))
                return response
            if not authorized:
                response = make_response(_error("site_forbidden", 403))
                reason = "forbidden"
                return response
            authorized_site = selected
            if not feature_enabled:
                response = make_response(_error("not_found", 404))
                reason = "feature_disabled"
                return response
            keys = set(request.args)
            if (
                keys - allowed_parameters
                or not required_parameters.issubset(keys)
                or any(len(request.args.getlist(key)) != 1 for key in request.args)
            ):
                response = make_response(_error("invalid_request", 400))
                reason = "invalid_request"
                return response
            service = runtime.query_service
            if service is None:
                response = make_response(_error("source_unavailable", 503))
                reason = "source_unavailable"
                return response
            try:
                result = operation(service, selected)
                if isinstance(result.result, dict):
                    if route_name == "traffic_online_guests":
                        product_status = result.result.get("status")
                        product_source_health_status = result.result.get(
                            "source_health_status"
                        )
                        product_rate_evidence_status = result.result.get(
                            "rate_evidence_status"
                        )
                        product_population_complete = result.result.get(
                            "population_complete"
                        )
                        for field in (
                            "scoped_client_row_count", "known_authorized_count",
                            "unknown_auth_count", "rate_valid_count",
                            "rate_partial_count", "rate_unavailable_count",
                        ):
                            product_counts[field] = result.result.get(field)
                    snapshot = result.result.get("snapshot")
                    if isinstance(snapshot, dict):
                        freshness_status = snapshot.get("freshness_status")
                    coverage = result.result.get("coverage")
                    if isinstance(coverage, dict):
                        coverage_status = coverage.get("coverage_status")
                    items = result.result.get("items")
                    if isinstance(items, list):
                        item_count = len(items)
                response = make_response(_success(
                    selected,
                    result.result,
                    page=result.page,
                    enforce_size=True,
                ))
                response_bytes = len(response.get_data())
                if route_name == "traffic_online_guests" and isinstance(result.page, dict):
                    product_has_next_page = result.page.get("next_cursor") is not None
                if response.status_code == 503:
                    reason = "response_too_large"
                elif response.status_code == 200:
                    reason = (
                        freshness_status
                        if freshness_status in {"fresh", "stale", "unavailable"}
                        else "ok"
                    )
                return response
            except AdminQueryCursorExpired:
                response = make_response(_error("cursor_expired", 400))
                reason = "cursor_expired"
                return response
            except AdminQueryValidationError:
                response = make_response(_error("invalid_request", 400))
                reason = "invalid_request"
                return response
            except AdminQueryForbidden:
                response = make_response(_error("site_forbidden", 403))
                reason = "forbidden"
                return response
            except AdminQueryBusy:
                response = make_response(_error("concurrency_limit", 429))
                response.headers["Retry-After"] = "1"
                reason = "busy"
                return response
            except AdminQueryDeadline:
                response = make_response(_error("query_deadline", 503))
                reason = "query_deadline"
                return response
            except AdminQueryUnavailable:
                response = make_response(_error("source_unavailable", 503))
                reason = "source_unavailable"
                return response
            except AdminQueryError:
                response = make_response(_error("internal_error", 500))
                return response
            except Exception:
                try:
                    logger.error(
                        "admin.current_traffic_query_failed",
                        extra={
                            "event": "admin.current_traffic_query_failed",
                            "request_id": getattr(g, "admin_request_id", None),
                            "route_name": route_name,
                        },
                    )
                except Exception:
                    pass
                response = make_response(_error("internal_error", 500))
                return response
        finally:
            status_code = response.status_code if "response" in locals() else 500
            try:
                fields = dict(
                    request_id=getattr(g, "admin_request_id", None),
                    route_name=route_name,
                    site_id=authorized_site,
                    status_code=status_code,
                    outcome="success" if status_code == 200 else "error",
                    reason=reason,
                    duration_ms=max(0, int((time.monotonic() - started) * 1000)),
                    coverage_status=coverage_status,
                    freshness_status=freshness_status,
                    item_count=item_count,
                )
                if route_name == "traffic_online_guests":
                    fields.update({
                        "product": "online_guests_traffic",
                        "status": product_status,
                        "source_health_status": product_source_health_status,
                        "rate_evidence_status": product_rate_evidence_status,
                        "population_complete": product_population_complete,
                        **product_counts,
                        "returned_count": item_count,
                        "has_next_page": product_has_next_page,
                        "response_bytes": response_bytes,
                        "cursor_used": "cursor" in request.args,
                    })
                _event(
                    logger,
                    "admin.current_traffic_query_completed",
                    **fields,
                )
            except Exception:
                pass

    def _traffic_history_query(site_id: str) -> Response:
        started = time.monotonic()
        authorized_site = None
        range_id = None
        requested_products = None
        include_history = True
        statistics_requested = False
        peak_requested = False
        aps_requested = False
        ap_share_requested = False
        statistics_status = None
        peak_status = None
        ap_traffic_status = None
        ap_population_count = None
        ap_returned_count = None
        ap_share_status = None
        ap_share_population_count = None
        ap_share_historical_population_count = None
        ap_share_current_population_status = None
        ap_share_current_population_count = None
        ap_share_returned_count = None
        ap_share_population_complete = None
        ap_share_accepted_interval_count = None
        ap_share_accepted_interval_seconds = None
        ap_share_download_denominator_status = None
        ap_share_upload_denominator_status = None
        ap_share_total_denominator_status = None
        ap_share_unproven_count = None
        busiest_bucket_status = None
        busiest_hour_status = None
        result_status = None
        coverage_status = None
        bucket_count = 0
        gap_bucket_count = None
        transition_count = None
        reason = "internal_error"
        response: Response
        try:
            try:
                selected = resolver.resolve(site_id)
            except AdminSiteContextError:
                response = make_response(_error("invalid_request", 400))
                reason = "invalid_request"
                return response
            except AdminAccessDenied:
                response = make_response(_error("site_forbidden", 403))
                reason = "forbidden"
                return response
            except Exception:
                response = make_response(_error("internal_error", 500))
                return response
            try:
                authorized = policy.authorize(
                    g.admin_principal, "admin.read.context", selected
                )
            except Exception:
                response = make_response(_error("internal_error", 500))
                return response
            if not authorized:
                response = make_response(_error("site_forbidden", 403))
                reason = "forbidden"
                return response
            authorized_site = selected
            if not config.traffic_enabled or not config.traffic_history_enabled:
                response = make_response(_error("not_found", 404))
                reason = "feature_disabled"
                return response
            if (
                not set(request.args).issubset({"range", "include", "products"})
                or "range" not in request.args
                or len(request.args.getlist("range")) != 1
                or (
                    "include" in request.args
                    and len(request.args.getlist("include")) != 1
                )
                or (
                    "products" in request.args
                    and len(request.args.getlist("products")) != 1
                )
                or ("include" in request.args and "products" in request.args)
            ):
                response = make_response(_error("invalid_request", 400))
                reason = "invalid_request"
                return response
            range_id = request.args.get("range")
            if "products" in request.args:
                if not config.traffic_independent_ranges_enabled:
                    response = make_response(_error("not_found", 404))
                    reason = "feature_disabled"
                    return response
                products_text = request.args.get("products")
                tokens = (
                    products_text.split(",")
                    if isinstance(products_text, str) and products_text
                    else []
                )
                canonical = (
                    "history", "statistics", "peak", "aps", "apshare"
                )
                requested_products = tuple(
                    product for product in canonical if product in tokens
                )
                if (
                    not tokens
                    or len(tokens) != len(set(tokens))
                    or ",".join(requested_products) != products_text
                ):
                    response = make_response(_error("invalid_request", 400))
                    reason = "invalid_request"
                    return response
                include_history = "history" in requested_products
                statistics_requested = "statistics" in requested_products
                peak_requested = "peak" in requested_products
                aps_requested = "aps" in requested_products
                ap_share_requested = "apshare" in requested_products
            elif "include" in request.args:
                include = request.args.get("include")
                if include not in {
                    "statistics", "statistics,peak", "aps",
                    "statistics,aps", "statistics,peak,aps",
                }:
                    response = make_response(_error("invalid_request", 400))
                    reason = "invalid_request"
                    return response
                statistics_requested = include.startswith("statistics")
                peak_requested = include.startswith("statistics,peak")
                aps_requested = include.endswith("aps")
            if statistics_requested and not config.traffic_statistics_enabled:
                response = make_response(_error("not_found", 404))
                reason = "feature_disabled"
                return response
            if peak_requested and not config.traffic_peak_enabled:
                response = make_response(_error("not_found", 404))
                reason = "feature_disabled"
                return response
            if aps_requested and not config.traffic_by_ap_enabled:
                response = make_response(_error("not_found", 404))
                reason = "feature_disabled"
                return response
            if ap_share_requested and not config.traffic_ap_share_enabled:
                response = make_response(_error("not_found", 404))
                reason = "feature_disabled"
                return response
            service = runtime.query_service
            if service is None:
                response = make_response(_error("source_unavailable", 503))
                reason = "source_unavailable"
                return response
            try:
                result = service.historical_traffic_history(
                    g.admin_principal,
                    selected,
                    range_id=range_id,
                    include_history=include_history,
                    include_statistics=statistics_requested,
                    include_peak=peak_requested,
                    include_aps=aps_requested,
                    include_ap_share=ap_share_requested,
                    requested_products=requested_products,
                )
                result_status = result.result.get("status")
                coverage = result.result.get("coverage", {})
                coverage_status = coverage.get("status")
                bucket_count = coverage.get("bucket_count", 0)
                gap_bucket_count = coverage.get("gap_bucket_count")
                transition_count = coverage.get("source_transition_count")
                statistics = result.result.get("period_statistics")
                statistics_status = (
                    statistics.get("status")
                    if isinstance(statistics, dict) else None
                )
                peak = result.result.get("peak_load")
                if isinstance(peak, dict):
                    peak_status = peak.get("status")
                    busiest_bucket = peak.get("busiest_bucket")
                    busiest_hour = peak.get("busiest_hour")
                    busiest_bucket_status = (
                        busiest_bucket.get("status")
                        if isinstance(busiest_bucket, dict) else None
                    )
                    busiest_hour_status = (
                        busiest_hour.get("status")
                        if isinstance(busiest_hour, dict) else None
                    )
                ap_traffic = result.result.get("ap_traffic")
                if isinstance(ap_traffic, dict):
                    ap_traffic_status = ap_traffic.get("status")
                    population = ap_traffic.get("population")
                    if isinstance(population, dict):
                        ap_population_count = population.get("population_count")
                        ap_returned_count = population.get("returned_ap_count")
                ap_share = result.result.get("ap_traffic_share")
                if isinstance(ap_share, dict):
                    ap_share_status = ap_share.get("status")
                    share_population = ap_share.get("population")
                    if isinstance(share_population, dict):
                        ap_share_population_count = share_population.get(
                            "population_count"
                        )
                        ap_share_historical_population_count = share_population.get(
                            "historical_population_count"
                        )
                        ap_share_current_population_status = share_population.get(
                            "current_population_status"
                        )
                        ap_share_current_population_count = share_population.get(
                            "current_population_count"
                        )
                        ap_share_returned_count = share_population.get(
                            "returned_ap_count"
                        )
                        ap_share_population_complete = share_population.get(
                            "population_complete"
                        )
                    share_coverage = ap_share.get("coverage")
                    if isinstance(share_coverage, dict):
                        ap_share_accepted_interval_count = share_coverage.get(
                            "accepted_interval_count"
                        )
                        ap_share_accepted_interval_seconds = share_coverage.get(
                            "accepted_interval_seconds"
                        )
                    share_denominators = ap_share.get("denominators")
                    if isinstance(share_denominators, dict):
                        ap_share_download_denominator_status = share_denominators.get(
                            "download_status"
                        )
                        ap_share_upload_denominator_status = share_denominators.get(
                            "upload_status"
                        )
                        ap_share_total_denominator_status = share_denominators.get(
                            "total_status"
                        )
                    share_items = ap_share.get("items")
                    if isinstance(share_items, list):
                        ap_share_unproven_count = sum(
                            item.get("range_presence_proven") is False
                            for item in share_items if isinstance(item, dict)
                        )
                response = make_response(_success(
                    selected,
                    result.result,
                    enforce_size=True,
                ))
                reason = "response_too_large" if response.status_code == 503 else "ok"
                return response
            except AdminQueryValidationError:
                response = make_response(_error("invalid_request", 400))
                reason = "invalid_request"
                return response
            except AdminQueryForbidden:
                response = make_response(_error("site_forbidden", 403))
                reason = "forbidden"
                return response
            except AdminQueryBusy:
                response = make_response(_error("concurrency_limit", 429))
                response.headers["Retry-After"] = "1"
                reason = "busy"
                return response
            except AdminQueryDeadline:
                response = make_response(_error("query_deadline", 503))
                reason = "query_deadline"
                return response
            except AdminQueryIntegrityUnavailable:
                response = make_response(_error("source_unavailable", 503))
                reason = "source_integrity"
                return response
            except AdminQueryUnavailable:
                response = make_response(_error("source_unavailable", 503))
                reason = "source_unavailable"
                return response
            except AdminQueryError:
                response = make_response(_error("internal_error", 500))
                return response
            except Exception:
                response = make_response(_error("internal_error", 500))
                return response
        finally:
            status_code = response.status_code if "response" in locals() else 500
            try:
                _event(
                    logger,
                    "admin.traffic_history_query_completed",
                    request_id=getattr(g, "admin_request_id", None),
                    site_id=authorized_site,
                    range_id=range_id if range_id in {"24h", "7d"} else None,
                    http_status=status_code,
                    outcome="success" if status_code == 200 else "error",
                    reason=reason,
                    duration_ms=max(0, int((time.monotonic() - started) * 1000)),
                    result_status=result_status,
                    coverage_status=coverage_status,
                    bucket_count=bucket_count,
                    gap_bucket_count=gap_bucket_count,
                    source_transition_count=transition_count,
                    statistics_requested=statistics_requested,
                    statistics_status=statistics_status,
                    peak_requested=peak_requested,
                    peak_status=peak_status,
                    ap_traffic_requested=aps_requested,
                    ap_traffic_status=ap_traffic_status,
                    ap_population_count=ap_population_count,
                    ap_returned_count=ap_returned_count,
                    ap_supported_max=12 if aps_requested else None,
                    ap_share_requested=ap_share_requested,
                    share_status=ap_share_status,
                    share_population_count=ap_share_population_count,
                    share_historical_population_count=(
                        ap_share_historical_population_count
                    ),
                    share_current_population_status=(
                        ap_share_current_population_status
                    ),
                    share_current_population_count=(
                        ap_share_current_population_count
                    ),
                    share_returned_ap_count=ap_share_returned_count,
                    share_supported_max_ap_count=(
                        12 if ap_share_requested else None
                    ),
                    share_population_complete=ap_share_population_complete,
                    share_coverage_status=(
                        coverage_status if ap_share_requested else None
                    ),
                    share_accepted_interval_count=(
                        ap_share_accepted_interval_count
                    ),
                    share_accepted_interval_seconds=(
                        ap_share_accepted_interval_seconds
                    ),
                    share_download_denominator_status=(
                        ap_share_download_denominator_status
                    ),
                    share_upload_denominator_status=(
                        ap_share_upload_denominator_status
                    ),
                    share_total_denominator_status=(
                        ap_share_total_denominator_status
                    ),
                    share_unproven_contribution_ap_count=(
                        ap_share_unproven_count
                    ),
                    share_unsupported_population=(
                        ap_share_status == "unsupported_population"
                        if ap_share_requested else None
                    ),
                    share_integrity_failure=(
                        reason == "source_integrity"
                        if ap_share_requested else None
                    ),
                    busiest_bucket_status=busiest_bucket_status,
                    busiest_hour_status=busiest_hour_status,
                    response_bytes=getattr(response, "content_length", None),
                    requested_products=(
                        ",".join(requested_products)
                        if requested_products is not None else None
                    ),
                    product_count=(
                        len(requested_products)
                        if requested_products is not None else None
                    ),
                )
            except Exception:
                pass

    def _current_state_query(
        site_id: str,
        *,
        route_name: str,
        source_kind: str,
        capability: str,
        allowed_parameters: frozenset[str],
        operation: Callable[..., Any],
    ) -> Response:
        started = time.monotonic()
        selected = None
        authorized_site = None
        item_count = 0
        response: Response
        reason = "internal_error"
        try:
            try:
                selected = resolver.resolve(site_id)
            except AdminSiteContextError:
                response = make_response(_error("invalid_request", 400))
                reason = "invalid_request"
                return response
            except AdminAccessDenied:
                response = make_response(_error("site_forbidden", 403))
                reason = "forbidden"
                return response
            except Exception:
                response = make_response(_error("internal_error", 500))
                reason = "internal_error"
                return response
            try:
                authorized = policy.authorize(
                    g.admin_principal, capability, selected
                )
            except Exception:
                response = make_response(_error("internal_error", 500))
                reason = "internal_error"
                return response
            if not authorized:
                response = make_response(_error("site_forbidden", 403))
                reason = "forbidden"
                return response
            authorized_site = selected
            if not config.home_live_enabled:
                response = make_response(_error("not_found", 404))
                reason = "feature_disabled"
                return response
            if set(request.args) - allowed_parameters or (
                not allowed_parameters and request.args
            ) or any(len(request.args.getlist(key)) != 1 for key in request.args):
                response = make_response(_error("invalid_request", 400))
                reason = "invalid_request"
                return response
            service = runtime.query_service
            if service is None:
                response = make_response(_error("source_unavailable", 503))
                reason = "source_unavailable"
                return response
            try:
                result = operation(service, selected)
                if isinstance(result.result, dict) and isinstance(result.result.get("items"), list):
                    item_count = len(result.result["items"])
                response = make_response(_success(
                    selected, result.result, page=result.page, enforce_size=True
                ))
                if response.status_code == 503:
                    reason = "response_too_large"
                elif response.status_code == 200:
                    snapshot = result.result.get("snapshot") if isinstance(result.result, dict) else None
                    freshness = snapshot.get("freshness_status") if isinstance(snapshot, dict) else None
                    reason = freshness if freshness in {"fresh", "stale"} else "ok"
                else:
                    reason = "internal_error"
                return response
            except AdminQueryValidationError:
                response = make_response(_error("invalid_request", 400))
                reason = "invalid_request"
                return response
            except AdminQueryForbidden:
                response = make_response(_error("site_forbidden", 403))
                reason = "forbidden"
                return response
            except AdminQueryBusy:
                response = make_response(_error("concurrency_limit", 429))
                response.headers["Retry-After"] = "1"
                reason = "busy"
                return response
            except AdminQueryDeadline:
                response = make_response(_error("query_deadline", 503))
                reason = "query_deadline"
                return response
            except AdminQueryUnavailable:
                response = make_response(_error("source_unavailable", 503))
                reason = "source_unavailable"
                return response
            except AdminQueryError:
                response = make_response(_error("internal_error", 500))
                reason = "internal_error"
                return response
            except Exception:
                try:
                    logger.error(
                        "admin.current_state_query_failed",
                        extra={
                            "event": "admin.current_state_query_failed",
                            "request_id": getattr(g, "admin_request_id", None),
                            "route_name": route_name,
                            "source_kind": source_kind,
                        },
                    )
                except Exception:
                    pass
                response = make_response(_error("internal_error", 500))
                reason = "internal_error"
                return response
        finally:
            status_code = response.status_code if "response" in locals() else 500
            outcome = "success" if status_code == 200 else "error"
            try:
                _event(
                    logger,
                    "admin.current_state_query_completed",
                    request_id=getattr(g, "admin_request_id", None),
                    route_name=route_name,
                    source_kind=source_kind,
                    site_id=authorized_site,
                    status_code=status_code,
                    outcome=outcome,
                    reason=reason,
                    duration_ms=max(0, int((time.monotonic() - started) * 1000)),
                    item_count=item_count,
                )
            except Exception:
                pass

    def _site_query(site_id: str, operation: Callable[..., Any]) -> Response:
        try:
            selected = resolver.resolve(site_id)
        except AdminSiteContextError:
            return _error("invalid_request", 400)
        except AdminAccessDenied:
            return _error("site_forbidden", 403)
        service = runtime.query_service
        if service is None:
            return _error("source_unavailable", 503)
        try:
            response = operation(service, selected)
        except AdminQueryValidationError:
            return _error("invalid_request", 400)
        except AdminQueryForbidden:
            return _error("site_forbidden", 403)
        except AdminQueryNotFound:
            return _error("not_found", 404)
        except AdminQueryBusy:
            result = make_response(_error("concurrency_limit", 429))
            result.headers["Retry-After"] = "1"
            return result
        except AdminQueryDeadline:
            return _error("query_deadline", 503)
        except AdminQueryUnavailable:
            return _error("source_unavailable", 503)
        except AdminQueryError:
            return _error("internal_error", 500)
        except Exception:
            logger.exception("admin.query_failed")
            return _error("internal_error", 500)
        return _success(
            selected,
            response.result,
            page=response.page,
            enforce_size=True,
        )

    def _delete_preauth(response: Response) -> Response:
        response.delete_cookie(PREAUTH_COOKIE, path="/admin/login")
        return response

    def _login_failure(next_value: str | None, *, csrf_token: str) -> Response:
        return make_response(
            render_template(
                "admin_login.html",
                csrf_token=csrf_token,
                form_action=_login_url(next_value),
                error_message="Authentication failed.",
            ),
            401,
        )

    def _success(
        site_id: str | None,
        result: Any,
        *,
        status_code: int = 200,
        page: dict[str, Any] | None = None,
        enforce_size: bool = False,
    ) -> Response:
        payload = {
            "api_version": API_VERSION,
            "request_id": g.admin_request_id,
            "site_id": site_id,
            "result": result,
            "page": page,
        }
        try:
            body = json.dumps(
                payload,
                allow_nan=False,
                ensure_ascii=True,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
        except (TypeError, ValueError):
            return _error("internal_error", 500)
        if enforce_size and len(body) > config.max_response_bytes:
            return _error("response_too_large", 503)
        response = make_response(body, status_code)
        response.mimetype = "application/json"
        return response

    return blueprint


def _error(code: str, status_code: int) -> Response:
    if _is_api_path(request.path):
        return jsonify(
            {
                "api_version": API_VERSION,
                "request_id": getattr(g, "admin_request_id", str(uuid.uuid4())),
                "error": {
                    "code": code,
                    "message": "The request could not be completed.",
                },
            }
        ), status_code
    return make_response("The request could not be completed.", status_code)


def _is_admin_path(path: str) -> bool:
    return path == ADMIN_PREFIX or path.startswith(ADMIN_PREFIX + "/")


def _is_api_path(path: str) -> bool:
    return path == ADMIN_API_PREFIX or path.startswith(ADMIN_API_PREFIX + "/")


def _is_current_state_path(path: str) -> bool:
    return (
        path.startswith(ADMIN_API_PREFIX + "/sites/")
        and "/current-state/" in path
    )


def _is_current_traffic_path(path: str) -> bool:
    return (
        path.startswith(ADMIN_API_PREFIX + "/sites/")
        and (
            "/current-traffic/" in path
            or path.endswith("/traffic/current")
            or path.endswith("/traffic/history")
            or path.endswith("/traffic/online-guests/current")
        )
    )


def _is_home_activity_path(path: str) -> bool:
    return (
        path.startswith(ADMIN_API_PREFIX + "/sites/")
        and "/home-activity/" in path
    )


def _activity_duration_category(value: Any) -> str:
    seconds = (value.to_utc - value.from_utc).total_seconds()
    if seconds <= 24 * 3600:
        return "up_to_24h"
    if seconds <= 7 * 86400:
        return "over_24h_to_7d"
    if seconds <= 31 * 86400:
        return "over_7d_to_31d"
    if seconds <= 90 * 86400:
        return "over_31d_to_90d"
    if seconds <= 365 * 86400:
        return "over_90d_to_365d"
    return "over_365d"


def _canonical_source_ip(value: object) -> str | None:
    try:
        return str(ipaddress.ip_address(value))
    except (TypeError, ValueError):
        return None


def _source_allowed(source_ip: str, networks: tuple[Any, ...]) -> bool:
    address = ipaddress.ip_address(source_ip)
    return any(address.version == network.version and address in network for network in networks)


def _cookie_values(name: str) -> list[str]:
    values = []
    for item in request.headers.get("Cookie", "").split(";"):
        key, separator, value = item.strip().partition("=")
        if separator and key == name:
            values.append(value.strip('"'))
    return values


def _validated_next(value: object, maximum: int) -> str | None:
    if value is None or value == "":
        return None
    if (
        not isinstance(value, str)
        or len(value) > maximum
        or "\\" in value
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
    ):
        return None
    parsed = urlsplit(value)
    if parsed.scheme or parsed.netloc or not parsed.path.startswith("/admin/"):
        return None
    return value


def _login_url(next_value: str | None) -> str:
    if not next_value:
        return "/admin/login"
    from urllib.parse import quote

    return "/admin/login?next=" + quote(next_value, safe="/")


def _event(logger: logging.Logger, event: str, **fields: Any) -> None:
    safe_fields = {key: value for key, value in fields.items() if value is not None}
    logger.info(event, extra={"event": event, **safe_fields})
