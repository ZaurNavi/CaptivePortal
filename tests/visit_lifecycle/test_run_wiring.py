from __future__ import annotations

import inspect

import run as runtime
from app.web.web import create_app


def test_create_app_exposes_explicit_visit_submitter_injection():
    assert "visit_start_submitter" in inspect.signature(create_app).parameters


def test_shutdown_drains_auth_before_closing_visit_start_sink(monkeypatch):
    events = []

    class VisitRuntime:
        def stop_scheduling(self):
            events.append("visit.stop_scheduling")

        def stop_accepting(self):
            events.append("visit.stop_accepting")

        def close(self):
            events.append("visit.close")

    class Executor:
        def shutdown(self, **kwargs):
            events.append("auth.shutdown")

    monkeypatch.setattr(runtime, "_shutdown_completed", False)
    monkeypatch.setattr(runtime, "_visit_lifecycle", VisitRuntime())
    monkeypatch.setattr(runtime, "auth_executor", Executor())
    monkeypatch.setattr(runtime, "_pending_session_cleaner", None)
    monkeypatch.setattr(runtime, "_observation_foundation", None)
    monkeypatch.setattr(runtime, "_public_traffic_worker", None)
    monkeypatch.setattr(runtime, "_visitor_snapshot_collector", None)
    monkeypatch.setattr(runtime, "_visitor_registry", None)
    runtime.shutdown_handler()
    assert events == [
        "visit.stop_scheduling",
        "auth.shutdown",
        "visit.stop_accepting",
        "visit.close",
    ]
