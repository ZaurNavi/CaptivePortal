"""Deterministic F-B2 synthetic proof vectors."""

from app.device_fingerprint.source_health_policy import build_current_source_health_policy
from research.device_fingerprint_fb2.proof import run_f_b2_proof


def test_offline_proof_covers_frozen_boundaries_and_failure_isolation():
    policy = build_current_source_health_policy(health_anchor_margin_seconds=0)
    proof = run_f_b2_proof(policy)
    assert proof["result"] == "PASS"
    assert proof["policy_artifact_id"] == policy.artifact_id
    assert proof["outcomes"] == {
        "healthy_periodic_sensor": "covered_available",
        "sensor_freshness_boundary": "covered_available",
        "sensor_transport_silence": "unknown",
        "portal_freshness_boundary": "covered_available",
        "portal_transport_silence": "unknown",
        "acquisition_failure": "acquisition_unavailable",
        "delivery_failure": "delivery_unavailable_loss_possible",
        "unknown_reason": "unknown",
        "historical_event_at_timestamp": "covered_available",
        "historical_event_after_timestamp": "unknown",
        "periodic_event_after_timestamp": "covered_available",
        "epoch_emitter_mismatch": "unknown",
        "recovery_no_interval_completion": "covered_available",
        "arrived_backfill_evidence_usable": "present_evidence_usable",
        "no_covered_delayed": "confirmed",
        "negative_age_invalid": "confirmed",
    }
