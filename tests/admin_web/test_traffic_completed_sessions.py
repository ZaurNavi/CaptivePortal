from __future__ import annotations

import logging
from dataclasses import replace
from types import SimpleNamespace

import pytest
from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix

from app.admin_web import create_admin_web_runtime
from app.admin_web.completed_guest_traffic_serialization import (
    CompletedGuestSessionTrafficSerializationError,
    serialize_completed_guest_session_traffic,
)
from app.admin_web.config import AdminWebConfigError, admin_web_config_from_settings
from app.analytics import (
    CompletedGuestSessionTrafficItem,
    CompletedGuestSessionTrafficPage,
    CompletedGuestSessionTrafficRange,
    CompletedGuestSessionTrafficResult,
    CompletedGuestSessionTrafficSourceHealth,
)

from .conftest import SITE_ID, enabled_settings, login


OTHER_SITE = "f" * 24


def _item(**overrides):
    values = dict(
        visit_id="11111111-1111-4111-8111-111111111111",
        client_mac="AA:BB:CC:DD:EE:01",
        started_at="2026-09-05T09:55:00.000Z",
        closed_at="2026-09-05T10:00:00.000Z",
        duration_seconds=300,
        start_ssid="Zefer_Parki",
        final_ssid="Zefer_Parki",
        start_ap_mac="AA:BB:CC:DD:EE:10",
        final_ap_mac="AA:BB:CC:DD:EE:11",
        observed_download_bytes=500,
        observed_upload_bytes=200,
        observed_total_bytes=700,
        download_evidence_status="complete",
        upload_evidence_status="complete",
        traffic_evidence_status="complete",
        evidence_reason_codes=(),
        sample_count=3,
        accepted_download_interval_count=2,
        accepted_upload_interval_count=2,
        first_observed_at="2026-09-05T09:55:30.000Z",
        last_observed_at="2026-09-05T09:59:30.000Z",
    )
    values.update(overrides)
    return CompletedGuestSessionTrafficItem(**values)


def _result(*, items=None, status="ok", observations="healthy", cursor=None, **overrides):
    items = (_item(),) if items is None else tuple(items)
    values = dict(
        metric_version="network_traffic_completed_guest_session_observed_bytes.v1",
        session_method="closed_visit_completion_cohort.v1",
        attribution_method="visit_window_observation_counter_interval_sum.v1",
        continuity_method="observation_uptime_progress.v1",
        unit="bytes",
        site_id=SITE_ID,
        range=CompletedGuestSessionTrafficRange(
            "24h", "2026-09-04T10:05:00.000Z",
            "2026-09-05T10:05:00.000Z", "2026-09-05T10:05:00.000Z",
        ),
        status=status,
        source_health=CompletedGuestSessionTrafficSourceHealth(
            "healthy", observations
        ),
        page=CompletedGuestSessionTrafficPage(
            100, len(items), cursor, "closed_at_desc_visit_id_desc.v1"
        ),
        items=items,
    )
    values.update(overrides)
    return CompletedGuestSessionTrafficResult(**values)


class Source:
    def __init__(self, result=None):
        self.result = result or _result()
        self.calls = []

    def get_completed_guest_session_traffic(self, site_id, **kwargs):
        self.calls.append((site_id, kwargs))
        return replace(
            self.result,
            page=replace(self.result.page, limit=kwargs["limit"]),
        )


def _app(tmp_path, monkeypatch, source, *, enabled=True):
    if enabled:
        monkeypatch.setattr(
            "app.analytics.completed_guest_traffic.CompletedGuestSessionTrafficReadService",
            lambda _gateway: source,
        )
    runtime = create_admin_web_runtime(
        enabled_settings(
            web_admin_traffic_enabled="true",
            web_admin_traffic_history_enabled="false",
            web_admin_traffic_completed_sessions_enabled=str(enabled).lower(),
        ),
        SimpleNamespace(state="active", visit_service=object()),
        SimpleNamespace(repository=SimpleNamespace(
            config=SimpleNamespace(db_path=tmp_path / "registry.sqlite3")
        )),
        SimpleNamespace(repository=SimpleNamespace(db_path=tmp_path / "visits.sqlite3")),
        SimpleNamespace(_repository=SimpleNamespace(db_path=tmp_path / "observations.sqlite3")),
        logging.getLogger("traffic-completed-sessions-test"),
    )
    app = Flask(__name__)
    app.config.update(TESTING=True)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)
    app.register_blueprint(runtime.blueprint)
    app.extensions["admin_web_runtime"] = runtime
    return app


def _url(site=SITE_ID, query="range=24h"):
    return f"/admin/api/v1/sites/{site}/traffic/completed-sessions?{query}"


def test_feature_defaults_off_and_depends_only_on_admin_traffic():
    assert admin_web_config_from_settings({}).traffic_completed_sessions_enabled is False
    with pytest.raises(AdminWebConfigError, match="COMPLETED_SESSIONS_ENABLED requires"):
        admin_web_config_from_settings(enabled_settings(
            web_admin_traffic_enabled="false",
            web_admin_traffic_completed_sessions_enabled="true",
        ))
    value = admin_web_config_from_settings(enabled_settings(
        web_admin_traffic_enabled="true",
        web_admin_traffic_history_enabled="false",
        web_admin_traffic_completed_sessions_enabled="true",
    ))
    assert value.traffic_completed_sessions_enabled is True


def test_security_feature_and_query_validation_order(tmp_path, monkeypatch):
    source = Source()
    disabled = _app(tmp_path, monkeypatch, source, enabled=False).test_client()
    duplicate = _url(query="range=24h&range=7d")
    assert disabled.get(duplicate, base_url="https://localhost").status_code == 401
    assert login(disabled).status_code == 302
    assert disabled.get(duplicate, base_url="https://localhost").status_code == 404

    enabled = _app(tmp_path, monkeypatch, source).test_client()
    assert login(enabled).status_code == 302
    assert enabled.get(_url(OTHER_SITE, "range=24h&range=7d"), base_url="https://localhost").status_code == 403
    response = enabled.get(duplicate, base_url="https://localhost")
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "invalid_request"
    assert source.calls == []


@pytest.mark.parametrize("query", [
    "", "range=30d", "bad=1&range=24h", "range=24h&limit=0",
    "range=24h&limit=101", "range=24h&limit=200",
    "range=24h&limit=201", "range=24h&limit=0100", "range=24h&limit=050",
    "range=24h&limit=invalid",
    "range=24h&cursor=x&cursor=y",
])
def test_query_grammar_is_exact(tmp_path, monkeypatch, query):
    source = Source()
    client = _app(tmp_path, monkeypatch, source).test_client()
    assert login(client).status_code == 302
    assert client.get(_url(query=query), base_url="https://localhost").status_code == 400
    assert source.calls == []


def test_route_executes_one_deadline_bounded_read_and_returns_exact_root(tmp_path, monkeypatch):
    source = Source()
    app = _app(tmp_path, monkeypatch, source)
    checks = []

    class Deadline:
        def require_remaining(self):
            checks.append("check")

    class Controls:
        def run(self, operation):
            return operation(Deadline())

    app.extensions["admin_web_runtime"].query_service._execution_controls = Controls()
    client = app.test_client()
    assert login(client).status_code == 302
    response = client.get(_url(query="range=24h&limit=100"), base_url="https://localhost")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["page"] is None
    assert payload["result"]["page"]["limit"] == 100
    assert payload["result"]["items"][0]["observed_total_bytes"] == 700
    assert checks == ["check", "check"]
    assert len(source.calls) == 1
    assert source.calls[0][1]["deadline"].__class__ is Deadline


def test_limit_defaults_to_100(tmp_path, monkeypatch):
    source = Source()
    client = _app(tmp_path, monkeypatch, source).test_client()
    assert login(client).status_code == 302
    response = client.get(_url(query="range=24h"), base_url="https://localhost")
    assert response.status_code == 200
    assert response.get_json()["result"]["page"]["limit"] == 100
    assert source.calls[0][1]["limit"] == 100


@pytest.mark.parametrize("changes", [
    {"traffic_evidence_status": "other"},
    {"evidence_reason_codes": ("private_sql_error",)},
    {"observed_download_bytes": 500, "accepted_download_interval_count": 0},
    {"observed_total_bytes": None},
    {"traffic_evidence_status": "complete", "evidence_reason_codes": ("counter_reset",)},
    {
        "observed_upload_bytes": None,
        "observed_total_bytes": None,
        "accepted_upload_interval_count": 0,
        "upload_evidence_status": "unavailable",
        "traffic_evidence_status": "partial",
        "evidence_reason_codes": ("counter_missing",),
    },
])
def test_serializer_fails_closed_on_impossible_item_combinations(changes):
    with pytest.raises(CompletedGuestSessionTrafficSerializationError):
        serialize_completed_guest_session_traffic(
            _result(items=[_item(**changes)]), SITE_ID
        )


def test_serializer_rejects_fractional_range_excess_and_mixed_insufficient_root():
    value = _result()
    with pytest.raises(CompletedGuestSessionTrafficSerializationError):
        serialize_completed_guest_session_traffic(
            replace(value, page=replace(value.page, limit=101)), SITE_ID
        )
    with pytest.raises(CompletedGuestSessionTrafficSerializationError):
        serialize_completed_guest_session_traffic(
            replace(
                value,
                range=replace(
                    value.range,
                    from_utc="2026-09-04T10:04:59.999Z",
                ),
            ),
            SITE_ID,
        )

    insufficient = _item(
        observed_download_bytes=None,
        observed_upload_bytes=None,
        observed_total_bytes=None,
        download_evidence_status="insufficient_data",
        upload_evidence_status="insufficient_data",
        traffic_evidence_status="insufficient_data",
        evidence_reason_codes=("no_usable_interval",),
        sample_count=0,
        accepted_download_interval_count=0,
        accepted_upload_interval_count=0,
        first_observed_at=None,
        last_observed_at=None,
    )
    long_visit = replace(
        _item(),
        visit_id="00000000-0000-4000-8000-000000000002",
        started_at="2026-09-04T08:59:00.000Z",
        closed_at="2026-09-05T09:59:00.000Z",
        duration_seconds=90_000,
        observed_download_bytes=None,
        observed_upload_bytes=None,
        observed_total_bytes=None,
        download_evidence_status="unavailable",
        upload_evidence_status="unavailable",
        traffic_evidence_status="unavailable",
        evidence_reason_codes=("attribution_window_exceeds_supported_max",),
        sample_count=0,
        accepted_download_interval_count=0,
        accepted_upload_interval_count=0,
        first_observed_at=None,
        last_observed_at=None,
    )
    with pytest.raises(CompletedGuestSessionTrafficSerializationError):
        serialize_completed_guest_session_traffic(
            _result(
                items=[insufficient, long_visit],
                status="insufficient_data",
            ),
            SITE_ID,
        )
    serialized, _page = serialize_completed_guest_session_traffic(
        _result(items=[insufficient, long_visit], status="partial"),
        SITE_ID,
    )
    assert serialized["status"] == "partial"


def test_observation_unavailable_keeps_visit_identity_but_no_traffic():
    item = _item(
        observed_download_bytes=None,
        observed_upload_bytes=None,
        observed_total_bytes=None,
        download_evidence_status="unavailable",
        upload_evidence_status="unavailable",
        traffic_evidence_status="unavailable",
        evidence_reason_codes=("observation_source_unavailable",),
        sample_count=0,
        accepted_download_interval_count=0,
        accepted_upload_interval_count=0,
        first_observed_at=None,
        last_observed_at=None,
    )
    serialized, _page = serialize_completed_guest_session_traffic(
        _result(items=[item], status="partial", observations="unavailable"), SITE_ID
    )
    assert serialized["items"][0]["client_mac"] == item.client_mac
    assert serialized["items"][0]["observed_total_bytes"] is None
