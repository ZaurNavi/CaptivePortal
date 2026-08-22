from __future__ import annotations

from urllib.parse import quote

import pytest
from flask import Flask
from werkzeug.datastructures import MultiDict

import app.admin_web.routes as routes
from app.admin_web import create_admin_web_runtime

from .conftest import PASSWORD, SITE_ID, csrf_from, enabled_settings, login


def test_login_requires_https_and_allowed_source(admin_app):
    client = admin_app.test_client()
    assert client.get("/admin/login").status_code == 403
    forbidden = client.get(
        "/admin/login",
        base_url="https://localhost",
        environ_overrides={"REMOTE_ADDR": "192.0.2.10"},
    )
    assert forbidden.status_code == 403


def test_one_trusted_proxy_hop_controls_https_and_source(admin_app):
    client = admin_app.test_client()
    response = client.get(
        "/admin/login",
        headers={
            "X-Forwarded-Proto": "https",
            "X-Forwarded-For": "127.0.0.1",
        },
        environ_overrides={"REMOTE_ADDR": "127.0.0.1"},
    )
    assert response.status_code == 200


def test_login_form_issues_one_time_state_and_security_headers(admin_app):
    response = admin_app.test_client().get(
        "/admin/login", base_url="https://localhost"
    )
    assert response.status_code == 200
    assert len(csrf_from(response)) == 43
    cookie = response.headers["Set-Cookie"]
    assert "captivportal_admin_preauth=" in cookie
    assert "Secure" in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=Strict" in cookie
    assert "Path=/admin/login" in cookie
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "default-src 'self'" in response.headers["Content-Security-Policy"]
    assert "Access-Control-Allow-Origin" not in response.headers


def test_full_preauth_store_returns_sanitized_503(admin_app):
    runtime = admin_app.extensions["admin_web_runtime"]
    runtime.preauth_store._max_states = 1
    first = admin_app.test_client().get(
        "/admin/login", base_url="https://localhost"
    )
    second = admin_app.test_client().get(
        "/admin/login", base_url="https://localhost"
    )
    assert first.status_code == 200
    assert second.status_code == 503
    assert second.data == b"The request could not be completed."


def test_valid_login_rotates_session_and_logout_revokes(admin_app):
    client = admin_app.test_client()
    response = login(client)
    assert response.status_code == 302
    assert response.headers["Location"].endswith(f"/admin/sites/{SITE_ID}/")
    session_cookie = next(
        value for value in response.headers.getlist("Set-Cookie")
        if value.startswith("captivportal_admin_session=")
    )
    assert all(value in session_cookie for value in ("Secure", "HttpOnly", "SameSite=Strict", "Path=/admin"))

    shell = client.get(f"/admin/sites/{SITE_ID}/", base_url="https://localhost")
    assert shell.status_code == 200
    raw_session_token = session_cookie.split("=", 1)[1].split(";", 1)[0]
    assert raw_session_token.encode("ascii") not in shell.data
    csrf = csrf_from(shell)
    logout = client.post(
        "/admin/logout",
        data={"csrf_token": csrf},
        base_url="https://localhost",
    )
    assert logout.status_code == 302
    assert "Max-Age=0" in logout.headers["Set-Cookie"]
    denied = client.get(
        f"/admin/sites/{SITE_ID}/", base_url="https://localhost"
    )
    assert denied.status_code == 302


@pytest.mark.parametrize("username,password", [("unknown", PASSWORD), ("operator", "wrong")])
def test_invalid_credentials_are_generic_and_hash_once(
    admin_app, monkeypatch, username, password
):
    client = admin_app.test_client()
    form = client.get("/admin/login", base_url="https://localhost")
    token = csrf_from(form)
    original = routes.check_password_hash
    calls = []

    def checked(value, submitted):
        calls.append((value, submitted))
        return original(value, submitted)

    monkeypatch.setattr(routes, "check_password_hash", checked)
    response = client.post(
        "/admin/login",
        data={"username": username, "password": password, "csrf_token": token},
        base_url="https://localhost",
    )
    assert response.status_code == 401
    assert b"Authentication failed." in response.data
    assert username.encode() not in response.data
    assert password.encode() not in response.data
    assert len(calls) == 1
    assert any(
        "captivportal_admin_preauth=" in value and "Max-Age=0" in value
        for value in response.headers.getlist("Set-Cookie")
    )


def test_correct_credential_hashes_once_and_deletes_preauth(admin_app, monkeypatch):
    client = admin_app.test_client()
    token = csrf_from(client.get("/admin/login", base_url="https://localhost"))
    original = routes.check_password_hash
    calls = []

    def checked(value, submitted):
        calls.append((value, submitted))
        return original(value, submitted)

    monkeypatch.setattr(routes, "check_password_hash", checked)
    response = client.post(
        "/admin/login",
        data={"username": "operator", "password": PASSWORD, "csrf_token": token},
        base_url="https://localhost",
    )
    assert response.status_code == 302
    assert len(calls) == 1
    assert any(
        "captivportal_admin_preauth=" in value and "Max-Age=0" in value
        for value in response.headers.getlist("Set-Cookie")
    )


def test_unicode_username_is_rejected_before_hash(admin_app, monkeypatch):
    client = admin_app.test_client()
    token = csrf_from(client.get("/admin/login", base_url="https://localhost"))
    monkeypatch.setattr(
        routes,
        "check_password_hash",
        lambda *_: pytest.fail("password hash must not run"),
    )
    response = client.post(
        "/admin/login",
        data={"username": "opérator", "password": "wrong", "csrf_token": token},
        base_url="https://localhost",
    )
    assert response.status_code == 400


def test_full_session_store_rejects_before_password_hash(admin_app, monkeypatch):
    runtime = admin_app.extensions["admin_web_runtime"]
    runtime.session_store._max_sessions = 1
    reservation = runtime.session_store.reserve()
    runtime.session_store.commit(reservation, routes.AdminPrincipal("existing"))
    client = admin_app.test_client()
    token = csrf_from(client.get("/admin/login", base_url="https://localhost"))
    monkeypatch.setattr(
        routes,
        "check_password_hash",
        lambda *_: pytest.fail("password hash must not run at capacity"),
    )
    response = client.post(
        "/admin/login",
        data={"username": "operator", "password": PASSWORD, "csrf_token": token},
        base_url="https://localhost",
    )
    assert response.status_code == 503
    assert runtime.rate_limiter.size() == 0


@pytest.mark.parametrize(
    "username,password",
    [("operator", PASSWORD), ("operator", "wrong"), ("unknown", PASSWORD)],
)
def test_capacity_response_is_credential_independent(
    admin_app, monkeypatch, username, password
):
    runtime = admin_app.extensions["admin_web_runtime"]
    runtime.session_store._max_sessions = 1
    reservation = runtime.session_store.reserve()
    runtime.session_store.commit(reservation, routes.AdminPrincipal("existing"))
    client = admin_app.test_client()
    token = csrf_from(client.get("/admin/login", base_url="https://localhost"))
    calls = []
    monkeypatch.setattr(routes, "check_password_hash", lambda *_: calls.append(1))
    response = client.post(
        "/admin/login",
        data={"username": username, "password": password, "csrf_token": token},
        base_url="https://localhost",
    )
    assert response.status_code == 503
    assert response.data == b"The request could not be completed."
    assert calls == []


def test_rate_lock_is_checked_before_csrf_and_password(admin_app, monkeypatch):
    runtime = admin_app.extensions["admin_web_runtime"]
    for _ in range(runtime.config.login_max_failures):
        assert runtime.rate_limiter.begin_attempt("127.0.0.1") == "allowed"
        runtime.rate_limiter.finish_attempt("127.0.0.1", "failure")
    client = admin_app.test_client()
    token = csrf_from(client.get("/admin/login", base_url="https://localhost"))
    before = runtime.preauth_store.size()
    monkeypatch.setattr(
        routes,
        "check_password_hash",
        lambda *_: pytest.fail("locked login must not verify password"),
    )
    response = client.post(
        "/admin/login",
        data={"username": "operator", "password": PASSWORD, "csrf_token": token},
        base_url="https://localhost",
    )
    assert response.status_code == 429
    assert runtime.preauth_store.size() == before


def test_rate_capacity_is_reserved_before_csrf_and_password(admin_app, monkeypatch):
    runtime = admin_app.extensions["admin_web_runtime"]
    runtime.rate_limiter._max_trackers = 1
    assert runtime.rate_limiter.begin_attempt("192.0.2.1") == "allowed"
    client = admin_app.test_client()
    token = csrf_from(client.get("/admin/login", base_url="https://localhost"))
    before = runtime.preauth_store.size()
    monkeypatch.setattr(
        routes,
        "check_password_hash",
        lambda *_: pytest.fail("capacity rejection must not verify password"),
    )
    response = client.post(
        "/admin/login",
        data={"username": "operator", "password": PASSWORD, "csrf_token": token},
        base_url="https://localhost",
    )
    assert response.status_code == 429
    assert runtime.preauth_store.size() == before
    runtime.rate_limiter.finish_attempt("192.0.2.1", "neutral")


def test_csrf_replay_is_rejected_before_password_hash(admin_app, monkeypatch):
    client = admin_app.test_client()
    form = client.get("/admin/login", base_url="https://localhost")
    token = csrf_from(form)
    preauth_cookie = next(
        part.split(";", 1)[0].split("=", 1)[1]
        for part in form.headers.getlist("Set-Cookie")
        if part.startswith("captivportal_admin_preauth=")
    )
    first = client.post(
        "/admin/login",
        data={"username": "operator", "password": "wrong", "csrf_token": token},
        base_url="https://localhost",
    )
    assert first.status_code == 401
    client.set_cookie("captivportal_admin_preauth", preauth_cookie, domain="localhost")
    monkeypatch.setattr(
        routes,
        "check_password_hash",
        lambda *_: pytest.fail("replayed CSRF must not verify password"),
    )
    replay = client.post(
        "/admin/login",
        data={"username": "operator", "password": PASSWORD, "csrf_token": token},
        base_url="https://localhost",
    )
    assert replay.status_code == 400


def test_login_exception_releases_capacity_and_deletes_preauth(admin_app, monkeypatch):
    runtime = admin_app.extensions["admin_web_runtime"]
    client = admin_app.test_client()
    token = csrf_from(client.get("/admin/login", base_url="https://localhost"))
    monkeypatch.setattr(
        routes,
        "check_password_hash",
        lambda *_: (_ for _ in ()).throw(RuntimeError("safe failure")),
    )
    response = client.post(
        "/admin/login",
        data={"username": "operator", "password": PASSWORD, "csrf_token": token},
        base_url="https://localhost",
    )
    assert response.status_code == 500
    assert runtime.session_store.counts() == (0, 0)
    assert runtime.rate_limiter.size() == 0
    assert any(
        "captivportal_admin_preauth=" in value and "Max-Age=0" in value
        for value in response.headers.getlist("Set-Cookie")
    )


def test_invalid_csrf_does_not_count_as_password_failure():
    runtime = create_admin_web_runtime(
        enabled_settings(web_admin_login_max_failures="1"),
        __import__("types").SimpleNamespace(state="active"),
        object(), object(), object(),
        __import__("logging").getLogger("admin-csrf-rate-test"),
    )
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(runtime.blueprint)
    client = app.test_client()
    token = csrf_from(client.get("/admin/login", base_url="https://localhost"))
    bad = client.post(
        "/admin/login",
        data={"username": "operator", "password": "wrong", "csrf_token": token[:-1] + "="},
        base_url="https://localhost",
    )
    assert bad.status_code == 400
    assert runtime.rate_limiter.size() == 0
    valid_token = csrf_from(client.get("/admin/login", base_url="https://localhost"))
    failure = client.post(
        "/admin/login",
        data={"username": "operator", "password": "wrong", "csrf_token": valid_token},
        base_url="https://localhost",
    )
    assert failure.status_code == 401


def test_request_limits_and_duplicate_scalars_are_admin_only(admin_app):
    client = admin_app.test_client()
    wrong_type = client.post(
        "/admin/login",
        json={},
        base_url="https://localhost",
    )
    assert wrong_type.status_code == 415
    duplicate = client.post(
        "/admin/login",
        data=MultiDict(
            [
                ("username", "operator"),
                ("username", "other"),
                ("password", PASSWORD),
                ("csrf_token", "a" * 43),
            ]
        ),
        base_url="https://localhost",
    )
    assert duplicate.status_code == 400
    duplicate_query = client.get(
        "/admin/login?next=/admin/&next=/admin/other",
        base_url="https://localhost",
    )
    assert duplicate_query.status_code == 400
    oversized_query = client.get(
        "/admin/login?next=" + ("a" * 9000),
        base_url="https://localhost",
    )
    assert oversized_query.status_code == 400


@pytest.mark.parametrize(
    "field,value",
    [
        ("username", "a" * 129),
        ("password", "a" * 1025),
        ("csrf_token", "a" * 257),
    ],
)
def test_login_field_bounds_reject_before_password_hash(
    admin_app, monkeypatch, field, value
):
    client = admin_app.test_client()
    token = csrf_from(client.get("/admin/login", base_url="https://localhost"))
    data = {"username": "operator", "password": PASSWORD, "csrf_token": token}
    data[field] = value
    monkeypatch.setattr(
        routes,
        "check_password_hash",
        lambda *_: pytest.fail("over-limit input must not verify password"),
    )
    response = client.post(
        "/admin/login", data=data, base_url="https://localhost"
    )
    assert response.status_code == 400


def test_missing_content_length_is_411(admin_app):
    with admin_app.test_request_context(
        "/admin/login",
        method="POST",
        base_url="https://localhost",
        content_type="application/x-www-form-urlencoded",
        environ_overrides={"CONTENT_LENGTH": None, "REMOTE_ADDR": "127.0.0.1"},
    ):
        response = admin_app.make_response(admin_app.preprocess_request())
        assert response.status_code == 411


def test_oversized_post_is_rejected_before_form_parsing():
    runtime = create_admin_web_runtime(
        enabled_settings(web_admin_max_post_bytes="1024"),
        object(), object(), object(), object(),
        __import__("logging").getLogger("admin-limit-test"),
    )
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(runtime.blueprint)
    response = app.test_client().post(
        "/admin/login",
        data="x" * 1025,
        content_type="application/x-www-form-urlencoded",
        base_url="https://localhost",
    )
    assert response.status_code == 413


def test_open_redirect_falls_back_to_default_site(admin_app):
    client = admin_app.test_client()
    response = login(client, next_value=quote("https://evil.example/", safe=""))
    assert response.status_code == 302
    assert response.headers["Location"].endswith(f"/admin/sites/{SITE_ID}/")


def test_site_context_and_minimal_api_are_session_protected(admin_app):
    client = admin_app.test_client()
    unauthenticated = client.get(
        "/admin/api/v1/session", base_url="https://localhost"
    )
    assert unauthenticated.status_code == 401
    assert unauthenticated.json["error"]["code"] == "authentication_required"
    login(client)
    session = client.get("/admin/api/v1/session", base_url="https://localhost")
    assert session.status_code == 200
    assert session.json["result"]["principal_type"] == "platform_operator"
    sites = client.get("/admin/api/v1/sites", base_url="https://localhost")
    assert sites.json["result"]["site_ids"] == [SITE_ID]
    health = client.get("/admin/api/v1/health", base_url="https://localhost")
    assert health.status_code == 200


def test_forbidden_site_is_rejected_without_fallback(admin_app):
    client = admin_app.test_client()
    login(client)
    invalid = client.get("/admin/sites/ABC/", base_url="https://localhost")
    forbidden = client.get(
        "/admin/sites/ffffffffffffffffffffffff/",
        base_url="https://localhost",
    )
    assert invalid.status_code == 400
    assert forbidden.status_code == 403


def test_unicode_logout_csrf_is_controlled_failure(admin_app):
    client = admin_app.test_client()
    login(client)
    response = client.post(
        "/admin/logout",
        data={"csrf_token": "é" * 43},
        base_url="https://localhost",
    )
    assert response.status_code == 400
