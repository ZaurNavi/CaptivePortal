from dataclasses import replace
from datetime import timedelta
import json
from types import SimpleNamespace
import threading

import pytest

from app.analytics.source_gateway import QueryDeadline
from app.network_metadata.validation import ni_timestamp, ni_format_utc
from app.network_metadata.recognition_read_service import (NetworkMetadataRecognitionReadService,
    RecognitionSourceEvidenceV1, RecognitionSniV1, RecognitionDnsV1, RecognitionDnsQueryV1)
from app.network_metadata.projection_source import NetworkMetadataProjectionSourceReadService
from app.network_metadata_projection.recognition_read_service import (DeviceNetworkMetadataRecognitionReadService,
    RecognitionProjectionSnapshotV2, RecognitionProjectionEdgeFactV1)
from app.network_metadata_projection.models import RegistryEvaluation
from app.network_service_recognition.read_service import DeviceServiceRecognitionReadService
from app.network_service_recognition.models import ServiceUnavailable, ServiceDeadline, ServiceBusy
from app.network_service_recognition.serialization import serialize_device_service_intelligence
from .support import AT, bundle, documents, encode
from .test_protected_readers import store, DEVICE
from tests.network_metadata import source_event, record, outcome
from tests.network_metadata_projection.support import stack, MAC

SITE = "0123456789abcdef01234567"
EVENT = "2026-10-11T23:59:00.123456Z"
GEN = "9412aebe-6e13-463b-9a93-d2e5c8475766"
REF = "10000000-0000-5000-8000-000000000001"


def synthetic(host="www.youtube.com", family="tls", presence="observed_retained", *, event=EVENT):
    fact = RecognitionProjectionEdgeFactV1("a" * 64, event, REF, family, GEN,
        "synthetic-sensor", "lab-scope", "b" * 64, "src", "10.73.0.7", 12345, "203.0.113.93", 443, "TCP", "external", "outbound")
    snapshot = RecognitionProjectionSnapshotV2(2, SITE, DEVICE, "authoritative", "usable", None, DEVICE, (fact,), 0)
    payloads = dict(dns=None, tls=None, quic=None)
    payloads[family] = (RecognitionDnsV1("dns", "request", None, 1, 0, False, False, "observed_retained", "not_observed",
        (RecognitionDnsQueryV1(0, host, "A"),), ()) if family == "dns" else RecognitionSniV1(host, presence))
    source = RecognitionSourceEvidenceV1(1, SITE, REF, event, family, GEN, GEN + ":0", "synthetic-sensor", "lab-scope",
        "b" * 64, "observed_retained", "10.73.0.7", "203.0.113.93", 12345, 443, "TCP", None, None, **payloads)
    return snapshot, source


class Projection:
    def __init__(self, value): self.value, self.calls = value, []
    def read_service_recognition_snapshot(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return self.value


class Source:
    def __init__(self, values): self.values, self.calls = values, []
    def read_recognition_evidence(self, site, refs, *, deadline):
        self.calls.append(refs)
        return tuple(value for value in self.values if value.observation_id in refs)


def read(snapshot=None, source=None, *, b=None, at=AT, reader=None, deadline=None):
    if snapshot is None: snapshot, source = synthetic()
    service = reader or DeviceServiceRecognitionReadService(Projection(snapshot), Source((source,)), b or bundle())
    return service.get_device_service_summary(SITE, DEVICE, MAC, evaluated_at_utc=at, deadline=deadline or QueryDeadline.after(5))


def test_real_two_store_to_summary_round_trip(tmp_path):
    from app.network_service_recognition.artifacts import load_bundle
    event = source_event("tls", timestamp=EVENT, dest_ip="203.0.113.93", proto="TCP")
    event["tls"]["sni"] = "www.youtube.com"
    data = record(event)
    with store(tmp_path, source=data + b"\n") as source_state:
        source_state.clock.value = ni_timestamp(AT, canonical=True)
        source_state.repo.ingest_batch([outcome(source_state.config.capture_scope_binding, data,
            generation=source_state.generation.source_generation_id)], source_state.run, source_state.health, source_state.anchor)
        ni01 = NetworkMetadataProjectionSourceReadService(source_state.config.db_path)
        ref = source_state.repo.connection.execute("SELECT observation_id FROM network_metadata_observations").fetchone()[0]
        projected_source = ni01.get_projection_source_record(ref)
        projection = stack(tmp_path, [projected_source])
        projection.clock.value = ni_timestamp(AT, canonical=True)
        projection.attribution.states["203.0.113.93"] = "endpoint_absent"
        original = projection.attribution.resolve_ipv4
        def resolve(*args):
            value = original(*args)
            return replace(value, valid_from="2026-10-11T00:00:00.000Z", valid_until="2026-10-13T00:00:00.000Z") if value.state == "resolved" else value
        projection.attribution.resolve_ipv4 = resolve
        projection.registry.values[MAC] = RegistryEvaluation("authoritative", DEVICE)
        projection.service.poll()
        try:
            before = tuple(source_state.repo.connection.iterdump()), tuple(projection.repo.connection.iterdump())
            b = bundle()
            reader = DeviceServiceRecognitionReadService(DeviceNetworkMetadataRecognitionReadService(projection.config.db_path),
                NetworkMetadataRecognitionReadService(source_state.config.db_path), b)
            result = read(reader=reader)
            assert result.recent_services[0].service_id == "service.youtube"
            assert result.evidence_state == "supported_results_present" and result.freshness_state == "fresh"
            public = json.dumps(serialize_device_service_intelligence(result, b))
            for private in ("www.youtube.com", "203.0.113.93", MAC, ref, "source_event_identity", "matched_rule_ids", "evidence_refs"):
                assert private not in public
            assert before == (tuple(source_state.repo.connection.iterdump()), tuple(projection.repo.connection.iterdump()))
        finally: projection.repo.close()


@pytest.mark.parametrize("family", ["tls", "quic"])
def test_positive_and_half_open_recent_windows(family):
    snapshot, source = synthetic(family=family)
    result = read(snapshot, source)
    assert result.recent_services[0].support_state == "directly_supported"
    assert result.service_categories[0].service_category_id == "category.video_streaming"
    assert result.last_service_observation.observed_at == EVENT
    for offset, recent in ((3600, True), (3601, False), (86400, False)):
        event = ni_format_utc(ni_timestamp(AT, canonical=True) - timedelta(seconds=offset))
        result = read(*synthetic(family=family, event=event))
        assert bool(result.recent_services) is recent and result.last_service_observation is not None
    with pytest.raises(ServiceUnavailable): read(*synthetic(family=family, event=AT))


@pytest.mark.parametrize("host,family,presence", [("www.youtube.com", "dns", "observed_retained"),
    (None, "tls", "not_observed"), (None, "quic", "expired"), ("bad..hostname", "tls", "observed_retained")])
def test_no_dns_or_missing_sni_positive(host, family, presence):
    result = read(*synthetic(host, family, presence))
    assert result.last_service_observation is None and result.evidence_state == "recognition_limited"
    assert result.coverage.recognition_state == "limited"


@pytest.mark.parametrize("field", ["site_id", "event_at", "source_generation_id", "source_event_family", "capture_source_id", "network_scope_id", "capture_scope_binding_digest"])
def test_exact_cross_store_provenance(field):
    snapshot, source = synthetic()
    with pytest.raises(ServiceUnavailable): read(snapshot, replace(source, **{field: "mismatched"}))


@pytest.mark.parametrize("family", ["tls", "quic"])
def test_exact_device_and_peer_endpoints_positive(family):
    snapshot, source = synthetic(family=family)
    fact = snapshot.facts[0]
    assert (source.src_ip, source.src_port, source.dst_ip, source.dst_port, source.transport_protocol) == (
        fact.device_ip, fact.device_port, fact.peer_ip, fact.peer_port, fact.transport_protocol)
    assert read(snapshot, source).last_service_observation.service_id == "service.youtube"


@pytest.mark.parametrize("family", ["tls", "quic"])
@pytest.mark.parametrize("field,wrong", [("src_ip", "10.73.0.99"), ("src_port", 54321),
    ("dst_ip", "203.0.113.94"), ("dst_port", 8443), ("transport_protocol", "UDP")])
def test_retained_endpoint_mismatch_rejects_entire_read(family, field, wrong):
    snapshot, source = synthetic(family=family)
    with pytest.raises(ServiceUnavailable) as caught:
        read(snapshot, replace(source, **{field: wrong}))
    assert caught.value.reason == "source_unavailable"


@pytest.mark.parametrize("field,wrong", [("src_ip", "10.73.0.99"), ("src_port", 54321)])
def test_multi_fact_source_mismatch_fails_before_any_match(monkeypatch, field, wrong):
    from .test_limits_vectors import many_sources
    from app.network_service_recognition import read_service
    snapshot, sources = many_sources(2)
    calls = []
    def forbidden_match(**kwargs):
        calls.append(kwargs)
        raise AssertionError("No matching before the complete provenance set validates")
    monkeypatch.setattr(read_service, "match_direct_sni_v1", forbidden_match)
    reader = DeviceServiceRecognitionReadService(Projection(snapshot), Source((sources[0], replace(sources[1], **{field: wrong}))), bundle())
    with pytest.raises(ServiceUnavailable) as caught: read(reader=reader)
    assert caught.value.reason == "source_unavailable" and calls == []


def test_legitimately_expired_endpoints_preserve_existing_limited_behavior():
    snapshot, source = synthetic()
    source = replace(source, sensitive_endpoint_presence_state="expired", src_ip=None, src_port=None,
        dst_ip=None, dst_port=None, transport_protocol=None)
    result = read(snapshot, source)
    assert result.last_service_observation.service_id == "service.youtube"
    assert result.coverage.recognition_state == "limited" and result.freshness_state == "fresh"


@pytest.mark.parametrize("binding,expected", [("not_yet_registry_resolved", "pending"), ("registry_unavailable", "unavailable"), ("absent", "absent")])
def test_pending_identity_does_not_read_sensitive_store(binding, expected):
    snapshot, source = synthetic()
    reader = Source((source,))
    snapshot = replace(snapshot, identity_binding_state=binding, bound_device_id=None, facts=())
    result = read(reader=DeviceServiceRecognitionReadService(Projection(snapshot), reader, bundle()))
    assert result.identity_binding_state == expected and result.evidence_state == "identity_pending" and reader.calls == []


@pytest.mark.parametrize("runtime,expected", [("registry_degraded", "fresh"), ("attribution_unavailable", "fresh"), ("source_unavailable", "fresh"),
    ("capacity_halted", "fresh"), ("initializing", "fresh")])
def test_coverage_and_freshness_do_not_erase_supported(runtime, expected):
    snapshot, source = synthetic()
    result = read(replace(snapshot, projection_runtime_state=runtime), source)
    assert result.evidence_state == "supported_results_present" and result.freshness_state == expected


def test_unknown_is_not_inactivity_and_expired_rules_limited():
    result = read(*synthetic("unknown.example.invalid"))
    assert result.evidence_state == "no_supported_result_observed_with_sufficient_coverage"
    at = "2027-01-09T20:04:00.000000Z"
    result = read(*synthetic(event="2027-01-09T20:03:00.000000Z"), at=at)
    assert result.evidence_state == "recognition_limited" and result.last_service_observation is None


def test_deadline_and_single_slot_release(monkeypatch):
    from app.network_service_recognition import read_service
    with pytest.raises(ServiceDeadline): read(deadline=QueryDeadline.after(0))
    assert read().last_service_observation is not None
    assert read_service._READ_SLOTS.acquire(False)
    try:
        with pytest.raises(ServiceBusy): read()
    finally: read_service._READ_SLOTS.release()


def test_missing_duplicate_and_overflow_evidence_fail_no_subset():
    snapshot, source = synthetic()
    with pytest.raises(ServiceUnavailable): read(reader=DeviceServiceRecognitionReadService(Projection(snapshot), Source(()), bundle()))
    with pytest.raises(ServiceUnavailable): read(replace(snapshot, facts=snapshot.facts * 5001), source)
    bad = replace(source, tls=None, quic=RecognitionSniV1("www.youtube.com", "observed_retained"))
    with pytest.raises(ServiceUnavailable): read(snapshot, bad)


def test_public_cross_fields_and_no_protected_serialization():
    b, result = bundle(), read()
    for changed in (replace(result, freshness_state="stale"), replace(result, evidence_state="identity_pending"),
        replace(result, identity_binding_state="pending"), replace(result, taxonomy_digest_sha256="0" * 64),
        replace(result, service_categories=()), replace(result, recent_services=result.recent_services * 2)):
        with pytest.raises(ServiceUnavailable): serialize_device_service_intelligence(changed, b)
    with pytest.raises(ServiceUnavailable): serialize_device_service_intelligence(synthetic()[1], b)
