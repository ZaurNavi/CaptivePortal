from __future__ import annotations

import threading
import time
from pathlib import Path
from types import SimpleNamespace

import run as process_runtime

from app.observations.runtime import (
    DisabledObservationFoundation,
    ObservationFoundationRuntime,
    UnavailableObservationFoundation,
    create_observation_foundation,
)
from app.observations.models import CleanupResult


class Telemetry:
    def __init__(self):
        self.events = []

    def safe_emit_system(self, event, level="info", **fields):
        self.events.append((event, level, fields))
        return True


def enabled(tmp_path: Path):
    return {
        "observation_foundation_enabled": "true",
        "observation_db_path": str(tmp_path / "data" / "observations.sqlite3"),
        "observation_client_enabled": "true",
        "observation_ap_enabled": "true",
        "observation_site_ids": "site-a",
        "observation_client_initial_delay_seconds": "60",
        "observation_client_interval_seconds": "60",
        "observation_ap_initial_delay_seconds": "60",
        "observation_cleanup_initial_delay_seconds": "60",
    }


def test_disabled_factory_has_zero_io_threads_and_provider_calls(tmp_path):
    class Provider:
        def __getattr__(self, name):
            raise AssertionError(f"provider accessed: {name}")

    target = tmp_path / "not-created.sqlite3"
    runtime = create_observation_foundation(
        {"observation_foundation_enabled": "false", "observation_db_path": str(target)},
        Provider(),
        Telemetry(),
    )
    assert isinstance(runtime, DisabledObservationFoundation)
    assert runtime.state == "disabled"
    assert runtime.start() is False
    assert runtime.stop() is True
    assert not target.exists()


def test_invalid_enabled_config_returns_unavailable(tmp_path):
    telemetry = Telemetry()
    runtime = create_observation_foundation(
        {"observation_foundation_enabled": "true", "observation_site_ids": ""},
        object(),
        telemetry,
    )
    assert isinstance(runtime, UnavailableObservationFoundation)
    assert runtime.state == "unavailable"
    assert any(event[0] == "observation.runtime_unavailable" for event in telemetry.events)


def test_runtime_preserves_provider_identity_recovers_starts_and_stops(tmp_path):
    data = tmp_path / "data"
    data.mkdir(mode=0o750)
    provider = object()
    telemetry = Telemetry()
    runtime = create_observation_foundation(enabled(tmp_path), provider, telemetry)
    assert isinstance(runtime, ObservationFoundationRuntime)
    assert runtime.provider is provider
    assert runtime.client_worker.provider is provider
    assert runtime.ap_worker.provider is provider
    assert runtime.state == "disabled"
    assert runtime.start() is True
    assert runtime.start() is False
    assert runtime.state == "active"
    assert runtime.stop(2) is True
    assert runtime.stop(2) is True
    assert runtime.state == "disabled"
    names = [event[0] for event in telemetry.events]
    assert "observation.runtime_started" in names
    assert "observation.runtime_stopped" in names


def test_runtime_start_does_not_wait_for_full_integrity_scan(
    tmp_path,
    monkeypatch,
):
    data = tmp_path / "data"
    data.mkdir(mode=0o750)
    runtime = create_observation_foundation(
        enabled(tmp_path),
        object(),
        Telemetry(),
    )
    entered = threading.Event()
    release = threading.Event()

    def delayed_health_check(*, should_interrupt):
        entered.set()
        while not release.wait(0.01):
            if should_interrupt():
                return False
        return True

    monkeypatch.setattr(
        runtime.repository,
        "validate_runtime_health",
        delayed_health_check,
    )

    started_at = time.monotonic()
    assert runtime.start() is True
    elapsed = time.monotonic() - started_at
    try:
        assert elapsed < 0.5
        assert entered.wait(1)
        assert runtime.state == "active"
        assert runtime.integrity_worker.running is True
    finally:
        release.set()
        runtime.stop(2)


def test_background_integrity_failure_degrades_without_stopping_runtime(
    tmp_path,
    monkeypatch,
):
    data = tmp_path / "data"
    data.mkdir(mode=0o750)
    telemetry = Telemetry()
    runtime = create_observation_foundation(
        enabled(tmp_path),
        object(),
        telemetry,
    )

    def failed_health_check(*, should_interrupt):
        raise RuntimeError("integrity failure")

    monkeypatch.setattr(
        runtime.repository,
        "validate_runtime_health",
        failed_health_check,
    )

    assert runtime.start() is True
    try:
        deadline = time.monotonic() + 1
        while (
            runtime.integrity_worker.last_error is None
            and time.monotonic() < deadline
        ):
            time.sleep(0.01)
        assert runtime.state == "degraded"
        assert runtime.client_worker.running is True
        assert runtime.ap_worker.running is True
        names = [event[0] for event in telemetry.events]
        assert "observation.integrity_check_failed" in names
    finally:
        runtime.stop(2)


def test_stop_timeout_leaves_runtime_stopping(tmp_path, monkeypatch):
    data = tmp_path / "data"
    data.mkdir(mode=0o750)
    runtime = create_observation_foundation(enabled(tmp_path), object(), Telemetry())
    assert runtime.start() is True
    actual_stop = runtime.ap_worker.stop
    monkeypatch.setattr(runtime.ap_worker, "stop", lambda timeout: False)
    assert runtime.stop(0.1) is False
    assert runtime.state == "stopping"
    actual_stop(1)


def test_unavailable_working_runtime_still_stops_workers(tmp_path, monkeypatch):
    data = tmp_path / "data"
    data.mkdir(mode=0o750)
    runtime = create_observation_foundation(enabled(tmp_path), object(), Telemetry())
    calls = []
    runtime._state = "unavailable"
    monkeypatch.setattr(runtime.ap_worker, "stop", lambda timeout: calls.append("ap") or True)
    monkeypatch.setattr(runtime.client_worker, "stop", lambda timeout: calls.append("client") or True)
    monkeypatch.setattr(runtime.cleanup_worker, "stop", lambda timeout: calls.append("cleanup") or True)
    assert runtime.stop(1) is True
    assert runtime.state == "disabled"
    assert calls == ["ap", "client", "cleanup"]


def test_cleanup_success_clears_runtime_degraded_state(tmp_path, monkeypatch):
    data = tmp_path / "data"
    data.mkdir(mode=0o750)
    runtime = create_observation_foundation(enabled(tmp_path), object(), Telemetry())
    runtime._state = "active"
    calls = 0

    def cleanup_once(**kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("temporary cleanup failure")
        return CleanupResult(0, 0, 0, False, False)

    monkeypatch.setattr(runtime.cleanup_worker._cleanup, "run_once", cleanup_once)
    try:
        runtime.cleanup_worker.run_once()
    except RuntimeError:
        pass
    assert runtime.state == "degraded"

    runtime.cleanup_worker.run_once()
    assert runtime.cleanup_worker.last_error is None
    assert runtime.state == "active"


def test_integrity_timeout_marks_runtime_degraded(tmp_path):
    data = tmp_path / "data"
    data.mkdir(mode=0o750)
    runtime = create_observation_foundation(
        enabled(tmp_path),
        object(),
        Telemetry(),
    )
    runtime._state = "active"
    runtime.integrity_worker.timed_out = True

    assert runtime.state == "degraded"


def test_process_wiring_passes_same_provider_and_app_telemetry(monkeypatch):
    events = []
    provider = object()
    auth_telemetry = object()
    observation = SimpleNamespace(
        start=lambda: events.append("observation.start"),
        stop=lambda *a: events.append("observation.stop"),
    )
    app = SimpleNamespace(
        extensions={"auth_telemetry": auth_telemetry},
        run=lambda **kwargs: events.append("app.run"),
    )
    snapshot = SimpleNamespace(start=lambda: None)
    registry = SimpleNamespace(start=lambda: None)
    cleaner = SimpleNamespace(start=lambda: None)
    captured = {}

    monkeypatch.setattr(process_runtime, "_observation_foundation", None)
    monkeypatch.setattr(process_runtime, "_pending_session_cleaner", None)
    monkeypatch.setattr(process_runtime, "_visitor_snapshot_collector", None)
    monkeypatch.setattr(process_runtime, "_visitor_registry", None)

    monkeypatch.setattr(process_runtime.atexit, "register", lambda callback: None)
    monkeypatch.setattr(process_runtime.signal, "signal", lambda *args: None)
    monkeypatch.setattr(process_runtime, "get_settings", lambda: {
        "host": "127.0.0.1", "port": 8088, "debug": False,
    })
    monkeypatch.setattr(process_runtime, "create_controller", lambda: provider)
    monkeypatch.setattr(process_runtime, "create_visitor_snapshot_collector", lambda **kwargs: snapshot)
    monkeypatch.setattr(process_runtime, "create_app", lambda **kwargs: app)
    monkeypatch.setattr(process_runtime, "create_pending_session_cleaner", lambda **kwargs: cleaner)
    monkeypatch.setattr(process_runtime, "create_visitor_registry", lambda settings: registry)
    monkeypatch.setattr(process_runtime, "_start_public_traffic_worker", lambda app: None)
    monkeypatch.setattr(process_runtime, "shutdown_handler", lambda: None)

    def factory(*, settings, provider, telemetry, logger):
        captured.update(provider=provider, telemetry=telemetry)
        return observation

    monkeypatch.setattr(process_runtime, "create_observation_foundation", factory)
    process_runtime.main()
    assert captured == {"provider": provider, "telemetry": auth_telemetry}
    assert events == ["observation.start", "app.run"]


def test_process_shutdown_orders_cleaner_before_observations(monkeypatch):
    events = []

    class Stopper:
        config = SimpleNamespace(shutdown_timeout_seconds=2)

        def __init__(self, name):
            self.name = name

        def stop(self, *args, **kwargs):
            events.append(self.name)
            return True

    class Traffic:
        def stop(self):
            events.append("traffic")

    class Executor:
        def shutdown(self, **kwargs):
            events.append("auth")

    monkeypatch.setattr(process_runtime, "_shutdown_completed", False)
    monkeypatch.setattr(process_runtime, "_pending_session_cleaner", Stopper("cleaner"))
    monkeypatch.setattr(process_runtime, "_observation_foundation", Stopper("observation"))
    monkeypatch.setattr(process_runtime, "_public_traffic_worker", Traffic())
    monkeypatch.setattr(process_runtime, "_visitor_snapshot_collector", None)
    monkeypatch.setattr(process_runtime, "_visitor_registry", None)
    monkeypatch.setattr(process_runtime, "auth_executor", Executor())
    process_runtime.shutdown_handler()
    assert events == ["cleaner", "observation", "traffic", "auth"]
