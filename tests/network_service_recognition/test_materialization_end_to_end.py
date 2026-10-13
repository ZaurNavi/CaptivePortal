from dataclasses import replace
from datetime import timedelta
from types import SimpleNamespace
import json
import platform
import sqlite3
import time
import pytest
from app.analytics.source_gateway import QueryDeadline
from app.network_metadata.validation import ni_timestamp
from app.network_metadata.projection_source import NetworkMetadataProjectionSourceReadService
from app.network_metadata_projection.models import RegistryEvaluation
from app.network_metadata_projection.service_extension import install_service_recognition_extension
from app.network_metadata_projection.service_delivery_read_service import ServiceRecognitionDeliveryReadService
from app.network_service_recognition.source_adapter import WorkerSourceReadService
from app.network_service_recognition.materialization_repository import ServiceMaterializationRepository
from app.network_service_recognition.worker import ServiceMaterializationWorker
from app.network_service_recognition.materialized_read_service import MaterializedDeviceServiceReadService
from app.network_service_recognition.read_service import DeviceServiceRecognitionReadService
from app.network_metadata_projection.recognition_read_service import DeviceNetworkMetadataRecognitionReadService
from app.network_service_recognition.shadow import compare_shadow
from app.network_service_recognition.models import ServiceDeadline
from .test_protected_readers import store,DEVICE
from .test_summary import SITE,EVENT
from .test_materialization_worker import lane
from .support import AT,bundle
from tests.network_metadata import source_event,record,outcome
from tests.network_metadata_projection.support import stack,MAC


def test_real_three_store_background_roundtrip_immutable_upstream(tmp_path,record_property):
    event=source_event('tls',timestamp=EVENT,dest_ip='203.0.113.93',proto='TCP')
    event['tls']['sni']='www.youtube.com'
    data=record(event)
    with store(tmp_path,source=data+b'\n') as source:
        source.clock.value=ni_timestamp(AT,canonical=True)
        source.repo.ingest_batch([outcome(source.config.capture_scope_binding,data,generation=source.generation.source_generation_id)],source.run,source.health,source.anchor)
        ref=source.repo.connection.execute('SELECT observation_id FROM network_metadata_observations').fetchone()[0]
        ni01=NetworkMetadataProjectionSourceReadService(source.config.db_path)
        projection=stack(tmp_path,[ni01.get_projection_source_record(ref)])
        projection.clock.value=ni_timestamp(AT,canonical=True)
        projection.attribution.states['203.0.113.93']='endpoint_absent'
        original=projection.attribution.resolve_ipv4
        def resolve(*args):
            value=original(*args)
            return replace(value,valid_from='2026-10-11T00:00:00.000Z',valid_until='2026-10-13T00:00:00.000Z') if value.state=='resolved' else value
        projection.attribution.resolve_ipv4=resolve
        projection.registry.values[MAC]=RegistryEvaluation('authoritative',DEVICE)
        install_service_recognition_extension(projection.repo)
        target=ServiceMaterializationRepository(str(tmp_path/'ni04.sqlite3'),clock=projection.clock).initialize()
        b=bundle()
        worker=ServiceMaterializationWorker(target,ServiceRecognitionDeliveryReadService(projection.config.db_path),WorkerSourceReadService(source.config.db_path),b,clock=projection.clock)
        try:
            worker.cycle() # Empty generation/backfill before the new committed edge.
            projection.service.poll()
            before=(tuple(source.repo.connection.iterdump()),tuple(projection.repo.connection.iterdump()))
            start=time.perf_counter()
            worker.cycle()
            latency=(time.perf_counter()-start)*1000
            reader=MaterializedDeviceServiceReadService(target.db_path,b)
            value=reader.get_device_service_summary(SITE,DEVICE,MAC,evaluated_at_utc=AT,deadline=QueryDeadline.after(2))
            assert value.recent_services[0].service_id=='service.youtube'
            assert target.checkpoint(worker.generation_id)['last_edge_feed_seq']==1
            assert before==(tuple(source.repo.connection.iterdump()),tuple(projection.repo.connection.iterdump()))
            legacy=DeviceServiceRecognitionReadService(DeviceNetworkMetadataRecognitionReadService(projection.config.db_path),WorkerSourceReadService(source.config.db_path),b)
            comparison=compare_shadow(legacy,reader,SITE,DEVICE,MAC,evaluated_at_utc=AT,deadline=QueryDeadline.after(5))
            assert comparison.status=='PASS' and comparison.extra_positive_count==comparison.missing_positive_count==0
            record_property('single_live_batch_ms',latency)
        finally:
            target.close();projection.repo.close()


def test_reader_targeted_latency_samples(lane,record_property):
    lane.worker.cycle()
    reader=MaterializedDeviceServiceReadService(lane.repo.db_path,bundle())
    for _ in range(10):reader.get_device_service_summary(SITE,DEVICE,MAC,evaluated_at_utc=AT,deadline=QueryDeadline.after(2))
    samples=[]
    for _ in range(300):
        start=time.perf_counter()
        value=reader.get_device_service_summary(SITE,DEVICE,MAC,evaluated_at_utc=AT,deadline=QueryDeadline.after(2))
        samples.append((time.perf_counter()-start)*1000)
        assert value.schema_version==3
    ordered=sorted(samples)
    p95,p99=ordered[284],ordered[296]
    record_property('reader_lab_samples',json.dumps({'count':300,'warmup':10,'python':platform.python_version(),'sqlite':sqlite3.sqlite_version,'p95_ms':p95,'p99_ms':p99,'maximum_ms':max(samples)}))
    assert p95<=50 and p99<=100


def test_legacy_deadline_separate_not_false_mismatch(lane):
    class Deadline:
        def get_device_service_summary(self,*a,**kw):raise ServiceDeadline()
    result=compare_shadow(Deadline(),object(),SITE,DEVICE,MAC,evaluated_at_utc=AT,deadline=QueryDeadline.after(5))
    assert result.status=='LEGACY_DEADLINE_RECORDED' and result.extra_positive_count==0


def test_real_live_latency_and_bounded_rss(tmp_path,record_property):
    from .memory_measurement import resident_highwater_bytes
    records=[];offsets=[];offset=0
    for i in range(20):
        event=source_event('tls',timestamp=EVENT,dest_ip='203.0.113.93',proto='TCP',flow_id=i+1)
        event['tls']['sni']='www.youtube.com'
        data=record(event)
        records.append(data);offsets.append(offset);offset+=len(data)+1
    with store(tmp_path,source=b''.join(d+b'\n' for d in records)) as source:
        source.clock.value=ni_timestamp(AT,canonical=True)
        source.repo.ingest_batch([outcome(source.config.capture_scope_binding,d,start=o,generation=source.generation.source_generation_id) for d,o in zip(records,offsets)],source.run,source.health,source.anchor)
        ni01=NetworkMetadataProjectionSourceReadService(source.config.db_path)
        refs=tuple(r[0] for r in source.repo.connection.execute('SELECT observation_id FROM network_metadata_observations ORDER BY record_start_byte_offset'))
        projection=stack(tmp_path,[ni01.get_projection_source_record(refs[0])])
        projection.source.records=[]
        projection.clock.value=ni_timestamp(AT,canonical=True)
        projection.attribution.states['203.0.113.93']='endpoint_absent'
        original=projection.attribution.resolve_ipv4
        projection.attribution.resolve_ipv4=lambda *args:replace(original(*args),valid_from='2026-10-11T00:00:00.000Z',valid_until='2026-10-13T00:00:00.000Z') if original(*args).state=='resolved' else original(*args)
        projection.registry.values[MAC]=RegistryEvaluation('authoritative',DEVICE)
        install_service_recognition_extension(projection.repo)
        target=ServiceMaterializationRepository(str(tmp_path/'ni04.sqlite3'),clock=projection.clock).initialize()
        worker=ServiceMaterializationWorker(target,ServiceRecognitionDeliveryReadService(projection.config.db_path),WorkerSourceReadService(source.config.db_path),bundle(),clock=projection.clock)
        try:
            worker.cycle()
            before_rss=resident_highwater_bytes()
            samples=[]
            for ref in refs:
                projection.source.records.append(ni01.get_projection_source_record(ref))
                projection.service.poll()
                committed=time.perf_counter()
                worker.cycle()
                samples.append((time.perf_counter()-committed)*1000)
            delta=max(0,resident_highwater_bytes()-before_rss)
            ordered=sorted(samples)
            record_property('live_lab_samples',json.dumps({'count':20,'p95_ms':ordered[18],'p99_ms':ordered[19],'maximum_ms':max(samples),'rss_highwater_delta_bytes':delta,'python':platform.python_version(),'sqlite':sqlite3.sqlite_version,'scope':'disposable single-device real three-store incremental fixture; not production capacity certification'}))
            assert ordered[18]<=10000 and ordered[19]<=30000 and delta<=64*1024*1024
            assert target.connection.execute('SELECT count(*) FROM service_recognition_observations').fetchone()[0]==20
        finally:target.close();projection.repo.close()
