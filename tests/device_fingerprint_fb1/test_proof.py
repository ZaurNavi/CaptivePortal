"""Read-only topology, exact clock offsets, and sanitized candidate report."""

import hashlib
import json
import sqlite3
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from app.device_fingerprint.models import DeviceFingerprintValidationError
from research.device_fingerprint_fb1.proof import (
    inspect_task01_topology, measure_clock_offsets, report_json,
    run_candidate_proof, write_report_file,
)
from tests.device_fingerprint import SITE
from tests.device_fingerprint.test_binding_contracts import T, _pair
from tests.device_fingerprint.test_storage_v2 import _representative_v1
from tests.device_fingerprint_fa4.test_measurement import _fixture

HEAD = "0ae5581e37df8344581272c6702913b6f926eaf7"
TREE = "6267741118c920ac180af57e4e2ba1da47badb3f"


def _clock_input():
    return {
        "measurement_method_id": "paired-read-v1",
        "task01_clock_domain_id": "task01-clock",
        "producer_clock_domains": [
            {"clock_domain_id": "sensor-clock", "producer_id": "sensor-zefer-01"},
        ],
        "clock_samples": [
            {"producer_id": "sensor-zefer-01", "clock_domain_id": "sensor-clock",
             "producer_time_utc": "2026-09-15T11:59:59.875Z",
             "task01_time_utc": T},
            {"producer_id": "sensor-zefer-01", "clock_domain_id": "sensor-clock",
             "producer_time_utc": "2026-09-15T12:00:00.040Z",
             "task01_time_utc": T},
        ],
    }


def _input(db_path):
    timeline, policy, _ = _pair()
    return {
        "repository_commit_sha": HEAD,
        "repository_tree_sha": TREE,
        "task01_db_path": str(db_path),
        "clock_proof_input": _clock_input(),
        "candidate_timeline_payload": timeline.semantic_payload,
        "candidate_clock_policy_payload": policy.semantic_payload,
        "cutover_fixtures": [{
            "site_id": SITE, "origin_group": "dhcp", "source_kind": "dhcp",
            "cutover_utc": T, "guard_seconds": 3,
            "checks": [
                {"observed_at": "2026-09-15T11:59:56.999Z", "expected_outcome": "AUTHORIZED"},
                {"observed_at": "2026-09-15T11:59:57.000Z", "expected_outcome": "CUTOVER_AMBIGUOUS"},
                {"observed_at": T, "expected_outcome": "CUTOVER_AMBIGUOUS"},
                {"observed_at": "2026-09-15T12:00:02.999Z", "expected_outcome": "CUTOVER_AMBIGUOUS"},
                {"observed_at": "2026-09-15T12:00:03.000Z", "expected_outcome": "AUTHORIZED"},
            ],
        }],
    }


def _durable_fingerprint(path):
    main, wal = Path(path), Path(str(path) + "-wal")
    return (hashlib.sha256(main.read_bytes()).hexdigest(),
            hashlib.sha256(wal.read_bytes() if wal.exists() else b"").hexdigest())


def test_exact_clock_samples_use_integer_milliseconds_and_declared_domains():
    summary = measure_clock_offsets(_clock_input())
    assert summary["sample_count"] == 2
    assert summary["overall_measured_max_relative_offset_ms"] == 125
    assert summary["per_producer_max_absolute_offset_ms"] == [{
        "producer_id": "sensor-zefer-01", "sample_count": 2,
        "max_absolute_offset_ms": 125,
    }]
    for mutate in (
        lambda value: value.update(extra=True),
        lambda value: value["clock_samples"][0].update(clock_domain_id="unknown"),
        lambda value: value["clock_samples"][0].update(producer_time_utc="2026-09-15T11:59:59Z"),
        lambda value: value["clock_samples"][0].update(extra=True),
        lambda value: value.update(clock_samples=[]),
    ):
        candidate = deepcopy(_clock_input())
        mutate(candidate)
        with pytest.raises(DeviceFingerprintValidationError):
            measure_clock_offsets(candidate)


def test_v2_topology_is_read_only_scope_only_and_report_is_sanitized(tmp_path):
    cfg, repo, _svc, _case = _fixture(tmp_path)
    before = _durable_fingerprint(cfg.db_path)
    summary = inspect_task01_topology(cfg.db_path)
    assert _durable_fingerprint(cfg.db_path) == before
    assert summary["task01_schema_version"] == 2
    assert summary["scope_count"] == 1
    assert summary["scopes"] == [{
        "site_id": SITE, "producer_id": "sensor-zefer-01",
        "capture_source_id": "zefer-span-01", "source_kind": "dhcp",
        "evidence_row_count": 5, "source_health_row_count": 5,
        "minimum_observed_at": summary["scopes"][0]["minimum_observed_at"],
        "maximum_observed_at": summary["scopes"][0]["maximum_observed_at"],
    }]
    report = run_candidate_proof(_input(cfg.db_path))
    assert _durable_fingerprint(cfg.db_path) == before
    assert report["result"] == "PROOF_COMPLETE"
    assert report["cutover_fixture_summary"]["pass"] is True
    assert [row["pass"] for row in report["cutover_fixture_summary"]["fixtures"][0]["tested_timestamps"]] == [True] * 5
    assert report["authority_overlap_check"] is True
    assert report["emitter_reference_check"] is True
    assert report["mac_registry_absent"] is True
    assert report["classification_foundation_valid_from_status"] == "NOT_FROZEN_F_B1_A"
    assert report["raw_payload_retained"] is False
    assert report["raw_device_identity_retained"] is False
    serialized = report_json(report)
    for forbidden in ("AA:BB:CC:DD:EE:FF", "192.168.8.10", "payload_json",
                      "observed_mac", "observed_ip", "Bearer", "Sec-CH-UA", str(cfg.db_path)):
        assert forbidden not in serialized
    assert report_json(json.loads(serialized)) == serialized
    injected = deepcopy(report)
    injected["topology_summary"]["scopes"][0]["payload_json"] = "SECRET"
    with pytest.raises(DeviceFingerprintValidationError):
        report_json(injected)
    target = tmp_path / "proof.json"
    write_report_file(report, str(target))
    assert target.read_text(encoding="utf-8") == serialized
    with pytest.raises(FileExistsError):
        write_report_file(report, str(target))
    repo.close()


def test_v1_topology_supported_without_migration_and_unsupported_fails_closed(tmp_path):
    legacy, _before = _representative_v1(tmp_path)
    fingerprint = _durable_fingerprint(legacy)
    summary = inspect_task01_topology(str(legacy))
    assert summary["task01_schema_version"] == 1
    assert summary["scopes"][0]["evidence_row_count"] == 2
    assert summary["scopes"][0]["source_health_row_count"] == 1
    assert _durable_fingerprint(legacy) == fingerprint
    other = tmp_path / "unsupported.sqlite3"
    connection = sqlite3.connect(other)
    connection.execute("PRAGMA user_version=3")
    connection.close()
    with pytest.raises(DeviceFingerprintValidationError):
        inspect_task01_topology(str(other))


def test_candidate_policy_must_equal_measured_clock_proof_and_mismatch_fails(tmp_path):
    cfg, repo, _svc, _case = _fixture(tmp_path, count=1)
    value = _input(cfg.db_path)
    value["candidate_clock_policy_payload"]["measured_max_relative_clock_offset_ms"] = 120
    with pytest.raises(DeviceFingerprintValidationError):
        run_candidate_proof(value)
    value = _input(cfg.db_path)
    value["cutover_fixtures"][0]["checks"][0]["expected_outcome"] = "NO_BINDING"
    assert run_candidate_proof(value)["result"] == "PROOF_FAILED"
    value = _input(cfg.db_path)
    value["candidate_timeline_payload"]["binding_epochs"][0]["source_health_emitter_contract"]["content_sha256"] = "0" * 64
    with pytest.raises(DeviceFingerprintValidationError):
        run_candidate_proof(value)
    repo.close()


def test_zero_guard_cutover_proof_boundary_is_exact(tmp_path):
    cfg, repo, _svc, _case = _fixture(tmp_path, count=1)
    timeline, policy, _ = _pair(0)
    value = _input(cfg.db_path)
    value["candidate_timeline_payload"] = timeline.semantic_payload
    value["candidate_clock_policy_payload"] = policy.semantic_payload
    value["cutover_fixtures"] = [{
        "site_id": SITE, "origin_group": "dhcp", "source_kind": "dhcp",
        "cutover_utc": T, "guard_seconds": 0,
        "checks": [
            {"observed_at": "2026-09-15T11:59:59.999Z", "expected_outcome": "AUTHORIZED"},
            {"observed_at": T, "expected_outcome": "AUTHORIZED"},
        ],
    }]
    assert run_candidate_proof(value)["cutover_fixture_summary"]["pass"] is True
    repo.close()


def test_offline_cli_uses_closed_input_and_outputs_only_sanitized_report(tmp_path):
    cfg, repo, _svc, _case = _fixture(tmp_path, count=1)
    source, target = tmp_path / "input.json", tmp_path / "output.json"
    source.write_text(json.dumps(_input(cfg.db_path)), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "-m", "research.device_fingerprint_fb1", "--input", str(source),
         "--output", str(target)], capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    output = target.read_text(encoding="utf-8")
    assert json.loads(output)["result"] == "PROOF_COMPLETE"
    assert str(cfg.db_path) not in output
    assert "observed_mac" not in output and "payload_json" not in output
    repo.close()
