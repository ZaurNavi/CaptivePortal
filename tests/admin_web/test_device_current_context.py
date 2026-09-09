from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace
import logging
import sqlite3

import pytest
from flask import Flask

from app.admin_web.config import AdminWebConfigError, admin_web_config_from_settings
from app.admin_web.device_current_context_serialization import (
    DeviceCurrentContextSerializationError,
    serialize_device_current_context,
)
from app.admin_web.device_gateway import AdminDeviceRow
from app.admin_web.models import AdminPrincipal
from app.admin_web.policy import AdminAccessPolicy
from app.admin_web.query_service import AdminQueryService
from app.admin_web.query_service import AdminQueryForbidden, AdminQueryResponse
from app.admin_web import create_admin_web_runtime
from app.analytics.current_guest_traffic import (
    CurrentGuestTrafficClientResult,
    CurrentGuestTrafficReadService,
)
from app.analytics.current_guest_traffic import (
    CurrentGuestTrafficIntegrityUnavailable,
    CurrentGuestTrafficSourceUnavailable,
)
from app.analytics.source_gateway import AnalyticsQueryDeadlineExceeded
from app.analytics.models import CurrentGuestTrafficItem
from app.current_state.models import CurrentClientState, CurrentSnapshotMeta
from app.current_state.models import CurrentStateStorageError
from app.current_state.read_service import CurrentClientLookup, CurrentStateReadService

from .conftest import SITE_ID, enabled_settings, login


DEVICE_ID = "10000000-0000-4000-8000-000000000001"
MAC = "02:00:00:00:00:01"
NOW = "2026-09-08T16:00:00.000Z"


def _snapshot(*, status="fresh", cycle="current", complete=True):
    return CurrentSnapshotMeta(
        cycle_id=cycle,
        site_id=SITE_ID,
        kind="client",
        evaluated_at=NOW,
        observed_at=NOW if cycle else None,
        capture_finished_at=NOW if cycle else None,
        age_seconds=0.0 if cycle else None,
        freshness_status=status,
        freshness_reason=(
            "within_freshness_window" if status == "fresh"
            else "older_than_freshness_window" if status == "stale"
            else "no_complete_snapshot"
        ),
        complete=complete,
        source_scope_version=1 if cycle else None,
        source_scope_hash="a" * 64 if cycle else None,
        source_scope=(
            {"scope_type": "client_ssid_allowlist", "site_id": SITE_ID, "ssids": ["Zefer_Parki"]}
            if cycle else None
        ),
        latest_attempt_result=None,
        latest_attempt_at=None,
        latest_partial_cycle_id=None,
    )


def _client(auth="authorized"):
    return CurrentClientState(
        cycle_id="current", site_id=SITE_ID, observed_at=NOW,
        client_mac=MAC, name="Phone", hostname="phone", device_type="phone",
        ip="192.0.2.10", ssid="Zefer_Parki", ap_name="AP-1",
        ap_mac="AA:BB:CC:DD:EE:FF", radio_id=1, band="5GHz", channel=44,
        rssi=-52, snr=31, controller_uptime=180,
        auth_status_code=2, auth_classification=auth,
        controller_traffic_down=1000, controller_traffic_up=2000,
        controller_traffic_total=3000, active=True, wireless=True,
    )


def _traffic(rate_status="valid"):
    numeric = rate_status == "valid"
    reason = "valid" if numeric else "no_baseline"
    item = CurrentGuestTrafficItem(
        client_mac=MAC, name="Phone", ssid="Zefer_Parki",
        ap_mac="AA:BB:CC:DD:EE:FF",
        download_mbps=1.0 if numeric else None,
        upload_mbps=2.0 if numeric else None,
        total_mbps=3.0 if numeric else None,
        source_progress_status="advanced" if numeric else "unproven",
        connection_continuity_status="proven" if numeric else "unproven",
        continuity_basis="uptime_progress" if numeric else "none",
        download_reason=reason, upload_reason=reason, total_reason=reason,
        rate_status=rate_status,
    )
    return CurrentGuestTrafficClientResult(
        site_id=SITE_ID, evaluated_at_utc=NOW,
        current_cycle_id="current",
        baseline_cycle_id="baseline" if numeric else None,
        source_scope_hash="a" * 64,
        source_health_status="healthy",
        source_health_reason="within_freshness_window",
        rate_evidence_status="complete" if numeric else "insufficient_data",
        elapsed_seconds=60.0 if numeric else None,
        item=item,
    )


def _serialize(current, traffic=None, applicability="applicable", reason="authorized_current_guest", failure=None):
    return serialize_device_current_context(
        site_id=SITE_ID, device_id=DEVICE_ID, evaluated_at_utc=NOW,
        scope={"scope_type": "client_ssid_allowlist", "site_id": SITE_ID, "ssids": ["Zefer_Parki"]},
        current=current, traffic=traffic, applicability=applicability,
        applicability_reason=reason, traffic_failure_reason=failure,
    )


def test_device_current_serializer_preserves_online_zero_and_byte_units():
    traffic = _traffic()
    traffic = replace(
        traffic,
        item=replace(traffic.item, download_mbps=0.0, upload_mbps=0.0, total_mbps=0.0),
    )
    result = _serialize(CurrentClientLookup(_snapshot(), _client()), traffic)

    assert result["current_state"]["presence_status"] == "online"
    assert result["current_state"]["client"]["controller_traffic_total_bytes"] == 3000
    assert result["current_guest_traffic"]["item"]["total_mbps"] == 0.0
    assert "source_scope_hash" not in str(result)


@pytest.mark.parametrize("auth", ["pending", "other", "unknown"])
def test_device_current_non_authorized_is_not_applicable(auth):
    result = _serialize(
        CurrentClientLookup(_snapshot(), _client(auth)),
        applicability="not_applicable",
        reason="not_authorized_current_guest",
    )
    assert result["current_guest_traffic"]["rate_evidence_status"] == "not_applicable"
    assert result["current_guest_traffic"]["item"] is None


def test_device_current_offline_and_unknown_never_expose_client():
    offline = _serialize(
        CurrentClientLookup(_snapshot(), None),
        applicability="not_applicable", reason="offline",
    )
    unknown = _serialize(
        CurrentClientLookup(_snapshot(status="stale"), None),
        applicability="unknown", reason="current_state_unknown",
    )
    assert offline["current_state"]["presence_status"] == "offline"
    assert unknown["current_state"]["presence_status"] == "unknown"
    assert offline["current_state"]["client"] is None
    assert unknown["current_state"]["client"] is None


def test_device_current_traffic_failure_retains_current_state():
    result = _serialize(
        CurrentClientLookup(_snapshot(), _client()),
        failure="query_deadline",
    )
    assert result["current_state"]["client"]["client_mac"] == MAC
    assert result["current_guest_traffic"]["rate_evidence_status"] is None
    assert result["current_guest_traffic"]["failure_reason"] == "query_deadline"


def test_device_current_serializer_rejects_cycle_mismatch():
    with pytest.raises(DeviceCurrentContextSerializationError, match="coherence"):
        _serialize(
            CurrentClientLookup(_snapshot(), _client()),
            replace(_traffic(), current_cycle_id="newer"),
        )


_KEEP_SCOPE = object()


def _invalid_timestamp_lookup(
    *,
    evaluated_at=NOW,
    observed_at="invalid persisted timestamp",
    capture_finished_at=NOW,
    reason="invalid_timestamp",
    source_scope=_KEEP_SCOPE,
):
    snapshot = _snapshot(status="unavailable")
    return CurrentClientLookup(
        replace(
            snapshot,
            evaluated_at=evaluated_at,
            observed_at=observed_at,
            capture_finished_at=capture_finished_at,
            age_seconds=None,
            freshness_reason=reason,
            source_scope=(
                snapshot.source_scope if source_scope is _KEEP_SCOPE else source_scope
            ),
        ),
        None,
    )


def test_device_current_serializer_sanitizes_semantic_invalid_timestamp():
    result = _serialize(
        _invalid_timestamp_lookup(),
        applicability="unknown",
        reason="current_state_unknown",
    )

    assert result["current_state"]["presence_status"] == "unknown"
    assert result["current_state"]["presence_reason"] == "current_state_unknown"
    assert result["current_state"]["client"] is None
    assert result["current_state"]["snapshot"] == {
        "cycle_id": "current",
        "observed_at": None,
        "capture_finished_at": None,
        "age_seconds": None,
        "freshness_status": "unavailable",
        "freshness_reason": "invalid_timestamp",
        "complete": True,
    }
    assert result["current_guest_traffic"]["applicability"] == "unknown"
    assert result["current_guest_traffic"]["item"] is None
    assert result["current_guest_traffic"]["failure_reason"] is None


def test_device_current_serializer_rejects_calendar_invalid_timestamp():
    invalid = CurrentClientLookup(
        replace(
            _snapshot(),
            observed_at="2026-02-30T16:00:00.000Z",
        ),
        replace(_client(), observed_at="2026-02-30T16:00:00.000Z"),
    )
    with pytest.raises(DeviceCurrentContextSerializationError, match="timestamp"):
        _serialize(invalid, _traffic())


def test_device_current_serializer_rejects_reversed_normal_capture_interval():
    reversed_interval = CurrentClientLookup(
        replace(
            _snapshot(),
            capture_finished_at="2026-09-08T15:59:59.999Z",
        ),
        _client(),
    )
    with pytest.raises(DeviceCurrentContextSerializationError, match="interval"):
        _serialize(reversed_interval, _traffic())


def test_device_current_flag_defaults_off_and_requires_admin():
    assert admin_web_config_from_settings({"web_admin_enabled": "false"}).device_current_context_enabled is False
    with pytest.raises(AdminWebConfigError):
        admin_web_config_from_settings({
            "web_admin_enabled": "false",
            "web_admin_device_current_context_enabled": "true",
        })


class _DeviceGateway:
    def __init__(self):
        self.calls = []

    def get_device(self, **kwargs):
        self.calls.append(kwargs)
        return AdminDeviceRow(
            device_id=DEVICE_ID, canonical_mac=MAC, device_type="phone",
            site_first_seen_at=NOW, site_last_seen_at=NOW,
            site_snapshot_count=1, site_visit_count=1,
            last_site_ip=None, last_site_ssid=None, last_site_ap_mac=None,
            latest_snapshot=None,
        )


class _CurrentState:
    config = SimpleNamespace(client_ssids=("Zefer_Parki",))

    def __init__(self):
        self.calls = []

    def get_current_client(self, site_id, client_mac, **kwargs):
        self.calls.append((site_id, client_mac, kwargs))
        return CurrentClientLookup(
            replace(_snapshot(), evaluated_at=kwargs["evaluated_at_utc"]),
            _client(),
        )


class _Traffic:
    def __init__(self):
        self.calls = []

    def get_current_guest_traffic_for_client(self, site_id, client_mac, **kwargs):
        self.calls.append((site_id, client_mac, kwargs))
        return replace(_traffic(), evaluated_at_utc=kwargs["evaluated_at_utc"])


def test_device_current_query_uses_one_anchor_and_pins_traffic_to_state_cycle():
    config = admin_web_config_from_settings(enabled_settings(
        web_admin_device_current_context_enabled="true"
    ))
    devices = _DeviceGateway()
    current = _CurrentState()
    traffic = _Traffic()
    service = AdminQueryService(
        config=config,
        policy=AdminAccessPolicy(config.allowed_site_ids),
        device_gateway=devices,
        read_gateway=object(),
        visit_analytics_service=object(),
        current_state_read_service=current,
        current_guest_traffic_read_service=traffic,
    )

    response = service.device_current_context(
        AdminPrincipal("operator"), SITE_ID, DEVICE_ID
    )

    state_anchor = current.calls[0][2]["evaluated_at_utc"]
    assert traffic.calls[0][2] == {
        "evaluated_at_utc": state_anchor, "current_cycle_id": "current"
    }
    assert devices.calls[0]["deadline"] is not None
    assert response.result["evaluated_at_utc"] == state_anchor


def test_device_current_missing_site_membership_stops_before_current_sources():
    config = admin_web_config_from_settings(enabled_settings(
        web_admin_device_current_context_enabled="true"
    ))
    devices = _DeviceGateway()
    devices.get_device = lambda **kwargs: None
    current = _CurrentState()
    traffic = _Traffic()
    service = AdminQueryService(
        config=config, policy=AdminAccessPolicy(config.allowed_site_ids),
        device_gateway=devices, read_gateway=object(),
        visit_analytics_service=object(), current_state_read_service=current,
        current_guest_traffic_read_service=traffic,
    )
    from app.admin_web.query_service import AdminQueryNotFound
    with pytest.raises(AdminQueryNotFound):
        service.device_current_context(AdminPrincipal("operator"), SITE_ID, DEVICE_ID)
    assert current.calls == []
    assert traffic.calls == []


class _RouteQuery:
    def __init__(self):
        self.calls = []

    def device_current_context(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return AdminQueryResponse({"contract_version": "admin.device.current.v1"})


def _route_app(tmp_path, *, enabled, query_service=None):
    runtime = create_admin_web_runtime(
        enabled_settings(web_admin_device_current_context_enabled=(
            "true" if enabled else "false"
        )),
        SimpleNamespace(state="active", visit_service=object()),
        SimpleNamespace(repository=SimpleNamespace(config=SimpleNamespace(
            db_path=tmp_path / "registry.sqlite3"
        ))),
        SimpleNamespace(repository=SimpleNamespace(db_path=tmp_path / "visits.sqlite3")),
        SimpleNamespace(_repository=SimpleNamespace(db_path=tmp_path / "observations.sqlite3")),
        logging.getLogger("device-current-route-test"),
    )
    query = query_service if query_service is not None else _RouteQuery()
    runtime.query_service = query
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(runtime.blueprint)
    return app, query


def test_device_current_route_security_feature_and_query_ordering(tmp_path):
    disabled_app, disabled_query = _route_app(tmp_path, enabled=False)
    disabled_client = disabled_app.test_client()
    path = f"/admin/api/v1/sites/{SITE_ID}/devices/{DEVICE_ID}/current"
    anonymous = disabled_client.get(path + "?x=1&x=2", base_url="https://localhost")
    assert anonymous.status_code == 401
    login(disabled_client)
    assert disabled_client.get(path, base_url="https://localhost").status_code == 404
    assert disabled_query.calls == []

    enabled_app, enabled_query = _route_app(tmp_path, enabled=True)
    enabled_client = enabled_app.test_client()
    login(enabled_client)
    invalid = enabled_client.get(
        f"/admin/api/v1/sites/not-a-site/devices/{DEVICE_ID}/current?x=1&x=2",
        base_url="https://localhost",
    )
    forbidden = enabled_client.get(
        f"/admin/api/v1/sites/{'f' * 24}/devices/{DEVICE_ID}/current?x=1&x=2",
        base_url="https://localhost",
    )
    malformed = enabled_client.get(path + "?mac=x&mac=y", base_url="https://localhost")
    valid = enabled_client.get(path, base_url="https://localhost")
    assert (invalid.status_code, forbidden.status_code, malformed.status_code) == (400, 403, 400)
    assert valid.status_code == 200
    assert len(enabled_query.calls) == 1


def test_device_current_flag_controls_template_exposure(tmp_path):
    disabled_app, _ = _route_app(tmp_path, enabled=False)
    enabled_app, _ = _route_app(tmp_path, enabled=True)
    disabled_client = disabled_app.test_client()
    enabled_client = enabled_app.test_client()
    login(disabled_client)
    login(enabled_client)
    path = f"/admin/sites/{SITE_ID}/devices/{DEVICE_ID}"

    assert b'device-current-context' not in disabled_client.get(
        path, base_url="https://localhost"
    ).data
    assert b'id="device-current-context"' in enabled_client.get(
        path, base_url="https://localhost"
    ).data


def test_device_current_requires_exact_device_capability_before_source_access():
    class Policy:
        def __init__(self):
            self.calls = []

        def authorize(self, principal, capability, site_id):
            self.calls.append(capability)
            return capability != "admin.read.device"

    config = admin_web_config_from_settings(enabled_settings(
        web_admin_device_current_context_enabled="true"
    ))
    policy = Policy()
    devices = _DeviceGateway()
    service = AdminQueryService(
        config=config, policy=policy, device_gateway=devices,
        read_gateway=object(), visit_analytics_service=object(),
        current_state_read_service=_CurrentState(),
        current_guest_traffic_read_service=_Traffic(),
    )
    with pytest.raises(AdminQueryForbidden):
        service.device_current_context(AdminPrincipal("operator"), SITE_ID, DEVICE_ID)
    assert policy.calls == ["admin.read.device"]
    assert devices.calls == []


def test_device_current_authoritative_state_failure_is_endpoint_unavailable():
    config = admin_web_config_from_settings(enabled_settings(
        web_admin_device_current_context_enabled="true"
    ))
    current = _CurrentState()
    current.get_current_client = lambda *args, **kwargs: (_ for _ in ()).throw(
        CurrentStateStorageError("private source detail")
    )
    service = AdminQueryService(
        config=config, policy=AdminAccessPolicy(config.allowed_site_ids),
        device_gateway=_DeviceGateway(), read_gateway=object(),
        visit_analytics_service=object(), current_state_read_service=current,
        current_guest_traffic_read_service=_Traffic(),
    )
    from app.admin_web.query_service import AdminQueryUnavailable
    with pytest.raises(AdminQueryUnavailable):
        service.device_current_context(AdminPrincipal("operator"), SITE_ID, DEVICE_ID)


@pytest.mark.parametrize(
    "failure,reason",
    [
        (CurrentGuestTrafficSourceUnavailable("private"), "source_unavailable"),
        (CurrentGuestTrafficIntegrityUnavailable("private"), "integrity_unavailable"),
        (AnalyticsQueryDeadlineExceeded("private"), "query_deadline"),
    ],
)
def test_device_current_traffic_technical_failure_is_local(failure, reason):
    class Traffic(_Traffic):
        def get_current_guest_traffic_for_client(self, *args, **kwargs):
            raise failure

    config = admin_web_config_from_settings(enabled_settings(
        web_admin_device_current_context_enabled="true"
    ))
    service = AdminQueryService(
        config=config, policy=AdminAccessPolicy(config.allowed_site_ids),
        device_gateway=_DeviceGateway(), read_gateway=object(),
        visit_analytics_service=object(), current_state_read_service=_CurrentState(),
        current_guest_traffic_read_service=Traffic(),
    )
    result = service.device_current_context(
        AdminPrincipal("operator"), SITE_ID, DEVICE_ID
    ).result
    assert result["current_state"]["client"]["client_mac"] == MAC
    assert result["current_guest_traffic"]["failure_reason"] == reason
    assert result["current_guest_traffic"]["rate_evidence_status"] is None


@pytest.mark.parametrize(
    ("reason", "observed_at", "capture_finished_at", "drop_scope"),
    [
        ("invalid_timestamp", "invalid persisted timestamp", NOW, False),
        ("invalid_timestamp", NOW, "2026-09-08T15:59:59.999Z", False),
        ("invalid_source_scope", NOW, "2026-09-08T15:59:59.999Z", True),
    ],
)
def test_device_current_semantic_timestamp_endpoint_is_http_200(
    tmp_path, reason, observed_at, capture_finished_at, drop_scope,
):
    class InvalidTimestampCurrent(_CurrentState):
        def get_current_client(self, site_id, client_mac, **kwargs):
            self.calls.append((site_id, client_mac, kwargs))
            return _invalid_timestamp_lookup(
                evaluated_at=kwargs["evaluated_at_utc"],
                observed_at=observed_at,
                capture_finished_at=capture_finished_at,
                reason=reason,
                source_scope=None if drop_scope else _KEEP_SCOPE,
            )

    config = admin_web_config_from_settings(enabled_settings(
        web_admin_device_current_context_enabled="true"
    ))
    current = InvalidTimestampCurrent()
    traffic = _Traffic()
    service = AdminQueryService(
        config=config, policy=AdminAccessPolicy(config.allowed_site_ids),
        device_gateway=_DeviceGateway(), read_gateway=object(),
        visit_analytics_service=object(), current_state_read_service=current,
        current_guest_traffic_read_service=traffic,
    )
    app, _query = _route_app(
        tmp_path, enabled=True, query_service=service
    )
    client = app.test_client()
    login(client)

    response = client.get(
        f"/admin/api/v1/sites/{SITE_ID}/devices/{DEVICE_ID}/current",
        base_url="https://localhost",
    )
    payload = response.get_json()["result"]

    assert response.status_code == 200
    assert payload["current_state"]["presence_status"] == "unknown"
    assert payload["current_state"]["client"] is None
    assert payload["current_state"]["snapshot"]["observed_at"] is None
    assert payload["current_state"]["snapshot"]["capture_finished_at"] is None
    assert payload["current_state"]["snapshot"]["freshness_reason"] == reason
    assert payload["current_guest_traffic"]["applicability"] == "unknown"
    assert payload["current_guest_traffic"]["item"] is None
    assert payload["current_guest_traffic"]["failure_reason"] is None
    assert traffic.calls == []


def test_device_current_raw_sqlite_traffic_failure_is_local_http_200(tmp_path):
    class RawSqlTrafficCurrent(_CurrentState, CurrentStateReadService):
        def read_current_guest_rate_client_evidence(self, *_args, **_kwargs):
            raise sqlite3.OperationalError("private storage detail")

    config = admin_web_config_from_settings(enabled_settings(
        web_admin_device_current_context_enabled="true"
    ))
    current = RawSqlTrafficCurrent()
    traffic = CurrentGuestTrafficReadService(current)
    service = AdminQueryService(
        config=config, policy=AdminAccessPolicy(config.allowed_site_ids),
        device_gateway=_DeviceGateway(), read_gateway=object(),
        visit_analytics_service=object(), current_state_read_service=current,
        current_guest_traffic_read_service=traffic,
    )
    app, _query = _route_app(
        tmp_path, enabled=True, query_service=service
    )
    client = app.test_client()
    login(client)

    response = client.get(
        f"/admin/api/v1/sites/{SITE_ID}/devices/{DEVICE_ID}/current",
        base_url="https://localhost",
    )
    payload = response.get_json()["result"]
    current_traffic = payload["current_guest_traffic"]

    assert response.status_code == 200
    assert payload["current_state"]["client"]["client_mac"] == MAC
    assert current_traffic == {
        "applicability": "applicable",
        "applicability_reason": "authorized_current_guest",
        "source_health_status": None,
        "source_health_reason": None,
        "rate_evidence_status": None,
        "current_cycle_id": "current",
        "baseline_cycle_id": None,
        "elapsed_seconds": None,
        "item": None,
        "failure_reason": "source_unavailable",
    }
