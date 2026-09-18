"""F-B1-A closed contracts, exact authority, and half-open cutover proofs."""

from copy import deepcopy

import pytest

from app.device_fingerprint.artifact_content import ArtifactRef, canonical_artifact_json, make_artifact_content
from app.device_fingerprint.binding_contracts import (
    make_binding_clock_policy, make_evidence_source_binding_timeline,
    resolve_authoritative_binding, validate_binding_clock_pair,
)
from app.device_fingerprint.models import DeviceFingerprintValidationError
from app.device_fingerprint.source_health_emitter_contracts import (
    build_network_sensor_source_health_emitter_contract,
    make_source_health_emitter_contract,
)
from tests.device_fingerprint import SITE

T = "2026-09-15T12:00:00.000Z"
BEFORE = "2026-09-15T11:00:00.000Z"
AFTER = "2026-09-15T13:00:00.000Z"


def _epoch(identity, start, end, emitter, *, producer="sensor-zefer-01",
           capture="zefer-span-01", site=SITE, kind="dhcp", origin="dhcp"):
    return {
        "binding_epoch_id": identity, "site_id": site, "origin_group": origin,
        "source_kind": kind, "capture_source_id": capture, "producer_id": producer,
        "source_health_emitter_contract": ArtifactRef(emitter.artifact_id, emitter.content_sha256).as_dict(),
        "effective_from_utc": start, "effective_to_utc": end,
    }


def _payload(*epochs):
    return {"binding_timeline_contract_version": 1, "binding_epochs": list(epochs)}


def _clock(guard=3, *, domains=None):
    return make_binding_clock_policy({
        "binding_clock_policy_version": 1,
        "producer_clock_domains": domains or [
            {"clock_domain_id": "sensor-clock", "producer_id": "sensor-zefer-01"},
        ],
        "task01_clock_domain_id": "task01-clock",
        "measured_max_relative_clock_offset_ms": 125,
        "measurement_method_id": "paired-read-v1",
        "measurement_evidence_ref": "lab-clock-proof-v1",
        "cutover_guard_seconds": guard,
    })


def _pair(guard=3):
    emitter = build_network_sensor_source_health_emitter_contract()
    payload = _payload(_epoch("A", BEFORE, T, emitter), _epoch("B", T, None, emitter))
    return make_evidence_source_binding_timeline(payload, [emitter]), _clock(guard), emitter


def test_timeline_and_clock_closed_schema_identity_and_set_ordering():
    timeline, policy, emitter = _pair()
    payload = deepcopy(timeline.semantic_payload)
    reversed_payload = deepcopy(payload)
    reversed_payload["binding_epochs"].reverse()
    again = make_evidence_source_binding_timeline(reversed_payload, [emitter])
    assert timeline.semantic_payload_json == again.semantic_payload_json
    assert timeline.content_sha256 == again.content_sha256
    assert timeline.artifact_id == again.artifact_id
    changed = deepcopy(payload)
    changed["binding_epochs"][0]["capture_source_id"] = "another-capture"
    alternate = make_evidence_source_binding_timeline(changed, [emitter])
    assert alternate.content_sha256 != timeline.content_sha256
    assert alternate.artifact_id != timeline.artifact_id

    clock_payload = deepcopy(policy.semantic_payload)
    clock_payload["producer_clock_domains"].append({
        "clock_domain_id": "second-clock", "producer_id": "sensor-zefer-01",
    })
    first = make_binding_clock_policy(clock_payload)
    clock_payload["producer_clock_domains"].reverse()
    second = make_binding_clock_policy(clock_payload)
    assert first.semantic_payload_json == second.semantic_payload_json
    assert first.content_sha256 == second.content_sha256
    assert first.artifact_id == second.artifact_id
    clock_payload["cutover_guard_seconds"] = 4
    third = make_binding_clock_policy(clock_payload)
    assert third.content_sha256 != first.content_sha256
    assert third.artifact_id != first.artifact_id


def test_equal_primary_different_canonical_bytes_uses_universal_tie_break():
    emitter = build_network_sensor_source_health_emitter_contract()
    first = _epoch("same-id", BEFORE, T, emitter)
    second = _epoch("same-id", BEFORE, T, emitter, site="a" * 24)
    result = make_evidence_source_binding_timeline(_payload(first, second), [emitter])
    assert result.semantic_payload["binding_epochs"] == sorted(
        (first, second), key=canonical_artifact_json,
    )
    with pytest.raises(DeviceFingerprintValidationError):
        make_evidence_source_binding_timeline(_payload(first, deepcopy(first)), [emitter])
    domains = [
        {"clock_domain_id": "same", "producer_id": "sensor-zefer-01"},
        {"clock_domain_id": "same", "producer_id": "portal-zefer-01"},
    ]
    assert len(_clock(domains=domains).semantic_payload["producer_clock_domains"]) == 2
    with pytest.raises(DeviceFingerprintValidationError):
        _clock(domains=[domains[0], deepcopy(domains[0])])


@pytest.mark.parametrize("observed,status,identity", [
    ("2026-09-15T11:59:56.999Z", "AUTHORIZED", "A"),
    ("2026-09-15T11:59:57.000Z", "CUTOVER_AMBIGUOUS", None),
    (T, "CUTOVER_AMBIGUOUS", None),
    ("2026-09-15T12:00:02.999Z", "CUTOVER_AMBIGUOUS", None),
    ("2026-09-15T12:00:03.000Z", "AUTHORIZED", "B"),
])
def test_positive_guard_exact_half_open_boundaries(observed, status, identity):
    timeline, policy, _ = _pair()
    result = resolve_authoritative_binding(timeline, policy, SITE, "dhcp", "dhcp", observed)
    assert result["status"] == status
    assert (result["binding_epoch"] or {}).get("binding_epoch_id") == identity
    assert result["reason"] == ("binding_cutover_ambiguous" if identity is None else None)


def test_zero_guard_boundary_and_no_binding():
    timeline, policy, _ = _pair(0)
    assert resolve_authoritative_binding(timeline, policy, SITE, "dhcp", "dhcp",
                                         "2026-09-15T11:59:59.999Z")["binding_epoch"]["binding_epoch_id"] == "A"
    assert resolve_authoritative_binding(timeline, policy, SITE, "dhcp", "dhcp", T)["binding_epoch"]["binding_epoch_id"] == "B"
    assert resolve_authoritative_binding(timeline, policy, SITE, "portal", "portal_headers", T)["status"] == "NO_BINDING"
    assert resolve_authoritative_binding(timeline, policy, SITE, "dhcp", "dhcp",
                                         "2026-09-15T10:00:00.000Z")["status"] == "NO_BINDING"


def test_emitter_semantic_change_requires_new_epoch_and_preserves_historical_ref():
    first = build_network_sensor_source_health_emitter_contract()
    changed_payload = deepcopy(first.semantic_payload)
    changed_payload["reason_code_definitions"][0]["exact_meaning"] += " revised"
    second = make_source_health_emitter_contract(changed_payload)
    timeline = make_evidence_source_binding_timeline(_payload(
        _epoch("X", BEFORE, T, first), _epoch("Y", T, None, second),
    ), [first, second])
    policy = _clock(0)
    old = resolve_authoritative_binding(timeline, policy, SITE, "dhcp", "dhcp",
                                        "2026-09-15T11:59:59.999Z")["binding_epoch"]
    new = resolve_authoritative_binding(timeline, policy, SITE, "dhcp", "dhcp", T)["binding_epoch"]
    assert old["producer_id"] == new["producer_id"]
    assert old["capture_source_id"] == new["capture_source_id"]
    assert old["source_health_emitter_contract"]["artifact_id"] == first.artifact_id
    assert new["source_health_emitter_contract"]["artifact_id"] == second.artifact_id
    assert first.artifact_id != second.artifact_id


@pytest.mark.parametrize("mutation", [
    lambda rows: rows[1].update(effective_from_utc="2026-09-15T11:59:59.999Z"),
    lambda rows: rows[0].update(effective_to_utc=None),
    lambda rows: rows[1].update(effective_to_utc="2026-09-15T14:00:00.000Z", effective_from_utc="2026-09-15T11:59:59.999Z"),
    lambda rows: rows[0].update(effective_to_utc=BEFORE),
    lambda rows: rows[1].update(effective_to_utc="2026-09-15T11:59:59.999Z"),
    lambda rows: rows[0].pop("producer_id"),
    lambda rows: rows[0].update(producer_id=""),
    lambda rows: rows[0].pop("capture_source_id"),
    lambda rows: rows[0].update(capture_source_id=""),
    lambda rows: rows[0].pop("source_health_emitter_contract"),
    lambda rows: rows[0].update(origin_group="mac_registry"),
    lambda rows: rows[0].update(origin_group="other"),
    lambda rows: rows[0].update(extra=True),
    lambda rows: rows[0].update(effective_from_utc="2026-09-15T11:00:00Z"),
])
def test_invalid_binding_epochs_fail_closed(mutation):
    emitter = build_network_sensor_source_health_emitter_contract()
    rows = [_epoch("A", BEFORE, T, emitter), _epoch("B", T, None, emitter)]
    mutation(rows)
    with pytest.raises(DeviceFingerprintValidationError):
        make_evidence_source_binding_timeline(_payload(*rows), [emitter])


def test_two_open_ended_epochs_and_reference_failures():
    emitter = build_network_sensor_source_health_emitter_contract()
    open_epochs = _payload(_epoch("A", BEFORE, None, emitter),
                           _epoch("B", T, None, emitter))
    with pytest.raises(DeviceFingerprintValidationError):
        make_evidence_source_binding_timeline(open_epochs, [emitter])
    for changed in (
        {"artifact_id": emitter.artifact_id, "content_sha256": "0" * 64},
        {"artifact_id": make_artifact_content("WrongType", {}).artifact_id,
         "content_sha256": make_artifact_content("WrongType", {}).content_sha256},
        {"artifact_id": "SourceHealthEmitterContract:v1:sha256:" + "1" * 64,
         "content_sha256": "1" * 64},
    ):
        epoch = _epoch("A", BEFORE, T, emitter)
        epoch["source_health_emitter_contract"] = changed
        with pytest.raises(DeviceFingerprintValidationError):
            make_evidence_source_binding_timeline(_payload(epoch), [emitter])


def test_top_level_and_clock_domain_shape_are_closed_and_cross_validated():
    emitter = build_network_sensor_source_health_emitter_contract()
    with pytest.raises(DeviceFingerprintValidationError):
        make_evidence_source_binding_timeline({**_payload(_epoch("A", BEFORE, T, emitter)),
                                               "extra": True}, [emitter])
    timeline, policy, _ = _pair()
    validate_binding_clock_pair(timeline, policy)
    base = deepcopy(policy.semantic_payload)
    mutations = (
        lambda p: p.update(extra=True),
        lambda p: p.update(binding_clock_policy_version=0),
        lambda p: p.update(task01_clock_domain_id=""),
        lambda p: p.update(measured_max_relative_clock_offset_ms=-1),
        lambda p: p.update(cutover_guard_seconds=-1),
        lambda p: p["producer_clock_domains"][0].update(extra=True),
    )
    for mutate in mutations:
        changed = deepcopy(base)
        mutate(changed)
        with pytest.raises(DeviceFingerprintValidationError):
            make_binding_clock_policy(changed)
    wrong_domain = _clock(domains=[{"clock_domain_id": "portal-clock", "producer_id": "portal-zefer-01"}])
    with pytest.raises(DeviceFingerprintValidationError):
        validate_binding_clock_pair(timeline, wrong_domain)
