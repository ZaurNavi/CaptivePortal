from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.device_fingerprint_sensor.models import NormalizedEvent, SensorSpoolError
from app.device_fingerprint_sensor.spool import SensorSpool

UTC = timezone.utc


class Clock:
    value = datetime(2026, 9, 14, tzinfo=UTC)
    def __call__(self): return self.value


def event(index, endpoint="evidence", observed=None):
    identity = f"00000000-0000-4000-8000-{index:012d}"
    return NormalizedEvent(endpoint, identity, "dhcp", observed or "2026-09-14T00:00:00.000Z", {"id": index})


def spool(tmp_path, clock, **changes):
    value = SensorSpool(str(tmp_path / "spool.sqlite3"), total_budget_bytes=changes.get("budget", 10_000_000), main_db_max_bytes=5_000_000, max_events=changes.get("max_events", 100), now=clock)
    value.initialize(); return value


def test_spool_is_delete_journal_bounded_and_endpoint_homogeneous(tmp_path):
    clock = Clock(); value = spool(tmp_path, clock)
    assert value.connection.execute("PRAGMA journal_mode").fetchone()[0] == "delete"
    assert value.connection.execute("PRAGMA user_version").fetchone()[0] == 1
    value.enqueue([event(1), event(2, "source_health")])
    endpoint, rows = value.batch(100)
    assert endpoint == "evidence" and len(rows) == 1
    value.acknowledge([rows[0][0]])
    assert value.batch(100)[0] == "source_health"


def test_stable_id_is_idempotent_and_stale_rows_are_dropped(tmp_path):
    clock = Clock(); value = spool(tmp_path, clock)
    value.enqueue([event(1), event(1)])
    assert value.metrics()["rows"] == 1
    value.enqueue([event(2, observed="2026-09-12T00:00:00.000Z")])
    assert value.metrics()["rows"] == 1
    assert value.stale_dropped == 1


def test_row_cap_evicts_oldest_evidence_not_health(tmp_path):
    clock = Clock(); value = spool(tmp_path, clock, max_events=2)
    value.enqueue([event(1, "source_health"), event(2)])
    value.enqueue([event(3)])
    assert value.metrics()["rows"] == 2
    documents = [row[1] for row in value.batch(100)[1]]
    assert documents[0]["id"] == 1


def test_transaction_is_limited_to_100(tmp_path):
    clock = Clock(); value = spool(tmp_path, clock, max_events=1000)
    with pytest.raises(SensorSpoolError):
        value.enqueue([event(index) for index in range(101)])


def test_physical_fingerprint_contains_no_raw_packet_material(tmp_path):
    clock = Clock(); value = spool(tmp_path, clock)
    value.enqueue([event(1)])
    raw = Path(value.path).read_bytes()
    assert b"raw_packet" not in raw and b"private.example" not in raw


def test_batch_purges_more_than_one_chunk_without_delivering_stale_rows(tmp_path):
    clock = Clock(); value = spool(tmp_path, clock, max_events=200)
    value.enqueue([event(index) for index in range(100)])
    value.enqueue([event(index) for index in range(100, 150)])
    clock.value += timedelta(days=2)
    value.capacity_blocked = True
    deletions = []
    original = value._purge_stale

    def measured_purge():
        deleted = original()
        deletions.append(deleted)
        return deleted

    value._purge_stale = measured_purge
    value.enqueue([event(999, observed="2026-09-16T00:00:00.000Z")])
    endpoint, rows = value.batch(100)
    assert endpoint == "evidence"
    assert [document["id"] for _sequence, document in rows] == [999]
    assert deletions == [100, 50]
    assert all(deleted <= 100 for deleted in deletions)
    assert value.stale_dropped == 150
    assert value.capacity_blocked is False
