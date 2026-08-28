"""Deterministic synthetic AP-24H capacity/read-only evidence runner."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sqlite3
import tempfile
import time
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.analytics.home_ap_24h import HomeAp24ReadService
from app.analytics.source_gateway import QueryDeadline
from app.current_state.config import current_state_config_from_settings
from app.current_state.normalizer import canonical_scope
from app.current_state.read_service import CurrentStateReadService
from app.current_state.repository import CurrentStateRepository
from app.observations.models import ObservationConfig
from app.observations.read_service import ObservationReadService
from app.observations.repository import ObservationRepository


UTC = timezone.utc
SITE = "a" * 24
ANCHOR = datetime(2026, 8, 28, 12, tzinfo=UTC)


def stamp(value):
    return value.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def mac(index):
    return f"02:00:{(index >> 16) & 255:02X}:{(index >> 8) & 255:02X}:{index & 255:02X}:01"


def fingerprint(path):
    digest = hashlib.sha256()
    with open(path, "rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return (Path(path).stat().st_size, digest.hexdigest())


def populate_current(repository, aps, cycles):
    scope_json, scope_hash = canonical_scope("ap", SITE, ())
    start = ANCHOR - timedelta(hours=24)
    with closing(sqlite3.connect(repository.db_path)) as connection:
        connection.execute("BEGIN IMMEDIATE")
        for cycle_index in range(cycles):
            moment = start + timedelta(seconds=180 * cycle_index)
            if moment >= ANCHOR:
                break
            cycle_id = f"capacity-{cycle_index:04d}"
            timestamp = stamp(moment)
            connection.execute(
                """INSERT INTO current_state_cycles VALUES
                (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (cycle_id, "ap", SITE, timestamp, timestamp, 1, "success", 1,
                 scope_json, scope_hash, aps, aps, aps, 0, 0, 0, 0, 0, 0, 1,
                 None, 1, timestamp),
            )
            connection.executemany(
                """INSERT INTO current_ap_state VALUES
                (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                ((cycle_id, "ap", SITE, timestamp, mac(index), f"AP-{index}", None,
                  "EAP", None, 0 if index == 0 and cycle_index % 20 == 0 else 1,
                  "unknown", None, None, None) for index in range(aps)),
            )
        connection.commit()


def populate_observations(repository, aps, cycles):
    """Build a dense query-capacity stress fixture, not collector output."""
    start = ANCHOR - timedelta(hours=24)
    with closing(sqlite3.connect(repository.db_path)) as connection:
        connection.execute("BEGIN IMMEDIATE")
        for cycle_index in range(cycles):
            moment = start + timedelta(seconds=180 * cycle_index)
            if moment >= ANCHOR:
                break
            cycle_id = f"obs-capacity-{cycle_index:04d}"
            timestamp = stamp(moment)
            connection.execute(
                """INSERT INTO observation_cycles (
                    cycle_id, kind, site_id, state, started_at, finished_at,
                    complete, result, source_rows_reported, items_seen,
                    items_stored, items_skipped, error_count,
                    data_quality_warning_count, created_at, updated_at
                ) VALUES (?, 'ap_dynamic', ?, 'completed', ?, ?, 1, 'success',
                          ?, ?, ?, 0, 0, 0, ?, ?)""",
                (cycle_id, SITE, timestamp, timestamp, aps, aps, aps, timestamp, timestamp),
            )
            connection.executemany(
                """INSERT INTO ap_observations (
                    cycle_id, observed_at, site_id, ap_mac, partial,
                    overview_ok, wired_uplink_ok, lan_traffic_ok, radios_ok,
                    overview_observed_at, wired_observed_at, lan_observed_at,
                    name, model
                ) VALUES (?, ?, ?, ?, 0, 1, 1, 1, 1, ?, ?, ?, ?, 'EAP')""",
                (
                    (
                        cycle_id, timestamp, SITE, mac(index), timestamp,
                        timestamp, timestamp, f"AP-{index}",
                    )
                    for index in range(aps)
                ),
            )
        connection.commit()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--aps", type=int, default=500)
    parser.add_argument("--cycles", type=int, default=481)
    parser.add_argument("--observation-cycles", type=int, default=481)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--deadline-seconds", type=int, default=10)
    parser.add_argument("--root", default=str(Path(tempfile.gettempdir())))
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="ap24-capacity-", dir=args.root) as directory:
        root = Path(directory)
        current_path = root / "current.sqlite3"
        observation_path = root / "observations.sqlite3"
        current_config = current_state_config_from_settings({
            "current_state_enabled": "true", "current_state_db_path": str(current_path),
            "current_state_site_ids": SITE, "current_state_client_ssids_json": '["guest"]',
            "observation_db_path": str(observation_path),
        })
        current = CurrentStateRepository(current_config); current.initialize()
        observations = ObservationRepository(ObservationConfig(
            enabled=True, db_path=str(observation_path), dynamic_retention_days=180,
            config_retention_days=730, cleanup_initial_delay_seconds=900,
            cleanup_interval_seconds=86400, cleanup_batch_size=5000,
            cleanup_max_duration_seconds=30, shutdown_timeout_seconds=20,
        )); observations.initialize(stamp(ANCHOR - timedelta(days=2)))
        populate_current(current, args.aps, args.cycles)
        populate_observations(observations, args.aps, args.observation_cycles)
        before = (fingerprint(current_path), fingerprint(observation_path))
        service = HomeAp24ReadService(
            CurrentStateReadService(current), ObservationReadService(observations),
            current_state_ap_interval_seconds=60, quality_gap_seconds=180,
            observation_dynamic_max_requests=200,
        )
        elapsed_samples = []
        value = None
        for _ in range(args.runs):
            started = time.perf_counter()
            value = service.get_home_ap_24h(
                SITE, evaluated_at_utc=ANCHOR, limit=20,
                deadline=QueryDeadline.after(args.deadline_seconds),
            )
            elapsed_samples.append(time.perf_counter() - started)
        assert value is not None
        elapsed_p95 = sorted(elapsed_samples)[max(0, math.ceil(0.95 * len(elapsed_samples)) - 1)]
        response_bytes = len(json.dumps(value, separators=(",", ":"), sort_keys=True).encode())
        after = (fingerprint(current_path), fingerprint(observation_path))
        with current.read_connection() as connection:
            current_plan = [row[3] for row in connection.execute(
                "EXPLAIN QUERY PLAN SELECT a.* FROM current_ap_state a JOIN current_state_cycles c ON c.cycle_id=a.cycle_id WHERE a.site_id=? AND c.kind='ap' AND c.result='success' AND c.complete=1 AND c.capture_started_at>=? AND c.capture_started_at<?",
                (SITE, stamp(ANCHOR - timedelta(hours=25)), stamp(ANCHOR)),
            )]
            current_latest_plan = [row[3] for row in connection.execute(
                "EXPLAIN QUERY PLAN SELECT a.ap_mac FROM current_ap_state a JOIN current_state_cycles c ON c.cycle_id=a.cycle_id WHERE a.site_id=? AND c.kind='ap' AND c.result='success' AND c.complete=1 AND c.cycle_id=(SELECT latest.cycle_id FROM current_state_cycles latest WHERE latest.kind='ap' AND latest.site_id=? AND latest.result='success' AND latest.complete=1 AND latest.capture_started_at<? ORDER BY latest.capture_started_at DESC,latest.cycle_id DESC LIMIT 1)",
                (SITE, SITE, stamp(ANCHOR)),
            )]
        with observations.read_connection() as connection:
            observation_plan = [row[3] for row in connection.execute(
                "EXPLAIN QUERY PLAN SELECT o.* FROM ap_observations o JOIN observation_cycles c ON c.cycle_id=o.cycle_id WHERE o.site_id=? AND c.kind='ap_dynamic' AND c.state='completed' AND o.observed_at>=? AND o.observed_at<? ORDER BY o.observed_at",
                (SITE, stamp(ANCHOR - timedelta(hours=24)), stamp(ANCHOR)),
            )]
        print(json.dumps({
            "fixture_kind": "query-capacity stress fixture",
            "aps": args.aps, "current_cycles_requested": args.cycles,
            "observation_cycles_requested": args.observation_cycles,
            "runs": args.runs,
            "elapsed_seconds": [round(value, 3) for value in elapsed_samples],
            "p95_seconds": round(elapsed_p95, 3),
            "max_seconds": round(max(elapsed_samples), 3),
            "response_bytes": response_bytes,
            "deadline_seconds": args.deadline_seconds,
            "deadline_reached": any(value >= args.deadline_seconds for value in elapsed_samples),
            "read_only_fingerprints_unchanged": before == after,
            "returned_items": len(value["items"]), "summary_ap_count": value["summary"]["ap_count_in_window"],
            "current_plan": current_plan,
            "current_latest_inventory_plan": current_latest_plan,
            "observation_plan": observation_plan,
        }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
