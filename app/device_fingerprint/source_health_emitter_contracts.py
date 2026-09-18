"""Immutable F-B0 contracts for the admitted source-health emitters."""

from __future__ import annotations

from typing import Any

from .artifact_content import ArtifactContent, canonical_set, make_artifact_content
from .models import DeviceFingerprintValidationError

_IDENTITY_SUFFIX = "8e6173bf7ea566bdfb3823fc58bc728ca14e3893"
_STATUSES = frozenset({"available", "unavailable", "unsupported"})
_DOMAINS = frozenset({"ACQUISITION", "DELIVERY", "CAPABILITY", "RECOVERY", "OTHER"})
_TOP_LEVEL = frozenset({
    "emitter_contract_version", "producer_service_implementation_identity",
    "source_kinds", "heartbeat_behavior_cadence_semantics",
    "persisted_status_emission_semantics", "reason_code_definitions",
    "delivery_spool_loss_behavior_relevant_to_coverage",
    "task01_delayed_event_interaction", "source_health_event_compatibility_version",
})


def _fail() -> None:
    raise DeviceFingerprintValidationError("Invalid source-health emitter contract")


def _shape(value: Any, fields: set[str] | frozenset[str]) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != fields:
        _fail()
    return value


def _text(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        _fail()
    return value


def _positive(value: Any, maximum: int) -> int:
    if type(value) is not int or not 0 < value <= maximum:
        _fail()
    return value


def _boolean(value: Any) -> bool:
    if type(value) is not bool:
        _fail()
    return value


def _string_set(value: Any, allowed: frozenset[str] | None = None) -> list[str]:
    if not isinstance(value, list) or not value:
        _fail()
    for member in value:
        _text(member)
        if allowed is not None and member not in allowed:
            _fail()
    return canonical_set(value, lambda member: member)


def make_source_health_emitter_contract(payload: dict[str, Any]) -> ArtifactContent:
    """Validate the exact R14 V1 shape and canonicalize its declared SETs."""
    value = _shape(payload, _TOP_LEVEL)
    _positive(value["emitter_contract_version"], 2**31 - 1)
    _positive(value["source_health_event_compatibility_version"], 2**31 - 1)
    _text(value["producer_service_implementation_identity"])
    source_kinds = _string_set(value["source_kinds"])

    heartbeat = _shape(value["heartbeat_behavior_cadence_semantics"], {
        "mode", "nominal_interval_ms", "same_state_heartbeat_required",
    })
    if _text(heartbeat["mode"]) not in {"PERIODIC", "EVENT_DRIVEN", "NONE"}:
        _fail()
    nominal = heartbeat["nominal_interval_ms"]
    if heartbeat["mode"] == "PERIODIC":
        _positive(nominal, 2**63 - 1)
    elif nominal is not None:
        _fail()
    _boolean(heartbeat["same_state_heartbeat_required"])

    emission = _shape(value["persisted_status_emission_semantics"], {
        "allowed_statuses", "status_transition_delivery_required_when_transport_available",
    })
    allowed_statuses = _string_set(emission["allowed_statuses"], _STATUSES)
    _boolean(emission["status_transition_delivery_required_when_transport_available"])

    reasons = value["reason_code_definitions"]
    if not isinstance(reasons, list):
        _fail()
    for reason in reasons:
        _shape(reason, {"reason_code", "exact_meaning", "status_compatibility",
                        "failure_domain_semantics"})
        _text(reason["reason_code"])
        _text(reason["exact_meaning"])
        if _text(reason["failure_domain_semantics"]) not in _DOMAINS:
            _fail()
        _string_set(reason["status_compatibility"], _STATUSES)
    ordered_reasons = canonical_set(reasons, lambda reason: reason["reason_code"])
    ordered_reasons = [
        {**reason, "status_compatibility": _string_set(reason["status_compatibility"], _STATUSES)}
        for reason in ordered_reasons
    ]

    delivery = _shape(value["delivery_spool_loss_behavior_relevant_to_coverage"], {
        "producer_spool_mode", "lossless_interval_completion_claim_permitted",
        "evidence_eviction_possible", "capacity_block_possible",
    })
    if _text(delivery["producer_spool_mode"]) not in {"NONE", "BOUNDED_LOSSY", "BOUNDED_NONLOSSY"}:
        _fail()
    if delivery["lossless_interval_completion_claim_permitted"] is not False:
        _fail()
    _boolean(delivery["evidence_eviction_possible"])
    _boolean(delivery["capacity_block_possible"])

    delayed = _shape(value["task01_delayed_event_interaction"], {
        "must_obey_task01_delayed_event_contract",
        "historical_health_backfill_permitted_when_within_task01_limit",
        "recovery_never_proves_missing_interval_complete",
    })
    if (delayed["must_obey_task01_delayed_event_contract"] is not True
            or delayed["recovery_never_proves_missing_interval_complete"] is not True):
        _fail()
    _boolean(delayed["historical_health_backfill_permitted_when_within_task01_limit"])

    return make_artifact_content("SourceHealthEmitterContract", {
        **value,
        "source_kinds": source_kinds,
        "persisted_status_emission_semantics": {
            **emission, "allowed_statuses": allowed_statuses,
        },
        "reason_code_definitions": ordered_reasons,
    })


def _reason(code: str, meaning: str, domain: str) -> dict[str, Any]:
    return {
        "reason_code": code, "exact_meaning": meaning,
        "status_compatibility": ["unavailable"],
        "failure_domain_semantics": domain,
    }


def _payload(identity: str, kinds: list[str], mode: str, interval: int | None,
             heartbeat: bool, statuses: list[str], reasons: list[dict[str, Any]],
             *, capacity_block: bool) -> dict[str, Any]:
    return {
        "emitter_contract_version": 1,
        "producer_service_implementation_identity": identity,
        "source_kinds": kinds,
        "heartbeat_behavior_cadence_semantics": {
            "mode": mode, "nominal_interval_ms": interval,
            "same_state_heartbeat_required": heartbeat,
        },
        "persisted_status_emission_semantics": {
            "allowed_statuses": statuses,
            "status_transition_delivery_required_when_transport_available": True,
        },
        "reason_code_definitions": reasons,
        "delivery_spool_loss_behavior_relevant_to_coverage": {
            "producer_spool_mode": "BOUNDED_LOSSY",
            "lossless_interval_completion_claim_permitted": False,
            "evidence_eviction_possible": True,
            "capacity_block_possible": capacity_block,
        },
        "task01_delayed_event_interaction": {
            "must_obey_task01_delayed_event_contract": True,
            "historical_health_backfill_permitted_when_within_task01_limit": True,
            "recovery_never_proves_missing_interval_complete": True,
        },
        "source_health_event_compatibility_version": 1,
    }


def build_network_sensor_source_health_emitter_contract() -> ArtifactContent:
    return make_source_health_emitter_contract(_payload(
        "CaptivPortal/device_fingerprint_sensor/source-health@" + _IDENTITY_SUFFIX,
        ["dhcp", "tcp_syn", "tls_client", "quic_client"],
        "PERIODIC", 300_000, True,
        ["available", "unavailable", "unsupported"],
        [
            _reason("capture_interface_unavailable", "Configured capture interface failed preflight", "ACQUISITION"),
            _reason("raw_parser_unavailable", "Raw packet acquisition or parsing stopped", "ACQUISITION"),
            _reason("suricata_unavailable", "Suricata evidence acquisition is unavailable", "ACQUISITION"),
            _reason("eve_datagram_truncated", "Suricata EVE datagram was truncated", "ACQUISITION"),
            _reason("ingest_delivery_unavailable", "Task-01 evidence delivery is unavailable", "DELIVERY"),
        ], capacity_block=True,
    ))


def build_portal_source_health_emitter_contract() -> ArtifactContent:
    return make_source_health_emitter_contract(_payload(
        "CaptivPortal/device_fingerprint_portal/source-health@" + _IDENTITY_SUFFIX,
        ["portal_headers"], "EVENT_DRIVEN", None, False,
        ["available", "unavailable"],
        [_reason("ingest_delivery_unavailable", "Task-01 evidence delivery was temporarily unavailable", "DELIVERY")],
        capacity_block=False,
    ))


def build_source_health_emitter_contracts() -> tuple[ArtifactContent, ArtifactContent]:
    """Return the two explicit contracts in deterministic artifact-ID order."""
    contracts = (
        build_network_sensor_source_health_emitter_contract(),
        build_portal_source_health_emitter_contract(),
    )
    return tuple(sorted(contracts, key=lambda contract: (contract.artifact_id,
                                                         contract.semantic_payload_json)))
