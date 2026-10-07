"""Immutable Settings boundary models and bounded public errors."""
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping

TARGET = "captive-portal.service"
API_VERSION = "admin.settings.v1"


class ActivationState(str, Enum):
    ACTIVE = "active"
    PENDING = "pending_main_restart"
    FAILED = "activation_failed"
    UNAVAILABLE = "runtime_unavailable"


class ConsumerState(str, Enum):
    ACTIVE = "active"
    DISABLED = "consumer_disabled"


class StoreState(str, Enum):
    DISABLED = "disabled"
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


class SettingsError(Exception):
    def __init__(self, code, status=503, details=()):
        super().__init__(code)
        self.code, self.status, self.details = code, status, tuple(details)


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


@dataclass(frozen=True, slots=True)
class ResolvedSettingsSnapshot:
    generation_id: int | None
    values: Mapping[str, Any]
    base_source_by_key: Mapping[str, str]
    base_value_by_key: Mapping[str, int | str | None]
    persisted_override_by_key: Mapping[str, int | str | None]


@dataclass(frozen=True, slots=True)
class SettingReadModelV1:
    key: str
    display_label: str
    description: str
    group: str
    value_type: str
    scope_type: str
    scope_id: None
    editable: bool
    read_only_reason: None
    secret_class: str
    default_value: int
    base_source: str
    base_value: int
    persisted_override_value: int | None
    configured_value: int
    effective_value: int | None
    pending_value: int | None
    configured_generation: int
    effective_generation: int | None
    activation_state: str
    apply_requirement: str
    activation_target: str
    consumer_state: str | None
    validation: Mapping[str, int | str]
    last_changed_at: str | None
    last_changed_by: Mapping[str, str] | None


@dataclass(frozen=True, slots=True)
class SettingsReadModelV1:
    body: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class SettingsMutationChange:
    key: str
    operation: str
    value: int | str | None = None


@dataclass(frozen=True, slots=True)
class SettingsMutationResult:
    status: int
    body: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class SettingsActivationEvent:
    generation_id: int
    target: str
    attempted_at_utc: str
    activation_result: str
    effective_generation_after_attempt: int | None
    safe_error_code: str | None


@dataclass(frozen=True, slots=True)
class SettingsAdminContext:
    feature_enabled: bool
    store_state: str
    read_service: Any = None
    mutation_service: Any = None


@dataclass(frozen=True, slots=True)
class SettingsBootstrapResult:
    feature_enabled: bool
    store_state: str
    runtime_settings: Mapping[str, Any]
    resolved_snapshot: ResolvedSettingsSnapshot
    admin_context: SettingsAdminContext
    activation_service: Any = None
