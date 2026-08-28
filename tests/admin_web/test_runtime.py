from __future__ import annotations

import logging
from types import SimpleNamespace

import run as process_runtime
from app.admin_web import create_admin_web_runtime

from .conftest import enabled_settings


def test_disabled_runtime_registers_no_routes_or_state_stores():
    runtime = create_admin_web_runtime(
        {"web_admin_enabled": "false"},
        None,
        None,
        None,
        None,
        logging.getLogger("admin-disabled"),
    )
    assert runtime.state == "disabled"
    assert runtime.blueprint is None
    assert runtime.session_store is None


def test_invalid_enabled_config_fails_admin_closed_without_secret_log(caplog):
    secret = "plaintext-must-not-leak"
    with caplog.at_level(logging.ERROR):
        runtime = create_admin_web_runtime(
            enabled_settings(web_admin_password_hash=secret),
            object(), object(), object(), object(),
            logging.getLogger("admin-invalid"),
        )
    assert runtime.state == "unavailable"
    assert runtime.blueprint is None
    assert secret not in caplog.text


def test_valid_security_with_missing_sources_keeps_safe_shell_available():
    runtime = create_admin_web_runtime(
        enabled_settings(),
        None, None, None, None,
        logging.getLogger("admin-unavailable"),
    )
    assert runtime.state == "unavailable"
    assert runtime.blueprint is not None


def test_concrete_read_boundaries_compose_admin_query_service(tmp_path):
    registry = SimpleNamespace(
        repository=SimpleNamespace(
            config=SimpleNamespace(db_path=str(tmp_path / "registry.sqlite3"))
        )
    )
    visits = SimpleNamespace(
        repository=SimpleNamespace(db_path=tmp_path / "visits.sqlite3")
    )
    observations = SimpleNamespace(
        _repository=SimpleNamespace(db_path=tmp_path / "observations.sqlite3")
    )
    analytics = SimpleNamespace(state="active", visit_service=object())
    runtime = create_admin_web_runtime(
        enabled_settings(),
        analytics,
        registry,
        visits,
        observations,
        logging.getLogger("admin-query-composition"),
    )
    assert runtime.state == "active"
    assert runtime.query_service is not None


def test_incomplete_read_boundary_keeps_admin_runtime_unavailable():
    analytics = SimpleNamespace(state="active", visit_service=object())
    runtime = create_admin_web_runtime(
        enabled_settings(),
        analytics,
        SimpleNamespace(repository=object()),
        SimpleNamespace(repository=object()),
        SimpleNamespace(_repository=object()),
        logging.getLogger("admin-query-incomplete"),
    )
    assert runtime.state == "unavailable"
    assert runtime.query_service is None
    assert runtime.blueprint is not None


def test_process_runtime_composes_admin_after_sources(monkeypatch):
    selected = SimpleNamespace(blueprint=object())
    seen = {}

    class App:
        extensions = {"authorization_health_tracker": "auth-health"}

        def register_blueprint(self, blueprint):
            seen["blueprint"] = blueprint

    def create(settings, analytics, registry, visits, observations, logger, **kwargs):
        seen.update(
            settings=settings,
            analytics=analytics,
            registry=registry,
            visits=visits,
            observations=observations,
            current_state=kwargs.get("current_state_read_service"),
            authorization_health_tracker=kwargs.get(
                "authorization_health_tracker"
            ),
            current_state_runtime=kwargs.get("current_state_runtime"),
            observation_runtime=kwargs.get("observation_runtime"),
            visit_runtime=kwargs.get("visit_runtime"),
        )
        return selected

    analytics = SimpleNamespace(
        _source_services={"visits": "visit-read", "observations": "obs-read"}
    )
    current_read = object()
    monkeypatch.setattr(process_runtime, "_analytics_runtime", analytics)
    monkeypatch.setattr(
        process_runtime,
        "_current_state_runtime",
        SimpleNamespace(read_service=current_read),
    )
    monkeypatch.setattr(process_runtime, "_observation_foundation", "observation-runtime")
    monkeypatch.setattr(process_runtime, "_visit_lifecycle", "visit-runtime")
    monkeypatch.setattr(process_runtime, "create_admin_web_runtime", create)
    process_runtime._configure_admin_web(App(), {"web_admin_enabled": "false"}, "registry")
    assert seen["analytics"] is analytics
    assert seen["registry"] == "registry"
    assert seen["visits"] == "visit-read"
    assert seen["observations"] == "obs-read"
    assert seen["current_state"] is current_read
    assert seen["authorization_health_tracker"] == "auth-health"
    assert seen["current_state_runtime"] is process_runtime._current_state_runtime
    assert seen["observation_runtime"] == "observation-runtime"
    assert seen["visit_runtime"] == "visit-runtime"
    assert seen["blueprint"] is selected.blueprint


def test_process_runtime_starts_ap24_telemetry_after_admin_composition(monkeypatch):
    events = []
    telemetry = object()
    selected = SimpleNamespace(blueprint=None)

    class Worker:
        def start(self):
            events.append("start")

    worker = Worker()

    class App:
        extensions = {"auth_telemetry": telemetry}

        def register_blueprint(self, _blueprint):
            raise AssertionError("no blueprint expected")

    def create(*_args, **_kwargs):
        events.append("compose_admin")
        return selected

    def create_worker(settings, *, admin_runtime, telemetry, logger):
        assert settings == {"web_admin_enabled": "true"}
        assert admin_runtime is selected
        assert telemetry is App.extensions["auth_telemetry"]
        assert logger is process_runtime.logger
        events.append("compose_worker")
        return worker

    monkeypatch.setattr(process_runtime, "_analytics_runtime", SimpleNamespace(
        _source_services={"visits": None, "observations": None}
    ))
    monkeypatch.setattr(process_runtime, "_current_state_runtime", None)
    monkeypatch.setattr(process_runtime, "_observation_foundation", None)
    monkeypatch.setattr(process_runtime, "_visit_lifecycle", None)
    monkeypatch.setattr(process_runtime, "create_admin_web_runtime", create)
    monkeypatch.setattr(
        process_runtime,
        "create_home_ap_24h_telemetry_worker",
        create_worker,
    )

    process_runtime._configure_admin_web(
        App(), {"web_admin_enabled": "true"}, None
    )

    assert events == ["compose_admin", "compose_worker", "start"]
    assert App.extensions["home_ap_24h_telemetry_worker"] is worker


def test_process_runtime_admin_failure_is_fail_open(monkeypatch):
    class App:
        extensions = {}

        def register_blueprint(self, _):
            raise AssertionError("must not register")

    monkeypatch.setattr(
        process_runtime,
        "create_admin_web_runtime",
        lambda *_: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    process_runtime._configure_admin_web(App(), {}, None)
    assert process_runtime._admin_web_runtime is None


def test_ap24_telemetry_composition_failure_does_not_disable_admin(monkeypatch):
    selected = SimpleNamespace(blueprint=None)

    class App:
        extensions = {}

        def register_blueprint(self, _blueprint):
            raise AssertionError("no blueprint expected")

    monkeypatch.setattr(process_runtime, "_analytics_runtime", SimpleNamespace(
        _source_services={"visits": None, "observations": None}
    ))
    monkeypatch.setattr(process_runtime, "_current_state_runtime", None)
    monkeypatch.setattr(process_runtime, "_observation_foundation", None)
    monkeypatch.setattr(process_runtime, "_visit_lifecycle", None)
    monkeypatch.setattr(
        process_runtime,
        "create_admin_web_runtime",
        lambda *_args, **_kwargs: selected,
    )
    monkeypatch.setattr(
        process_runtime,
        "create_home_ap_24h_telemetry_worker",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    process_runtime._configure_admin_web(App(), {}, None)

    assert process_runtime._admin_web_runtime is selected
    assert App.extensions["admin_web_runtime"] is selected
    assert App.extensions["home_ap_24h_telemetry_worker"] is None


def test_access_handler_strips_all_admin_query_values_only():
    assert process_runtime._safe_access_requestline(
        "GET /admin/login?next=/admin/private HTTP/1.1"
    ) == "GET /admin/login HTTP/1.1"
    assert process_runtime._safe_access_requestline(
        "GET /admin/api/v1/sites?cursor=secret HTTP/1.1"
    ) == "GET /admin/api/v1/sites HTTP/1.1"
    assert process_runtime._safe_access_requestline(
        "GET /capport/login?client=known HTTP/1.1"
    ) == "GET /capport/login?client=known HTTP/1.1"


def test_production_handler_never_logs_admin_query_values():
    sentinel = "SECRET_ADMIN_SENTINEL"
    handler = object.__new__(process_runtime.SecretSafeRequestHandler)
    handler.requestline = f"GET /admin/login?next={sentinel} HTTP/1.1"
    records = []
    handler.log = lambda level, template, *args: records.append(template % args)
    handler.log_request(200, 10)
    assert records == ['"GET /admin/login HTTP/1.1" 200 10']
    assert sentinel not in records[0]


def test_shutdown_clears_admin_security_state(monkeypatch):
    calls = []
    monkeypatch.setattr(process_runtime, "_shutdown_completed", False)
    monkeypatch.setattr(
        process_runtime,
        "_admin_web_runtime",
        SimpleNamespace(clear=lambda: calls.append("clear")),
    )
    monkeypatch.setattr(process_runtime, "_home_ap_24h_telemetry_worker", None)
    monkeypatch.setattr(process_runtime, "_pending_session_cleaner", None)
    monkeypatch.setattr(process_runtime, "_observation_foundation", None)
    monkeypatch.setattr(process_runtime, "_public_traffic_worker", None)
    monkeypatch.setattr(process_runtime, "_visit_lifecycle", None)
    monkeypatch.setattr(process_runtime, "_visitor_snapshot_collector", None)
    monkeypatch.setattr(process_runtime, "_visitor_registry", None)
    monkeypatch.setattr(
        process_runtime.auth_executor,
        "shutdown",
        lambda **_: None,
    )
    process_runtime.shutdown_handler()
    process_runtime.shutdown_handler()
    assert calls == ["clear"]


def test_shutdown_stops_ap24_telemetry_before_read_sources(monkeypatch):
    calls = []
    monkeypatch.setattr(process_runtime, "_shutdown_completed", False)
    monkeypatch.setattr(
        process_runtime,
        "_home_ap_24h_telemetry_worker",
        SimpleNamespace(stop=lambda: calls.append("telemetry")),
    )
    monkeypatch.setattr(
        process_runtime,
        "_admin_web_runtime",
        SimpleNamespace(clear=lambda: calls.append("admin")),
    )
    monkeypatch.setattr(process_runtime, "_pending_session_cleaner", None)
    monkeypatch.setattr(
        process_runtime,
        "_observation_foundation",
        SimpleNamespace(stop=lambda: calls.append("observations")),
    )
    monkeypatch.setattr(
        process_runtime,
        "_current_state_runtime",
        SimpleNamespace(stop=lambda: calls.append("current_state")),
    )
    monkeypatch.setattr(process_runtime, "_public_traffic_worker", None)
    monkeypatch.setattr(process_runtime, "_visit_lifecycle", None)
    monkeypatch.setattr(process_runtime, "_visitor_snapshot_collector", None)
    monkeypatch.setattr(process_runtime, "_visitor_registry", None)
    monkeypatch.setattr(
        process_runtime.auth_executor,
        "shutdown",
        lambda **_: calls.append("auth_executor"),
    )

    process_runtime.shutdown_handler()

    assert calls.index("telemetry") < calls.index("observations")
    assert calls.index("telemetry") < calls.index("current_state")
