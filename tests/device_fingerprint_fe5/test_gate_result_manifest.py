from copy import deepcopy

import pytest

from app.device_fingerprint.artifact_content import ArtifactRef
from app.device_fingerprint.foundation_gate_artifacts import make_gate_result_manifest
from app.device_fingerprint.models import DeviceFingerprintValidationError

_EXECUTION_ID = "11111111-1111-4111-8111-111111111111"
_DECISION_ID = "22222222-2222-4222-8222-222222222222"


def _ref(digit):
    digest = digit * 64
    return ArtifactRef(f"Fixture:v1:sha256:{digest}", digest).as_dict()


def _payload():
    return {
        "gate_id": "F-E5", "gate_contract_version": "R14-F-E5-v1",
        "status": "PASS", "candidate_repository_commit_sha": "a" * 40,
        "candidate_repository_tree_sha": "b" * 40,
        "input_artifact_refs": [_ref("d"), _ref("c")],
        "output_artifact_refs": [_ref("d"), _ref("c")],
        "retained_evidence_refs": [
            {"evidence_label": "zeta", "file_sha256": "f" * 64,
             "media_type": "application/json", "path_or_reference": None},
            {"evidence_label": "alpha", "file_sha256": "e" * 64,
             "media_type": "text/plain", "path_or_reference": "retained://fixture"},
        ],
        "proof_execution_identity": {
            "execution_id": _EXECUTION_ID, "executor_kind": "TECHLEAD_GATE_TOOL",
            "repository_commit_sha": "a" * 40, "repository_tree_sha": "b" * 40,
            "procedure_or_test_suite_id": "F-E5-external-freshness-governance-v1",
            "environment_identity": "synthetic-test", "execution_artifact_sha256": None,
        },
        "trusted_time_inputs": {
            "foundation_knowledge_evaluation_at_utc": "2026-09-23T12:00:00.000Z",
            "foundation_admission_evaluation_at_utc": None,
            "knowledge_evaluation_at_utc": None,
        },
        "decision_record_refs": [_DECISION_ID, _EXECUTION_ID],
    }


def test_exact_gate_manifest_ordering_and_permutation_identity():
    payload = _payload()
    artifact = make_gate_result_manifest(payload)
    semantic = artifact.semantic_payload
    assert [r["artifact_id"] for r in semantic["input_artifact_refs"]] == [
        _ref("c")["artifact_id"], _ref("d")["artifact_id"],
    ]
    assert [r["evidence_label"] for r in semantic["retained_evidence_refs"]] == ["alpha", "zeta"]
    assert semantic["decision_record_refs"] == [_EXECUTION_ID, _DECISION_ID]
    reverse = deepcopy(payload)
    for field in ("input_artifact_refs", "output_artifact_refs",
                  "retained_evidence_refs", "decision_record_refs"):
        reverse[field].reverse()
    assert make_gate_result_manifest(reverse).artifact_id == artifact.artifact_id


@pytest.mark.parametrize("mutate", [
    lambda p: p.update(extra="no"),
    lambda p: p.update(status="PENDING"),
    lambda p: p.update(candidate_repository_commit_sha="ABC"),
    lambda p: p["proof_execution_identity"].update(execution_id="11111111-1111-1111-8111-111111111111"),
    lambda p: p["proof_execution_identity"].update(execution_id="11111111-1111-4111-8111-11111111111A"),
    lambda p: p["proof_execution_identity"].update(repository_tree_sha="invalid"),
    lambda p: p["proof_execution_identity"].update(extra="no"),
    lambda p: p["trusted_time_inputs"].update(foundation_knowledge_evaluation_at_utc="2026-09-23T12:00:00Z"),
    lambda p: p["trusted_time_inputs"].update(extra="no"),
    lambda p: p["retained_evidence_refs"][0].update(file_sha256="invalid"),
    lambda p: p["retained_evidence_refs"][0].update(extra="no"),
    lambda p: p["decision_record_refs"].append("NOT-UUID"),
    lambda p: p["decision_record_refs"].append(p["decision_record_refs"][0]),
    lambda p: p["input_artifact_refs"].append(p["input_artifact_refs"][0]),
])
def test_gate_manifest_fails_closed_on_bad_shape_identity_or_duplicate(mutate):
    payload = _payload()
    mutate(payload)
    with pytest.raises(DeviceFingerprintValidationError):
        make_gate_result_manifest(payload)


def test_generic_gate_manifest_permits_empty_sets_for_fail_result():
    payload = _payload()
    payload.update(status="FAIL", output_artifact_refs=[],
                   retained_evidence_refs=[], decision_record_refs=[])
    artifact = make_gate_result_manifest(payload)
    assert artifact.semantic_payload["status"] == "FAIL"
    assert artifact.semantic_payload["output_artifact_refs"] == []
