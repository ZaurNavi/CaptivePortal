"""Builder-only A1 checks; these do not execute any Foundation gate."""

from app.device_fingerprint.classification_policy import build_initial_classification_policy_v1
from app.device_fingerprint.evidence_adapter_contracts import (
    build_initial_evidence_adapter_contract_set_v1,
    build_utility_repair_a1_evidence_adapter_contract_set_v1,
    make_evidence_adapter_contract_set,
)
from app.device_fingerprint.fe5_external_knowledge import build_satori_k1_freshness_policy
from app.device_fingerprint.foundation_schema_artifacts import build_foundation_schema_artifacts
from app.device_fingerprint.taxonomy_artifacts import (
    build_alias_mapping_v1, build_classification_taxonomy_v1,
)


def _contracts():
    registry = build_foundation_schema_artifacts()["EvidenceSchemaRegistryContract"]
    return (build_initial_evidence_adapter_contract_set_v1(registry),
            build_utility_repair_a1_evidence_adapter_contract_set_v1(registry))


def test_a1_changes_only_three_ceilings_not_historical_initial_contract():
    historical, repaired = _contracts()
    assert historical.artifact_id != repaired.artifact_id
    expected = historical.semantic_payload
    promoted = []
    for entry in expected["adapter_entries"]:
        if (entry["adapter_kind"] == "TASK01_EVIDENCE"
                and entry["source_kind"] in {"dhcp", "portal_headers"}):
            entry["base_claim_strength_ceiling"] = "strong"
            promoted.append((entry["source_kind"], entry["feature_schema_version"]))
    assert set(promoted) == {("dhcp", 1), ("portal_headers", 1), ("portal_headers", 2)}
    assert repaired.semantic_payload == expected
    assert historical.content_sha256 == "7cca6802ebc5839317643dcb584173b75d985477da687ab0d8fe5802b181f788"


def test_a1_contract_is_deterministic_under_input_order_permutation():
    historical, repaired = _contracts()
    payload = repaired.semantic_payload
    payload["adapter_entries"].reverse()
    assert make_evidence_adapter_contract_set(payload).artifact_id == repaired.artifact_id
    assert _contracts() == (historical, repaired)


def test_classification_policy_changes_only_eacs_reference():
    historical, repaired = _contracts()
    taxonomy = build_classification_taxonomy_v1()
    aliases = build_alias_mapping_v1()
    old = build_initial_classification_policy_v1(taxonomy, aliases, historical)
    new = build_initial_classification_policy_v1(taxonomy, aliases, repaired)
    expected = old.semantic_payload
    expected["evidence_adapter_contract_set"] = {
        "artifact_id": repaired.artifact_id, "content_sha256": repaired.content_sha256,
    }
    assert new.semantic_payload == expected
    assert new.artifact_id != old.artifact_id


def test_a1_does_not_change_satori_freshness_limits_or_caps():
    payload = build_satori_k1_freshness_policy().semantic_payload
    assert (payload["fresh_max_age_ms"], payload["stale_max_age_ms"]) == (
        31536000000, 63072000000,
    )
    assert [(row["freshness_state"], row["claim_eligible"], row["claim_strength_cap"])
            for row in payload["freshness_state_rules"]] == [
        ("fresh", True, "NO_ADDITIONAL_CAP"),
        ("stale", True, "supporting"),
        ("expired", False, "NONE"),
    ]
