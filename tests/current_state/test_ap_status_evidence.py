"""Read-only prior AP inventory authority for current traffic."""
from dataclasses import replace
import hashlib
import sqlite3

import pytest

from app.current_state.repository import CurrentStateRepository
from app.current_state.read_service import CurrentStateReadService
from app.current_state.models import CurrentStateValidationError
from .conftest import cycle, ap_row, SITE, OTHER_SITE, NOW


@pytest.fixture
def reader(config):
    repository = CurrentStateRepository(config)
    repository.initialize()
    return CurrentStateReadService(repository)


def publish(reader, *, cycle_id="ap", started=NOW, finished=NOW, result="success", site=SITE):
    rows = [ap_row(cycle_id=cycle_id, site_id=site, mac=f"AA:BB:CC:DD:EE:0{n}", observed_at=started,
                   status_classification=status, status_code=code)
            for n, status, code in ((1, "online", 1), (2, "offline", 0), (3, "unknown", None))]
    parent = replace(cycle(kind="ap", cycle_id=cycle_id, site_id=site, started=started, result=result, items_stored=3),
                     capture_finished_at=finished, unknown_status_count=1)
    reader.repository.publish_cycle(parent, ap_rows=rows)


@pytest.mark.parametrize("at,state,age", [
    (NOW, "aligned_fresh", 0), ("2026-08-23T10:01:30.000Z", "aligned_fresh", 90),
    ("2026-08-23T10:01:30.001Z", "stale", 90.001),
])
def test_A_T08_status_age_measured_from_finish_at_exact_threshold(reader, at, state, age):
    publish(reader, started="2026-08-23T09:59:40.000Z")
    value = reader.read_ap_status_evidence_at(SITE, at)
    assert value.state == state and value.age_at_traffic_seconds == age
    assert value.statuses["AA:BB:CC:DD:EE:02"] == "offline"
    with pytest.raises(TypeError):
        value.statuses["AA:BB:CC:DD:EE:02"] = "online"


def test_future_partial_snapshot_not_used_and_no_cross_site_join(reader):
    publish(reader, cycle_id="prior")
    publish(reader, cycle_id="future", started="2026-08-23T10:00:31.000Z", finished="2026-08-23T10:00:31.000Z")
    publish(reader, cycle_id="partial", started="2026-08-23T10:00:20.000Z", finished="2026-08-23T10:00:20.000Z", result="partial")
    value = reader.read_ap_status_evidence_at(SITE, "2026-08-23T10:00:30.000Z")
    assert value.cycle_id == "prior"
    assert reader.read_ap_status_evidence_at(SITE, "2026-08-23T09:59:59.000Z").state == "unavailable"
    if OTHER_SITE in reader.config.site_ids:
        assert reader.read_ap_status_evidence_at(OTHER_SITE, NOW).state == "unavailable"
    else:
        with pytest.raises(CurrentStateValidationError):
            reader.read_ap_status_evidence_at(OTHER_SITE, NOW)


@pytest.mark.parametrize("field,value", [
    ("source_scope_hash", "0" * 64), ("source_rows_reported", 2), ("items_seen", 2),
    ("unknown_status_count", 0), ("error_count", 1), ("data_quality_warning_count", 1),
])
def test_corrupt_newest_status_does_not_fallback_to_older(reader, field, value):
    publish(reader, cycle_id="old", started="2026-08-23T09:59:50.000Z", finished="2026-08-23T09:59:50.000Z")
    publish(reader, cycle_id="new")
    with sqlite3.connect(reader.repository.db_path) as connection:
        if field == "items_seen":
            connection.execute("UPDATE current_state_cycles SET items_seen=?, items_stored=? WHERE cycle_id='new'", (value, value))
        else:
            connection.execute(f"UPDATE current_state_cycles SET {field}=? WHERE cycle_id='new'", (value,))
    assert reader.read_ap_status_evidence_at(SITE, NOW).state == "unavailable"


def test_reader_leaves_database_exact_bytes_unchanged(reader):
    publish(reader)
    path = reader.repository.db_path
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    reader.read_ap_status_evidence_at(SITE, NOW)
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before
