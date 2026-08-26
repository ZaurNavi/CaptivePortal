"""Deterministic long-history capacity gate for Home Activity.

Run from the repository root, for example:
    python tests/analytics/home_activity_capacity_benchmark.py --rows 50000
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import tempfile
import time
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.analytics.source_gateway import AnalyticsSourceGateway, QueryDeadline
from app.visit_lifecycle.models import VisitLifecycleConfig
from app.visit_lifecycle.read_service import VisitLifecycleReadService
from app.visit_lifecycle.repository import VisitRepository


SITE = "capacity-site"
SSID = "capacity-guest"
UTC = timezone.utc
EVALUATED = datetime(2026, 8, 25, 12, tzinfo=UTC)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=int, default=50_000)
    parser.add_argument("--days", type=int, default=730)
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--deadline", type=float, default=10.0)
    args = parser.parse_args()
    if args.rows < 365 or args.days < 365 or args.runs < 2:
        parser.error("rows/days must cover 365 days and runs must be >= 2")

    with tempfile.TemporaryDirectory(prefix="home-activity-capacity-") as root:
        repository = _repository(Path(root))
        repository.initialize()
        seed_seconds = _seed(repository, args.rows, args.days)
        gateway = AnalyticsSourceGateway(
            None, VisitLifecycleReadService(repository), None
        )
        fingerprints_before = _fingerprints(repository)
        plans = gateway.explain_home_activity(
            site_id=SITE, guest_ssids=(SSID,),
            from_utc=_stamp(EVALUATED - timedelta(days=args.days)),
            to_utc=_stamp(EVALUATED), deadline=QueryDeadline.after(10),
        )
        windows = (
            ("today", EVALUATED.replace(hour=0, minute=0, second=0, microsecond=0)),
            ("24h", EVALUATED - timedelta(days=1)),
            ("7d", EVALUATED - timedelta(days=7)),
            ("30d", EVALUATED - timedelta(days=30)),
            ("current_month", EVALUATED.replace(day=1, hour=0)),
            ("32d", EVALUATED - timedelta(days=32)),
            ("90d", EVALUATED - timedelta(days=90)),
            ("365d", EVALUATED - timedelta(days=365)),
            ("retained", EVALUATED - timedelta(days=args.days)),
        )
        results = []
        for label, range_start in windows:
            durations = []
            failures = 0
            raw = None
            for _ in range(args.runs):
                started = time.perf_counter()
                try:
                    raw = gateway.home_activity_data(
                        site_id=SITE, guest_ssids=(SSID,),
                        from_utc=_stamp(range_start),
                        to_utc=_stamp(EVALUATED),
                        deadline=QueryDeadline.after(args.deadline),
                    )
                except Exception:
                    failures += 1
                durations.append(time.perf_counter() - started)
            ordered = sorted(durations[1:])
            results.append({
                "range": label,
                "days": round(
                    (EVALUATED - range_start).total_seconds() / 86400, 3
                ),
                "cold_seconds": round(durations[0], 6),
                "warm_p50_seconds": round(statistics.median(ordered), 6),
                "warm_p95_seconds": round(
                    ordered[max(0, int(len(ordered) * 0.95 + 0.999999) - 1)], 6
                ),
                "max_seconds": round(max(durations), 6),
                "deadline_failures": failures,
                "verified_visits": (
                    None if raw is None else raw["visits"]["verified_visit_count"]
                ),
                "traffic_fingerprints": (
                    None if raw is None else raw["traffic"]["included_fingerprint_count"]
                ),
            })
        report = {
            "rows_per_source": args.rows,
            "history_days": args.days,
            "seed_seconds": round(seed_seconds, 3),
            "runs_per_range": args.runs,
            "deadline_seconds": args.deadline,
            "plans": plans,
            "received_at_fallback_rows": _fallback_rows(repository),
            "results": results,
            "read_only_fingerprints_unchanged": (
                fingerprints_before == _fingerprints(repository)
            ),
        }
        print(json.dumps(report, indent=2, sort_keys=True))
        return int(
            not report["read_only_fingerprints_unchanged"]
            or any(item["deadline_failures"] for item in results)
        )


def _repository(root: Path) -> VisitRepository:
    return VisitRepository(VisitLifecycleConfig(
        enabled=True,
        db_path=str(root / "visits.sqlite3"),
        webhook_source=str(root / "normalized.log"),
        scan_interval_seconds=5,
        reconcile_interval_seconds=30,
        max_line_bytes=1_048_576,
        reader_max_lines_per_scan=5_000,
        reader_max_bytes_per_scan=16_777_216,
        reader_max_duration_seconds=20,
        reconcile_batch_size=500,
        pending_offline_batch_size=500,
        offline_match_grace_seconds=30,
        start_writer_slot_wait_ms=750,
        reader_writer_slot_wait_ms=250,
        reconciliation_writer_slot_wait_ms=250,
        sqlite_busy_timeout_ms=500,
        start_max_attempts=3,
        start_total_budget_ms=2_000,
        shutdown_timeout_seconds=20,
        max_offline_clock_skew_seconds=120,
        max_reported_duration_drift_seconds=300,
    ))


def _seed(repository: VisitRepository, row_count: int, days: int) -> float:
    started = time.perf_counter()
    visits = []
    authorizations = []
    events = []
    for index in range(row_count):
        at = EVALUATED - timedelta(
            days=index % days,
            seconds=(index * 7919) % 86_400 + 1,
        )
        timestamp = _stamp(at)
        visit_id = f"{index:08x}-0000-4000-8000-{index:012x}"
        session_id = f"{index:08x}-1111-4111-8111-{index:012x}"
        mac = "02:00:%02X:%02X:%02X:%02X" % (
            (index >> 24) & 255, (index >> 16) & 255,
            (index >> 8) & 255, index & 255,
        )
        visits.append((
            visit_id, SITE, mac, session_id, 1, "AUTHORIZED", timestamp,
            timestamp, "closed", timestamp, "client_offline",
            "controller_timestamp", SSID, SSID, 0, timestamp, 0,
        ))
        authorizations.append((
            visit_id, session_id, 1, 1, timestamp, "AUTHORIZED", SSID,
            timestamp,
        ))
        events.append((
            f"event-{index}", SITE, mac,
            None if index % 13 == 0 else timestamp, timestamp,
            index, index + 1, "unmatched" if index % 11 == 0 else "closed",
            timestamp, timestamp, SSID, index % 3600, index % 5_000_000,
        ))
    with closing(repository._connect()) as connection:  # noqa: SLF001
        connection.executemany(
            """
            INSERT INTO visits (
              visit_id,site_id,client_mac,start_auth_session_id,
              start_auth_run_number,start_final_reason,started_at,closed_at,
              status,updated_at,close_reason,close_time_source,start_ssid,
              final_ssid,duration_seconds,created_at,link_reconcile_attempt_count
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            visits,
        )
        connection.executemany(
            """
            INSERT INTO visit_authorizations (
              visit_id,auth_session_id,auth_run_number,authorization_attempt,
              authorized_at,final_reason,portal_ssid,created_at
            ) VALUES (?,?,?,?,?,?,?,?)
            """,
            authorizations,
        )
        connection.executemany(
            """
            INSERT INTO visit_source_events (
              event_id,event_type,site_id,client_mac,controller_event_at,
              received_at,source_identity,source_offset_start,source_offset_end,
              processing_result,first_processed_at,processed_at,ssid,
              reported_connected_seconds,reported_traffic_total_bytes
            ) VALUES (?,'omada.client_offline',?,?,?,?,
                      'capacity',?,?,?,?,?,?,?,?)
            """,
            events,
        )
        connection.execute(
            """
            INSERT INTO visit_reader_state (
              source_identity,source_path,source_offset,last_observed_size,
              retired_completed,missing_warning_emitted,updated_at
            ) VALUES ('capacity','/capacity',1,1,0,0,?)
            """,
            (_stamp(EVALUATED),),
        )
        connection.commit()
    return time.perf_counter() - started


def _fingerprints(repository: VisitRepository) -> tuple[int, ...]:
    with closing(repository._connect(readonly=True)) as connection:  # noqa: SLF001
        return (
            int(connection.execute("PRAGMA user_version").fetchone()[0]),
            int(connection.execute("SELECT COUNT(*) FROM visits").fetchone()[0]),
            int(connection.execute("SELECT COUNT(*) FROM visit_authorizations").fetchone()[0]),
            int(connection.execute("SELECT COUNT(*) FROM visit_source_events").fetchone()[0]),
            int(connection.execute("SELECT COUNT(*) FROM visit_reader_state").fetchone()[0]),
        )


def _fallback_rows(repository: VisitRepository) -> int:
    with closing(repository._connect(readonly=True)) as connection:  # noqa: SLF001
        return int(connection.execute(
            "SELECT COUNT(*) FROM visit_source_events "
            "WHERE controller_event_at IS NULL AND received_at IS NOT NULL"
        ).fetchone()[0])


def _stamp(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="milliseconds").replace(
        "+00:00", "Z"
    )


if __name__ == "__main__":
    raise SystemExit(main())
