"""SQLite persistence for Visit Lifecycle, exact schemas through version 6."""

from __future__ import annotations

import os
from app.operations_verification import startup_check
import sqlite3
import stat
import threading
import time
import uuid
from collections import deque
from contextlib import closing, contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

from .models import (
    protocol_visit_guard,
    OfflineEvidence,
    OfflineProcessingOutcome,
    ReaderCheckpoint,
    ReaderProgress,
    ReconcileCandidate,
    SCHEMA_VERSION,
    VisitLifecycleConfig,
    VisitRecord,
    VisitSchemaError,
    VisitStartOutcome,
    VisitStorageCategory,
    VisitStorageError,
    VisitWriterContention,
    VisitReaderState,
    NormalizedVisitStart,
)


ALLOWED_AUTO_CREATE_ROOT = Path("/opt/CaptivePortal/data")

_SQLITE_BUSY = 5
_SQLITE_LOCKED = 6
_SQLITE_READONLY = 8
_SQLITE_IOERR = 10
_SQLITE_CORRUPT = 11
_SQLITE_FULL = 13
_SQLITE_CANTOPEN = 14
_SQLITE_CONSTRAINT = 19
_SQLITE_NOTADB = 26

WRITE_OPERATION_START = "start"
WRITE_OPERATION_READER_LINE = "reader_line"
WRITE_OPERATION_READER_CHECKPOINT = "reader_checkpoint"
WRITE_OPERATION_PENDING_RETRY = "pending_retry"
# Compatibility alias for tests/integrations that intentionally acquire a
# generic reader-line lease.
WRITE_OPERATION_READER = WRITE_OPERATION_READER_LINE
WRITE_OPERATION_RECONCILIATION = "reconciliation"
WRITE_OPERATION_STARTUP = "startup"

BACKGROUND_STARVATION_AGE_MS = 200
BACKGROUND_CHUNK_MAX_ITEMS = 25
BACKGROUND_CHUNK_TARGET_MAX_HOLD_MS = 50

_BACKGROUND_CLASS_BY_OPERATION = {
    WRITE_OPERATION_READER_LINE: "reader",
    WRITE_OPERATION_READER_CHECKPOINT: "reader",
    WRITE_OPERATION_PENDING_RETRY: "pending_retry",
    WRITE_OPERATION_RECONCILIATION: "reconciliation",
}

REQUIRED_TABLES = frozenset({
    "visits",
    "visit_authorizations",
    "visit_source_events",
    "visit_reader_state",
})

REQUIRED_INDEXES: Mapping[str, tuple[str, ...]] = {
    "uq_visits_open_site_mac": ("site_id", "client_mac"),
    "idx_visits_site_started": ("site_id", "started_at", "visit_id"),
    "idx_visits_site_closed": ("site_id", "closed_at", "visit_id"),
    "idx_visits_site_mac_started": (
        "site_id", "client_mac", "started_at", "visit_id",
    ),
    "idx_visits_site_device_started": (
        "site_id", "device_id", "started_at", "visit_id",
    ),
    "idx_visits_site_status_started": (
        "site_id", "status", "started_at", "visit_id",
    ),
    "idx_visits_site_start_ssid": (
        "site_id", "start_ssid", "started_at", "visit_id",
    ),
    "idx_visits_site_final_ssid": (
        "site_id", "final_ssid", "started_at", "visit_id",
    ),
    "idx_visits_site_start_ap": (
        "site_id", "start_ap_mac", "started_at", "visit_id",
    ),
    "idx_visits_site_final_ap": (
        "site_id", "final_ap_mac", "started_at", "visit_id",
    ),
    "idx_visit_auth_visit_time": ("visit_id", "authorized_at", "row_id"),
    "idx_visit_auth_visit_ssid": ("visit_id", "portal_ssid"),
    "idx_visit_auth_visit_ap": ("visit_id", "portal_ap_mac"),
    "idx_visit_events_site_controller": (
        "site_id", "controller_event_at", "event_id",
    ),
    "idx_visit_events_site_processed": (
        "site_id", "processed_at", "event_id",
    ),
    "idx_visit_events_result_processed": (
        "processing_result", "processed_at",
    ),
    "idx_visit_events_source_offsets": (
        "source_identity", "source_offset_start", "source_offset_end",
    ),
    "idx_visits_reconcile_due": (
        "link_reconcile_next_at", "started_at", "visit_id",
    ),
}


@dataclass
class _WriteLease:
    lock_wait_ms: int
    progress_made: bool = False
    work_absent: bool = False

    def mark_progress(self) -> None:
        self.progress_made = True

    def mark_no_work(self) -> None:
        self.work_absent = True


@dataclass(frozen=True)
class _WriterWaiter:
    token: object
    operation: str
    background_class: str | None
    enqueued_at: float


@dataclass(frozen=True)
class _OfflineMatch:
    closed_at: str | None
    duration_seconds: int | None
    close_time_source: str | None
    reason: str | None
    duration_drift_seconds: float | None = None
    duration_drift_exceeded: bool = False


class PriorityWriteCoordinator:
    """Single writer gate with foreground priority and bounded fairness."""

    def __init__(self, *, monotonic=time.monotonic):
        self._condition = threading.Condition()
        self._monotonic = monotonic
        self._holder_operation: str | None = None
        self._holder_acquired_at: float | None = None
        self._foreground: deque[_WriterWaiter] = deque()
        self._background: deque[_WriterWaiter] = deque()
        self._starvation_since: dict[str, float] = {}
        self._foreground_required_after_escape = False

    @contextmanager
    def acquire(
        self,
        operation: str,
        *,
        timeout_ms: int,
        deadline: float | None = None,
        cancel_event: threading.Event | None = None,
    ):
        started = self._monotonic()
        local_deadline = started + max(0, timeout_ms) / 1000
        if deadline is not None:
            local_deadline = min(local_deadline, deadline)
        foreground = operation == WRITE_OPERATION_START
        background_class = _BACKGROUND_CLASS_BY_OPERATION.get(operation)
        queue = self._foreground if foreground else self._background
        waiter = _WriterWaiter(
            token=object(),
            operation=operation,
            background_class=background_class,
            enqueued_at=started,
        )
        acquired = False
        lease: _WriteLease | None = None
        with self._condition:
            queue.append(waiter)
            try:
                while True:
                    now = self._monotonic()
                    if not self._foreground:
                        self._foreground_required_after_escape = False
                    if cancel_event is not None and cancel_event.is_set():
                        if background_class is not None:
                            self._starvation_since.pop(background_class, None)
                        raise VisitStorageError(
                            VisitStorageCategory.UNAVAILABLE,
                            "Visit write wait was cancelled",
                            operation=operation,
                            lock_wait_ms=_elapsed_ms(started, now),
                            contention_layer="coordinator",
                            contention=self._snapshot_locked(
                                waiter_operation=operation,
                                waiter_started=started,
                                now=now,
                            ),
                        )
                    is_head = bool(queue) and queue[0] is waiter
                    aged_escape = (
                        not foreground
                        and background_class is not None
                        and is_head
                        and self._background_is_aged_locked(
                            background_class,
                            now,
                        )
                        and not self._foreground_required_after_escape
                    )
                    priority_allows = (
                        (
                            foreground
                            and (
                                self._foreground_required_after_escape
                                or not self._aged_background_head_locked(now)
                            )
                        )
                        or not self._foreground
                        or aged_escape
                    )
                    if (
                        self._holder_operation is None
                        and is_head
                        and priority_allows
                    ):
                        queue.popleft()
                        self._holder_operation = operation
                        self._holder_acquired_at = now
                        if foreground:
                            self._foreground_required_after_escape = False
                        elif aged_escape and self._foreground:
                            self._foreground_required_after_escape = True
                        acquired = True
                        break
                    if (
                        background_class is not None
                        and self._foreground_blocks_locked(waiter)
                    ):
                        self._starvation_since.setdefault(
                            background_class,
                            now,
                        )
                    remaining = local_deadline - now
                    if remaining <= 0:
                        raise VisitStorageError(
                            VisitStorageCategory.BUSY,
                            "Visit write slot is busy",
                            operation=operation,
                            lock_wait_ms=_elapsed_ms(started, now),
                            contention_layer="coordinator",
                            contention=self._snapshot_locked(
                                waiter_operation=operation,
                                waiter_started=started,
                                now=now,
                            ),
                        )
                    self._condition.wait(min(remaining, 0.050))
            finally:
                if not acquired:
                    try:
                        queue.remove(waiter)
                    except ValueError:
                        pass
                    self._condition.notify_all()
        try:
            lease = _WriteLease(
                lock_wait_ms=_elapsed_ms(started, self._monotonic())
            )
            yield lease
        finally:
            with self._condition:
                if (
                    lease is not None
                    and background_class is not None
                    and (lease.progress_made or lease.work_absent)
                ):
                    self._starvation_since.pop(background_class, None)
                self._holder_operation = None
                self._holder_acquired_at = None
                self._condition.notify_all()

    def wake_all(self) -> None:
        with self._condition:
            self._condition.notify_all()

    def clear_background_work(self, operation: str) -> None:
        background_class = _BACKGROUND_CLASS_BY_OPERATION.get(operation)
        if background_class is None:
            return
        with self._condition:
            self._starvation_since.pop(background_class, None)
            self._condition.notify_all()

    def snapshot(
        self,
        *,
        waiter_operation: str | None = None,
        waiter_started: float | None = None,
    ) -> VisitWriterContention:
        with self._condition:
            return self._snapshot_locked(
                waiter_operation=waiter_operation,
                waiter_started=waiter_started,
                now=self._monotonic(),
            )

    def _waiting_counts(self) -> tuple[int, int]:
        """Return foreground/background queue depths atomically."""
        with self._condition:
            return len(self._foreground), len(self._background)

    def _background_is_aged_locked(
        self,
        background_class: str,
        now: float,
    ) -> bool:
        since = self._starvation_since.get(background_class)
        return (
            since is not None
            and (now - since) * 1000 >= BACKGROUND_STARVATION_AGE_MS
        )

    def _aged_background_head_locked(self, now: float) -> bool:
        if not self._background:
            return False
        background_class = self._background[0].background_class
        return (
            background_class is not None
            and self._background_is_aged_locked(background_class, now)
        )

    def _foreground_blocks_locked(self, waiter: _WriterWaiter) -> bool:
        return (
            bool(self._background)
            and self._background[0] is waiter
            and (
                (
                    self._holder_operation is None
                    and bool(self._foreground)
                )
                or self._holder_operation == WRITE_OPERATION_START
            )
        )

    def _snapshot_locked(
        self,
        *,
        waiter_operation: str | None,
        waiter_started: float | None,
        now: float,
    ) -> VisitWriterContention:
        return VisitWriterContention(
            holder_operation=self._holder_operation,
            holder_age_ms=(
                None
                if self._holder_acquired_at is None
                else _elapsed_ms(self._holder_acquired_at, now)
            ),
            foreground_queue_depth=len(self._foreground),
            background_queue_depth=len(self._background),
            waiter_operation=waiter_operation,
            waiter_wait_ms=(
                None
                if waiter_started is None
                else _elapsed_ms(waiter_started, now)
            ),
        )


def _elapsed_ms(started: float, finished: float) -> int:
    return max(0, int(round((finished - started) * 1000)))

REQUIRED_TRIGGERS = frozenset({"trg_visits_start_evidence_immutable"})

REQUIRED_FOREIGN_KEYS: Mapping[str, frozenset[tuple[str, str, str, str]]] = {
    "visits": frozenset({
        ("offline_event_id", "visit_source_events", "event_id", "SET NULL"),
    }),
    "visit_authorizations": frozenset({
        ("visit_id", "visits", "visit_id", "CASCADE"),
    }),
    "visit_source_events": frozenset({
        ("visit_id", "visits", "visit_id", "SET NULL"),
    }),
}

REQUIRED_NOT_NULL_COLUMNS: Mapping[str, frozenset[str]] = {
    "visits": frozenset({
        "site_id",
        "client_mac",
        "start_auth_session_id",
        "start_auth_run_number",
        "start_final_reason",
        "started_at",
        "status",
        "created_at",
        "updated_at",
    }),
    "visit_authorizations": frozenset({
        "visit_id",
        "auth_session_id",
        "auth_run_number",
        "authorized_at",
        "final_reason",
        "created_at",
    }),
}

REQUIRED_V2_SOURCE_COLUMNS = frozenset({
    "client_ip",
    "ssid",
    "ap_mac",
    "reported_connected_seconds",
    "reported_traffic_total_bytes",
})

MIGRATION_V1_TO_V2_STATEMENTS = (
    "ALTER TABLE visit_source_events ADD COLUMN client_ip TEXT",
    "ALTER TABLE visit_source_events ADD COLUMN ssid TEXT",
    """ALTER TABLE visit_source_events ADD COLUMN ap_mac TEXT
       CHECK (ap_mac IS NULL OR ap_mac GLOB
           '[0-9A-F][0-9A-F]:[0-9A-F][0-9A-F]:[0-9A-F][0-9A-F]:[0-9A-F][0-9A-F]:[0-9A-F][0-9A-F]:[0-9A-F][0-9A-F]')""",
    """ALTER TABLE visit_source_events
       ADD COLUMN reported_connected_seconds INTEGER
       CHECK (
           reported_connected_seconds IS NULL OR (
               typeof(reported_connected_seconds) = 'integer'
               AND reported_connected_seconds >= 0
           )
       )""",
    """ALTER TABLE visit_source_events
       ADD COLUMN reported_traffic_total_bytes INTEGER
       CHECK (
           reported_traffic_total_bytes IS NULL OR (
               typeof(reported_traffic_total_bytes) = 'integer'
               AND reported_traffic_total_bytes >= 0
           )
       )""",
)


def _utc_check(column: str, *, nullable: bool = False) -> str:
    expression = (
        f"(length({column}) = 24 "
        f"AND substr({column}, 5, 1) = '-' "
        f"AND substr({column}, 8, 1) = '-' "
        f"AND substr({column}, 11, 1) = 'T' "
        f"AND substr({column}, 14, 1) = ':' "
        f"AND substr({column}, 17, 1) = ':' "
        f"AND substr({column}, 20, 1) = '.' "
        f"AND substr({column}, 24, 1) = 'Z')"
    )
    return f"({column} IS NULL OR {expression})" if nullable else expression


def _schema_sql_v1() -> str:
    return f"""
        BEGIN IMMEDIATE;

        CREATE TABLE visits (
            visit_id TEXT PRIMARY KEY CHECK (length(visit_id) = 36),
            site_id TEXT NOT NULL CHECK (length(trim(site_id)) > 0),
            client_mac TEXT NOT NULL CHECK (length(client_mac) = 17),

            device_id TEXT,
            initial_snapshot_id TEXT,

            start_auth_session_id TEXT NOT NULL
                CHECK (length(trim(start_auth_session_id)) > 0),
            start_auth_run_number INTEGER NOT NULL
                CHECK (start_auth_run_number > 0),
            start_final_reason TEXT NOT NULL
                CHECK (length(trim(start_final_reason)) > 0),

            link_reconcile_attempted_at TEXT
                CHECK {_utc_check('link_reconcile_attempted_at', nullable=True)},
            link_reconcile_next_at TEXT
                CHECK {_utc_check('link_reconcile_next_at', nullable=True)},
            link_reconcile_attempt_count INTEGER NOT NULL DEFAULT 0
                CHECK (link_reconcile_attempt_count >= 0),

            started_at TEXT NOT NULL CHECK {_utc_check('started_at')},
            closed_at TEXT CHECK {_utc_check('closed_at', nullable=True)},
            status TEXT NOT NULL CHECK (status IN ('open', 'closed')),
            close_reason TEXT,
            close_time_source TEXT,

            start_ip TEXT,
            start_ssid TEXT,
            start_ap_mac TEXT CHECK (
                start_ap_mac IS NULL OR length(start_ap_mac) = 17
            ),
            final_ip TEXT,
            final_ssid TEXT,
            final_ap_mac TEXT CHECK (
                final_ap_mac IS NULL OR length(final_ap_mac) = 17
            ),

            reported_connected_seconds INTEGER CHECK (
                reported_connected_seconds IS NULL
                OR reported_connected_seconds >= 0
            ),
            reported_traffic_total_bytes INTEGER CHECK (
                reported_traffic_total_bytes IS NULL
                OR reported_traffic_total_bytes >= 0
            ),
            reported_traffic_up_bytes INTEGER CHECK (
                reported_traffic_up_bytes IS NULL
                OR reported_traffic_up_bytes >= 0
            ),
            reported_traffic_down_bytes INTEGER CHECK (
                reported_traffic_down_bytes IS NULL
                OR reported_traffic_down_bytes >= 0
            ),
            duration_seconds INTEGER CHECK (
                duration_seconds IS NULL OR duration_seconds >= 0
            ),
            offline_event_id TEXT UNIQUE,
            created_at TEXT NOT NULL CHECK {_utc_check('created_at')},
            updated_at TEXT NOT NULL CHECK {_utc_check('updated_at')},

            CHECK (
                (status = 'open'
                 AND closed_at IS NULL
                 AND close_reason IS NULL
                 AND close_time_source IS NULL
                 AND duration_seconds IS NULL
                 AND offline_event_id IS NULL)
                OR
                (status = 'closed'
                 AND closed_at IS NOT NULL
                 AND close_reason IS NOT NULL
                 AND close_time_source IS NOT NULL
                 AND duration_seconds IS NOT NULL
                 AND closed_at >= started_at)
            ),
            FOREIGN KEY (offline_event_id)
                REFERENCES visit_source_events(event_id) ON DELETE SET NULL
        );

        CREATE TABLE visit_authorizations (
            row_id INTEGER PRIMARY KEY,
            visit_id TEXT NOT NULL,
            auth_session_id TEXT NOT NULL
                CHECK (length(trim(auth_session_id)) > 0),
            auth_run_number INTEGER NOT NULL CHECK (auth_run_number > 0),
            authorization_attempt INTEGER CHECK (
                authorization_attempt IS NULL OR authorization_attempt >= 0
            ),
            authorized_at TEXT NOT NULL CHECK {_utc_check('authorized_at')},
            final_reason TEXT NOT NULL CHECK (length(trim(final_reason)) > 0),
            client_ip TEXT,
            portal_ssid TEXT,
            portal_ap_mac TEXT CHECK (
                portal_ap_mac IS NULL OR length(portal_ap_mac) = 17
            ),
            portal_radio_id INTEGER CHECK (
                portal_radio_id IS NULL OR portal_radio_id >= 0
            ),
            created_at TEXT NOT NULL CHECK {_utc_check('created_at')},
            UNIQUE (auth_session_id, auth_run_number),
            FOREIGN KEY (visit_id) REFERENCES visits(visit_id) ON DELETE CASCADE
        );

        CREATE TABLE visit_source_events (
            event_id TEXT PRIMARY KEY,
            event_type TEXT NOT NULL CHECK (length(trim(event_type)) > 0),
            site_id TEXT,
            client_mac TEXT CHECK (
                client_mac IS NULL OR length(client_mac) = 17
            ),
            controller_event_at TEXT
                CHECK {_utc_check('controller_event_at', nullable=True)},
            received_at TEXT CHECK {_utc_check('received_at', nullable=True)},
            source_identity TEXT NOT NULL
                CHECK (length(trim(source_identity)) > 0),
            source_offset_start INTEGER NOT NULL
                CHECK (source_offset_start >= 0),
            source_offset_end INTEGER NOT NULL
                CHECK (source_offset_end >= source_offset_start),
            processing_result TEXT NOT NULL CHECK (
                processing_result IN (
                    'pending_match', 'closed', 'unmatched', 'invalid'
                )
            ),
            visit_id TEXT,
            reason TEXT,
            first_processed_at TEXT NOT NULL
                CHECK {_utc_check('first_processed_at')},
            processed_at TEXT NOT NULL CHECK {_utc_check('processed_at')},
            pending_until TEXT CHECK {_utc_check('pending_until', nullable=True)},
            last_match_attempt_at TEXT
                CHECK {_utc_check('last_match_attempt_at', nullable=True)},
            CHECK (
                processing_result != 'pending_match'
                OR pending_until IS NOT NULL
            ),
            FOREIGN KEY (visit_id) REFERENCES visits(visit_id) ON DELETE SET NULL
        );

        CREATE TABLE visit_reader_state (
            source_identity TEXT PRIMARY KEY,
            source_path TEXT NOT NULL CHECK (length(trim(source_path)) > 0),
            source_offset INTEGER NOT NULL CHECK (source_offset >= 0),
            last_observed_size INTEGER CHECK (
                last_observed_size IS NULL OR last_observed_size >= 0
            ),
            checkpoint_offset INTEGER CHECK (
                checkpoint_offset IS NULL OR checkpoint_offset >= 0
            ),
            checkpoint_length INTEGER CHECK (
                checkpoint_length IS NULL OR checkpoint_length >= 0
            ),
            checkpoint_sha256 TEXT CHECK (
                checkpoint_sha256 IS NULL OR length(checkpoint_sha256) = 64
            ),
            retired_completed INTEGER NOT NULL DEFAULT 0
                CHECK (retired_completed IN (0, 1)),
            missing_warning_emitted INTEGER NOT NULL DEFAULT 0
                CHECK (missing_warning_emitted IN (0, 1)),
            updated_at TEXT NOT NULL CHECK {_utc_check('updated_at')},
            CHECK (
                (checkpoint_offset IS NULL
                 AND checkpoint_length IS NULL
                 AND checkpoint_sha256 IS NULL)
                OR
                (checkpoint_offset IS NOT NULL
                 AND checkpoint_length IS NOT NULL
                 AND checkpoint_sha256 IS NOT NULL)
            )
        );

        CREATE TRIGGER trg_visits_start_evidence_immutable
        BEFORE UPDATE OF
            start_auth_session_id,
            start_auth_run_number,
            start_final_reason,
            started_at
        ON visits
        WHEN
            NEW.start_auth_session_id != OLD.start_auth_session_id
            OR NEW.start_auth_run_number != OLD.start_auth_run_number
            OR NEW.start_final_reason != OLD.start_final_reason
            OR NEW.started_at != OLD.started_at
        BEGIN
            SELECT RAISE(ABORT, 'visit start evidence is immutable');
        END;

        CREATE UNIQUE INDEX uq_visits_open_site_mac
            ON visits(site_id, client_mac) WHERE status = 'open';
        CREATE INDEX idx_visits_site_started
            ON visits(site_id, started_at, visit_id);
        CREATE INDEX idx_visits_site_closed
            ON visits(site_id, closed_at, visit_id);
        CREATE INDEX idx_visits_site_mac_started
            ON visits(site_id, client_mac, started_at, visit_id);
        CREATE INDEX idx_visits_site_device_started
            ON visits(site_id, device_id, started_at, visit_id);
        CREATE INDEX idx_visits_site_status_started
            ON visits(site_id, status, started_at, visit_id);
        CREATE INDEX idx_visits_site_start_ssid
            ON visits(site_id, start_ssid, started_at, visit_id);
        CREATE INDEX idx_visits_site_final_ssid
            ON visits(site_id, final_ssid, started_at, visit_id);
        CREATE INDEX idx_visits_site_start_ap
            ON visits(site_id, start_ap_mac, started_at, visit_id);
        CREATE INDEX idx_visits_site_final_ap
            ON visits(site_id, final_ap_mac, started_at, visit_id);
        CREATE INDEX idx_visit_auth_visit_time
            ON visit_authorizations(visit_id, authorized_at, row_id);
        CREATE INDEX idx_visit_auth_visit_ssid
            ON visit_authorizations(visit_id, portal_ssid);
        CREATE INDEX idx_visit_auth_visit_ap
            ON visit_authorizations(visit_id, portal_ap_mac);
        CREATE INDEX idx_visit_events_site_controller
            ON visit_source_events(site_id, controller_event_at, event_id);
        CREATE INDEX idx_visit_events_site_processed
            ON visit_source_events(site_id, processed_at, event_id);
        CREATE INDEX idx_visit_events_result_processed
            ON visit_source_events(processing_result, processed_at);
        CREATE INDEX idx_visit_events_source_offsets
            ON visit_source_events(
                source_identity, source_offset_start, source_offset_end
            );
        CREATE INDEX idx_visits_reconcile_due
            ON visits(link_reconcile_next_at, started_at, visit_id)
            WHERE device_id IS NULL OR initial_snapshot_id IS NULL;

        PRAGMA user_version = 1;
        COMMIT;
    """


def _schema_sql_v2() -> str:
    legacy = _schema_sql_v1()
    final_marker = "        PRAGMA user_version = 1;\n        COMMIT;"
    if legacy.count(final_marker) != 1:
        raise RuntimeError("Visit schema v1 final marker is not unique")
    migration = "\n".join(
        f"        {statement.strip()};"
        for statement in MIGRATION_V1_TO_V2_STATEMENTS
    )
    return legacy.replace(
        final_marker,
        f"{migration}\n        PRAGMA user_version = 2;\n        COMMIT;",
    )


PROTOCOL_SUMMARY_DDL = """CREATE TABLE visit_network_protocol_summary (
    visit_id TEXT PRIMARY KEY REFERENCES visits(visit_id) ON DELETE CASCADE,
    summary_version INTEGER NOT NULL CHECK(summary_version=1),
    site_id TEXT NOT NULL, client_mac TEXT NOT NULL, device_id TEXT,
    visit_guard TEXT NOT NULL, visit_started_at TEXT NOT NULL, snapshot_id TEXT, binding_confirmed_at TEXT,
    dns_at TEXT, dns_edge TEXT, tls_at TEXT, tls_edge TEXT, quic_at TEXT, quic_edge TEXT,
    summary_state TEXT NOT NULL CHECK(summary_state IN ('pending','partial','active','unavailable','finalized')),
    source_coverage TEXT NOT NULL CHECK(source_coverage IN ('unknown','bounded_partial','unavailable')),
    attribution_coverage TEXT NOT NULL CHECK(attribution_coverage IN ('unknown','current_available','limited')),
    partial_reason TEXT NOT NULL CHECK(partial_reason IN ('identity_unconfirmed','source_unavailable',
        'no_confirmed_observation','late_unresolved','bounded_source','grace_elapsed_partial')),
    evaluated_at TEXT NOT NULL, finalized_at TEXT,
    CHECK((dns_at IS NULL)=(dns_edge IS NULL)), CHECK((tls_at IS NULL)=(tls_edge IS NULL)),
    CHECK((quic_at IS NULL)=(quic_edge IS NULL)),
    CHECK((summary_state='finalized')=(finalized_at IS NOT NULL)))"""


def _schema_sql_v3():
    return _schema_sql_v2().replace('        PRAGMA user_version = 2;\n        COMMIT;',
        PROTOCOL_SUMMARY_DDL + ';\n        PRAGMA user_version = 3;\n        COMMIT;')


SERVICE_HISTORY_DDL = (
    """CREATE TABLE visit_service_membership (
        fact_key TEXT PRIMARY KEY,site_id TEXT NOT NULL,device_id TEXT NOT NULL,client_mac TEXT NOT NULL,
        edge_id TEXT NOT NULL,service_id TEXT NOT NULL,observed_at TEXT NOT NULL,
        generation_id TEXT NOT NULL,source_ref TEXT NOT NULL,source_observation_id TEXT NOT NULL,
        binding_seq INTEGER NOT NULL CHECK(binding_seq>0),taxonomy_id TEXT NOT NULL,taxonomy_version INTEGER NOT NULL,
        taxonomy_digest TEXT NOT NULL,ruleset_id TEXT NOT NULL,ruleset_version INTEGER NOT NULL,ruleset_digest TEXT NOT NULL,
        rule_id TEXT NOT NULL,service_label TEXT NOT NULL,organization_id TEXT NOT NULL,organization_label TEXT NOT NULL,category_id TEXT NOT NULL,
        visit_id TEXT REFERENCES visits(visit_id) ON DELETE CASCADE,visit_guard TEXT,
        status TEXT NOT NULL CHECK(status IN ('pending','provisional','confirmed','ambiguous','invalidated','expired')),
        reason TEXT NOT NULL CHECK(reason IN ('identity_pending','unique_visit','visit_revision','lineage_pending','binding_changed','conflicting_fact','future_event','no_visit','sealed_visit','pending_expired')),
        created_at TEXT NOT NULL,updated_at TEXT NOT NULL,last_outbox_seq INTEGER NOT NULL CHECK(last_outbox_seq>0),
        finalized_at TEXT,CHECK((visit_id IS NULL)=(visit_guard IS NULL)),UNIQUE(site_id,edge_id,service_id))""",
    'CREATE INDEX idx_visit_service_match ON visit_service_membership(site_id,device_id,client_mac,observed_at,fact_key)',
    'CREATE INDEX idx_visit_service_rollup ON visit_service_membership(visit_id,service_id,status,observed_at,fact_key)',
    'CREATE INDEX idx_visit_service_pending ON visit_service_membership(finalized_at,status,updated_at,fact_key)',
    'CREATE INDEX idx_visit_service_generation ON visit_service_membership(generation_id,finalized_at,status,fact_key)',
    'CREATE INDEX idx_visit_service_unsealed ON visit_service_membership(visit_id,service_id,finalized_at,fact_key)',
    """CREATE TABLE visit_service_summary (
        site_id TEXT NOT NULL,visit_id TEXT NOT NULL REFERENCES visits(visit_id) ON DELETE CASCADE,service_id TEXT NOT NULL,
        device_id TEXT NOT NULL,visit_guard TEXT NOT NULL,generation_id TEXT NOT NULL,service_label TEXT NOT NULL,
        organization_id TEXT NOT NULL,organization_label TEXT NOT NULL,
        first_observed_at TEXT NOT NULL,last_observed_at TEXT NOT NULL,
        distinct_observation_count INTEGER NOT NULL CHECK(distinct_observation_count>0),
        taxonomy_id TEXT NOT NULL,taxonomy_version INTEGER NOT NULL,taxonomy_digest TEXT NOT NULL,
        ruleset_id TEXT NOT NULL,ruleset_version INTEGER NOT NULL,ruleset_digest TEXT NOT NULL,
        status TEXT NOT NULL CHECK(status IN ('processing','confirmed','incomplete')),
        updated_at TEXT NOT NULL,finalized_at TEXT,
        PRIMARY KEY(site_id,visit_id,service_id))""",
    """CREATE TABLE visit_service_consumer_state (
        singleton_id INTEGER PRIMARY KEY CHECK(singleton_id=1),consumer_id TEXT NOT NULL,
        source_stream_id TEXT NOT NULL,last_outbox_seq INTEGER NOT NULL CHECK(last_outbox_seq>=0),last_outbox_hash TEXT NOT NULL,
        active_generation_id TEXT,source_head_seq INTEGER NOT NULL CHECK(source_head_seq>=last_outbox_seq),
        history_ttl_days INTEGER NOT NULL CHECK(history_ttl_days BETWEEN 1 AND 365),
        status TEXT NOT NULL CHECK(status IN ('processing','incomplete','unavailable')),
        safe_reason TEXT NOT NULL CHECK(safe_reason IN ('backfill_limited','source_unavailable','checkpoint_conflict')),
        updated_at TEXT NOT NULL)""",
)


def _schema_sql_v4():
    return _schema_sql_v3().replace('        PRAGMA user_version = 3;\n        COMMIT;',
        ';\n'.join(SERVICE_HISTORY_DDL) + ';\n        PRAGMA user_version = 4;\n        COMMIT;')


SERVICE_CONSUMER_V5_DDL = SERVICE_HISTORY_DDL[-1].replace(
    '        history_ttl_days INTEGER NOT NULL CHECK(history_ttl_days BETWEEN 1 AND 365),\n',
    '        detached_count INTEGER NOT NULL CHECK(detached_count>=0),\n')
SERVICE_PENDING_V5_DDL = (
    'ALTER TABLE visit_service_membership ADD COLUMN pending_since TEXT',
    'ALTER TABLE visit_service_membership ADD COLUMN linkage_attached_at TEXT',
    'CREATE INDEX idx_visit_service_detached_expiry ON visit_service_membership(pending_since,fact_key) '
    "WHERE visit_id IS NULL AND status<>'expired'",
    'CREATE INDEX idx_visit_service_review ON visit_service_membership(fact_key) '
    "WHERE finalized_at IS NULL AND status NOT IN ('invalidated','expired','ambiguous')",
)
NI04_UNATTACHED_PENDING_TTL_SECONDS = 3600
SERVICE_DETACHED_CAPACITY = 100000


def _schema_sql_v5():
    return _schema_sql_v4().replace(SERVICE_HISTORY_DDL[-1], SERVICE_CONSUMER_V5_DDL).replace(
        '        PRAGMA user_version = 4;\n        COMMIT;',
        ';\n'.join(SERVICE_PENDING_V5_DDL) + ';\n        PRAGMA user_version = 5;\n        COMMIT;')


SERVICE_PENDING_V6_DDL = (
    'ALTER TABLE visit_service_consumer_state ADD COLUMN first_credit_floor_utc TEXT',
    'DROP INDEX idx_visit_service_detached_expiry',
    'CREATE INDEX idx_visit_service_detached_expiry ON visit_service_membership(pending_since,fact_key) '
    'WHERE visit_id IS NULL',
)


def _schema_sql_v6():
    return _schema_sql_v5().replace('        PRAGMA user_version = 5;\n        COMMIT;',
        ';\n'.join(SERVICE_PENDING_V6_DDL) + ';\n        PRAGMA user_version = 6;\n        COMMIT;')


def expected_visit_signature(version):
    """An explicit schema for each supported revision; never a >= predicate."""
    builders = {2: _schema_sql_v2, 3: _schema_sql_v3, 4: _schema_sql_v4, 5: _schema_sql_v5, 6: _schema_sql_v6}
    if type(version) is not int or version not in builders:
        raise VisitSchemaError('Unsupported Visit schema version')
    with closing(sqlite3.connect(':memory:')) as connection:
        connection.executescript(builders[version]())
        return _schema_signature(connection)


class VisitRepository:
    """Own Visit schema v6 and short serialized write transactions."""

    def __init__(
        self,
        config: VisitLifecycleConfig,
        *,
        busy_timeout_ms: int | None = None,
        write_coordinator: PriorityWriteCoordinator | None = None,
        migration_clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ):
        self.config = config
        self.db_path = Path(config.db_path)
        self._service_review_after = None
        self._migration_clock = migration_clock
        sqlite_timeout = (
            config.sqlite_busy_timeout_ms
            if busy_timeout_ms is None
            else busy_timeout_ms
        )
        self.sqlite_busy_timeout_ms = max(
            1,
            min(int(sqlite_timeout), 60_000),
        )
        self._write_coordinator = (
            write_coordinator or PriorityWriteCoordinator()
        )

    @startup_check('visits',lambda self:self.db_path,
        ('schema_version','schema_signature','quick_check','foreign_key_check'),failures=(VisitSchemaError,))
    def initialize(self) -> bool:
        self._ensure_parent()
        existed = self._database_exists()
        created = False
        try:
            with self._bounded_write(WRITE_OPERATION_STARTUP) as lease, closing(
                self._connect()
            ) as connection:
                version = int(connection.execute("PRAGMA user_version").fetchone()[0])
                if version > SCHEMA_VERSION:
                    raise VisitSchemaError("Visit schema is newer than this code")
                if version == 0:
                    if self._user_schema_objects(connection):
                        raise VisitSchemaError(
                            "Visit schema version 0 is non-empty"
                        )
                    connection.executescript(_schema_sql_v6())
                    created = True
                elif version == 1:
                    self._migrate_v1_to_v2(connection)
                    version = 2
                elif version not in (2, 3, 4, 5, 6):
                    raise VisitSchemaError(
                        f"Unsupported Visit schema version: {version}"
                    )
                if version == 2:
                    self._migrate_protocol_summary(connection)
                    version = 3
                if version == 3:
                    self._migrate_service_history(connection)
                    version = 4
                if version in (4, 5):
                    self._migrate_service_lifetime(connection)
                self._startup_check(connection)
                if os.name == "posix":
                    os.chmod(self.db_path, 0o640)
                lease.mark_progress()
        except VisitSchemaError:
            raise
        except sqlite3.Error as exc:
            raise _storage_error(exc, operation=WRITE_OPERATION_STARTUP) from exc
        except OSError as exc:
            raise VisitStorageError(VisitStorageCategory.UNAVAILABLE) from exc
        if not existed and not created:
            raise VisitSchemaError("Visit database creation did not complete")
        return created

    def _migrate_v1_to_v2(
        self,
        connection: sqlite3.Connection,
    ) -> None:
        connection.execute("BEGIN IMMEDIATE")
        try:
            quick = connection.execute("PRAGMA quick_check").fetchone()
            if not quick or str(quick[0]) != "ok":
                raise VisitSchemaError(
                    "Visit schema v1 health check failed"
                )
            if _schema_signature(connection) != _expected_v1_signature():
                raise VisitSchemaError(
                    "Visit schema v1 does not match the exact contract"
                )
            pending = int(connection.execute(
                "SELECT COUNT(*) FROM visit_source_events "
                "WHERE processing_result='pending_match'"
            ).fetchone()[0])
            if pending:
                raise VisitSchemaError(
                    "Visit schema v1 contains pending offline evidence"
                )
            for statement in MIGRATION_V1_TO_V2_STATEMENTS:
                connection.execute(statement)
            connection.execute("PRAGMA user_version = 2")
            if _schema_signature(connection) != _expected_v2_signature():
                raise VisitSchemaError('Visit v1 migration did not produce exact v2')
            connection.commit()
        except Exception:
            connection.rollback()
            raise

    def _migrate_protocol_summary(self, connection):
        connection.execute('BEGIN IMMEDIATE')
        try:
            if _schema_signature(connection) != expected_visit_signature(2):
                raise VisitSchemaError('Visit v2 migration source schema mismatch')
            if connection.execute('PRAGMA quick_check').fetchone()[0] != 'ok' or connection.execute('PRAGMA foreign_key_check').fetchone():
                raise VisitSchemaError('Visit v2 migration source failed validation')
            connection.execute(PROTOCOL_SUMMARY_DDL)
            connection.execute('PRAGMA user_version=3')
            if _schema_signature(connection)!=expected_visit_signature(3) or connection.execute('PRAGMA foreign_key_check').fetchone():
                raise VisitSchemaError('Visit v3 migration output invalid')
            connection.commit()
        except BaseException:
            connection.rollback()
            raise

    def _migrate_service_history(self, connection):
        connection.execute('BEGIN IMMEDIATE')
        try:
            if _schema_signature(connection)!=expected_visit_signature(3) or connection.execute('PRAGMA quick_check').fetchone()[0]!='ok' or connection.execute('PRAGMA foreign_key_check').fetchone():
                raise VisitSchemaError('Visit v3 migration source failed validation')
            for statement in SERVICE_HISTORY_DDL:connection.execute(statement)
            connection.execute('PRAGMA user_version=4')
            if _schema_signature(connection)!=expected_visit_signature(4):
                raise VisitSchemaError('Visit v4 migration output invalid')
            connection.commit()
        except BaseException:
            connection.rollback()
            raise

    def _migrate_service_lifetime(self, connection):
        """Exact V4/V5 -> V6: fence + unlinked-only cutover, ONE commit.

        No source DB is opened or acknowledged here. Linked parent-owned rows,
        summaries and the complete stream checkpoint survive byte-for-byte.
        """
        from app.network_metadata.validation import ni_timestamp, ni_format_utc, canonical_uuid, digest, integer
        connection.execute('BEGIN IMMEDIATE')
        try:
            version=connection.execute('PRAGMA user_version').fetchone()[0]
            if (version not in (4,5) or _schema_signature(connection)!=expected_visit_signature(version)
                    or connection.execute('PRAGMA quick_check').fetchone()[0]!='ok'
                    or connection.execute('PRAGMA foreign_key_check').fetchone()):
                raise VisitSchemaError('Visit lifetime migration source failed validation')
            old = connection.execute('SELECT * FROM visit_service_consumer_state').fetchone()
            detached=connection.execute('SELECT count(*) FROM visit_service_membership WHERE visit_id IS NULL').fetchone()[0]
            if old is None and connection.execute('SELECT 1 FROM visit_service_membership LIMIT 1').fetchone():
                raise VisitSchemaError('Visit history has no durable consumer checkpoint')
            if old is not None:
                canonical_uuid(old['consumer_id']);canonical_uuid(old['source_stream_id'])
                integer(old['last_outbox_seq']);integer(old['source_head_seq'],old['last_outbox_seq'])
                digest(old['last_outbox_hash'])
                if version==5 and old['detached_count']!=detached:
                    raise VisitSchemaError('Visit detached count mismatch at cutover')
            # A future/corrupt legacy event must not silently push the floor
            # forward. Startup migration may scan legacy staging; routine GC
            # below never does. No rows are changed until this check completes.
            cutover=ni_format_utc(self._migration_clock())
            instant=ni_timestamp(cutover,canonical=True)
            for row in connection.execute('SELECT * FROM visit_service_membership WHERE visit_id IS NULL'):
                try:
                    event=ni_timestamp(row['observed_at'],canonical=True)
                    if event>instant or self._service_fact_key(row)!=row['fact_key']:raise ValueError
                    if version==5:self._pending_clock(dict(row),cutover)
                except Exception:
                    raise VisitSchemaError('Visit cutover has invalid or future detached provenance') from None
            if version==4:
                for statement in SERVICE_PENDING_V5_DDL:connection.execute(statement)
                # V4 lacks a first-staging clock. Preserve the conservative
                # earliest durable clock for linked rows, never give a new hour.
                connection.execute('UPDATE visit_service_membership SET pending_since=created_at')
                connection.execute('UPDATE visit_service_membership SET linkage_attached_at=created_at WHERE visit_id IS NOT NULL')
                connection.execute('DROP TABLE visit_service_consumer_state')
                connection.execute(SERVICE_CONSUMER_V5_DDL)
                if old is not None:
                    values={k:old[k] for k in old.keys() if k!='history_ttl_days'}
                    values['detached_count']=detached
                    connection.execute('INSERT INTO visit_service_consumer_state('+','.join(values)+') VALUES('
                        +','.join('?' for _ in values)+')',tuple(values.values()))
            for statement in SERVICE_PENDING_V6_DDL:connection.execute(statement)
            if detached:
                connection.execute('UPDATE visit_service_consumer_state SET first_credit_floor_utc=?,detached_count=0 WHERE singleton_id=1',(cutover,))
                connection.execute('DELETE FROM visit_service_membership WHERE visit_id IS NULL')
            connection.execute('PRAGMA user_version=6')
            self._startup_check(connection)
            connection.commit()
        except BaseException:
            connection.rollback()
            raise

    def create_or_reuse_start(
        self,
        start: NormalizedVisitStart,
        *,
        now_utc: str,
        deadline: float | None = None,
        cancel_event: threading.Event | None = None,
    ) -> VisitStartOutcome:
        lock_wait_ms = 0
        try:
            with self._bounded_write(
                WRITE_OPERATION_START,
                deadline=deadline,
                cancel_event=cancel_event,
            ) as lease, closing(self._connect(
                busy_timeout_ms=self._remaining_sqlite_timeout_ms(deadline),
            )) as connection:
                lock_wait_ms = lease.lock_wait_ms
                connection.execute("BEGIN IMMEDIATE")
                existing = connection.execute(
                    """
                    SELECT a.visit_id
                    FROM visit_authorizations AS a
                    WHERE a.auth_session_id = ? AND a.auth_run_number = ?
                    """,
                    (start.auth_session_id, start.auth_run_number),
                ).fetchone()
                if existing is not None:
                    connection.commit()
                    return VisitStartOutcome(
                        status="duplicate",
                        visit_id=str(existing["visit_id"]),
                    )

                row = connection.execute(
                    """
                    SELECT visit_id
                    FROM visits
                    WHERE site_id = ? AND client_mac = ? AND status = 'open'
                    """,
                    (start.site_id, start.client_mac),
                ).fetchone()
                created = row is None
                if created:
                    visit_id = str(uuid.uuid4())
                    connection.execute(
                        """
                        INSERT INTO visits (
                            visit_id, site_id, client_mac,
                            start_auth_session_id, start_auth_run_number,
                            start_final_reason, started_at, status,
                            start_ip, start_ssid, start_ap_mac,
                            created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, 'open', ?, ?, ?, ?, ?)
                        """,
                        (
                            visit_id,
                            start.site_id,
                            start.client_mac,
                            start.auth_session_id,
                            start.auth_run_number,
                            start.final_reason,
                            start.authorized_at,
                            start.client_ip,
                            start.portal_ssid,
                            start.portal_ap_mac,
                            now_utc,
                            now_utc,
                        ),
                    )
                else:
                    visit_id = str(row["visit_id"])
                connection.execute(
                    """
                    INSERT INTO visit_authorizations (
                        visit_id, auth_session_id, auth_run_number,
                        authorization_attempt, authorized_at, final_reason,
                        client_ip, portal_ssid, portal_ap_mac,
                        portal_radio_id, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        visit_id,
                        start.auth_session_id,
                        start.auth_run_number,
                        start.authorization_attempt,
                        start.authorized_at,
                        start.final_reason,
                        start.client_ip,
                        start.portal_ssid,
                        start.portal_ap_mac,
                        start.portal_radio_id,
                        now_utc,
                    ),
                )
                connection.commit()
                return VisitStartOutcome(
                    status="opened" if created else "reused",
                    visit_id=visit_id,
                    created=created,
                    authorization_attached=True,
                )
        except sqlite3.Error as exc:
            raise _storage_error(
                exc,
                operation=WRITE_OPERATION_START,
                lock_wait_ms=lock_wait_ms,
            ) from exc

    def wake_write_waiters(self) -> None:
        self._write_coordinator.wake_all()

    def protocol_candidates(self, now, *, after=None, limit=25, deadline=None):
        """Bounded fair page, only OPEN/recent provisional; no historic backfill."""
        if type(limit) is not int or not 1 <= limit <= BACKGROUND_CHUNK_MAX_ITEMS:
            raise ValueError('Invalid protocol batch bound')
        cutoff = _add_seconds(now, -900)
        with self.read_connection() as c:
            if deadline is not None:
                c.set_progress_handler(lambda: int(time.monotonic() >= deadline), 100)
            try:
                rows = c.execute("SELECT v.* FROM visits v LEFT JOIN visit_network_protocol_summary s ON s.visit_id=v.visit_id "
                    "WHERE v.visit_id>? AND (v.status='open' OR v.closed_at>=? OR s.visit_id IS NOT NULL) "
                    "AND s.finalized_at IS NULL ORDER BY v.visit_id LIMIT ?", (after or '', cutoff, limit)).fetchall()
                return tuple(_visit_row(row) for row in rows)
            finally:
                c.set_progress_handler(None, 0)

    def saved_protocol_summary(self, visit):
        with self.read_connection() as c:
            row = c.execute('SELECT * FROM visit_network_protocol_summary WHERE visit_id=?', (visit.visit_id,)).fetchone()
            return None if row is None else dict(row)

    def service_consumer_cursor(self):
        with self.read_connection() as c:
            row=c.execute('SELECT * FROM visit_service_consumer_state WHERE singleton_id=1').fetchone()
            return None if row is None else dict(row)

    def service_delivery_unavailable(self, *, now, deadline, conflict=False):
        # Persist one transition, not a heartbeat/error write every idle pass.
        old=self.service_consumer_cursor()
        reason='checkpoint_conflict' if conflict else 'source_unavailable'
        if old is None or old['status']=='unavailable' and old['safe_reason']==reason:return
        with self._bounded_write(WRITE_OPERATION_RECONCILIATION,deadline=deadline) as lease,closing(
                self._connect(busy_timeout_ms=1)) as c:
            c.execute('BEGIN IMMEDIATE')
            c.execute("UPDATE visit_service_consumer_state SET status='unavailable',safe_reason=?,updated_at=? WHERE singleton_id=1 AND last_outbox_seq=? AND last_outbox_hash=?",
                (reason,now,old['last_outbox_seq'],old['last_outbox_hash']))
            c.commit();lease.mark_progress()

    @staticmethod
    def _service_fact_key(row):
        import hashlib,json
        return hashlib.sha256(json.dumps([row['site_id'],row['edge_id'],row['service_id']],separators=(',',':')).encode()).hexdigest()

    @staticmethod
    def _service_credit(row):
        return row is not None and row['visit_id'] is not None and row['status'] in ('provisional','confirmed')

    @staticmethod
    def _pending_clock(row,now):
        """Persisted P must be canonical, non-future, and no earlier than E."""
        from .models import normalize_utc
        from app.network_metadata.validation import ni_timestamp
        value=row.get('pending_since')
        if value is None:raise VisitSchemaError('Visit pending clock missing')
        if normalize_utc(value,'pending_since')!=value:
            raise VisitSchemaError('Visit pending clock invalid')
        first=datetime.fromisoformat(value.replace('Z','+00:00'))
        instant=datetime.fromisoformat(now.replace('Z','+00:00'))
        if first>instant or ni_timestamp(row['observed_at'],canonical=True)>first:
            raise VisitSchemaError('Visit pending clock contradicts original event')
        return first

    def _gc_service_pending(self,c,now,floor,hold,cancel_event,transitions,capacity):
        """One indexed physical batch. No permanent per-key rejection guards."""
        from app.network_metadata.validation import ni_timestamp
        cutoff=_add_seconds(now,-NI04_UNATTACHED_PENDING_TTL_SECONDS)
        boundary=datetime.fromisoformat(cutoff.replace('Z','+00:00'))
        fence=ni_timestamp(floor,canonical=True) if floor is not None else None
        rows=c.execute('SELECT * FROM visit_service_membership INDEXED BY idx_visit_service_detached_expiry '
            'WHERE visit_id IS NULL AND pending_since<=? ORDER BY pending_since,fact_key LIMIT 25',(cutoff,)).fetchall()
        changed=0
        for raw in rows:
            if time.monotonic()>=hold or cancel_event is not None and cancel_event.is_set():break
            old=dict(raw);self._pending_clock(old,now)
            if self._service_fact_key(old)!=old['fact_key']:
                raise VisitSchemaError('Visit detached canonical identity invalid')
            event=ni_timestamp(old['observed_at'],canonical=True)
            if event>boundary and (fence is None or event>fence):continue
            c.execute('DELETE FROM visit_service_membership WHERE fact_key=? AND visit_id IS NULL',(old['fact_key'],))
            capacity[0]-=1
            if capacity[0]<0:raise VisitSchemaError('Visit service detached count invariant failed')
            # Ephemeral committed-transition evidence, NOT a persisted tombstone.
            first=transitions.get(old['fact_key'],(old,None))[0]
            transitions[old['fact_key']]=(first,dict(old,status='expired',reason='pending_expired',updated_at=now))
            changed+=1
        return changed

    def _service_association(self,c,row,now,active):
        """At most two real event-time candidates; no current-MAC substitution."""
        from app.network_metadata.validation import ni_timestamp
        event=ni_timestamp(row['observed_at'],canonical=True)
        current=datetime.fromisoformat(now.replace('Z','+00:00'))
        if event>current:raise VisitSchemaError('Visit service future event')
        if row.get('visit_id') is None and ('status' in row or row.get('pending_since') is not None):
            first=self._pending_clock(row,now)
            if row.get('status')=='expired' or (current-first).total_seconds()>=NI04_UNATTACHED_PENDING_TTL_SECONDS:
                return None,'expired','pending_expired',now
        if row['generation_id']!=active:return None,'pending','lineage_pending',None
        floor=event.isoformat(timespec='milliseconds').replace('+00:00','Z')
        candidates=c.execute('SELECT * FROM visits WHERE site_id=? AND client_mac=? AND started_at<=? AND (closed_at IS NULL OR closed_at>?) ORDER BY started_at DESC LIMIT 2',
            (row['site_id'],row['client_mac'],floor,floor)).fetchall()
        if len(candidates)!=1:return None,'ambiguous' if candidates else 'pending','identity_pending' if candidates else 'no_visit',None
        visit=_visit_row(candidates[0])
        if visit.device_id!=row['device_id'] or visit.initial_snapshot_id is None:return None,'pending','identity_pending',None
        if visit.closed_at is not None and current>=datetime.fromisoformat(visit.closed_at.replace('Z','+00:00'))+timedelta(seconds=900):
            if row.get('visit_id')!=visit.visit_id:return None,'pending','sealed_visit',None
            return visit,'confirmed','unique_visit',now
        return visit,'confirmed' if visit.status=='closed' else 'provisional','unique_visit',None

    def _store_service_member(self,c,old,new,now,transitions,capacity):
        """Incremental count, bounded indexed first/last probes; no raw rescan."""
        if old is not None and old['visit_id'] is None and old['pending_since'] is None:
            raise VisitSchemaError('Visit pending clock missing')
        if new['visit_id'] is None:
            if new.get('pending_since') is None:new['pending_since']=now
            self._pending_clock(new,now)
            age=(datetime.fromisoformat(now.replace('Z','+00:00'))-
                datetime.fromisoformat(new['pending_since'].replace('Z','+00:00'))).total_seconds()
            if age<0 or age>=NI04_UNATTACHED_PENDING_TTL_SECONDS:
                new.update(status='expired',reason='pending_expired',finalized_at=now)
            if old is None or old['visit_id'] is not None:
                # Present in-flight rows only. Physical GC frees this capacity
                # in this same transaction before new source admission.
                if capacity[0]>=SERVICE_DETACHED_CAPACITY:
                    raise VisitSchemaError('Visit service detached capacity exhausted')
                capacity[0]+=1
        elif old is not None and old['visit_id'] is None and new.get('linkage_attached_at') is None:
            new['linkage_attached_at']=now
        if old is not None and old['visit_id'] is None and new['visit_id'] is not None:
            capacity[0]-=1
            if capacity[0]<0:raise VisitSchemaError('Visit service detached count invariant failed')
        first=transitions.get(new['fact_key'],(old,None))[0]
        transitions[new['fact_key']]=(first,dict(new))
        groups={}
        for member,sign in ((old,-1),(new,1)):
            if self._service_credit(member):
                key=(member['site_id'],member['visit_id'],member['service_id'])
                groups[key]=groups.get(key,0)+sign
        columns=tuple(new)
        c.execute('INSERT INTO visit_service_membership('+','.join(columns)+') VALUES('+','.join('?' for _ in columns)+') ON CONFLICT(fact_key) DO UPDATE SET '+
            ','.join(k+'=excluded.'+k for k in columns if k!='fact_key'),tuple(new.values()))
        for key,delta in groups.items():
            previous=c.execute('SELECT * FROM visit_service_summary WHERE site_id=? AND visit_id=? AND service_id=?',key).fetchone()
            count=(previous['distinct_observation_count'] if previous else 0)+delta
            if count<=0:
                c.execute('DELETE FROM visit_service_summary WHERE site_id=? AND visit_id=? AND service_id=?',key);continue
            bounds=[]
            for status in ('provisional','confirmed'):
                for order in ('ASC','DESC'):
                    value=c.execute('SELECT * FROM visit_service_membership WHERE visit_id=? AND service_id=? AND status=? ORDER BY observed_at '+order+',fact_key '+order+' LIMIT 1',
                        (key[1],key[2],status)).fetchone()
                    if value is not None:bounds.append(dict(value))
            if not bounds:raise VisitSchemaError('Visit service count invariant failed')
            first=min(r['observed_at'] for r in bounds);latest=max(bounds,key=lambda r:(r['observed_at'],r['fact_key']))
            visit=_visit_row(c.execute('SELECT * FROM visits WHERE visit_id=?',(key[1],)).fetchone())
            saved=dict(site_id=key[0],visit_id=key[1],service_id=key[2],device_id=visit.device_id,visit_guard=protocol_visit_guard(visit),
                generation_id=latest['generation_id'],service_label=latest['service_label'],organization_id=latest['organization_id'],organization_label=latest['organization_label'],
                first_observed_at=first,last_observed_at=latest['observed_at'],distinct_observation_count=count,
                **{k:latest[k] for k in ('taxonomy_id','taxonomy_version','taxonomy_digest','ruleset_id','ruleset_version','ruleset_digest')},
                status='processing' if visit.status=='open' else 'confirmed',updated_at=now,
                finalized_at=now if c.execute('SELECT 1 FROM visit_service_membership WHERE visit_id=? AND service_id=? AND finalized_at IS NULL LIMIT 1',
                    (key[1],key[2])).fetchone() is None else None)
            cols=tuple(saved)
            c.execute('INSERT INTO visit_service_summary('+','.join(cols)+') VALUES('+','.join('?' for _ in cols)+') ON CONFLICT(site_id,visit_id,service_id) DO UPDATE SET '+
                ','.join(k+'=excluded.'+k for k in cols if k not in ('site_id','visit_id','service_id')),tuple(saved.values()))

    def consume_service_delivery(self,page,expected_cursor,*,now,deadline,cancel_event=None,crash_point=lambda _:None,on_committed=lambda _:None):
        """Source snapshot already closed. Membership/rollup/checkpoint ONE commit."""
        import uuid
        from app.network_service_recognition.materialization_repository import MaterializationConflict
        if len(page['entries'])>25:raise ValueError('Invalid Visit history batch')
        with self._bounded_write(WRITE_OPERATION_RECONCILIATION,deadline=deadline,cancel_event=cancel_event) as lease, closing(
                self._connect(busy_timeout_ms=1)) as c:
            c.execute('BEGIN IMMEDIATE')
            hold=min(deadline,time.monotonic()+BACKGROUND_CHUNK_TARGET_MAX_HOLD_MS/1000)
            c.set_progress_handler(lambda:int(time.monotonic()>=hold or cancel_event is not None and cancel_event.is_set()),100)
            try:
                current=c.execute('SELECT * FROM visit_service_consumer_state WHERE singleton_id=1').fetchone()
                if (None if current is None else dict(current))!=expected_cursor:raise MaterializationConflict()
                if current is not None and current['source_stream_id']!=page['stream_id']:raise MaterializationConflict()
                seq,hashed=page['after_seq'],page['after_hash'];active=current['active_generation_id'] if current else None
                changed=0;reviewed=set();transitions={};capacity=[current['detached_count'] if current else 0]
                floor=current['first_credit_floor_utc'] if current else None
                from app.network_metadata.validation import ni_timestamp
                fence=ni_timestamp(floor,canonical=True) if floor is not None else None
                instant=datetime.fromisoformat(now.replace('Z','+00:00'))
                # Reclaim BEFORE admission, so a full but expired backlog does
                # not permanently block the next source entry. One batch/pass.
                changed+=self._gc_service_pending(c,now,floor,hold,cancel_event,transitions,capacity)
                for event in page['entries']:
                    if time.monotonic()>=hold:break
                    if event['kind'] in ('binding','generation'):
                        if event['kind']=='binding':
                            where='site_id=? AND client_mac=? AND binding_seq<? AND status<>?'
                            args=(event['site_id'],event['client_mac'],event['binding_seq'],'invalidated')
                        else:
                            where="generation_id<>? AND status IN ('provisional','confirmed')"
                            args=(event['generation_id'],)
                        affected=c.execute('SELECT * FROM visit_service_membership WHERE finalized_at IS NULL AND '+where+' ORDER BY fact_key LIMIT 25',args).fetchall()
                        for raw in affected:
                            old=dict(raw);new=dict(old,visit_id=None,visit_guard=None,status='invalidated' if event['kind']=='binding' else 'pending',
                                reason='binding_changed' if event['kind']=='binding' else 'lineage_pending',updated_at=now)
                            if event['kind']=='binding':new['binding_seq']=event['binding_seq']
                            self._store_service_member(c,old,new,now,transitions,capacity);reviewed.add(new['fact_key']);changed+=1
                        # Do not pass this marker until EVERY affected provisional
                        # row has been durably corrected, in bounded chunks.
                        if c.execute('SELECT 1 FROM visit_service_membership WHERE finalized_at IS NULL AND '+where+' LIMIT 1',args).fetchone():break
                        if event['kind']=='generation':active=event['generation_id']
                    else:
                        key=self._service_fact_key(event)
                        raw=c.execute('SELECT * FROM visit_service_membership WHERE fact_key=?',(key,)).fetchone()
                        old=None if raw is None else dict(raw)
                        observed=ni_timestamp(event['observed_at'],canonical=True)
                        if observed>instant:raise MaterializationConflict()
                        if old is not None and any(old[k]!=event[k] for k in ('observed_at','source_ref')):
                            raise MaterializationConflict()
                        if old is None and ((instant-observed).total_seconds()>=NI04_UNATTACHED_PENDING_TTL_SECONDS
                                or fence is not None and observed<=fence):
                            # Valid but no longer eligible FIRST delivery. Consume
                            # and checkpoint atomically; no membership/guard/TTL.
                            transitions[key+':discarded']=(None,dict(visit_id=None,status='discarded',reason='old_first_delivery'))
                        elif old is None or old['finalized_at'] is None:
                            fields=('site_id','device_id','client_mac','edge_id','service_id','observed_at','generation_id','source_ref','source_observation_id',
                                'binding_seq','taxonomy_id','taxonomy_version','taxonomy_digest','ruleset_id','ruleset_version','ruleset_digest','rule_id','service_label','organization_id','organization_label','category_id')
                            new={k:event[k] for k in fields}
                            new.update(fact_key=key,created_at=old['created_at'] if old else now,updated_at=now,last_outbox_seq=event['outbox_seq'],
                                visit_id=old['visit_id'] if old else None,visit_guard=old['visit_guard'] if old else None,finalized_at=None,
                                pending_since=old['pending_since'] if old else None,
                                linkage_attached_at=old['linkage_attached_at'] if old else None)
                            conflicts=old is not None and any(old[k]!=new[k] for k in ('site_id','device_id','client_mac','edge_id','service_id','observed_at','source_ref'))
                            if old is not None and old['binding_seq']>new['binding_seq']:
                                new=dict(old)  # Older replay cannot undo an authoritative correction.
                            elif conflicts:
                                new=dict(old,visit_id=None,visit_guard=None,status='ambiguous',reason='conflicting_fact',updated_at=now)
                            else:
                                visit,status,reason,finalized=self._service_association(c,new,now,page['active_generation'])
                                new.update(visit_id=visit.visit_id if visit else None,visit_guard=protocol_visit_guard(visit) if visit else None,
                                    status=status,reason=reason,finalized_at=finalized)
                            self._store_service_member(c,old,new,now,transitions,capacity);reviewed.add(key);changed+=1
                        # Sealed history never silently changes on late generations.
                    seq,hashed=event['outbox_seq'],event['entry_hash']
                    crash_point('visit_membership_applied' if event['kind']=='positive' else 'visit_marker_applied')
                # Fair, bounded correction of late Visit closure/binding and
                # previously staged missing identities; no source/raw rescan.
                rows=c.execute("SELECT * FROM visit_service_membership INDEXED BY idx_visit_service_review WHERE finalized_at IS NULL AND status NOT IN ('invalidated','expired','ambiguous') "
                    "AND fact_key>? ORDER BY fact_key LIMIT 25",(self._service_review_after or '',)).fetchall()
                if not rows and self._service_review_after is not None:
                    rows=c.execute("SELECT * FROM visit_service_membership INDEXED BY idx_visit_service_review WHERE finalized_at IS NULL AND status NOT IN ('invalidated','expired','ambiguous') ORDER BY fact_key LIMIT 25").fetchall()
                for raw in rows:
                    if time.monotonic()>=hold:break
                    old=dict(raw)
                    if old['fact_key'] in reviewed or old['reason']=='conflicting_fact':continue
                    visit,status,reason,finalized=self._service_association(c,old,now,page['active_generation'])
                    if visit is None and status=='expired':
                        # Eligibility is already denied by persisted P. The
                        # indexed GC owns deletion/expiry accounting; do not
                        # spend the priority-writer budget rewriting another
                        # batch into temporary tombstones before deleting it.
                        continue
                    new=dict(old,visit_id=visit.visit_id if visit else None,visit_guard=protocol_visit_guard(visit) if visit else None,
                        status=status,reason=reason,finalized_at=finalized)
                    if new!=old:
                        new['updated_at']=now;self._store_service_member(c,old,new,now,transitions,capacity);changed+=1
                target=dict(singleton_id=1,consumer_id=current['consumer_id'] if current else str(uuid.uuid4()),source_stream_id=page['stream_id'],
                    last_outbox_seq=seq,last_outbox_hash=hashed,active_generation_id=page['active_generation'],source_head_seq=page['head_seq'],
                    detached_count=capacity[0],first_credit_floor_utc=floor,
                    status='processing' if seq<page['head_seq'] else 'incomplete',safe_reason='backfill_limited',updated_at=now)
                source_age=(datetime.fromisoformat(now.replace('Z','+00:00'))-ni_timestamp(page['source_updated_at'],canonical=True)).total_seconds()
                if page['source_state'] in {'source_unavailable','recognition_unavailable','capacity_halted','blocked_conflict','stopping'} or not 0<=source_age<=300:
                    target.update(status='unavailable',safe_reason='source_unavailable')
                cp_changed=current is None or any(current[k]!=v for k,v in target.items() if k!='updated_at')
                if cp_changed:
                    cols=tuple(target)
                    c.execute('INSERT INTO visit_service_consumer_state('+','.join(cols)+') VALUES('+','.join('?' for _ in cols)+') ON CONFLICT(singleton_id) DO UPDATE SET '+
                        ','.join(k+'=excluded.'+k for k in cols if k!='singleton_id'),tuple(target.values()))
                crash_point('visit_checkpoint_applied')
                c.set_progress_handler(None,0)
                if changed or cp_changed:
                    if time.monotonic()>=deadline or cancel_event is not None and cancel_event.is_set():raise MaterializationConflict()
                    crash_point('visit_before_commit');c.commit();lease.mark_progress()
                    # Never publish rolled-back transitions. Process death in
                    # the commit/export gap is explicitly a telemetry gap.
                    try:on_committed(tuple(transitions.values()))
                    except Exception:pass
                    crash_point('visit_after_commit')
                else:c.rollback();lease.mark_no_work()
                self._service_review_after=rows[-1]['fact_key'] if rows else None
                return changed
            except BaseException:
                c.set_progress_handler(None,0)
                if c.in_transaction:c.rollback()
                raise

    def service_unresolved_sample(self, *, deadline):
        """Low-frequency bounded read, never a telemetry heartbeat write."""
        if time.monotonic()>=deadline:raise TimeoutError('Visit linkage sample deadline')
        with self.read_connection() as c:
            c.set_progress_handler(lambda:int(time.monotonic()>=deadline),100)
            try:
                return c.execute("SELECT count(*) FROM (SELECT 1 FROM visit_service_membership INDEXED BY idx_visit_service_detached_expiry "
                    "WHERE visit_id IS NULL AND status<>'expired' LIMIT ?)",
                    (SERVICE_DETACHED_CAPACITY+1,)).fetchone()[0]
            finally:c.set_progress_handler(None,0)

    @staticmethod
    def _protocol_bounds_clear(c, visit, end):
        return c.execute("SELECT 1 FROM visits WHERE site_id=? AND client_mac=? AND visit_id<>? "
            "AND started_at<? AND (closed_at IS NULL OR closed_at>?) LIMIT 1",
            (visit.site_id, visit.client_mac, visit.visit_id, end, visit.started_at)).fetchone() is None

    def protocol_bounds_clear(self, visit, end):
        with self.read_connection() as c:
            return self._protocol_bounds_clear(c, visit, end)

    def put_protocol_summaries(self, updates, *, deadline, cancel_event=None):
        """Source readers are closed. Existing priority lease, one short batch."""
        from .models import protocol_visit_guard
        if len(updates) > BACKGROUND_CHUNK_MAX_ITEMS:
            raise ValueError('Invalid protocol batch bound')
        # No idle BEGIN/COMMIT/WAL writes merely to refresh evaluated_at.
        changes = []
        for visit, value in updates:
            previous = self.saved_protocol_summary(visit)
            if previous is not None and all(previous[k] == v for k, v in value.items() if k != 'evaluated_at'):
                continue
            changes.append((visit, value))
        if not changes:
            return 0
        changed = 0
        try:
            with self._bounded_write(WRITE_OPERATION_RECONCILIATION, deadline=deadline, cancel_event=cancel_event) as lease, closing(
                    self._connect(busy_timeout_ms=1)) as c:
                c.execute('BEGIN IMMEDIATE')
                hold_deadline = min(deadline, time.monotonic()+BACKGROUND_CHUNK_TARGET_MAX_HOLD_MS/1000)
                for visit, value in changes:
                    if time.monotonic() >= hold_deadline or cancel_event is not None and cancel_event.is_set():
                        break
                    current = c.execute('SELECT * FROM visits WHERE visit_id=?', (visit.visit_id,)).fetchone()
                    if current is None or protocol_visit_guard(_visit_row(current)) != protocol_visit_guard(visit):
                        continue
                    if value['partial_reason'] != 'identity_unconfirmed' and not self._protocol_bounds_clear(
                            c, visit, visit.closed_at or value['evaluated_at']):
                        continue
                    old = c.execute('SELECT finalized_at FROM visit_network_protocol_summary WHERE visit_id=?', (visit.visit_id,)).fetchone()
                    if old is not None and old[0] is not None:
                        continue  # No silent correction of sealed historical cards.
                    columns = tuple(value)
                    sql = 'INSERT INTO visit_network_protocol_summary('+','.join(columns)+') VALUES('+','.join('?' for _ in columns)+')'
                    sql += ' ON CONFLICT(visit_id) DO UPDATE SET '+','.join(k+'=excluded.'+k for k in columns if k != 'visit_id')
                    c.execute(sql, tuple(value.values()))
                    changed += 1
                if changed:
                    c.commit(); lease.mark_progress()
                else:
                    c.rollback(); lease.mark_no_work()
        except sqlite3.Error as exc:
            raise _storage_error(exc, operation=WRITE_OPERATION_RECONCILIATION) from exc
        return changed

    def get_visit(self, site_id: str, visit_id: str) -> VisitRecord | None:
        with closing(self._connect(readonly=True)) as connection:
            row = connection.execute(
                "SELECT * FROM visits WHERE site_id = ? AND visit_id = ?",
                (site_id, visit_id),
            ).fetchone()
        return _visit_row(row) if row is not None else None

    @contextmanager
    def read_connection(self):
        """Yield a URI-mode read-only connection for bounded read services."""
        connection = self._connect(readonly=True)
        try:
            yield connection
        finally:
            connection.close()

    def get_open_visit(
        self,
        site_id: str,
        client_mac: str,
    ) -> VisitRecord | None:
        with closing(self._connect(readonly=True)) as connection:
            row = connection.execute(
                """
                SELECT * FROM visits
                WHERE site_id = ? AND client_mac = ? AND status = 'open'
                """,
                (site_id, client_mac),
            ).fetchone()
        return _visit_row(row) if row is not None else None

    def list_visit_rows(
        self,
        *,
        site_id: str,
        from_utc: str | None,
        to_utc: str | None,
        status: str | None,
        client_mac: str | None,
        device_id: str | None,
        ssid: str | None,
        ap_mac: str | None,
        cursor: tuple[str, str] | None,
        limit: int,
    ) -> list[VisitRecord]:
        clauses = ["v.site_id = ?"]
        params: list[Any] = [site_id]
        if from_utc is not None:
            clauses.append("(v.closed_at IS NULL OR v.closed_at > ?)")
            params.append(from_utc)
        if to_utc is not None:
            clauses.append("v.started_at < ?")
            params.append(to_utc)
        if status is not None:
            clauses.append("v.status = ?")
            params.append(status)
        if client_mac is not None:
            clauses.append("v.client_mac = ?")
            params.append(client_mac)
        if device_id is not None:
            clauses.append("v.device_id = ?")
            params.append(device_id)
        if ssid is not None:
            clauses.append(
                """(
                    v.start_ssid = ? OR v.final_ssid = ? OR EXISTS (
                        SELECT 1 FROM visit_authorizations AS a
                        WHERE a.visit_id = v.visit_id AND a.portal_ssid = ?
                    )
                )"""
            )
            params.extend((ssid, ssid, ssid))
        if ap_mac is not None:
            clauses.append(
                """(
                    v.start_ap_mac = ? OR v.final_ap_mac = ? OR EXISTS (
                        SELECT 1 FROM visit_authorizations AS a
                        WHERE a.visit_id = v.visit_id AND a.portal_ap_mac = ?
                    )
                )"""
            )
            params.extend((ap_mac, ap_mac, ap_mac))
        if cursor is not None:
            clauses.append(
                "(v.started_at < ? OR (v.started_at = ? AND v.visit_id < ?))"
            )
            params.extend((cursor[0], cursor[0], cursor[1]))
        params.append(limit)
        with closing(self._connect(readonly=True)) as connection:
            rows = connection.execute(
                f"""
                SELECT v.* FROM visits AS v
                WHERE {' AND '.join(clauses)}
                ORDER BY v.started_at DESC, v.visit_id DESC
                LIMIT ?
                """,
                tuple(params),
            ).fetchall()
        return [_visit_row(row) for row in rows]

    def list_unmatched_rows(
        self,
        *,
        site_id: str,
        from_utc: str,
        to_utc: str,
        reason: str | None,
        cursor: tuple[str, str] | None,
        limit: int,
    ) -> list[sqlite3.Row]:
        clauses = [
            "site_id = ?",
            "processing_result = 'unmatched'",
            "processed_at >= ?",
            "processed_at < ?",
        ]
        params: list[Any] = [site_id, from_utc, to_utc]
        if reason is not None:
            clauses.append("reason = ?")
            params.append(reason)
        if cursor is not None:
            clauses.append(
                "(processed_at < ? OR (processed_at = ? AND event_id < ?))"
            )
            params.extend((cursor[0], cursor[0], cursor[1]))
        params.append(limit)
        with closing(self._connect(readonly=True)) as connection:
            return connection.execute(
                f"""
                SELECT * FROM visit_source_events
                WHERE {' AND '.join(clauses)}
                ORDER BY processed_at DESC, event_id DESC
                LIMIT ?
                """,
                tuple(params),
            ).fetchall()

    def list_due_reconciliation(
        self,
        now_utc: str,
        limit: int,
    ) -> tuple[ReconcileCandidate, ...]:
        with closing(self._connect(readonly=True)) as connection:
            rows = connection.execute(
                """
                SELECT visit_id, site_id, client_mac,
                       start_auth_session_id, device_id, initial_snapshot_id
                FROM visits
                WHERE (device_id IS NULL OR initial_snapshot_id IS NULL)
                  AND (
                    link_reconcile_next_at IS NULL
                    OR link_reconcile_next_at <= ?
                  )
                ORDER BY
                    COALESCE(link_reconcile_next_at, created_at) ASC,
                    started_at ASC,
                    visit_id ASC
                LIMIT ?
                """,
                (now_utc, limit),
            ).fetchall()
        return tuple(ReconcileCandidate(**dict(row)) for row in rows)

    def record_reconciliation_attempt(
        self,
        visit_id: str,
        *,
        device_id: str | None,
        initial_snapshot_id: str | None,
        attempted_at: str,
        retry_at: str,
        deadline: float | None = None,
        cancel_event: threading.Event | None = None,
    ) -> tuple[bool, bool]:
        try:
            with self._bounded_write(
                WRITE_OPERATION_RECONCILIATION,
                deadline=deadline,
                cancel_event=cancel_event,
            ) as lease, closing(self._connect()) as connection:
                connection.execute("BEGIN IMMEDIATE")
                before = connection.execute(
                    """
                    SELECT device_id, initial_snapshot_id
                    FROM visits WHERE visit_id = ?
                    """,
                    (visit_id,),
                ).fetchone()
                if before is None:
                    connection.commit()
                    lease.mark_no_work()
                    return False, True
                new_device = before["device_id"] or device_id
                new_snapshot = before["initial_snapshot_id"] or initial_snapshot_id
                complete = new_device is not None and new_snapshot is not None
                changed = (
                    new_device != before["device_id"]
                    or new_snapshot != before["initial_snapshot_id"]
                )
                connection.execute(
                    """
                    UPDATE visits
                    SET device_id = ?, initial_snapshot_id = ?,
                        link_reconcile_attempted_at = ?,
                        link_reconcile_next_at = ?,
                        link_reconcile_attempt_count =
                            link_reconcile_attempt_count + 1,
                        updated_at = CASE WHEN ? THEN ? ELSE updated_at END
                    WHERE visit_id = ?
                    """,
                    (
                        new_device,
                        new_snapshot,
                        attempted_at,
                        None if complete else retry_at,
                        int(changed),
                        attempted_at,
                        visit_id,
                    ),
                )
                connection.commit()
                lease.mark_progress()
                return changed, complete
        except sqlite3.Error as exc:
            raise _storage_error(
                exc,
                operation=WRITE_OPERATION_RECONCILIATION,
            ) from exc

    def get_reader_states(self) -> dict[str, VisitReaderState]:
        with closing(self._connect(readonly=True)) as connection:
            rows = connection.execute(
                "SELECT * FROM visit_reader_state"
            ).fetchall()
        return {
            str(row["source_identity"]): VisitReaderState(
                source_identity=str(row["source_identity"]),
                source_path=str(row["source_path"]),
                source_offset=int(row["source_offset"]),
                last_observed_size=(
                    None
                    if row["last_observed_size"] is None
                    else int(row["last_observed_size"])
                ),
                checkpoint_offset=(
                    None
                    if row["checkpoint_offset"] is None
                    else int(row["checkpoint_offset"])
                ),
                checkpoint_length=(
                    None
                    if row["checkpoint_length"] is None
                    else int(row["checkpoint_length"])
                ),
                checkpoint_sha256=row["checkpoint_sha256"],
                retired_completed=bool(row["retired_completed"]),
                missing_warning_emitted=bool(
                    row["missing_warning_emitted"]
                ),
                updated_at=str(row["updated_at"]),
            )
            for row in rows
        }

    def observe_reader_progress(
        self,
        progress: ReaderProgress,
        *,
        now_utc: str,
        deadline: float | None = None,
        cancel_event: threading.Event | None = None,
    ) -> None:
        try:
            with self._bounded_write(
                WRITE_OPERATION_READER_CHECKPOINT,
                deadline=deadline,
                cancel_event=cancel_event,
            ) as lease, closing(self._connect()) as connection:
                connection.execute("BEGIN IMMEDIATE")
                self._upsert_reader_progress(connection, progress, now_utc)
                connection.commit()
                lease.mark_progress()
        except sqlite3.Error as exc:
            raise _storage_error(
                exc,
                operation=WRITE_OPERATION_READER_CHECKPOINT,
            ) from exc

    def reset_reader_source(
        self,
        progress: ReaderProgress,
        *,
        now_utc: str,
        deadline: float | None = None,
        cancel_event: threading.Event | None = None,
    ) -> None:
        self.observe_reader_progress(
            progress,
            now_utc=now_utc,
            deadline=deadline,
            cancel_event=cancel_event,
        )

    def mark_reader_source_missing(
        self,
        source_identity: str,
        *,
        now_utc: str,
        deadline: float | None = None,
        cancel_event: threading.Event | None = None,
    ) -> None:
        try:
            with self._bounded_write(
                WRITE_OPERATION_READER_CHECKPOINT,
                deadline=deadline,
                cancel_event=cancel_event,
            ) as lease, closing(self._connect()) as connection:
                connection.execute("BEGIN IMMEDIATE")
                updated = connection.execute(
                    """
                    UPDATE visit_reader_state
                    SET missing_warning_emitted=1, updated_at=?
                    WHERE source_identity=?
                    """,
                    (now_utc, source_identity),
                )
                connection.commit()
                if updated.rowcount:
                    lease.mark_progress()
                else:
                    lease.mark_no_work()
        except sqlite3.Error as exc:
            raise _storage_error(
                exc,
                operation=WRITE_OPERATION_READER_CHECKPOINT,
            ) from exc

    def delete_reader_state(
        self,
        source_identity: str,
        *,
        deadline: float | None = None,
        cancel_event: threading.Event | None = None,
    ) -> None:
        try:
            with self._bounded_write(
                WRITE_OPERATION_READER_CHECKPOINT,
                deadline=deadline,
                cancel_event=cancel_event,
            ) as lease, closing(self._connect()) as connection:
                connection.execute("BEGIN IMMEDIATE")
                deleted = connection.execute(
                    "DELETE FROM visit_reader_state WHERE source_identity=?",
                    (source_identity,),
                )
                connection.commit()
                if deleted.rowcount:
                    lease.mark_progress()
                else:
                    lease.mark_no_work()
        except sqlite3.Error as exc:
            raise _storage_error(
                exc,
                operation=WRITE_OPERATION_READER_CHECKPOINT,
            ) from exc

    def apply_journal_line(
        self,
        *,
        progress: ReaderProgress,
        evidence: OfflineEvidence | None,
        now_utc: str,
        grace_seconds: float,
        max_clock_skew_seconds: float,
        max_duration_drift_seconds: float,
        deadline: float | None = None,
        cancel_event: threading.Event | None = None,
    ) -> OfflineProcessingOutcome | None:
        try:
            with self._bounded_write(
                WRITE_OPERATION_READER_LINE,
                deadline=deadline,
                cancel_event=cancel_event,
            ) as lease, closing(self._connect()) as connection:
                connection.execute("BEGIN IMMEDIATE")
                outcome = self._apply_journal_line_transaction(
                    connection,
                    evidence=evidence,
                    progress=progress,
                    now_utc=now_utc,
                    grace_seconds=grace_seconds,
                    max_clock_skew_seconds=max_clock_skew_seconds,
                    max_duration_drift_seconds=max_duration_drift_seconds,
                )
                self._upsert_reader_progress(connection, progress, now_utc)
                connection.commit()
                lease.mark_progress()
                return outcome
        except sqlite3.Error as exc:
            raise _storage_error(
                exc,
                operation=WRITE_OPERATION_READER_LINE,
            ) from exc

    def process_pending_events(
        self,
        *,
        now_utc: str,
        limit: int,
        max_clock_skew_seconds: float,
        max_duration_drift_seconds: float,
        deadline: float | None = None,
        cancel_event: threading.Event | None = None,
        on_committed_chunk: (
            Callable[[tuple[OfflineProcessingOutcome, ...]], None] | None
        ) = None,
    ) -> tuple[OfflineProcessingOutcome, ...]:
        """Retry a bounded pass using short independently committed chunks."""
        outcomes: list[OfflineProcessingOutcome] = []
        examined = 0
        cursor: tuple[str, str] | None = None
        try:
            while examined < limit:
                if cancel_event is not None and cancel_event.is_set():
                    self._write_coordinator.clear_background_work(
                        WRITE_OPERATION_PENDING_RETRY
                    )
                    break
                if deadline is not None and time.monotonic() >= deadline:
                    break
                chunk_outcomes: list[OfflineProcessingOutcome] = []
                chunk_examined = 0
                chunk_cursor = cursor
                no_work = False
                chunk_limit = min(
                    BACKGROUND_CHUNK_MAX_ITEMS,
                    limit - examined,
                )
                with self._bounded_write(
                    WRITE_OPERATION_PENDING_RETRY,
                    deadline=deadline,
                    cancel_event=cancel_event,
                ) as lease:
                    if cancel_event is not None and cancel_event.is_set():
                        self._write_coordinator.clear_background_work(
                            WRITE_OPERATION_PENDING_RETRY
                        )
                        break
                    if deadline is not None and time.monotonic() >= deadline:
                        break
                    chunk_started = time.monotonic()
                    with closing(self._connect()) as connection:
                        connection.execute("BEGIN IMMEDIATE")
                        rows = self._pending_rows_after(
                            connection,
                            cursor=cursor,
                            limit=chunk_limit,
                        )
                        if not rows:
                            connection.commit()
                            lease.mark_no_work()
                            no_work = True
                        else:
                            for row in rows:
                                if chunk_examined and (
                                    (time.monotonic() - chunk_started) * 1000
                                    >= BACKGROUND_CHUNK_TARGET_MAX_HOLD_MS
                                ):
                                    break
                                if (
                                    cancel_event is not None
                                    and cancel_event.is_set()
                                ) or (
                                    deadline is not None
                                    and time.monotonic() >= deadline
                                ):
                                    break
                                pending_until = str(row["pending_until"])
                                event_id = str(row["event_id"])
                                chunk_cursor = (pending_until, event_id)
                                chunk_examined += 1
                                current = connection.execute(
                                    """
                                    SELECT * FROM visit_source_events
                                    WHERE event_id=?
                                      AND processing_result='pending_match'
                                    """,
                                    (event_id,),
                                ).fetchone()
                                if current is None:
                                    continue
                                chunk_outcomes.append(
                                    self._retry_pending_row(
                                        connection,
                                        row=current,
                                        now_utc=now_utc,
                                        max_clock_skew_seconds=(
                                            max_clock_skew_seconds
                                        ),
                                        max_duration_drift_seconds=(
                                            max_duration_drift_seconds
                                        ),
                                    )
                                )
                            connection.commit()
                            if chunk_examined:
                                lease.mark_progress()
                committed = tuple(chunk_outcomes)
                outcomes.extend(committed)
                if committed and on_committed_chunk is not None:
                    on_committed_chunk(committed)
                examined += chunk_examined
                cursor = chunk_cursor
                if no_work:
                    break
                if chunk_examined == 0:
                    if cancel_event is not None and cancel_event.is_set():
                        self._write_coordinator.clear_background_work(
                            WRITE_OPERATION_PENDING_RETRY
                        )
                    break
            return tuple(outcomes)
        except sqlite3.Error as exc:
            raise _storage_error(
                exc,
                operation=WRITE_OPERATION_PENDING_RETRY,
            ) from exc

    @staticmethod
    def _pending_rows_after(
        connection: sqlite3.Connection,
        *,
        cursor: tuple[str, str] | None,
        limit: int,
    ) -> list[sqlite3.Row]:
        if cursor is None:
            return connection.execute(
                """
                SELECT * FROM visit_source_events
                WHERE processing_result='pending_match'
                ORDER BY pending_until ASC, event_id ASC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return connection.execute(
            """
            SELECT * FROM visit_source_events
            WHERE processing_result='pending_match'
              AND (
                    pending_until > ?
                    OR (pending_until = ? AND event_id > ?)
                  )
            ORDER BY pending_until ASC, event_id ASC
            LIMIT ?
            """,
            (cursor[0], cursor[0], cursor[1], limit),
        ).fetchall()

    def _apply_journal_line_transaction(
        self,
        connection: sqlite3.Connection,
        *,
        evidence: OfflineEvidence | None,
        progress: ReaderProgress,
        now_utc: str,
        grace_seconds: float,
        max_clock_skew_seconds: float,
        max_duration_drift_seconds: float,
    ) -> OfflineProcessingOutcome | None:
        if evidence is None:
            return None
        if evidence.event_id is None:
            return OfflineProcessingOutcome(
                processing_result="invalid",
                reason=evidence.invalid_reason or "invalid_event_id",
            )
        existing = connection.execute(
            "SELECT processing_result, visit_id, reason "
            "FROM visit_source_events WHERE event_id=?",
            (evidence.event_id,),
        ).fetchone()
        if existing is not None:
            return OfflineProcessingOutcome(
                processing_result=str(existing["processing_result"]),
                event_id=evidence.event_id,
                visit_id=existing["visit_id"],
                reason=existing["reason"],
                duplicate=True,
            )
        if evidence.invalid_reason is not None:
            self._insert_source_event(
                connection,
                evidence=evidence,
                progress=progress,
                processing_result="invalid",
                visit_id=None,
                reason=evidence.invalid_reason,
                now_utc=now_utc,
                pending_until=None,
            )
            return OfflineProcessingOutcome(
                processing_result="invalid",
                event_id=evidence.event_id,
                reason=evidence.invalid_reason,
            )

        visit = self._open_visit_row(
            connection,
            evidence.site_id,
            evidence.client_mac,
        )
        if visit is None:
            pending_until = _add_seconds(now_utc, grace_seconds)
            self._insert_source_event(
                connection,
                evidence=evidence,
                progress=progress,
                processing_result="pending_match",
                visit_id=None,
                reason="no_open_visit",
                now_utc=now_utc,
                pending_until=pending_until,
            )
            return OfflineProcessingOutcome(
                processing_result="pending_match",
                event_id=evidence.event_id,
                reason="no_open_visit",
            )
        return self._finalize_or_reject(
            connection,
            evidence=evidence,
            visit=visit,
            progress=progress,
            now_utc=now_utc,
            max_clock_skew_seconds=max_clock_skew_seconds,
            max_duration_drift_seconds=max_duration_drift_seconds,
            insert_event=True,
        )

    def _retry_pending_row(
        self,
        connection: sqlite3.Connection,
        *,
        row: sqlite3.Row,
        now_utc: str,
        max_clock_skew_seconds: float,
        max_duration_drift_seconds: float,
    ) -> OfflineProcessingOutcome:
        evidence = _evidence_from_row(row)
        visit = self._open_visit_row(
            connection,
            evidence.site_id,
            evidence.client_mac,
        )
        if visit is not None and str(visit["created_at"]) <= str(
            row["pending_until"]
        ):
            return self._finalize_or_reject(
                connection,
                evidence=evidence,
                visit=visit,
                progress=None,
                now_utc=now_utc,
                max_clock_skew_seconds=max_clock_skew_seconds,
                max_duration_drift_seconds=max_duration_drift_seconds,
                insert_event=False,
            )
        result = (
            "unmatched"
            if now_utc >= str(row["pending_until"])
            else "pending_match"
        )
        connection.execute(
            """
            UPDATE visit_source_events
            SET processing_result=?, reason='no_open_visit',
                processed_at=?, last_match_attempt_at=?
            WHERE event_id=? AND processing_result='pending_match'
            """,
            (result, now_utc, now_utc, evidence.event_id),
        )
        return OfflineProcessingOutcome(
            processing_result=result,
            event_id=evidence.event_id,
            reason="no_open_visit",
        )

    def _finalize_or_reject(
        self,
        connection: sqlite3.Connection,
        *,
        evidence: OfflineEvidence,
        visit: sqlite3.Row,
        progress: ReaderProgress | None,
        now_utc: str,
        max_clock_skew_seconds: float,
        max_duration_drift_seconds: float,
        insert_event: bool,
    ) -> OfflineProcessingOutcome:
        match = self._match_offline(
            connection,
            evidence=evidence,
            visit=visit,
            max_clock_skew_seconds=max_clock_skew_seconds,
            max_duration_drift_seconds=max_duration_drift_seconds,
        )
        if match.closed_at is None:
            reason = match.reason
            if insert_event:
                assert progress is not None
                self._insert_source_event(
                    connection,
                    evidence=evidence,
                    progress=progress,
                    processing_result="unmatched",
                    visit_id=None,
                    reason=reason,
                    now_utc=now_utc,
                    pending_until=None,
                )
            else:
                connection.execute(
                    """
                    UPDATE visit_source_events
                    SET processing_result='unmatched', visit_id=NULL,
                        reason=?, processed_at=?, last_match_attempt_at=?
                    WHERE event_id=? AND processing_result='pending_match'
                    """,
                    (reason, now_utc, now_utc, evidence.event_id),
                )
            return OfflineProcessingOutcome(
                processing_result="unmatched",
                event_id=evidence.event_id,
                reason=reason,
            )

        closed_at = match.closed_at
        duration_seconds = match.duration_seconds
        close_time_source = match.close_time_source
        visit_id = str(visit["visit_id"])
        if insert_event:
            assert progress is not None
            self._insert_source_event(
                connection,
                evidence=evidence,
                progress=progress,
                processing_result="closed",
                visit_id=visit_id,
                reason=None,
                now_utc=now_utc,
                pending_until=None,
            )
        else:
            connection.execute(
                """
                UPDATE visit_source_events
                SET processing_result='closed', visit_id=?, reason=NULL,
                    processed_at=?, last_match_attempt_at=?
                WHERE event_id=? AND processing_result='pending_match'
                """,
                (visit_id, now_utc, now_utc, evidence.event_id),
            )
        updated = connection.execute(
            """
            UPDATE visits
            SET status='closed', closed_at=?,
                close_reason='omada_client_offline', close_time_source=?,
                final_ip=?, final_ssid=?, final_ap_mac=?,
                reported_connected_seconds=?,
                reported_traffic_total_bytes=?,
                reported_traffic_up_bytes=NULL,
                reported_traffic_down_bytes=NULL,
                duration_seconds=?, offline_event_id=?, updated_at=?
            WHERE visit_id=? AND status='open'
            """,
            (
                closed_at,
                close_time_source,
                evidence.client_ip,
                evidence.ssid,
                evidence.ap_mac,
                evidence.reported_connected_seconds,
                evidence.reported_traffic_total_bytes,
                duration_seconds,
                evidence.event_id,
                now_utc,
                visit_id,
            ),
        ).rowcount
        if updated != 1:
            raise sqlite3.IntegrityError(
                "Open Visit changed during finalization"
            )
        return OfflineProcessingOutcome(
            processing_result="closed",
            event_id=evidence.event_id,
            visit_id=visit_id,
            duration_drift_seconds=match.duration_drift_seconds,
            duration_drift_threshold_seconds=max_duration_drift_seconds,
            duration_drift_exceeded=match.duration_drift_exceeded,
            close_time_source=close_time_source,
        )

    def _match_offline(
        self,
        connection: sqlite3.Connection,
        *,
        evidence: OfflineEvidence,
        visit: sqlite3.Row,
        max_clock_skew_seconds: float,
        max_duration_drift_seconds: float,
    ) -> _OfflineMatch:
        started = _parse_utc(str(visit["started_at"]))
        controller = _parse_optional_utc(evidence.controller_event_at)
        received = _parse_optional_utc(evidence.received_at)
        authorization = connection.execute(
            """
            SELECT COUNT(*) AS authorization_count,
                   MAX(authorized_at) AS latest_authorized_at
            FROM visit_authorizations
            WHERE visit_id=?
            """,
            (visit["visit_id"],),
        ).fetchone()
        authorization_count = int(authorization["authorization_count"])
        latest_value = authorization["latest_authorized_at"]
        if authorization_count < 1 or latest_value is None:
            return _OfflineMatch(
                None, None, None, "authorization_evidence_missing"
            )
        latest_authorized = _parse_utc(str(latest_value))
        match_floor = max(started, latest_authorized)
        close_at: datetime | None = None
        source: str | None = None
        if controller is not None and controller >= match_floor:
            close_at = controller
            source = "controller"
        elif controller is not None:
            earliest = match_floor - timedelta(
                seconds=max_clock_skew_seconds
            )
            if (
                authorization_count == 1
                and controller >= earliest
                and received is not None
                and received >= match_floor
            ):
                close_at = received
                source = "received_clock_fallback"
            else:
                return _OfflineMatch(
                    None, None, None, "stale_or_ambiguous"
                )
        elif (
            authorization_count == 1
            and received is not None
            and received >= match_floor
        ):
            close_at = received
            source = "received_clock_fallback"
        else:
            return _OfflineMatch(None, None, None, "stale_or_ambiguous")

        drift_seconds: float | None = None
        drift_exceeded = False
        if (
            evidence.reported_connected_seconds is not None
            and controller is not None
        ):
            reported_start = controller - timedelta(
                seconds=evidence.reported_connected_seconds
            )
            drift_seconds = abs((reported_start - started).total_seconds())
            drift_exceeded = drift_seconds > max_duration_drift_seconds

        known_ssids = {
            str(row[0])
            for row in connection.execute(
                """
                SELECT portal_ssid FROM visit_authorizations
                WHERE visit_id=? AND portal_ssid IS NOT NULL
                """,
                (visit["visit_id"],),
            ).fetchall()
        }
        if visit["start_ssid"] is not None:
            known_ssids.add(str(visit["start_ssid"]))
        if (
            evidence.ssid is not None
            and known_ssids
            and evidence.ssid not in known_ssids
        ):
            return _OfflineMatch(None, None, None, "ssid_changed")
        duration = int((close_at - started).total_seconds())
        return _OfflineMatch(
            _format_utc(close_at),
            duration,
            source,
            None,
            duration_drift_seconds=drift_seconds,
            duration_drift_exceeded=drift_exceeded,
        )

    @staticmethod
    def _open_visit_row(
        connection: sqlite3.Connection,
        site_id: str | None,
        client_mac: str | None,
    ) -> sqlite3.Row | None:
        if site_id is None or client_mac is None:
            return None
        return connection.execute(
            """
            SELECT * FROM visits
            WHERE site_id=? AND client_mac=? AND status='open'
            """,
            (site_id, client_mac),
        ).fetchone()

    @staticmethod
    def _insert_source_event(
        connection: sqlite3.Connection,
        *,
        evidence: OfflineEvidence,
        progress: ReaderProgress,
        processing_result: str,
        visit_id: str | None,
        reason: str | None,
        now_utc: str,
        pending_until: str | None,
    ) -> None:
        connection.execute(
            """
            INSERT INTO visit_source_events (
                event_id, event_type, site_id, client_mac,
                controller_event_at, received_at,
                client_ip, ssid, ap_mac,
                reported_connected_seconds,
                reported_traffic_total_bytes,
                source_identity, source_offset_start, source_offset_end,
                processing_result, visit_id, reason,
                first_processed_at, processed_at, pending_until,
                last_match_attempt_at
            ) VALUES (?, 'omada.client_offline', ?, ?, ?, ?, ?, ?, ?, ?, ?,
                      ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                evidence.event_id,
                evidence.site_id,
                evidence.client_mac,
                evidence.controller_event_at,
                evidence.received_at,
                evidence.client_ip,
                evidence.ssid,
                evidence.ap_mac,
                evidence.reported_connected_seconds,
                evidence.reported_traffic_total_bytes,
                progress.source_identity,
                (
                    progress.source_offset
                    if progress.source_offset_start is None
                    else progress.source_offset_start
                ),
                progress.source_offset,
                processing_result,
                visit_id,
                reason,
                now_utc,
                now_utc,
                pending_until,
                now_utc if processing_result == "pending_match" else None,
            ),
        )

    @staticmethod
    def _upsert_reader_progress(
        connection: sqlite3.Connection,
        progress: ReaderProgress,
        now_utc: str,
    ) -> None:
        connection.execute(
            """
            INSERT INTO visit_reader_state (
                source_identity, source_path, source_offset,
                last_observed_size, checkpoint_offset,
                checkpoint_length, checkpoint_sha256,
                retired_completed, missing_warning_emitted, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
            ON CONFLICT(source_identity) DO UPDATE SET
                source_path=excluded.source_path,
                source_offset=excluded.source_offset,
                last_observed_size=excluded.last_observed_size,
                checkpoint_offset=excluded.checkpoint_offset,
                checkpoint_length=excluded.checkpoint_length,
                checkpoint_sha256=excluded.checkpoint_sha256,
                retired_completed=excluded.retired_completed,
                missing_warning_emitted=0,
                updated_at=excluded.updated_at
            """,
            (
                progress.source_identity,
                progress.source_path,
                progress.source_offset,
                progress.last_observed_size,
                progress.checkpoint.checkpoint_offset,
                progress.checkpoint.checkpoint_length,
                progress.checkpoint.checkpoint_sha256,
                int(progress.retired_completed),
                now_utc,
            ),
        )

    def authorization_count(self, visit_id: str) -> int:
        with closing(self._connect(readonly=True)) as connection:
            return int(connection.execute(
                "SELECT COUNT(*) FROM visit_authorizations WHERE visit_id = ?",
                (visit_id,),
            ).fetchone()[0])

    def _startup_check(self, connection: sqlite3.Connection) -> None:
        version = int(connection.execute("PRAGMA user_version").fetchone()[0])
        if version != SCHEMA_VERSION:
            raise VisitSchemaError("Visit schema version mismatch")
        quick = connection.execute("PRAGMA quick_check").fetchone()
        if not quick or str(quick[0]) != "ok":
            raise VisitSchemaError("Visit startup health check failed")
        self._validate_schema(connection)

    def _validate_schema(self, connection: sqlite3.Connection) -> None:
        if not REQUIRED_TABLES.issubset(self._table_names(connection)):
            raise VisitSchemaError("Visit schema is missing required tables")
        source_columns = {
            str(row[1])
            for row in connection.execute(
                "PRAGMA table_info(visit_source_events)"
            )
        }
        if not REQUIRED_V2_SOURCE_COLUMNS.issubset(source_columns):
            raise VisitSchemaError(
                "Visit source-event schema is missing v2 columns"
            )
        indexes = {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'index'"
            )
        }
        if not set(REQUIRED_INDEXES).issubset(indexes):
            raise VisitSchemaError("Visit schema is missing required indexes")
        for name, expected in REQUIRED_INDEXES.items():
            actual = tuple(
                str(row[2])
                for row in connection.execute(f"PRAGMA index_info({name})")
            )
            if actual != expected:
                raise VisitSchemaError(f"Visit index is invalid: {name}")
        triggers = {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'trigger'"
            )
        }
        if not REQUIRED_TRIGGERS.issubset(triggers):
            raise VisitSchemaError("Visit schema is missing required triggers")
        for table, expected in REQUIRED_FOREIGN_KEYS.items():
            actual = {
                (str(row[3]), str(row[2]), str(row[4]), str(row[6]))
                for row in connection.execute(
                    f"PRAGMA foreign_key_list({table})"
                )
            }
            if not expected.issubset(actual):
                raise VisitSchemaError(
                    f"Visit foreign key contract is invalid: {table}"
                )
        for table, expected in REQUIRED_NOT_NULL_COLUMNS.items():
            actual = {
                str(row[1])
                for row in connection.execute(f"PRAGMA table_info({table})")
                if int(row[3]) == 1
            }
            if not expected.issubset(actual):
                raise VisitSchemaError(
                    f"Visit required-column contract is invalid: {table}"
                )
        open_index = next(
            (
                row
                for row in connection.execute("PRAGMA index_list(visits)")
                if str(row[1]) == "uq_visits_open_site_mac"
            ),
            None,
        )
        if (
            open_index is None
            or int(open_index[2]) != 1
            or int(open_index[4]) != 1
        ):
            raise VisitSchemaError("Visit open invariant index is invalid")
        violations = connection.execute("PRAGMA foreign_key_check").fetchone()
        if violations is not None:
            raise VisitSchemaError("Visit foreign key validation failed")
        if _schema_signature(connection) != expected_visit_signature(SCHEMA_VERSION):
            raise VisitSchemaError(
                "Visit schema does not match the exact contract for this version"
            )

    @staticmethod
    def _table_names(connection: sqlite3.Connection) -> set[str]:
        return {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }

    @staticmethod
    def _user_schema_objects(connection: sqlite3.Connection) -> set[str]:
        return {
            str(row[0])
            for row in connection.execute(
                """
                SELECT name FROM sqlite_master
                WHERE name NOT LIKE 'sqlite_%'
                  AND type IN ('table', 'index', 'view', 'trigger')
                """
            )
        }

    def _connect(
        self,
        *,
        readonly: bool = False,
        busy_timeout_ms: int | None = None,
    ) -> sqlite3.Connection:
        timeout_ms = (
            self.sqlite_busy_timeout_ms
            if busy_timeout_ms is None
            else max(1, min(int(busy_timeout_ms), 60_000))
        )
        self._validate_database_target(require_exists=readonly)
        if readonly:
            uri = f"{self.db_path.resolve(strict=False).as_uri()}?mode=ro"
            connection = sqlite3.connect(
                uri,
                uri=True,
                timeout=timeout_ms / 1000,
            )
        else:
            connection = sqlite3.connect(
                str(self.db_path),
                timeout=timeout_ms / 1000,
            )
        connection.row_factory = sqlite3.Row
        try:
            connection.execute(f"PRAGMA busy_timeout={timeout_ms}")
            connection.execute("PRAGMA foreign_keys=ON")
            if readonly:
                connection.execute("PRAGMA query_only=ON")
            else:
                connection.execute("PRAGMA journal_mode=WAL")
                connection.execute("PRAGMA synchronous=NORMAL")
        except Exception:
            connection.close()
            raise
        return connection

    @contextmanager
    def _bounded_write(
        self,
        operation: str,
        *,
        deadline: float | None = None,
        cancel_event: threading.Event | None = None,
    ):
        if operation == "reader":
            operation = WRITE_OPERATION_READER_LINE
        timeout_ms = {
            WRITE_OPERATION_START: self.config.start_writer_slot_wait_ms,
            WRITE_OPERATION_READER_LINE: (
                self.config.reader_writer_slot_wait_ms
            ),
            WRITE_OPERATION_READER_CHECKPOINT: (
                self.config.reader_writer_slot_wait_ms
            ),
            WRITE_OPERATION_PENDING_RETRY: (
                self.config.reader_writer_slot_wait_ms
            ),
            WRITE_OPERATION_RECONCILIATION: (
                self.config.reconciliation_writer_slot_wait_ms
            ),
            WRITE_OPERATION_STARTUP: self.config.sqlite_busy_timeout_ms,
        }[operation]
        with self._write_coordinator.acquire(
            operation,
            timeout_ms=timeout_ms,
            deadline=deadline,
            cancel_event=cancel_event,
        ) as lease:
            yield lease

    def _remaining_sqlite_timeout_ms(self, deadline: float | None) -> int:
        if deadline is None:
            return self.sqlite_busy_timeout_ms
        remaining_ms = int((deadline - time.monotonic()) * 1000)
        if remaining_ms <= 0:
            raise VisitStorageError(
                VisitStorageCategory.BUSY,
                "Visit Start latency budget is exhausted",
                operation=WRITE_OPERATION_START,
            )
        return min(self.sqlite_busy_timeout_ms, remaining_ms)

    def _ensure_parent(self) -> None:
        parent = self.db_path.parent
        if parent.exists():
            if not parent.is_dir() or not os.access(parent, os.W_OK):
                raise VisitStorageError(
                    VisitStorageCategory.UNAVAILABLE,
                    "Visit database parent is unavailable",
                )
            return
        resolved = parent.resolve(strict=False)
        allowed = ALLOWED_AUTO_CREATE_ROOT.resolve(strict=False)
        if not (resolved == allowed or allowed in resolved.parents):
            raise VisitStorageError(
                VisitStorageCategory.UNAVAILABLE,
                "Missing Visit database parent is not approved",
            )
        try:
            parent.mkdir(parents=True, mode=0o750, exist_ok=True)
            if os.name == "posix":
                os.chmod(parent, 0o750)
        except OSError as exc:
            raise VisitStorageError(VisitStorageCategory.UNAVAILABLE) from exc

    def _database_exists(self) -> bool:
        return self._validate_database_target(require_exists=False)

    def _validate_database_target(self, *, require_exists: bool) -> bool:
        try:
            target = os.lstat(self.db_path)
        except FileNotFoundError:
            if require_exists:
                raise VisitStorageError(
                    VisitStorageCategory.UNAVAILABLE,
                    "Visit database does not exist",
                )
            return False
        except OSError as exc:
            raise VisitStorageError(VisitStorageCategory.UNAVAILABLE) from exc
        if stat.S_ISLNK(target.st_mode) or not stat.S_ISREG(target.st_mode):
            raise VisitStorageError(
                VisitStorageCategory.UNAVAILABLE,
                "Visit database target must be a regular file",
            )
        return True


def _visit_row(row: sqlite3.Row) -> VisitRecord:
    return VisitRecord(**dict(row))


def _schema_signature(
    connection: sqlite3.Connection,
) -> tuple[tuple[str, str, str, str], ...]:
    rows = connection.execute(
        """
        SELECT type, name, tbl_name, sql
        FROM sqlite_master
        WHERE name NOT LIKE 'sqlite_%'
          AND sql IS NOT NULL
        ORDER BY type, name
        """
    ).fetchall()
    return tuple(
        (
            str(row[0]),
            str(row[1]),
            str(row[2]),
            " ".join(str(row[3]).split()),
        )
        for row in rows
    )


def _expected_v1_signature() -> tuple[tuple[str, str, str, str], ...]:
    connection = sqlite3.connect(":memory:")
    try:
        connection.executescript(_schema_sql_v1())
        return _schema_signature(connection)
    finally:
        connection.close()


def _expected_v2_signature() -> tuple[tuple[str, str, str, str], ...]:
    connection = sqlite3.connect(":memory:")
    try:
        connection.executescript(_schema_sql_v2())
        return _schema_signature(connection)
    finally:
        connection.close()


def _evidence_from_row(row: sqlite3.Row) -> OfflineEvidence:
    return OfflineEvidence(
        event_id=str(row["event_id"]),
        site_id=row["site_id"],
        client_mac=row["client_mac"],
        controller_event_at=row["controller_event_at"],
        received_at=row["received_at"],
        client_ip=row["client_ip"],
        ssid=row["ssid"],
        ap_mac=row["ap_mac"],
        reported_connected_seconds=row["reported_connected_seconds"],
        reported_traffic_total_bytes=row[
            "reported_traffic_total_bytes"
        ],
    )


def _parse_utc(value: str) -> datetime:
    return datetime.strptime(
        value,
        "%Y-%m-%dT%H:%M:%S.%fZ",
    ).replace(tzinfo=timezone.utc)


def _parse_optional_utc(value: str | None) -> datetime | None:
    return None if value is None else _parse_utc(value)


def _format_utc(value: datetime) -> str:
    return (
        value.astimezone(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def _add_seconds(value: str, seconds: float) -> str:
    return _format_utc(_parse_utc(value) + timedelta(seconds=seconds))


def classify_sqlite_error(exc: sqlite3.Error) -> VisitStorageCategory:
    code = getattr(exc, "sqlite_errorcode", None)
    primary = (code & 0xFF) if isinstance(code, int) else None
    if primary in {_SQLITE_BUSY, _SQLITE_LOCKED}:
        return VisitStorageCategory.BUSY
    if primary == _SQLITE_FULL:
        return VisitStorageCategory.FULL
    if primary == _SQLITE_IOERR:
        return VisitStorageCategory.IO_ERROR
    if primary in {_SQLITE_CORRUPT, _SQLITE_NOTADB}:
        return VisitStorageCategory.CORRUPT
    if primary in {_SQLITE_READONLY, _SQLITE_CANTOPEN}:
        return VisitStorageCategory.UNAVAILABLE
    if primary == _SQLITE_CONSTRAINT:
        return VisitStorageCategory.CONSTRAINT
    message = str(exc).lower()
    for fragment, category in (
        ("database is locked", VisitStorageCategory.BUSY),
        ("database table is locked", VisitStorageCategory.BUSY),
        ("database or disk is full", VisitStorageCategory.FULL),
        ("disk i/o error", VisitStorageCategory.IO_ERROR),
        ("database disk image is malformed", VisitStorageCategory.CORRUPT),
        ("file is not a database", VisitStorageCategory.CORRUPT),
        ("readonly database", VisitStorageCategory.UNAVAILABLE),
        ("unable to open database file", VisitStorageCategory.UNAVAILABLE),
        ("constraint failed", VisitStorageCategory.CONSTRAINT),
    ):
        if fragment in message:
            return category
    return VisitStorageCategory.UNKNOWN


def _storage_error(
    exc: sqlite3.Error,
    *,
    operation: str | None = None,
    lock_wait_ms: int | None = None,
) -> VisitStorageError:
    return VisitStorageError(
        classify_sqlite_error(exc),
        operation=operation,
        lock_wait_ms=lock_wait_ms,
        contention_layer="sqlite",
    )
