"""QIO-01A: invocation-local ownership and positive-only health cadence."""

import inspect
import json
import logging
import threading
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import app.device_fingerprint_integration.worker as module
from app.device_fingerprint_integration.models import IdentityResolution, IntegrationError, plus
from app.device_fingerprint_integration.worker import IntegrationWorker, consumer_lock
from .test_repository_identity import A, DEVICE, SNAPSHOT, VISIT, job, repository

HEALTH = "fingerprint.integration_worker_health"
OWNED_IDLE = (False, True)
LOCK_MISSED = (False, False)
RESULT_REF = "ClassificationResult:v1:sha256:" + "a" * 64


class LoopEvent:
    """One bounded iteration per supplied time; no sleeps or real-time cadence."""

    def __init__(self, count, after_wait=None):
        self.count, self.index = count, 0
        self.stopped = False
        self.waits = []
        self.after_wait = after_wait

    def is_set(self):
        return self.stopped

    def set(self):
        self.stopped = True

    def wait(self, seconds):
        self.waits.append(seconds)
        assert seconds == 1
        self.index += 1
        if self.after_wait is not None:
            self.after_wait(self.index)
        if self.index >= self.count:
            self.set()
        return self.stopped


@pytest.fixture
def events(monkeypatch):
    captured = []
    monkeypatch.setattr(module, "emit", lambda event, **fields: captured.append({"event": event, **fields}))
    return captured


def idle_worker(tmp_path):
    repo = SimpleNamespace(path=tmp_path / "integration.sqlite", claim=Mock(return_value=None),
                           identity_due=Mock(return_value=None))
    return IntegrationWorker(repo, None, None, clock=lambda: A)


def drive(worker, times, monkeypatch, outcomes=None):
    event = LoopEvent(len(times))
    worker.stop_event = event
    monkeypatch.setattr(module, "time", SimpleNamespace(monotonic=lambda: times[event.index]))
    if outcomes is not None:
        assert len(times) == len(outcomes)

        def cycle():
            outcome = outcomes[event.index]
            if isinstance(outcome, BaseException):
                raise outcome
            return outcome

        monkeypatch.setattr(worker, "_run_cycle", cycle)
    worker.run()
    assert event.waits == [1] * len(times)
    return event


def health(reason):
    return {"event": HEALTH, "reason_code": reason}


@pytest.mark.parametrize("times,ready_indices", [
    (list(range(122)), [0, 60, 120]),
    ([0, 59.999, 60, 60.001, 119.999, 120], [0, 2, 5]),
    ([0, 3600, 3600.001, 3660], [0, 1, 3]),
    ([100, 99, 0, 159.999, 160], [0, 4]),
    ([0, 60, 59.999, -100, 119.999, 120], [0, 1, 5]),
    ([0], [0]),
])
def test_owned_idle_monotonic_heartbeat_boundaries(tmp_path, monkeypatch, events, times, ready_indices):
    worker = idle_worker(tmp_path)
    observed = []
    original = worker._run_cycle

    def owned_cycle():
        observed.append((len(events), times[len(observed)]))
        return original()

    monkeypatch.setattr(worker, "_run_cycle", owned_cycle)
    drive(worker, times, monkeypatch)
    emitted_at = [index for index, (before, _) in enumerate(observed)
                  if (observed[index + 1][0] if index + 1 < len(observed) else len(events)) > before]
    assert emitted_at == ready_indices
    assert events == [health("ready")] * len(ready_indices)
    assert module.READY_HEARTBEAT_MAX_INTERVAL_SECONDS == 60
    assert worker.repository.claim.call_count == len(times)
    assert worker.repository.identity_due.call_count == len(times)


@pytest.mark.parametrize("outcomes,reasons", [
    ([LOCK_MISSED, OWNED_IDLE, OWNED_IDLE], ["consumer_lock_unavailable", "ready"]),
    ([OWNED_IDLE, LOCK_MISSED, LOCK_MISSED, OWNED_IDLE, OWNED_IDLE],
     ["ready", "consumer_lock_unavailable", "consumer_lock_unavailable", "ready"]),
    ([RuntimeError("first"), RuntimeError("first"), ValueError("different"), OWNED_IDLE],
     ["integration_unavailable", "integration_unavailable", "integration_unavailable", "ready"]),
    ([OWNED_IDLE, RuntimeError("failure"), RuntimeError("failure"), OWNED_IDLE, OWNED_IDLE],
     ["ready", "integration_unavailable", "integration_unavailable", "ready"]),
    ([LOCK_MISSED, RuntimeError("failure"), LOCK_MISSED, OWNED_IDLE],
     ["consumer_lock_unavailable", "integration_unavailable", "consumer_lock_unavailable", "ready"]),
])
def test_each_non_ready_iteration_and_recovery_is_immediate(tmp_path, monkeypatch, events, outcomes, reasons):
    drive(idle_worker(tmp_path), list(range(len(outcomes))), monkeypatch, outcomes)
    assert events == [health(reason) for reason in reasons]


@pytest.mark.parametrize("failure", [LOCK_MISSED, RuntimeError("unavailable")])
def test_recovery_resets_heartbeat_deadline(tmp_path, monkeypatch, events, failure):
    drive(idle_worker(tmp_path), [0, 1, 2, 61.999, 62, 62.001], monkeypatch,
          [OWNED_IDLE, failure, OWNED_IDLE, OWNED_IDLE, OWNED_IDLE, OWNED_IDLE])
    reason = "consumer_lock_unavailable" if failure == LOCK_MISSED else "integration_unavailable"
    assert events == [health("ready"), health(reason), health("ready"), health("ready")]


def test_new_worker_does_not_inherit_another_workers_deadline(tmp_path, monkeypatch, events):
    drive(idle_worker(tmp_path), [1000, 1001], monkeypatch)
    drive(idle_worker(tmp_path), [1002, 1003], monkeypatch)
    assert events == [health("ready"), health("ready")]


def test_success_is_observed_after_bounded_cycle_not_during_long_job(tmp_path, monkeypatch, events):
    worker = idle_worker(tmp_path)
    clock = {"now": 0}
    event = LoopEvent(1)
    worker.stop_event = event

    def cycle():
        assert events == []
        clock["now"] = 3600
        assert events == []
        return OWNED_IDLE

    reads = []

    def monotonic():
        reads.append(clock["now"])
        return clock["now"]

    monkeypatch.setattr(worker, "_run_cycle", cycle)
    monkeypatch.setattr(module, "time", SimpleNamespace(monotonic=monotonic))
    worker.run()
    assert reads == [3600]
    assert events == [health("ready")]
    assert event.waits == [1]


def test_utc_domain_clock_changes_do_not_schedule_heartbeat(tmp_path, monkeypatch, events):
    worker = idle_worker(tmp_path)
    worker.clock = Mock(side_effect=[plus(A, offset) for offset in (0, 1, 86400, -86400, 2, 3, 4, 5)])
    drive(worker, [0, 1, 59.999, 60], monkeypatch)
    assert worker.clock.call_count == 8
    assert events == [health("ready"), health("ready")]


@pytest.mark.parametrize("activity_stub", [False, True])
def test_public_bool_stub_cannot_invent_lock_ownership(tmp_path, monkeypatch, events, activity_stub):
    worker = idle_worker(tmp_path)
    stub = Mock(return_value=activity_stub)
    monkeypatch.setattr(worker, "run_once", stub)
    with consumer_lock(worker.repository.path) as acquired:
        assert acquired
        drive(worker, [0, 1], monkeypatch)
    assert events == [health("consumer_lock_unavailable")] * 2
    stub.assert_not_called()
    worker.repository.claim.assert_not_called()
    worker.repository.identity_due.assert_not_called()


def test_direct_owned_success_cannot_leave_stale_ready_for_loop_lock_misses(tmp_path, monkeypatch, events):
    worker = idle_worker(tmp_path)
    assert worker.run_once() is False  # Real owned idle, not a failed cycle.
    assert events == []
    with consumer_lock(worker.repository.path) as acquired:
        assert acquired  # Another legal consumer owns the lock during both loop cycles.
        drive(worker, [0, 1], monkeypatch)
    assert events == [health("consumer_lock_unavailable")] * 2


def test_concurrent_direct_lock_miss_cannot_poison_loop_owned_completion(tmp_path, monkeypatch, events):
    worker = idle_worker(tmp_path)
    entered, release = threading.Event(), threading.Event()
    failures = []

    def claim(_now):
        entered.set()
        assert release.wait(5), "test synchronization timed out"
        return None

    worker.repository.claim.side_effect = claim
    worker.stop_event = LoopEvent(1)
    monkeypatch.setattr(module, "time", SimpleNamespace(monotonic=lambda: 0))

    def run():
        try:
            worker.run()
        except BaseException as exc:
            failures.append(exc)

    thread = threading.Thread(target=run)
    thread.start()
    try:
        assert entered.wait(5), "worker did not reach the owned claim"
        assert worker.run_once() is False  # Concurrent direct invocation misses this worker's lock.
        assert events == []
    finally:
        release.set()
        thread.join(5)
    assert not thread.is_alive() and failures == []
    assert events == [health("ready")]
    assert worker.repository.claim.call_count == 1


def test_initial_stop_produces_no_cycle_or_synthetic_event(tmp_path, monkeypatch, events):
    worker = idle_worker(tmp_path)
    cycle = Mock(side_effect=AssertionError("stopped worker must not execute"))
    monkeypatch.setattr(worker, "_run_cycle", cycle)
    worker.stop()
    worker.run()
    cycle.assert_not_called()
    assert events == []


@pytest.mark.parametrize("crash", [KeyboardInterrupt(), SystemExit()])
@pytest.mark.parametrize("prior_success", [False, True])
def test_crash_does_not_fabricate_ready_or_shutdown_failure(tmp_path, monkeypatch, events, crash, prior_success):
    outcomes = [OWNED_IDLE, crash] if prior_success else [crash]
    with pytest.raises(type(crash)):
        drive(idle_worker(tmp_path), list(range(len(outcomes))), monkeypatch, outcomes)
    assert events == ([health("ready")] if prior_success else [])


def test_public_signature_activity_and_unhandled_exception_remain_unchanged(tmp_path, events):
    assert list(inspect.signature(IntegrationWorker.__init__).parameters) == [
        "self", "repository", "executor", "identity_resolver", "clock"]
    assert inspect.signature(IntegrationWorker.__init__).parameters["clock"].kind is inspect.Parameter.KEYWORD_ONLY
    assert list(inspect.signature(IntegrationWorker.run_once).parameters) == ["self"]
    worker = idle_worker(tmp_path)
    assert worker.run_once() is False
    with consumer_lock(worker.repository.path) as acquired:
        assert acquired
        assert worker.run_once() is False
    worker.repository.claim.side_effect = IntegrationError("integration_unavailable")
    with pytest.raises(IntegrationError, match="integration_unavailable"):
        worker.run_once()
    assert events == []


@pytest.mark.parametrize("outcome", ["success", "retry", "no_result", "lease_lost", "finish_failure"])
def test_real_durable_classification_outcomes_and_event_order(tmp_path, monkeypatch, events, outcome):
    repo = repository(tmp_path)
    pending = job(repo)
    now = [plus(A, 150)]
    core = SimpleNamespace(classification_id=pending.planned_classification_id,
                           classification_result_id=RESULT_REF)

    def execute(claimed, *, recovery_only):
        assert claimed.integration_id == pending.integration_id and not recovery_only
        if outcome == "lease_lost":
            now[0] = plus(A, 450)
        if outcome in {"retry", "no_result", "lease_lost"}:
            raise IntegrationError("snapshot_timeout" if outcome == "retry" else "binding_unavailable")
        return core, plus(A, -300), plus(A, 120)

    resolver = Mock()
    resolver.resolve.return_value = IdentityResolution()
    worker = IntegrationWorker(repo, SimpleNamespace(execute=execute), resolver, clock=lambda: now[0])
    if outcome == "finish_failure":
        monkeypatch.setattr(repo, "finish", Mock(side_effect=IntegrationError("persistence_unavailable")))
    drive(worker, [0], monkeypatch)
    stored = repo.get(pending.integration_id)
    started = {"event": "fingerprint.integration_classification_started",
               "integration_id": pending.integration_id, "attempt_count": 1}
    if outcome == "success":
        assert stored.classification_state == "CLASSIFIED"
        assert stored.classification_id == pending.planned_classification_id
        assert (stored.effective_window_start_utc, stored.effective_window_end_utc) == (plus(A, -300), plus(A, 120))
        domain = {"event": "fingerprint.integration_classification_succeeded",
                  "integration_id": pending.integration_id, "classification_id": pending.planned_classification_id}
    elif outcome in {"retry", "no_result"}:
        retry = outcome == "retry"
        assert stored.classification_state == ("PENDING" if retry else "NO_RESULT_FINAL")
        assert stored.last_reason_code == ("snapshot_timeout" if retry else "binding_unavailable")
        assert stored.next_attempt_at_utc == plus(A, 180 if retry else 150)
        domain = {"event": "fingerprint.integration_classification_retry" if retry else "fingerprint.integration_classification_no_result",
                  "integration_id": pending.integration_id, "reason_code": stored.last_reason_code, "attempt_count": 1}
    elif outcome == "lease_lost":
        assert stored.classification_state == "LEASED" and stored.lease_until_utc == plus(A, 450)
        domain = {"event": HEALTH, "integration_id": pending.integration_id, "reason_code": "lease_lost"}
    else:
        assert stored.classification_state == "LEASED"
        assert events == [started, health("integration_unavailable")]
        return
    assert stored.attempt_count == 1
    assert events == [started, domain, health("ready")]


@pytest.mark.parametrize("state,reason", [
    ("UNRESOLVED", None), ("DEVICE_RESOLVED", None),
    ("DEVICE_AND_VISIT_RESOLVED", None), ("CONFLICT", "identity_device_conflict"),
    ("UNRESOLVED", "resolver_exception"),
])
def test_identity_only_activity_resolution_conflict_and_failure_preserved(tmp_path, monkeypatch, events, state, reason):
    repo = repository(tmp_path)
    pending = job(repo)
    resolution = IdentityResolution(state, reason, SNAPSHOT if state != "UNRESOLVED" else None,
                                    DEVICE if state != "UNRESOLVED" else None,
                                    VISIT if state == "DEVICE_AND_VISIT_RESOLVED" else None)
    resolver = Mock()
    resolver.resolve.return_value = resolution
    if reason == "resolver_exception":
        resolver.resolve.side_effect = RuntimeError("disposable failure")
    executor = Mock()
    worker = IntegrationWorker(repo, executor, resolver, clock=lambda: A)
    assert worker.run_once() is True  # Identity due, classification not due yet.
    stored = repo.get(pending.integration_id)
    assert stored.classification_state == "PENDING" and stored.attempt_count == 0
    assert stored.identity_state == state
    assert stored.identity_last_attempt_at_utc == A
    assert repo.identity_due(plus(A, 29)) is None
    assert (repo.identity_due(plus(A, 30)) is not None) == (state in {"UNRESOLVED", "DEVICE_RESOLVED"})
    if state == "UNRESOLVED":
        assert events == []
        assert stored.identity_reason == ("identity_proof_unavailable" if reason else None)
    else:
        assert events == [{"event": "fingerprint.integration_identity_conflict" if state == "CONFLICT"
                           else "fingerprint.integration_identity_resolved",
                           "integration_id": pending.integration_id, "device_id": resolution.device_id,
                           "visit_id": resolution.visit_id, "reason_code": reason}]
    drive(worker, [0], monkeypatch)
    assert events[-1] == health("ready")
    executor.execute.assert_not_called()
    resolver.resolve.assert_called_once()


def test_identity_expiry_does_not_change_hour_limit_or_force_resolver(tmp_path, monkeypatch, events):
    repo = repository(tmp_path)
    pending = job(repo)
    leased, _ = repo.claim(plus(A, 150))
    assert repo.finish(leased, plus(A, 150), state="NO_RESULT_FINAL")
    resolver = Mock()
    worker = IntegrationWorker(repo, None, resolver, clock=lambda: plus(A, 3600))
    drive(worker, [0], monkeypatch)
    stored = repo.get(pending.integration_id)
    assert stored.identity_state == "UNRESOLVED" and stored.identity_reason == "identity_proof_unavailable"
    assert stored.identity_last_attempt_at_utc == plus(A, 3600)
    assert repo.identity_due(plus(A, 3630)) is None
    resolver.resolve.assert_not_called()
    assert events == [health("ready")]


def test_job_and_identity_event_sequence_precedes_loop_ready(tmp_path, monkeypatch, events):
    repo = repository(tmp_path)
    pending = job(repo)
    core = SimpleNamespace(classification_id=pending.planned_classification_id, classification_result_id=RESULT_REF)
    executor = Mock()
    executor.execute.return_value = (core, plus(A, -300), plus(A, 120))
    resolver = Mock()
    resolver.resolve.return_value = IdentityResolution("DEVICE_AND_VISIT_RESOLVED", None, SNAPSHOT, DEVICE, VISIT)
    worker = IntegrationWorker(repo, executor, resolver, clock=lambda: plus(A, 150))
    drive(worker, [0, 1], monkeypatch)
    assert [event["event"] for event in events] == [
        "fingerprint.integration_classification_started", "fingerprint.integration_classification_succeeded",
        "fingerprint.integration_identity_resolved", HEALTH]
    assert events[2] == {"event": "fingerprint.integration_identity_resolved", "integration_id": pending.integration_id,
                         "device_id": DEVICE, "visit_id": VISIT, "reason_code": None}
    assert events[-1] == health("ready")
    executor.execute.assert_called_once()
    resolver.resolve.assert_called_once()


def test_idle_heartbeat_adds_no_durable_health_state_or_database_changes(tmp_path, monkeypatch, events):
    repo = repository(tmp_path)
    before = repo.path.read_bytes()
    with repo.connection(readonly=True) as conn:
        schema = conn.execute("SELECT sql FROM sqlite_master ORDER BY name").fetchall()
    worker = IntegrationWorker(repo, None, None, clock=lambda: A)
    drive(worker, list(range(121)), monkeypatch)
    assert repo.path.read_bytes() == before
    assert {path.name for path in tmp_path.iterdir()} == {repo.path.name, repo.path.name + ".consumer.lock"}
    with repo.connection(readonly=True) as conn:
        assert [tuple(row) for row in conn.execute("SELECT sql FROM sqlite_master ORDER BY name")] == [tuple(row) for row in schema]
        assert conn.execute("SELECT count(*) FROM integration_jobs").fetchone()[0] == 0
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 1
    assert events == [health("ready")] * 3


def test_real_emitter_loop_json_stays_minimal_and_does_not_leak_exception(tmp_path, monkeypatch, caplog):
    worker = idle_worker(tmp_path)
    with caplog.at_level(logging.INFO, logger="captivportal.fingerprint.integration"):
        drive(worker, [0, 1, 2, 3], monkeypatch,
              [OWNED_IDLE, LOCK_MISSED, RuntimeError("must-not-appear-in-json"), OWNED_IDLE])
    records = [json.loads(record.getMessage()) for record in caplog.records
               if record.name == "captivportal.fingerprint.integration"]
    assert records == [health(reason) for reason in (
        "ready", "consumer_lock_unavailable", "integration_unavailable", "ready")]
    assert all(set(record) == {"event", "reason_code"} for record in records)
