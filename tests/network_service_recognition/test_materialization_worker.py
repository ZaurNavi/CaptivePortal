from dataclasses import replace
from datetime import timedelta
from types import SimpleNamespace
import pytest

from app.network_metadata.validation import ni_timestamp,ni_format_utc
from app.network_metadata_projection.service_delivery_read_service import RecognitionFeedEntryV1,RecognitionFeedBoundsV1,RecognitionIdentityV1,RecognitionCandidateV1,RecognitionDeviceCoverageV1,AuthoritativeBindingChangeV1
from app.network_service_recognition.worker import ServiceMaterializationWorker
from app.network_service_recognition.materialization_repository import ServiceMaterializationRepository,MaterializationConflict
from app.network_service_recognition.materialization_config import materialization_config_from_env
from app.network_service_recognition.materialization_telemetry import MaterializationTelemetry,FIELDS
from .test_summary import synthetic,Source as EvidenceSource,SITE,DEVICE,MAC
from .support import AT,bundle


class Projection:
    def __init__(self,fact):
        self.fact=fact
        self.identity=RecognitionIdentityV1(SITE,MAC,DEVICE,'authoritative',1)
        self.entries=()
        self.history=(RecognitionCandidateV1(fact,self.identity),)
        self.changes=()
        self.pending=0
        self.calls=[]
    def recognition_feed_bounds(self,**kw):
        return RecognitionFeedBoundsV1(self.entries[0].feed_seq if self.entries else None,self.entries[-1].feed_seq if self.entries else 0)
    def read_service_recognition_feed(self,after,**kw):
        self.calls.append(('feed',after))
        return tuple(e for e in self.entries if e.feed_seq>after)[:kw['limit']]
    def read_authoritative_binding_changes(self,after,**kw):return tuple(c for c in self.changes if c.change_seq>after)
    def read_current_identity(self,*a,**kw):return self.identity
    def read_recognition_device_coverage(self,*a,**kw):
        return RecognitionDeviceCoverageV1('attribution_unavailable' if self.pending else 'usable','pending_attribution' if self.pending else None,self.identity.binding_state,self.identity.device_id,self.pending)
    def read_candidate_sites(self,after_site_id=None,**kw):return (SITE,) if after_site_id is None else ()
    def read_candidate_page(self,site,first,last,**kw):
        self.calls.append(('backfill',site,kw.get('client_mac')))
        cursor=kw.get('cursor')
        return tuple(c for c in self.history if cursor is None or (c.fact.event_at,c.fact.edge_id)>cursor)[:kw['limit']]


class Source(EvidenceSource):
    def verify_available(self,**kw):
        kw['deadline'].require_remaining()
        return True


@pytest.fixture
def lane(tmp_path):
    snapshot,source=synthetic()
    now=SimpleNamespace(value=ni_timestamp(AT,canonical=True),tick=0.)
    repo=ServiceMaterializationRepository(str(tmp_path/'store.sqlite3'),clock=lambda:now.value).initialize()
    projection=Projection(snapshot.facts[0])
    worker=ServiceMaterializationWorker(repo,projection,Source((source,)),bundle(),clock=lambda:now.value,monotonic=lambda:now.tick)
    yield SimpleNamespace(repo=repo,projection=projection,worker=worker,now=now,source=source)
    repo.close()


def test_background_positive_no_admin_request(lane):
    assert lane.worker.cycle()
    assert lane.repo.connection.execute('SELECT service_id FROM device_service_rollups').fetchone()[0]=='service.youtube'
    assert lane.repo.connection.execute('SELECT runtime_state FROM service_materialization_runtime').fetchone()[0]=='usable'
    assert lane.repo.checkpoint(lane.worker.generation_id)['backfill_state']=='complete'


def test_live_atomic_and_idempotent_overlap(lane):
    lane.projection.history=()
    lane.worker.cycle()
    lane.projection.entries=(RecognitionFeedEntryV1(1,AT,lane.projection.fact,lane.projection.identity),)
    lane.worker.cycle()
    assert lane.repo.checkpoint(lane.worker.generation_id)['last_edge_feed_seq']==1
    lane.projection.history=(RecognitionCandidateV1(lane.projection.fact,lane.projection.identity),)
    lane.projection.changes=(AuthoritativeBindingChangeV1(1,SITE,MAC,DEVICE,AT),)
    lane.worker.cycle()
    assert lane.repo.connection.execute('SELECT count(*) FROM service_recognition_observations').fetchone()[0]==1


@pytest.mark.parametrize('point',['materialization_evaluated','before_commit','after_commit'])
def test_live_crash_checkpoint_exact(lane,point):
    lane.projection.history=()
    lane.worker.cycle()
    lane.projection.entries=(RecognitionFeedEntryV1(1,AT,lane.projection.fact,lane.projection.identity),)
    def crash(p):
        if p==point:raise RuntimeError('synthetic')
    lane.repo.crash_point=crash
    with pytest.raises(RuntimeError):lane.worker.cycle()
    assert lane.repo.checkpoint(lane.worker.generation_id)['last_edge_feed_seq']==int(point=='after_commit')
    lane.repo.crash_point=lambda _:None
    lane.worker.cycle()
    assert lane.repo.connection.execute('SELECT count(*) FROM service_recognition_observations').fetchone()[0]==1


def test_non_authoritative_live_then_exact_binding_replay(lane):
    lane.projection.history=()
    lane.worker.cycle()
    pending=replace(lane.projection.identity,device_id=None,binding_state='not_yet_registry_resolved',registry_binding_change_seq=None)
    lane.projection.identity=pending
    lane.projection.entries=(RecognitionFeedEntryV1(1,AT,lane.projection.fact,pending),)
    lane.worker.cycle()
    assert lane.repo.checkpoint(lane.worker.generation_id)['last_edge_feed_seq']==1
    assert lane.repo.connection.execute('SELECT count(*) FROM service_recognition_observations').fetchone()[0]==0
    lane.projection.identity=RecognitionIdentityV1(SITE,MAC,DEVICE,'authoritative',2)
    lane.projection.history=(RecognitionCandidateV1(lane.projection.fact,lane.projection.identity),)
    lane.projection.changes=(AuthoritativeBindingChangeV1(2,SITE,MAC,DEVICE,AT),)
    lane.worker.cycle()
    assert lane.repo.connection.execute('SELECT count(*) FROM service_recognition_observations').fetchone()[0]==1
    assert ('backfill',SITE,MAC) in lane.projection.calls


def test_peer_pending_and_reconciliation_without_new_edge(lane):
    lane.projection.pending=1
    lane.worker.cycle()
    assert lane.repo.connection.execute('SELECT device_linked_pending FROM device_materialization_state').fetchone()[0]==1
    lane.now.tick=31
    lane.now.value+=timedelta(seconds=31)
    lane.projection.pending=0
    lane.worker.cycle()
    state=lane.repo.connection.execute('SELECT * FROM device_materialization_state').fetchone()
    assert state['device_linked_pending']==0 and state['pipeline_attribution_state']=='usable'
    assert lane.repo.connection.execute('SELECT count(*) FROM service_recognition_observations').fetchone()[0]==1


def test_source_failure_no_cursor_advance(lane):
    lane.projection.history=()
    lane.worker.cycle()
    lane.projection.entries=(RecognitionFeedEntryV1(1,AT,lane.projection.fact,lane.projection.identity),)
    lane.worker.source=Source(())
    with pytest.raises(Exception):lane.worker.cycle()
    assert lane.repo.checkpoint(lane.worker.generation_id)['last_edge_feed_seq']==0


def test_gap_no_false_cursor_progress(lane):
    lane.worker.cycle()
    lane.projection.entries=(RecognitionFeedEntryV1(4,AT,lane.projection.fact,lane.projection.identity),)
    assert not lane.worker.cycle()
    cp=lane.repo.checkpoint(lane.worker.generation_id)
    assert cp['last_edge_feed_seq']==0 and cp['backfill_state']=='running'
    assert cp['recovery_feed_highwater_seq']==4 and cp['last_feed_gap_at_utc']==AT
    assert lane.repo.connection.execute('SELECT count(*) FROM service_recognition_observations').fetchone()[0]==1
    lane.now.tick=2
    lane.worker.cycle()
    cp=lane.repo.checkpoint(lane.worker.generation_id)
    assert cp['last_edge_feed_seq']==4 and cp['recovery_feed_highwater_seq'] is None
    assert cp['last_feed_gap_at_utc']==AT


def test_idle_heartbeat_write_limit(lane):
    lane.worker.cycle()
    statements=[]
    lane.repo.connection.set_trace_callback(statements.append)
    for tick in range(1,10):
        lane.now.tick=tick
        lane.now.value=ni_timestamp(AT,canonical=True)+timedelta(seconds=tick)
        lane.worker.cycle()
    assert not any(s.startswith(('BEGIN','UPDATE','INSERT','DELETE')) for s in statements)


def test_default_off_no_db_open(monkeypatch):
    from app.network_service_recognition.cli import main
    monkeypatch.setenv('NETWORK_SERVICE_MATERIALIZATION_MODE','off')
    assert main(['run'])==0
    assert materialization_config_from_env({}).mode=='off'


@pytest.mark.parametrize('field',sorted(FIELDS))
def test_privacy_closed_telemetry(field):
    class Logger:
        def info(self,message,**kw):assert kw['extra']['materialization_counts']=={field:1}
    MaterializationTelemetry(Logger()).emit(**{field:1})


@pytest.mark.parametrize('values',[{'client_mac':1},{'feed_cursor_seq':True},{'feed_cursor_seq':-1},{'feed_cursor_seq':1.5},{'feed_cursor_seq':2**63}])
def test_invalid_telemetry_rejected(values):
    with pytest.raises(ValueError):MaterializationTelemetry().emit(**values)
