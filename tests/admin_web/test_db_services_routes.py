import json
import logging
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from flask import Flask

from app.admin_web import operations_inventory as inventory
from app.admin_web.capabilities import DEFAULT_GLOBAL_CAPABILITIES, parse_global_capabilities
from app.admin_web.config import operations_enabled_from_settings, AdminWebConfigError
from app.admin_web.models import AdminPrincipal
from app.admin_web.operations_service import AdminOperationsReadService, OperationsError
from app.admin_web.policy import AdminAccessPolicy
from app.admin_web.runtime import create_admin_web_runtime
from app.settings_control.features import AdminFeaturePlanV1
from app.settings_control.models import ResolvedSettingsSnapshot
from tests.admin_web.conftest import enabled_settings, login, SITE_ID
from tests.admin_web.test_operations_inventory import resolved
from tests.admin_web.test_operations_service import NOW, regular, systemd_text

API = "/admin/api/v1/operations/db-services"
HTML = "/admin/db-services"


def operations_app(monkeypatch, flag="true", grants="admin.read.operations", valid_manifest=True):
    reads = []
    def load():
        reads.append(1)
        if not valid_manifest: raise inventory.InventoryUnavailable()
        return resolved()
    monkeypatch.setattr(inventory, "load_inventory", load)
    settings = enabled_settings(web_admin_db_services_enabled=flag, web_admin_global_capabilities=grants)
    plan = AdminFeaturePlanV1.from_snapshot(ResolvedSettingsSnapshot(None, settings, {}, {}, {}))
    runtime = create_admin_web_runtime(settings, None, None, None, None, logging.getLogger("synthetic.operations"), feature_plan=plan)
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(runtime.blueprint)
    app.extensions["admin_web_runtime"] = runtime
    return app, runtime, reads


def logged_in(app):
    client = app.test_client()
    assert login(client).status_code == 302
    return client


@pytest.mark.parametrize("flag", [True, False, "TRUE", "False", "1", " true", "", None, 1])
def test_exact_startup_flag_rejects_noncanonical_values(flag):
    with pytest.raises(AdminWebConfigError): operations_enabled_from_settings({"web_admin_db_services_enabled": flag})


def test_new_global_grant_independent_not_default_and_not_site_permission():
    assert "admin.read.operations" not in DEFAULT_GLOBAL_CAPABILITIES
    assert parse_global_capabilities("admin.read.operations") == {"admin.read.operations"}
    policy = AdminAccessPolicy(frozenset({SITE_ID}))
    assert policy.authorize_global(AdminPrincipal("op", global_capabilities={"admin.read.operations"}), "admin.read.operations")
    for principal in (AdminPrincipal("op", global_capabilities=DEFAULT_GLOBAL_CAPABILITIES),
                      AdminPrincipal("op", "site_operator", {"admin.read.operations"}),
                      AdminPrincipal("op", global_capabilities={"admin.read.devices"})):
        assert not policy.authorize_global(principal, "admin.read.operations")


def test_off_has_no_inventory_or_service_nav_and_routes_404(monkeypatch):
    from app.admin_web import operations_service
    topology = Mock(side_effect=AssertionError("OFF must not assemble topology"))
    monkeypatch.setattr(operations_service, "topology_snapshot", topology)
    app, runtime, reads = operations_app(monkeypatch, flag="false")
    assert runtime.operations_state == "disabled" and runtime.operations_service is None and reads == []
    client = logged_in(app)
    assert client.get(HTML, base_url="https://localhost").status_code == 404
    assert client.get(API, base_url="https://localhost").status_code == 404
    home = client.get(f"/admin/sites/{SITE_ID}/", base_url="https://localhost")
    assert b"DB &amp; Services" not in home.data and reads == []
    assert topology.mock_calls == []


@pytest.mark.parametrize("grants", ["admin.read.settings.global", "admin.write.settings.global"])
def test_no_grant_403_hidden_and_no_sampling(monkeypatch, grants):
    from app.admin_web import operations_service
    topology = Mock(side_effect=AssertionError("No topology before authorization"))
    monkeypatch.setattr(operations_service, "topology_snapshot", topology)
    app, runtime, _ = operations_app(monkeypatch, grants=grants)
    runtime.operations_service = Mock()
    client = logged_in(app)
    for path in (HTML, API):
        response = client.get(path, base_url="https://localhost")
        assert response.status_code == 403
        assert response.json["error"]["code"] == "operations_forbidden"
    assert b"DB &amp; Services" not in client.get(f"/admin/sites/{SITE_ID}/", base_url="https://localhost").data
    assert runtime.operations_service.mock_calls == []
    assert topology.mock_calls == []
    runtime.clear()


def test_unauthenticated_boundaries_no_source_reads(monkeypatch):
    app, runtime, _ = operations_app(monkeypatch)
    runtime.operations_service = Mock()
    client = app.test_client()
    assert client.get(HTML, base_url="https://localhost").status_code == 302
    assert client.get(API, base_url="https://localhost").status_code == 401
    assert runtime.operations_service.mock_calls == []
    runtime.clear()


def test_global_page_nav_and_no_site_or_settings_controller(monkeypatch):
    app, runtime, reads = operations_app(monkeypatch, grants="admin.read.operations,admin.read.settings.global")
    assert runtime.state == "unavailable" and runtime.query_service is None
    assert runtime.operations_state == "active" and reads == [1]
    client = logged_in(app)
    response = client.get(HTML, base_url="https://localhost")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Databases &amp; Services" in html and "Global Operations" in html
    assert 'data-api-base="' + API + '"' in html
    assert "data-site-id" not in html and "Current Site" not in html and SITE_ID not in html
    assert 'href="/admin/"' in html and 'filename="admin.js"' not in html
    assert "/admin/static/db_services.js" in html and "/admin/static/admin.js" not in html
    assert html.count('class="ops-summary"') == 1
    assert 'aria-current="page">DB &amp; Services' in html
    assert "Devices</a>" not in html and "Visits</a>" not in html
    assert response.headers["Cache-Control"] == "no-store"
    assert "default-src 'self'" in response.headers["Content-Security-Policy"]
    runtime.clear()


def test_site_nav_position_and_manifest_unavailable_does_not_hide_page(monkeypatch):
    app, runtime, _ = operations_app(monkeypatch, valid_manifest=False)
    assert runtime.operations_state == "unavailable" and runtime.operations_service is None
    assert runtime.session_store is not None and runtime.query_service is None
    client = logged_in(app)
    html = client.get(f"/admin/sites/{SITE_ID}/", base_url="https://localhost").get_data(as_text=True)
    assert 'href="/admin/db-services"' in html
    assert client.get(HTML, base_url="https://localhost").status_code == 200
    error = client.get(API, base_url="https://localhost")
    assert error.status_code == 503 and error.json["error"] == {"code": "operations_unavailable", "details": []}
    assert "/etc/" not in error.get_data(as_text=True)
    runtime.clear()


@pytest.mark.parametrize("path", [API, HTML])
@pytest.mark.parametrize("suffix,body", [("?site_id=x", None), ("?path=/secret", None), ("?unit=anything", None),
                                       ("?x=1&x=2", None), ("?", b"body")])
def test_no_query_or_body_before_sampling(monkeypatch, path, suffix, body):
    app, runtime, _ = operations_app(monkeypatch)
    runtime.operations_service = Mock()
    response = logged_in(app).get(path + suffix, data=body, base_url="https://localhost")
    assert response.status_code == 400
    assert runtime.operations_service.mock_calls == []
    runtime.clear()


def test_api_snapshot_partial_summary_and_exact_response_cap(monkeypatch):
    app, runtime, _ = operations_app(monkeypatch)
    # No real systemd or approved-root filesystem probes in focused fixtures.
    def failed(_cancel): raise OSError("SYNTHETIC_PRIVATE_STDERR")
    runtime.operations_service = AdminOperationsReadService(resolved(), acquire=failed, lstat=regular, now=lambda: NOW)
    response = logged_in(app).get(API, base_url="https://localhost")
    assert response.status_code == 200
    model = response.json
    assert model["scope"] == "global" and model["snapshot_state"] == "partial"
    assert len(model["services"]) == 9 and len(model["databases"]) == 17
    assert len(response.data) <= 48000
    assert model["summary"]["databases"]["present_unverified"] == 17
    assert "SYNTHETIC_PRIVATE_STDERR" not in response.get_data(as_text=True)
    assert "/opt/" not in response.get_data(as_text=True)
    runtime.clear()


@pytest.mark.parametrize("code", ["snapshot_pending", "operations_unavailable"])
def test_safe_503_and_unrelated_runtime_unchanged(monkeypatch, code):
    app, runtime, _ = operations_app(monkeypatch)
    before = runtime.state
    runtime.operations_service = Mock(read=Mock(side_effect=OperationsError(code)))
    response = logged_in(app).get(API, base_url="https://localhost")
    assert response.status_code == 503 and response.json["error"]["code"] == code
    assert runtime.state == before
    runtime.clear()
    runtime.operations_service.close.assert_called_once_with()


def test_response_oversize_and_exception_are_private(monkeypatch):
    app, runtime, _ = operations_app(monkeypatch)
    runtime.operations_service = Mock(read=Mock(return_value={"x": "SYNTHETIC_PRIVATE_CANARY" * 5000}))
    client = logged_in(app)
    assert client.get(API, base_url="https://localhost").status_code == 503
    runtime.operations_service.read.side_effect = RuntimeError("/private/SYNTHETIC_PRIVATE_CANARY")
    error = client.get(API, base_url="https://localhost")
    assert error.status_code == 503 and "SYNTHETIC_PRIVATE_CANARY" not in error.get_data(as_text=True)
    runtime.clear()


def test_invalid_feature_is_isolated_and_never_reads_manifest(monkeypatch):
    app, runtime, reads = operations_app(monkeypatch, flag="INVALID")
    assert runtime.operations_state == "unavailable" and runtime.operations_service is None
    assert reads == [] and runtime.session_store is not None
    assert login(app.test_client()).status_code == 302
    runtime.clear()


@pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
def test_no_mutation_methods_standard_405(monkeypatch, method):
    app, runtime, _ = operations_app(monkeypatch)
    runtime.operations_service = Mock()
    assert getattr(logged_in(app), method)(API, base_url="https://localhost").status_code == 405
    assert runtime.operations_service.mock_calls == []
    runtime.clear()
