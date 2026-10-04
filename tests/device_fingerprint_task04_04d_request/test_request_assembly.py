"""Pinned profile, pure request identity, and acceptance-only assembly tests."""

from __future__ import annotations

from inspect import signature
import sqlite3

import pytest

from app.device_fingerprint.artifact_content import ArtifactRef, make_artifact_content
from app.device_fingerprint.classification_policy import build_initial_classification_policy_v1
from app.device_fingerprint.classification_request import make_classification_request_manifest
from app.device_fingerprint.control_plane_store import (
    ActiveProfilePointerV1, ControlPlaneOperationError, PinnedRuntimeProfile,
)
from app.device_fingerprint.evidence_adapter_contracts import build_initial_evidence_adapter_contract_set_v1
from app.device_fingerprint.knowledge_bundle import build_initial_knowledge_bundle_v1
from app.device_fingerprint.models import DeviceFingerprintValidationError
from app.device_fingerprint.request_assembly import DeviceFingerprintRequestAssembly, RequestAssemblyError
from app.device_fingerprint.runtime_profile_artifacts import make_classification_runtime_profile
from tests.device_fingerprint import SITE
from tests.device_fingerprint_fe7.test_knowledge_bundle import candidate
from tests.device_fingerprint_task04_t01.test_snapshot_service import MAC, START, END, context
from tests.device_fingerprint_task04_t03.test_origin_assessment import _dhcp_row

TIME = "2026-09-22T22:30:34.464Z"


def ref(content):
    return ArtifactRef(content.artifact_id, content.content_sha256).as_dict()


class FakeControl:
    def __init__(self, contents, profile, *, pinned=None):
        self.contents = contents
        self.profile = profile
        self.pinned = pinned
        self.pins = []
        self.loads = []
        self.commit_checks = []
        self.commit_failure = None

    def load_artifact(self, artifact_id, digest=None):
        self.loads.append(artifact_id)
        item = self.contents[artifact_id]
        assert digest is None or item.content_sha256 == digest
        return item

    def pin_active_profile(self, kind):
        self.pins.append(kind)
        return self.pinned

    def check_pinned_commit_allowed(self, pinned):
        self.commit_checks.append(pinned)
        if self.commit_failure is not None:
            raise ControlPlaneOperationError(self.commit_failure)
        return True

    def capture_pinned_commit_lineage(self, pinned):
        try:
            self.check_pinned_commit_allowed(pinned)
        except ControlPlaneOperationError as exc:
            if exc.reason_code == "ttl_capture_proof_invalidated":
                raise ControlPlaneOperationError("runtime_profile_invalidated") from exc
            raise
        return (pinned.validity_record,)


def prepared(*, clock=lambda: TIME, hook=lambda *_: True, evidence_rows=()):
    ctx = context(evidence_rows)
    knowledge = candidate()
    bundle = build_initial_knowledge_bundle_v1(knowledge)
    registry_ref = ctx.profile.semantic_payload["evidence_schema_registry_contract"]
    adapter = build_initial_evidence_adapter_contract_set_v1(ctx.contents[registry_ref["artifact_id"]])
    policy = build_initial_classification_policy_v1(
        knowledge.classification_taxonomy, knowledge.alias_mapping, adapter)
    classifier = make_artifact_content("ClassifierArtifactManifest", {"synthetic": True})
    profile = make_classification_runtime_profile({
        "classification_runtime_profile_contract_version": 1,
        "foundation_runtime_profile": ref(ctx.profile),
        "knowledge_bundle": ref(bundle), "classification_policy": ref(policy),
        "evidence_adapter_contract_set": ref(adapter),
        "classifier_artifact_manifest": ref(classifier),
    })
    contents = dict(ctx.contents)
    contents.update({item.artifact_id: item for item in (
        ctx.profile, bundle, adapter, policy, classifier, profile,
        *(getattr(knowledge, field) for field in knowledge.__dataclass_fields__),
    )})
    store = FakeControl(contents, profile)
    service = DeviceFingerprintRequestAssembly(
        control_plane_store=store, read_service=ctx.read,
        compatibility_hook=hook, utc_clock=clock,
        process_memory_guard=lambda _limit: True)
    return ctx, store, service, profile


def candidate_run(service, profile):
    return service.assemble_pre_acceptance_candidate(profile, SITE, MAC, START, END)


# Captured on exact base 97bd1cf924024a38cc3229bfd726a25fe6754b07 before repair.
@pytest.mark.parametrize("with_dhcp,request_sha,origin_shas,result_sha", [
    (False, "11cddc6cc4a59a284102d05624923cd6d29bd37399257e2f3bc8a8779b8bff93", {
        "dhcp": "86e15793c6f0bd4a8f9d184380804636f4ebb87bc545e95e7baa2a6d660e52d3",
        "mac_registry": "ebecdce07f8997b9b7508ae427b6c74493f4cee86bf21956e80ac8d7b86ca3e5",
        "portal": "4ad88b312d57df263a79f9d72d62acdb15f58942db7e2a592225d0a554c16e98",
        "quic": "058f57e4ef5b0323119d28c09bd77f3f7ee44865b9a78429b92a72b749c3c75c",
        "tcp": "d6b4217ef4878f8943f40cc841d4afa0506119374dfd75e390ca24926c59050a",
        "tls": "a0f5b388f7360bd93001696a195e58435af33016a0fc140e72546ade153cfd4d",
    }, "f2250e57ea2cf270c335d2acf4041be465aaedf5416f934be0d13ff7f720b5cb"),
    (True, "33a7b48dab2b796a0c6b47fabe11964cef3f3ac49b166639d1c6c0823a5b2667", {
        "dhcp": "1390bd7a0c43844eeb8c5e3209c782c1125ae569977567f305a3ba194fb15f2d",
        "mac_registry": "0e4f8b2c64efabda9f449efb7f580f8444a27452c6f156d23338eefe977da687",
        "portal": "d10c4aa382df2319bfb68dc660597d54f06a7fa0b7240c5690a0d062584a6480",
        "quic": "4accc3c443b627ba228540ec059ba12c3bfde7795faceec942badef7e52e2041",
        "tcp": "ccdd612e62744fa66f4fd20cdf93e61b46393c49e9c38fea514821d5c9ac7f11",
        "tls": "16969f498a089885728c131e57af5688e5a6331f368a4eeb0d9ef7efcce65c36",
    }, "2678b1d02b68515660f1bc89c5145bc8513260f3be668b8a5ae4fd2e654ac942"),
])
def test_request_semantic_ids_equal_pre_repair_base(with_dhcp, request_sha, origin_shas, result_sha):
    _, _, service, profile = prepared(evidence_rows=[_dhcp_row()] if with_dhcp else ())
    result = candidate_run(service, profile)
    assert result.classification_request_manifest.artifact_id == (
        "ClassificationRequestManifest:v1:sha256:" + request_sha)
    ordered = sorted(result.origin_assessments, key=lambda item: item.semantic_payload["origin_group"])
    assert [(item.semantic_payload["origin_group"], item.artifact_id) for item in ordered] == [
        (origin, "OriginAssessment:v1:sha256:" + sha) for origin, sha in origin_shas.items()]
    assert result.classification_result.artifact_id == "ClassificationResult:v1:sha256:" + result_sha


def test_request_validates_knowledge_once_uses_private_matchers_and_drops_proof(monkeypatch):
    from dataclasses import fields
    import app.device_fingerprint.knowledge_bundle as module
    import app.device_fingerprint.knowledge_artifacts as k1
    import app.device_fingerprint.k4_ieee_import as k4
    import app.device_fingerprint.origin_assessment as origin
    import app.device_fingerprint.request_assembly as assembly
    hook_calls = []
    _, _, service, profile = prepared(
        evidence_rows=[_dhcp_row()], hook=lambda *args: hook_calls.append(args) or True)
    calls, proofs, matches = [], [], []
    original = module.validate_knowledge_bundle_dependencies
    factory = assembly._validate_knowledge_bundle_once
    k1_match = origin._match_k1_records_prevalidated
    k4_match = origin._match_k4_records_prevalidated

    def counted(bundle, candidate):
        calls.append((bundle, candidate))
        return original(bundle, candidate)

    def capture_proof(bundle, candidate):
        proof = factory(bundle, candidate)
        proofs.append(proof)
        return proof

    def private_k1(*args):
        matches.append("K1")
        return k1_match(*args)

    def private_k4(*args):
        matches.append("K4")
        return k4_match(*args)

    def forbidden(*_args, **_kwargs):
        pytest.fail("Validated request called a public full-validation matcher")

    monkeypatch.setattr(module, "validate_knowledge_bundle_dependencies", counted)
    monkeypatch.setattr(assembly, "_validate_knowledge_bundle_once", capture_proof)
    monkeypatch.setattr(k1, "match_k1_records", forbidden)
    monkeypatch.setattr(k4, "match_k4_records", forbidden)
    monkeypatch.setattr(origin, "_match_k1_records_prevalidated", private_k1)
    monkeypatch.setattr(origin, "_match_k4_records_prevalidated", private_k4)
    for request_index in range(2):
        result = candidate_run(service, profile)
        assert len(calls) == len(proofs) == request_index + 1
        assert matches.count("K1") == matches.count("K4") == request_index + 1
        assert len(hook_calls[-1]) == 7
        assert hook_calls[-1] == (
            result.classification_runtime_profile, result.foundation_runtime_profile,
            result.knowledge_bundle, result.knowledge_candidate, result.classification_policy,
            result.evidence_adapter_contract_set, result.classifier_artifact_manifest)
        assert all(not isinstance(getattr(result, field.name), module._ValidatedKnowledgeBundle)
                   for field in fields(result))
        for artifact in (result.classification_request_manifest, *result.origin_assessments,
                         result.classification_result):
            assert b"_ValidatedKnowledgeBundle" not in artifact.semantic_payload_json
            assert b"validated_knowledge" not in artifact.semantic_payload_json
    assert proofs[0] is not proofs[1] and proofs[0].candidate is not proofs[1].candidate
    with pytest.raises(DeviceFingerprintValidationError,
                       match="Invalid request-scoped KnowledgeBundle validation proof"):
        module._require_validated_knowledge(proofs[0], proofs[1].bundle, proofs[1].candidate)



def test_request_exact_seven_fields_digest_and_no_runtime_lineage():
    _, _, service, profile = prepared()
    result = candidate_run(service, profile)
    request = result.classification_request_manifest
    assert set(request.semantic_payload) == {
        "evidence_snapshot_content", "source_evaluability", "knowledge_bundle",
        "classification_policy", "evidence_adapter_contract_set",
        "classifier_artifact_manifest", "knowledge_evaluation_at_utc"}
    assert result.classification_result.semantic_payload["classification_request_digest"] == request.content_sha256
    assert profile.artifact_id.encode() not in request.semantic_payload_json
    assert b"RuntimeProfileActivationRecord" not in request.semantic_payload_json
    assert b"PRE_ACCEPTANCE_CANDIDATE" not in request.semantic_payload_json
    assert result.runtime_profile_activation_record is None
    assert result.pinned_runtime_profile is None


def test_request_constructor_rejects_extra_field_and_mismatched_refs():
    _, _, service, profile = prepared()
    result = candidate_run(service, profile)
    request = result.classification_request_manifest.semantic_payload
    contents = {name: getattr(result, name) for name in (
        "evidence_snapshot_content", "source_evaluability", "knowledge_bundle",
        "classification_policy", "evidence_adapter_contract_set",
        "classifier_artifact_manifest")}
    with pytest.raises(DeviceFingerprintValidationError):
        make_classification_request_manifest({**request, "site_id": SITE}, **contents)
    with pytest.raises(DeviceFingerprintValidationError):
        make_classification_request_manifest({**request, "knowledge_bundle": ref(result.classification_policy)},
                                             **contents)


def test_candidate_path_never_pins_and_profile_selection_is_not_product_api():
    _, store, service, profile = prepared()
    result = candidate_run(service, profile)
    assert result.classification_runtime_profile == profile
    assert result.foundation_runtime_profile == store.contents[
        profile.semantic_payload["foundation_runtime_profile"]["artifact_id"]]
    assert store.pins == []
    assert "candidate_classification_runtime_profile" not in signature(
        service.assemble_production).parameters


def test_negative_age_fails_before_request_and_result():
    _, _, service, profile = prepared(clock=lambda: "2026-09-16T12:00:00.000Z")
    with pytest.raises(RequestAssemblyError) as caught:
        candidate_run(service, profile)
    assert caught.value.reason_code == "negative_knowledge_age"


@pytest.mark.parametrize("hook", [None, lambda *_: False,
                                  lambda *_: (_ for _ in ()).throw(ValueError("blocked"))])
def test_compatibility_hook_fail_closed(hook):
    _, _, service, profile = prepared(hook=hook)
    with pytest.raises(RequestAssemblyError) as caught:
        candidate_run(service, profile)
    assert caught.value.reason_code == "runtime_profile_incompatible"


def test_knowledge_bundle_closure_and_six_origins_share_one_lineage():
    _, _, service, profile = prepared()
    result = candidate_run(service, profile)
    assert len(result.origin_assessments) == 6
    assert {item.semantic_payload["origin_group"] for item in result.origin_assessments} == {
        "dhcp", "portal", "tcp", "tls", "quic", "mac_registry"}
    for item in result.origin_assessments:
        payload = item.semantic_payload
        assert payload["evidence_snapshot_content"] == ref(result.evidence_snapshot_content)
        assert payload["source_evaluability"] == ref(result.source_evaluability)
    assert result.classification_request_manifest.semantic_payload["knowledge_bundle"] == ref(
        result.knowledge_bundle)
    assert result.classification_result.semantic_payload["knowledge_bundle"] == ref(result.knowledge_bundle)


def test_same_semantic_inputs_ignore_activation_and_later_wall_clock():
    _, _, service, profile = prepared()
    first = candidate_run(service, profile)
    _, _, second_service, second_profile = prepared()
    second = candidate_run(second_service, second_profile)
    assert first.classification_request_manifest == second.classification_request_manifest
    assert first.classification_result == second.classification_result


def test_production_pins_classification_once_and_never_reads_foundation_pointer():
    _, store, service, profile = prepared()
    pointer = ActiveProfilePointerV1(
        "classification", profile.artifact_id, profile.content_sha256,
        "11111111-1111-4111-8111-111111111111",
        "22222222-2222-4222-8222-222222222222", TIME)
    store.pinned = PinnedRuntimeProfile(
        pointer, profile, make_artifact_content("RuntimeProfileAdmissionManifest", {}),
        make_artifact_content("RuntimeProfileActivationRecord", {}),
        make_artifact_content("RuntimeProfileValidityRecord", {}))
    result = service.assemble_production(SITE, MAC, START, END)
    assert store.pins == ["classification"]
    assert result.pinned_runtime_profile is store.pinned
    assert result.foundation_runtime_profile == store.contents[
        profile.semantic_payload["foundation_runtime_profile"]["artifact_id"]]
    assert result.classification_runtime_profile == profile
    assert store.pinned.activation_record.artifact_id.encode() not in (
        result.classification_request_manifest.semantic_payload_json)
    _, _, candidate_service, candidate_profile = prepared()
    candidate_result = candidate_run(candidate_service, candidate_profile)
    assert result.classification_request_manifest == candidate_result.classification_request_manifest
    assert result.classification_result == candidate_result.classification_result


def test_expired_external_source_does_not_fail_request():
    _, _, service, profile = prepared(clock=lambda: "2028-09-22T22:30:34.464Z",
                                     evidence_rows=[_dhcp_row()])
    result = candidate_run(service, profile)
    assert result.classification_request_manifest.semantic_payload[
        "knowledge_evaluation_at_utc"] == "2028-09-22T22:30:34.464Z"
    dhcp = next(row for row in result.origin_assessments
                if row.semantic_payload["origin_group"] == "dhcp")
    platform = next(row for row in dhcp.semantic_payload["dimension_assessments"]
                    if row["dimension_name"] == "platform_family")
    assert platform["internal_state"] == "no_claim"
    assert "knowledge_source_expired" in platform["explanation_codes"]


def test_hook_receives_exact_resolved_semantic_set():
    calls = []

    def hook(*items):
        calls.append(items)
        return True

    _, _, service, profile = prepared(hook=hook)
    result = candidate_run(service, profile)
    assert len(calls) == 1
    assert calls[0] == (
        result.classification_runtime_profile, result.foundation_runtime_profile,
        result.knowledge_bundle, result.knowledge_candidate, result.classification_policy,
        result.evidence_adapter_contract_set, result.classifier_artifact_manifest)


def test_production_caller_cannot_supply_profile_or_knowledge_time():
    _, _, service, profile = prepared()
    parameters = signature(service.assemble_production).parameters
    assert set(parameters) == {"site_id", "observed_mac", "window_start_utc", "window_end_utc"}
    with pytest.raises(TypeError):
        service.assemble_production(SITE, MAC, START, END,
                                    candidate_classification_runtime_profile=profile)
    with pytest.raises(TypeError):
        service.assemble_production(SITE, MAC, START, END,
                                    knowledge_evaluation_at_utc="2020-01-01T00:00:00.000Z")


def test_active_pointer_switch_after_pin_does_not_change_inflight_semantics():
    _, store, service, profile = prepared()
    pointer = ActiveProfilePointerV1(
        "classification", profile.artifact_id, profile.content_sha256,
        "11111111-1111-4111-8111-111111111111",
        "22222222-2222-4222-8222-222222222222", TIME)
    store.pinned = PinnedRuntimeProfile(
        pointer, profile, make_artifact_content("RuntimeProfileAdmissionManifest", {}),
        make_artifact_content("RuntimeProfileActivationRecord", {}),
        make_artifact_content("RuntimeProfileValidityRecord", {}))
    original_pin = store.pin_active_profile

    def switch_after_pin(kind):
        pinned = original_pin(kind)
        store.profile = make_artifact_content("ClassificationRuntimeProfile", {"new": True})
        store.foundation_active = make_artifact_content("FoundationRuntimeProfile", {"new": True})
        return pinned

    store.pin_active_profile = switch_after_pin
    result = service.assemble_production(SITE, MAC, START, END)
    assert store.pins == ["classification"]
    assert result.classification_runtime_profile == profile
    assert result.foundation_runtime_profile.artifact_id == (
        profile.semantic_payload["foundation_runtime_profile"]["artifact_id"])
    assert result.classification_result.semantic_payload["classification_request_digest"] == (
        result.classification_request_manifest.content_sha256)


def test_noncanonical_knowledge_and_missing_immutable_dependency_are_incompatible():
    _, store, service, profile = prepared()
    malformed = make_artifact_content("KnowledgeBundle", {"noncanonical": True})
    with pytest.raises(RequestAssemblyError) as error:
        service.reconstruct_knowledge_bundle(malformed, service._resolve)
    assert error.value.reason_code == "runtime_profile_incompatible"
    bundle_id = profile.semantic_payload["knowledge_bundle"]["artifact_id"]
    original_load = store.load_artifact

    def missing_bundle(artifact_id, digest=None):
        if artifact_id == bundle_id:
            store.loads.append(artifact_id)
            raise ControlPlaneOperationError("runtime_profile_dependency_unavailable")
        return original_load(artifact_id, digest)

    store.load_artifact = missing_bundle
    with pytest.raises(RequestAssemblyError) as error:
        candidate_run(service, profile)
    assert error.value.reason_code == "runtime_profile_incompatible"
    assert store.loads.count(bundle_id) == 1
    assert store.pins == []


def test_proven_transient_knowledge_load_is_typed_without_fallback():
    _, store, service, profile = prepared()
    bundle_id = profile.semantic_payload["knowledge_bundle"]["artifact_id"]
    original_load = store.load_artifact

    def busy_bundle(artifact_id, digest=None):
        if artifact_id == bundle_id:
            store.loads.append(artifact_id)
            raise sqlite3.OperationalError("database is locked")
        return original_load(artifact_id, digest)

    store.load_artifact = busy_bundle
    with pytest.raises(RequestAssemblyError) as error:
        candidate_run(service, profile)
    assert error.value.reason_code == "knowledge_bundle_unavailable"
    assert store.loads.count(bundle_id) == 1
    assert store.pins == []


def test_missing_active_production_lineage_is_not_remapped_or_retried():
    _, store, service, _ = prepared()

    def missing_pin(kind):
        store.pins.append(kind)
        raise ControlPlaneOperationError("activation_lineage_unavailable")

    store.pin_active_profile = missing_pin
    with pytest.raises(RequestAssemblyError) as error:
        service.assemble_production(SITE, MAC, START, END)
    assert error.value.reason_code == "activation_lineage_unavailable"
    assert store.pins == ["classification"]
    assert store.loads == []
