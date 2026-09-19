"""Disposable WAL/checkpoint/writer/retention measurement proofs."""

import pytest

from research.device_fingerprint_fa4.measurement import report_json
from research.device_fingerprint_fa4.workload import StressCase, run_disposable_stress

HEAD = "f5a7e33e1db0a6020aa13a8595101034441954f2"
TREE = "5b4aa2d52bda2d57ce62ccd606d259afc463fc96"


def _case():
    return StressCase("fixed-small", 5, 5, 2, 2, 2, HEAD, TREE)


def test_stress_rejects_any_external_db_target(tmp_path):
    path = tmp_path / "not-disposable.sqlite3"
    path.write_bytes(b"sensitive database")
    with pytest.raises(ValueError, match="internally created"):
        run_disposable_stress(_case(), target_db_path=str(path), temporary_parent=str(tmp_path))
    assert path.read_bytes() == b"sensitive database"


def test_disposable_stress_is_deterministic_in_semantics_and_measures_wal(
    tmp_path, accepted_dependencies,
):
    first = run_disposable_stress(
        _case(), temporary_parent=str(tmp_path),
        semantic_dependencies=accepted_dependencies,
    )
    second = run_disposable_stress(
        _case(), temporary_parent=str(tmp_path),
        semantic_dependencies=accepted_dependencies,
    )
    assert first["result"] == second["result"] == "MEASUREMENT_COMPLETE"
    assert first["measurement_case"]["mode"] == "DISPOSABLE_STRESS"
    for field in ("cardinality", "pagination", "payload_accounting", "semantic_byte_accounting"):
        assert first[field] == second[field]
    assert first["semantic_byte_accounting"]["final_binding_and_dependency_overhead_status"] == "COMPLETE"
    assert first["cardinality"]["total_evidence_rows"] == 5
    assert first["cardinality"]["total_relevant_health_rows"] == 5
    assert first["pagination"] == {"evidence_pages": 3, "health_pages": 7}
    assert first["retention_latency"]["deleted_evidence_rows"] == 9
    assert first["retention_latency"]["deleted_health_rows"] == 5
    assert len(first["writer_latency"]["batches"]) == 2
    assert all(item["duration_ns"] >= 0 for item in first["writer_latency"]["batches"])
    assert first["wal_checkpoint"]["wal_bytes_during_reader"] >= first["wal_checkpoint"]["wal_bytes_before_reader"]
    assert len(first["wal_checkpoint"]["checkpoint_during_reader"]) == 3
    assert len(first["wal_checkpoint"]["checkpoint_after_reader_release"]) == 3
    assert first["timing"]["held_reader_transaction_lifetime"]["duration_ns"] >= 0
    assert first["cpu_memory"]["python_peak_allocated_bytes"] >= 0
    serialized = report_json(first)
    assert "AA:BB:CC:DD:EE:FF" not in serialized
    assert "192.168.8.10" not in serialized
    assert "LAB-ONLY-NOT-RETAINED" not in serialized
    assert list(tmp_path.iterdir()) == []
