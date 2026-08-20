"""Reproducible capacity gate for TASK-ANALYTICS-01A.

This is an opt-in benchmark, not a pytest test. It builds disposable source
databases with the real schemas and measures bounded Analytics gateway reads.
"""

from __future__ import annotations

import argparse
import json
import tempfile
import time
import uuid
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from app.analytics.source_gateway import (
    AnalyticsQueryDeadlineExceeded,
    AnalyticsSourceGateway,
    QueryDeadline,
)
from app.observations.models import ObservationConfig
from app.observations.read_service import ObservationReadService
from app.observations.repository import ObservationRepository
from app.visit_lifecycle.models import NormalizedVisitStart, VisitLifecycleConfig
from app.visit_lifecycle.read_service import VisitLifecycleReadService
from app.visit_lifecycle.repository import VisitRepository


UTC = timezone.utc
SITE = "capacity-site"
SCENARIOS = {
    "A": (30, 2, 1),
    "B": (100, 10, 7),
    "C": (300, 30, 7),
}


class _UnusedRegistryReadService:
    def analytics_read_connection(self):  # pragma: no cover - safety tripwire
        raise AssertionError("registry must not be used by this benchmark")


class CountingGateway(AnalyticsSourceGateway):
    def __init__(self, *args: Any):
        super().__init__(*args)
        self.sql_calls = 0
        self.rows_transferred = 0
        self.peak_collection = 0

    def reset_counts(self) -> None:
        self.sql_calls = 0
        self.rows_transferred = 0
        self.peak_collection = 0

    def _one(self, *args: Any, **kwargs: Any):
        self.sql_calls += 1
        row = super()._one(*args, **kwargs)
        count = int(row is not None)
        self.rows_transferred += count
        self.peak_collection = max(self.peak_collection, count)
        return row

    def _all(self, *args: Any, **kwargs: Any):
        self.sql_calls += 1
        rows = super()._all(*args, **kwargs)
        count = len(rows)
        self.rows_transferred += count
        self.peak_collection = max(self.peak_collection, count)
        return rows


@dataclass(frozen=True)
class Scenario:
    name: str
    clients: int
    access_points: int
    days: int

    @property
    def minutes(self) -> int:
        return self.days * 24 * 60


def _utc(value: datetime) -> str:
    return value.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _mac(prefix: int, index: int) -> str:
    return (
        f"02:{prefix:02X}:{(index >> 16) & 255:02X}:"
        f"{(index >> 8) & 255:02X}:{index & 255:02X}:01"
    )


def _observation_repository(root: Path) -> ObservationRepository:
    repository = ObservationRepository(ObservationConfig(
        enabled=True,
        db_path=str(root / "observations.sqlite3"),
        dynamic_retention_days=180,
        config_retention_days=730,
        cleanup_initial_delay_seconds=900,
        cleanup_interval_seconds=86400,
        cleanup_batch_size=5000,
        cleanup_max_duration_seconds=30,
        shutdown_timeout_seconds=20,
    ))
    repository.initialize("2026-01-01T00:00:00.000Z")
    return repository


def _visit_repository(root: Path) -> VisitRepository:
    repository = VisitRepository(VisitLifecycleConfig(
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
    repository.initialize()
    return repository


def _seed_observations(
    repository: ObservationRepository,
    scenario: Scenario,
    start: datetime,
) -> tuple[list[str], list[str]]:
    clients = [_mac(0x11, index) for index in range(scenario.clients)]
    access_points = [
        _mac(0xAA, index) for index in range(scenario.access_points)
    ]
    with closing(repository._connect()) as connection:  # noqa: SLF001
        connection.execute("PRAGMA synchronous=OFF")
        cycle_sql = """
            INSERT INTO observation_cycles (
                cycle_id, kind, site_id, state, started_at, finished_at,
                complete, result, source_rows_reported, items_seen,
                items_stored, items_skipped, error_count,
                data_quality_warning_count, created_at, updated_at
            ) VALUES (?, ?, ?, 'completed', ?, ?, 1, 'success', ?, ?, ?, 0, 0, 0, ?, ?)
        """
        client_sql = """
            INSERT INTO client_observations (
                cycle_id, observed_at, site_id, client_mac,
                source_inventory_complete, ap_mac, radio_id, band, channel,
                rssi, snr, traffic_down, traffic_up
            ) VALUES (?, ?, ?, ?, 1, ?, 1, '5 GHz', 36, -55, 32, 1000, 500)
        """
        ap_sql = """
            INSERT INTO ap_observations (
                cycle_id, observed_at, site_id, ap_mac, partial,
                overview_ok, wired_uplink_ok, lan_traffic_ok, radios_ok,
                overview_observed_at, name, cpu_util, mem_util
            ) VALUES (?, ?, ?, ?, 0, 1, 1, 1, 1, ?, 'AP', 20.0, 30.0)
        """
        cycles: list[tuple[Any, ...]] = []
        client_rows: list[tuple[Any, ...]] = []
        ap_rows: list[tuple[Any, ...]] = []

        def flush() -> None:
            connection.executemany(cycle_sql, cycles)
            connection.executemany(client_sql, client_rows)
            connection.executemany(ap_sql, ap_rows)
            cycles.clear()
            client_rows.clear()
            ap_rows.clear()
            connection.commit()

        for minute in range(scenario.minutes):
            observed = _utc(start + timedelta(minutes=minute))
            finished = _utc(start + timedelta(minutes=minute, seconds=1))
            client_cycle = f"client-{minute}"
            ap_cycle = f"ap-{minute}"
            cycles.append((
                client_cycle, "client", SITE, observed, finished,
                scenario.clients, scenario.clients, scenario.clients,
                observed, finished,
            ))
            cycles.append((
                ap_cycle, "ap_dynamic", SITE, observed, finished,
                scenario.access_points, scenario.access_points,
                scenario.access_points, observed, finished,
            ))
            client_rows.extend(
                (
                    client_cycle, observed, SITE, client,
                    access_points[index % len(access_points)],
                )
                for index, client in enumerate(clients)
            )
            ap_rows.extend(
                (ap_cycle, observed, SITE, ap, observed)
                for ap in access_points
            )
            if minute % 120 == 119:
                flush()
        if cycles:
            flush()
        connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    return clients, access_points


def _seed_visits(
    repository: VisitRepository,
    clients: list[str],
    start: datetime,
) -> None:
    authorized_at = _utc(start)
    for index, client in enumerate(clients):
        repository.create_or_reuse_start(
            NormalizedVisitStart(
                auth_session_id=str(uuid.uuid5(uuid.NAMESPACE_OID, f"auth-{index}")),
                site_id=SITE,
                client_mac=client,
                authorized_at=authorized_at,
                auth_run_number=1,
                authorization_attempt=1,
                final_reason="AUTHORIZED",
                client_ip=None,
                portal_ssid="capacity",
                portal_ap_mac=None,
                portal_radio_id=None,
            ),
            now_utc=authorized_at,
        )


def _measure(gateway: CountingGateway, name: str, operation):
    gateway.reset_counts()
    started = time.perf_counter()
    status = "ok"
    try:
        operation()
    except AnalyticsQueryDeadlineExceeded:
        status = "query_deadline"
    elapsed_ms = (time.perf_counter() - started) * 1000
    return {
        "query": name,
        "status": status,
        "elapsed_ms": round(elapsed_ms, 3),
        "sql_calls": gateway.sql_calls,
        "rows_transferred": gateway.rows_transferred,
        "peak_collection": gateway.peak_collection,
    }


def run_scenario(scenario: Scenario) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix=f"analytics-{scenario.name}-") as raw:
        root = Path(raw)
        observations = _observation_repository(root)
        visits = _visit_repository(root)
        start = datetime(2026, 1, 1, tzinfo=UTC)
        clients, _aps = _seed_observations(observations, scenario, start)
        _seed_visits(visits, clients, start)
        gateway = CountingGateway(
            ObservationReadService(observations),
            VisitLifecycleReadService(visits),
            _UnusedRegistryReadService(),
        )
        end = start + timedelta(days=scenario.days)
        from_utc = _utc(start)
        to_utc = _utc(end)
        day_from = _utc(max(start, end - timedelta(days=1)))
        deadline = lambda: QueryDeadline.after(10)
        queries = [
            _measure(gateway, "cycle_quality_24h", lambda: gateway.cycle_quality(
                site_id=SITE, kind="client", from_utc=day_from,
                to_utc=to_utc, deadline=deadline(),
            )),
            _measure(gateway, f"cycle_quality_{scenario.days}d", lambda: gateway.cycle_quality(
                site_id=SITE, kind="client", from_utc=from_utc,
                to_utc=to_utc, deadline=deadline(),
            )),
            _measure(gateway, "single_visit_coverage", lambda: gateway.observation_coverage(
                site_id=SITE, client_mac=clients[0], from_utc=from_utc,
                to_utc=to_utc, gap_threshold_seconds=180,
                deadline=deadline(),
            )),
            _measure(gateway, "site_field_completeness_24h", lambda: gateway.field_completeness(
                site_id=SITE, source="client", from_utc=day_from,
                to_utc=to_utc,
                fields=("ap_mac", "radio_id", "band", "channel", "rssi", "snr", "traffic_down", "traffic_up"),
                quality_mode="strict_complete", deadline=deadline(),
            )),
            _measure(gateway, f"site_field_completeness_{scenario.days}d", lambda: gateway.field_completeness(
                site_id=SITE, source="client", from_utc=from_utc,
                to_utc=to_utc,
                fields=("ap_mac", "radio_id", "band", "channel", "rssi", "snr", "traffic_down", "traffic_up"),
                quality_mode="strict_complete", deadline=deadline(),
            )),
            _measure(gateway, "visit_link_coverage", lambda: gateway.visit_population(
                site_id=SITE, from_utc=from_utc, to_utc=to_utc,
                deadline=deadline(),
            )),
            _measure(gateway, "source_freshness", lambda: gateway.observation_watermarks(
                site_id=SITE, from_utc=from_utc, to_utc=to_utc,
                deadline=deadline(),
            )),
        ]
        with observations.read_connection() as connection:
            table_rows = {
                table: int(connection.execute(
                    f"SELECT COUNT(*) FROM {table}"
                ).fetchone()[0])
                for table in (
                    "observation_cycles", "client_observations",
                    "ap_observations", "ap_radio_observations",
                )
            }
            plan = " | ".join(str(row[-1]) for row in connection.execute(
                """
                EXPLAIN QUERY PLAN SELECT COUNT(*)
                FROM client_observations o
                JOIN observation_cycles c ON c.cycle_id=o.cycle_id
                WHERE o.site_id=? AND o.observed_at>=? AND o.observed_at<?
                """,
                (SITE, from_utc, to_utc),
            ))
        database_bytes = sum(
            path.stat().st_size
            for path in root.iterdir()
            if path.is_file() and "sqlite3" in path.name
        )
        return {
            "scenario": scenario.name,
            "clients": scenario.clients,
            "access_points": scenario.access_points,
            "days": scenario.days,
            "table_rows": table_rows,
            "database_bytes": database_bytes,
            "query_plan": plan,
            "queries": queries,
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--scenario", choices=(*SCENARIOS, "ALL"), default="ALL"
    )
    args = parser.parse_args()
    names = SCENARIOS if args.scenario == "ALL" else (args.scenario,)
    for name in names:
        clients, access_points, days = SCENARIOS[name]
        print(json.dumps(run_scenario(Scenario(
            name, clients, access_points, days
        )), sort_keys=True))
    print(json.dumps({
        "maximum_31_day_estimate": {
            "clients": 300,
            "days": 31,
            "client_rows": 300 * 31 * 24 * 60,
        }
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
