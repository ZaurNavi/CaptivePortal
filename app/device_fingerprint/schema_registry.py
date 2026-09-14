"""Immutable-after-composition evidence schema registry."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from .models import DeviceFingerprintUnsupportedSchema, DeviceFingerprintValidationError
from .validation import canonical_json, validate_feature_schema_version, validate_source_kind

Validator = Callable[[Mapping[str, Any]], Mapping[str, Any]]


class EvidenceSchemaRegistry:
    def __init__(self) -> None:
        self._validators: dict[tuple[str, int], Validator] = {}
        self._frozen = False

    def register(self, source_kind: str, feature_schema_version: int, validator: Validator) -> None:
        key = (validate_source_kind(source_kind), validate_feature_schema_version(feature_schema_version))
        if self._frozen or key in self._validators or not callable(validator):
            raise DeviceFingerprintValidationError("Schema registration is invalid")
        self._validators[key] = validator

    def freeze(self) -> "EvidenceSchemaRegistry":
        self._frozen = True
        return self

    @property
    def frozen(self) -> bool:
        return self._frozen

    def validate(self, source_kind: str, feature_schema_version: int, payload: Any) -> Mapping[str, Any]:
        if not self._frozen:
            raise DeviceFingerprintValidationError("Schema registry is not frozen")
        validator = self._validators.get((source_kind, feature_schema_version))
        if validator is None:
            raise DeviceFingerprintUnsupportedSchema("Unsupported evidence schema")
        if not isinstance(payload, Mapping):
            raise DeviceFingerprintValidationError("Payload must be an object")
        result = validator(payload)
        if not isinstance(result, Mapping):
            raise DeviceFingerprintValidationError("Schema validator returned invalid payload")
        normalized = dict(result)
        canonical_json(normalized)
        return normalized


def build_production_schema_registry() -> EvidenceSchemaRegistry:
    return EvidenceSchemaRegistry().freeze()
