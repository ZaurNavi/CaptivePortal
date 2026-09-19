"""Read-only snapshot measurement, privacy and integrity proofs."""

import hashlib
import json
from dataclasses import replace
from datetime import timedelta
from pathlib import Path

import pytest

from app.device_fingerprint.models import DeviceFingerprintValidationError
from app.device_fingerprint.repository import DeviceFingerprintRepository
from app.device_fingerprint.schema_registry import build_production_schema_registry
from app.device_fingerprint.service import DeviceFingerprintService
from app.device_fingerprint.validation import (
    canonical_json, canonical_sha256, format_utc, parse_utc,
)
from research.device_fingerprint_fa4.measurement import (
    InspectionCase, failed_report, inspect_read_only, report_json, write_report_file,
)
from research.device_fingerprint_fa4.semantic_accounting import (
    applicable_binding_epochs, required_health_scopes,
)
from research.device_fingerprint_fa4.workload import FIXED_MAC, FIXED_NOW, _evidence, _health
from tests.device_fingerprint import config, producer

HEAD = "f5a7e33e1db0a6020aa13a8595101034441954f2"
TREE = "5b4aa2d52bda2d57ce62ccd606d259afc463fc96"


def _fixture(tmp_path, count=5):
    cfg = config(tmp_path)
    repo = DeviceFingerprintRepository(cfg.db_path, max_db_bytes=cfg.max_db_bytes)
    repo.initialize()
    svc = DeviceFingerprintService(cfg, repo, build_production_schema_registry(), now=lambda: FIXED_NOW)
    for number in range(count):
        assert svc.evidence_batch(producer(), {"producer_id": producer().producer_id,
                                               "events": [_evidence(number)]}).inserted == 1
        assert svc.source_health_batch(producer(), {"producer_id": producer().producer_id,
                                                    "events": [_health(number)]}).inserted == 1
    case = InspectionCase(
        "fixture", cfg.db_path, producer().site_id, FIXED_MAC,
        format_utc(FIXED_NOW - timedelta(seconds=1)),
        format_utc(FIXED_NOW + timedelta(seconds=1)),
        ((producer().producer_id, producer().capture_source_id, "dhcp"),),
        2, HEAD, TREE,
    )
    return cfg, repo, svc, case


def _fingerprint(path):
    main = Path(path)
    wal = Path(str(path) + "-wal")
    return (hashlib.sha256(main.read_bytes()).hexdigest(),
            hashlib.sha256(wal.read_bytes()).hexdigest() if wal.exists() else None)


def _complete_case(case, dependencies):
    epochs = applicable_binding_epochs(
        dependencies, case.site_id, case.from_utc, case.to_utc,
    )
    return replace(case, health_scopes=required_health_scopes(epochs))


def test_read_only_pages_exhaust_and_report_query_plans_without_mutation(tmp_path):
    cfg, repo, _svc, case = _fixture(tmp_path)
    before = _fingerprint(cfg.db_path)
    report = inspect_read_only(case)
    assert _fingerprint(cfg.db_path) == before
    assert report["result"] == "MEASUREMENT_COMPLETE"
    assert report["cardinality"]["total_evidence_rows"] == 5
    assert report["cardinality"]["total_relevant_health_rows"] == 5
    assert report["pagination"] == {"evidence_pages": 3, "health_pages": 3}
    assert report["payload_accounting"]["verified_evidence_row_count"] == 5
    assert report["payload_accounting"]["materialized_evidence_row_count"] == 5
    assert report["payload_accounting"]["verified_payload_bytes"] == report["payload_accounting"]["materialized_payload_bytes"]
    assert report["semantic_byte_accounting"]["final_binding_and_dependency_overhead_status"] == "PENDING_FOUNDATION_DEPENDENCIES"
    assert len(report["query_plans"]) == 8
    assert all(row["plan_rows"] and "SELECT *" in row["normalized_sql_shape"] for row in report["query_plans"])
    assert {row["query_case_id"] for row in report["query_plans"]} == {
        "evidence_first", "evidence_continuation", "evidence_source_kind",
        "evidence_producer_id", "evidence_capture_source_id",
        "health_first", "health_continuation", "health_latest_predecessor",
    }
    assert report["timing"]["reader_transaction_lifetime"]["duration_ns"] >= 0
    assert report["timing"]["watermark_capture"]["duration_ns"] >= 0
    assert report["cpu_memory"]["python_peak_allocated_bytes"] >= 0
    assert report["cpu_memory"]["process_cpu_duration_ns"] >= 0
    repo.close()


def test_complete_semantic_accounting_uses_exact_six_category_formula_and_is_private(
    tmp_path, accepted_dependencies,
):
    _cfg, repo, _svc, case = _fixture(tmp_path, count=2)
    case = _complete_case(case, accepted_dependencies)
    report = inspect_read_only(case, semantic_dependencies=accepted_dependencies)
    accounting = report["semantic_byte_accounting"]
    categories = (
        "authorized_evidence_descriptor_bytes",
        "verified_payload_bytes",
        "materialized_payload_bytes",
        "authorized_health_descriptor_bytes",
        "binding_descriptor_bytes",
        "semantic_dependency_reference_bytes",
    )
    assert accounting["total_semantic_input_bytes"] == sum(
        accounting[field] for field in categories
    )
    assert accounting["descriptor_scope"] == "r14_snapshot_semantic_descriptors_complete"
    assert accounting["final_binding_and_dependency_overhead_status"] == "COMPLETE"
    assert accounting["binding_epoch_count"] == 5
    serialized = report_json(report)
    for forbidden in (
        FIXED_MAC, FIXED_MAC.lower(), "192.168.8.10", "payload_json",
        "android-dhcp-13", "LAB-ONLY-NOT-RETAINED", "Bearer", "User-Agent",
        "Sec-CH-UA-Model",
    ):
        assert forbidden not in serialized
    repo.close()


@pytest.mark.parametrize("scope_variant", ["missing", "extra", "duplicate"])
def test_complete_health_scope_set_fails_closed_when_not_exact(
    tmp_path, accepted_dependencies, scope_variant,
):
    _cfg, repo, _svc, case = _fixture(tmp_path, count=1)
    exact = _complete_case(case, accepted_dependencies)
    if scope_variant == "missing":
        candidate = replace(exact, health_scopes=exact.health_scopes[:-1])
    elif scope_variant == "extra":
        candidate = replace(
            exact,
            health_scopes=exact.health_scopes + (("extra-producer", "extra-capture", "dhcp"),),
        )
    else:
        candidate = replace(
            exact,
            health_scopes=exact.health_scopes + (exact.health_scopes[0],),
        )
    with pytest.raises((DeviceFingerprintValidationError, ValueError)):
        inspect_read_only(candidate, semantic_dependencies=accepted_dependencies)
    repo.close()


def _insert_health(svc, number, observed_at):
    event = _health(number)
    event["observed_at"] = observed_at
    assert svc.source_health_batch(producer(), {
        "producer_id": producer().producer_id, "events": [event],
    }).inserted == 1


def test_complete_health_includes_same_epoch_predecessor_before_window(
    tmp_path, accepted_dependencies,
):
    _cfg, repo, svc, case = _fixture(tmp_path, count=0)
    predecessor_at = format_utc(parse_utc(case.from_utc) - timedelta(milliseconds=1))
    _insert_health(svc, 100, predecessor_at)
    report = inspect_read_only(
        _complete_case(case, accepted_dependencies),
        semantic_dependencies=accepted_dependencies,
    )
    assert report["cardinality"]["total_relevant_health_rows"] == 1
    assert report["semantic_byte_accounting"]["authorized_health_descriptor_bytes"] > 0
    repo.close()


def test_complete_health_boundary_row_is_counted_once(
    tmp_path, accepted_dependencies,
):
    _cfg, repo, svc, case = _fixture(tmp_path, count=0)
    _insert_health(svc, 101, case.from_utc)
    report = inspect_read_only(
        _complete_case(case, accepted_dependencies),
        semantic_dependencies=accepted_dependencies,
    )
    assert report["cardinality"]["total_relevant_health_rows"] == 1
    repo.close()


def test_complete_health_without_predecessor_does_not_fabricate_row(
    tmp_path, accepted_dependencies,
):
    _cfg, repo, _svc, case = _fixture(tmp_path, count=0)
    report = inspect_read_only(
        _complete_case(case, accepted_dependencies),
        semantic_dependencies=accepted_dependencies,
    )
    assert report["cardinality"]["total_relevant_health_rows"] == 0
    assert report["semantic_byte_accounting"]["authorized_health_descriptor_bytes"] == 0
    assert report["semantic_byte_accounting"]["binding_epoch_count"] == 5
    assert report["semantic_byte_accounting"]["binding_descriptor_bytes"] > 0
    repo.close()


def test_reader_transaction_lifetime_includes_open_and_all_pagination(tmp_path):
    _cfg, repo, _svc, case = _fixture(tmp_path)
    timing = inspect_read_only(case)["timing"]
    lifetime = timing["reader_transaction_lifetime"]["duration_ns"]
    assert lifetime >= timing["open_snapshot_transaction"]["duration_ns"]
    assert lifetime >= timing["evidence_pagination_total"]["duration_ns"]
    assert lifetime >= timing["health_pagination_total"]["duration_ns"]
    repo.close()


def test_snapshot_watermark_remains_pinned_during_delayed_insert(tmp_path, monkeypatch):
    _cfg, repo, svc, case = _fixture(tmp_path)
    from app.device_fingerprint.read_service import DeviceFingerprintSnapshotReadSession
    original = DeviceFingerprintSnapshotReadSession.list_evidence
    once = {"done": False}
    def traced(self, *args, **kwargs):
        page = original(self, *args, **kwargs)
        if not once["done"]:
            once["done"] = True
            svc.evidence_batch(producer(), {"producer_id": producer().producer_id,
                                            "events": [_evidence(99)]})
        return page
    monkeypatch.setattr(DeviceFingerprintSnapshotReadSession, "list_evidence", traced)
    report = inspect_read_only(case)
    assert report["cardinality"]["total_evidence_rows"] == 5
    assert report["watermark_summary"]["max_committed_ingest_sequence"] == 10
    assert repo.read_ingest_watermark(repo.connection)["max_committed_ingest_sequence"] == 11
    repo.close()


def test_unknown_intact_counts_verified_not_materialized_and_corrupt_fails(tmp_path):
    cfg, repo, _svc, case = _fixture(tmp_path, count=2)
    payload = canonical_json({"future": "intact"})
    digest = canonical_sha256(payload)
    repo.connection.execute(
        "UPDATE device_fingerprint_evidence SET source_kind=?,feature_schema_version=?,payload_json=?,payload_sha256=? WHERE source_event_id=?",
        ("future_source", 1, payload, digest, _evidence(0)["source_event_id"]),
    )
    report = inspect_read_only(case)
    accounting = report["payload_accounting"]
    assert accounting["verified_evidence_row_count"] == 2
    assert accounting["materialized_evidence_row_count"] == 1
    assert accounting["unsupported_intact_row_count"] == 1
    assert accounting["verified_payload_bytes"] > accounting["materialized_payload_bytes"]
    assert accounting["verified_payload_bytes"] - accounting["materialized_payload_bytes"] == len(payload.encode())
    repo.connection.execute(
        "UPDATE device_fingerprint_evidence SET payload_sha256=? WHERE source_event_id=?",
        ("0" * 64, _evidence(0)["source_event_id"]),
    )
    with pytest.raises(DeviceFingerprintValidationError):
        inspect_read_only(case)
    repo.close()


def test_serialized_report_has_no_raw_identity_payload_or_secrets(tmp_path):
    _cfg, repo, _svc, case = _fixture(tmp_path, count=1)
    serialized = report_json(inspect_read_only(case))
    for forbidden in (
        FIXED_MAC, FIXED_MAC.lower(), "192.168.8.10", "payload_json",
        "android-dhcp-13", "LAB-ONLY-NOT-RETAINED", "Bearer", "User-Agent",
        "Sec-CH-UA-Model", "SnapshotContentPolicy", "SnapshotExecutionPolicy",
    ):
        assert forbidden not in serialized
    assert "MEASUREMENT_COMPLETE" in serialized
    repo.close()


def test_report_file_is_exclusive_and_failure_report_never_retains_error_message(tmp_path):
    _cfg, repo, _svc, case = _fixture(tmp_path, count=1)
    target = tmp_path / "fa4_measurement_report.json"
    report = inspect_read_only(case)
    write_report_file(report, str(target))
    assert json.loads(target.read_text(encoding="utf-8")) == report
    with pytest.raises(FileExistsError):
        write_report_file(report, str(target))
    with pytest.raises(ValueError):
        write_report_file(report, str(tmp_path / "fingerprint.sqlite3"))
    failed = failed_report(HEAD, TREE, "fixture", "INSPECT", "DeviceFingerprintValidationError")
    assert failed["result"] == "MEASUREMENT_FAILED"
    assert "SECRET-CANARY" not in report_json(failed)
    repo.close()
