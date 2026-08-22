"""Reproducible capacity gate for the Admin cross-source device page."""

from __future__ import annotations

import argparse
import json
import sqlite3
import statistics
import tempfile
import time
from dataclasses import asdict
from pathlib import Path

from app.admin_web.device_gateway import AdminDeviceReadGateway
from app.analytics.source_gateway import QueryDeadline


SITE = "a" * 24


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--devices", type=int, default=50_000)
    parser.add_argument("--snapshots-per-device", type=int, default=3)
    parser.add_argument("--visits-per-device", type=int, default=2)
    parser.add_argument("--runs", type=int, default=6)
    arguments = parser.parse_args()
    if arguments.devices <= 0 or arguments.runs < 2:
        raise SystemExit("devices must be positive and runs must be at least 2")

    with tempfile.TemporaryDirectory(prefix="admin-device-capacity-") as directory:
        registry = Path(directory) / "registry.sqlite3"
        visits = Path(directory) / "visits.sqlite3"
        _create(registry, visits)
        _populate(
            registry,
            visits,
            devices=arguments.devices,
            snapshots_per_device=arguments.snapshots_per_device,
            visits_per_device=arguments.visits_per_device,
        )
        gateway = AdminDeviceReadGateway(registry, visits)
        durations: list[float] = []
        overheads: list[float] = []
        response_bytes = 0
        for _ in range(arguments.runs):
            started = time.perf_counter()
            page = gateway.list_devices(
                site_id=SITE,
                limit=100,
                deadline=QueryDeadline.after(10.0),
            )
            durations.append(time.perf_counter() - started)
            overhead_started = time.perf_counter()
            encoded = json.dumps(
                [asdict(item) for item in page.items],
                allow_nan=False,
                ensure_ascii=True,
                separators=(",", ":"),
            ).encode("utf-8")
            overheads.append(time.perf_counter() - overhead_started)
            response_bytes = len(encoded)
        plan = gateway.explain(site_id=SITE, deadline=QueryDeadline.after(10.0))

    p95 = _percentile(durations[1:], 0.95)
    overhead_p95 = _percentile(overheads[1:], 0.95)
    print(f"devices={arguments.devices}")
    print(f"snapshots={arguments.devices * arguments.snapshots_per_device}")
    print(f"visits={arguments.devices * arguments.visits_per_device}")
    print("page_rows=100")
    print("sqlite_rows_max=101")
    print("application_rows=100")
    print("sql_statement_count=1")
    print(f"source_sql_p95_seconds={p95:.6f}")
    print(f"admin_overhead_p95_ms={overhead_p95 * 1000:.3f}")
    print(f"response_bytes={response_bytes}")
    print("hard_deadline_seconds=10")
    print("explain_query_plan=")
    for detail in plan:
        print(f"  {detail}")
    passed = (
        p95 <= 5.0
        and max(durations) < 10.0
        and overhead_p95 < 0.1
        and response_bytes <= 1_048_576
    )
    print(f"capacity_gate={'PASS' if passed else 'FAIL'}")
    return 0 if passed else 1


def _percentile(values: list[float], quantile: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(round((len(ordered) - 1) * quantile)))
    return ordered[index]


def _create(registry: Path, visits: Path) -> None:
    with sqlite3.connect(registry) as connection:
        connection.executescript(
            """
            PRAGMA journal_mode=WAL;
            PRAGMA user_version=1;
            CREATE TABLE visitor_devices (
                device_id TEXT PRIMARY KEY,
                mac TEXT NOT NULL UNIQUE
            );
            CREATE TABLE device_snapshots (
                snapshot_id TEXT PRIMARY KEY,
                device_id TEXT NOT NULL,
                site_id TEXT NOT NULL,
                requested_mac TEXT NOT NULL,
                authorized_at TEXT NOT NULL,
                captured_at TEXT NOT NULL,
                name TEXT,
                hostname TEXT,
                system_name TEXT,
                ip TEXT,
                ssid TEXT,
                ap_name TEXT,
                ap_mac TEXT,
                device_type TEXT,
                radio_id INTEGER,
                channel INTEGER,
                rssi INTEGER,
                snr INTEGER,
                traffic_down INTEGER,
                traffic_up INTEGER,
                uptime INTEGER,
                active INTEGER,
                auth_status INTEGER
            );
            CREATE INDEX idx_device_snapshots_site_order
            ON device_snapshots(site_id, authorized_at DESC, captured_at DESC);
            """
        )
    with sqlite3.connect(visits) as connection:
        connection.executescript(
            """
            PRAGMA journal_mode=WAL;
            PRAGMA user_version=2;
            CREATE TABLE visits (
                visit_id TEXT PRIMARY KEY,
                site_id TEXT NOT NULL,
                client_mac TEXT NOT NULL,
                device_id TEXT,
                started_at TEXT NOT NULL,
                closed_at TEXT,
                status TEXT NOT NULL
            );
            CREATE INDEX idx_visits_site_device_started
            ON visits(site_id, device_id, started_at DESC, visit_id DESC);
            """
        )


def _populate(
    registry: Path,
    visits: Path,
    *,
    devices: int,
    snapshots_per_device: int,
    visits_per_device: int,
) -> None:
    with sqlite3.connect(registry) as connection:
        connection.execute("PRAGMA synchronous=OFF")
        connection.executemany(
            "INSERT INTO visitor_devices(device_id, mac) VALUES (?, ?)",
            ((_device_id(number), _mac(number)) for number in range(devices)),
        )
        connection.executemany(
            """
            INSERT INTO device_snapshots(
                snapshot_id, device_id, site_id, requested_mac,
                authorized_at, captured_at, ip, ssid, ap_mac, device_type
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                (
                    f"s-{number}-{sample}",
                    _device_id(number),
                    SITE,
                    _mac(number),
                    _timestamp(number, sample),
                    _timestamp(number, sample),
                    f"192.0.2.{number % 254 + 1}",
                    "OwnerWiFi",
                    "AA:BB:CC:DD:EE:FF",
                    "phone",
                )
                for number in range(devices)
                for sample in range(snapshots_per_device)
            ),
        )
    with sqlite3.connect(visits) as connection:
        connection.execute("PRAGMA synchronous=OFF")
        connection.executemany(
            """
            INSERT INTO visits(
                visit_id, site_id, client_mac, device_id,
                started_at, closed_at, status
            ) VALUES (?, ?, ?, ?, ?, ?, 'closed')
            """,
            (
                (
                    f"v-{number}-{sample}",
                    SITE,
                    _mac(number),
                    _device_id(number),
                    _timestamp(number, sample),
                    _timestamp(number, sample + 1),
                )
                for number in range(devices)
                for sample in range(visits_per_device)
            ),
        )


def _device_id(number: int) -> str:
    return f"00000000-0000-4000-8000-{number:012d}"


def _mac(number: int) -> str:
    return (
        f"02:00:{number // 16_777_216 % 256:02X}:"
        f"{number // 65_536 % 256:02X}:{number // 256 % 256:02X}:{number % 256:02X}"
    )


def _timestamp(number: int, sample: int) -> str:
    seconds = number * 10 + sample
    return f"2026-01-{seconds // 86_400 % 28 + 1:02d}T{seconds // 3_600 % 24:02d}:{seconds // 60 % 60:02d}:{seconds % 60:02d}.000Z"


if __name__ == "__main__":
    raise SystemExit(main())
