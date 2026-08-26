from __future__ import annotations

import os
import sqlite3
import time

import pytest

import run as process_runtime

from app.current_state.runtime import (
    CurrentStateRuntime,
    DisabledCurrentStateRuntime,
    UnavailableCurrentStateRuntime,
    create_current_state_runtime,
)
from app.current_state.models import CurrentStateSchemaError
from app.current_state import repository as repository_module
from app.current_state.repository import CurrentStateRepository
from app.models import Result


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


@pytest.mark.parametrize("message", ("database is locked", "database is busy"))
def test_existing_database_restart_retries_transient_storage_and_polls(
    enabled_settings, monkeypatch, message,
):
    enabled_settings["current_state_client_initial_delay_seconds"] = "0"
    enabled_settings["current_state_ap_initial_delay_seconds"] = "0"
    config_runtime = create_current_state_runtime(
        enabled_settings, Provider(), Telemetry()
    )
    assert isinstance(config_runtime, CurrentStateRuntime)
    CurrentStateRepository(config_runtime.config).initialize()

    class PollingProvider:
        def list_observation_clients(self, _site, page, page_size, _timeout):
            return Result.ok(data={
                "clients": [], "total_rows": 0, "page": page,
                "page_size": page_size, "http_status": 200, "error_code": 0,
            })

        def list_observation_access_points(
            self, _site, page, page_size, _timeout
        ):
            return Result.ok(data={
                "access_points": [], "total_rows": 0, "page": page,
                "page_size": page_size, "http_status": 200, "error_code": 0,
            })

    runtime = create_current_state_runtime(
        enabled_settings, PollingProvider(), Telemetry()
    )
    real_connect = repository_module.sqlite3.connect
    connect_attempts = 0

    def transient_then_connect(*args, **kwargs):
        nonlocal connect_attempts
        connect_attempts += 1
        if connect_attempts == 1:
            raise sqlite3.OperationalError(message)
        return real_connect(*args, **kwargs)

    monkeypatch.setattr(repository_module.sqlite3, "connect", transient_then_connect)
    assert runtime.start() is True
    deadline = time.monotonic() + 2
    cycle_kinds = set()
    while time.monotonic() < deadline:
        with runtime.repository.read_connection() as connection:
            cycle_kinds = {
                str(row[0]) for row in connection.execute(
                    "SELECT DISTINCT kind FROM current_state_cycles"
                )
            }
        if cycle_kinds == {"client", "ap"}:
            break
        time.sleep(0.01)
    assert connect_attempts >= 2
    assert cycle_kinds == {"client", "ap"}
    assert runtime.client_worker.running
    assert runtime.ap_worker.running
    assert runtime.stop(2.0)


def test_nontransient_schema_error_is_not_retried(enabled_settings):
    runtime = create_current_state_runtime(
        enabled_settings, Provider(), Telemetry()
    )
    attempts = 0

    def invalid_schema():
        nonlocal attempts
        attempts += 1
        raise CurrentStateSchemaError("incompatible schema")

    runtime.repository.initialize = invalid_schema
    assert runtime.start() is False
    assert runtime.state == "unavailable"
    assert attempts == 1


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
