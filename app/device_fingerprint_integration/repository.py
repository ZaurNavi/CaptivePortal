"""Short FULL-sync transactions in the dedicated relation-only SQLite."""

from contextlib import contextmanager
from dataclasses import fields
from pathlib import Path
import os
import sqlite3
import uuid

from .models import IntegrationError, IntegrationJob, LEASE_SECONDS, MAX_ATTEMPTS, plus, parse_utc

_COLUMNS = tuple(field.name for field in fields(IntegrationJob))
_DDL = """
CREATE TABLE integration_jobs (
 integration_id TEXT PRIMARY KEY,
 auth_session_id TEXT NOT NULL, auth_run_number INTEGER NOT NULL CHECK(auth_run_number>0),
 site_id TEXT NOT NULL, observed_mac TEXT NOT NULL, authorized_at_utc TEXT NOT NULL,
 planned_classification_id TEXT NOT NULL UNIQUE, due_at_utc TEXT NOT NULL,
 classification_state TEXT NOT NULL CHECK(classification_state IN ('PENDING','LEASED','CLASSIFIED','NO_RESULT_FINAL')),
 attempt_count INTEGER NOT NULL CHECK(attempt_count BETWEEN 0 AND 5), next_attempt_at_utc TEXT NOT NULL,
 lease_token TEXT, lease_until_utc TEXT,
 effective_window_start_utc TEXT, effective_window_end_utc TEXT,
 classification_id TEXT, classification_result_id TEXT, last_reason_code TEXT,
 registry_snapshot_id TEXT, device_id TEXT, visit_id TEXT,
 identity_state TEXT NOT NULL CHECK(identity_state IN ('UNRESOLVED','DEVICE_RESOLVED','DEVICE_AND_VISIT_RESOLVED','CONFLICT')),
 identity_reason TEXT, identity_last_attempt_at_utc TEXT,
 created_at_utc TEXT NOT NULL, updated_at_utc TEXT NOT NULL,
 UNIQUE(auth_session_id,auth_run_number),
 CHECK(classification_id IS NULL OR classification_id=planned_classification_id),
 CHECK((classification_state='LEASED' AND lease_token IS NOT NULL AND lease_until_utc IS NOT NULL)
    OR (classification_state!='LEASED' AND lease_token IS NULL AND lease_until_utc IS NULL))
);
CREATE INDEX integration_due ON integration_jobs(classification_state,next_attempt_at_utc,due_at_utc);
CREATE INDEX integration_device ON integration_jobs(site_id,device_id,authorized_at_utc DESC,integration_id DESC);
CREATE INDEX integration_identity ON integration_jobs(identity_state,identity_last_attempt_at_utc);
PRAGMA user_version=1;
"""


class IntegrationRepository:
    def __init__(self, database_path, *, busy_timeout_ms=100):
        self.path = Path(database_path).resolve()
        if type(busy_timeout_ms) is not int or not 1 <= busy_timeout_ms <= 1000:
            raise ValueError("Invalid bounded busy timeout")
        self.timeout_ms = busy_timeout_ms

    @contextmanager
    def connection(self, *, readonly=False):
        conn = None
        try:
            conn = sqlite3.connect(f"{self.path.as_uri()}?mode={'ro' if readonly else 'rw'}",
                                  uri=True, timeout=self.timeout_ms / 1000, isolation_level=None)
            conn.row_factory = sqlite3.Row
            conn.execute(f"PRAGMA busy_timeout={self.timeout_ms}")
            conn.execute("PRAGMA foreign_keys=ON")
            if not readonly:
                conn.execute("PRAGMA synchronous=FULL")
            yield conn
        except sqlite3.Error as exc:
            reason = "retryable_sqlite_busy" if (getattr(exc, "sqlite_errorcode", 0) or 0) & 255 in (
                5, 6) or str(exc).lower() in (  # SQLITE_BUSY/LOCKED, including Python 3.10.
                    "database is locked", "database is busy") else "integration_unavailable"
            raise IntegrationError(reason) from exc
        finally:
            if conn is not None:
                if conn.in_transaction:
                    conn.rollback()
                conn.close()

    def initialize(self):
        if not self.path.parent.is_dir() or self.path.is_symlink():
            raise IntegrationError("integration_unavailable")
        fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600) if not self.path.exists() else None
        if fd is not None:
            os.close(fd)
        with self.connection() as conn:
            version = conn.execute("PRAGMA user_version").fetchone()[0]
            if version == 0:
                if conn.execute("SELECT 1 FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'").fetchone():
                    raise IntegrationError("integration_schema_invalid")
                conn.executescript("BEGIN IMMEDIATE;" + _DDL + "COMMIT;")
            elif version != 1:
                raise IntegrationError("integration_schema_invalid")
            columns = tuple(row[1] for row in conn.execute("PRAGMA table_info(integration_jobs)"))
            if columns != _COLUMNS:
                raise IntegrationError("integration_schema_invalid")

    @staticmethod
    def _job(row):
        return None if row is None else IntegrationJob(**dict(row))

    def enqueue(self, request, now):
        parse_utc(now)
        integration_id, planned = str(uuid.uuid4()), str(uuid.uuid4())
        due = plus(request.authorized_at_utc, 150)
        with self.connection() as conn:
            row = conn.execute("""INSERT INTO integration_jobs (
                integration_id,auth_session_id,auth_run_number,site_id,observed_mac,authorized_at_utc,
                planned_classification_id,due_at_utc,classification_state,attempt_count,next_attempt_at_utc,
                identity_state,created_at_utc,updated_at_utc)
                VALUES (?,?,?,?,?,?,?,?,'PENDING',0,?,'UNRESOLVED',?,?)
                ON CONFLICT(auth_session_id,auth_run_number) DO UPDATE SET updated_at_utc=integration_jobs.updated_at_utc
                WHERE integration_jobs.site_id=excluded.site_id AND integration_jobs.observed_mac=excluded.observed_mac
                AND integration_jobs.authorized_at_utc=excluded.authorized_at_utc
                RETURNING integration_id""", (integration_id, request.auth_session_id, request.auth_run_number,
                    request.site_id, request.observed_mac, request.authorized_at_utc, planned, due, due, now, now)).fetchone()
            if row is None:
                raise IntegrationError("integration_identity_conflict")
            return row[0], row[0] == integration_id

    def get(self, integration_id):
        with self.connection(readonly=True) as conn:
            return self._job(conn.execute("SELECT * FROM integration_jobs WHERE integration_id=?",
                                         (integration_id,)).fetchone())

    def claim(self, now):
        parse_utc(now)
        with self.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("""SELECT * FROM integration_jobs WHERE due_at_utc<=? AND
                ((classification_state='PENDING' AND next_attempt_at_utc<=? AND attempt_count<5)
                OR (classification_state='LEASED' AND lease_until_utc<=?))
                ORDER BY due_at_utc,integration_id LIMIT 1""", (now, now, now)).fetchone()
            if row is None:
                return None
            previous = self._job(row)
            conn.execute("""UPDATE integration_jobs SET classification_state='LEASED',lease_token=?,
                lease_until_utc=?,attempt_count=min(attempt_count+1,5),updated_at_utc=? WHERE integration_id=?""",
                (str(uuid.uuid4()), plus(now, LEASE_SECONDS), now, previous.integration_id))
            job = self._job(conn.execute("SELECT * FROM integration_jobs WHERE integration_id=?",
                                        (previous.integration_id,)).fetchone())
            conn.commit()
            return job, previous.attempt_count >= MAX_ATTEMPTS

    def finish(self, job, now, *, state, reason=None, core=None, start=None, end=None, retry_at=None,
               identity_conflict=False):
        parse_utc(now)
        if state not in {"PENDING", "CLASSIFIED", "NO_RESULT_FINAL"}:
            raise ValueError("Invalid completion state")
        with self.connection() as conn:
            return conn.execute("""UPDATE integration_jobs SET classification_state=?,last_reason_code=?,
                classification_id=?,classification_result_id=?,effective_window_start_utc=?,effective_window_end_utc=?,
                next_attempt_at_utc=?,lease_token=NULL,lease_until_utc=NULL,updated_at_utc=?,
                identity_state=CASE WHEN ? THEN 'CONFLICT' ELSE identity_state END,
                identity_reason=CASE WHEN ? THEN ? ELSE identity_reason END
                WHERE integration_id=? AND classification_state='LEASED' AND lease_token=? AND lease_until_utc>?""",
                (state, reason, None if core is None else core.classification_id,
                 None if core is None else core.classification_result_id, start, end,
                 retry_at or job.next_attempt_at_utc, now, identity_conflict, identity_conflict, reason,
                 job.integration_id, job.lease_token, now)).rowcount == 1

    def identity_due(self, now):
        parse_utc(now)
        with self.connection(readonly=True) as conn:
            return self._job(conn.execute("""SELECT * FROM integration_jobs
                WHERE identity_state IN ('UNRESOLVED','DEVICE_RESOLVED')
                AND (identity_last_attempt_at_utc IS NULL OR identity_last_attempt_at_utc<=?)
                AND (identity_last_attempt_at_utc IS NULL OR
                     identity_last_attempt_at_utc<strftime('%Y-%m-%dT%H:%M:%fZ',authorized_at_utc,'+3600 seconds'))
                ORDER BY coalesce(identity_last_attempt_at_utc,''),integration_id LIMIT 1""", (plus(now, -30),)).fetchone())

    def save_identity(self, job, resolution, now):
        with self.connection() as conn:
            conn.execute("""UPDATE integration_jobs SET registry_snapshot_id=?,device_id=?,visit_id=?,
                identity_state=?,identity_reason=?,identity_last_attempt_at_utc=?,updated_at_utc=?
                WHERE integration_id=? AND identity_state!='CONFLICT'""",
                (resolution.snapshot_id, resolution.device_id, resolution.visit_id,
                 resolution.state, resolution.reason, now, now, job.integration_id))

    def for_auth_run(self, site, session, number):
        with self.connection(readonly=True) as conn:
            return self._job(conn.execute("SELECT * FROM integration_jobs WHERE site_id=? AND auth_session_id=? AND auth_run_number=?",
                                         (site, session, number)).fetchone())

    def current_for_device(self, site, device):
        with self.connection(readonly=True) as conn:
            return self._job(conn.execute("""SELECT * FROM integration_jobs WHERE site_id=? AND device_id=?
                AND classification_state='CLASSIFIED' AND identity_state IN ('DEVICE_RESOLVED','DEVICE_AND_VISIT_RESOLVED')
                ORDER BY authorized_at_utc DESC,integration_id DESC LIMIT 1""", (site, device)).fetchone())
