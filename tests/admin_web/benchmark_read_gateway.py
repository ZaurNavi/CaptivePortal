"""Reproducible representative Admin Visits/Observation read benchmark."""

from __future__ import annotations

import json
import sqlite3
import tempfile
import time
from pathlib import Path

from app.admin_web.read_gateway import AdminSqlReadGateway
from app.analytics.source_gateway import QueryDeadline


SITE = "a" * 24
MAC = "02:00:00:00:00:01"
AP = "02:00:00:00:00:02"
ROWS = 100_000
RUNS = 6


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="admin-read-capacity-") as directory:
        visit_path = Path(directory) / "visits.sqlite3"
        observation_path = Path(directory) / "observations.sqlite3"
        _create(visit_path, observation_path)
        _populate(visit_path, observation_path)
        gateway = AdminSqlReadGateway(visit_path, observation_path)
        measurements = {
            "visits": lambda: gateway.list_visits(
                site_id=SITE, limit=100, deadline=QueryDeadline.after(10)
            ),
            "clients": lambda: gateway.list_client_observations(
                site_id=SITE, client_mac=MAC,
                from_utc="2026-01-01T00:00:00.000Z",
                to_utc="2026-01-31T23:59:59.999Z",
                limit=100, deadline=QueryDeadline.after(10),
            ),
            "aps": lambda: gateway.list_ap_observations(
                site_id=SITE, ap_mac=AP,
                from_utc="2026-01-01T00:00:00.000Z",
                to_utc="2026-01-31T23:59:59.999Z",
                limit=100, deadline=QueryDeadline.after(10),
            ),
        }
        passed = True
        for name, operation in measurements.items():
            durations = []
            overheads = []
            size = 0
            for _ in range(RUNS):
                started = time.perf_counter()
                result = operation()
                durations.append(time.perf_counter() - started)
                overhead_started = time.perf_counter()
                encoded = json.dumps(
                    result[0], allow_nan=False, ensure_ascii=True,
                    separators=(",", ":"),
                ).encode("utf-8")
                overheads.append(time.perf_counter() - overhead_started)
                size = len(encoded)
            p95 = max(durations[1:])
            overhead_p95 = max(overheads[1:]) * 1000
            print(
                f"{name}: rows={ROWS} page=100 "
                f"source_p95_seconds={p95:.6f} "
                f"admin_overhead_p95_ms={overhead_p95:.3f} "
                f"response_bytes={size}"
            )
            passed = passed and p95 < 5 and overhead_p95 < 100 and size < 1_048_576
    print(f"representative_read_gate={'PASS' if passed else 'FAIL'}")
    return 0 if passed else 1


def _create(visits: Path, observations: Path) -> None:
    with sqlite3.connect(visits) as connection:
        connection.executescript(
            """
            PRAGMA journal_mode=WAL; PRAGMA user_version=2;
            CREATE TABLE visits (
              visit_id TEXT PRIMARY KEY, site_id TEXT, client_mac TEXT,
              device_id TEXT, started_at TEXT, closed_at TEXT, status TEXT,
              duration_seconds INTEGER, start_ssid TEXT, final_ssid TEXT,
              start_ap_mac TEXT, final_ap_mac TEXT,
              reported_traffic_total_bytes INTEGER, close_reason TEXT,
              close_time_source TEXT, start_ip TEXT, final_ip TEXT,
              reported_connected_seconds INTEGER,
              reported_traffic_up_bytes INTEGER,
              reported_traffic_down_bytes INTEGER
            );
            CREATE TABLE visit_authorizations (
              visit_id TEXT, portal_ssid TEXT, portal_ap_mac TEXT
            );
            CREATE INDEX idx_visits_site_started
            ON visits(site_id, started_at DESC, visit_id DESC);
            """
        )
    with sqlite3.connect(observations) as connection:
        connection.executescript(
            """
            PRAGMA journal_mode=WAL; PRAGMA user_version=1;
            CREATE TABLE observation_cycles(cycle_id TEXT PRIMARY KEY,state TEXT);
            CREATE TABLE client_observations (
              row_id INTEGER PRIMARY KEY, cycle_id TEXT, observed_at TEXT,
              site_id TEXT, client_mac TEXT, ip TEXT, ssid TEXT, ap_name TEXT,
              ap_mac TEXT, radio_id INTEGER, band TEXT, channel INTEGER,
              rssi INTEGER, snr INTEGER, rx_rate INTEGER, tx_rate INTEGER,
              traffic_down INTEGER, traffic_up INTEGER, uptime INTEGER,
              auth_status INTEGER, active INTEGER
            );
            CREATE TABLE ap_observations (
              row_id INTEGER PRIMARY KEY, cycle_id TEXT, observed_at TEXT,
              site_id TEXT, ap_mac TEXT, name TEXT, ip TEXT, model TEXT,
              firmware_version TEXT, cpu_util REAL, mem_util REAL,
              uptime_seconds INTEGER, wired_download_mbps REAL,
              wired_upload_mbps REAL, lan_rx_mbps REAL, lan_tx_mbps REAL,
              partial INTEGER
            );
            CREATE TABLE ap_radio_observations (
              row_id INTEGER PRIMARY KEY, cycle_id TEXT,
              ap_observation_row_id INTEGER, radio_observed_at TEXT,
              site_id TEXT, ap_mac TEXT, band TEXT, radio_id INTEGER,
              actual_channel INTEGER, frequency_mhz INTEGER,
              channel_width TEXT, tx_power REAL, tx_util REAL, rx_util REAL,
              interference_util REAL, busy_util REAL, radio_rx_mbps REAL,
              radio_tx_mbps REAL
            );
            CREATE INDEX idx_client_site_mac_time
            ON client_observations(site_id,client_mac,observed_at,row_id);
            CREATE INDEX idx_ap_site_mac_time
            ON ap_observations(site_id,ap_mac,observed_at,row_id);
            CREATE INDEX idx_radio_site_ap_band_time
            ON ap_radio_observations(site_id,ap_mac,band,radio_observed_at,row_id);
            """
        )


def _populate(visits: Path, observations: Path) -> None:
    with sqlite3.connect(visits) as connection:
        connection.execute("PRAGMA synchronous=OFF")
        connection.executemany(
            """
            INSERT INTO visits(
              visit_id,site_id,client_mac,device_id,started_at,status
            ) VALUES (?,?,?,?,?,'open')
            """,
            (
                (f"v-{row}", SITE, MAC, f"d-{row}", _timestamp(row))
                for row in range(ROWS)
            ),
        )
    with sqlite3.connect(observations) as connection:
        connection.execute("PRAGMA synchronous=OFF")
        connection.execute("INSERT INTO observation_cycles VALUES ('c','completed')")
        connection.executemany(
            """
            INSERT INTO client_observations(
              row_id,cycle_id,observed_at,site_id,client_mac,ip,active
            ) VALUES (?,'c',?,?,?,'192.0.2.1',1)
            """,
            ((row + 1, _timestamp(row), SITE, MAC) for row in range(ROWS)),
        )
        connection.executemany(
            """
            INSERT INTO ap_observations(
              row_id,cycle_id,observed_at,site_id,ap_mac,name,partial
            ) VALUES (?,'c',?,?,?,'AP-1',0)
            """,
            ((row + 1, _timestamp(row), SITE, AP) for row in range(ROWS)),
        )
        connection.executemany(
            """
            INSERT INTO ap_radio_observations(
              row_id,cycle_id,ap_observation_row_id,radio_observed_at,
              site_id,ap_mac,band,radio_id
            ) VALUES (?,'c',?,?,?,?, '5GHz',1)
            """,
            (
                (row + 1, row + 1, _timestamp(row), SITE, AP)
                for row in range(ROWS)
            ),
        )


def _timestamp(row: int) -> str:
    second = row % (31 * 86_400)
    return (
        f"2026-01-{second // 86_400 + 1:02d}T"
        f"{second // 3_600 % 24:02d}:{second // 60 % 60:02d}:"
        f"{second % 60:02d}.000Z"
    )


if __name__ == "__main__":
    raise SystemExit(main())
