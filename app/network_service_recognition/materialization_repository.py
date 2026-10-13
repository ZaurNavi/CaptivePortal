"""Single NI-04 writer: checked immutable facts and atomic consumer progress."""
import os
import sqlite3
import uuid
from dataclasses import asdict
from hashlib import sha256
from contextlib import contextmanager
from datetime import datetime,timedelta,timezone
from pathlib import Path

from app.network_metadata.validation import canonical_uuid,digest,integer,ni_format_utc,ni_timestamp
from app.network_attribution.validation import canonical_mac
from app.device_fingerprint.validation import validate_site_id
from .artifacts import RecognitionBundle,AdmittedArtifact
from .materialization_schema import create_schema,validate_schema,MaterializationUnavailable
from .canonical import canonical_json

HEADROOM = 4 * 1024 * 1024


class MaterializationConflict(RuntimeError):
    def __init__(self):
        super().__init__("materialization_lineage_conflict")


class MaterializationCapacity(RuntimeError):
    def __init__(self):
        super().__init__("materialization_capacity_halted")


def bundle_identity(bundle):
    if type(bundle) is not RecognitionBundle or not all(type(v) is AdmittedArtifact for v in (bundle.taxonomy,bundle.manifest,bundle.ruleset)):
        raise MaterializationConflict()
    values = {}
    for kind,artifact in (("taxonomy",bundle.taxonomy),("knowledge_manifest",bundle.manifest),("ruleset",bundle.ruleset)):
        for suffix in ("_id","_version","_digest_sha256"):
            key = kind + suffix
            values[key] = artifact[key]
        if kind != "ruleset" and any(bundle.ruleset[kind+s] != artifact[kind+s] for s in ("_id","_version","_digest_sha256")):
            raise MaterializationConflict()
    return values


class ServiceMaterializationRepository:
    def __init__(self, db_path, *, max_db_bytes=512*1024*1024,
                 clock=lambda: datetime.now(timezone.utc),crash_point=lambda _:None):
        if type(db_path) is not str or not Path(db_path).is_absolute() or type(max_db_bytes) is not int or not 128*1024*1024 <= max_db_bytes <= 2*1024**3:
            raise MaterializationUnavailable()
        self.db_path,self.max_db_bytes,self.clock,self.crash_point=db_path,max_db_bytes,clock,crash_point
        self.connection=self._writer_fd=None
        self._retention=False
        self.live_state="initializing"

    def footprint(self):
        try:
            return sum(path.stat().st_size for suffix in ("","-wal","-shm","-journal")
                       if (path:=Path(self.db_path+suffix)).exists())
        except OSError:
            raise MaterializationUnavailable() from None

    def initialize(self):
        try:
            self._writer_fd=os.open(self.db_path+".writer.lock",os.O_CREAT|os.O_RDWR,0o640)
            if os.name=="nt":
                import msvcrt
                msvcrt.locking(self._writer_fd,msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(self._writer_fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
            path=Path(self.db_path)
            if path.exists() and path.stat().st_size:
                probe=sqlite3.connect(path.resolve().as_uri()+"?mode=ro",uri=True,timeout=.5)
                try:
                    probe.execute("PRAGMA foreign_keys=ON")
                    validate_schema(probe,integrity=True)
                finally:
                    probe.close()
            self.connection=sqlite3.connect(self.db_path,isolation_level=None,timeout=.5)
            self.connection.row_factory=sqlite3.Row
            self.connection.create_function("service_retention_authorized",0,lambda:int(self._retention))
            for pragma in ("foreign_keys=ON","journal_mode=WAL","synchronous=FULL","busy_timeout=500","wal_autocheckpoint=1000"):
                self.connection.execute("PRAGMA "+pragma)
            if self.connection.execute("SELECT count(*) FROM sqlite_schema").fetchone()[0]==0 and self.connection.execute("PRAGMA user_version").fetchone()[0]==0:
                with self.transaction():
                    create_schema(self.connection,ni_format_utc(self.clock()))
            validate_schema(self.connection,integrity=True)
            self.live_state=self.connection.execute("SELECT runtime_state FROM service_materialization_runtime").fetchone()[0]
            return self
        except BaseException:
            self.close()
            raise

    def close(self):
        if self.connection is not None:
            self.connection.close()
            self.connection=None
        if self._writer_fd is not None:
            os.close(self._writer_fd)
            self._writer_fd=None

    @contextmanager
    def transaction(self, *, retention=False):
        if self.connection is None or self.connection.in_transaction:
            raise MaterializationUnavailable()
        if not retention and self.footprint()+HEADROOM>self.max_db_bytes:
            self.maintain_capacity()
        self.connection.execute("BEGIN IMMEDIATE")
        self._retention=retention
        try:
            yield
            if not retention and self.footprint()+HEADROOM>self.max_db_bytes:
                raise MaterializationCapacity()
            self.crash_point("before_commit")
            self.connection.execute("COMMIT")
            self.crash_point("after_commit")
        except BaseException:
            if self.connection.in_transaction:
                self.connection.execute("ROLLBACK")
            raise
        finally:
            self._retention=False

    def maintain_capacity(self):
        self.retain()
        self.connection.execute("PRAGMA wal_checkpoint(PASSIVE)")
        if self.footprint()+HEADROOM>self.max_db_bytes:
            self.live_state="capacity_halted"
            raise MaterializationCapacity()

    def retain(self):
        at=self.clock()
        cutoff=ni_format_utc(at-timedelta(days=14))
        grace=ni_format_utc(at-timedelta(days=1))
        # Every pass is bounded; no VACUUM or deletion of current positives.
        with self.transaction(retention=True):
            self.connection.execute("DELETE FROM device_service_rollups WHERE rowid IN (SELECT rowid FROM device_service_rollups WHERE last_observed_at<? ORDER BY last_observed_at LIMIT 256)",(cutoff,))
            self.connection.execute("DELETE FROM service_recognition_observations WHERE rowid IN (SELECT o.rowid FROM service_recognition_observations o WHERE observed_at<? AND NOT EXISTS (SELECT 1 FROM device_service_rollups r WHERE r.generation_id=o.generation_id AND r.last_service_observation_id=o.service_observation_id) ORDER BY observed_at LIMIT 256)",(cutoff,))
            latest=self.connection.execute("SELECT generation_id FROM service_materialization_generations WHERE state='superseded' ORDER BY superseded_at_utc DESC,generation_id LIMIT 1").fetchone()
            obsolete=self.connection.execute("SELECT generation_id FROM service_materialization_generations WHERE state IN ('superseded','expired','failed') AND generation_id<>coalesce((SELECT active_generation_id FROM service_materialization_runtime), '') AND (coalesce(superseded_at_utc,build_started_at_utc)<? OR generation_id<>?) LIMIT 1",(grace,latest[0] if latest else "")).fetchone()
            if obsolete:
                gen=obsolete[0]
                # Bounded cascade preparation, never unbounded generation delete.
                self.connection.execute("DELETE FROM device_service_rollups WHERE rowid IN (SELECT rowid FROM device_service_rollups WHERE generation_id=? LIMIT 256)",(gen,))
                self.connection.execute("DELETE FROM service_recognition_observations WHERE rowid IN (SELECT o.rowid FROM service_recognition_observations o WHERE generation_id=? AND NOT EXISTS(SELECT 1 FROM device_service_rollups r WHERE r.generation_id=o.generation_id AND r.last_service_observation_id=o.service_observation_id) LIMIT 256)",(gen,))
                for table in ("device_materialization_state","service_binding_replay_jobs"):
                    self.connection.execute(f"DELETE FROM {table} WHERE rowid IN (SELECT rowid FROM {table} WHERE generation_id=? LIMIT 256)",(gen,))
                if not any(self.connection.execute(f"SELECT 1 FROM {table} WHERE generation_id=? LIMIT 1",(gen,)).fetchone() for table in ("device_service_rollups","service_recognition_observations","device_materialization_state","service_binding_replay_jobs")):
                    self.connection.execute("DELETE FROM service_materialization_generations WHERE generation_id=?",(gen,))
            self.connection.execute("DELETE FROM service_binding_replay_jobs WHERE rowid IN (SELECT rowid FROM service_binding_replay_jobs WHERE state IN ('complete','terminal') AND to_utc<? LIMIT 128)",(grace,))

    def ensure_generation(self,bundle,highwater,at):
        integer(highwater)
        now=ni_timestamp(at,canonical=True)
        identity=bundle_identity(bundle)
        # Tuple identity is stable across restarts; it is not a publication timestamp.
        gen=str(uuid.uuid5(uuid.NAMESPACE_URL,"ni04-materialization:"+":".join(identity[k] for k in ("taxonomy_digest_sha256","knowledge_manifest_digest_sha256","ruleset_digest_sha256"))))
        existing=self.connection.execute("SELECT * FROM service_materialization_generations WHERE generation_id=?",(gen,)).fetchone()
        if existing:
            if any(existing[k]!=v for k,v in identity.items()):
                raise MaterializationConflict()
            return gen
        # Eligibility boundary is the conservative common boundary of active rules.
        intervals=[bundle.manifest.index[r["rule_id"]] for r in bundle.ruleset["rules"] if r["lifecycle_state"]=="active" and "_sni_" in r["rule_kind"]]
        if not intervals or any(not first<=now<last for first,last in intervals):
            raise MaterializationConflict()
        until=ni_format_utc(min(last for _,last in intervals))
        first=ni_format_utc(now-timedelta(days=1))
        with self.transaction():
            for kind in ("taxonomy","knowledge_manifest","ruleset"):
                row=self.connection.execute(f"SELECT {kind}_digest_sha256 FROM service_materialization_generations WHERE {kind}_id=? AND {kind}_version=? LIMIT 1",(identity[kind+"_id"],identity[kind+"_version"])).fetchone()
                if row and row[0]!=identity[kind+"_digest_sha256"]:
                    raise MaterializationConflict()
            building=self.connection.execute("SELECT 1 FROM service_materialization_generations WHERE state='building' LIMIT 1").fetchone()
            if building:
                raise MaterializationConflict()
            cols=("generation_id","state",*identity,"build_started_at_utc","backfill_from_utc","live_feed_start_seq","publishable_until_utc")
            self.connection.execute(f"INSERT INTO service_materialization_generations({','.join(cols)}) VALUES({','.join('?' for _ in cols)})",(gen,"building",*identity.values(),at,first,highwater,until))
            self.connection.execute("INSERT INTO service_materialization_checkpoints(generation_id,last_edge_feed_seq,last_binding_change_seq,backfill_state,backfill_from_utc,updated_at_utc) VALUES(?,?,0,'not_started',?,?)",(gen,highwater,first,at))
        return gen

    def checkpoint(self,gen):
        canonical_uuid(gen)
        row=self.connection.execute("SELECT * FROM service_materialization_checkpoints WHERE generation_id=?",(gen,)).fetchone()
        if row is None:
            raise MaterializationConflict()
        return row

    def runtime(self,state,at, *, highwater=None,cursor=None,poll=None,commit=None,reconcile=None):
        allowed={"initializing","backfilling","usable","lagging","source_unavailable","recognition_unavailable","capacity_halted","blocked_conflict","stopping"}
        if state not in allowed:
            raise MaterializationConflict()
        ni_timestamp(at,canonical=True)
        for value in (highwater,cursor):
            if value is not None: integer(value)
        for value in (poll,commit,reconcile):
            if value is not None: ni_timestamp(value,canonical=True)
        self.connection.execute("UPDATE service_materialization_runtime SET runtime_state=?,safe_reason=?,observed_feed_highwater_seq=coalesce(?,observed_feed_highwater_seq),committed_feed_cursor_seq=coalesce(?,committed_feed_cursor_seq),last_upstream_poll_at_utc=coalesce(?,last_upstream_poll_at_utc),last_successful_commit_at_utc=coalesce(?,last_successful_commit_at_utc),last_coverage_reconcile_at_utc=coalesce(?,last_coverage_reconcile_at_utc),updated_at_utc=? WHERE singleton_id=1",(state,None if state=="usable" else state,highwater,cursor,poll,commit,reconcile,at))
        self.live_state=state

    def promote(self,gen,at,highwater):
        ni_timestamp(at,canonical=True)
        integer(highwater)
        with self.transaction():
            candidate=self.connection.execute("SELECT * FROM service_materialization_generations WHERE generation_id=?",(gen,)).fetchone()
            cp=self.checkpoint(gen)
            if candidate is None or candidate["state"]!="building" or candidate["publishable_until_utc"]<=at or cp["backfill_state"]!="complete" or cp["recovery_feed_highwater_seq"] is not None or cp["last_edge_feed_seq"]!=highwater or self.connection.execute("SELECT 1 FROM service_binding_replay_jobs WHERE generation_id=? AND state IN ('pending','running') LIMIT 1",(gen,)).fetchone():
                raise MaterializationConflict()
            validate_schema(self.connection,integrity=True)
            self.connection.execute("UPDATE service_materialization_generations SET state='superseded',superseded_at_utc=? WHERE state='active'",(at,))
            self.connection.execute("UPDATE service_materialization_generations SET state='active',activated_at_utc=? WHERE generation_id=?",(at,gen))
            self.connection.execute("UPDATE service_materialization_runtime SET active_generation_id=? WHERE singleton_id=1",(gen,))
            self.runtime("usable",at,highwater=highwater,cursor=highwater,poll=at,commit=at)

    def put_evaluated(self,gen,evaluation,bundle,at):
        """Caller owns atomic batch. Evaluation contains no persisted raw evidence."""
        if not self.connection.in_transaction:
            raise MaterializationConflict()
        generation=self.connection.execute('SELECT * FROM service_materialization_generations WHERE generation_id=?',(gen,)).fetchone()
        if generation is None or generation['state'] not in {'building','active'} or generation['publishable_until_utc']<=at or any(generation[k]!=v for k,v in bundle_identity(bundle).items()):
            raise MaterializationConflict()
        ident=evaluation.identity
        validate_site_id(ident.site_id)
        canonical_uuid(ident.device_id)
        if ident.binding_state!="authoritative" or canonical_mac(ident.client_mac)!=ident.client_mac:
            raise MaterializationConflict()
        integer(ident.registry_binding_change_seq,1)
        state=self.connection.execute("SELECT * FROM device_materialization_state WHERE generation_id=? AND site_id=? AND device_id=?",(gen,ident.site_id,ident.device_id)).fetchone()
        if state and state["client_mac"]!=ident.client_mac:
            raise MaterializationConflict()
        observation=evaluation.observation
        if observation is not None and observation.resolution_state=="service_resolved":
            if observation.site_id!=ident.site_id or observation.device_id!=ident.device_id or len(observation.evidence_refs)!=1 or evaluation.matched_rule_id is None:
                raise MaterializationConflict()
            ref=observation.evidence_refs[0]
            digest(observation.service_observation_id)
            encoded=asdict(observation)
            encoded.pop('service_observation_id');encoded.pop('resolution_state')
            if sha256(canonical_json(encoded)).hexdigest()!=observation.service_observation_id:
                raise MaterializationConflict()
            for kind,parent in (('recognition_ruleset',bundle.ruleset),('taxonomy',bundle.taxonomy)):
                original='ruleset' if kind=='recognition_ruleset' else kind
                if any(getattr(observation,kind+s)!=parent[original+s] for s in ('_id','_version','_digest_sha256')):
                    raise MaterializationConflict()
            rule=next((r for r in bundle.ruleset['rules'] if r['rule_id']==evaluation.matched_rule_id),None)
            if (rule is None or rule['target_type']!='service' or rule['target_id']!=observation.service_id
                    or rule['lifecycle_state']!='active' or rule['rule_kind'] not in {'service_sni_exact','service_sni_suffix'}):
                raise MaterializationConflict()
            reviewed,due=bundle.manifest.index[rule['rule_id']]
            if not reviewed<=ni_timestamp(at,canonical=True)<due:raise MaterializationConflict()
            digest(ref.edge_id);canonical_uuid(ref.source_observation_ref,5)
            values=dict(service_observation_id=observation.service_observation_id,generation_id=gen,edge_id=ref.edge_id,source_observation_ref=ref.source_observation_ref,
                site_id=ident.site_id,device_id=ident.device_id,client_mac=ident.client_mac,registry_binding_change_seq=ident.registry_binding_change_seq,
                observed_at=observation.observed_at,source_event_family=ref.signal_type.removesuffix("_sni"),service_id=observation.service_id,organization_id=observation.organization_id,
                service_category_id=observation.service_category_id,evidence_strength_class=observation.evidence_strength_class,support_state=observation.support_state,
                matched_rule_id=evaluation.matched_rule_id,materialized_at_utc=at)
            old=self.connection.execute("SELECT * FROM service_recognition_observations WHERE generation_id=? AND (edge_id=? OR service_observation_id=?)",(gen,ref.edge_id,observation.service_observation_id)).fetchone()
            if old:
                # Later authoritative revalidation must not rewrite fact provenance.
                if any(old[k]!=v for k,v in values.items() if k not in {"materialized_at_utc","registry_binding_change_seq"}):
                    raise MaterializationConflict()
            else:
                self.connection.execute(f"INSERT INTO service_recognition_observations({','.join(values)}) VALUES({','.join('?' for _ in values)})",tuple(values.values()))
            service=bundle.taxonomy.index["services"][observation.service_id]
            org=next(x for x in bundle.taxonomy["organizations"] if x["organization_id"]==observation.organization_id)
            cat=next(x for x in bundle.taxonomy["service_categories"] if x["service_category_id"]==observation.service_category_id)
            rollup=(gen,ident.site_id,ident.device_id,ident.client_mac,observation.service_id,service["display_name"],observation.organization_id,org["display_name"],observation.service_category_id,cat["display_name"],observation.observed_at,observation.service_observation_id)
            old_rollup=self.connection.execute("SELECT client_mac FROM device_service_rollups WHERE generation_id=? AND site_id=? AND device_id=? AND service_id=?",(gen,ident.site_id,ident.device_id,observation.service_id)).fetchone()
            if old_rollup and old_rollup[0]!=ident.client_mac:
                raise MaterializationConflict()
            self.connection.execute("INSERT INTO device_service_rollups VALUES(?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(generation_id,site_id,device_id,service_id) DO UPDATE SET last_observed_at=excluded.last_observed_at,last_service_observation_id=excluded.last_service_observation_id WHERE excluded.last_observed_at>device_service_rollups.last_observed_at",rollup)
        self.connection.execute("INSERT INTO device_materialization_state VALUES(?,?,?,?,'authoritative',?,'unknown','unknown',0,?,?,?, ?,?) ON CONFLICT(generation_id,site_id,device_id) DO UPDATE SET registry_binding_change_seq=excluded.registry_binding_change_seq,recognition_state=CASE WHEN excluded.last_recognition_limitation_at IS NOT NULL THEN 'limited' ELSE device_materialization_state.recognition_state END,last_recognition_limitation_at=CASE WHEN excluded.last_recognition_limitation_at IS NULL THEN device_materialization_state.last_recognition_limitation_at ELSE max(coalesce(device_materialization_state.last_recognition_limitation_at,''),excluded.last_recognition_limitation_at) END,last_materialized_at_utc=excluded.last_materialized_at_utc",
            (gen,ident.site_id,ident.device_id,ident.client_mac,ident.registry_binding_change_seq,"limited" if evaluation.limited else "usable",at,evaluation.coverage_valid_from_utc,evaluation.observed_at if evaluation.limited else None,at))
        self.crash_point("materialization_evaluated")
