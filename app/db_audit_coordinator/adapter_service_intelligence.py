"""NI-04 RAM T3 bridge. Persistent WAL check is done on SOURCE, not spoofed.

The canonical owner validator combines physical WAL and logical checks, so a
RAM connection cannot call it as if journal_mode were WAL. Reuse its exact DDL
signature and constants, repeat its singleton/lineage checks on RAM, then add
full integrity/FK and canonical immutable fact checks. No recognition replay.
"""
import hashlib

from . import contracts as c
from .live_policy import require


def validate(db, guard):
    from app.network_service_recognition.materialization_schema import signature,expected_signature,ALGORITHM
    from app.network_metadata.validation import canonical_uuid,digest,integer,ni_timestamp
    from app.network_attribution.validation import canonical_mac
    from app.device_fingerprint.validation import validate_site_id
    from app.network_service_recognition.artifacts import CATEGORIES,IDS,_id
    require(db.execute('PRAGMA user_version').fetchone()[0]==1 and signature(db)==expected_signature())
    rows=list(db.execute('SELECT * FROM service_materialization_schema'))
    require(len(rows)==1 and tuple(rows[0][:4])==(1,1,1,ALGORITHM)); ni_timestamp(rows[0][4],canonical=True)
    runtime=list(db.execute('SELECT * FROM service_materialization_runtime'))
    require(len(runtime)==1); ni_timestamp(runtime[0]['updated_at_utc'],canonical=True)
    active=list(db.execute("SELECT generation_id FROM service_materialization_generations WHERE state='active'"))
    require(len(active)<=1 and runtime[0]['active_generation_id']==(active[0][0] if active else None))
    lineage=hashlib.sha256(); watermark=hashlib.sha256()
    for row in db.execute('SELECT * FROM service_materialization_generations ORDER BY generation_id'):
        guard(); canonical_uuid(row['generation_id'])
        for kind in ('taxonomy','knowledge_manifest','ruleset'):
            require(row[kind+'_id']==IDS[kind])
            integer(row[kind+'_version'],1); digest(row[kind+'_digest_sha256'])
        integer(row['live_feed_start_seq'])
        for key in ('build_started_at_utc','backfill_from_utc','publishable_until_utc'):
            ni_timestamp(row[key],canonical=True)
        lineage.update(c.encode(tuple(row)))
    tables=(('service_recognition_observations','service_observation_id'),
        ('device_service_rollups','generation_id,site_id,device_id,service_id'),
        ('device_materialization_state','generation_id,site_id,device_id'),
        ('service_materialization_checkpoints','generation_id'),('service_binding_replay_jobs','job_id'))
    for table,order in tables:
        for row in db.execute(f'SELECT * FROM {table} ORDER BY {order}'):
            guard(); canonical_uuid(row['generation_id'])
            if 'site_id' in row.keys(): validate_site_id(row['site_id'])
            if 'client_mac' in row.keys(): require(canonical_mac(row['client_mac'])==row['client_mac'])
            if 'device_id' in row.keys(): canonical_uuid(row['device_id'])
            if 'registry_binding_change_seq' in row.keys(): integer(row['registry_binding_change_seq'],1)
            if table in {'service_recognition_observations','device_service_rollups'}:
                _id(row['service_id'],'service',58);_id(row['organization_id'],'org',62)
                require(row['service_category_id'] in CATEGORIES)
            for key in row.keys():
                if row[key] is not None and (key.endswith('_utc') or key in {'observed_at','last_observed_at',
                        'last_recognition_limitation_at','backfill_event_at','cursor_event_at'}):
                    ni_timestamp(row[key],canonical=True)
            if table=='service_recognition_observations':
                # Owner service_observation() uses SHA256; this is NOT a UUID.
                digest(row['service_observation_id']);digest(row['edge_id'])
                canonical_uuid(row['source_observation_ref'],5)
                _id(row['matched_rule_id'],'rule')
                require(row['evidence_strength_class']=='strong' and row['support_state']=='directly_supported')
            if table=='service_binding_replay_jobs':digest(row['job_id']);integer(row['binding_change_seq'],1)
            if table=='service_materialization_checkpoints':
                integer(row['last_edge_feed_seq']);integer(row['last_binding_change_seq'])
                for key in ('recovery_feed_highwater_seq','recovery_live_feed_seq'):
                    if row[key] is not None:integer(row[key])
            watermark.update(c.encode(tuple(row)))
    # FK proves existence, not that the referenced observation belongs to this
    # device/service. Reuse the owner's immutable rollup provenance contract.
    require(db.execute('''SELECT 1 FROM device_service_rollups r
        JOIN service_recognition_observations o ON o.generation_id=r.generation_id
          AND o.service_observation_id=r.last_service_observation_id
        WHERE r.site_id<>o.site_id OR r.device_id<>o.device_id OR r.client_mac<>o.client_mac
          OR r.service_id<>o.service_id OR r.organization_id<>o.organization_id
          OR r.service_category_id<>o.service_category_id OR r.last_observed_at<>o.observed_at LIMIT 1''').fetchone() is None)
    return 'native_lineage',lineage.hexdigest(),watermark.hexdigest()
