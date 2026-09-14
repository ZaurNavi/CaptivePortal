"""Exact SQLite schema v1 for fingerprint evidence."""

SCHEMA_VERSION = 1

SCHEMA_SQL = """
CREATE TABLE device_fingerprint_evidence (
 evidence_id TEXT PRIMARY KEY NOT NULL CHECK(length(evidence_id)=36),
 producer_id TEXT NOT NULL CHECK(length(producer_id) BETWEEN 1 AND 64),
 source_event_id TEXT NOT NULL CHECK(length(source_event_id)=36),
 source_kind TEXT NOT NULL CHECK(length(source_kind) BETWEEN 1 AND 64),
 source_subtype TEXT NULL CHECK(source_subtype IS NULL OR length(source_subtype) BETWEEN 1 AND 64),
 extractor_name TEXT NOT NULL CHECK(length(extractor_name) BETWEEN 1 AND 64),
 extractor_version TEXT NOT NULL CHECK(length(extractor_version) BETWEEN 1 AND 64),
 feature_schema_version INTEGER NOT NULL CHECK(feature_schema_version>=1 AND feature_schema_version<=2147483647),
 rule_version TEXT NULL CHECK(rule_version IS NULL OR length(rule_version) BETWEEN 1 AND 64),
 site_id TEXT NOT NULL CHECK(length(site_id)=24 AND site_id NOT GLOB '*[^0-9a-f]*'),
 capture_source_id TEXT NOT NULL CHECK(length(capture_source_id) BETWEEN 1 AND 64),
 observed_at TEXT NOT NULL CHECK(length(observed_at)=24 AND substr(observed_at,-1,1)='Z'),
 observed_mac TEXT NOT NULL CHECK(length(observed_mac)=17),
 observed_ip TEXT NULL CHECK(observed_ip IS NULL OR length(observed_ip) BETWEEN 2 AND 45),
 privacy_class TEXT NOT NULL CHECK(privacy_class='P1'),
 quality_state TEXT NOT NULL CHECK(quality_state IN ('valid','partial','degraded')),
 payload_json TEXT NOT NULL CHECK(length(payload_json)>=2),
 payload_sha256 TEXT NOT NULL CHECK(length(payload_sha256)=64 AND payload_sha256 NOT GLOB '*[^0-9a-f]*'),
 ingested_at TEXT NOT NULL CHECK(length(ingested_at)=24 AND substr(ingested_at,-1,1)='Z')
);
CREATE UNIQUE INDEX uq_df_evidence_producer_event ON device_fingerprint_evidence(producer_id,source_event_id);
CREATE INDEX idx_df_evidence_site_mac_time ON device_fingerprint_evidence(site_id,observed_mac,observed_at,evidence_id);
CREATE INDEX idx_df_evidence_site_kind_time ON device_fingerprint_evidence(site_id,source_kind,observed_at,evidence_id);
CREATE INDEX idx_df_evidence_retention ON device_fingerprint_evidence(observed_at,evidence_id);
CREATE TABLE device_fingerprint_source_health_events (
 source_health_id TEXT PRIMARY KEY NOT NULL CHECK(length(source_health_id)=36),
 producer_id TEXT NOT NULL CHECK(length(producer_id) BETWEEN 1 AND 64),
 source_health_event_id TEXT NOT NULL CHECK(length(source_health_event_id)=36),
 site_id TEXT NOT NULL CHECK(length(site_id)=24 AND site_id NOT GLOB '*[^0-9a-f]*'),
 capture_source_id TEXT NOT NULL CHECK(length(capture_source_id) BETWEEN 1 AND 64),
 source_kind TEXT NOT NULL CHECK(length(source_kind) BETWEEN 1 AND 64),
 status TEXT NOT NULL CHECK(status IN ('available','unavailable','unsupported')),
 reason_code TEXT NULL CHECK(reason_code IS NULL OR length(reason_code) BETWEEN 1 AND 64),
 observed_at TEXT NOT NULL CHECK(length(observed_at)=24 AND substr(observed_at,-1,1)='Z'),
 content_sha256 TEXT NOT NULL CHECK(length(content_sha256)=64 AND content_sha256 NOT GLOB '*[^0-9a-f]*'),
 ingested_at TEXT NOT NULL CHECK(length(ingested_at)=24 AND substr(ingested_at,-1,1)='Z')
);
CREATE UNIQUE INDEX uq_df_source_health_producer_event ON device_fingerprint_source_health_events(producer_id,source_health_event_id);
CREATE INDEX idx_df_source_health_scope_time ON device_fingerprint_source_health_events(site_id,capture_source_id,source_kind,observed_at,source_health_id);
CREATE INDEX idx_df_source_health_retention ON device_fingerprint_source_health_events(observed_at,source_health_id);
PRAGMA user_version=1;
"""

EXPECTED_COLUMNS = {
    "device_fingerprint_evidence": (
        ("evidence_id", "TEXT", 1, 1), ("producer_id", "TEXT", 1, 0),
        ("source_event_id", "TEXT", 1, 0), ("source_kind", "TEXT", 1, 0),
        ("source_subtype", "TEXT", 0, 0), ("extractor_name", "TEXT", 1, 0),
        ("extractor_version", "TEXT", 1, 0), ("feature_schema_version", "INTEGER", 1, 0),
        ("rule_version", "TEXT", 0, 0), ("site_id", "TEXT", 1, 0),
        ("capture_source_id", "TEXT", 1, 0), ("observed_at", "TEXT", 1, 0),
        ("observed_mac", "TEXT", 1, 0), ("observed_ip", "TEXT", 0, 0),
        ("privacy_class", "TEXT", 1, 0), ("quality_state", "TEXT", 1, 0),
        ("payload_json", "TEXT", 1, 0), ("payload_sha256", "TEXT", 1, 0),
        ("ingested_at", "TEXT", 1, 0),
    ),
    "device_fingerprint_source_health_events": (
        ("source_health_id", "TEXT", 1, 1), ("producer_id", "TEXT", 1, 0),
        ("source_health_event_id", "TEXT", 1, 0), ("site_id", "TEXT", 1, 0),
        ("capture_source_id", "TEXT", 1, 0), ("source_kind", "TEXT", 1, 0),
        ("status", "TEXT", 1, 0), ("reason_code", "TEXT", 0, 0),
        ("observed_at", "TEXT", 1, 0), ("content_sha256", "TEXT", 1, 0),
        ("ingested_at", "TEXT", 1, 0),
    ),
}

EXPECTED_INDEXES = {
    "device_fingerprint_evidence": {
        "uq_df_evidence_producer_event": (1, ("producer_id", "source_event_id")),
        "idx_df_evidence_site_mac_time": (0, ("site_id", "observed_mac", "observed_at", "evidence_id")),
        "idx_df_evidence_site_kind_time": (0, ("site_id", "source_kind", "observed_at", "evidence_id")),
        "idx_df_evidence_retention": (0, ("observed_at", "evidence_id")),
    },
    "device_fingerprint_source_health_events": {
        "uq_df_source_health_producer_event": (1, ("producer_id", "source_health_event_id")),
        "idx_df_source_health_scope_time": (0, ("site_id", "capture_source_id", "source_kind", "observed_at", "source_health_id")),
        "idx_df_source_health_retention": (0, ("observed_at", "source_health_id")),
    },
}

REQUIRED_CHECK_FRAGMENTS = {
    "device_fingerprint_evidence": (
        "check(length(evidence_id)=36)",
        "check(length(producer_id)between1and64)",
        "check(length(source_event_id)=36)",
        "check(length(source_kind)between1and64)",
        "check(source_subtypeisnullorlength(source_subtype)between1and64)",
        "check(length(extractor_name)between1and64)",
        "check(length(extractor_version)between1and64)",
        "check(feature_schema_version>=1andfeature_schema_version<=2147483647)",
        "check(rule_versionisnullorlength(rule_version)between1and64)",
        "check(length(site_id)=24andsite_idnotglob'*[^0-9a-f]*')",
        "check(length(capture_source_id)between1and64)",
        "check(length(observed_at)=24andsubstr(observed_at,-1,1)='z')",
        "check(length(observed_mac)=17)",
        "check(observed_ipisnullorlength(observed_ip)between2and45)",
        "check(privacy_class='p1')",
        "check(quality_statein('valid','partial','degraded'))",
        "check(length(payload_json)>=2)",
        "check(length(payload_sha256)=64andpayload_sha256notglob'*[^0-9a-f]*')",
        "check(length(ingested_at)=24andsubstr(ingested_at,-1,1)='z')",
    ),
    "device_fingerprint_source_health_events": (
        "check(length(source_health_id)=36)",
        "check(length(producer_id)between1and64)",
        "check(length(source_health_event_id)=36)",
        "check(length(site_id)=24andsite_idnotglob'*[^0-9a-f]*')",
        "check(length(capture_source_id)between1and64)",
        "check(length(source_kind)between1and64)",
        "check(statusin('available','unavailable','unsupported'))",
        "check(reason_codeisnullorlength(reason_code)between1and64)",
        "check(length(observed_at)=24andsubstr(observed_at,-1,1)='z')",
        "check(length(content_sha256)=64andcontent_sha256notglob'*[^0-9a-f]*')",
        "check(length(ingested_at)=24andsubstr(ingested_at,-1,1)='z')",
    ),
}
