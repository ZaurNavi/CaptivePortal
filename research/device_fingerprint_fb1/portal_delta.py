"""Bounded F-B0/F-B1 Portal heartbeat delta, without a production cutover."""

from __future__ import annotations

from copy import deepcopy

from app.device_fingerprint.artifact_content import ArtifactContent, ArtifactRef
from app.device_fingerprint.binding_contracts import (
    make_evidence_source_binding_timeline, resolve_authoritative_binding,
    validate_binding_clock_pair,
)
from app.device_fingerprint.models import DeviceFingerprintValidationError
from app.device_fingerprint.source_health_emitter_contracts import (
    build_network_sensor_source_health_emitter_contract,
    build_periodic_portal_source_health_emitter_contract,
    build_portal_source_health_emitter_contract,
)
from app.device_fingerprint.validation import parse_utc

_H1_SHA = "337db041dcb194cb44f019686e0c4d29d221def7"
_SENSOR_ID = "SourceHealthEmitterContract:v1:sha256:45fb264bca5acd33e2202ea3048038cf59218c3c802610ed95d36c5d35022e56"
_HISTORICAL_PORTAL_ID = "SourceHealthEmitterContract:v1:sha256:568c6738c30c6d3c3ba8ddecea937b6289e37479c8d453810cc4b0884b2f8ee8"


def _fail(message: str) -> None:
    raise DeviceFingerprintValidationError(message)


def prove_portal_emitter_delta() -> ArtifactContent:
    """Verify only the admitted heartbeat/implementation-identity delta."""
    sensor = build_network_sensor_source_health_emitter_contract()
    historical = build_portal_source_health_emitter_contract()
    replacement = build_periodic_portal_source_health_emitter_contract()
    if sensor.artifact_id != _SENSOR_ID or historical.artifact_id != _HISTORICAL_PORTAL_ID:
        _fail("Historical emitter identity changed")
    old = deepcopy(historical.semantic_payload)
    new = deepcopy(replacement.semantic_payload)
    if new.pop("producer_service_implementation_identity") != (
            "CaptivPortal/device_fingerprint_portal/source-health@" + _H1_SHA):
        _fail("Replacement Portal emitter does not identify H1")
    old.pop("producer_service_implementation_identity")
    if new.pop("heartbeat_behavior_cadence_semantics") != {
            "mode": "PERIODIC", "nominal_interval_ms": 60_000,
            "same_state_heartbeat_required": True,
    }:
        _fail("Replacement Portal heartbeat contract changed")
    if old.pop("heartbeat_behavior_cadence_semantics") != {
            "mode": "EVENT_DRIVEN", "nominal_interval_ms": None,
            "same_state_heartbeat_required": False,
    } or new != old:
        _fail("Portal non-heartbeat semantics changed")
    return replacement


def build_portal_cutover_timeline(
        historical_timeline: ArtifactContent, clock_policy: ArtifactContent,
        cutover_utc: str) -> ArtifactContent:
    """Build a portal-only immutable candidate; caller supplies controlled T later."""
    parse_utc(cutover_utc)
    validate_binding_clock_pair(historical_timeline, clock_policy)
    if (clock_policy.semantic_payload["measured_max_relative_clock_offset_ms"] != 0
            or clock_policy.semantic_payload["cutover_guard_seconds"] != 0):
        _fail("Portal delta requires the unchanged zero-offset, zero-guard clock proof")
    sensor = build_network_sensor_source_health_emitter_contract()
    historical_portal = build_portal_source_health_emitter_contract()
    replacement = prove_portal_emitter_delta()
    epochs = deepcopy(historical_timeline.semantic_payload["binding_epochs"])
    portal_open = [epoch for epoch in epochs
                   if epoch["origin_group"] == "portal"
                   and epoch["source_kind"] == "portal_headers"
                   and epoch["effective_to_utc"] is None]
    if len(portal_open) != 1:
        _fail("Expected exactly one open historical Portal epoch")
    old = portal_open[0]
    if old["source_health_emitter_contract"]["artifact_id"] != historical_portal.artifact_id:
        _fail("Open Portal epoch does not reference historical emitter")
    if parse_utc(cutover_utc) <= parse_utc(old["effective_from_utc"]):
        _fail("Portal cutover must follow historical epoch start")
    old["effective_to_utc"] = cutover_utc
    new = deepcopy(old)
    new["binding_epoch_id"] = old["binding_epoch_id"] + "-periodic"
    new["effective_from_utc"] = cutover_utc
    new["effective_to_utc"] = None
    new["source_health_emitter_contract"] = ArtifactRef(
        replacement.artifact_id, replacement.content_sha256,
    ).as_dict()
    epochs.append(new)
    candidate = make_evidence_source_binding_timeline(
        {"binding_timeline_contract_version": historical_timeline.semantic_payload[
            "binding_timeline_contract_version"], "binding_epochs": epochs},
        (sensor, historical_portal, replacement),
    )
    validate_binding_clock_pair(candidate, clock_policy)
    original_network = [epoch for epoch in historical_timeline.semantic_payload["binding_epochs"]
                        if epoch["origin_group"] != "portal"]
    candidate_network = [epoch for epoch in candidate.semantic_payload["binding_epochs"]
                         if epoch["origin_group"] != "portal"]
    if candidate_network != original_network:
        _fail("Network binding epochs changed")
    for observed_at, expected_id in (
            (old["effective_from_utc"], old["binding_epoch_id"]),
            (cutover_utc, new["binding_epoch_id"])):
        resolved = resolve_authoritative_binding(
            candidate, clock_policy, old["site_id"], "portal", "portal_headers", observed_at,
        )
        if resolved["status"] != "AUTHORIZED" or resolved["binding_epoch"]["binding_epoch_id"] != expected_id:
            _fail("Portal cutover authority failed")
    return candidate
