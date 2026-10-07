import io
import json
import logging
from pathlib import Path
from app.network_metadata.telemetry import NetworkMetadataTelemetry, REASONS
from app.network_metadata.validation import strict_json
from app.network_metadata.models import NetworkMetadataValidationError, FAULT_CATEGORIES
from . import store, record, outcome


def test_logs_reject_all_sensitive_and_arbitrary_dynamic_fields():
    output = io.StringIO()
    logger = logging.Logger("test-private")
    logger.addHandler(logging.StreamHandler(output))
    telemetry = NetworkMetadataTelemetry(logger)
    telemetry.emit("batch_committed", count=1, dns_name="secret.example", reason_code="secret.example",
                   source_generation_id="10.73.0.7", service_name="secret.example", family="secret.example")
    assert json.loads(output.getvalue()) == {"event": "batch_committed", "count": 1}


def test_source_unavailable_is_health_reason_not_record_fault():
    output = io.StringIO()
    logger = logging.Logger("test-source-reason")
    logger.addHandler(logging.StreamHandler(output))
    assert "source_unavailable" in REASONS
    assert "source_" + "unreadable" not in REASONS
    assert "source_unavailable" not in FAULT_CATEGORIES
    NetworkMetadataTelemetry(logger).emit("health_transition", reason_code="source_unavailable",
        source_path="/private/source.jsonl", error="private OS exception")
    assert json.loads(output.getvalue()) == {"event": "health_transition", "reason_code": "source_unavailable"}


def test_transient_fault_digest_never_retained_or_logged(tmp_path):
    with store(tmp_path, source=b"{\n") as state:
        output = io.StringIO()
        logger = logging.Logger("fault-digest-privacy")
        logger.addHandler(logging.StreamHandler(output))
        state.repo.telemetry = NetworkMetadataTelemetry(logger)
        item = outcome(state.config.capture_scope_binding, b"{", generation=state.generation.source_generation_id)
        assert item.source_record_sha256 is not None
        state.repo.ingest_batch([item], state.run, state.health, state.anchor)
        rendered = output.getvalue() + "".join(repr(tuple(row)) for table in ("source_health", "ingest_fault_aggregates")
            for row in state.repo.connection.execute(f"SELECT * FROM network_metadata_{table}"))
        assert item.source_record_sha256 not in rendered
        assert state.repo.connection.execute("SELECT count(*) FROM network_metadata_source_records").fetchone()[0] == 0


def test_diagnostic_tables_and_fault_errors_exclude_sensitive_values(tmp_path):
    with store(tmp_path) as state:
        item = outcome(state.config.capture_scope_binding, generation=state.generation.source_generation_id)
        state.repo.ingest_batch([item], state.run, state.health, state.anchor)
        rendered = "".join(repr(tuple(row)) for table in ("source_generations", "checkpoint", "source_health", "ingest_runs",
            "capture_scope_bindings", "ingest_fault_aggregates") for row in state.repo.connection.execute(f"SELECT * FROM network_metadata_{table}"))
        for sentinel in ("ni-query-sentinel.example", "203.0.113.93", "2001:db8::93", "10.73.0.7"):
            assert sentinel not in rendered
        assert state.repo.connection.execute("PRAGMA foreign_key_check").fetchall() == []
        columns = {row[1] for table in state.repo.connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
                   for row in state.repo.connection.execute(f"PRAGMA table_info({table[0]})")}
        assert not columns & {"raw_json", "payload_json", "extras_json", "source_record_bytes", "pcap"}
        try:
            strict_json(b'{"secret-name":NaN}')
        except NetworkMetadataValidationError as error:
            assert "secret-name" not in str(error)


def test_fingerprint_boundary_and_read_select_allowlist():
    root = Path(__file__).resolve().parents[2] / "app" / "network_metadata"
    health = (root / "health.py").read_text()
    assert "latest_source_health" in health and "import sqlite3" not in health
    assert ".execute(" not in health and "network_metadata_source" not in health
    assert "SELECT *" not in (root / "read_service.py").read_text()
    for file in root.glob("*.py"):
        text = file.read_text()
        assert "app.device_fingerprint.repository" not in text
        assert "app.settings" not in text and "app.config" not in text
