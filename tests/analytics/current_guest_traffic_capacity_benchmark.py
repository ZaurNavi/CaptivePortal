"""Reproducible 10k+10k capacity fixture for Owner/Tech Lead execution.

This is not a pytest test.  It creates only temporary Current State databases,
never contacts Omada, and fingerprints every SQLite file before/after timed
read-only service calls.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import tempfile
import time
from dataclasses import asdict
from pathlib import Path

from app.analytics.current_guest_traffic import CurrentGuestTrafficReadService
from app.current_state.config import current_state_config_from_settings
from app.current_state.models import CurrentStateCycle
from app.current_state.normalizer import canonical_scope
from app.current_state.read_service import CurrentStateReadService
from app.current_state.repository import CurrentStateRepository


SITE = "a" * 24
SSIDS = ("Guest", "Guest2")
BASELINE_AT = "2026-09-01T09:59:00.000Z"
CURRENT_AT = "2026-09-01T10:00:00.000Z"
EVALUATED_AT = "2026-09-01T10:00:30.000Z"
POPULATION = 10_000


def _mac(index: int, *, prefix: int = 2) -> str:
    return ":".join(
        f"{value:02X}"
        for value in (
            prefix,
            (index >> 24) & 0xFF,
            (index >> 16) & 0xFF,
            (index >> 8) & 0xFF,
            index & 0xFF,
            1,
        )
    )


def _config(root: Path, name: str):
    return current_state_config_from_settings({
        "current_state_enabled": "true",
        "current_state_db_path": str(root / f"{name}.sqlite3"),
        "current_state_site_ids": SITE,
        "current_state_client_ssids_json": json.dumps(SSIDS),
        "observation_db_path": str(root / "observations.sqlite3"),
        "visit_lifecycle_db_path": str(root / "visits.sqlite3"),
        "visitor_registry_db_path": str(root / "registry.sqlite3"),
        "portal_counter_db_path": str(root / "portal.sqlite3"),
        "public_traffic_db_path": str(root / "traffic.sqlite3"),
    })


def _cycle(cycle_id: str, at: str, count: int) -> CurrentStateCycle:
    scope_json, scope_hash = canonical_scope("client", SITE, SSIDS)
    return CurrentStateCycle(
        cycle_id=cycle_id,
        kind="client",
        site_id=SITE,
        capture_started_at=at,
        capture_finished_at=at,
        complete=True,
        result="success",
        source_scope_version=1,
        source_scope_json=scope_json,
        source_scope_hash=scope_hash,
        source_rows_reported=count,
        items_seen=count,
        items_stored=count,
        items_skipped=0,
        unidentified_count=0,
        duplicate_identity_count=0,
        unknown_status_count=0,
        error_count=0,
        data_quality_warning_count=0,
        page_count=100,
        failure_category=None,
        duration_ms=1_000,
        created_at=at,
    )


def _row(
    cycle_id: str,
    at: str,
    mac: str,
    *,
    auth: str,
    ssid: str,
    uptime: int | None,
    down: int | None,
    up: int | None,
    ap: str,
) -> dict[str, object]:
    return {
        "cycle_id": cycle_id,
        "cycle_kind": "client",
        "site_id": SITE,
        "observed_at": at,
        "client_mac": mac,
        "name": None,
        "hostname": None,
        "device_type": None,
        "ip": None,
        "ssid": ssid,
        "ap_name": None,
        "ap_mac": ap,
        "radio_id": None,
        "band": None,
        "channel": None,
        "rssi": None,
        "snr": None,
        "controller_uptime": uptime,
        "auth_status_code": 2 if auth == "authorized" else None,
        "auth_classification": auth,
        "controller_traffic_down": down,
        "controller_traffic_up": up,
        "controller_traffic_total": (
            down + up if down is not None and up is not None else None
        ),
        "active": True,
        "wireless": True,
    }


def _mixed_rows() -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    baseline: list[dict[str, object]] = []
    current: list[dict[str, object]] = []
    for index in range(POPULATION):
        mac = _mac(index)
        auth = "unknown" if index % 97 == 0 else "pending" if index % 89 == 0 else "authorized"
        mode = index % 11
        baseline_uptime: int | None = 1_000
        current_uptime: int | None = 1_060
        baseline_down: int | None = index * 1_000
        baseline_up: int | None = index * 700
        current_down: int | None = (baseline_down or 0) + (index % 500)
        current_up: int | None = (baseline_up or 0) + (index % 300)
        baseline_ssid = current_ssid = "Guest"
        if mode == 2:  # true zero
            current_down, current_up = baseline_down, baseline_up
        elif mode == 3:  # frozen
            current_uptime = baseline_uptime
        elif mode == 4:  # connection reset
            current_uptime = 1
        elif mode == 5:  # direction reset
            current_down = max(0, (baseline_down or 0) - 1)
        elif mode == 6:  # missing direction
            current_up = None
        elif mode == 7:  # SSID transition
            baseline_ssid = "Guest2"
        elif mode == 8:  # missing uptime / diagnostic-only growth
            current_uptime = None
        elif mode == 9:  # missing compatible baseline via replacement identity
            mac = _mac(index, prefix=4)
        baseline.append(_row(
            "baseline", BASELINE_AT, _mac(index), auth=auth,
            ssid=baseline_ssid, uptime=baseline_uptime,
            down=baseline_down, up=baseline_up, ap="10:20:30:40:50:60",
        ))
        current.append(_row(
            "current", CURRENT_AT, mac, auth=auth,
            ssid=current_ssid, uptime=current_uptime,
            down=current_down, up=current_up, ap="10:20:30:40:50:61",
        ))
    return baseline, current


def _stack(root: Path, name: str, baseline, current):
    repository = CurrentStateRepository(_config(root, name))
    repository.initialize()
    if baseline is not None:
        repository.publish_cycle(
            _cycle("baseline", BASELINE_AT, len(baseline)),
            client_rows=baseline,
        )
    repository.publish_cycle(
        _cycle("current", CURRENT_AT, len(current)), client_rows=current
    )
    service = CurrentGuestTrafficReadService(CurrentStateReadService(repository))
    return repository, service


def _fingerprint(path: Path) -> dict[str, dict[str, object]]:
    if not path.is_file():
        raise RuntimeError("Current State database is unavailable")
    main_bytes = path.read_bytes()
    wal_path = Path(f"{path}-wal")
    # Opening a WAL-mode database read-only may create an empty WAL and SHM.
    # Durable comparison therefore models WAL logical bytes: absent and empty
    # are equivalent, while every non-empty byte remains strictly fingerprinted.
    wal_bytes = wal_path.read_bytes() if wal_path.is_file() else b""
    return {
        "main": _byte_fingerprint(main_bytes),
        "wal": _byte_fingerprint(wal_bytes),
    }


def _byte_fingerprint(data: bytes) -> dict[str, object]:
    return {
        "size": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def _assert_fingerprint_contract(root: Path) -> None:
    database = root / "fingerprint-contract.sqlite3"
    wal = Path(f"{database}-wal")
    database.write_bytes(b"main-database")
    missing_wal = _fingerprint(database)
    wal.write_bytes(b"")
    empty_wal = _fingerprint(database)
    if missing_wal != empty_wal:
        raise RuntimeError("missing and empty WAL fingerprints differ")
    wal.write_bytes(b"non-empty-wal")
    if _fingerprint(database) == empty_wal:
        raise RuntimeError("non-empty WAL mutation was not detected")
    wal.write_bytes(b"")
    database.write_bytes(b"changed-main-database")
    if _fingerprint(database) == empty_wal:
        raise RuntimeError("main database mutation was not detected")


def _measure(service, *, limit: int, runs: int) -> dict[str, object]:
    durations = []
    semantic = None
    for _ in range(runs):
        started = time.perf_counter()
        result = service.get_current_guest_traffic(
            SITE, evaluated_at_utc=EVALUATED_AT, limit=limit
        )
        durations.append(time.perf_counter() - started)
        current = {
            "status": result.status,
            "source_health": result.source_health_status,
            "rate_evidence": result.rate_evidence_status,
            "population": result.population_count,
            "valid": result.rate_valid_count,
            "partial": result.rate_partial_count,
            "unavailable": result.rate_unavailable_count,
            "returned": result.page.returned_count,
            "first": [asdict(item) for item in result.items[:3]],
        }
        if semantic is not None and current != semantic:
            raise RuntimeError("benchmark result is nondeterministic")
        semantic = current
    ordered = sorted(durations)
    p95_index = max(0, min(len(ordered) - 1, int(0.95 * len(ordered) + 0.999) - 1))
    return {
        "runs": runs,
        "p50_seconds": statistics.median(durations),
        "p95_seconds": ordered[p95_index],
        "max_seconds": max(durations),
        "semantic": semantic,
    }


def _plans(repository: CurrentStateRepository) -> dict[str, list[str]]:
    queries = {
        "current_cycle": """
            SELECT * FROM current_state_cycles
            WHERE site_id=? AND kind='client' AND source_scope_hash=?
              AND result='success' AND complete=1
            ORDER BY capture_started_at DESC, cycle_id DESC LIMIT 1
        """,
        "newer_attempt": """
            SELECT * FROM current_state_cycles
            WHERE site_id=? AND kind='client' AND source_scope_hash=?
              AND capture_started_at<=?
              AND (capture_started_at>? OR (capture_started_at=? AND cycle_id>?))
            ORDER BY capture_started_at DESC, cycle_id DESC LIMIT 1
        """,
        "scoped_counts": """
            SELECT COUNT(*), SUM(auth_classification='authorized'),
                   SUM(auth_classification='unknown')
            FROM current_client_state WHERE cycle_id=? AND site_id=?
        """,
        "baseline_cycle": """
            SELECT * FROM current_state_cycles
            WHERE site_id=? AND kind='client' AND source_scope_hash=?
              AND result='success' AND complete=1 AND capture_started_at<?
            ORDER BY capture_started_at DESC, cycle_id DESC LIMIT 1
        """,
        "current_rows": """
            SELECT * FROM current_client_state
            WHERE cycle_id=? AND site_id=? ORDER BY client_mac
        """,
        "matching_baseline": """
            SELECT baseline.* FROM current_client_state AS baseline
            JOIN current_client_state AS current
              ON current.cycle_id=? AND current.site_id=?
             AND current.client_mac=baseline.client_mac
            WHERE baseline.cycle_id=? AND baseline.site_id=?
            ORDER BY baseline.client_mac
        """,
    }
    _, scope_hash = canonical_scope("client", SITE, SSIDS)
    params = {
        "current_cycle": (SITE, scope_hash),
        "newer_attempt": (
            SITE, scope_hash, EVALUATED_AT, CURRENT_AT, CURRENT_AT, "current"
        ),
        "scoped_counts": ("current", SITE),
        "baseline_cycle": (SITE, scope_hash, CURRENT_AT),
        "current_rows": ("current", SITE),
        "matching_baseline": ("current", SITE, "baseline", SITE),
    }
    result = {}
    with repository.read_connection() as connection:
        connection.execute("BEGIN")
        for name, query in queries.items():
            result[name] = [
                str(row[3])
                for row in connection.execute(
                    f"EXPLAIN QUERY PLAN {query}", params[name]
                ).fetchall()
            ]
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=10)
    args = parser.parse_args()
    if args.runs < 10:
        raise SystemExit("--runs must be at least 10")
    with tempfile.TemporaryDirectory(prefix="traffic07-read-") as temporary:
        root = Path(temporary)
        _assert_fingerprint_contract(root)
        baseline, current = _mixed_rows()
        repository, service = _stack(root, "global", baseline, current)
        database = Path(repository.config.db_path)
        before = _fingerprint(database)
        measurements = {
            "R50": _measure(service, limit=50, runs=args.runs),
            "R200": _measure(service, limit=200, runs=args.runs),
            "RG10K": _measure(service, limit=200, runs=args.runs),
        }
        after = _fingerprint(database)
        if before != after:
            raise RuntimeError("read-only benchmark changed Current State storage")

        semantic = {}
        variants = {
            "RZERO": (None, []),
            "RNOBASE": (None, [_row("current", CURRENT_AT, down=1, up=1, auth="authorized", ssid="Guest", uptime=100, mac=_mac(1), ap="10:20:30:40:50:60")]),
            "RFROZEN": ([_row("baseline", BASELINE_AT, down=1, up=1, auth="authorized", ssid="Guest", uptime=100, mac=_mac(1), ap="10:20:30:40:50:60")], [_row("current", CURRENT_AT, down=1, up=1, auth="authorized", ssid="Guest", uptime=100, mac=_mac(1), ap="10:20:30:40:50:60")]),
            "RRESET": ([_row("baseline", BASELINE_AT, down=10, up=10, auth="authorized", ssid="Guest", uptime=100, mac=_mac(1), ap="10:20:30:40:50:60")], [_row("current", CURRENT_AT, down=1, up=1, auth="authorized", ssid="Guest", uptime=1, mac=_mac(1), ap="10:20:30:40:50:60")]),
        }
        for name, (variant_baseline, variant_current) in variants.items():
            _repo, variant_service = _stack(
                root, name.lower(), variant_baseline, variant_current
            )
            result = variant_service.get_current_guest_traffic(
                SITE, evaluated_at_utc=EVALUATED_AT
            )
            semantic[name] = {
                "status": result.status,
                "population": result.population_count,
                "rate_evidence": result.rate_evidence_status,
                "items": [asdict(item) for item in result.items],
            }

        print(json.dumps({
            "fixture": {
                "current_rows": len(current),
                "baseline_rows": len(baseline),
                "database": before,
            },
            "measurements": measurements,
            "semantic_variants": semantic,
            "query_plans": _plans(repository),
            "fingerprint_contract": True,
            "read_only_unchanged": before == after,
        }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
