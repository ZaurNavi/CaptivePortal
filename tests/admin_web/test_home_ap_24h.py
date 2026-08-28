from __future__ import annotations

from datetime import datetime, timedelta, timezone
from copy import deepcopy
from types import SimpleNamespace

import pytest

from app.admin_web.config import admin_web_config_from_settings
from app.admin_web.home_ap_24h_config import (
    HomeAp24ConfigError,
    home_ap_24h_config_from_settings,
)
from app.admin_web.cursors import encode_cursor
from app.admin_web.models import AdminPrincipal
from app.admin_web.home_ap_24h_serialization import (
    HomeAp24SerializationError,
    serialize_home_ap_24h,
)
from app.admin_web.policy import AdminAccessPolicy
from app.admin_web.query_service import (
    AdminQueryBusy,
    AdminQueryDeadline,
    AdminQueryService,
    AdminQueryUnavailable,
    AdminQueryValidationError,
)
from app.analytics.home_ap_24h import CONTRACT_VERSION

from .conftest import SITE_ID, enabled_settings
from .conftest import login


ANCHOR = "2026-08-28T12:00:00.000Z"
AP = "AA:BB:CC:DD:EE:01"


def result(*, has_more=False):
    window_start = datetime(2026, 8, 27, 12, tzinfo=timezone.utc)
    timeline = []
    for index in range(96):
        bucket_start = window_start + timedelta(minutes=15 * index)
        bucket_end = bucket_start + timedelta(minutes=15)
        timeline.append({
            "from_utc": bucket_start.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            "to_utc": bucket_end.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            "ap_state": "operational", "ap_state_reason": "operational_evidence",
            "observation_quality": "operational", "observation_reason_codes": [],
            "operational_seconds": 900, "unavailable_seconds": 0,
            "unknown_evidence_seconds": 0, "short_history_seconds": 0,
            "authoritative_state_sample_count": 1,
            "complete_observation_sample_count": 1,
            "diagnostic_partial_observation_sample_count": 0,
        })
    counts = {"operational": 1, "degraded": 0, "unavailable": 0, "unknown": 0}
    source = {
        "status": "operational", "schema_version": 1,
        "first_evidence_at": ANCHOR, "last_evidence_at": ANCHOR,
        "complete_cycle_count": 1, "partial_cycle_count": 0,
        "failed_cycle_count": 0, "max_gap_seconds": None,
    }
    return {
        "contract_version": CONTRACT_VERSION,
        "window": {"kind": "rolling_24h", "evaluated_at_utc": ANCHOR,
                   "from_utc": "2026-08-27T12:00:00.000Z", "to_utc": ANCHOR,
                   "bucket_seconds": 900, "bucket_count": 96},
        "block_status": "operational", "block_reason": None,
        "sources": {"current_state": source, "observations": dict(source)},
        "summary": {"ap_count_in_window": 1, "current": counts,
                    "history": dict(counts), "observation_quality": dict(counts),
                    "short_history_ap_count": 0, "status_gap_ap_count": 0,
                    "observation_problem_ap_count": 0},
        "items": [{
            "ap_mac": AP, "name": "AP", "model": "EAP", "identity_source": "current_state",
            "current": {"status": "operational", "reason_code": "fresh_online_evidence",
                        "observed_at": ANCHOR, "freshness_status": "fresh"},
            "history": {"status": "operational", "reason_code": "operational_history",
                        "coverage_status": "complete", "history_eligible_from": ANCHOR,
                        "first_evidence_at": ANCHOR, "last_evidence_at": ANCHOR,
                        "authoritative_sample_count": 1, "operational_seconds": 86400,
                        "unavailable_seconds": 0, "unknown_evidence_seconds": 0,
                        "short_history_seconds": 0, "max_gap_seconds": 60,
                        "current_vs_24h": "consistent_with_24h_online_evidence"},
            "observation_quality": {"status": "operational", "reason_code": None,
                                    "complete_sample_count": 1,
                                    "diagnostic_partial_sample_count": 0,
                                    "section_problem_counts": {"overview": 0, "wired_uplink": 0,
                                                               "lan_traffic": 0, "radios": 0}},
            "timeline": timeline,
        }],
        "page": {"limit": 20, "has_more": has_more},
    }


class Source:
    def __init__(self):
        self.calls = []

    def get_home_ap_24h(self, site_id, **kwargs):
        self.calls.append((site_id, kwargs))
        return result(has_more=len(self.calls) == 1)


def query_service(source):
    config = admin_web_config_from_settings(enabled_settings())
    return AdminQueryService(
        config=config,
        policy=AdminAccessPolicy(config.allowed_site_ids),
        device_gateway=object(), read_gateway=object(), visit_analytics_service=object(),
        home_ap_24h_read_service=source,
    )


def test_config_default_disabled_ignores_broken_optional_values():
    admin = admin_web_config_from_settings(enabled_settings())
    value = home_ap_24h_config_from_settings({
        "web_admin_home_ap_24h_enabled": "false",
        "web_admin_home_ap_24h_refresh_seconds": "broken",
    }, admin_config=admin)
    assert value.enabled is False
    assert value.refresh_seconds == 120


@pytest.mark.parametrize("key,value", [
    ("web_admin_home_ap_24h_refresh_seconds", "59"),
    ("web_admin_home_ap_24h_request_timeout_seconds", "10"),
])
def test_enabled_config_is_bounded(key, value):
    admin = admin_web_config_from_settings(enabled_settings())
    settings = {"web_admin_home_ap_24h_enabled": "true", key: value}
    with pytest.raises(HomeAp24ConfigError):
        home_ap_24h_config_from_settings(settings, admin_config=admin)


def test_query_cursor_preserves_anchor_and_binds_site_limit_and_mac():
    source = Source(); service = query_service(source); principal = AdminPrincipal("operator")
    first = service.home_ap_24h(principal, SITE_ID, limit="20")
    cursor = first.result["page"]["next_cursor"]
    assert cursor
    second = service.home_ap_24h(principal, SITE_ID, limit="20", cursor=cursor)
    assert source.calls[0][1]["evaluated_at_utc"] is None
    assert source.calls[1][1]["evaluated_at_utc"] == datetime(2026, 8, 28, 12, tzinfo=timezone.utc)
    assert source.calls[1][1]["after_ap_mac"] == AP
    assert second.result["window"]["evaluated_at_utc"] == ANCHOR
    with pytest.raises(AdminQueryValidationError):
        service.home_ap_24h(principal, SITE_ID, limit="19", cursor=cursor)


@pytest.mark.parametrize("cursor", [
    "%%%",
    encode_cursor(
        kind="wrong_kind", site_id=SITE_ID, timestamp=ANCHOR, identity=AP,
        filters={"limit": 20, "contract_version": CONTRACT_VERSION,
                 "window": "rolling_24h:900:96"},
    ),
    encode_cursor(
        kind="home_ap_24h", site_id="f" * 24, timestamp=ANCHOR, identity=AP,
        filters={"limit": 20, "contract_version": CONTRACT_VERSION,
                 "window": "rolling_24h:900:96"},
    ),
    encode_cursor(
        kind="home_ap_24h", site_id=SITE_ID, timestamp=ANCHOR,
        identity="aa:bb:cc:dd:ee:01",
        filters={"limit": 20, "contract_version": CONTRACT_VERSION,
                 "window": "rolling_24h:900:96"},
    ),
])
def test_query_rejects_malformed_or_context_mismatched_cursors(cursor):
    with pytest.raises(AdminQueryValidationError):
        query_service(Source()).home_ap_24h(
            AdminPrincipal("operator"), SITE_ID, limit="20", cursor=cursor
        )


@pytest.mark.parametrize("limit", ["0", "01", "21", "x", ""])
def test_query_rejects_noncanonical_page_limits(limit):
    with pytest.raises(AdminQueryValidationError):
        query_service(Source()).home_ap_24h(AdminPrincipal("operator"), SITE_ID, limit=limit)


def test_disabled_route_is_canonical_404_after_authentication(admin_app):
    client = admin_app.test_client()
    login(client)
    response = client.get(
        f"/admin/api/v1/sites/{SITE_ID}/home/ap-24h",
        base_url="https://localhost",
    )
    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "not_found"


def test_home_page_uses_browser_compatible_ap24_dataset_contract(admin_app):
    runtime = admin_app.extensions["admin_web_runtime"]
    runtime.home_ap_24h_state = "active"
    runtime.home_ap_24h_config = SimpleNamespace(
        enabled=True,
        refresh_seconds=121,
        request_timeout_seconds=21,
    )
    client = admin_app.test_client()
    login(client)

    response = client.get(
        f"/admin/sites/{SITE_ID}/",
        base_url="https://localhost",
    )

    assert response.status_code == 200
    text = response.get_data(as_text=True)
    assert 'data-home-ap24h-enabled="true"' in text
    assert 'data-home-ap24h-unavailable="false"' in text
    assert 'data-home-ap24h-refresh-seconds="121"' in text
    assert 'data-home-ap24h-request-timeout-seconds="21"' in text
    assert "data-home-ap-24h-enabled" not in text
    assert "data-home-ap-24h-unavailable" not in text
    assert "data-home-ap-24h-refresh-seconds" not in text
    assert "data-home-ap-24h-request-timeout-seconds" not in text


def test_route_rejects_duplicate_or_unknown_parameters_before_source(admin_app):
    client = admin_app.test_client(); login(client)
    runtime = admin_app.extensions["admin_web_runtime"]
    calls = []

    class Query:
        def home_ap_24h(self, *_args, **_kwargs):
            calls.append(True)
            return SimpleNamespace(result=result())

    runtime.home_ap_24h_state = "active"
    runtime.query_service = Query()
    for query in ("limit=20&limit=20", "unknown=1"):
        response = client.get(
            f"/admin/api/v1/sites/{SITE_ID}/home/ap-24h?{query}",
            base_url="https://localhost",
        )
        assert response.status_code == 400
    assert calls == []


def test_route_returns_size_bounded_site_scoped_payload(admin_app):
    client = admin_app.test_client(); login(client)
    runtime = admin_app.extensions["admin_web_runtime"]

    class Query:
        def home_ap_24h(self, principal, site_id, **kwargs):
            assert isinstance(principal, AdminPrincipal)
            assert site_id == SITE_ID
            assert kwargs == {"limit": "20", "cursor": None}
            return SimpleNamespace(result=result())

    runtime.home_ap_24h_state = "active"
    runtime.query_service = Query()
    response = client.get(
        f"/admin/api/v1/sites/{SITE_ID}/home/ap-24h?limit=20",
        base_url="https://localhost",
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["site_id"] == SITE_ID
    assert payload["result"]["contract_version"] == CONTRACT_VERSION
    assert len(response.data) < runtime.config.max_response_bytes


@pytest.mark.parametrize("mutation", [
    lambda value: value["summary"]["current"].update(operational=0),
    lambda value: value["items"][0]["timeline"][0].update(operational_seconds=899),
    lambda value: value["items"][0]["timeline"][1].update(from_utc=ANCHOR),
    lambda value: value["items"][0]["history"].update(coverage_status="invented"),
    lambda value: value["items"][0].update(ap_mac="not-a-mac"),
    lambda value: value["page"].update(limit=21),
])
def test_serializer_rejects_inconsistent_or_malformed_source_results(mutation):
    value = deepcopy(result())
    mutation(value)
    with pytest.raises(HomeAp24SerializationError):
        serialize_home_ap_24h(value)


def test_serializer_accepts_known_before_window_source_gap_history():
    value = deepcopy(result())
    item = value["items"][0]
    item["current"] = {
        "status": "unknown",
        "reason_code": "current_state_source_gap",
        "observed_at": None,
        "freshness_status": "unavailable",
    }
    item["history"].update({
        "status": "unknown",
        "reason_code": "current_state_source_gap",
        "coverage_status": "insufficient_data",
        "history_eligible_from": "2026-08-27T12:00:00.000Z",
        "first_evidence_at": "2026-08-27T11:00:00.000Z",
        "last_evidence_at": "2026-08-27T11:00:00.000Z",
        "authoritative_sample_count": 0,
        "operational_seconds": 0,
        "unavailable_seconds": 0,
        "unknown_evidence_seconds": 86400,
        "short_history_seconds": 0,
        "max_gap_seconds": None,
        "current_vs_24h": "history_insufficient",
    })
    for bucket in item["timeline"]:
        bucket.update({
            "ap_state": "unknown",
            "ap_state_reason": "current_state_source_gap",
            "operational_seconds": 0,
            "unavailable_seconds": 0,
            "unknown_evidence_seconds": 900,
            "short_history_seconds": 0,
            "authoritative_state_sample_count": 0,
        })
    value["summary"]["current"] = {
        "operational": 0, "degraded": 0, "unavailable": 0, "unknown": 1,
    }
    value["summary"]["history"] = dict(value["summary"]["current"])
    value["summary"]["status_gap_ap_count"] = 1

    serialized = serialize_home_ap_24h(value)

    assert serialized["items"][0]["history"]["reason_code"] == (
        "current_state_source_gap"
    )


def test_route_enforces_response_size_cap(admin_app):
    client = admin_app.test_client(); login(client)
    runtime = admin_app.extensions["admin_web_runtime"]
    oversized = result()
    oversized["items"][0]["name"] = "x" * (runtime.config.max_response_bytes + 1)

    class Query:
        def home_ap_24h(self, *_args, **_kwargs):
            return SimpleNamespace(result=oversized)

    runtime.home_ap_24h_state = "active"
    runtime.query_service = Query()
    response = client.get(
        f"/admin/api/v1/sites/{SITE_ID}/home/ap-24h?limit=20",
        base_url="https://localhost",
    )
    assert response.status_code == 503
    assert response.get_json()["error"]["code"] == "response_too_large"


@pytest.mark.parametrize("error,status,code", [
    (AdminQueryBusy, 429, "concurrency_limit"),
    (AdminQueryDeadline, 503, "query_deadline"),
    (AdminQueryUnavailable, 503, "source_unavailable"),
])
def test_route_maps_independent_query_failures(admin_app, error, status, code):
    client = admin_app.test_client(); login(client)
    runtime = admin_app.extensions["admin_web_runtime"]

    class Query:
        def home_ap_24h(self, *_args, **_kwargs):
            raise error()

    runtime.home_ap_24h_state = "active"
    runtime.query_service = Query()
    response = client.get(
        f"/admin/api/v1/sites/{SITE_ID}/home/ap-24h",
        base_url="https://localhost",
    )
    assert response.status_code == status
    assert response.get_json()["error"]["code"] == code
    if status == 429:
        assert response.headers["Retry-After"] == "1"
