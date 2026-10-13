"""One bounded background lane; no Admin, Portal, Auth or upstream writer."""
import sqlite3
import threading
import time
from datetime import datetime,timedelta,timezone

from app.analytics.source_gateway import QueryDeadline
from app.network_metadata.validation import ni_timestamp,ni_format_utc
from app.network_metadata.recognition_read_service import RecognitionSourceEvidenceV1
from app.network_metadata_projection.service_delivery_read_service import RecognitionCandidateV1,RecognitionFeedEntryV1,RecognitionFeedBoundsV1,RecognitionDeviceCoverageV1
from .evaluator import ServiceRecognitionEvaluatorV1
from .binding_replay import enqueue_binding_changes,read_targeted_replay_page,BindingReplayConflict
from .materialization_repository import MaterializationConflict,MaterializationCapacity
from .materialization_schema import MaterializationUnavailable
from .materialization_telemetry import MaterializationTelemetry
from .models import ServiceUnavailable,pipeline_coverage


class ServiceMaterializationWorker:
    def __init__(self,repository,projection_reader,source_reader,bundle, *, clock=lambda:datetime.now(timezone.utc),
                 monotonic=time.monotonic,telemetry=None):
        self.repository,self.projection,self.source,self.bundle=repository,projection_reader,source_reader,bundle
        self.clock,self.monotonic=clock,monotonic
        self.evaluator=ServiceRecognitionEvaluatorV1(bundle)
        self.telemetry=telemetry or MaterializationTelemetry()
        self.generation_id=None
        self._stop=threading.Event()
        self._last_heartbeat=self._last_coverage=self._last_backfill=self._last_retention=None
        self._cycle_lock=threading.Lock()
        self._failures=0

    def stop(self):self._stop.set()

    def _deadline(self):return QueryDeadline(self.monotonic()+30,self.monotonic)

    def _evidence(self,candidates,at,deadline, *, window_from_utc=None):
        # Entire batch's source and identity cross-check precedes ANY matcher.
        grouped={}
        for candidate in candidates:
            if type(candidate) is not RecognitionCandidateV1:raise MaterializationConflict()
            ident=candidate.identity
            if ident.binding_state=='authoritative':
                grouped.setdefault(ident.site_id,[]).append(candidate)
            elif ident.binding_state not in {'absent','registry_unavailable','not_yet_registry_resolved'} or ident.device_id is not None or ident.registry_binding_change_seq is not None:
                raise MaterializationConflict()
        evidence={}
        for site,rows in grouped.items():
            refs=tuple(sorted({c.fact.source_observation_ref for c in rows}))
            if len(refs)>256:raise MaterializationConflict()
            values=self.source.read_recognition_evidence(site,refs,deadline=deadline)
            if type(values) is not tuple or len(values)!=len(refs):raise ServiceUnavailable()
            seen=set()
            for value in values:
                if type(value) is not RecognitionSourceEvidenceV1 or value.observation_id not in refs or value.observation_id in seen:raise ServiceUnavailable()
                seen.add(value.observation_id)
                evidence[(site,value.observation_id)]=value
            for c in rows:
                self.evaluator.validate(c.fact,evidence[(site,c.fact.source_observation_ref)],c.identity,at,window_from_utc=window_from_utc)
        result=[]
        for site,rows in grouped.items():
            evaluated,_=self.evaluator.evaluate_batch(tuple((c.fact,c.identity) for c in rows),
                {ref:value for (s,ref),value in evidence.items() if s==site},at,deadline=deadline,window_from_utc=window_from_utc)
            result.extend(evaluated)
        # Current identity is re-read before committing immutable device facts.
        for ident in { (e.identity.site_id,e.identity.client_mac):e.identity for e in result }.values():
            current=self.projection.read_current_identity(ident.site_id,ident.client_mac,deadline=deadline)
            if current!=ident:raise MaterializationConflict()
        deadline.require_remaining()
        return tuple(result)

    def _coverage_rows(self,evaluated,at,deadline):
        ids={(e.identity.site_id,e.identity.device_id,e.identity.client_mac):e.identity for e in evaluated}
        # A 256-row live batch may touch >128 devices. Remaining devices get
        # honest unknown state and are picked up by bounded reconciliation.
        rows=[]
        first=ni_format_utc(ni_timestamp(at,canonical=True)-timedelta(days=1))
        for ident in tuple(ids.values())[:128]:
            previous=self.repository.connection.execute('SELECT coverage_evaluated_at_utc FROM device_materialization_state WHERE generation_id=? AND site_id=? AND device_id=?',(self.generation_id,ident.site_id,ident.device_id)).fetchone()
            if previous is not None and 0<=(ni_timestamp(at,canonical=True)-ni_timestamp(previous[0],canonical=True)).total_seconds()<30:
                continue
            value=self.projection.read_recognition_device_coverage(ident.site_id,ident.device_id,ident.client_mac,first,at,deadline=deadline)
            if type(value) is not RecognitionDeviceCoverageV1:raise MaterializationConflict()
            if value.identity_binding_state!='authoritative' or value.bound_device_id!=ident.device_id:raise MaterializationConflict()
            if type(value.device_linked_pending_count) is not int or value.device_linked_pending_count<0:raise MaterializationConflict()
            source,attribute=pipeline_coverage(value.projection_runtime_state,value.projection_safe_reason)
            rows.append((ident,source,attribute,bool(value.device_linked_pending_count)))
        return tuple(rows)

    def _put_coverage(self,rows,at):
        for identity,source,attribute,pending in rows:
            self.repository.connection.execute("UPDATE device_materialization_state SET source_state=?,pipeline_attribution_state=?,device_linked_pending=?,coverage_evaluated_at_utc=? WHERE generation_id=? AND site_id=? AND device_id=? AND client_mac=?",(source,attribute,int(pending),at,self.generation_id,identity.site_id,identity.device_id,identity.client_mac))

    def _put_batch(self,evaluated,coverage,at):
        for row in evaluated:self.repository.put_evaluated(self.generation_id,row,self.bundle,at)
        self._put_coverage(coverage,at)

    def _live(self,cp,bounds,at,deadline):
        recovering=cp['recovery_live_feed_seq'] is not None
        after=cp['recovery_live_feed_seq'] if recovering else cp['last_edge_feed_seq']
        high=bounds.max_feed_seq or 0
        if high<after:raise MaterializationConflict()
        # Sequence deletion is not processing. Stay fail-closed; initiate a
        # durable 24h recovery scan without advancing the live cursor.
        if high>after and (bounds.min_retained_feed_seq is None or bounds.min_retained_feed_seq>after+1):
            self._gap(cp,at,high)
            return False,'gap'
        entries=self.projection.read_service_recognition_feed(after,limit=256,deadline=deadline)
        if type(entries) is not tuple or len(entries)>256:raise MaterializationConflict()
        if any(type(e) is not RecognitionFeedEntryV1 for e in entries):raise MaterializationConflict()
        if any(e.feed_seq!=after+i+1 for i,e in enumerate(entries)):
            self._gap(cp,at,high)
            return False,'gap'
        if not entries:
            if high>after:
                self._gap(cp,at,high)
                return False,'gap'
            return False,None
        candidates=tuple(RecognitionCandidateV1(e.fact,e.identity) for e in entries)
        evaluated=self._evidence(candidates,at,deadline)
        coverage=self._coverage_rows(evaluated,at,deadline)
        end=entries[-1].feed_seq
        high=max(high,end)
        with self.repository.transaction():
            check=self.repository.checkpoint(self.generation_id)
            if (check['recovery_live_feed_seq'] if recovering else check['last_edge_feed_seq'])!=after:raise MaterializationConflict()
            self._put_batch(evaluated,coverage,at)
            column='recovery_live_feed_seq' if recovering else 'last_edge_feed_seq'
            self.repository.connection.execute(f'UPDATE service_materialization_checkpoints SET {column}=?,updated_at_utc=? WHERE generation_id=?',(end,at,self.generation_id))
            self.repository.runtime('lagging' if end<high else 'backfilling' if cp['backfill_state']!='complete' else 'usable',at,highwater=high,cursor=end,poll=at,commit=at)
            deadline.require_remaining()
        self.telemetry.emit(live_batches_total=1,feed_rows_examined_total=len(entries),candidate_edges_total=len(evaluated),service_positive_observations_total=sum(e.observation is not None and e.observation.resolution_state=='service_resolved' for e in evaluated))
        self._last_heartbeat=self.monotonic()
        return True,None

    def _gap(self,cp,at,high):
        # Existing completed coverage is withdrawn; committed positives survive.
        with self.repository.transaction():
            self.repository.connection.execute("UPDATE service_materialization_checkpoints SET backfill_state='running',backfill_from_utc=?,backfill_site_id=NULL,backfill_event_at=NULL,backfill_edge_id=NULL,recovery_feed_highwater_seq=?,recovery_live_feed_seq=?,recovery_cutoff_utc=?,last_feed_gap_at_utc=?,updated_at_utc=? WHERE generation_id=?",(ni_format_utc(ni_timestamp(at,canonical=True)-timedelta(days=1)),high,high,at,at,at,self.generation_id))
            self.repository.runtime('lagging',at)

    def _replay(self,at,deadline):
        cp=self.repository.checkpoint(self.generation_id)
        changes=self.projection.read_authoritative_binding_changes(cp['last_binding_change_seq'],limit=128,deadline=deadline)
        enqueue_binding_changes(self.repository,self.generation_id,cp['last_binding_change_seq'],changes,at)
        job=self.repository.connection.execute("SELECT * FROM service_binding_replay_jobs WHERE generation_id=? AND state IN ('pending','running') ORDER BY binding_change_seq LIMIT 1",(self.generation_id,)).fetchone()
        if job is None:return bool(changes)
        if job['to_utc']<=ni_format_utc(ni_timestamp(at,canonical=True)-timedelta(days=1)):
            with self.repository.transaction():self.repository.connection.execute("UPDATE service_binding_replay_jobs SET state='terminal' WHERE job_id=?",(job['job_id'],))
            return True
        current=self.projection.read_current_identity(job['site_id'],job['client_mac'],deadline=deadline)
        if current.binding_state!='authoritative' or current.device_id!=job['device_id']:
            with self.repository.transaction():self.repository.connection.execute("UPDATE service_binding_replay_jobs SET state='terminal' WHERE job_id=?",(job['job_id'],))
            return True
        page=read_targeted_replay_page(self.projection,job,deadline=deadline)
        if any(c.identity.device_id!=job['device_id'] or c.identity.site_id!=job['site_id'] or c.identity.client_mac!=job['client_mac'] for c in page):raise MaterializationConflict()
        evaluated=self._evidence(page,at,deadline,window_from_utc=job['from_utc'])
        coverage=self._coverage_rows(evaluated,at,deadline)
        with self.repository.transaction():
            self._put_batch(evaluated,coverage,at)
            cursor=(page[-1].fact.event_at,page[-1].fact.edge_id) if page else (job['cursor_event_at'],job['cursor_edge_id'])
            self.repository.connection.execute("UPDATE service_binding_replay_jobs SET state=?,cursor_event_at=?,cursor_edge_id=? WHERE job_id=?",('complete' if len(page)<128 else 'running',*cursor,job['job_id']))
            self.repository.runtime('backfilling' if cp['backfill_state']!='complete' else 'usable',at,commit=at)
            deadline.require_remaining()
        self.telemetry.emit(binding_replay_edges_total=len(page),binding_replay_jobs_total=len(changes))
        return True

    def _reconcile(self,at,deadline):
        tick=self.monotonic()
        if self._last_coverage is not None and tick-self._last_coverage<30:return False
        cutoff=ni_format_utc(ni_timestamp(at,canonical=True)-timedelta(seconds=30))
        due=self.repository.connection.execute('SELECT * FROM device_materialization_state WHERE generation_id=? AND coverage_evaluated_at_utc<=? ORDER BY coverage_evaluated_at_utc,site_id,device_id LIMIT 128',(self.generation_id,cutoff)).fetchall()
        if not due:
            self._last_coverage=tick
            return False
        from app.network_metadata_projection.service_delivery_read_service import RecognitionIdentityV1
        rows=[]
        for row in due:
            identity=self.projection.read_current_identity(row['site_id'],row['client_mac'],deadline=deadline)
            if identity.binding_state=='authoritative' and identity.device_id!=row['device_id']:raise MaterializationConflict()
            if identity.binding_state!='authoritative':
                rows.append((row,identity,None))
                continue
            value=self.projection.read_recognition_device_coverage(row['site_id'],row['device_id'],row['client_mac'],ni_format_utc(ni_timestamp(at,canonical=True)-timedelta(days=1)),at,deadline=deadline)
            if type(value) is not RecognitionDeviceCoverageV1 or type(value.device_linked_pending_count) is not int or value.device_linked_pending_count<0:raise MaterializationConflict()
            if value.identity_binding_state!='authoritative' or value.bound_device_id!=row['device_id']:raise MaterializationConflict()
            rows.append((row,identity,value))
        with self.repository.transaction():
            for row,identity,value in rows:
                state={'not_yet_registry_resolved':'pending','registry_unavailable':'unavailable','absent':'absent','authoritative':'authoritative'}[identity.binding_state]
                source,attribute=pipeline_coverage(value.projection_runtime_state,value.projection_safe_reason) if value is not None else ('unknown','unknown')
                pending=bool(value.device_linked_pending_count) if value else False
                self.repository.connection.execute('UPDATE device_materialization_state SET identity_binding_state=?,source_state=?,pipeline_attribution_state=?,device_linked_pending=?,coverage_evaluated_at_utc=? WHERE generation_id=? AND site_id=? AND device_id=?',(state,source,attribute,int(pending),at,self.generation_id,row['site_id'],row['device_id']))
            self.repository.runtime('backfilling' if self.repository.checkpoint(self.generation_id)['backfill_state']!='complete' else 'usable',at,reconcile=at,commit=at)
            deadline.require_remaining()
        self._last_coverage=tick
        self.telemetry.emit(coverage_reconciliations_total=len(rows))
        return True

    def _backfill(self,cp,at,deadline):
        if cp['backfill_state'] in {'complete','blocked'}:return False
        tick=self.monotonic()
        if self._last_backfill is not None and tick-self._last_backfill<1:return False
        gen=self.repository.connection.execute('SELECT * FROM service_materialization_generations WHERE generation_id=?',(self.generation_id,)).fetchone()
        site=cp['backfill_site_id']
        if site is None:
            sites=self.projection.read_candidate_sites(limit=1,deadline=deadline)
            site=sites[0] if sites else None
        cursor=(cp['backfill_event_at'],cp['backfill_edge_id']) if cp['backfill_event_at'] is not None else None
        page=self.projection.read_candidate_page(site,cp['backfill_from_utc'],cp['recovery_cutoff_utc'] or gen['build_started_at_utc'],cursor=cursor,limit=128,deadline=deadline) if site else ()
        if type(page) is not tuple or len(page)>128:raise MaterializationConflict()
        evaluated=self._evidence(page,at,deadline,window_from_utc=cp['backfill_from_utc'])
        coverage=self._coverage_rows(evaluated,at,deadline)
        complete=False
        if len(page)<128:
            next_sites=self.projection.read_candidate_sites(site,limit=1,deadline=deadline) if site else ()
            site=next_sites[0] if next_sites else None
            cursor=None
            complete=site is None
        elif page:cursor=(page[-1].fact.event_at,page[-1].fact.edge_id)
        with self.repository.transaction():
            self._put_batch(evaluated,coverage,at)
            self.repository.connection.execute('UPDATE service_materialization_checkpoints SET backfill_state=?,backfill_site_id=?,backfill_event_at=?,backfill_edge_id=?,updated_at_utc=? WHERE generation_id=?',('complete' if complete else 'running',site,*(cursor or (None,None)),at,self.generation_id))
            if complete and cp['recovery_feed_highwater_seq'] is not None:
                # Only a completed recovery scan can retire the lost delivery
                # interval. The gap timestamp continues forbidding a complete
                # negative coverage claim for the affected 24h window.
                self.repository.connection.execute('UPDATE service_materialization_checkpoints SET last_edge_feed_seq=recovery_live_feed_seq,recovery_feed_highwater_seq=NULL,recovery_live_feed_seq=NULL,recovery_cutoff_utc=NULL WHERE generation_id=?',(self.generation_id,))
            self.repository.runtime('backfilling',at,commit=at)
            deadline.require_remaining()
        self._last_backfill=tick
        self.telemetry.emit(backfill_pages_total=1,backfill_edges_total=len(page))
        return True

    def cycle(self):
        if not self._cycle_lock.acquire(blocking=False):raise MaterializationConflict()
        try:
            at=ni_format_utc(self.clock())
            deadline=self._deadline()
            if self.source.verify_available(deadline=deadline) is not True:raise ServiceUnavailable()
            bounds=self.projection.recognition_feed_bounds(deadline=deadline)
            if type(bounds) is not RecognitionFeedBoundsV1:raise MaterializationConflict()
            high=bounds.max_feed_seq or 0
            self.generation_id=self.repository.ensure_generation(self.bundle,high,at)
            gen=self.repository.connection.execute('SELECT * FROM service_materialization_generations WHERE generation_id=?',(self.generation_id,)).fetchone()
            if gen['publishable_until_utc']<=at:raise MaterializationConflict()
            cp=self.repository.checkpoint(self.generation_id)
            live,reason=self._live(cp,bounds,at,deadline)
            if reason=='gap':return False
            cp=self.repository.checkpoint(self.generation_id)
            # Replay and coverage can proceed each bounded cycle; backfill is
            # strictly gated by live catch-up, never by an Admin request.
            replay=self._replay(at,deadline)
            coverage=self._reconcile(at,deadline)
            cp=self.repository.checkpoint(self.generation_id)
            current=cp['recovery_live_feed_seq'] if cp['recovery_live_feed_seq'] is not None else cp['last_edge_feed_seq']
            backfill=self._backfill(cp,at,deadline) if current==high else False
            cp=self.repository.checkpoint(self.generation_id)
            if gen['state']=='building' and cp['backfill_state']=='complete' and cp['last_edge_feed_seq']==high and not self.repository.connection.execute("SELECT 1 FROM service_binding_replay_jobs WHERE generation_id=? AND state IN ('pending','running') LIMIT 1",(self.generation_id,)).fetchone():
                self.repository.promote(self.generation_id,at,high)
            tick=self.monotonic()
            if self._last_heartbeat is None or tick-self._last_heartbeat>=10:
                with self.repository.transaction():
                    self.repository.runtime('lagging' if cp['last_edge_feed_seq']<high else 'backfilling' if cp['backfill_state']!='complete' else 'usable',at,highwater=high,cursor=cp['last_edge_feed_seq'],poll=at)
                self._last_heartbeat=tick
            if self._last_retention is None or tick-self._last_retention>=60:
                self.repository.retain()
                self._last_retention=tick
            self._failures=0
            return bool(live or replay or coverage or backfill)
        finally:
            self._cycle_lock.release()

    def run(self):
        if self.repository.connection is None:self.repository.initialize()
        while not self._stop.is_set():
            try:
                busy=self.cycle()
                if not busy:self._stop.wait(1)
            except Exception as error:
                disk_full=isinstance(error,sqlite3.Error) and (getattr(error,'sqlite_errorcode',0)&255)==13
                state='capacity_halted' if isinstance(error,MaterializationCapacity) or disk_full else 'blocked_conflict' if isinstance(error,(MaterializationConflict,BindingReplayConflict)) else 'source_unavailable'
                self.repository.live_state=state
                # Best effort honest heartbeat; capacity never permits cursor writes.
                try:
                    with self.repository.transaction():self.repository.runtime(state,ni_format_utc(self.clock()))
                except Exception:pass
                self._failures=min(self._failures+1,5)
                self.telemetry.emit(**({'capacity_halt_total':1} if state=='capacity_halted' else {'source_failures_total':1}))
                self._stop.wait(min(30,2**self._failures))
        try:
            with self.repository.transaction():self.repository.runtime('stopping',ni_format_utc(self.clock()))
        finally:self.repository.close()
