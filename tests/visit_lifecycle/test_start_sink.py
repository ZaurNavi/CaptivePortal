from __future__ import annotations

import logging

import pytest

from app.visit_lifecycle import (
    VisitStartOutcome,
    VisitStorageCategory,
    VisitStorageError,
    VisitWriterContention,
    VisitTelemetry,
    VisitValidationError,
)
from app.visit_lifecycle.start_sink import LocalVisitStartSubmitter

from .conftest import make_request


class ServiceStub:
    def __init__(self, error=None):
        self.error = error

    def submit_authorized(self, request, **_kwargs):
        if self.error is not None:
            raise self.error
        return VisitStartOutcome(status="opened", visit_id="visit")

    def wake_write_waiters(self):
        return None


class SequenceService:
    def __init__(self, values):
        self.values = list(values)
        self.calls = 0
        self.wake_calls = 0

    def submit_authorized(self, request, **_kwargs):
        value = self.values[self.calls]
        self.calls += 1
        if isinstance(value, Exception):
            raise value
        return value

    def wake_write_waiters(self):
        self.wake_calls += 1


class CapturingTelemetry:
    def __init__(self):
        self.events = []

    def emit(self, event, level="info", **fields):
        self.events.append((event, level, fields))
        return True


@pytest.mark.parametrize(
    "category",
    [
        VisitStorageCategory.BUSY,
        VisitStorageCategory.FULL,
        VisitStorageCategory.CORRUPT,
        VisitStorageCategory.IO_ERROR,
    ],
)
def test_storage_failure_is_safe_outcome(category):
    sink = LocalVisitStartSubmitter(
        ServiceStub(VisitStorageError(category)),
        VisitTelemetry(logging.getLogger("test.start_sink")),
    )
    outcome = sink.submit_authorized(make_request())
    assert outcome.status == "unavailable"
    assert outcome.storage_category == category.value


def test_stop_accepting_rejects_new_calls_without_queueing():
    sink = LocalVisitStartSubmitter(
        ServiceStub(),
        VisitTelemetry(logging.getLogger("test.start_sink")),
    )
    sink.stop_accepting()
    assert sink.submit_authorized(make_request()).status == "shutting_down"
    assert sink.wait_for_idle(0) is True


def test_transient_busy_recovers_without_final_storage_error():
    service = SequenceService([
        VisitStorageError(VisitStorageCategory.BUSY),
        VisitStartOutcome(status="opened", visit_id="visit"),
    ])
    telemetry = CapturingTelemetry()
    sink = LocalVisitStartSubmitter(
        service,
        telemetry,
        total_budget_ms=500,
    )
    assert sink.submit_authorized(make_request()).status == "opened"
    assert service.calls == 2
    assert not [item for item in telemetry.events if item[0] == "visit.storage_error"]


def test_ambiguous_busy_retry_emits_one_recovered_event():
    service = SequenceService([
        VisitStorageError(VisitStorageCategory.BUSY),
        VisitStartOutcome(status="duplicate", visit_id="visit"),
    ])
    telemetry = CapturingTelemetry()
    sink = LocalVisitStartSubmitter(
        service,
        telemetry,
        total_budget_ms=500,
    )
    assert sink.submit_authorized(make_request()).status == "duplicate"
    recovered = [
        item for item in telemetry.events
        if item[0] == "visit.start_retry_recovered"
    ]
    assert len(recovered) == 1
    assert recovered[0][1] == "info"
    assert recovered[0][2]["operation"] == "start"
    assert recovered[0][2]["attempt"] == 2
    assert recovered[0][2]["retry_exhausted"] is False


def test_busy_exhaustion_is_bounded_and_emits_one_final_error():
    service = SequenceService([
        VisitStorageError(VisitStorageCategory.BUSY),
        VisitStorageError(VisitStorageCategory.BUSY),
        VisitStorageError(VisitStorageCategory.BUSY),
    ])
    telemetry = CapturingTelemetry()
    sink = LocalVisitStartSubmitter(
        service,
        telemetry,
        total_budget_ms=500,
    )
    outcome = sink.submit_authorized(make_request())
    assert outcome.status == "unavailable"
    assert outcome.storage_category == "busy"
    assert service.calls == 3
    errors = [
        item for item in telemetry.events if item[0] == "visit.storage_error"
    ]
    assert len(errors) == 1
    assert errors[0][2]["operation"] == "start"
    assert errors[0][2]["attempt"] == 3
    assert errors[0][2]["retry_exhausted"] is True
    assert errors[0][2]["budget_ms"] == 500


def test_final_busy_telemetry_aggregates_every_retry_blocker():
    background = VisitStorageError(
        VisitStorageCategory.BUSY,
        lock_wait_ms=11,
        contention_layer="coordinator",
        contention=VisitWriterContention(
            holder_operation="pending_retry",
            holder_age_ms=40,
            foreground_queue_depth=0,
            background_queue_depth=1,
            waiter_operation="start",
            waiter_wait_ms=11,
        ),
    )
    foreground = VisitStorageError(
        VisitStorageCategory.BUSY,
        lock_wait_ms=17,
        contention_layer="coordinator",
        contention=VisitWriterContention(
            holder_operation="start",
            holder_age_ms=17,
            foreground_queue_depth=1,
            background_queue_depth=0,
            waiter_operation="start",
            waiter_wait_ms=17,
        ),
    )
    sqlite_busy = VisitStorageError(
        VisitStorageCategory.BUSY,
        lock_wait_ms=23,
        contention_layer="sqlite",
    )
    service = SequenceService([background, sqlite_busy, foreground])
    telemetry = CapturingTelemetry()
    sink = LocalVisitStartSubmitter(service, telemetry, total_budget_ms=500)

    assert sink.submit_authorized(make_request()).status == "unavailable"
    fields = [
        event[2]
        for event in telemetry.events
        if event[0] == "visit.storage_error"
    ][0]
    assert fields["coordinator_busy_attempt_count"] == 2
    assert fields["sqlite_busy_attempt_count"] == 1
    assert fields["background_blocked_attempt_count"] == 1
    assert fields["background_blocked_wait_ms"] == 11
    assert fields["foreground_blocked_attempt_count"] == 1
    assert fields["foreground_blocked_wait_ms"] == 17
    assert fields["max_background_holder_age_ms"] == 40
    assert fields["last_holder_operation"] == "start"
    assert fields["contention_layer"] == "coordinator"
    assert fields["holder_operation"] == "start"
    assert fields["holder_age_ms"] == 17
    assert fields["foreground_queue_depth"] == 1
    assert fields["background_queue_depth"] == 0
    assert fields["waiter_operation"] == "start"
    assert fields["waiter_wait_ms"] == 17


def test_permanent_storage_error_is_not_retried():
    service = SequenceService([
        VisitStorageError(VisitStorageCategory.CORRUPT),
    ])
    telemetry = CapturingTelemetry()
    sink = LocalVisitStartSubmitter(service, telemetry)
    outcome = sink.submit_authorized(make_request())
    assert outcome.storage_category == "corrupt"
    assert service.calls == 1
    errors = [
        item for item in telemetry.events if item[0] == "visit.storage_error"
    ]
    assert len(errors) == 1
    assert errors[0][2]["retry_exhausted"] is False


def test_validation_error_is_not_retried():
    service = SequenceService([VisitValidationError("invalid")])
    telemetry = CapturingTelemetry()
    sink = LocalVisitStartSubmitter(service, telemetry)
    assert sink.submit_authorized(make_request()).status == "invalid"
    assert service.calls == 1
    errors = [
        item for item in telemetry.events if item[0] == "visit.storage_error"
    ]
    assert len(errors) == 1
    assert errors[0][1] == "warning"
    assert errors[0][2]["stage"] == "start_validation"
