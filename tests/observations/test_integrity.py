from __future__ import annotations

import time

from app.observations.integrity import ObservationIntegrityWorker
from app.observations.telemetry import ObservationTelemetry


class Events:
    def __init__(self):
        self.items = []

    def safe_emit_system(self, event, level="info", **fields):
        self.items.append((event, level, fields))
        return True


class Logger:
    def log(self, *args, **kwargs):
        raise AssertionError("telemetry fallback should not be used")


def wait_until_stopped(worker, timeout=1.0):
    deadline = time.monotonic() + timeout
    while worker.running and time.monotonic() < deadline:
        time.sleep(0.01)
    assert worker.running is False


def test_integrity_worker_reports_success_without_blocking_start():
    class Repository:
        def validate_runtime_health(self, *, should_interrupt):
            assert should_interrupt() is False
            return True

    events = Events()
    worker = ObservationIntegrityWorker(
        Repository(),
        ObservationTelemetry(events, Logger()),
    )

    assert worker.start() is True
    wait_until_stopped(worker)

    assert worker.completed is True
    assert worker.timed_out is False
    assert worker.last_error is None
    assert [item[0] for item in events.items] == [
        "observation.integrity_check_started",
        "observation.integrity_check_completed",
    ]


def test_integrity_worker_reports_hard_deadline():
    class Repository:
        def validate_runtime_health(self, *, should_interrupt):
            return not should_interrupt()

    values = iter((0.0, 2.0, 2.0))
    events = Events()
    worker = ObservationIntegrityWorker(
        Repository(),
        ObservationTelemetry(events, Logger()),
        max_duration_seconds=1.0,
        monotonic=lambda: next(values, 2.0),
    )

    assert worker.start() is True
    wait_until_stopped(worker)

    assert worker.completed is False
    assert worker.timed_out is True
    assert worker.last_error is None
    assert [item[0] for item in events.items] == [
        "observation.integrity_check_started",
        "observation.integrity_check_timed_out",
    ]


def test_integrity_worker_failure_is_sanitized_and_degraded():
    class Repository:
        def validate_runtime_health(self, *, should_interrupt):
            raise RuntimeError("sensitive database detail")

    events = Events()
    worker = ObservationIntegrityWorker(
        Repository(),
        ObservationTelemetry(events, Logger()),
    )

    assert worker.start() is True
    wait_until_stopped(worker)

    assert isinstance(worker.last_error, RuntimeError)
    event, level, fields = events.items[-1]
    assert event == "observation.integrity_check_failed"
    assert level == "error"
    assert fields["failure_category"] == "storage_error"
    assert "sensitive" not in repr(fields)
