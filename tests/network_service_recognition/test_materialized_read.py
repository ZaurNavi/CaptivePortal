from dataclasses import replace
from datetime import timedelta
import json
import pytest
from app.analytics.source_gateway import QueryDeadline
from app.network_metadata.validation import ni_timestamp,ni_format_utc
from app.network_service_recognition.materialized_read_service import MaterializedDeviceServiceReadService
from app.network_service_recognition.serialization import serialize_device_service_intelligence
from app.network_service_recognition.models import ServiceUnavailable
from .test_materialization_worker import lane
from .test_summary import SITE,DEVICE,MAC
from .support import bundle,AT


def read(lane,at=AT,**identity):
    return MaterializedDeviceServiceReadService(lane.repo.db_path,bundle()).get_device_service_summary(
        identity.get('site',SITE),identity.get('device',DEVICE),identity.get('mac',MAC),evaluated_at_utc=at,deadline=QueryDeadline.after(2))


def test_v3_positive_query_only_no_source_reads(lane,monkeypatch):
    lane.worker.cycle()
    before=tuple(lane.repo.connection.iterdump())
    def forbidden(*args,**kw):pytest.fail('serve_called_upstream')
    monkeypatch.setattr(lane.projection,'read_candidate_page',forbidden)
    monkeypatch.setattr(lane.worker.source,'read_recognition_evidence',forbidden)
    import app.network_service_recognition.matcher as matcher
    monkeypatch.setattr(matcher,'match_direct_sni_v1',forbidden)
    result=read(lane)
    assert result.schema_version==3 and result.materialization.state=='current'
    assert result.recent_services[0].service_id=='service.youtube'
    value=serialize_device_service_intelligence(result,bundle())
    assert set(value['materialization'])=={'state','window_coverage_state','last_successful_update_at_utc','lag_seconds'}
    public=json.dumps(value)
    for private in (MAC,'www.youtube.com','edge_id','source_observation_ref','matched_rule_id','10.73.0.7'):
        assert private not in public
    assert tuple(lane.repo.connection.iterdump())==before


@pytest.mark.parametrize('seconds,mat,recent,last',[(11,'lagging',True,True),(121,'unavailable',True,True),(3601,'unavailable',False,True),(86401,'unavailable',False,False)])
def test_worker_outage_and_cutoff_without_write(lane,seconds,mat,recent,last):
    lane.worker.cycle()
    result=read(lane,ni_format_utc(ni_timestamp(AT,canonical=True)+timedelta(seconds=seconds)))
    assert result.materialization.state==mat
    assert bool(result.recent_services)==recent and (result.last_service_observation is not None)==last
    assert result.availability_state=='degraded'
    if last:assert result.evidence_state=='supported_results_present'
    else:assert result.evidence_state=='materialization_incomplete'


def test_no_result_incomplete_never_sufficient_negative(lane):
    lane.projection.history=()
    lane.worker.cycle()
    result=read(lane)
    assert result.evidence_state=='identity_pending' and result.materialization.window_coverage_state=='unknown'
    assert result.last_service_observation is None


def test_exact_mac_conflict_no_reassignment(lane):
    lane.worker.cycle()
    with pytest.raises(ServiceUnavailable):read(lane,mac='AA:BB:CC:DD:EE:FF')
    assert read(lane,site='f'*24).recent_services==()
    assert read(lane,device='10000000-0000-4000-8000-000000000099').recent_services==()


@pytest.mark.parametrize('runtime,expected',[('capacity_halted','capacity_halted'),('blocked_conflict','conflict'),('source_unavailable','unavailable'),('recognition_unavailable','unavailable')])
def test_honest_degradation_preserves_valid_positive(lane,runtime,expected):
    lane.worker.cycle()
    with lane.repo.transaction():lane.repo.runtime(runtime,AT)
    result=read(lane)
    assert result.materialization.state==expected and result.last_service_observation is not None
    assert result.evidence_state=='supported_results_present'


def test_expired_generation_not_published(lane):
    lane.worker.cycle()
    with lane.repo.transaction():lane.repo.connection.execute('UPDATE service_materialization_generations SET publishable_until_utc=?',(AT,))
    result=read(lane)
    assert not result.recent_services and result.last_service_observation is None
    assert result.coverage.recognition_state=='unavailable'
    assert result.evidence_state!='no_supported_result_observed_with_sufficient_coverage'


def test_unavailable_store_no_legacy_fallback(tmp_path):
    service=MaterializedDeviceServiceReadService(str(tmp_path/'missing.sqlite3'),bundle())
    with pytest.raises(ServiceUnavailable):service.get_device_service_summary(SITE,DEVICE,MAC,evaluated_at_utc=AT,deadline=QueryDeadline.after(2))
    assert not (tmp_path/'missing.sqlite3').exists()


def test_four_bounded_product_queries(lane,monkeypatch):
    lane.worker.cycle()
    import app.network_service_recognition.materialized_read_service as module
    original=module.sqlite3.connect
    calls=[]
    def traced(*args,**kwargs):
        connection=original(*args,**kwargs)
        connection.set_trace_callback(calls.append)
        return connection
    monkeypatch.setattr(module.sqlite3,'connect',traced)
    read(lane)
    product=[s for s in calls if s.startswith(('SELECT r.*','SELECT * FROM device_materialization_state'))]
    assert len(product)==4
    assert sum('LIMIT 13' in s for s in product)==1 and sum('LIMIT 1' in s and 'LIMIT 13' not in s for s in product)==1


def test_reader_missing_active_is_unknown(lane):
    result=read(lane)
    assert result.materialization.state=='unavailable' and result.evidence_state=='identity_pending'


def test_safely_evaluated_unknown_is_distinct_from_never_processed(lane):
    from .test_materialization_worker import Source
    lane.worker.source=Source((replace(lane.source,tls=replace(lane.source.tls,sni='unmatched.example')),))
    lane.worker.cycle()
    result=read(lane)
    assert result.identity_binding_state=='authoritative'
    assert result.materialization.window_coverage_state=='complete'
    assert result.evidence_state=='no_supported_result_observed_with_sufficient_coverage'
    assert not result.recent_services and result.last_service_observation is None


def test_inconsistent_rollup_is_not_converted_to_empty_negative(lane):
    lane.worker.cycle()
    lane.repo.connection.execute("UPDATE device_service_rollups SET organization_id='org.wrong'")
    with pytest.raises(ServiceUnavailable):read(lane)
