"""Opt-in API and browser contract; the default strict path stays separate."""
import copy
import json
import logging
import shutil
import sqlite3
import subprocess
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix

from app.analytics.current_traffic import CurrentTrafficReadService
from app.admin_web.current_traffic_serialization import (
    serialize_partial_current_summary, serialize_partial_current_ap_page, CurrentTrafficSerializationError,
)
from app.admin_web.config import admin_web_config_from_settings, AdminWebConfigError
from app.settings_control.features import AdminFeaturePlanV1
from app.settings_control.models import ResolvedSettingsSnapshot
from app.admin_web import create_admin_web_runtime
from tests.analytics.conftest import analytics_stack
from tests.analytics.test_current_partial_coverage import retained, publish, summary, page, SITE, EVALUATED
from .conftest import enabled_settings, login

API_CYCLE = "10000000-0000-4000-8000-000000000001"


class ClockedTraffic(CurrentTrafficReadService):
    """Only the explicit caller evaluation clock is fixed for disposable data."""
    def get_current_site_traffic(self, site_id, **kwargs):
        return super().get_current_site_traffic(site_id, evaluated_at_utc=EVALUATED, **kwargs)

    def get_current_site_traffic_partial_coverage(self, site_id, **kwargs):
        return super().get_current_site_traffic_partial_coverage(site_id, evaluated_at_utc=EVALUATED, **kwargs)

    def list_current_ap_traffic_partial_coverage(self, site_id, **kwargs):
        return super().list_current_ap_traffic_partial_coverage(site_id, evaluated_at_utc=EVALUATED, **kwargs)


def app_for(retained, *, flag="true"):
    stack, status = retained
    settings = enabled_settings(web_admin_home_live_enabled="true", web_admin_home_traffic_enabled="true",
                                web_admin_traffic_enabled="true", web_admin_traffic_partial_coverage_enabled=flag)
    plan = AdminFeaturePlanV1.from_snapshot(ResolvedSettingsSnapshot(None, settings, {}, {}, {}))
    runtime = create_admin_web_runtime(
        settings, SimpleNamespace(state="active", visit_service=object(), current_traffic_service=ClockedTraffic(stack.gateway)),
        stack.gateway._registry, stack.gateway._visits, stack.gateway._observations, logging.getLogger("partial-traffic-test"),
        feature_plan=plan, current_state_read_service=status,
    )
    assert runtime.state == "active"
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)
    app.register_blueprint(runtime.blueprint)
    return app


@pytest.mark.parametrize("route", ["current-traffic/summary", f"current-traffic/aps?cycle_id={API_CYCLE}", "traffic/current"])
def test_A_T12_explicit_mode_guard_acl_and_dispatch(retained, route):
    publish(retained, cycle_id=API_CYCLE, missing="source_unavailable", fourth="offline")
    app = app_for(retained)
    client = app.test_client()
    path = f"/admin/api/v1/sites/{SITE}/{route}"
    delimiter = "&" if "?" in path else "?"
    assert client.get(path + delimiter + "coverage_mode=partial_v1", base_url="https://localhost").status_code == 401
    assert login(client).status_code == 302
    response = client.get(path + delimiter + "coverage_mode=partial_v1", base_url="https://localhost")
    assert response.status_code == 200
    data = response.get_json()["result"]
    assert data["measurement_state"] == "complete_online_population" and data["traffic"]["total_mbps"] == 21
    for extra in ("coverage_mode=wrong", "coverage_mode=", "coverage_mode=partial_v1&coverage_mode=partial_v1"):
        assert client.get(path + delimiter + extra, base_url="https://localhost").status_code == 400
    forbidden = path.replace(SITE, "b" * 24) + delimiter + "coverage_mode=partial_v1"
    assert client.get(forbidden, base_url="https://localhost").status_code == 403
    disabled = app_for(retained, flag="false").test_client()
    assert login(disabled).status_code == 302
    assert disabled.get(path + delimiter + "coverage_mode=partial_v1", base_url="https://localhost").status_code == 404


def test_A_T12_strict_response_unchanged_and_history_mode_not_admitted(retained):
    publish(retained, result="success")
    clients = []
    for flag in ("false", "true"):
        client = app_for(retained, flag=flag).test_client()
        login(client)
        clients.append(client)
    path = f"/admin/api/v1/sites/{SITE}/current-traffic/summary"
    responses = [c.get(path, base_url="https://localhost").get_json()["result"] for c in clients]
    assert responses[0] == responses[1]
    assert "measurement_state" not in responses[0] and "metric_version" not in responses[0]
    assert responses[0]["traffic"]["total_mbps"] == 24
    for c in clients:
        assert c.get(f"/admin/api/v1/sites/{SITE}/current-traffic/aps?cycle_id=incident&limit=251&coverage_mode=partial_v1", base_url="https://localhost").status_code in (400, 404)
        assert c.get(f"/admin/api/v1/sites/{SITE}/traffic/history?range=24h&coverage_mode=partial_v1", base_url="https://localhost").status_code != 200


@pytest.mark.parametrize("route", ["current-traffic/summary", f"current-traffic/aps?cycle_id={API_CYCLE}", "traffic/current"])
@pytest.mark.parametrize("error", [sqlite3.OperationalError("database is locked"), PermissionError("synthetic-private-status-path")])
def test_R1_P1_status_open_failure_is_safe_partial_200(retained, monkeypatch, route, error):
    publish(retained, cycle_id=API_CYCLE, missing="source_unavailable", fourth="offline")
    app = app_for(retained)
    def fail_open(*, write):
        assert write is False
        raise error
    monkeypatch.setattr(retained[1].repository, "_connect", fail_open)
    client = app.test_client()
    assert login(client).status_code == 302
    path = f"/admin/api/v1/sites/{SITE}/{route}"
    response = client.get(path + ("&" if "?" in path else "?") + "coverage_mode=partial_v1", base_url="https://localhost")
    assert response.status_code == 200
    value = response.get_json()["result"]
    assert value["measurement_state"] == "partial_measured"
    assert value["traffic"]["total_mbps"] == 21
    assert value["status_evidence"]["state"] == "unavailable"
    assert "status_evidence_unavailable" in value["coverage"]["coverage_reasons"]
    assert value["coverage"]["offline_excluded_ap_count"] == 0
    assert str(error) not in response.get_data(as_text=True)


def test_flag_default_and_exact_boolean():
    assert admin_web_config_from_settings(enabled_settings()).traffic_partial_coverage_enabled is False
    assert admin_web_config_from_settings(enabled_settings(web_admin_traffic_partial_coverage_enabled=True)).traffic_partial_coverage_enabled is True
    for invalid in ("yes", "TRUE", "1", " false "):
        with pytest.raises(AdminWebConfigError):
            admin_web_config_from_settings(enabled_settings(web_admin_traffic_partial_coverage_enabled=invalid))


def test_A_T13_templates_deliver_flag_and_current_clock_without_history_modification(retained):
    for flag in ("false", "true"):
        c = app_for(retained, flag=flag).test_client()
        login(c)
        for suffix, hook in (("/", "home-traffic"), ("/traffic", "traffic-current-panel")):
            response = c.get(f"/admin/sites/{SITE}{suffix}", base_url="https://localhost")
            assert response.status_code == 200
            text = response.get_data(as_text=True)
            assert f'data-partial-coverage="{flag}"' in text and text.count(f'id="{hook}"') == 1


@pytest.mark.parametrize("section,key,value", [
    ("traffic", "total_mbps", 0), ("source_selection", "source_mixing_allowed", True),
    ("coverage", "installed_ap_count", 3), ("coverage", "offline_excluded_ap_count", 0),
    ("status_evidence", "state", "unavailable"), ("snapshot", "freshness_status", "unavailable"),
])
def test_new_serializer_rejects_inconsistent_payload(retained, section, key, value):
    publish(retained, missing="source_unavailable", fourth="offline")
    actual = summary(retained)
    bad = dict(getattr(actual, section)) | {key: value}
    with pytest.raises(CurrentTrafficSerializationError):
        serialize_partial_current_summary(replace(actual, **{section: bad}), SITE)


def test_A_T13_real_frontend_validator_labels_and_offline_details(retained, tmp_path):
    publish(retained, missing="source_unavailable", fourth="offline")
    actual = summary(retained)
    wire = {"api_version": "admin.read.v1", "site_id": SITE, "result": serialize_partial_current_summary(actual, SITE)}
    result, metadata = serialize_partial_current_ap_page(page(retained), SITE, cycle_id="incident", limit=100)
    wire_page = {"api_version": "admin.read.v1", "site_id": SITE, "result": result, "page": metadata}
    source = Path("app/admin_web/static/admin.js").read_text(encoding="utf-8")
    script = tmp_path / "partial-current.cjs"
    script.write_text("global.window={};\n" + source + "\nconst wire=" + json.dumps(wire) + ";\nconst wirePage=" + json.dumps(wire_page) + ";\n" + r'''
const api = window.CaptivPortalCurrentPartialCoverage;
const legacy = window.CaptivPortalHomeTrafficTest;
const assert = (v, reason) => {if (!v) throw new Error(reason);};
const clone = (v) => JSON.parse(JSON.stringify(v));
assert(api.summary(wire, wire.site_id), 'real summary accepted');
assert(api.page(wirePage, wire.site_id, wire.result), 'real page accepted');
assert(!legacy.validateTrafficSummary(wire, wire.site_id), 'new DTO never misread by strict validator');
let c = api.copy(wire.result);
assert(c.title === 'Total traffic: 21 Mbps', 'complete online title');
assert(c.coverage === '3 Online / 4 total · 1 Offline excluded', 'online denominator');
assert(c.message === 'All confirmed Online APs are measured.', 'online message');
assert(api.apCopy(wirePage.result.items[3]) === 'Offline · excluded from online traffic scope', 'offline explanation');
const partial = clone(wire.result);
partial.measurement_state = 'partial_measured'; partial.population_scope = 'measured_only';
c = api.copy(partial);
assert(c.title === 'Measured traffic: 21 Mbps' && c.coverage === 'Partial data · 3 of 4 APs measured', 'partial copy');
const complete = clone(wire.result);
complete.measurement_state = 'complete_installed'; complete.coverage.measured_pair_ap_count = 4; complete.traffic.total_mbps = 24;
c = api.copy(complete);
assert(c.title === 'Total traffic: 24 Mbps' && c.coverage === 'Complete AP coverage · 4 of 4 APs measured', 'installed copy');
assert(api.copy(complete, 'stale').title === 'Traffic is stale', 'stale copy');
assert(api.copy(partial, 'unavailable').title === 'No reliable traffic data', 'unavailable copy');
for (const mutate of [r => r.traffic.total_mbps=0, r=>r.source_selection.source_mixing_allowed=true,
    r=>r.status_evidence.state='stale', r=>r.coverage.offline_excluded_ap_count=0,
    r=>r.coverage.coverage_reasons.push('fabricated')]) {
  const b=clone(wire); mutate(b.result); assert(api.summary(b, wire.site_id)===null, 'invalid DTO fail closed');
}
const b=clone(wirePage); b.result.status_evidence.cycle_id='future';
assert(api.page(b,wire.site_id,wire.result)===null, 'page status context pinned');
const missing=clone(wirePage.result.items[3]); missing.coverage_role='missing'; missing.status_classification='online';
assert(api.apCopy(missing)==='Online · traffic measurement unavailable', 'online missing copy');
missing.status_classification='unknown';
assert(api.apCopy(missing)==='Status unknown · traffic measurement unavailable', 'unknown copy');
assert(legacy.formatMbps(0)==='0.00 Mbps' && legacy.formatMbps(null)==='—', 'zero/null');
class Node {
  constructor(tag,text='') {this.tag=tag;this.textContent=text;this.children=[];this.dataset={};this.style={};}
  append(...items) {this.children.push(...items);}
  replaceChildren(...items) {this.children=items;}
}
const node=(tag,cls,text)=>new Node(tag,text||'');
const target=node('div'), footer=node('p');
const roster=wirePage.result.items.map(item=>({...item,product_status_classification:item.status_classification}));
window.CaptivPortalHomeLiveTest.renderAccessPointRoster(node,target,footer,roster,null,false,wirePage.result.items,true,true,legacy.formatMbps);
const texts=n=>[n.textContent,...n.children.flatMap(texts)];
assert(texts(target.children[3]).includes('Offline · excluded from online traffic scope'),'real roster offline text');
assert(texts(target.children[3]).filter(t=>t==='—').length===3,'real roster missing directions not zero');
''', encoding="utf-8")
    node = shutil.which("node")
    assert node, "Node is required for this focused browser contract"
    completed = subprocess.run([node, str(script)], capture_output=True, text=True)
    assert completed.returncode == 0, completed.stdout + completed.stderr


@pytest.mark.parametrize("flag", [False, True])
def test_current_panel_uses_coordinator_opt_in_and_server_measurement_state(retained, tmp_path, flag):
    publish(retained, missing="source_unavailable" if flag else None, fourth="offline" if flag else "online", result="partial" if flag else "success")
    if flag:
        result = serialize_partial_current_summary(summary(retained), SITE)
    else:
        from app.admin_web.current_traffic_serialization import serialize_current_traffic_summary
        result = serialize_current_traffic_summary(ClockedTraffic(retained[0].gateway).get_current_site_traffic(SITE, fresh_max_age_seconds=90, stale_max_age_seconds=180, max_ap_skew_seconds=60), SITE)
    source = Path("app/admin_web/static/admin.js").read_text(encoding="utf-8")
    helper = source.split("/* CURRENT_PARTIAL_COVERAGE_START */", 1)[1].split("/* CURRENT_PARTIAL_COVERAGE_END */", 1)[0]
    panel = source.split("/* TRAFFIC_CURRENT_PANEL_START */", 1)[1].split("/* TRAFFIC_CURRENT_PANEL_END */", 1)[0]
    script = tmp_path / "partial-panel.cjs"
    setup = r'''
const elements=new Map();
const ids=['admin-page','traffic-current-panel','traffic-current-state','traffic-current-state-title','traffic-current-state-message','traffic-current-download','traffic-current-upload','traffic-current-total','traffic-current-source','traffic-current-freshness','traffic-current-coverage','traffic-current-updated'];
ids.forEach(id=>elements.set(id,{dataset:{},textContent:''}));
elements.get('admin-page').dataset={page:'traffic',trafficEnabled:'true'};
const registered=[];
global.window={CaptivPortalTrafficCoordinator:{registerPanel:s=>registered.push(s)}};
global.document={getElementById:id=>elements.get(id)||null};
'''
    assertions = r'''
(async()=>{
 if (registered.length!==1) throw new Error('one existing coordinator registration');
 let url;
 const spec=registered[0];
 const value=await spec.load({apiBase:'/site',siteId:wire.site_id,requestJson:async u=>{url=u;return wire;}});
 if (url !== '/site/traffic/current'+(flag?'?coverage_mode=partial_v1':'')) throw new Error('opt-in request');
 spec.render(value);
 if (elements.get('traffic-current-total').textContent!==(flag?'21.00 Mbps':'24.00 Mbps')) throw new Error('rendered backend total');
 if (flag && (elements.get('traffic-current-state-title').textContent!=='Total traffic: 21 Mbps'
   || elements.get('traffic-current-coverage').textContent!=='3 Online / 4 total · 1 Offline excluded')) throw new Error('real renderer exact copy');
})().catch(e=>{console.error(e);process.exitCode=1;});
'''
    script.write_text(setup + "\nconst flag=" + json.dumps(flag) + ";\nconst wire=" + json.dumps({"api_version": "admin.read.v1", "site_id": SITE, "result": result})
                      + ";\nelements.get('traffic-current-panel').dataset.partialCoverage=String(flag);\n" + helper + panel + assertions, encoding="utf-8")
    completed = subprocess.run([shutil.which("node"), str(script)], capture_output=True, text=True)
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_A_T15_protected_non_history_js_blocks_are_byte_identical_to_baseline():
    candidate = Path("app/admin_web/static/admin.js").read_text(encoding="utf-8")
    baseline = subprocess.run(["git", "show", "e8061de9fbd6da8be5cd269779070a4db4d59d64:app/admin_web/static/admin.js"], capture_output=True, text=True, encoding="utf-8", check=True).stdout
    for marker in ("TRAFFIC_NETWORK_RANGE_CONTEXT", "TRAFFIC_ONLINE_GUESTS_PANEL", "TRAFFIC_COMPLETED_SESSIONS_PANEL", "TRAFFIC_EVIDENCE_PANEL"):
        segment = lambda text: text.split(f"/* {marker}_START */", 1)[1].split(f"/* {marker}_END */", 1)[0]
        assert segment(candidate) == segment(baseline), marker
