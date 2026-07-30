from __future__ import annotations

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


@pytest.fixture(autouse=True)
def restore_runtime_globals():
    original_completed = runtime._shutdown_completed
    original_traffic = runtime._public_traffic_worker
    original_collector = runtime._visitor_snapshot_collector
    runtime._shutdown_completed = False
    runtime._public_traffic_worker = None
    runtime._visitor_snapshot_collector = None
    yield
    runtime._shutdown_completed = original_completed
    runtime._public_traffic_worker = original_traffic
    runtime._visitor_snapshot_collector = original_collector


def _prepare_main(
    monkeypatch,
    *,
    collector_start_result=True,
    collector_start_error=None,
):
    events = []
    controller = object()
    collector = FakeCollector(
        events,
        start_result=collector_start_result,
        start_error=collector_start_error,
    )
    app = FakeApp(events)
    observed = {
        "collector_provider": None,
        "app_controller": None,
        "app_collector": None,
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
    return events, controller, collector, app, observed


def test_main_wires_one_provider_and_starts_collector_before_app(
    monkeypatch,
):
    events, controller, collector, app, observed = _prepare_main(
        monkeypatch
    )

    runtime.main()

    assert observed == {
        "collector_provider": controller,
        "app_controller": controller,
        "app_collector": collector,
    }
    assert collector.start_calls == 1
    assert events.index("create_controller") < events.index(
        "create_visitor_snapshot_collector"
    )
    assert events.index(
        "create_visitor_snapshot_collector"
    ) < events.index("create_app")
    assert events.index("collector.start") < events.index("app.run")
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
    events, _, collector, app, _ = _prepare_main(
        monkeypatch,
        collector_start_result=start_result,
        collector_start_error=start_error,
    )

    runtime.main()

    assert collector.start_calls == 1
    assert events.count("app.run") == 1
    assert len(app.run_calls) == 1


def test_shutdown_order_timeout_and_idempotency(monkeypatch):
    events = []
    auth_executor = FakeAuthExecutor(events)
    traffic = FakeTrafficWorker(events)
    collector = FakeCollector(events, timeout=23.75)
    runtime._public_traffic_worker = traffic
    runtime._visitor_snapshot_collector = collector
    monkeypatch.setattr(runtime, "auth_executor", auth_executor)

    runtime.shutdown_handler()
    runtime.shutdown_handler()

    assert events == [
        "public_traffic.stop",
        "auth_executor.shutdown",
        "collector.stop_accepting",
        "collector.drain_and_stop",
    ]
    assert auth_executor.calls == [{
        "wait": True,
        "cancel_futures": False,
    }]
    assert collector.stop_accepting_calls == 1
    assert collector.drain_calls == [23.75]
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
