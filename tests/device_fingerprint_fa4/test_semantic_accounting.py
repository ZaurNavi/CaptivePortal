"""R14 COMPLETE semantic-byte accounting dependency proofs."""

import json
from dataclasses import replace

import pytest

from app.device_fingerprint.artifact_content import (
    canonical_artifact_json,
    make_artifact_content,
)
from app.device_fingerprint.binding_contracts import (
    make_binding_clock_policy,
    make_evidence_source_binding_timeline,
)
from app.device_fingerprint.models import DeviceFingerprintValidationError
from app.device_fingerprint.source_health_emitter_contracts import (
    build_source_health_emitter_contracts,
)
from research.device_fingerprint_fa4.measurement import _EVIDENCE_FIELDS, _HEALTH_FIELDS
from research.device_fingerprint_fa4.semantic_accounting import (
    ACCEPTED_BINDING_CLOCK_POLICY_ID,
    ACCEPTED_BINDING_TIMELINE_ID,
    ACCEPTED_CLASSIFICATION_FOUNDATION_VALID_FROM_UTC,
    ACCEPTED_SCHEMA_REGISTRY_ID,
    authorized_descriptor,
    binding_descriptor_bytes,
    complete_semantic_byte_accounting,
    load_semantic_accounting_dependencies,
    ordered_binding_descriptors,
    resolve_row_binding,
    semantic_dependency_descriptor,
    semantic_dependency_reference_bytes,
    validate_semantic_accounting_dependencies,
)

from .conftest import (
    EFFECTIVE_FROM,
    NETWORK_EMITTER,
    SITE_ID,
    accepted_clock_payload,
    accepted_timeline_payload,
    binding_epoch,
)


def _evidence_row(observed_at: str = "2026-09-18T10:43:30.000Z") -> dict:
    return {
        "evidence_id": "00000000-0000-4000-8000-000000000001",
        "ingest_sequence": 1,
        "producer_id": "sensor-zefer-01",
        "source_kind": "dhcp",
        "source_subtype": None,
        "capture_source_id": "zefer-span-01",
        "extractor_name": "dhcp-v1",
        "extractor_version": "1.0.0",
        "feature_schema_version": 1,
        "rule_version": None,
        "site_id": SITE_ID,
        "observed_at": observed_at,
        "ingested_at": "2026-09-18T10:43:31.000Z",
        "observed_mac": "AA:BB:CC:DD:EE:FF",
        "privacy_class": "device_fingerprint_restricted",
        "quality_state": "valid",
        "payload_sha256": "a" * 64,
    }


def _health_row() -> dict:
    return {
        "source_health_id": "00000000-0000-4000-8000-000000000002",
        "ingest_sequence": 2,
        "producer_id": "sensor-zefer-01",
        "source_kind": "dhcp",
        "capture_source_id": "zefer-span-01",
        "site_id": SITE_ID,
        "status": "available",
        "reason_code": None,
        "observed_at": "2026-09-18T10:43:30.000Z",
        "ingested_at": "2026-09-18T10:43:31.000Z",
        "content_sha256": "b" * 64,
    }


def test_exact_accepted_dependency_identities_are_rematerialized(accepted_dependencies):
    assert accepted_dependencies.binding_timeline.artifact_id == ACCEPTED_BINDING_TIMELINE_ID
    assert accepted_dependencies.binding_clock_policy.artifact_id == ACCEPTED_BINDING_CLOCK_POLICY_ID
    assert accepted_dependencies.schema_registry_contract.artifact_id == ACCEPTED_SCHEMA_REGISTRY_ID
    validate_semantic_accounting_dependencies(accepted_dependencies)


def test_dependency_payload_files_are_rematerialized_not_trusted(tmp_path):
    timeline_path = tmp_path / "timeline.json"
    clock_path = tmp_path / "clock.json"
    timeline_path.write_text(json.dumps(accepted_timeline_payload()), encoding="utf-8")
    clock_path.write_text(json.dumps(accepted_clock_payload()), encoding="utf-8")
    loaded = load_semantic_accounting_dependencies(str(timeline_path), str(clock_path))
    assert loaded.binding_timeline.artifact_id == ACCEPTED_BINDING_TIMELINE_ID
    assert loaded.binding_clock_policy.artifact_id == ACCEPTED_BINDING_CLOCK_POLICY_ID

    wrong = accepted_clock_payload()
    wrong["measurement_method_id"] = "unaccepted-clock-proof"
    clock_path.write_text(json.dumps(wrong), encoding="utf-8")
    with pytest.raises(DeviceFingerprintValidationError, match="Wrong accepted"):
        load_semantic_accounting_dependencies(str(timeline_path), str(clock_path))


def test_evidence_and_health_descriptor_bytes_include_exact_binding_epoch(accepted_dependencies):
    evidence, evidence_epoch = authorized_descriptor(
        _evidence_row(), _EVIDENCE_FIELDS, accepted_dependencies,
    )
    health, health_epoch = authorized_descriptor(
        _health_row(), _HEALTH_FIELDS, accepted_dependencies,
    )
    assert evidence["binding_epoch_id"] == health["binding_epoch_id"]
    assert evidence_epoch == health_epoch
    assert b'"binding_epoch_id":"zefer-dhcp-v1-20260918T104329014Z"' in (
        canonical_artifact_json(evidence)
    )
    assert b'"binding_epoch_id":"zefer-dhcp-v1-20260918T104329014Z"' in (
        canonical_artifact_json(health)
    )


def test_missing_binding_fails_closed(accepted_dependencies):
    with pytest.raises(DeviceFingerprintValidationError, match="no unambiguous"):
        authorized_descriptor(
            _evidence_row("2026-09-18T10:43:29.013Z"),
            _EVIDENCE_FIELDS,
            accepted_dependencies,
        )


def test_cutover_ambiguity_fails_closed():
    first = binding_epoch(
        "dhcp", "dhcp", "sensor-zefer-01", "zefer-span-01", NETWORK_EMITTER,
        effective_from=EFFECTIVE_FROM,
        effective_to="2026-09-18T10:44:00.000Z",
    )
    second = {
        **first,
        "binding_epoch_id": "zefer-dhcp-v2-20260918T104400000Z",
        "effective_from_utc": "2026-09-18T10:44:00.000Z",
        "effective_to_utc": None,
    }
    timeline = make_evidence_source_binding_timeline(
        {"binding_timeline_contract_version": 1, "binding_epochs": [first, second]},
        build_source_health_emitter_contracts(),
    )
    clock_payload = accepted_clock_payload()
    clock_payload["cutover_guard_seconds"] = 1
    clock = make_binding_clock_policy(clock_payload)
    with pytest.raises(DeviceFingerprintValidationError, match="no unambiguous"):
        resolve_row_binding(_evidence_row("2026-09-18T10:44:00.000Z"), timeline, clock)


@pytest.mark.parametrize("field,artifact_type", [
    ("binding_timeline", "EvidenceSourceBindingTimeline"),
    ("binding_clock_policy", "BindingClockPolicy"),
    ("schema_registry_contract", "EvidenceSchemaRegistryContract"),
])
def test_wrong_dependency_identity_is_rejected(accepted_dependencies, field, artifact_type):
    wrong = make_artifact_content(artifact_type, {"wrong": True})
    with pytest.raises(DeviceFingerprintValidationError, match="Wrong accepted"):
        validate_semantic_accounting_dependencies(
            replace(accepted_dependencies, **{field: wrong}),
        )


def test_binding_epoch_dedup_and_canonical_order_are_exact(accepted_dependencies):
    epochs = accepted_dependencies.binding_timeline.semantic_payload["binding_epochs"]
    reversed_with_duplicate = list(reversed(epochs)) + [epochs[0]]
    ordered = ordered_binding_descriptors(reversed_with_duplicate)
    assert len(ordered) == len(epochs) == 5
    assert [(row["effective_from_utc"], row["origin_group"], row["source_kind"],
             row["capture_source_id"], row["producer_id"], row["binding_epoch_id"])
            for row in ordered] == sorted(
                (row["effective_from_utc"], row["origin_group"], row["source_kind"],
                 row["capture_source_id"], row["producer_id"], row["binding_epoch_id"])
                for row in epochs
            )
    byte_count, epoch_count = binding_descriptor_bytes(reversed_with_duplicate)
    assert epoch_count == 5
    assert byte_count == sum(len(canonical_artifact_json(row)) for row in ordered)


def test_semantic_dependency_reference_bytes_are_exact_pre_admission_structure(
    accepted_dependencies,
):
    descriptor = semantic_dependency_descriptor(accepted_dependencies)
    assert descriptor["classification_foundation_valid_from_utc"] == (
        ACCEPTED_CLASSIFICATION_FOUNDATION_VALID_FROM_UTC
    )
    assert descriptor["origin_runtime_admission"]["tcp_state"] == "ENABLED"
    assert descriptor["origin_runtime_admission"]["tcp_reason_code"] == "TTL_PROOF_VALID"
    assert semantic_dependency_reference_bytes(accepted_dependencies) == len(
        canonical_artifact_json(descriptor)
    )


def test_complete_status_requires_every_exact_byte_category():
    categories = {
        "authorized_evidence_descriptor_bytes": 101,
        "verified_payload_bytes": 102,
        "materialized_payload_bytes": 103,
        "authorized_health_descriptor_bytes": 104,
        "binding_descriptor_bytes": 105,
        "semantic_dependency_reference_bytes": 106,
    }
    complete = complete_semantic_byte_accounting(categories)
    assert complete["total_semantic_input_bytes"] == sum(categories.values())
    assert complete["final_binding_and_dependency_overhead_status"] == "COMPLETE"
    for missing in categories:
        incomplete = dict(categories)
        incomplete.pop(missing)
        with pytest.raises(DeviceFingerprintValidationError, match="Incomplete"):
            complete_semantic_byte_accounting(incomplete)
