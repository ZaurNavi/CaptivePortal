"""Opt-in A/B/C capacity gate for Wireless Analytics v1."""

from __future__ import annotations

import argparse
from contextlib import closing
import json
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from app.analytics.source_gateway import (
    AnalyticsQueryDeadlineExceeded,
    QueryDeadline,
)
from app.observations.read_service import ObservationReadService

from .capacity_benchmark import (
    CountingGateway,
    SCENARIOS,
    SITE,
    Scenario,
    _UnusedRegistryReadService,
    _observation_repository,
    _seed_observations,
    _utc,
)


UTC = timezone.utc


def _seed_radios(repository) -> None:
    with closing(repository._connect()) as connection:  # noqa: SLF001
        connection.execute("PRAGMA synchronous=OFF")
        connection.execute(
            """
            INSERT INTO ap_radio_observations (
                cycle_id, ap_observation_row_id, radio_observed_at,
                site_id, ap_mac, band, radio_id, tx_util, rx_util,
                interference_util, busy_util, rx_bytes, tx_bytes,
                rx_packets, tx_packets, rx_drop_packets, tx_drop_packets,
                rx_error_packets, tx_error_packets,
                rx_retry_packets, tx_retry_packets,
                radio_rx_mbps, radio_tx_mbps,
                radio_rx_rate_reason, radio_tx_rate_reason
            )
            SELECT cycle_id, row_id, observed_at, site_id, ap_mac,
                   '5 GHz', 1, 10.0, 5.0, 2.0, 17.0,
                   row_id*1000, row_id*500, row_id*100, row_id*50,
                   row_id, row_id, row_id, row_id, row_id, row_id,
                   1.5, 2.5, 'ok', 'ok'
            FROM ap_observations
            """
        )
        connection.commit()
        connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")


def _measure(
    gateway: CountingGateway,
    name: str,
    operation: Callable[[], Any],
) -> dict[str, Any]:
    gateway.reset_counts()
    started = time.perf_counter()
    status = "ok"
    try:
        operation()
    except AnalyticsQueryDeadlineExceeded:
        status = "query_deadline"
    elapsed = time.perf_counter() - started
    return {
        "query": name,
        "status": status,
        "elapsed_seconds": round(elapsed, 3),
        "sql_calls": gateway.sql_calls,
        "rows_transferred_to_python": gateway.rows_transferred,
        "peak_materialized_sample_count": gateway.peak_collection,
    }


def run_scenario(scenario: Scenario) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(
        prefix=f"wireless-{scenario.name}-"
    ) as raw:
        root = Path(raw)
        observations = _observation_repository(root)
        start = datetime(2026, 1, 1, tzinfo=UTC)
        clients, access_points = _seed_observations(
            observations, scenario, start
        )
        _seed_radios(observations)
        gateway = CountingGateway(
            ObservationReadService(observations),
            _UnusedRegistryReadService(),
            _UnusedRegistryReadService(),
        )
        end = start + timedelta(days=scenario.days)
        start_text = _utc(start)
        end_text = _utc(end)
        deadline = lambda: QueryDeadline.after(10)
        common = {
            "site_id": SITE, "from_utc": start_text,
            "to_utc": end_text, "quality_mode": "strict_complete",
        }
        queries = [
            _measure(gateway, "signal_rssi", lambda: (
                gateway.wireless_scalar_distribution(
                    **common, source="client", metric="rssi", filters={},
                    threshold=-70, deadline=deadline(),
                )
            )),
            _measure(gateway, "client_context_ap", lambda: (
                gateway.client_context_distribution(
                    **common, dimension="ap_mac", deadline=deadline(),
                )
            )),
            _measure(gateway, "concurrent_clients", lambda: (
                gateway.concurrent_client_distribution(
                    **common, group_by=None, deadline=deadline(),
                )
            )),
            _measure(gateway, "ap_cpu", lambda: (
                gateway.wireless_scalar_distribution(
                    **common, source="ap", metric="cpu_util", filters={},
                    threshold=None, deadline=deadline(),
                )
            )),
            _measure(gateway, "radio_busy", lambda: (
                gateway.radio_utilization_distributions(
                    **common, metric="busy_util", ap_mac=None, band=None,
                    deadline=deadline(),
                )
            )),
            _measure(gateway, "client_counter_rate", lambda: (
                gateway.client_counter_rate_distribution(
                    **common, metric="client_download_mbps",
                    max_gap_seconds=180, client_mac=None,
                    deadline=deadline(),
                )
            )),
            _measure(gateway, "radio_counter_quality", lambda: (
                gateway.radio_counter_quality(
                    **common, max_gap_seconds=180, ap_mac=None, band=None,
                    deadline=deadline(),
                )
            )),
            _measure(gateway, "rssi_busy_join", lambda: (
                gateway.signal_ap_correlation(
                    **common, signal_metric="rssi", ap_metric="busy_util",
                    max_lag_seconds=120, deadline=deadline(),
                )
            )),
        ]
        with observations.read_connection() as connection:
            rows = {
                table: int(connection.execute(
                    f"SELECT COUNT(*) FROM {table}"
                ).fetchone()[0])
                for table in (
                    "client_observations", "ap_observations",
                    "ap_radio_observations",
                )
            }
            plans = {
                "client_site_time": " | ".join(
                    str(row[-1]) for row in connection.execute(
                        "EXPLAIN QUERY PLAN SELECT row_id, rssi "
                        "FROM client_observations WHERE site_id=? "
                        "AND observed_at>=? AND observed_at<?",
                        (SITE, start_text, end_text),
                    )
                ),
                "radio_site_ap_band_time": " | ".join(
                    str(row[-1]) for row in connection.execute(
                        "EXPLAIN QUERY PLAN SELECT row_id, busy_util "
                        "FROM ap_radio_observations WHERE site_id=? "
                        "AND ap_mac=? AND band=? "
                        "AND radio_observed_at>=? AND radio_observed_at<?",
                        (
                            SITE, access_points[0], "5 GHz",
                            start_text, end_text,
                        ),
                    )
                ),
            }
        return {
            "scenario": scenario.name,
            "clients": scenario.clients,
            "access_points": scenario.access_points,
            "days": scenario.days,
            "rows": rows,
            "query_plans": plans,
            "queries": queries,
            "privacy": {
                "client_identifiers_returned": False,
                "raw_rows_returned": False,
            },
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
        print(json.dumps(run_scenario(
            Scenario(name, clients, access_points, days)
        ), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
