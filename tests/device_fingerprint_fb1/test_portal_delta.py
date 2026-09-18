"""Bounded Portal heartbeat emitter and synthetic cutover proofs."""

from copy import deepcopy

import pytest

from app.device_fingerprint.artifact_content import ArtifactRef
from app.device_fingerprint.binding_contracts import (
    make_binding_clock_policy, make_evidence_source_binding_timeline,
    resolve_authoritative_binding,
)
from app.device_fingerprint.models import DeviceFingerprintValidationError
from app.device_fingerprint.source_health_emitter_contracts import (
    build_network_sensor_source_health_emitter_contract,
    build_periodic_portal_source_health_emitter_contract,
    build_portal_source_health_emitter_contract, build_source_health_emitter_contracts,
)
from research.device_fingerprint_fb1.portal_delta import (
    build_portal_cutover_timeline, prove_portal_emitter_delta,
)
from tests.device_fingerprint import SITE

START = "2026-09-15T11:00:00.000Z"
CUTOVER = "2026-09-15T12:00:00.000Z"  # Synthetic fixture, never production T.
BEFORE = "2026-09-15T11:59:59.999Z"
AFTER = "2026-09-15T12:00:00.001Z"
SENSOR_ID = "SourceHealthEmitterContract:v1:sha256:45fb264bca5acd33e2202ea3048038cf59218c3c802610ed95d36c5d35022e56"
HISTORICAL_PORTAL_ID = "SourceHealthEmitterContract:v1:sha256:568c6738c30c6d3c3ba8ddecea937b6289e37479c8d453810cc4b0884b2f8ee8"
H1 = "337db041dcb194cb44f019686e0c4d29d221def7"


def _epoch(identity, origin, kind, producer, capture, emitter):
    return {
        "binding_epoch_id": identity, "site_id": SITE, "origin_group": origin,
        "source_kind": kind, "capture_source_id": capture, "producer_id": producer,
        "source_health_emitter_contract": ArtifactRef(
            emitter.artifact_id, emitter.content_sha256,
        ).as_dict(),
        "effective_from_utc": START, "effective_to_utc": None,
    }


def _historical_pair():
    sensor = build_network_sensor_source_health_emitter_contract()
    portal = build_portal_source_health_emitter_contract()
    timeline = make_evidence_source_binding_timeline({
        "binding_timeline_contract_version": 1,
        "binding_epochs": [
            _epoch("sensor-dhcp", "dhcp", "dhcp", "sensor-zefer-01", "zefer-span-01", sensor),
            _epoch("portal-old", "portal", "portal_headers", "portal-zefer-01", "zefer-portal-http-01", portal),
        ],
    }, (sensor, portal))
    clock = make_binding_clock_policy({
        "binding_clock_policy_version": 1,
        "producer_clock_domains": [
            {"clock_domain_id": "sensor-clock", "producer_id": "sensor-zefer-01"},
            {"clock_domain_id": "portal-clock", "producer_id": "portal-zefer-01"},
        ],
        "task01_clock_domain_id": "task01-clock",
        "measured_max_relative_clock_offset_ms": 0,
        "measurement_method_id": "synthetic-paired-read-v1",
        "measurement_evidence_ref": "synthetic-clock-proof-v1",
        "cutover_guard_seconds": 0,
    })
    return timeline, clock


def test_periodic_portal_contract_is_exact_h1_delta_and_old_ids_remain():
    sensor = build_network_sensor_source_health_emitter_contract()
    historical = build_portal_source_health_emitter_contract()
    periodic = prove_portal_emitter_delta()
    assert sensor.artifact_id == SENSOR_ID
    assert historical.artifact_id == HISTORICAL_PORTAL_ID
    assert sensor.content_sha256 == SENSOR_ID.rsplit(":", 1)[1]
    assert historical.content_sha256 == HISTORICAL_PORTAL_ID.rsplit(":", 1)[1]
    assert {item.artifact_id for item in build_source_health_emitter_contracts()} == {
        SENSOR_ID, HISTORICAL_PORTAL_ID,
    }
    assert periodic == build_periodic_portal_source_health_emitter_contract()
    payload = periodic.semantic_payload
    assert payload["producer_service_implementation_identity"] == (
        "CaptivPortal/device_fingerprint_portal/source-health@" + H1
    )
    assert payload["heartbeat_behavior_cadence_semantics"] == {
        "mode": "PERIODIC", "nominal_interval_ms": 60000,
        "same_state_heartbeat_required": True,
    }
    assert payload["source_kinds"] == ["portal_headers"]
    assert payload["persisted_status_emission_semantics"]["allowed_statuses"] == [
        "available", "unavailable",
    ]
    assert [(row["reason_code"], row["failure_domain_semantics"])
            for row in payload["reason_code_definitions"]] == [
                ("ingest_delivery_unavailable", "DELIVERY"),
            ]
    assert payload["delivery_spool_loss_behavior_relevant_to_coverage"][
        "lossless_interval_completion_claim_permitted"] is False
    assert payload["task01_delayed_event_interaction"][
        "recovery_never_proves_missing_interval_complete"] is True


def test_portal_cutover_is_half_open_isolated_and_does_not_rewrite_network():
    historical, clock = _historical_pair()
    original_payload = deepcopy(historical.semantic_payload)
    original_clock = deepcopy(clock.semantic_payload)
    candidate = build_portal_cutover_timeline(historical, clock, CUTOVER)
    assert candidate == build_portal_cutover_timeline(historical, clock, CUTOVER)
    assert historical.semantic_payload == original_payload
    assert clock.semantic_payload == original_clock
    assert clock.semantic_payload["measured_max_relative_clock_offset_ms"] == 0
    assert clock.semantic_payload["cutover_guard_seconds"] == 0
    old = next(epoch for epoch in original_payload["binding_epochs"]
               if epoch["origin_group"] == "portal")
    epochs = candidate.semantic_payload["binding_epochs"]
    finished = next(epoch for epoch in epochs if epoch["binding_epoch_id"] == "portal-old")
    replacement = next(epoch for epoch in epochs if epoch["binding_epoch_id"] == "portal-old-periodic")
    assert finished == {**old, "effective_to_utc": CUTOVER}
    assert replacement == {
        **old, "binding_epoch_id": "portal-old-periodic",
        "effective_from_utc": CUTOVER, "effective_to_utc": None,
        "source_health_emitter_contract": ArtifactRef(
            prove_portal_emitter_delta().artifact_id,
            prove_portal_emitter_delta().content_sha256,
        ).as_dict(),
    }
    assert [epoch for epoch in epochs if epoch["origin_group"] != "portal"] == [
        epoch for epoch in original_payload["binding_epochs"] if epoch["origin_group"] != "portal"
    ]
    for at, expected_epoch, expected_emitter in (
            (BEFORE, "portal-old", HISTORICAL_PORTAL_ID),
            (CUTOVER, "portal-old-periodic", prove_portal_emitter_delta().artifact_id),
            (AFTER, "portal-old-periodic", prove_portal_emitter_delta().artifact_id)):
        result = resolve_authoritative_binding(candidate, clock, SITE, "portal", "portal_headers", at)
        assert result["status"] == "AUTHORIZED"
        assert result["binding_epoch"]["binding_epoch_id"] == expected_epoch
        assert result["binding_epoch"]["source_health_emitter_contract"]["artifact_id"] == expected_emitter
    assert finished["binding_epoch_id"] != replacement["binding_epoch_id"]
    assert set(replacement) == set(old)  # No inherited health-state field exists in the epoch.


def test_portal_cutover_rejects_rewrite_or_invalid_timestamp():
    historical, clock = _historical_pair()
    with pytest.raises(DeviceFingerprintValidationError):
        build_portal_cutover_timeline(historical, clock, START)
    with pytest.raises(DeviceFingerprintValidationError):
        build_portal_cutover_timeline(historical, clock, "2026-09-15T12:00:00Z")
    changed_clock = deepcopy(clock.semantic_payload)
    changed_clock["measured_max_relative_clock_offset_ms"] = 1
    with pytest.raises(DeviceFingerprintValidationError):
        build_portal_cutover_timeline(historical, make_binding_clock_policy(changed_clock), CUTOVER)
    changed_clock["measured_max_relative_clock_offset_ms"] = 0
    changed_clock["cutover_guard_seconds"] = 1
    with pytest.raises(DeviceFingerprintValidationError):
        build_portal_cutover_timeline(historical, make_binding_clock_policy(changed_clock), CUTOVER)
    changed = deepcopy(historical.semantic_payload)
    portal = next(epoch for epoch in changed["binding_epochs"] if epoch["origin_group"] == "portal")
    portal["effective_to_utc"] = CUTOVER
    sensor = build_network_sensor_source_health_emitter_contract()
    old = build_portal_source_health_emitter_contract()
    closed = make_evidence_source_binding_timeline(changed, (sensor, old))
    with pytest.raises(DeviceFingerprintValidationError):
        build_portal_cutover_timeline(closed, clock, AFTER)
