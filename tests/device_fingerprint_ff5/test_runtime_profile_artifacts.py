"""R14 closed runtime profile, admission, activation, and validity schemas."""

from __future__ import annotations

from copy import deepcopy

import pytest

from app.device_fingerprint.artifact_content import ArtifactRef
from app.device_fingerprint.ff5_runtime_profile_atomicity import _Fixture
from app.device_fingerprint.models import DeviceFingerprintValidationError
from app.device_fingerprint.runtime_profile_artifacts import (
    direct_artifact_refs, make_classification_runtime_profile,
    make_foundation_runtime_profile, make_runtime_profile_activation_record,
    make_runtime_profile_admission_manifest, make_runtime_profile_validity_record,
)

_BUILDERS = (
    make_foundation_runtime_profile,
    make_classification_runtime_profile,
    make_runtime_profile_admission_manifest,
    make_runtime_profile_activation_record,
    make_runtime_profile_validity_record,
)


@pytest.fixture
def samples(tmp_path):
    fixture = _Fixture(tmp_path / "artifacts.sqlite")
    rpm = fixture.admission("foundation", fixture.foundation_a)
    activation, validity, _ = fixture.records(rpm, 1)
    return fixture, (
        fixture.foundation_a.semantic_payload,
        fixture.classification_a.semantic_payload,
        rpm.semantic_payload,
        activation.semantic_payload,
        validity.semantic_payload,
    )


@pytest.mark.parametrize("index", range(5))
def test_each_artifact_closed_shape_and_deterministic_double_build(samples, index):
    _, payloads = samples
    builder = _BUILDERS[index]
    payload = payloads[index]
    first = builder(payload)
    second = builder(deepcopy(payload))
    assert first.artifact_id == second.artifact_id
    assert first.semantic_payload_json == second.semantic_payload_json
    assert first.content_sha256 == second.content_sha256
    missing = deepcopy(payload)
    missing.pop(next(iter(missing)))
    extra = {**payload, "forbidden": "value"}
    for bad in (missing, extra):
        with pytest.raises(DeviceFingerprintValidationError):
            builder(bad)


@pytest.mark.parametrize("index,field", [
    (0, "foundation_profile_contract_version"),
    (1, "classification_runtime_profile_contract_version"),
    (2, "runtime_profile_admission_contract_version"),
    (3, "activation_contract_version"),
    (4, "runtime_profile_validity_contract_version"),
])
def test_bool_is_not_positive_integer(samples, index, field):
    _, payloads = samples
    bad = deepcopy(payloads[index])
    bad[field] = True
    with pytest.raises(DeviceFingerprintValidationError):
        _BUILDERS[index](bad)


@pytest.mark.parametrize("index,field", [
    (0, "binding_clock_policy"),
    (1, "knowledge_bundle"),
    (2, "foundation_admission_manifest"),
])
def test_wrong_or_invalid_artifact_ref_is_rejected(samples, index, field):
    _, payloads = samples
    bad = deepcopy(payloads[index])
    bad[field] = payloads[0]["source_health_policy"]  # valid ref, wrong target type
    with pytest.raises(DeviceFingerprintValidationError):
        _BUILDERS[index](bad)
    bad[field] = {"artifact_id": "invalid", "content_sha256": "0" * 64}
    with pytest.raises(DeviceFingerprintValidationError):
        _BUILDERS[index](bad)


@pytest.mark.parametrize("index,id_field,digest_field", [
    (3, "runtime_profile_id", "runtime_profile_digest"),
    (4, "runtime_profile_id", "runtime_profile_digest"),
])
def test_record_wrong_target_artifact_type_is_rejected(samples, index, id_field, digest_field):
    _, payloads = samples
    bad = deepcopy(payloads[index])
    other = payloads[0]["binding_clock_policy"]
    bad[id_field], bad[digest_field] = other["artifact_id"], other["content_sha256"]
    with pytest.raises(DeviceFingerprintValidationError):
        _BUILDERS[index](bad)


@pytest.mark.parametrize("index,field", [
    (2, "expected_previous_activation_record_id"),
    (3, "activation_record_id"),
    (3, "activation_generation_id"),
    (4, "validity_record_id"),
    (4, "activation_record_id"),
])
def test_invalid_uuid_is_rejected(samples, index, field):
    _, payloads = samples
    bad = deepcopy(payloads[index])
    bad[field] = "not-a-uuid"
    with pytest.raises(DeviceFingerprintValidationError):
        _BUILDERS[index](bad)


@pytest.mark.parametrize("index,field", [
    (0, "classification_foundation_valid_from_utc"),
    (3, "activated_at_utc"),
    (4, "effective_at_utc"),
])
def test_invalid_utc_ms_is_rejected(samples, index, field):
    _, payloads = samples
    bad = deepcopy(payloads[index])
    bad[field] = "2026-09-23T12:00:00Z"
    with pytest.raises(DeviceFingerprintValidationError):
        _BUILDERS[index](bad)


def test_foundation_canonical_emitter_set_and_nullable_ttl(samples):
    fixture, payloads = samples
    payload = deepcopy(payloads[0])
    second = ArtifactRef(fixture.leaves["SourceHealthEmitterContract"].artifact_id,
                         fixture.leaves["SourceHealthEmitterContract"].content_sha256).as_dict()
    payload["source_health_emitter_contracts"].append(second)
    with pytest.raises(DeviceFingerprintValidationError):
        make_foundation_runtime_profile(payload)
    payload = deepcopy(payloads[0])
    payload["ttl_capture_placement_proof"] = payload["binding_clock_policy"]
    with pytest.raises(DeviceFingerprintValidationError):
        make_foundation_runtime_profile(payload)
    assert payloads[0]["ttl_capture_placement_proof"] is None


def test_classification_profile_has_no_acceptance_lineage(samples):
    _, payloads = samples
    assert set(payloads[1]) == {
        "classification_runtime_profile_contract_version", "foundation_runtime_profile",
        "knowledge_bundle", "classification_policy", "evidence_adapter_contract_set",
        "classifier_artifact_manifest",
    }


def test_admission_initial_noninitial_and_lineage_invariants(samples):
    fixture, payloads = samples
    initial = payloads[2]
    assert initial["previous_active_profile"] is None
    for field, value in (
        ("previous_active_profile", initial["candidate_profile"]),
        ("expected_previous_activation_record_id", "00000000-0000-4000-8000-000000000001"),
        ("expected_previous_activation_generation_id", "00000000-0000-4000-8000-000000000002"),
        ("task04_acceptance_manifest", ArtifactRef(
            fixture.leaves["Task04AcceptanceManifest"].artifact_id,
            fixture.leaves["Task04AcceptanceManifest"].content_sha256).as_dict()),
        ("update_class", "UNKNOWN_UPDATE"),
        ("compatibility_validation_result", "FAIL"),
    ):
        bad = deepcopy(initial)
        bad[field] = value
        with pytest.raises(DeviceFingerprintValidationError):
            make_runtime_profile_admission_manifest(bad)
    bad = deepcopy(initial)
    bad["profile_kind"] = "classification"
    with pytest.raises(DeviceFingerprintValidationError):
        make_runtime_profile_admission_manifest(bad)


def test_activation_predecessor_and_validity_state_rules(samples):
    _, payloads = samples
    activation = payloads[3]
    validity = payloads[4]
    for field, value in (
        ("activation_result", "PENDING"),
        ("previous_activation_record_id", activation["activation_record_id"]),
        ("activation_reason_update_class", "UNKNOWN"),
    ):
        bad = deepcopy(activation)
        bad[field] = value
        with pytest.raises(DeviceFingerprintValidationError):
            make_runtime_profile_activation_record(bad)
    for field, value in (
        ("state", "UNKNOWN"),
        ("reason_code", "SUPERSEDED_SAFE"),
        ("inflight_commit_rule", "REJECT_PINNED_INFLIGHT"),
        ("previous_validity_record_id", validity["validity_record_id"]),
    ):
        bad = deepcopy(validity)
        bad[field] = value
        with pytest.raises(DeviceFingerprintValidationError):
            make_runtime_profile_validity_record(bad)


def test_direct_refs_are_exact_and_canonical(samples):
    fixture, payloads = samples
    foundation = fixture.foundation_a
    classification = fixture.classification_a
    rpm = make_runtime_profile_admission_manifest(payloads[2])
    for artifact, count in ((foundation, 9), (classification, 5), (rpm, 2)):
        refs = direct_artifact_refs(artifact)
        assert len(refs) == count
        assert [ref.artifact_id for ref in refs] == sorted(ref.artifact_id for ref in refs)
    assert direct_artifact_refs(fixture.leaves["KnowledgeBundle"]) == ()
