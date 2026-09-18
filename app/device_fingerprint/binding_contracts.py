"""Immutable F-B1 binding contracts and pure event-time authority resolution."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable

from .artifact_content import ArtifactContent, ArtifactRef, canonical_set, make_artifact_content
from .models import DeviceFingerprintValidationError
from .validation import parse_utc, validate_site_id

_ORIGINS = frozenset({"dhcp", "portal", "tcp", "tls", "quic"})
_EPOCH_FIELDS = frozenset({
    "binding_epoch_id", "site_id", "origin_group", "source_kind",
    "capture_source_id", "producer_id", "source_health_emitter_contract",
    "effective_from_utc", "effective_to_utc",
})
_CLOCK_FIELDS = frozenset({
    "binding_clock_policy_version", "producer_clock_domains", "task01_clock_domain_id",
    "measured_max_relative_clock_offset_ms", "measurement_method_id",
    "measurement_evidence_ref", "cutover_guard_seconds",
})
_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


def _fail(message: str) -> None:
    raise DeviceFingerprintValidationError(message)


def _shape(value: Any, fields: frozenset[str] | set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != fields:
        _fail(f"Invalid {label} shape")
    return value


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        _fail(f"Invalid {label}")
    return value


def _integer(value: Any, label: str, *, minimum: int, maximum: int) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        _fail(f"Invalid {label}")
    return value


def _milliseconds(value: str) -> int:
    delta = parse_utc(value) - _EPOCH
    return ((delta.days * 86400 + delta.seconds) * 1000
            + delta.microseconds // 1000)


def _emitter_ref(value: Any, emitters: dict[str, ArtifactContent] | None) -> dict[str, str]:
    reference = ArtifactRef.from_dict(value)
    if not reference.artifact_id.startswith("SourceHealthEmitterContract:v1:sha256:"):
        _fail("Binding emitter reference has wrong artifact type")
    if emitters is not None:
        content = emitters.get(reference.artifact_id)
        if content is None:
            _fail("Unknown binding emitter contract")
        reference.resolve(content, "SourceHealthEmitterContract")
    return reference.as_dict()


def _timeline_payload(payload: Any, emitters: dict[str, ArtifactContent] | None) -> dict[str, Any]:
    value = _shape(payload, {"binding_timeline_contract_version", "binding_epochs"}, "binding timeline")
    _integer(value["binding_timeline_contract_version"], "binding timeline version",
             minimum=1, maximum=2**31 - 1)
    raw_epochs = value["binding_epochs"]
    if not isinstance(raw_epochs, list):
        _fail("Invalid binding epochs")
    epochs = []
    for raw in raw_epochs:
        epoch = _shape(raw, _EPOCH_FIELDS, "binding epoch")
        _text(epoch["binding_epoch_id"], "binding epoch ID")
        validate_site_id(epoch["site_id"])
        if not isinstance(epoch["origin_group"], str) or epoch["origin_group"] not in _ORIGINS:
            _fail("Invalid origin group")
        _text(epoch["source_kind"], "source kind")
        _text(epoch["capture_source_id"], "capture source ID")
        _text(epoch["producer_id"], "producer ID")
        reference = _emitter_ref(epoch["source_health_emitter_contract"], emitters)
        start = _milliseconds(epoch["effective_from_utc"])
        end_value = epoch["effective_to_utc"]
        end = None if end_value is None else _milliseconds(end_value)
        if end is not None and end <= start:
            _fail("Binding interval must be positive")
        epochs.append({**epoch, "source_health_emitter_contract": reference})
    ordered = canonical_set(epochs, lambda epoch: epoch["binding_epoch_id"])
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for epoch in ordered:
        key = (epoch["site_id"], epoch["origin_group"], epoch["source_kind"])
        groups.setdefault(key, []).append(epoch)
    for group in groups.values():
        by_time = sorted(group, key=lambda epoch: (_milliseconds(epoch["effective_from_utc"]),
                                                   epoch["binding_epoch_id"]))
        for previous, current in zip(by_time, by_time[1:]):
            previous_end = previous["effective_to_utc"]
            if previous_end is None or _milliseconds(previous_end) > _milliseconds(current["effective_from_utc"]):
                _fail("Overlapping authoritative binding epochs")
    return {"binding_timeline_contract_version": value["binding_timeline_contract_version"],
            "binding_epochs": ordered}


def make_evidence_source_binding_timeline(
    payload: dict[str, Any], emitter_contracts: Iterable[ArtifactContent],
) -> ArtifactContent:
    """Resolve every emitter reference and materialize a closed R14 timeline."""
    emitters: dict[str, ArtifactContent] = {}
    for content in emitter_contracts:
        if not isinstance(content, ArtifactContent) or content.artifact_type != "SourceHealthEmitterContract":
            _fail("Invalid emitter contract collection")
        if content.artifact_id in emitters:
            _fail("Duplicate emitter contract")
        emitters[content.artifact_id] = content
    return make_artifact_content("EvidenceSourceBindingTimeline", _timeline_payload(payload, emitters))


def _clock_payload(payload: Any) -> dict[str, Any]:
    value = _shape(payload, _CLOCK_FIELDS, "binding clock policy")
    _integer(value["binding_clock_policy_version"], "binding clock policy version",
             minimum=1, maximum=2**31 - 1)
    _text(value["task01_clock_domain_id"], "Task-01 clock domain")
    _text(value["measurement_method_id"], "clock measurement method")
    _text(value["measurement_evidence_ref"], "clock measurement evidence reference")
    _integer(value["measured_max_relative_clock_offset_ms"], "relative clock offset",
             minimum=0, maximum=2**63 - 1)
    _integer(value["cutover_guard_seconds"], "cutover guard", minimum=0, maximum=2**63 - 1)
    domains = value["producer_clock_domains"]
    if not isinstance(domains, list):
        _fail("Invalid producer clock domains")
    for domain in domains:
        _shape(domain, {"clock_domain_id", "producer_id"}, "clock domain")
        _text(domain["clock_domain_id"], "clock domain ID")
        _text(domain["producer_id"], "clock-domain producer ID")
    return {**value, "producer_clock_domains": canonical_set(domains, lambda row: row["clock_domain_id"])}


def make_binding_clock_policy(payload: dict[str, Any]) -> ArtifactContent:
    return make_artifact_content("BindingClockPolicy", _clock_payload(payload))


def validate_binding_clock_pair(timeline: ArtifactContent, clock_policy: ArtifactContent) -> None:
    """Require declared clock domains for every timeline producer (not future-skew inference)."""
    if (not isinstance(timeline, ArtifactContent)
            or timeline.artifact_type != "EvidenceSourceBindingTimeline"
            or not isinstance(clock_policy, ArtifactContent)
            or clock_policy.artifact_type != "BindingClockPolicy"):
        _fail("Invalid binding artifact pair")
    epochs = _timeline_payload(timeline.semantic_payload, None)["binding_epochs"]
    policy = _clock_payload(clock_policy.semantic_payload)
    covered = {row["producer_id"] for row in policy["producer_clock_domains"]}
    if not {row["producer_id"] for row in epochs} <= covered:
        _fail("Binding producer has no declared clock domain")


def resolve_authoritative_binding(
    timeline: ArtifactContent, clock_policy: ArtifactContent,
    site_id: str, origin_group: str, source_kind: str, observed_at: str,
) -> dict[str, Any]:
    """Select one nominal epoch, or fail closed across exact half-open cutover guards."""
    validate_binding_clock_pair(timeline, clock_policy)
    validate_site_id(site_id)
    if not isinstance(origin_group, str) or origin_group not in _ORIGINS:
        _fail("Invalid origin group")
    _text(source_kind, "source kind")
    instant = _milliseconds(observed_at)
    guard_ms = clock_policy.semantic_payload["cutover_guard_seconds"] * 1000
    epochs = [epoch for epoch in timeline.semantic_payload["binding_epochs"]
              if (epoch["site_id"], epoch["origin_group"], epoch["source_kind"])
              == (site_id, origin_group, source_kind)]
    epochs.sort(key=lambda epoch: _milliseconds(epoch["effective_from_utc"]))
    for previous, current in zip(epochs, epochs[1:]):
        if previous["effective_to_utc"] == current["effective_from_utc"]:
            cutover = _milliseconds(current["effective_from_utc"])
            if cutover - guard_ms <= instant < cutover + guard_ms:
                return {"status": "CUTOVER_AMBIGUOUS", "binding_epoch": None,
                        "reason": "binding_cutover_ambiguous"}
    nominal = [epoch for epoch in epochs
               if _milliseconds(epoch["effective_from_utc"]) <= instant
               and (epoch["effective_to_utc"] is None
                    or instant < _milliseconds(epoch["effective_to_utc"]))]
    if len(nominal) > 1:
        _fail("Multiple authoritative binding epochs")
    if not nominal:
        return {"status": "NO_BINDING", "binding_epoch": None, "reason": None}
    return {"status": "AUTHORIZED", "binding_epoch": nominal[0], "reason": None}
