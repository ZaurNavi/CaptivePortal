from dataclasses import replace
from datetime import timedelta
import pytest
from app.analytics.source_gateway import QueryDeadline
from app.network_metadata.validation import ni_timestamp,ni_format_utc
from app.network_service_recognition.artifacts import load_bundle
from app.network_service_recognition.materialization_repository import MaterializationConflict
from app.network_service_recognition.materialized_read_service import MaterializedDeviceServiceReadService
from app.network_service_recognition.evaluator import ServiceRecognitionEvaluatorV1
from app.network_service_recognition.worker import ServiceMaterializationWorker
from .test_materialization_worker import lane
from .test_summary import SITE,DEVICE,MAC
from .support import AT,bundle,documents,encode


def next_bundle():
    docs=documents()
    docs[0]['taxonomy_version']=2
    next(s for s in docs[0]['services'] if s['service_id']=='service.youtube')['display_name']='YouTube synthetic revision'
    docs[1]['knowledge_manifest_version']=2
    docs[1]['sources'][0]['claim_summary']+=' Synthetic revision.'
    docs[2]['ruleset_version']=2
    return load_bundle(*encode(docs),previous=bundle())


def test_atomic_generation_switch_no_mixed_publication(lane):
    lane.worker.cycle()
    old=lane.worker.generation_id
    b=next_bundle()
    candidate=lane.repo.ensure_generation(b,0,AT)
    reader=MaterializedDeviceServiceReadService(lane.repo.db_path,b,admitted_bundles=(bundle(),))
    value=reader.get_device_service_summary(SITE,DEVICE,MAC,evaluated_at_utc=AT,deadline=QueryDeadline.after(2))
    assert value.recognition_ruleset_version==1
    assert value.recent_services[0].display_name=='YouTube'
    with pytest.raises(MaterializationConflict):lane.repo.promote(candidate,AT,0)
    lane.worker=ServiceMaterializationWorker(lane.repo,lane.projection,lane.worker.source,b,clock=lambda:lane.now.value,monotonic=lambda:lane.now.tick)
    lane.worker.cycle()
    value=reader.get_device_service_summary(SITE,DEVICE,MAC,evaluated_at_utc=AT,deadline=QueryDeadline.after(2))
    assert value.recognition_ruleset_version==2
    assert value.recent_services[0].display_name=='YouTube synthetic revision'
    assert lane.repo.connection.execute("SELECT state FROM service_materialization_generations WHERE generation_id=?",(old,)).fetchone()[0]=='superseded'
    assert lane.repo.connection.execute("SELECT count(*) FROM service_materialization_generations WHERE state='active'").fetchone()[0]==1


def test_same_identity_conflict_no_overwrite(lane):
    lane.worker.cycle()
    docs=documents()
    docs[0]['services'][0]['display_name']='Changed without version bump'
    b=load_bundle(*encode(docs))
    with pytest.raises(MaterializationConflict):lane.repo.ensure_generation(b,0,AT)
    assert lane.repo.connection.execute('SELECT count(*) FROM service_materialization_generations').fetchone()[0]==1


def test_superseded_retention_grace_preserves_active(lane):
    lane.worker.cycle()
    old=lane.worker.generation_id
    b=next_bundle()
    lane.worker=ServiceMaterializationWorker(lane.repo,lane.projection,lane.worker.source,b,clock=lambda:lane.now.value,monotonic=lambda:lane.now.tick)
    lane.worker.cycle()
    new=lane.worker.generation_id
    lane.repo.retain()
    assert lane.repo.connection.execute('SELECT 1 FROM service_materialization_generations WHERE generation_id=?',(old,)).fetchone()
    lane.now.value+=timedelta(days=1,seconds=1)
    for _ in range(3):lane.repo.retain()
    assert not lane.repo.connection.execute('SELECT 1 FROM service_materialization_generations WHERE generation_id=?',(old,)).fetchone()
    assert lane.repo.connection.execute("SELECT state FROM service_materialization_generations WHERE generation_id=?",(new,)).fetchone()[0]=='active'
