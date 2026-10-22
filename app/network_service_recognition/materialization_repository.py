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
from app.network_metadata.models import NetworkMetadataValidationError
from app.network_attribution.validation import canonical_mac
from app.device_fingerprint.validation import validate_site_id
from .artifacts import RecognitionBundle,AdmittedArtifact
from .materialization_schema import create_schema,validate_schema,migrate_visit_delivery,MaterializationUnavailable
from .canonical import canonical_json

HEADROOM = 4 * 1024 * 1024
VISIT_DELIVERY_FIELDS = ('outbox_seq','stream_id','kind','site_id','device_id','client_mac','edge_id','service_id',
    'observed_at','source_ref','generation_id','source_observation_id','binding_seq','taxonomy_id','taxonomy_version',
    'taxonomy_digest','ruleset_id','ruleset_version','ruleset_digest','rule_id','service_label','organization_id',
    'organization_label','category_id','created_at','previous_hash')


def visit_delivery_hash(row):
    return sha256(canonical_json({k:row[k] for k in VISIT_DELIVERY_FIELDS})).hexdigest()


def validate_visit_delivery(row):
    """Closed, bounded provenance only; never accepts raw endpoint payload."""
    import re
    if set(row)!=set(VISIT_DELIVERY_FIELDS):raise MaterializationConflict()
    integer(row['outbox_seq'],1);canonical_uuid(row['stream_id']);digest(row['previous_hash'])
    ni_timestamp(row['created_at'],canonical=True)
    common={'outbox_seq','stream_id','kind','created_at','previous_hash'}
    if row['kind']=='positive':
        required=set(VISIT_DELIVERY_FIELDS)-common
        validate_site_id(row['site_id']);canonical_uuid(row['device_id'])
        if canonical_mac(row['client_mac'])!=row['client_mac']:raise MaterializationConflict()
        digest(row['edge_id']);digest(row['source_observation_id']);canonical_uuid(row['source_ref'],5)
        ni_timestamp(row['observed_at'],canonical=True);canonical_uuid(row['generation_id'])
        integer(row['binding_seq'],1);integer(row['taxonomy_version'],1);integer(row['ruleset_version'],1)
        digest(row['taxonomy_digest']);digest(row['ruleset_digest'])
        for key in ('service_id','taxonomy_id','ruleset_id','rule_id','organization_id','category_id'):
            if not isinstance(row[key],str) or len(row[key])>128 or re.fullmatch(r'[A-Za-z0-9_.:-]+',row[key]) is None:raise MaterializationConflict()
        for key in ('service_label','organization_label'):
            if not isinstance(row[key],str) or not 1<=len(row[key])<=128 or any(ord(c)<32 for c in row[key]):raise MaterializationConflict()
    elif row['kind']=='binding':
        required={'site_id','device_id','client_mac','binding_seq'}
        validate_site_id(row['site_id']);canonical_uuid(row['device_id']);integer(row['binding_seq'],1)
        if canonical_mac(row['client_mac'])!=row['client_mac']:raise MaterializationConflict()
    elif row['kind']=='generation':
        required={'generation_id'};canonical_uuid(row['generation_id'])
    else:raise MaterializationConflict()
    if any(row[k] is not None for k in set(row)-common-required):raise MaterializationConflict()


@contextmanager
def _visit_readonly(path, deadline=None):
    if deadline is not None:deadline.require_remaining()
    connection=sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro',uri=True,isolation_level=None,timeout=0)
    connection.row_factory=sqlite3.Row
    try:
        connection.execute('PRAGMA query_only=ON');connection.execute('PRAGMA foreign_keys=ON');connection.execute('BEGIN')
        if deadline is not None:connection.set_progress_handler(lambda:int(deadline.expired()),100)
        yield connection
        if deadline is not None:deadline.require_remaining()
    finally:
        connection.set_progress_handler(None,0)
        connection.rollback();connection.close()


def read_visit_delivery_page(path, cursor, *, deadline):
    """One bounded RO snapshot, released before ANY Visit write transaction."""
    with _visit_readonly(path,deadline) as c:
        validate_schema(c)
        if c.execute('PRAGMA user_version').fetchone()[0]!=2:raise MaterializationUnavailable()
        anchor=dict(c.execute('SELECT * FROM ni04_visit_delivery_outbox WHERE outbox_seq=0').fetchone())
        if cursor is None:
            if anchor['floor_seq']!=0:raise MaterializationConflict()
            seq,hashed=0,anchor['floor_hash']
        else:
            seq,hashed=cursor['last_outbox_seq'],cursor['last_outbox_hash']
            integer(seq);digest(hashed);canonical_uuid(cursor['consumer_id'])
            if cursor['source_stream_id']!=anchor['stream_id'] or anchor['consumer_id'] not in (None,cursor['consumer_id']):raise MaterializationConflict()
            if not anchor['floor_seq']<=seq<=anchor['head_seq']:raise MaterializationConflict()
            row=c.execute('SELECT entry_hash FROM ni04_visit_delivery_outbox WHERE outbox_seq=?',(seq,)).fetchone() if seq!=anchor['floor_seq'] else None
            expected=anchor['floor_hash'] if seq==anchor['floor_seq'] else row[0] if row else None
            if expected!=hashed:raise MaterializationConflict()
        entries=[];previous=hashed
        for raw in c.execute('SELECT * FROM ni04_visit_delivery_outbox WHERE outbox_seq>? ORDER BY outbox_seq LIMIT 25',(seq,)).fetchall():
            row={k:raw[k] for k in VISIT_DELIVERY_FIELDS}
            validate_visit_delivery(row)
            if row['stream_id']!=anchor['stream_id'] or row['outbox_seq']!=seq+len(entries)+1 or row['previous_hash']!=previous or visit_delivery_hash(row)!=raw['entry_hash']:raise MaterializationConflict()
            row['entry_hash']=raw['entry_hash'];entries.append(row);previous=raw['entry_hash']
        if seq<anchor['head_seq'] and not entries:raise MaterializationConflict()
        if entries and entries[-1]['outbox_seq']==anchor['head_seq'] and previous!=anchor['head_hash']:raise MaterializationConflict()
        runtime=c.execute('SELECT active_generation_id,runtime_state,updated_at_utc FROM service_materialization_runtime WHERE singleton_id=1').fetchone()
        return dict(stream_id=anchor['stream_id'],floor_seq=anchor['floor_seq'],floor_hash=anchor['floor_hash'],
            head_seq=anchor['head_seq'],head_hash=anchor['head_hash'],after_seq=seq,after_hash=hashed,
            active_generation=runtime[0],source_state=runtime[1],source_updated_at=runtime[2],entries=tuple(entries))


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
                 clock=lambda: datetime.now(timezone.utc),crash_point=lambda _:None,
                 visit_delivery_db_path=None):
        if type(db_path) is not str or not Path(db_path).is_absolute() or type(max_db_bytes) is not int or not 128*1024*1024 <= max_db_bytes <= 2*1024**3:
            raise MaterializationUnavailable()
        self.db_path,self.max_db_bytes,self.clock,self.crash_point=db_path,max_db_bytes,clock,crash_point
        self.connection=self._writer_fd=None
        self._retention=False
        self.live_state="initializing"
        if visit_delivery_db_path is not None and (type(visit_delivery_db_path) is not str or not Path(visit_delivery_db_path).is_absolute()):
            raise MaterializationUnavailable()
        # No history publication/pruning until both applications are explicitly
        # configured for Visit history. Parent Visit owns lifetime; no age TTL.
        self.visit_delivery_db_path=visit_delivery_db_path

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
            elif self.connection.execute('PRAGMA user_version').fetchone()[0]==1:
                with self.transaction():
                    migrate_visit_delivery(self.connection,ni_format_utc(self.clock()))
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
        # Read/close the Visit checkpoint BEFORE acquiring the NI04 write lock.
        acknowledgement=self._visit_acknowledgement()
        # Every pass is bounded; no VACUUM or deletion of current positives.
        with self.transaction(retention=True):
            self._prune_visit_delivery(acknowledgement)
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

    def append_visit_delivery(self, kind, at, **fields):
        if self.visit_delivery_db_path is None:return False
        if not self.connection.in_transaction:raise MaterializationConflict()
        if kind not in {'positive','binding','generation'} or set(fields)-set(VISIT_DELIVERY_FIELDS):raise MaterializationConflict()
        ni_timestamp(at,canonical=True)
        anchor=self.connection.execute('SELECT * FROM ni04_visit_delivery_outbox WHERE outbox_seq=0').fetchone()
        if anchor['head_seq']-anchor['floor_seq']>=100000:raise MaterializationCapacity()
        row={k:None for k in VISIT_DELIVERY_FIELDS}
        row.update(fields,outbox_seq=anchor['head_seq']+1,stream_id=anchor['stream_id'],kind=kind,
            created_at=at,previous_hash=anchor['head_hash'])
        validate_visit_delivery(row)
        row['entry_hash']=visit_delivery_hash(row)
        self.connection.execute('INSERT INTO ni04_visit_delivery_outbox('+','.join(row)+') VALUES('+','.join('?' for _ in row)+')',tuple(row.values()))
        self.connection.execute('UPDATE ni04_visit_delivery_outbox SET head_seq=?,head_hash=? WHERE outbox_seq=0',
            (row['outbox_seq'],row['entry_hash']))
        self.crash_point('visit_delivery_appended')
        return True

    def _visit_acknowledgement(self):
        if self.visit_delivery_db_path is None:return None
        try:
            with _visit_readonly(self.visit_delivery_db_path) as c:
                from app.visit_lifecycle.repository import expected_visit_signature,_schema_signature
                if c.execute('PRAGMA user_version').fetchone()[0]!=6 or _schema_signature(c)!=expected_visit_signature(6):return None
                # Partial integrity check of this one-row checkpoint B-tree,
                # not a full Visit history scan on every retention tick.
                if c.execute("PRAGMA quick_check('visit_service_consumer_state')").fetchone()[0]!='ok':return None
                row=c.execute('SELECT consumer_id,source_stream_id,last_outbox_seq,last_outbox_hash FROM visit_service_consumer_state WHERE singleton_id=1').fetchone()
                return None if row is None else dict(row)
        except Exception:
            return None  # Unknown/unavailable/rollback checkpoint never prunes.

    def _prune_visit_delivery(self, ack):
        if ack is None:return
        try:
            if self.connection.execute('PRAGMA user_version').fetchone()[0]!=2:return
            canonical_uuid(ack['consumer_id']);canonical_uuid(ack['source_stream_id']);integer(ack['last_outbox_seq']);digest(ack['last_outbox_hash'])
            anchor=self.connection.execute('SELECT * FROM ni04_visit_delivery_outbox WHERE outbox_seq=0').fetchone()
            seq=ack['last_outbox_seq']
            if (anchor['stream_id']!=ack['source_stream_id'] or anchor['consumer_id'] not in (None,ack['consumer_id'])
                    or not anchor['floor_seq']<=seq<=anchor['head_seq']):return
            expected=anchor['floor_hash'] if seq==anchor['floor_seq'] else self.connection.execute('SELECT entry_hash FROM ni04_visit_delivery_outbox WHERE outbox_seq=?',(seq,)).fetchone()
            expected=expected if isinstance(expected,str) else expected[0] if expected else None
            if expected!=ack['last_outbox_hash']:return
            rows=self.connection.execute('SELECT outbox_seq,entry_hash FROM ni04_visit_delivery_outbox WHERE outbox_seq>0 AND outbox_seq<=? ORDER BY outbox_seq LIMIT 256',(seq,)).fetchall()
            if not rows:return
            end,hashed=rows[-1]
            self.connection.execute('DELETE FROM ni04_visit_delivery_outbox WHERE outbox_seq>0 AND outbox_seq<=?',(end,))
            self.connection.execute('UPDATE ni04_visit_delivery_outbox SET floor_seq=?,floor_hash=?,consumer_id=? WHERE outbox_seq=0',(end,hashed,ack['consumer_id']))
            self.crash_point('visit_delivery_pruned')
        except (ValueError,KeyError,TypeError,NetworkMetadataValidationError):
            return

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
            self.append_visit_delivery('generation',at,generation_id=gen)
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
            if old is None:
                if observation.support_state!='directly_supported' or observation.evidence_strength_class!='strong' or values['source_event_family'] not in {'tls','quic'}:
                    raise MaterializationConflict()
                self.append_visit_delivery('positive',at,site_id=ident.site_id,device_id=ident.device_id,client_mac=ident.client_mac,
                    edge_id=ref.edge_id,service_id=observation.service_id,observed_at=observation.observed_at,
                    source_ref=ref.source_observation_ref,generation_id=gen,source_observation_id=observation.service_observation_id,
                    binding_seq=ident.registry_binding_change_seq,taxonomy_id=bundle.taxonomy['taxonomy_id'],
                    taxonomy_version=bundle.taxonomy['taxonomy_version'],taxonomy_digest=bundle.taxonomy['taxonomy_digest_sha256'],
                    ruleset_id=bundle.ruleset['ruleset_id'],ruleset_version=bundle.ruleset['ruleset_version'],ruleset_digest=bundle.ruleset['ruleset_digest_sha256'],
                    rule_id=evaluation.matched_rule_id,service_label=service['display_name'],organization_id=observation.organization_id,
                    organization_label=org['display_name'],category_id=observation.service_category_id)
            rollup=(gen,ident.site_id,ident.device_id,ident.client_mac,observation.service_id,service["display_name"],observation.organization_id,org["display_name"],observation.service_category_id,cat["display_name"],observation.observed_at,observation.service_observation_id)
            old_rollup=self.connection.execute("SELECT client_mac FROM device_service_rollups WHERE generation_id=? AND site_id=? AND device_id=? AND service_id=?",(gen,ident.site_id,ident.device_id,observation.service_id)).fetchone()
            if old_rollup and old_rollup[0]!=ident.client_mac:
                raise MaterializationConflict()
            self.connection.execute("INSERT INTO device_service_rollups VALUES(?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(generation_id,site_id,device_id,service_id) DO UPDATE SET last_observed_at=excluded.last_observed_at,last_service_observation_id=excluded.last_service_observation_id WHERE excluded.last_observed_at>device_service_rollups.last_observed_at",rollup)
        self.connection.execute("INSERT INTO device_materialization_state VALUES(?,?,?,?,'authoritative',?,'unknown','unknown',0,?,?,?, ?,?) ON CONFLICT(generation_id,site_id,device_id) DO UPDATE SET registry_binding_change_seq=excluded.registry_binding_change_seq,recognition_state=CASE WHEN excluded.last_recognition_limitation_at IS NOT NULL THEN 'limited' ELSE device_materialization_state.recognition_state END,last_recognition_limitation_at=CASE WHEN excluded.last_recognition_limitation_at IS NULL THEN device_materialization_state.last_recognition_limitation_at ELSE max(coalesce(device_materialization_state.last_recognition_limitation_at,''),excluded.last_recognition_limitation_at) END,last_materialized_at_utc=excluded.last_materialized_at_utc",
            (gen,ident.site_id,ident.device_id,ident.client_mac,ident.registry_binding_change_seq,"limited" if evaluation.limited else "usable",at,evaluation.coverage_valid_from_utc,evaluation.observed_at if evaluation.limited else None,at))
        self.crash_point("materialization_evaluated")
