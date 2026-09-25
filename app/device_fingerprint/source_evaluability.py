"""Pure R14 T-02 SourceEvaluability construction from a pinned T-01 snapshot."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Callable

from .artifact_content import ArtifactContent, ArtifactRef, canonical_set, make_artifact_content
from .binding_contracts import (
    make_binding_clock_policy, resolve_authoritative_binding, validate_binding_clock_pair,
)
from .models import DeviceFingerprintValidationError
from .runtime_profile_artifacts import make_foundation_runtime_profile
from .source_health_policy import evaluate_source_health
from .validation import format_utc, parse_utc

__all__ = ["make_source_evaluability", "DeviceFingerprintSourceEvaluabilityBuilder"]

_TOP_FIELDS = frozenset({
    "source_evaluability_contract_version", "evidence_snapshot_content",
    "source_health_policy", "source_entries",
})
_ENTRY_FIELDS = frozenset({
    "origin_group", "source_kind", "binding_epoch_id", "producer_id",
    "capture_source_id", "aggregate_evaluability_state", "coverage_intervals",
    "explanation_codes",
})
_INTERVAL_FIELDS = frozenset({
    "start_utc", "end_utc", "coverage_class", "reason_classification",
    "reason_code_refs",
})
_ORIGINS = frozenset({"dhcp", "portal", "tcp", "tls", "quic"})
_COVERAGE = frozenset({
    "covered_available", "acquisition_unavailable", "delivery_unavailable_loss_possible",
    "delivery_loss_confirmed", "unsupported", "unknown",
})
_REASONS = frozenset({
    "HEALTH_AVAILABLE", "ACQUISITION_UNAVAILABLE", "DELIVERY_UNAVAILABLE_LOSS_POSSIBLE",
    "DELIVERY_LOSS_CONFIRMED", "SOURCE_UNSUPPORTED", "HEALTH_UNKNOWN",
    "HEARTBEAT_STALE", "BINDING_CUTOVER_UNKNOWN", "HEALTH_EVIDENCE_INCONSISTENCY",
    "UNSUPPORTED_BUT_EVIDENCE_PRESENT",
})
_AGGREGATES = frozenset({"evaluable", "partially_evaluable", "not_evaluable", "unknown"})
_COVERAGE_REASON = {
    "covered_available": "HEALTH_AVAILABLE",
    "acquisition_unavailable": "ACQUISITION_UNAVAILABLE",
    "delivery_unavailable_loss_possible": "DELIVERY_UNAVAILABLE_LOSS_POSSIBLE",
    "delivery_loss_confirmed": "DELIVERY_LOSS_CONFIRMED",
    "unsupported": "SOURCE_UNSUPPORTED",
    "unknown": "HEALTH_UNKNOWN",
}
_REASON_COVERAGE = {
    "HEALTH_AVAILABLE": "covered_available",
    "ACQUISITION_UNAVAILABLE": "acquisition_unavailable",
    "DELIVERY_UNAVAILABLE_LOSS_POSSIBLE": "delivery_unavailable_loss_possible",
    "DELIVERY_LOSS_CONFIRMED": "delivery_loss_confirmed",
    "SOURCE_UNSUPPORTED": "unsupported",
    "HEALTH_UNKNOWN": "unknown",
    "HEARTBEAT_STALE": "unknown",
    "BINDING_CUTOVER_UNKNOWN": "unknown",
    "HEALTH_EVIDENCE_INCONSISTENCY": "acquisition_unavailable",
    "UNSUPPORTED_BUT_EVIDENCE_PRESENT": "unsupported",
}


def _fail(message: str) -> None:
    raise DeviceFingerprintValidationError(message)


def _shape(value: Any, fields: frozenset[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != fields:
        _fail(f"Invalid {label} shape")
    return value


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        _fail(f"Invalid {label}")
    return value


def _ref(value: ArtifactContent) -> dict[str, str]:
    return ArtifactRef(value.artifact_id, value.content_sha256).as_dict()


def _exact_ref(value: Any, content: ArtifactContent, kind: str) -> dict[str, str]:
    reference = ArtifactRef.from_dict(value)
    reference.resolve(content, kind)
    return reference.as_dict()


def _segment(snapshot: dict[str, Any], binding: dict[str, Any]) -> tuple[datetime, datetime]:
    start = max(parse_utc(snapshot["window_start_utc"]),
                parse_utc(binding["effective_from_utc"]))
    end = parse_utc(snapshot["window_end_utc"])
    if binding["effective_to_utc"] is not None:
        end = min(end, parse_utc(binding["effective_to_utc"]))
    if start >= end:
        _fail("Binding does not intersect snapshot window")
    return start, end


def _aggregate(intervals: list[dict[str, Any]]) -> str:
    non_quarantine = [row for row in intervals
                      if row["reason_classification"] != "BINDING_CUTOVER_UNKNOWN"]
    if non_quarantine and all(row["coverage_class"] == "covered_available"
                              for row in non_quarantine):
        return "evaluable"
    covered = any(row["coverage_class"] == "covered_available" for row in non_quarantine)
    if covered and any(row["coverage_class"] != "covered_available" for row in non_quarantine):
        return "partially_evaluable"
    if (any(row["reason_classification"] == "BINDING_CUTOVER_UNKNOWN" for row in intervals)
            or any(row["coverage_class"] in {"unknown", "delivery_unavailable_loss_possible"}
                   for row in intervals)):
        return "unknown"
    if non_quarantine and all(row["coverage_class"] in {
            "acquisition_unavailable", "delivery_loss_confirmed", "unsupported"}
            for row in non_quarantine):
        return "not_evaluable"
    _fail("Invalid aggregate coverage composition")


def make_source_evaluability(
    payload: dict[str, Any], *, evidence_snapshot_content: ArtifactContent,
    source_health_policy: ArtifactContent,
) -> ArtifactContent:
    """Validate the exact C.3.29 shape, complete partition and canonical SETs."""
    if (not isinstance(evidence_snapshot_content, ArtifactContent)
            or evidence_snapshot_content.artifact_type != "EvidenceSnapshotContent"
            or not isinstance(source_health_policy, ArtifactContent)
            or source_health_policy.artifact_type != "SourceHealthPolicy"):
        _fail("Invalid SourceEvaluability dependencies")
    value = _shape(payload, _TOP_FIELDS, "SourceEvaluability")
    if type(value["source_evaluability_contract_version"]) is not int or value[
            "source_evaluability_contract_version"] != 1:
        _fail("Unsupported SourceEvaluability version")
    snapshot_ref = _exact_ref(value["evidence_snapshot_content"],
                              evidence_snapshot_content, "EvidenceSnapshotContent")
    health_ref = _exact_ref(value["source_health_policy"],
                            source_health_policy, "SourceHealthPolicy")
    snapshot = evidence_snapshot_content.semantic_payload
    raw_bindings = snapshot.get("binding_epoch_descriptors")
    if not isinstance(raw_bindings, list):
        _fail("Invalid snapshot binding descriptors")
    bindings: dict[str, dict[str, Any]] = {}
    identity_fields = ("origin_group", "source_kind", "binding_epoch_id",
                       "producer_id", "capture_source_id")
    for binding in raw_bindings:
        if not isinstance(binding, dict) or any(field not in binding for field in (
                *identity_fields, "effective_from_utc", "effective_to_utc")):
            _fail("Invalid snapshot binding descriptor")
        identity = _text(binding["binding_epoch_id"], "binding epoch ID")
        if identity in bindings:
            _fail("Duplicate snapshot binding epoch")
        bindings[identity] = binding
    raw_entries = value["source_entries"]
    if not isinstance(raw_entries, list):
        _fail("Source entries must be a SET list")
    entries = []
    seen_epochs: set[str] = set()
    for raw in raw_entries:
        entry = _shape(raw, _ENTRY_FIELDS, "SourceEvaluabilityEntry")
        epoch_id = _text(entry["binding_epoch_id"], "entry binding epoch ID")
        binding = bindings.get(epoch_id)
        if binding is None or epoch_id in seen_epochs:
            _fail("Unknown or duplicate SourceEvaluability binding epoch")
        seen_epochs.add(epoch_id)
        if not isinstance(entry["origin_group"], str) or entry["origin_group"] not in _ORIGINS:
            _fail("Invalid SourceEvaluability origin")
        for field in identity_fields:
            _text(entry[field], f"entry {field}")
            if entry[field] != binding[field]:
                _fail("SourceEvaluability entry/binding identity mismatch")
        if (not isinstance(entry["aggregate_evaluability_state"], str)
                or entry["aggregate_evaluability_state"] not in _AGGREGATES):
            _fail("Invalid aggregate evaluability state")
        segment_start, segment_end = _segment(snapshot, binding)
        raw_intervals = entry["coverage_intervals"]
        if not isinstance(raw_intervals, list) or not raw_intervals:
            _fail("Missing coverage partition")
        intervals = []
        expected_start = segment_start
        for raw_interval in raw_intervals:
            interval = _shape(raw_interval, _INTERVAL_FIELDS, "CoverageInterval")
            start, end = parse_utc(interval["start_utc"]), parse_utc(interval["end_utc"])
            if start != expected_start or start >= end or end > segment_end:
                _fail("Coverage intervals have a gap, overlap or invalid boundary")
            if (not isinstance(interval["coverage_class"], str)
                    or interval["coverage_class"] not in _COVERAGE):
                _fail("Invalid coverage class")
            if (not isinstance(interval["reason_classification"], str)
                    or interval["reason_classification"] not in _REASONS):
                _fail("Invalid reason classification")
            if _REASON_COVERAGE[interval["reason_classification"]] != interval["coverage_class"]:
                _fail("Coverage and reason classification disagree")
            reasons = interval["reason_code_refs"]
            if not isinstance(reasons, list):
                _fail("Invalid reason-code SET")
            canonical_reasons = canonical_set(
                [_text(reason, "reason-code reference") for reason in reasons],
                lambda reason: reason)
            if interval["reason_classification"] in {
                    "BINDING_CUTOVER_UNKNOWN", "HEARTBEAT_STALE"} and canonical_reasons:
                _fail("Quarantine/stale interval cannot carry reason-code references")
            normalized = {**interval, "reason_code_refs": canonical_reasons}
            if intervals and all(intervals[-1][field] == normalized[field] for field in (
                    "coverage_class", "reason_classification")):
                _fail("Adjacent identical coverage/reason intervals are not normalized")
            intervals.append(normalized)
            expected_start = end
        if expected_start != segment_end:
            _fail("Coverage intervals do not reach segment end")
        explanations = entry["explanation_codes"]
        if not isinstance(explanations, list):
            _fail("Invalid explanation-code SET")
        canonical_explanations = canonical_set(
            [_text(code, "explanation code") for code in explanations], lambda code: code)
        expected_explanations = canonical_set(
            list({row["reason_classification"] for row in intervals}), lambda code: code)
        if canonical_explanations != expected_explanations:
            _fail("Explanation codes differ from interval reasons")
        if entry["aggregate_evaluability_state"] != _aggregate(intervals):
            _fail("Aggregate state differs from coverage intervals")
        entries.append({**entry, "coverage_intervals": intervals,
                        "explanation_codes": canonical_explanations})
    if seen_epochs != set(bindings):
        _fail("SourceEvaluability entries do not cover exact snapshot bindings")
    entries = canonical_set(entries, lambda entry: (
        entry["origin_group"], entry["source_kind"],
        bindings[entry["binding_epoch_id"]]["effective_from_utc"],
        entry["producer_id"], entry["capture_source_id"], entry["binding_epoch_id"],
    ))
    return make_artifact_content("SourceEvaluability", {
        "source_evaluability_contract_version": 1,
        "evidence_snapshot_content": snapshot_ref,
        "source_health_policy": health_ref,
        "source_entries": entries,
    })


class DeviceFingerprintSourceEvaluabilityBuilder:
    """Reconstruct coverage using only exact pinned immutable Foundation inputs."""

    def __init__(
        self, *, foundation_runtime_profile: ArtifactContent,
        artifact_resolver: Callable[[ArtifactRef], ArtifactContent],
    ) -> None:
        if not isinstance(foundation_runtime_profile, ArtifactContent) or not callable(artifact_resolver):
            _fail("Invalid pinned Foundation input")
        profile = make_foundation_runtime_profile(foundation_runtime_profile.semantic_payload)
        if profile != foundation_runtime_profile:
            _fail("Noncanonical FoundationRuntimeProfile")

        def resolve(field: str, kind: str) -> ArtifactContent:
            try:
                reference = ArtifactRef.from_dict(profile.semantic_payload[field])
                if not reference.artifact_id.startswith(f"{kind}:v1:sha256:"):
                    _fail("Wrong Foundation dependency type")
                content = artifact_resolver(reference)
                reference.resolve(content, kind)
                return content
            except (LookupError, TypeError, AttributeError) as exc:
                raise DeviceFingerprintValidationError("Unresolved Foundation dependency") from exc

        health = resolve("source_health_policy", "SourceHealthPolicy")
        timeline = resolve("evidence_source_binding_timeline", "EvidenceSourceBindingTimeline")
        clock = resolve("binding_clock_policy", "BindingClockPolicy")
        if make_binding_clock_policy(clock.semantic_payload) != clock:
            _fail("Noncanonical BindingClockPolicy")
        validate_binding_clock_pair(timeline, clock)
        self._profile = profile
        self._health = health
        self._timeline = timeline
        self._clock = clock

    def _quarantine_boundaries(self, binding: dict[str, Any],
                               segment_start: datetime, segment_end: datetime) -> set[datetime]:
        peers = [epoch for epoch in self._timeline.semantic_payload["binding_epochs"]
                 if (epoch["site_id"], epoch["origin_group"], epoch["source_kind"])
                 == (binding["site_id"], binding["origin_group"], binding["source_kind"])]
        peers.sort(key=lambda epoch: parse_utc(epoch["effective_from_utc"]))
        guard = timedelta(seconds=self._clock.semantic_payload["cutover_guard_seconds"])
        boundaries = set()
        for previous, current in zip(peers, peers[1:]):
            if previous["effective_to_utc"] == current["effective_from_utc"]:
                cutover = parse_utc(current["effective_from_utc"])
                for point in (cutover - guard, cutover + guard):
                    if segment_start < point < segment_end:
                        boundaries.add(point)
        return boundaries

    def _entry(self, snapshot: dict[str, Any], binding: dict[str, Any]) -> dict[str, Any]:
        segment_start, segment_end = _segment(snapshot, binding)
        epoch_id = binding["binding_epoch_id"]
        emitter = binding["source_health_emitter_contract"]
        health = []
        for row in snapshot["source_health_descriptors"]:
            if row["binding_epoch_id"] != epoch_id:
                continue
            if any(row[field] != binding[field] for field in (
                    "source_kind", "producer_id", "capture_source_id")):
                _fail("Health descriptor differs from binding epoch")
            health.append(row)
        health.sort(key=lambda row: (
            row["observed_at"], row["ingest_sequence"], row["source_health_id"]))
        rules = [rule for rule in self._health.semantic_payload["emitter_source_family_rules"]
                 if rule["source_health_emitter_contract"] == emitter
                 and rule["source_kind"] == binding["source_kind"]]
        if len(rules) > 1:
            _fail("Ambiguous exact source-health family rule")
        breakpoints = {segment_start, segment_end}
        breakpoints.update(self._quarantine_boundaries(binding, segment_start, segment_end))
        for row in health:
            observed = parse_utc(row["observed_at"])
            if segment_start < observed < segment_end:
                breakpoints.add(observed)
            if len(rules) == 1:
                stale = observed + timedelta(
                    milliseconds=rules[0]["freshness"]["freshness_timeout_ms"] + 1)
                if segment_start < stale < segment_end:
                    breakpoints.add(stale)
        points = sorted(breakpoints)
        evidence_times = [parse_utc(row["observed_at"])
                          for row in snapshot["evidence_descriptors"]
                          if row["binding_epoch_id"] == epoch_id]
        intervals = []
        index = 0
        latest = None
        for start, end in zip(points, points[1:]):
            if start >= end:
                _fail("Zero-length atomic coverage interval")
            while index < len(health) and parse_utc(health[index]["observed_at"]) <= start:
                latest = health[index]
                index += 1
            authority = resolve_authoritative_binding(
                self._timeline, self._clock, binding["site_id"], binding["origin_group"],
                binding["source_kind"], format_utc(start))
            if authority["status"] == "CUTOVER_AMBIGUOUS":
                coverage, reason, reason_refs = "unknown", "BINDING_CUTOVER_UNKNOWN", []
            else:
                selected = authority["binding_epoch"]
                if (authority["status"] != "AUTHORIZED" or selected is None
                        or selected["binding_epoch_id"] != epoch_id):
                    _fail("Snapshot binding conflicts with pinned event-time authority")
                event = None if latest is None else {
                    "source_health_emitter_contract": emitter,
                    "source_kind": binding["source_kind"],
                    "status": latest["status"],
                    "reason_code": latest["reason_code"],
                    "observed_at": latest["observed_at"],
                }
                disposition = evaluate_source_health(
                    self._health, emitter, binding["source_kind"], event, format_utc(start))
                coverage = disposition["coverage_class"]
                if disposition["freshness"] == "stale":
                    reason, reason_refs = "HEARTBEAT_STALE", []
                else:
                    reason = _COVERAGE_REASON[coverage]
                    reason_refs = ([latest["reason_code"]] if latest is not None
                                   and disposition["age_ms"] is not None
                                   and latest["reason_code"] is not None else [])
                present = any(start <= observed < end for observed in evidence_times)
                if present and coverage == "acquisition_unavailable":
                    reason = "HEALTH_EVIDENCE_INCONSISTENCY"
                elif present and coverage == "unsupported":
                    reason = "UNSUPPORTED_BUT_EVIDENCE_PRESENT"
            current = {"start_utc": format_utc(start), "end_utc": format_utc(end),
                       "coverage_class": coverage, "reason_classification": reason,
                       "reason_code_refs": reason_refs}
            if intervals and all(intervals[-1][field] == current[field] for field in (
                    "coverage_class", "reason_classification")):
                intervals[-1]["end_utc"] = current["end_utc"]
                intervals[-1]["reason_code_refs"] = canonical_set(
                    list(set(intervals[-1]["reason_code_refs"] + current["reason_code_refs"])),
                    lambda code: code)
            else:
                intervals.append(current)
        explanations = sorted({row["reason_classification"] for row in intervals})
        return {
            "origin_group": binding["origin_group"],
            "source_kind": binding["source_kind"],
            "binding_epoch_id": epoch_id,
            "producer_id": binding["producer_id"],
            "capture_source_id": binding["capture_source_id"],
            "aggregate_evaluability_state": _aggregate(intervals),
            "coverage_intervals": intervals,
            "explanation_codes": explanations,
        }

    def build(self, evidence_snapshot_content: ArtifactContent) -> ArtifactContent:
        if (not isinstance(evidence_snapshot_content, ArtifactContent)
                or evidence_snapshot_content.artifact_type != "EvidenceSnapshotContent"):
            _fail("Invalid EvidenceSnapshotContent input")
        snapshot = evidence_snapshot_content.semantic_payload
        _exact_ref(snapshot["evidence_source_binding_timeline"],
                   self._timeline, "EvidenceSourceBindingTimeline")
        _exact_ref(snapshot["binding_clock_policy"], self._clock, "BindingClockPolicy")
        profile = self._profile.semantic_payload
        if (snapshot["snapshot_contract_version"] != profile["snapshot_contract_version"]
                or snapshot["classification_foundation_valid_from_utc"] !=
                profile["classification_foundation_valid_from_utc"]):
            _fail("Snapshot/FoundationRuntimeProfile mismatch")
        entries = [self._entry(snapshot, binding)
                   for binding in snapshot["binding_epoch_descriptors"]]
        return make_source_evaluability({
            "source_evaluability_contract_version": 1,
            "evidence_snapshot_content": _ref(evidence_snapshot_content),
            "source_health_policy": _ref(self._health),
            "source_entries": entries,
        }, evidence_snapshot_content=evidence_snapshot_content,
            source_health_policy=self._health)
