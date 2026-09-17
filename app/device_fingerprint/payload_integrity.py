"""Pure integrity boundary for persisted Task-01 evidence payloads."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .models import DeviceFingerprintValidationError
from .schema_registry import EvidenceSchemaRegistry
from .validation import (
    canonical_json,
    canonical_sha256,
    validate_feature_schema_version,
    validate_source_kind,
)

_SHA256 = re.compile(r"[0-9a-f]{64}")


@dataclass(frozen=True, slots=True)
class VerifiedEvidencePayload:
    schema_supported: bool
    materialized_payload: Mapping[str, Any] | None
    reason_code: str | None
    verified_payload_bytes: int
    materialized_payload_bytes: int


def verify_persisted_payload(
    source_kind: str,
    feature_schema_version: int,
    payload_json: str,
    payload_sha256: str,
    registry: EvidenceSchemaRegistry,
) -> VerifiedEvidencePayload:
    """Verify stored canonical bytes before exact-schema materialization."""
    if not isinstance(payload_json, str):
        raise DeviceFingerprintValidationError("Invalid persisted payload JSON")
    try:
        decoded = json.loads(
            payload_json,
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
    except (ValueError, TypeError, RecursionError) as exc:
        raise DeviceFingerprintValidationError("Invalid persisted payload JSON") from exc
    if not isinstance(decoded, dict):
        raise DeviceFingerprintValidationError("Persisted payload must be an object")

    canonical = canonical_json(decoded)
    if canonical != payload_json:
        raise DeviceFingerprintValidationError("Persisted payload is not canonical")
    if not isinstance(payload_sha256, str) or _SHA256.fullmatch(payload_sha256) is None:
        raise DeviceFingerprintValidationError("Invalid persisted payload digest")
    if canonical_sha256(canonical) != payload_sha256:
        raise DeviceFingerprintValidationError("Persisted payload digest mismatch")

    verified_bytes = len(canonical.encode("utf-8"))
    source_kind = validate_source_kind(source_kind)
    feature_schema_version = validate_feature_schema_version(feature_schema_version)
    if not isinstance(registry, EvidenceSchemaRegistry):
        raise DeviceFingerprintValidationError("Invalid evidence schema registry")
    if not registry.supports(source_kind, feature_schema_version):
        return VerifiedEvidencePayload(
            schema_supported=False,
            materialized_payload=None,
            reason_code="unsupported_evidence_contract",
            verified_payload_bytes=verified_bytes,
            materialized_payload_bytes=0,
        )
    materialized = registry.validate(source_kind, feature_schema_version, decoded)
    return VerifiedEvidencePayload(
        schema_supported=True,
        materialized_payload=materialized,
        reason_code=None,
        verified_payload_bytes=verified_bytes,
        materialized_payload_bytes=verified_bytes,
    )


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DeviceFingerprintValidationError("Duplicate persisted payload key")
        result[key] = value
    return result


def _reject_constant(_value: str) -> None:
    raise DeviceFingerprintValidationError("Non-standard persisted payload constant")
