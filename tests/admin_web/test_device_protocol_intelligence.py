"""#296 replaces the removed Device rolling window with stored Visit results."""
import logging
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
from flask import Flask

from app.admin_web.config import admin_web_config_from_settings, AdminWebConfigError
from app.admin_web.models import AdminPrincipal
from app.admin_web.query_service import (
    AdminQueryResponse, AdminQueryValidationError, AdminQueryForbidden, AdminQueryNotFound,
    AdminQueryUnavailable, AdminQueryDeadline, AdminQueryBusy,
)
from app.admin_web.routes import create_admin_web_blueprint
from app.admin_web.runtime import create_admin_web_runtime
from app.settings_control.features import AdminFeaturePlanV1
from app.settings_control.models import ResolvedSettingsSnapshot
from .conftest import SITE_ID, enabled_settings, login
from tests.visit_lifecycle.conftest import visit_config, visit_repository, visit_service, make_request
from tests.visit_lifecycle.test_visit_service_delivery import delivery

DEVICE = "10000000-0000-4000-8000-000000000001"
VISIT = "20000000-0000-4000-8000-000000000001"
PATH = f"/admin/api/v2/sites/{SITE_ID}/devices/{DEVICE}/visits/{VISIT}/protocol-intelligence"
OLD_PATH = f"/admin/api/v1/sites/{SITE_ID}/devices/{DEVICE}/protocol-intelligence"


def summary():
    return dict(type="VisitProtocolSummaryV1", schema_version=1, site_id=SITE_ID, device_id=DEVICE,
        visit_id=VISIT, visit_status="open", started_at="2026-10-21T10:00:00.000Z", closed_at=None,
        summary_state="active", protocols=[dict(protocol_id="tls",last_observed_at="2026-10-21T10:01:00.000000Z")],
        last_protocol_observation=dict(protocol_id="tls",last_observed_at="2026-10-21T10:01:00.000000Z"),
        evaluated_at="2026-10-21T10:02:00.000Z",source_coverage="bounded_partial",
        attribution_coverage="current_available",finalized_at=None,partial_reason="bounded_source",
        historical_completeness_claimed=False)


@pytest.fixture
def product_app(admin_app):
    runtime = admin_app.extensions["admin_web_runtime"]
    runtime.config = replace(runtime.config, device_protocol_intelligence_enabled=True)
    runtime.query_service._config = runtime.config
    def forbidden(*a, **k):
        pytest.fail("Visit API must never use Device MAC, Registry, NI02 or live NI03")
    runtime.query_service._devices = SimpleNamespace(get_device=forbidden)
    runtime.query_service._reads = SimpleNamespace(visit_protocol_summary=lambda **kwargs: summary())
    app = Flask(__name__); app.config["TESTING"] = True
    app.register_blueprint(create_admin_web_blueprint(runtime,logger=logging.getLogger("visit-protocol-test")))
    app.extensions["admin_web_runtime"] = runtime
    return app


def test_exact_api_success_headers_and_privacy(product_app):
    client=product_app.test_client();login(client)
    response=client.get(PATH,base_url="https://localhost")
    assert response.status_code==200
    assert set(response.json)=={"api_version","request_id","site_id","result","page"}
    assert response.json["api_version"]=="admin.visit.protocol-intelligence.v1"
    assert response.json["result"]==summary() and response.json["page"] is None
    assert response.headers["Cache-Control"]=="no-store" and response.headers["Pragma"]=="no-cache"
    for private in ("client_mac","peer_ip","edge_id","snapshot_id","attribution_binding_id","sni"):
        assert private not in response.get_data(as_text=True)
    assert client.get(OLD_PATH,base_url="https://localhost").status_code==404


@pytest.mark.parametrize("authenticated,site,device,visit,suffix,body,status,code",[
    (False,SITE_ID,DEVICE,VISIT,"",None,401,"authentication_required"),
    (True,"invalid",DEVICE,VISIT,"",None,400,"invalid_request"),
    (True,"f"*24,DEVICE,VISIT,"",None,403,"site_forbidden"),
    (True,SITE_ID,"invalid",VISIT,"",None,400,"invalid_request"),
    (True,SITE_ID,DEVICE,"invalid","",None,400,"invalid_request"),
    (True,SITE_ID,"ABCD0000-0000-4000-8000-000000000001",VISIT,"",None,400,"invalid_request"),
    (True,SITE_ID,DEVICE,VISIT,"?extra=1",None,400,"invalid_request"),
    (True,SITE_ID,DEVICE,VISIT,"?a=1&a=2",None,400,"invalid_request"),
    (True,SITE_ID,DEVICE,VISIT,"",b"{}",400,"invalid_request"),
    (True,SITE_ID,DEVICE,VISIT,"",None,404,"not_found"),
])
def test_feature_off_preserves_route_gate_precedence_no_read(admin_app,monkeypatch,authenticated,site,device,visit,suffix,body,status,code):
    query=admin_app.extensions["admin_web_runtime"].query_service
    monkeypatch.setattr(query,"visit_protocol_intelligence",lambda *a,**k:pytest.fail("OFF read"))
    client=admin_app.test_client()
    if authenticated:login(client)
    path=f"/admin/api/v2/sites/{site}/devices/{device}/visits/{visit}/protocol-intelligence"
    response=client.get(path+suffix,data=body,base_url="https://localhost")
    assert response.status_code==status and response.json["error"]["code"]==code
    assert response.json["api_version"]=="admin.visit.protocol-intelligence.v1"


def test_capability_denial_precedes_input_and_feature_gate(admin_app,monkeypatch):
    runtime=admin_app.extensions["admin_web_runtime"];original=type(runtime.access_policy).authorize
    monkeypatch.setattr(type(runtime.access_policy),"authorize",lambda self,p,c,s:False if c=="admin.read.visits" else original(self,p,c,s))
    client=admin_app.test_client();login(client)
    response=client.get(PATH.replace(VISIT,"invalid")+"?extra=1",base_url="https://localhost")
    assert response.status_code==403 and response.json["error"]["code"]=="site_forbidden"


@pytest.mark.parametrize("exc,status,code",[(AdminQueryBusy,429,"concurrency_limit"),
    (AdminQueryDeadline,503,"query_deadline"),(AdminQueryUnavailable,503,"source_unavailable"),
    (AdminQueryNotFound,404,"not_found"),(AdminQueryForbidden,403,"site_forbidden"),(RuntimeError,500,"internal_error")])
def test_api_safe_failure_mapping(product_app,monkeypatch,caplog,exc,status,code):
    def fail(*a,**k):raise exc("private-device-sentinel")
    monkeypatch.setattr(product_app.extensions["admin_web_runtime"].query_service,"visit_protocol_intelligence",fail)
    client=product_app.test_client();login(client);response=client.get(PATH,base_url="https://localhost")
    assert response.status_code==status and response.json["error"]["code"]==code
    if status==429:assert response.headers["Retry-After"]=="1"
    assert "private-device-sentinel" not in response.get_data(as_text=True)+caplog.text
    assert DEVICE not in caplog.text


def test_response_cap(product_app,monkeypatch):
    query=product_app.extensions["admin_web_runtime"].query_service
    monkeypatch.setattr(query,"visit_protocol_intelligence",lambda *a,**k:AdminQueryResponse("a"*16385))
    client=product_app.test_client();login(client)
    response=client.get(PATH,base_url="https://localhost")
    assert response.status_code==503 and response.json["error"]["code"]=="response_too_large"


def test_shared_slot_and_exact_visit_ownership_not_device_mac(product_app):
    query=product_app.extensions["admin_web_runtime"].query_service;requested=[]
    query._reads=SimpleNamespace(visit_protocol_summary=lambda **kw:requested.append(kw))
    client=product_app.test_client();login(client)
    for _ in range(query._config.max_concurrent_queries):assert query._slots.acquire(False)
    try:
        response=client.get(PATH,base_url="https://localhost")
        assert response.status_code==429 and requested==[]
    finally:
        for _ in range(query._config.max_concurrent_queries):query._slots.release()
    assert client.get(PATH,base_url="https://localhost").status_code==404
    assert requested[0]["site_id"]==SITE_ID and requested[0]["device_id"]==DEVICE and requested[0]["visit_id"]==VISIT
    with pytest.raises(AdminQueryValidationError):
        query.visit_protocol_intelligence(AdminPrincipal("operator"),SITE_ID,DEVICE,"invalid")


def test_page_composition_visit_cards_only(product_app,admin_app):
    for app,enabled in [(product_app,True),(admin_app,False)]:
        client=app.test_client();login(client)
        for suffix in (f"devices/{DEVICE}","visits"):
            response=client.get(f"/admin/sites/{SITE_ID}/{suffix}",base_url="https://localhost")
            assert response.status_code==200
            assert (b"device_protocol_intelligence.js" in response.data) is enabled
            assert b'id="device-protocol-intelligence"' not in response.data


def test_flag_default_outer_gate_and_registry_independence():
    assert not admin_web_config_from_settings({}).device_protocol_intelligence_enabled
    settings={"web_admin_enabled":"false","web_admin_device_protocol_intelligence_enabled":"true"}
    config=admin_web_config_from_settings(settings)
    assert not config.enabled and config.device_protocol_intelligence_enabled
    plan=AdminFeaturePlanV1.from_snapshot(ResolvedSettingsSnapshot(None,settings,{},{},{}))
    assert plan.composition_settings(settings)["web_admin_device_protocol_intelligence_enabled"]=="true"
    from app.settings_control.definitions import SettingsDefinitionRegistry
    assert len(SettingsDefinitionRegistry().for_domain("features"))==17
    with pytest.raises(AdminWebConfigError):admin_web_config_from_settings({"web_admin_device_protocol_intelligence_enabled":"TRUE"})


@pytest.mark.parametrize("enabled",[False,True])
def test_admin_never_composes_raw_projection_even_when_enabled(monkeypatch,tmp_path,enabled):
    import app.network_metadata_projection.config as configuration
    monkeypatch.setattr(configuration,"projection_config_from_env",lambda:pytest.fail("Admin may only open Visits DB"))
    values=enabled_settings(web_admin_device_protocol_intelligence_enabled="true" if enabled else "false")
    plan=AdminFeaturePlanV1.from_snapshot(ResolvedSettingsSnapshot(None,values,{},{},{}))
    runtime=create_admin_web_runtime(values,SimpleNamespace(state="active",visit_service=object()),
        SimpleNamespace(repository=SimpleNamespace(config=SimpleNamespace(db_path=tmp_path/"r"))),
        SimpleNamespace(repository=SimpleNamespace(db_path=tmp_path/"v")),
        SimpleNamespace(_repository=SimpleNamespace(db_path=tmp_path/"o")),logging.getLogger("ni03"),feature_plan=plan)
    assert runtime.state=="active" and runtime.feature_plan is plan
    assert not hasattr(runtime.query_service,"_protocol_intelligence")
    assert not any(tmp_path.iterdir())


def test_open_visit_background_to_real_readonly_api_no_source_query(product_app,visit_config,visit_repository,visit_service,monkeypatch):
    import hashlib
    import sqlite3
    from app.admin_web.read_gateway import AdminSqlReadGateway
    from tests.visit_lifecycle.test_visit_protocol_materialization import Source, fact, worker, SNAPSHOT
    from app.network_metadata_projection.read_service import DeviceNetworkMetadataReadService
    outcome=visit_service.submit_authorized(make_request(site_id=SITE_ID))
    visit_repository.record_reconciliation_attempt(outcome.visit_id,device_id=DEVICE,initial_snapshot_id=SNAPSHOT,
        attempted_at="2026-08-13T10:00:00.000Z",retry_at="2026-08-13T10:01:00.000Z")
    source=Source();source.facts=[fact("10:00:01"),fact("10:00:02","tls","b"),fact("10:00:03","quic","c")]
    assert worker(visit_config,visit_repository,source).run_protocol_once(now="2026-08-13T10:01:00.000Z")==1
    query=product_app.extensions["admin_web_runtime"].query_service
    query._reads=AdminSqlReadGateway(visit_config.db_path,"absent-observation.sqlite3")
    monkeypatch.setattr(DeviceNetworkMetadataReadService,"read_visit_protocol_snapshot",lambda *a,**k:pytest.fail("HTTP must not query NI02"))
    path=PATH.replace(VISIT,outcome.visit_id);client=product_app.test_client();login(client)
    with sqlite3.connect(visit_config.db_path) as c:c.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    before=hashlib.sha256(Path(visit_config.db_path).read_bytes()).hexdigest()
    response=client.get(path,base_url="https://localhost")
    assert response.status_code==200
    value=response.json["result"]
    assert value["visit_status"]=="open" and len(value["protocols"])==3
    assert value["visit_id"]==outcome.visit_id and value["historical_completeness_claimed"] is False
    assert client.get(path.replace(DEVICE,"90000000-0000-4000-8000-000000000001"),base_url="https://localhost").status_code==404
    assert client.get(path.replace(outcome.visit_id,VISIT),base_url="https://localhost").status_code==404
    assert hashlib.sha256(Path(visit_config.db_path).read_bytes()).hexdigest()==before


def test_same_open_visit_shows_both_materialized_sections_no_http_source_reads(product_app,delivery,visit_repository,visit_service,monkeypatch):
    from app.admin_web.read_gateway import AdminSqlReadGateway
    from tests.visit_lifecycle.test_visit_service_delivery import open_visit,put,evaluated,NOW,DEVICE as SOURCE_DEVICE
    from tests.visit_lifecycle.test_visit_protocol_materialization import Source
    import app.network_service_recognition.materialization_repository as source_module
    source,gen,w=delivery;visit=open_visit(visit_service,visit_repository)
    assert SOURCE_DEVICE==DEVICE
    protocol=Source();protocol.facts=[dict(source_event_family=f,event_at='2026-10-12T14:10:00.000001Z',edge_id=e*64) for f,e in [('dns','a'),('tls','b'),('quic','c')]]
    w.protocol_reader=protocol
    assert w.run_protocol_once(now=NOW)==1
    put(source,gen,evaluated());assert w.run_services_once(now=NOW)==1
    query=product_app.extensions['admin_web_runtime'].query_service
    query._reads=AdminSqlReadGateway(visit_repository.db_path,'absent.sqlite3')
    monkeypatch.setattr(source_module,'read_visit_delivery_page',lambda *a,**k:pytest.fail('Admin GET must not open NI04'))
    client=product_app.test_client();login(client)
    path=PATH.replace(VISIT,visit.visit_id)
    protocols=client.get(path,base_url='https://localhost')
    services=client.get(path.replace('/protocol-intelligence','/recognized-services'),base_url='https://localhost')
    assert protocols.status_code==services.status_code==200
    assert protocols.json['result']['visit_status']==services.json['result']['visit_status']=='open'
    assert len(protocols.json['result']['protocols'])==3
    history=services.json['result'];assert history['type']=='VisitServiceHistoryV1' and history['services'][0]['display_name']=='YouTube'
    assert history['services'][0]['distinct_observation_count']==1 and history['historical_completeness_claimed'] is False
    for secret in ('client_mac','edge_id','source_ref','source_observation_id','binding_seq','sni','www.youtube.com'):
        assert secret not in services.get_data(as_text=True)
    assert client.get(path.replace(DEVICE,'90000000-0000-4000-8000-000000000001').replace('/protocol-intelligence','/recognized-services'),base_url='https://localhost').status_code==404
    assert client.get(path.replace('/protocol-intelligence','/recognized-services')+'?extra=1',base_url='https://localhost').status_code==400
    unauthenticated=product_app.test_client().get(path.replace('/protocol-intelligence','/recognized-services'),base_url='https://localhost')
    assert unauthenticated.status_code==401 and unauthenticated.json['api_version']=='admin.visit.recognized-services.v1'
