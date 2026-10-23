from __future__ import annotations

import pytest

from app.admin_web.query_service import (
    AdminQueryBusy,
    AdminQueryDeadline,
    AdminQueryNotFound,
    AdminQueryResponse,
    AdminQueryUnavailable,
)

from .conftest import SITE_ID, login


DEVICE_ID = "10000000-0000-4000-8000-000000000001"
VISIT_ID = "20000000-0000-4000-8000-000000000001"
FROM = "2026-01-01T00:00:00.000Z"
TO = "2026-01-02T00:00:00.000Z"


class QueryService:
    def __init__(self):
        self.calls = []
        self.failure = None
        self.payload = AdminQueryResponse(
            {"items": [{"safe": True}]},
            {"limit": 100, "next_cursor": None},
        )

    def __getattr__(self, name):
        def call(*args, **kwargs):
            self.calls.append((name, args, kwargs))
            if self.failure is not None:
                raise self.failure
            return self.payload

        return call


@pytest.fixture
def api_client(admin_app):
    service = QueryService()
    admin_app.extensions["admin_web_runtime"].query_service = service
    client = admin_app.test_client()
    login(client)
    return client, service


@pytest.mark.parametrize(
    "path,method",
    [
        (f"/admin/api/v1/sites/{SITE_ID}/summary/visits?from_utc={FROM}&to_utc={TO}", "visit_summary"),
        (f"/admin/api/v1/sites/{SITE_ID}/summary/devices?from_utc={FROM}&to_utc={TO}", "device_summary"),
        (f"/admin/api/v1/sites/{SITE_ID}/devices", "list_devices"),
        (f"/admin/api/v1/sites/{SITE_ID}/devices/{DEVICE_ID}", "device_detail"),
        (f"/admin/api/v1/sites/{SITE_ID}/visits", "list_visits"),
        (f"/admin/api/v1/sites/{SITE_ID}/visits/{VISIT_ID}", "visit_detail"),
        (f"/admin/api/v1/sites/{SITE_ID}/observations/clients?client_mac=02:00:00:00:00:01&from_utc={FROM}&to_utc={TO}", "client_observations"),
        (f"/admin/api/v1/sites/{SITE_ID}/observations/aps?ap_mac=02:00:00:00:00:02&from_utc={FROM}&to_utc={TO}", "ap_observations"),
    ],
)
def test_all_01b_routes_use_session_service_and_safe_envelope(
    api_client, path, method
):
    client, service = api_client
    response = client.get(path, base_url="https://localhost")
    assert response.status_code == 200
    assert response.get_json()["api_version"] == "admin.read.v1"
    assert response.get_json()["site_id"] == SITE_ID
    assert service.calls[-1][0] == method
    assert response.headers["Cache-Control"] == "no-store"
    assert "Access-Control-Allow-Origin" not in response.headers


def test_api_requires_authenticated_session(admin_app):
    response = admin_app.test_client().get(
        f"/admin/api/v1/sites/{SITE_ID}/devices",
        base_url="https://localhost",
    )
    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == "authentication_required"


def test_invalid_and_forbidden_site_stop_before_query_service(api_client):
    client, service = api_client
    invalid = client.get(
        "/admin/api/v1/sites/not-a-site/devices",
        base_url="https://localhost",
    )
    forbidden = client.get(
        f"/admin/api/v1/sites/{'f' * 24}/devices",
        base_url="https://localhost",
    )
    assert invalid.status_code == 400
    assert forbidden.status_code == 403
    assert service.calls == []


@pytest.mark.parametrize(
    "suffix",
    ["?unknown=x", "?limit=1&limit=2", "?mac=x&mac=y"],
)
def test_unknown_or_duplicate_scalar_input_is_rejected(api_client, suffix):
    client, service = api_client
    response = client.get(
        f"/admin/api/v1/sites/{SITE_ID}/devices{suffix}",
        base_url="https://localhost",
    )
    assert response.status_code == 400
    assert service.calls == []


def test_device_mac_filter_is_forwarded_once(api_client):
    client, service = api_client
    response = client.get(
        f"/admin/api/v1/sites/{SITE_ID}/devices?mac=02-00-00-00-00-01",
        base_url="https://localhost",
    )
    assert response.status_code == 200
    assert service.calls[-1][0] == "list_devices"
    assert service.calls[-1][2]["mac"] == "02-00-00-00-00-01"


@pytest.mark.parametrize(
    "failure,status,code",
    [
        (AdminQueryNotFound(), 404, "not_found"),
        (AdminQueryDeadline(), 503, "query_deadline"),
        (AdminQueryUnavailable(), 503, "source_unavailable"),
    ],
)
def test_sanitized_query_error_mapping(api_client, failure, status, code):
    client, service = api_client
    service.failure = failure
    response = client.get(
        f"/admin/api/v1/sites/{SITE_ID}/devices/{DEVICE_ID}",
        base_url="https://localhost",
    )
    assert response.status_code == status
    assert response.get_json()["error"] == {
        "code": code,
        "message": "The request could not be completed.",
    }


def test_query_capacity_returns_retry_after(api_client):
    client, service = api_client
    service.failure = AdminQueryBusy()
    response = client.get(
        f"/admin/api/v1/sites/{SITE_ID}/devices",
        base_url="https://localhost",
    )
    assert response.status_code == 429
    assert response.headers["Retry-After"] == "1"
    assert response.get_json()["error"]["code"] == "concurrency_limit"


def test_response_size_cap_is_enforced_without_truncated_json(api_client):
    client, service = api_client
    service.payload = AdminQueryResponse({"value": "x" * 1_100_000})
    response = client.get(
        f"/admin/api/v1/sites/{SITE_ID}/devices",
        base_url="https://localhost",
    )
    assert response.status_code == 503
    assert response.get_json()["error"]["code"] == "response_too_large"


@pytest.mark.parametrize("visit_version", [6, 7])
def test_device_list_and_inventory_HTTP_use_real_Visit_V6_and_fail_closed_on_future(
    admin_app, tmp_path, visit_version,
):
    import hashlib
    import sqlite3
    from app.admin_web.device_gateway import AdminDeviceReadGateway
    from app.admin_web.query_service import AdminQueryService
    from .test_device_gateway import _native_visit_databases, _native_visit, _snapshot

    paths = _native_visit_databases(tmp_path)
    _snapshot(paths[0], device_id=DEVICE_ID, mac="02:00:00:00:00:01",
              captured_at="2026-01-01T01:00:00.000Z", site_id=SITE_ID)
    _native_visit(paths[1], device_id=DEVICE_ID, mac="02:00:00:00:00:01",
                  started_at="2026-01-01T01:00:00.000Z", site_id=SITE_ID)
    if visit_version == 7:
        # Disposable unsupported future metadata, not an admitted V6 fixture.
        with sqlite3.connect(paths[1]) as connection:
            connection.execute("PRAGMA user_version=7")
    before = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
    runtime = admin_app.extensions["admin_web_runtime"]
    runtime.query_service = AdminQueryService(
        config=runtime.config, policy=runtime.access_policy,
        device_gateway=AdminDeviceReadGateway(*paths), read_gateway=object(),
        visit_analytics_service=object(), inventory_timezone_name="UTC",
    )
    client = admin_app.test_client()
    prefix = f"/admin/api/v1/sites/{SITE_ID}/devices"
    for suffix in ("", "/inventory-summary"):
        denied = client.get(prefix + suffix, base_url="https://localhost")
        assert denied.status_code == 401
    login(client)
    listed = client.get(prefix, base_url="https://localhost")
    inventory = client.get(prefix + "/inventory-summary", base_url="https://localhost")
    if visit_version == 6:
        assert listed.status_code == inventory.status_code == 200
        payload = listed.get_json()
        assert payload["site_id"] == SITE_ID and payload["api_version"] == "admin.read.v1"
        assert len(payload["result"]["items"]) == 1
        item = payload["result"]["items"][0]
        assert item["device_id"] == DEVICE_ID and item["canonical_mac"] == "02:00:00:00:00:01"
        assert item["site_visit_count"] == item["site_snapshot_count"] == 1
        summary = inventory.get_json()["result"]
        assert summary["total_devices"] == 1 and summary["new_devices_today"] == 0
        assert summary["timezone"] == "UTC"
    else:
        assert listed.status_code == inventory.status_code == 503
        assert listed.get_json()["error"]["code"] == "source_unavailable"
        assert inventory.get_json()["error"]["code"] == "source_unavailable"
        assert "result" not in listed.get_json() and "result" not in inventory.get_json()
    for suffix in ("", "/inventory-summary"):
        denied = client.get(f"/admin/api/v1/sites/{'f' * 24}/devices" + suffix,
                            base_url="https://localhost")
        assert denied.status_code == 403
    assert before == {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
