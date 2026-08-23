"""Reproducible synthetic capacity evidence for Current State schema v1."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
import statistics
import tempfile
import time
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

from app.current_state.cleanup import CurrentStateCleanup
from app.current_state.config import current_state_config_from_settings
from app.current_state.models import CurrentStateCycle, format_utc
from app.current_state.normalizer import canonical_scope
from app.current_state.read_service import CurrentStateReadService
from app.current_state.repository import CurrentStateRepository


SITE = "a" * 24
SSID = "Zefer_Parki"
UTC = timezone.utc


def _settings(path: Path) -> dict[str, str]:
    return {
        "current_state_enabled": "true",
        "current_state_db_path": str(path),
        "current_state_site_ids": SITE,
        "current_state_client_ssids_json": json.dumps([SSID]),
    }


def _mac(index: int) -> str:
    value = index % (1 << 48)
    return ":".join(f"{(value >> shift) & 0xff:02X}" for shift in (40, 32, 24, 16, 8, 0))


def _cycle_values(identifier: str, started: str, rows: int) -> tuple[object, ...]:
    scope_json, scope_hash = canonical_scope("client", SITE, (SSID,))
    return (
        identifier, "client", SITE, started, started, 1, "success", 1,
        scope_json, scope_hash, rows, rows, rows, 0, 0, 0, 0, 0, 0, 1,
        None, 1, started,
    )


def _client_values(cycle_id: str, observed: str, index: int) -> tuple[object, ...]:
    ap_mac = _mac(10_000 + index % 30)
    down = index * 100
    up = index * 25
    auth = ("authorized", "pending", "other", "unknown")[index % 4]
    code = (2, 1, 0, None)[index % 4]
    return (
        cycle_id, "client", SITE, observed, _mac(index), f"client-{index}",
        f"host-{index}", "synthetic", f"192.0.2.{index % 250 + 1}", SSID,
        f"ap-{index % 30}", ap_mac, index % 2,
        "2.4GHz" if index % 2 == 0 else "5GHz", 1 + index % 165,
        -30 - index % 60, index % 50, index * 3, code, auth,
        down, up, down + up, True, True,
    )


def _seed_history(
    repository: CurrentStateRepository,
    *,
    history_rows: int,
    rows_per_cycle: int,
) -> tuple[int, int]:
    cycle_sql = """
        INSERT INTO current_state_cycles (
          cycle_id,kind,site_id,capture_started_at,capture_finished_at,
          complete,result,source_scope_version,source_scope_json,
          source_scope_hash,source_rows_reported,items_seen,items_stored,
          items_skipped,unidentified_count,duplicate_identity_count,
          unknown_status_count,error_count,data_quality_warning_count,
          page_count,failure_category,duration_ms,created_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """
    row_sql = """
        INSERT INTO current_client_state (
          cycle_id,cycle_kind,site_id,observed_at,client_mac,name,hostname,
          device_type,ip,ssid,ap_name,ap_mac,radio_id,band,channel,rssi,snr,
          controller_uptime,auth_status_code,auth_classification,
          controller_traffic_down,controller_traffic_up,
          controller_traffic_total,active,wireless
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """
    remaining = history_rows
    cycle_number = 0
    peak_wal = 0
    peak_shm = 0
    start = datetime(2026, 8, 20, tzinfo=UTC)
    connection = sqlite3.connect(repository.config.db_path)
    try:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=NORMAL")
        while remaining:
            row_count = min(rows_per_cycle, remaining)
            identifier = f"history-{cycle_number:06d}"
            observed = format_utc(start + timedelta(seconds=30 * cycle_number))
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(cycle_sql, _cycle_values(identifier, observed, row_count))
            connection.executemany(
                row_sql,
                (_client_values(identifier, observed, index) for index in range(row_count)),
            )
            connection.commit()
            remaining -= row_count
            cycle_number += 1
            wal = Path(str(repository.config.db_path) + "-wal")
            if wal.exists():
                peak_wal = max(peak_wal, wal.stat().st_size)
            shm = Path(str(repository.config.db_path) + "-shm")
            if shm.exists():
                peak_shm = max(peak_shm, shm.stat().st_size)
    finally:
        connection.close()
    repository._enforce_modes()
    return peak_wal, peak_shm


def _seed_current(repository: CurrentStateRepository, rows: int) -> str:
    identifier = "latest-current-10000"
    observed = "2026-08-23T10:00:00.000Z"
    cycle = CurrentStateCycle(
        cycle_id=identifier,
        kind="client",
        site_id=SITE,
        capture_started_at=observed,
        capture_finished_at=observed,
        complete=True,
        result="success",
        source_scope_version=1,
        source_scope_json=canonical_scope("client", SITE, (SSID,))[0],
        source_scope_hash=canonical_scope("client", SITE, (SSID,))[1],
        source_rows_reported=rows,
        items_seen=rows,
        items_stored=rows,
        items_skipped=0,
        unidentified_count=0,
        duplicate_identity_count=0,
        unknown_status_count=rows // 4,
        error_count=0,
        data_quality_warning_count=0,
        page_count=max(1, (rows + 499) // 500),
        failure_category=None,
        duration_ms=1,
        created_at=observed,
    )
    columns = (
        "cycle_id", "cycle_kind", "site_id", "observed_at", "client_mac",
        "name", "hostname", "device_type", "ip", "ssid", "ap_name",
        "ap_mac", "radio_id", "band", "channel", "rssi", "snr",
        "controller_uptime", "auth_status_code", "auth_classification",
        "controller_traffic_down", "controller_traffic_up",
        "controller_traffic_total", "active", "wireless",
    )
    rows_payload = [dict(zip(columns, _client_values(identifier, observed, index))) for index in range(rows)]
    repository.publish_cycle(cycle, client_rows=rows_payload)
    return observed


def _seed_aps(repository: CurrentStateRepository, rows: int = 30) -> None:
    identifier = "latest-ap-30"
    observed = "2026-08-23T10:00:00.000Z"
    scope_json, scope_hash = canonical_scope("ap", SITE, ())
    cycle = CurrentStateCycle(
        cycle_id=identifier,
        kind="ap",
        site_id=SITE,
        capture_started_at=observed,
        capture_finished_at=observed,
        complete=True,
        result="success",
        source_scope_version=1,
        source_scope_json=scope_json,
        source_scope_hash=scope_hash,
        source_rows_reported=rows,
        items_seen=rows,
        items_stored=rows,
        items_skipped=0,
        unidentified_count=0,
        duplicate_identity_count=0,
        unknown_status_count=0,
        error_count=0,
        data_quality_warning_count=0,
        page_count=1,
        failure_category=None,
        duration_ms=1,
        created_at=observed,
    )
    values = []
    for index in range(rows):
        values.append({
            "cycle_id": identifier,
            "cycle_kind": "ap",
            "site_id": SITE,
            "observed_at": observed,
            "ap_mac": _mac(10_000 + index),
            "name": f"ap-{index}",
            "ip": f"198.51.100.{index + 1}",
            "model": "synthetic",
            "firmware_version": "evidence-only",
            "status_code": 1,
            "status_classification": "online",
            "last_seen_ms": 0,
            "controller_uptime": index,
            "uptime_raw": None,
        })
    repository.publish_cycle(cycle, ap_rows=values)


def _measure(operation: Callable[[], object], repeats: int = 5) -> dict[str, float]:
    values = []
    for _ in range(repeats):
        started = time.perf_counter()
        operation()
        values.append((time.perf_counter() - started) * 1000)
    ordered = sorted(values)
    p95_index = max(0, min(len(ordered) - 1, int(len(ordered) * 0.95) - 1))
    return {
        "min_ms": round(min(values), 3),
        "mean_ms": round(statistics.fmean(values), 3),
        "p95_ms": round(ordered[p95_index], 3),
        "max_ms": round(max(values), 3),
    }


def _read_benchmark(repository: CurrentStateRepository) -> tuple[dict[str, object], dict[str, object]]:
    service = CurrentStateReadService(repository)
    evaluated = "2026-08-23T10:00:30.000Z"
    first = service.list_current_clients(SITE, limit=100, evaluated_at_utc=evaluated)
    cursor = first.next_cursor
    operations: dict[str, Callable[[], object]] = {
        "summary": lambda: service.get_current_client_summary(SITE, evaluated_at_utc=evaluated),
        "first_page": lambda: service.list_current_clients(SITE, limit=100, evaluated_at_utc=evaluated),
        "cursor_page": lambda: service.list_current_clients(SITE, limit=100, cursor=cursor, evaluated_at_utc=evaluated),
        "traffic_sort": lambda: service.list_current_clients(SITE, limit=100, sort="controller_traffic_total", evaluated_at_utc=evaluated),
        "uptime_sort": lambda: service.list_current_clients(SITE, limit=100, sort="controller_uptime", evaluated_at_utc=evaluated),
        "ap_filter": lambda: service.list_current_clients(SITE, limit=100, ap_mac=_mac(10_000), evaluated_at_utc=evaluated),
        "auth_filter": lambda: service.list_current_clients(SITE, limit=100, auth_classification="authorized", evaluated_at_utc=evaluated),
        "ap_summary": lambda: service.get_current_ap_summary(SITE, evaluated_at_utc=evaluated),
        "history_24h_prototype": lambda: _history_24h(repository),
    }
    timings = {name: _measure(operation) for name, operation in operations.items()}
    plans = {
        "latest_cycle": repository.explain(
            "SELECT * FROM current_state_cycles WHERE kind=? AND site_id=? ORDER BY capture_started_at DESC LIMIT 1",
            ("client", SITE),
        ),
        "traffic_sort": repository.explain(
            "SELECT * FROM current_client_state WHERE cycle_id=? ORDER BY controller_traffic_total IS NULL, controller_traffic_total DESC, client_mac ASC LIMIT 101",
            ("latest-current-10000",),
        ),
        "uptime_sort": repository.explain(
            "SELECT * FROM current_client_state WHERE cycle_id=? ORDER BY controller_uptime IS NULL, controller_uptime DESC, client_mac ASC LIMIT 101",
            ("latest-current-10000",),
        ),
        "ap_filter": repository.explain(
            "SELECT * FROM current_client_state WHERE cycle_id=? AND ap_mac=? ORDER BY controller_traffic_total IS NULL, controller_traffic_total DESC, client_mac ASC LIMIT 101",
            ("latest-current-10000", _mac(10_000)),
        ),
        "auth_filter": repository.explain(
            "SELECT * FROM current_client_state WHERE cycle_id=? AND auth_classification=? ORDER BY controller_traffic_total IS NULL, controller_traffic_total DESC, client_mac ASC LIMIT 101",
            ("latest-current-10000", "authorized"),
        ),
        "history_24h": repository.explain(
            "SELECT ap_mac, COUNT(*) FROM current_client_state x JOIN current_state_cycles c ON c.cycle_id=x.cycle_id WHERE c.kind='client' AND c.site_id=? AND c.complete=1 AND c.capture_started_at>=? GROUP BY ap_mac",
            (SITE, "2026-08-20T00:00:00.000Z"),
        ),
    }
    return timings, plans


def _history_24h(repository: CurrentStateRepository) -> tuple[tuple[object, ...], ...]:
    with repository.read_connection() as connection:
        rows = connection.execute(
            """
            SELECT x.ap_mac, COUNT(*) AS observed_clients,
                   COUNT(DISTINCT x.client_mac) AS distinct_clients
            FROM current_client_state x
            JOIN current_state_cycles c ON c.cycle_id=x.cycle_id
            WHERE c.kind='client' AND c.site_id=? AND c.complete=1
              AND c.capture_started_at>=?
            GROUP BY x.ap_mac
            """,
            (SITE, "2026-08-20T00:00:00.000Z"),
        ).fetchall()
    return tuple(tuple(row) for row in rows)


def _index_bytes(path: Path) -> int | None:
    connection = sqlite3.connect(path)
    try:
        row = connection.execute(
            "SELECT SUM(pgsize) FROM dbstat WHERE name LIKE 'idx_%' OR name LIKE 'sqlite_autoindex_%'"
        ).fetchone()
        return int(row[0] or 0)
    except sqlite3.Error:
        return None
    finally:
        connection.close()


def _cleanup_benchmark(root: Path) -> dict[str, object]:
    path = root / "cleanup.sqlite3"
    config = replace(
        current_state_config_from_settings(_settings(path)),
        cleanup_max_rows_per_transaction=100,
        cleanup_max_cycles_per_run=10,
    )
    repository = CurrentStateRepository(config)
    repository.initialize()
    sentinel = sqlite3.connect(path)
    try:
        sentinel.execute("PRAGMA journal_mode=WAL")
        peak_wal, _ = _seed_history(
            repository, history_rows=1_000, rows_per_cycle=1_000
        )
        _seed_current(repository, 1)
        started = time.perf_counter()
        result = CurrentStateCleanup(repository, config).run_once(
            now_utc="2026-08-23T10:00:00.000Z"
        )
        duration_ms = (time.perf_counter() - started) * 1000
        wal = Path(str(path) + "-wal")
        if wal.exists():
            peak_wal = max(peak_wal, wal.stat().st_size)
    finally:
        sentinel.close()
    return {
        "duration_ms": round(duration_ms, 3),
        "oversized_cycle_rows": 1_000,
        "row_budget": 100,
        "deleted_cycles": result.deleted_cycles,
        "deleted_client_rows": result.deleted_client_rows,
        "whole_cycle_deleted": result.deleted_client_rows == 1_000,
        "peak_wal_bytes": peak_wal,
    }


def run(history_rows: int, current_rows: int, rows_per_cycle: int) -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="current-state-capacity-") as directory:
        root = Path(directory)
        path = root / "current_state.sqlite3"
        repository = CurrentStateRepository(
            current_state_config_from_settings(_settings(path))
        )
        repository.initialize()
        sentinel = sqlite3.connect(path)
        try:
            sentinel.execute("PRAGMA journal_mode=WAL")
            write_started = time.perf_counter()
            peak_wal, peak_shm = _seed_history(
                repository,
                history_rows=history_rows,
                rows_per_cycle=rows_per_cycle,
            )
            _seed_current(repository, current_rows)
            _seed_aps(repository)
            write_seconds = time.perf_counter() - write_started
            wal_path = Path(str(path) + "-wal")
            shm_path = Path(str(path) + "-shm")
            if wal_path.exists():
                peak_wal = max(peak_wal, wal_path.stat().st_size)
            if shm_path.exists():
                peak_shm = max(peak_shm, shm_path.stat().st_size)
        finally:
            sentinel.close()
        connection = sqlite3.connect(path)
        try:
            connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        finally:
            connection.close()
        db_bytes = path.stat().st_size
        shm = Path(str(path) + "-shm")
        shm_bytes = shm.stat().st_size if shm.exists() else 0
        measured_rows = history_rows + current_rows
        projected_5m = round(db_bytes * (5_000_000 / measured_rows))
        disk = shutil.disk_usage(path)
        projected_headroom = disk.free - projected_5m - peak_wal
        timings, plans = _read_benchmark(repository)
        return {
            "schema_version": 1,
            "history_rows": history_rows,
            "current_snapshot_rows": current_rows,
            "total_measured_rows": measured_rows,
            "rows_per_history_cycle": rows_per_cycle,
            "write_seconds": round(write_seconds, 3),
            "db_bytes": db_bytes,
            "index_bytes": _index_bytes(path),
            "projected_db_bytes_at_5m_rows": projected_5m,
            "peak_wal_bytes": peak_wal,
            "peak_shm_bytes": peak_shm,
            "shm_bytes": shm_bytes,
            "host_filesystem_total_bytes": disk.total,
            "host_filesystem_free_bytes": disk.free,
            "local_projected_remaining_headroom_bytes": projected_headroom,
            "local_projected_remaining_headroom_ratio": round(projected_headroom / disk.total, 6),
            "production_disk_gate": "pending_production_filesystem_evidence",
            "read_timings": timings,
            "query_plans": plans,
            "cleanup": _cleanup_benchmark(root),
            "db_mode": oct(os.stat(path).st_mode & 0o777) if os.name == "posix" else "platform_not_posix",
            "wal_shm_mode_contract": "checked_by_posix_tests" if os.name != "posix" else "measured_at_runtime",
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--history-rows", type=int, default=1_440_000)
    parser.add_argument("--current-rows", type=int, default=10_000)
    parser.add_argument("--rows-per-cycle", type=int, default=250)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = run(args.history_rows, args.current_rows, args.rows_per_cycle)
    encoded = json.dumps(result, indent=2, sort_keys=True)
    if args.output is not None:
        args.output.write_text(encoded + "\n", encoding="utf-8")
    print(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
