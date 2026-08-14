from __future__ import annotations

import logging
import uuid

from app.visit_lifecycle import VisitTelemetry
from app.visit_lifecycle.reconciliation import VisitLinkReconciler

from .conftest import config_with, make_request


class FakeRegistry:
    def __init__(self):
        self.devices = {}
        self.snapshots = {}
        self.device_calls = []
        self.snapshot_calls = []

    def get_device_by_mac(self, mac):
        self.device_calls.append(mac)
        return self.devices.get(mac)

    def get_snapshot_by_auth_session(self, session_id, *, site_id, client_mac):
        self.snapshot_calls.append((session_id, site_id, client_mac))
        return self.snapshots.get(session_id)


class FakeClock:
    def __init__(self):
        self.value = 0.0

    def monotonic(self):
        return self.value

    def advance(self, seconds):
        self.value += seconds


class AdvancingRegistry(FakeRegistry):
    def __init__(self, clock):
        super().__init__()
        self.clock = clock

    def get_device_by_mac(self, mac):
        value = super().get_device_by_mac(mac)
        self.clock.advance(0.3)
        return value

    def get_snapshot_by_auth_session(self, session_id, *, site_id, client_mac):
        value = super().get_snapshot_by_auth_session(
            session_id,
            site_id=site_id,
            client_mac=client_mac,
        )
        self.clock.advance(0.3)
        return value


class CapturingTelemetry:
    def __init__(self):
        self.events = []

    def emit(self, event, level="info", **fields):
        self.events.append((event, level, fields))
        return True


def _reconciler(config, repository, registry):
    return VisitLinkReconciler(
        config=config,
        repository=repository,
        registry_read_service=registry,
        telemetry=VisitTelemetry(logging.getLogger("test.reconcile")),
    )


def test_registry_links_are_added_outside_start_transaction(
    visit_config,
    visit_service,
    visit_repository,
):
    request = make_request()
    opened = visit_service.submit_authorized(request)
    before = visit_repository.get_visit("site-a", opened.visit_id)
    assert before.device_id is None
    assert before.initial_snapshot_id is None

    device_id = str(uuid.uuid4())
    snapshot_id = str(uuid.uuid4())
    registry = FakeRegistry()
    registry.devices[before.client_mac] = {"device_id": device_id}
    registry.snapshots[request.auth_session_id] = {
        "snapshot_id": snapshot_id,
        "site_id": "site-a",
        "requested_mac": before.client_mac,
    }
    assert _reconciler(visit_config, visit_repository, registry).run_once() == 1
    linked = visit_repository.get_visit("site-a", opened.visit_id)
    assert linked.device_id == device_id
    assert linked.initial_snapshot_id == snapshot_id
    assert linked.link_reconcile_attempt_count == 1
    assert linked.link_reconcile_attempted_at is not None
    assert linked.link_reconcile_next_at is None


def test_missing_snapshot_is_retried_and_existing_link_is_not_replaced(
    visit_config,
    visit_service,
    visit_repository,
):
    request = make_request()
    opened = visit_service.submit_authorized(request)
    original_device_id = str(uuid.uuid4())
    registry = FakeRegistry()
    registry.devices["02:11:22:33:44:55"] = {
        "device_id": original_device_id
    }
    reconciler = _reconciler(visit_config, visit_repository, registry)
    assert reconciler.run_once() == 1
    partial = visit_repository.get_visit("site-a", opened.visit_id)
    assert partial.device_id == original_device_id
    assert partial.initial_snapshot_id is None
    assert partial.link_reconcile_next_at is not None

    with visit_repository._connect() as connection:  # noqa: SLF001
        connection.execute(
            "UPDATE visits SET link_reconcile_next_at=NULL WHERE visit_id=?",
            (opened.visit_id,),
        )
    registry.devices["02:11:22:33:44:55"] = {
        "device_id": str(uuid.uuid4())
    }
    snapshot_id = str(uuid.uuid4())
    registry.snapshots[request.auth_session_id] = {
        "snapshot_id": snapshot_id,
        "site_id": "site-a",
        "requested_mac": "02:11:22:33:44:55",
    }
    reconciler.run_once()
    complete = visit_repository.get_visit("site-a", opened.visit_id)
    assert complete.device_id == original_device_id
    assert complete.initial_snapshot_id == snapshot_id
    assert complete.link_reconcile_attempt_count == 2


def test_more_than_batch_size_unresolved_rows_do_not_starve(
    visit_config,
    visit_service,
    visit_repository,
):
    config = config_with(visit_config, reconcile_batch_size=500)
    for index in range(501):
        visit_service.submit_authorized(make_request(
            client_mac=(
                f"02:00:00:{index // 65536:02X}:"
                f"{(index // 256) % 256:02X}:{index % 256:02X}"
            ),
        ))
    registry = FakeRegistry()
    reconciler = _reconciler(config, visit_repository, registry)
    assert reconciler.run_once() == 0
    assert len(registry.device_calls) == 500
    assert reconciler.run_once() == 0
    assert len(registry.device_calls) == 501
    with visit_repository._connect(readonly=True) as connection:  # noqa: SLF001
        counts = [
            row[0]
            for row in connection.execute(
                "SELECT link_reconcile_attempt_count FROM visits"
            )
        ]
    assert counts.count(1) == 501


def test_reconciliation_pass_stops_at_monotonic_deadline(
    visit_config,
    visit_service,
    visit_repository,
):
    config = config_with(visit_config, reconcile_batch_size=3)
    for index in range(3):
        visit_service.submit_authorized(make_request(
            client_mac=f"02:00:00:00:20:{index:02X}",
        ))
    clock = FakeClock()
    registry = AdvancingRegistry(clock)
    telemetry = CapturingTelemetry()
    reconciler = VisitLinkReconciler(
        config=config,
        repository=visit_repository,
        registry_read_service=registry,
        telemetry=telemetry,
        monotonic=clock.monotonic,
        pass_max_duration_seconds=0.8,
    )

    assert reconciler.run_once() == 0
    assert len(registry.device_calls) == 2
    assert len(registry.snapshot_calls) == 1
    with visit_repository._connect(readonly=True) as connection:  # noqa: SLF001
        counts = [
            row[0]
            for row in connection.execute(
                "SELECT link_reconcile_attempt_count FROM visits"
            )
        ]
    assert sorted(counts) == [0, 0, 1]
    deadline_events = [
        item for item in telemetry.events
        if item[0] == "visit.reconciliation_degraded"
        and item[2].get("stage") == "pass_deadline"
    ]
    assert len(deadline_events) == 1
    assert deadline_events[0][2]["processed_count"] == 1


def test_snapshot_wrong_site_or_mac_is_not_linked(
    visit_config,
    visit_service,
    visit_repository,
):
    request = make_request()
    opened = visit_service.submit_authorized(request)
    registry = FakeRegistry()
    registry.snapshots[request.auth_session_id] = {
        "snapshot_id": str(uuid.uuid4()),
        "site_id": "site-b",
        "requested_mac": "02:11:22:33:44:55",
    }
    _reconciler(visit_config, visit_repository, registry).run_once()
    assert visit_repository.get_visit(
        "site-a", opened.visit_id
    ).initial_snapshot_id is None
