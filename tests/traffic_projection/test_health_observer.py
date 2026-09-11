from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.traffic_projection import health_observer as observer_module
from app.traffic_projection.health_observer import TrafficProjectionHealthObserver
from app.traffic_projection.models import (
    TrafficProjectionStorageCorrupt,
    TrafficProjectionStorageUnavailable,
)


SITE = "site-a"


class Telemetry:
    def __init__(self):
        self.events = []

    def emit(self, event, **fields):
        self.events.append((event, fields))

    def named(self, event):
        return [fields for name, fields in self.events if name == event]


class Service:
    def __init__(self, version="version-a", sites=(SITE,), observation=None):
        self.projection_version = version
        self.config = SimpleNamespace(site_ids=sites)
        self.observation = observation or _observation()
        self.calls = []

    def health_observation(self, site_id):
        self.calls.append(site_id)
        if isinstance(self.observation, BaseException):
            raise self.observation
        if callable(self.observation):
            return self.observation(site_id)
        return self.observation


class Root(Service):
    def __init__(self, services=(), **kwargs):
        super().__init__(**kwargs)
        self.services = services
        self.enumeration_failure = None

    def _health_worker_services(self):
        if self.enumeration_failure is not None:
            raise self.enumeration_failure
        return self.services


def _observation(
    status="healthy",
    *,
    source_available=True,
    sweep=None,
    cursor=(None, None),
    error=None,
):
    return {
        "health": {
            "status": status,
            "build_state": "active",
            "projection_revision": 3,
            "source_head_utc": "2026-09-11T12:00:00.000Z",
            "projection_head_utc": "2026-09-11T12:00:00.000Z",
            "head_lag_seconds": 0.0,
            "last_incremental_progress_at": "2026-09-11T12:00:00.000Z",
            "reconcile_sweep_started_at": sweep,
            "last_full_reconcile_completed_at": "2026-09-11T12:00:00.000Z",
            "backlog_cycle_count": 0,
        },
        "site_state": {
            "reconcile_sweep_from_utc": (
                "2026-09-01T00:00:00.000Z" if sweep else None
            ),
            "reconcile_sweep_source_head_utc": (
                "2026-09-11T12:00:00.000Z" if sweep else None
            ),
            "reconcile_cursor_started_at": cursor[0],
            "reconcile_cursor_cycle_id": cursor[1],
            "last_error_category": error,
        },
        "source_available": source_available,
        "version_status": "active",
    }


class NoThread:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.started = False

    def start(self):
        self.started = True

    def join(self, timeout=None):
        self.timeout = timeout

    def is_alive(self):
        return False


def test_start_seeds_active_and_target_keys_before_startup_observation(monkeypatch):
    monkeypatch.setattr(observer_module.threading, "Thread", NoThread)
    telemetry = Telemetry()
    active = Service("version-a", ("site-a", "site-b"))
    target = Service("version-b", ("site-a",))
    root = Root((active, target), version="version-a")
    observer = TrafficProjectionHealthObserver(root, telemetry=telemetry)
    expected = {
        ("version-a", "site-a"), ("version-a", "site-b"),
        ("version-b", "site-a"),
    }
    active.observation = lambda _site: (
        _observation() if observer.known_owned_keys == expected
        else (_ for _ in ()).throw(AssertionError("keys not seeded"))
    )
    observer.start(initial_services=[active, target])
    assert observer.known_owned_keys == expected
    assert len(telemetry.named("traffic_projection_product_health")) == 3


@pytest.mark.parametrize("status", ["diverged", "stale"])
def test_first_observation_does_not_fabricate_transition(status):
    telemetry = Telemetry()
    service = Service(observation=_observation(status))
    observer = TrafficProjectionHealthObserver(service, telemetry=telemetry)
    observer.observe_service_site(service, SITE)
    assert len(telemetry.named("traffic_projection_product_health")) == 1
    assert telemetry.named("traffic_projection_site_diverged") == []
    assert telemetry.named("traffic_projection_stale") == []
    assert telemetry.named("traffic_projection_recovered") == []


@pytest.mark.parametrize(
    "status,event",
    [("diverged", "traffic_projection_site_diverged"),
     ("stale", "traffic_projection_stale")],
)
def test_known_health_transition_emits_dedicated_event(status, event):
    telemetry = Telemetry()
    service = Service(observation=_observation())
    observer = TrafficProjectionHealthObserver(service, telemetry=telemetry)
    observer.observe_service_site(service, SITE)
    service.observation = _observation(status)
    observer.observe_service_site(service, SITE)
    assert len(telemetry.named("traffic_projection_product_health")) == 2
    assert len(telemetry.named(event)) == 1


def test_source_unavailable_transition_and_writer_dedupe_update_state():
    telemetry = Telemetry()
    service = Service(observation=_observation(source_available=True))
    observer = TrafficProjectionHealthObserver(service, telemetry=telemetry)
    observer.observe_service_site(service, SITE)
    service.observation = _observation(status="stale", source_available=False)
    observer.observe_service_site(
        service, SITE, source_unavailable_event_already_emitted=True
    )
    assert telemetry.named("traffic_projection_worker_source_unavailable") == []
    assert observer._previous_source_available[("version-a", SITE)] is False
    assert len(telemetry.named("traffic_projection_product_health")) == 2

    observer.observe_service_site(service, SITE)
    assert telemetry.named("traffic_projection_worker_source_unavailable") == []


def test_first_source_unavailable_emits_one_operational_and_one_product_event():
    telemetry = Telemetry()
    service = Service(observation=_observation("stale", source_available=False))
    observer = TrafficProjectionHealthObserver(service, telemetry=telemetry)
    observer.observe_service_site(service, SITE, force_heartbeat=True)
    assert len(telemetry.named("traffic_projection_worker_source_unavailable")) == 1
    assert len(telemetry.named("traffic_projection_product_health")) == 1


def test_storage_failure_is_bounded_and_recovery_forces_canonical_product_health():
    now = [0.0]
    telemetry = Telemetry()
    service = Service(observation=RuntimeError("unreadable"))
    observer = TrafficProjectionHealthObserver(
        service, telemetry=telemetry, monotonic=lambda: now[0]
    )
    observer.observe_service_site(service, SITE)
    observer.observe_service_site(service, SITE)
    assert len(telemetry.named("traffic_projection_worker_storage_unavailable")) == 1
    assert len(telemetry.named("traffic_projection_product_health")) == 1
    now[0] = 55.0
    observer.observe_service_site(service, SITE)
    assert len(telemetry.named("traffic_projection_product_health")) == 2
    service.observation = _observation("unavailable")
    observer.observe_service_site(service, SITE)
    assert len(telemetry.named("traffic_projection_product_health")) == 3


@pytest.mark.parametrize(
    "failure",
    [
        TrafficProjectionStorageUnavailable("unavailable"),
        TrafficProjectionStorageCorrupt("corrupt"),
        RuntimeError("enumeration unavailable"),
    ],
)
def test_enumeration_failure_falls_back_for_every_known_owned_key(failure):
    telemetry = Telemetry()
    active = Service("version-a", ("site-a",))
    target = Service("version-b", ("site-b",))
    root = Root((active, target), version="version-a")
    observer = TrafficProjectionHealthObserver(root, telemetry=telemetry)
    observer.known_owned_keys = {("version-a", "site-a"), ("version-b", "site-b")}
    root.enumeration_failure = failure
    observer._observe_once()
    fallback = telemetry.named("traffic_projection_product_health")
    assert {(item["projection_version"], item["site_id"]) for item in fallback} == {
        ("version-a", "site-a"), ("version-b", "site-b")
    }
    assert all(item["status"] == "unavailable" for item in fallback)


def test_one_site_observer_failure_does_not_skip_later_healthy_site(monkeypatch):
    telemetry = Telemetry()
    service = Service("version-a", ("site-a", "site-b"))
    root = Root((service,), version="version-a")
    observer = TrafficProjectionHealthObserver(root, telemetry=telemetry)
    original = observer.observe_service_site

    def observe(current_service, site_id, **kwargs):
        if site_id == "site-a":
            raise RuntimeError("one Site failed")
        return original(current_service, site_id, **kwargs)

    monkeypatch.setattr(observer, "observe_service_site", observe)
    observer._observe_once()
    health = telemetry.named("traffic_projection_product_health")
    assert [(item["site_id"], item["status"]) for item in health] == [
        ("site-a", "unavailable"),
        ("site-b", "healthy"),
    ]


def test_reconcile_stuck_uses_cursor_identity_not_incremental_progress():
    now = [0.0]
    telemetry = Telemetry()
    service = Service(observation=_observation(
        "catching_up",
        sweep="2026-09-11T11:00:00.000Z",
        cursor=("2026-09-10T00:00:00.000Z", "cycle-a"),
    ))
    observer = TrafficProjectionHealthObserver(
        service, telemetry=telemetry, monotonic=lambda: now[0]
    )
    observer.observe_service_site(service, SITE)
    service.observation["health"]["last_incremental_progress_at"] = (
        "2026-09-11T12:00:30.000Z"
    )
    now[0] = 60.0
    observer.observe_service_site(service, SITE)
    observer.observe_service_site(service, SITE)
    assert len(telemetry.named("traffic_projection_reconcile_stuck")) == 1


def test_request_stop_is_nonblocking_and_stop_joins_bounded_thread():
    telemetry = Telemetry()
    service = Service()
    observer = TrafficProjectionHealthObserver(service, telemetry=telemetry)
    thread = NoThread()
    observer._thread = thread
    observer.request_stop()
    assert observer._stop.is_set()
    assert not hasattr(thread, "timeout")
    assert observer.stop(2.0) is True
    assert thread.timeout == 2.0
