"""Deterministic F-B3 proof against actual Task-01 repository cleanup."""

from __future__ import annotations

import hashlib
import inspect
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

from app.device_fingerprint.config import SOURCE_HEALTH_RETENTION_MARGIN_SECONDS
from app.device_fingerprint.health_retention_contract import (
    activation_margin_compatible, derive_health_anchor_margin_seconds,
    final_source_health_policy,
)
from app.device_fingerprint.models import ValidatedEvidence, ValidatedSourceHealth
from app.device_fingerprint.repository import DeviceFingerprintRepository
from app.device_fingerprint.validation import format_utc

_NOW = datetime(2026, 9, 18, 12, tzinfo=timezone.utc)
_PAYLOAD = "{}"
_PAYLOAD_SHA = hashlib.sha256(_PAYLOAD.encode("utf-8")).hexdigest()


def _identifier(number: int) -> str:
    return str(UUID(int=number))


def _evidence(number: int, observed_at: str) -> ValidatedEvidence:
    return ValidatedEvidence(
        producer_id="sensor-zefer-01", source_event_id=_identifier(number),
        source_kind="dhcp", source_subtype=None, extractor_name="dhcp-v1",
        extractor_version="1.0.0", feature_schema_version=1, rule_version=None,
        site_id="6a64f17630da7c70d232187a", capture_source_id="zefer-span-01",
        observed_at=observed_at, observed_mac="aa-bb-cc-dd-ee-ff", observed_ip=None,
        privacy_class="P1", quality_state="valid", payload_json=_PAYLOAD,
        payload_sha256=_PAYLOAD_SHA,
    )


def _health(number: int, observed_at: str) -> ValidatedSourceHealth:
    return ValidatedSourceHealth(
        producer_id="sensor-zefer-01", source_health_event_id=_identifier(number),
        site_id="6a64f17630da7c70d232187a", capture_source_id="zefer-span-01",
        source_kind="dhcp", status="available", reason_code=None,
        observed_at=observed_at, content_sha256="0" * 64,
    )


def run_f_b3_proof(directory: Path, *, evidence_retention_days: int) -> dict[str, object]:
    """Use an isolated new SQLite DB; no live data, clocks, or binding lookup."""
    if type(evidence_retention_days) is not int or not 1 <= evidence_retention_days <= 90:
        raise ValueError("Unsupported evidence retention fixture")
    policy = final_source_health_policy()
    margin = derive_health_anchor_margin_seconds(policy)
    if margin != SOURCE_HEALTH_RETENTION_MARGIN_SECONDS:
        raise AssertionError("Policy and Task-01 capability differ")
    evidence_cutoff = _NOW - timedelta(days=evidence_retention_days)
    health_cutoff = evidence_cutoff - timedelta(seconds=margin)
    repo = DeviceFingerprintRepository(
        str(directory / f"fb3-retention-{evidence_retention_days}.sqlite3"),
        max_db_bytes=67_108_864,
    )
    repo.initialize()
    try:
        repo.ingest_evidence([
            _evidence(1, format_utc(evidence_cutoff)),
            _evidence(2, format_utc(evidence_cutoff - timedelta(milliseconds=1))),
        ], ingested_at=format_utc(_NOW))
        repo.ingest_source_health([
            _health(3, format_utc(health_cutoff)),
            _health(4, format_utc(health_cutoff - timedelta(milliseconds=1))),
        ], ingested_at=format_utc(_NOW))
        deleted = repo.cleanup(now=_NOW, evidence_retention_days=evidence_retention_days)
        evidence_remaining = {row[0] for row in repo.connection.execute(
            "SELECT observed_at FROM device_fingerprint_evidence")}
        health_remaining = {row[0] for row in repo.connection.execute(
            "SELECT observed_at FROM device_fingerprint_source_health_events")}
    finally:
        repo.close()
    if (deleted != {"device_fingerprint_evidence": 1,
                    "device_fingerprint_source_health_events": 1}
            or evidence_remaining != {format_utc(evidence_cutoff)}
            or health_remaining != {format_utc(health_cutoff)}):
        raise AssertionError("Task-01 cleanup boundary proof failed")
    cleanup_source = inspect.getsource(DeviceFingerprintRepository.cleanup)
    topology_tokens = ("BindingTimeline", "binding_epoch", "producer_id",
                       "capture_source_id", "source_kind")
    if any(token in cleanup_source for token in topology_tokens):
        raise AssertionError("Cleanup consulted binding topology")
    return {
        "derived_health_anchor_margin_seconds": margin,
        "max_family_freshness_seconds": 600,
        "clock_uncertainty_seconds": 0,
        "evidence_retention_days": evidence_retention_days,
        "evidence_retention_seconds": evidence_retention_days * 86_400,
        "source_health_retention_seconds": evidence_retention_days * 86_400 + margin,
        "evidence_cutoff": format_utc(evidence_cutoff),
        "health_cutoff": format_utc(health_cutoff),
        "oldest_evidence_retained": True,
        "required_predecessor_retained": True,
        "older_health_row_deleted": True,
        "older_evidence_row_deleted": True,
        "cleanup_parses_binding_timeline": False,
        "activation_600_with_600": activation_margin_compatible(600, 600),
        "activation_601_with_600": activation_margin_compatible(601, 600),
    }
