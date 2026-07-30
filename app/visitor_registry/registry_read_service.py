"""Read-only query facade for Visitor Device Registry."""

from __future__ import annotations

import ipaddress
from datetime import date, datetime
from typing import Any

from app.common.mac import format_mac_colon

from .registry_repository import VisitorRegistryRepository
from .registry_service import (
    VisitorRegistryService,
    canonical_uuid,
    normalize_timestamp,
)


class VisitorRegistryReadService:
    def __init__(
        self,
        repository: VisitorRegistryRepository,
        service: VisitorRegistryService,
        *,
        configured_enabled: bool,
    ):
        self.repository = repository
        self.service = service
        self.configured_enabled = configured_enabled

    def get_status(self) -> dict[str, Any]:
        status = self.repository.get_status(self.configured_enabled)
        reader_states = list(status.reader_states)
        return {
            "configured_enabled": status.configured_enabled,
            "available": (
                status.database_ready
                and status.registry_state != "unavailable"
            ),
            "database_exists": status.database_exists,
            "database_ready": status.database_ready,
            "db_path": self.repository.config.db_path,
            "source_log_path": self.repository.config.source_log_path,
            "schema_version": status.schema_version,
            "registry_state": status.registry_state,
            "state_reason": status.state_reason,
            "initial_backfill_completed": (
                status.initial_backfill_completed
            ),
            "initial_backfill_completed_at": (
                status.initial_backfill_completed_at
            ),
            "last_successful_scan_at": status.last_successful_scan_at,
            "last_snapshot_stored_at": status.last_snapshot_stored_at,
            "missing_inode_warning_count": sum(
                1
                for item in reader_states
                if item.get("missing_warning_emitted") is True
            ),
            "reader_states": reader_states,
            "partial": not status.initial_backfill_completed,
        }

    def get_stats(self, local_date: date | None = None) -> dict[str, Any]:
        selected = local_date or datetime.now(
            self.service.timezone
        ).date()
        start, end = self.service.local_day_bounds(selected)
        result = self.repository.get_stats(start, end)
        status = self.repository.get_status(self.configured_enabled)
        result.update({
            "local_date": selected.isoformat(),
            "timezone": self.service.timezone_name,
            "initial_backfill_completed": (
                status.initial_backfill_completed
            ),
            "partial": not status.initial_backfill_completed,
        })
        return result

    def get_device_by_id(
        self,
        device_id: str,
    ) -> dict[str, Any] | None:
        return self.repository.get_device_by_id(
            canonical_uuid(device_id)
        )

    def get_device_by_mac(
        self,
        mac: str,
    ) -> dict[str, Any] | None:
        return self.repository.get_device_by_mac(format_mac_colon(mac))

    def list_devices(
        self,
        filters: dict[str, Any],
        *,
        limit: int,
        offset: int,
    ) -> list[dict[str, Any]]:
        if limit <= 0 or limit > 200:
            raise ValueError("limit must be between 1 and 200")
        if offset < 0:
            raise ValueError("offset must not be negative")
        normalized = dict(filters)
        if normalized.get("mac"):
            normalized["mac"] = format_mac_colon(normalized["mac"])
        if normalized.get("ap_mac"):
            normalized["ap_mac"] = format_mac_colon(
                normalized["ap_mac"]
            )
        if normalized.get("ip"):
            normalized["ip"] = str(
                ipaddress.ip_address(normalized["ip"].strip())
            )
        if normalized.get("seen_from"):
            try:
                normalized["seen_from"] = normalize_timestamp(
                    normalized["seen_from"]
                )
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    "seen_from must be a timezone-aware timestamp"
                ) from exc
        if normalized.get("seen_to"):
            try:
                normalized["seen_to"] = normalize_timestamp(
                    normalized["seen_to"]
                )
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    "seen_to must be a timezone-aware timestamp"
                ) from exc
        return self.repository.list_devices(
            filters=normalized,
            limit=limit,
            offset=offset,
        )

    def list_device_snapshots(
        self,
        device_id: str,
        *,
        limit: int,
        offset: int,
    ) -> list[dict[str, Any]]:
        if limit <= 0 or limit > 200:
            raise ValueError("limit must be between 1 and 200")
        if offset < 0:
            raise ValueError("offset must not be negative")
        return self.repository.list_device_snapshots(
            canonical_uuid(device_id),
            limit=limit,
            offset=offset,
        )
