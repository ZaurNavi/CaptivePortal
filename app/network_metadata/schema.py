"""Exact NI-01 SQLite V1 DDL and reference signature, not a migration system."""
import sqlite3

from .models import NetworkMetadataStorageCorrupt, NetworkMetadataValidationError


def _hex(column):
    return f"length({column})=64 AND {column} NOT GLOB '*[^0-9a-f]*'"


_PRESENCE = "CHECK({0} IN ('observed_retained','not_observed','expired'))"
_HEALTH = "CHECK({0} IN ('usable','partial','stale','unavailable','unknown'))"
_OBS_FK = "REFERENCES network_metadata_observations(observation_id) ON DELETE CASCADE"
TABLE_DDL = {
"network_metadata_schema": "singleton_id INTEGER PRIMARY KEY CHECK(singleton_id=1), schema_version INTEGER NOT NULL CHECK(schema_version=1), created_at_utc TEXT NOT NULL",
"network_metadata_ingest_runs": "ingest_run_id TEXT PRIMARY KEY, started_at_utc TEXT NOT NULL, repository_head TEXT NOT NULL, repository_tree TEXT NOT NULL, normalizer_version TEXT NOT NULL, configuration_digest TEXT NOT NULL",
"network_metadata_capture_scope_bindings": "binding_digest TEXT PRIMARY KEY, schema_version INTEGER NOT NULL CHECK(schema_version=1), capture_source_id TEXT NOT NULL, site_id TEXT NOT NULL, network_scope_id TEXT NOT NULL, ipv4_cidrs_json TEXT NOT NULL, valid_from_utc TEXT NOT NULL",
"network_metadata_source_generations": """source_generation_id TEXT PRIMARY KEY, logical_source_id TEXT NOT NULL,
host_boot_id TEXT NOT NULL, st_dev INTEGER NOT NULL CHECK(st_dev>=0), st_ino INTEGER NOT NULL CHECK(st_ino>=0),
generation_start_offset INTEGER NOT NULL CHECK(generation_start_offset>=0),
committed_byte_offset INTEGER NOT NULL CHECK(committed_byte_offset>=generation_start_offset),
end_offset INTEGER CHECK(end_offset IS NULL OR end_offset>=generation_start_offset),
capture_scope_binding_schema_version INTEGER NOT NULL CHECK(capture_scope_binding_schema_version=1),
capture_scope_binding_digest TEXT NOT NULL REFERENCES network_metadata_capture_scope_bindings(binding_digest),
binding_valid_from_utc TEXT NOT NULL, opened_at_utc TEXT NOT NULL, closed_at_utc TEXT, close_reason TEXT,
coverage_gap_possible INTEGER NOT NULL CHECK(coverage_gap_possible IN (0,1)),
processing_state TEXT NOT NULL CHECK(processing_state IN ('runnable','blocked')),
blocked_reason_code TEXT, blocked_at_utc TEXT, blocked_record_start_byte_offset INTEGER,
CHECK((processing_state='runnable' AND blocked_reason_code IS NULL AND blocked_at_utc IS NULL
AND blocked_record_start_byte_offset IS NULL) OR (processing_state='blocked'
AND blocked_reason_code IS NOT NULL AND blocked_reason_code IN
('source_record_identity_conflict','normalizer_determinism_conflict','replay_identity_evidence_expired')
AND blocked_at_utc IS NOT NULL AND length(blocked_at_utc)=27
AND blocked_at_utc GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9].[0-9][0-9][0-9][0-9][0-9][0-9]Z'
AND substr(blocked_at_utc,1,4)>'0000'
AND date(substr(blocked_at_utc,1,10),'+0 days') IS NOT NULL
AND date(substr(blocked_at_utc,1,10),'+0 days')=substr(blocked_at_utc,1,10)
AND substr(blocked_at_utc,12,2) BETWEEN '00' AND '23'
AND substr(blocked_at_utc,15,2) BETWEEN '00' AND '59'
AND substr(blocked_at_utc,18,2) BETWEEN '00' AND '59'
AND blocked_record_start_byte_offset IS NOT NULL
AND blocked_record_start_byte_offset>=generation_start_offset
AND blocked_record_start_byte_offset=committed_byte_offset
AND closed_at_utc IS NULL AND end_offset IS NULL AND close_reason IS NULL)),
CHECK((closed_at_utc IS NULL AND end_offset IS NULL AND close_reason IS NULL) OR
(closed_at_utc IS NOT NULL AND end_offset IS NOT NULL AND close_reason IS NOT NULL))""",
"network_metadata_checkpoint": f"""logical_source_id TEXT PRIMARY KEY,
source_generation_id TEXT NOT NULL REFERENCES network_metadata_source_generations(source_generation_id),
committed_byte_offset INTEGER NOT NULL CHECK(committed_byte_offset>=0),
continuity_anchor_start_offset INTEGER NOT NULL CHECK(continuity_anchor_start_offset>=0),
continuity_anchor_length INTEGER NOT NULL CHECK(continuity_anchor_length BETWEEN 0 AND 4096),
continuity_anchor_sha256 TEXT, updated_at_utc TEXT NOT NULL,
CHECK(continuity_anchor_start_offset+continuity_anchor_length=committed_byte_offset),
CHECK((continuity_anchor_length=0 AND continuity_anchor_sha256 IS NULL) OR
(continuity_anchor_length>0 AND continuity_anchor_sha256 IS NOT NULL AND {_hex('continuity_anchor_sha256')}))""",
"network_metadata_source_health": """health_id TEXT PRIMARY KEY, evaluated_at TEXT NOT NULL,
capture_source_id TEXT NOT NULL, source_generation_id TEXT REFERENCES network_metadata_source_generations(source_generation_id),
capture_health TEXT NOT NULL """ + _HEALTH.format("capture_health") + ", metadata_output_health TEXT NOT NULL " + _HEALTH.format("metadata_output_health") + ", metadata_ingest_health TEXT NOT NULL " + _HEALTH.format("metadata_ingest_health") + ", last_output_event_at TEXT, last_ingested_event_at TEXT, committed_byte_offset INTEGER CHECK(committed_byte_offset IS NULL OR committed_byte_offset>=0), reason_codes_json TEXT NOT NULL",
"network_metadata_observations": """observation_id TEXT PRIMARY KEY,
schema_version INTEGER NOT NULL CHECK(schema_version=1), source_type TEXT NOT NULL CHECK(source_type='suricata'),
source_contract_version TEXT NOT NULL CHECK(source_contract_version='suricata-eve-v1'),
source_event_family TEXT NOT NULL CHECK(source_event_family IN ('dns','tls','quic')), source_event_identity TEXT NOT NULL UNIQUE,
source_generation_id TEXT NOT NULL REFERENCES network_metadata_source_generations(source_generation_id),
record_start_byte_offset INTEGER NOT NULL CHECK(record_start_byte_offset>=0), capture_source_id TEXT NOT NULL,
capture_scope_binding_schema_version INTEGER NOT NULL CHECK(capture_scope_binding_schema_version=1),
capture_scope_binding_digest TEXT NOT NULL REFERENCES network_metadata_capture_scope_bindings(binding_digest),
network_scope_id TEXT NOT NULL, network_scope_state TEXT NOT NULL CHECK(network_scope_state='within_intended_scope'),
site_id TEXT NOT NULL, event_at TEXT NOT NULL, ingested_at TEXT NOT NULL, flow_id_decimal TEXT, transaction_id_decimal TEXT,
source_health_ref TEXT NOT NULL REFERENCES network_metadata_source_health(health_id),
ingest_run_id TEXT NOT NULL REFERENCES network_metadata_ingest_runs(ingest_run_id), normalizer_version TEXT NOT NULL,
sensitive_endpoint_presence_state TEXT NOT NULL """ + _PRESENCE.format("sensitive_endpoint_presence_state") + ", UNIQUE(source_generation_id,record_start_byte_offset)",
"network_metadata_source_records": f"""source_generation_id TEXT NOT NULL REFERENCES network_metadata_source_generations(source_generation_id),
record_start_byte_offset INTEGER NOT NULL CHECK(record_start_byte_offset>=0),
record_end_byte_offset INTEGER NOT NULL CHECK(record_end_byte_offset>record_start_byte_offset),
record_byte_length INTEGER NOT NULL CHECK(record_byte_length>=0),
source_event_family TEXT NOT NULL CHECK(source_event_family IN ('dns','tls','quic')),
outcome_code TEXT NOT NULL CHECK(outcome_code='normalized'), observation_id TEXT NOT NULL UNIQUE {_OBS_FK},
ingested_at TEXT NOT NULL, source_record_sha256 TEXT, semantic_payload_sha256 TEXT,
digest_state TEXT NOT NULL CHECK(digest_state IN ('retained','expired')),
PRIMARY KEY(source_generation_id,record_start_byte_offset),
CHECK(record_end_byte_offset=record_start_byte_offset+record_byte_length+1),
CHECK((digest_state='retained' AND source_record_sha256 IS NOT NULL AND semantic_payload_sha256 IS NOT NULL
AND {_hex('source_record_sha256')} AND {_hex('semantic_payload_sha256')}) OR
(digest_state='expired' AND source_record_sha256 IS NULL AND semantic_payload_sha256 IS NULL))""",
"network_metadata_sensitive_endpoints": f"observation_id TEXT PRIMARY KEY {_OBS_FK}, src_ip TEXT, dst_ip TEXT, src_port INTEGER CHECK(src_port IS NULL OR src_port BETWEEN 0 AND 65535), dst_port INTEGER CHECK(dst_port IS NULL OR dst_port BETWEEN 0 AND 65535), transport_protocol TEXT CHECK(transport_protocol IS NULL OR transport_protocol IN ('TCP','UDP'))",
"network_metadata_dns": f"""observation_id TEXT PRIMARY KEY {_OBS_FK}, dns_version INTEGER NOT NULL CHECK(dns_version=3),
dns_event_kind TEXT NOT NULL CHECK(dns_event_kind IN ('request','response')), dns_tx_id_decimal TEXT NOT NULL,
dns_wire_id INTEGER CHECK(dns_wire_id IS NULL OR dns_wire_id BETWEEN 0 AND 65535), rcode TEXT,
query_names_presence_state TEXT NOT NULL {_PRESENCE.format('query_names_presence_state')},
answer_values_presence_state TEXT NOT NULL {_PRESENCE.format('answer_values_presence_state')},
query_count_observed INTEGER NOT NULL CHECK(query_count_observed>=0), answer_count_observed INTEGER NOT NULL CHECK(answer_count_observed>=0),
queries_truncated INTEGER NOT NULL CHECK(queries_truncated IN (0,1)), answers_truncated INTEGER NOT NULL CHECK(answers_truncated IN (0,1))""",
"network_metadata_dns_queries": f"observation_id TEXT NOT NULL {_OBS_FK}, ordinal INTEGER NOT NULL CHECK(ordinal BETWEEN 0 AND 7), query_name TEXT NOT NULL, query_type TEXT NOT NULL, PRIMARY KEY(observation_id,ordinal)",
"network_metadata_dns_answers": f"observation_id TEXT NOT NULL {_OBS_FK}, ordinal INTEGER NOT NULL CHECK(ordinal BETWEEN 0 AND 31), answer_type TEXT NOT NULL CHECK(answer_type IN ('A','AAAA','CNAME')), answer_value TEXT NOT NULL, PRIMARY KEY(observation_id,ordinal)",
"network_metadata_tls": f"""observation_id TEXT PRIMARY KEY {_OBS_FK}, tls_version TEXT, sni TEXT,
sni_presence_state TEXT NOT NULL {_PRESENCE.format('sni_presence_state')},
client_alpns_truncated INTEGER NOT NULL CHECK(client_alpns_truncated IN (0,1)), server_alpns_truncated INTEGER NOT NULL CHECK(server_alpns_truncated IN (0,1))""",
"network_metadata_tls_alpn": f"observation_id TEXT NOT NULL {_OBS_FK}, side TEXT NOT NULL CHECK(side IN ('client','server')), ordinal INTEGER NOT NULL CHECK(ordinal BETWEEN 0 AND 15), alpn TEXT NOT NULL, PRIMARY KEY(observation_id,side,ordinal)",
"network_metadata_quic": f"observation_id TEXT PRIMARY KEY {_OBS_FK}, quic_version TEXT, sni TEXT, sni_presence_state TEXT NOT NULL {_PRESENCE.format('sni_presence_state')}",
"network_metadata_ingest_fault_aggregates": """logical_source_id TEXT NOT NULL, source_generation_key TEXT NOT NULL,
source_generation_id TEXT REFERENCES network_metadata_source_generations(source_generation_id), fault_category TEXT NOT NULL,
aggregation_epoch_start_utc TEXT NOT NULL, count INTEGER NOT NULL CHECK(count>0), first_seen_utc TEXT NOT NULL,
last_seen_utc TEXT NOT NULL, first_relevant_offset INTEGER CHECK(first_relevant_offset IS NULL OR first_relevant_offset>=0),
last_relevant_offset INTEGER CHECK(last_relevant_offset IS NULL OR last_relevant_offset>=0),
PRIMARY KEY(logical_source_id,source_generation_key,fault_category,aggregation_epoch_start_utc),
CHECK((source_generation_id IS NULL AND source_generation_key='none') OR
(source_generation_id IS NOT NULL AND source_generation_key=source_generation_id))""",
}
INDEX_DDL = {
"ux_nm_one_active_generation": "CREATE UNIQUE INDEX ux_nm_one_active_generation ON network_metadata_source_generations(logical_source_id) WHERE closed_at_utc IS NULL",
"idx_nm_observations_site_event": "network_metadata_observations(site_id,event_at,observation_id)",
"idx_nm_observations_site_family_event": "network_metadata_observations(site_id,source_event_family,event_at,observation_id)",
"idx_nm_observations_event": "network_metadata_observations(event_at,observation_id)",
"idx_nm_observations_ingested": "network_metadata_observations(ingested_at,observation_id)",
"idx_nm_source_generations_logical_opened": "network_metadata_source_generations(logical_source_id,opened_at_utc)",
"idx_nm_source_generations_closed": "network_metadata_source_generations(closed_at_utc,source_generation_id)",
"idx_nm_source_records_observation": "network_metadata_source_records(observation_id)",
"idx_nm_source_records_ingested": "network_metadata_source_records(ingested_at,source_generation_id,record_start_byte_offset)",
"idx_nm_source_health_capture_eval": "network_metadata_source_health(capture_source_id,evaluated_at,health_id)",
"idx_nm_source_health_generation_eval": "network_metadata_source_health(source_generation_id,evaluated_at,health_id)",
"idx_nm_faults_last_seen_category": "network_metadata_ingest_fault_aggregates(last_seen_utc,fault_category)",
"idx_nm_bindings_site_valid_from": "network_metadata_capture_scope_bindings(site_id,valid_from_utc,binding_digest)",
"idx_nm_ingest_runs_started": "network_metadata_ingest_runs(started_at_utc,ingest_run_id)",
}


def create_schema(connection, now):
    for name, columns in TABLE_DDL.items():
        connection.execute(f"CREATE TABLE {name} ({columns})")
    for name, ddl in INDEX_DDL.items():
        connection.execute(ddl if ddl.startswith("CREATE") else f"CREATE INDEX {name} ON {ddl}")
    connection.execute("INSERT INTO network_metadata_schema VALUES(1,1,?)", (now,))
    connection.execute("PRAGMA user_version=1")


def _signature(connection):
    signature = {}
    for kind, name, sql in connection.execute("SELECT type,name,sql FROM sqlite_master WHERE type IN ('table','index','trigger','view') AND name NOT LIKE 'sqlite_%'"):
        signature[(kind, name)] = " ".join((sql or "").split())
    for name in TABLE_DDL:
        signature[("columns", name)] = tuple(tuple(row) for row in connection.execute(f"PRAGMA table_info({name})"))
        signature[("fk", name)] = tuple(tuple(row) for row in connection.execute(f"PRAGMA foreign_key_list({name})"))
        signature[("indexes", name)] = tuple(tuple(row) for row in connection.execute(f"PRAGMA index_list({name})"))
    return signature


def validate_schema(connection, *, writer=True):
    try:
        with sqlite3.connect(":memory:") as reference:
            create_schema(reference, "2000-01-01T00:00:00.000000Z")
            expected = _signature(reference)
        if connection.execute("PRAGMA user_version").fetchone()[0] != 1 or _signature(connection) != expected:
            raise NetworkMetadataStorageCorrupt()
        rows = connection.execute("SELECT singleton_id,schema_version,created_at_utc FROM network_metadata_schema").fetchall()
        if len(rows) != 1 or tuple(rows[0])[:2] != (1, 1):
            raise NetworkMetadataStorageCorrupt()
        from .validation import ni_timestamp
        ni_timestamp(rows[0][2], canonical=True)
        if connection.execute("PRAGMA foreign_keys").fetchone()[0] != 1:
            raise NetworkMetadataStorageCorrupt()
        if connection.execute("PRAGMA journal_mode").fetchone()[0].lower() != "wal":
            raise NetworkMetadataStorageCorrupt()
        if writer and connection.execute("PRAGMA synchronous").fetchone()[0] != 2:
            raise NetworkMetadataStorageCorrupt()
    except (sqlite3.Error, ValueError, TypeError, NetworkMetadataValidationError):
        raise NetworkMetadataStorageCorrupt() from None
