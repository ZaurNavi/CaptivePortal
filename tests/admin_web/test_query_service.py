from __future__ import annotations

import threading

import pytest

from app.admin_web.config import admin_web_config_from_settings
from app.admin_web.device_gateway import (
    AdminDeviceContextExpired,
    AdminDeviceListContextPage,
    AdminDeviceListContextRow,
    AdminDevicePage,
    AdminDeviceRow,
)
from app.admin_web.device_list_context_cursor import DeviceListContextCursorCodec
from app.admin_web.models import AdminPrincipal
from app.admin_web.policy import AdminAccessPolicy
from app.admin_web.query_service import (
    AdminQueryBusy,
    AdminQueryCursorExpired,
    AdminQueryDeadline,
    AdminQueryForbidden,
    AdminQueryIntegrityUnavailable,
    AdminQueryService,
    AdminQueryUnavailable,
    AdminQueryValidationError,
)
from app.analytics.source_gateway import (
    AnalyticsQueryDeadlineExceeded,
    QueryDeadline,
)
from app.analytics.models import (
    AnalyticsProvenance,
    AnalyticsQuality,
    AnalyticsResult,
)
from app.current_state.models import (
    CurrentSnapshotMeta,
    CurrentStateStorageError,
    CurrentStateValidationError,
)
from app.current_state.read_service import (
    CurrentClientInventoryContext,
    CurrentClientInventoryContextExpired,
)
from app.current_state.normalizer import canonical_scope

from .conftest import SITE_ID, enabled_settings


DEVICE_ID = "10000000-0000-4000-8000-000000000001"
DEVICE_LIST_SCOPE_HASH = canonical_scope(
    "client", SITE_ID, ("Zefer_Parki",)
)[1]


def _device() -> AdminDeviceRow:
    return AdminDeviceRow(
        device_id=DEVICE_ID,
        canonical_mac="02:00:00:00:00:01",
        device_type="phone",
        site_first_seen_at="2026-01-01T00:00:00.000Z",
        site_last_seen_at="2026-01-02T00:00:00.000Z",
        site_snapshot_count=2,
        site_visit_count=3,
        last_site_ip="192.0.2.1",
        last_site_ssid="OwnerWiFi",
        last_site_ap_mac="AA:BB:CC:DD:EE:FF",
        latest_snapshot={"captured_at": "2026-01-02T00:00:00.000Z"},
    )


def _context_device(*, presence="online", rank=0):
    return AdminDeviceListContextRow(
        device_id=DEVICE_ID,
        canonical_mac="02:00:00:00:00:01",
        hostname="client-host",
        device_type="phone",
        site_first_seen_at="2026-01-01T00:00:00.000Z",
        site_last_seen_at="2026-01-02T00:00:00.000Z",
        site_snapshot_count=2,
        site_visit_count=3,
        last_site_ip="192.0.2.1",
        last_site_ssid="OwnerWiFi",
        last_site_ap_mac="AA:BB:CC:DD:EE:FF",
        current_presence=presence,
        online_rank=rank,
    )


class DeviceGateway:
    def __init__(self):
        self.calls = []

    def list_devices(self, **kwargs):
        self.calls.append(kwargs)
        return AdminDevicePage((_device(),), False)

    def get_device(self, **kwargs):
        self.calls.append(kwargs)
        return _device()


class ReadGateway:
    def __init__(self):
        self.calls = []

    def list_visits(self, **kwargs):
        self.calls.append(("visits", kwargs))
        return (({"visit_id": "v", "started_at": "2026-01-01T00:00:00.000Z"},), False)

    def get_visit(self, **kwargs):
        self.calls.append(("visit", kwargs))
        return {"visit_id": kwargs["visit_id"]}

    def latest_client_observation(self, **kwargs):
        self.calls.append(("latest", kwargs))
        return {"observed_at": "2026-01-01T00:00:00.000Z"}

    def list_client_observations(self, **kwargs):
        self.calls.append(("clients", kwargs))
        return (({
            "observed_at": "2026-01-01T00:00:00.000Z",
            "client_mac": kwargs["client_mac"],
            "_row_id": 1,
        },), False)

    def list_ap_observations(self, **kwargs):
        self.calls.append(("aps", kwargs))
        return (({
            "observed_at": "2026-01-01T00:00:00.000Z",
            "ap_mac": kwargs["ap_mac"],
            "radios": [],
            "_row_id": 1,
        },), False)


class Analytics:
    def __init__(self):
        self.calls = []

    def get_visit_counts(self, site, start, end, *, deadline=None):
        self.calls.append(("visits", site, start, end, deadline))
        return _analytics_result()

    def get_device_counts(self, site, start, end, *, deadline=None):
        self.calls.append(("devices", site, start, end, deadline))
        return _analytics_result()


def _analytics_result(*, status="ok", reason=None):
    return AnalyticsResult(
        status=status,
        quality=AnalyticsQuality("strict_complete", reason=reason),
        value=None,
        provenance=AnalyticsProvenance(
            site_id=SITE_ID,
            from_utc="2026-01-01T00:00:00.000Z",
            to_utc="2026-01-02T00:00:00.000Z",
            evaluation_at_utc="2026-01-02T00:00:00.000Z",
            computed_at_utc="2026-01-02T00:00:00.000Z",
            quality_mode="strict_complete",
            source_names=("visits",),
            source_schema_versions={"visits": 2},
            source_watermarks={"visits": None},
            source_rows_examined=0,
            source_rows_accepted=0,
            source_rows_rejected=0,
            sample_size=0,
            missing_count=0,
            partial_cycle_count=0,
            failed_cycle_count=0,
            abandoned_cycle_count=0,
            filters={},
            metric_version="test.v1",
            query_duration_ms=0.0,
        ),
    )


def _service(*, max_queries=2):
    settings = enabled_settings(
        web_admin_max_concurrent_queries=max_queries,
        web_admin_device_page_size=100,
        web_admin_visit_page_size=100,
        web_admin_observation_page_size=100,
    )
    config = admin_web_config_from_settings(settings)
    devices = DeviceGateway()
    reads = ReadGateway()
    analytics = Analytics()
    service = AdminQueryService(
        config=config,
        policy=AdminAccessPolicy(config.allowed_site_ids),
        device_gateway=devices,
        read_gateway=reads,
        visit_analytics_service=analytics,
    )
    return service, devices, reads, analytics


class DeviceListContextGateway(DeviceGateway):
    def __init__(self, *, has_more=False, fail=None):
        super().__init__()
        self.has_more = has_more
        self.fail = fail

    def list_devices_context(self, **kwargs):
        self.calls.append(kwargs)
        if self.fail is not None:
            failure = self.fail
            self.fail = None
            raise failure
        if kwargs["overlay_mode"] == "trusted":
            item = _context_device()
        else:
            item = _context_device(presence="unknown", rank=1)
        return AdminDeviceListContextPage((item,), self.has_more)


class DeviceListCurrentSource:
    def __init__(self, *, mode="trusted", failure=None):
        self.config = type("Config", (), {"client_ssids": ("Zefer_Parki",)})()
        self.mode = mode
        self.failure = failure
        self.calls = []

    def get_current_client_inventory_context(self, site_id, **kwargs):
        self.calls.append((site_id, kwargs))
        if self.failure is not None:
            raise self.failure
        evaluated = kwargs["evaluated_at_utc"]
        if self.mode == "trusted":
            snapshot = _device_list_context_snapshot(evaluated)
            return CurrentClientInventoryContext(
                site_id, evaluated, "trusted", snapshot, "cycle-1",
                DEVICE_LIST_SCOPE_HASH,
            )
        snapshot = _device_list_context_snapshot(
            evaluated,
            freshness_status="stale",
            freshness_reason="older_than_freshness_window",
            age_seconds=100.0,
        )
        return CurrentClientInventoryContext(
            site_id, evaluated, "unknown", snapshot, None, None
        )


def _device_list_context_snapshot(evaluated, **changes):
    values = {
        "cycle_id": "cycle-1",
        "site_id": SITE_ID,
        "kind": "client",
        "evaluated_at": evaluated,
        "observed_at": "2026-09-09T11:59:50.000Z",
        "capture_finished_at": "2026-09-09T11:59:55.000Z",
        "age_seconds": 10.0,
        "freshness_status": "fresh",
        "freshness_reason": "within_freshness_window",
        "complete": True,
        "source_scope_version": 1,
        "source_scope_hash": DEVICE_LIST_SCOPE_HASH,
        "source_scope": {
            "scope_type": "client_ssid_allowlist",
            "site_id": SITE_ID,
            "ssids": ["Zefer_Parki"],
        },
        "latest_attempt_result": "success",
        "latest_attempt_at": "2026-09-09T11:59:55.000Z",
        "latest_partial_cycle_id": None,
    }
    values.update(changes)
    return CurrentSnapshotMeta(**values)


def _device_list_context_service(
    *, current=None, gateway=None, state="active", maximum=4096
):
    settings = enabled_settings(
        web_admin_device_list_context_enabled="true",
        web_admin_device_page_size=1,
    )
    config = admin_web_config_from_settings(settings)
    devices = gateway or DeviceListContextGateway()
    codec = DeviceListContextCursorCodec(
        secret_key=b"x" * 32,
        maximum_length=maximum,
    )
    service = AdminQueryService(
        config=config,
        policy=AdminAccessPolicy(config.allowed_site_ids),
        device_gateway=devices,
        read_gateway=ReadGateway(),
        visit_analytics_service=Analytics(),
        current_state_read_service=current,
        device_list_context_state=state,
        device_list_context_cursor_codec=codec,
    )
    return service, devices, codec


def test_query_service_repeats_site_capability_before_source_access():
    service, devices, _reads, _analytics = _service()
    with pytest.raises(AdminQueryForbidden):
        service.list_devices(AdminPrincipal("x"), "f" * 24)
    assert devices.calls == []


def test_device_list_dto_does_not_expose_detail_snapshot():
    service, devices, _reads, _analytics = _service()
    response = service.list_devices(AdminPrincipal("x"), SITE_ID)
    assert response.result["items"][0]["canonical_mac"] == "02:00:00:00:00:01"
    assert "latest_snapshot" not in response.result["items"][0]
    assert isinstance(devices.calls[0]["deadline"], QueryDeadline)


def test_device_mac_filter_is_canonical_and_bound_to_cursor():
    service, devices, _reads, _analytics = _service()
    devices.list_devices = lambda **kwargs: (
        devices.calls.append(kwargs)
        or AdminDevicePage((_device(),), True)
    )
    first = service.list_devices(
        AdminPrincipal("x"), SITE_ID, mac="02-00-00-00-00-01"
    )
    assert devices.calls[0]["canonical_mac"] == "02:00:00:00:00:01"
    cursor = first.page["next_cursor"]
    with pytest.raises(AdminQueryValidationError):
        service.list_devices(
            AdminPrincipal("x"),
            SITE_ID,
            mac="02:00:00:00:00:02",
            cursor=cursor,
        )
    assert len(devices.calls) == 1


def test_invalid_device_mac_stops_before_source_query():
    service, devices, _reads, _analytics = _service()
    with pytest.raises(AdminQueryValidationError):
        service.list_devices(AdminPrincipal("x"), SITE_ID, mac="not-a-mac")
    assert devices.calls == []


def test_device_detail_propagates_one_deadline_to_all_sources():
    service, devices, reads, _analytics = _service()
    response = service.device_detail(AdminPrincipal("x"), SITE_ID, DEVICE_ID)
    deadline = devices.calls[0]["deadline"]
    assert all(call[1]["deadline"] is deadline for call in reads.calls)
    assert response.result["latest_snapshot"]["captured_at"].endswith("Z")


@pytest.mark.parametrize("method", ["client_observations", "ap_observations"])
def test_observation_window_bound_is_enforced(method):
    service, _devices, reads, _analytics = _service()
    arguments = {
        "from_utc": "2026-01-01T00:00:00.000Z",
        "to_utc": "2026-01-03T00:00:00.000Z",
    }
    arguments["client_mac" if method == "client_observations" else "ap_mac"] = (
        "02:00:00:00:00:01"
    )
    with pytest.raises(AdminQueryValidationError):
        getattr(service, method)(AdminPrincipal("x"), SITE_ID, **arguments)
    assert reads.calls == []


def test_summary_calls_analytics_once_and_supplies_admin_deadline():
    service, _devices, _reads, analytics = _service()
    service.visit_summary(
        AdminPrincipal("x"),
        SITE_ID,
        "2026-01-01T00:00:00.000Z",
        "2026-01-02T00:00:00.000Z",
    )
    assert len(analytics.calls) == 1
    assert isinstance(analytics.calls[0][-1], QueryDeadline)


def test_unavailable_analytics_result_maps_to_generic_unavailable():
    service, _devices, _reads, analytics = _service()
    analytics.get_visit_counts = lambda *args, **kwargs: _analytics_result(
        status="unavailable", reason="source_unavailable"
    )
    with pytest.raises(AdminQueryUnavailable):
        service.visit_summary(
            AdminPrincipal("x"),
            SITE_ID,
            "2026-01-01T00:00:00.000Z",
            "2026-01-02T00:00:00.000Z",
        )


def test_concurrency_is_nonblocking_and_slot_is_released():
    service, devices, _reads, _analytics = _service(max_queries=1)
    entered = threading.Event()
    release = threading.Event()
    original = devices.list_devices

    def blocked(**kwargs):
        entered.set()
        assert release.wait(5)
        return original(**kwargs)

    devices.list_devices = blocked
    result = []
    thread = threading.Thread(
        target=lambda: result.append(
            service.list_devices(AdminPrincipal("x"), SITE_ID)
        )
    )
    thread.start()
    assert entered.wait(5)
    with pytest.raises(AdminQueryBusy):
        service.list_devices(AdminPrincipal("x"), SITE_ID)
    release.set()
    thread.join(5)
    assert not thread.is_alive()
    assert result
    service.list_devices(AdminPrincipal("x"), SITE_ID)


def test_representative_admin_and_02a_analytics_reads_can_run_together():
    service, _devices, _reads, analytics = _service(max_queries=1)
    barrier = threading.Barrier(2)
    original = analytics.get_visit_counts

    def concurrent(*args, **kwargs):
        barrier.wait(timeout=5)
        return original(*args, **kwargs)

    analytics.get_visit_counts = concurrent
    failures = []

    def admin_request():
        try:
            service.visit_summary(
                AdminPrincipal("x"), SITE_ID,
                "2026-01-01T00:00:00.000Z",
                "2026-01-02T00:00:00.000Z",
            )
        except Exception as exc:  # pragma: no cover - assertion captures it
            failures.append(exc)

    thread = threading.Thread(target=admin_request)
    thread.start()
    analytics.get_visit_counts(
        SITE_ID,
        "2026-01-01T00:00:00.000Z",
        "2026-01-02T00:00:00.000Z",
    )
    thread.join(5)
    assert not thread.is_alive()
    assert failures == []


def test_device_list_context_feature_off_keeps_old_path_and_decoder():
    service, devices, _reads, _analytics = _service()
    response = service.list_devices(AdminPrincipal("x"), SITE_ID)
    assert len(devices.calls) == 1
    assert response.result == {
        "items": [{
            "device_id": DEVICE_ID,
            "canonical_mac": "02:00:00:00:00:01",
            "device_type": "phone",
            "site_first_seen_at": "2026-01-01T00:00:00.000Z",
            "site_last_seen_at": "2026-01-02T00:00:00.000Z",
            "site_snapshot_count": 2,
            "site_visit_count": 3,
            "last_site_ip": "192.0.2.1",
            "last_site_ssid": "OwnerWiFi",
            "last_site_ap_mac": "AA:BB:CC:DD:EE:FF",
        }]
    }


def test_device_list_context_unavailable_composition_stops_before_sources():
    current = DeviceListCurrentSource()
    service, devices, _codec = _device_list_context_service(
        current=current, state="unavailable"
    )
    with pytest.raises(AdminQueryUnavailable):
        service.list_devices(AdminPrincipal("x"), SITE_ID)
    assert current.calls == []
    assert devices.calls == []


def test_device_list_context_initial_trusted_calls_once_and_signs_cursor():
    current = DeviceListCurrentSource()
    gateway = DeviceListContextGateway(has_more=True)
    service, devices, codec = _device_list_context_service(
        current=current, gateway=gateway
    )
    response = service.list_devices(AdminPrincipal("x"), SITE_ID)
    assert len(current.calls) == 1
    assert devices.calls[0]["overlay_mode"] == "trusted"
    assert devices.calls[0]["current_cycle_id"] == "cycle-1"
    assert response.result["items"][0]["hostname"] == "client-host"
    assert response.result["items"][0]["current_presence"] == "online"
    decoded = codec.decode(response.page["next_cursor"], site_id=SITE_ID, filters={})
    assert decoded.overlay_mode == "trusted"
    assert decoded.current_cycle_id == "cycle-1"


@pytest.mark.parametrize(
    "snapshot_changes",
    [
        {"cycle_id": "other-cycle"},
        {"source_scope_hash": "0" * 64},
        {"source_scope_version": 2},
    ],
    ids=["wrong-cycle", "wrong-scope-hash", "wrong-scope-version"],
)
def test_device_list_context_initial_trusted_snapshot_must_match_descriptor(
    snapshot_changes,
):
    current = DeviceListCurrentSource()
    gateway = DeviceListContextGateway()

    def incompatible(site_id, **kwargs):
        evaluated = kwargs["evaluated_at_utc"]
        return CurrentClientInventoryContext(
            site_id,
            evaluated,
            "trusted",
            _device_list_context_snapshot(evaluated, **snapshot_changes),
            "cycle-1",
            DEVICE_LIST_SCOPE_HASH,
        )

    current.get_current_client_inventory_context = incompatible
    service, devices, _codec = _device_list_context_service(
        current=current, gateway=gateway
    )

    with pytest.raises(AdminQueryIntegrityUnavailable):
        service.list_devices(AdminPrincipal("x"), SITE_ID)
    assert devices.calls == []


def test_device_list_context_initial_semantic_unknown_uses_unknown_gateway():
    current = DeviceListCurrentSource(mode="unknown")
    service, devices, _codec = _device_list_context_service(current=current)
    response = service.list_devices(AdminPrincipal("x"), SITE_ID)
    assert len(current.calls) == 1
    assert devices.calls[0]["overlay_mode"] == "unknown"
    assert response.result["current_state_overlay"]["source_execution_status"] == "available"
    assert response.result["items"][0]["current_presence"] == "unknown"


@pytest.mark.parametrize(
    "current",
    [None, DeviceListCurrentSource(failure=CurrentStateStorageError("busy"))],
    ids=["absent", "source-exception"],
)
def test_device_list_context_initial_current_failure_fails_open_unknown(current):
    service, devices, _codec = _device_list_context_service(current=current)
    response = service.list_devices(AdminPrincipal("x"), SITE_ID)
    overlay = response.result["current_state_overlay"]
    assert overlay["overlay_mode"] == "unknown"
    assert overlay["source_execution_status"] == "unavailable"
    assert overlay["snapshot"] is None
    assert devices.calls[0]["overlay_mode"] == "unknown"


def test_device_list_context_initial_retention_race_fails_open_without_trusted_cursor():
    current = DeviceListCurrentSource()
    gateway = DeviceListContextGateway(
        has_more=True,
        fail=AdminDeviceContextExpired("expired"),
    )
    service, devices, codec = _device_list_context_service(
        current=current, gateway=gateway
    )
    response = service.list_devices(AdminPrincipal("x"), SITE_ID)
    assert [call["overlay_mode"] for call in devices.calls] == ["trusted", "unknown"]
    decoded = codec.decode(response.page["next_cursor"], site_id=SITE_ID, filters={})
    assert decoded.overlay_mode == "unknown"
    assert decoded.source_execution_status == "unavailable"


def test_device_list_context_unknown_continuation_never_reads_current_and_preserves_chain():
    initial_current = DeviceListCurrentSource(mode="unknown")
    gateway = DeviceListContextGateway(has_more=True)
    service, devices, _codec = _device_list_context_service(
        current=initial_current, gateway=gateway
    )
    first = service.list_devices(AdminPrincipal("x"), SITE_ID)
    initial_calls = len(initial_current.calls)
    second = service.list_devices(
        AdminPrincipal("x"), SITE_ID, cursor=first.page["next_cursor"]
    )
    assert len(initial_current.calls) == initial_calls
    assert devices.calls[-1]["cursor"][0] == 1
    assert second.result["current_state_overlay"] == first.result["current_state_overlay"]


def test_device_list_context_trusted_continuation_revalidates_same_signed_context():
    current = DeviceListCurrentSource()
    gateway = DeviceListContextGateway(has_more=True)
    service, devices, _codec = _device_list_context_service(
        current=current, gateway=gateway
    )
    first = service.list_devices(AdminPrincipal("x"), SITE_ID)
    signed_overlay = first.result["current_state_overlay"]
    second = service.list_devices(
        AdminPrincipal("x"), SITE_ID, cursor=first.page["next_cursor"]
    )
    assert len(current.calls) == 2
    assert current.calls[1][1]["current_cycle_id"] == "cycle-1"
    assert (
        current.calls[1][1]["expected_source_scope_hash"]
        == DEVICE_LIST_SCOPE_HASH
    )
    assert devices.calls[-1]["current_cycle_id"] == "cycle-1"
    assert second.result["current_state_overlay"] == signed_overlay


@pytest.mark.parametrize(
    "snapshot_changes",
    [
        {
            "freshness_status": "stale",
            "freshness_reason": "older_than_freshness_window",
            "age_seconds": 100.0,
        },
        {"complete": False},
        {"cycle_id": "other-cycle"},
    ],
    ids=["stale", "incomplete", "wrong-cycle"],
)
def test_device_list_context_trusted_continuation_rejects_snapshot_contradiction(
    snapshot_changes,
):
    current = DeviceListCurrentSource()
    gateway = DeviceListContextGateway(has_more=True)
    service, devices, _codec = _device_list_context_service(
        current=current, gateway=gateway
    )
    first = service.list_devices(AdminPrincipal("x"), SITE_ID)
    trusted_gateway_calls = len(devices.calls)

    def incompatible(site_id, **kwargs):
        evaluated = kwargs["evaluated_at_utc"]
        return CurrentClientInventoryContext(
            site_id,
            evaluated,
            "trusted",
            _device_list_context_snapshot(evaluated, **snapshot_changes),
            "cycle-1",
            DEVICE_LIST_SCOPE_HASH,
        )

    current.get_current_client_inventory_context = incompatible
    with pytest.raises(AdminQueryIntegrityUnavailable):
        service.list_devices(
            AdminPrincipal("x"), SITE_ID, cursor=first.page["next_cursor"]
        )
    assert len(devices.calls) == trusted_gateway_calls


@pytest.mark.parametrize(
    "failure,expected",
    [
        (CurrentClientInventoryContextExpired("expired"), AdminQueryCursorExpired),
        (CurrentStateStorageError("busy"), AdminQueryUnavailable),
    ],
)
def test_device_list_context_trusted_continuation_maps_current_failures(failure, expected):
    current = DeviceListCurrentSource()
    gateway = DeviceListContextGateway(has_more=True)
    service, _devices, _codec = _device_list_context_service(
        current=current, gateway=gateway
    )
    first = service.list_devices(AdminPrincipal("x"), SITE_ID)
    current.failure = failure
    with pytest.raises(expected):
        service.list_devices(
            AdminPrincipal("x"), SITE_ID, cursor=first.page["next_cursor"]
        )


def test_device_list_context_trusted_continuation_validation_is_integrity_failure():
    current = DeviceListCurrentSource()
    gateway = DeviceListContextGateway(has_more=True)
    service, devices, _codec = _device_list_context_service(
        current=current, gateway=gateway
    )
    first = service.list_devices(AdminPrincipal("x"), SITE_ID)
    trusted_gateway_calls = len(devices.calls)
    current.failure = CurrentStateValidationError("semantic contradiction")

    with pytest.raises(AdminQueryIntegrityUnavailable) as raised:
        service.list_devices(
            AdminPrincipal("x"), SITE_ID, cursor=first.page["next_cursor"]
        )
    assert type(raised.value) is AdminQueryIntegrityUnavailable
    assert len(devices.calls) == trusted_gateway_calls


def test_device_list_context_trusted_gateway_expiry_maps_cursor_expired():
    current = DeviceListCurrentSource()
    gateway = DeviceListContextGateway(has_more=True)
    service, _devices, _codec = _device_list_context_service(
        current=current, gateway=gateway
    )
    first = service.list_devices(AdminPrincipal("x"), SITE_ID)
    gateway.fail = AdminDeviceContextExpired("expired")
    with pytest.raises(AdminQueryCursorExpired) as raised:
        service.list_devices(
            AdminPrincipal("x"), SITE_ID, cursor=first.page["next_cursor"]
        )
    assert raised.value.code == "cursor_expired"


def test_device_list_context_cursor_tamper_stops_before_current_read():
    current = DeviceListCurrentSource()
    gateway = DeviceListContextGateway(has_more=True)
    service, _devices, _codec = _device_list_context_service(
        current=current, gateway=gateway
    )
    first = service.list_devices(AdminPrincipal("x"), SITE_ID)
    current.calls.clear()
    token = first.page["next_cursor"]
    tampered = ("A" if token[0] != "A" else "B") + token[1:]
    with pytest.raises(AdminQueryValidationError):
        service.list_devices(AdminPrincipal("x"), SITE_ID, cursor=tampered)
    assert current.calls == []


def test_device_list_context_serializer_and_encode_failures_are_typed():
    current = DeviceListCurrentSource()
    bad_gateway = DeviceListContextGateway()
    bad_gateway.list_devices_context = lambda **kwargs: AdminDeviceListContextPage(
        (_context_device(presence="bad"),), False
    )
    service, _devices, _codec = _device_list_context_service(
        current=current, gateway=bad_gateway
    )
    with pytest.raises(AdminQueryIntegrityUnavailable):
        service.list_devices(AdminPrincipal("x"), SITE_ID)

    service, _devices, _codec = _device_list_context_service(
        current=DeviceListCurrentSource(),
        gateway=DeviceListContextGateway(has_more=True),
        maximum=64,
    )
    with pytest.raises(AdminQueryUnavailable):
        service.list_devices(AdminPrincipal("x"), SITE_ID)


def test_device_list_context_trusted_continuation_keeps_signed_public_metadata():
    current = DeviceListCurrentSource()
    gateway = DeviceListContextGateway(has_more=True)
    service, _devices, _codec = _device_list_context_service(
        current=current, gateway=gateway
    )
    first = service.list_devices(AdminPrincipal("x"), SITE_ID)
    signed = first.result["current_state_overlay"]

    def revalidate(site_id, **kwargs):
        snapshot = _device_list_context_snapshot(
            kwargs["evaluated_at_utc"],
            observed_at="2026-09-09T11:59:51.000Z",
        )
        return CurrentClientInventoryContext(
            site_id, kwargs["evaluated_at_utc"], "trusted", snapshot,
            "cycle-1", DEVICE_LIST_SCOPE_HASH,
        )

    current.get_current_client_inventory_context = revalidate
    second = service.list_devices(
        AdminPrincipal("x"), SITE_ID, cursor=first.page["next_cursor"]
    )
    assert second.result["current_state_overlay"] == signed


def test_device_list_context_deadline_is_not_downgraded_to_unknown():
    current = DeviceListCurrentSource(
        failure=AnalyticsQueryDeadlineExceeded("deadline")
    )
    service, devices, _codec = _device_list_context_service(current=current)
    with pytest.raises(AdminQueryDeadline):
        service.list_devices(AdminPrincipal("x"), SITE_ID)
    assert devices.calls == []
