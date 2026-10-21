"""External R14 T-02 formal harness. CLI execution is Owner/TechLead-only.

Importing this file has no repository, database, network or gate side effects.
The accepted T-01 R2 read-only/immutability implementation is hash-pinned.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib
import importlib.util
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import uuid
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any


sys.dont_write_bytecode = True
EXPECTED_COMMIT = "b3c6a63c044ca35e5996669596dc17eebfba9c92"
EXPECTED_TREE = "3d2588b9b50cc43ec2841997b1f9f08afdfac60a"
PROCEDURE = "T-02-source-evaluability-execution-v1"
GATE_CONTRACT = "R14-T-02-v1"
T01_HELPER_SHA256 = "3f1e6fa01cfd47b4225b8411a7e0627d609d9bbb4ae1f02b2fe5d0a3efcce9fe"
T01_HELPER = Path(__file__).resolve().parents[1] / "t01" / "task04-t01-gate-r1.py"
CASE_IDS = tuple(f"T02-M{number:02d}" for number in range(1, 13))
MAC = "AA:BB:CC:DD:EE:FF"  # Disposable input only; never written into retained evidence.
_HELPER = None


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _runner_intact(path: Path, digest: str) -> bool:
    try:
        return (_sha256(path) == digest and _sha256(T01_HELPER) == T01_HELPER_SHA256)
    except OSError:
        return False


def _t01():
    global _HELPER
    if not T01_HELPER.is_file() or _sha256(T01_HELPER) != T01_HELPER_SHA256:
        raise RuntimeError("BLOCKED_HARDENED_HELPER_CHANGED")
    if _HELPER is not None:
        return _HELPER
    spec = importlib.util.spec_from_file_location("task04_t01_hardened_helper", T01_HELPER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    _HELPER = module
    return _HELPER


def _ref(content: Any) -> dict[str, str]:
    return {"artifact_id": content.artifact_id, "content_sha256": content.content_sha256}


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=True, allow_nan=False, sort_keys=True,
                       separators=(",", ":")) + "\n").encode("utf-8")


def _document(content: Any) -> dict[str, Any]:
    return {"artifact_type": content.artifact_type,
            "artifact_schema_version": content.artifact_schema_version,
            "artifact_id": content.artifact_id,
            "content_sha256": content.content_sha256,
            "semantic_payload": content.semantic_payload}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def load_api(repo: Path) -> SimpleNamespace:
    helper = _t01()
    base = helper.load_repository_modules(repo)
    source = importlib.import_module("app.device_fingerprint.source_evaluability")
    snapshot_artifacts = importlib.import_module("app.device_fingerprint.snapshot_artifacts")
    health_policy = importlib.import_module("app.device_fingerprint.source_health_policy")
    binding = importlib.import_module("app.device_fingerprint.binding_contracts")
    for module in (source, snapshot_artifacts, health_policy, binding):
        if not Path(module.__file__).resolve().is_relative_to(repo.resolve()):
            raise helper.Blocked("BLOCKED_CANDIDATE_IDENTITY")
    return SimpleNamespace(**vars(base), source=source, snapshot_artifacts=snapshot_artifacts,
                           health_policy=health_policy, binding=binding, repo=repo.resolve())


def resolve_pinned(connection: sqlite3.Connection, api: SimpleNamespace,
                   lineage: Any) -> tuple[dict[str, Any], Any]:
    helper = _t01()
    fields = {
        "source_health_policy": "SourceHealthPolicy",
        "evidence_source_binding_timeline": (
            "EvidenceSourceBindingTimeline"),
        "binding_clock_policy": "BindingClockPolicy",
    }
    resolved = {}
    try:
        for field, kind in fields.items():
            reference = lineage.profile.semantic_payload[field]
            content = helper._resolve_artifact(connection, api, reference)
            if content.artifact_type != kind or _ref(content) != reference:
                raise ValueError("Pinned Foundation dependency mismatch")
            resolved[field] = content
        timeline = resolved["evidence_source_binding_timeline"]
        emitter_refs = {json.dumps(epoch["source_health_emitter_contract"], sort_keys=True)
                        for epoch in timeline.semantic_payload["binding_epochs"]}
        emitters = [helper._resolve_artifact(connection, api, json.loads(ref))
                    for ref in sorted(emitter_refs)]
        policy_emitters = [helper._resolve_artifact(connection, api, ref)
                           for ref in resolved["source_health_policy"].semantic_payload[
                               "accepted_source_health_emitter_contracts"]]
        if api.health_policy.make_source_health_policy(
                resolved["source_health_policy"].semantic_payload, policy_emitters) != resolved[
                    "source_health_policy"]:
            raise ValueError("Noncanonical SourceHealthPolicy")
        if api.binding.make_evidence_source_binding_timeline(
                timeline.semantic_payload, emitters) != timeline:
            raise ValueError("Noncanonical binding timeline")
        if api.binding.make_binding_clock_policy(
                resolved["binding_clock_policy"].semantic_payload) != resolved[
                    "binding_clock_policy"]:
            raise ValueError("Noncanonical BindingClockPolicy")
        api.binding.validate_binding_clock_pair(timeline, resolved["binding_clock_policy"])
        def resolver(reference):
            content = helper._resolve_artifact(connection, api, reference.as_dict())
            reference.resolve(content, content.artifact_type)
            return content
        api.source.DeviceFingerprintSourceEvaluabilityBuilder(
            foundation_runtime_profile=lineage.profile, artifact_resolver=resolver)
        return resolved, resolver
    except Exception as exc:
        raise helper.Blocked("BLOCKED_FOUNDATION_LINEAGE") from exc


def execute_pytest(repo: Path, run_dir: Path) -> tuple[int, str, str]:
    with tempfile.TemporaryDirectory(prefix="t02-pytest-", dir=run_dir) as temporary:
        temporary_path = Path(temporary)
        process_temp = temporary_path / "process-temp"
        process_temp.mkdir()
        command = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
                   "--basetemp", str(temporary_path / "pytest-temp"),
                   "tests/device_fingerprint_task04_t02"]
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(repo) + os.pathsep + environment.get("PYTHONPATH", "")
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        environment["PYTEST_ADDOPTS"] = ""
        for name in ("TEMP", "TMP", "TMPDIR"):
            environment[name] = str(process_temp)
        try:
            result = subprocess.run(command, cwd=repo, env=environment,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    text=True, encoding="utf-8", errors="replace", timeout=1800)
            return result.returncode, result.stdout, subprocess.list2cmdline(command)
        except (OSError, subprocess.SubprocessError) as exc:
            return 1, f"T-02 pytest execution error: {type(exc).__name__}\n", subprocess.list2cmdline(command)


def _health_row(epoch: dict, observed: str, number: int, status: str,
                reason: str | None, ingested: str) -> dict[str, Any]:
    return {
        "source_health_id": str(uuid.UUID(int=500_000 + number, version=4)),
        "source_health_event_id": str(uuid.UUID(int=600_000 + number, version=4)),
        "ingest_sequence": 10_000 + number, "producer_id": epoch["producer_id"],
        "source_kind": epoch["source_kind"], "capture_source_id": epoch["capture_source_id"],
        "site_id": epoch["site_id"], "status": status, "reason_code": reason,
        "observed_at": observed, "ingested_at": ingested, "content_sha256": "a" * 64,
    }


def _insert_rows(api: SimpleNamespace, path: Path, evidence: list[dict],
                 health: list[dict]) -> None:
    store = api.repository.DeviceFingerprintRepository(path, max_db_bytes=67_108_864)
    store.initialize()
    store.close()
    with sqlite3.connect(path) as connection:
        for table, rows in (("device_fingerprint_evidence", evidence),
                            ("device_fingerprint_source_health_events", health)):
            for row in rows:
                columns = tuple(row)
                connection.execute(
                    f"INSERT INTO {table} (" + ",".join(columns) + ") VALUES ("
                    + ",".join("?" for _ in columns) + ")",
                    tuple(row[column] for column in columns))
        connection.execute(
            "UPDATE device_fingerprint_storage_state SET database_generation_id=?, "
            "last_ingest_sequence=? WHERE singleton_id=1",
            ("11111111-1111-4111-8111-111111111111",
             max((row["ingest_sequence"] for row in evidence + health), default=0)))


def _fixture_window(api: SimpleNamespace, profile: Any, timeline: Any,
                    clock: Any) -> tuple[dict, str, str, str]:
    valid_from = api.validation.parse_utc(profile.semantic_payload[
        "classification_foundation_valid_from_utc"])
    guard = clock.semantic_payload["cutover_guard_seconds"]
    for epoch in timeline.semantic_payload["binding_epochs"]:
        if epoch["origin_group"] != "dhcp" or epoch["source_kind"] != "dhcp":
            continue
        start = max(valid_from, api.validation.parse_utc(epoch["effective_from_utc"]))
        start += timedelta(seconds=guard + 3600)
        end = start + timedelta(minutes=20)
        if epoch["effective_to_utc"] is None or end < api.validation.parse_utc(
                epoch["effective_to_utc"]):
            return epoch, api.validation.format_utc(start), api.validation.format_utc(end), (
                api.validation.format_utc(start + timedelta(minutes=1)))
    raise RuntimeError("No disposable authorized DHCP window in pinned binding timeline")


def _entry(content: Any, epoch_id: str) -> dict:
    return next(row for row in content.semantic_payload["source_entries"]
                if row["binding_epoch_id"] == epoch_id)


def _controlled_cutover_context(api: SimpleNamespace):
    """Load only the exact candidate's existing disposable cutover fixture."""
    module = importlib.import_module(
        "tests.device_fingerprint_task04_t01.test_snapshot_service")
    source = Path(module.__file__).resolve(strict=True)
    if not source.is_relative_to(api.repo.resolve(strict=True)):
        raise _t01().Blocked("BLOCKED_CANDIDATE_IDENTITY")
    return module.context(), source.relative_to(api.repo.resolve()).as_posix()


def execute_matrix(run_dir: Path, api: SimpleNamespace, profile: Any,
                   pinned: dict[str, Any], resolver: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    """Retain real Task-01 -> T-01 -> T-02 artifacts from disposable databases."""
    with tempfile.TemporaryDirectory(prefix="t02-matrix-", dir=run_dir) as temporary:
        return _execute_matrix(Path(temporary), api, profile, pinned, resolver)


def _execute_matrix(directory: Path, api: SimpleNamespace, profile: Any,
                    pinned: dict[str, Any], resolver: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    timeline = pinned["evidence_source_binding_timeline"]
    clock = pinned["binding_clock_policy"]
    health_policy = pinned["source_health_policy"]
    epoch, start, end, observed = _fixture_window(api, profile, timeline, clock)
    ingested = api.validation.format_utc(api.validation.parse_utc(end) + timedelta(days=1))
    captured = api.validation.format_utc(api.validation.parse_utc(end) + timedelta(days=2))
    case_records: dict[str, dict] = {}
    retained: dict[str, dict] = {}
    traces: dict[str, Any] = {}
    builder = api.source.DeviceFingerprintSourceEvaluabilityBuilder(
        foundation_runtime_profile=profile, artifact_resolver=resolver)

    def capture(case_id: str, health: list[dict], evidence: list[dict],
                verify, *, window_start=start, window_end=end, fixture_profile=None,
                fixture_epoch=None, fixture_resolver=None, fixture_builder=None,
                fixture_health_policy=None, fixture_captured=None):
        selected_profile = fixture_profile or profile
        selected_epoch = fixture_epoch or epoch
        selected_resolver = fixture_resolver or resolver
        selected_builder = fixture_builder or builder
        selected_health_policy = fixture_health_policy or health_policy
        selected_captured = fixture_captured or captured
        fixture_digest = hashlib.sha256(_json_bytes({"health": health, "evidence": evidence,
            "window_start": window_start, "window_end": window_end,
            "foundation_runtime_profile": _ref(selected_profile)})).hexdigest()
        case_dir = directory / case_id
        case_dir.mkdir()
        path = case_dir / "task01-disposable.sqlite"
        try:
            _insert_rows(api, path, evidence, health)
            reader = api.read.DeviceFingerprintReadService(str(path), retention_days=30)
            service = api.snapshot.DeviceFingerprintSnapshotService(
                reader, foundation_runtime_profile=selected_profile,
                artifact_resolver=selected_resolver,
                utc_clock=lambda: selected_captured,
                process_memory_guard=lambda _limit: True)
            snapshot = service.build(selected_epoch["site_id"], MAC, window_start,
                                     window_end).evidence_snapshot_content
            output = selected_builder.build(snapshot)
            snapshot_document = json.loads(api.artifact.canonical_artifact_json(
                _document(snapshot)))
            output_document = json.loads(api.artifact.canonical_artifact_json(
                _document(output)))
            rebuilt = api.source.make_source_evaluability(
                output_document["semantic_payload"], evidence_snapshot_content=snapshot,
                source_health_policy=selected_health_policy)
            _require(rebuilt == output and _document(rebuilt) == output_document,
                     "T-02 artifact round-trip mismatch")
            _require(output.semantic_payload["evidence_snapshot_content"] == _ref(snapshot),
                     "T-02 snapshot ref mismatch")
            _require(output.semantic_payload["source_health_policy"] == _ref(selected_health_policy),
                     "T-02 health-policy ref mismatch")
            _require(set(output.semantic_payload) == {"source_evaluability_contract_version",
                "evidence_snapshot_content", "source_health_policy", "source_entries"},
                "T-02 extra semantic field")
            verify(snapshot, output)
            case_records[case_id] = {"status": "PASS", "input_fixture_sha256": fixture_digest,
                "evidence_snapshot_content": _ref(snapshot), "source_evaluability": _ref(output),
                "source_entries": [{"binding_epoch_id": row["binding_epoch_id"],
                    "aggregate_evaluability_state": row["aggregate_evaluability_state"],
                    "coverage_intervals": row["coverage_intervals"]}
                    for row in output.semantic_payload["source_entries"]]}
            for content in (snapshot, output):
                retained[content.artifact_id] = (snapshot_document if content is snapshot
                                                  else output_document)
            return snapshot, output
        except Exception as exc:
            case_records[case_id] = {"status": "FAIL", "input_fixture_sha256": fixture_digest,
                                     "observed_failure_type": type(exc).__name__}
            return None

    def check(expected_coverage, expected_reason, expected_aggregate):
        def verify(_snapshot, output):
            row = _entry(output, epoch["binding_epoch_id"])
            interval = row["coverage_intervals"][0]
            _require((interval["coverage_class"], interval["reason_classification"],
                      row["aggregate_evaluability_state"]) ==
                     (expected_coverage, expected_reason, expected_aggregate),
                     "T-02 disposition mismatch")
        return verify

    def health_at(status, reason=None, number=1, when=observed):
        return _health_row(epoch, when, number, status, reason, ingested)

    # Cases M01-M05 select a one-minute interval beginning at the health event.
    one_minute = api.validation.format_utc(api.validation.parse_utc(observed) + timedelta(minutes=1))
    cases = [
        ("T02-M01", [health_at("available")], [],
         check("covered_available", "HEALTH_AVAILABLE", "evaluable")),
        ("T02-M02", [health_at("unavailable", "capture_interface_unavailable")], [],
         check("acquisition_unavailable", "ACQUISITION_UNAVAILABLE", "not_evaluable")),
        ("T02-M03", [health_at("unavailable", "ingest_delivery_unavailable")], [],
         check("delivery_unavailable_loss_possible", "DELIVERY_UNAVAILABLE_LOSS_POSSIBLE", "unknown")),
        ("T02-M04", [health_at("unsupported")], [],
         check("unsupported", "SOURCE_UNSUPPORTED", "not_evaluable")),
        ("T02-M05", [], [], check("unknown", "HEALTH_UNKNOWN", "unknown")),
    ]
    for case_id, health, evidence, verify in cases:
        capture(case_id, health, evidence, verify,
                window_start=observed, window_end=one_minute)

    def verify_freshness(_snapshot, output):
        intervals = _entry(output, epoch["binding_epoch_id"])["coverage_intervals"]
        timeout = next(rule["freshness"]["freshness_timeout_ms"]
                       for rule in health_policy.semantic_payload["emitter_source_family_rules"]
                       if rule["source_health_emitter_contract"] == epoch[
                           "source_health_emitter_contract"] and rule["source_kind"] == "dhcp")
        boundary = api.validation.parse_utc(observed) + timedelta(milliseconds=timeout)
        first_stale = api.validation.format_utc(boundary + timedelta(milliseconds=1))
        _require(any(row["coverage_class"] == "covered_available"
                     and row["start_utc"] <= api.validation.format_utc(boundary) < row["end_utc"]
                     for row in intervals), "Freshness exact boundary not covered")
        _require(any(row["reason_classification"] == "HEARTBEAT_STALE"
                     and row["start_utc"] == first_stale for row in intervals),
                 "Freshness +1ms boundary not stale")
        traces["freshness"] = {"timeout_ms": timeout,
                               "at_timeout": api.validation.format_utc(boundary),
                               "first_stale": first_stale}

    capture("T02-M06", [health_at("available")], [], verify_freshness,
            window_start=observed, window_end=end)

    def verify_cutover(snapshot, output):
        rows = output.semantic_payload["source_entries"]
        descriptors = snapshot.semantic_payload["binding_epoch_descriptors"]
        _require(len(descriptors) >= 2 and {old_epoch["binding_epoch_id"],
                 new_epoch["binding_epoch_id"]}.issubset(
                     {item["binding_epoch_id"] for item in descriptors}),
                 "Cutover snapshot does not intersect both binding epochs")
        _require(old_epoch["binding_epoch_id"] != new_epoch["binding_epoch_id"],
                 "Old/new binding identity collapsed")
        old = _entry(output, old_epoch["binding_epoch_id"])
        new = _entry(output, new_epoch["binding_epoch_id"])
        lower = api.validation.format_utc(cutover - timedelta(seconds=guard))
        upper = api.validation.format_utc(cutover + timedelta(seconds=guard))
        _require(any(interval["reason_classification"] == "BINDING_CUTOVER_UNKNOWN"
                     and interval["start_utc"] >= lower
                     for interval in old["coverage_intervals"]),
                 "Old-side cutover quarantine missing")
        _require(any(interval["reason_classification"] == "BINDING_CUTOVER_UNKNOWN"
                     and interval["end_utc"] <= upper
                     for interval in new["coverage_intervals"]),
                 "New-side cutover quarantine missing")
        _require(any(interval["coverage_class"] == "covered_available"
                     and interval["start_utc"] < lower
                     for interval in old["coverage_intervals"]),
                 "Pre-quarantine old epoch lost valid health")
        _require(any(interval["reason_classification"] == "HEALTH_UNKNOWN"
                     and interval["start_utc"] >= upper
                     for interval in new["coverage_intervals"]),
                 "Old health inherited into new epoch after quarantine")
        traces["cutover"] = [{"epoch": row["binding_epoch_id"],
                               "intervals": row["coverage_intervals"]} for row in (old, new)]

    peers = [item for item in timeline.semantic_payload["binding_epochs"]
             if (item["site_id"], item["origin_group"], item["source_kind"]) ==
             (epoch["site_id"], epoch["origin_group"], epoch["source_kind"])]
    peers.sort(key=lambda item: item["effective_from_utc"])
    admitted_valid_from = api.validation.parse_utc(profile.semantic_payload[
        "classification_foundation_valid_from_utc"])
    admitted_guard = clock.semantic_payload["cutover_guard_seconds"]
    pair = next(((a, b) for a, b in zip(peers, peers[1:])
                 if a["effective_to_utc"] == b["effective_from_utc"]
                 and api.validation.parse_utc(b["effective_from_utc"])
                     - timedelta(seconds=admitted_guard + 60) >= admitted_valid_from
                 and api.validation.parse_utc(a["effective_from_utc"])
                     <= api.validation.parse_utc(b["effective_from_utc"])
                     - timedelta(seconds=admitted_guard + 60)
                 and (b["effective_to_utc"] is None
                      or api.validation.parse_utc(b["effective_to_utc"])
                         >= api.validation.parse_utc(b["effective_from_utc"])
                         + timedelta(seconds=admitted_guard + 60))), None)
    fixture_profile = profile
    fixture_timeline = timeline
    fixture_clock = clock
    fixture_health_policy = health_policy
    fixture_resolver = resolver
    fixture_source = None
    fixture_mode = "ADMITTED_FOUNDATION_CUTOVER"
    if pair is None:
        controlled, fixture_source = _controlled_cutover_context(api)
        fixture_mode = "CONTROLLED_CANDIDATE_CUTOVER_FIXTURE"
        fixture_profile = controlled.profile
        fixture_resolver = lambda reference: controlled.contents[reference.artifact_id]
        fixture_timeline = fixture_resolver(api.artifact.ArtifactRef.from_dict(
            fixture_profile.semantic_payload["evidence_source_binding_timeline"]))
        fixture_clock = fixture_resolver(api.artifact.ArtifactRef.from_dict(
            fixture_profile.semantic_payload["binding_clock_policy"]))
        fixture_health_policy = fixture_resolver(api.artifact.ArtifactRef.from_dict(
            fixture_profile.semantic_payload["source_health_policy"]))
        controlled_peers = [item for item in fixture_timeline.semantic_payload["binding_epochs"]
                            if item["origin_group"] == "dhcp" and item["source_kind"] == "dhcp"]
        controlled_peers.sort(key=lambda item: item["effective_from_utc"])
        pair = next(((a, b) for a, b in zip(controlled_peers, controlled_peers[1:])
                     if a["site_id"] == b["site_id"] and
                     a["effective_to_utc"] == b["effective_from_utc"]), None)
    if pair is None:
        case_records["T02-M07"] = {"status": "FAIL", "input_fixture_sha256":
            hashlib.sha256(b"candidate-controlled-cutover-unavailable").hexdigest(),
            "observed_failure_type": "ControlledCutoverFixtureUnavailable",
            "fixture_mode": fixture_mode}
    else:
        old_epoch, new_epoch = pair
        cutover = api.validation.parse_utc(new_epoch["effective_from_utc"])
        guard = fixture_clock.semantic_payload["cutover_guard_seconds"]
        cutover_start = api.validation.format_utc(cutover - timedelta(seconds=guard + 60))
        cutover_end = api.validation.format_utc(cutover + timedelta(seconds=guard + 60))
        cutover_ingested = api.validation.format_utc(
            api.validation.parse_utc(cutover_end) + timedelta(days=1))
        cutover_captured = api.validation.format_utc(
            api.validation.parse_utc(cutover_end) + timedelta(days=2))
        old_health = _health_row(old_epoch, cutover_start, 70, "available", None,
                                 cutover_ingested)
        controlled_builder = api.source.DeviceFingerprintSourceEvaluabilityBuilder(
            foundation_runtime_profile=fixture_profile, artifact_resolver=fixture_resolver)
        capture("T02-M07", [old_health], [], verify_cutover,
                window_start=cutover_start, window_end=cutover_end,
                fixture_profile=fixture_profile, fixture_epoch=old_epoch,
                fixture_resolver=fixture_resolver, fixture_builder=controlled_builder,
                fixture_health_policy=fixture_health_policy,
                fixture_captured=cutover_captured)
        case_records["T02-M07"].update({
            "fixture_mode": fixture_mode,
            "fixture_source_module_relative_path": fixture_source,
            "fixture_foundation_runtime_profile": _ref(fixture_profile),
            "fixture_evidence_source_binding_timeline": _ref(fixture_timeline),
            "fixture_binding_clock_policy": _ref(fixture_clock),
            "fixture_source_health_policy": _ref(fixture_health_policy),
            "old_binding_epoch_id": old_epoch["binding_epoch_id"],
            "new_binding_epoch_id": new_epoch["binding_epoch_id"],
            "cutover_timestamp_utc": api.validation.format_utc(cutover),
            "cutover_guard_seconds": guard,
        })

    helper = _t01()
    present = helper._fixture_row(api, epoch, observed, ingested, 1)
    present_cases = (
        ("acquisition", "unavailable", "capture_interface_unavailable",
         "acquisition_unavailable", "HEALTH_EVIDENCE_INCONSISTENCY"),
        ("unsupported", "unsupported", None,
         "unsupported", "UNSUPPORTED_BUT_EVIDENCE_PRESENT"),
        ("delivery", "unavailable", "ingest_delivery_unavailable",
         "delivery_unavailable_loss_possible", "DELIVERY_UNAVAILABLE_LOSS_POSSIBLE"),
    )
    present_results = {}
    for label, status, reason, coverage, explanation in present_cases:
        def verify_present(snapshot, output, expected_coverage=coverage,
                           expected_reason=explanation):
            _require(len(snapshot.semantic_payload["evidence_descriptors"]) == 1,
                     "Present evidence not retained")
            rows = _entry(output, epoch["binding_epoch_id"])["coverage_intervals"]
            _require(any(row["coverage_class"] == expected_coverage and
                         row["reason_classification"] == expected_reason for row in rows),
                     "Present evidence disposition mismatch")
        subcase = f"T02-M08-{label}"
        capture(subcase, [health_at(status, reason)], [present], verify_present,
                window_start=observed, window_end=one_minute)
        present_results[label] = case_records.pop(subcase)
    case_records["T02-M08"] = {
        "status": "PASS" if all(item["status"] == "PASS"
                                for item in present_results.values()) else "FAIL",
        "input_fixture_sha256": hashlib.sha256(_json_bytes({
            label: item["input_fixture_sha256"] for label, item in present_results.items()})).hexdigest(),
        "present_evidence_subcases": present_results}
    traces["present_evidence"] = {
        label: {"coverage": coverage, "reason": explanation} for label, _, _, coverage,
        explanation in present_cases}

    def verify_order(_snapshot, output):
        row = _entry(output, epoch["binding_epoch_id"])
        _require(row["explanation_codes"] == sorted(row["explanation_codes"]),
                 "Reason codes not SET ordered")
        _require(row["coverage_intervals"][0]["reason_code_refs"] == [
            "capture_interface_unavailable", "raw_parser_unavailable"],
            "Reason-code union not canonically SET ordered")
        traces["ordering"] = _ref(output)
    second_observed = api.validation.format_utc(
        api.validation.parse_utc(observed) + timedelta(seconds=10))
    ordered_health = [health_at("unavailable", "capture_interface_unavailable", 91),
                      health_at("unavailable", "raw_parser_unavailable", 92,
                                when=second_observed)]
    first = capture("T02-M09", ordered_health, [], verify_order,
                    window_start=observed, window_end=one_minute)
    if first is not None:
        second = capture("T02-M09-permutation", list(reversed(ordered_health)), [],
                         verify_order, window_start=observed, window_end=one_minute)
        if second is None or first[1].artifact_id != second[1].artifact_id:
            case_records["T02-M09"]["status"] = "FAIL"
        case_records.pop("T02-M09-permutation", None)

    baseline = first
    if baseline is None:
        case_records["T02-M10"] = {"status": "FAIL", "input_fixture_sha256":
            hashlib.sha256(b"no-valid-baseline").hexdigest()}
        case_records["T02-M11"] = {"status": "FAIL", "input_fixture_sha256":
            hashlib.sha256(b"no-valid-baseline").hexdigest()}
    else:
        snapshot, output = baseline
        mutations = {}
        base = output.semantic_payload
        entry = base["source_entries"][0]
        for name in ("gap", "overlap", "wrong_start", "wrong_end", "duplicate_source",
                     "wrong_epoch", "covered_delayed"):
            payload = copy.deepcopy(base)
            row = payload["source_entries"][0]
            interval = row["coverage_intervals"][0]
            midpoint = api.validation.format_utc(api.validation.parse_utc(
                interval["start_utc"]) + timedelta(seconds=30))
            if name in ("gap", "overlap"):
                row["coverage_intervals"] = [copy.deepcopy(interval), copy.deepcopy(interval)]
                row["coverage_intervals"][0]["end_utc"] = midpoint
                row["coverage_intervals"][1]["start_utc"] = api.validation.format_utc(
                    api.validation.parse_utc(midpoint) + timedelta(milliseconds=(1 if name == "gap" else -1)))
            elif name == "wrong_start":
                interval["start_utc"] = midpoint
            elif name == "wrong_end":
                interval["end_utc"] = midpoint
            elif name == "duplicate_source":
                payload["source_entries"].append(copy.deepcopy(row))
            elif name == "wrong_epoch":
                row["binding_epoch_id"] = "wrong-epoch"
            else:
                interval["coverage_class"] = "covered_delayed"
            digest = hashlib.sha256(_json_bytes(payload)).hexdigest()
            try:
                api.source.make_source_evaluability(payload,
                    evidence_snapshot_content=snapshot, source_health_policy=health_policy)
                mutations[name] = {"status": "FAIL", "input_fixture_sha256": digest,
                                   "expected_failure": "DeviceFingerprintValidationError",
                                   "observed_failure": "ACCEPTED"}
            except api.source.DeviceFingerprintValidationError as exc:
                mutations[name] = {"status": "PASS", "input_fixture_sha256": digest,
                                   "expected_failure": "DeviceFingerprintValidationError",
                                   "observed_failure": type(exc).__name__}
        for case_id, names in (("T02-M10", ("gap", "overlap", "wrong_start", "wrong_end",
                                         "duplicate_source", "wrong_epoch")),
                               ("T02-M11", ("covered_delayed",))):
            case_records[case_id] = {"status": "PASS" if all(
                mutations[name]["status"] == "PASS" for name in names) else "FAIL",
                "input_fixture_sha256": hashlib.sha256(_json_bytes(
                    {name: mutations[name]["input_fixture_sha256"] for name in names})).hexdigest(),
                "expected_failure_records": {name: mutations[name] for name in names}}

    def verify_absence(snapshot, output):
        intervals = _entry(output, epoch["binding_epoch_id"])["coverage_intervals"]
        _require(len(snapshot.semantic_payload["evidence_descriptors"]) == 1,
                 "Later backfilled evidence not audit-visible")
        _require(any(row["coverage_class"] == "delivery_unavailable_loss_possible"
                     for row in intervals), "Recovery rewrote prior delivery loss")
        _require(all(row["coverage_class"] != "covered_delayed" for row in intervals),
                 "Absence/backfill was upgraded to covered_delayed")
        _require(all("negative" not in code.lower() for row in intervals
                     for code in row["reason_code_refs"]), "Negative fingerprint inferred")
    backfill_observed = api.validation.format_utc(
        api.validation.parse_utc(observed) + timedelta(seconds=45))
    backfill = helper._fixture_row(api, epoch, backfill_observed, ingested, 123)
    capture("T02-M12", [health_at("unavailable", "ingest_delivery_unavailable", 121),
                        health_at("available", None, 122, when=api.validation.format_utc(
                            api.validation.parse_utc(observed) + timedelta(seconds=30)))],
            [backfill], verify_absence, window_start=observed, window_end=one_minute)

    return ({"cases": case_records, "traces": traces,
             "all_pass": set(case_records) == set(CASE_IDS) and all(
                 case["status"] == "PASS" for case in case_records.values())},
            {"artifacts": [retained[key] for key in sorted(retained)]})


def _evidence_refs(run_dir: Path) -> list[dict[str, str]]:
    return [{"evidence_label": label, "file_sha256": _sha256(run_dir / filename),
             "media_type": media, "path_or_reference": filename} for label, filename, media in (
        ("t02-execution-evidence", "t02-execution-evidence.json", "application/json"),
        ("t02-artifacts", "t02-artifacts.json", "application/json"),
        ("t02-pytest-log", "t02-pytest.log", "text/plain"))]


def _formal_outputs(run_dir: Path, api: SimpleNamespace, lineage: Any,
                    pinned: dict[str, Any], runner_sha: str, passed: bool):
    helper = _t01()
    inputs = [_ref(lineage.profile), _ref(pinned["source_health_policy"]),
              _ref(pinned["evidence_source_binding_timeline"]),
              _ref(pinned["binding_clock_policy"])]
    evidence = _evidence_refs(run_dir)
    identity = {"execution_id": str(uuid.uuid4()), "executor_kind": "TECHLEAD_GATE_TOOL",
                "repository_commit_sha": EXPECTED_COMMIT, "repository_tree_sha": EXPECTED_TREE,
                "procedure_or_test_suite_id": PROCEDURE,
                "environment_identity": helper._environment_identity(),
                "execution_artifact_sha256": runner_sha}
    proof = None
    if passed:
        proof = api.gate_proof.make_gate_proof_artifact({
            "proof_kind": "SOURCE_EVALUABILITY_EXECUTION", "source_gate_id": "T-02",
            "candidate_repository_commit_sha": EXPECTED_COMMIT,
            "candidate_repository_tree_sha": EXPECTED_TREE, "input_artifact_refs": inputs,
            "procedure_or_test_suite_id": PROCEDURE, "proof_execution_identity": identity,
            "canonical_result_summary": "T-02:pytest=PASS;matrix=12/12 PASS",
            "retained_evidence_refs": evidence})
    result = api.gate_result.make_gate_result_manifest({
        "gate_id": "T-02", "gate_contract_version": GATE_CONTRACT,
        "status": "PASS" if passed else "FAIL",
        "candidate_repository_commit_sha": EXPECTED_COMMIT,
        "candidate_repository_tree_sha": EXPECTED_TREE,
        "input_artifact_refs": inputs, "output_artifact_refs": [_ref(proof)] if proof else [],
        "retained_evidence_refs": evidence, "proof_execution_identity": identity,
        "trusted_time_inputs": {"foundation_knowledge_evaluation_at_utc": None,
                                "foundation_admission_evaluation_at_utc": None,
                                "knowledge_evaluation_at_utc": None},
        "decision_record_refs": []})
    if proof:
        helper._write_and_roundtrip(run_dir / "t02-gate-proof-artifact.json", proof,
                                    api.gate_proof.make_gate_proof_artifact,
                                    api.artifact.canonical_artifact_json)
    helper._write_and_roundtrip(run_dir / "t02-gate-result-manifest.json", result,
                                api.gate_result.make_gate_result_manifest,
                                api.artifact.canonical_artifact_json)
    (run_dir / "t02-summary.txt").write_text(
        f"GATE_EXECUTION_STATUS={'PASS' if passed else 'FAIL'}\n"
        f"GATE_RESULT_MANIFEST={result.artifact_id}\n"
        f"GATE_PROOF_ARTIFACT={proof.artifact_id if proof else 'NONE'}\n", encoding="utf-8")
    return proof, result


def _blocked(run_dir: Path, status: str) -> int:
    for name in ("t02-execution-evidence.json", "t02-artifacts.json", "t02-pytest.log",
                 "t02-gate-proof-artifact.json", "t02-gate-result-manifest.json"):
        (run_dir / name).unlink(missing_ok=True)
    (run_dir / "t02-summary.txt").write_text(
        f"GATE_EXECUTION_STATUS={status}\nFORMAL_GATE_RESULT_MANIFEST=NONE\n",
        encoding="utf-8")
    print(f"GATE_EXECUTION_STATUS={status}")
    return 2


def run_gate(repo: Path, foundation_db: Path, output_dir: Path) -> int:
    try:
        helper = _t01()
        repo = repo.resolve(strict=True)
    except (RuntimeError, OSError):
        print("GATE_EXECUTION_STATUS=BLOCKED_CANDIDATE_IDENTITY")
        return 2
    runner_path = Path(__file__).resolve()
    runner_sha = _sha256(runner_path)
    output_dir = output_dir.resolve()
    if (output_dir.is_relative_to(repo) or output_dir.exists() and
            (not output_dir.is_dir() or any(output_dir.iterdir()))):
        print("GATE_EXECUTION_STATUS=BLOCKED_OUTPUT_DIR")
        return 2
    output_dir.mkdir(parents=True, exist_ok=True)
    run_dir = output_dir / str(uuid.uuid4())
    run_dir.mkdir(exist_ok=False)
    connection = None
    try:
        helper.verify_repository(repo)
        original = helper.repository_filesystem_fingerprint(repo)
        api = load_api(repo)
        connection = helper.open_foundation_read_only(foundation_db)
        lineage = helper.verify_foundation(connection, api)
        pinned, resolver = resolve_pinned(connection, api, lineage)
        helper._require_repository_unchanged(repo, original)
    except (helper.Blocked, OSError) as exc:
        if connection is not None:
            connection.rollback()
            connection.close()
        return _blocked(run_dir, exc.status if isinstance(exc, helper.Blocked)
                        else "BLOCKED_CANDIDATE_IDENTITY")
    try:
        pytest_status, pytest_log, pytest_command = execute_pytest(repo, run_dir)
        (run_dir / "t02-pytest.log").write_text(pytest_log, encoding="utf-8")
        try:
            matrix, artifacts = execute_matrix(run_dir, api, lineage.profile, pinned, resolver)
        except helper.Blocked as exc:
            return _blocked(run_dir, exc.status)
        except Exception as exc:
            matrix, artifacts = {"cases": {}, "traces": {}, "all_pass": False,
                                 "execution_failure_type": type(exc).__name__}, {"artifacts": []}
        helper._require_repository_unchanged(repo, original)
        evidence = {"candidate_repository_commit_sha": EXPECTED_COMMIT,
                    "candidate_repository_tree_sha": EXPECTED_TREE, "runner_sha256": runner_sha,
                    "hardened_helper_sha256": T01_HELPER_SHA256,
                    "foundation_lineage": {name: _ref(content) for name, content in (
                        ("FoundationAdmissionManifest", lineage.manifest),
                        ("FoundationRuntimeProfile", lineage.profile),
                        ("RuntimeProfileAdmissionManifest", lineage.admission),
                        ("RuntimeProfileActivationRecord", lineage.activation),
                        ("RuntimeProfileValidityRecord", lineage.validity),
                        ("F-ADMIT GateResultManifest", lineage.gate_result),
                        ("EvidenceSchemaRegistryContract", lineage.registry))},
                    "pinned_dependencies": {name: _ref(content) for name, content in pinned.items()},
                    "pytest_command": pytest_command, "pytest_exit_status": pytest_status,
                    "matrix": matrix}
        (run_dir / "t02-execution-evidence.json").write_bytes(_json_bytes(evidence))
        (run_dir / "t02-artifacts.json").write_bytes(_json_bytes(artifacts))
        if not _runner_intact(runner_path, runner_sha):
            return _blocked(run_dir, "BLOCKED_RUNNER_CHANGED")
        passed = pytest_status == 0 and matrix["all_pass"]
        _formal_outputs(run_dir, api, lineage, pinned, runner_sha, passed)
        helper._require_repository_unchanged(repo, original)
        if not _runner_intact(runner_path, runner_sha):
            return _blocked(run_dir, "BLOCKED_RUNNER_CHANGED")
        print(f"GATE_EXECUTION_STATUS={'PASS' if passed else 'FAIL'}")
        return 0 if passed else 1
    except helper.Blocked as exc:
        return _blocked(run_dir, exc.status)
    finally:
        connection.rollback()
        connection.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--foundation-control-db", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    return run_gate(args.repo, args.foundation_control_db, args.output_dir)


if __name__ == "__main__":
    raise SystemExit(main())
