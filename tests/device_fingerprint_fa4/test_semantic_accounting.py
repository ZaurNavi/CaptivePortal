"""R14 COMPLETE semantic-byte accounting dependency proofs."""

import json
from dataclasses import replace

import pytest

from app.device_fingerprint.artifact_content import (
    ArtifactRef,
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
    ACCEPTED_TTL_PROOF_ID,
    applicable_binding_epochs,
    authorized_descriptor,
    binding_descriptor_bytes,
    complete_semantic_byte_accounting,
    health_anchor_descriptor,
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


def _epoch_for(dependencies, source_kind: str) -> dict:
    return next(
        epoch
        for epoch in dependencies.binding_timeline.semantic_payload["binding_epochs"]
        if epoch["source_kind"] == source_kind
    )


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


def test_dependency_payload_import_rejects_duplicate_json_keys(tmp_path):
    timeline_path = tmp_path / "timeline.json"
    clock_path = tmp_path / "clock.json"
    timeline_path.write_text('{"duplicate":1,"duplicate":2}', encoding="utf-8")
    clock_path.write_text(json.dumps(accepted_clock_payload()), encoding="utf-8")
    with pytest.raises(DeviceFingerprintValidationError, match="Duplicate"):
        load_semantic_accounting_dependencies(str(timeline_path), str(clock_path))


@pytest.mark.parametrize("invalid_payload", [
    "{",
    "[]",
    '{"\u00e9":1,"e\u0301":2}',
])
def test_dependency_payload_import_rejects_invalid_nonobject_and_nfc_collision(
    tmp_path, invalid_payload,
):
    timeline_path = tmp_path / "timeline.json"
    clock_path = tmp_path / "clock.json"
    timeline_path.write_text(invalid_payload, encoding="utf-8")
    clock_path.write_text(json.dumps(accepted_clock_payload()), encoding="utf-8")
    with pytest.raises(DeviceFingerprintValidationError):
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


@pytest.mark.parametrize("row_factory,fields", [
    (_evidence_row, _EVIDENCE_FIELDS),
    (_health_row, _HEALTH_FIELDS),
])
@pytest.mark.parametrize("field,value", [
    ("producer_id", "wrong-producer"),
    ("capture_source_id", "wrong-capture"),
])
def test_row_authority_mismatch_fails_closed(
    accepted_dependencies, row_factory, fields, field, value,
):
    row = row_factory()
    row[field] = value
    with pytest.raises(DeviceFingerprintValidationError, match="authoritative binding"):
        authorized_descriptor(row, fields, accepted_dependencies)


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


def test_previous_epoch_health_anchor_is_not_inherited_across_cutover():
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
    clock = make_binding_clock_policy(accepted_clock_payload())
    row = _health_row()
    row["observed_at"] = "2026-09-18T10:43:59.999Z"
    assert health_anchor_descriptor(row, _HEALTH_FIELDS, second, timeline, clock) is None


@pytest.mark.parametrize(("source_kind", "observed_at"), [
    ("dhcp", "2026-09-18T10:43:13.705Z"),
    ("portal_headers", "2026-09-18T08:39:36.219Z"),
])
def test_pre_first_epoch_health_predecessor_is_omitted_without_error(
    accepted_dependencies, source_kind, observed_at,
):
    epoch = _epoch_for(accepted_dependencies, source_kind)
    row = _health_row()
    row.update({
        "producer_id": epoch["producer_id"],
        "capture_source_id": epoch["capture_source_id"],
        "source_kind": source_kind,
        "observed_at": observed_at,
    })
    assert health_anchor_descriptor(
        row,
        _HEALTH_FIELDS,
        epoch,
        accepted_dependencies.binding_timeline,
        accepted_dependencies.binding_clock_policy,
    ) is None


def test_malformed_pre_epoch_health_anchor_still_fails_closed(accepted_dependencies):
    epoch = _epoch_for(accepted_dependencies, "dhcp")
    row = _health_row()
    row["observed_at"] = "2026-09-18T10:43:13.705Z"
    del row["status"]
    with pytest.raises(DeviceFingerprintValidationError, match="Incomplete"):
        health_anchor_descriptor(
            row,
            _HEALTH_FIELDS,
            epoch,
            accepted_dependencies.binding_timeline,
            accepted_dependencies.binding_clock_policy,
        )


def test_health_at_exact_epoch_start_is_authorized(accepted_dependencies):
    epoch = _epoch_for(accepted_dependencies, "dhcp")
    row = _health_row()
    row["observed_at"] = epoch["effective_from_utc"]
    descriptor = health_anchor_descriptor(
        row,
        _HEALTH_FIELDS,
        epoch,
        accepted_dependencies.binding_timeline,
        accepted_dependencies.binding_clock_policy,
    )
    assert descriptor is not None
    assert descriptor["binding_epoch_id"] == epoch["binding_epoch_id"]


def test_in_epoch_no_binding_health_anchor_fails_closed(accepted_dependencies):
    target = {
        **_epoch_for(accepted_dependencies, "dhcp"),
        "binding_epoch_id": "bounded-unregistered-dhcp-epoch",
        "effective_from_utc": "2026-09-18T10:43:20.000Z",
        "effective_to_utc": "2026-09-18T10:43:29.014Z",
    }
    row = _health_row()
    row["observed_at"] = "2026-09-18T10:43:25.000Z"
    with pytest.raises(DeviceFingerprintValidationError, match="no unambiguous"):
        health_anchor_descriptor(
            row,
            _HEALTH_FIELDS,
            target,
            accepted_dependencies.binding_timeline,
            accepted_dependencies.binding_clock_policy,
        )


@pytest.mark.parametrize(("field", "value"), [
    ("producer_id", "wrong-producer"),
    ("capture_source_id", "wrong-capture"),
])
def test_health_anchor_authority_mismatch_remains_fail_closed(
    accepted_dependencies, field, value,
):
    epoch = _epoch_for(accepted_dependencies, "dhcp")
    row = _health_row()
    row[field] = value
    with pytest.raises(DeviceFingerprintValidationError, match="authoritative binding"):
        health_anchor_descriptor(
            row,
            _HEALTH_FIELDS,
            epoch,
            accepted_dependencies.binding_timeline,
            accepted_dependencies.binding_clock_policy,
        )


def test_cutover_ambiguous_health_anchor_is_quarantined():
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
    row = _health_row()
    row["observed_at"] = second["effective_from_utc"]
    assert health_anchor_descriptor(
        row, _HEALTH_FIELDS, second, timeline, clock,
    ) is None


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


def test_wrong_ttl_proof_identity_is_rejected(accepted_dependencies):
    assert accepted_dependencies.ttl_capture_placement_proof.artifact_id == ACCEPTED_TTL_PROOF_ID
    wrong = ArtifactRef(
        "TTLCapturePlacementProof:v1:sha256:" + "0" * 64,
        "0" * 64,
    )
    with pytest.raises(DeviceFingerprintValidationError, match="TTLCapturePlacementProof"):
        validate_semantic_accounting_dependencies(
            replace(accepted_dependencies, ttl_capture_placement_proof=wrong),
        )


@pytest.mark.parametrize("window_start", [
    ACCEPTED_CLASSIFICATION_FOUNDATION_VALID_FROM_UTC,
    "2026-09-18T10:43:29.015Z",
])
def test_complete_window_at_or_after_valid_from_is_allowed(
    accepted_dependencies, window_start,
):
    assert len(applicable_binding_epochs(
        accepted_dependencies,
        SITE_ID,
        window_start,
        "2026-09-18T10:43:30.000Z",
    )) == 5


def test_complete_window_before_valid_from_fails_closed(accepted_dependencies):
    with pytest.raises(DeviceFingerprintValidationError, match="valid-from"):
        applicable_binding_epochs(
            accepted_dependencies,
            SITE_ID,
            "2026-09-18T10:43:29.013Z",
            "2026-09-18T10:43:30.000Z",
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
