from copy import deepcopy
import csv
import hashlib
import io

import pytest

from app.device_fingerprint.artifact_content import ArtifactRef, canonical_artifact_json
from app.device_fingerprint.k4_ieee_import import (
    build_ieee_k4_source_governance_candidate,
    compute_ieee_k4_source_bundle_sha256,
    import_ieee_k4_bytes,
    is_ieee_assignment_lookup_eligible,
    match_k4_records,
)
from app.device_fingerprint.knowledge_artifacts import make_canonical_k4_record_set
from app.device_fingerprint.models import DeviceFingerprintValidationError

def _csv(*rows, bom=False):
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(("Registry", "Assignment", "Organization Name", "Organization Address"))
    writer.writerows(rows)
    data = output.getvalue().encode("utf-8")
    return (b"\xef\xbb\xbf" + data) if bom else data


def _provenance():
    digest = "a" * 64
    return ArtifactRef(f"KnowledgeProvenanceManifest:v1:sha256:{digest}", digest)


def _import(l=(), m=(), s=()):
    return import_ieee_k4_bytes(
        _csv(*l), _csv(*m), _csv(*s), knowledge_provenance=_provenance(),
    )


def _record(family="MA-L", prefix="001122", bits=24):
    row = ((family, prefix, "Org A", "Address"),)
    return _import(l=row if family == "MA-L" else (),
                   m=row if family == "MA-M" else (),
                   s=row if family == "MA-S" else ()).semantic_payload["records"][0]


def _set_with(record):
    return {
        "record_set_contract_version": 1, "knowledge_slot": "K4",
        "knowledge_provenance": _provenance().as_dict(), "records": [record],
    }


@pytest.mark.parametrize("family,prefix,bits", [
    ("MA-L", "001122", 24), ("MA-M", "0011223", 28),
    ("MA-S", "001122334", 36),
])
def test_exact_k4_record_shape_and_prefix_pairing(family, prefix, bits):
    record = _record(family, prefix, bits)
    assert record["registry_family"] == family
    assert record["prefix_length_bits"] == bits
    assert record["prefix_hex"] == prefix
    assert record["manufacturer_mapping"] is None
    assert make_canonical_k4_record_set(_set_with(record)).semantic_payload["records"] == [record]


@pytest.mark.parametrize("mutation", [
    lambda r: r.update(extra="no"),
    lambda r: r.update(record_type="K1_DHCP"),
    lambda r: r.update(prefix_hex="00112G"),
    lambda r: r.update(prefix_hex="00:11:22"),
    lambda r: r.update(prefix_hex="0011223"),
    lambda r: r.update(prefix_hex="00112A"),
    lambda r: r.update(prefix_length_bits=28),
    lambda r: r.update(registry_family="MA-M"),
    lambda r: r.update(registry_family="unknown"),
])
def test_k4_record_validation_fails_closed(mutation):
    record = _record()
    mutation(record)
    with pytest.raises(DeviceFingerprintValidationError):
        make_canonical_k4_record_set(_set_with(record))


def test_k4_slot_and_future_explicit_mapping_validation():
    record = _record()
    payload = _set_with(record)
    payload["knowledge_slot"] = "K1"
    with pytest.raises(DeviceFingerprintValidationError):
        make_canonical_k4_record_set(payload)
    mapping = {
        "manufacturer_id": "canonical-maker", "mapping_version": "reviewed-v1",
        "review_basis": "reviewed explicit assignment mapping",
        "base_claim_strength": "supporting",
    }
    record["manufacturer_mapping"] = mapping
    assert make_canonical_k4_record_set(_set_with(record)).semantic_payload["records"][0][
        "manufacturer_mapping"
    ] == mapping
    for change in ({"base_claim_strength": "certain"}, {"extra": "no"},
                   {"manufacturer_id": ""}):
        invalid = deepcopy(record)
        invalid["manufacturer_mapping"].update(change)
        with pytest.raises(DeviceFingerprintValidationError):
            make_canonical_k4_record_set(_set_with(invalid))


def test_import_accepts_exact_header_utf8_sig_uppercase_and_nfc():
    l = _csv(("MA-L", "0011AB", "Cafe\u0301", "Address"), bom=True)
    artifact = import_ieee_k4_bytes(l, _csv(), _csv(), knowledge_provenance=_provenance())
    record = artifact.semantic_payload["records"][0]
    assert record["prefix_hex"] == "0011ab"
    assert record["assignment_org_label"] == "Caf\u00e9"
    assert record["manufacturer_mapping"] is None


@pytest.mark.parametrize("malformed", [
    b"Registry,Assignment,Organization Name\nMA-L,001122,Org\n",
    b"Registry,Assignment,Organization Name,Organization Address\nMA-M,001122,Org,Addr\n",
    b"Registry,Assignment,Organization Name,Organization Address\nMA-L,0011223,Org,Addr\n",
    b"Registry,Assignment,Organization Name,Organization Address\nMA-L,00112G,Org,Addr\n",
    b"Registry,Assignment,Organization Name,Organization Address\nMA-L,001122,,Addr\n",
    b"Registry,Assignment,Organization Name,Organization Address\nMA-L,001122,Org\n",
    b"Registry,Assignment,Organization Name,Organization Address\nMA-L,001122,Org,Addr,Extra\n",
    b"Registry,Assignment,Organization Name,Organization Address\nMA-L,001122,Org,Addr\n\xff",
])
def test_import_rejects_malformed_would_be_source_rows(malformed):
    with pytest.raises(DeviceFingerprintValidationError):
        import_ieee_k4_bytes(malformed, _csv(), _csv(), knowledge_provenance=_provenance())


def test_public_org_identity_is_exact_and_private_is_assignment_scoped():
    rows = (
        ("MA-L", "001122", "Apple Inc.", "Address One"),
        ("MA-L", "001123", "Apple Inc.", "Address Two"),
        ("MA-L", "001124", "Apple, Inc.", "Address Three"),
        ("MA-L", "001125", "APPLE INC.", "Address Four"),
        ("MA-L", "001126", "Private", "Address Five"),
        ("MA-L", "001127", "Private", "Address Six"),
    )
    records = _import(l=rows).semantic_payload["records"]
    by_prefix = {record["prefix_hex"]: record for record in records}
    assert by_prefix["001122"]["assignment_org_id"] == by_prefix["001123"]["assignment_org_id"]
    assert len({by_prefix[p]["assignment_org_id"] for p in ("001122", "001124", "001125")}) == 3
    assert by_prefix["001126"]["assignment_org_id"] != by_prefix["001127"]["assignment_org_id"]
    assert by_prefix["001126"]["assignment_org_label"] == "Private"
    assert _import(l=tuple(reversed(rows))).artifact_id == _import(l=rows).artifact_id


def test_address_and_row_position_do_not_affect_semantic_record_identity():
    first = _import(l=(("MA-L", "001122", "Org A", "Address One"),))
    second = _import(l=(("MA-L", "001122", "Org A", "Completely Different"),))
    assert first.artifact_id == second.artifact_id
    assert first.semantic_payload["records"][0]["source_record_identity"] == second.semantic_payload["records"][0]["source_record_identity"]


def test_duplicate_prefix_collapses_only_identical_assignment_semantics():
    rows = (
        ("MA-L", "001122", "Org A", "Address 1"),
        ("MA-L", "001122", "Org A", "Address 2"),
        ("MA-L", "001122", "Org B", "Address 3"),
    )
    first = _import(l=rows)
    second = _import(l=tuple(reversed(rows)))
    assert first.artifact_id == second.artifact_id
    records = first.semantic_payload["records"]
    assert len(records) == 2
    assert {r["assignment_org_label"] for r in records} == {"Org A", "Org B"}
    assert all(r["manufacturer_mapping"] is None for r in records)


def test_bundle_identity_uses_exact_ordered_metadata_and_changes_with_bytes():
    sources = (b"L", b"M", b"S")
    expected_members = [
        {"registry_family": "MA-L", "filename": "oui.csv",
         "source_url": "https://standards-oui.ieee.org/oui/oui.csv",
         "sha256": hashlib.sha256(b"L").hexdigest(), "size_bytes": 1},
        {"registry_family": "MA-M", "filename": "mam.csv",
         "source_url": "https://standards-oui.ieee.org/oui28/mam.csv",
         "sha256": hashlib.sha256(b"M").hexdigest(), "size_bytes": 1},
        {"registry_family": "MA-S", "filename": "oui36.csv",
         "source_url": "https://standards-oui.ieee.org/oui36/oui36.csv",
         "sha256": hashlib.sha256(b"S").hexdigest(), "size_bytes": 1},
    ]
    expected = hashlib.sha256(canonical_artifact_json({
        "bundle_identity_version": "ieee_ra_k4_source_bundle_v1",
        "members": expected_members,
    })).hexdigest()
    assert compute_ieee_k4_source_bundle_sha256(*sources) == expected
    assert compute_ieee_k4_source_bundle_sha256(b"L", b"M!", b"S") != expected
    assert compute_ieee_k4_source_bundle_sha256(b"M", b"L", b"S") != expected


@pytest.mark.parametrize("invalid", [
    "00:11:22:33:44", "00:11:22:33:44:GG", "00:11:22:33:44:55:66",
    "00-11-22-33-44-55", "AA:11:22:33:44:55", "001122334455",
])
def test_mac48_validation_rejects_noncanonical_forms(invalid):
    with pytest.raises(DeviceFingerprintValidationError):
        is_ieee_assignment_lookup_eligible(invalid)


def test_locally_administered_mac_cannot_be_transformed_into_a_k4_claim():
    records = _import(l=(("MA-L", "021122", "Org A", "Addr"),
                         ("MA-L", "061122", "Org B", "Addr"),
                         ("MA-L", "001122", "Org C", "Addr")))
    assert not is_ieee_assignment_lookup_eligible("02:11:22:33:44:55")
    assert not is_ieee_assignment_lookup_eligible("06:11:22:33:44:55")
    assert is_ieee_assignment_lookup_eligible("00:11:22:33:44:55")
    assert match_k4_records(records, "02:11:22:33:44:55") == ()
    assert match_k4_records(records, "06:11:22:33:44:55") == ()
    assert [r["assignment_org_label"] for r in match_k4_records(records, "00:11:22:33:44:55")] == ["Org C"]


def test_longest_prefix_includes_all_selected_ambiguous_records_only():
    records = _import(
        l=(("MA-L", "001122", "Org L", "Addr"),),
        m=(("MA-M", "0011223", "Org M", "Addr"),),
        s=(("MA-S", "001122334", "Org S1", "Addr"),
           ("MA-S", "001122334", "Org S2", "Addr")),
    )
    selected = match_k4_records(records, "00:11:22:33:44:55")
    assert {r["assignment_org_label"] for r in selected} == {"Org S1", "Org S2"}
    assert len(selected) == 2
    assert [r["assignment_org_label"] for r in match_k4_records(records, "00:11:22:3f:44:55")] == ["Org M"]
    assert [r["assignment_org_label"] for r in match_k4_records(records, "00:11:22:ff:44:55")] == ["Org L"]
    assert match_k4_records(records, "00:22:22:33:44:55") == ()


def test_governance_candidate_is_deterministic_and_does_not_invent_freshness():
    artifact = build_ieee_k4_source_governance_candidate()
    assert artifact.artifact_id == build_ieee_k4_source_governance_candidate().artifact_id
    payload = artifact.semantic_payload
    assert payload["license_text_sha256"] is None
    assert payload["local_storage_status"] == "STORED_LOCAL"
    assert payload["modification_import_status"] == "IMPORTED_NORMALIZED"
    assert payload["redistribution_status"] == "ALLOWED"
    assert payload["attribution_requirement"] == "NOT_REQUIRED"
    assert payload["commercial_use_status"] == "ALLOWED"
    assert "F-E5 owns exact freshness age thresholds" in payload["review_basis_semantics"]
