from dataclasses import replace
from datetime import timedelta
from hashlib import sha256
import uuid
import pytest
from app.network_metadata.validation import ni_timestamp,ni_format_utc
from app.network_metadata_projection.service_delivery_read_service import RecognitionCandidateV1,RecognitionFeedEntryV1
from app.network_service_recognition.worker import ServiceMaterializationWorker
from app.network_service_recognition.materialization_repository import ServiceMaterializationRepository
from .test_materialization_worker import lane,Source
from .support import AT,bundle


def history(lane,count):
    candidates=[];sources=[]
    for i in range(count):
        event=ni_format_utc(ni_timestamp(AT,canonical=True)-timedelta(hours=24)+timedelta(seconds=i))
        ref=str(uuid.uuid5(uuid.NAMESPACE_URL,'disposable-backfill:'+str(i)))
        fact=replace(lane.projection.fact,event_at=event,edge_id=sha256(str(i).encode()).hexdigest(),source_observation_ref=ref)
        candidates.append(RecognitionCandidateV1(fact,lane.projection.identity))
        sources.append(replace(lane.source,event_at=event,observation_id=ref))
    lane.projection.history=tuple(sorted(candidates,key=lambda c:(c.fact.event_at,c.fact.edge_id)))
    lane.worker.source=Source(tuple(sources))


def test_durable_keyset_resume_without_zero_restart(lane):
    history(lane,129)
    lane.worker.cycle()
    gen=lane.worker.generation_id
    cp=lane.repo.checkpoint(gen)
    assert cp['backfill_state']=='running' and cp['backfill_site_id'] is not None
    assert lane.repo.connection.execute('SELECT count(*) FROM service_recognition_observations').fetchone()[0]==128
    path=lane.repo.db_path
    lane.repo.close()
    lane.repo=ServiceMaterializationRepository(path,clock=lambda:lane.now.value).initialize()
    lane.worker=ServiceMaterializationWorker(lane.repo,lane.projection,lane.worker.source,bundle(),clock=lambda:lane.now.value,monotonic=lambda:lane.now.tick)
    lane.now.tick=2;lane.now.value+=timedelta(seconds=2)
    lane.worker.cycle()
    assert lane.repo.checkpoint(gen)['backfill_state']=='complete'
    assert lane.repo.connection.execute('SELECT count(*) FROM service_recognition_observations').fetchone()[0]==129
    assert lane.repo.connection.execute('SELECT count(*) FROM device_service_rollups').fetchone()[0]==1


def test_one_page_per_second(lane):
    history(lane,257)
    lane.worker.cycle()
    for _ in range(3):lane.worker.cycle()
    assert lane.repo.connection.execute('SELECT count(*) FROM service_recognition_observations').fetchone()[0]==128
    lane.now.tick=1;lane.now.value+=timedelta(seconds=1)
    lane.worker.cycle()
    assert lane.repo.connection.execute('SELECT count(*) FROM service_recognition_observations').fetchone()[0]==256
    assert lane.repo.checkpoint(lane.worker.generation_id)['backfill_state']=='running'


@pytest.mark.parametrize('point',['materialization_evaluated','before_commit','after_commit'])
def test_page_cursor_and_results_atomic(lane,point):
    history(lane,129)
    gen=lane.repo.ensure_generation(bundle(),0,AT)
    lane.worker.generation_id=gen
    def crash(p):
        if p==point:raise RuntimeError('disposable_crash')
    lane.repo.crash_point=crash
    with pytest.raises(RuntimeError):lane.worker.cycle()
    committed=point=='after_commit'
    assert bool(lane.repo.checkpoint(gen)['backfill_event_at'])==committed
    assert lane.repo.connection.execute('SELECT count(*) FROM service_recognition_observations').fetchone()[0]==128*int(committed)


def test_backfill_yields_to_live_backlog(lane):
    history(lane,257)
    lane.worker.cycle()
    rows=lane.projection.history
    # Three hundred live deliveries, deliberately more than one bounded batch.
    live=[];values=list(lane.worker.source.values)
    for i in range(300):
        base=rows[i%len(rows)].fact
        ref=str(uuid.uuid5(uuid.NAMESPACE_URL,'disposable-live:'+str(i)))
        event=ni_format_utc(ni_timestamp(AT,canonical=True)-timedelta(seconds=1))
        fact=replace(base,edge_id=sha256(('live:'+str(i)).encode()).hexdigest(),source_observation_ref=ref,event_at=event)
        live.append(RecognitionFeedEntryV1(i+1,AT,fact,lane.projection.identity))
        values.append(replace(lane.source,event_at=event,observation_id=ref))
    lane.projection.entries=tuple(live)
    lane.worker.source=Source(tuple(values))
    lane.now.tick=2;lane.now.value+=timedelta(seconds=2)
    before=lane.repo.checkpoint(lane.worker.generation_id)['backfill_edge_id']
    lane.worker.cycle()
    assert lane.repo.checkpoint(lane.worker.generation_id)['last_edge_feed_seq']==256
    assert lane.repo.checkpoint(lane.worker.generation_id)['backfill_edge_id']==before


def test_captured_H_live_then_fixed_24h_snapshot(lane):
    history(lane,1)
    lane.projection.entries=(RecognitionFeedEntryV1(7,AT,lane.projection.fact,lane.projection.identity),)
    lane.worker.cycle()
    cp=lane.repo.checkpoint(lane.worker.generation_id)
    gen=lane.repo.connection.execute('SELECT * FROM service_materialization_generations').fetchone()
    assert gen['live_feed_start_seq']==7 and cp['last_edge_feed_seq']==7
    assert ni_timestamp(gen['build_started_at_utc'],canonical=True)-ni_timestamp(cp['backfill_from_utc'],canonical=True)==timedelta(days=1)
    assert lane.projection.calls[0]==('feed',7)
