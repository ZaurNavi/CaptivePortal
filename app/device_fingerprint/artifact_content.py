"""Immutable R14 ArtifactContent identity and canonical byte rules."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Callable

from .models import DeviceFingerprintValidationError

_DIGEST = re.compile(r"[0-9a-f]{64}")
_ARTIFACT_ID = re.compile(r"([A-Za-z][A-Za-z0-9]*):v1:sha256:([0-9a-f]{64})")


def _fail(message: str) -> None:
    raise DeviceFingerprintValidationError(message)


def _normalized(value: Any) -> Any:
    if isinstance(value, dict):
        result = {}
        for key, child in value.items():
            if not isinstance(key, str):
                _fail("Artifact object keys must be strings")
            normalized_key = unicodedata.normalize("NFC", key)
            if normalized_key in result:
                _fail("Artifact NFC key collision")
            result[normalized_key] = _normalized(child)
        return result
    if isinstance(value, (list, tuple)):
        return [_normalized(child) for child in value]
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if value is None or type(value) in (bool, int):
        return value
    if isinstance(value, (float, Decimal)):
        _fail("Artifact floating-point values are forbidden")
    _fail("Unsupported artifact value")


def canonical_artifact_json(value: Any) -> bytes:
    """Return ArtifactCanonicalJsonV1 UTF-8 bytes (not evidence JSON)."""
    try:
        normalized = _normalized(value)
        return json.dumps(
            normalized, ensure_ascii=True, allow_nan=False, sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError, OverflowError, RecursionError) as exc:
        raise DeviceFingerprintValidationError("Invalid artifact JSON") from exc


def decode_artifact_json(value: str) -> Any:
    """Decode imported JSON without losing duplicate-key evidence."""
    if not isinstance(value, str):
        _fail("Artifact JSON must be text")
    try:
        return json.loads(
            value, object_pairs_hook=_unique_pairs,
            parse_constant=lambda _constant: _fail("Non-standard artifact constant"),
        )
    except (ValueError, TypeError, RecursionError) as exc:
        raise DeviceFingerprintValidationError("Invalid artifact JSON") from exc


def _unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            _fail("Duplicate artifact JSON key")
        result[key] = value
    return result


def canonical_set(values: list[Any], primary_key: Callable[[Any], Any]) -> list[Any]:
    """Order a declared SET and reject duplicate semantic primary keys."""
    if not isinstance(values, list):
        _fail("Artifact SET must be a list")
    ordered = []
    for value in values:
        normalized = _normalized(value)
        key = _normalized(primary_key(normalized))
        ordered.append((key, canonical_artifact_json(normalized), normalized))
    try:
        ordered.sort(key=lambda row: (row[0], row[1]))
    except TypeError as exc:
        raise DeviceFingerprintValidationError("Invalid artifact SET key") from exc
    for previous, current in zip(ordered, ordered[1:]):
        if previous[0] == current[0] and previous[1] == current[1]:
            _fail("Duplicate artifact SET element")
    return [row[2] for row in ordered]


@dataclass(frozen=True, slots=True)
class ArtifactContent:
    artifact_type: str
    artifact_schema_version: int
    _semantic_payload_json: bytes
    content_sha256: str
    artifact_id: str

    def __post_init__(self) -> None:
        if (self.artifact_schema_version != 1
                or not isinstance(self._semantic_payload_json, bytes)):
            _fail("Invalid artifact content")
        try:
            parsed = decode_artifact_json(self._semantic_payload_json.decode("utf-8"))
        except UnicodeError as exc:
            raise DeviceFingerprintValidationError("Invalid artifact content") from exc
        if not isinstance(parsed, dict) or canonical_artifact_json(parsed) != self._semantic_payload_json:
            _fail("Noncanonical artifact content")
        digest = hashlib.sha256(self.digest_input_json).hexdigest()
        if (self.content_sha256 != digest
                or self.artifact_id != f"{self.artifact_type}:v1:sha256:{digest}"):
            _fail("Artifact content identity mismatch")

    @property
    def semantic_payload(self) -> dict[str, Any]:
        return json.loads(self._semantic_payload_json)

    @property
    def semantic_payload_json(self) -> bytes:
        return self._semantic_payload_json

    @property
    def digest_input_json(self) -> bytes:
        return canonical_artifact_json({
            "artifact_type": self.artifact_type,
            "artifact_schema_version": self.artifact_schema_version,
            "semantic_payload": self.semantic_payload,
        })


def make_artifact_content(artifact_type: str, semantic_payload: dict[str, Any]) -> ArtifactContent:
    if not isinstance(artifact_type, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9]*", artifact_type):
        _fail("Invalid artifact type")
    if not isinstance(semantic_payload, dict):
        _fail("Artifact semantic payload must be an object")
    payload_json = canonical_artifact_json(semantic_payload)
    digest_input = canonical_artifact_json({
        "artifact_type": artifact_type,
        "artifact_schema_version": 1,
        "semantic_payload": json.loads(payload_json),
    })
    digest = hashlib.sha256(digest_input).hexdigest()
    return ArtifactContent(
        artifact_type=artifact_type,
        artifact_schema_version=1,
        _semantic_payload_json=payload_json,
        content_sha256=digest,
        artifact_id=f"{artifact_type}:v1:sha256:{digest}",
    )


@dataclass(frozen=True, slots=True)
class ArtifactRef:
    artifact_id: str
    content_sha256: str

    def __post_init__(self) -> None:
        match = _ARTIFACT_ID.fullmatch(self.artifact_id) if isinstance(self.artifact_id, str) else None
        if (match is None or not isinstance(self.content_sha256, str)
                or _DIGEST.fullmatch(self.content_sha256) is None
                or match.group(2) != self.content_sha256):
            _fail("Invalid artifact reference")

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "ArtifactRef":
        if not isinstance(value, dict) or set(value) != {"artifact_id", "content_sha256"}:
            _fail("Invalid artifact reference shape")
        return cls(value["artifact_id"], value["content_sha256"])

    def as_dict(self) -> dict[str, str]:
        return {"artifact_id": self.artifact_id, "content_sha256": self.content_sha256}

    def resolve(self, content: ArtifactContent, expected_type: str) -> None:
        if (not isinstance(content, ArtifactContent)
                or content.artifact_type != expected_type
                or self.artifact_id != content.artifact_id
                or self.content_sha256 != content.content_sha256):
            _fail("Artifact reference does not match content")
