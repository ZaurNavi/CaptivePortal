from __future__ import annotations

import threading
from types import SimpleNamespace

import pytest

import run as runtime


class FakeApp:
    def __init__(self, events):
        self.events = events
        self.extensions = {}
        self.run_calls = []

    def run(self, **kwargs):
        self.events.append("app.run")
        self.run_calls.append(kwargs)


class FakeCollector:
    def __init__(
        self,
        events,
        *,
        start_result=True,
        start_error=None,
        timeout=17.5,
    ):
        self.events = events
        self.start_result = start_result
        self.start_error = start_error
        self.config = SimpleNamespace(
            shutdown_timeout_seconds=timeout
        )
        self.start_calls = 0
        self.stop_accepting_calls = 0
        self.drain_calls = []

    def start(self):
        self.events.append("collector.start")
        self.start_calls += 1
        if self.start_error is not None:
            raise self.start_error
        return self.start_result

    def stop_accepting(self):
        self.events.append("collector.stop_accepting")
        self.stop_accepting_calls += 1

    def drain_and_stop(self, timeout_seconds):
        self.events.append("collector.drain_and_stop")
        self.drain_calls.append(timeout_seconds)


class FakeAuthExecutor:
    def __init__(self, events):
        self.events = events
        self.calls = []

    def shutdown(self, **kwargs):
        self.events.append("auth_executor.shutdown")
        self.calls.append(kwargs)


class FakeTrafficWorker:
    def __init__(self, events):
        self.events = events
        self.stop_calls = 0

    def stop(self):
        self.events.append("public_traffic.stop")
        self.stop_calls += 1


class FakeRegistry:
    def __init__(
        self,
        events,
        *,
        start_result=True,
        start_error=None,
        timeout=11.5,
    ):
        self.events = events
        self.start_result = start_result
        self.start_error = start_error
        self.config = SimpleNamespace(
            shutdown_timeout_seconds=timeout
        )
        self.start_calls = 0
        self.stop_calls = []

    def start(self):
        self.events.append("registry.start")
        self.start_calls += 1
        if self.start_error is not None:
            raise self.start_error
        return self.start_result

    def stop(self, timeout, *, final_scan):
        self.events.append("registry.stop")
        self.stop_calls.append((timeout, final_scan))


@pytest.fixture(autouse=True)
def restore_runtime_globals():
    original_completed = runtime._shutdown_completed
    original_traffic = runtime._public_traffic_worker
    original_collector = runtime._visitor_snapshot_collector
    original_registry = runtime._visitor_registry
    runtime._shutdown_completed = False
    runtime._public_traffic_worker = None
    runtime._visitor_snapshot_collector = None
    runtime._visitor_registry = None
    yield
    runtime._shutdown_completed = original_completed
    runtime._public_traffic_worker = original_traffic
    runtime._visitor_snapshot_collector = original_collector
    runtime._visitor_registry = original_registry


def _prepare_main(
    monkeypatch,
    *,
    collector_start_result=True,
    collector_start_error=None,
    registry_start_result=True,
    registry_start_error=None,
    registry_create_error=None,
):
    events = []
    controller = object()
    collector = FakeCollector(
        events,
        start_result=collector_start_result,
        start_error=collector_start_error,
    )
    registry = FakeRegistry(
        events,
        start_result=registry_start_result,
        start_error=registry_start_error,
    )
    app = FakeApp(events)
    observed = {
        "collector_provider": None,
        "app_controller": None,
        "app_collector": None,
        "registry_settings": None,
    }

    monkeypatch.setattr(
        runtime.atexit,
        "register",
        lambda callback: events.append("atexit.register"),
    )
    monkeypatch.setattr(
        runtime.signal,
        "signal",
        lambda *args: None,
    )
    monkeypatch.setattr(
        runtime,
        "get_settings",
        lambda: {
            "host": "127.0.0.1",
            "port": 8088,
            "debug": False,
        },
    )

    def create_controller():
        events.append("create_controller")
        return controller

    def create_collector(*, settings, provider):
        events.append("create_visitor_snapshot_collector")
        observed["collector_provider"] = provider
        return collector

    def create_registry(settings):
        events.append("create_visitor_registry")
        observed["registry_settings"] = settings
        if registry_create_error is not None:
            raise registry_create_error
        return registry

    def create_app(*, controller, visitor_snapshot_collector):
        events.append("create_app")
        observed["app_controller"] = controller
        observed["app_collector"] = visitor_snapshot_collector
        return app

    monkeypatch.setattr(
        runtime,
        "create_controller",
        create_controller,
    )
    monkeypatch.setattr(
        runtime,
        "create_visitor_snapshot_collector",
        create_collector,
    )
    monkeypatch.setattr(
        runtime,
        "create_visitor_registry",
        create_registry,
    )
    monkeypatch.setattr(runtime, "create_app", create_app)
    monkeypatch.setattr(
        runtime,
        "_start_public_traffic_worker",
        lambda actual_app: events.append("public_traffic.start"),
    )
    monkeypatch.setattr(
        runtime,
        "shutdown_handler",
        lambda: events.append("shutdown_handler"),
    )
    return events, controller, collector, registry, app, observed


def test_main_wires_one_provider_and_starts_collector_before_app(
    monkeypatch,
):
    events, controller, collector, registry, app, observed = _prepare_main(
        monkeypatch
    )

    runtime.main()

    assert observed == {
        "collector_provider": controller,
        "app_controller": controller,
        "app_collector": collector,
        "registry_settings": {
            "host": "127.0.0.1",
            "port": 8088,
            "debug": False,
        },
    }
    assert collector.start_calls == 1
    assert registry.start_calls == 1
    assert events.index("create_controller") < events.index(
        "create_visitor_snapshot_collector"
    )
    assert events.index(
        "create_visitor_snapshot_collector"
    ) < events.index("create_app")
    assert events.index("create_app") < events.index("collector.start")
    assert events.index("collector.start") < events.index(
        "create_visitor_registry"
    )
    assert events.index("create_visitor_registry") < events.index(
        "registry.start"
    )
    assert events.index("registry.start") < events.index("app.run")
    assert app.run_calls == [{
        "host": "127.0.0.1",
        "port": 8088,
        "debug": False,
        "use_reloader": False,
    }]


@pytest.mark.parametrize(
    ("start_result", "start_error"),
    [
        (False, None),
        (False, OSError("collector start failed")),
    ],
)
def test_disabled_unavailable_or_raising_collector_does_not_stop_app(
    monkeypatch,
    start_result,
    start_error,
):
    events, _, collector, registry, app, _ = _prepare_main(
        monkeypatch,
        collector_start_result=start_result,
        collector_start_error=start_error,
    )

    runtime.main()

    assert collector.start_calls == 1
    assert registry.start_calls == 1
    assert events.count("app.run") == 1
    assert len(app.run_calls) == 1


@pytest.mark.parametrize(
    ("start_result", "start_error"),
    [
        (False, None),
        (False, OSError("registry start failed")),
    ],
)
def test_disabled_unavailable_or_raising_registry_does_not_stop_app(
    monkeypatch,
    start_result,
    start_error,
):
    events, _, collector, registry, app, _ = _prepare_main(
        monkeypatch,
        registry_start_result=start_result,
        registry_start_error=start_error,
    )

    runtime.main()

    assert collector.start_calls == 1
    assert registry.start_calls == 1
    assert events.count("app.run") == 1
    assert len(app.run_calls) == 1


@pytest.mark.parametrize(
    "factory_error",
    [OSError("path lookup failed"), RuntimeError("symlink loop")],
)
def test_unexpected_registry_factory_failure_remains_fail_open(
    monkeypatch,
    factory_error,
):
    events, _, _, registry, app, _ = _prepare_main(
        monkeypatch,
        registry_create_error=factory_error,
    )

    runtime.main()

    assert registry.start_calls == 0
    assert isinstance(
        runtime._visitor_registry,
        runtime.UnavailableVisitorRegistry,
    )
    assert events.count("app.run") == 1
    assert len(app.run_calls) == 1


def test_background_registry_audit_does_not_delay_app_run(
    monkeypatch,
):
    events, _, _, registry, app, _ = _prepare_main(monkeypatch)
    audit_started = threading.Event()
    release_audit = threading.Event()

    def run_audit():
        audit_started.set()
        release_audit.wait(1)

    def start_registry():
        events.append("registry.start")
        registry.start_calls += 1
        threading.Thread(target=run_audit, daemon=True).start()
        return True

    def run_app(**kwargs):
        assert audit_started.wait(0.2)
        assert not release_audit.is_set()
        events.append("app.run")
        app.run_calls.append(kwargs)
        release_audit.set()

    registry.start = start_registry
    app.run = run_app

    runtime.main()

    assert events.index("registry.start") < events.index("app.run")
    assert app.run_calls


def test_shutdown_order_timeout_and_idempotency(monkeypatch):
    events = []
    auth_executor = FakeAuthExecutor(events)
    traffic = FakeTrafficWorker(events)
    collector = FakeCollector(events, timeout=23.75)
    registry = FakeRegistry(events, timeout=12.25)
    runtime._public_traffic_worker = traffic
    runtime._visitor_snapshot_collector = collector
    runtime._visitor_registry = registry
    monkeypatch.setattr(runtime, "auth_executor", auth_executor)

    runtime.shutdown_handler()
    runtime.shutdown_handler()

    assert events == [
        "public_traffic.stop",
        "auth_executor.shutdown",
        "collector.stop_accepting",
        "collector.drain_and_stop",
        "registry.stop",
    ]
    assert auth_executor.calls == [{
        "wait": True,
        "cancel_futures": False,
    }]
    assert collector.stop_accepting_calls == 1
    assert collector.drain_calls == [23.75]
    assert registry.stop_calls == [(12.25, True)]
    assert traffic.stop_calls == 1


def test_shutdown_uses_90_second_fallback_without_collector_config(
    monkeypatch,
):
    events = []
    auth_executor = FakeAuthExecutor(events)

    class CollectorWithoutConfig:
        def __init__(self):
            self.drain_calls = []

        def stop_accepting(self):
            events.append("collector.stop_accepting")

        def drain_and_stop(self, timeout_seconds):
            events.append("collector.drain_and_stop")
            self.drain_calls.append(timeout_seconds)

    collector = CollectorWithoutConfig()
    runtime._visitor_snapshot_collector = collector
    monkeypatch.setattr(runtime, "auth_executor", auth_executor)

    runtime.shutdown_handler()

    assert events == [
        "auth_executor.shutdown",
        "collector.stop_accepting",
        "collector.drain_and_stop",
    ]
    assert collector.drain_calls == [90.0]
