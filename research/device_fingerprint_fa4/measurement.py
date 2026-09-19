"""Read-only F-A4-A measurement of the accepted Task-01 snapshot path."""

from __future__ import annotations

import json
import os
import platform
import re
import time
import tracemalloc
from collections import Counter
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any
from unittest.mock import patch

from app.device_fingerprint.artifact_content import canonical_artifact_json
from app.device_fingerprint.models import DeviceFingerprintValidationError
from app.device_fingerprint.payload_integrity import verify_persisted_payload
from app.device_fingerprint.read_service import DeviceFingerprintReadService
from app.device_fingerprint.repository import DeviceFingerprintRepository
from app.device_fingerprint.schema_registry import build_production_schema_registry
from app.device_fingerprint.validation import (
    format_utc, parse_utc, validate_mac, validate_site_id,
)

from .semantic_accounting import (
    SemanticAccountingDependencies,
    applicable_binding_epochs,
    authorized_descriptor,
    binding_descriptor_bytes,
    complete_semantic_byte_accounting,
    health_anchor_descriptor,
    required_health_scopes,
    semantic_dependency_descriptor,
    semantic_dependency_reference_bytes,
    validate_complete_health_scopes,
    validate_semantic_accounting_dependencies,
)

_SHA = re.compile(r"[0-9a-f]{40}")
_EVIDENCE_FIELDS = (
    "evidence_id", "ingest_sequence", "producer_id", "source_kind",
    "source_subtype", "capture_source_id", "extractor_name", "extractor_version",
    "feature_schema_version", "rule_version", "site_id", "observed_at",
    "ingested_at", "observed_mac", "privacy_class", "quality_state",
    "payload_sha256",
)
_HEALTH_FIELDS = (
    "source_health_id", "ingest_sequence", "producer_id", "source_kind",
    "capture_source_id", "status", "reason_code", "observed_at",
    "ingested_at", "content_sha256",
)


@dataclass(frozen=True, slots=True)
class InspectionCase:
    measurement_case_id: str
    db_path: str
    site_id: str
    observed_mac: str
    from_utc: str
    to_utc: str
    health_scopes: tuple[tuple[str, str, str], ...]
    page_size: int
    repository_commit_sha: str
    repository_tree_sha: str
    retention_days: int = 30


def _validate(case: InspectionCase) -> None:
    if not isinstance(case.measurement_case_id, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", case.measurement_case_id):
        raise ValueError("Invalid measurement case ID")
    if any(_SHA.fullmatch(value) is None for value in (
        case.repository_commit_sha, case.repository_tree_sha,
    )):
        raise ValueError("Invalid candidate identity")
    validate_site_id(case.site_id)
    validate_mac(case.observed_mac)
    if parse_utc(case.from_utc) >= parse_utc(case.to_utc):
        raise ValueError("Invalid measurement window")
    if type(case.page_size) is not int or not 1 <= case.page_size <= 500:
        raise ValueError("Page size must be within accepted 1..500 range")
    if not isinstance(case.health_scopes, tuple) or not case.health_scopes:
        raise ValueError("At least one source-health scope is required")
    if len(set(case.health_scopes)) != len(case.health_scopes):
        raise ValueError("Duplicate health scope")


def _ns() -> int:
    return time.perf_counter_ns()


def _duration(start: int) -> dict[str, int]:
    ns = _ns() - start
    return {"duration_ns": ns, "duration_ms": ns // 1_000_000}


def _plans(connection: Any, case: InspectionCase, watermark: int,
           health_scopes: tuple[tuple[str, str, str], ...]) -> list[dict[str, Any]]:
    """Mirror the current read-session SELECT/WHERE/ORDER/LIMIT shapes."""
    site, mac = case.site_id, validate_mac(case.observed_mac)
    producer, capture, kind = health_scopes[0]
    evidence_where = "site_id=? AND observed_mac=? AND observed_at>=? AND observed_at<? AND ingest_sequence<=?"
    evidence_params: tuple[Any, ...] = (site, mac, case.from_utc, case.to_utc, watermark)
    health_where = ("site_id=? AND producer_id=? AND capture_source_id=? AND source_kind=? "
                    "AND observed_at>=? AND observed_at<? AND ingest_sequence<=?")
    health_params: tuple[Any, ...] = (site, producer, capture, kind, case.from_utc, case.to_utc, watermark)
    ec = "(observed_at>? OR (observed_at=? AND evidence_id>?))"
    hc = "(observed_at>? OR (observed_at=? AND source_health_id>?))"
    cursor = (case.from_utc, case.from_utc, "00000000-0000-4000-8000-000000000000")
    shapes = [
        ("evidence_first", "device_fingerprint_evidence", evidence_where, evidence_params, "evidence_id", False),
        ("evidence_continuation", "device_fingerprint_evidence", evidence_where + " AND " + ec,
         evidence_params + cursor, "evidence_id", False),
        ("evidence_source_kind", "device_fingerprint_evidence", evidence_where + " AND source_kind=?",
         evidence_params + (kind,), "evidence_id", False),
        ("evidence_producer_id", "device_fingerprint_evidence", evidence_where + " AND producer_id=?",
         evidence_params + (producer,), "evidence_id", False),
        ("evidence_capture_source_id", "device_fingerprint_evidence", evidence_where + " AND capture_source_id=?",
         evidence_params + (capture,), "evidence_id", False),
        ("health_first", "device_fingerprint_source_health_events", health_where, health_params,
         "source_health_id", False),
        ("health_continuation", "device_fingerprint_source_health_events", health_where + " AND " + hc,
         health_params + cursor, "source_health_id", False),
        ("health_latest_predecessor", "device_fingerprint_source_health_events",
         "site_id=? AND producer_id=? AND capture_source_id=? AND source_kind=? AND observed_at<=? AND ingest_sequence<=?",
         (site, producer, capture, kind, case.to_utc, watermark), "source_health_id", True),
    ]
    result = []
    for case_id, table, where, params, id_column, reverse in shapes:
        direction = " DESC" if reverse else ""
        sql = (f"SELECT * FROM {table} WHERE {where} ORDER BY observed_at{direction},"
               f"{id_column}{direction} LIMIT ?")
        details = [str(row[3]) for row in connection.execute(
            "EXPLAIN QUERY PLAN " + sql, params + ((1 if reverse else case.page_size + 1),),
        )]
        result.append({
            "query_case_id": case_id,
            "normalized_sql_shape": " ".join(sql.split()),
            "plan_rows": details,
            "used_index_names": sorted(set(re.findall(r"USING (?:COVERING )?INDEX ([A-Za-z0-9_]+)", " ".join(details)))),
            "full_table_scan_observed": any(
                re.search(rf"\bSCAN {table}\b", line)
                and "USING INDEX" not in line
                and "USING COVERING INDEX" not in line
                for line in details
            ),
        })
    return result


def _count_rows(connection: Any, table: str) -> int:
    return int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


def _rss() -> tuple[int | None, bool]:
    if os.name != "posix":
        return None, False
    try:
        import resource
        return int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss), True
    except (ImportError, OSError):
        return None, False


def inspect_read_only(
    case: InspectionCase,
    *,
    semantic_dependencies: SemanticAccountingDependencies | None = None,
) -> dict[str, Any]:
    """Measure one fully exhausted pinned snapshot without writing to its DB."""
    _validate(case)
    if semantic_dependencies is not None:
        validate_semantic_accounting_dependencies(semantic_dependencies)
    cpu_start, total_start = time.process_time_ns(), _ns()
    tracemalloc.start()
    service = DeviceFingerprintReadService(case.db_path, retention_days=case.retention_days)
    registry = build_production_schema_registry()
    transaction_start = open_start = _ns()
    watermark_capture_ns = 0
    original_watermark_read = DeviceFingerprintRepository.read_ingest_watermark
    def timed_watermark(connection: Any) -> Any:
        nonlocal watermark_capture_ns
        start = _ns()
        try:
            return original_watermark_read(connection)
        finally:
            watermark_capture_ns += _ns() - start
    try:
        with patch.object(DeviceFingerprintRepository, "read_ingest_watermark", staticmethod(timed_watermark)):
            session = service.open_snapshot_read()
        open_timing = _duration(open_start)
        with session as snapshot:
            watermark = snapshot.watermark
            connection = snapshot._connection  # instrumentation of this exact read transaction
            if int(connection.execute("PRAGMA query_only").fetchone()[0]) != 1:
                raise RuntimeError("Snapshot connection is not query-only")
            if semantic_dependencies is None:
                applicable_epochs: list[dict[str, Any]] = []
                measurement_health_scopes = case.health_scopes
            else:
                applicable_epochs = applicable_binding_epochs(
                    semantic_dependencies, case.site_id, case.from_utc, case.to_utc,
                )
                measurement_health_scopes = validate_complete_health_scopes(
                    case.health_scopes, required_health_scopes(applicable_epochs),
                )
            query_plans = _plans(
                connection, case, watermark.max_committed_ingest_sequence,
                measurement_health_scopes,
            )
            database_summary = {
                "schema_version": int(connection.execute("PRAGMA user_version").fetchone()[0]),
                "evidence_rows_all_devices": _count_rows(connection, "device_fingerprint_evidence"),
                "health_rows_all_scopes": _count_rows(connection, "device_fingerprint_source_health_events"),
                "database_size_bytes": Path(case.db_path).stat().st_size,
            }
            evidence_pages = health_pages = evidence_count = health_count = 0
            verified_count = materialized_count = unsupported_count = 0
            verified_bytes = materialized_bytes = largest_payload = 0
            evidence_descriptor_bytes = health_descriptor_bytes = 0
            health_descriptors: dict[str, dict[str, Any]] = {}
            grouped: Counter[tuple[str, int, str]] = Counter()
            verify_ns = 0
            page_start = _ns()
            cursor = None
            while True:
                page = snapshot.list_evidence(
                    case.site_id, case.observed_mac, case.from_utc, case.to_utc,
                    limit=case.page_size, cursor=cursor,
                )
                evidence_pages += 1
                for row in page["items"]:
                    evidence_count += 1
                    grouped[(row["source_kind"], row["feature_schema_version"], row["quality_state"])] += 1
                    descriptor = {field: row[field] for field in _EVIDENCE_FIELDS}
                    if semantic_dependencies is not None:
                        descriptor, _epoch = authorized_descriptor(
                            row, _EVIDENCE_FIELDS, semantic_dependencies,
                        )
                    evidence_descriptor_bytes += len(canonical_artifact_json(descriptor))
                    verify_start = _ns()
                    verified = verify_persisted_payload(
                        row["source_kind"], row["feature_schema_version"],
                        row["payload_json"], row["payload_sha256"], registry,
                    )
                    verify_ns += _ns() - verify_start
                    verified_count += 1
                    verified_bytes += verified.verified_payload_bytes
                    largest_payload = max(largest_payload, verified.verified_payload_bytes)
                    materialized_bytes += verified.materialized_payload_bytes
                    if verified.schema_supported:
                        materialized_count += 1
                    else:
                        unsupported_count += 1
                cursor = page["next_cursor"]
                if cursor is None:
                    break
            evidence_timing = _duration(page_start)
            health_start = _ns()
            for producer, capture, kind in measurement_health_scopes:
                cursor = None
                while True:
                    page = snapshot.list_source_health(
                        case.site_id, producer, capture, kind, case.from_utc, case.to_utc,
                        limit=case.page_size, cursor=cursor,
                    )
                    health_pages += 1
                    for row in page["items"]:
                        descriptor = {field: row[field] for field in _HEALTH_FIELDS}
                        if semantic_dependencies is not None:
                            descriptor, _epoch = authorized_descriptor(
                                row, _HEALTH_FIELDS, semantic_dependencies,
                            )
                            existing = health_descriptors.get(row["source_health_id"])
                            if (existing is not None
                                    and canonical_artifact_json(existing)
                                    != canonical_artifact_json(descriptor)):
                                raise DeviceFingerprintValidationError(
                                    "Conflicting source-health descriptor identity"
                                )
                            health_descriptors[row["source_health_id"]] = descriptor
                        else:
                            health_count += 1
                            health_descriptor_bytes += len(canonical_artifact_json(descriptor))
                    cursor = page["next_cursor"]
                    if cursor is None:
                        break
                if semantic_dependencies is None:
                    snapshot.latest_source_health(
                        case.site_id, producer, capture, kind, through_utc=case.to_utc,
                    )
            if semantic_dependencies is not None:
                window_start = parse_utc(case.from_utc)
                for epoch in applicable_epochs:
                    epoch_start = parse_utc(epoch["effective_from_utc"])
                    segment_start = format_utc(max(window_start, epoch_start))
                    anchor = snapshot.latest_source_health(
                        case.site_id,
                        epoch["producer_id"],
                        epoch["capture_source_id"],
                        epoch["source_kind"],
                        through_utc=segment_start,
                    )
                    if anchor is None:
                        continue
                    descriptor = health_anchor_descriptor(
                        anchor,
                        _HEALTH_FIELDS,
                        epoch,
                        semantic_dependencies.binding_timeline,
                        semantic_dependencies.binding_clock_policy,
                    )
                    if descriptor is None:
                        continue
                    existing = health_descriptors.get(anchor["source_health_id"])
                    if (existing is not None
                            and canonical_artifact_json(existing)
                            != canonical_artifact_json(descriptor)):
                        raise DeviceFingerprintValidationError(
                            "Conflicting source-health descriptor identity"
                        )
                    health_descriptors[anchor["source_health_id"]] = descriptor
                health_count = len(health_descriptors)
                health_descriptor_bytes = sum(
                    len(canonical_artifact_json(descriptor))
                    for descriptor in health_descriptors.values()
                )
            health_timing = _duration(health_start)
        reader_timing = _duration(transaction_start)
    finally:
        _current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
    rss, rss_available = _rss()
    if semantic_dependencies is None:
        semantic_accounting = {
            "task01_evidence_descriptor_bytes": evidence_descriptor_bytes,
            "verified_payload_bytes": verified_bytes,
            "materialized_payload_bytes": materialized_bytes,
            "task01_health_descriptor_bytes": health_descriptor_bytes,
            "known_measurable_input_bytes": evidence_descriptor_bytes + verified_bytes
            + materialized_bytes + health_descriptor_bytes,
            "descriptor_scope": "task01_durable_fields_only_binding_epoch_pending",
            "final_binding_and_dependency_overhead_status": "PENDING_FOUNDATION_DEPENDENCIES",
        }
    else:
        binding_bytes, binding_count = binding_descriptor_bytes(applicable_epochs)
        dependency_bytes = semantic_dependency_reference_bytes(semantic_dependencies)
        semantic_accounting = complete_semantic_byte_accounting({
            "authorized_evidence_descriptor_bytes": evidence_descriptor_bytes,
            "verified_payload_bytes": verified_bytes,
            "materialized_payload_bytes": materialized_bytes,
            "authorized_health_descriptor_bytes": health_descriptor_bytes,
            "binding_descriptor_bytes": binding_bytes,
            "semantic_dependency_reference_bytes": dependency_bytes,
        })
        semantic_accounting.update({
            "binding_epoch_count": binding_count,
            "semantic_dependency_artifact_ids": {
                "evidence_source_binding_timeline": (
                    semantic_dependencies.binding_timeline.artifact_id
                ),
                "binding_clock_policy": semantic_dependencies.binding_clock_policy.artifact_id,
                "evidence_schema_registry_contract": (
                    semantic_dependencies.schema_registry_contract.artifact_id
                ),
                "ttl_capture_placement_proof": (
                    semantic_dependencies.ttl_capture_placement_proof.artifact_id
                ),
                "origin_runtime_admission": semantic_dependency_descriptor(
                    semantic_dependencies
                )["origin_runtime_admission"]["artifact_id"],
            },
            "origin_runtime_admission_status": "PRE_F_ADMIT_SIZING_ONLY",
        })
    report = {
        "report_schema_version": 1,
        "candidate_identity": {
            "repository_commit_sha": case.repository_commit_sha,
            "repository_tree_sha": case.repository_tree_sha,
        },
        "environment": {"python": platform.python_version(), "platform": platform.system(),
                        "sqlite_version": __import__("sqlite3").sqlite_version},
        "measurement_case": {"measurement_case_id": case.measurement_case_id,
                             "mode": "READ_ONLY_INSPECTION",
                             "window_duration_ms": (parse_utc(case.to_utc) - parse_utc(case.from_utc)) // timedelta(milliseconds=1),
                             "page_size": case.page_size},
        "database_summary": database_summary,
        "watermark_summary": {"database_generation_id": watermark.database_generation_id,
                              "max_committed_ingest_sequence": watermark.max_committed_ingest_sequence},
        "query_plans": query_plans,
        "cardinality": {"total_evidence_rows": evidence_count,
                        "total_relevant_health_rows": health_count,
                        "by_source_schema_quality": [
                            {"source_kind": kind, "feature_schema_version": version,
                             "quality_state": quality, "count": count}
                            for (kind, version, quality), count in sorted(grouped.items())
                        ], "largest_canonical_payload_bytes": largest_payload},
        "pagination": {"evidence_pages": evidence_pages, "health_pages": health_pages},
        "payload_accounting": {
            "verified_evidence_row_count": verified_count,
            "verified_payload_bytes": verified_bytes,
            "materialized_evidence_row_count": materialized_count,
            "materialized_payload_bytes": materialized_bytes,
            "unsupported_intact_row_count": unsupported_count,
        },
        "semantic_byte_accounting": semantic_accounting,
        "timing": {"open_snapshot_transaction": open_timing,
                   "watermark_capture": {"duration_ns": watermark_capture_ns,
                                         "duration_ms": watermark_capture_ns // 1_000_000},
                   "evidence_pagination_total": evidence_timing,
                   "health_pagination_total": health_timing,
                   "payload_verify_materialize_total": {"duration_ns": verify_ns,
                                                        "duration_ms": verify_ns // 1_000_000},
                   "reader_transaction_lifetime": reader_timing,
                   "complete_measurement": _duration(total_start)},
        "cpu_memory": {"process_cpu_duration_ns": time.process_time_ns() - cpu_start,
                       "python_peak_allocated_bytes": peak, "posix_maxrss": rss,
                       "posix_maxrss_available": rss_available},
        "wal_checkpoint": None, "writer_latency": None, "retention_latency": None,
        "privacy_audit": {"raw_identity_retained": False, "raw_payload_retained": False,
                          "report_contains_secrets": False},
        "result": "MEASUREMENT_COMPLETE",
    }
    return report


def report_json(report: dict[str, Any]) -> str:
    """Return a closed-schema, non-pretty machine-readable report."""
    expected = {
        "report_schema_version", "candidate_identity", "environment",
        "measurement_case", "database_summary", "watermark_summary",
        "query_plans", "cardinality", "pagination", "payload_accounting",
        "semantic_byte_accounting", "timing", "cpu_memory", "wal_checkpoint",
        "writer_latency", "retention_latency", "privacy_audit", "result",
    }
    if set(report) != expected or report["report_schema_version"] != 1:
        raise ValueError("Invalid F-A4-A report schema")
    if report["result"] not in {"MEASUREMENT_COMPLETE", "MEASUREMENT_FAILED"}:
        raise ValueError("Invalid F-A4-A result")
    return json.dumps(report, ensure_ascii=True, allow_nan=False, sort_keys=True,
                      separators=(",", ":"))


def write_report_file(report: dict[str, Any], path: str) -> None:
    """Retain one sanitized machine-readable measurement report."""
    target = Path(path)
    if target.suffix.lower() in {".db", ".sqlite", ".sqlite3"}:
        raise ValueError("Report output cannot be a database target")
    serialized = report_json(report)
    with target.open("x", encoding="utf-8", newline="") as handle:
        handle.write(serialized)


def failed_report(commit_sha: str, tree_sha: str, case_id: str, mode: str,
                  error_kind: str) -> dict[str, Any]:
    """Fail closed without retaining exception messages or sensitive inputs."""
    return {
        "report_schema_version": 1,
        "candidate_identity": {"repository_commit_sha": commit_sha,
                               "repository_tree_sha": tree_sha},
        "environment": {"python": platform.python_version(), "platform": platform.system(),
                        "sqlite_version": __import__("sqlite3").sqlite_version},
        "measurement_case": {"measurement_case_id": case_id, "mode": mode,
                             "failure_kind": error_kind},
        "database_summary": None, "watermark_summary": None,
        "query_plans": None, "cardinality": None, "pagination": None,
        "payload_accounting": None, "semantic_byte_accounting": None,
        "timing": None, "cpu_memory": None, "wal_checkpoint": None,
        "writer_latency": None, "retention_latency": None,
        "privacy_audit": {"raw_identity_retained": False,
                          "raw_payload_retained": False, "report_contains_secrets": False},
        "result": "MEASUREMENT_FAILED",
    }
