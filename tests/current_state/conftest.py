from __future__ import annotations

from dataclasses import replace

import pytest

from app.current_state.config import current_state_config_from_settings
from app.current_state.models import CurrentStateCycle
from app.current_state.normalizer import canonical_scope


SITE = "a" * 24
OTHER_SITE = "b" * 24
NOW = "2026-08-23T10:00:00.000Z"


@pytest.fixture
def enabled_settings(tmp_path):
    return {
        "current_state_enabled": "true",
        "current_state_db_path": str(tmp_path / "current_state.sqlite3"),
        "current_state_site_ids": SITE,
        "current_state_client_ssids_json": '["Zefer_Parki"]',
        "observation_db_path": str(tmp_path / "observations.sqlite3"),
        "visit_lifecycle_db_path": str(tmp_path / "visits.sqlite3"),
        "visitor_registry_db_path": str(tmp_path / "registry.sqlite3"),
        "portal_counter_db_path": str(tmp_path / "portal.sqlite3"),
        "public_traffic_db_path": str(tmp_path / "traffic.sqlite3"),
    }


@pytest.fixture
def config(enabled_settings):
    return current_state_config_from_settings(enabled_settings)


def cycle(kind="client", cycle_id="cycle-1", site_id=SITE, started=NOW, result="success", items_stored=0, items_seen=None, scope_hash=None):
    scope_json, actual_hash = canonical_scope(kind, site_id, ("Zefer_Parki",))
    stored = items_stored
    seen = stored if items_seen is None else items_seen
    return CurrentStateCycle(
        cycle_id=cycle_id,
        kind=kind,
        site_id=site_id,
        capture_started_at=started,
        capture_finished_at=started,
        complete=result == "success",
        result=result,
        source_scope_version=1,
        source_scope_json=scope_json,
        source_scope_hash=scope_hash or actual_hash,
        source_rows_reported=seen,
        items_seen=seen,
        items_stored=stored,
        items_skipped=seen - stored,
        unidentified_count=0,
        duplicate_identity_count=0,
        unknown_status_count=0,
        error_count=0 if result == "success" else 1,
        data_quality_warning_count=0,
        page_count=1,
        failure_category=None if result == "success" else "controller_error",
        duration_ms=10,
        created_at=started,
    )


def client_row(cycle_id="cycle-1", site_id=SITE, mac="AA:BB:CC:DD:EE:01", **updates):
    row = {
        "cycle_id": cycle_id,
        "cycle_kind": "client",
        "site_id": site_id,
        "observed_at": NOW,
        "client_mac": mac,
        "name": None,
        "hostname": None,
        "device_type": None,
        "ip": None,
        "ssid": "Zefer_Parki",
        "ap_name": None,
        "ap_mac": None,
        "radio_id": None,
        "band": None,
        "channel": None,
        "rssi": None,
        "snr": None,
        "controller_uptime": None,
        "auth_status_code": None,
        "auth_classification": "unknown",
        "controller_traffic_down": None,
        "controller_traffic_up": None,
        "controller_traffic_total": None,
        "active": True,
        "wireless": True,
    }
    row.update(updates)
    return row


def ap_row(cycle_id="cycle-ap", site_id=SITE, mac="AA:BB:CC:DD:FF:01", **updates):
    row = {
        "cycle_id": cycle_id,
        "cycle_kind": "ap",
        "site_id": site_id,
        "observed_at": NOW,
        "ap_mac": mac,
        "name": None,
        "ip": None,
        "model": None,
        "firmware_version": None,
        "status_code": None,
        "status_classification": "unknown",
        "last_seen_ms": None,
        "controller_uptime": None,
        "uptime_raw": None,
    }
    row.update(updates)
    return row
