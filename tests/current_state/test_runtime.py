from __future__ import annotations

import os

import run as process_runtime

from app.current_state.runtime import (
    CurrentStateRuntime,
    DisabledCurrentStateRuntime,
    UnavailableCurrentStateRuntime,
    create_current_state_runtime,
)


class Telemetry:
    def __init__(self):
        self.events = []

    def safe_emit_system(self, event, **fields):
        self.events.append(event)
        return True


class Provider:
    def list_observation_clients(self, *args):
        raise AssertionError("initial delay should prevent test polling")

    def list_observation_access_points(self, *args):
        raise AssertionError("initial delay should prevent test polling")


def test_disabled_runtime_starts_no_worker(tmp_path):
    runtime = create_current_state_runtime({}, Provider(), Telemetry())
    assert isinstance(runtime, DisabledCurrentStateRuntime)
    assert runtime.start() is False
    assert not (tmp_path / "current_state.sqlite3").exists()


def test_invalid_enabled_config_is_fail_open():
    telemetry = Telemetry()
    runtime = create_current_state_runtime({"current_state_enabled": "true"}, Provider(), telemetry)
    assert isinstance(runtime, UnavailableCurrentStateRuntime)
    assert runtime.start() is False
    assert "current_state.storage_error" in telemetry.events


def test_runtime_reuses_shared_provider_and_stops_bounded(enabled_settings):
    enabled_settings["current_state_client_initial_delay_seconds"] = "3600"
    enabled_settings["current_state_ap_initial_delay_seconds"] = "3600"
    provider = Provider()
    telemetry = Telemetry()
    runtime = create_current_state_runtime(enabled_settings, provider, telemetry)
    assert isinstance(runtime, CurrentStateRuntime)
    assert runtime.provider is provider
    assert runtime.client_worker.provider is provider
    assert runtime.ap_worker.provider is provider
    assert runtime.start() is True
    assert runtime.state == "active"
    assert runtime.stop(2.0) is True
    assert runtime.state == "disabled"
    assert telemetry.events.count("current_state.runtime_started") == 1
    assert telemetry.events.count("current_state.runtime_stopped") == 1


def test_storage_failure_degrades_only_current_state(enabled_settings):
    enabled_settings["current_state_db_path"] = os.path.join(enabled_settings["current_state_db_path"], "child.sqlite3")
    runtime = create_current_state_runtime(enabled_settings, Provider(), Telemetry())
    assert isinstance(runtime, CurrentStateRuntime)
    assert runtime.start() is False
    assert runtime.state == "unavailable"


def test_client_and_ap_degradation_are_independent(enabled_settings):
    enabled_settings["current_state_client_initial_delay_seconds"] = "3600"
    enabled_settings["current_state_ap_initial_delay_seconds"] = "3600"
    runtime = create_current_state_runtime(enabled_settings, Provider(), Telemetry())
    assert runtime.start()
    runtime.client_worker.degraded = True
    assert runtime.state == "degraded"
    assert runtime.client_state == "degraded"
    assert runtime.ap_state == "active"
    assert runtime.stop(2.0)


def test_process_composition_reuses_controller_and_telemetry(monkeypatch):
    provider = object()
    telemetry = object()
    selected = object()
    seen = {}

    class App:
        extensions = {"auth_telemetry": telemetry}

    def create(*, settings, provider, telemetry, logger):
        seen.update(settings=settings, provider=provider, telemetry=telemetry)
        return selected

    monkeypatch.setattr(process_runtime, "create_current_state_runtime", create)
    process_runtime._configure_current_state(App(), {"key": "value"}, provider)
    assert seen == {
        "settings": {"key": "value"},
        "provider": provider,
        "telemetry": telemetry,
    }
    assert App.extensions["current_state_runtime"] is selected


def test_process_composition_failure_is_portal_fail_open(monkeypatch):
    class App:
        extensions = {}

    monkeypatch.setattr(
        process_runtime,
        "create_current_state_runtime",
        lambda **_: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    process_runtime._configure_current_state(App(), {}, object())
    assert App.extensions["current_state_runtime"] is None
    assert process_runtime._current_state_runtime is None
