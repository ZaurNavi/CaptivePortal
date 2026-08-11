from __future__ import annotations

import threading

from app.observations.cleanup import ObservationCleanup, ObservationCleanupWorker

from .conftest import client_row, make_config


def cycle(repository, identifier, kind, timestamp, *, state="completed"):
    repository.create_cycle(
        kind=kind,
        site_id="site-a",
        started_at=timestamp,
        cycle_id=identifier,
    )
    if state == "completed":
        repository.finalize_cycle(
            identifier,
            finished_at=timestamp,
            complete=True,
            result="success",
        )


def count(repository, table):
    with repository.read_connection() as connection:
        return connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def test_cleanup_uses_separate_retention_and_preserves_running(repository):
    cycle(repository, "old-client", "client", "2025-01-01T00:00:00.000Z")
    repository.insert_client_batch([
        client_row("old-client", "2025-01-01T00:00:01.000Z")
    ])
    cycle(repository, "new-client", "client", "2026-07-01T00:00:00.000Z")
    cycle(repository, "old-config", "ap_config", "2023-01-01T00:00:00.000Z")
    cycle(repository, "kept-config", "ap_config", "2025-01-01T00:00:00.000Z")
    cycle(
        repository,
        "old-running",
        "client",
        "2025-01-01T00:00:00.000Z",
        state="running",
    )

    result = ObservationCleanup(repository, repository.config).run_once(
        now_utc="2026-08-01T00:00:00.000Z"
    )
    assert result.deleted_dynamic_cycles == 1
    assert result.deleted_config_cycles == 1
    assert result.interrupted is False
    assert count(repository, "client_observations") == 0
    assert repository.get_cycle("new-client") is not None
    assert repository.get_cycle("kept-config") is not None
    assert repository.get_cycle("old-running").state == "running"
    # Cleanup is global maintenance and never creates its own cycle row.
    assert count(repository, "observation_cycles") == 3


def test_cleanup_is_bounded_by_duration(repository, tmp_path):
    for index in range(3):
        cycle(
            repository,
            f"old-{index}",
            "client",
            f"2025-01-0{index + 1}T00:00:00.000Z",
        )
    config = make_config(
        tmp_path,
        db_path=repository.config.db_path,
        cleanup_batch_size=1,
        cleanup_max_duration_seconds=1.0,
    )
    values = iter((0.0, 0.0, 2.0))
    result = ObservationCleanup(repository, config).run_once(
        now_utc="2026-08-01T00:00:00.000Z",
        monotonic=lambda: next(values, 2.0),
    )
    assert result.deleted_dynamic_cycles == 1
    assert result.duration_exhausted is True
    assert count(repository, "observation_cycles") == 2


def test_cleanup_honors_shutdown_before_first_batch(repository):
    cycle(repository, "old", "client", "2025-01-01T00:00:00.000Z")
    stop = threading.Event()
    stop.set()
    result = ObservationCleanup(repository, repository.config).run_once(
        now_utc="2026-08-01T00:00:00.000Z",
        shutdown_event=stop,
    )
    assert result.interrupted is True
    assert result.batches == 0
    assert repository.get_cycle("old") is not None


def test_cleanup_worker_start_stop_is_idempotent(repository, tmp_path):
    config = make_config(
        tmp_path,
        db_path=repository.config.db_path,
        cleanup_initial_delay_seconds=60.0,
        shutdown_timeout_seconds=1.0,
    )
    worker = ObservationCleanupWorker(
        ObservationCleanup(repository, config),
        config,
    )
    assert worker.start() is True
    assert worker.start() is False
    assert worker.stop() is True
    assert worker.stop() is True
