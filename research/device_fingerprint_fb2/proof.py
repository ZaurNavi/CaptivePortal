"""Bounded synthetic proofs for the frozen SourceHealthPolicy candidate."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.device_fingerprint.artifact_content import ArtifactRef
from app.device_fingerprint.models import DeviceFingerprintValidationError
from app.device_fingerprint.source_health_emitter_contracts import (
    build_network_sensor_source_health_emitter_contract,
    build_periodic_portal_source_health_emitter_contract,
    build_portal_source_health_emitter_contract,
)
from app.device_fingerprint.source_health_policy import evaluate_source_health

_START = datetime(2026, 9, 18, 12, tzinfo=timezone.utc)


def _timestamp(offset_ms: int) -> str:
    return (_START + timedelta(milliseconds=offset_ms)).isoformat(
        timespec="milliseconds").replace("+00:00", "Z")


def _ref(emitter) -> dict[str, str]:
    return ArtifactRef(emitter.artifact_id, emitter.content_sha256).as_dict()


def _event(emitter, source_kind: str, status: str = "available", reason_code: str | None = None):
    return {"source_health_emitter_contract": _ref(emitter),
            "source_kind": source_kind, "status": status,
            "reason_code": reason_code, "observed_at": _timestamp(0)}


def run_f_b2_proof(policy) -> dict[str, object]:
    """Run fixed vectors; return deterministic outcomes, never inspect live state."""
    sensor = build_network_sensor_source_health_emitter_contract()
    historical = build_portal_source_health_emitter_contract()
    periodic = build_periodic_portal_source_health_emitter_contract()
    outcomes: dict[str, str] = {}

    def check(name: str, emitter, source_kind: str, age_ms: int,
              expected: str, event=None) -> None:
        actual = evaluate_source_health(
            policy, _ref(emitter), source_kind,
            _event(emitter, source_kind) if event is None else event,
            _timestamp(age_ms),
        )
        if actual["coverage_class"] != expected or actual["interval_complete"] is not False:
            raise AssertionError(f"{name}: {actual!r}")
        outcomes[name] = actual["coverage_class"]

    check("healthy_periodic_sensor", sensor, "dhcp", 0, "covered_available")
    check("sensor_freshness_boundary", sensor, "dhcp", 600_000, "covered_available")
    check("sensor_transport_silence", sensor, "dhcp", 600_001, "unknown")
    check("portal_freshness_boundary", periodic, "portal_headers", 180_000,
          "covered_available")
    check("portal_transport_silence", periodic, "portal_headers", 180_001, "unknown")
    check("acquisition_failure", sensor, "dhcp", 0, "acquisition_unavailable",
          _event(sensor, "dhcp", "unavailable", "capture_interface_unavailable"))
    check("delivery_failure", periodic, "portal_headers", 0,
          "delivery_unavailable_loss_possible",
          _event(periodic, "portal_headers", "unavailable", "ingest_delivery_unavailable"))
    check("unknown_reason", periodic, "portal_headers", 0, "unknown",
          _event(periodic, "portal_headers", "unavailable", "unrecognized"))
    check("historical_event_at_timestamp", historical, "portal_headers", 0,
          "covered_available")
    check("historical_event_after_timestamp", historical, "portal_headers", 1, "unknown")
    check("periodic_event_after_timestamp", periodic, "portal_headers", 1,
          "covered_available")
    check("epoch_emitter_mismatch", periodic, "portal_headers", 0, "unknown",
          _event(historical, "portal_headers"))
    recovery = evaluate_source_health(policy, _ref(periodic), "portal_headers",
                                      _event(periodic, "portal_headers"), _timestamp(0))
    if recovery != {"coverage_class": "covered_available", "freshness": "fresh",
                    "age_ms": 0, "interval_complete": False}:
        raise AssertionError("Recovery cannot prove prior interval complete")
    outcomes["recovery_no_interval_completion"] = recovery["coverage_class"]
    rules = policy.semantic_payload["emitter_source_family_rules"]
    if not all(rule["backfill"]["must_obey_task01_delayed_event_contract"]
               and rule["backfill"]["arrived_backfill_present_evidence_usable"]
               and rule["backfill"]["recovery_never_upgrades_interval_to_complete"]
               for rule in rules):
        raise AssertionError("Arrived evidence/backfill contract changed")
    outcomes["arrived_backfill_evidence_usable"] = "present_evidence_usable"
    if "covered_delayed" in policy.semantic_payload_json.decode("utf-8"):
        raise AssertionError("Forbidden coverage class")
    outcomes["no_covered_delayed"] = "confirmed"
    try:
        evaluate_source_health(policy, _ref(historical), "portal_headers",
                               _event(historical, "portal_headers"), _timestamp(-1))
    except DeviceFingerprintValidationError:
        outcomes["negative_age_invalid"] = "confirmed"
    else:
        raise AssertionError("Negative event age was accepted")
    return {"result": "PASS", "policy_artifact_id": policy.artifact_id,
            "outcomes": outcomes}
