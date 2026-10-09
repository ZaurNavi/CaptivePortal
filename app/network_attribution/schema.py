"""Fresh SQLite NI-02A schema V1; existing non-exact schemas fail closed."""

import sqlite3

from .models import NetworkAttributionStorageUnavailable

TABLES = {
    "attribution_schema": "singleton INTEGER PRIMARY KEY CHECK(singleton=1), schema_version INTEGER NOT NULL CHECK(schema_version=1)",
    "authority_facts": """fact_id TEXT PRIMARY KEY, schema_version INTEGER NOT NULL CHECK(schema_version=1),
site_id TEXT NOT NULL, capture_source_id TEXT NOT NULL, event_at TEXT NOT NULL, ingested_at TEXT NOT NULL,
message_type TEXT NOT NULL CHECK(message_type IN ('ack','release','decline')), client_mac TEXT NOT NULL,
ipv4 TEXT NOT NULL, xid INTEGER NOT NULL CHECK(xid BETWEEN 0 AND 4294967295),
server_ipv4 TEXT, option54_ipv4 TEXT, lease_seconds INTEGER, authority_class TEXT NOT NULL,
CHECK((message_type='ack' AND authority_class='trusted_dhcp_ack' AND server_ipv4 IS NOT NULL
AND option54_ipv4 IS NOT NULL AND lease_seconds IS NOT NULL AND lease_seconds BETWEEN 1 AND 86400) OR
(message_type IN ('release','decline') AND authority_class='validated_client_' || message_type
AND server_ipv4 IS NULL AND option54_ipv4 IS NULL AND lease_seconds IS NULL))""",
    "binding_intervals": """binding_id TEXT PRIMARY KEY, site_id TEXT NOT NULL, capture_source_id TEXT NOT NULL,
client_mac TEXT NOT NULL, ipv4 TEXT NOT NULL, valid_from TEXT NOT NULL, valid_until TEXT NOT NULL,
last_confirmed_at TEXT NOT NULL, lease_expires_at TEXT NOT NULL,
start_fact_id TEXT NOT NULL REFERENCES authority_facts(fact_id),
last_fact_id TEXT NOT NULL REFERENCES authority_facts(fact_id), end_reason TEXT,
CHECK(valid_from<=valid_until AND last_confirmed_at>=valid_from AND lease_expires_at>last_confirmed_at),
CHECK(end_reason IS NULL OR end_reason IN ('superseded_same_mac','superseded_same_ip','client_release','client_decline'))""",
    "binding_fact_links": "binding_id TEXT NOT NULL REFERENCES binding_intervals(binding_id) ON DELETE CASCADE, fact_id TEXT NOT NULL REFERENCES authority_facts(fact_id), PRIMARY KEY(binding_id,fact_id)",
    "source_coverage": """coverage_id TEXT PRIMARY KEY, coverage_from TEXT NOT NULL, coverage_until TEXT,
site_id TEXT NOT NULL, capture_source_id TEXT NOT NULL, state TEXT NOT NULL CHECK(state IN ('usable','unavailable')),
verified_through TEXT NOT NULL CHECK(verified_through>=coverage_from),
reason_code TEXT, CHECK(coverage_until IS NULL OR coverage_from<=coverage_until),
CHECK((state='usable' AND reason_code IS NULL) OR (state='unavailable' AND reason_code IS NOT NULL))""",
    "authority_horizon": "site_id TEXT PRIMARY KEY, first_usable_at TEXT NOT NULL, retained_from TEXT NOT NULL CHECK(retained_from>=first_usable_at)",
}
INDEXES = {
    "idx_na_ip_time": "binding_intervals(site_id,ipv4,valid_from,valid_until)",
    "idx_na_mac_time": "binding_intervals(site_id,client_mac,valid_from,valid_until)",
    "idx_na_fact_time": "authority_facts(site_id,event_at,client_mac,ipv4)",
    "idx_na_link_fact": "binding_fact_links(fact_id)",
    "idx_na_coverage_time": "source_coverage(site_id,capture_source_id,coverage_from,coverage_until)",
    "idx_na_expired": "binding_intervals(valid_until,binding_id)",
}


def create_schema(connection):
    for name, ddl in TABLES.items():
        connection.execute(f"CREATE TABLE {name} ({ddl})")
    for name, ddl in INDEXES.items():
        connection.execute(f"CREATE INDEX {name} ON {ddl}")
    connection.execute("CREATE UNIQUE INDEX ux_na_open_coverage ON source_coverage(site_id,capture_source_id) WHERE coverage_until IS NULL")
    connection.execute("CREATE TRIGGER immutable_na_facts BEFORE UPDATE ON authority_facts BEGIN SELECT RAISE(ABORT,'immutable_authority_fact'); END")
    connection.execute("INSERT INTO attribution_schema VALUES(1,1)")
    connection.execute("PRAGMA user_version=1")


def signature(connection):
    return tuple((kind, name, " ".join(sql.split())) for kind, name, sql in connection.execute(
        "SELECT type,name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name"))


def validate_schema_contract(connection):
    """Bounded schema-size checks, safe for each read snapshot."""
    with sqlite3.connect(":memory:") as reference:
        create_schema(reference)
        expected = signature(reference)
    if (connection.execute("PRAGMA user_version").fetchone()[0] != 1
            or signature(connection) != expected
            or [tuple(row) for row in connection.execute("SELECT * FROM attribution_schema")] != [(1, 1)]
            or connection.execute("PRAGMA foreign_keys").fetchone()[0] != 1
            or connection.execute("PRAGMA journal_mode").fetchone()[0].lower() != "wal"):
        raise NetworkAttributionStorageUnavailable("attribution_schema_unavailable")


def validate_storage_integrity(connection):
    """Full storage scans belong at initialization, not per endpoint lookup."""
    if (connection.execute("PRAGMA quick_check").fetchone()[0] != "ok"
            or connection.execute("PRAGMA foreign_key_check").fetchone() is not None):
        raise NetworkAttributionStorageUnavailable("attribution_schema_unavailable")


def validate_schema(connection):
    validate_schema_contract(connection)
    validate_storage_integrity(connection)
