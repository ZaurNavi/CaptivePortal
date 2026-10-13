"""Exact V2 recovery matrix: pipeline health cannot stand in for Device trust."""
import ast
import json
from dataclasses import asdict, replace
from datetime import timedelta
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.analytics.source_gateway import QueryDeadline
from app.network_metadata.validation import ni_format_utc, ni_timestamp
from app.network_metadata_projection.models import RegistryEvaluation, ProjectionUnavailable
from app.network_metadata_projection.recognition_read_service import DeviceNetworkMetadataRecognitionReadService
from app.network_service_recognition.models import ServiceUnavailable
from app.network_service_recognition.read_service import DeviceServiceRecognitionReadService
from app.network_service_recognition.serialization import serialize_device_service_intelligence
from tests.network_metadata_projection.support import stack, source_record, SITE, MAC, OTHER_MAC, T0
from .support import AT, bundle
from .test_summary import synthetic, read, Source, Projection, DEVICE


@pytest.mark.parametrize("runtime,reason,pipeline,source_state", [
    ("usable", None, "usable", "usable"),
    ("registry_degraded", "registry_unavailable", "usable", "usable"),
    ("attribution_unavailable", "pending_attribution", "degraded", "usable"),
    ("attribution_unavailable", "attribution_authority_unavailable", "unavailable", "usable"),
    ("attribution_unavailable", None, "unknown", "usable"),
    ("source_unavailable", "source_unavailable", "unknown", "unavailable"),
    ("capacity_halted", "capacity_halted", "degraded", "degraded"),
    ("capacity_waiting_reader", "capacity_waiting_reader", "degraded", "degraded"),
    ("blocked_conflict", "edge_semantic_conflict", "degraded", "degraded"),
    ("initializing", None, "unknown", "unknown"),
    ("stopping", None, "unknown", "unknown"),
])
@pytest.mark.parametrize("linked", [0, 1])
def test_T01_T04_T05_T07_closed_mapping_preserves_confirmed_fact(runtime, reason, pipeline, source_state, linked):
    snapshot, source = synthetic()
    result = read(replace(snapshot, projection_runtime_state=runtime, projection_safe_reason=reason,
                          device_linked_pending_count=linked), source)
    assert result.schema_version == 2
    assert result.last_service_observation.service_id == "service.youtube"
    assert result.freshness_state == "fresh"
    assert asdict(result.coverage) == {
        "scope": "confirmed_device_evidence", "source_state": source_state,
        "pipeline_attribution_state": pipeline, "device_evidence_binding_state": "authoritative",
        "device_linked_pending": bool(linked), "recognition_state": "usable",
        "historical_window_completeness_claimed": False,
    }
    assert result.availability_state == ("usable" if source_state == pipeline == "usable" and not linked else "degraded")
    public = serialize_device_service_intelligence(result, bundle())
    assert public["coverage"] == asdict(result.coverage)
    assert "device_linked_pending_count" not in json.dumps(public)


@pytest.mark.parametrize("reason", ["pending_attribution", "attribution_authority_unavailable", None])
def test_T06_T08_no_edge_means_no_recognition_even_with_exact_sni(reason):
    snapshot, source = synthetic()
    source_reader = Source((source,))
    snapshot = replace(snapshot, facts=(), projection_runtime_state="attribution_unavailable", projection_safe_reason=reason)
    result = read(reader=DeviceServiceRecognitionReadService(Projection(snapshot), source_reader, bundle()))
    assert result.last_service_observation is None and result.recent_services == ()
    assert result.evidence_state == "insufficient_attribution"
    assert source_reader.calls == []


@pytest.mark.parametrize("seconds,expected", [(300, "fresh"), (301, "recent"), (3600, "recent"), (3601, "stale"), (86400, "stale")])
def test_T24_freshness_age_only(seconds, expected):
    event = ni_format_utc(ni_timestamp(AT, canonical=True) - timedelta(seconds=seconds))
    snapshot, source = synthetic(event=event)
    result = read(replace(snapshot, projection_runtime_state="attribution_unavailable",
                          projection_safe_reason="attribution_authority_unavailable"), source)
    assert result.freshness_state == expected
    assert serialize_device_service_intelligence(result, bundle())["freshness_state"] == expected


@pytest.mark.parametrize("changes", [
    {"schema_version": 1}, {"schema_version": True}, {"projection_runtime_state": "future"},
    {"projection_safe_reason": "invented", "projection_runtime_state": "attribution_unavailable"},
    {"projection_safe_reason": "pending_attribution", "projection_runtime_state": "usable"},
    {"device_linked_pending_count": True}, {"device_linked_pending_count": -1},
    {"device_linked_pending_count": 5001}, {"historical_window_completeness_claimed": True},
    {"bound_device_id": "10000000-0000-4000-8000-000000000002"},
])
def test_unsupported_or_inconsistent_snapshot_fails_closed(changes):
    snapshot, source = synthetic()
    with pytest.raises(ServiceUnavailable):
        read(replace(snapshot, **changes), source)


def test_v1_duck_shape_and_public_v1_rejected():
    snapshot, source = synthetic()
    with pytest.raises(ServiceUnavailable):
        read(SimpleNamespace(**asdict(snapshot)), source)
    result = read()
    with pytest.raises(ServiceUnavailable):
        serialize_device_service_intelligence(replace(result, schema_version=1), bundle())
    for change in ({"device_linked_pending": 1}, {"scope": "current_pipeline"},
                   {"device_evidence_binding_state": "none"}, {"pipeline_attribution_state": "invented"}):
        with pytest.raises(ServiceUnavailable):
            serialize_device_service_intelligence(replace(result, coverage=replace(result.coverage, **change)), bundle())


def test_T19_no_private_ni03_mapping_or_import():
    root = Path(__file__).resolve().parents[2] / "app/network_service_recognition"
    for path in root.glob("*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert not (node.module or "").startswith("app.network_protocol_intelligence")
            if isinstance(node, ast.Attribute):
                assert node.attr != "_COVERAGE"


def snapshot_for(state, *, site=SITE, mac=MAC, device=DEVICE, end=None):
    end = end or T0 + timedelta(minutes=1)
    return DeviceNetworkMetadataRecognitionReadService(state.config.db_path).read_service_recognition_snapshot(
        site, device, mac, ni_format_utc(end - timedelta(days=1)), ni_format_utc(end),
        max_rows=5000, deadline=QueryDeadline.after(5))


@pytest.mark.parametrize("kind,linked", [("same_device", 1), ("other_device", 0), ("both_pending", 0), ("other_site", 0)])
def test_T02_T03_T04_T10_T29_T30_pending_requires_exact_materialized_device_link(tmp_path, kind, linked):
    # First edge is confirmed. The independent second observation may be pending.
    first = source_record(dst_ip="203.0.113.93")
    second = source_record(100, src_ip="10.73.0.9", dst_ip="203.0.113.94")
    if kind == "other_site":
        second = replace(second, site_id="f" * 24)
    state = stack(tmp_path, [first, second])
    try:
        state.attribution.states.update({"203.0.113.93": "endpoint_absent", "203.0.113.94": "unavailable"})
        state.attribution.macs["10.73.0.9"] = OTHER_MAC if kind == "other_device" else MAC
        if kind == "both_pending":
            state.attribution.states["10.73.0.9"] = "unavailable"
        state.registry.values[MAC] = RegistryEvaluation("authoritative", DEVICE)
        state.service.poll()
        before = tuple(state.repo.connection.iterdump())
        snapshot = snapshot_for(state)
        assert snapshot.device_linked_pending_count == linked
        assert snapshot.projection_safe_reason == "pending_attribution"
        assert len(snapshot.facts) == (2 if kind == "same_device" else 1)
        if not linked:
            assert all(f.source_observation_ref != second.observation_id for f in snapshot.facts)
        # Read-only repeated extraction cannot rewrite past edge/pending identities.
        assert snapshot_for(state) == snapshot
        assert tuple(state.repo.connection.iterdump()) == before
        with pytest.raises(ProjectionUnavailable):
            snapshot_for(state, device="10000000-0000-4000-8000-000000000002")
    finally:
        state.repo.close()


def test_v2_serialization_golden_field_order_and_coverage():
    result = serialize_device_service_intelligence(read(), bundle())
    assert list(result) == [
        "schema_version", "site_id", "device_id", "evaluated_at_utc", "window",
        "availability_state", "evidence_state", "identity_binding_state", "recent_services",
        "service_categories", "last_service_observation", "freshness_state", "coverage",
        "recognition_ruleset_id", "recognition_ruleset_version", "recognition_ruleset_digest_sha256",
        "taxonomy_id", "taxonomy_version", "taxonomy_digest_sha256",
    ]
    assert json.dumps(result["coverage"], separators=(",", ":")) == (
        '{"scope":"confirmed_device_evidence","source_state":"usable",'
        '"pipeline_attribution_state":"usable","device_evidence_binding_state":"authoritative",'
        '"device_linked_pending":false,"recognition_state":"usable",'
        '"historical_window_completeness_claimed":false}')
    assert json.dumps(result, separators=(",", ":")) == json.dumps(
        serialize_device_service_intelligence(read(), bundle()), separators=(",", ":"))


def test_runtime_binding_facts_and_pending_share_one_read_snapshot(tmp_path):
    state = stack(tmp_path, [source_record(dst_ip="203.0.113.93")])
    try:
        state.attribution.states["203.0.113.93"] = "unavailable"
        state.registry.values[MAC] = RegistryEvaluation("authoritative", DEVICE)
        state.service.poll()
        reader = DeviceNetworkMetadataRecognitionReadService(state.config.db_path)
        original = reader._snapshot
        triggered = []
        class RuntimeCursor:
            def __init__(self, cursor):
                self.cursor = cursor
            def fetchone(self):
                row = self.cursor.fetchone()  # Establish the reader's WAL snapshot.
                with state.repo.transaction():
                    state.repo.connection.execute("DELETE FROM projection_pending_attribution")
                    state.repo.runtime("usable")
                triggered.append(True)
                return row
        class Connection:
            def __init__(self, connection):
                self.connection = connection
            def execute(self, query, *args):
                cursor = self.connection.execute(query, *args)
                return RuntimeCursor(cursor) if query.startswith("SELECT runtime_state,") else cursor
        @contextmanager
        def snapshot(**kwargs):
            with original(**kwargs) as connection:
                yield Connection(connection)
        reader._snapshot = snapshot
        end = T0 + timedelta(minutes=1)
        value = reader.read_service_recognition_snapshot(
            SITE, DEVICE, MAC, ni_format_utc(end - timedelta(days=1)), ni_format_utc(end),
            max_rows=5000, deadline=QueryDeadline.after(5))
        assert triggered == [True]
        assert value.projection_runtime_state == "attribution_unavailable"
        assert value.projection_safe_reason == "pending_attribution"
        assert len(value.facts) == value.device_linked_pending_count == 1
        current = snapshot_for(state)
        assert current.projection_runtime_state == "usable"
        assert current.device_linked_pending_count == 0
        assert current.facts == value.facts
    finally:
        state.repo.close()


def test_pending_window_half_open_and_inbound_edge_can_link_without_service_fact(tmp_path):
    state = stack(tmp_path, [source_record(src_ip="203.0.113.93", dst_ip="10.73.0.7")])
    try:
        state.attribution.states["203.0.113.93"] = "unavailable"
        state.registry.values[MAC] = RegistryEvaluation("authoritative", DEVICE)
        state.service.poll()
        snapshot = snapshot_for(state)
        assert snapshot.facts == () and snapshot.device_linked_pending_count == 1
        event = ni_timestamp(state.source.records[0].event_at, canonical=True)
        assert snapshot_for(state, end=event).device_linked_pending_count == 0
        assert snapshot_for(state, end=event + timedelta(days=1)).device_linked_pending_count == 1
        assert snapshot_for(state, end=event + timedelta(days=1, microseconds=1)).device_linked_pending_count == 0
    finally:
        state.repo.close()
