"""Exact fresh Core V2 with an optional, separately versioned Service extension."""
import sqlite3
from functools import lru_cache
from .models import ALGORITHM, ATTRIBUTION_STATES, RUNTIME_STATES, ProjectionUnavailable
from .validation import timestamp
from app.network_metadata.validation import ni_timestamp

STATES = ",".join("'" + item + "'" for item in sorted(ATTRIBUTION_STATES))
SNAPSHOT_STATES = ",".join("'" + item + "'" for item in sorted(ATTRIBUTION_STATES - {"invalid"}))
VERSION = "projection_contract_version INTEGER NOT NULL CHECK(projection_contract_version=2), projection_algorithm_version TEXT NOT NULL CHECK(projection_algorithm_version='" + ALGORITHM + "')"
TABLES = {
"network_metadata_projection_schema": "singleton_id INTEGER PRIMARY KEY CHECK(singleton_id=1), schema_version INTEGER NOT NULL CHECK(schema_version=2), " + VERSION + ", created_at_utc TEXT NOT NULL",
"projection_scope_admission": "singleton_id INTEGER PRIMARY KEY CHECK(singleton_id=1), admission_digest TEXT NOT NULL UNIQUE, admission_json TEXT NOT NULL",
"projection_runs": "projection_run_id TEXT PRIMARY KEY, started_at_utc TEXT NOT NULL, repository_head TEXT NOT NULL, repository_tree TEXT NOT NULL, " + VERSION + ", configuration_digest TEXT NOT NULL, scope_admission_digest TEXT NOT NULL REFERENCES projection_scope_admission(admission_digest)",
"projection_source_reset_epoch": "singleton_id INTEGER PRIMARY KEY CHECK(singleton_id=1), reset_epoch_id TEXT NOT NULL UNIQUE, reset_at_utc TEXT NOT NULL, admission_digest TEXT NOT NULL REFERENCES projection_scope_admission(admission_digest), source_snapshot_digest TEXT NOT NULL, floor_count INTEGER NOT NULL CHECK(floor_count>=0)",
"projection_source_reset_floors": """source_generation_id TEXT PRIMARY KEY,
reset_epoch_id TEXT NOT NULL REFERENCES projection_source_reset_epoch(reset_epoch_id), reset_at_utc TEXT NOT NULL,
site_id TEXT NOT NULL, capture_source_id TEXT NOT NULL, network_scope_id TEXT NOT NULL,
capture_scope_binding_digest TEXT NOT NULL, binding_valid_from_utc TEXT NOT NULL,
generation_start_offset INTEGER NOT NULL CHECK(generation_start_offset>=0),
committed_byte_offset INTEGER NOT NULL CHECK(committed_byte_offset>=generation_start_offset),
last_retained_record_start_byte_offset INTEGER, last_retained_observation_id TEXT,
CHECK((last_retained_record_start_byte_offset IS NULL AND last_retained_observation_id IS NULL) OR
(last_retained_record_start_byte_offset IS NOT NULL AND last_retained_observation_id IS NOT NULL AND
last_retained_record_start_byte_offset>=generation_start_offset AND last_retained_record_start_byte_offset<committed_byte_offset))""",
"device_network_metadata_edges": """edge_id TEXT PRIMARY KEY, schema_version INTEGER NOT NULL CHECK(schema_version=1),
site_id TEXT NOT NULL, client_mac TEXT NOT NULL, event_at TEXT NOT NULL, source_ingested_at TEXT NOT NULL, projected_at TEXT NOT NULL,
device_endpoint_role TEXT NOT NULL CHECK(device_endpoint_role IN ('src','dst')), device_ip TEXT NOT NULL,
device_port INTEGER CHECK(device_port IS NULL OR device_port BETWEEN 0 AND 65535), peer_ip TEXT,
peer_port INTEGER CHECK(peer_port IS NULL OR peer_port BETWEEN 0 AND 65535),
transport_protocol TEXT CHECK(transport_protocol IS NULL OR transport_protocol IN ('TCP','UDP')),
peer_scope TEXT NOT NULL CHECK(peer_scope IN ('local','external','unknown')),
direction TEXT NOT NULL CHECK(direction IN ('outbound','inbound','local','unknown')),
source_observation_ref TEXT NOT NULL, source_event_identity TEXT NOT NULL,
source_event_family TEXT NOT NULL CHECK(source_event_family IN ('dns','tls','quic')),
source_generation_id TEXT NOT NULL, record_start_byte_offset INTEGER NOT NULL CHECK(record_start_byte_offset>=0),
capture_source_id TEXT NOT NULL, network_scope_id TEXT NOT NULL,
network_scope_state TEXT NOT NULL CHECK(network_scope_state='within_intended_scope'), capture_scope_binding_digest TEXT NOT NULL,
attribution_state TEXT NOT NULL CHECK(attribution_state='resolved'), attribution_source TEXT NOT NULL CHECK(attribution_source='trusted_dhcp_v4'),
attribution_binding_id TEXT NOT NULL, attribution_valid_from TEXT NOT NULL, attribution_valid_until TEXT NOT NULL,
peer_attribution_state TEXT NOT NULL CHECK(peer_attribution_state IN (""" + STATES + """)), peer_attribution_binding_id TEXT,
""" + VERSION + """, projection_run_id TEXT NOT NULL REFERENCES projection_runs(projection_run_id), edge_semantic_digest TEXT NOT NULL,
UNIQUE(source_observation_ref,device_endpoint_role), CHECK(peer_ip IS NOT NULL OR peer_port IS NULL),
CHECK((peer_attribution_state='resolved' AND peer_attribution_binding_id IS NOT NULL) OR (peer_attribution_state!='resolved' AND peer_attribution_binding_id IS NULL))""",
"projection_registry_identities": "device_id TEXT PRIMARY KEY, client_mac TEXT NOT NULL UNIQUE, registry_schema_version INTEGER NOT NULL CHECK(registry_schema_version=1), first_bound_at TEXT NOT NULL, last_verified_at TEXT NOT NULL, registry_record_updated_at TEXT",
"projection_site_mac_bindings": """site_id TEXT NOT NULL, client_mac TEXT NOT NULL,
binding_state TEXT NOT NULL CHECK(binding_state IN ('authoritative','not_yet_registry_resolved','registry_unavailable')),
device_id TEXT REFERENCES projection_registry_identities(device_id), first_edge_at TEXT NOT NULL, last_edge_at TEXT NOT NULL,
last_evaluated_at TEXT NOT NULL, authoritative_bound_at TEXT, last_safe_reason TEXT, PRIMARY KEY(site_id,client_mac),
CHECK((binding_state='authoritative' AND device_id IS NOT NULL AND authoritative_bound_at IS NOT NULL) OR
(binding_state IN ('not_yet_registry_resolved','registry_unavailable') AND device_id IS NULL AND authoritative_bound_at IS NULL))""",
"projection_registry_binding_events": """binding_event_id INTEGER PRIMARY KEY, site_id TEXT NOT NULL, client_mac TEXT NOT NULL,
previous_state TEXT, new_state TEXT NOT NULL, device_id TEXT, evaluated_at TEXT NOT NULL, registry_schema_version INTEGER,
registry_record_updated_at TEXT, safe_reason TEXT, projection_run_id TEXT NOT NULL REFERENCES projection_runs(projection_run_id)""",
"projection_source_checkpoints": "source_generation_id TEXT PRIMARY KEY, last_record_start_byte_offset INTEGER NOT NULL CHECK(last_record_start_byte_offset>=0), last_observation_id TEXT, last_source_ingested_at TEXT, updated_at_utc TEXT NOT NULL",
"projection_pending_attribution": """observation_id TEXT PRIMARY KEY, site_id TEXT NOT NULL, source_generation_id TEXT NOT NULL,
record_start_byte_offset INTEGER NOT NULL CHECK(record_start_byte_offset>=0), event_at TEXT NOT NULL, source_ingested_at TEXT NOT NULL,
pending_src INTEGER NOT NULL CHECK(pending_src IN (0,1)), pending_dst INTEGER NOT NULL CHECK(pending_dst IN (0,1)),
src_snapshot_state TEXT NOT NULL CHECK(src_snapshot_state IN (""" + SNAPSHOT_STATES + """)), src_snapshot_binding_id TEXT,
dst_snapshot_state TEXT NOT NULL CHECK(dst_snapshot_state IN (""" + SNAPSHOT_STATES + """)), dst_snapshot_binding_id TEXT,
first_pending_at TEXT NOT NULL, last_attempt_at TEXT NOT NULL, next_retry_at TEXT NOT NULL,
CHECK(pending_src=1 OR pending_dst=1), CHECK(pending_src=(src_snapshot_state='unavailable')), CHECK(pending_dst=(dst_snapshot_state='unavailable')),
CHECK((src_snapshot_state='resolved' AND src_snapshot_binding_id IS NOT NULL) OR (src_snapshot_state!='resolved' AND src_snapshot_binding_id IS NULL)),
CHECK((dst_snapshot_state='resolved' AND dst_snapshot_binding_id IS NOT NULL) OR (dst_snapshot_state!='resolved' AND dst_snapshot_binding_id IS NULL))""",
"projection_runtime_state": "singleton_id INTEGER PRIMARY KEY CHECK(singleton_id=1), runtime_state TEXT NOT NULL CHECK(runtime_state IN (" + ",".join("'" + state + "'" for state in sorted(RUNTIME_STATES)) + ")), safe_reason TEXT, last_source_poll_at TEXT, last_projection_commit_at TEXT, last_registry_reconcile_at TEXT, last_retention_at TEXT, pending_attribution_count INTEGER NOT NULL CHECK(pending_attribution_count>=0), blocked_observation_id TEXT, updated_at_utc TEXT NOT NULL",
}
INDEXES = {
"idx_projection_site_event": "device_network_metadata_edges(site_id,event_at,edge_id)",
"idx_projection_mac_event": "device_network_metadata_edges(site_id,client_mac,event_at,edge_id)",
"idx_projection_mac_family_event_latest": "device_network_metadata_edges(site_id,client_mac,source_event_family,event_at DESC,edge_id)",
"idx_projection_observation_role": "device_network_metadata_edges(source_observation_ref,device_endpoint_role)",
"idx_projection_binding_evaluation": "projection_site_mac_bindings(binding_state,last_evaluated_at,site_id,client_mac)",
"idx_projection_identity_mac": "projection_registry_identities(client_mac)",
"idx_projection_binding_event": "projection_registry_binding_events(site_id,client_mac,evaluated_at,binding_event_id)",
"idx_projection_retry": "projection_pending_attribution(next_retry_at,observation_id)",
"idx_projection_checkpoint": "projection_source_checkpoints(updated_at_utc,source_generation_id)",
"idx_projection_edge_expiry": "device_network_metadata_edges(event_at,edge_id)",
"idx_projection_edge_ingest_expiry": "device_network_metadata_edges(source_ingested_at,edge_id)",
"idx_projection_event_expiry": "projection_registry_binding_events(evaluated_at,binding_event_id)",
}


def create_schema(connection, now):
    for name, ddl in TABLES.items():
        connection.execute(f"CREATE TABLE {name} ({ddl})")
    for name, ddl in INDEXES.items():
        connection.execute(f"CREATE INDEX {name} ON {ddl}")
    for table in ("device_network_metadata_edges", "projection_registry_binding_events"):
        connection.execute(f"CREATE TRIGGER immutable_{table} BEFORE UPDATE ON {table} BEGIN SELECT RAISE(ABORT,'immutable_projection_fact'); END")
        connection.execute(f"CREATE TRIGGER retained_{table} BEFORE DELETE ON {table} WHEN projection_retention_delete_authorized()!=1 BEGIN SELECT RAISE(ABORT,'projection_retention_required'); END")
    for table in ("projection_scope_admission", "projection_source_reset_epoch", "projection_source_reset_floors"):
        for operation in ("UPDATE", "DELETE"):
            connection.execute(f"CREATE TRIGGER immutable_{table}_{operation.lower()} BEFORE {operation} ON {table} BEGIN SELECT RAISE(ABORT,'immutable_reset_boundary'); END")
    connection.execute("INSERT INTO network_metadata_projection_schema VALUES(1,2,2,?,?)", (ALGORITHM, now))
    connection.execute("INSERT INTO projection_runtime_state(singleton_id,runtime_state,pending_attribution_count,updated_at_utc) VALUES(1,'initializing',0,?)", (now,))
    connection.execute("PRAGMA user_version=2")


def signature(connection):
    return tuple((kind, name, " ".join(sql.split())) for kind, name, sql in connection.execute(
        "SELECT type,name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name"))


@lru_cache(maxsize=1)
def _expected_signatures():
    from .service_extension import create_extension_objects
    with sqlite3.connect(":memory:") as reference:
        create_schema(reference, "2000-01-01T00:00:00.000000Z")
        core = signature(reference)
        create_extension_objects(reference)
        extension = tuple(row for row in signature(reference) if row not in core)
    return core, extension


def validate_core_schema_v2(connection):
    expected, _ = _expected_signatures()
    _validate_core_schema_v2(connection, expected)


def _validate_core_schema_v2(connection, expected):
    names = {row[1] for row in expected}
    actual = tuple(row for row in signature(connection) if row[1] in names)
    rows = connection.execute("SELECT * FROM network_metadata_projection_schema").fetchall()
    runtime = connection.execute("SELECT * FROM projection_runtime_state").fetchall()
    if (actual != expected or connection.execute("PRAGMA user_version").fetchone()[0] != 2
            or len(rows) != 1 or tuple(rows[0])[:4] != (1, 2, 2, ALGORITHM)
            or len(runtime) != 1 or runtime[0][0] != 1
            or connection.execute("PRAGMA foreign_keys").fetchone()[0] != 1
            or connection.execute("PRAGMA journal_mode").fetchone()[0].lower() != "wal"):
        raise ValueError
    ni_timestamp(rows[0][4], canonical=True)
    from .config import ScopeAdmission
    admission_rows = connection.execute("SELECT admission_digest,admission_json FROM projection_scope_admission").fetchall()
    if len(admission_rows) > 1:
        raise ValueError
    if admission_rows:
        admitted = ScopeAdmission(admission_rows[0][1])
        if admitted.digest != admission_rows[0][0] or admitted.canonical != admission_rows[0][1]:
            raise ValueError
    epoch = connection.execute("SELECT * FROM projection_source_reset_epoch").fetchall()
    if len(epoch) > 1 or (epoch and not admission_rows):
        raise ValueError
    if epoch:
        from .validation import validate_reset_floors
        validate_reset_floors(connection, admitted)
    elif connection.execute("SELECT 1 FROM projection_source_reset_floors LIMIT 1").fetchone():
        raise ValueError


def validate_service_recognition_extension_v1(connection):
    from .service_extension import validate_extension_metadata
    _, expected = _expected_signatures()
    names = {row[1] for row in expected}
    actual = tuple(row for row in signature(connection) if row[1] in names)
    if not actual:
        return False
    if actual != expected:
        raise ValueError
    validate_extension_metadata(connection)
    return True


def validate_schema(connection, *, integrity=False):
    core, _ = _expected_signatures()
    return _validate_schema(connection, core, integrity=integrity)


def _validate_schema(connection, core, *, integrity):
    """Shared strict validator; only the maintenance operation supplies old core."""
    try:
        _validate_core_schema_v2(connection, core)
        present = validate_service_recognition_extension_v1(connection)
        _, extension = _expected_signatures()
        if signature(connection) != tuple(sorted(core + (extension if present else ()))):
            raise ValueError
        if integrity and (connection.execute("PRAGMA quick_check").fetchone()[0] != "ok"
                          or connection.execute("PRAGMA foreign_key_check").fetchone() is not None):
            raise ValueError
        return "CORE_PLUS_EXTENSION_V1" if present else "CORE_ONLY"
    except Exception:
        raise ProjectionUnavailable() from None
