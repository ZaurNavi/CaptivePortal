"""Admin Security + Site Context HTTP boundary for Web Foundation 01A."""

from __future__ import annotations

import hmac
import ipaddress
import logging
import time
import uuid
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
from .policy import AdminAccessDenied, AdminSiteContextError
from .tokens import is_canonical_token, token_matches


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
        if any(len(request.args.getlist(key)) != 1 for key in request.args):
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
        try:
            selected = resolver.resolve(site_id)
        except AdminSiteContextError:
            return _error("invalid_request", 400)
        except AdminAccessDenied:
            return _error("site_forbidden", 403)
        if not policy.authorize(g.admin_principal, "admin.read.context", selected):
            return _error("site_forbidden", 403)
        return make_response(
            render_template(
                "admin_shell.html",
                site_id=selected,
                username=g.admin_principal.username,
                csrf_token=g.admin_session.csrf_token,
                runtime_state=runtime.state,
            )
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

    def _success(site_id: str | None, result: dict[str, Any], *, status_code: int = 200) -> Response:
        return jsonify(
            {
                "api_version": API_VERSION,
                "request_id": g.admin_request_id,
                "site_id": site_id,
                "result": result,
                "page": None,
            }
        ), status_code

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
