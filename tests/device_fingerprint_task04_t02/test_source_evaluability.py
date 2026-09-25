"""Exact T-02 interval, cutover, freshness and artifact-identity contracts."""

from __future__ import annotations

from copy import deepcopy

import pytest

from app.device_fingerprint.artifact_content import ArtifactRef, make_artifact_content
from app.device_fingerprint.models import DeviceFingerprintValidationError
from app.device_fingerprint.runtime_profile_artifacts import make_foundation_runtime_profile
from app.device_fingerprint.source_evaluability import (
    DeviceFingerprintSourceEvaluabilityBuilder, make_source_evaluability,
)
from tests.device_fingerprint import SITE
from tests.device_fingerprint_task04_t01.test_snapshot_service import (
    END, MAC, START, context, evidence, health,
)

_AFTER_CUTOVER = "2026-09-15T12:00:03.000Z"
_B_END = "2026-09-15T12:20:00.000Z"


def _ref(content):
    return ArtifactRef(content.artifact_id, content.content_sha256).as_dict()


def _health(number, observed_at, status="available", reason=None):
    row = health(number, observed_at=observed_at)
    row.update(status=status, reason_code=reason)
    return row


def _build(health_rows=(), evidence_rows=(), *, start=START, end=END):
    ctx = context(evidence_rows, health_rows)
    snapshot = ctx.service.build(SITE, MAC, start, end).evidence_snapshot_content
    builder = DeviceFingerprintSourceEvaluabilityBuilder(
        foundation_runtime_profile=ctx.profile,
        artifact_resolver=lambda reference: ctx.contents[reference.artifact_id],
    )
    output = builder.build(snapshot)
    return ctx, snapshot, output


def _entry(output, epoch="B"):
    return next(item for item in output.semantic_payload["source_entries"]
                if item["binding_epoch_id"] == epoch)


def _intervals(output, epoch="B"):
    return _entry(output, epoch)["coverage_intervals"]


def _policy(ctx):
    return ctx.contents[ctx.profile.semantic_payload["source_health_policy"]["artifact_id"]]


def _manual(coverage="covered_available", reason="HEALTH_AVAILABLE", *,
            start=_AFTER_CUTOVER, end=_B_END, reasons=None):
    ctx = context()
    snapshot = ctx.service.build(SITE, MAC, start, end).evidence_snapshot_content
    binding = snapshot.semantic_payload["binding_epoch_descriptors"][0]
    interval = {"start_utc": start, "end_utc": end, "coverage_class": coverage,
                "reason_classification": reason, "reason_code_refs": reasons or []}
    entry = {field: binding[field] for field in (
        "origin_group", "source_kind", "binding_epoch_id", "producer_id", "capture_source_id")}
    entry.update(aggregate_evaluability_state={
        "covered_available": "evaluable",
        "acquisition_unavailable": "not_evaluable",
        "delivery_unavailable_loss_possible": "unknown",
        "delivery_loss_confirmed": "not_evaluable",
        "unsupported": "not_evaluable", "unknown": "unknown",
    }[coverage], coverage_intervals=[interval], explanation_codes=[reason])
    payload = {"source_evaluability_contract_version": 1,
               "evidence_snapshot_content": _ref(snapshot),
               "source_health_policy": _ref(_policy(ctx)), "source_entries": [entry]}
    return ctx, snapshot, payload


def _validate(ctx, snapshot, payload):
    return make_source_evaluability(payload, evidence_snapshot_content=snapshot,
                                   source_health_policy=_policy(ctx))


@pytest.mark.parametrize("status,reason,coverage,classification,aggregate", [
    ("available", None, "covered_available", "HEALTH_AVAILABLE", "evaluable"),
    ("unavailable", "capture_interface_unavailable", "acquisition_unavailable",
     "ACQUISITION_UNAVAILABLE", "not_evaluable"),
    ("unavailable", "ingest_delivery_unavailable", "delivery_unavailable_loss_possible",
     "DELIVERY_UNAVAILABLE_LOSS_POSSIBLE", "unknown"),
    ("unsupported", None, "unsupported", "SOURCE_UNSUPPORTED", "not_evaluable"),
    ("unavailable", "unrecognized_reason", "unknown", "HEALTH_UNKNOWN", "unknown"),
])
def test_t02_01_04_07_exact_health_dispositions(status, reason, coverage, classification, aggregate):
    row = _health(1, _AFTER_CUTOVER, status, reason)
    _, _, output = _build([row], start=_AFTER_CUTOVER, end="2026-09-15T12:01:00.000Z")
    interval = _intervals(output)[0]
    assert (interval["coverage_class"], interval["reason_classification"]) == (
        coverage, classification)
    assert interval["reason_code_refs"] == ([reason] if reason is not None else [])
    assert _entry(output)["aggregate_evaluability_state"] == aggregate


def test_t02_05_delivery_loss_confirmed_closed_schema_without_policy_mutation():
    ctx, snapshot, payload = _manual("delivery_loss_confirmed", "DELIVERY_LOSS_CONFIRMED")
    result = _validate(ctx, snapshot, payload)
    assert _entry(result)["aggregate_evaluability_state"] == "not_evaluable"
    assert _intervals(result)[0]["coverage_class"] == "delivery_loss_confirmed"
    assert all(mapping["coverage_class"] != "delivery_loss_confirmed"
               for rule in _policy(ctx).semantic_payload["emitter_source_family_rules"]
               for mapping in rule["status_reason_failure_domain_mappings"])


def test_t02_06_missing_health_is_unknown_without_claims():
    _, _, output = _build(start=_AFTER_CUTOVER, end=_B_END)
    assert _intervals(output) == [{
        "start_utc": _AFTER_CUTOVER, "end_utc": _B_END,
        "coverage_class": "unknown", "reason_classification": "HEALTH_UNKNOWN",
        "reason_code_refs": [],
    }]
    assert _entry(output)["aggregate_evaluability_state"] == "unknown"
    assert set(output.semantic_payload) == {
        "source_evaluability_contract_version", "evidence_snapshot_content",
        "source_health_policy", "source_entries",
    }


def test_exact_emitter_source_family_rule_missing_is_conservative_unknown():
    ctx = context([evidence(1, observed_at="2026-09-15T12:01:00.000Z")],
                  [_health(1, _AFTER_CUTOVER)])
    snapshot = ctx.service.build(SITE, MAC, _AFTER_CUTOVER, _B_END).evidence_snapshot_content
    policy_payload = _policy(ctx).semantic_payload
    binding = snapshot.semantic_payload["binding_epoch_descriptors"][0]
    policy_payload["emitter_source_family_rules"] = [
        rule for rule in policy_payload["emitter_source_family_rules"]
        if (rule["source_health_emitter_contract"], rule["source_kind"]) != (
            binding["source_health_emitter_contract"], binding["source_kind"])]
    missing_rule_policy = make_artifact_content("SourceHealthPolicy", policy_payload)
    ctx.contents[missing_rule_policy.artifact_id] = missing_rule_policy
    profile_payload = ctx.profile.semantic_payload
    profile_payload["source_health_policy"] = _ref(missing_rule_policy)
    profile = make_foundation_runtime_profile(profile_payload)
    builder = DeviceFingerprintSourceEvaluabilityBuilder(
        foundation_runtime_profile=profile,
        artifact_resolver=lambda reference: ctx.contents[reference.artifact_id])
    output = builder.build(snapshot)
    assert _intervals(output) == [{
        "start_utc": _AFTER_CUTOVER, "end_utc": _B_END,
        "coverage_class": "unknown", "reason_classification": "HEALTH_UNKNOWN",
        "reason_code_refs": [],
    }]


def test_t02_08_10_exact_freshness_boundary_and_predecessor_split():
    row = _health(2, _AFTER_CUTOVER)
    _, _, output = _build([row], start=_AFTER_CUTOVER,
                          end="2026-09-15T12:10:03.002Z")
    assert [(item["start_utc"], item["end_utc"], item["reason_classification"])
            for item in _intervals(output)] == [
        (_AFTER_CUTOVER, "2026-09-15T12:10:03.001Z", "HEALTH_AVAILABLE"),
        ("2026-09-15T12:10:03.001Z", "2026-09-15T12:10:03.002Z", "HEARTBEAT_STALE"),
    ]


def test_t02_08_age_equal_timeout_is_fresh():
    row = _health(3, _AFTER_CUTOVER)
    _, _, output = _build([row], start="2026-09-15T12:10:03.000Z",
                          end="2026-09-15T12:10:03.001Z")
    assert _intervals(output)[0]["reason_classification"] == "HEALTH_AVAILABLE"


def test_t02_09_predecessor_before_segment_start_is_effective_when_fresh():
    row = _health(4, _AFTER_CUTOVER)
    _, snapshot, output = _build([row], start="2026-09-15T12:02:00.000Z",
                                 end="2026-09-15T12:03:00.000Z")
    assert snapshot.semantic_payload["source_health_descriptors"][0]["observed_at"] == row["observed_at"]
    assert _intervals(output)[0]["coverage_class"] == "covered_available"


@pytest.mark.parametrize("same_sequence", [False, True])
def test_same_timestamp_health_tie_uses_ingest_then_health_id(same_sequence):
    first = _health(5, _AFTER_CUTOVER, "available")
    second = _health(6, _AFTER_CUTOVER, "unavailable", "capture_interface_unavailable")
    if same_sequence:
        second["ingest_sequence"] = first["ingest_sequence"]
    _, _, output = _build([second, first], start=_AFTER_CUTOVER,
                          end="2026-09-15T12:01:00.000Z")
    assert _intervals(output)[0]["coverage_class"] == "acquisition_unavailable"


def test_t02_11_12_14_15_transition_merge_and_reason_union():
    first = _health(10, "2026-09-15T12:01:00.000Z", "unavailable", "capture_interface_unavailable")
    second = _health(11, "2026-09-15T12:02:00.000Z", "unavailable", "raw_parser_unavailable")
    third = _health(12, "2026-09-15T12:03:00.000Z", "available")
    _, _, output = _build([first, second, third], start=_AFTER_CUTOVER,
                          end="2026-09-15T12:04:00.000Z")
    intervals = _intervals(output)
    assert [(row["start_utc"], row["end_utc"], row["reason_classification"])
            for row in intervals] == [
        (_AFTER_CUTOVER, first["observed_at"], "HEALTH_UNKNOWN"),
        (first["observed_at"], third["observed_at"], "ACQUISITION_UNAVAILABLE"),
        (third["observed_at"], "2026-09-15T12:04:00.000Z", "HEALTH_AVAILABLE"),
    ]
    assert intervals[1]["reason_code_refs"] == ["capture_interface_unavailable", "raw_parser_unavailable"]
    assert all(row["start_utc"] < row["end_utc"] for row in intervals)


def test_t02_13_different_reason_classification_prevents_merge():
    row = _health(13, "2026-09-15T12:01:00.000Z", "unavailable", "unrecognized_reason")
    _, _, output = _build([row], start=_AFTER_CUTOVER, end="2026-09-15T12:02:00.000Z")
    intervals = _intervals(output)
    assert len(intervals) == 1  # Same unknown/HEALTH_UNKNOWN normalizes across the event.
    ctx, snapshot, payload = _manual("unknown", "HEALTH_UNKNOWN")
    split = "2026-09-15T12:10:00.000Z"
    payload["source_entries"][0]["coverage_intervals"] = [
        {"start_utc": _AFTER_CUTOVER, "end_utc": split, "coverage_class": "unknown",
         "reason_classification": "HEALTH_UNKNOWN", "reason_code_refs": []},
        {"start_utc": split, "end_utc": _B_END, "coverage_class": "unknown",
         "reason_classification": "HEARTBEAT_STALE", "reason_code_refs": []},
    ]
    payload["source_entries"][0]["explanation_codes"] = ["HEARTBEAT_STALE", "HEALTH_UNKNOWN"]
    assert len(_intervals(_validate(ctx, snapshot, payload))) == 2


@pytest.mark.parametrize("mutate", [
    lambda p: p["source_entries"][0]["coverage_intervals"][0].update(
        start_utc="2026-09-15T12:00:04.000Z"),
    lambda p: p["source_entries"][0]["coverage_intervals"][0].update(
        end_utc="2026-09-15T12:19:59.999Z"),
    lambda p: p["source_entries"][0]["coverage_intervals"][0].update(
        start_utc="2026-09-15T12:00:02.000Z"),
    lambda p: p["source_entries"][0]["coverage_intervals"][0].update(
        end_utc="2026-09-15T12:20:00.001Z"),
])
def test_t02_16_19_wrong_segment_boundaries_rejected(mutate):
    ctx, snapshot, payload = _manual()
    mutate(payload)
    with pytest.raises(DeviceFingerprintValidationError):
        _validate(ctx, snapshot, payload)


@pytest.mark.parametrize("second_start", [
    "2026-09-15T12:10:00.001Z", "2026-09-15T12:09:59.999Z",
])
def test_t02_16_17_gap_or_overlap_rejected(second_start):
    ctx, snapshot, payload = _manual()
    first = payload["source_entries"][0]["coverage_intervals"][0]
    first["end_utc"] = "2026-09-15T12:10:00.000Z"
    second = {**first, "start_utc": second_start, "end_utc": _B_END,
              "coverage_class": "unknown", "reason_classification": "HEALTH_UNKNOWN"}
    payload["source_entries"][0]["coverage_intervals"].append(second)
    payload["source_entries"][0]["explanation_codes"] = ["HEALTH_AVAILABLE", "HEALTH_UNKNOWN"]
    with pytest.raises(DeviceFingerprintValidationError):
        _validate(ctx, snapshot, payload)


def test_t02_20_21_23_64_order_and_reconstruction_identity():
    first = _health(20, "2026-09-15T11:40:00.000Z")
    second = _health(21, "2026-09-15T12:10:00.000Z")
    _, snap_a, out_a = _build([first, second])
    _, snap_b, out_b = _build([second, first])
    assert snap_a.artifact_id == snap_b.artifact_id
    assert (out_a.artifact_id, out_a.content_sha256) == (out_b.artifact_id, out_b.content_sha256)
    ctx = context()
    snapshot = ctx.service.build(SITE, MAC, START, END).evidence_snapshot_content
    builder = DeviceFingerprintSourceEvaluabilityBuilder(
        foundation_runtime_profile=ctx.profile,
        artifact_resolver=lambda reference: ctx.contents[reference.artifact_id])
    output = builder.build(snapshot)
    payload = output.semantic_payload
    payload["source_entries"].reverse()
    assert _validate(ctx, snapshot, payload).artifact_id == output.artifact_id
    assert output.artifact_id == builder.build(snapshot).artifact_id


def test_t02_22_reason_code_set_input_order_does_not_change_digest():
    ctx, snapshot, payload = _manual("acquisition_unavailable", "ACQUISITION_UNAVAILABLE",
                                     reasons=["z_reason", "a_reason"])
    first = _validate(ctx, snapshot, payload)
    payload["source_entries"][0]["coverage_intervals"][0]["reason_code_refs"].reverse()
    second = _validate(ctx, snapshot, payload)
    assert first.artifact_id == second.artifact_id
    assert _intervals(first)[0]["reason_code_refs"] == ["a_reason", "z_reason"]


def test_t02_24_covered_delayed_rejected():
    ctx, snapshot, payload = _manual()
    payload["source_entries"][0]["coverage_intervals"][0]["coverage_class"] = "covered_delayed"
    with pytest.raises(DeviceFingerprintValidationError):
        _validate(ctx, snapshot, payload)


def test_t02_25_30_cutover_quarantine_old_new_no_nearest_or_inheritance():
    old = _health(30, "2026-09-15T11:59:55.000Z")
    _, _, output = _build([old], start="2026-09-15T11:59:55.000Z",
                          end="2026-09-15T12:00:05.000Z")
    assert [(row["start_utc"], row["end_utc"], row["reason_classification"])
            for row in _intervals(output, "A")] == [
        ("2026-09-15T11:59:55.000Z", "2026-09-15T11:59:57.000Z", "HEALTH_AVAILABLE"),
        ("2026-09-15T11:59:57.000Z", "2026-09-15T12:00:00.000Z", "BINDING_CUTOVER_UNKNOWN"),
    ]
    assert [(row["start_utc"], row["end_utc"], row["reason_classification"])
            for row in _intervals(output, "B")] == [
        ("2026-09-15T12:00:00.000Z", _AFTER_CUTOVER, "BINDING_CUTOVER_UNKNOWN"),
        (_AFTER_CUTOVER, "2026-09-15T12:00:05.000Z", "HEALTH_UNKNOWN"),
    ]
    assert _entry(output, "B")["aggregate_evaluability_state"] == "unknown"
    assert _entry(output, "A")["aggregate_evaluability_state"] == "evaluable"
    _, _, all_quarantine = _build(start="2026-09-15T11:59:59.000Z",
                                  end="2026-09-15T12:00:01.000Z")
    assert all(_entry(all_quarantine, epoch)["aggregate_evaluability_state"] == "unknown"
               for epoch in ("A", "B"))
    assert all(all(row["reason_classification"] == "BINDING_CUTOVER_UNKNOWN"
                   for row in _intervals(all_quarantine, epoch)) for epoch in ("A", "B"))


def test_t02_31_nonquarantine_covered_plus_quarantine_is_evaluable():
    old = _health(31, "2026-09-15T11:59:55.000Z")
    new = _health(32, _AFTER_CUTOVER)
    _, _, output = _build([old, new], start="2026-09-15T11:59:55.000Z",
                          end="2026-09-15T12:00:05.000Z")
    assert all(_entry(output, epoch)["aggregate_evaluability_state"] == "evaluable"
               for epoch in ("A", "B"))
    assert all(any(row["reason_classification"] == "BINDING_CUTOVER_UNKNOWN"
                   for row in _intervals(output, epoch)) for epoch in ("A", "B"))


def test_t02_29_new_epoch_health_changes_only_new_epoch_future_interval():
    old = _health(33, "2026-09-15T11:59:55.000Z")
    new = _health(34, "2026-09-15T12:00:04.000Z")
    _, _, output = _build([old, new], start="2026-09-15T11:59:55.000Z",
                          end="2026-09-15T12:00:05.000Z")
    assert [(row["start_utc"], row["end_utc"], row["reason_classification"])
            for row in _intervals(output, "B")] == [
        ("2026-09-15T12:00:00.000Z", _AFTER_CUTOVER, "BINDING_CUTOVER_UNKNOWN"),
        (_AFTER_CUTOVER, new["observed_at"], "HEALTH_UNKNOWN"),
        (new["observed_at"], "2026-09-15T12:00:05.000Z", "HEALTH_AVAILABLE"),
    ]


@pytest.mark.parametrize("second_status,second_reason,expected", [
    ("unavailable", "capture_interface_unavailable", "partially_evaluable"),
    ("unavailable", "ingest_delivery_unavailable", "partially_evaluable"),
])
def test_t02_32_33_mixed_covered_and_failure_is_partial(second_status, second_reason, expected):
    first = _health(40, _AFTER_CUTOVER)
    second = _health(41, "2026-09-15T12:01:00.000Z", second_status, second_reason)
    _, _, output = _build([first, second], start=_AFTER_CUTOVER,
                          end="2026-09-15T12:02:00.000Z")
    assert _entry(output)["aggregate_evaluability_state"] == expected


@pytest.mark.parametrize("coverage,reason,aggregate", [
    ("acquisition_unavailable", "ACQUISITION_UNAVAILABLE", "not_evaluable"),
    ("unsupported", "SOURCE_UNSUPPORTED", "not_evaluable"),
    ("delivery_loss_confirmed", "DELIVERY_LOSS_CONFIRMED", "not_evaluable"),
    ("unknown", "HEALTH_UNKNOWN", "unknown"),
    ("delivery_unavailable_loss_possible", "DELIVERY_UNAVAILABLE_LOSS_POSSIBLE", "unknown"),
])
def test_t02_34_38_exact_aggregate_precedence(coverage, reason, aggregate):
    ctx, snapshot, payload = _manual(coverage, reason)
    output = _validate(ctx, snapshot, payload)
    assert _entry(output)["aggregate_evaluability_state"] == aggregate


@pytest.mark.parametrize("status,reason,expected_coverage,expected_reason", [
    ("unavailable", "capture_interface_unavailable", "acquisition_unavailable",
     "HEALTH_EVIDENCE_INCONSISTENCY"),
    ("unsupported", None, "unsupported", "UNSUPPORTED_BUT_EVIDENCE_PRESENT"),
    ("unavailable", "ingest_delivery_unavailable", "delivery_unavailable_loss_possible",
     "DELIVERY_UNAVAILABLE_LOSS_POSSIBLE"),
    ("unavailable", "unrecognized_reason", "unknown", "HEALTH_UNKNOWN"),
])
def test_t02_39_41_43_present_evidence_matrix(status, reason, expected_coverage, expected_reason):
    item = evidence(50, observed_at="2026-09-15T12:01:00.000Z")
    health_row = _health(50, _AFTER_CUTOVER, status, reason)
    _, snapshot, output = _build([health_row], [item], start=_AFTER_CUTOVER,
                                 end="2026-09-15T12:02:00.000Z")
    assert len(snapshot.semantic_payload["evidence_descriptors"]) == 1
    assert (_intervals(output)[0]["coverage_class"],
            _intervals(output)[0]["reason_classification"]) == (
        expected_coverage, expected_reason)
    assert set(output.semantic_payload) == {
        "source_evaluability_contract_version", "evidence_snapshot_content",
        "source_health_policy", "source_entries",
    }


def test_t02_42_delivery_loss_confirmed_with_evidence_remains_loss_confirmed():
    ctx = context([evidence(51, observed_at="2026-09-15T12:01:00.000Z")])
    snapshot = ctx.service.build(SITE, MAC, _AFTER_CUTOVER, _B_END).evidence_snapshot_content
    binding = snapshot.semantic_payload["binding_epoch_descriptors"][0]
    entry = {field: binding[field] for field in (
        "origin_group", "source_kind", "binding_epoch_id", "producer_id", "capture_source_id")}
    entry.update(aggregate_evaluability_state="not_evaluable", explanation_codes=["DELIVERY_LOSS_CONFIRMED"],
                 coverage_intervals=[{"start_utc": _AFTER_CUTOVER, "end_utc": _B_END,
                                      "coverage_class": "delivery_loss_confirmed",
                                      "reason_classification": "DELIVERY_LOSS_CONFIRMED",
                                      "reason_code_refs": []}])
    payload = {"source_evaluability_contract_version": 1, "evidence_snapshot_content": _ref(snapshot),
               "source_health_policy": _ref(_policy(ctx)), "source_entries": [entry]}
    assert _intervals(_validate(ctx, snapshot, payload))[0]["reason_classification"] == (
        "DELIVERY_LOSS_CONFIRMED")
    assert len(snapshot.semantic_payload["evidence_descriptors"]) == 1


@pytest.mark.parametrize("status,reason,expected", [
    ("available", None, "covered_available"),
    ("unavailable", "capture_interface_unavailable", "acquisition_unavailable"),
    ("unavailable", "ingest_delivery_unavailable", "delivery_unavailable_loss_possible"),
])
def test_t02_44_45_absence_does_not_create_negative_claim(status, reason, expected):
    _, snapshot, output = _build([_health(60, _AFTER_CUTOVER, status, reason)],
                                 start=_AFTER_CUTOVER, end="2026-09-15T12:01:00.000Z")
    assert snapshot.semantic_payload["evidence_descriptors"] == []
    assert _intervals(output)[0]["coverage_class"] == expected
    assert all("claim" not in key for key in output.semantic_payload)


def test_t02_46_47_recovery_and_backfill_do_not_upgrade_prior_loss():
    unavailable = _health(70, _AFTER_CUTOVER, "unavailable", "ingest_delivery_unavailable")
    recovered = _health(71, "2026-09-15T12:02:00.000Z", "available")
    backfilled = evidence(71, observed_at="2026-09-15T12:01:00.000Z")
    _, snapshot, output = _build([unavailable, recovered], [backfilled],
                                 start=_AFTER_CUTOVER, end="2026-09-15T12:03:00.000Z")
    assert len(snapshot.semantic_payload["evidence_descriptors"]) == 1
    assert [(row["coverage_class"], row["reason_classification"])
            for row in _intervals(output)] == [
        ("delivery_unavailable_loss_possible", "DELIVERY_UNAVAILABLE_LOSS_POSSIBLE"),
        ("covered_available", "HEALTH_AVAILABLE"),
    ]
    assert "covered_delayed" not in str(output.semantic_payload)


def test_t02_48_no_mac_registry_entry():
    _, _, output = _build()
    assert {entry["origin_group"] for entry in output.semantic_payload["source_entries"]} == {"dhcp"}


@pytest.mark.parametrize("field", [
    "evidence_source_binding_timeline", "binding_clock_policy",
])
def test_t02_49_50_snapshot_pinned_reference_mismatch_fails(field):
    ctx = context()
    snapshot = ctx.service.build(SITE, MAC, START, END).evidence_snapshot_content
    changed = snapshot.semantic_payload
    changed[field] = {**changed[field], "artifact_id": changed[field]["artifact_id"].replace(
        changed[field]["content_sha256"], "0" * 64), "content_sha256": "0" * 64}
    wrong = make_artifact_content("EvidenceSnapshotContent", changed)
    builder = DeviceFingerprintSourceEvaluabilityBuilder(
        foundation_runtime_profile=ctx.profile,
        artifact_resolver=lambda reference: ctx.contents[reference.artifact_id])
    with pytest.raises(DeviceFingerprintValidationError):
        builder.build(wrong)


def test_t02_51_profile_mismatch_and_wrong_input_type_fail():
    ctx = context()
    changed = ctx.profile.semantic_payload
    changed["snapshot_contract_version"] = 2
    mismatched = make_foundation_runtime_profile(changed)
    builder = DeviceFingerprintSourceEvaluabilityBuilder(
        foundation_runtime_profile=mismatched,
        artifact_resolver=lambda reference: ctx.contents[reference.artifact_id])
    snapshot = ctx.service.build(SITE, MAC, START, END).evidence_snapshot_content
    with pytest.raises(DeviceFingerprintValidationError):
        builder.build(snapshot)
    with pytest.raises(DeviceFingerprintValidationError):
        builder.build(_policy(ctx))


@pytest.mark.parametrize("mutation", [
    lambda p: p["evidence_snapshot_content"].update(
        artifact_id="EvidenceSnapshotContent:v1:sha256:" + "0" * 64, content_sha256="0" * 64),
    lambda p: p["source_health_policy"].update(
        artifact_id="SourceHealthPolicy:v1:sha256:" + "0" * 64, content_sha256="0" * 64),
    lambda p: p.update(extra=True),
    lambda p: p.pop("source_entries"),
    lambda p: p["source_entries"][0].update(extra=True),
    lambda p: p["source_entries"][0]["coverage_intervals"][0].update(coverage_class="covered_delayed"),
    lambda p: p["source_entries"][0]["coverage_intervals"][0].update(reason_classification="OTHER"),
    lambda p: p["source_entries"][0]["coverage_intervals"][0].update(
        reason_classification="SOURCE_UNSUPPORTED"),
    lambda p: p["source_entries"][0].update(aggregate_evaluability_state="maybe"),
    lambda p: p["source_entries"].append(deepcopy(p["source_entries"][0])),
    lambda p: p["source_entries"][0].update(binding_epoch_id="missing"),
    lambda p: p["source_entries"][0].update(producer_id="wrong-producer"),
    lambda p: p["source_entries"][0].update(explanation_codes=[]),
])
def test_t02_52_63_closed_artifact_mutations_rejected(mutation):
    ctx, snapshot, payload = _manual()
    mutation(payload)
    with pytest.raises(DeviceFingerprintValidationError):
        _validate(ctx, snapshot, payload)


def test_t02_builder_resolves_exact_pinned_dependencies_only_once():
    ctx = context()
    calls = []

    def resolve(reference):
        calls.append(reference.artifact_id)
        return ctx.contents[reference.artifact_id]

    builder = DeviceFingerprintSourceEvaluabilityBuilder(
        foundation_runtime_profile=ctx.profile, artifact_resolver=resolve)
    assert len(calls) == 3
    snapshot = ctx.service.build(SITE, MAC, START, END).evidence_snapshot_content
    builder.build(snapshot)
    assert len(calls) == 3
    assert {ctx.contents[identity].artifact_type for identity in calls} == {
        "SourceHealthPolicy", "EvidenceSourceBindingTimeline", "BindingClockPolicy"}
