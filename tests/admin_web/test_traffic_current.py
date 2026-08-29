from __future__ import annotations

import logging
from types import SimpleNamespace

import pytest
from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix

from app.admin_web import create_admin_web_runtime
from app.admin_web.current_traffic_serialization import serialize_current_traffic_summary
from app.admin_web.policy import AdminAccessPolicy
from app.admin_web.query_service import AdminQueryBusy, AdminQueryDeadline

from .conftest import SITE_ID, enabled_settings, login
from .test_home_traffic import TrafficSource, traffic_summary


def _app(tmp_path, source, *, enabled: bool = True) -> Flask:
    runtime = create_admin_web_runtime(
        enabled_settings(
            web_admin_traffic_enabled="true" if enabled else "false",
            web_admin_home_live_enabled="false",
            web_admin_home_traffic_enabled="false",
        ),
        SimpleNamespace(
            state="active",
            visit_service=object(),
            current_traffic_service=source,
        ),
        SimpleNamespace(
            repository=SimpleNamespace(
                config=SimpleNamespace(db_path=tmp_path / "registry.sqlite3")
            )
        ),
        SimpleNamespace(repository=SimpleNamespace(db_path=tmp_path / "visits.sqlite3")),
        SimpleNamespace(
            _repository=SimpleNamespace(db_path=tmp_path / "observations.sqlite3")
        ),
        logging.getLogger("traffic-current-test"),
    )
    app = Flask(__name__)
    app.config.update(TESTING=True)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)
    app.register_blueprint(runtime.blueprint)
    app.extensions["admin_web_runtime"] = runtime
    return app


def _url(site_id: str = SITE_ID) -> str:
    return f"/admin/api/v1/sites/{site_id}/traffic/current"


@pytest.mark.parametrize("mode", ["complete", "partial", "empty", "none"])
def test_current_traffic_route_reuses_canonical_summary_serializer(tmp_path, mode):
    source = TrafficSource()
    source.summary = traffic_summary(mode=mode)
    app = _app(tmp_path, source)
    client = app.test_client()
    assert login(client).status_code == 302

    response = client.get(_url(), base_url="https://localhost")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["api_version"] == "admin.read.v1"
    assert payload["site_id"] == SITE_ID
    assert payload["result"] == serialize_current_traffic_summary(source.summary, SITE_ID)
    assert len(source.calls) == 1
    operation, called_site, options = source.calls[0]
    assert operation == "summary" and called_site == SITE_ID
    assert set(options) == {
        "deadline",
        "fresh_max_age_seconds",
        "stale_max_age_seconds",
        "max_ap_skew_seconds",
    }
    assert options["deadline"].expired() is False
    assert options["fresh_max_age_seconds"] == 90
    assert options["stale_max_age_seconds"] == 180
    assert options["max_ap_skew_seconds"] == 60


def test_current_traffic_security_order_and_capabilities(tmp_path, monkeypatch):
    calls = []
    original = AdminAccessPolicy.authorize

    def recording(self, principal, capability, site_id):
        calls.append((capability, site_id))
        return original(self, principal, capability, site_id)

    monkeypatch.setattr(AdminAccessPolicy, "authorize", recording)
    source = TrafficSource()
    app = _app(tmp_path, source)
    anonymous = app.test_client()
    assert anonymous.get(
        f"{_url()}?bad=1&bad=2", base_url="https://localhost"
    ).status_code == 401
    assert calls == [] and source.calls == []

    client = app.test_client()
    assert login(client).status_code == 302
    assert client.get(_url("not-a-site"), base_url="https://localhost").status_code == 400
    assert client.get(
        f"{_url('f' * 24)}?bad=1&bad=2", base_url="https://localhost"
    ).status_code == 403
    assert source.calls == []

    assert client.get(_url(), base_url="https://localhost").status_code == 200
    assert calls[-2:] == [
        ("admin.read.context", SITE_ID),
        ("admin.read.overview", SITE_ID),
    ]


@pytest.mark.parametrize("query", ["bad=1", "bad=1&bad=2", "limit=1"])
def test_current_traffic_rejects_all_query_parameters_before_source(tmp_path, query):
    source = TrafficSource()
    app = _app(tmp_path, source)
    client = app.test_client()
    assert login(client).status_code == 302

    response = client.get(f"{_url()}?{query}", base_url="https://localhost")

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "invalid_request"
    assert source.calls == []


def test_current_traffic_feature_disabled_is_canonical_404_after_security(tmp_path):
    source = TrafficSource()
    app = _app(tmp_path, source, enabled=False)
    anonymous = app.test_client()
    duplicate = f"{_url()}?bad=1&bad=2"
    assert anonymous.get(duplicate, base_url="https://localhost").status_code == 401
    client = app.test_client()
    assert login(client).status_code == 302
    assert client.get(duplicate, base_url="https://localhost").status_code == 404
    assert source.calls == []


def test_current_traffic_source_unavailable_is_isolated_503(tmp_path):
    app = _app(tmp_path, None)
    client = app.test_client()
    assert login(client).status_code == 302

    response = client.get(_url(), base_url="https://localhost")

    assert response.status_code == 503
    assert response.get_json()["error"]["code"] == "source_unavailable"


@pytest.mark.parametrize(
    "error,code,retry_after",
    [
        (AdminQueryBusy("busy"), "concurrency_limit", "1"),
        (AdminQueryDeadline("deadline"), "query_deadline", None),
    ],
)
def test_current_traffic_preserves_query_boundary_errors(
    tmp_path, monkeypatch, error, code, retry_after
):
    source = TrafficSource()
    app = _app(tmp_path, source)
    runtime = app.extensions["admin_web_runtime"]

    def fail(*_args, **_kwargs):
        raise error

    monkeypatch.setattr(runtime.query_service, "current_traffic_summary", fail)
    client = app.test_client()
    assert login(client).status_code == 302

    response = client.get(_url(), base_url="https://localhost")

    assert response.status_code in {429, 503}
    assert response.get_json()["error"]["code"] == code
    assert response.headers.get("Retry-After") == retry_after
    assert source.calls == []


def test_current_traffic_template_and_scope_are_read_only(tmp_path):
    app = _app(tmp_path, TrafficSource())
    client = app.test_client()
    assert login(client).status_code == 302
    body = client.get(
        f"/admin/sites/{SITE_ID}/traffic", base_url="https://localhost"
    ).get_data(as_text=True)
    assert "Current Network Throughput" in body
    assert "not an Internet-only measurement" in body
    assert 'id="traffic-current-download">—' in body
    assert "<script>" not in body

    route_source = open("app/admin_web/routes.py", encoding="utf-8").read()
    assert "OmadaProvider" not in route_source
    assert "INSERT " not in route_source and "UPDATE " not in route_source
