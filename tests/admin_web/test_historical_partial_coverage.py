"""Actual opt-in History composition, ACL, legacy and browser regression."""
import copy
import json
import logging
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix

from app.admin_web import create_admin_web_runtime
from app.analytics.historical_traffic import HistoricalTrafficReadService
from app.settings_control.features import AdminFeaturePlanV1
from app.settings_control.models import ResolvedSettingsSnapshot
from tests.analytics.conftest import analytics_stack
from tests.analytics.test_historical_partial_coverage import publish, read, wire, SITE, AT, START, EVALUATED
from .conftest import enabled_settings, login
from .test_traffic_history_frontend import _run_node, _panel_source, _range_context_source

API_SITE = "0123456789abcdef01234567"


def app_for(stack, monkeypatch, *, flag="true"):
    import app.admin_web.query_service as queries
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 1, 1, 12, tzinfo=timezone.utc)
    monkeypatch.setattr(queries, "datetime", Clock)
    settings = enabled_settings(web_admin_traffic_enabled="true", web_admin_traffic_history_enabled="true",
        web_admin_traffic_statistics_enabled="true", web_admin_traffic_peak_enabled="true",
        web_admin_traffic_partial_coverage_enabled=flag, web_admin_traffic_independent_ranges_enabled="true")
    plan = AdminFeaturePlanV1.from_snapshot(ResolvedSettingsSnapshot(None, settings, {}, {}, {}))
    runtime = create_admin_web_runtime(settings,
        SimpleNamespace(state="active", visit_service=object(), historical_traffic_service=HistoricalTrafficReadService(stack.gateway)),
        stack.gateway._registry, stack.gateway._visits, stack.gateway._observations,
        logging.getLogger("history-partial-test"), feature_plan=plan)
    assert runtime.state == "active"
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)
    app.register_blueprint(runtime.blueprint)
    app.extensions["admin_web_runtime"] = runtime
    return app


def url(query="range=24h", site=API_SITE):
    return f"/admin/api/v1/sites/{site}/traffic/history?{query}"


def test_opt_in_history_actual_read_and_legacy_identical(analytics_stack, monkeypatch):
    publish(analytics_stack, site=API_SITE)
    clients = []
    for flag in ("false", "true"):
        c = app_for(analytics_stack, monkeypatch, flag=flag).test_client()
        login(c)
        clients.append(c)
    legacy = [c.get(url(), base_url="https://localhost") for c in clients]
    assert all(r.status_code == 200 for r in legacy)
    assert legacy[0].get_json()["result"] == legacy[1].get_json()["result"]
    assert "partial_coverage" not in legacy[0].get_json()["result"]
    assert clients[0].get(url("range=24h&coverage_mode=partial_v1"), base_url="https://localhost").status_code == 404
    response = clients[1].get(url("range=24h&coverage_mode=partial_v1"), base_url="https://localhost")
    assert response.status_code == 200
    out = response.get_json()["result"]
    assert out["partial_coverage"]["buckets"][0]["total_mbps"] == 21
    assert out["buckets"] == legacy[1].get_json()["result"]["buckets"]
    assert "no-store" in response.headers["Cache-Control"]


def test_history_browser_flag_off_retains_strict_request_and_numbers(analytics_stack, tmp_path):
    from app.admin_web.historical_traffic_serialization import serialize_historical_traffic
    from app.admin_web.traffic_network_ranges import resolve_traffic_network_range
    from app.analytics.validation import parse_utc
    publish(analytics_stack)
    publish(analytics_stack, "strict-a", at="2026-01-01T11:56:00.000Z", result="success", pairs=[(20, 4)])
    publish(analytics_stack, "strict-b", at="2026-01-01T11:59:00.000Z", result="success", pairs=[(20, 4)])
    strict = HistoricalTrafficReadService(analytics_stack.gateway).get_site_history(
        SITE, from_utc=START, to_utc=EVALUATED, evaluated_at_utc=EVALUATED, include_period_statistics=True)
    out = serialize_historical_traffic(strict, SITE,
        resolved_range=resolve_traffic_network_range("24h", parse_utc(EVALUATED, "at")),
        include_period_statistics=True)
    payload = dict(api_version="admin.read.v1", site_id=SITE, result=out)
    assertions = r'''
(async()=>{
 const spec=registrations[0];let requests=[];
 const loaded=await spec.load({siteId:payload.site_id,apiBase:"/site",requestJson:async u=>{requests.push(u);return payload;}});
 assert.equal(requests.length,1);assert(!requests[0].includes("coverage_mode"));
 spec.render(loaded);
 assert.equal(elements["traffic-statistics-average-total"].textContent,"24.00 Mbps");
 assert.equal(elements["traffic-statistics-peak-total"].textContent,"24.00 Mbps");
 assert(!elements["traffic-history-chart-svg"].children.some(x=>x.attributes["data-partial-state"]));
 assert(!elements["traffic-history-state-message"].textContent.includes("partial AP measurements"));
 console.log("LEGACY_HISTORY_FLAG_OFF_OK");
})().catch(e=>{console.error(e);process.exitCode=1;});
'''
    script = NODE_DOM + '\nelements["traffic-history-panel"].dataset.partialCoverage="false";\n'
    script += "const payload=" + json.dumps(payload) + ";\n"
    assert "LEGACY_HISTORY_FLAG_OFF_OK" in _run_node(tmp_path, script + _range_context_source() + _panel_source() + assertions)


@pytest.mark.parametrize("query,code", [("range=24h&coverage_mode=wrong", 400),
    ("range=24h&coverage_mode=", 400), ("range=24h&coverage_mode=partial_v1&coverage_mode=partial_v1", 400),
    ("range=48h&coverage_mode=partial_v1", 400), ("range=7d&coverage_mode=partial_v1", 200),
    ("range=24h&include=statistics,peak&coverage_mode=partial_v1", 200),
    ("range=24h&products=history,statistics,peak&coverage_mode=partial_v1", 200),
    ("range=24h&products=statistics&coverage_mode=partial_v1", 200)])
def test_history_query_gate_and_products(analytics_stack, monkeypatch, query, code):
    publish(analytics_stack, site=API_SITE)
    c = app_for(analytics_stack, monkeypatch).test_client()
    assert c.get(url(query), base_url="https://localhost").status_code == 401
    login(c)
    response = c.get(url(query), base_url="https://localhost")
    assert response.status_code == code
    if code == 200:
        value = response.get_json()["result"]
        assert value["partial_coverage"]["comparison_allowed"] is False
        assert value["comparison_state"] == "unavailable_partial_coverage"
        if "products=statistics" in query:
            assert "buckets" not in value and "period_statistics" in value
    assert c.get(url(query, "b" * 24), base_url="https://localhost").status_code == 403


NODE_DOM = r'''
const assert=require("node:assert/strict");
class Element {
  constructor(id,ns=null){this.id=id;this.namespaceURI=ns;this.dataset={};this.textContent="";this.children=[];this.attributes={};this.listeners={};}
  setAttribute(k,v){this.attributes[k]=String(v);}
  addEventListener(k,f){(this.listeners[k]??=[]).push(f);}
  replaceChildren(...children){this.children=children;}
  appendChild(child){this.children.push(child);}
}
const ids=["admin-page","traffic-history-panel","traffic-history-state","traffic-history-state-title","traffic-history-state-message","traffic-history-applied-range","traffic-history-coverage","traffic-history-watermark","traffic-history-gaps","traffic-history-source-transitions","traffic-history-timezone","traffic-history-chart-svg","traffic-network-range-24h","traffic-network-range-7d",
"traffic-statistics-panel","traffic-statistics-state","traffic-statistics-state-title","traffic-statistics-state-message","traffic-statistics-average-download","traffic-statistics-average-upload","traffic-statistics-average-total","traffic-statistics-peak-download","traffic-statistics-peak-upload","traffic-statistics-peak-total","traffic-statistics-applied-range","traffic-statistics-coverage","traffic-statistics-interval-coverage","traffic-statistics-watermark","traffic-statistics-average-heading","traffic-statistics-peak-heading"];
const elements=Object.fromEntries(ids.map(id=>[id,new Element(id)]));
elements["admin-page"].dataset={page:"traffic",trafficEnabled:"true"};
elements["traffic-history-panel"].dataset={historyEnabled:"true",partialCoverage:"true"};
elements["traffic-statistics-panel"].dataset={statisticsEnabled:"true"};
elements["traffic-history-chart-svg"].namespaceURI="http://www.w3.org/2000/svg";
let registrations=[];
global.window={CaptivPortalTrafficCoordinator:{registerPanel:spec=>registrations.push(spec),refreshPanel:()=>false}};
global.document={getElementById:id=>elements[id]||null,createElementNS:(ns,name)=>new Element(name,ns)};
'''


@pytest.mark.parametrize("case,pairs,message,markers", [
    ("partial", [(10, 1), (5, 1), (3, 1), (None, None)], "Observed partial AP measurements", 2),
    ("direction", [(4, None), (None, 2)], "Observed partial AP measurements", 2),
    ("unmeasured", [(None, None)], "Observed partial AP measurements", 0),
    ("empty", None, "No partial AP measurements were found", 0),
])
def test_real_browser_sparse_overlay_and_exact_statistics_copy(analytics_stack, tmp_path, case, pairs, message, markers):
    if pairs is not None:
        publish(analytics_stack, pairs=pairs)
    publish(analytics_stack, "strict-a", at="2026-01-01T11:56:00.000Z", result="success", pairs=[(20, 4)])
    publish(analytics_stack, "strict-b", at="2026-01-01T11:59:00.000Z", result="success", pairs=[(20, 4)])
    # Presence before range start proves neither continuity nor absence.
    publish(analytics_stack, "prefix", at=START, result="failed", pairs=[(None, None)])
    out = wire(read(analytics_stack, include_period_statistics=True), include_period_statistics=True)
    payload = dict(api_version="admin.read.v1", site_id=SITE, result=out)
    assertions = r'''
(async()=>{
 const spec=registrations[0]; let requested;
 const loaded=await spec.load({siteId:payload.site_id,apiBase:"/site",requestJson:async u=>{requested=u;return payload;}});
 assert(requested.endsWith("&coverage_mode=partial_v1"));
 spec.render(loaded);
 assert(elements["traffic-history-state-message"].textContent.includes(expectedMessage));
 assert(elements["traffic-statistics-average-total"].textContent==="24.00 Mbps");
 assert(elements["traffic-statistics-peak-total"].textContent==="24.00 Mbps");
 assert(elements["traffic-statistics-average-heading"].textContent.startsWith("Average · complete-coverage intervals only"));
 assert(elements["traffic-statistics-peak-heading"].textContent.startsWith("Max observed with complete AP coverage"));
 const chart=elements["traffic-history-chart-svg"];
 const polygons=chart.children.filter(x=>x.id==="polygon");
 assert.equal(polygons.length,expectedMarkers);
 assert(chart.children.some(x=>x.id==="polyline"),"strict evidence remains distinct");
 if(testCase==="partial"){
   assert(polygons[0].attributes["aria-label"].includes("Measured traffic: 21.00 Mbps"));
   assert(polygons[0].attributes["aria-label"].includes("pair coverage 3/4 AP opportunities"));
   assert(polygons[0].attributes["aria-label"].includes("both complete and partial AP measurements"));
 }
 if(testCase==="direction") assert(polygons.every(x=>x.attributes["aria-label"].includes("Combined total unavailable")));
 if(testCase==="unmeasured"){
   const evidence=chart.children.filter(x=>x.attributes["data-partial-state"]==="partial_unmeasured");
   assert.equal(evidence.length,1);assert(evidence[0].attributes["aria-label"].includes("no reliable traffic measurement"));
   assert.equal(evidence[0].attributes.y,"24","no numeric zero point");
 }
 const malformed=structuredClone(payload);malformed.result.partial_coverage.has_partial_measurements=false;
 await assert.rejects(()=>spec.load({siteId:payload.site_id,apiBase:"/site",requestJson:async()=>malformed}));
 console.log("PARTIAL_HISTORY_BROWSER_OK");
})().catch(e=>{console.error(e);process.exitCode=1;});
'''
    script = NODE_DOM + "\nconst payload=" + json.dumps(payload) + ";\n" + (
        f"const expectedMessage={json.dumps(message)}, expectedMarkers={markers}, testCase={json.dumps(case)};\n")
    result = _run_node(tmp_path, script + _range_context_source() + _panel_source() + assertions)
    assert "PARTIAL_HISTORY_BROWSER_OK" in result


@pytest.mark.parametrize("state,reason,qualifier,message", [
    ("unavailable", "overlay_source_unavailable", "partial coverage not verified", "Partial-coverage evidence is unavailable for this period."),
    ("capacity_limited", "overlay_capacity_limited", "partial coverage not fully evaluated", "Partial-coverage evidence exceeded the bounded query limit for this period."),
])
def test_browser_failure_envelope_preserves_strict_numbers(analytics_stack, tmp_path, monkeypatch, state, reason, qualifier, message):
    import sqlite3
    from app.analytics.source_gateway import PartialTrafficCapacityLimited
    publish(analytics_stack, "strict-a", at="2026-01-01T11:56:00.000Z", result="success", pairs=[(20, 4)])
    publish(analytics_stack, "strict-b", at="2026-01-01T11:59:00.000Z", result="success", pairs=[(20, 4)])
    def broken(**kwargs):
        raise (PartialTrafficCapacityLimited() if state == "capacity_limited" else sqlite3.OperationalError("source inaccessible"))
    monkeypatch.setattr(analytics_stack.gateway, "read_partial_ap_traffic_evidence", broken)
    payload = dict(api_version="admin.read.v1", site_id=SITE, result=wire(read(analytics_stack, include_period_statistics=True), include_period_statistics=True))
    assertions = r'''
(async()=>{
 const spec=registrations[0];const loaded=await spec.load({siteId:payload.site_id,apiBase:"/site",requestJson:async()=>payload});spec.render(loaded);
 assert(elements["traffic-history-state-message"].textContent.includes(message));
 assert(elements["traffic-statistics-average-heading"].textContent.endsWith(qualifier));
 assert.equal(elements["traffic-statistics-average-total"].textContent,"24.00 Mbps");
 assert.equal(elements["traffic-statistics-peak-total"].textContent,"24.00 Mbps");
 assert(!elements["traffic-history-chart-svg"].children.some(x=>x.attributes["data-partial-state"]));
 console.log("FAILURE_QUALIFIED_STRICT_OK");
})().catch(e=>{console.error(e);process.exitCode=1;});
'''
    script = NODE_DOM + f"\nconst payload={json.dumps(payload)}, message={json.dumps(message)}, qualifier={json.dumps(qualifier)};\n"
    assert "FAILURE_QUALIFIED_STRICT_OK" in _run_node(tmp_path, script + _range_context_source() + _panel_source() + assertions)


def test_independent_ranges_one_request_includes_null_shares_and_partial_contract(analytics_stack, tmp_path):
    publish(analytics_stack)
    publish(analytics_stack, "strict-a", at="2026-01-01T11:56:00.000Z", result="success", pairs=[(20, 4)])
    publish(analytics_stack, "strict-b", at="2026-01-01T11:59:00.000Z", result="success", pairs=[(20, 4)])
    out = wire(read(analytics_stack, include_period_statistics=True, include_ap_share=True),
               include_period_statistics=True, include_ap_share=True, requested_products=("history", "statistics", "apshare"))
    payload = dict(api_version="admin.read.v1", site_id=SITE, result=out)
    additions = r'''
elements["admin-page"].dataset.trafficIndependentRangesEnabled="true";
window.CaptivPortalTrafficCoordinator.queuePanel=()=>{};
document.createElement=name=>new Element(name);
for(const id of ["traffic-apshare-panel","traffic-apshare-state","traffic-apshare-state-title","traffic-apshare-state-message","traffic-apshare-applied-range","traffic-apshare-population","traffic-apshare-coverage","traffic-apshare-current","traffic-apshare-items",
"traffic-history-range-24h","traffic-history-range-7d","traffic-statistics-range-24h","traffic-statistics-range-7d","traffic-apshare-range-24h","traffic-apshare-range-7d"]){elements[id]=new Element(id);}
elements["traffic-apshare-panel"].dataset.apshareEnabled="true";
'''
    assertions = r'''
(async()=>{
 const spec=registrations[0];let requests=[];
 const loaded=await spec.load({siteId:payload.site_id,apiBase:"/site",requestJson:async u=>{requests.push(u);return payload;}});
 assert.equal(requests.length,1);assert(requests[0].includes("products=history%2Cstatistics%2Capshare&coverage_mode=partial_v1"));
 spec.render(loaded);
 assert(elements["traffic-apshare-state-message"].textContent==="AP share unavailable for the full period because AP coverage is partial.");
 assert(elements["traffic-apshare-items"].children.length>0);
 assert(JSON.stringify(elements["traffic-apshare-items"]).includes("Total Share: —"));
 assert.equal(elements["traffic-statistics-average-total"].textContent,"24.00 Mbps");
 spec.prepareRefresh();
 const malformed=structuredClone(payload);malformed.result.ap_traffic_share.items[0].total_share_fraction=.5;
 await assert.rejects(()=>spec.load({siteId:payload.site_id,apiBase:"/site",requestJson:async()=>malformed}));
 console.log("INDEPENDENT_PARTIAL_HISTORY_OK");
})().catch(e=>{console.error(e);process.exitCode=1;});
'''
    script = NODE_DOM + additions + "\nconst payload=" + json.dumps(payload) + ";\n"
    assert "INDEPENDENT_PARTIAL_HISTORY_OK" in _run_node(tmp_path, script + _panel_source() + assertions)
