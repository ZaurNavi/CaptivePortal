#!/usr/bin/env python3
import hashlib
import json
import os
import sys
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

# Owner-authorized source pin for CaptivPortal F-E1 research.
REPO = "xnih/satori"
SOURCE_COMMIT = "c5dfcfbff31620e35248aa86da0c67f2ad4982f5"
SOURCE_PATH = "fingerprints/dhcp.xml"
EXPECTED_GIT_BLOB_SHA1 = "a82926690c28d2147534f24bdbdbeb0d1a2970fb"
SOURCE_URL = f"https://raw.githubusercontent.com/{REPO}/{SOURCE_COMMIT}/{SOURCE_PATH}"

OUT_DIR = Path("satori-k1-fe1-audit")
SOURCE_FILE = OUT_DIR / "satori-dhcp-source.xml"
AUDIT_JSON = OUT_DIR / "satori-k1-audit.json"
AUDIT_MD = OUT_DIR / "satori-k1-audit.md"
RECORDS_JSONL = OUT_DIR / "satori-k1-candidate-records.jsonl"
REJECTS_JSONL = OUT_DIR / "satori-k1-rejected-source-tests.jsonl"
AMBIGUITY_JSON = OUT_DIR / "satori-k1-ambiguity-groups.json"
FIXTURES_JSON = OUT_DIR / "satori-k1-fixture-matrix.json"

# Frozen import scope proposed by Tech Lead for F-E1.
SUPPORTED_MESSAGE_TYPES = {
    "Discover": "discover",
    "Request": "request",
    "Inform": "inform",
    "Decline": "decline",
    "Release": "release",
}
SERVER_SIDE_OR_UNSUPPORTED_MESSAGE_TYPES = {"ACK", "Offer", "NAK"}
SUPPORTED_SIGNAL_ATTRS = {"dhcpoption55", "dhcpoptions", "dhcpvendorcode"}
META_ATTRS = {"weight", "matchtype", "dhcptype"}

# Conservative direct V1 taxonomy mapping only. No name heuristics.
PLATFORM_MAP = {
    "Android": "android",
    "iOS": "ios",
    "Windows": "windows",
    "Mac OS": "macos",
    "ChromeOS": "chromeos",
    "Linux": "linux",
}
DEVICE_CLASS_MAP = {
    "Smartphone": "smartphone",
    "Tablet": "tablet",
    "tablet": "tablet",
    "Laptop": "laptop",
}

# Deliberately conservative source authority for this community fingerprint corpus.
BASE_CLAIM_STRENGTH = "supporting"
IMPORTER_ID = "captivportal-satori-k1-audit-v1"


def canonical_json_bytes(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git_blob_sha1(data: bytes) -> str:
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()


def fetch_source():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(
        SOURCE_URL,
        headers={"User-Agent": "CaptivPortal-FE1-Research/1.0"},
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        data = r.read()
    actual_blob = git_blob_sha1(data)
    if actual_blob != EXPECTED_GIT_BLOB_SHA1:
        raise SystemExit(
            "SOURCE PIN FAILURE: Git blob SHA mismatch\n"
            f"expected={EXPECTED_GIT_BLOB_SHA1}\nactual={actual_blob}\n"
        )
    SOURCE_FILE.write_bytes(data)
    return data


def parse_sequence(raw):
    if raw is None:
        raise ValueError("missing sequence")
    if raw == "":
        return []
    parts = raw.split(",")
    vals = []
    for p in parts:
        if p == "":
            raise ValueError("empty sequence element")
        v = int(p, 10)
        if not (0 <= v <= 255):
            raise ValueError(f"out-of-range option code {v}")
        vals.append(v)
    if len(vals) > 64:
        raise ValueError(f"sequence length {len(vals)} > 64")
    return vals


def printable_ascii_1_128(raw):
    if raw is None:
        return False
    try:
        b = raw.encode("ascii")
    except UnicodeEncodeError:
        return False
    return 1 <= len(b) <= 128 and all(0x20 <= x <= 0x7E for x in b)


def any_scalar():
    return {"mode": "ANY"}


def any_seq():
    return {"mode": "ANY"}


def exact_scalar(v):
    return {"mode": "EXACT_VALUE", "value": v}


def exact_seq(v):
    return {"mode": "EXACT_SEQUENCE", "value": v}


def empty_predicates():
    return {
        "message_type": any_scalar(),
        "parameter_request_list": any_seq(),
        "option_order": any_seq(),
        "vendor_class": any_scalar(),
        "client_identifier_kind": any_scalar(),
        "maximum_message_size": any_scalar(),
        "rapid_commit_requested": any_scalar(),
        "capport_requested": any_scalar(),
        "ipv6_only_preferred_requested": any_scalar(),
        "hostname_present": any_scalar(),
    }


def taxonomy_outcomes(fp_attrs):
    outcomes = []
    source_os_class = fp_attrs.get("os_class", "")
    source_device_type = fp_attrs.get("device_type", "")

    if source_os_class in PLATFORM_MAP:
        outcomes.append({
            "dimension_name": "platform_family",
            "outcome_kind": "CANONICAL_VALUE",
            "canonical_target_id": PLATFORM_MAP[source_os_class],
            "broad_taxon_ref": None,
            "out_of_scope_taxon_ref": None,
            "base_claim_strength": BASE_CLAIM_STRENGTH,
        })

    if source_device_type in DEVICE_CLASS_MAP:
        outcomes.append({
            "dimension_name": "device_class",
            "outcome_kind": "CANONICAL_VALUE",
            "canonical_target_id": DEVICE_CLASS_MAP[source_device_type],
            "broad_taxon_ref": None,
            "out_of_scope_taxon_ref": None,
            "base_claim_strength": BASE_CLAIM_STRENGTH,
        })

    outcomes.sort(key=lambda x: canonical_json_bytes(x))
    return outcomes


def source_test_identity(fp_attrs, test_attrs):
    # Identity is content-derived and independent of XML row position/order.
    # Include source taxonomy fields and source test attributes, including weight,
    # so provenance points to the exact source claim; importer semantics still ignore weight.
    payload = {
        "source": "satori-dhcp",
        "fingerprint": {
            "name": fp_attrs.get("name", ""),
            "os_name": fp_attrs.get("os_name", ""),
            "os_class": fp_attrs.get("os_class", ""),
            "os_vendor": fp_attrs.get("os_vendor", ""),
            "device_type": fp_attrs.get("device_type", ""),
            "device_vendor": fp_attrs.get("device_vendor", ""),
            "author": fp_attrs.get("author", ""),
            "last_updated": fp_attrs.get("last_updated", ""),
        },
        "test": dict(sorted(test_attrs.items())),
    }
    digest = sha256_hex(canonical_json_bytes(payload))
    return f"satori-dhcp-test:v1:sha256:{digest}", payload


def record_id(predicates, outcomes, source_identity):
    payload = {
        "record_type": "K1_DHCP",
        "dhcp_predicates": predicates,
        "candidate_taxonomy_refs": outcomes,
        "source_record_identity": source_identity,
    }
    return f"k1-satori:v1:sha256:{sha256_hex(canonical_json_bytes(payload))}"


def classify_test(fp_attrs, test_attrs):
    reasons = []
    matchtype = test_attrs.get("matchtype")
    dhcptype = test_attrs.get("dhcptype")

    if matchtype != "exact":
        reasons.append("unsupported_matchtype")

    if dhcptype == "Any":
        normalized_message = None
    elif dhcptype in SUPPORTED_MESSAGE_TYPES:
        normalized_message = SUPPORTED_MESSAGE_TYPES[dhcptype]
    elif dhcptype in SERVER_SIDE_OR_UNSUPPORTED_MESSAGE_TYPES:
        normalized_message = None
        reasons.append("unsupported_message_type")
    else:
        normalized_message = None
        reasons.append("unknown_message_type")

    signal_fields = sorted(set(test_attrs) & SUPPORTED_SIGNAL_ATTRS)
    nonmeta_fields = set(test_attrs) - META_ATTRS
    unsupported_nonmeta = sorted(nonmeta_fields - SUPPORTED_SIGNAL_ATTRS)

    # One Satori <test> is one independent lookup rule in upstream code.
    # More than one supported signal in a single <test> would need explicit source-semantics proof.
    if len(signal_fields) == 0:
        reasons.append("no_supported_k1_signal")
    elif len(signal_fields) > 1:
        reasons.append("multiple_supported_signal_fields_quarantine")

    # Do not silently erase unsupported predicates (e.g. ipttl) from a mixed rule.
    if unsupported_nonmeta:
        if signal_fields:
            reasons.append("mixed_supported_and_unsupported_predicates")
        else:
            reasons.append("unsupported_predicate_only")

    outcomes = taxonomy_outcomes(fp_attrs)
    if not outcomes:
        reasons.append("no_direct_v1_taxonomy_mapping")

    predicates = empty_predicates()
    if dhcptype != "Any" and normalized_message is not None:
        predicates["message_type"] = exact_scalar(normalized_message)

    if len(signal_fields) == 1:
        field = signal_fields[0]
        raw = test_attrs[field]
        try:
            if field == "dhcpoption55":
                predicates["parameter_request_list"] = exact_seq(parse_sequence(raw))
            elif field == "dhcpoptions":
                predicates["option_order"] = exact_seq(parse_sequence(raw))
            elif field == "dhcpvendorcode":
                if not printable_ascii_1_128(raw):
                    reasons.append("vendor_class_not_PrintableAscii1To128")
                else:
                    predicates["vendor_class"] = exact_scalar(raw)
        except Exception as e:
            reasons.append("invalid_supported_predicate:" + str(e))

    # de-duplicate reason codes but retain deterministic order
    reasons = sorted(set(reasons))
    return reasons, predicates, outcomes, signal_fields, unsupported_nonmeta


def project_candidate_set(records):
    # K1 records are already matched; this function projects taxonomy per dimension.
    dims = defaultdict(set)
    for r in records:
        for o in r["candidate_taxonomy_refs"]:
            if o["outcome_kind"] == "CANONICAL_VALUE":
                dims[o["dimension_name"]].add(o["canonical_target_id"])
    result = {}
    for dim in ("platform_family", "device_class", "manufacturer_family", "model_family"):
        vals = sorted(dims.get(dim, set()))
        if len(vals) == 0:
            result[dim] = {"status": "unknown", "values": []}
        elif len(vals) == 1:
            result[dim] = {"status": "resolved", "values": vals}
        else:
            result[dim] = {"status": "ambiguous", "values": vals}
    return result


def predicates_key(predicates):
    return sha256_hex(canonical_json_bytes(predicates))


def main():
    data = fetch_source()
    source_sha256 = sha256_hex(data)
    source_git_blob_sha1 = git_blob_sha1(data)
    retrieved_at = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")

    root = ET.fromstring(data)
    source_meta = dict(root.attrib)
    fingerprints_parent = root.find("fingerprints")
    if fingerprints_parent is None:
        raise SystemExit("Invalid Satori DHCP XML: <fingerprints> missing")

    counts = Counter()
    rejection_reasons = Counter()
    source_os_classes = Counter()
    source_device_types = Counter()
    message_types = Counter()
    matchtypes = Counter()
    signal_attrs = Counter()
    accepted_records_by_id = {}
    rejected_rows = []
    accepted_source_identities = set()

    for fp in fingerprints_parent.findall("fingerprint"):
        counts["fingerprints_total"] += 1
        fp_attrs = dict(fp.attrib)
        source_os_classes[fp_attrs.get("os_class", "")] += 1
        source_device_types[fp_attrs.get("device_type", "")] += 1
        tests_parent = fp.find("dhcp_tests")
        if tests_parent is None:
            counts["fingerprints_without_dhcp_tests"] += 1
            continue

        for test in tests_parent.findall("test"):
            counts["source_tests_total"] += 1
            test_attrs = dict(test.attrib)
            matchtypes[test_attrs.get("matchtype", "<missing>")] += 1
            message_types[test_attrs.get("dhcptype", "<missing>")] += 1
            for k in SUPPORTED_SIGNAL_ATTRS:
                if k in test_attrs:
                    signal_attrs[k] += 1

            source_identity, source_identity_payload = source_test_identity(fp_attrs, test_attrs)
            reasons, predicates, outcomes, sig_fields, unsupported_nonmeta = classify_test(fp_attrs, test_attrs)

            if reasons:
                counts["source_tests_rejected"] += 1
                for reason in reasons:
                    rejection_reasons[reason] += 1
                rejected_rows.append({
                    "source_record_identity": source_identity,
                    "fingerprint_name": fp_attrs.get("name", ""),
                    "os_class": fp_attrs.get("os_class", ""),
                    "device_type": fp_attrs.get("device_type", ""),
                    "test": test_attrs,
                    "reasons": reasons,
                })
                continue

            rid = record_id(predicates, outcomes, source_identity)
            rec = {
                "record_type": "K1_DHCP",
                "canonical_record_id": rid,
                "dhcp_predicates": predicates,
                "candidate_taxonomy_refs": outcomes,
                "source_record_identity": source_identity,
            }
            counts["source_tests_accepted"] += 1
            accepted_source_identities.add(source_identity)
            if rid in accepted_records_by_id:
                counts["accepted_duplicate_canonical_records"] += 1
            else:
                accepted_records_by_id[rid] = rec

    records = sorted(accepted_records_by_id.values(), key=lambda r: r["canonical_record_id"])
    counts["canonical_records_unique"] = len(records)

    # Group identical predicates to prove ambiguity preservation and row-order independence.
    by_predicate = defaultdict(list)
    for r in records:
        by_predicate[predicates_key(r["dhcp_predicates"])].append(r)

    ambiguity_groups = []
    for key, group in by_predicate.items():
        if len(group) <= 1:
            continue
        projection = project_candidate_set(group)
        all_names = []
        for r in group:
            all_names.append(r["source_record_identity"])
        ambiguity_groups.append({
            "predicate_digest": key,
            "record_count": len(group),
            "record_ids": sorted(r["canonical_record_id"] for r in group),
            "source_record_identities": sorted(all_names),
            "projection": projection,
            "dhcp_predicates": group[0]["dhcp_predicates"],
        })
    ambiguity_groups.sort(key=lambda g: (-g["record_count"], g["predicate_digest"]))
    counts["predicate_groups_total"] = len(by_predicate)
    counts["ambiguous_predicate_groups"] = len(ambiguity_groups)
    counts["records_in_ambiguous_groups"] = sum(g["record_count"] for g in ambiguity_groups)

    # Coverage from accepted canonical records.
    coverage = defaultdict(Counter)
    for r in records:
        for o in r["candidate_taxonomy_refs"]:
            if o["outcome_kind"] == "CANONICAL_VALUE":
                coverage[o["dimension_name"]][o["canonical_target_id"]] += 1

    # Explicit mandatory fixture from R14: Android/smartphone + Android/tablet.
    synthetic_pred = empty_predicates()
    synthetic_pred["message_type"] = exact_scalar("discover")
    synthetic_pred["vendor_class"] = exact_scalar("captivportal-fe1-fixture")
    synthetic_a = {
        "record_type": "K1_DHCP",
        "canonical_record_id": "fixture-A",
        "dhcp_predicates": synthetic_pred,
        "candidate_taxonomy_refs": [
            {"dimension_name":"platform_family","outcome_kind":"CANONICAL_VALUE","canonical_target_id":"android","broad_taxon_ref":None,"out_of_scope_taxon_ref":None,"base_claim_strength":"supporting"},
            {"dimension_name":"device_class","outcome_kind":"CANONICAL_VALUE","canonical_target_id":"smartphone","broad_taxon_ref":None,"out_of_scope_taxon_ref":None,"base_claim_strength":"supporting"},
        ],
        "source_record_identity": "fixture-A",
    }
    synthetic_b = {
        "record_type": "K1_DHCP",
        "canonical_record_id": "fixture-B",
        "dhcp_predicates": synthetic_pred,
        "candidate_taxonomy_refs": [
            {"dimension_name":"platform_family","outcome_kind":"CANONICAL_VALUE","canonical_target_id":"android","broad_taxon_ref":None,"out_of_scope_taxon_ref":None,"base_claim_strength":"supporting"},
            {"dimension_name":"device_class","outcome_kind":"CANONICAL_VALUE","canonical_target_id":"tablet","broad_taxon_ref":None,"out_of_scope_taxon_ref":None,"base_claim_strength":"supporting"},
        ],
        "source_record_identity": "fixture-B",
    }
    fixture_projection = project_candidate_set([synthetic_a, synthetic_b])
    fixture_pass = (
        fixture_projection["platform_family"] == {"status":"resolved","values":["android"]}
        and fixture_projection["device_class"] == {"status":"ambiguous","values":["smartphone","tablet"]}
    )

    fixture_matrix = {
        "r14_mandatory_android_smartphone_plus_tablet": {
            "candidate_records": [synthetic_a, synthetic_b],
            "projection": fixture_projection,
            "pass": fixture_pass,
        },
        "row_order_permutation": {
            "projection_ab": project_candidate_set([synthetic_a, synthetic_b]),
            "projection_ba": project_candidate_set([synthetic_b, synthetic_a]),
            "pass": project_candidate_set([synthetic_a, synthetic_b]) == project_candidate_set([synthetic_b, synthetic_a]),
        },
        "no_match": {
            "candidate_records": [],
            "projection": project_candidate_set([]),
            "pass": all(v["status"] == "unknown" for v in project_candidate_set([]).values()),
        },
    }

    audit = {
        "audit_version": 1,
        "importer_identity": IMPORTER_ID,
        "source": {
            "repository": REPO,
            "commit": SOURCE_COMMIT,
            "path": SOURCE_PATH,
            "url": SOURCE_URL,
            "git_blob_sha1": source_git_blob_sha1,
            "sha256": source_sha256,
            "bytes": len(data),
            "retrieved_at_utc": retrieved_at,
            "xml_root_metadata": source_meta,
        },
        "owner_authorization": "Satori fingerprints/dhcp.xml authorized as K1 source candidate for F-E1 with constrained canonical import",
        "import_contract": {
            "matchtype": "exact only",
            "message_types": {"accepted_client_types": sorted(SUPPORTED_MESSAGE_TYPES), "Any": "message_type=ANY", "rejected": sorted(SERVER_SIDE_OR_UNSUPPORTED_MESSAGE_TYPES)},
            "signal_mapping": {
                "dhcpoption55": "parameter_request_list EXACT_SEQUENCE",
                "dhcpoptions": "option_order EXACT_SEQUENCE",
                "dhcpvendorcode": "vendor_class EXACT_VALUE",
            },
            "unsupported_source_predicates": "reject/quarantine whole source test; never erase predicate",
            "multiple_supported_signal_fields": "reject/quarantine pending explicit source-semantics proof",
            "weight": "ignored for matching/authority; retained only inside source_record_identity provenance",
            "other_DhcpV1PredicateSet_fields": "ANY",
            "manufacturer_model_claims": "none from Satori K1 V1",
            "base_claim_strength": BASE_CLAIM_STRENGTH,
            "platform_direct_map": PLATFORM_MAP,
            "device_class_direct_map": DEVICE_CLASS_MAP,
        },
        "counts": dict(sorted(counts.items())),
        "rejection_reasons": dict(sorted(rejection_reasons.items())),
        "accepted_coverage": {k: dict(sorted(v.items())) for k, v in sorted(coverage.items())},
        "source_taxonomy_inventory": {
            "os_class": dict(sorted(source_os_classes.items(), key=lambda kv: (-kv[1], kv[0]))),
            "device_type": dict(sorted(source_device_types.items(), key=lambda kv: (-kv[1], kv[0]))),
        },
        "source_test_inventory": {
            "matchtype": dict(sorted(matchtypes.items())),
            "dhcptype": dict(sorted(message_types.items())),
            "supported_signal_attribute_occurrences": dict(sorted(signal_attrs.items())),
        },
        "ambiguity_summary": {
            "ambiguous_predicate_groups": len(ambiguity_groups),
            "records_in_ambiguous_groups": counts["records_in_ambiguous_groups"],
            "top_groups": ambiguity_groups[:20],
        },
        "fixture_matrix": fixture_matrix,
        "gate_interpretation": {
            "fe1_status": "CANDIDATE_AUDIT_COMPLETE_NOT_AUTOMATIC_GATE_PASS",
            "notes": [
                "F-E1 PASS still requires TechLead review of this report and retained artifacts.",
                "F-E5 later freezes exact KnowledgeFreshnessPolicy thresholds; this audit does not invent freshness ages.",
                "F-E6 later freezes complete source taxonomy mappings/aliases; this audit uses only conservative direct V1 mappings.",
            ],
        },
    }

    with RECORDS_JSONL.open("w", encoding="utf-8", newline="\n") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")
    with REJECTS_JSONL.open("w", encoding="utf-8", newline="\n") as f:
        for r in sorted(rejected_rows, key=lambda x: x["source_record_identity"]):
            f.write(json.dumps(r, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")
    AMBIGUITY_JSON.write_text(json.dumps(ambiguity_groups, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    FIXTURES_JSON.write_text(json.dumps(fixture_matrix, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    AUDIT_JSON.write_text(json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")

    lines = []
    lines.append("# CaptivPortal F-E1 — Satori K1 canonical-import audit")
    lines.append("")
    lines.append("## Source pin")
    lines.append("")
    lines.append(f"- Repository: `{REPO}`")
    lines.append(f"- Commit: `{SOURCE_COMMIT}`")
    lines.append(f"- File: `{SOURCE_PATH}`")
    lines.append(f"- Git blob SHA-1: `{source_git_blob_sha1}`")
    lines.append(f"- Source SHA-256: `{source_sha256}`")
    lines.append(f"- Bytes: `{len(data)}`")
    lines.append(f"- XML last_updated: `{source_meta.get('last_updated','')}`")
    lines.append(f"- Retrieved: `{retrieved_at}`")
    lines.append("")
    lines.append("## Canonical import result")
    lines.append("")
    for k in ("fingerprints_total", "source_tests_total", "source_tests_accepted", "source_tests_rejected", "canonical_records_unique", "ambiguous_predicate_groups", "records_in_ambiguous_groups"):
        lines.append(f"- {k}: **{counts.get(k,0)}**")
    lines.append("")
    lines.append("## Accepted V1 coverage")
    lines.append("")
    for dim in sorted(coverage):
        lines.append(f"### {dim}")
        for target, n in sorted(coverage[dim].items()):
            lines.append(f"- `{target}`: {n} canonical records")
        lines.append("")
    lines.append("## Rejection reasons")
    lines.append("")
    for reason, n in sorted(rejection_reasons.items(), key=lambda kv: (-kv[1], kv[0])):
        lines.append(f"- `{reason}`: {n}")
    lines.append("")
    lines.append("## Mandatory R14 fixture")
    lines.append("")
    lines.append(f"- Android/smartphone + Android/tablet projection: **{'PASS' if fixture_pass else 'FAIL'}**")
    lines.append(f"- platform_family: `{fixture_projection['platform_family']}`")
    lines.append(f"- device_class: `{fixture_projection['device_class']}`")
    lines.append(f"- row-order permutation: **{'PASS' if fixture_matrix['row_order_permutation']['pass'] else 'FAIL'}**")
    lines.append(f"- no-match empty CandidateSet projection: **{'PASS' if fixture_matrix['no_match']['pass'] else 'FAIL'}**")
    lines.append("")
    lines.append("## Tech Lead interpretation")
    lines.append("")
    lines.append("This report is a bounded F-E1 source/import audit, not automatic Foundation gate closure.")
    lines.append("No Satori score/weight is used for matching or ranking. No MAC/OUI/UA/TCP/TLS/QUIC predicate is imported.")
    lines.append("Unsupported or mixed source predicates are quarantined rather than silently weakened.")
    lines.append("Freshness age thresholds are intentionally NOT invented here; F-E5 owns them.")
    lines.append("Complete taxonomy/alias admission remains F-E6; this audit uses only direct conservative V1 mappings.")
    AUDIT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("=== CAPTIVPORTAL F-E1 SATORI AUDIT COMPLETE ===")
    print(f"SOURCE_SHA256={source_sha256}")
    print(f"GIT_BLOB_SHA1={source_git_blob_sha1}")
    print(f"FINGERPRINTS={counts.get('fingerprints_total',0)}")
    print(f"SOURCE_TESTS={counts.get('source_tests_total',0)}")
    print(f"ACCEPTED_TESTS={counts.get('source_tests_accepted',0)}")
    print(f"REJECTED_TESTS={counts.get('source_tests_rejected',0)}")
    print(f"CANONICAL_RECORDS={counts.get('canonical_records_unique',0)}")
    print(f"AMBIGUOUS_PREDICATE_GROUPS={counts.get('ambiguous_predicate_groups',0)}")
    print(f"MANDATORY_FIXTURE={'PASS' if fixture_pass else 'FAIL'}")
    print(f"REPORT={AUDIT_MD}")
    print(f"JSON={AUDIT_JSON}")
    print(f"RECORDS={RECORDS_JSONL}")
    print(f"REJECTS={REJECTS_JSONL}")
    print(f"AMBIGUITY={AMBIGUITY_JSON}")
    print(f"FIXTURES={FIXTURES_JSON}")


if __name__ == "__main__":
    main()
