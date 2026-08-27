from __future__ import annotations

import threading
import time
from contextlib import contextmanager

import pytest

from app.visit_lifecycle import (
    VisitStorageCategory,
    VisitStorageError,
    VisitWriterContention,
)
from app.visit_lifecycle.models import (
    OfflineEvidence,
    ReaderCheckpoint,
    ReaderProgress,
)
from app.visit_lifecycle.repository import (
    BACKGROUND_CHUNK_MAX_ITEMS,
    PriorityWriteCoordinator,
    WRITE_OPERATION_PENDING_RETRY,
    WRITE_OPERATION_READER_LINE,
    WRITE_OPERATION_RECONCILIATION,
    WRITE_OPERATION_START,
    WRITE_OPERATION_STARTUP,
)

from .conftest import make_request


NOW = "2026-08-13T10:06:00.000Z"


class FakeClock:
    def __init__(self):
        self.value = 0.0

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value += seconds


def _wait_for(predicate, timeout=1.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.002)
    return predicate()


def test_starvation_credit_survives_timeout_and_one_escape_requires_start():
    clock = FakeClock()
    coordinator = PriorityWriteCoordinator(monotonic=clock)

    with coordinator.acquire(WRITE_OPERATION_START, timeout_ms=1_000):
        with pytest.raises(VisitStorageError) as deferred:
            with coordinator.acquire(
                WRITE_OPERATION_PENDING_RETRY,
                timeout_ms=0,
            ):
                raise AssertionError("background unexpectedly acquired")
    assert deferred.value.contention_layer == "coordinator"

    clock.advance(0.250)
    order = []
    release_holder = threading.Event()
    release_escape = threading.Event()

    def waiting(operation, name, release=None):
        with coordinator.acquire(operation, timeout_ms=5_000) as lease:
            order.append(name)
            if release is not None:
                release.wait(1)
            lease.mark_progress()

    def holder():
        with coordinator.acquire(WRITE_OPERATION_STARTUP, timeout_ms=1_000):
            release_holder.wait(1)

    holder_thread = threading.Thread(target=holder)
    holder_thread.start()
    assert _wait_for(lambda: coordinator.snapshot().holder_operation == "startup")
    start = threading.Thread(
        target=waiting,
        args=(WRITE_OPERATION_START, "start"),
    )
    escaped = threading.Thread(
        target=waiting,
        args=(WRITE_OPERATION_PENDING_RETRY, "escaped", release_escape),
    )
    second = threading.Thread(
        target=waiting,
        args=(WRITE_OPERATION_RECONCILIATION, "second"),
    )
    start.start()
    escaped.start()
    second.start()
    assert _wait_for(lambda: coordinator._waiting_counts() == (1, 2))  # noqa: SLF001
    release_holder.set()
    assert _wait_for(lambda: order == ["escaped"])
    release_escape.set()
    for thread in (holder_thread, start, escaped, second):
        thread.join(2)
        assert not thread.is_alive()
    assert order == ["escaped", "start", "second"]


def test_background_holder_does_not_create_starvation_escape_before_start():
    clock = FakeClock()
    coordinator = PriorityWriteCoordinator(monotonic=clock)
    release_holder = threading.Event()
    order = []

    def holder():
        with coordinator.acquire(
            WRITE_OPERATION_PENDING_RETRY,
            timeout_ms=1_000,
        ) as lease:
            release_holder.wait(1)
            lease.mark_progress()

    def waiter(operation, label):
        with coordinator.acquire(operation, timeout_ms=5_000) as lease:
            order.append(label)
            lease.mark_progress()

    holder_thread = threading.Thread(target=holder)
    start_thread = threading.Thread(
        target=waiter,
        args=(WRITE_OPERATION_START, "start"),
    )
    reconciliation_thread = threading.Thread(
        target=waiter,
        args=(WRITE_OPERATION_RECONCILIATION, "reconciliation"),
    )
    holder_thread.start()
    assert _wait_for(
        lambda: coordinator.snapshot().holder_operation == "pending_retry"
    )
    start_thread.start()
    reconciliation_thread.start()
    assert _wait_for(lambda: coordinator._waiting_counts() == (1, 1))  # noqa: SLF001
    clock.advance(0.250)
    coordinator.wake_all()
    assert "reconciliation" not in coordinator._starvation_since  # noqa: SLF001
    release_holder.set()
    for thread in (holder_thread, start_thread, reconciliation_thread):
        thread.join(2)
        assert not thread.is_alive()
    assert order == ["start", "reconciliation"]


def test_background_fifo_and_snapshot_expose_safe_holder_context():
    coordinator = PriorityWriteCoordinator()
    release = threading.Event()
    order = []

    def holder():
        with coordinator.acquire(WRITE_OPERATION_READER_LINE, timeout_ms=500):
            release.wait(1)

    thread = threading.Thread(target=holder)
    thread.start()
    assert _wait_for(
        lambda: coordinator.snapshot().holder_operation == "reader_line"
    )
    snapshot = coordinator.snapshot(
        waiter_operation=WRITE_OPERATION_START,
        waiter_started=time.monotonic() - 0.010,
    )
    assert snapshot.holder_operation == "reader_line"
    assert snapshot.holder_age_ms is not None
    assert snapshot.waiter_operation == "start"
    assert snapshot.waiter_wait_ms >= 0

    def waiter(operation, label):
        with coordinator.acquire(operation, timeout_ms=1_000):
            order.append(label)

    first = threading.Thread(
        target=waiter,
        args=(WRITE_OPERATION_PENDING_RETRY, "pending"),
    )
    second = threading.Thread(
        target=waiter,
        args=(WRITE_OPERATION_RECONCILIATION, "reconciliation"),
    )
    first.start()
    assert _wait_for(lambda: coordinator._waiting_counts()[1] == 1)  # noqa: SLF001
    second.start()
    assert _wait_for(lambda: coordinator._waiting_counts()[1] == 2)  # noqa: SLF001
    release.set()
    for candidate in (thread, first, second):
        candidate.join(2)
    assert order == ["pending", "reconciliation"]


def test_fairness_latch_clears_when_foreground_waiter_cancels():
    clock = FakeClock()
    coordinator = PriorityWriteCoordinator(monotonic=clock)
    with coordinator.acquire(WRITE_OPERATION_START, timeout_ms=100):
        with pytest.raises(VisitStorageError):
            with coordinator.acquire(
                WRITE_OPERATION_PENDING_RETRY,
                timeout_ms=0,
            ):
                pass
    clock.advance(0.250)
    release = threading.Event()
    cancel_start = threading.Event()
    order = []

    def holder():
        with coordinator.acquire(WRITE_OPERATION_STARTUP, timeout_ms=1_000):
            release.wait(1)

    def start():
        with pytest.raises(VisitStorageError):
            with coordinator.acquire(
                WRITE_OPERATION_START,
                timeout_ms=5_000,
                cancel_event=cancel_start,
            ):
                pass

    def background():
        with coordinator.acquire(
            WRITE_OPERATION_PENDING_RETRY,
            timeout_ms=5_000,
        ):
            order.append("background")

    threads = [
        threading.Thread(target=holder),
        threading.Thread(target=start),
        threading.Thread(target=background),
    ]
    threads[0].start()
    assert _wait_for(lambda: coordinator.snapshot().holder_operation == "startup")
    threads[1].start()
    threads[2].start()
    assert _wait_for(lambda: coordinator._waiting_counts() == (1, 1))  # noqa: SLF001
    cancel_start.set()
    coordinator.wake_all()
    release.set()
    for thread in threads:
        thread.join(2)
        assert not thread.is_alive()
    assert order == ["background"]
    assert coordinator._waiting_counts() == (0, 0)  # noqa: SLF001


def test_shutdown_cancels_aged_background_and_foreground_without_deadlock():
    coordinator = PriorityWriteCoordinator()
    release = threading.Event()
    cancel = threading.Event()
    errors = []

    def holder():
        with coordinator.acquire(WRITE_OPERATION_STARTUP, timeout_ms=1_000):
            release.wait(1)

    def waiter(operation):
        try:
            with coordinator.acquire(
                operation,
                timeout_ms=5_000,
                cancel_event=cancel,
            ):
                pass
        except VisitStorageError as exc:
            errors.append(exc.category)

    threads = [threading.Thread(target=holder)]
    threads[0].start()
    assert _wait_for(lambda: coordinator.snapshot().holder_operation == "startup")
    threads.extend([
        threading.Thread(target=waiter, args=(WRITE_OPERATION_START,)),
        threading.Thread(
            target=waiter,
            args=(WRITE_OPERATION_PENDING_RETRY,),
        ),
        threading.Thread(
            target=waiter,
            args=(WRITE_OPERATION_RECONCILIATION,),
        ),
    ])
    for thread in threads[1:]:
        thread.start()
    assert _wait_for(lambda: coordinator._waiting_counts() == (1, 2))  # noqa: SLF001
    cancel.set()
    coordinator.wake_all()
    release.set()
    for thread in threads:
        thread.join(2)
        assert not thread.is_alive()
    assert errors == [
        VisitStorageCategory.UNAVAILABLE,
        VisitStorageCategory.UNAVAILABLE,
        VisitStorageCategory.UNAVAILABLE,
    ]
    assert coordinator._waiting_counts() == (0, 0)  # noqa: SLF001


def _seed_pending(repository, count):
    checkpoint = ReaderCheckpoint(0, 0, "0" * 64)
    for index in range(count):
        event_id = f"pending:{index:04d}"
        progress = ReaderProgress(
            source_identity="fixture",
            source_path="fixture.jsonl",
            source_offset=index + 1,
            last_observed_size=count,
            checkpoint=checkpoint,
            source_offset_start=index,
        )
        outcome = repository.apply_journal_line(
            progress=progress,
            evidence=OfflineEvidence(
                event_id=event_id,
                site_id="site-a",
                client_mac=f"02:00:00:00:{index // 256:02X}:{index % 256:02X}",
                controller_event_at=NOW,
                received_at=NOW,
                client_ip=None,
                ssid=None,
                ap_mac=None,
                reported_connected_seconds=None,
                reported_traffic_total_bytes=None,
            ),
            now_utc=NOW,
            grace_seconds=30,
            max_clock_skew_seconds=120,
            max_duration_drift_seconds=300,
        )
        assert outcome.processing_result == "pending_match"


def test_pending_pass_chunks_and_keyset_reaches_later_still_pending_rows(
    visit_repository,
    visit_service,
    monkeypatch,
):
    count = BACKGROUND_CHUNK_MAX_ITEMS * 2 + 7
    _seed_pending(visit_repository, count)
    coordinator = visit_repository._write_coordinator  # noqa: SLF001
    original_acquire = coordinator.acquire
    grants = []
    grant_order = []
    examined = []
    original_retry = visit_repository._retry_pending_row  # noqa: SLF001

    @contextmanager
    def counted_acquire(operation, **kwargs):
        with original_acquire(operation, **kwargs) as lease:
            if operation == WRITE_OPERATION_PENDING_RETRY:
                grants.append(operation)
            grant_order.append(operation)
            yield lease

    def counted_retry(connection, *, row, **kwargs):
        examined.append(str(row["event_id"]))
        return original_retry(connection, row=row, **kwargs)

    monkeypatch.setattr(coordinator, "acquire", counted_acquire)
    monkeypatch.setattr(visit_repository, "_retry_pending_row", counted_retry)
    chunks = 0

    def after_chunk(_outcomes):
        nonlocal chunks
        chunks += 1
        if chunks == 1:
            outcome = visit_service.submit_authorized(make_request())
            assert outcome.status == "opened"

    outcomes = visit_repository.process_pending_events(
        now_utc=NOW,
        limit=count,
        max_clock_skew_seconds=120,
        max_duration_drift_seconds=300,
        on_committed_chunk=after_chunk,
    )

    assert len(grants) == 3
    assert grant_order[:3] == [
        WRITE_OPERATION_PENDING_RETRY,
        WRITE_OPERATION_START,
        WRITE_OPERATION_PENDING_RETRY,
    ]
    assert len(outcomes) == count
    assert examined == [f"pending:{index:04d}" for index in range(count)]
    assert len(set(examined)) == count
    with visit_repository._connect(readonly=True) as connection:  # noqa: SLF001
        assert connection.execute(
            "SELECT COUNT(*) FROM visit_source_events "
            "WHERE processing_result='pending_match'"
        ).fetchone()[0] == count


def test_pending_deadline_and_cancellation_prevent_new_chunk(
    visit_repository,
    monkeypatch,
):
    _seed_pending(visit_repository, BACKGROUND_CHUNK_MAX_ITEMS + 5)
    coordinator = visit_repository._write_coordinator  # noqa: SLF001
    original_acquire = coordinator.acquire
    grants = 0
    cancel = threading.Event()

    @contextmanager
    def counted_acquire(operation, **kwargs):
        nonlocal grants
        with original_acquire(operation, **kwargs) as lease:
            if operation == WRITE_OPERATION_PENDING_RETRY:
                grants += 1
            yield lease

    monkeypatch.setattr(coordinator, "acquire", counted_acquire)
    visit_repository.process_pending_events(
        now_utc=NOW,
        limit=100,
        max_clock_skew_seconds=120,
        max_duration_drift_seconds=300,
        on_committed_chunk=lambda _outcomes: cancel.set(),
        cancel_event=cancel,
        deadline=time.monotonic() + 5,
    )
    assert grants == 1


def test_pending_shared_deadline_stops_before_reacquisition(
    visit_config,
    monkeypatch,
):
    from app.visit_lifecycle import repository as repository_module
    from app.visit_lifecycle.repository import VisitRepository

    clock = FakeClock()
    coordinator = PriorityWriteCoordinator(monotonic=clock)
    repository = VisitRepository(
        visit_config,
        write_coordinator=coordinator,
    )
    repository.initialize()
    _seed_pending(repository, BACKGROUND_CHUNK_MAX_ITEMS + 5)
    monkeypatch.setattr(repository_module.time, "monotonic", clock)
    grants = 0
    original_acquire = coordinator.acquire

    @contextmanager
    def counted_acquire(operation, **kwargs):
        nonlocal grants
        with original_acquire(operation, **kwargs) as lease:
            if operation == WRITE_OPERATION_PENDING_RETRY:
                grants += 1
            yield lease

    monkeypatch.setattr(coordinator, "acquire", counted_acquire)
    repository.process_pending_events(
        now_utc=NOW,
        limit=100,
        max_clock_skew_seconds=120,
        max_duration_drift_seconds=300,
        deadline=1.0,
        on_committed_chunk=lambda _outcomes: clock.advance(1.1),
    )
    assert grants == 1


def test_pending_deadline_before_first_item_preserves_starvation_credit(
    visit_config,
    monkeypatch,
):
    from app.visit_lifecycle import repository as repository_module
    from app.visit_lifecycle.repository import VisitRepository

    clock = FakeClock()
    coordinator = PriorityWriteCoordinator(monotonic=clock)
    repository = VisitRepository(
        visit_config,
        write_coordinator=coordinator,
    )
    repository.initialize()
    _seed_pending(repository, 1)
    coordinator._starvation_since["pending_retry"] = 0.0  # noqa: SLF001
    clock.advance(0.250)
    monkeypatch.setattr(repository_module.time, "monotonic", clock)
    original_acquire = coordinator.acquire

    @contextmanager
    def expire_after_grant(operation, **kwargs):
        with original_acquire(operation, **kwargs) as lease:
            if operation == WRITE_OPERATION_PENDING_RETRY:
                clock.advance(1.0)
            yield lease

    monkeypatch.setattr(coordinator, "acquire", expire_after_grant)
    outcomes = repository.process_pending_events(
        now_utc=NOW,
        limit=1,
        max_clock_skew_seconds=120,
        max_duration_drift_seconds=300,
        deadline=1.0,
    )

    assert outcomes == ()
    assert coordinator._starvation_since["pending_retry"] == 0.0  # noqa: SLF001


def test_pending_query_proving_no_work_clears_starvation_credit(
    visit_config,
):
    from app.visit_lifecycle.repository import VisitRepository

    clock = FakeClock()
    coordinator = PriorityWriteCoordinator(monotonic=clock)
    repository = VisitRepository(
        visit_config,
        write_coordinator=coordinator,
    )
    repository.initialize()
    coordinator._starvation_since["pending_retry"] = 0.0  # noqa: SLF001
    clock.advance(0.250)

    outcomes = repository.process_pending_events(
        now_utc=NOW,
        limit=1,
        max_clock_skew_seconds=120,
        max_duration_drift_seconds=300,
    )

    assert outcomes == ()
    assert "pending_retry" not in coordinator._starvation_since  # noqa: SLF001


def test_pending_soft_hold_boundary_is_checked_between_atomic_items(
    visit_repository,
    monkeypatch,
):
    from app.visit_lifecycle import repository as repository_module

    _seed_pending(visit_repository, 6)
    clock = FakeClock()
    monkeypatch.setattr(repository_module.time, "monotonic", clock)
    original = visit_repository._retry_pending_row  # noqa: SLF001
    chunk_sizes = []

    def slow_item(*args, **kwargs):
        result = original(*args, **kwargs)
        clock.advance(0.030)
        return result

    monkeypatch.setattr(visit_repository, "_retry_pending_row", slow_item)
    outcomes = visit_repository.process_pending_events(
        now_utc=NOW,
        limit=6,
        max_clock_skew_seconds=120,
        max_duration_drift_seconds=300,
        on_committed_chunk=lambda chunk: chunk_sizes.append(len(chunk)),
    )
    assert len(outcomes) == 6
    assert chunk_sizes == [2, 2, 2]


def test_chunk_failure_preserves_previous_commit(visit_repository, monkeypatch):
    _seed_pending(visit_repository, BACKGROUND_CHUNK_MAX_ITEMS + 1)
    original = visit_repository._retry_pending_row  # noqa: SLF001
    calls = 0

    def fail_second_chunk(connection, *, row, **kwargs):
        nonlocal calls
        calls += 1
        if calls == BACKGROUND_CHUNK_MAX_ITEMS + 1:
            connection.execute("SELECT no_such_column")
        outcome = original(connection, row=row, **kwargs)
        connection.execute(
            "UPDATE visit_source_events SET processed_at=? WHERE event_id=?",
            (f"2026-08-13T10:06:{calls:02d}.000Z", row["event_id"]),
        )
        return outcome

    monkeypatch.setattr(
        visit_repository,
        "_retry_pending_row",
        fail_second_chunk,
    )
    with pytest.raises(VisitStorageError):
        visit_repository.process_pending_events(
            now_utc="2026-08-13T10:07:00.000Z",
            limit=BACKGROUND_CHUNK_MAX_ITEMS + 1,
            max_clock_skew_seconds=120,
            max_duration_drift_seconds=300,
        )
    with visit_repository._connect(readonly=True) as connection:  # noqa: SLF001
        committed = connection.execute(
            "SELECT COUNT(*) FROM visit_source_events "
            "WHERE processed_at != ?",
            (NOW,),
        ).fetchone()[0]
    assert committed == BACKGROUND_CHUNK_MAX_ITEMS

    monkeypatch.setattr(visit_repository, "_retry_pending_row", original)
    resumed = visit_repository.process_pending_events(
        now_utc="2026-08-13T10:07:00.000Z",
        limit=BACKGROUND_CHUNK_MAX_ITEMS + 1,
        max_clock_skew_seconds=120,
        max_duration_drift_seconds=300,
    )
    assert len(resumed) == 1
    with visit_repository._connect(readonly=True) as connection:  # noqa: SLF001
        assert connection.execute(
            "SELECT COUNT(*) FROM visit_source_events "
            "WHERE processing_result='pending_match'"
        ).fetchone()[0] == 0


def test_pending_row_is_revalidated_inside_transaction(
    visit_repository,
    monkeypatch,
):
    _seed_pending(visit_repository, 2)
    original = visit_repository._retry_pending_row  # noqa: SLF001
    examined = []

    def mutate_next(connection, *, row, **kwargs):
        examined.append(str(row["event_id"]))
        if len(examined) == 1:
            connection.execute(
                "UPDATE visit_source_events "
                "SET processing_result='unmatched', pending_until=NULL "
                "WHERE event_id='pending:0001'"
            )
        return original(connection, row=row, **kwargs)

    monkeypatch.setattr(visit_repository, "_retry_pending_row", mutate_next)
    outcomes = visit_repository.process_pending_events(
        now_utc=NOW,
        limit=2,
        max_clock_skew_seconds=120,
        max_duration_drift_seconds=300,
    )
    assert len(outcomes) == 1
    assert examined == ["pending:0000"]


def test_contention_snapshot_can_be_embedded_in_storage_error():
    snapshot = VisitWriterContention(
        holder_operation="pending_retry",
        holder_age_ms=42,
        foreground_queue_depth=1,
        background_queue_depth=2,
        waiter_operation="start",
        waiter_wait_ms=17,
    )
    error = VisitStorageError(
        VisitStorageCategory.BUSY,
        contention_layer="coordinator",
        contention=snapshot,
    )
    assert error.contention == snapshot
