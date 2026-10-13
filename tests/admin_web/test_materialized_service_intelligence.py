from dataclasses import replace
from datetime import datetime
import pytest
from app.admin_web.config import admin_web_config_from_settings,AdminWebConfigError
from app.network_service_recognition.materialized_read_service import MaterializedDeviceServiceReadService
from tests.network_service_recognition.test_materialization_worker import lane
from tests.network_service_recognition.support import bundle,AT
from app.network_metadata.validation import ni_timestamp
from .conftest import enabled_settings,login,SITE_ID
from .test_device_service_intelligence import service_app,PATH


@pytest.mark.parametrize('mode',['off','shadow','serve'])
def test_closed_mode_and_no_second_product_flag(mode):
    value=admin_web_config_from_settings(enabled_settings(network_service_materialization_mode=mode))
    assert value.network_service_materialization_mode==mode
    assert not value.device_service_intelligence_enabled


@pytest.mark.parametrize('mode',['Serve','on',True,None,0])
def test_invalid_modes_fail_closed(mode):
    with pytest.raises(AdminWebConfigError):admin_web_config_from_settings(enabled_settings(network_service_materialization_mode=mode))


def test_real_materialized_auth_api_without_upstream(service_app,lane,monkeypatch,record_property):
    lane.worker.cycle()
    runtime=service_app.extensions['admin_web_runtime']
    runtime.config=replace(runtime.config,network_service_materialization_mode='serve')
    runtime.query_service._config=runtime.config
    runtime.query_service._service_intelligence=MaterializedDeviceServiceReadService(lane.repo.db_path,bundle())
    import app.admin_web.query_service as queries
    class FixedDateTime(datetime):
        @classmethod
        def now(cls,tz=None):return ni_timestamp(AT,canonical=True)
    monkeypatch.setattr(queries,'datetime',FixedDateTime)
    # Blueprint captures its own config, so bind a fresh instance like runtime startup.
    import logging
    from flask import Flask
    from app.admin_web.routes import create_admin_web_blueprint
    app=Flask(__name__);app.config['TESTING']=True
    app.register_blueprint(create_admin_web_blueprint(runtime,logger=logging.getLogger('materialization_test')))
    app.extensions['admin_web_runtime']=runtime
    client=app.test_client();login(client)
    response=client.get(PATH,base_url='https://localhost')
    assert response.status_code==200
    assert response.json['api_version']=='admin.device.service-intelligence.v3'
    assert response.json['result']['schema_version']==3 and response.json['result']['recent_services'][0]['service_id']=='service.youtube'
    assert len(response.data)<16384 and response.headers['Cache-Control']=='no-store'
    assert client.get(PATH+'?anything=1',base_url='https://localhost').json['api_version']=='admin.device.service-intelligence.v3'
    import time,json
    times=[]
    for _ in range(20):
        started=time.perf_counter()
        response=client.get(PATH,base_url='https://localhost')
        times.append((time.perf_counter()-started)*1000)
        assert response.status_code==200
    measured=sorted(times)
    record_property('authenticated_api_lab_samples',json.dumps({'count':20,'p95_ms':measured[18],'p99_ms':measured[19],'maximum_ms':max(times),'scope':'local Flask test-client authenticated disposable fixture, not production-class browser/network certification'}))
    assert measured[18]<=250 and measured[19]<=500


def test_serve_composition_does_not_parse_upstream_env(monkeypatch,tmp_path):
    import app.network_metadata.config as ni01
    import app.network_metadata_projection.config as ni02b
    from app.admin_web.runtime import create_admin_web_runtime
    from app.settings_control.features import AdminFeaturePlanV1
    from app.settings_control.models import ResolvedSettingsSnapshot
    from .test_device_service_intelligence import enabled_settings
    def forbidden(*a,**kw):pytest.fail('serve_upstream_composition')
    monkeypatch.setattr(ni01,'network_metadata_config_from_env',forbidden)
    monkeypatch.setattr(ni02b,'projection_config_from_env',forbidden)
    values=enabled_settings(web_admin_device_service_intelligence_enabled='true',network_service_materialization_mode='serve',network_service_materialization_db_path=str(tmp_path/'ni04.sqlite3'))
    plan=AdminFeaturePlanV1.from_snapshot(ResolvedSettingsSnapshot(None,values,{},{},{}))
    from types import SimpleNamespace
    import logging
    runtime=create_admin_web_runtime(values,SimpleNamespace(state='active',visit_service=object()),
        SimpleNamespace(repository=SimpleNamespace(config=SimpleNamespace(db_path=tmp_path/'registry.db'))),
        SimpleNamespace(repository=SimpleNamespace(db_path=tmp_path/'visits.db')),
        SimpleNamespace(_repository=SimpleNamespace(db_path=tmp_path/'observations.db')),
        logging.getLogger('serve_composition'),feature_plan=plan)
    assert type(runtime.query_service._service_intelligence) is MaterializedDeviceServiceReadService
    assert runtime.config.network_service_materialization_mode=='serve'
    assert not (tmp_path/'ni04.sqlite3').exists()
