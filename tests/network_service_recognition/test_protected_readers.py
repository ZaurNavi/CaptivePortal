"""Real disposable NI-01/NI-02B stores; no protected fields leave these tests."""
from dataclasses import FrozenInstanceError, replace
from datetime import timedelta
import sqlite3
from contextlib import contextmanager
from hashlib import sha256

import pytest

from app.analytics.source_gateway import QueryDeadline, AnalyticsQueryDeadlineExceeded
from app.network_metadata.models import NetworkMetadataStorageUnavailable, NetworkMetadataValidationError
from app.network_metadata.projection_source import NetworkMetadataProjectionSourceReadService
from app.network_metadata.recognition_read_service import NetworkMetadataRecognitionReadService
from app.network_metadata.validation import ni_format_utc
from app.network_metadata_projection.models import ProjectionUnavailable, RegistryEvaluation
from app.network_metadata_projection.recognition_read_service import DeviceNetworkMetadataRecognitionReadService
from app.network_service_recognition.matcher import match_direct_sni_v1
from tests.network_metadata import store as source_store, outcome, record, source_event
from tests.network_metadata_projection.support import stack, SITE, MAC, T0
from .support import bundle, AT

DEVICE = "10000000-0000-4000-8000-000000000001"


@contextmanager
def store(tmp_path, *, source):
    # This test exercises repository/protected-reader contracts, not the POSIX
    # capture-file adapter. Supply a real bounded hash of disposable input bytes.
    with source_store(tmp_path, source=source) as state:
        def anchor(offset):
            length = min(4096, offset)
            return (offset - length, length, sha256(source[offset-length:offset]).hexdigest()) if length else (0, 0, None)
        state.anchor = anchor
        yield state


def source_read(state, refs=None, *, deadline=None, site=None):
    refs = refs or tuple(row[0] for row in state.repo.connection.execute(
        "SELECT observation_id FROM network_metadata_observations ORDER BY observation_id"))
    return NetworkMetadataRecognitionReadService(state.config.db_path).read_recognition_evidence(
        site or state.config.capture_scope_binding.site_id, refs, deadline=deadline or QueryDeadline.after(5))


@pytest.mark.parametrize("family", ["tls", "quic", "dns"])
def test_real_source_round_trip_closed_and_no_mutation(tmp_path, family):
    event = source_event(family)
    if family != "dns":
        event[family]["sni"] = "www.youtube.com"
    data = record(event)
    with store(tmp_path, source=data + b"\n") as state:
        state.repo.ingest_batch([outcome(state.config.capture_scope_binding, data,
            generation=state.generation.source_generation_id)], state.run, state.health, state.anchor)
        before = tuple(state.repo.connection.iterdump())
        values = source_read(state)
        assert tuple(state.repo.connection.iterdump()) == before
        assert type(values) is tuple and len(values) == 1
        value = values[0]
        assert value.source_event_family == family and value.schema_version == 1
        assert (value.dns is not None) == (family == "dns")
        assert (value.tls is not None) == (family == "tls")
        assert (value.quic is not None) == (family == "quic")
        assert "youtube" not in repr(value)
        with pytest.raises(FrozenInstanceError):
            value.event_at = AT
        if family != "dns":
            b = bundle()
            matched = match_direct_sni_v1(hostname=getattr(value, family).sni, signal_family=family + "_sni",
                evaluated_at_utc=AT, taxonomy=b.taxonomy, manifest=b.manifest, ruleset=b.ruleset)
            assert matched.service_id == "service.youtube"


def test_dns_original_answer_ordinals_preserved(tmp_path):
    event = source_event()
    event["dns"]["answers"] = [{"rrtype": "MX"}, {"rrtype": "A", "rdata": "203.0.113.93"}]
    data = record(event)
    with store(tmp_path, source=data + b"\n") as state:
        state.repo.ingest_batch([outcome(state.config.capture_scope_binding, data,
            generation=state.generation.source_generation_id)], state.run, state.health, state.anchor)
        assert [item.ordinal for item in source_read(state)[0].dns.answers] == [1]


@pytest.mark.parametrize("damage", ["DELETE FROM network_metadata_tls",
    "UPDATE network_metadata_tls SET sni_presence_state='expired'",
    "UPDATE network_metadata_observations SET capture_source_id='wrong-source'",
    "UPDATE network_metadata_observations SET flow_id_decimal='01'",
    "UPDATE network_metadata_observations SET flow_id_decimal='999999999999999999999999999999999999999999'",
    "PRAGMA user_version=2"])
def test_source_integrity_fails_closed(tmp_path, damage):
    data = record(source_event("tls"))
    with store(tmp_path, source=data + b"\n") as state:
        state.repo.ingest_batch([outcome(state.config.capture_scope_binding, data,
            generation=state.generation.source_generation_id)], state.run, state.health, state.anchor)
        state.repo.connection.execute(damage)
        with pytest.raises(NetworkMetadataStorageUnavailable):
            source_read(state)


def test_source_retained_expiry_not_restored(tmp_path):
    data = record(source_event("tls"))
    with store(tmp_path, source=data + b"\n") as state:
        state.repo.ingest_batch([outcome(state.config.capture_scope_binding, data,
            generation=state.generation.source_generation_id)], state.run, state.health, state.anchor)
        state.repo.connection.execute("UPDATE network_metadata_tls SET sni=NULL,sni_presence_state='expired'")
        value = source_read(state)[0]
        assert value.tls.sni is None and value.tls.sni_presence_state == "expired"
        with pytest.raises(NetworkMetadataStorageUnavailable):
            source_read(state, site="abcdef0123456789abcdef01")
        with pytest.raises(AnalyticsQueryDeadlineExceeded):
            source_read(state, deadline=QueryDeadline.after(0))


@pytest.mark.parametrize("damage", ["UPDATE network_metadata_dns SET query_count_observed=0",
    "UPDATE network_metadata_dns SET queries_truncated=1", "UPDATE network_metadata_dns SET answer_count_observed=0"])
def test_dns_child_count_integrity(tmp_path, damage):
    data = record(source_event())
    with store(tmp_path, source=data + b"\n") as state:
        state.repo.ingest_batch([outcome(state.config.capture_scope_binding, data,
            generation=state.generation.source_generation_id)], state.run, state.health, state.anchor)
        state.repo.connection.execute(damage)
        with pytest.raises(NetworkMetadataStorageUnavailable): source_read(state)


def test_dns_retention_expired_keeps_original_observed_counts(tmp_path):
    data = record(source_event())
    with store(tmp_path, source=data + b"\n") as state:
        state.repo.ingest_batch([outcome(state.config.capture_scope_binding, data,
            generation=state.generation.source_generation_id)], state.run, state.health, state.anchor)
        state.repo.connection.execute("DELETE FROM network_metadata_dns_queries")
        state.repo.connection.execute("DELETE FROM network_metadata_dns_answers")
        state.repo.connection.execute("UPDATE network_metadata_dns SET query_names_presence_state='expired',answer_values_presence_state='expired'")
        dns = source_read(state)[0].dns
        assert dns.query_count_observed == dns.answer_count_observed == 1
        assert dns.queries == dns.answers == ()


@pytest.mark.parametrize("refs", [(), [DEVICE], (DEVICE,), tuple(DEVICE for _ in range(257))])
def test_source_batch_contract_no_open(tmp_path, refs):
    with pytest.raises(NetworkMetadataValidationError):
        NetworkMetadataRecognitionReadService(str(tmp_path / "absent.db")).read_recognition_evidence(
            SITE, refs, deadline=QueryDeadline.after(5))
    assert not (tmp_path / "absent.db").exists()


def projection_read(state, **kwargs):
    at = T0 + timedelta(minutes=1)
    return DeviceNetworkMetadataRecognitionReadService(state.config.db_path).read_service_recognition_snapshot(
        SITE, DEVICE, MAC, ni_format_utc(at - timedelta(days=1)), ni_format_utc(at),
        max_rows=5000, deadline=QueryDeadline.after(5), **kwargs)


@pytest.fixture
def projected(tmp_path):
    from tests.network_metadata_projection.support import source_record
    state = stack(tmp_path, [source_record(dst_ip="203.0.113.93", dst_port=443)])
    state.attribution.states["203.0.113.93"] = "endpoint_absent"
    state.registry.values[MAC] = RegistryEvaluation("authoritative", DEVICE)
    state.service.poll()
    try:
        yield state
    finally:
        state.repo.close()


def test_projection_read_same_snapshot_exact_binding(projected):
    before = tuple(projected.repo.connection.iterdump())
    result = projection_read(projected)
    assert len(result.facts) == 1
    assert result.bound_device_id == DEVICE and result.identity_binding_state == "authoritative"
    assert result.facts[0].direction == "outbound" and result.facts[0].peer_scope == "external"
    assert (result.facts[0].device_ip, result.facts[0].device_port) == ("10.73.0.7", 65535)
    assert result.historical_window_completeness_claimed is False
    assert tuple(projected.repo.connection.iterdump()) == before


@pytest.mark.parametrize("damage", [
    "UPDATE projection_registry_identities SET client_mac='00:11:22:33:44:77'",
    "UPDATE projection_runtime_state SET runtime_state='source_unavailable'",
    "DELETE FROM projection_site_mac_bindings"])
def test_projection_binding_and_runtime(projected, damage):
    projected.repo.connection.execute(damage)
    if "registry_identities" in damage:
        with pytest.raises(ProjectionUnavailable):
            projection_read(projected)
    else:
        value = projection_read(projected)
        if damage.startswith("DELETE"):
            assert value.identity_binding_state == "absent" and value.facts == ()
        else:
            assert value.projection_runtime_state == "source_unavailable"


@pytest.mark.parametrize("damage", ["DROP INDEX idx_projection_mac_event", "PRAGMA user_version=99"])
def test_projection_schema_no_repair(projected, damage):
    projected.repo.connection.execute(damage)
    with pytest.raises(ProjectionUnavailable):
        projection_read(projected)
