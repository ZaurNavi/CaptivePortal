from __future__ import annotations

import copy
import threading
import time
from concurrent.futures import Future
from datetime import datetime, timedelta, timezone

import pytest

from app.models import Result
from app.visitor_registry.config import VisitorSnapshotConfig
from app.visitor_registry.snapshot_collector import (
    AuthorizedClientSnapshotCollector,
    DisabledVisitorSnapshotCollector,
    UnavailableVisitorSnapshotCollector,
    create_visitor_snapshot_collector,
)
from app.visitor_registry.snapshot_models import (
    AuthorizedClientAuthContext,
    AuthorizedClientSnapshotRequest,
    SnapshotSubmitOutcome,
)
from app.visitor_registry.telemetry import VisitorSnapshotTelemetry


NOW = datetime(2026, 7, 30, 1, 5, 12, tzinfo=timezone.utc)


class MemoryWriter:
    def __init__(self, initialize_result=True, fail_write=False):
        self.available = False
        self.initialize_result = initialize_result
        self.fail_write = fail_write
        self.records = []
        self.closed = 0
        self.lock = threading.RLock()

    def initialize(self):
        self.available = self.initialize_result
        return self.initialize_result

    def write(self, record):
        if self.fail_write:
            raise OSError("disk failed")
        with self.lock:
            self.records.append(copy.deepcopy(record))

    def close(self):
        self.available = False
        self.closed += 1


class SlowQueueRejectionWriter(MemoryWriter):
    def __init__(self):
        super().__init__()
        self.queue_write_entered = threading.Event()
        self.release_queue_write = threading.Event()

    def write(self, record):
        if record.get("error_category") == "queue_rejected":
            self.queue_write_entered.set()
            assert self.release_queue_write.wait(3)
        super().write(record)


class FakeSystemTelemetry:
    def __init__(self, result=True, raises=False):
        self.result = result
        self.raises = raises
        self.events = []
        self.lock = threading.RLock()

    def safe_emit_system(self, event, level="info", **fields):
        if self.raises:
            raise OSError("telemetry failed")
        with self.lock:
            self.events.append({
                "event": event,
                "level": level,
                **copy.deepcopy(fields),
            })
        return self.result


class SequenceProvider:
    def __init__(self, results):
        self.results = list(results)
        self.calls = []
        self.lock = threading.RLock()

    def get_client_snapshot(
        self,
        site_id,
        client_mac,
        timeout_seconds,
    ):
        with self.lock:
            self.calls.append(
                (site_id, client_mac, timeout_seconds)
            )
            result = self.results[
                min(len(self.calls) - 1, len(self.results) - 1)
            ]
        return result


class BlockingProvider:
    def __init__(self, result):
        self.result = result
        self.entered = threading.Event()
        self.release = threading.Event()
        self.calls = 0

    def get_client_snapshot(self, *args):
        self.calls += 1
        self.entered.set()
        assert self.release.wait(3)
        return self.result


class ParallelBlockingProvider:
    def __init__(self, result, expected_calls=2):
        self.result = result
        self.expected_calls = expected_calls
        self.all_entered = threading.Event()
        self.release = threading.Event()
        self.calls = 0
        self.lock = threading.RLock()

    def get_client_snapshot(self, *args):
        with self.lock:
            self.calls += 1
            if self.calls == self.expected_calls:
                self.all_entered.set()
        assert self.release.wait(3)
        return self.result


class AdvancingProvider:
    def __init__(self, result, clock, advance_seconds):
        self.result = result
        self.clock = clock
        self.advance_seconds = advance_seconds
        self.calls = 0

    def get_client_snapshot(self, *args):
        self.calls += 1
        self.clock["now"] += timedelta(
            seconds=self.advance_seconds
        )
        return self.result


class FailingExecutor:
    def __init__(self, *, fail_on_start=False, **kwargs):
        if fail_on_start:
            raise OSError("executor start failed")

    def submit(self, *args, **kwargs):
        raise RuntimeError("executor submit failed")

    def shutdown(self, **kwargs):
        return None


class ManualExecutor:
    def __init__(self, **kwargs):
        self.submissions = []

    def submit(self, fn, *args):
        future = Future()
        self.submissions.append((future, fn, args))
        return future

    def run_next(self):
        future, fn, args = self.submissions.pop(0)
        try:
            future.set_result(fn(*args))
        except BaseException as exc:
            future.set_exception(exc)
        return future

    def fail_next(self, exception):
        future, _, _ = self.submissions.pop(0)
        future.set_exception(exception)
        return future

    def shutdown(self, **kwargs):
        return None


def raw_client(mac="02-11-22-33-44-55", **updates):
    result = {
        "id": "client-id",
        "mac": mac,
        "name": "device",
        "hostName": "device",
        "ip": "192.0.2.27",
        "ipv6List": [],
        "ssid": "Zefer_Parki",
        "active": True,
        "authStatus": 2,
        "multiLink": [],
    }
    result.update(updates)
    return result


def success(mac="02-11-22-33-44-55", **updates):
    return Result.ok(
        message="Success.",
        data={
            "http_status": 200,
            "error_code": 0,
            "raw_result": raw_client(mac, **updates),
        },
    )


def failure(
    category,
    *,
    retryable,
    status=None,
    code=None,
    message="provider failed",
):
    return Result.fail(
        error="SNAPSHOT_REQUEST_FAILED",
        message=message,
        data={
            "http_status": status,
            "error_code": code,
            "failure_category": category,
            "retryable": retryable,
            "raw_result": None,
        },
    )


def request(**updates):
    values = {
        "auth_session_id": "session-id",
        "site_id": "site-id",
        "requested_mac": "02-11-22-33-44-55",
        "authorized_at": NOW - timedelta(seconds=1),
        "auth_context": AuthorizedClientAuthContext(
            client_ip="192.0.2.27",
            portal_ssid="Zefer_Parki",
            portal_ap_mac="02-AA-BB-CC-DD-EE",
            portal_radio_id="0",
            auth_run_number=1,
            authorization_attempt=1,
            auth_final_reason="AUTHORIZED_AFTER_ATTEMPT",
            retry_request_id=None,
        ),
    }
    values.update(updates)
    return AuthorizedClientSnapshotRequest(**values)


def config(**updates):
    values = {
        "enabled": True,
        "log_file": "unused.log",
        "max_workers": 1,
        "max_pending": 2,
        "max_job_age_seconds": 30.0,
        "request_timeout_seconds": 5.0,
        "retry_delays_seconds": (0.0, 0.0),
        "rotation_max_bytes": 1000,
        "rotation_backup_count": 1,
        "shutdown_timeout_seconds": 2.0,
    }
    values.update(updates)
    return VisitorSnapshotConfig(**values)


def collector(provider, writer=None, telemetry=None, **config_updates):
    writer = writer or MemoryWriter()
    system_telemetry = telemetry or FakeSystemTelemetry()
    service = AuthorizedClientSnapshotCollector(
        config=config(**config_updates),
        provider=provider,
        writer=writer,
        telemetry=VisitorSnapshotTelemetry(
            telemetry_provider=lambda: system_telemetry
        ),
        utcnow=lambda: NOW,
    )
    assert service.start()
    return service, writer, system_telemetry


def wait_for(predicate, timeout=3):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("condition was not reached")


def stop(service):
    service.drain_and_stop(2)


def test_successful_job_writes_one_complete_captured_event():
    provider = SequenceProvider([success()])
    service, writer, telemetry = collector(provider)
    assert service.submit(request()) is SnapshotSubmitOutcome.ACCEPTED
    wait_for(lambda: len(writer.records) == 1)
    wait_for(lambda: service.active_job_count == 0)
    record = writer.records[0]
    assert record["event"] == "visitor.client_snapshot.captured"
    assert record["schema_version"] == 1
    assert record["attempts"] == 1
    assert record["requested_mac"] == "02:11:22:33:44:55"
    assert record["client"]["mac"] == "02:11:22:33:44:55"
    assert record["auth_context"]["portal_ap_mac"] == (
        "02:AA:BB:CC:DD:EE"
    )
    assert record["authorized_at"].endswith("Z")
    assert record["captured_at"].endswith("Z")
    assert record["queue_delay_ms"] >= 0
    assert record["request_duration_ms"] >= 0
    assert record["snapshot_lag_ms"] == 1000
    assert provider.calls == [
        ("site-id", "02:11:22:33:44:55", 5.0)
    ]
    assert any(
        event["event"] == "visitor_snapshot_job_submitted"
        for event in telemetry.events
    )
    stop(service)


def test_transient_failures_retry_at_most_three_times():
    provider = SequenceProvider([
        failure("timeout", retryable=True),
        failure("http_error", retryable=True, status=500),
        success(),
    ])
    service, writer, telemetry = collector(provider)
    assert service.submit(request()) is SnapshotSubmitOutcome.ACCEPTED
    wait_for(lambda: len(writer.records) == 1)
    assert writer.records[0]["event"].endswith("captured")
    assert writer.records[0]["attempts"] == 3
    assert len(provider.calls) == 3
    assert sum(
        event["event"] == "visitor_snapshot_retry_scheduled"
        for event in telemetry.events
    ) == 2
    stop(service)


def test_final_transient_failure_preserves_last_diagnostics():
    provider = SequenceProvider([
        failure(
            "client_not_available",
            retryable=True,
            status=200,
            code=-41011,
        )
    ])
    service, writer, _ = collector(provider)
    assert service.submit(request()) is SnapshotSubmitOutcome.ACCEPTED
    wait_for(lambda: len(writer.records) == 1)
    record = writer.records[0]
    assert record["event"].endswith("failed")
    assert record["error_category"] == "client_not_available"
    assert record["attempts"] == 3
    assert record["http_status"] == 200
    assert record["error_code"] == -41011
    assert len(provider.calls) == 3
    stop(service)


@pytest.mark.parametrize(
    "category",
    ["controller_error", "http_error", "token_error"],
)
def test_permanent_provider_failure_does_not_retry(category):
    provider = SequenceProvider([
        failure(category, retryable=False, status=400, code=-1)
    ])
    service, writer, _ = collector(provider)
    assert service.submit(request()) is SnapshotSubmitOutcome.ACCEPTED
    wait_for(lambda: len(writer.records) == 1)
    assert len(provider.calls) == 1
    expected = (
        "controller_error"
        if category == "token_error"
        else category
    )
    assert writer.records[0]["error_category"] == expected
    stop(service)


def test_stale_job_never_calls_provider():
    provider = SequenceProvider([success()])
    service, writer, _ = collector(provider)
    old = request(authorized_at=NOW - timedelta(seconds=31))
    assert service.submit(old) is SnapshotSubmitOutcome.ACCEPTED
    wait_for(lambda: len(writer.records) == 1)
    assert provider.calls == []
    assert writer.records[0]["error_category"] == "snapshot_stale"
    assert writer.records[0]["attempts"] == 0
    stop(service)


def test_job_becoming_stale_between_attempts_stops_retry():
    clock = {"now": NOW}
    provider = AdvancingProvider(
        failure("timeout", retryable=True),
        clock,
        advance_seconds=31,
    )
    writer = MemoryWriter()
    service = AuthorizedClientSnapshotCollector(
        config=config(),
        provider=provider,
        writer=writer,
        telemetry=VisitorSnapshotTelemetry(
            telemetry_provider=lambda: FakeSystemTelemetry()
        ),
        utcnow=lambda: clock["now"],
    )
    assert service.start()
    assert service.submit(request(
        authorized_at=NOW,
    )) is SnapshotSubmitOutcome.ACCEPTED
    wait_for(lambda: len(writer.records) == 1)
    assert provider.calls == 1
    assert writer.records[0]["attempts"] == 1
    assert writer.records[0]["error_category"] == "snapshot_stale"
    stop(service)


def test_provider_call_started_before_deadline_can_finish_after_it():
    clock = {"now": NOW}
    provider = AdvancingProvider(
        success(),
        clock,
        advance_seconds=31,
    )
    writer = MemoryWriter()
    service = AuthorizedClientSnapshotCollector(
        config=config(),
        provider=provider,
        writer=writer,
        telemetry=VisitorSnapshotTelemetry(
            telemetry_provider=lambda: FakeSystemTelemetry()
        ),
        utcnow=lambda: clock["now"],
    )
    assert service.start()
    assert service.submit(request(
        authorized_at=NOW,
    )) is SnapshotSubmitOutcome.ACCEPTED
    wait_for(lambda: len(writer.records) == 1)
    assert provider.calls == 1
    assert writer.records[0]["event"].endswith("captured")
    stop(service)


def test_mac_mismatch_is_final_and_keeps_safe_raw():
    provider = SequenceProvider([success("02-66-77-88-99-AA")])
    service, writer, _ = collector(provider)
    assert service.submit(request()) is SnapshotSubmitOutcome.ACCEPTED
    wait_for(lambda: len(writer.records) == 1)
    record = writer.records[0]
    assert record["error_category"] == "mac_mismatch"
    assert record["returned_mac"] == "02:66:77:88:99:AA"
    assert record["raw_controller_snapshot"]["mac"] == (
        "02-66-77-88-99-AA"
    )
    assert len(provider.calls) == 1
    stop(service)


@pytest.mark.parametrize("bad_value", [float("nan"), "\ud800", object()])
def test_non_json_raw_becomes_normalization_error_without_raw(
    bad_value,
):
    provider = SequenceProvider([success(rateLimit={"value": bad_value})])
    service, writer, _ = collector(provider)
    assert service.submit(request()) is SnapshotSubmitOutcome.ACCEPTED
    wait_for(lambda: len(writer.records) == 1)
    record = writer.records[0]
    assert record["error_category"] == "normalization_error"
    assert "raw_controller_snapshot" not in record
    assert "rateLimit.value" in record["message"]
    assert len(provider.calls) == 1
    stop(service)


def test_recursive_redaction_emits_operational_event_without_raw():
    provider = SequenceProvider([
        success(
            accessToken="secret",
            nested={"password": "secret"},
        )
    ])
    service, writer, telemetry = collector(provider)
    assert service.submit(request()) is SnapshotSubmitOutcome.ACCEPTED
    wait_for(lambda: len(writer.records) == 1)
    raw = writer.records[0]["raw_controller_snapshot"]
    assert raw["accessToken"] == "[REDACTED]"
    assert raw["nested"]["password"] == "[REDACTED]"
    event = next(
        item
        for item in telemetry.events
        if item["event"]
        == "visitor_snapshot_sensitive_field_redacted"
    )
    assert "raw_controller_snapshot" not in event
    assert "secret" not in repr(event)
    stop(service)


def test_provider_error_message_is_sanitized_before_data_log():
    provider = SequenceProvider([
        failure(
            "controller_error",
            retryable=False,
            message=(
                "Authorization: Bearer top-secret\n"
                "password=hidden cookie=session-secret"
            ),
        )
    ])
    service, writer, _ = collector(provider)
    assert service.submit(request()) is SnapshotSubmitOutcome.ACCEPTED
    wait_for(lambda: len(writer.records) == 1)
    message = writer.records[0]["message"]
    assert "top-secret" not in message
    assert "hidden" not in message
    assert "session-secret" not in message
    assert "\n" not in message
    assert message.count("[REDACTED]") == 3
    stop(service)


def test_active_duplicate_is_suppressed_and_capacity_released():
    provider = BlockingProvider(success())
    service, writer, telemetry = collector(provider)
    first = request()
    assert service.submit(first) is SnapshotSubmitOutcome.ACCEPTED
    assert provider.entered.wait(2)
    assert service.submit(first) is (
        SnapshotSubmitOutcome.DUPLICATE_SUPPRESSED
    )
    provider.release.set()
    wait_for(lambda: len(writer.records) == 1)
    wait_for(lambda: service.active_job_count == 0)
    assert provider.calls == 1
    assert any(
        event["event"]
        == "visitor_snapshot_duplicate_suppressed"
        for event in telemetry.events
    )
    stop(service)


def test_different_clients_run_in_parallel_up_to_worker_limit():
    provider = ParallelBlockingProvider(success(), expected_calls=2)
    service, writer, _ = collector(
        provider,
        max_workers=2,
        max_pending=0,
    )
    first = request()
    second = request(
        auth_session_id="second-session",
        requested_mac="02:11:22:33:44:66",
    )
    assert service.submit(first) is SnapshotSubmitOutcome.ACCEPTED
    assert service.submit(second) is SnapshotSubmitOutcome.ACCEPTED
    assert provider.all_entered.wait(2)
    assert provider.calls == 2
    provider.release.set()
    wait_for(lambda: len(writer.records) == 2)
    stop(service)


def test_completed_job_can_be_submitted_again_with_stable_id():
    provider = SequenceProvider([success(), success()])
    service, writer, _ = collector(provider)
    first = request()
    assert service.submit(first) is SnapshotSubmitOutcome.ACCEPTED
    wait_for(lambda: len(writer.records) == 1)
    wait_for(lambda: service.active_job_count == 0)
    assert service.submit(first) is SnapshotSubmitOutcome.ACCEPTED
    wait_for(lambda: len(writer.records) == 2)
    assert len(provider.calls) == 2
    assert writer.records[0]["snapshot_id"] == (
        writer.records[1]["snapshot_id"]
    )
    stop(service)


def test_queue_rejection_is_nonblocking_and_does_not_call_provider():
    provider = BlockingProvider(success())
    service, writer, telemetry = collector(
        provider,
        max_pending=0,
    )
    assert service.submit(request()) is SnapshotSubmitOutcome.ACCEPTED
    assert provider.entered.wait(2)
    second = request(
        auth_session_id="second-session",
        requested_mac="02-AA-BB-CC-DD-EE",
    )
    started = time.monotonic()
    assert service.submit(second) is SnapshotSubmitOutcome.QUEUE_REJECTED
    assert time.monotonic() - started < 0.5
    assert provider.calls == 1
    rejected = next(
        item
        for item in writer.records
        if item.get("error_category") == "queue_rejected"
    )
    assert rejected["attempts"] == 0
    assert rejected["queue_delay_ms"] is None
    assert rejected["request_duration_ms"] == 0
    assert any(
        event["event"] == "visitor_snapshot_queue_rejected"
        for event in telemetry.events
    )
    provider.release.set()
    wait_for(lambda: len(writer.records) == 2)
    stop(service)


def test_slow_queue_rejection_write_does_not_hold_collector_lock():
    provider = BlockingProvider(success())
    writer = SlowQueueRejectionWriter()
    service, _, _ = collector(
        provider,
        writer=writer,
        max_pending=0,
    )
    assert service.submit(request()) is SnapshotSubmitOutcome.ACCEPTED
    assert provider.entered.wait(2)

    outcomes = []
    rejected_request = request(
        auth_session_id="rejected-session",
        requested_mac="02:11:22:33:44:66",
    )
    submit_thread = threading.Thread(
        target=lambda: outcomes.append(
            service.submit(rejected_request)
        ),
    )
    submit_thread.start()
    assert writer.queue_write_entered.wait(2)

    def capacity_released():
        acquired = service._capacity.acquire(blocking=False)
        if acquired:
            service._capacity.release()
        return acquired

    try:
        provider.release.set()
        wait_for(capacity_released)
    finally:
        writer.release_queue_write.set()
        submit_thread.join(2)

    assert outcomes == [SnapshotSubmitOutcome.QUEUE_REJECTED]
    wait_for(lambda: service.active_job_count == 0)
    assert len(writer.records) == 2
    stop(service)


def test_exact_capacity_includes_workers_and_pending_jobs():
    provider = SequenceProvider([success()])
    writer = MemoryWriter()
    telemetry = FakeSystemTelemetry()
    manual_executor = ManualExecutor()
    service = AuthorizedClientSnapshotCollector(
        config=config(max_workers=2, max_pending=1),
        provider=provider,
        writer=writer,
        telemetry=VisitorSnapshotTelemetry(
            telemetry_provider=lambda: telemetry
        ),
        executor_factory=lambda **kwargs: manual_executor,
        utcnow=lambda: NOW,
    )
    assert service.start()
    for index in range(3):
        assert service.submit(request(
            auth_session_id=f"session-{index}",
            requested_mac=f"02:11:22:33:44:{55 + index:02X}",
        )) is SnapshotSubmitOutcome.ACCEPTED
    assert service.submit(request(
        auth_session_id="session-over-capacity",
        requested_mac="02:11:22:33:44:99",
    )) is SnapshotSubmitOutcome.QUEUE_REJECTED
    assert len(manual_executor.submissions) == 3
    while manual_executor.submissions:
        manual_executor.run_next()
    wait_for(lambda: service.active_job_count == 0)
    stop(service)


def test_executor_submit_failure_rolls_back_key_and_capacity():
    provider = SequenceProvider([success()])
    writer = MemoryWriter()
    telemetry = FakeSystemTelemetry()
    executor = FailingExecutor()
    service = AuthorizedClientSnapshotCollector(
        config=config(max_workers=1, max_pending=0),
        provider=provider,
        writer=writer,
        telemetry=VisitorSnapshotTelemetry(
            telemetry_provider=lambda: telemetry
        ),
        executor_factory=lambda **kwargs: executor,
    )
    assert service.start()
    assert service.submit(request()) is SnapshotSubmitOutcome.UNAVAILABLE
    assert service.active_job_count == 0
    assert service.state == "unavailable"
    assert provider.calls == []
    service.drain_and_stop(0)


def test_future_exception_releases_active_key_and_capacity():
    provider = SequenceProvider([success()])
    writer = MemoryWriter()
    telemetry = FakeSystemTelemetry()
    executor = ManualExecutor()
    service = AuthorizedClientSnapshotCollector(
        config=config(max_workers=1, max_pending=0),
        provider=provider,
        writer=writer,
        telemetry=VisitorSnapshotTelemetry(
            telemetry_provider=lambda: telemetry
        ),
        executor_factory=lambda **kwargs: executor,
        utcnow=lambda: NOW,
    )
    assert service.start()
    first = request()
    assert service.submit(first) is SnapshotSubmitOutcome.ACCEPTED
    executor.fail_next(RuntimeError("worker failed"))
    wait_for(lambda: service.active_job_count == 0)
    assert writer.records[0]["error_category"] == "internal_error"
    assert service.submit(first) is SnapshotSubmitOutcome.ACCEPTED
    executor.run_next()
    wait_for(lambda: len(writer.records) == 2)
    stop(service)


@pytest.mark.parametrize(
    "invalid_request",
    [
        request(auth_session_id=""),
        request(site_id=""),
        request(requested_mac="bad"),
        request(authorized_at=NOW.replace(tzinfo=None)),
        request(
            auth_context=AuthorizedClientAuthContext(
                client_ip=None,
                portal_ssid=None,
                portal_ap_mac=None,
                portal_radio_id=None,
                auth_run_number=0,
                authorization_attempt=0,
                auth_final_reason="AUTHORIZED",
                retry_request_id=None,
            )
        ),
        request(
            auth_context=AuthorizedClientAuthContext(
                client_ip=None,
                portal_ssid=None,
                portal_ap_mac=None,
                portal_radio_id=None,
                auth_run_number=1,
                authorization_attempt=-1,
                auth_final_reason="AUTHORIZED",
                retry_request_id=None,
            )
        ),
        request(
            auth_context=AuthorizedClientAuthContext(
                client_ip=None,
                portal_ssid=None,
                portal_ap_mac=None,
                portal_radio_id=None,
                auth_run_number=1,
                authorization_attempt=0,
                auth_final_reason="",
                retry_request_id=None,
            )
        ),
    ],
)
def test_invalid_context_is_rejected_without_data_event(
    invalid_request,
):
    provider = SequenceProvider([success()])
    service, writer, telemetry = collector(provider)
    assert service.submit(invalid_request) is (
        SnapshotSubmitOutcome.INVALID_CONTEXT
    )
    assert provider.calls == []
    assert writer.records == []
    assert any(
        item["event"] == "visitor_snapshot_invalid_context"
        for item in telemetry.events
    )
    stop(service)


def test_optional_context_is_normalized_without_rejecting_job():
    context = AuthorizedClientAuthContext(
        client_ip="bad",
        portal_ssid=123,
        portal_ap_mac="bad",
        portal_radio_id=1,
        auth_run_number=1,
        authorization_attempt=0,
        auth_final_reason="ALREADY_AUTHORIZED",
        retry_request_id=None,
    )
    provider = SequenceProvider([success()])
    service, writer, _ = collector(provider)
    assert service.submit(request(auth_context=context)) is (
        SnapshotSubmitOutcome.ACCEPTED
    )
    wait_for(lambda: len(writer.records) == 1)
    actual = writer.records[0]["auth_context"]
    assert actual["client_ip"] is None
    assert actual["portal_ssid"] is None
    assert actual["portal_ap_mac"] is None
    assert actual["portal_radio_id"] is None
    assert actual["authorization_attempt"] == 0
    stop(service)


def test_shutdown_interrupts_retry_sleep_and_writes_failed():
    provider = SequenceProvider([
        failure("timeout", retryable=True)
    ])
    service, writer, telemetry = collector(
        provider,
        retry_delays_seconds=(10.0, 10.0),
    )
    assert service.submit(request()) is SnapshotSubmitOutcome.ACCEPTED
    wait_for(lambda: len(provider.calls) == 1)
    service.stop_accepting()
    service.drain_and_stop(0.1)
    wait_for(lambda: len(writer.records) == 1)
    assert writer.records[0]["error_category"] == (
        "shutdown_cancelled"
    )
    assert len(provider.calls) == 1
    assert any(
        item["event"] == "visitor_snapshot_shutdown_cancelled"
        for item in telemetry.events
    )
    assert sum(
        item["event"] == "visitor_snapshot_drain_timeout"
        for item in telemetry.events
    ) == 1


def test_drain_timeout_event_precedes_cancel_and_is_not_duplicated():
    order = []

    class OrderedTelemetry(FakeSystemTelemetry):
        def safe_emit_system(self, event, level="info", **fields):
            order.append(event)
            return super().safe_emit_system(event, level, **fields)

    provider = SequenceProvider([success()])
    writer = MemoryWriter()
    telemetry = OrderedTelemetry()
    executor = ManualExecutor()
    service = AuthorizedClientSnapshotCollector(
        config=config(),
        provider=provider,
        writer=writer,
        telemetry=VisitorSnapshotTelemetry(
            telemetry_provider=lambda: telemetry
        ),
        executor_factory=lambda **kwargs: executor,
        utcnow=lambda: NOW,
    )
    assert service.start()
    assert service.submit(request()) is SnapshotSubmitOutcome.ACCEPTED
    future = executor.submissions[0][0]
    original_cancel = future.cancel

    def recording_cancel():
        order.append("future.cancel")
        return original_cancel()

    future.cancel = recording_cancel
    service.drain_and_stop(0)
    service.drain_and_stop(0)

    timeout_events = [
        item
        for item in telemetry.events
        if item["event"] == "visitor_snapshot_drain_timeout"
    ]
    assert timeout_events == [{
        "event": "visitor_snapshot_drain_timeout",
        "level": "warning",
        "component": "visitor_snapshot",
        "timeout_seconds": 0.0,
        "unfinished_job_count": 1,
    }]
    assert order.index("visitor_snapshot_drain_timeout") < (
        order.index("future.cancel")
    )


def test_stop_accepting_still_drains_an_already_accepted_job():
    provider = SequenceProvider([success()])
    writer = MemoryWriter()
    telemetry = FakeSystemTelemetry()
    executor = ManualExecutor()
    service = AuthorizedClientSnapshotCollector(
        config=config(),
        provider=provider,
        writer=writer,
        telemetry=VisitorSnapshotTelemetry(
            telemetry_provider=lambda: telemetry
        ),
        executor_factory=lambda **kwargs: executor,
        utcnow=lambda: NOW,
    )
    assert service.start()
    assert service.submit(request()) is SnapshotSubmitOutcome.ACCEPTED
    service.stop_accepting()
    assert service.submit(request(
        auth_session_id="too-late",
    )) is SnapshotSubmitOutcome.SHUTTING_DOWN
    executor.run_next()
    wait_for(lambda: len(writer.records) == 1)
    assert writer.records[0]["event"].endswith("captured")
    service.drain_and_stop(1)
    service.drain_and_stop(1)
    assert writer.closed == 1
    assert sum(
        item["event"] == "visitor_snapshot_collector_stopped"
        for item in telemetry.events
    ) == 1
    assert not any(
        item["event"] == "visitor_snapshot_drain_timeout"
        for item in telemetry.events
    )


def test_writer_failure_makes_collector_unavailable_fail_open():
    writer = MemoryWriter(fail_write=True)
    provider = SequenceProvider([success()])
    service, _, telemetry = collector(provider, writer=writer)
    assert service.submit(request()) is SnapshotSubmitOutcome.ACCEPTED
    wait_for(lambda: service.state == "unavailable")
    assert service.submit(
        request(auth_session_id="next")
    ) is SnapshotSubmitOutcome.UNAVAILABLE
    assert any(
        item["event"] == "visitor_snapshot_write_failed"
        for item in telemetry.events
    )
    wait_for(lambda: service.active_job_count == 0)
    service.drain_and_stop(2)


def test_writer_initialization_failure_never_creates_executor_or_get():
    writer = MemoryWriter(initialize_result=False)
    provider = SequenceProvider([success()])
    system_telemetry = FakeSystemTelemetry()
    service = AuthorizedClientSnapshotCollector(
        config=config(),
        provider=provider,
        writer=writer,
        telemetry=VisitorSnapshotTelemetry(
            telemetry_provider=lambda: system_telemetry
        ),
    )
    assert not service.start()
    assert service.state == "unavailable"
    assert service.submit(request()) is SnapshotSubmitOutcome.UNAVAILABLE
    assert provider.calls == []


def test_executor_start_failure_closes_writer_and_is_fail_open():
    writer = MemoryWriter()
    provider = SequenceProvider([success()])
    telemetry = FakeSystemTelemetry()
    service = AuthorizedClientSnapshotCollector(
        config=config(),
        provider=provider,
        writer=writer,
        telemetry=VisitorSnapshotTelemetry(
            telemetry_provider=lambda: telemetry
        ),
        executor_factory=lambda **kwargs: FailingExecutor(
            fail_on_start=True
        ),
    )
    assert not service.start()
    assert service.state == "unavailable"
    assert writer.closed == 1
    assert service.submit(request()) is SnapshotSubmitOutcome.UNAVAILABLE
    assert provider.calls == []


def test_disabled_and_unavailable_implementations_have_no_threads():
    system_telemetry = FakeSystemTelemetry()
    telemetry = VisitorSnapshotTelemetry(
        telemetry_provider=lambda: system_telemetry
    )
    disabled = DisabledVisitorSnapshotCollector(telemetry)
    assert disabled.start() is False
    assert disabled.start() is False
    assert disabled.submit(request()) is SnapshotSubmitOutcome.DISABLED
    assert sum(
        event["event"] == "visitor_snapshot_collector_disabled"
        for event in system_telemetry.events
    ) == 1

    unavailable = UnavailableVisitorSnapshotCollector(
        telemetry=telemetry,
        stage="test",
    )
    assert unavailable.start() is False
    assert unavailable.submit(request()) is (
        SnapshotSubmitOutcome.UNAVAILABLE
    )


def test_invalid_factory_config_is_fail_open():
    provider = SequenceProvider([success()])
    service = create_visitor_snapshot_collector(
        settings={
            "visitor_snapshot_enabled": "true",
            "visitor_snapshot_max_workers": "0",
        },
        provider=provider,
        telemetry_service=FakeSystemTelemetry(),
    )
    assert isinstance(service, UnavailableVisitorSnapshotCollector)
    assert service.submit(request()) is SnapshotSubmitOutcome.UNAVAILABLE


def test_telemetry_failure_does_not_break_capture():
    provider = SequenceProvider([success()])
    writer = MemoryWriter()
    telemetry = FakeSystemTelemetry(raises=True)
    service, _, _ = collector(
        provider,
        writer=writer,
        telemetry=telemetry,
    )
    assert service.submit(request()) is SnapshotSubmitOutcome.ACCEPTED
    wait_for(lambda: len(writer.records) == 1)
    assert writer.records[0]["event"].endswith("captured")
    stop(service)
