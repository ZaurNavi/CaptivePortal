"""Immutable F-B2 source-health policy and pure conservative evaluation."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable

from .artifact_content import ArtifactContent, ArtifactRef, canonical_set, make_artifact_content
from .models import DeviceFingerprintValidationError
from .source_health_emitter_contracts import (
    build_network_sensor_source_health_emitter_contract,
    build_periodic_portal_source_health_emitter_contract,
    build_portal_source_health_emitter_contract,
)
from .validation import parse_utc

TASK01_TIMESTAMP_SKEW_REF = "Task01TimestampSkewContract:v1:max_future_source_event_skew_seconds=120"
TASK01_DELAYED_EVENT_REF = "Task01DelayedEventContract:v1:max_delayed_event_age_seconds=86400"

_COVERAGE = frozenset({
    "covered_available", "acquisition_unavailable", "delivery_unavailable_loss_possible",
    "delivery_loss_confirmed", "unsupported", "unknown",
})
_STATUSES = frozenset({"available", "unavailable", "unsupported"})
_DOMAINS = frozenset({"ACQUISITION", "DELIVERY", "CAPABILITY", "RECOVERY", "OTHER"})
_DOMAIN_COVERAGE = {
    "ACQUISITION": "acquisition_unavailable",
    "DELIVERY": "delivery_unavailable_loss_possible",
    "CAPABILITY": "unsupported",
}
_TOP = frozenset({
    "source_health_policy_version", "accepted_source_health_emitter_contracts",
    "emitter_source_family_rules", "task01_timestamp_skew_contract_ref",
    "task01_delayed_event_contract_ref", "health_anchor_margin_seconds",
})
_RULE = frozenset({
    "source_health_emitter_contract", "source_kind", "expected_heartbeat", "freshness",
    "status_reason_failure_domain_mappings", "coverage_class_mapping", "backfill",
})
_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


def _fail(message: str) -> None:
    raise DeviceFingerprintValidationError(message)


def _shape(value: Any, fields: frozenset[str] | set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != fields:
        _fail(f"Invalid {label} shape")
    return value


def _integer(value: Any, label: str, *, minimum: int = 0) -> int:
    if type(value) is not int or not minimum <= value <= 2**63 - 1:
        _fail(f"Invalid {label}")
    return value


def _ref(value: Any, emitters: dict[str, ArtifactContent]) -> dict[str, str]:
    reference = ArtifactRef.from_dict(value)
    emitter = emitters.get(reference.artifact_id)
    if emitter is None:
        _fail("Unknown SourceHealthEmitterContract")
    reference.resolve(emitter, "SourceHealthEmitterContract")
    return reference.as_dict()


def _millis(value: str) -> int:
    delta = parse_utc(value) - _EPOCH
    return (delta.days * 86400 + delta.seconds) * 1000 + delta.microseconds // 1000


def _current_emitters() -> tuple[ArtifactContent, ArtifactContent, ArtifactContent]:
    return (
        build_network_sensor_source_health_emitter_contract(),
        build_portal_source_health_emitter_contract(),
        build_periodic_portal_source_health_emitter_contract(),
    )


def _freshness_for(emitter: ArtifactContent) -> int:
    current = _current_emitters()
    values = {current[0].artifact_id: 600_000, current[1].artifact_id: 0,
              current[2].artifact_id: 180_000}
    if emitter.artifact_id not in values:
        _fail("No frozen freshness rule for emitter")
    return values[emitter.artifact_id]


def _expected_mappings(emitter: ArtifactContent) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    payload = emitter.semantic_payload
    statuses = payload["persisted_status_emission_semantics"]["allowed_statuses"]
    mappings: list[dict[str, Any]] = []
    domains: dict[str, str] = {}
    if "available" in statuses:
        mappings.append({"status": "available", "reason_code": None,
                         "failure_domain": "OTHER", "coverage_class": "covered_available"})
    if "unsupported" in statuses:
        mappings.append({"status": "unsupported", "reason_code": None,
                         "failure_domain": "CAPABILITY", "coverage_class": "unsupported"})
        domains["CAPABILITY"] = "unsupported"
    for reason in payload["reason_code_definitions"]:
        domain = reason["failure_domain_semantics"]
        coverage = _DOMAIN_COVERAGE.get(domain)
        if coverage is None:
            _fail("No admitted coverage mapping for reason domain")
        domains[domain] = coverage
        for status in reason["status_compatibility"]:
            mappings.append({"status": status, "reason_code": reason["reason_code"],
                             "failure_domain": domain, "coverage_class": coverage})
    coverage_mappings = [{"failure_domain": domain, "coverage_class": coverage}
                         for domain, coverage in domains.items()]
    return mappings, coverage_mappings


def make_source_health_policy(
        payload: dict[str, Any], emitter_contracts: Iterable[ArtifactContent],
) -> ArtifactContent:
    """Validate exact V1 shape, frozen current mappings, and declared SET ordering."""
    value = _shape(payload, _TOP, "SourceHealthPolicy")
    if _integer(value["source_health_policy_version"], "policy version", minimum=1) != 1:
        _fail("Unsupported policy version")
    _integer(value["health_anchor_margin_seconds"], "health anchor margin")
    if (value["task01_timestamp_skew_contract_ref"] != TASK01_TIMESTAMP_SKEW_REF
            or value["task01_delayed_event_contract_ref"] != TASK01_DELAYED_EVENT_REF):
        _fail("Task-01 contract reference mismatch")
    emitters: dict[str, ArtifactContent] = {}
    for emitter in emitter_contracts:
        if not isinstance(emitter, ArtifactContent) or emitter.artifact_type != "SourceHealthEmitterContract":
            _fail("Invalid emitter collection")
        if emitter.artifact_id in emitters:
            _fail("Duplicate emitter contract")
        emitters[emitter.artifact_id] = emitter
    expected = {emitter.artifact_id for emitter in _current_emitters()}
    if set(emitters) != expected:
        _fail("Current policy requires exactly three admitted emitter contracts")
    raw_refs = value["accepted_source_health_emitter_contracts"]
    if not isinstance(raw_refs, list):
        _fail("Invalid accepted emitter refs")
    refs = canonical_set([_ref(item, emitters) for item in raw_refs],
                         lambda item: item["artifact_id"])
    if {item["artifact_id"] for item in refs} != expected:
        _fail("Accepted emitter refs are incomplete")
    raw_rules = value["emitter_source_family_rules"]
    if not isinstance(raw_rules, list):
        _fail("Invalid emitter family rules")
    rules = []
    for raw in raw_rules:
        rule = _shape(raw, _RULE, "emitter family rule")
        reference = _ref(rule["source_health_emitter_contract"], emitters)
        emitter = emitters[reference["artifact_id"]]
        kind = rule["source_kind"]
        if not isinstance(kind, str) or kind not in emitter.semantic_payload["source_kinds"]:
            _fail("Emitter source kind mismatch")
        heartbeat = _shape(rule["expected_heartbeat"], {"mode", "nominal_interval_ms"},
                           "expected heartbeat")
        declared = emitter.semantic_payload["heartbeat_behavior_cadence_semantics"]
        if heartbeat != {"mode": declared["mode"], "nominal_interval_ms": declared["nominal_interval_ms"]}:
            _fail("Expected heartbeat does not match emitter")
        if heartbeat["mode"] not in {"PERIODIC", "EVENT_DRIVEN", "NONE"}:
            _fail("Invalid heartbeat mode")
        if heartbeat["mode"] == "PERIODIC":
            _integer(heartbeat["nominal_interval_ms"], "nominal interval", minimum=1)
        elif heartbeat["nominal_interval_ms"] is not None:
            _fail("Non-periodic heartbeat cannot declare an interval")
        freshness = _shape(rule["freshness"], {"freshness_timeout_ms", "when_timeout_exceeded"},
                           "freshness")
        _integer(freshness["freshness_timeout_ms"], "freshness timeout")
        if (freshness["when_timeout_exceeded"] != "unknown"
                or freshness["freshness_timeout_ms"] != _freshness_for(emitter)):
            _fail("Freshness rule differs from frozen value")
        backfill = _shape(rule["backfill"], {
            "must_obey_task01_delayed_event_contract", "arrived_backfill_present_evidence_usable",
            "recovery_never_upgrades_interval_to_complete",
        }, "backfill")
        if any(backfill[key] is not True for key in backfill):
            _fail("Invalid backfill rule")
        expected_mappings, expected_coverage = _expected_mappings(emitter)
        raw_mappings = rule["status_reason_failure_domain_mappings"]
        if not isinstance(raw_mappings, list):
            _fail("Invalid status/reason mappings")
        mappings = []
        for entry in raw_mappings:
            mapping = _shape(entry, {"status", "reason_code", "failure_domain", "coverage_class"},
                             "status/reason mapping")
            if (mapping["status"] not in _STATUSES
                    or mapping["failure_domain"] not in _DOMAINS
                    or mapping["coverage_class"] not in _COVERAGE
                    or (mapping["reason_code"] is not None
                        and (not isinstance(mapping["reason_code"], str) or not mapping["reason_code"].strip()))):
                _fail("Invalid status/reason mapping")
            mappings.append(mapping)
        mappings = canonical_set(mappings, lambda item: (item["status"], item["reason_code"] or ""))
        if mappings != canonical_set(expected_mappings,
                                     lambda item: (item["status"], item["reason_code"] or "")):
            _fail("Status/reason mappings differ from admitted emitter semantics")
        raw_coverage = rule["coverage_class_mapping"]
        if not isinstance(raw_coverage, list):
            _fail("Invalid coverage mappings")
        coverage = []
        for entry in raw_coverage:
            mapping = _shape(entry, {"failure_domain", "coverage_class"}, "coverage mapping")
            if mapping["failure_domain"] not in _DOMAINS or mapping["coverage_class"] not in _COVERAGE:
                _fail("Invalid coverage mapping")
            coverage.append(mapping)
        coverage = canonical_set(coverage, lambda item: item["failure_domain"])
        if coverage != canonical_set(expected_coverage, lambda item: item["failure_domain"]):
            _fail("Coverage mappings differ from admitted emitter semantics")
        rules.append({**rule, "source_health_emitter_contract": reference,
                      "status_reason_failure_domain_mappings": mappings,
                      "coverage_class_mapping": coverage})
    rules = canonical_set(rules, lambda item: (
        item["source_health_emitter_contract"]["artifact_id"], item["source_kind"]))
    expected_pairs = {(emitter.artifact_id, kind) for emitter in emitters.values()
                      for kind in emitter.semantic_payload["source_kinds"]}
    if {(rule["source_health_emitter_contract"]["artifact_id"], rule["source_kind"])
            for rule in rules} != expected_pairs:
        _fail("Emitter family rules are incomplete")
    return make_artifact_content("SourceHealthPolicy", {
        **value, "accepted_source_health_emitter_contracts": refs,
        "emitter_source_family_rules": rules,
    })


def build_current_source_health_policy(*, health_anchor_margin_seconds: int) -> ArtifactContent:
    """Build a candidate only; the explicit margin is not F-B3 admission."""
    emitters = _current_emitters()
    rules = []
    for emitter in emitters:
        payload = emitter.semantic_payload
        heartbeat = payload["heartbeat_behavior_cadence_semantics"]
        mappings, coverage = _expected_mappings(emitter)
        for kind in payload["source_kinds"]:
            rules.append({
                "source_health_emitter_contract": ArtifactRef(
                    emitter.artifact_id, emitter.content_sha256).as_dict(),
                "source_kind": kind,
                "expected_heartbeat": {"mode": heartbeat["mode"],
                                       "nominal_interval_ms": heartbeat["nominal_interval_ms"]},
                "freshness": {"freshness_timeout_ms": _freshness_for(emitter),
                              "when_timeout_exceeded": "unknown"},
                "status_reason_failure_domain_mappings": mappings,
                "coverage_class_mapping": coverage,
                "backfill": {
                    "must_obey_task01_delayed_event_contract": True,
                    "arrived_backfill_present_evidence_usable": True,
                    "recovery_never_upgrades_interval_to_complete": True,
                },
            })
    return make_source_health_policy({
        "source_health_policy_version": 1,
        "accepted_source_health_emitter_contracts": [ArtifactRef(
            emitter.artifact_id, emitter.content_sha256).as_dict() for emitter in emitters],
        "emitter_source_family_rules": rules,
        "task01_timestamp_skew_contract_ref": TASK01_TIMESTAMP_SKEW_REF,
        "task01_delayed_event_contract_ref": TASK01_DELAYED_EVENT_REF,
        "health_anchor_margin_seconds": health_anchor_margin_seconds,
    }, emitters)


def evaluate_source_health(
        policy: ArtifactContent, bound_emitter_ref: dict[str, str], source_kind: str,
        latest_event: dict[str, Any] | None, evaluation_time_utc: str,
) -> dict[str, Any]:
    """Interpret one explicitly compatible event; never infer interval completeness."""
    evaluation_ms = _millis(evaluation_time_utc)

    def unknown(disposition: str, *, age_ms: int | None = None) -> dict[str, Any]:
        return {"coverage_class": "unknown", "freshness": disposition, "age_ms": age_ms,
                "interval_complete": False}

    if not isinstance(policy, ArtifactContent) or policy.artifact_type != "SourceHealthPolicy":
        return unknown("policy_mismatch")
    try:
        reference = ArtifactRef.from_dict(bound_emitter_ref)
    except DeviceFingerprintValidationError:
        return unknown("emitter_mismatch")
    rules = [rule for rule in policy.semantic_payload["emitter_source_family_rules"]
             if rule["source_health_emitter_contract"] == reference.as_dict()
             and rule["source_kind"] == source_kind]
    if len(rules) != 1:
        return unknown("emitter_mismatch")
    if latest_event is None:
        return unknown("no_event")
    if (not isinstance(latest_event, dict)
            or set(latest_event) != {"source_health_emitter_contract", "source_kind",
                                       "status", "reason_code", "observed_at"}
            or latest_event["source_health_emitter_contract"] != reference.as_dict()
            or latest_event["source_kind"] != source_kind):
        return unknown("event_mismatch")
    observed_ms = _millis(latest_event["observed_at"])
    age_ms = evaluation_ms - observed_ms
    if age_ms < 0:
        _fail("Negative source-health age")
    rule = rules[0]
    if age_ms > rule["freshness"]["freshness_timeout_ms"]:
        return unknown("stale", age_ms=age_ms)
    match = [mapping for mapping in rule["status_reason_failure_domain_mappings"]
             if mapping["status"] == latest_event["status"]
             and mapping["reason_code"] == latest_event["reason_code"]]
    if len(match) != 1:
        return unknown("unrecognized_status_reason", age_ms=age_ms)
    return {"coverage_class": match[0]["coverage_class"], "freshness": "fresh",
            "age_ms": age_ms, "interval_complete": False}
