"""Bounded, explicit recovery for safely provable stale open Visits."""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import stat
import sys
import uuid
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Sequence

from .models import SCHEMA_VERSION
from .repository import (
    _expected_v2_signature,
    _format_utc,
    _parse_utc,
    _schema_signature,
)


DEFAULT_LIMIT = 500
MIN_LIMIT = 1
MAX_LIMIT = 5_000


class RecoveryError(RuntimeError):
    """Safe operator-facing recovery validation or storage failure."""


@dataclass(frozen=True)
class RecoveryCandidate:
    visit_id: str
    client_mac: str
    started_at: str
    latest_authorized_at: str
    event_id: str
    controller_event_at: str
    legacy_processing_result: str
    legacy_reason: str
    reported_duration_drift_seconds: float | None
    semantic_duplicate_count: int = 0


@dataclass(frozen=True)
class _Evaluation:
    candidate: RecoveryCandidate | None
    reason: str | None


def recover(
    *,
    db_path: str,
    site_id: str,
    apply: bool = False,
    limit: int = DEFAULT_LIMIT,
    after_started_at: str | None = None,
    after_visit_id: str | None = None,
    now_utc: str | None = None,
) -> dict[str, Any]:
    """Evaluate or apply one deterministic, Site-scoped recovery page."""
    resolved = _database_path(db_path)
    site = _site_id(site_id)
    bounded_limit = _limit(limit)
    continuation = _continuation(after_started_at, after_visit_id)
    evaluated_at = now_utc or _utc_now()
    _canonical_utc(evaluated_at, "now_utc")
    mode = "rw" if apply else "ro"
    connection = _connect(resolved, mode=mode)
    try:
        if not apply:
            connection.execute("BEGIN")
        _validate_source(connection)
        rows = _open_page(
            connection,
            site_id=site,
            limit=bounded_limit,
            continuation=continuation,
        )
        examined = rows[:bounded_limit]
        truncated = len(rows) > bounded_limit
        open_count = int(connection.execute(
            "SELECT COUNT(*) FROM visits WHERE site_id=? AND status='open'",
            (site,),
        ).fetchone()[0])
        candidates: list[RecoveryCandidate] = []
        skip_reasons: Counter[str] = Counter()
        applied_count = 0
        semantic_duplicate_count = 0
        for visit in examined:
            if apply:
                evaluation = _apply_one(
                    connection,
                    visit_id=str(visit["visit_id"]),
                    site_id=site,
                    now_utc=evaluated_at,
                )
                if evaluation.candidate is not None:
                    applied_count += 1
            else:
                evaluation = _evaluate_visit(connection, visit)
            if evaluation.candidate is not None:
                candidates.append(evaluation.candidate)
                semantic_duplicate_count += (
                    evaluation.candidate.semantic_duplicate_count
                )
            else:
                skip_reasons[evaluation.reason or "no_safe_candidate"] += 1

        last_key = (
            (str(examined[-1]["started_at"]), str(examined[-1]["visit_id"]))
            if examined
            else continuation
        )
        remaining = _remaining_open_count(
            connection,
            site_id=site,
            after=last_key,
        )
        if not apply:
            connection.rollback()
        return {
            "resolved_db_path": str(resolved),
            "schema_version": SCHEMA_VERSION,
            "mode": "apply" if apply else "dry-run",
            "site_id": site,
            "evaluated_at": evaluated_at,
            "limit": bounded_limit,
            "examined_count": len(examined),
            "open_visit_count": open_count,
            "recoverable_count": len(candidates),
            "unrecoverable_count": len(examined) - len(candidates),
            "applied_count": applied_count,
            "semantic_duplicate_count": semantic_duplicate_count,
            "truncated": truncated,
            "remaining_open_visit_count": remaining,
            "next_after_started_at": (
                last_key[0] if truncated and last_key is not None else None
            ),
            "next_after_visit_id": (
                last_key[1] if truncated and last_key is not None else None
            ),
            "candidates": [asdict(value) for value in candidates],
            "skip_reason_counts": dict(sorted(skip_reasons.items())),
        }
    except sqlite3.Error as exc:
        try:
            connection.rollback()
        except sqlite3.Error:
            pass
        raise RecoveryError("Visit recovery storage operation failed") from exc
    finally:
        connection.close()


def backup_database(*, db_path: str, backup_to: str) -> dict[str, Any]:
    """Create and verify a consistent SQLite Backup API copy."""
    source_path = _database_path(db_path)
    destination = _backup_path(backup_to)
    source = _connect(source_path, mode="ro")
    created = False
    try:
        _validate_source(source)
        destination_connection = sqlite3.connect(str(destination))
        created = True
        try:
            source.backup(destination_connection)
        finally:
            destination_connection.close()
        verification = _connect(destination, mode="ro")
        try:
            quick = verification.execute("PRAGMA quick_check").fetchone()
            quick_value = str(quick[0]) if quick else ""
            version = int(
                verification.execute("PRAGMA user_version").fetchone()[0]
            )
            if quick_value != "ok" or version != SCHEMA_VERSION:
                raise RecoveryError("Visit recovery backup verification failed")
            if _schema_signature(verification) != _expected_v2_signature():
                raise RecoveryError("Visit recovery backup schema is invalid")
        finally:
            verification.close()
        return {
            "resolved_db_path": str(source_path),
            "resolved_backup_path": str(destination),
            "mode": "backup",
            "source_schema_version": SCHEMA_VERSION,
            "backup_schema_version": version,
            "quick_check": quick_value,
        }
    except sqlite3.Error as exc:
        if created:
            _remove_failed_backup(destination)
        raise RecoveryError("Visit recovery backup failed") from exc
    except Exception:
        if created:
            _remove_failed_backup(destination)
        raise
    finally:
        source.close()


def _apply_one(
    connection: sqlite3.Connection,
    *,
    visit_id: str,
    site_id: str,
    now_utc: str,
) -> _Evaluation:
    connection.execute("BEGIN IMMEDIATE")
    try:
        visit = connection.execute(
            "SELECT * FROM visits WHERE visit_id=? AND site_id=?",
            (visit_id, site_id),
        ).fetchone()
        if visit is None or str(visit["status"]) != "open":
            result = _Evaluation(None, "visit_changed")
        else:
            result = _evaluate_visit(connection, visit)
        candidate = result.candidate
        if candidate is None:
            connection.rollback()
            return result
        event = connection.execute(
            "SELECT * FROM visit_source_events WHERE event_id=?",
            (candidate.event_id,),
        ).fetchone()
        if event is None:
            connection.rollback()
            return _Evaluation(None, "visit_changed")
        updated_event = connection.execute(
            """
            UPDATE visit_source_events
            SET processing_result='closed', visit_id=?, reason=NULL,
                processed_at=?, last_match_attempt_at=?
            WHERE event_id=? AND processing_result='unmatched'
              AND reason='stale_or_ambiguous' AND visit_id IS NULL
            """,
            (visit_id, now_utc, now_utc, candidate.event_id),
        ).rowcount
        closed_at = str(event["controller_event_at"])
        duration = int(
            (
                _parse_utc(closed_at)
                - _parse_utc(str(visit["started_at"]))
            ).total_seconds()
        )
        updated_visit = connection.execute(
            """
            UPDATE visits
            SET status='closed', closed_at=?,
                close_reason='omada_client_offline_recovered',
                close_time_source='controller', final_ip=?, final_ssid=?,
                final_ap_mac=?, reported_connected_seconds=?,
                reported_traffic_total_bytes=?,
                reported_traffic_up_bytes=NULL,
                reported_traffic_down_bytes=NULL, duration_seconds=?,
                offline_event_id=?, updated_at=?
            WHERE visit_id=? AND site_id=? AND client_mac=? AND status='open'
            """,
            (
                closed_at,
                event["client_ip"],
                event["ssid"],
                event["ap_mac"],
                event["reported_connected_seconds"],
                event["reported_traffic_total_bytes"],
                duration,
                candidate.event_id,
                now_utc,
                visit_id,
                site_id,
                visit["client_mac"],
            ),
        ).rowcount
        if updated_event != 1 or updated_visit != 1:
            connection.rollback()
            return _Evaluation(None, "visit_changed")
        connection.commit()
        return result
    except Exception:
        connection.rollback()
        raise


def _evaluate_visit(
    connection: sqlite3.Connection,
    visit: sqlite3.Row,
) -> _Evaluation:
    authorization = connection.execute(
        """
        SELECT COUNT(*) AS authorization_count,
               MAX(authorized_at) AS latest_authorized_at
        FROM visit_authorizations
        WHERE visit_id=?
        """,
        (visit["visit_id"],),
    ).fetchone()
    if int(authorization["authorization_count"]) < 1:
        return _Evaluation(None, "authorization_evidence_missing")
    latest_authorized_at = authorization["latest_authorized_at"]
    if latest_authorized_at is None:
        return _Evaluation(None, "authorization_evidence_missing")
    rows = connection.execute(
        """
        SELECT e.*,
               EXISTS(
                   SELECT 1 FROM visits AS used
                   WHERE used.offline_event_id=e.event_id
               ) AS already_linked
        FROM visit_source_events AS e
        WHERE e.event_type='omada.client_offline'
          AND e.processing_result='unmatched'
          AND e.reason='stale_or_ambiguous'
          AND e.site_id=? AND e.client_mac=?
          AND e.controller_event_at IS NOT NULL
          AND e.controller_event_at>=?
          AND e.visit_id IS NULL
        ORDER BY e.controller_event_at ASC, e.event_id ASC
        """,
        (visit["site_id"], visit["client_mac"], latest_authorized_at),
    ).fetchall()
    if not rows:
        return _Evaluation(None, "no_safe_offline_after_latest_authorization")
    unlinked = [row for row in rows if not bool(row["already_linked"])]
    if not unlinked:
        return _Evaluation(None, "source_event_already_linked")
    known_ssids = {
        str(row[0])
        for row in connection.execute(
            "SELECT portal_ssid FROM visit_authorizations "
            "WHERE visit_id=? AND portal_ssid IS NOT NULL",
            (visit["visit_id"],),
        )
    }
    if visit["start_ssid"] is not None:
        known_ssids.add(str(visit["start_ssid"]))
    safe = [
        row for row in unlinked
        if row["ssid"] is None
        or not known_ssids
        or str(row["ssid"]) in known_ssids
    ]
    if not safe:
        return _Evaluation(None, "ssid_conflict")
    earliest_at = str(safe[0]["controller_event_at"])
    earliest = [
        row for row in safe if str(row["controller_event_at"]) == earliest_at
    ]
    signature = _terminal_signature(earliest[0])
    if any(_terminal_signature(row) != signature for row in earliest[1:]):
        return _Evaluation(None, "ambiguous_same_timestamp_events")
    selected = min(earliest, key=lambda row: str(row["event_id"]))
    reported = selected["reported_connected_seconds"]
    drift = None
    if reported is not None:
        reported_start = _parse_utc(earliest_at) - timedelta(seconds=int(reported))
        drift = abs(
            (reported_start - _parse_utc(str(visit["started_at"]))).total_seconds()
        )
    return _Evaluation(
        RecoveryCandidate(
            visit_id=str(visit["visit_id"]),
            client_mac=str(visit["client_mac"]),
            started_at=str(visit["started_at"]),
            latest_authorized_at=str(latest_authorized_at),
            event_id=str(selected["event_id"]),
            controller_event_at=earliest_at,
            legacy_processing_result=str(selected["processing_result"]),
            legacy_reason=str(selected["reason"]),
            reported_duration_drift_seconds=drift,
            semantic_duplicate_count=max(0, len(earliest) - 1),
        ),
        None,
    )


def _terminal_signature(row: sqlite3.Row) -> tuple[Any, ...]:
    return tuple(row[name] for name in (
        "site_id", "client_mac", "controller_event_at", "client_ip", "ssid",
        "ap_mac", "reported_connected_seconds", "reported_traffic_total_bytes",
    ))


def _open_page(
    connection: sqlite3.Connection,
    *,
    site_id: str,
    limit: int,
    continuation: tuple[str, str] | None,
) -> list[sqlite3.Row]:
    clause = ""
    params: list[Any] = [site_id]
    if continuation is not None:
        clause = "AND (started_at>? OR (started_at=? AND visit_id>?))"
        params.extend((continuation[0], continuation[0], continuation[1]))
    params.append(limit + 1)
    return connection.execute(
        f"""
        SELECT * FROM visits
        WHERE site_id=? AND status='open' {clause}
        ORDER BY started_at ASC, visit_id ASC
        LIMIT ?
        """,
        tuple(params),
    ).fetchall()


def _remaining_open_count(
    connection: sqlite3.Connection,
    *,
    site_id: str,
    after: tuple[str, str] | None,
) -> int:
    if after is None:
        return int(connection.execute(
            "SELECT COUNT(*) FROM visits WHERE site_id=? AND status='open'",
            (site_id,),
        ).fetchone()[0])
    return int(connection.execute(
        """
        SELECT COUNT(*) FROM visits
        WHERE site_id=? AND status='open'
          AND (started_at>? OR (started_at=? AND visit_id>?))
        """,
        (site_id, after[0], after[0], after[1]),
    ).fetchone()[0])


def _validate_source(connection: sqlite3.Connection) -> None:
    version = int(connection.execute("PRAGMA user_version").fetchone()[0])
    if version != SCHEMA_VERSION:
        raise RecoveryError("Visit recovery source schema version is invalid")
    quick = connection.execute("PRAGMA quick_check").fetchone()
    if not quick or str(quick[0]) != "ok":
        raise RecoveryError("Visit recovery source health check failed")
    if _schema_signature(connection) != _expected_v2_signature():
        raise RecoveryError("Visit recovery source schema is invalid")
    if connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
        raise RecoveryError("Visit recovery source foreign keys are invalid")


def _connect(path: Path, *, mode: str) -> sqlite3.Connection:
    uri = f"{path.as_uri()}?mode={mode}"
    connection = sqlite3.connect(uri, uri=True, timeout=5.0)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    if mode == "ro":
        connection.execute("PRAGMA query_only=ON")
    return connection


def _database_path(value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        raise RecoveryError("Visit recovery database path must be absolute")
    resolved = path.resolve(strict=False)
    try:
        target = os.lstat(resolved)
    except OSError as exc:
        raise RecoveryError("Visit recovery database does not exist") from exc
    if not stat.S_ISREG(target.st_mode):
        raise RecoveryError("Visit recovery database must be a regular file")
    return resolved


def _backup_path(value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        raise RecoveryError("Visit recovery backup path must be absolute")
    resolved = path.resolve(strict=False)
    if resolved.exists():
        raise RecoveryError("Visit recovery backup destination already exists")
    if not resolved.parent.is_dir():
        raise RecoveryError("Visit recovery backup parent does not exist")
    return resolved


def _remove_failed_backup(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def _site_id(value: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise RecoveryError("Visit recovery site id is invalid")
    return value


def _limit(value: int) -> int:
    if type(value) is not int or not MIN_LIMIT <= value <= MAX_LIMIT:
        raise RecoveryError("Visit recovery limit must be between 1 and 5000")
    return value


def _continuation(
    started_at: str | None,
    visit_id: str | None,
) -> tuple[str, str] | None:
    if (started_at is None) != (visit_id is None):
        raise RecoveryError("Visit recovery continuation must be a complete pair")
    if started_at is None or visit_id is None:
        return None
    canonical = _canonical_utc(started_at, "after_started_at")
    try:
        parsed = uuid.UUID(visit_id)
    except (ValueError, AttributeError) as exc:
        raise RecoveryError("Visit recovery continuation UUID is invalid") from exc
    if str(parsed) != visit_id:
        raise RecoveryError("Visit recovery continuation UUID is not canonical")
    return canonical, visit_id


def _canonical_utc(value: str, name: str) -> str:
    try:
        parsed = _parse_utc(value)
    except (TypeError, ValueError) as exc:
        raise RecoveryError(f"Visit recovery {name} is invalid") from exc
    if _format_utc(parsed) != value:
        raise RecoveryError(f"Visit recovery {name} is not canonical")
    return value


def _utc_now() -> str:
    return _format_utc(datetime.now(timezone.utc))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-path", required=True)
    parser.add_argument("--site-id")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--after-started-at")
    parser.add_argument("--after-visit-id")
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--dry-run", action="store_true")
    actions.add_argument("--apply", action="store_true")
    actions.add_argument("--backup-to")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        if args.backup_to is not None:
            if any((
                args.site_id is not None,
                args.limit is not None,
                args.after_started_at is not None,
                args.after_visit_id is not None,
            )):
                parser.error("backup mode rejects Visit selection arguments")
            result = backup_database(
                db_path=args.db_path,
                backup_to=args.backup_to,
            )
        else:
            if args.site_id is None:
                parser.error("--site-id is required for dry-run/apply")
            result = recover(
                db_path=args.db_path,
                site_id=args.site_id,
                apply=bool(args.apply),
                limit=(DEFAULT_LIMIT if args.limit is None else args.limit),
                after_started_at=args.after_started_at,
                after_visit_id=args.after_visit_id,
            )
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
        return 0
    except (RecoveryError, sqlite3.Error, OSError, ValueError) as exc:
        message = (
            str(exc)
            if isinstance(exc, RecoveryError)
            else "Visit recovery operation failed"
        )
        print(message, file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
