"""R14 T-01 snapshot content, read-session, integrity and limit regression proof."""

from __future__ import annotations

import copy
import sqlite3
import uuid
from dataclasses import dataclass

import pytest

from app.device_fingerprint.artifact_content import ArtifactRef, canonical_artifact_json, make_artifact_content
from app.device_fingerprint.artifact_dependency_graph import extract_direct_artifact_refs
from app.device_fingerprint.binding_contracts import make_evidence_source_binding_timeline
from app.device_fingerprint.f_admit_foundation import prepare_initial_foundation_admission
from app.device_fingerprint.models import (
    DeviceFingerprintStorageUnavailable, DeviceFingerprintValidationError,
)
from app.device_fingerprint.read_service import IngestWatermark
from app.device_fingerprint.read_service import DeviceFingerprintReadService
from app.device_fingerprint.runtime_profile_artifacts import make_foundation_runtime_profile
from app.device_fingerprint.snapshot_artifacts import (
    make_evidence_snapshot_content, make_snapshot_record,
)
from app.device_fingerprint.snapshot_service import (
    DeviceFingerprintSnapshotService, SnapshotBuildError,
)
from app.device_fingerprint.validation import canonical_json, canonical_sha256
from tests.device_fingerprint import SITE
from tests.device_fingerprint_f_admit.test_f_admit import inputs
from tests.device_fingerprint.test_repository import initialized

START = "2026-09-15T11:30:00.000Z"
END = "2026-09-15T12:30:00.000Z"
CAPTURED = "2026-09-15T14:00:00.000Z"
MAC = "AA:BB:CC:DD:EE:FF"
GENERATION = "11111111-1111-4111-8111-111111111111"
KNOWN = {
    "message_type": "discover", "parameter_request_list": [1, 3, 6],
    "option_order": [53, 55], "vendor_class": "android-dhcp-13",
    "client_identifier_kind": "mac", "maximum_message_size": 1500,
    "rapid_commit_requested": False, "capport_requested": True,
    "ipv6_only_preferred_requested": False, "hostname_present": True,
}


def aid(number):
    return str(uuid.UUID(int=number, version=4))


def ref(content):
    return ArtifactRef(content.artifact_id, content.content_sha256).as_dict()


def evidence(number=1, *, payload=None, version=1, observed_at="2026-09-15T12:10:00.000Z",
             producer="sensor-zefer-01", capture="zefer-span-01", raw=None):
    encoded = canonical_json(KNOWN if payload is None else payload) if raw is None else raw
    return {
        "evidence_id": aid(number), "source_event_id": aid(100_000 + number),
        "ingest_sequence": number, "producer_id": producer, "source_kind": "dhcp",
        "source_subtype": None, "capture_source_id": capture, "extractor_name": "dhcp-v1",
        "extractor_version": "1.0.0", "feature_schema_version": version,
        "rule_version": None, "site_id": SITE, "observed_at": observed_at,
        "ingested_at": CAPTURED, "observed_mac": MAC, "observed_ip": "192.168.8.10",
        "privacy_class": "P1", "quality_state": "valid", "payload_json": encoded,
        "payload_sha256": canonical_sha256(encoded),
    }


def health(number=1, *, observed_at="2026-09-15T12:10:00.000Z",
           producer="sensor-zefer-01", capture="zefer-span-01"):
    return {
        "source_health_id": aid(500_000 + number), "source_health_event_id": aid(600_000 + number),
        "ingest_sequence": 10_000 + number, "producer_id": producer,
        "source_kind": "dhcp", "capture_source_id": capture,
        "site_id": SITE, "status": "available", "reason_code": None,
        "observed_at": observed_at, "ingested_at": CAPTURED,
        "content_sha256": "a" * 64,
    }


class FakeSession:
    def __init__(self, read):
        self.read = read
        self.watermark = IngestWatermark(GENERATION, read.watermark)
        self.evidence = copy.deepcopy(read.evidence)
        self.health = copy.deepcopy(read.health)
        self.closed = False

    def __enter__(self):
        self.read.opens += 1
        return self

    def __exit__(self, *_):
        self.closed = True

    @staticmethod
    def _page(rows, cursor, limit, id_field):
        rows = sorted(rows, key=lambda row: (row["observed_at"], row[id_field]))
        if cursor is not None:
            rows = [row for row in rows if (row["observed_at"], row[id_field]) > cursor]
        selected = rows[:limit]
        return {"items": selected, "next_cursor": (
            (selected[-1]["observed_at"], selected[-1][id_field])
            if len(rows) > limit else None)}

    def list_evidence(self, site, mac, start, end, *, limit, cursor):
        rows = [row for row in self.evidence if row["site_id"] == site
                and row["observed_mac"] == mac and start <= row["observed_at"] < end
                and row["ingest_sequence"] <= self.watermark.max_committed_ingest_sequence]
        return self._page(rows, cursor, limit, "evidence_id")

    def list_source_health(self, site, producer, capture, source, start, end, *, limit, cursor):
        rows = [row for row in self.health if (row["site_id"], row["producer_id"],
                row["capture_source_id"], row["source_kind"]) == (site, producer, capture, source)
                and start <= row["observed_at"] < end
                and row["ingest_sequence"] <= self.watermark.max_committed_ingest_sequence]
        return self._page(rows, cursor, limit, "source_health_id")

    def latest_source_health(self, site, producer, capture, source, *, through_utc):
        self.read.health_scopes.append((producer, capture, source, through_utc))
        rows = [row for row in self.health if (row["site_id"], row["producer_id"],
                row["capture_source_id"], row["source_kind"]) == (site, producer, capture, source)
                and row["observed_at"] <= through_utc
                and row["ingest_sequence"] <= self.watermark.max_committed_ingest_sequence]
        return max(rows, key=lambda row: (row["observed_at"], row["source_health_id"])) if rows else None


class FakeRead:
    def __init__(self, evidence_rows=(), health_rows=(), *, watermark=100_000):
        self.evidence = list(evidence_rows)
        self.health = list(health_rows)
        self.watermark = watermark
        self.opens = 0
        self.health_scopes = []

    def open_snapshot_read(self):
        return FakeSession(self)


@dataclass
class Context:
    profile: object
    contents: dict
    read: FakeRead
    service: DeviceFingerprintSnapshotService


def context(evidence_rows=(), health_rows=(), *, content_limits=None, execution_changes=None,
            page_size=500, watermark=100_000):
    value = inputs()
    plan = prepare_initial_foundation_admission(
        value, trusted_admission_clock=lambda: "2026-09-23T00:00:00.000Z")
    cp = {
        "snapshot_content_policy_version": 1,
        "max_authorized_evidence_rows": 10_000,
        "max_authorized_health_rows": 10_000,
        "max_verified_payload_bytes": 10_000_000,
        "max_materialized_payload_bytes": 10_000_000,
        "max_total_semantic_input_bytes": 100_000_000,
    }
    cp.update(content_limits or {})
    ep = {
        "snapshot_execution_policy_version": 1,
        "max_read_transaction_duration_ms": 240_000,
        "sqlite_busy_timeout_ms": 500,
        "max_retry_count": 0,
        "process_memory_guard_bytes": 100_663_296,
    }
    ep.update(execution_changes or {})
    content_policy = make_artifact_content("SnapshotContentPolicy", cp)
    execution_policy = make_artifact_content("SnapshotExecutionPolicy", ep)
    profile_payload = plan.foundation_runtime_profile.semantic_payload
    profile_payload.update({
        "classification_foundation_valid_from_utc": "2026-09-15T10:00:00.000Z",
        "snapshot_content_policy": ref(content_policy),
        "snapshot_execution_policy": ref(execution_policy),
    })
    profile = make_foundation_runtime_profile(profile_payload)
    contents = {item.artifact_id: item for item in (
        *value.immutable_dependencies, plan.origin_runtime_admission,
        content_policy, execution_policy)}
    read = FakeRead(evidence_rows, health_rows, watermark=watermark)
    service = DeviceFingerprintSnapshotService(
        read, foundation_runtime_profile=profile,
        artifact_resolver=lambda artifact_ref: contents[artifact_ref.artifact_id],
        utc_clock=lambda: CAPTURED, process_memory_guard=lambda _limit: True,
        page_size=page_size)
    return Context(profile, contents, read, service)


def build(ctx):
    return ctx.service.build(SITE, MAC, START, END)


def replace_timeline(ctx, epochs):
    old_ref = ctx.profile.semantic_payload["evidence_source_binding_timeline"]
    old = ctx.contents[old_ref["artifact_id"]]
    emitter_ref = old.semantic_payload["binding_epochs"][0]["source_health_emitter_contract"]
    emitter = ctx.contents[emitter_ref["artifact_id"]]
    timeline = make_evidence_source_binding_timeline({
        "binding_timeline_contract_version": 1, "binding_epochs": epochs,
    }, [emitter])
    ctx.contents[timeline.artifact_id] = timeline
    profile_payload = ctx.profile.semantic_payload
    profile_payload["evidence_source_binding_timeline"] = ref(timeline)
    ctx.profile = make_foundation_runtime_profile(profile_payload)
    ctx.service._profile = ctx.profile
    return timeline


def assert_reason(ctx, reason):
    with pytest.raises(SnapshotBuildError) as caught:
        build(ctx)
    assert caught.value.reason_code == reason


def test_known_schema_materializes_only_transient_payload():
    ctx = context([evidence()], [health()])
    result = build(ctx)
    content = result.evidence_snapshot_content.semantic_payload
    record = result.snapshot_record.semantic_payload
    assert len(content["evidence_descriptors"]) == 1
    assert content["evidence_descriptors"][0]["rule_version"] is None
    assert content["evidence_descriptors"][0]["binding_epoch_id"] == "B"
    assert len(content["source_health_descriptors"]) == 1
    assert record["verified_evidence_row_count"] == record["materialized_evidence_row_count"] == 1
    assert record["verified_payload_bytes"] == record["materialized_payload_bytes"] == len(
        canonical_json(KNOWN).encode("utf-8"))
    assert record["build_outcome"] == "success"
    assert result.materialization.ordered_entries[0].normalized_payload == KNOWN
    assert "vendor_class" not in str(content)
    assert "vendor_class" not in str(record)
    assert ctx.read.opens == 1


@pytest.mark.parametrize("raw,reason", [
    ('{', "corrupt_payload"),
    ('{"a":1,"a":2}', "corrupt_payload"),
    ('[]', "corrupt_payload"),
    ('1', "corrupt_payload"),
    ('{"x": 1}', "corrupt_payload"),
])
def test_generic_corruption_fails_whole_snapshot(raw, reason):
    assert_reason(context([evidence(raw=raw)]), reason)


def test_payload_hash_mismatch_fails_whole_snapshot():
    row = evidence()
    row["payload_sha256"] = "0" * 64
    assert_reason(context([row]), "payload_hash_mismatch")


def test_known_invalid_schema_never_falls_back_to_unsupported():
    assert_reason(context([evidence(payload={"unknown": "valid-generic-json"})]),
                  "schema_validation_failure")


def test_intact_future_schema_stays_in_audit_and_verified_sizing():
    row = evidence(version=99, payload={"future": "opaque"})
    result = build(context([row]))
    content, record = result.evidence_snapshot_content.semantic_payload, result.snapshot_record.semantic_payload
    assert len(content["evidence_descriptors"]) == 1
    assert result.materialization.ordered_entries == ()
    assert record["verified_evidence_row_count"] == 1
    assert record["verified_payload_bytes"] == len(row["payload_json"].encode("utf-8"))
    assert record["materialized_evidence_row_count"] == record["materialized_payload_bytes"] == 0


def test_complete_pagination_and_order_independent_of_page_size():
    rows = [evidence(number, observed_at="2026-09-15T12:10:00.000Z")
            for number in range(1, 503)]
    rows[-1]["payload_json"] = canonical_json({**KNOWN, "vendor_class": "last-page"})
    rows[-1]["payload_sha256"] = canonical_sha256(rows[-1]["payload_json"])
    first = build(context(rows, page_size=500))
    second = build(context(list(reversed(rows)), page_size=97))
    assert len(first.evidence_snapshot_content.semantic_payload["evidence_descriptors"]) == 502
    assert any(entry.normalized_payload["vendor_class"] == "last-page"
               for entry in first.materialization.ordered_entries)
    assert first.evidence_snapshot_content.artifact_id == second.evidence_snapshot_content.artifact_id


def test_real_task01_session_freezes_watermark_before_concurrent_insert(tmp_path):
    cfg, _repository = initialized(tmp_path)
    first, later = evidence(1), evidence(2)
    columns = tuple(first)
    insert = ("INSERT INTO device_fingerprint_evidence (" + ",".join(columns) + ") VALUES ("
              + ",".join("?" for _ in columns) + ")")
    with sqlite3.connect(cfg.db_path) as writer:
        writer.execute(insert, tuple(first[field] for field in columns))
        writer.execute("UPDATE device_fingerprint_storage_state SET last_ingest_sequence=1")

    class ConcurrentRead(DeviceFingerprintReadService):
        opens = 0

        def open_snapshot_read(self):
            self.opens += 1
            session = super().open_snapshot_read()
            with sqlite3.connect(cfg.db_path) as writer:
                writer.execute(insert, tuple(later[field] for field in columns))
                writer.execute("UPDATE device_fingerprint_storage_state SET last_ingest_sequence=2")
            return session

    ctx = context()
    read = ConcurrentRead(cfg.db_path, retention_days=30)
    ctx.service._read_service = read
    result = build(ctx)
    content = result.evidence_snapshot_content.semantic_payload
    assert read.opens == 1
    assert content["max_committed_ingest_sequence"] == 1
    assert [row["evidence_id"] for row in content["evidence_descriptors"]] == [first["evidence_id"]]
    assert result.snapshot_record.semantic_payload["verified_evidence_row_count"] == 1


def test_binding_authority_and_cutover_quarantine():
    good = evidence(1)
    wrong_producer = evidence(2, producer="wrong-producer")
    wrong_capture = evidence(3, capture="wrong-capture")
    quarantined = evidence(4, observed_at="2026-09-15T12:00:00.000Z")
    result = build(context([good, wrong_producer, wrong_capture, quarantined]))
    assert [item["evidence_id"] for item in result.evidence_snapshot_content.semantic_payload[
        "evidence_descriptors"]] == [good["evidence_id"]]
    assert result.snapshot_record.semantic_payload["scope_anomaly_count"] == 3
    assert {item["reason_code"] for item in result.snapshot_record.semantic_payload[
        "scope_anomaly_reason_counts"]} == {"binding_scope_mismatch", "binding_cutover_ambiguous"}


def test_guard_adjacent_outside_epoch_never_enters_descriptors_or_health_scope():
    ctx = context([evidence()], [health()])
    timeline_ref = ctx.profile.semantic_payload["evidence_source_binding_timeline"]
    epochs = ctx.contents[timeline_ref["artifact_id"]].semantic_payload["binding_epochs"]
    outside = {**epochs[1], "binding_epoch_id": "C", "origin_group": "tcp",
               "source_kind": "tcp_syn", "effective_from_utc": END}
    replace_timeline(ctx, [*epochs, outside])
    first = build(ctx)
    assert [row["binding_epoch_id"] for row in first.evidence_snapshot_content.semantic_payload[
        "binding_epoch_descriptors"]] == ["A", "B"]
    assert all(scope[2] != "tcp_syn" for scope in ctx.read.health_scopes)
    first_bytes = first.snapshot_record.semantic_payload["total_semantic_input_bytes"]
    ctx.read.health_scopes.clear()
    outside_health = health(1000, observed_at=END)
    outside_health["source_kind"] = "tcp_syn"
    ctx.read.health.append(outside_health)
    second = build(ctx)
    assert second.evidence_snapshot_content.artifact_id == first.evidence_snapshot_content.artifact_id
    assert second.snapshot_record.semantic_payload["total_semantic_input_bytes"] == first_bytes
    assert all(scope[2] != "tcp_syn" for scope in ctx.read.health_scopes)


def test_health_pagination_anchor_and_canonical_order():
    rows = [health(number, observed_at="2026-09-15T12:10:00.000Z")
            for number in range(1, 503)]
    anchor = health(700, observed_at="2026-09-15T11:20:00.000Z")
    result = build(context([], [*rows, anchor], page_size=100))
    health_rows = result.evidence_snapshot_content.semantic_payload["source_health_descriptors"]
    assert len(health_rows) == 503
    assert health_rows[0]["source_health_id"] == anchor["source_health_id"]
    assert health_rows[-1]["source_health_id"] == rows[-1]["source_health_id"]


def test_per_epoch_health_anchors_preserve_old_authority_and_mid_window_transition():
    predecessor = health(700, observed_at="2026-09-15T11:20:00.000Z")
    old = health(701, observed_at="2026-09-15T11:40:00.000Z")
    cutover = health(702, observed_at="2026-09-15T12:00:00.000Z")
    new = health(703, observed_at="2026-09-15T12:10:00.000Z")
    ctx = context([], [predecessor, old, cutover, new])
    result = build(ctx)
    rows = result.evidence_snapshot_content.semantic_payload["source_health_descriptors"]
    assert [(row["source_health_id"], row["binding_epoch_id"]) for row in rows] == [
        (predecessor["source_health_id"], "A"), (old["source_health_id"], "A"),
        (new["source_health_id"], "B"),
    ]
    assert [scope[3] for scope in ctx.read.health_scopes] == [START, "2026-09-15T12:00:00.000Z"]
    assert result.snapshot_record.semantic_payload["scope_anomaly_count"] == 1


def test_pre_epoch_health_cannot_become_new_epoch_anchor():
    early = health(704, observed_at="2026-09-15T10:50:00.000Z")
    ctx = context([], [early])
    result = build(ctx)
    assert result.evidence_snapshot_content.semantic_payload["source_health_descriptors"] == []
    assert len(ctx.read.health_scopes) == 2


def test_conflicting_duplicate_health_id_fails_closed():
    first = health(705, observed_at="2026-09-15T11:20:00.000Z")
    conflicting = health(705, observed_at="2026-09-15T12:10:00.000Z")
    assert_reason(context([], [first, conflicting]), "corrupt_source_health")


@pytest.mark.parametrize("start,end", [
    (END, START), (START, START),
    ("2026-09-15T09:00:00.000Z", END),
    (START, "2026-09-15T14:00:00.001Z"),
])
def test_completed_window_validation(start, end):
    ctx = context()
    with pytest.raises(SnapshotBuildError, match="invalid_window"):
        ctx.service.build(SITE, MAC, start, end)
    assert ctx.read.opens == 0


def test_execution_policy_and_capture_time_do_not_change_content_identity():
    first = build(context([evidence()]))
    ctx = context([evidence()], execution_changes={"max_read_transaction_duration_ms": 120_000})
    ctx.service._utc_clock = lambda: "2026-09-15T15:00:00.000Z"
    second = build(ctx)
    assert first.evidence_snapshot_content.artifact_id == second.evidence_snapshot_content.artifact_id
    assert first.snapshot_record.artifact_id != second.snapshot_record.artifact_id


def test_operational_timeout_busy_and_missing_memory_adapter_are_not_semantic_results():
    ctx = context([evidence()], execution_changes={"max_read_transaction_duration_ms": 1})
    moments = iter((0.0, 0.1))
    ctx.service._monotonic = lambda: next(moments)
    assert_reason(ctx, "snapshot_timeout")
    assert ctx.read.opens == 0

    class BusyRead:
        def __init__(self):
            self.opens = 0

        def open_snapshot_read(self):
            self.opens += 1
            raise sqlite3.OperationalError("database is locked")

    ctx = context(execution_changes={"max_retry_count": 1})
    busy = BusyRead()
    ctx.service._read_service = busy
    assert_reason(ctx, "retryable_sqlite_busy")
    assert busy.opens == 2
    ctx = context()
    ctx.service._memory_guard = None
    assert_reason(ctx, "snapshot_memory_guard_unavailable")
    assert ctx.read.opens == 0


def test_real_task01_busy_wrapper_obeys_retry_limit_without_output(monkeypatch):
    ctx = context(execution_changes={"max_retry_count": 2})
    attempts = []

    def busy_open(_path):
        attempts.append(1)
        raise DeviceFingerprintStorageUnavailable("Fingerprint repository is unavailable") from (
            sqlite3.OperationalError("database is locked"))

    monkeypatch.setattr("app.device_fingerprint.read_service.open_read_only", busy_open)
    ctx.service._read_service = DeviceFingerprintReadService("unused-disposable.db", retention_days=30)
    assert_reason(ctx, "retryable_sqlite_busy")
    assert len(attempts) == 3


def test_nonbusy_task01_storage_wrapper_is_not_misreported_as_busy(monkeypatch):
    ctx = context(execution_changes={"max_retry_count": 2})
    attempts = []

    def failed_open(_path):
        attempts.append(1)
        raise DeviceFingerprintStorageUnavailable("Fingerprint repository is unavailable") from (
            sqlite3.DatabaseError("database disk image is malformed"))

    monkeypatch.setattr("app.device_fingerprint.read_service.open_read_only", failed_open)
    ctx.service._read_service = DeviceFingerprintReadService("unused-disposable.db", retention_days=30)
    assert_reason(ctx, "storage_unavailable")
    assert len(attempts) == 1


def test_profile_dependency_mismatch_fails_before_task01_row_processing():
    ctx = context([evidence()])
    payload = ctx.profile.semantic_payload
    payload["ttl_capture_placement_proof"] = None
    ctx.service._profile = make_foundation_runtime_profile(payload)
    assert_reason(ctx, "runtime_profile_incompatible")
    assert ctx.read.opens == 0


def test_binding_unavailable_fails_closed_before_task01_read():
    ctx = context()
    with pytest.raises(SnapshotBuildError, match="binding_unavailable"):
        ctx.service.build("e" * 24, MAC, START, END)
    assert ctx.read.opens == 0


def test_all_quarantine_window_builds_without_nearest_epoch_assignment():
    cutover = "2026-09-15T12:00:00.000Z"
    evidence_row = evidence(observed_at=cutover)
    health_row = health(observed_at=cutover)
    ctx = context([evidence_row], [health_row])
    result = ctx.service.build(SITE, MAC, "2026-09-15T11:59:59.000Z",
                               "2026-09-15T12:00:01.000Z")
    content = result.evidence_snapshot_content.semantic_payload
    record = result.snapshot_record.semantic_payload
    assert [row["binding_epoch_id"] for row in content["binding_epoch_descriptors"]] == ["A", "B"]
    assert content["evidence_descriptors"] == []
    assert content["source_health_descriptors"] == []
    assert result.materialization.ordered_entries == ()
    assert record["build_outcome"] == "success"
    assert record["scope_anomaly_reason_counts"] == [
        {"reason_code": "binding_cutover_ambiguous", "count": 2},
    ]
    assert ctx.read.opens == 1


@pytest.mark.parametrize("field", [
    "max_authorized_evidence_rows", "max_authorized_health_rows",
    "max_verified_payload_bytes", "max_materialized_payload_bytes",
    "max_total_semantic_input_bytes",
])
def test_zero_pinned_content_ceiling_fails_before_task01_read(field):
    ctx = context([evidence()], content_limits={field: 0})
    assert_reason(ctx, "runtime_profile_incompatible")
    assert ctx.read.opens == 0


@pytest.mark.parametrize("field,measured", [
    ("max_authorized_evidence_rows", "verified_evidence_row_count"),
    ("max_authorized_health_rows", None),
    ("max_verified_payload_bytes", "verified_payload_bytes"),
    ("max_materialized_payload_bytes", "materialized_payload_bytes"),
    ("max_total_semantic_input_bytes", "total_semantic_input_bytes"),
])
def test_content_policy_exact_boundary_and_one_less(field, measured):
    rows, health_rows = [evidence(1), evidence(2)], [health(1), health(2)]
    baseline = build(context(rows, health_rows)).snapshot_record.semantic_payload
    amount = len(health_rows) if measured is None else baseline[measured]
    assert build(context(rows, health_rows, content_limits={field: amount})).snapshot_record
    assert_reason(context(rows, health_rows, content_limits={field: amount - 1}), "resource_limited")


def test_closed_snapshot_content_and_record_shapes():
    ctx = context([evidence()], [health()])
    result = build(ctx)
    payload = result.evidence_snapshot_content.semantic_payload
    profile = ctx.profile
    refs = ctx.contents
    kwargs = dict(
        foundation_runtime_profile=profile,
        binding_timeline=refs[profile.semantic_payload["evidence_source_binding_timeline"]["artifact_id"]],
        binding_clock_policy=refs[profile.semantic_payload["binding_clock_policy"]["artifact_id"]],
        schema_registry_contract=refs[profile.semantic_payload["evidence_schema_registry_contract"]["artifact_id"]],
        origin_runtime_admission=refs[profile.semantic_payload["origin_runtime_admission"]["artifact_id"]],
    )
    assert make_evidence_snapshot_content(payload, **kwargs) == result.evidence_snapshot_content
    for changed in ({**payload, "extra": 1}, {k: v for k, v in payload.items() if k != "site_id"},
                    {**payload, "snapshot_contract_version": True}):
        with pytest.raises(DeviceFingerprintValidationError):
            make_evidence_snapshot_content(changed, **kwargs)
    wrong_ref = copy.deepcopy(payload)
    wrong_ref["binding_clock_policy"]["content_sha256"] = "f" * 64
    with pytest.raises(DeviceFingerprintValidationError):
        make_evidence_snapshot_content(wrong_ref, **kwargs)
    duplicated = copy.deepcopy(payload)
    duplicated["binding_epoch_descriptors"].append(duplicated["binding_epoch_descriptors"][0])
    with pytest.raises(DeviceFingerprintValidationError):
        make_evidence_snapshot_content(duplicated, **kwargs)
    for descriptor_field in ("evidence_descriptors", "source_health_descriptors"):
        for bad_id in ([], {}, None, ""):
            invalid = copy.deepcopy(payload)
            invalid[descriptor_field][0]["binding_epoch_id"] = bad_id
            with pytest.raises(DeviceFingerprintValidationError):
                make_evidence_snapshot_content(invalid, **kwargs)
    record = result.snapshot_record.semantic_payload
    record_kwargs = dict(
        evidence_snapshot_content=result.evidence_snapshot_content,
        foundation_runtime_profile=profile,
        snapshot_content_policy=refs[profile.semantic_payload["snapshot_content_policy"]["artifact_id"]],
        snapshot_execution_policy=refs[profile.semantic_payload["snapshot_execution_policy"]["artifact_id"]],
    )
    assert make_snapshot_record(record, **record_kwargs) == result.snapshot_record
    for changed in ({**record, "extra": 1}, {k: v for k, v in record.items() if k != "build_outcome"},
                    {**record, "scope_anomaly_count": 1},
                    {**record, "snapshot_captured_at_utc": START}):
        with pytest.raises(DeviceFingerprintValidationError):
            make_snapshot_record(changed, **record_kwargs)
    duplicate_reasons = {**record, "scope_anomaly_count": 2,
                         "scope_anomaly_reason_counts": [
                             {"reason_code": "scope", "count": 1},
                             {"reason_code": "scope", "count": 1}]}
    with pytest.raises(DeviceFingerprintValidationError):
        make_snapshot_record(duplicate_reasons, **record_kwargs)
    wrong_policy = copy.deepcopy(record)
    wrong_policy["snapshot_execution_policy"] = ref(make_artifact_content(
        "SnapshotExecutionPolicy", {"synthetic": "wrong"}))
    with pytest.raises(DeviceFingerprintValidationError):
        make_snapshot_record(wrong_policy, **record_kwargs)
    content_refs = {item.artifact_type for item in extract_direct_artifact_refs(
        result.evidence_snapshot_content) for item in [ctx.contents[item.artifact_id]]}
    assert {"EvidenceSourceBindingTimeline", "BindingClockPolicy", "EvidenceSchemaRegistryContract",
            "OriginRuntimeAdmission", "TTLCapturePlacementProof", "SourceHealthEmitterContract"} <= content_refs
    record_refs = {item.artifact_id for item in extract_direct_artifact_refs(result.snapshot_record)}
    assert record_refs == {record[field]["artifact_id"] for field in (
        "evidence_snapshot_content", "foundation_runtime_profile", "snapshot_content_policy",
        "snapshot_execution_policy")}
