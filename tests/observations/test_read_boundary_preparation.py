"""Local preparation is separate from provider-capable worker startup."""
import threading

import pytest

from app.observations.runtime import create_observation_foundation
from .test_runtime import Telemetry, enabled


class ProviderSpy:
    def __init__(self):
        self.calls = []

    def __getattr__(self, name):
        self.calls.append(name)
        raise AssertionError("provider access during local preparation")


def workers(runtime):
    return (runtime.client_worker, runtime.ap_worker,
            runtime.cleanup_worker, runtime.integrity_worker)


def test_fresh_local_preparation_is_idempotent_and_network_thread_free(tmp_path, monkeypatch):
    (tmp_path / "data").mkdir(mode=0o750)
    provider, telemetry = ProviderSpy(), Telemetry()
    runtime = create_observation_foundation(enabled(tmp_path), provider, telemetry)
    calls = []
    initialize = runtime.repository.initialize

    def prepare_repository():
        calls.append("initialize")
        return initialize()

    monkeypatch.setattr(runtime.repository, "initialize", prepare_repository)
    for worker in workers(runtime):
        monkeypatch.setattr(worker, "start", lambda: pytest.fail("worker started during preparation"))
    before = tuple(thread.ident for thread in threading.enumerate())
    assert runtime.state == "disabled" and not runtime.read_boundary_ready
    assert all(not worker.running for worker in workers(runtime))
    assert provider.calls == []
    assert runtime.prepare_read_boundary() is True
    assert runtime.read_boundary_ready and runtime.state == "disabled"
    assert runtime.repository.db_path.is_file()
    assert runtime.prepare_read_boundary() is True
    assert calls == ["initialize"]
    assert all(not worker.running for worker in workers(runtime))
    assert tuple(thread.ident for thread in threading.enumerate()) == before
    assert provider.calls == []
    assert not any(event[0] == "observation.runtime_started" for event in telemetry.events)


@pytest.mark.parametrize("prepare_first", [False, True])
def test_start_initializes_once_and_preserves_abandoned_cycle_telemetry(tmp_path, monkeypatch, prepare_first):
    (tmp_path / "data").mkdir(mode=0o750)
    provider, telemetry = ProviderSpy(), Telemetry()
    runtime = create_observation_foundation(enabled(tmp_path), provider, telemetry)
    runtime.repository.initialize("2026-01-01T00:00:00.000Z")
    runtime.repository.create_cycle(kind="client", site_id="site-a",
        started_at="2026-01-01T00:00:00.000Z", cycle_id="abandoned-before-prepare")
    initialized, started = [], []
    original = runtime.repository.initialize

    def initialize():
        initialized.append(True)
        return original()

    monkeypatch.setattr(runtime.repository, "initialize", initialize)
    for name, worker in zip(("client", "ap", "cleanup", "integrity"), workers(runtime)):
        monkeypatch.setattr(worker, "start", lambda name=name: started.append(name) or True)
        monkeypatch.setattr(worker, "stop", lambda *_: True)
    if prepare_first:
        assert runtime.prepare_read_boundary() is True
        assert started == []
    assert runtime.start() is True
    assert runtime.start() is False
    assert initialized == [True]
    assert started == ["client", "ap", "cleanup", "integrity"]
    assert runtime.state == "active" and runtime.read_boundary_ready
    event = next(item for item in telemetry.events if item[0] == "observation.runtime_started")
    assert event[2]["abandoned_cycles"] == 1
    assert event[2]["client_enabled"] is True and event[2]["ap_enabled"] is True
    assert event[2]["site_count"] == 1
    assert provider.calls == []
    assert runtime.stop() is True
    assert not runtime.read_boundary_ready
    assert runtime.prepare_read_boundary() is True
    assert initialized == [True, True]  # A stopped lifecycle validates again.


def test_failed_preparation_is_fail_open_and_never_starts_workers(tmp_path, monkeypatch):
    provider, telemetry = ProviderSpy(), Telemetry()
    runtime = create_observation_foundation(enabled(tmp_path), provider, telemetry)
    initialized = []

    def fail():
        initialized.append(True)
        raise OSError("disposable unavailable storage")

    monkeypatch.setattr(runtime.repository, "initialize", fail)
    for worker in workers(runtime):
        monkeypatch.setattr(worker, "start", lambda: pytest.fail("worker started after preparation failure"))
    assert runtime.prepare_read_boundary() is False
    assert runtime.prepare_read_boundary() is False
    assert runtime.start() is False
    assert runtime.state == "unavailable" and not runtime.read_boundary_ready
    assert initialized == [True] and provider.calls == []
    failures = [event for event in telemetry.events if event[0] == "observation.runtime_unavailable"]
    assert len(failures) == 1
    assert failures[0][2]["failure_category"] == "initialization_error"


@pytest.mark.parametrize("settings", [
    {"observation_foundation_enabled": "false"},
    {"observation_foundation_enabled": "true", "observation_site_ids": ""},
])
def test_disabled_unavailable_variants_have_no_prepared_read_boundary(settings):
    provider = ProviderSpy()
    runtime = create_observation_foundation(settings, provider, Telemetry())
    assert runtime.prepare_read_boundary() is False
    assert runtime.read_boundary_ready is False
    assert runtime.start() is False
    assert provider.calls == []
