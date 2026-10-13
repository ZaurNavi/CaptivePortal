"""Closed NI-04 V1 store. No upstream schema or raw network evidence."""
import sqlite3
from functools import lru_cache
from app.network_metadata.validation import ni_timestamp

ALGORITHM = "background-service-materialization.v1"
DDL = (
    """CREATE TABLE service_materialization_schema (
        singleton_id INTEGER PRIMARY KEY CHECK(singleton_id=1),
        schema_version INTEGER NOT NULL CHECK(schema_version=1),
        materialization_contract_version INTEGER NOT NULL CHECK(materialization_contract_version=1),
        algorithm_version TEXT NOT NULL CHECK(algorithm_version='background-service-materialization.v1'),
        created_at_utc TEXT NOT NULL)""",
    """CREATE TABLE service_materialization_generations (
        generation_id TEXT PRIMARY KEY,
        state TEXT NOT NULL CHECK(state IN ('building','active','superseded','expired','failed')),
        taxonomy_id TEXT NOT NULL,taxonomy_version INTEGER NOT NULL CHECK(taxonomy_version>0),taxonomy_digest_sha256 TEXT NOT NULL,
        knowledge_manifest_id TEXT NOT NULL,knowledge_manifest_version INTEGER NOT NULL CHECK(knowledge_manifest_version>0),knowledge_manifest_digest_sha256 TEXT NOT NULL,
        ruleset_id TEXT NOT NULL,ruleset_version INTEGER NOT NULL CHECK(ruleset_version>0),ruleset_digest_sha256 TEXT NOT NULL,
        build_started_at_utc TEXT NOT NULL,backfill_from_utc TEXT NOT NULL,
        live_feed_start_seq INTEGER NOT NULL CHECK(live_feed_start_seq>=0),
        activated_at_utc TEXT,superseded_at_utc TEXT,publishable_until_utc TEXT NOT NULL,
        UNIQUE(taxonomy_digest_sha256,knowledge_manifest_digest_sha256,ruleset_digest_sha256))""",
    "CREATE UNIQUE INDEX idx_materialization_active ON service_materialization_generations(state) WHERE state='active'",
    """CREATE TABLE service_recognition_observations (
        service_observation_id TEXT NOT NULL,generation_id TEXT NOT NULL,
        edge_id TEXT NOT NULL,source_observation_ref TEXT NOT NULL,
        site_id TEXT NOT NULL,device_id TEXT NOT NULL,client_mac TEXT NOT NULL,
        registry_binding_change_seq INTEGER NOT NULL CHECK(registry_binding_change_seq>0),
        observed_at TEXT NOT NULL,source_event_family TEXT NOT NULL CHECK(source_event_family IN ('tls','quic')),
        service_id TEXT NOT NULL,organization_id TEXT NOT NULL,service_category_id TEXT NOT NULL,
        evidence_strength_class TEXT NOT NULL CHECK(evidence_strength_class='strong'),
        support_state TEXT NOT NULL CHECK(support_state='directly_supported'),
        matched_rule_id TEXT NOT NULL,materialized_at_utc TEXT NOT NULL,
        PRIMARY KEY(service_observation_id),UNIQUE(generation_id,service_observation_id),UNIQUE(generation_id,edge_id),
        FOREIGN KEY(generation_id) REFERENCES service_materialization_generations(generation_id) ON DELETE CASCADE)""",
    "CREATE INDEX idx_materialization_observation_retention ON service_recognition_observations(observed_at,generation_id,service_observation_id)",
    """CREATE TRIGGER materialization_observation_immutable BEFORE UPDATE ON service_recognition_observations
        BEGIN SELECT RAISE(ABORT,'immutable_service_observation'); END""",
    """CREATE TRIGGER materialization_observation_retention BEFORE DELETE ON service_recognition_observations
        WHEN service_retention_authorized()<>1 BEGIN SELECT RAISE(ABORT,'unauthorized_service_retention'); END""",
    """CREATE TABLE device_service_rollups (
        generation_id TEXT NOT NULL,site_id TEXT NOT NULL,device_id TEXT NOT NULL,client_mac TEXT NOT NULL,
        service_id TEXT NOT NULL,display_name TEXT NOT NULL,organization_id TEXT NOT NULL,organization_display_name TEXT NOT NULL,
        service_category_id TEXT NOT NULL,service_category_display_name TEXT NOT NULL,
        last_observed_at TEXT NOT NULL,last_service_observation_id TEXT NOT NULL,
        PRIMARY KEY(generation_id,site_id,device_id,service_id),
        FOREIGN KEY(generation_id,last_service_observation_id) REFERENCES service_recognition_observations(generation_id,service_observation_id))""",
    "CREATE INDEX idx_materialization_device_recent ON device_service_rollups(generation_id,site_id,device_id,client_mac,last_observed_at DESC,service_id)",
    "CREATE INDEX idx_materialization_rollup_retention ON device_service_rollups(last_observed_at,generation_id,site_id,device_id,service_id)",
    "CREATE INDEX idx_materialization_rollup_observation ON device_service_rollups(generation_id,last_service_observation_id)",
    """CREATE TABLE device_materialization_state (
        generation_id TEXT NOT NULL,site_id TEXT NOT NULL,device_id TEXT NOT NULL,client_mac TEXT NOT NULL,
        identity_binding_state TEXT NOT NULL CHECK(identity_binding_state IN ('authoritative','pending','unavailable','absent','conflict')),
        registry_binding_change_seq INTEGER NOT NULL CHECK(registry_binding_change_seq>0),
        source_state TEXT NOT NULL CHECK(source_state IN ('usable','degraded','unknown','unavailable')),
        pipeline_attribution_state TEXT NOT NULL CHECK(pipeline_attribution_state IN ('usable','degraded','unknown','unavailable')),
        device_linked_pending INTEGER NOT NULL CHECK(device_linked_pending IN (0,1)),
        recognition_state TEXT NOT NULL CHECK(recognition_state IN ('usable','limited','unavailable')),
        coverage_evaluated_at_utc TEXT NOT NULL,coverage_valid_from_utc TEXT NOT NULL,
        last_recognition_limitation_at TEXT,last_materialized_at_utc TEXT,
        PRIMARY KEY(generation_id,site_id,device_id),
        FOREIGN KEY(generation_id) REFERENCES service_materialization_generations(generation_id) ON DELETE CASCADE)""",
    "CREATE INDEX idx_materialization_coverage_due ON device_materialization_state(generation_id,coverage_evaluated_at_utc,site_id,device_id)",
    """CREATE TABLE service_materialization_checkpoints (
        generation_id TEXT PRIMARY KEY,last_edge_feed_seq INTEGER NOT NULL CHECK(last_edge_feed_seq>=0),
        last_binding_change_seq INTEGER NOT NULL CHECK(last_binding_change_seq>=0),
        backfill_state TEXT NOT NULL CHECK(backfill_state IN ('not_started','running','complete','blocked')),
        backfill_from_utc TEXT NOT NULL,backfill_site_id TEXT,backfill_event_at TEXT,backfill_edge_id TEXT,
        recovery_feed_highwater_seq INTEGER CHECK(recovery_feed_highwater_seq>=0),
        recovery_live_feed_seq INTEGER CHECK(recovery_live_feed_seq>=0),
        recovery_cutoff_utc TEXT,last_feed_gap_at_utc TEXT,
        updated_at_utc TEXT NOT NULL,
        CHECK((recovery_feed_highwater_seq IS NULL)=(recovery_live_feed_seq IS NULL)),
        CHECK((recovery_feed_highwater_seq IS NULL)=(recovery_cutoff_utc IS NULL)),
        FOREIGN KEY(generation_id) REFERENCES service_materialization_generations(generation_id) ON DELETE CASCADE)""",
    """CREATE TABLE service_binding_replay_jobs (
        job_id TEXT PRIMARY KEY,generation_id TEXT NOT NULL,binding_change_seq INTEGER NOT NULL CHECK(binding_change_seq>0),
        site_id TEXT NOT NULL,client_mac TEXT NOT NULL,device_id TEXT NOT NULL,
        from_utc TEXT NOT NULL,to_utc TEXT NOT NULL,cursor_event_at TEXT,cursor_edge_id TEXT,
        state TEXT NOT NULL CHECK(state IN ('pending','running','complete','terminal')),
        UNIQUE(generation_id,binding_change_seq),
        CHECK((cursor_event_at IS NULL)=(cursor_edge_id IS NULL)),
        FOREIGN KEY(generation_id) REFERENCES service_materialization_generations(generation_id) ON DELETE CASCADE)""",
    "CREATE INDEX idx_materialization_replay_due ON service_binding_replay_jobs(generation_id,state,binding_change_seq)",
    """CREATE TABLE service_materialization_runtime (
        singleton_id INTEGER PRIMARY KEY CHECK(singleton_id=1),
        runtime_state TEXT NOT NULL CHECK(runtime_state IN ('initializing','backfilling','usable','lagging','source_unavailable','recognition_unavailable','capacity_halted','blocked_conflict','stopping')),
        safe_reason TEXT,active_generation_id TEXT,last_upstream_poll_at_utc TEXT,
        last_successful_commit_at_utc TEXT,observed_feed_highwater_seq INTEGER CHECK(observed_feed_highwater_seq>=0),
        committed_feed_cursor_seq INTEGER CHECK(committed_feed_cursor_seq>=0),
        last_coverage_reconcile_at_utc TEXT,updated_at_utc TEXT NOT NULL,
        FOREIGN KEY(active_generation_id) REFERENCES service_materialization_generations(generation_id))""",
)


class MaterializationUnavailable(RuntimeError):
    def __init__(self):
        super().__init__("materialization_unavailable")


def signature(connection):
    return tuple((kind,name," ".join(sql.lower().split()) if sql else None)
        for kind,name,sql in connection.execute("SELECT type,name,sql FROM sqlite_schema WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name"))


@lru_cache(maxsize=1)
def expected_signature():
    connection = sqlite3.connect(":memory:")
    try:
        for statement in DDL:
            connection.execute(statement)
        return signature(connection)
    finally:
        connection.close()


def create_schema(connection, at):
    ni_timestamp(at, canonical=True)
    for statement in DDL:
        connection.execute(statement)
    connection.execute("PRAGMA user_version=1")
    connection.execute("INSERT INTO service_materialization_schema VALUES(1,1,1,?,?)", (ALGORITHM,at))
    connection.execute("INSERT INTO service_materialization_runtime(singleton_id,runtime_state,updated_at_utc) VALUES(1,'initializing',?)", (at,))


def validate_schema(connection, *, integrity=False):
    try:
        if signature(connection) != expected_signature():
            raise ValueError
        if connection.execute("PRAGMA user_version").fetchone()[0] != 1 or connection.execute("PRAGMA foreign_keys").fetchone()[0] != 1:
            raise ValueError
        if connection.execute("PRAGMA journal_mode").fetchone()[0].lower() != "wal":
            raise ValueError
        rows = connection.execute("SELECT * FROM service_materialization_schema").fetchall()
        if len(rows) != 1 or tuple(rows[0][:4]) != (1,1,1,ALGORITHM):
            raise ValueError
        ni_timestamp(rows[0][4],canonical=True)
        if connection.execute("SELECT count(*) FROM service_materialization_runtime").fetchone()[0] != 1:
            raise ValueError
        if integrity and (tuple(row[0] for row in connection.execute("PRAGMA quick_check")) != ("ok",)
                or connection.execute("PRAGMA foreign_key_check").fetchone() is not None):
            raise ValueError
    except Exception:
        raise MaterializationUnavailable() from None
