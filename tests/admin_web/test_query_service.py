from __future__ import annotations

import threading

import pytest

from app.admin_web.config import admin_web_config_from_settings
from app.admin_web.device_gateway import (
    AdminDevicePage,
    AdminDeviceRow,
)
from app.admin_web.models import AdminPrincipal
from app.admin_web.policy import AdminAccessPolicy
from app.admin_web.query_service import (
    AdminQueryBusy,
    AdminQueryForbidden,
    AdminQueryService,
    AdminQueryUnavailable,
    AdminQueryValidationError,
)
from app.analytics.source_gateway import QueryDeadline
from app.analytics.models import (
    AnalyticsProvenance,
    AnalyticsQuality,
    AnalyticsResult,
)

from .conftest import SITE_ID, enabled_settings


DEVICE_ID = "10000000-0000-4000-8000-000000000001"


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
