"""Exact read-only Registry/Visit device projection for Admin Web."""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.analytics.source_gateway import (
    AnalyticsQueryDeadlineExceeded,
    QueryDeadline,
)


_REGISTRY_ALIAS = "registry_db"
_VISIT_ALIAS = "visit_db"
_PROGRESS_OPCODE_INTERVAL = 10_000
_MAC_PATTERN = re.compile(r"[0-9A-F]{2}(?::[0-9A-F]{2}){5}")


class AdminDeviceSourceError(RuntimeError):
    """A source could not provide the requested read-only projection."""


class AdminDeviceIntegrityError(AdminDeviceSourceError):
    """Persisted sources disagree about a canonical device identity."""


@dataclass(frozen=True, slots=True)
class AdminDeviceRow:
    device_id: str
    canonical_mac: str
    device_type: str | None
    site_first_seen_at: str
    site_last_seen_at: str
    site_snapshot_count: int
    site_visit_count: int
    last_site_ip: str | None
    last_site_ssid: str | None
    last_site_ap_mac: str | None
    latest_snapshot: dict[str, Any] | None


@dataclass(frozen=True, slots=True)
class AdminDevicePage:
    items: tuple[AdminDeviceRow, ...]
    has_more: bool


_DEVICE_PAGE_SQL = f"""
WITH
snapshot_ranked AS (
    SELECT
        s.device_id,
        d.mac AS registry_mac,
        s.requested_mac AS snapshot_mac,
        s.authorized_at,
        s.captured_at,
        s.name,
        s.hostname,
        s.system_name,
        s.ip,
        s.ssid,
        s.ap_name,
        s.ap_mac,
        s.device_type,
        s.radio_id,
        s.channel,
        s.rssi,
        s.snr,
        s.traffic_down,
        s.traffic_up,
        s.uptime,
        s.active,
        s.auth_status,
        MIN(s.captured_at) OVER (
            PARTITION BY s.device_id
        ) AS snapshot_first_seen_at,
        MAX(s.captured_at) OVER (
            PARTITION BY s.device_id
        ) AS snapshot_last_seen_at,
        COUNT(*) OVER (
            PARTITION BY s.device_id
        ) AS snapshot_count,
        MIN(s.requested_mac) OVER (
            PARTITION BY s.device_id
        ) AS snapshot_mac_min,
        MAX(s.requested_mac) OVER (
            PARTITION BY s.device_id
        ) AS snapshot_mac_max,
        ROW_NUMBER() OVER (
            PARTITION BY s.device_id
            ORDER BY s.captured_at DESC,
                     s.authorized_at DESC,
                     s.snapshot_id DESC
        ) AS latest_rank
    FROM {_REGISTRY_ALIAS}.device_snapshots AS s
    JOIN {_REGISTRY_ALIAS}.visitor_devices AS d
      ON d.device_id = s.device_id
    WHERE s.site_id = :site_id
),
snapshot_evidence AS (
    SELECT
        device_id,
        snapshot_first_seen_at AS first_seen_at,
        snapshot_last_seen_at AS last_seen_at,
        snapshot_count,
        0 AS visit_count,
        registry_mac,
        snapshot_mac_min,
        snapshot_mac_max,
        NULL AS visit_mac_min,
        NULL AS visit_mac_max,
        device_type,
        ip AS last_site_ip,
        ssid AS last_site_ssid,
        ap_mac AS last_site_ap_mac
        ,authorized_at AS snapshot_authorized_at
        ,captured_at AS snapshot_captured_at
        ,name AS snapshot_name
        ,hostname AS snapshot_hostname
        ,system_name AS snapshot_system_name
        ,ap_name AS snapshot_ap_name
        ,radio_id AS snapshot_radio_id
        ,channel AS snapshot_channel
        ,rssi AS snapshot_rssi
        ,snr AS snapshot_snr
        ,traffic_down AS snapshot_traffic_down
        ,traffic_up AS snapshot_traffic_up
        ,uptime AS snapshot_uptime
        ,active AS snapshot_active
        ,auth_status AS snapshot_auth_status
    FROM snapshot_ranked
    WHERE latest_rank = 1
),
visit_evidence AS (
    SELECT
        v.device_id,
        MIN(v.started_at) AS first_seen_at,
        MAX(CASE
            WHEN v.status = 'closed' THEN v.closed_at
            ELSE v.started_at
        END) AS last_seen_at,
        0 AS snapshot_count,
        COUNT(*) AS visit_count,
        NULL AS registry_mac,
        NULL AS snapshot_mac_min,
        NULL AS snapshot_mac_max,
        MIN(v.client_mac) AS visit_mac_min,
        MAX(v.client_mac) AS visit_mac_max,
        NULL AS device_type,
        NULL AS last_site_ip,
        NULL AS last_site_ssid,
        NULL AS last_site_ap_mac
        ,NULL AS snapshot_authorized_at
        ,NULL AS snapshot_captured_at
        ,NULL AS snapshot_name
        ,NULL AS snapshot_hostname
        ,NULL AS snapshot_system_name
        ,NULL AS snapshot_ap_name
        ,NULL AS snapshot_radio_id
        ,NULL AS snapshot_channel
        ,NULL AS snapshot_rssi
        ,NULL AS snapshot_snr
        ,NULL AS snapshot_traffic_down
        ,NULL AS snapshot_traffic_up
        ,NULL AS snapshot_uptime
        ,NULL AS snapshot_active
        ,NULL AS snapshot_auth_status
    FROM {_VISIT_ALIAS}.visits AS v
    WHERE v.site_id = :site_id
      AND v.device_id IS NOT NULL
    GROUP BY v.device_id
),
combined AS (
    SELECT * FROM snapshot_evidence
    UNION ALL
    SELECT * FROM visit_evidence
),
devices AS (
    SELECT
        device_id,
        COALESCE(MAX(registry_mac), MAX(visit_mac_min)) AS canonical_mac,
        MAX(device_type) AS device_type,
        MIN(first_seen_at) AS site_first_seen_at,
        MAX(last_seen_at) AS site_last_seen_at,
        SUM(snapshot_count) AS site_snapshot_count,
        SUM(visit_count) AS site_visit_count,
        MAX(last_site_ip) AS last_site_ip,
        MAX(last_site_ssid) AS last_site_ssid,
        MAX(last_site_ap_mac) AS last_site_ap_mac,
        MAX(snapshot_authorized_at) AS snapshot_authorized_at,
        MAX(snapshot_captured_at) AS snapshot_captured_at,
        MAX(snapshot_name) AS snapshot_name,
        MAX(snapshot_hostname) AS snapshot_hostname,
        MAX(snapshot_system_name) AS snapshot_system_name,
        MAX(snapshot_ap_name) AS snapshot_ap_name,
        MAX(snapshot_radio_id) AS snapshot_radio_id,
        MAX(snapshot_channel) AS snapshot_channel,
        MAX(snapshot_rssi) AS snapshot_rssi,
        MAX(snapshot_snr) AS snapshot_snr,
        MAX(snapshot_traffic_down) AS snapshot_traffic_down,
        MAX(snapshot_traffic_up) AS snapshot_traffic_up,
        MAX(snapshot_uptime) AS snapshot_uptime,
        MAX(snapshot_active) AS snapshot_active,
        MAX(snapshot_auth_status) AS snapshot_auth_status,
        CASE
            WHEN MAX(snapshot_mac_min) IS NOT MAX(snapshot_mac_max) THEN 1
            WHEN MAX(visit_mac_min) IS NOT MAX(visit_mac_max) THEN 1
            WHEN MAX(registry_mac) IS NOT NULL
             AND MAX(snapshot_mac_min) IS NOT NULL
             AND MAX(registry_mac) <> MAX(snapshot_mac_min) THEN 1
            WHEN MAX(registry_mac) IS NOT NULL
             AND MAX(visit_mac_min) IS NOT NULL
             AND MAX(registry_mac) <> MAX(visit_mac_min) THEN 1
            ELSE 0
        END AS identity_conflict
    FROM combined
    GROUP BY device_id
),
page AS (
    SELECT *
    FROM devices
    WHERE (:device_id IS NULL OR device_id = :device_id)
      AND (:canonical_mac IS NULL OR canonical_mac = :canonical_mac)
      AND (
        :cursor_at IS NULL
        OR site_last_seen_at < :cursor_at
        OR (
            site_last_seen_at = :cursor_at
            AND device_id < :cursor_device_id
        )
    )
    ORDER BY site_last_seen_at DESC, device_id DESC
    LIMIT :row_limit
)
SELECT
    device_id,
    canonical_mac,
    device_type,
    site_first_seen_at,
    site_last_seen_at,
    site_snapshot_count,
    site_visit_count,
    last_site_ip,
    last_site_ssid,
    last_site_ap_mac,
    snapshot_authorized_at,
    snapshot_captured_at,
    snapshot_name,
    snapshot_hostname,
    snapshot_system_name,
    snapshot_ap_name,
    snapshot_radio_id,
    snapshot_channel,
    snapshot_rssi,
    snapshot_snr,
    snapshot_traffic_down,
    snapshot_traffic_up,
    snapshot_uptime,
    snapshot_active,
    snapshot_auth_status,
    identity_conflict
FROM page
ORDER BY site_last_seen_at DESC, device_id DESC
"""


class AdminDeviceReadGateway:
    """Execute one exact Site-device page query across live source DBs."""

    def __init__(self, registry_db_path: str | Path, visit_db_path: str | Path):
        self._registry_path = Path(registry_db_path)
        self._visit_path = Path(visit_db_path)

    def list_devices(
        self,
        *,
        site_id: str,
        limit: int,
        deadline: QueryDeadline,
        cursor: tuple[str, str] | None = None,
        canonical_mac: str | None = None,
    ) -> AdminDevicePage:
        return self._query(
            site_id=site_id,
            limit=limit,
            deadline=deadline,
            cursor=cursor,
            device_id=None,
            canonical_mac=canonical_mac,
        )

    def get_device(
        self,
        *,
        site_id: str,
        device_id: str,
        deadline: QueryDeadline,
    ) -> AdminDeviceRow | None:
        page = self._query(
            site_id=site_id,
            limit=1,
            deadline=deadline,
            cursor=None,
            device_id=device_id,
            canonical_mac=None,
        )
        return page.items[0] if page.items else None

    def _query(
        self,
        *,
        site_id: str,
        limit: int,
        deadline: QueryDeadline,
        cursor: tuple[str, str] | None,
        device_id: str | None,
        canonical_mac: str | None,
    ) -> AdminDevicePage:
        if not isinstance(site_id, str) or not site_id:
            raise ValueError("site_id must be a non-empty string")
        if type(limit) is not int or limit <= 0 or limit > 500:
            raise ValueError("limit must be between 1 and 500")
        if device_id is not None and (
            not isinstance(device_id, str) or not device_id
        ):
            raise ValueError("device_id must be a non-empty string")
        if canonical_mac is not None and (
            not isinstance(canonical_mac, str)
            or _MAC_PATTERN.fullmatch(canonical_mac) is None
        ):
            raise ValueError("canonical_mac must be canonical")
        cursor_at, cursor_device_id = cursor or (None, None)
        connection = self._open(deadline)
        try:
            rows = connection.execute(
                _DEVICE_PAGE_SQL,
                {
                    "site_id": site_id,
                    "cursor_at": cursor_at,
                    "cursor_device_id": cursor_device_id,
                    "device_id": device_id,
                    "canonical_mac": canonical_mac,
                    "row_limit": limit + 1,
                },
            ).fetchall()
        except sqlite3.Error as exc:
            if deadline.expired() or "interrupt" in str(exc).lower():
                raise AnalyticsQueryDeadlineExceeded(
                    "Admin device query deadline exceeded"
                ) from None
            raise AdminDeviceSourceError("device source unavailable") from None
        finally:
            connection.set_progress_handler(None, 0)
            try:
                connection.rollback()
            finally:
                connection.close()

        selected = rows[:limit]
        if any(int(row["identity_conflict"]) != 0 for row in selected):
            raise AdminDeviceIntegrityError("device identity conflict")
        items = tuple(self._row(row) for row in selected)
        return AdminDevicePage(items=items, has_more=len(rows) > limit)

    def explain(self, *, site_id: str, deadline: QueryDeadline) -> tuple[str, ...]:
        """Return query-plan detail for an explicit capacity diagnostic."""
        connection = self._open(deadline)
        try:
            rows = connection.execute(
                "EXPLAIN QUERY PLAN " + _DEVICE_PAGE_SQL,
                {
                    "site_id": site_id,
                    "cursor_at": None,
                    "cursor_device_id": None,
                    "device_id": None,
                    "canonical_mac": None,
                    "row_limit": 101,
                },
            ).fetchall()
            return tuple(str(row[3]) for row in rows)
        except sqlite3.Error:
            raise AdminDeviceSourceError("device source unavailable") from None
        finally:
            connection.set_progress_handler(None, 0)
            try:
                connection.rollback()
            finally:
                connection.close()

    def _open(self, deadline: QueryDeadline) -> sqlite3.Connection:
        deadline.require_remaining()
        try:
            connection = sqlite3.connect(
                "file:admin-device-read?mode=memory&cache=private",
                uri=True,
                isolation_level=None,
                timeout=0.0,
            )
            connection.row_factory = sqlite3.Row
            connection.execute(
                f"ATTACH DATABASE ? AS {_REGISTRY_ALIAS}",
                (self._read_uri(self._registry_path),),
            )
            connection.execute(
                f"ATTACH DATABASE ? AS {_VISIT_ALIAS}",
                (self._read_uri(self._visit_path),),
            )
            connection.execute("PRAGMA query_only=ON")
            connection.execute("BEGIN")
            if int(
                connection.execute(
                    f"PRAGMA {_REGISTRY_ALIAS}.user_version"
                ).fetchone()[0]
            ) != 1:
                raise AdminDeviceSourceError("device source unavailable")
            if int(
                connection.execute(
                    f"PRAGMA {_VISIT_ALIAS}.user_version"
                ).fetchone()[0]
            ) != 2:
                raise AdminDeviceSourceError("device source unavailable")
            connection.set_progress_handler(
                lambda: 1 if deadline.expired() else 0,
                _PROGRESS_OPCODE_INTERVAL,
            )
            return connection
        except (OSError, sqlite3.Error, AdminDeviceSourceError):
            if "connection" in locals():
                connection.set_progress_handler(None, 0)
                connection.close()
            raise AdminDeviceSourceError("device source unavailable") from None

    @staticmethod
    def _read_uri(path: Path) -> str:
        return f"{path.resolve(strict=False).as_uri()}?mode=ro"

    @staticmethod
    def _row(row: sqlite3.Row) -> AdminDeviceRow:
        mac = row["canonical_mac"]
        if not isinstance(mac, str) or _MAC_PATTERN.fullmatch(mac) is None:
            raise AdminDeviceIntegrityError("device identity conflict")
        snapshot = None
        if row["snapshot_captured_at"] is not None:
            snapshot = {
                "authorized_at": row["snapshot_authorized_at"],
                "captured_at": row["snapshot_captured_at"],
                "name": row["snapshot_name"],
                "hostname": row["snapshot_hostname"],
                "system_name": row["snapshot_system_name"],
                "device_type": row["device_type"],
                "ip": row["last_site_ip"],
                "ssid": row["last_site_ssid"],
                "ap_name": row["snapshot_ap_name"],
                "ap_mac": row["last_site_ap_mac"],
                "radio_id": row["snapshot_radio_id"],
                "channel": row["snapshot_channel"],
                "rssi": row["snapshot_rssi"],
                "snr": row["snapshot_snr"],
                "traffic_down": row["snapshot_traffic_down"],
                "traffic_up": row["snapshot_traffic_up"],
                "uptime": row["snapshot_uptime"],
                "active": (
                    None
                    if row["snapshot_active"] is None
                    else bool(row["snapshot_active"])
                ),
                "auth_status": row["snapshot_auth_status"],
            }
        return AdminDeviceRow(
            device_id=str(row["device_id"]),
            canonical_mac=mac,
            device_type=row["device_type"],
            site_first_seen_at=str(row["site_first_seen_at"]),
            site_last_seen_at=str(row["site_last_seen_at"]),
            site_snapshot_count=int(row["site_snapshot_count"]),
            site_visit_count=int(row["site_visit_count"]),
            last_site_ip=row["last_site_ip"],
            last_site_ssid=row["last_site_ssid"],
            last_site_ap_mac=row["last_site_ap_mac"],
            latest_snapshot=snapshot,
        )
