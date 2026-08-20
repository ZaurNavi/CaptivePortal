from __future__ import annotations

import logging
import hashlib
import threading
from types import SimpleNamespace

import run as process_runtime

from app.analytics.runtime import create_analytics_runtime
from app.visit_lifecycle.read_service import VisitLifecycleReadService
from app.visitor_registry.registry_read_service import VisitorRegistryReadService
from app.visitor_registry.registry_service import VisitorRegistryService


SITE = "0123456789abcdef01234567"


def _settings(**overrides):
    values = {
        "analytics_foundation_enabled": "true",
        "analytics_wireless_enabled": "true",
        "analytics_visit_enabled": "true",
        "analytics_api_enabled": "true",
        "analytics_api_bearer_token": "x" * 32,
        "analytics_api_allowed_networks": "127.0.0.1/32,::1/128",
        "analytics_api_allowed_site_ids": SITE,
    }
    values.update(overrides)
    return values


def _sources(stack):
    observation = SimpleNamespace(
        state="active", repository=stack.observations
    )
    visit = SimpleNamespace(
        state="active",
        read_service=VisitLifecycleReadService(stack.visits),
    )
    registry = VisitorRegistryReadService(
        stack.registry,
        VisitorRegistryService("UTC"),
        configured_enabled=True,
    )
    return observation, visit, registry


def test_disabled_runtime_creates_no_routes_or_source_connections():
    class Exploding:
        def __getattr__(self, name):
            raise AssertionError(name)

    runtime = create_analytics_runtime(
        _settings(analytics_foundation_enabled="false"),
        Exploding(), Exploding(), Exploding(), logging.getLogger("test"),
    )
    assert runtime.state == "disabled"
    assert runtime.blueprint is None


def test_active_runtime_reuses_existing_read_boundaries(analytics_stack):
    observation, visit, registry = _sources(analytics_stack)
    threads_before = tuple(thread.ident for thread in threading.enumerate())
    runtime = create_analytics_runtime(
        _settings(), observation, visit, registry, logging.getLogger("test")
    )
    assert runtime.state == "active"
    assert runtime.blueprint is not None
    assert set(runtime.source_health) == {"observations", "visits", "registry"}
    assert all(item.available for item in runtime.source_health.values())
    assert all(item.query_only for item in runtime.source_health.values())
    assert {
        name: item.actual_schema_version
        for name, item in runtime.source_health.items()
    } == {"observations": 1, "visits": 2, "registry": 1}
    assert tuple(thread.ident for thread in threading.enumerate()) == threads_before


def test_runtime_does_not_initialize_or_migrate_sources(
    analytics_stack, monkeypatch
):
    observation, visit, registry = _sources(analytics_stack)
    monkeypatch.setattr(
        analytics_stack.observations,
        "initialize",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError()),
    )
    monkeypatch.setattr(
        analytics_stack.visits,
        "initialize",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError()),
    )
    monkeypatch.setattr(
        analytics_stack.registry,
        "initialize",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError()),
    )
    runtime = create_analytics_runtime(
        _settings(), observation, visit, registry, logging.getLogger("test")
    )
    assert runtime.state == "active"


def test_missing_each_source_is_controlled_unavailable(analytics_stack):
    observation, visit, registry = _sources(analytics_stack)
    for sources in (
        (None, visit, registry),
        (observation, None, registry),
        (observation, visit, None),
    ):
        runtime = create_analytics_runtime(
            _settings(), *sources, logging.getLogger("test")
        )
        assert runtime.state == "unavailable"
        assert runtime.blueprint is not None


def test_invalid_security_config_fails_closed_without_routes(analytics_stack):
    observation, visit, registry = _sources(analytics_stack)
    runtime = create_analytics_runtime(
        _settings(analytics_api_bearer_token="short"),
        observation, visit, registry, logging.getLogger("test"),
    )
    assert runtime.state == "unavailable"
    assert runtime.blueprint is None


def test_invalid_metric_config_keeps_protected_health_available(
    analytics_stack,
):
    observation, visit, registry = _sources(analytics_stack)
    runtime = create_analytics_runtime(
        _settings(analytics_max_query_window_days="0"),
        observation, visit, registry, logging.getLogger("test"),
    )
    assert runtime.state == "unavailable"
    assert runtime.blueprint is not None


def test_health_payload_contains_no_paths_or_security_configuration(
    analytics_stack,
):
    observation, visit, registry = _sources(analytics_stack)
    runtime = create_analytics_runtime(
        _settings(), observation, visit, registry, logging.getLogger("test")
    )
    text = repr(runtime.health_payload())
    assert str(analytics_stack.observations.db_path) not in text
    assert "allowed_network" not in text
    assert SITE not in text
    assert "bearer" not in text


def test_live_health_rechecks_sources_and_recovers_without_restart(
    analytics_stack,
):
    observation, visit, registry = _sources(analytics_stack)
    runtime = create_analytics_runtime(
        _settings(), observation, visit, registry, logging.getLogger("test")
    )
    healthy, payload = runtime.live_health_payload()
    assert healthy is True
    assert payload["state"] == "active"

    original = runtime._source_services["observations"]  # noqa: SLF001

    class Unavailable:
        def analytics_read_connection(self):
            raise OSError("source disappeared")

    runtime._source_services["observations"] = Unavailable()  # noqa: SLF001
    healthy, payload = runtime.live_health_payload()
    assert healthy is False
    assert payload["state"] == "unavailable"
    assert payload["sources"]["observations"] == {
        "available": False,
        "expected_schema_version": 1,
        "actual_schema_version": None,
        "query_only": False,
    }

    runtime._source_services["observations"] = original  # noqa: SLF001
    healthy, payload = runtime.live_health_payload()
    assert healthy is True
    assert payload["state"] == "active"


def test_live_health_rejects_current_schema_mismatch_without_writes(
    analytics_stack,
):
    observation, visit, registry = _sources(analytics_stack)
    runtime = create_analytics_runtime(
        _settings(), observation, visit, registry, logging.getLogger("test")
    )
    original = runtime._source_services["visits"]  # noqa: SLF001

    class WrongVersion:
        def analytics_read_connection(self):
            context = original.analytics_read_connection()

            class Wrapped:
                def __enter__(self):
                    connection = context.__enter__()
                    return _VersionOverrideConnection(connection)

                def __exit__(self, *args):
                    return context.__exit__(*args)

            return Wrapped()

    runtime._source_services["visits"] = WrongVersion()  # noqa: SLF001
    before = hashlib.sha256(
        analytics_stack.visits.db_path.read_bytes()
    ).hexdigest()
    healthy, payload = runtime.live_health_payload()
    after = hashlib.sha256(
        analytics_stack.visits.db_path.read_bytes()
    ).hexdigest()
    assert healthy is False
    assert payload["sources"]["visits"]["actual_schema_version"] == 999
    assert before == after


class _VersionOverrideConnection:
    def __init__(self, connection):
        self._connection = connection

    def execute(self, statement, parameters=()):
        if statement == "PRAGMA user_version":
            return _SingleValueCursor(999)
        return self._connection.execute(statement, parameters)


class _SingleValueCursor:
    def __init__(self, value):
        self._value = value

    def fetchone(self):
        return (self._value,)


def test_production_access_handler_strips_analytics_query_values():
    sentinel = "SECRET_SENTINEL"
    handler = object.__new__(process_runtime.SecretSafeRequestHandler)
    handler.requestline = (
        "GET " + process_runtime.API_PREFIX
        + f"/health?token={sentinel}&from_utc=private HTTP/1.1"
    )
    records = []
    handler.log = lambda level, template, *args: records.append(
        template % args
    )
    handler.log_request(400, 123)
    assert records == [
        f'"GET {process_runtime.API_PREFIX}/health HTTP/1.1" 400 123'
    ]
    assert sentinel not in records[0]
    assert "from_utc" not in records[0]


def test_production_access_handler_preserves_portal_requestline():
    handler = object.__new__(process_runtime.SecretSafeRequestHandler)
    handler.requestline = "GET /capport/login?client=known HTTP/1.1"
    records = []
    handler.log = lambda level, template, *args: records.append(
        template % args
    )
    handler.log_request(200, 10)
    assert records == ['"GET /capport/login?client=known HTTP/1.1" 200 10']


def test_run_composition_passes_existing_source_objects_and_registers_blueprint(
    monkeypatch,
):
    observation = object()
    visit = object()
    registry = object()
    blueprint = object()
    selected = SimpleNamespace(blueprint=blueprint)
    seen = {}

    class App:
        extensions = {}

        def register_blueprint(self, value):
            seen["blueprint"] = value

    def create(settings, observation_runtime, visit_runtime,
               registry_read_service, logger):
        seen.update({
            "settings": settings,
            "observation": observation_runtime,
            "visit": visit_runtime,
            "registry": registry_read_service,
        })
        return selected

    monkeypatch.setattr(process_runtime, "_observation_foundation", observation)
    monkeypatch.setattr(process_runtime, "_visit_lifecycle", visit)
    monkeypatch.setattr(process_runtime, "create_analytics_runtime", create)
    app = App()
    process_runtime._configure_analytics(app, {"key": "value"}, registry)
    assert seen == {
        "settings": {"key": "value"},
        "observation": observation,
        "visit": visit,
        "registry": registry,
        "blueprint": blueprint,
    }
    assert app.extensions["analytics_runtime"] is selected


def test_run_composition_failure_is_fail_open(monkeypatch):
    class App:
        extensions = {}

    monkeypatch.setattr(
        process_runtime,
        "create_analytics_runtime",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("failed")),
    )
    app = App()
    process_runtime._configure_analytics(app, {}, None)
    assert app.extensions["analytics_runtime"] is None
