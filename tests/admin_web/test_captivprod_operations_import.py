"""Combined release conflict canaries; no live systemd, DB or configuration IO."""
import ast
import inspect
from pathlib import Path
import subprocess
from unittest.mock import Mock

import pytest
from flask import Flask, g

from app.admin_web import routes
from app.admin_web.operations_service import OperationsError
from tests.admin_web.test_db_services_routes import API, operations_app, logged_in


FAMILIES = (
    (API, "admin.operations.db-services.v1"),
    ("/admin/api/v1/sites/s/devices/d/service-intelligence", "admin.device.service-intelligence.v3"),
    ("/admin/api/v1/sites/s/devices/d/protocol-intelligence", "admin.device.protocol-intelligence.v1"),
    ("/admin/api/v1/settings", "admin.settings.v1"),
    ("/admin/api/v1/settings/features", "admin.settings.features.v1"),
    ("/admin/api/v1/settings/features/generations", "admin.settings.features.mutation.v1"),
    ("/admin/api/v1/settings/portal", "admin.settings.portal.v1"),
    ("/admin/api/v1/settings/portal/generations", "admin.settings.portal.mutation.v1"),
    ("/admin/api/v1/settings/controller", "admin.settings.controller.v3"),
    ("/admin/api/v1/settings/controller/generations", "admin.settings.controller.mutation.v1"),
    ("/admin/api/v1/settings/controller/client-secret/generations", "admin.settings.controller.secret.mutation.v1"),
    ("/admin/api/v1/sites/s/devices", routes.API_VERSION),
)


def assert_error_contract(function, path, version, status):
    app = Flask(__name__)
    with app.test_request_context(path, base_url="https://localhost"):
        g.admin_request_id = "synthetic-captivprod-import"
        g.admin_service_api_version = "admin.device.service-intelligence.v3"
        response = app.make_response(function("synthetic_error", status))
        assert response.status_code == status
        assert response.mimetype == "application/json"
        assert response.json["api_version"] == version
        assert response.json["request_id"] == "synthetic-captivprod-import"
        assert response.json["error"] == ({"code": "synthetic_error", "details": []} if path == API else
            {"code": "synthetic_error", "message": "The request could not be completed."})
        if status in (429, 503):
            assert getattr(g, "admin_device_error_code", None) == "synthetic_error"
        else:
            assert not hasattr(g, "admin_device_error_code")


@pytest.mark.parametrize("path,version", FAMILIES)
@pytest.mark.parametrize("status", [400, 401, 403, 404, 429, 503])
def test_combined_error_dto_and_429_503_attribution(path, version, status):
    assert_error_contract(routes._error, path, version, status)


@pytest.mark.parametrize("status", [429, 503])
def test_negative_canary_rejects_removed_attribution_even_with_correct_dto(status):
    tree = ast.parse(inspect.getsource(routes._error))
    function = tree.body[0]
    assert isinstance(function.body[0], ast.If)
    assert "admin_device_error_code" in ast.unparse(function.body[0])
    del function.body[0]
    namespace = dict(vars(routes))
    exec(compile(ast.fix_missing_locations(tree), "<removed-attribution-canary>", "exec"), namespace)
    with pytest.raises(AssertionError):
        assert_error_contract(namespace["_error"], API, "admin.operations.db-services.v1", status)


@pytest.mark.parametrize("code", ["snapshot_pending", "operations_unavailable"])
def test_real_operations_503_retains_attribution_and_does_not_log_as_device(monkeypatch, caplog, code):
    app, runtime, _ = operations_app(monkeypatch)
    runtime.operations_service = Mock(read=Mock(side_effect=OperationsError(code)))
    try:
        with logged_in(app) as client:
            response = client.get(API, base_url="https://localhost")
            assert response.status_code == 503
            assert response.json["error"] == {"code": code, "details": []}
            assert g.admin_device_error_code == code
            assert response.headers["Cache-Control"] == "no-store"
            assert not any(getattr(record, "event", None) == "admin.device_query_unavailable"
                           for record in caplog.records)
    finally:
        runtime.clear()


def test_feature_off_does_not_construct_sampler_or_stat_or_open_manifest(monkeypatch):
    import app.admin_web.operations_service as service
    constructor = Mock(side_effect=AssertionError("disabled feature constructed sampler"))
    monkeypatch.setattr(service, "AdminOperationsReadService", constructor)
    app, runtime, reads = operations_app(monkeypatch, flag="false")
    try:
        assert runtime.operations_service is None and reads == []
        assert logged_in(app).get(API, base_url="https://localhost").status_code == 404
        assert constructor.mock_calls == [] and reads == []
    finally:
        runtime.clear()


def test_all_existing_error_branches_identical_to_captivprod_base():
    base = subprocess.check_output(["git", "show",
        "0ebda1c53b57fa98d0d0dde82d5ded7ef4b31a66:app/admin_web/routes.py"],
        cwd=Path(__file__).parents[2]).decode("utf-8")
    baseline = next(node for node in ast.parse(base).body if isinstance(node, ast.FunctionDef) and node.name == "_error")
    current = ast.parse(inspect.getsource(routes._error)).body[0]
    assert isinstance(current.body[1], ast.If)
    assert ast.unparse(current.body[1].test) == "request.path == '/admin/api/v1/operations/db-services'"
    del current.body[1]
    assert ast.dump(current) == ast.dump(baseline)
