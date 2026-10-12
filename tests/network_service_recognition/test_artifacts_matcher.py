import copy
import hashlib
import json
from pathlib import Path
import pytest

from app.network_service_recognition.artifacts import CATEGORIES, load_bundle
from app.network_service_recognition.canonical import (RecognitionValidationError, canonical_hostname,
    canonical_json, strict_artifact_json, content_digest)
from app.network_service_recognition.matcher import match_direct_sni_v1
from .support import AT, KNOWLEDGE, NAMES, documents, encode, bundle


def match(host, signal="tls_sni", at=AT, value=None):
    value = value or bundle()
    return match_direct_sni_v1(hostname=host, signal_family=signal, evaluated_at_utc=at,
        taxonomy=value.taxonomy, manifest=value.manifest, ruleset=value.ruleset)


def test_exact_lane_a_bytes_and_semantic_digests():
    expected_raw = (
        "58ff1a1e49cf07229f0247bbeeca6db79acc99b6cd19437aa6245a1ab5c8cfc0",
        "6f1617441b8ce20aed6d91056a685c9efa444b04cfe79e42f57e7db0091d57a0",
        "e6493f24b802a21e34fcbc436f2e7b150172d3bab3e04db7cb4c7005466c94c1")
    expected_semantic = (
        "7e122a828c0877d4fb61382646604a2b4a8421a40c4388e513460c84c69c8278",
        "7ecca6dc42ef73c2dd4b40e4d56d4115078f548cd3693e510f095968be1f0210",
        "46d9485b6aea5c6a0b40a4b9a969eed553a4353904a1667fe85cb0620c02a56a")
    value = bundle()
    for name, raw, semantic, artifact, kind in zip(NAMES, expected_raw, expected_semantic,
            (value.taxonomy, value.manifest, value.ruleset), ("taxonomy", "knowledge_manifest", "ruleset")):
        assert hashlib.sha256(KNOWLEDGE.joinpath(name).read_bytes()).hexdigest() == raw
        assert content_digest(artifact, kind + "_digest_sha256") == semantic
    assert len(value.taxonomy["service_categories"]) == 3
    with pytest.raises(TypeError):
        value.taxonomy["services"][0]["display_name"] = "Mutation"


@pytest.mark.parametrize("count", range(1, 11))
def test_category_subsets_and_full_closed_vocabulary(count):
    docs = documents()
    categories = sorted(CATEGORIES)[:count]
    docs[0]["service_categories"] = [dict(service_category_id=key, display_name=key) for key in categories]
    for row in docs[0]["services"]:
        row["service_category_id"] = categories[0]
    assert len(load_bundle(*encode(docs)).taxonomy["service_categories"]) == count


@pytest.mark.parametrize("case", ["zero", "eleven", "unknown", "duplicate", "unsorted", "missing_ref"])
def test_invalid_category_sets_reject_without_repair(case):
    docs = documents()
    rows = docs[0]["service_categories"]
    if case == "zero": rows.clear()
    elif case == "eleven":
        docs[0]["service_categories"] = [dict(service_category_id=key, display_name=key)
            for key in sorted((*CATEGORIES, "category.unknown"))]
    elif case == "unknown": rows[0]["service_category_id"] = "category.invalid"
    elif case == "duplicate": rows.insert(0, copy.deepcopy(rows[0]))
    elif case == "unsorted": rows.reverse()
    else: rows.pop(0)
    with pytest.raises(RecognitionValidationError): load_bundle(*encode(docs))


def test_normative_r1_synthetic_digests():
    first, due = "2026-10-10T00:00:00.000000Z", "2026-12-31T00:00:00.000000Z"
    taxonomy = dict(schema_version=1, taxonomy_id="captivportal.network-intelligence.recognition-taxonomy",
        taxonomy_version=1, organizations=[dict(display_name="Example Lab", organization_id="org.example_lab", organization_kind="service_operator")],
        service_categories=[dict(display_name="Video Streaming", service_category_id="category.video_streaming")],
        services=[dict(display_name="Example Video", lifecycle_state="active", organization_id="org.example_lab",
            service_category_id="category.video_streaming", service_id="service.example_video")])
    manifest = dict(schema_version=1, knowledge_manifest_id="captivportal.network-intelligence.recognition-knowledge", knowledge_manifest_version=1,
        reviewed_at_utc=first, review_due_at_utc=due, sources=[dict(claim_summary="Synthetic fixture only; not production recognition knowledge.",
            knowledge_ref="knowledge.synthetic.example_video", publisher_or_owner="CaptivPortal synthetic fixture", reviewed_at_utc=first,
            review_due_at_utc=due, source_class="reviewed_internal_research", source_locator="fixture://synthetic/example-video")])
    ruleset = dict(schema_version=1, ruleset_id="captivportal.network-intelligence.service-recognition", ruleset_version=1,
        rules=[dict(ambiguity_group_id=None, hostname_pattern="video.example.invalid", knowledge_refs=["knowledge.synthetic.example_video"],
            lifecycle_state="active", reviewed_at_utc=first, review_due_at_utc=due, rule_id="rule.synthetic.example_video.sni",
            rule_kind="service_sni_exact", target_id="service.example_video", target_type="service")])
    value = load_bundle(*encode([taxonomy, manifest, ruleset]))
    assert value.taxonomy["taxonomy_digest_sha256"] == "63c37fdcf6d276a6ab7521e2e7cd6c9d5baad2c821a6c76ea8e87d294a836700"
    assert value.manifest["knowledge_manifest_digest_sha256"] == "8529f4bc8b29d7bbe64d1d8394ba6d33021b2c59cd70ad5ccc5b0ce4e01e0ed1"
    assert value.ruleset["ruleset_digest_sha256"] == "61097d804e91e5bad70b8f6d1e883718e84d631effcec0fe3240e8a806a426bd"


@pytest.mark.parametrize("raw", [b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":1.5}', b'{"a":Infinity}',
    b'{"a":-Infinity}', b'{ "a":1}', b'{"a":1}\n', b'\xef\xbb\xbf{}', b'{"a":"e\\u0301"}'])
def test_strict_json_rejection(raw):
    with pytest.raises(RecognitionValidationError): strict_artifact_json(raw)


@pytest.mark.parametrize("case", ["digest", "extra", "unsorted_sources", "duplicate_sources", "unsorted_rules", "duplicate_rules",
    "duplicate_target", "dangling_ref", "duplicate_ref", "dns_active", "orphan_group", "unknown_target", "review_inversion", "source_expired"])
def test_closed_bundle_invalid_cases(case):
    docs = documents()
    rule = docs[2]["rules"][0]
    if case == "digest":
        raw = list(encode(docs)); changed = json.loads(raw[0]); changed["taxonomy_digest_sha256"] = "0" * 64
        raw[0] = canonical_json(changed)
    else:
        if case == "extra": docs[0]["extra"] = True
        elif case == "unsorted_sources": docs[1]["sources"].reverse()
        elif case == "duplicate_sources": docs[1]["sources"].insert(0, copy.deepcopy(docs[1]["sources"][0]))
        elif case == "unsorted_rules": docs[2]["rules"].reverse()
        elif case in {"duplicate_rules", "duplicate_target"}:
            other = copy.deepcopy(rule)
            if case == "duplicate_target": other["rule_id"] += "_copy"
            docs[2]["rules"].insert(1, other)
        elif case == "dangling_ref": rule["knowledge_refs"] = ["knowledge.absent"]
        elif case == "duplicate_ref": rule["knowledge_refs"] *= 2
        elif case == "dns_active": rule["rule_kind"] = "service_dns_connected_exact"
        elif case == "orphan_group": rule["ambiguity_group_id"] = "ambiguity.orphan"
        elif case == "unknown_target": rule["target_id"] = "service.absent"
        elif case == "review_inversion": rule["reviewed_at_utc"] = "2026-10-10T00:00:00.000000Z"
        else: docs[1]["sources"][0]["review_due_at_utc"] = docs[1]["reviewed_at_utc"]
        raw = encode(docs)
    with pytest.raises(RecognitionValidationError): load_bundle(*raw)


VECTORS = json.loads(Path(__file__).with_name("fixtures").joinpath("research-fixtures-v1.json").read_bytes())["vectors"]
@pytest.mark.parametrize("row", [row for row in VECTORS if row["signal_family"] in {"tls_sni", "quic_sni"}
    and row["source"] != "synthetic_disallowed_context"], ids=lambda row: row["case_id"])
def test_production_matcher_reference_vectors(row):
    assert match(row["observed_hostname"], row["signal_family"]).service_id == row["expected_service_id"]


@pytest.mark.parametrize("host", ["notwww.youtube.com", "music.youtube.com", "youtube.com", "www.youtube.com..", "www.youtube.com/", "é.youtube.com", "", None])
def test_hostname_false_positives(host):
    assert match(host).resolution_state == "unknown"


def test_due_equality_and_normalization():
    assert match("WWW.YOUTUBE.COM.").service_id == "service.youtube"
    assert match("www.youtube.com", at="2027-01-09T20:04:00.000000Z").service_id is None
    with pytest.raises(RecognitionValidationError): match("www.youtube.com", signal="dns_query_name")


def test_explicit_ambiguity_and_invalid_collision():
    docs = documents()
    first, second = docs[2]["rules"][:2]
    second["hostname_pattern"] = first["hostname_pattern"]
    with pytest.raises(RecognitionValidationError): load_bundle(*encode(docs))
    first["ambiguity_group_id"] = second["ambiguity_group_id"] = "ambiguity.synthetic_shared"
    value = load_bundle(*encode(docs))
    outcome = match(first["hostname_pattern"], value=value)
    assert outcome.resolution_state == "ambiguous" and outcome.service_id is None and outcome.organization_id is None
    assert outcome.matched_rule_ids == tuple(sorted((first["rule_id"], second["rule_id"])))


def test_exact_and_longer_suffix_precedence():
    docs = documents()
    first, second, third = docs[2]["rules"][:3]
    first["rule_kind"], first["hostname_pattern"] = "service_sni_suffix", "example.invalid"
    second["rule_kind"], second["hostname_pattern"] = "service_sni_suffix", "video.example.invalid"
    third["hostname_pattern"] = "exact.video.example.invalid"
    value = load_bundle(*encode(docs))
    assert match("deep.video.example.invalid", value=value).service_id == second["target_id"]
    assert match("exact.video.example.invalid", value=value).service_id == third["target_id"]
    assert match("notexample.invalid", value=value).service_id is None


def test_registry_is_non_runtime_and_corrected():
    data = Path(__file__).parents[2].joinpath("docs/network-service-recognition/NI04-UNIFIED55-RESEARCH-REGISTRY-v1.json").read_bytes()
    assert hashlib.sha256(data).hexdigest() == "70893ee3ec5ccd283c9bccce7948a5d914d8ad3a8f5ca81785a1654a9cbf79c7"
    value = json.loads(data)
    assert value["non_runtime"] is True and len({row["service_id"] for row in value["services"]}) == 55
    for row in value["services"]:
        if row["service_name"] in {"X", "VK"}:
            assert row["service_id"].endswith("_platform") and row["admission_decision"] == "ARCH_HOLD"
    assert len(bundle().ruleset["rules"]) == 5
