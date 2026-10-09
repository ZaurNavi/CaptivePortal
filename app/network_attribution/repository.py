"""Sensor-owned single writer, atomic facts/intervals and separate coverage."""

import os
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.device_fingerprint.validation import format_utc, parse_utc

from .models import (
    IPv4BindingIntervalV1, NetworkAttributionConflict,
    NetworkAttributionStorageUnavailable, NetworkAttributionValidationError,
)
from .schema import create_schema, validate_schema
from .validation import source_values, validate_fact

RETENTION_SECONDS = 30 * 86400
RETENTION_BATCH_SIZE = 100


def coverage_is_continuous(connection, site, source, start, end):
    rows = connection.execute(
        "SELECT * FROM source_coverage WHERE site_id=? AND capture_source_id=? AND coverage_from<=? "
        "AND (coverage_until IS NULL OR coverage_until>?) ORDER BY coverage_from,coverage_id",
        (site, source, end, start)).fetchall()
    through = start
    for row in rows:
        until = row["coverage_until"]
        if until is not None and until <= row["coverage_from"]:
            continue
        if (row["coverage_from"] > through or row["state"] != "usable"
                or (until is None and row["verified_through"] < end)):
            return False
        if until is None or until > end:
            return True
        through = max(through, until)
    return False


class NetworkAttributionRepository:
    def __init__(self, config, *, clock=lambda: datetime.now(timezone.utc)):
        self.config, self.clock = config, clock
        self.connection = None
        self._writer_fd = None
        self._mutex = threading.RLock()

    def _acquire_writer(self):
        self._writer_fd = os.open(self.config.db_path + ".writer.lock", os.O_CREAT | os.O_RDWR, 0o600)
        if os.name == "nt":
            import msvcrt
            os.lseek(self._writer_fd, 0, os.SEEK_SET)
            msvcrt.locking(self._writer_fd, msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(self._writer_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def initialize(self):
        if not self.config.enabled:
            raise NetworkAttributionStorageUnavailable("attribution_disabled")
        try:
            self._acquire_writer()
            if Path(self.config.db_path).exists() and Path(self.config.db_path).stat().st_size:
                # Reject a foreign/corrupt DB before changing its journaling configuration.
                probe = sqlite3.connect(Path(self.config.db_path).resolve().as_uri() + "?mode=ro", uri=True)
                try:
                    probe.execute("PRAGMA foreign_keys=ON")
                    validate_schema(probe)
                finally:
                    probe.close()
            self.connection = sqlite3.connect(self.config.db_path, timeout=.5,
                                             isolation_level=None, check_same_thread=False)
            self.connection.row_factory = sqlite3.Row
            for pragma in ("foreign_keys=ON", "journal_mode=WAL", "synchronous=FULL",
                           "busy_timeout=500", "wal_autocheckpoint=1000"):
                self.connection.execute("PRAGMA " + pragma)
            # Reserve WAL/shm space inside the total configured DB footprint.
            self._check_capacity()
            page_size = self.connection.execute("PRAGMA page_size").fetchone()[0]
            pages = (self.config.max_db_bytes - 32800) // (page_size * 2 + 24)
            if pages < 1 or self.connection.execute(f"PRAGMA max_page_count={pages}").fetchone()[0] > pages:
                raise NetworkAttributionStorageUnavailable("attribution_capacity_exhausted")
            objects = self.connection.execute("SELECT count(*) FROM sqlite_master").fetchone()[0]
            if objects == 0 and self.connection.execute("PRAGMA user_version").fetchone()[0] == 0:
                with self.transaction():
                    create_schema(self.connection)
            validate_schema(self.connection)
            return self
        except (sqlite3.Error, OSError, NetworkAttributionStorageUnavailable):
            self.close()
            raise NetworkAttributionStorageUnavailable("attribution_store_unavailable") from None

    def _check_capacity(self):
        total = sum(path.stat().st_size for path in (
            Path(self.config.db_path), Path(self.config.db_path + "-wal"),
            Path(self.config.db_path + "-shm")) if path.exists())
        if total > self.config.max_db_bytes:
            raise NetworkAttributionStorageUnavailable("attribution_capacity_exhausted")

    @contextmanager
    def transaction(self):
        with self._mutex:
            if self.connection is None:
                raise NetworkAttributionStorageUnavailable("attribution_store_unavailable")
            try:
                self._check_capacity()
                self.connection.execute("BEGIN IMMEDIATE")
                yield
                self._check_capacity()
                self.connection.execute("COMMIT")
                # COMMIT can append WAL frames not yet visible in the pre-commit
                # footprint. Actual exhaustion remains fail-closed.
                self._check_capacity()
            except BaseException as error:
                if self.connection.in_transaction:
                    self.connection.execute("ROLLBACK")
                if isinstance(error, (sqlite3.Error, OSError)):
                    raise NetworkAttributionStorageUnavailable("attribution_store_unavailable") from None
                raise

    def maintain_wal(self):
        """One non-waiting maintenance attempt; pinned readers are not faults."""
        with self._mutex:
            if self.connection is None:
                raise NetworkAttributionStorageUnavailable("attribution_store_unavailable")
            try:
                self._check_capacity()
                busy, frames, checkpointed = self.connection.execute("PRAGMA wal_checkpoint(PASSIVE)").fetchone()
                if busy or frames != checkpointed:
                    return False
                # A new reader can race the PASSIVE result. Do not wait for it
                # or classify a busy TRUNCATE result as storage failure.
                timeout = self.connection.execute("PRAGMA busy_timeout").fetchone()[0]
                try:
                    self.connection.execute("PRAGMA busy_timeout=0")
                    reclaimed = self.connection.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()[0] == 0
                finally:
                    self.connection.execute(f"PRAGMA busy_timeout={timeout}")
                self._check_capacity()
                return reclaimed
            except sqlite3.OperationalError as error:
                code = getattr(error, "sqlite_errorcode", 0) & 255
                # Primary SQLite result codes BUSY=5, LOCKED=6; Python 3.10
                # does not expose the named result-code constants.
                if code in (5, 6) or str(error).lower() in {
                        "database is locked", "database table is locked"}:
                    return False
                raise NetworkAttributionStorageUnavailable("attribution_store_unavailable") from None
            except (sqlite3.Error, OSError):
                raise NetworkAttributionStorageUnavailable("attribution_store_unavailable") from None

    def _insert(self, table, values):
        columns = ",".join(values)
        self.connection.execute(f"INSERT INTO {table} ({columns}) VALUES ({','.join('?' for _ in values)})",
                                tuple(values.values()))

    def coverage(self, site_id, capture_source_id, state, event_at, reason_code=None):
        source_values(site_id, capture_source_id, event_at)
        if state not in {"usable", "unavailable"} or (state == "usable" and reason_code is not None):
            raise NetworkAttributionValidationError("invalid_coverage")
        if state == "unavailable":
            source_values(site_id, reason_code, event_at)
        with self.transaction():
            self._coverage(site_id, capture_source_id, state, event_at, reason_code)

    def _coverage(self, site, source, state, timestamp, reason):
        row = self.connection.execute(
            "SELECT * FROM source_coverage WHERE site_id=? AND capture_source_id=? AND coverage_until IS NULL",
            (site, source)).fetchone()
        if row is not None:
            if timestamp < row["coverage_from"]:
                raise NetworkAttributionConflict("coverage_clock_regression")
            if row["state"] == state and row["reason_code"] == reason:
                return
            self.connection.execute("UPDATE source_coverage SET coverage_until=? WHERE coverage_id=?",
                                    (timestamp, row["coverage_id"]))
        self._insert("source_coverage", dict(coverage_id=str(uuid.uuid4()), coverage_from=timestamp,
                     coverage_until=None, site_id=site, capture_source_id=source, state=state,
                     verified_through=timestamp, reason_code=reason))
        if state == "usable":
            self.connection.execute("INSERT OR IGNORE INTO authority_horizon VALUES(?,?,?)", (site, timestamp, timestamp))

    def capture_started(self, site, source, timestamp):
        """Unclosed prior process coverage never proves an unobserved crash gap."""
        source_values(site, source, timestamp)
        with self.transaction():
            old = self.connection.execute("SELECT * FROM source_coverage WHERE site_id=? AND capture_source_id=? AND coverage_until IS NULL",
                                          (site, source)).fetchone()
            if old is not None:
                if timestamp < old["verified_through"]:
                    raise NetworkAttributionConflict("coverage_clock_regression")
                # Canonical timestamps have millisecond precision. Preserve the
                # last verified instant inside the half-open completed interval.
                boundary = min(timestamp, format_utc(parse_utc(old["verified_through"]) + timedelta(milliseconds=1))) if old["state"] == "usable" else timestamp
                self.connection.execute("UPDATE source_coverage SET coverage_until=? WHERE coverage_id=?", (boundary, old["coverage_id"]))
                if boundary < timestamp:
                    self._insert("source_coverage", dict(coverage_id=str(uuid.uuid4()), coverage_from=boundary,
                        coverage_until=timestamp, site_id=site, capture_source_id=source, state="unavailable",
                        verified_through=boundary, reason_code="capture_restart_gap"))
            self._coverage(site, source, "usable", timestamp, None)

    def confirm_capture(self, site, source, timestamp):
        source_values(site, source, timestamp)
        with self.transaction():
            row = self.connection.execute("SELECT * FROM source_coverage WHERE site_id=? AND capture_source_id=? AND coverage_until IS NULL",
                                          (site, source)).fetchone()
            if row is None or row["state"] != "usable" or timestamp < row["verified_through"]:
                raise NetworkAttributionStorageUnavailable("source_coverage_unavailable")
            self.connection.execute("UPDATE source_coverage SET verified_through=? WHERE coverage_id=?", (timestamp, row["coverage_id"]))

    def record(self, fact):
        """Return interval, or None for duplicate/unmatched client termination.

        A conflicting authority event is rejected atomically and fences that source
        unavailable; the previous facts/intervals themselves are never overwritten.
        """
        validate_fact(fact)
        conflict = False
        result = None
        with self.transaction():
            existing = self.connection.execute("SELECT * FROM authority_facts WHERE fact_id=?", (fact.fact_id,)).fetchone()
            if existing is not None:
                prior = dict(existing)
                current = asdict(fact)
                prior.pop("ingested_at")
                current.pop("ingested_at")
                if prior != current:
                    raise NetworkAttributionConflict("fact_identity_conflict")
                return None
            active_coverage = self.connection.execute(
                "SELECT state FROM source_coverage WHERE site_id=? AND capture_source_id=? AND coverage_from<=? "
                "AND (coverage_until IS NULL OR ?<coverage_until)",
                (fact.site_id, fact.capture_source_id, fact.event_at, fact.event_at)).fetchall()
            if len(active_coverage) != 1 or active_coverage[0][0] != "usable":
                raise NetworkAttributionStorageUnavailable("source_coverage_unavailable")
            # No late event may silently rewrite already materialized authority.
            related = self.connection.execute(
                "SELECT * FROM authority_facts WHERE site_id=? AND event_at>=? "
                "AND (client_mac=? OR ipv4=?)",
                (fact.site_id, fact.event_at, fact.client_mac, fact.ipv4)).fetchall()
            collisions = [row for row in related if row["event_at"] > fact.event_at or
                (fact.message_type == "ack" and row["message_type"] == "ack" and
                 (row["client_mac"] != fact.client_mac or row["ipv4"] != fact.ipv4
                  or row["lease_seconds"] != fact.lease_seconds))]
            if collisions:
                self._coverage(fact.site_id, fact.capture_source_id, "unavailable", fact.event_at,
                               "authority_event_conflict")
                conflict = True
            else:
                live = self.connection.execute(
                    "SELECT * FROM binding_intervals WHERE site_id=? AND valid_from<=? AND ?<valid_until "
                    "AND (client_mac=? OR ipv4=?)",
                    (fact.site_id, fact.event_at, fact.event_at, fact.client_mac, fact.ipv4)).fetchall()
                exact = [row for row in live if row["client_mac"] == fact.client_mac and row["ipv4"] == fact.ipv4]
                if fact.message_type != "ack" and (len(exact) != 1 or len(live) != 1):
                    return None
                if fact.message_type != "ack" and not coverage_is_continuous(
                        self.connection, fact.site_id, exact[0]["capture_source_id"],
                        exact[0]["last_confirmed_at"], fact.event_at):
                    return None
                if len(exact) > 1:
                    raise NetworkAttributionConflict("overlapping_authority")
                self._insert("authority_facts", asdict(fact))
                if fact.message_type == "ack":
                    expires = format_utc(parse_utc(fact.event_at) + timedelta(seconds=fact.lease_seconds))
                    if exact and exact[0]["capture_source_id"] == fact.capture_source_id:
                        binding_id = exact[0]["binding_id"]
                        self.connection.execute(
                            "UPDATE binding_intervals SET last_confirmed_at=?,lease_expires_at=?,valid_until=?,last_fact_id=? WHERE binding_id=?",
                            (fact.event_at, expires, expires, fact.fact_id, binding_id))
                    else:
                        for row in live:
                            reason = "superseded_same_mac" if row["client_mac"] == fact.client_mac else "superseded_same_ip"
                            self.connection.execute("UPDATE binding_intervals SET valid_until=?,end_reason=?,last_fact_id=? WHERE binding_id=?",
                                                    (fact.event_at, reason, fact.fact_id, row["binding_id"]))
                        binding_id = str(uuid.uuid4())
                        self._insert("binding_intervals", dict(binding_id=binding_id, site_id=fact.site_id,
                            capture_source_id=fact.capture_source_id, client_mac=fact.client_mac, ipv4=fact.ipv4,
                            valid_from=fact.event_at, valid_until=expires, last_confirmed_at=fact.event_at,
                            lease_expires_at=expires, start_fact_id=fact.fact_id, last_fact_id=fact.fact_id, end_reason=None))
                else:
                    binding_id = exact[0]["binding_id"]
                    self.connection.execute("UPDATE binding_intervals SET valid_until=?,end_reason=?,last_fact_id=? WHERE binding_id=?",
                                            (fact.event_at, "client_" + fact.message_type, fact.fact_id, binding_id))
                self.connection.execute("INSERT INTO binding_fact_links VALUES(?,?)", (binding_id, fact.fact_id))
                row = self.connection.execute("SELECT * FROM binding_intervals WHERE binding_id=?", (binding_id,)).fetchone()
                result = IPv4BindingIntervalV1(**dict(row))
        if conflict:
            raise NetworkAttributionConflict("authority_event_conflict")
        return result

    def retain(self, *, at=None):
        """One bounded batch per call. Facts still referenced by retained rows survive."""
        timestamp = format_utc(self.clock()) if at is None else at
        parse_utc(timestamp)
        cutoff = format_utc(parse_utc(timestamp) - timedelta(seconds=RETENTION_SECONDS))
        with self.transaction():
            self.connection.execute("UPDATE authority_horizon SET retained_from=max(retained_from,?) WHERE first_usable_at<?", (cutoff, cutoff))
            self.connection.execute("DELETE FROM binding_intervals WHERE binding_id IN "
                "(SELECT binding_id FROM binding_intervals WHERE valid_until<? ORDER BY valid_until LIMIT ?)", (cutoff, RETENTION_BATCH_SIZE))
            self.connection.execute("DELETE FROM binding_fact_links WHERE rowid IN "
                "(SELECT l.rowid FROM binding_fact_links l JOIN authority_facts f USING(fact_id) "
                "JOIN binding_intervals b USING(binding_id) WHERE f.event_at<? AND f.fact_id<>b.start_fact_id "
                "AND f.fact_id<>b.last_fact_id AND f.event_at<(SELECT max(a.event_at) FROM binding_fact_links x "
                "JOIN authority_facts a USING(fact_id) WHERE x.binding_id=b.binding_id AND a.message_type='ack' "
                "AND a.event_at<=?) LIMIT ?)", (cutoff, cutoff, RETENTION_BATCH_SIZE))
            self.connection.execute("DELETE FROM authority_facts WHERE fact_id IN "
                "(SELECT fact_id FROM authority_facts WHERE event_at<? AND fact_id NOT IN "
                "(SELECT start_fact_id FROM binding_intervals UNION SELECT last_fact_id FROM binding_intervals "
                "UNION SELECT fact_id FROM binding_fact_links) ORDER BY event_at LIMIT ?)", (cutoff, RETENTION_BATCH_SIZE))
            # Keep the crossing coverage predecessor needed for a retained interval.
            self.connection.execute("DELETE FROM source_coverage WHERE coverage_id IN "
                "(SELECT c.coverage_id FROM source_coverage c WHERE c.coverage_until<? AND NOT EXISTS "
                "(SELECT 1 FROM binding_intervals b WHERE b.site_id=c.site_id AND b.capture_source_id=c.capture_source_id "
                "AND b.valid_from<c.coverage_until AND c.coverage_from<b.valid_until) ORDER BY c.coverage_until,c.coverage_id LIMIT ?)", (cutoff, RETENTION_BATCH_SIZE))

    def close(self):
        with self._mutex:
            if self.connection is not None:
                self.connection.close()
                self.connection = None
            if self._writer_fd is not None:
                os.close(self._writer_fd)
                self._writer_fd = None
