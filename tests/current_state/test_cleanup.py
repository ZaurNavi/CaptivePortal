from __future__ import annotations

from dataclasses import replace

from app.current_state.cleanup import CurrentStateCleanup
from app.current_state.repository import CurrentStateRepository

from .conftest import SITE, client_row, cycle


def publish(repository, identifier, started, count=1, result="success"):
    rows = [
        client_row(
            cycle_id=identifier,
            mac=f"AA:BB:CC:DD:{index // 256:02X}:{index % 256:02X}",
            observed_at=started,
        )
        for index in range(count)
    ]
    repository.publish_cycle(
        cycle(cycle_id=identifier, started=started, result=result, items_stored=len(rows), items_seen=len(rows)),
        client_rows=rows,
    )


def test_cleanup_deletes_expired_whole_cycles_and_preserves_latest_roles(config):
    repository = CurrentStateRepository(config)
    repository.initialize()
    publish(repository, "old-complete", "2026-08-19T00:00:00.000Z", 2)
    publish(repository, "latest-complete", "2026-08-20T00:00:00.000Z", 1)
    publish(repository, "latest-partial", "2026-08-20T01:00:00.000Z", 1, "partial")
    repository.publish_cycle(cycle(cycle_id="latest-attempt", started="2026-08-20T02:00:00.000Z", result="failed", items_seen=0))
    cleanup = CurrentStateCleanup(repository, config)
    result = cleanup.run_once(now_utc="2026-08-23T10:00:00.000Z")
    assert result.deleted_cycles == 1
    assert repository.get_cycle("old-complete") is None
    assert repository.get_cycle("latest-complete") is not None
    assert repository.get_cycle("latest-partial") is not None
    assert repository.get_cycle("latest-attempt") is not None


def test_cycle_larger_than_row_budget_is_deleted_whole(config):
    config = replace(config, cleanup_max_rows_per_transaction=2)
    repository = CurrentStateRepository(config)
    repository.initialize()
    publish(repository, "large-old", "2026-08-19T00:00:00.000Z", 3)
    publish(repository, "new", "2026-08-23T09:00:00.000Z", 1)
    result = CurrentStateCleanup(repository, config).run_once(now_utc="2026-08-23T10:00:00.000Z")
    assert result.deleted_client_rows == 3
    with repository.read_connection() as connection:
        assert connection.execute("SELECT COUNT(*) FROM current_client_state WHERE cycle_id='large-old'").fetchone()[0] == 0


def test_hard_cap_deletes_oldest_removable_cycles(config):
    config = replace(config, history_max_client_rows=2)
    repository = CurrentStateRepository(config)
    repository.initialize()
    publish(repository, "old", "2026-08-23T08:00:00.000Z", 2)
    publish(repository, "new", "2026-08-23T09:00:00.000Z", 2)
    result = CurrentStateCleanup(repository, config).run_once(now_utc="2026-08-23T10:00:00.000Z")
    assert result.deleted_cycles == 1
    assert repository.get_cycle("old") is None
    assert repository.count_client_rows() == 2
    assert result.retention_pressure is False


def test_preservation_can_report_retention_pressure(config):
    config = replace(config, history_max_client_rows=1)
    repository = CurrentStateRepository(config)
    repository.initialize()
    publish(repository, "only", "2026-08-23T09:00:00.000Z", 2)
    result = CurrentStateCleanup(repository, config).run_once(now_utc="2026-08-23T10:00:00.000Z")
    assert result.retention_pressure is True
    assert repository.get_cycle("only") is not None


def test_cleanup_stop_event_is_bounded(config):
    import threading
    repository = CurrentStateRepository(config)
    repository.initialize()
    stop = threading.Event()
    stop.set()
    result = CurrentStateCleanup(repository, config).run_once(now_utc="2026-08-23T10:00:00.000Z", stop_event=stop)
    assert result.interrupted is True
    assert result.deleted_cycles == 0
