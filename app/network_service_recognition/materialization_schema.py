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


# Exactly one additional source-owned table. Sequence zero is the durable
# stream/floor anchor, not a second queue or metadata database. Facts have no
# FK to expiring NI04 generations: unacknowledged delivery must survive them.
VISIT_OUTBOX_DDL = """CREATE TABLE ni04_visit_delivery_outbox (
    outbox_seq INTEGER PRIMARY KEY AUTOINCREMENT,
    stream_id TEXT NOT NULL,
    kind TEXT NOT NULL CHECK(kind IN ('anchor','positive','binding','generation')),
    site_id TEXT,device_id TEXT,client_mac TEXT,edge_id TEXT,service_id TEXT,
    observed_at TEXT,source_ref TEXT,generation_id TEXT,source_observation_id TEXT,
    binding_seq INTEGER CHECK(binding_seq>0),
    taxonomy_id TEXT,taxonomy_version INTEGER,taxonomy_digest TEXT,
    ruleset_id TEXT,ruleset_version INTEGER,ruleset_digest TEXT,rule_id TEXT,
    service_label TEXT,organization_id TEXT,organization_label TEXT,category_id TEXT,
    created_at TEXT NOT NULL,previous_hash TEXT NOT NULL,entry_hash TEXT NOT NULL,
    head_seq INTEGER,head_hash TEXT,floor_seq INTEGER,floor_hash TEXT,consumer_id TEXT,
    CHECK((kind='anchor')=(outbox_seq=0)),
    CHECK((kind='anchor')=(head_seq IS NOT NULL)),
    CHECK(kind<>'anchor' OR (head_seq>=floor_seq AND floor_seq>=0 AND head_hash IS NOT NULL AND floor_hash IS NOT NULL)),
    CHECK(kind<>'positive' OR (site_id IS NOT NULL AND device_id IS NOT NULL AND client_mac IS NOT NULL
        AND edge_id IS NOT NULL AND service_id IS NOT NULL AND observed_at IS NOT NULL
        AND source_ref IS NOT NULL AND generation_id IS NOT NULL AND source_observation_id IS NOT NULL
        AND binding_seq IS NOT NULL AND taxonomy_id IS NOT NULL AND taxonomy_version>0 AND taxonomy_digest IS NOT NULL
        AND ruleset_id IS NOT NULL AND ruleset_version>0 AND ruleset_digest IS NOT NULL AND rule_id IS NOT NULL
        AND service_label IS NOT NULL AND organization_id IS NOT NULL AND organization_label IS NOT NULL AND category_id IS NOT NULL)),
    CHECK(kind<>'binding' OR (site_id IS NOT NULL AND device_id IS NOT NULL AND client_mac IS NOT NULL AND binding_seq IS NOT NULL)),
    CHECK(kind<>'generation' OR generation_id IS NOT NULL))"""
VISIT_OUTBOX_INDEX = "CREATE INDEX idx_ni04_visit_delivery_identity ON ni04_visit_delivery_outbox(site_id,client_mac,outbox_seq)"
DDL_V2 = (DDL[0].replace('CHECK(schema_version=1)', 'CHECK(schema_version=2)'), *DDL[1:],
    VISIT_OUTBOX_DDL, VISIT_OUTBOX_INDEX)


def signature(connection):
    return tuple((kind,name," ".join(sql.lower().split()) if sql else None)
        for kind,name,sql in connection.execute("SELECT type,name,sql FROM sqlite_schema WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name"))


@lru_cache(maxsize=2)
def expected_signature(version=2):
    if type(version) is not int or version not in (1,2):
        raise MaterializationUnavailable()
    connection = sqlite3.connect(":memory:")
    try:
        for statement in (DDL if version==1 else DDL_V2):
            connection.execute(statement)
        return signature(connection)
    finally:
        connection.close()


def create_schema(connection, at):
    ni_timestamp(at, canonical=True)
    for statement in DDL_V2:
        connection.execute(statement)
    connection.execute("PRAGMA user_version=2")
    connection.execute("INSERT INTO service_materialization_schema VALUES(1,2,1,?,?)", (ALGORITHM,at))
    connection.execute("INSERT INTO service_materialization_runtime(singleton_id,runtime_state,updated_at_utc) VALUES(1,'initializing',?)", (at,))
    create_visit_delivery_anchor(connection, at)


def create_visit_delivery_anchor(connection, at):
    import uuid
    from hashlib import sha256
    stream=str(uuid.uuid4()); initial=sha256(('ni04-visit-delivery-v1:'+stream).encode('ascii')).hexdigest()
    connection.execute("INSERT INTO ni04_visit_delivery_outbox(outbox_seq,stream_id,kind,created_at,previous_hash,entry_hash,head_seq,head_hash,floor_seq,floor_hash) VALUES(0,?,'anchor',?,?,?,0,?,0,?)",
        (stream,at,initial,initial,initial,initial))


def migrate_visit_delivery(connection, at):
    """Only the NI04 sole writer calls this inside its existing transaction."""
    validate_schema(connection, integrity=True)
    if connection.execute('PRAGMA user_version').fetchone()[0] != 1:
        raise MaterializationUnavailable()
    connection.execute('ALTER TABLE service_materialization_schema RENAME TO old_materialization_schema_v1')
    connection.execute(DDL_V2[0])
    connection.execute('INSERT INTO service_materialization_schema SELECT singleton_id,2,materialization_contract_version,algorithm_version,created_at_utc FROM old_materialization_schema_v1')
    connection.execute('DROP TABLE old_materialization_schema_v1')
    connection.execute(VISIT_OUTBOX_DDL);connection.execute(VISIT_OUTBOX_INDEX)
    create_visit_delivery_anchor(connection, at)
    connection.execute('PRAGMA user_version=2')
    validate_schema(connection, integrity=True)


def validate_schema(connection, *, integrity=False):
    try:
        version=connection.execute('PRAGMA user_version').fetchone()[0]
        if type(version) is not int or version not in (1,2) or signature(connection) != expected_signature(version):
            raise ValueError
        if connection.execute("PRAGMA foreign_keys").fetchone()[0] != 1:
            raise ValueError
        if connection.execute("PRAGMA journal_mode").fetchone()[0].lower() != "wal":
            raise ValueError
        rows = connection.execute("SELECT * FROM service_materialization_schema").fetchall()
        if len(rows) != 1 or tuple(rows[0][:4]) != (1,version,1,ALGORITHM):
            raise ValueError
        ni_timestamp(rows[0][4],canonical=True)
        runtime=connection.execute("SELECT active_generation_id,updated_at_utc FROM service_materialization_runtime").fetchall()
        if len(runtime)!=1:
            raise ValueError
        ni_timestamp(runtime[0][1],canonical=True)
        active=connection.execute("SELECT generation_id FROM service_materialization_generations WHERE state='active' LIMIT 2").fetchall()
        if len(active)>1 or runtime[0][0]!=(active[0][0] if active else None):
            raise ValueError
        if version==2:
            anchor=connection.execute("SELECT stream_id,head_seq,head_hash,floor_seq,floor_hash FROM ni04_visit_delivery_outbox WHERE outbox_seq=0 AND kind='anchor'").fetchone()
            if anchor is None or not 0<=anchor[3]<=anchor[1]:raise ValueError
            from app.network_metadata.validation import canonical_uuid,digest
            canonical_uuid(anchor[0]);digest(anchor[2]);digest(anchor[4])
        if integrity and (tuple(row[0] for row in connection.execute("PRAGMA quick_check")) != ("ok",)
                or connection.execute("PRAGMA foreign_key_check").fetchone() is not None):
            raise ValueError
    except Exception:
        raise MaterializationUnavailable() from None
