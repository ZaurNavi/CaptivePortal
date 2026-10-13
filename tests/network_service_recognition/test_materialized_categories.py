from dataclasses import replace
from datetime import timedelta
from hashlib import sha256
import uuid
import pytest
from app.analytics.source_gateway import QueryDeadline
from app.network_metadata.validation import ni_format_utc,ni_timestamp
from app.network_metadata_projection.service_delivery_read_service import RecognitionCandidateV1
from app.network_service_recognition.artifacts import load_bundle
from app.network_service_recognition.evaluator import ServiceRecognitionEvaluatorV1
from app.network_service_recognition.materialized_read_service import MaterializedDeviceServiceReadService
from .test_materialization_worker import lane,Source
from .support import AT,documents,encode
from .test_summary import SITE,DEVICE,MAC


def setup_many(lane, *, count=13,old=False,tied=False):
    docs=documents()
    taxonomy,_,ruleset=docs
    category_rows=taxonomy['service_categories']
    # The excluded thirteenth Service owns a category not used by the first 12.
    category_first='category.video_streaming'
    category_last=next(c['service_category_id'] for c in category_rows if c['service_category_id']!=category_first)
    taxonomy['services']=[]
    template=ruleset['rules'][0]
    ruleset['rules']=[]
    sources=[];history=[]
    for i in range(count):
        sid=f'service.synthetic_{i:02d}'
        taxonomy['services'].append(dict(service_id=sid,display_name=f'Synthetic {i:02d}',organization_id='org.google',service_category_id=category_last if i==12 else category_first,lifecycle_state='active'))
        ruleset['rules'].append(dict(template,rule_id=f'rule.synthetic_{i:02d}',rule_kind='service_sni_exact',target_type='service',target_id=sid,hostname_pattern=f'case-{i}.example',ambiguity_group_id=None))
        event=ni_format_utc(ni_timestamp(AT,canonical=True)-timedelta(seconds=3700 if old and i==12 else 60+(0 if tied else i)))
        ref=str(uuid.uuid5(uuid.NAMESPACE_URL,f'category-fixture:{i}'))
        fact=replace(lane.projection.fact,event_at=event,edge_id=sha256(f'edge-{i}'.encode()).hexdigest(),source_observation_ref=ref)
        history.append(RecognitionCandidateV1(fact,lane.projection.identity))
        sources.append(replace(lane.source,event_at=event,observation_id=ref,tls=replace(lane.source.tls,sni=f'case-{i}.example')))
    b=load_bundle(*encode(docs))
    lane.worker.bundle=b;lane.worker.evaluator=ServiceRecognitionEvaluatorV1(b)
    lane.projection.history=tuple(sorted(history,key=lambda c:(c.fact.event_at,c.fact.edge_id)))
    lane.worker.source=Source(tuple(sources))
    lane.worker.cycle()
    return b,category_first,category_last


def result(lane,b):
    return MaterializedDeviceServiceReadService(lane.repo.db_path,b).get_device_service_summary(SITE,DEVICE,MAC,evaluated_at_utc=AT,deadline=QueryDeadline.after(2))


def test_13th_unique_category_excluded(lane):
    b,first,last=setup_many(lane)
    value=result(lane,b)
    assert len(value.recent_services)==12
    assert [r.service_id for r in value.recent_services]==[f'service.synthetic_{i:02d}' for i in range(12)]
    assert value.coverage.recognition_state=='limited'
    assert [r.service_category_id for r in value.service_categories]==[first]
    assert last not in [r.service_category_id for r in value.service_categories]


def test_shared_category_latest_selected_and_service_ties(lane):
    b,first,last=setup_many(lane,tied=True)
    value=result(lane,b)
    assert [r.service_id for r in value.recent_services]==sorted(r.service_id for r in value.recent_services)
    assert len(value.service_categories)==1
    assert value.service_categories[0].last_observed_at==value.recent_services[0].last_observed_at


def test_old_nonrecent_unique_category_not_added(lane):
    b,first,last=setup_many(lane,old=True)
    value=result(lane,b)
    assert len(value.recent_services)==12 and value.coverage.recognition_state=='usable'
    assert [r.service_category_id for r in value.service_categories]==[first]


def test_no_independent_category_table(lane):
    b,_,_=setup_many(lane)
    assert not lane.repo.connection.execute("SELECT 1 FROM sqlite_schema WHERE name='device_category_rollups'").fetchone()
    assert result(lane,b).schema_version==3
