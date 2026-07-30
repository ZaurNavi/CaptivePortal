"""Strict schema-v1 validation and read semantics for Visitor Registry."""

from __future__ import annotations

import hashlib
import ipaddress
import json
import uuid
from datetime import date, datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

from app.common.mac import format_mac_colon

from .device_ids import build_device_id
from .registry_models import (
    DecisionKind,
    MAX_SQLITE_INTEGER,
    RegistryEventDecision,
    RegistrySnapshot,
)
from .snapshot_ids import build_snapshot_id


CAPTURED_EVENT = "visitor.client_snapshot.captured"
ALLOWED_AUTH_FINAL_REASONS = frozenset({
    "ALREADY_AUTHORIZED",
    "AUTHORIZED_AFTER_ATTEMPT",
    "AUTHORIZED_FINAL_VERIFY",
})
_OPTIONAL_CLIENT_STRINGS = (
    "controller_client_id",
    "name",
    "hostname",
    "system_name",
    "device_type",
    "ssid",
    "ap_name",
)
_OPTIONAL_CLIENT_INTS = (
    "radio_id",
    "channel",
    "rssi",
    "snr",
    "auth_status",
)
_NONNEGATIVE_CLIENT_INTS = (
    "traffic_down",
    "traffic_up",
    "uptime",
    "last_seen",
)
_NONNEGATIVE_EVENT_INTS = (
    "attempts",
    "queue_delay_ms",
    "request_duration_ms",
    "snapshot_lag_ms",
)
_MISSING = object()


class SnapshotValidationError(ValueError):
    def __init__(self, reason: str, field: str):
        super().__init__(f"{reason}: {field}")
        self.reason = reason
        self.field = field


class VisitorRegistryService:
    def __init__(self, timezone_name: str):
        self.timezone_name = timezone_name
        self.timezone = ZoneInfo(timezone_name)

    def now_iso(self) -> str:
        return format_utc_timestamp(datetime.now(timezone.utc))

    def decide(self, event: dict[str, Any]) -> RegistryEventDecision:
        if event.get("event") != CAPTURED_EVENT:
            return RegistryEventDecision(kind=DecisionKind.ADVANCE)

        snapshot_value = event.get("snapshot_id", _MISSING)
        if snapshot_value is _MISSING:
            return self._untracked_warning("missing_required_field")
        if not isinstance(snapshot_value, str):
            return self._untracked_warning("invalid_field_type")
        try:
            snapshot_id = canonical_uuid(snapshot_value)
        except ValueError:
            return self._untracked_warning("invalid_field_format")

        event_hash = canonical_event_sha256(event)
        try:
            snapshot = self._validate_snapshot(
                event,
                snapshot_id=snapshot_id,
                event_hash=event_hash,
            )
        except SnapshotValidationError as exc:
            return RegistryEventDecision(
                kind=DecisionKind.SKIP,
                snapshot_id=snapshot_id,
                event_sha256=event_hash,
                skip_reason=exc.reason,
                warning_reason=exc.reason,
            )
        return RegistryEventDecision(
            kind=DecisionKind.STORE,
            snapshot_id=snapshot_id,
            event_sha256=event_hash,
            snapshot=snapshot,
        )

    @staticmethod
    def _untracked_warning(reason: str) -> RegistryEventDecision:
        return RegistryEventDecision(
            kind=DecisionKind.ADVANCE,
            warning_reason=reason,
        )

    def _validate_snapshot(
        self,
        event: dict[str, Any],
        *,
        snapshot_id: str,
        event_hash: str,
    ) -> RegistrySnapshot:
        schema_version = _required(event, "schema_version")
        if type(schema_version) is not int:
            raise SnapshotValidationError(
                "invalid_field_type",
                "schema_version",
            )
        if schema_version != 1:
            raise SnapshotValidationError(
                "unsupported_schema_version",
                "schema_version",
            )

        auth_session_id = _required_nonempty_string(
            event,
            "auth_session_id",
        )
        site_id = _required_nonempty_string(event, "site_id")
        authorized_at = _required_timestamp(event, "authorized_at")
        captured_at = _required_timestamp(event, "captured_at")
        requested_mac = _required_mac(event, "requested_mac")

        auth_context = _required_object(event, "auth_context")
        client = _required_object(event, "client")
        raw_controller = _required_object(
            event,
            "raw_controller_snapshot",
        )
        client_mac = _required_mac(client, "mac", prefix="client.")
        if client_mac != requested_mac:
            raise SnapshotValidationError(
                "client_mac_mismatch",
                "client.mac",
            )

        expected_id = build_snapshot_id(
            auth_session_id,
            requested_mac,
        )
        if snapshot_id != expected_id:
            raise SnapshotValidationError(
                "snapshot_id_mismatch",
                "snapshot_id",
            )

        normalized_auth = self._normalize_auth_context(auth_context)
        normalized_client = self._normalize_client(client, client_mac)
        event_metrics = {
            name: _optional_nonnegative_int(event, name)
            for name in _NONNEGATIVE_EVENT_INTS
        }

        return RegistrySnapshot(
            snapshot_id=snapshot_id,
            device_id=build_device_id(requested_mac),
            mac=requested_mac,
            event_sha256=event_hash,
            schema_version=schema_version,
            auth_session_id=auth_session_id,
            site_id=site_id,
            requested_mac=requested_mac,
            authorized_at=authorized_at,
            captured_at=captured_at,
            attempts=event_metrics["attempts"],
            queue_delay_ms=event_metrics["queue_delay_ms"],
            request_duration_ms=event_metrics["request_duration_ms"],
            snapshot_lag_ms=event_metrics["snapshot_lag_ms"],
            auth_final_reason=normalized_auth["auth_final_reason"],
            auth_run_number=normalized_auth["auth_run_number"],
            authorization_attempt=(
                normalized_auth["authorization_attempt"]
            ),
            retry_request_id=normalized_auth["retry_request_id"],
            portal_client_ip=normalized_auth["client_ip"],
            portal_ssid=normalized_auth["portal_ssid"],
            portal_ap_mac=normalized_auth["portal_ap_mac"],
            portal_radio_id=normalized_auth["portal_radio_id"],
            controller_client_id=_profile_string(
                normalized_client["controller_client_id"]
            ),
            name=_profile_string(normalized_client["name"]),
            hostname=_profile_string(normalized_client["hostname"]),
            system_name=_profile_string(
                normalized_client["system_name"]
            ),
            device_type=_profile_string(
                normalized_client["device_type"]
            ),
            ip=normalized_client["ip"],
            ssid=normalized_client["ssid"],
            ap_name=normalized_client["ap_name"],
            ap_mac=normalized_client["ap_mac"],
            radio_id=normalized_client["radio_id"],
            channel=normalized_client["channel"],
            rssi=normalized_client["rssi"],
            snr=normalized_client["snr"],
            traffic_down=normalized_client["traffic_down"],
            traffic_up=normalized_client["traffic_up"],
            uptime=normalized_client["uptime"],
            controller_last_seen_ms=normalized_client["last_seen"],
            active=normalized_client["active"],
            auth_status=normalized_client["auth_status"],
            auth_context_json=canonical_json(normalized_auth),
            client_json=canonical_json(normalized_client),
            raw_controller_snapshot_json=canonical_json(raw_controller),
        )

    @staticmethod
    def _normalize_auth_context(
        value: dict[str, Any],
    ) -> dict[str, Any]:
        result = dict(value)
        required_keys = (
            "client_ip",
            "portal_ssid",
            "portal_ap_mac",
            "portal_radio_id",
            "auth_run_number",
            "authorization_attempt",
            "auth_final_reason",
            "retry_request_id",
        )
        for key in required_keys:
            if key not in value:
                raise SnapshotValidationError(
                    "missing_required_field",
                    f"auth_context.{key}",
                )

        result["client_ip"] = _optional_ip(
            value["client_ip"],
            "auth_context.client_ip",
        )
        result["portal_ssid"] = _nullable_string(
            value["portal_ssid"],
            "auth_context.portal_ssid",
        )
        result["portal_ap_mac"] = _optional_mac_value(
            value["portal_ap_mac"],
            "auth_context.portal_ap_mac",
        )
        result["portal_radio_id"] = _nullable_string(
            value["portal_radio_id"],
            "auth_context.portal_radio_id",
        )
        result["auth_run_number"] = _exact_int(
            value["auth_run_number"],
            "auth_context.auth_run_number",
            minimum=1,
        )
        result["authorization_attempt"] = _exact_int(
            value["authorization_attempt"],
            "auth_context.authorization_attempt",
            minimum=0,
        )
        final_reason = value["auth_final_reason"]
        if not isinstance(final_reason, str):
            raise SnapshotValidationError(
                "invalid_field_type",
                "auth_context.auth_final_reason",
            )
        if not final_reason.strip():
            raise SnapshotValidationError(
                "invalid_field_format",
                "auth_context.auth_final_reason",
            )
        if final_reason not in ALLOWED_AUTH_FINAL_REASONS:
            raise SnapshotValidationError(
                "invalid_field_value",
                "auth_context.auth_final_reason",
            )
        result["auth_final_reason"] = final_reason
        retry_id = value["retry_request_id"]
        if retry_id is not None:
            if not isinstance(retry_id, str):
                raise SnapshotValidationError(
                    "invalid_field_type",
                    "auth_context.retry_request_id",
                )
            if not retry_id.strip():
                raise SnapshotValidationError(
                    "invalid_field_format",
                    "auth_context.retry_request_id",
                )
        result["retry_request_id"] = retry_id
        return result

    @staticmethod
    def _normalize_client(
        value: dict[str, Any],
        client_mac: str,
    ) -> dict[str, Any]:
        result = dict(value)
        result["mac"] = client_mac
        for field in _OPTIONAL_CLIENT_STRINGS:
            result[field] = _optional_field_string(value, field)
        for field in _OPTIONAL_CLIENT_INTS:
            result[field] = _optional_field_int(value, field)
        for field in _NONNEGATIVE_CLIENT_INTS:
            result[field] = _optional_nonnegative_int(value, field)
        result["ip"] = _optional_ip(
            value.get("ip"),
            "client.ip",
        )
        result["ap_mac"] = _optional_mac_value(
            value.get("ap_mac"),
            "client.ap_mac",
        )
        active = value.get("active")
        if active is not None and type(active) is not bool:
            raise SnapshotValidationError(
                "invalid_field_type",
                "client.active",
            )
        result["active"] = active
        return result

    def local_day_bounds(
        self,
        local_date: date,
    ) -> tuple[str, str]:
        start = datetime.combine(
            local_date,
            datetime.min.time(),
            tzinfo=self.timezone,
        )
        from datetime import timedelta

        end = start + timedelta(days=1)
        return format_utc_timestamp(start), format_utc_timestamp(end)


def canonical_event_sha256(event: dict[str, Any]) -> str:
    return hashlib.sha256(
        canonical_json(event).encode("utf-8")
    ).hexdigest()


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
    )


def canonical_uuid(value: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError("UUID must be a non-empty string")
    parsed = uuid.UUID(value)
    canonical = str(parsed)
    if canonical != value:
        raise ValueError("UUID must use canonical lowercase form")
    return canonical


def parse_timestamp(value: str) -> datetime:
    if not isinstance(value, str):
        raise TypeError("timestamp must be a string")
    text = value.strip()
    if not text:
        raise ValueError("timestamp is empty")
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def format_utc_timestamp(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return (
        value.astimezone(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def normalize_timestamp(value: str) -> str:
    return format_utc_timestamp(parse_timestamp(value))


def _required(mapping: dict[str, Any], key: str) -> Any:
    if key not in mapping:
        raise SnapshotValidationError("missing_required_field", key)
    return mapping[key]


def _required_object(
    mapping: dict[str, Any],
    key: str,
) -> dict[str, Any]:
    value = _required(mapping, key)
    if not isinstance(value, dict):
        raise SnapshotValidationError("invalid_field_type", key)
    return dict(value)


def _required_nonempty_string(
    mapping: dict[str, Any],
    key: str,
) -> str:
    value = _required(mapping, key)
    if not isinstance(value, str):
        raise SnapshotValidationError("invalid_field_type", key)
    if not value.strip():
        raise SnapshotValidationError("invalid_field_format", key)
    return value


def _required_timestamp(
    mapping: dict[str, Any],
    key: str,
) -> str:
    value = _required(mapping, key)
    if not isinstance(value, str):
        raise SnapshotValidationError("invalid_field_type", key)
    try:
        return normalize_timestamp(value)
    except (TypeError, ValueError):
        raise SnapshotValidationError(
            "invalid_field_format",
            key,
        ) from None


def _required_mac(
    mapping: dict[str, Any],
    key: str,
    *,
    prefix: str = "",
) -> str:
    value = _required(mapping, key)
    if not isinstance(value, str):
        raise SnapshotValidationError(
            "invalid_field_type",
            f"{prefix}{key}",
        )
    try:
        return format_mac_colon(value)
    except ValueError:
        raise SnapshotValidationError(
            "invalid_field_format",
            f"{prefix}{key}",
        ) from None


def _nullable_string(value: Any, field: str) -> str | None:
    if value is not None and not isinstance(value, str):
        raise SnapshotValidationError("invalid_field_type", field)
    return value


def _optional_field_string(
    mapping: dict[str, Any],
    key: str,
) -> str | None:
    return _nullable_string(mapping.get(key), f"client.{key}")


def _optional_field_int(
    mapping: dict[str, Any],
    key: str,
) -> int | None:
    value = mapping.get(key)
    if value is None:
        return None
    return _exact_int(value, f"client.{key}")


def _optional_nonnegative_int(
    mapping: dict[str, Any],
    key: str,
) -> int | None:
    value = mapping.get(key)
    if value is None:
        return None
    return _exact_int(value, key, minimum=0)


def _exact_int(
    value: Any,
    field: str,
    *,
    minimum: int | None = None,
) -> int:
    if type(value) is not int:
        raise SnapshotValidationError("invalid_field_type", field)
    if (
        value < -MAX_SQLITE_INTEGER - 1
        or value > MAX_SQLITE_INTEGER
        or (minimum is not None and value < minimum)
    ):
        raise SnapshotValidationError("invalid_field_range", field)
    return value


def _profile_string(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    return value


def _optional_ip(value: Any, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise SnapshotValidationError("invalid_field_type", field)
    try:
        return str(ipaddress.ip_address(value.strip()))
    except ValueError:
        raise SnapshotValidationError(
            "invalid_field_format",
            field,
        ) from None


def _optional_mac_value(value: Any, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise SnapshotValidationError("invalid_field_type", field)
    try:
        return format_mac_colon(value)
    except ValueError:
        raise SnapshotValidationError(
            "invalid_field_format",
            field,
        ) from None
