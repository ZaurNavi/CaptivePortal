from copy import deepcopy

import pytest

from app.device_fingerprint.artifact_content import ArtifactRef
from app.device_fingerprint.k1_satori_import import (
    ACCEPTED_SATORI_AUDIT,
    SATORI_SOURCE_SHA256,
    _parse_verified_source,
    build_satori_source_governance_candidate,
    import_satori_dhcp_bytes,
)
from app.device_fingerprint.knowledge_artifacts import (
    match_k1_records,
    project_k1_candidate_dimensions,
)
from app.device_fingerprint.models import DeviceFingerprintValidationError

_DIGEST = "0" * 64
_PROVENANCE = ArtifactRef(
    artifact_id=f"KnowledgeProvenanceManifest:v1:sha256:{_DIGEST}",
    content_sha256=_DIGEST,
).as_dict()


def _xml(*fingerprints: str) -> bytes:
    return ("<root>" + "".join(fingerprints) + "</root>").encode("ascii")


def _fingerprint(taxonomy: str, tests: str) -> str:
    return f'<fingerprint os_class="Android" device_type="{taxonomy}">{tests}</fingerprint>'


def _evidence():
    return {
        "message_type": "discover",
        "parameter_request_list": [1, 3, 6],
        "option_order": [53, 55, 60],
        "vendor_class": None,
        "client_identifier_kind": "mac",
        "maximum_message_size": 1500,
        "rapid_commit_requested": False,
        "capport_requested": False,
        "ipv6_only_preferred_requested": False,
        "hostname_present": True,
    }


def test_synthetic_import_is_row_order_invariant():
    smartphone = _fingerprint(
        "Smartphone", '<test weight="9" matchtype="exact" dhcptype="Discover" dhcpoption55="1,3,6"/>',
    )
    tablet = _fingerprint(
        "Tablet", '<test weight="1" matchtype="exact" dhcptype="Discover" dhcpoption55="1,3,6"/>',
    )
    first = _parse_verified_source(_xml(smartphone, tablet), _PROVENANCE)
    second = _parse_verified_source(_xml(tablet, smartphone), _PROVENANCE)
    assert first.record_set.artifact_id == second.record_set.artifact_id
    assert first.audit == second.audit
    assert tuple(row["canonical_record_id"] for row in match_k1_records(
        first.record_set, _evidence(),
    )) == tuple(row["canonical_record_id"] for row in match_k1_records(
        second.record_set, _evidence(),
    ))


def test_weight_changes_cannot_rank_or_select_a_candidate():
    def imported(smartphone_weight: str, tablet_weight: str):
        return _parse_verified_source(_xml(
            _fingerprint(
                "Smartphone",
                f'<test weight="{smartphone_weight}" matchtype="exact" dhcptype="Discover" dhcpoption55="1,3,6"/>',
            ),
            _fingerprint(
                "Tablet",
                f'<test weight="{tablet_weight}" matchtype="exact" dhcptype="Discover" dhcpoption55="1,3,6"/>',
            ),
        ), _PROVENANCE).record_set

    for record_set in (imported("99", "1"), imported("1", "99")):
        candidates = match_k1_records(record_set, _evidence())
        assert len(candidates) == 2
        projection = project_k1_candidate_dimensions(candidates)
        assert projection["platform_family"]["canonical_values"] == ["android"]
        assert projection["device_class"]["canonical_values"] == ["smartphone", "tablet"]


def test_unsupported_or_mixed_source_predicates_are_quarantined_whole():
    source = _xml(_fingerprint("Smartphone", "".join((
        '<test weight="1" matchtype="exact" dhcptype="Discover" dhcpoption55="1,3,6" ipttl="64"/>',
        '<test weight="1" matchtype="exact" dhcptype="Discover" dhcpoption55="1,3,6" dhcpoptions="53,55,60"/>',
        '<test weight="1" matchtype="exact" dhcptype="ACK" dhcpoption55="1,3,6"/>',
        '<test weight="1" matchtype="partial" dhcptype="Discover" dhcpoption55="1,3,6"/>',
    ))))
    result = _parse_verified_source(source, _PROVENANCE)
    assert result.audit.source_tests_total == 4
    assert result.audit.source_tests_accepted == 0
    assert result.audit.source_tests_rejected == 4
    assert result.record_set.semantic_payload["records"] == []


def test_exact_signal_and_message_mappings_are_admitted_without_scoring():
    tests = "".join((
        '<test weight="9" matchtype="exact" dhcptype="Request" dhcpoptions="53,55,60"/>',
        '<test weight="1" matchtype="exact" dhcptype="Inform" dhcpvendorcode="SyntheticVendor"/>',
        '<test weight="5" matchtype="exact" dhcptype="Any" dhcpoption55="1,3,6"/>',
    ))
    result = _parse_verified_source(_xml(_fingerprint("Laptop", tests)), _PROVENANCE)
    records = result.record_set.semantic_payload["records"]
    assert result.audit.source_tests_accepted == 3
    assert {row["dhcp_predicates"]["message_type"]["mode"] for row in records} == {
        "ANY", "EXACT_VALUE",
    }
    assert {next(
        key for key in ("parameter_request_list", "option_order", "vendor_class")
        if row["dhcp_predicates"][key]["mode"] != "ANY"
    ) for row in records} == {"parameter_request_list", "option_order", "vendor_class"}


def test_public_import_requires_exact_pinned_bytes_and_audit():
    assert SATORI_SOURCE_SHA256 == "4f64a405fb1debbd2e066478a7190b821424e0691399068421fdaf168da09b14"
    assert ACCEPTED_SATORI_AUDIT.source_tests_accepted == 903
    with pytest.raises(DeviceFingerprintValidationError, match="digest mismatch"):
        import_satori_dhcp_bytes(b"<root/>", _PROVENANCE)


def test_source_governance_candidate_has_frozen_local_only_scope():
    artifact = build_satori_source_governance_candidate()
    payload = artifact.semantic_payload
    assert artifact.artifact_type == "SourceGovernanceRecord"
    assert payload["license_text_sha256"] is None
    assert payload["local_storage_status"] == "STORED_LOCAL"
    assert payload["modification_import_status"] == "IMPORTED_NORMALIZED"
    assert payload["redistribution_status"] == "NOT_APPLICABLE"
    assert payload["unresolved_restrictions"] == []
    assert "not vendored, committed, or redistributed" in payload["review_basis_semantics"]
