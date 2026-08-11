"""Reproducible local capacity sample for TASK-OBSERVATION-01A.

This is deliberately outside the pytest collection pattern. It creates an
isolated temporary SQLite database, performs representative storage/query/
cleanup work, and prints machine-readable JSON. It never contacts Omada.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import tempfile
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.observations.cleanup import ObservationCleanup
from app.observations.models import ObservationConfig, format_utc
from app.observations.read_service import ObservationReadService
from app.observations.repository import ObservationRepository


SITE_ID = "capacity-site"
AP_MACS = tuple(f"02:00:00:00:10:{index:02X}" for index in range(10))
CLIENT_MACS = tuple(
    f"02:00:00:{index // 65536:02X}:{(index // 256) % 256:02X}:{index % 256:02X}"
    for index in range(100)
)


def _config(path: Path) -> ObservationConfig:
    return ObservationConfig(
        enabled=True,
        db_path=str(path),
        dynamic_retention_days=180,
        config_retention_days=730,
        cleanup_initial_delay_seconds=900.0,
        cleanup_interval_seconds=86400.0,
        cleanup_batch_size=500,
        cleanup_max_duration_seconds=30.0,
        shutdown_timeout_seconds=20.0,
    )


def _client_row(cycle_id: str, observed_at: str, mac: str, index: int) -> dict:
    return {
        "cycle_id": cycle_id,
        "observed_at": observed_at,
        "site_id": SITE_ID,
        "client_mac": mac,
        "source_inventory_complete": True,
        "controller_client_id": f"client-{index}",
        "hostname": f"phone-{index}",
        "ip": f"192.0.2.{(index % 250) + 1}",
        "ssid": "capacity-ssid",
        "ap_mac": AP_MACS[index % len(AP_MACS)],
        "radio_id": index % 2,
        "band": "2.4GHz" if index % 2 == 0 else "5GHz",
        "channel": 11 if index % 2 == 0 else 36,
        "rssi": -40 - (index % 30),
        "snr": 20 + (index % 20),
        "auth_status": 2,
        "wireless": True,
        "active": True,
        "traffic_down": 100_000 + index,
        "traffic_up": 50_000 + index,
        "down_packet": 1000 + index,
        "up_packet": 500 + index,
    }


def _ap_entry(cycle_id: str, observed_at: str, mac: str, index: int):
    ap = {
        "cycle_id": cycle_id,
        "observed_at": observed_at,
        "site_id": SITE_ID,
        "ap_mac": mac,
        "partial": False,
        "overview_ok": True,
        "wired_uplink_ok": True,
        "lan_traffic_ok": True,
        "radios_ok": True,
        "overview_observed_at": observed_at,
        "wired_observed_at": observed_at,
        "lan_observed_at": observed_at,
        "name": f"AP-{index}",
        "model": "capacity-model",
        "firmware_version": "1.0.0",
        "cpu_util": 25.5,
        "mem_util": 40.5,
        "uptime_seconds": 100_000,
        "wired_up_bytes": 10_000_000 + index,
        "wired_down_bytes": 20_000_000 + index,
        "lan_rx_bytes": 15_000_000 + index,
        "lan_tx_bytes": 12_000_000 + index,
        "wired_download_rate_reason": "ok",
        "wired_upload_rate_reason": "ok",
        "lan_rx_rate_reason": "ok",
        "lan_tx_rate_reason": "ok",
    }
    radios = [
        {
            "radio_observed_at": observed_at,
            "band": band,
            "radio_id": radio_id,
            "actual_channel": 11 if radio_id == 0 else 36,
            "frequency_mhz": 2462 if radio_id == 0 else 5180,
            "channel_width": "20MHz" if radio_id == 0 else "80MHz",
            "tx_util": 20.0,
            "rx_util": 10.0,
            "busy_util": 35.0,
            "rx_bytes": 5_000_000 + index,
            "tx_bytes": 7_000_000 + index,
            "radio_rx_rate_reason": "ok",
            "radio_tx_rate_reason": "ok",
        }
        for radio_id, band in ((0, "2.4GHz"), (1, "5GHz"))
    ]
    return ap, radios


def run() -> dict:
    base = datetime(2026, 1, 1, tzinfo=UTC)
    with tempfile.TemporaryDirectory(
        prefix="observation-capacity-",
        ignore_cleanup_errors=True,
    ) as temp:
        path = Path(temp) / "observations.sqlite3"
        config = _config(path)
        repository = ObservationRepository(config)
        repository.initialize(format_utc(base))

        started = time.perf_counter()
        for minute in range(100):
            observed_at = format_utc(base + timedelta(minutes=minute))
            cycle_id = f"client-{minute:04d}"
            repository.create_cycle(
                kind="client",
                site_id=SITE_ID,
                started_at=observed_at,
                cycle_id=cycle_id,
            )
            repository.insert_client_batch([
                _client_row(cycle_id, observed_at, mac, index)
                for index, mac in enumerate(CLIENT_MACS)
            ])
            repository.finalize_cycle(
                cycle_id,
                finished_at=observed_at,
                complete=True,
                result="success",
                items_seen=len(CLIENT_MACS),
                items_stored=len(CLIENT_MACS),
            )
        client_insert_seconds = time.perf_counter() - started

        started = time.perf_counter()
        for sample in range(100):
            observed_at = format_utc(base + timedelta(seconds=30 * sample))
            cycle_id = f"ap-{sample:04d}"
            repository.create_cycle(
                kind="ap_dynamic",
                site_id=SITE_ID,
                started_at=observed_at,
                cycle_id=cycle_id,
            )
            repository.insert_ap_batch([
                _ap_entry(cycle_id, observed_at, mac, index)
                for index, mac in enumerate(AP_MACS)
            ])
            repository.finalize_cycle(
                cycle_id,
                finished_at=observed_at,
                complete=True,
                result="success",
                items_seen=len(AP_MACS),
                items_stored=len(AP_MACS),
            )
        ap_insert_seconds = time.perf_counter() - started

        started = time.perf_counter()
        for sample in range(4):
            captured_at = format_utc(base + timedelta(hours=6 * sample))
            cycle_id = f"config-{sample:02d}"
            repository.create_cycle(
                kind="ap_config",
                site_id=SITE_ID,
                started_at=captured_at,
                cycle_id=cycle_id,
            )
            rows = []
            for index, mac in enumerate(AP_MACS):
                payload = json.dumps(
                    {
                        "name": f"AP-{index}",
                        "revision": sample,
                        "tag_ids": ["capacity"],
                    },
                    ensure_ascii=True,
                    allow_nan=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
                rows.append({
                    "cycle_id": cycle_id,
                    "captured_at": captured_at,
                    "site_id": SITE_ID,
                    "ap_mac": mac,
                    "config_sha256": hashlib.sha256(
                        payload.encode("utf-8")
                    ).hexdigest(),
                    "schema_version": 1,
                    "config_json": payload,
                })
            repository.insert_ap_config_batch(rows)
            repository.finalize_cycle(
                cycle_id,
                finished_at=captured_at,
                complete=True,
                result="success",
                items_seen=len(AP_MACS),
                items_stored=len(AP_MACS),
            )
        config_insert_seconds = time.perf_counter() - started

        with sqlite3.connect(path) as connection:
            connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            page_size = int(connection.execute("PRAGMA page_size").fetchone()[0])
            page_count = int(connection.execute("PRAGMA page_count").fetchone()[0])
            row_counts = {
                table: int(
                    connection.execute(
                        f"SELECT COUNT(*) FROM {table}"
                    ).fetchone()[0]
                )
                for table in (
                    "observation_cycles",
                    "client_observations",
                    "ap_observations",
                    "ap_radio_observations",
                    "ap_config_snapshots",
                )
            }
            dbstat = {
                str(name): int(size)
                for name, size in connection.execute(
                    "SELECT name, SUM(pgsize) FROM dbstat GROUP BY name"
                )
            }

        service = ObservationReadService(repository)
        query_samples = []
        for _ in range(200):
            query_started = time.perf_counter()
            service.get_client_observations(
                SITE_ID,
                CLIENT_MACS[0],
                format_utc(base),
                format_utc(base + timedelta(days=1)),
                limit=100,
            )
            query_samples.append((time.perf_counter() - query_started) * 1000)
        query_samples.sort()

        old = base - timedelta(days=800)
        for index in range(500):
            timestamp = format_utc(old + timedelta(seconds=index))
            identifier = f"expired-{index:04d}"
            repository.create_cycle(
                kind="client",
                site_id=SITE_ID,
                started_at=timestamp,
                cycle_id=identifier,
            )
            repository.finalize_cycle(
                identifier,
                finished_at=timestamp,
                complete=True,
                result="success",
            )
        cleanup_started = time.perf_counter()
        cleanup = ObservationCleanup(repository, config).run_once(
            now_utc=format_utc(base + timedelta(days=1))
        )
        cleanup_seconds = time.perf_counter() - cleanup_started

        return {
            "sample": {
                "client_cycles": 100,
                "clients_per_cycle": 100,
                "ap_cycles": 100,
                "aps_per_cycle": 10,
                "radios_per_ap": 2,
                "config_cycles": 4,
            },
            "row_counts": row_counts,
            "database_bytes": page_size * page_count,
            "dbstat_bytes": dbstat,
            "insert_seconds": {
                "client": round(client_insert_seconds, 6),
                "ap_dynamic": round(ap_insert_seconds, 6),
                "ap_config": round(config_insert_seconds, 6),
            },
            "client_history_query_ms": {
                "mean": round(sum(query_samples) / len(query_samples), 6),
                "p95": round(query_samples[int(len(query_samples) * 0.95)], 6),
                "max": round(max(query_samples), 6),
            },
            "cleanup": {
                "expired_cycles": 500,
                "deleted_dynamic_cycles": cleanup.deleted_dynamic_cycles,
                "batches": cleanup.batches,
                "seconds": round(cleanup_seconds, 6),
            },
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = json.dumps(run(), indent=2, sort_keys=True)
    if args.output is not None:
        args.output.write_text(result + "\n", encoding="utf-8")
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
