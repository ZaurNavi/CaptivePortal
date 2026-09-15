"""Canonical Task-03A matrix formats and deterministic file helpers."""

from __future__ import annotations

import hashlib
import ipaddress
import json
import re
import uuid
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any, Callable

from app.device_fingerprint.schema_registry import build_production_schema_registry
from app.device_fingerprint.validation import (
    canonical_json as evidence_canonical_json,
    canonical_sha256,
    parse_utc,
    validate_health_status,
    validate_machine_id,
    validate_quality,
    validate_reason_code,
    validate_site_id,
    validate_source_kind,
    validate_uuid,
    validate_version,
)

MATRIX_FORMAT_VERSION = 1
MATRIX_REVISION = 1
MATRIX_RETENTION_DAYS = 180
BINDING_RETENTION_DAYS = 30
SITE_ID = "6a64f17630da7c70d232187a"

PRODUCTION_SCHEMA_REGISTRY = (
    ("dhcp", 1),
    ("portal_headers", 1),
    ("quic_client", 1),
    ("tcp_syn", 1),
    ("tls_client", 1),
)
SOURCE_KINDS = tuple(item[0] for item in PRODUCTION_SCHEMA_REGISTRY)
SOURCE_CAPTURE_IDS = {
    "dhcp": "zefer-span-01",
    "tcp_syn": "zefer-span-01",
    "tls_client": "zefer-span-01",
    "quic_client": "zefer-span-01",
    "portal_headers": "zefer-portal-http-01",
}
SOURCE_PRODUCER_IDS = {
    "dhcp": "sensor-zefer-01",
    "tcp_syn": "sensor-zefer-01",
    "tls_client": "sensor-zefer-01",
    "quic_client": "sensor-zefer-01",
    "portal_headers": "portal-zefer-01",
}

SEALED_DATA_FILES = (
    "manifest.json",
    "devices.jsonl",
    "device_states.jsonl",
    "samples.jsonl",
    "evidence.jsonl",
    "source_health.jsonl",
    "checksums.sha256",
)
CHECKSUM_FILES = tuple(sorted(name for name in SEALED_DATA_FILES if name != "checksums.sha256"))

DEVICE_CLASSES = frozenset({"smartphone", "tablet", "laptop"})
OS_FAMILIES = frozenset({"android", "ios", "ipados", "windows", "macos", "chromeos", "linux"})
CONTROL_BASES = frozenset({"owner_controlled", "explicitly_authorized"})
VERIFICATION_METHODS = frozenset({
    "device_settings",
    "device_about_page",
    "physical_manufacturer_label",
    "owner_purchase_record",
})
NETWORK_STATES = frozenset({"fresh_attach", "same_attachment_revisit"})
RUNTIME_CONTEXTS = frozenset({"captive_webview", "captive_helper", "normal_browser"})
BROWSER_FAMILIES = frozenset({
    "android_webview", "chrome", "edge", "firefox", "safari",
    "chromium_other", "captive_helper", "other",
})
MAC_MODES = frozenset({"global", "randomized_stable", "randomized_rotated", "unknown"})
PORTAL_ENTRY_MODES = frozenset({"omada_external_portal", "capport_login"})
POINT_ROLES = ("latest_before_start", "during_window", "latest_at_end")
INVALID_REASONS = frozenset({
    "binding_uncertain", "context_changed", "window_too_long", "evidence_missing",
    "ground_truth_unverified", "source_schema_error", "privacy_violation", "operator_abort",
})
COVERAGE_LIMITATIONS = frozenset({
    "no_chromeos", "no_linux", "quic_sparse", "captive_context_unavailable",
    "browser_diversity_limited", "device_count_minimum_only",
})

DEVICE_REQUIRED = frozenset({
    "matrix_format_version", "lab_device_id", "device_class_gt", "manufacturer_gt",
    "model_gt", "collection_authorized", "control_basis_gt",
    "ground_truth_verified_at", "ground_truth_verification_methods",
})
DEVICE_OPTIONAL = frozenset({"hardware_variant_gt"})
STATE_REQUIRED = frozenset({
    "matrix_format_version", "ground_truth_state_id", "lab_device_id", "os_family_gt",
    "os_version_gt", "os_major_gt", "state_verified_at", "state_verification_methods",
})
STATE_OPTIONAL = frozenset({"os_build_gt"})
SAMPLE_REQUIRED = frozenset({
    "matrix_format_version", "sample_id", "collection_run_id", "lab_device_id",
    "ground_truth_state_id", "site_id", "window_start_utc", "window_end_utc",
    "network_epoch_id", "network_state_gt", "runtime_context_gt", "browser_family_gt",
    "browser_version_major_gt", "mac_mode_gt", "portal_entry_mode_gt",
    "context_supported_gt", "sample_status", "sealed_at",
})
BINDING_REQUIRED = frozenset({"sample_id", "lab_device_id", "observed_mac"})
BINDING_OPTIONAL = frozenset({"observed_ip"})
EVIDENCE_REQUIRED = frozenset({
    "evidence_id", "source_event_id", "producer_id", "source_kind", "source_subtype",
    "extractor_name", "extractor_version", "feature_schema_version", "rule_version",
    "site_id", "capture_source_id", "observed_at", "quality_state", "privacy_class",
    "payload", "payload_sha256", "ingested_at", "sample_id", "lab_device_id",
})
SOURCE_HEALTH_REQUIRED = frozenset({
    "matrix_format_version", "sample_id", "lab_device_id", "source_health_id",
    "source_health_event_id", "producer_id", "site_id", "capture_source_id",
    "source_kind", "status", "reason_code", "observed_at", "ingested_at", "point_roles",
})
MANIFEST_REQUIRED = frozenset({
    "matrix_format_version", "matrix_id", "matrix_revision", "sealed_at",
    "repository_head", "repository_tree", "site_id", "collection_procedure_version",
    "ground_truth_policy_version", "production_schema_registry", "task01_retention_days",
    "device_count", "sealed_sample_count", "evidence_count", "source_health_count",
    "invalid_sample_count", "invalid_sample_reason_counts", "known_coverage_limitations",
    "supersedes_matrix_id",
})

_HEX40 = re.compile(r"[0-9a-f]{40}")
_HEX64 = re.compile(r"[0-9a-f]{64}")
_MAC = re.compile(r"(?<![0-9A-Fa-f])(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}(?![0-9A-Fa-f])")
_IPV4_CANDIDATE = re.compile(r"(?<![0-9])(?:[0-9]{1,3}\.){3}[0-9]{1,3}(?![0-9])")
_IPV6_CANDIDATE = re.compile(r"(?<![0-9A-Fa-f:])[0-9A-Fa-f:]{2,}(?![0-9A-Fa-f:])")
_RAW_MARKERS = ("mozilla/", "user-agent", "sec-ch-ua", "bearer ", "authorization:")
_PRIVATE_KEYS = frozenset({
    "observed_mac", "observed_ip", "raw_user_agent", "raw_client_hints", "sni",
    "server_name", "dns_history", "cookie", "authorization", "credential", "owner_name",
    "person_name", "imei", "serial_number", "sim_iccid", "personal_hostname",
})


class MatrixFormatError(ValueError):
    """A sanitized strict-format or sealed-matrix validation failure."""


def canonical_json_text(value: Any) -> str:
    try:
        return json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError, OverflowError, RecursionError) as exc:
        raise MatrixFormatError("Matrix JSON is invalid") from exc


def canonical_json_line(value: Any) -> bytes:
    return (canonical_json_text(value) + "\n").encode("utf-8")


def write_canonical_json(path: Path, value: Mapping[str, Any]) -> None:
    _write_bytes(path, canonical_json_line(dict(value)))


def write_canonical_jsonl(path: Path, values: Iterable[Mapping[str, Any]]) -> None:
    _write_bytes(path, b"".join(canonical_json_line(dict(value)) for value in values))


def read_canonical_json(path: Path) -> dict[str, Any]:
    raw = _read_bytes(path)
    value = _load_one(raw)
    if not isinstance(value, dict) or canonical_json_line(value) != raw:
        raise MatrixFormatError("JSON file is not canonical")
    return value


def read_canonical_jsonl(path: Path) -> list[dict[str, Any]]:
    raw = _read_bytes(path)
    if not raw:
        return []
    if not raw.endswith(b"\n") or b"\r" in raw:
        raise MatrixFormatError("JSONL framing is invalid")
    result: list[dict[str, Any]] = []
    for line in raw.splitlines(keepends=True):
        value = _load_one(line)
        if not isinstance(value, dict) or canonical_json_line(value) != line:
            raise MatrixFormatError("JSONL row is not canonical")
        result.append(value)
    return result


def validate_device(value: Mapping[str, Any]) -> dict[str, Any]:
    row = _row(value, DEVICE_REQUIRED, DEVICE_OPTIONAL, "device")
    _version_one(row)
    _uuid4(row["lab_device_id"], "lab_device_id")
    _enum(row["device_class_gt"], DEVICE_CLASSES, "device_class_gt")
    _ascii(row["manufacturer_gt"], 1, 64, "manufacturer_gt")
    _ascii(row["model_gt"], 1, 96, "model_gt")
    if "hardware_variant_gt" in row:
        _ascii(row["hardware_variant_gt"], 1, 96, "hardware_variant_gt")
    if row["collection_authorized"] is not True:
        raise MatrixFormatError("Device collection is not authorized")
    _enum(row["control_basis_gt"], CONTROL_BASES, "control_basis_gt")
    _timestamp(row["ground_truth_verified_at"], "ground_truth_verified_at")
    _verification_methods(row["ground_truth_verification_methods"], os_state=False)
    _privacy_scan(row)
    return row


def validate_device_state(value: Mapping[str, Any]) -> dict[str, Any]:
    row = _row(value, STATE_REQUIRED, STATE_OPTIONAL, "device state")
    _version_one(row)
    _uuid4(row["ground_truth_state_id"], "ground_truth_state_id")
    _uuid4(row["lab_device_id"], "lab_device_id")
    _enum(row["os_family_gt"], OS_FAMILIES, "os_family_gt")
    version = _ascii(row["os_version_gt"], 1, 64, "os_version_gt")
    major = _integer(row["os_major_gt"], 1, 99, "os_major_gt")
    if re.search(rf"(?<![0-9]){major}(?![0-9])", version) is None:
        raise MatrixFormatError("OS major does not agree with OS version")
    _timestamp(row["state_verified_at"], "state_verified_at")
    _verification_methods(row["state_verification_methods"], os_state=True)
    if "os_build_gt" in row:
        _ascii(row["os_build_gt"], 1, 64, "os_build_gt")
    _privacy_scan(row)
    return row


def validate_sample(value: Mapping[str, Any]) -> dict[str, Any]:
    row = _row(value, SAMPLE_REQUIRED, (), "sample")
    _version_one(row)
    for field in ("sample_id", "collection_run_id", "lab_device_id", "ground_truth_state_id", "network_epoch_id"):
        _uuid4(row[field], field)
    if _call(validate_site_id, row["site_id"]) != SITE_ID:
        raise MatrixFormatError("Sample Site is invalid")
    start = _timestamp(row["window_start_utc"], "window_start_utc")
    end = _timestamp(row["window_end_utc"], "window_end_utc")
    seconds = (end - start).total_seconds()
    if not 0 < seconds <= 600:
        raise MatrixFormatError("Sample window is invalid")
    _enum(row["network_state_gt"], NETWORK_STATES, "network_state_gt")
    _enum(row["runtime_context_gt"], RUNTIME_CONTEXTS, "runtime_context_gt")
    _enum(row["browser_family_gt"], BROWSER_FAMILIES, "browser_family_gt")
    if row["browser_version_major_gt"] is not None:
        _integer(row["browser_version_major_gt"], 1, 999, "browser_version_major_gt")
    _enum(row["mac_mode_gt"], MAC_MODES, "mac_mode_gt")
    _enum(row["portal_entry_mode_gt"], PORTAL_ENTRY_MODES, "portal_entry_mode_gt")
    if type(row["context_supported_gt"]) is not bool:
        raise MatrixFormatError("context_supported_gt is invalid")
    if row["sample_status"] != "sealed":
        raise MatrixFormatError("Only sealed samples are allowed")
    _timestamp(row["sealed_at"], "sealed_at")
    _privacy_scan(row)
    return row


def validate_binding(value: Mapping[str, Any]) -> dict[str, Any]:
    row = _row(value, BINDING_REQUIRED, BINDING_OPTIONAL, "binding")
    _uuid4(row["sample_id"], "sample_id")
    _uuid4(row["lab_device_id"], "lab_device_id")
    try:
        from app.device_fingerprint.validation import validate_ip, validate_mac
        row["observed_mac"] = _call(validate_mac, row["observed_mac"])
        if "observed_ip" in row:
            row["observed_ip"] = _call(validate_ip, row["observed_ip"])
    except MatrixFormatError:
        raise
    return row


def validate_evidence(value: Mapping[str, Any]) -> dict[str, Any]:
    row = _row(value, EVIDENCE_REQUIRED, (), "evidence")
    for field in ("evidence_id", "source_event_id", "sample_id", "lab_device_id"):
        _uuid(row[field], field)
    kind = _call(validate_source_kind, row["source_kind"])
    if _call(validate_machine_id, row["producer_id"]) != SOURCE_PRODUCER_IDS.get(kind):
        raise MatrixFormatError("Evidence producer is invalid")
    version = _integer(row["feature_schema_version"], 1, 2_147_483_647, "feature_schema_version")
    if (kind, version) not in PRODUCTION_SCHEMA_REGISTRY:
        raise MatrixFormatError("Evidence schema is unsupported")
    if row["source_subtype"] is not None:
        _call(validate_machine_id, row["source_subtype"])
    _call(validate_machine_id, row["extractor_name"])
    _call(validate_version, row["extractor_version"])
    if row["rule_version"] is not None:
        _call(validate_version, row["rule_version"])
    if _call(validate_site_id, row["site_id"]) != SITE_ID:
        raise MatrixFormatError("Evidence Site is invalid")
    if _call(validate_machine_id, row["capture_source_id"]) != SOURCE_CAPTURE_IDS[kind]:
        raise MatrixFormatError("Evidence capture source is invalid")
    _timestamp(row["observed_at"], "observed_at")
    _call(validate_quality, row["quality_state"])
    if row["privacy_class"] != "P1":
        raise MatrixFormatError("Evidence privacy class is invalid")
    if not isinstance(row["payload"], dict):
        raise MatrixFormatError("Evidence payload is invalid")
    registry = build_production_schema_registry()
    try:
        normalized = dict(registry.validate(kind, version, row["payload"]))
        payload_json = evidence_canonical_json(normalized)
    except Exception as exc:
        raise MatrixFormatError("Evidence payload is invalid") from exc
    if normalized != row["payload"] or canonical_sha256(payload_json) != row["payload_sha256"]:
        raise MatrixFormatError("Evidence payload digest is invalid")
    _timestamp(row["ingested_at"], "ingested_at")
    _privacy_scan(row)
    return row


def validate_source_health(value: Mapping[str, Any]) -> dict[str, Any]:
    row = _row(value, SOURCE_HEALTH_REQUIRED, (), "source health")
    _version_one(row)
    for field in ("sample_id", "lab_device_id", "source_health_id", "source_health_event_id"):
        _uuid(row[field], field)
    if _call(validate_site_id, row["site_id"]) != SITE_ID:
        raise MatrixFormatError("Source-health Site is invalid")
    kind = _call(validate_source_kind, row["source_kind"])
    if _call(validate_machine_id, row["producer_id"]) != SOURCE_PRODUCER_IDS.get(kind):
        raise MatrixFormatError("Source-health producer is invalid")
    if kind not in SOURCE_KINDS or row["capture_source_id"] != SOURCE_CAPTURE_IDS[kind]:
        raise MatrixFormatError("Source-health scope is invalid")
    _call(validate_machine_id, row["capture_source_id"])
    _call(validate_health_status, row["status"])
    _call(validate_reason_code, row["reason_code"])
    _timestamp(row["observed_at"], "observed_at")
    _timestamp(row["ingested_at"], "ingested_at")
    roles = row["point_roles"]
    if (
        not isinstance(roles, list)
        or not roles
        or len(set(roles)) != len(roles)
        or any(role not in POINT_ROLES for role in roles)
        or roles != [role for role in POINT_ROLES if role in roles]
    ):
        raise MatrixFormatError("Source-health point roles are invalid")
    _privacy_scan(row)
    return row


def validate_manifest(value: Mapping[str, Any], *, sealed: bool = True) -> dict[str, Any]:
    row = _row(value, MANIFEST_REQUIRED, (), "manifest")
    _version_one(row)
    if row["matrix_revision"] != MATRIX_REVISION:
        raise MatrixFormatError("Matrix revision is invalid")
    _uuid4(row["matrix_id"], "matrix_id")
    if sealed:
        _timestamp(row["sealed_at"], "sealed_at")
    elif row["sealed_at"] is not None:
        raise MatrixFormatError("Unsealed manifest has a sealing timestamp")
    if not isinstance(row["repository_head"], str) or _HEX40.fullmatch(row["repository_head"]) is None:
        raise MatrixFormatError("Repository HEAD is invalid")
    if not isinstance(row["repository_tree"], str) or _HEX40.fullmatch(row["repository_tree"]) is None:
        raise MatrixFormatError("Repository tree is invalid")
    if _call(validate_site_id, row["site_id"]) != SITE_ID:
        raise MatrixFormatError("Manifest Site is invalid")
    _call(validate_version, row["collection_procedure_version"])
    _call(validate_version, row["ground_truth_policy_version"])
    if row["production_schema_registry"] != [list(item) for item in PRODUCTION_SCHEMA_REGISTRY]:
        raise MatrixFormatError("Production schema registry is invalid")
    for field in (
        "task01_retention_days", "device_count", "sealed_sample_count", "evidence_count",
        "source_health_count", "invalid_sample_count",
    ):
        _integer(row[field], 0 if field != "task01_retention_days" else 1, 1_000_000_000, field)
    reasons = row["invalid_sample_reason_counts"]
    if not isinstance(reasons, dict) or any(key not in INVALID_REASONS for key in reasons):
        raise MatrixFormatError("Invalid-sample reasons are invalid")
    for key, count in reasons.items():
        _integer(count, 0, 1_000_000_000, key)
    if sum(reasons.values()) != row["invalid_sample_count"]:
        raise MatrixFormatError("Invalid-sample counts do not reconcile")
    limitations = row["known_coverage_limitations"]
    if (
        not isinstance(limitations, list)
        or limitations != sorted(set(limitations))
        or any(value not in COVERAGE_LIMITATIONS for value in limitations)
    ):
        raise MatrixFormatError("Coverage limitations are invalid")
    if row["supersedes_matrix_id"] is not None:
        _uuid4(row["supersedes_matrix_id"], "supersedes_matrix_id")
        if row["supersedes_matrix_id"] == row["matrix_id"]:
            raise MatrixFormatError("Matrix cannot supersede itself")
    _privacy_scan(row)
    return row


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        if path.is_symlink() or not path.is_file():
            raise MatrixFormatError("Matrix file target is unsafe")
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
    except OSError as exc:
        raise MatrixFormatError("Matrix file is unavailable") from exc
    return digest.hexdigest()


def checksum_text(directory: Path) -> str:
    return "".join(f"{sha256_file(directory / name)}  {name}\n" for name in CHECKSUM_FILES)


def validate_checksums(directory: Path) -> None:
    path = directory / "checksums.sha256"
    try:
        if path.is_symlink() or not path.is_file():
            raise MatrixFormatError("Checksum file target is unsafe")
        raw = path.read_bytes()
    except OSError as exc:
        raise MatrixFormatError("Checksum file is unavailable") from exc
    try:
        text = raw.decode("ascii")
    except UnicodeError as exc:
        raise MatrixFormatError("Checksum file is invalid") from exc
    expected = checksum_text(directory)
    if text != expected:
        raise MatrixFormatError("Checksum file does not match matrix files")


def write_checksums(directory: Path) -> None:
    _write_bytes(directory / "checksums.sha256", checksum_text(directory).encode("ascii"))


def _row(value: Mapping[str, Any], required: frozenset[str], optional: Iterable[str], label: str) -> dict[str, Any]:
    optional_fields = frozenset(optional)
    if (
        not isinstance(value, dict)
        or not required <= set(value)
        or not set(value) <= required | optional_fields
    ):
        raise MatrixFormatError(f"{label.capitalize()} fields are invalid")
    return dict(value)


def _version_one(row: Mapping[str, Any]) -> None:
    if row.get("matrix_format_version") != MATRIX_FORMAT_VERSION:
        raise MatrixFormatError("Matrix format version is invalid")


def _call(function: Callable[..., Any], *args: Any) -> Any:
    try:
        return function(*args)
    except Exception as exc:
        raise MatrixFormatError("Canonical value is invalid") from exc


def _uuid(value: Any, label: str) -> str:
    del label
    return _call(validate_uuid, value)


def _uuid4(value: Any, label: str) -> str:
    canonical = _uuid(value, label)
    if uuid.UUID(canonical).version != 4:
        raise MatrixFormatError(f"{label} must be UUID4")
    return canonical


def _timestamp(value: Any, label: str):
    del label
    return _call(parse_utc, value)


def _enum(value: Any, allowed: frozenset[str], label: str) -> str:
    if not isinstance(value, str) or value not in allowed:
        raise MatrixFormatError(f"{label} is invalid")
    return value


def _ascii(value: Any, minimum: int, maximum: int, label: str) -> str:
    if (
        not isinstance(value, str)
        or not minimum <= len(value) <= maximum
        or any(ord(character) < 0x20 or ord(character) > 0x7E for character in value)
    ):
        raise MatrixFormatError(f"{label} is invalid")
    return value


def _integer(value: Any, minimum: int, maximum: int, label: str) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise MatrixFormatError(f"{label} is invalid")
    return value


def _verification_methods(value: Any, *, os_state: bool) -> None:
    if (
        not isinstance(value, list)
        or not value
        or len(value) != len(set(value))
        or value != sorted(value)
        or any(method not in VERIFICATION_METHODS for method in value)
    ):
        raise MatrixFormatError("Verification methods are invalid")
    if os_state and not ({"device_settings", "device_about_page"} & set(value)):
        raise MatrixFormatError("OS state lacks an authoritative verification method")


def _privacy_scan(value: Any) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if not isinstance(key, str) or key.lower() in _PRIVATE_KEYS:
                raise MatrixFormatError("Private field is forbidden in sealed matrix")
            _privacy_scan(child)
        return
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for child in value:
            _privacy_scan(child)
        return
    if isinstance(value, str):
        lowered = value.lower()
        if _MAC.search(value) or _contains_ip(value) or any(marker in lowered for marker in _RAW_MARKERS):
            raise MatrixFormatError("Private value is forbidden in sealed matrix")


def _contains_ip(value: str) -> bool:
    candidates = [match.group(0) for match in _IPV4_CANDIDATE.finditer(value)]
    candidates.extend(match.group(0) for match in _IPV6_CANDIDATE.finditer(value))
    for candidate in candidates:
        try:
            ipaddress.ip_address(candidate)
        except ValueError:
            continue
        return True
    return False


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise MatrixFormatError("Duplicate JSON key")
        result[key] = value
    return result


def _load_one(raw: bytes) -> Any:
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs)
    except MatrixFormatError:
        raise
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise MatrixFormatError("Matrix JSON is invalid") from exc


def _read_bytes(path: Path) -> bytes:
    try:
        if path.is_symlink() or not path.is_file():
            raise MatrixFormatError("Matrix file target is unsafe")
        return path.read_bytes()
    except MatrixFormatError:
        raise
    except OSError as exc:
        raise MatrixFormatError("Matrix file is unavailable") from exc


def _write_bytes(path: Path, value: bytes) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and (path.is_symlink() or not path.is_file()):
            raise MatrixFormatError("Matrix output target is unsafe")
        path.write_bytes(value)
    except MatrixFormatError:
        raise
    except OSError as exc:
        raise MatrixFormatError("Matrix output is unavailable") from exc
