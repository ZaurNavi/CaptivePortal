from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.observations.models import ObservationConfig
from app.observations.repository import ObservationRepository


def make_config(tmp_path: Path, **updates) -> ObservationConfig:
    data = tmp_path / "data"
    data.mkdir(mode=0o750, exist_ok=True)
    if os.name == "posix":
        data.chmod(0o750)
    values = {
        "enabled": True,
        "db_path": str(data / "observations.sqlite3"),
        "dynamic_retention_days": 180,
        "config_retention_days": 730,
        "cleanup_initial_delay_seconds": 900.0,
        "cleanup_interval_seconds": 86400.0,
        "cleanup_batch_size": 5000,
        "cleanup_max_duration_seconds": 30.0,
        "shutdown_timeout_seconds": 20.0,
    }
    values.update(updates)
    return ObservationConfig(**values)


@pytest.fixture
def observation_config(tmp_path: Path) -> ObservationConfig:
    return make_config(tmp_path)


@pytest.fixture
def repository(observation_config: ObservationConfig) -> ObservationRepository:
    result = ObservationRepository(observation_config)
    result.initialize("2026-01-01T00:00:00.000Z")
    return result


def client_row(
    cycle_id: str,
    observed_at: str,
    *,
    site_id: str = "site-a",
    client_mac: str = "AA:BB:CC:DD:EE:01",
    **updates,
) -> dict:
    row = {
        "cycle_id": cycle_id,
        "observed_at": observed_at,
        "site_id": site_id,
        "client_mac": client_mac,
        "source_inventory_complete": True,
        "ssid": "Zefer_Parki",
        "ap_mac": "10:20:30:40:50:60",
        "radio_id": 1,
        "active": True,
        "auth_status": 2,
        "traffic_down": 100,
        "traffic_up": 200,
    }
    row.update(updates)
    return row


def ap_row(
    cycle_id: str,
    observed_at: str,
    *,
    site_id: str = "site-a",
    ap_mac: str = "10:20:30:40:50:60",
    **updates,
) -> dict:
    row = {
        "cycle_id": cycle_id,
        "observed_at": observed_at,
        "site_id": site_id,
        "ap_mac": ap_mac,
        "partial": False,
        "overview_ok": True,
        "wired_uplink_ok": True,
        "lan_traffic_ok": True,
        "radios_ok": True,
        "overview_observed_at": observed_at,
        "wired_observed_at": observed_at,
        "lan_observed_at": observed_at,
        "name": "AP-1",
        "wired_down_bytes": 1000,
        "wired_up_bytes": 2000,
    }
    row.update(updates)
    return row


def radio_row(
    observed_at: str,
    *,
    band: str = "5GHz",
    **updates,
) -> dict:
    row = {
        "radio_observed_at": observed_at,
        "band": band,
        "radio_id": 1,
        "actual_channel": 36,
        "rx_bytes": 100,
        "tx_bytes": 200,
    }
    row.update(updates)
    return row


def complete_cycle(
    repository: ObservationRepository,
    cycle_id: str,
    *,
    kind: str,
    site_id: str = "site-a",
    started_at: str = "2026-01-01T00:00:00.000Z",
) -> None:
    repository.create_cycle(
        kind=kind,
        site_id=site_id,
        started_at=started_at,
        cycle_id=cycle_id,
    )
    repository.finalize_cycle(
        cycle_id,
        finished_at=started_at,
        complete=True,
        result="success",
    )
