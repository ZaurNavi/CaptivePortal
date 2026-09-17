"""Synthetic-only fixtures for Task-03A matrix tooling."""

from __future__ import annotations

import sqlite3
import uuid
from pathlib import Path

from app.device_fingerprint.schema import SCHEMA_SQL
from app.device_fingerprint.validation import canonical_json, canonical_sha256
from research.device_fingerprint_03a.format import (
    MATRIX_FORMAT_VERSION,
    MATRIX_REVISION,
    PRODUCTION_SCHEMA_REGISTRY,
    SITE_ID,
    write_canonical_json,
    write_canonical_jsonl,
    write_checksums,
)


def uid(value: int) -> str:
    return str(uuid.UUID(int=value, version=4))


def device(identity: int = 1, *, device_class: str = "smartphone", manufacturer: str = "Example", model: str = "Model A"):
    return {
        "matrix_format_version": 1,
        "lab_device_id": uid(identity),
        "device_class_gt": device_class,
        "manufacturer_gt": manufacturer,
        "model_gt": model,
        "collection_authorized": True,
        "control_basis_gt": "owner_controlled",
        "ground_truth_verified_at": "2026-09-15T10:00:00.000Z",
        "ground_truth_verification_methods": ["device_about_page", "device_settings"],
    }


def device_state(identity: int = 101, *, device_id: int = 1, family: str = "android", version: str = "14"):
    return {
        "matrix_format_version": 1,
        "ground_truth_state_id": uid(identity),
        "lab_device_id": uid(device_id),
        "os_family_gt": family,
        "os_version_gt": version,
        "os_major_gt": int(version.split(".", 1)[0]),
        "state_verified_at": "2026-09-15T10:00:00.000Z",
        "state_verification_methods": ["device_settings"],
    }


def sample(
    identity: int = 201,
    *,
    device_id: int = 1,
    state_id: int = 101,
    epoch_id: int = 301,
    start: str = "2026-09-15T12:00:00.000Z",
    end: str = "2026-09-15T12:05:00.000Z",
    context: str = "normal_browser",
    supported: bool = False,
):
    return {
        "matrix_format_version": 1,
        "sample_id": uid(identity),
        "collection_run_id": uid(401),
        "lab_device_id": uid(device_id),
        "ground_truth_state_id": uid(state_id),
        "site_id": SITE_ID,
        "window_start_utc": start,
        "window_end_utc": end,
        "network_epoch_id": uid(epoch_id),
        "network_state_gt": "fresh_attach",
        "runtime_context_gt": context,
        "browser_family_gt": "chrome",
        "browser_version_major_gt": 120,
        "mac_mode_gt": "global",
        "portal_entry_mode_gt": "capport_login",
        "context_supported_gt": supported,
        "sample_status": "sealed",
        "sealed_at": "2026-09-15T12:06:00.000Z",
    }


def binding(sample_id: int = 201, *, device_id: int = 1, mac: str = "AA:BB:CC:DD:EE:01"):
    return {
        "sample_id": uid(sample_id),
        "lab_device_id": uid(device_id),
        "observed_mac": mac,
        "observed_ip": "192.168.8.10",
    }


def payload(kind: str):
    if kind == "dhcp":
        return {
            "message_type": "discover",
            "parameter_request_list": [1, 3, 6, 114],
            "option_order": [53, 55, 60],
            "vendor_class": "android-dhcp",
            "client_identifier_kind": "mac",
            "maximum_message_size": 1500,
            "rapid_commit_requested": False,
            "capport_requested": True,
            "ipv6_only_preferred_requested": False,
            "hostname_present": False,
        }
    if kind == "tcp_syn":
        return {
            "ip_version": 4,
            "observed_ttl": 64,
            "tcp_window": 65535,
            "mss": 1460,
            "window_scale": 8,
            "sack_permitted": True,
            "timestamps_present": True,
            "tcp_option_order": [2, 4, 8, 1, 3],
        }
    if kind == "tls_client":
        return {
            "ja4": "t13d0102h2_0123456789ab_abcdef012345",
            "ja4_a": "t13d0102h2",
            "ja4_b": "0123456789ab",
            "ja4_c": "abcdef012345",
            "tls_version_family": "tls1_3",
            "client_alpns": ["h2", "http/1.1"],
            "ech_extension_present": False,
            "grease_extension_present": True,
        }
    if kind == "quic_client":
        return {
            "ja4": "q13d0102h3_0123456789ab_abcdef012345",
            "ja4_a": "q13d0102h3",
            "ja4_b": "0123456789ab",
            "ja4_c": "abcdef012345",
            "quic_version": "0x00000001",
            "ech_extension_present": None,
            "grease_extension_present": True,
        }
    if kind == "portal_headers":
        return {
            "platform_family": "android",
            "mobile_boolean": True,
            "browser_runtime_family": "chromium",
            "webview_or_captive_context": None,
            "model_family": "Model A",
            "os_major": 14,
            "platform_source": "user_agent",
            "mobile_source": "user_agent",
            "runtime_source": "user_agent",
            "context_source": None,
            "model_source": "user_agent",
            "os_major_source": "user_agent",
            "ua_present": True,
            "sec_ch_ua_present": False,
            "sec_ch_ua_platform_present": False,
            "sec_ch_ua_mobile_present": False,
        }
    raise AssertionError(kind)


def sealed_evidence(
    identity: int = 501,
    *,
    sample_id: int = 201,
    device_id: int = 1,
    kind: str = "dhcp",
    observed_at: str = "2026-09-15T12:01:00.000Z",
):
    normalized = payload(kind)
    payload_json = canonical_json(normalized)
    return {
        "evidence_id": uid(identity),
        "source_event_id": uid(identity + 1000),
        "producer_id": "portal-zefer-01" if kind == "portal_headers" else "sensor-zefer-01",
        "source_kind": kind,
        "source_subtype": "capport_login" if kind == "portal_headers" else None,
        "extractor_name": "portal-http-parser" if kind == "portal_headers" else f"{kind}-v1",
        "extractor_version": "1.0.0",
        "feature_schema_version": 1,
        "rule_version": None,
        "site_id": SITE_ID,
        "capture_source_id": "zefer-portal-http-01" if kind == "portal_headers" else "zefer-span-01",
        "observed_at": observed_at,
        "quality_state": "valid",
        "privacy_class": "P1",
        "payload": normalized,
        "payload_sha256": canonical_sha256(payload_json),
        "ingested_at": "2026-09-15T12:01:01.000Z",
        "sample_id": uid(sample_id),
        "lab_device_id": uid(device_id),
    }


def source_health(identity: int = 601, *, sample_id: int = 201, device_id: int = 1, kind: str = "dhcp", observed_at: str = "2026-09-15T12:00:00.000Z", roles=None):
    return {
        "matrix_format_version": 1,
        "sample_id": uid(sample_id),
        "lab_device_id": uid(device_id),
        "source_health_id": uid(identity),
        "source_health_event_id": uid(identity + 1000),
        "producer_id": "portal-zefer-01" if kind == "portal_headers" else "sensor-zefer-01",
        "site_id": SITE_ID,
        "capture_source_id": "zefer-portal-http-01" if kind == "portal_headers" else "zefer-span-01",
        "source_kind": kind,
        "status": "available",
        "reason_code": None,
        "observed_at": observed_at,
        "ingested_at": "2026-09-15T12:00:01.000Z",
        "point_roles": roles or ["latest_before_start", "during_window"],
    }


def manifest(*, devices=1, samples=1, evidence=1, health=1, matrix_id=901, limitations=None):
    return {
        "matrix_format_version": MATRIX_FORMAT_VERSION,
        "matrix_id": uid(matrix_id),
        "matrix_revision": MATRIX_REVISION,
        "sealed_at": "2026-09-15T13:00:00.000Z",
        "repository_head": "a" * 40,
        "repository_tree": "b" * 40,
        "site_id": SITE_ID,
        "collection_procedure_version": "1.0.0",
        "ground_truth_policy_version": "1.0.0",
        "production_schema_registry": [list(item) for item in PRODUCTION_SCHEMA_REGISTRY],
        "task01_retention_days": 30,
        "device_count": devices,
        "sealed_sample_count": samples,
        "evidence_count": evidence,
        "source_health_count": health,
        "invalid_sample_count": 0,
        "invalid_sample_reason_counts": {},
        "known_coverage_limitations": sorted(["quic_sparse"] if limitations is None else limitations),
        "supersedes_matrix_id": None,
    }


def write_staging(directory: Path, *, devices=None, states=None, samples=None, bindings=None):
    directory.mkdir()
    write_canonical_jsonl(directory / "devices.jsonl", [device()] if devices is None else devices)
    write_canonical_jsonl(directory / "device_states.jsonl", [device_state()] if states is None else states)
    write_canonical_jsonl(directory / "samples.jsonl", [sample()] if samples is None else samples)
    write_canonical_jsonl(directory / "collection_bindings.jsonl", [binding()] if bindings is None else bindings)


def write_matrix(directory: Path, *, devices=None, states=None, samples=None, evidence=None, health=None, manifest_row=None):
    directory.mkdir()
    device_rows = [device()] if devices is None else devices
    state_rows = [device_state()] if states is None else states
    sample_rows = [sample()] if samples is None else samples
    evidence_rows = [sealed_evidence()] if evidence is None else evidence
    health_rows = [source_health()] if health is None else health
    write_canonical_json(directory / "manifest.json", manifest_row or manifest(
        devices=len(device_rows), samples=len(sample_rows), evidence=len(evidence_rows), health=len(health_rows),
    ))
    write_canonical_jsonl(directory / "devices.jsonl", device_rows)
    write_canonical_jsonl(directory / "device_states.jsonl", state_rows)
    write_canonical_jsonl(directory / "samples.jsonl", sample_rows)
    write_canonical_jsonl(directory / "evidence.jsonl", evidence_rows)
    write_canonical_jsonl(directory / "source_health.jsonl", health_rows)
    write_checksums(directory)


def create_source_database(path: Path, evidence_rows, health_rows=()):
    connection = sqlite3.connect(path)
    connection.executescript(SCHEMA_SQL)
    ingest_sequence = 0
    for row in evidence_rows:
        ingest_sequence += 1
        normalized = row["payload"]
        payload_json = canonical_json(normalized)
        connection.execute(
            """INSERT INTO device_fingerprint_evidence (
                evidence_id, producer_id, source_event_id, source_kind,
                source_subtype, extractor_name, extractor_version,
                feature_schema_version, rule_version, site_id, capture_source_id,
                observed_at, observed_mac, observed_ip, privacy_class,
                quality_state, payload_json, payload_sha256, ingested_at,
                ingest_sequence
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                row["evidence_id"], row["producer_id"], row["source_event_id"], row["source_kind"],
                row["source_subtype"], row["extractor_name"], row["extractor_version"],
                row["feature_schema_version"], row["rule_version"], row["site_id"],
                row["capture_source_id"], row["observed_at"], row.get("observed_mac", "AA:BB:CC:DD:EE:01"),
                row.get("observed_ip", "192.168.8.10"), row["privacy_class"], row["quality_state"],
                payload_json, canonical_sha256(payload_json), row["ingested_at"], ingest_sequence,
            ),
        )
    for row in health_rows:
        ingest_sequence += 1
        content = canonical_json({
            "capture_source_id": row["capture_source_id"],
            "observed_at": row["observed_at"],
            "reason_code": row["reason_code"],
            "site_id": row["site_id"],
            "source_health_event_id": row["source_health_event_id"],
            "source_kind": row["source_kind"],
            "status": row["status"],
        })
        connection.execute(
            """INSERT INTO device_fingerprint_source_health_events (
                source_health_id, producer_id, source_health_event_id,
                site_id, capture_source_id, source_kind, status, reason_code,
                observed_at, content_sha256, ingested_at, ingest_sequence
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                row["source_health_id"], row["producer_id"], row["source_health_event_id"],
                row["site_id"], row["capture_source_id"], row["source_kind"], row["status"],
                row["reason_code"], row["observed_at"], canonical_sha256(content), row["ingested_at"],
                ingest_sequence,
            ),
        )
    connection.execute(
        """INSERT INTO device_fingerprint_storage_state (
            singleton_id, database_generation_id, last_ingest_sequence
        ) VALUES (?, ?, ?)""",
        (1, uid(701), ingest_sequence),
    )
    connection.commit()
    connection.close()
