"""Deterministic F-B1-A topology, clock, and synthetic-cutover proofs."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.device_fingerprint.artifact_content import canonical_artifact_json
from app.device_fingerprint.artifact_content import canonical_set
from app.device_fingerprint.binding_contracts import (
    make_binding_clock_policy, make_evidence_source_binding_timeline,
    resolve_authoritative_binding, validate_binding_clock_pair,
)
from app.device_fingerprint.models import DeviceFingerprintValidationError
from app.device_fingerprint.repository import open_read_only
from app.device_fingerprint.source_health_emitter_contracts import build_source_health_emitter_contracts
from app.device_fingerprint.validation import parse_utc, validate_site_id

_TABLES = ("device_fingerprint_evidence", "device_fingerprint_source_health_events")
_TOPOLOGY_COLUMNS = frozenset({
    "site_id", "producer_id", "capture_source_id", "source_kind", "observed_at",
})
_SHA = re.compile(r"[0-9a-f]{40}")
_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


def _fail(message: str) -> None:
    raise DeviceFingerprintValidationError(message)


def _shape(value: Any, fields: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != fields:
        _fail(f"Invalid {label} shape")
    return value


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        _fail(f"Invalid {label}")
    return value


def _integer(value: Any, label: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum or value > 2**63 - 1:
        _fail(f"Invalid {label}")
    return value


def _milliseconds(value: str) -> int:
    delta = parse_utc(value) - _EPOCH
    return (delta.days * 86400 + delta.seconds) * 1000 + delta.microseconds // 1000


def inspect_task01_topology(db_path: str) -> dict[str, Any]:
    """Read only scope counts and time bounds from a supported Task-01 DB."""
    connection = open_read_only(db_path)
    try:
        if int(connection.execute("PRAGMA query_only").fetchone()[0]) != 1:
            _fail("Topology connection is not query-only")
        connection.execute("BEGIN")
        version = int(connection.execute("PRAGMA user_version").fetchone()[0])
        if version not in {1, 2}:
            _fail("Unsupported Task-01 topology schema version")
        tables = {row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )}
        if not set(_TABLES) <= tables:
            _fail("Task-01 topology table missing")
        combined: dict[tuple[str, str, str, str], dict[str, Any]] = {}
        for table in _TABLES:
            columns = {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}
            if not _TOPOLOGY_COLUMNS <= columns:
                _fail("Task-01 topology columns missing")
            rows = connection.execute(
                f"SELECT site_id,producer_id,capture_source_id,source_kind,"
                f"COUNT(*),MIN(observed_at),MAX(observed_at) FROM {table} "
                "GROUP BY site_id,producer_id,capture_source_id,source_kind"
            )
            for row in rows:
                key = tuple(row[:4])
                validate_site_id(key[0])
                for member in key[1:]:
                    _text(member, "topology scope")
                minimum, maximum = row[5], row[6]
                parse_utc(minimum)
                parse_utc(maximum)
                entry = combined.setdefault(key, {
                    "site_id": key[0], "producer_id": key[1],
                    "capture_source_id": key[2], "source_kind": key[3],
                    "evidence_row_count": 0, "source_health_row_count": 0,
                    "minimum_observed_at": minimum, "maximum_observed_at": maximum,
                })
                count_key = "evidence_row_count" if table == _TABLES[0] else "source_health_row_count"
                entry[count_key] = int(row[4])
                entry["minimum_observed_at"] = min(entry["minimum_observed_at"], minimum)
                entry["maximum_observed_at"] = max(entry["maximum_observed_at"], maximum)
        return {"task01_schema_version": version,
                "scope_count": len(combined),
                "scopes": [combined[key] for key in sorted(combined)]}
    finally:
        connection.close()


def measure_clock_offsets(proof_input: dict[str, Any]) -> dict[str, Any]:
    """Compute exact integer-millisecond producer↔Task-01 offsets from retained samples."""
    value = _shape(proof_input, {
        "measurement_method_id", "task01_clock_domain_id",
        "producer_clock_domains", "clock_samples",
    }, "clock proof")
    method = _text(value["measurement_method_id"], "measurement method")
    central = _text(value["task01_clock_domain_id"], "Task-01 clock domain")
    domains = value["producer_clock_domains"]
    samples = value["clock_samples"]
    if not isinstance(domains, list) or not domains or not isinstance(samples, list) or not samples:
        _fail("Clock proof needs domains and samples")
    declarations: set[tuple[str, str]] = set()
    for item in domains:
        _shape(item, {"clock_domain_id", "producer_id"}, "clock domain")
        domain = _text(item["clock_domain_id"], "clock domain ID")
        producer = _text(item["producer_id"], "clock producer ID")
        pair = (domain, producer)
        if pair in declarations:
            _fail("Duplicate clock domain declaration")
        declarations.add(pair)
    maxima: dict[str, int] = {}
    counts: dict[str, int] = {}
    for sample in samples:
        _shape(sample, {"producer_id", "clock_domain_id", "producer_time_utc",
                        "task01_time_utc"}, "clock sample")
        producer = _text(sample["producer_id"], "sample producer")
        domain = _text(sample["clock_domain_id"], "sample clock domain")
        if (domain, producer) not in declarations:
            _fail("Clock sample has undeclared producer domain")
        offset = abs(_milliseconds(sample["producer_time_utc"])
                     - _milliseconds(sample["task01_time_utc"]))
        maxima[producer] = max(maxima.get(producer, 0), offset)
        counts[producer] = counts.get(producer, 0) + 1
    if {producer for _domain, producer in declarations} != set(maxima):
        _fail("Every declared producer requires a clock sample")
    return {
        "measurement_method_id": method, "task01_clock_domain_id": central,
        "producer_clock_domains": canonical_set(domains, lambda row: row["clock_domain_id"]),
        "sample_count": len(samples),
        "per_producer_max_absolute_offset_ms": [
            {"producer_id": producer, "sample_count": counts[producer],
             "max_absolute_offset_ms": maxima[producer]}
            for producer in sorted(maxima)
        ],
        "overall_measured_max_relative_offset_ms": max(maxima.values()),
    }


def _verify_cutover_fixtures(timeline: Any, policy: Any,
                             fixtures: list[Any]) -> dict[str, Any]:
    if not isinstance(fixtures, list) or not fixtures:
        _fail("Cutover proof requires fixtures")
    results = []
    for fixture in fixtures:
        _shape(fixture, {"site_id", "origin_group", "source_kind", "cutover_utc",
                         "guard_seconds", "checks"}, "cutover fixture")
        site_id = validate_site_id(fixture["site_id"])
        origin = _text(fixture["origin_group"], "cutover origin")
        kind = _text(fixture["source_kind"], "cutover source kind")
        parse_utc(fixture["cutover_utc"])
        guard = _integer(fixture["guard_seconds"], "fixture guard")
        if guard != policy.semantic_payload["cutover_guard_seconds"]:
            _fail("Fixture guard differs from candidate policy")
        epochs = sorted((epoch for epoch in timeline.semantic_payload["binding_epochs"]
                         if (epoch["site_id"], epoch["origin_group"], epoch["source_kind"])
                         == (site_id, origin, kind)), key=lambda epoch: epoch["effective_from_utc"])
        if not any(a["effective_to_utc"] == b["effective_from_utc"] == fixture["cutover_utc"]
                   for a, b in zip(epochs, epochs[1:])):
            _fail("Fixture does not name an adjacent candidate cutover")
        checks = fixture["checks"]
        if not isinstance(checks, list) or not checks:
            _fail("Cutover fixture requires checks")
        tested = []
        for check in checks:
            _shape(check, {"observed_at", "expected_outcome"}, "cutover check")
            timestamp = parse_utc(check["observed_at"])
            expected = check["expected_outcome"]
            if not isinstance(expected, str) or expected not in {
                "AUTHORIZED", "NO_BINDING", "CUTOVER_AMBIGUOUS",
            }:
                _fail("Invalid expected cutover outcome")
            actual = resolve_authoritative_binding(
                timeline, policy, site_id, origin, kind, check["observed_at"]
            )["status"]
            tested.append({"observed_at": check["observed_at"],
                           "expected_outcome": expected, "actual_outcome": actual,
                           "pass": actual == expected})
        results.append({"cutover_utc": fixture["cutover_utc"],
                        "guard_seconds": guard, "tested_timestamps": tested,
                        "pass": all(check["pass"] for check in tested)})
    return {"fixture_count": len(results), "fixtures": results,
            "pass": all(fixture["pass"] for fixture in results)}


def run_candidate_proof(proof_input: dict[str, Any]) -> dict[str, Any]:
    """Build only candidate artifacts; retain sanitized deterministic F-B1-A evidence."""
    value = _shape(proof_input, {
        "repository_commit_sha", "repository_tree_sha", "task01_db_path",
        "clock_proof_input", "candidate_timeline_payload",
        "candidate_clock_policy_payload", "cutover_fixtures",
    }, "F-B1-A proof input")
    for field in ("repository_commit_sha", "repository_tree_sha"):
        if not isinstance(value[field], str) or _SHA.fullmatch(value[field]) is None:
            _fail("Invalid repository identity")
    topology = inspect_task01_topology(_text(value["task01_db_path"], "Task-01 DB path"))
    clock = measure_clock_offsets(value["clock_proof_input"])
    timeline = make_evidence_source_binding_timeline(
        value["candidate_timeline_payload"], build_source_health_emitter_contracts()
    )
    policy = make_binding_clock_policy(value["candidate_clock_policy_payload"])
    validate_binding_clock_pair(timeline, policy)
    policy_payload = policy.semantic_payload
    if (policy_payload["measurement_method_id"] != clock["measurement_method_id"]
            or policy_payload["task01_clock_domain_id"] != clock["task01_clock_domain_id"]
            or policy_payload["producer_clock_domains"] != clock["producer_clock_domains"]
            or policy_payload["measured_max_relative_clock_offset_ms"]
            != clock["overall_measured_max_relative_offset_ms"]):
        _fail("Candidate clock policy does not match measured proof")
    cutovers = _verify_cutover_fixtures(timeline, policy, value["cutover_fixtures"])
    return {
        "result": "PROOF_COMPLETE" if cutovers["pass"] else "PROOF_FAILED",
        "repository_commit_sha": value["repository_commit_sha"],
        "repository_tree_sha": value["repository_tree_sha"],
        "topology_summary": topology, "clock_measurement_summary": clock,
        "candidate_timeline_artifact": {
            "artifact_id": timeline.artifact_id, "content_sha256": timeline.content_sha256,
        },
        "candidate_clock_policy_artifact": {
            "artifact_id": policy.artifact_id, "content_sha256": policy.content_sha256,
        },
        "cutover_fixture_summary": cutovers,
        "authority_overlap_check": True, "emitter_reference_check": True,
        "mac_registry_absent": True, "raw_payload_retained": False,
        "raw_device_identity_retained": False,
        "classification_foundation_valid_from_status": "NOT_FROZEN_F_B1_A",
    }


def report_json(report: dict[str, Any]) -> str:
    """Closed, deterministic report serialization without input path or payloads."""
    _shape(report, {
        "result", "repository_commit_sha", "repository_tree_sha", "topology_summary",
        "clock_measurement_summary", "candidate_timeline_artifact",
        "candidate_clock_policy_artifact", "cutover_fixture_summary",
        "authority_overlap_check", "emitter_reference_check", "mac_registry_absent",
        "raw_payload_retained", "raw_device_identity_retained",
        "classification_foundation_valid_from_status",
    }, "F-B1-A report")
    if report["result"] not in {"PROOF_COMPLETE", "PROOF_FAILED"}:
        _fail("Invalid F-B1-A result")
    for field in ("repository_commit_sha", "repository_tree_sha"):
        if not isinstance(report[field], str) or _SHA.fullmatch(report[field]) is None:
            _fail("Invalid F-B1-A repository identity")
    topology = _shape(report["topology_summary"], {
        "task01_schema_version", "scope_count", "scopes",
    }, "topology summary")
    if (type(topology["task01_schema_version"]) is not int
            or topology["task01_schema_version"] not in {1, 2}
            or not isinstance(topology["scopes"], list)):
        _fail("Invalid topology summary")
    _integer(topology["scope_count"], "topology scope count")
    if topology["scope_count"] != len(topology["scopes"]):
        _fail("Invalid topology scope count")
    for scope in topology["scopes"]:
        _shape(scope, {"site_id", "producer_id", "capture_source_id", "source_kind",
                       "evidence_row_count", "source_health_row_count",
                       "minimum_observed_at", "maximum_observed_at"}, "topology scope")
        validate_site_id(scope["site_id"])
        for field in ("producer_id", "capture_source_id", "source_kind"):
            _text(scope[field], field)
        for field in ("evidence_row_count", "source_health_row_count"):
            _integer(scope[field], field)
        if parse_utc(scope["minimum_observed_at"]) > parse_utc(scope["maximum_observed_at"]):
            _fail("Invalid topology timestamp bounds")
    clock = _shape(report["clock_measurement_summary"], {
        "measurement_method_id", "task01_clock_domain_id", "producer_clock_domains",
        "sample_count", "per_producer_max_absolute_offset_ms",
        "overall_measured_max_relative_offset_ms",
    }, "clock summary")
    _text(clock["measurement_method_id"], "measurement method")
    _text(clock["task01_clock_domain_id"], "Task-01 clock domain")
    _integer(clock["sample_count"], "clock sample count", 1)
    _integer(clock["overall_measured_max_relative_offset_ms"], "clock offset")
    if not isinstance(clock["producer_clock_domains"], list) or not isinstance(
        clock["per_producer_max_absolute_offset_ms"], list
    ):
        _fail("Invalid clock summary lists")
    for domain in clock["producer_clock_domains"]:
        _shape(domain, {"clock_domain_id", "producer_id"}, "report clock domain")
        _text(domain["clock_domain_id"], "clock domain ID")
        _text(domain["producer_id"], "clock producer ID")
    for entry in clock["per_producer_max_absolute_offset_ms"]:
        _shape(entry, {"producer_id", "sample_count", "max_absolute_offset_ms"},
               "report producer offset")
        _text(entry["producer_id"], "clock producer ID")
        _integer(entry["sample_count"], "producer sample count", 1)
        _integer(entry["max_absolute_offset_ms"], "producer offset")
    for name in ("candidate_timeline_artifact", "candidate_clock_policy_artifact"):
        _shape(report[name], {"artifact_id", "content_sha256"}, name)
        _text(report[name]["artifact_id"], "artifact ID")
        _text(report[name]["content_sha256"], "artifact digest")
    cutovers = _shape(report["cutover_fixture_summary"], {
        "fixture_count", "fixtures", "pass",
    }, "cutover summary")
    _integer(cutovers["fixture_count"], "cutover fixture count", 1)
    if not isinstance(cutovers["fixtures"], list) or cutovers["fixture_count"] != len(cutovers["fixtures"]):
        _fail("Invalid cutover fixture count")
    if type(cutovers["pass"]) is not bool:
        _fail("Invalid cutover proof status")
    for fixture in cutovers["fixtures"]:
        _shape(fixture, {"cutover_utc", "guard_seconds", "tested_timestamps", "pass"},
               "report cutover fixture")
        parse_utc(fixture["cutover_utc"])
        _integer(fixture["guard_seconds"], "cutover guard")
        if not isinstance(fixture["tested_timestamps"], list) or type(fixture["pass"]) is not bool:
            _fail("Invalid cutover fixture checks")
        for check in fixture["tested_timestamps"]:
            _shape(check, {"observed_at", "expected_outcome", "actual_outcome", "pass"},
                   "report cutover check")
            parse_utc(check["observed_at"])
            if (not isinstance(check["expected_outcome"], str)
                    or check["expected_outcome"] not in {"AUTHORIZED", "NO_BINDING", "CUTOVER_AMBIGUOUS"}
                    or not isinstance(check["actual_outcome"], str)
                    or check["actual_outcome"] not in {"AUTHORIZED", "NO_BINDING", "CUTOVER_AMBIGUOUS"}
                    or type(check["pass"]) is not bool):
                _fail("Invalid cutover outcome")
    for name in ("authority_overlap_check", "emitter_reference_check", "mac_registry_absent"):
        if report[name] is not True:
            _fail("Invalid authority proof")
    if (report["raw_payload_retained"] is not False
            or report["raw_device_identity_retained"] is not False
            or report["classification_foundation_valid_from_status"] != "NOT_FROZEN_F_B1_A"):
        _fail("Invalid F-B1-A safety boundary")
    encoded = canonical_artifact_json(report)
    return encoded.decode("utf-8")


def write_report_file(report: dict[str, Any], path: str) -> None:
    target = Path(path)
    if target.suffix.lower() in {".db", ".sqlite", ".sqlite3"}:
        _fail("Report output cannot be a database")
    with target.open("x", encoding="utf-8", newline="") as handle:
        handle.write(report_json(report))
