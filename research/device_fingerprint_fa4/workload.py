"""Deterministic disposable Task-01 v2 WAL/write/retention stress proof."""

from __future__ import annotations

import ipaddress
import tempfile
import threading
import time
import tracemalloc
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from app.device_fingerprint.models import DeviceFingerprintConfig, DeviceFingerprintProducer
from app.device_fingerprint.read_service import DeviceFingerprintReadService
from app.device_fingerprint.repository import DeviceFingerprintRepository
from app.device_fingerprint.schema_registry import build_production_schema_registry
from app.device_fingerprint.service import DeviceFingerprintService
from app.device_fingerprint.validation import format_utc

from .measurement import InspectionCase, inspect_read_only, _duration, _ns, _rss
from .semantic_accounting import (
    SemanticAccountingDependencies,
    applicable_binding_epochs,
    required_health_scopes,
)

UTC = timezone.utc
FIXED_NOW = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)
FIXED_SITE = "6a64f17630da7c70d232187a"
FIXED_MAC = "AA:BB:CC:DD:EE:FF"


@dataclass(frozen=True, slots=True)
class StressCase:
    measurement_case_id: str
    evidence_row_count: int
    health_row_count: int
    page_size: int
    number_of_writer_batches: int
    rows_per_writer_batch: int
    repository_commit_sha: str
    repository_tree_sha: str


def _uuid(number: int) -> str:
    return str(uuid.UUID(int=number, version=4))


def _evidence(number: int) -> dict[str, Any]:
    return {
        "source_event_id": _uuid(number + 1), "source_kind": "dhcp",
        "source_subtype": None, "extractor_name": "dhcp-v1",
        "extractor_version": "1.0.0", "feature_schema_version": 1,
        "rule_version": None, "site_id": FIXED_SITE,
        "capture_source_id": "zefer-span-01", "observed_at": format_utc(FIXED_NOW),
        "observed_mac": FIXED_MAC, "observed_ip": "192.168.8.10",
        "quality_state": "valid",
        "payload": {
            "message_type": "discover", "parameter_request_list": [1, 3, 6],
            "option_order": [53, 55], "vendor_class": "android-dhcp-13",
            "client_identifier_kind": "mac", "maximum_message_size": 1500,
            "rapid_commit_requested": False, "capport_requested": True,
            "ipv6_only_preferred_requested": False, "hostname_present": True,
        },
    }


def _health(number: int) -> dict[str, Any]:
    return {
        "source_health_event_id": _uuid(number + 1_000_000),
        "site_id": FIXED_SITE, "capture_source_id": "zefer-span-01",
        "source_kind": "dhcp", "status": "available", "reason_code": None,
        "observed_at": format_utc(FIXED_NOW),
    }


def _seed(service: DeviceFingerprintService, producer: DeviceFingerprintProducer,
          count: int, make_event: Any, method: str, *, first: int = 0) -> None:
    for offset in range(0, count, 100):
        batch = [make_event(number) for number in range(
            first + offset, first + min(offset + 100, count))]
        result = getattr(service, method)(producer, {
            "producer_id": producer.producer_id, "events": batch,
        })
        if result.inserted != len(batch):
            raise RuntimeError("Disposable fixture did not insert exact row count")


def _wal_bytes(path: Path) -> int:
    wal = Path(str(path) + "-wal")
    return wal.stat().st_size if wal.exists() else 0


def run_disposable_stress(
    case: StressCase,
    *,
    temporary_parent: str | None = None,
    target_db_path: str | None = None,
    semantic_dependencies: SemanticAccountingDependencies | None = None,
) -> dict[str, Any]:
    """Never stress a supplied/existing database; create a new private temp DB."""
    if target_db_path is not None:
        raise ValueError("Stress target must be internally created and disposable")
    for field in ("evidence_row_count", "health_row_count", "number_of_writer_batches"):
        if type(getattr(case, field)) is not int or getattr(case, field) < 0:
            raise ValueError("Invalid explicit workload scale")
    if type(case.rows_per_writer_batch) is not int or not 1 <= case.rows_per_writer_batch <= 100:
        raise ValueError("Writer batch size exceeds accepted Task-01 API range")
    if type(case.page_size) is not int or not 1 <= case.page_size <= 500:
        raise ValueError("Page size exceeds accepted Task-01 read range")
    with tempfile.TemporaryDirectory(prefix="fa4-disposable-", dir=temporary_parent) as directory:
        path = Path(directory) / "fingerprint.sqlite3"
        producer = DeviceFingerprintProducer(
            "sensor-zefer-01", "LAB-ONLY-NOT-RETAINED", "zefer-span-01",
            FIXED_SITE, (ipaddress.ip_network("192.168.8.0/22"),), ("dhcp",),
        )
        config = DeviceFingerprintConfig(
            enabled=True, db_path=str(path), writer_lock_path=str(Path(directory) / "writer.lock"),
            bind_address="127.0.0.1", port=9443, tls_cert_path=str(Path(directory) / "cert"),
            tls_key_path=str(Path(directory) / "key"), allowed_networks=(ipaddress.ip_network("127.0.0.0/8"),),
            producers=(producer,), retention_days=30, max_future_skew_seconds=120,
            max_delayed_event_age_seconds=86_400, max_db_bytes=67_108_864,
            max_http_request_bytes=1_048_576, max_events_per_batch=100,
            max_payload_bytes=8_192, max_concurrent_ingest_requests=2,
        )
        repo = DeviceFingerprintRepository(config.db_path, max_db_bytes=config.max_db_bytes)
        repo.initialize()
        try:
            service = DeviceFingerprintService(config, repo, build_production_schema_registry(), now=lambda: FIXED_NOW)
            _seed(service, producer, case.evidence_row_count, _evidence, "evidence_batch")
            _seed(service, producer, case.health_row_count, _health, "source_health_batch")
            from_utc = format_utc(FIXED_NOW - timedelta(seconds=1))
            to_utc = format_utc(FIXED_NOW + timedelta(seconds=1))
            health_scopes = ((producer.producer_id, producer.capture_source_id, "dhcp"),)
            if semantic_dependencies is not None:
                health_scopes = required_health_scopes(applicable_binding_epochs(
                    semantic_dependencies, FIXED_SITE, from_utc, to_utc,
                ))
            inspection = inspect_read_only(InspectionCase(
                case.measurement_case_id, str(path), FIXED_SITE, FIXED_MAC,
                from_utc, to_utc, health_scopes,
                case.page_size, case.repository_commit_sha, case.repository_tree_sha,
            ), semantic_dependencies=semantic_dependencies)
            before = _wal_bytes(path)
            reader_start = _ns()
            cpu_start = time.process_time_ns()
            tracemalloc.start()
            read = DeviceFingerprintReadService(str(path), retention_days=30)
            writer_durations = []
            writer_error: list[BaseException] = []
            try:
                with read.open_snapshot_read() as snapshot:
                    pinned = snapshot.watermark.max_committed_ingest_sequence
                    snapshot.list_evidence(
                        FIXED_SITE, FIXED_MAC,
                        format_utc(FIXED_NOW - timedelta(seconds=1)),
                        format_utc(FIXED_NOW + timedelta(seconds=1)), limit=case.page_size,
                    )
                    def writer() -> None:
                        try:
                            for batch_no in range(case.number_of_writer_batches):
                                start = _ns()
                                _seed(service, producer, case.rows_per_writer_batch, _evidence,
                                      "evidence_batch", first=1_000_000 + batch_no * case.rows_per_writer_batch)
                                writer_durations.append(_duration(start))
                        except BaseException as exc:
                            writer_error.append(exc)
                    thread = threading.Thread(target=writer)
                    thread.start()
                    thread.join()
                    if writer_error:
                        raise writer_error[0]
                    retention_start = _ns()
                    deleted = repo.cleanup(now=FIXED_NOW + timedelta(days=31), evidence_retention_days=30)
                    retention_timing = _duration(retention_start)
                    during = _wal_bytes(path)
                    checkpoint_during = tuple(int(x) for x in repo.connection.execute("PRAGMA wal_checkpoint(PASSIVE)").fetchone())
                    if snapshot.watermark.max_committed_ingest_sequence != pinned:
                        raise RuntimeError("Snapshot watermark shifted")
                reader_timing = _duration(reader_start)
                checkpoint_after = tuple(int(x) for x in repo.connection.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone())
                after = _wal_bytes(path)
            finally:
                _current, peak = tracemalloc.get_traced_memory()
                tracemalloc.stop()
            rss, rss_available = _rss()
            inspection["measurement_case"]["mode"] = "DISPOSABLE_STRESS"
            inspection["measurement_case"]["workload"] = {
                "evidence_row_count": case.evidence_row_count,
                "health_row_count": case.health_row_count,
                "number_of_writer_batches": case.number_of_writer_batches,
                "rows_per_writer_batch": case.rows_per_writer_batch,
            }
            inspection["wal_checkpoint"] = {
                "wal_bytes_before_reader": before, "wal_bytes_during_reader": during,
                "wal_bytes_after_reader_release": after,
                "checkpoint_during_reader": list(checkpoint_during),
                "checkpoint_after_reader_release": list(checkpoint_after),
            }
            inspection["writer_latency"] = {"batches": writer_durations}
            inspection["retention_latency"] = {**retention_timing,
                                               "deleted_evidence_rows": int(deleted["device_fingerprint_evidence"]),
                                               "deleted_health_rows": int(deleted["device_fingerprint_source_health_events"])}
            inspection["timing"]["held_reader_transaction_lifetime"] = reader_timing
            inspection["cpu_memory"] = {
                "process_cpu_duration_ns": time.process_time_ns() - cpu_start,
                "python_peak_allocated_bytes": peak, "posix_maxrss": rss,
                "posix_maxrss_available": rss_available,
            }
            return inspection
        finally:
            repo.close()
