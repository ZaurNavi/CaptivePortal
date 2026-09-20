"""Small deterministic, non-Satori K1 fixtures for Foundation F-E1 gates."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.device_fingerprint.artifact_content import ArtifactRef
from app.device_fingerprint.knowledge_artifacts import make_canonical_k1_record_set

_FIXTURE_DIGEST = "0" * 64
_FIXTURE_PROVENANCE = ArtifactRef(
    artifact_id=f"KnowledgeProvenanceManifest:v1:sha256:{_FIXTURE_DIGEST}",
    content_sha256=_FIXTURE_DIGEST,
).as_dict()


def _any_predicates() -> dict[str, dict[str, Any]]:
    return {
        "message_type": {"mode": "ANY"},
        "parameter_request_list": {"mode": "ANY"},
        "option_order": {"mode": "ANY"},
        "vendor_class": {"mode": "ANY"},
        "client_identifier_kind": {"mode": "ANY"},
        "maximum_message_size": {"mode": "ANY"},
        "rapid_commit_requested": {"mode": "ANY"},
        "capport_requested": {"mode": "ANY"},
        "ipv6_only_preferred_requested": {"mode": "ANY"},
        "hostname_present": {"mode": "ANY"},
    }

def _full_exact_predicates() -> dict[str, dict[str, Any]]:
    return {
        "message_type": {"mode": "EXACT_VALUE", "value": "discover"},
        "parameter_request_list": {"mode": "EXACT_SEQUENCE", "value": [1, 3, 6, 15]},
        "option_order": {"mode": "EXACT_SEQUENCE", "value": [53, 55, 60]},
        "vendor_class": {"mode": "EXACT_NULL"},
        "client_identifier_kind": {"mode": "EXACT_VALUE", "value": "mac"},
        "maximum_message_size": {"mode": "EXACT_VALUE", "value": 1500},
        "rapid_commit_requested": {"mode": "EXACT_VALUE", "value": False},
        "capport_requested": {"mode": "EXACT_VALUE", "value": True},
        "ipv6_only_preferred_requested": {"mode": "EXACT_VALUE", "value": False},
        "hostname_present": {"mode": "EXACT_VALUE", "value": True},
    }


def _outcome(dimension: str, target: str | None) -> dict[str, Any]:
    return {
        "dimension_name": dimension,
        "outcome_kind": "CANONICAL_VALUE" if target is not None else "NO_CLAIM",
        "canonical_target_id": target,
        "broad_taxon_ref": None,
        "out_of_scope_taxon_ref": None,
        "base_claim_strength": "supporting" if target is not None else None,
    }


def _record(identity: str, device_class: str, predicates: dict[str, Any]) -> dict[str, Any]:
    return {
        "record_type": "K1_DHCP",
        "canonical_record_id": f"fixture:{identity}",
        "dhcp_predicates": predicates,
        "candidate_taxonomy_refs": [
            _outcome("platform_family", "android"),
            _outcome("device_class", device_class),
            _outcome("manufacturer_family", None),
            _outcome("model_family", None),
        ],
        "source_record_identity": f"synthetic-source:{identity}",
    }


def _evidence() -> dict[str, Any]:
    return {
        "message_type": "discover",
        "parameter_request_list": [1, 3, 6, 15],
        "option_order": [53, 55, 60],
        "vendor_class": None,
        "client_identifier_kind": "mac",
        "maximum_message_size": 1500,
        "rapid_commit_requested": False,
        "capport_requested": True,
        "ipv6_only_preferred_requested": False,
        "hostname_present": True,
    }


def _record_set(records: list[dict[str, Any]]):
    return make_canonical_k1_record_set({
        "record_set_contract_version": 1,
        "knowledge_slot": "K1",
        "knowledge_provenance": _FIXTURE_PROVENANCE,
        "records": records,
    })


def build_k1_fixture_definitions() -> dict[str, Any]:
    """Return deterministic definitions used by Owner/Tech Lead F-E1 execution."""
    exact_records = [
        _record("android-smartphone", "smartphone", _full_exact_predicates()),
        _record("android-tablet", "tablet", _full_exact_predicates()),
    ]
    matching = _evidence()
    mismatch = deepcopy(matching)
    mismatch["hostname_present"] = False
    any_record = _record("all-any", "smartphone", _any_predicates())
    vendor_record_predicates = _any_predicates()
    vendor_record_predicates["vendor_class"] = {
        "mode": "EXACT_VALUE", "value": "SyntheticVendor",
    }
    vendor_record = _record("vendor-exact", "tablet", vendor_record_predicates)
    return {
        "all_any": {
            "record_set": _record_set([any_record]),
            "evidence": deepcopy(matching),
            "expected_candidate_ids": ("fixture:all-any",),
        },
        "all_non_any_multi_candidate": {
            "record_set": _record_set(exact_records),
            "evidence": deepcopy(matching),
            "expected_candidate_ids": (
                "fixture:android-smartphone", "fixture:android-tablet",
            ),
            "expected_platform_values": ("android",),
            "expected_device_class_values": ("smartphone", "tablet"),
        },
        "one_non_any_mismatch": {
            "record_set": _record_set(exact_records),
            "evidence": mismatch,
            "expected_candidate_ids": (),
        },
        "row_order_permutation": {
            "first": _record_set(exact_records),
            "second": _record_set(list(reversed(exact_records))),
            "evidence": deepcopy(matching),
        },
        "nullable_exact_value": {
            "record_set": _record_set([vendor_record]),
            "evidence": {**deepcopy(matching), "vendor_class": "SyntheticVendor"},
            "expected_candidate_ids": ("fixture:vendor-exact",),
        },
    }
