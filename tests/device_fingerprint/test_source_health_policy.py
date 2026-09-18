"""Frozen F-B2 policy content and pure source-health interpretation."""

from copy import deepcopy

import pytest

from app.device_fingerprint.artifact_content import ArtifactRef
from app.device_fingerprint.models import DeviceFingerprintValidationError
from app.device_fingerprint.source_health_emitter_contracts import (
    build_network_sensor_source_health_emitter_contract,
    build_periodic_portal_source_health_emitter_contract,
    build_portal_source_health_emitter_contract,
)
from app.device_fingerprint.source_health_policy import (
    TASK01_DELAYED_EVENT_REF, TASK01_TIMESTAMP_SKEW_REF,
    build_current_source_health_policy, evaluate_source_health, make_source_health_policy,
)

T = "2026-09-18T12:00:00.000Z"


def _emitters():
    return (build_network_sensor_source_health_emitter_contract(),
            build_portal_source_health_emitter_contract(),
            build_periodic_portal_source_health_emitter_contract())


def _ref(emitter):
    return ArtifactRef(emitter.artifact_id, emitter.content_sha256).as_dict()


def _event(emitter, *, kind="portal_headers", status="available", reason=None):
    return {"source_health_emitter_contract": _ref(emitter), "source_kind": kind,
            "status": status, "reason_code": reason, "observed_at": T}


def _evaluate(policy, emitter, age_ms, event=None, *, kind="portal_headers"):
    from datetime import datetime, timedelta, timezone
    base = datetime(2026, 9, 18, 12, tzinfo=timezone.utc)
    evaluation = (base + timedelta(milliseconds=age_ms)).isoformat(
        timespec="milliseconds").replace("+00:00", "Z")
    return evaluate_source_health(policy, _ref(emitter), kind,
                                  event if event is not None else _event(emitter, kind=kind),
                                  evaluation)


def test_candidate_uses_exact_immutable_emitters_task01_refs_and_frozen_rules():
    sensor, old_portal, new_portal = _emitters()
    assert sensor.content_sha256 == "45fb264bca5acd33e2202ea3048038cf59218c3c802610ed95d36c5d35022e56"
    assert old_portal.content_sha256 == "568c6738c30c6d3c3ba8ddecea937b6289e37479c8d453810cc4b0884b2f8ee8"
    assert new_portal.content_sha256 == "c5813a1955c847f1b81a90b8a92ff911b2bb0b3067e82f80ab6ba46b9c9b9ffa"
    policy = build_current_source_health_policy(health_anchor_margin_seconds=0)
    payload = policy.semantic_payload
    assert payload["task01_timestamp_skew_contract_ref"] == (
        "Task01TimestampSkewContract:v1:max_future_source_event_skew_seconds=120"
    ) == TASK01_TIMESTAMP_SKEW_REF
    assert payload["task01_delayed_event_contract_ref"] == (
        "Task01DelayedEventContract:v1:max_delayed_event_age_seconds=86400"
    ) == TASK01_DELAYED_EVENT_REF
    assert payload["health_anchor_margin_seconds"] == 0  # Explicit test input; F-B3 not admitted.
    assert len(payload["accepted_source_health_emitter_contracts"]) == 3
    assert len(payload["emitter_source_family_rules"]) == 6
    assert {ref["artifact_id"] for ref in payload["accepted_source_health_emitter_contracts"]} == {
        emitter.artifact_id for emitter in _emitters()
    }
    for emitter, mode, interval, timeout in (
            (sensor, "PERIODIC", 300_000, 600_000),
            (old_portal, "EVENT_DRIVEN", None, 0),
            (new_portal, "PERIODIC", 60_000, 180_000)):
        rules = [row for row in payload["emitter_source_family_rules"]
                 if row["source_health_emitter_contract"] == _ref(emitter)]
        assert {row["source_kind"] for row in rules} == set(emitter.semantic_payload["source_kinds"])
        for rule in rules:
            assert rule["expected_heartbeat"] == {"mode": mode, "nominal_interval_ms": interval}
            assert rule["freshness"] == {"freshness_timeout_ms": timeout,
                                         "when_timeout_exceeded": "unknown"}
            assert rule["backfill"] == {
                "must_obey_task01_delayed_event_contract": True,
                "arrived_backfill_present_evidence_usable": True,
                "recovery_never_upgrades_interval_to_complete": True,
            }
            assert all(mapping["coverage_class"] != "delivery_loss_confirmed"
                       for mapping in rule["status_reason_failure_domain_mappings"])
    assert b"covered_delayed" not in policy.semantic_payload_json


def test_policy_set_order_is_deterministic_and_invalid_shapes_fail_closed():
    policy = build_current_source_health_policy(health_anchor_margin_seconds=0)
    payload = deepcopy(policy.semantic_payload)
    payload["accepted_source_health_emitter_contracts"].reverse()
    payload["emitter_source_family_rules"].reverse()
    for rule in payload["emitter_source_family_rules"]:
        rule["status_reason_failure_domain_mappings"].reverse()
        rule["coverage_class_mapping"].reverse()
    assert make_source_health_policy(payload, _emitters()).artifact_id == policy.artifact_id
    for mutate in (
            lambda p: p.update(extra=True),
            lambda p: p.update(health_anchor_margin_seconds=-1),
            lambda p: p.update(health_anchor_margin_seconds=True),
            lambda p: p.update(task01_timestamp_skew_contract_ref="wrong"),
            lambda p: p.update(task01_delayed_event_contract_ref="wrong"),
            lambda p: p["accepted_source_health_emitter_contracts"].append(
                deepcopy(p["accepted_source_health_emitter_contracts"][0])),
            lambda p: p["emitter_source_family_rules"].append(
                deepcopy(p["emitter_source_family_rules"][0])),
            lambda p: p["emitter_source_family_rules"][0]["freshness"].update(
                freshness_timeout_ms=123),
            lambda p: p["emitter_source_family_rules"][0]["expected_heartbeat"].update(
                mode="NONE"),
            lambda p: p["emitter_source_family_rules"][0]["backfill"].update(
                recovery_never_upgrades_interval_to_complete=False),
            lambda p: p["emitter_source_family_rules"][0]["status_reason_failure_domain_mappings"][0].update(
                coverage_class="delivery_loss_confirmed"),
            lambda p: p["emitter_source_family_rules"][0]["coverage_class_mapping"].append(
                deepcopy(p["emitter_source_family_rules"][0]["coverage_class_mapping"][0])),
    ):
        changed = deepcopy(policy.semantic_payload)
        mutate(changed)
        with pytest.raises(DeviceFingerprintValidationError):
            make_source_health_policy(changed, _emitters())
    with pytest.raises(DeviceFingerprintValidationError):
        build_current_source_health_policy(health_anchor_margin_seconds=None)


@pytest.mark.parametrize("index,kind,boundary", [
    (0, "dhcp", 600_000),
    (1, "portal_headers", 0),
    (2, "portal_headers", 180_000),
])
def test_exact_freshness_boundaries_and_negative_age(index, kind, boundary):
    policy = build_current_source_health_policy(health_anchor_margin_seconds=0)
    emitter = _emitters()[index]
    assert _evaluate(policy, emitter, 0, kind=kind)["coverage_class"] == "covered_available"
    if boundary:
        assert _evaluate(policy, emitter, boundary - 1, kind=kind)["freshness"] == "fresh"
    assert _evaluate(policy, emitter, boundary, kind=kind)["coverage_class"] == "covered_available"
    stale = _evaluate(policy, emitter, boundary + 1, kind=kind)
    assert (stale["coverage_class"], stale["freshness"]) == ("unknown", "stale")
    with pytest.raises(DeviceFingerprintValidationError, match="Negative"):
        _evaluate(policy, emitter, -1, kind=kind)


def test_failure_mappings_unknown_inputs_and_transport_silence():
    policy = build_current_source_health_policy(health_anchor_margin_seconds=0)
    sensor, old_portal, new_portal = _emitters()
    for reason in ("capture_interface_unavailable", "raw_parser_unavailable",
                   "suricata_unavailable", "eve_datagram_truncated"):
        result = _evaluate(policy, sensor, 1, kind="dhcp", event=_event(
            sensor, kind="dhcp", status="unavailable", reason=reason))
        assert result["coverage_class"] == "acquisition_unavailable"
    for emitter, kind in ((sensor, "dhcp"), (old_portal, "portal_headers"),
                          (new_portal, "portal_headers")):
        result = _evaluate(policy, emitter, 0, kind=kind, event=_event(
            emitter, kind=kind, status="unavailable", reason="ingest_delivery_unavailable"))
        assert result["coverage_class"] == "delivery_unavailable_loss_possible"
    assert _evaluate(policy, sensor, 0, kind="dhcp", event=_event(
        sensor, kind="dhcp", status="unsupported"))["coverage_class"] == "unsupported"
    for status, reason in (("unavailable", "unrecognized"), ("other", None),
                           ("available", "ingest_delivery_unavailable")):
        assert _evaluate(policy, new_portal, 0, event=_event(
            new_portal, status=status, reason=reason))["coverage_class"] == "unknown"
    assert evaluate_source_health(policy, _ref(new_portal), "portal_headers", None, T)[
        "coverage_class"] == "unknown"
    assert _evaluate(policy, new_portal, 180_001)["coverage_class"] == "unknown"
    assert _evaluate(policy, new_portal, 0, event=_event(old_portal))[
        "coverage_class"] == "unknown"
    unknown_ref = {"artifact_id": "SourceHealthEmitterContract:v1:sha256:" + "0" * 64,
                   "content_sha256": "0" * 64}
    assert evaluate_source_health(policy, unknown_ref, "portal_headers", _event(new_portal), T)[
        "coverage_class"] == "unknown"


def test_recovery_does_not_upgrade_missing_interval_and_historical_isolation():
    policy = build_current_source_health_policy(health_anchor_margin_seconds=0)
    _sensor, old_portal, new_portal = _emitters()
    assert _evaluate(policy, old_portal, 0)["coverage_class"] == "covered_available"
    assert _evaluate(policy, old_portal, 1)["coverage_class"] == "unknown"
    assert _evaluate(policy, new_portal, 0, event=_event(old_portal))[
        "coverage_class"] == "unknown"
    current = _evaluate(policy, new_portal, 0)
    assert current["coverage_class"] == "covered_available"
    assert current["interval_complete"] is False
    assert all(rule["backfill"]["arrived_backfill_present_evidence_usable"] is True
               and rule["backfill"]["recovery_never_upgrades_interval_to_complete"] is True
               for rule in policy.semantic_payload["emitter_source_family_rules"])
