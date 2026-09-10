from __future__ import annotations

from dataclasses import replace

import pytest

from app.admin_web.device_gateway import AdminDeviceListContextRow
from app.admin_web.device_list_context_serialization import (
    DeviceListContextSerializationError,
    serialize_device_list_context,
    serialize_device_list_context_overlay,
)
from app.current_state.models import CurrentSnapshotMeta


SITE = "a" * 24
SCOPE = {
    "scope_type": "client_ssid_allowlist",
    "site_id": SITE,
    "ssids": ["Guest", "Zefer_Parki"],
}
EVALUATED = "2026-09-09T12:00:00.000Z"


def _snapshot(**changes):
    value = CurrentSnapshotMeta(
        cycle_id="cycle-1",
        site_id=SITE,
        kind="client",
        evaluated_at=EVALUATED,
        observed_at="2026-09-09T11:59:50.000Z",
        capture_finished_at="2026-09-09T11:59:55.000Z",
        age_seconds=10.0,
        freshness_status="fresh",
        freshness_reason="within_freshness_window",
        complete=True,
        source_scope_version=1,
        source_scope_hash="1" * 64,
        source_scope=SCOPE,
        latest_attempt_result="success",
        latest_attempt_at="2026-09-09T11:59:55.000Z",
        latest_partial_cycle_id=None,
    )
    return replace(value, **changes)


def _row(**changes):
    value = AdminDeviceListContextRow(
        device_id="10000000-0000-4000-8000-000000000001",
        canonical_mac="02:00:00:00:00:01",
        hostname=None,
        device_type="phone",
        site_first_seen_at="2026-09-01T00:00:00.000Z",
        site_last_seen_at="2026-09-09T11:00:00.000Z",
        site_snapshot_count=2,
        site_visit_count=3,
        last_site_ip="192.0.2.1",
        last_site_ssid="Zefer_Parki",
        last_site_ap_mac="AA:BB:CC:DD:EE:FF",
        current_presence="online",
        online_rank=0,
    )
    return replace(value, **changes)


def _overlay(mode="trusted", status="available", snapshot=None, scope=SCOPE):
    if snapshot is None and status == "available":
        snapshot = _snapshot()
    return serialize_device_list_context_overlay(
        site_id=SITE,
        overlay_mode=mode,
        source_execution_status=status,
        evaluated_at_utc=EVALUATED,
        scope=scope,
        snapshot=snapshot,
    )


def test_device_list_context_serialization_exact_root_overlay_and_item_keys():
    result = serialize_device_list_context(
        site_id=SITE, items=(_row(),), overlay=_overlay()
    )
    assert set(result) == {"items", "current_state_overlay"}
    assert set(result["current_state_overlay"]) == {
        "overlay_mode", "ordering_applied", "source_execution_status",
        "evaluated_at_utc", "scope", "snapshot",
    }
    assert set(result["current_state_overlay"]["snapshot"]) == {
        "observed_at", "capture_finished_at", "age_seconds",
        "freshness_status", "freshness_reason", "complete",
    }
    assert set(result["items"][0]) == {
        "device_id", "canonical_mac", "hostname", "device_type",
        "site_first_seen_at", "site_last_seen_at", "site_snapshot_count",
        "site_visit_count", "last_site_ip", "last_site_ssid",
        "last_site_ap_mac", "current_presence",
    }
    assert result["items"][0]["hostname"] is None
    assert "online_rank" not in result["items"][0]
    assert "latest_snapshot" not in result["items"][0]
    assert "cycle_id" not in result["current_state_overlay"]["snapshot"]
    assert "source_scope_hash" not in result["current_state_overlay"]


def test_device_list_context_serialization_accepts_three_overlay_modes():
    trusted = _overlay()
    stale = _snapshot(
        freshness_status="stale",
        freshness_reason="older_than_freshness_window",
        age_seconds=100.0,
    )
    semantic = _overlay(mode="unknown", snapshot=stale)
    unavailable = _overlay(
        mode="unknown", status="unavailable", snapshot=None, scope=None
    )
    assert trusted["ordering_applied"] is True
    assert semantic["ordering_applied"] is False
    assert unavailable["snapshot"] is None
    assert unavailable["scope"] is None
    assert serialize_device_list_context(
        site_id=SITE,
        items=(_row(current_presence="unknown", online_rank=1),),
        overlay=semantic,
    )["items"][0]["current_presence"] == "unknown"


def test_device_list_context_serialization_validates_requested_site_and_scope():
    wrong_scope = {**SCOPE, "site_id": "b" * 24}
    with pytest.raises(DeviceListContextSerializationError):
        serialize_device_list_context_overlay(
            site_id=SITE,
            overlay_mode="trusted",
            source_execution_status="available",
            evaluated_at_utc=EVALUATED,
            scope=wrong_scope,
            snapshot=_snapshot(),
        )
    with pytest.raises(DeviceListContextSerializationError):
        _overlay(scope={**SCOPE, "ssids": ["Zefer_Parki", "Guest"]})


@pytest.mark.parametrize(
    "row",
    [
        _row(current_presence="bad"),
        _row(site_snapshot_count=-1),
        _row(site_visit_count=True),
        _row(last_site_ap_mac="bad"),
        _row(canonical_mac="bad"),
    ],
)
def test_device_list_context_serialization_rejects_invalid_items(row):
    with pytest.raises(DeviceListContextSerializationError):
        serialize_device_list_context(
            site_id=SITE, items=(row,), overlay=_overlay()
        )


def test_device_list_context_serialization_enforces_presence_by_overlay():
    with pytest.raises(DeviceListContextSerializationError):
        serialize_device_list_context(
            site_id=SITE,
            items=(_row(current_presence="unknown", online_rank=1),),
            overlay=_overlay(),
        )
    with pytest.raises(DeviceListContextSerializationError):
        serialize_device_list_context(
            site_id=SITE,
            items=(_row(),),
            overlay=_overlay(
                mode="unknown",
                snapshot=_snapshot(
                    freshness_status="stale",
                    freshness_reason="older_than_freshness_window",
                    age_seconds=100.0,
                ),
            ),
        )


@pytest.mark.parametrize(
    "snapshot",
    [
        _snapshot(freshness_status="stale"),
        _snapshot(complete=False),
        _snapshot(site_id="b" * 24),
        _snapshot(kind="ap_dynamic"),
        _snapshot(evaluated_at="2026-09-09T12:00:01.000Z"),
    ],
)
def test_device_list_context_serialization_rejects_contradictory_trusted_overlay(snapshot):
    with pytest.raises(DeviceListContextSerializationError):
        _overlay(snapshot=snapshot)


def test_device_list_context_serialization_sanitizes_invalid_timestamp_and_scope():
    for reason in ("invalid_timestamp", "invalid_source_scope"):
        snapshot = _snapshot(
            observed_at="not-a-time",
            capture_finished_at="also-bad",
            age_seconds=None,
            freshness_status="unavailable",
            freshness_reason=reason,
        )
        result = _overlay(mode="unknown", snapshot=snapshot)
        assert result["snapshot"]["observed_at"] is None
        assert result["snapshot"]["capture_finished_at"] is None
        assert result["snapshot"]["age_seconds"] is None


def test_device_list_context_serialization_rejects_contradictory_unknown_overlay():
    with pytest.raises(DeviceListContextSerializationError):
        _overlay(mode="unknown", snapshot=_snapshot())
    with pytest.raises(DeviceListContextSerializationError):
        _overlay(mode="trusted", status="unavailable", snapshot=None, scope=None)
