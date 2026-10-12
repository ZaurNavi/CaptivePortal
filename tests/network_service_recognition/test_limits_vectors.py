"""Bounded orchestration tests; synthetic knowledge is never a runtime admission."""
from dataclasses import replace
from hashlib import sha256
import json
import threading
from pathlib import Path
from uuid import UUID

import pytest

from app.network_service_recognition.artifacts import load_bundle
from app.network_service_recognition.models import ServiceUnavailable, service_observation
from app.network_service_recognition.matcher import match_direct_sni_v1
from app.network_metadata.recognition_read_service import RecognitionDnsQueryV1
from .support import AT, documents, encode, bundle
from .test_summary import synthetic, read, Projection, Source, DeviceServiceRecognitionReadService, SITE, DEVICE

VECTORS = json.loads(Path(__file__).with_name("fixtures").joinpath("research-fixtures-v1.json").read_bytes())["vectors"]


@pytest.mark.parametrize("row", VECTORS, ids=lambda row: row["case_id"])
def test_all_34_retained_reference_vectors_through_orchestrator(row):
    family = "dns" if row["signal_family"] == "dns_query_name" else "quic" if row["signal_family"] == "quic_sni" else "tls"
    snapshot, source = synthetic(row["observed_hostname"] or None, family)
    if row["case_id"] == "negative.local_edge":
        snapshot = replace(snapshot, facts=(replace(snapshot.facts[0], peer_scope="local"),))
    elif row["case_id"] == "negative.inbound_edge":
        snapshot = replace(snapshot, facts=(replace(snapshot.facts[0], direction="inbound"),))
    elif row["case_id"] == "negative.wrong_device":
        snapshot = replace(snapshot, bound_device_id=str(UUID(int=2)))
    if row["source"] == "synthetic_disallowed_context":
        with pytest.raises(ServiceUnavailable): read(snapshot, source)
    else:
        value = read(snapshot, source)
        actual = value.last_service_observation.service_id if value.last_service_observation else None
        assert actual == row["expected_service_id"]


def many_sources(count, *, scalars=1, positive=True):
    """Exact unique source refs and edge identities for hard-cap boundary tests."""
    snapshot, source = synthetic("www.youtube.com" if positive else "unadmitted.example.invalid",
                                 family="tls" if scalars == 1 else "dns")
    facts, sources = [], []
    for index in range(count):
        ref = str(UUID(int=(5 << 76) | (2 << 62) | (index + 1)))
        fact = replace(snapshot.facts[0], edge_id=sha256(str(index).encode()).hexdigest(), source_observation_ref=ref)
        value = replace(source, observation_id=ref)
        if scalars != 1:
            value = replace(value, dns=replace(value.dns, query_count_observed=scalars,
                queries=tuple(RecognitionDnsQueryV1(number, "unadmitted.example.invalid", "A") for number in range(scalars))))
        facts.append(fact); sources.append(value)
    return replace(snapshot, facts=tuple(facts)), tuple(sources)


@pytest.mark.parametrize("count,expected_batches", [(256, [256]), (257, [256, 1]), (5000, [256] * 19 + [136])])
def test_exact_batch_and_5000_fact_boundaries(count, expected_batches):
    snapshot, values = many_sources(count)
    source = Source(values)
    result = read(reader=DeviceServiceRecognitionReadService(Projection(snapshot), source, bundle()))
    assert len(result.recent_services) == 1
    assert [len(batch) for batch in source.calls] == expected_batches
    assert len({ref for batch in source.calls for ref in batch}) == count


def test_5001_facts_fail_before_any_source_read():
    snapshot, values = many_sources(5001)
    source = Source(values)
    with pytest.raises(ServiceUnavailable) as caught:
        read(reader=DeviceServiceRecognitionReadService(Projection(snapshot), source, bundle()))
    assert caught.value.reason == "source_unavailable" and source.calls == []


@pytest.mark.parametrize("extra,passes", [(0, True), (1, False)])
def test_25000_scalar_limit_no_partial_service_subset(extra, passes):
    snapshot, values = many_sources(5000, scalars=5, positive=False)
    if extra:
        values = (*values[:-1], replace(values[-1], dns=replace(values[-1].dns,
            queries=(*values[-1].dns.queries, RecognitionDnsQueryV1(5, "extra.example.invalid", "A")))))
    reader = DeviceServiceRecognitionReadService(Projection(snapshot), Source(values), bundle())
    if passes:
        assert read(reader=reader).recent_services == ()
    else:
        with pytest.raises(ServiceUnavailable): read(reader=reader)


def synthetic_55_bundle():
    docs = documents()
    service, rule = docs[0]["services"][0], docs[2]["rules"][0]
    docs[0]["services"] = [dict(service, service_id=f"service.synthetic_{index:02d}", display_name=f"Synthetic {index:02d}") for index in range(55)]
    docs[2]["rules"] = [dict(rule, rule_id=f"rule.synthetic_{index:02d}", target_id=f"service.synthetic_{index:02d}",
        hostname_pattern=f"service{index:02d}.example.invalid") for index in range(55)]
    # New disposable tuple only. This does not propose or admit any catalog rule.
    docs[0]["taxonomy_version"] = docs[2]["ruleset_version"] = 2
    return load_bundle(*encode(docs))


@pytest.mark.parametrize("count,limited", [(12, False), (13, True), (55, True)])
def test_data_driven_55_support_and_only_presentation_subset_is_limited(count, limited):
    snapshot, values = many_sources(count)
    values = tuple(replace(value, tls=replace(value.tls, sni=f"service{index:02d}.example.invalid")) for index, value in enumerate(values))
    result = read(reader=DeviceServiceRecognitionReadService(Projection(snapshot), Source(values), synthetic_55_bundle()))
    assert len(result.recent_services) == min(count, 12)
    assert [row.service_id for row in result.recent_services] == [f"service.synthetic_{index:02d}" for index in range(min(count, 12))]
    assert result.coverage.recognition_state == ("limited" if limited else "usable")
    assert result.last_service_observation.service_id == "service.synthetic_00"


def test_source_set_order_does_not_change_summary_or_observation_identity():
    snapshot, values = many_sources(2)
    b = bundle()
    first = read(reader=DeviceServiceRecognitionReadService(Projection(snapshot), Source(values), b))
    second = read(reader=DeviceServiceRecognitionReadService(Projection(replace(snapshot, facts=tuple(reversed(snapshot.facts)))), Source(tuple(reversed(values))), b))
    assert first == second
    matched = match_direct_sni_v1(hostname="www.youtube.com", signal_family="tls_sni", evaluated_at_utc=AT,
        taxonomy=b.taxonomy, manifest=b.manifest, ruleset=b.ruleset)
    left = service_observation(SITE, DEVICE, snapshot.facts[0], matched)
    right = service_observation(SITE, DEVICE, snapshot.facts[0], matched)
    assert left == right and len(left.service_observation_id) == 64


def test_missing_eighth_provenance_join_reference_fails_closed():
    snapshot, values = many_sources(1)
    with pytest.raises(ServiceUnavailable):
        read(reader=DeviceServiceRecognitionReadService(Projection(snapshot), Source((replace(values[0], observation_id=str(UUID(int=3))),)), bundle()))


def test_previous_tuple_conflict_and_noop_version_bump_reject():
    b = bundle()
    docs = documents()
    docs[0]["services"][0]["display_name"] = "Changed"
    with pytest.raises(ValueError): load_bundle(*encode(docs), previous=b)
    docs = documents(); docs[0]["taxonomy_version"] = 2
    with pytest.raises(ValueError): load_bundle(*encode(docs), previous=b)
    assert load_bundle(*encode(documents()), previous=b) == b


def test_launch_report_all_55_rows_truthful_and_non_runtime():
    root = Path(__file__).parents[2] / "docs/network-service-recognition"
    registry = json.loads((root / "NI04-UNIFIED55-RESEARCH-REGISTRY-v1.json").read_bytes())
    report = json.loads((root / "unified55-launch-scope-v1.json").read_bytes())
    assert report["non_runtime"] is True and report["production_activation"] is False
    assert len(report["services"]) == len({row["catalog_target"] for row in report["services"]}) == 55
    admitted = {row["target_id"] for row in bundle().ruleset["rules"]}
    for original, row in zip(registry["services"], report["services"]):
        assert row["catalog_target"] == original["service_id"]
        assert row["host_candidate"] == original["exact_hostname_candidate"]
        assert row["host_semantic_accepted"] == original["arch_first_party_host_approved"]
        assert row["rule_bundle_admitted"] == row["direct_SNI_supported"] == (original["service_id"] in admitted)
        assert (row["reason_if_not_admitted"] is None) == row["rule_bundle_admitted"]
    assert sum(row["direct_SNI_supported"] for row in report["services"]) == 5


def test_two_simultaneous_calls_have_one_active_slot_and_release():
    entered, release = threading.Event(), threading.Event()
    snapshot, source = synthetic()
    class BlockingProjection(Projection):
        def read_service_recognition_snapshot(self, *args, **kwargs):
            entered.set()
            assert release.wait(3)
            return self.value
    reader = DeviceServiceRecognitionReadService(BlockingProjection(snapshot), Source((source,)), bundle())
    results = []
    worker = threading.Thread(target=lambda: results.append(read(reader=reader)))
    worker.start()
    try:
        assert entered.wait(2)
        from app.network_service_recognition.models import ServiceBusy
        with pytest.raises(ServiceBusy): read()
    finally: release.set(); worker.join(3)
    assert not worker.is_alive() and len(results) == 1
    assert read().last_service_observation is not None
