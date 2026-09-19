"""Exact accepted F-B1 semantic inputs for F-A4 accounting tests."""

import pytest

from research.device_fingerprint_fa4.semantic_accounting import (
    build_semantic_accounting_dependencies,
)

SITE_ID = "6a64f17630da7c70d232187a"
EFFECTIVE_FROM = "2026-09-18T10:43:29.014Z"
NETWORK_EMITTER = {
    "artifact_id": (
        "SourceHealthEmitterContract:v1:sha256:"
        "45fb264bca5acd33e2202ea3048038cf59218c3c802610ed95d36c5d35022e56"
    ),
    "content_sha256": "45fb264bca5acd33e2202ea3048038cf59218c3c802610ed95d36c5d35022e56",
}
PORTAL_EMITTER = {
    "artifact_id": (
        "SourceHealthEmitterContract:v1:sha256:"
        "568c6738c30c6d3c3ba8ddecea937b6289e37479c8d453810cc4b0884b2f8ee8"
    ),
    "content_sha256": "568c6738c30c6d3c3ba8ddecea937b6289e37479c8d453810cc4b0884b2f8ee8",
}


def binding_epoch(origin: str, source_kind: str, producer: str, capture: str,
                  emitter: dict[str, str], *, suffix: str = "v1",
                  effective_from: str = EFFECTIVE_FROM,
                  effective_to: str | None = None) -> dict:
    return {
        "binding_epoch_id": f"zefer-{origin}-{suffix}-20260918T104329014Z",
        "site_id": SITE_ID,
        "origin_group": origin,
        "source_kind": source_kind,
        "capture_source_id": capture,
        "producer_id": producer,
        "source_health_emitter_contract": emitter,
        "effective_from_utc": effective_from,
        "effective_to_utc": effective_to,
    }


def accepted_timeline_payload() -> dict:
    return {
        "binding_timeline_contract_version": 1,
        "binding_epochs": [
            binding_epoch("dhcp", "dhcp", "sensor-zefer-01", "zefer-span-01",
                          NETWORK_EMITTER),
            binding_epoch("portal", "portal_headers", "portal-zefer-01",
                          "zefer-portal-http-01", PORTAL_EMITTER),
            binding_epoch("quic", "quic_client", "sensor-zefer-01", "zefer-span-01",
                          NETWORK_EMITTER),
            binding_epoch("tcp", "tcp_syn", "sensor-zefer-01", "zefer-span-01",
                          NETWORK_EMITTER),
            binding_epoch("tls", "tls_client", "sensor-zefer-01", "zefer-span-01",
                          NETWORK_EMITTER),
        ],
    }


def accepted_clock_payload() -> dict:
    domain = (
        "linux-realtime:local.domain.az:boot:39b7ba86-0a72-4e44-9091-f72d50385e97:"
        "time:[4026531834]"
    )
    return {
        "binding_clock_policy_version": 1,
        "producer_clock_domains": [
            {"clock_domain_id": domain, "producer_id": "portal-zefer-01"},
            {"clock_domain_id": domain, "producer_id": "sensor-zefer-01"},
        ],
        "task01_clock_domain_id": domain,
        "measured_max_relative_clock_offset_ms": 0,
        "measurement_method_id": "shared-linux-time-namespace-identity-v1",
        "measurement_evidence_ref": (
            "sha256:b2a188c881d94e70dedbe5abd2100c9f0f90d48cc2850377a088db065fb8f482"
        ),
        "cutover_guard_seconds": 0,
    }


@pytest.fixture
def accepted_dependencies():
    return build_semantic_accounting_dependencies(
        accepted_timeline_payload(), accepted_clock_payload(),
    )
