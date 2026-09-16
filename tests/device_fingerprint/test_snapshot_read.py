"""Task-01 snapshot-read transaction and watermark proofs."""

from __future__ import annotations

import sqlite3
import uuid
from dataclasses import FrozenInstanceError
from datetime import timedelta

import pytest

import app.device_fingerprint.read_service as read_module
from app.device_fingerprint.models import (
    DeviceFingerprintStorageCorrupt, DeviceFingerprintValidationError,
)
from app.device_fingerprint.read_service import DeviceFingerprintReadService
from app.device_fingerprint.validation import format_utc
from tests.device_fingerprint import NOW, SITE, evidence_event, health_event, producer
from tests.device_fingerprint.test_repository import service

MAC = "AA:BB:CC:DD:EE:FF"
START = format_utc(NOW - timedelta(minutes=3))
END = format_utc(NOW + timedelta(seconds=1))
EVIDENCE_TIME = format_utc(NOW - timedelta(minutes=1))


def _id(number: int) -> str:
    return str(uuid.UUID(int=number, version=4))


def _evidence(svc, count: int, *, first: int = 1, observed_at: str = EVIDENCE_TIME) -> None:
    for offset in range(0, count, 100):
        batch = [
            evidence_event(source_event_id=_id(number), observed_at=observed_at)
            for number in range(first + offset, first + min(offset + 100, count))
        ]
        assert svc.evidence_batch(producer(), {
            "producer_id": producer().producer_id, "events": batch,
        }).inserted == len(batch)


def _health(svc, count: int, *, first: int = 10_000) -> None:
    for offset in range(0, count, 100):
        batch = [
            health_event(source_health_event_id=_id(number))
            for number in range(first + offset, first + min(offset + 100, count))
        ]
        assert svc.source_health_batch(producer(), {
            "producer_id": producer().producer_id, "events": batch,
        }).inserted == len(batch)


def _all_pages(fetch, *, limit: int) -> list[dict]:
    items: list[dict] = []
    cursor = None
    while True:
        page = fetch(limit=limit, cursor=cursor)
        items.extend(page["items"])
        cursor = page["next_cursor"]
        if cursor is None:
            return items


class TracedConnection:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection
        self.calls: list[tuple[str, tuple, bool]] = []
        self.rollbacks = 0
        self.closed = False
        self.fail_evidence = False

    def execute(self, sql, parameters=()):
        self.calls.append((sql, tuple(parameters), self.connection.in_transaction))
        if self.fail_evidence and "FROM device_fingerprint_evidence WHERE" in sql:
            raise sqlite3.OperationalError("injected page failure")
        return self.connection.execute(sql, parameters)

    def rollback(self):
        self.rollbacks += 1
        self.connection.rollback()

    def close(self):
        self.closed = True
        self.connection.close()


def _trace_connections(monkeypatch):
    opened: list[TracedConnection] = []
    original = read_module.open_read_only

    def open_traced(path):
        connection = TracedConnection(original(path))
        opened.append(connection)
        return connection

    monkeypatch.setattr(read_module, "open_read_only", open_traced)
    return opened


def test_complete_evidence_health_pages_and_predecessor_share_one_transaction(tmp_path, monkeypatch):
    cfg, repo, svc = service(tmp_path)
    _evidence(svc, 503)
    _health(svc, 503)
    expected = repo.read_ingest_watermark(repo.connection)
    opened = _trace_connections(monkeypatch)
    read = DeviceFingerprintReadService(cfg.db_path, retention_days=30)

    with read.open_snapshot_read() as snapshot:
        watermark = snapshot.watermark
        assert watermark.database_generation_id == expected["database_generation_id"]
        assert watermark.max_committed_ingest_sequence == expected["max_committed_ingest_sequence"] == 1006
        with pytest.raises(FrozenInstanceError):
            watermark.max_committed_ingest_sequence = 0
        with pytest.raises(AttributeError):
            snapshot.watermark = watermark
        evidence = _all_pages(
            lambda **kw: snapshot.list_evidence(
                SITE, MAC, START, END, source_kind="dhcp",
                producer_id=producer().producer_id,
                capture_source_id=producer().capture_source_id, **kw,
            ), limit=200,
        )
        health = _all_pages(
            lambda **kw: snapshot.list_source_health(
                SITE, producer().producer_id, producer().capture_source_id,
                "dhcp", START, END, **kw,
            ), limit=200,
        )
        anchor = snapshot.latest_source_health(
            SITE, producer().producer_id, producer().capture_source_id,
            "dhcp", through_utc=format_utc(NOW),
        )
        assert len(evidence) == len(health) == 503
        assert len({item["evidence_id"] for item in evidence}) == 503
        assert len({item["source_health_id"] for item in health}) == 503
        assert [(item["observed_at"], item["evidence_id"]) for item in evidence] == sorted(
            (item["observed_at"], item["evidence_id"]) for item in evidence
        )
        assert [(item["observed_at"], item["source_health_id"]) for item in health] == sorted(
            (item["observed_at"], item["source_health_id"]) for item in health
        )
        assert anchor["source_health_id"] == health[-1]["source_health_id"]
        assert snapshot.list_evidence(SITE, MAC, START, END, producer_id="other-producer")["items"] == []
        assert snapshot.list_evidence(SITE, MAC, START, END, capture_source_id="other-capture")["items"] == []
        assert snapshot.list_evidence(SITE, MAC, START, END, source_kind="tcp_syn")["items"] == []
        assert snapshot.list_source_health(
            SITE, "other-producer", producer().capture_source_id, "dhcp", START, END,
        )["items"] == []
        assert snapshot.latest_source_health(
            SITE, "other-producer", producer().capture_source_id, "dhcp",
            through_utc=format_utc(NOW),
        ) is None
        assert opened[0].connection.in_transaction

    assert len(opened) == 1
    traced = opened[0]
    assert traced.closed and traced.rollbacks == 1
    assert sum(sql == "BEGIN" for sql, _, _ in traced.calls) == 1
    assert sum("FROM device_fingerprint_storage_state" in sql for sql, _, _ in traced.calls) == 1
    membership = [call for call in traced.calls if "FROM device_fingerprint_evidence WHERE" in call[0]
                  or "FROM device_fingerprint_source_health_events WHERE" in call[0]]
    assert membership
    assert all("ingest_sequence<=?" in sql and watermark.max_committed_ingest_sequence in params and active
               for sql, params, active in membership)
    assert all(active for sql, _, active in traced.calls if sql != "BEGIN")
    with pytest.raises(DeviceFingerprintValidationError, match="closed"):
        snapshot.list_evidence(SITE, MAC, START, END)


def test_concurrent_eligible_delayed_insert_cannot_shift_pages_or_watermark(tmp_path):
    cfg, _repo, svc = service(tmp_path)
    _evidence(svc, 503)
    read = DeviceFingerprintReadService(cfg.db_path, retention_days=30)
    with read.open_snapshot_read() as snapshot:
        first = snapshot.list_evidence(SITE, MAC, START, END, limit=200)
        watermark = snapshot.watermark
        _evidence(svc, 1, first=9000, observed_at=format_utc(NOW - timedelta(minutes=2)))
        remaining = []
        cursor = first["next_cursor"]
        while cursor is not None:
            page = snapshot.list_evidence(SITE, MAC, START, END, limit=200, cursor=cursor)
            remaining.extend(page["items"])
            cursor = page["next_cursor"]
        all_rows = first["items"] + remaining
        assert len(all_rows) == len({row["evidence_id"] for row in all_rows}) == 503
        assert snapshot.watermark is watermark
        assert all(row["ingest_sequence"] <= watermark.max_committed_ingest_sequence for row in all_rows)
    with read.open_snapshot_read() as next_snapshot:
        assert next_snapshot.watermark.max_committed_ingest_sequence == watermark.max_committed_ingest_sequence + 1
        assert len(_all_pages(
            lambda **kw: next_snapshot.list_evidence(SITE, MAC, START, END, **kw), limit=200,
        )) == 504


def test_concurrent_retention_delete_cannot_shift_active_snapshot_membership(tmp_path):
    cfg, repo, svc = service(tmp_path)
    _evidence(svc, 503)
    read = DeviceFingerprintReadService(cfg.db_path, retention_days=30)
    with read.open_snapshot_read() as snapshot:
        first = snapshot.list_evidence(SITE, MAC, START, END, limit=200)
        watermark = snapshot.watermark
        assert repo.cleanup(now=NOW + timedelta(days=32), evidence_retention_days=30)[
            "device_fingerprint_evidence"
        ] == 503
        remaining = []
        cursor = first["next_cursor"]
        while cursor is not None:
            page = snapshot.list_evidence(SITE, MAC, START, END, limit=200, cursor=cursor)
            remaining.extend(page["items"])
            cursor = page["next_cursor"]
        rows = first["items"] + remaining
        assert len(rows) == len({row["evidence_id"] for row in rows}) == 503
        assert snapshot.watermark is watermark
    with read.open_snapshot_read() as next_snapshot:
        assert next_snapshot.watermark == watermark
        assert next_snapshot.list_evidence(SITE, MAC, START, END)["items"] == []


def test_wal_checkpoint_does_not_shift_evidence_or_health_view(tmp_path):
    cfg, repo, svc = service(tmp_path)
    _evidence(svc, 1)
    _health(svc, 1)
    read = DeviceFingerprintReadService(cfg.db_path, retention_days=30)
    with read.open_snapshot_read() as snapshot:
        watermark = snapshot.watermark
        evidence_before = snapshot.list_evidence(SITE, MAC, START, END)
        health_before = snapshot.list_source_health(
            SITE, producer().producer_id, producer().capture_source_id, "dhcp", START, END,
        )
        anchor_before = snapshot.latest_source_health(
            SITE, producer().producer_id, producer().capture_source_id,
            "dhcp", through_utc=format_utc(NOW),
        )
        _evidence(svc, 1, first=9000)
        _health(svc, 1, first=20_000)
        checkpoint = repo.connection.execute("PRAGMA wal_checkpoint(PASSIVE)").fetchone()
        assert len(checkpoint) == 3
        assert snapshot.watermark is watermark
        assert snapshot.list_evidence(SITE, MAC, START, END) == evidence_before
        assert snapshot.list_source_health(
            SITE, producer().producer_id, producer().capture_source_id, "dhcp", START, END,
        ) == health_before
        assert snapshot.latest_source_health(
            SITE, producer().producer_id, producer().capture_source_id,
            "dhcp", through_utc=format_utc(NOW),
        ) == anchor_before
    with read.open_snapshot_read() as next_snapshot:
        assert next_snapshot.watermark.max_committed_ingest_sequence == watermark.max_committed_ingest_sequence + 2
        assert len(next_snapshot.list_evidence(SITE, MAC, START, END)["items"]) == 2
        assert len(next_snapshot.list_source_health(
            SITE, producer().producer_id, producer().capture_source_id, "dhcp", START, END,
        )["items"]) == 2


def test_failed_page_and_invalid_watermark_close_transaction_and_connection(tmp_path, monkeypatch):
    cfg, repo, svc = service(tmp_path)
    _evidence(svc, 1)
    opened = _trace_connections(monkeypatch)
    read = DeviceFingerprintReadService(cfg.db_path, retention_days=30)
    snapshot = read.open_snapshot_read()
    opened[0].fail_evidence = True
    with pytest.raises(sqlite3.OperationalError, match="injected page failure"):
        snapshot.list_evidence(SITE, MAC, START, END)
    assert opened[0].closed and opened[0].rollbacks == 1
    with pytest.raises(DeviceFingerprintValidationError, match="closed"):
        snapshot.list_source_health(SITE, producer().producer_id, producer().capture_source_id, "dhcp", START, END)

    repo.connection.execute(
        "UPDATE device_fingerprint_storage_state SET database_generation_id=?",
        ("0" * 36,),
    )
    with pytest.raises(DeviceFingerprintStorageCorrupt):
        read.open_snapshot_read()
    assert opened[1].closed and opened[1].rollbacks == 1


def test_invalid_allocator_watermark_fails_before_session_is_returned(tmp_path, monkeypatch):
    cfg, repo, _svc = service(tmp_path)
    generation = repo.read_ingest_watermark(repo.connection)["database_generation_id"]
    opened = _trace_connections(monkeypatch)
    monkeypatch.setattr(
        read_module.DeviceFingerprintRepository, "read_ingest_watermark",
        staticmethod(lambda _connection: {
            "database_generation_id": generation,
            "max_committed_ingest_sequence": "not-an-integer",
        }),
    )
    with pytest.raises(DeviceFingerprintStorageCorrupt):
        DeviceFingerprintReadService(cfg.db_path, retention_days=30).open_snapshot_read()
    assert len(opened) == 1 and opened[0].closed and opened[0].rollbacks == 1


@pytest.mark.parametrize("bad_limit,bad_cursor", [
    (0, None), (501, None), (True, None), (100, (START, "bad-id")),
])
def test_snapshot_page_validation_is_fail_closed(tmp_path, bad_limit, bad_cursor):
    cfg, _repo, _svc = service(tmp_path)
    read = DeviceFingerprintReadService(cfg.db_path, retention_days=30)
    snapshot = read.open_snapshot_read()
    with pytest.raises(DeviceFingerprintValidationError):
        snapshot.list_evidence(SITE, MAC, START, END, limit=bad_limit, cursor=bad_cursor)
    with pytest.raises(DeviceFingerprintValidationError, match="closed"):
        snapshot.list_evidence(SITE, MAC, START, END)
