"""Serve mode reads only NI-04. No source, projection or matcher dependency."""
import sqlite3
import threading
from datetime import timedelta
from pathlib import Path
from app.analytics.source_gateway import QueryDeadline,AnalyticsQueryDeadlineExceeded
from app.device_fingerprint.validation import validate_site_id
from app.network_attribution.validation import canonical_mac
from app.network_metadata.validation import canonical_uuid,digest,ni_timestamp,ni_format_utc
from .artifacts import RecognitionBundle,AdmittedArtifact
from .materialization_schema import validate_schema
from .models import (DeviceServiceSummaryV3,ServiceMaterializationV1,ServiceWindowV1,ServiceRecognitionCoverageV2,
    RecentServiceV1,RecentServiceCategoryV1,LastServiceObservationV1,ServiceUnavailable,ServiceDeadline,ServiceBusy,ServiceValidationError,
    freshness,materialized_evidence_state,materialized_availability)
from .serialization import serialize_device_service_intelligence

_SLOTS=threading.BoundedSemaphore(1)
_FACT_JOIN=(' LEFT JOIN service_recognition_observations o ON o.generation_id=r.generation_id '
    'AND o.service_observation_id=r.last_service_observation_id AND o.site_id=r.site_id '
    'AND o.device_id=r.device_id AND o.client_mac=r.client_mac AND o.service_id=r.service_id '
    'AND o.organization_id=r.organization_id AND o.service_category_id=r.service_category_id '
    'AND o.observed_at=r.last_observed_at')
_FACT_COLUMNS=('r.*,o.service_observation_id AS checked_observation_id,o.edge_id,o.source_observation_ref,'
    'o.registry_binding_change_seq,o.matched_rule_id,o.source_event_family,o.support_state')


class MaterializedDeviceServiceReadService:
    def __init__(self,db_path,bundle, *, admitted_bundles=()):
        if type(db_path) is not str or not Path(db_path).is_absolute() or type(bundle) is not RecognitionBundle:
            raise ServiceUnavailable('recognition_unavailable')
        self.db_path,self.bundle=db_path,bundle
        self._bundles={}
        for b in (bundle,*admitted_bundles):
            if type(b) is not RecognitionBundle or not all(type(a) is AdmittedArtifact for a in (b.taxonomy,b.manifest,b.ruleset)):raise ServiceUnavailable('recognition_unavailable')
            key=(b.taxonomy['taxonomy_digest_sha256'],b.manifest['knowledge_manifest_digest_sha256'],b.ruleset['ruleset_digest_sha256'])
            self._bundles[key]=b

    def publication_bundle(self,value):
        matches=[b for b in self._bundles.values() if b.ruleset['ruleset_digest_sha256']==value.recognition_ruleset_digest_sha256 and b.taxonomy['taxonomy_digest_sha256']==value.taxonomy_digest_sha256]
        if len(matches)!=1:raise ServiceUnavailable('recognition_unavailable')
        return matches[0]

    @staticmethod
    def _service_fields(row):
        return tuple(row[key] for key in ('service_id','display_name','organization_id','organization_display_name','service_category_id','service_category_display_name','last_observed_at'))+('directly_supported',)

    def get_device_service_summary(self,site_id,device_id,client_mac, *, evaluated_at_utc,deadline):
        try:
            validate_site_id(site_id)
            canonical_uuid(device_id)
            if canonical_mac(client_mac)!=client_mac:raise ValueError
            at=ni_timestamp(evaluated_at_utc,canonical=True)
        except Exception:raise ServiceValidationError() from None
        if not _SLOTS.acquire(blocking=False):raise ServiceBusy()
        connection=None
        try:
            bounded=QueryDeadline(min(deadline.expires_at,deadline.monotonic()+1),deadline.monotonic)
            bounded.require_remaining()
            connection=sqlite3.connect(Path(self.db_path).resolve().as_uri()+'?mode=ro',uri=True,timeout=.5,isolation_level=None)
            connection.row_factory=sqlite3.Row
            connection.set_progress_handler(lambda:int(bounded.expired()),100)
            for pragma in ('query_only=ON','foreign_keys=ON','busy_timeout=500'):connection.execute('PRAGMA '+pragma)
            connection.execute('BEGIN')
            validate_schema(connection)
            runtime=connection.execute("SELECT r.*,g.*,c.backfill_state,c.backfill_from_utc,c.last_feed_gap_at_utc,c.recovery_feed_highwater_seq,c.last_edge_feed_seq FROM service_materialization_runtime r LEFT JOIN service_materialization_generations g ON g.generation_id=r.active_generation_id LEFT JOIN service_materialization_checkpoints c ON c.generation_id=g.generation_id WHERE r.singleton_id=1").fetchone()
            if runtime is None:raise ServiceUnavailable()
            gen=runtime['active_generation_id']
            b=self.bundle
            valid=False
            if gen is not None:
                canonical_uuid(gen)
                key=tuple(runtime[k+'_digest_sha256'] for k in ('taxonomy','knowledge_manifest','ruleset'))
                b=self._bundles.get(key)
                if b is None or runtime['state']!='active':raise ServiceUnavailable('recognition_unavailable')
                for kind,parent in (('taxonomy',b.taxonomy),('knowledge_manifest',b.manifest),('ruleset',b.ruleset)):
                    for suffix in ('_id','_version','_digest_sha256'):
                        if runtime[kind+suffix]!=parent[kind+suffix]:raise ServiceUnavailable('recognition_unavailable')
                valid=at<ni_timestamp(runtime['publishable_until_utc'],canonical=True)
                if valid:
                    intervals=[b.manifest.index[r['rule_id']] for r in b.ruleset['rules'] if r['lifecycle_state']=='active' and '_sni_' in r['rule_kind']]
                    valid=bool(intervals) and all(first<=at<last for first,last in intervals)
            state=connection.execute('SELECT * FROM device_materialization_state WHERE generation_id=? AND site_id=? AND device_id=?',(gen,site_id,device_id)).fetchone()
            if state and state['client_mac']!=client_mac:raise ServiceUnavailable('recognition_unavailable')
            recent_cutoff,window_cutoff=ni_format_utc(at-timedelta(hours=1)),ni_format_utc(at-timedelta(days=1))
            query=('SELECT '+_FACT_COLUMNS+' FROM device_service_rollups r INDEXED BY idx_materialization_device_recent'+_FACT_JOIN+
                ' WHERE r.generation_id=? AND r.site_id=? AND r.device_id=? AND r.client_mac=? AND r.last_observed_at>=? ORDER BY r.last_observed_at DESC,r.service_id ASC LIMIT ')
            recent=connection.execute(query+'13',(gen,site_id,device_id,client_mac,recent_cutoff)).fetchall()
            last=connection.execute(query+'1',(gen,site_id,device_id,client_mac,window_cutoff)).fetchone()
            # A missing referenced observation cannot become a benign empty result.
            if recent and last is None:raise ServiceUnavailable('recognition_unavailable')
            rules={r['rule_id']:r for r in b.ruleset['rules']}
            for row in (*recent,*(() if last is None else (last,))):
                if row['checked_observation_id']!=row['last_service_observation_id']:
                    raise ServiceUnavailable('recognition_unavailable')
                digest(row['last_service_observation_id'])
                digest(row['edge_id'])
                canonical_uuid(row['source_observation_ref'],5)
                if not ni_timestamp(row['last_observed_at'],canonical=True)<at:raise ServiceUnavailable()
                rule=rules.get(row['matched_rule_id'])
                if rule is None or rule['target_type']!='service' or rule['target_id']!=row['service_id'] or row['support_state']!='directly_supported':raise ServiceUnavailable('recognition_unavailable')
            identity='absent' if state is None else state['identity_binding_state']
            if identity=='conflict':identity='unavailable'
            source,attribute=('unknown','unknown') if state is None else (state['source_state'],state['pipeline_attribution_state'])
            pending=bool(state['device_linked_pending']) if state and identity=='authoritative' else False
            rec='unavailable' if not valid or state is None or identity!='authoritative' else state['recognition_state']
            limitation=state['last_recognition_limitation_at'] if state else None
            if limitation is not None and limitation>=window_cutoff:rec='limited'
            elif valid and state is not None and identity=='authoritative' and rec=='limited':rec='usable'
            if len(recent)>12 and rec!='unavailable':rec='limited'
            poll=runtime['last_upstream_poll_at_utc']
            lag=None if poll is None else max(0,int((at-ni_timestamp(poll,canonical=True)).total_seconds()))
            if poll is not None and ni_timestamp(poll,canonical=True)>at:raise ServiceUnavailable()
            running=runtime['runtime_state']
            if running=='capacity_halted':mat_state='capacity_halted'
            elif running=='blocked_conflict':mat_state='conflict'
            elif running in {'source_unavailable','recognition_unavailable','initializing','stopping'} or lag is None or lag>120:mat_state='unavailable'
            elif runtime['backfill_state']!='complete' or runtime['recovery_feed_highwater_seq'] is not None:mat_state='backfilling'
            elif runtime['last_edge_feed_seq']!=runtime['observed_feed_highwater_seq'] or lag>10:mat_state='lagging'
            else:mat_state='current'
            complete=(state is not None and valid and runtime['backfill_state']=='complete' and runtime['recovery_feed_highwater_seq'] is None
                and state['coverage_valid_from_utc']<=window_cutoff and runtime['backfill_from_utc']<=window_cutoff
                and (runtime['last_feed_gap_at_utc'] is None or runtime['last_feed_gap_at_utc']<window_cutoff))
            # No recency claim based on stale per-device coverage.
            if state and (at-ni_timestamp(state['coverage_evaluated_at_utc'],canonical=True)).total_seconds()>60:
                source,attribute='unknown','unknown'
                complete=False
            if state and ni_timestamp(state['coverage_evaluated_at_utc'],canonical=True)>at:raise ServiceUnavailable()
            window_state='complete' if complete else 'partial' if state is not None else 'unknown'
            mat=ServiceMaterializationV1(mat_state,window_state,runtime['last_successful_commit_at_utc'],lag)
            if not valid or identity!='authoritative':recent,last=[],None
            visible=tuple(RecentServiceV1(*self._service_fields(row)) for row in recent[:12])
            latest={}
            for row in visible:latest.setdefault(row.service_category_id,(row.service_category_display_name,row.last_observed_at))
            cats=tuple(RecentServiceCategoryV1(k,*v) for k,v in sorted(latest.items(),key=lambda pair:(at-ni_timestamp(pair[1][1],canonical=True),pair[0])))
            last_dto=LastServiceObservationV1(*self._service_fields(last)) if last is not None else None
            coverage=ServiceRecognitionCoverageV2('confirmed_device_evidence',source,attribute,'authoritative' if identity=='authoritative' else 'none',pending,rec,False)
            identities={'recognition_'+key:b.ruleset[key] for key in ('ruleset_id','ruleset_version','ruleset_digest_sha256')}
            identities.update({k:b.taxonomy[k] for k in ('taxonomy_id','taxonomy_version','taxonomy_digest_sha256')})
            result=DeviceServiceSummaryV3(3,site_id,device_id,evaluated_at_utc,ServiceWindowV1(window_cutoff,evaluated_at_utc,86400,recent_cutoff,3600),
                materialized_availability(identity,coverage,mat),materialized_evidence_state(identity,last_dto,coverage,mat),identity,visible,cats,last_dto,
                freshness(None if last_dto is None else (at-ni_timestamp(last_dto.observed_at,canonical=True)).total_seconds(),coverage),coverage,**identities,materialization=mat)
            serialize_device_service_intelligence(result,b)
            bounded.require_remaining()
            return result
        except AnalyticsQueryDeadlineExceeded:raise ServiceDeadline() from None
        except (ServiceUnavailable,ServiceDeadline,ServiceBusy,ServiceValidationError):raise
        except Exception:
            if connection is not None and bounded.expired():raise ServiceDeadline() from None
            raise ServiceUnavailable() from None
        finally:
            if connection is not None:connection.close()
            _SLOTS.release()
