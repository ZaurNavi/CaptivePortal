"""R2 list-only presentation and independent Site inventory contracts."""

from dataclasses import replace
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import sqlite3
import subprocess

import pytest

from app.admin_web.device_fingerprint_presentation import DeviceFingerprintPresentationService, present_classification
from app.admin_web.device_gateway import AdminDeviceInventorySummary, AdminDeviceIntegrityError
from app.admin_web.models import AdminPrincipal
from app.admin_web.query_service import AdminQueryForbidden, AdminQueryIntegrityUnavailable, AdminQueryUnavailable
from app.common.device_type import normalize_device_type_key
from app.device_fingerprint.artifact_content import make_artifact_content
from app.device_fingerprint.classification_read import ClassificationReadRecord
from .conftest import SITE_ID, login
from .test_admin_ui_frontend import NODE
from .test_device_fingerprint_presentation import retained, shaped, ProductionReader
from .test_device_gateway import _databases, _gateway, _snapshot, _visit, _deadline, SITE, OTHER_SITE
from .test_query_service import _service, _device_list_context_service, DeviceListCurrentSource

ROOT = Path(__file__).parents[2]


@pytest.mark.parametrize("canonical", ["smartphone", "tablet", "laptop"])
def test_compact_type_resolved_exact_machine_identity(retained, canonical):
    record = shaped(retained)
    payload = record.result.semantic_payload
    payload["device_class_result"]["canonical_value_id"] = canonical
    result = make_artifact_content("ClassificationResult", payload)
    record = ClassificationReadRecord(replace(record.core, classification_result_id=result.artifact_id,
                                              classification_result_digest=result.content_sha256), result)
    assert present_classification(record).compact_type() == {
        "state": "classified", "status": "resolved", "canonical_value_id": canonical, "value": canonical.title()}


@pytest.mark.parametrize("status", ["unknown", "insufficient_evidence", "conflicting_evidence", "recognized_out_of_scope"])
def test_compact_type_unresolved_preserves_status(retained, status):
    assert present_classification(shaped(retained, status)).compact_type() == {
        "state": "classified", "status": status, "canonical_value_id": None, "value": "Unknown"}


def test_unsupported_resolved_type_uses_fingerprint_fail_soft_path(retained):
    record = shaped(retained)
    payload = record.result.semantic_payload
    payload["device_class_result"]["canonical_value_id"] = "desktop"
    result = make_artifact_content("ClassificationResult", payload)
    record = ClassificationReadRecord(replace(record.core, classification_result_id=result.artifact_id,
                                              classification_result_digest=result.content_sha256), result)
    reader = ProductionReader(record)
    value = DeviceFingerprintPresentationService(reader).get_many(SITE_ID, ("02:00:00:00:00:01",))
    assert value["02:00:00:00:00:01"].compact_type() == {
        "state": "unavailable", "status": None, "canonical_value_id": None, "value": "—"}


@pytest.mark.parametrize("context", [False, True])
@pytest.mark.parametrize("status", [None, "resolved", "unknown", "conflicting_evidence"])
def test_devices_one_site_safe_batch_for_both_page_paths(retained, context, status):
    query = (_device_list_context_service(current=DeviceListCurrentSource())[0] if context else _service()[0])
    reader = ProductionReader(shaped(retained, status) if status else None)
    query._fingerprint = DeviceFingerprintPresentationService(reader)
    response = query.list_devices(AdminPrincipal("operator"), SITE_ID, limit=1, mac="02-00-00-00-00-01")
    item = response.result["items"][0]
    assert reader.calls == [(SITE_ID, (item["canonical_mac"],))]
    assert item["fingerprint_type"] == present_classification(reader.record).compact_type()
    assert item["fingerprint_platform"] == present_classification(reader.record).compact_platform()
    assert item["platform_presentation"] == {"source": "controller", "key": "phone", "value": "phone"}
    assert response.page["limit"] == 1
    with pytest.raises(AdminQueryForbidden):
        query.list_devices(AdminPrincipal("operator"), "f" * 24)
    assert len(reader.calls) == 1


def test_inventory_empty_and_exact_site_population(tmp_path):
    paths = _databases(tmp_path)
    gateway = _gateway(paths)
    args = dict(site_id=SITE, today_start_utc="2026-10-05T20:00:00.000Z", evaluated_at_utc="2026-10-06T12:00:00.000Z", deadline=_deadline())
    assert gateway.device_inventory_summary(**args) == AdminDeviceInventorySummary(0, 0)
    _snapshot(paths[0], device_id="snapshot", mac="02:00:00:00:00:01", captured_at="2026-10-05T20:00:00.000Z")
    _visit(paths[1], device_id="visit", mac="02:00:00:00:00:02", started_at="2026-10-06T12:00:00.000Z")
    _snapshot(paths[0], device_id="both", mac="02:00:00:00:00:03", captured_at="2026-10-06T01:00:00.000Z")
    _visit(paths[1], device_id="both", mac="02:00:00:00:00:03", started_at="2026-10-05T19:59:59.999Z")
    _snapshot(paths[0], device_id="other-site", mac="02:00:00:00:00:04", captured_at="2026-10-06T01:00:00.000Z", site_id=OTHER_SITE)
    _visit(paths[1], device_id="future", mac="02:00:00:00:00:05", started_at="2026-10-06T12:00:00.001Z")
    with sqlite3.connect(paths[0]) as connection:
        connection.execute("INSERT INTO visitor_devices VALUES ('global-only', '02:00:00:00:00:06')")
    assert gateway.device_inventory_summary(**args) == AdminDeviceInventorySummary(4, 2)
    assert gateway.device_inventory_summary(**(args | {"site_id": OTHER_SITE})) == AdminDeviceInventorySummary(1, 1)
    assert gateway.list_devices(site_id=SITE, limit=1, canonical_mac="02:00:00:00:00:01", deadline=_deadline()).items[0].device_id == "snapshot"
    assert gateway.device_inventory_summary(**args) == AdminDeviceInventorySummary(4, 2)


@pytest.mark.parametrize("controller,status,platform,source,value,key", [
    ("Android", "resolved", "windows", "controller", "Android", "android"),
    ("Unknown", "resolved", "android", "fingerprint", "Android", "android"),
    (None, "resolved", "android", "fingerprint", "Android", "android"),
    ("Windows", "resolved", "android", "controller", "Windows", "windows"),
    (None, "unknown", "android", "none", "Unknown", None),
    (None, None, "android", "none", "—", None),
    ("Unknown", None, "android", "none", "Unknown", None),
    (" Android ", "resolved", "windows", "controller", " Android ", "android"),
    *[(name, "resolved", "android", "controller", name, name)
      for name in ("other", "generic", "n/a", "unavailable", "undefined", "phone", "mobile")],
])
def test_devices_effective_platform_preserves_controller_and_exact_precedence(retained, controller, status, platform, source, value, key):
    query, *_ = _service()
    reader = ProductionReader(shaped(retained, status, platform=platform) if status else None)
    query._fingerprint = DeviceFingerprintPresentationService(reader)
    item = {"canonical_mac": "02:00:00:00:00:01", "device_type": controller,
            "device_type_key": normalize_device_type_key(controller)}
    query._enrich_device_fingerprints(SITE_ID, [item])
    assert item["device_type"] == controller
    assert item["platform_presentation"] == {"source": source, "value": value, "key": key}
    assert reader.calls == [(SITE_ID, (item["canonical_mac"],))]


@pytest.mark.parametrize("count,sizes", [(0, []), (100, [100]), (250, [250]), (251, [250, 1]), (500, [250, 250])])
def test_techlead_refined_large_page_enrichment_is_at_most_two_bounded_batches(count, sizes):
    query, *_ = _service()
    reader = ProductionReader(None)
    query._fingerprint = DeviceFingerprintPresentationService(reader)
    items = [{"canonical_mac": f"02:00:00:00:{i // 256:02X}:{i % 256:02X}", "device_type": None, "device_type_key": None} for i in range(count)]
    query._enrich_device_fingerprints(SITE_ID, items)
    assert [len(macs) for site, macs in reader.calls] == sizes
    assert all(site == SITE_ID for site, macs in reader.calls)
    assert {mac for site, macs in reader.calls for mac in macs} == {item["canonical_mac"] for item in items}
    assert all(item["fingerprint_type"]["state"] == "no_result" for item in items)


def test_inventory_conflicting_identity_is_not_a_numeric_zero(tmp_path):
    paths = _databases(tmp_path)
    _snapshot(paths[0], device_id="conflict", mac="02:00:00:00:00:01", captured_at="2026-10-06T01:00:00.000Z")
    _visit(paths[1], device_id="conflict", mac="02:00:00:00:00:02", started_at="2026-10-06T01:00:00.000Z")
    with pytest.raises(AdminDeviceIntegrityError):
        _gateway(paths).device_inventory_summary(site_id=SITE, today_start_utc="2026-10-06T00:00:00.000Z", evaluated_at_utc="2026-10-06T12:00:00.000Z", deadline=_deadline())


@pytest.mark.parametrize("zone,instant,midnight", [
    ("Asia/Baku", "2026-10-06T00:30:00+00:00", "2026-10-05T20:00:00.000Z"),
    ("America/New_York", "2026-03-08T12:00:00+00:00", "2026-03-08T05:00:00.000Z"),
    ("America/New_York", "2026-11-01T12:00:00+00:00", "2026-11-01T04:00:00.000Z"),
])
def test_inventory_reuses_registry_iana_zone_and_one_evaluation(monkeypatch, zone, instant, midnight):
    query, gateway, *_ = _service()
    query._inventory_timezone_name = zone
    calls = []
    gateway.device_inventory_summary = lambda **kwargs: calls.append(kwargs) or AdminDeviceInventorySummary(3, 2)
    class Clock(datetime):
        @classmethod
        def now(cls, tz):
            assert tz is timezone.utc
            return cls.fromisoformat(instant)
    monkeypatch.setattr("app.admin_web.query_service.datetime", Clock)
    result = query.device_inventory_summary(AdminPrincipal("operator"), SITE_ID).result
    assert set(result) == {"total_devices", "new_devices_today", "timezone", "evaluated_at_utc"}
    assert result["timezone"] == zone and result["total_devices"] == 3 and result["new_devices_today"] == 2
    assert len(calls) == 1 and calls[0]["today_start_utc"] == midnight
    assert calls[0]["evaluated_at_utc"] == result["evaluated_at_utc"] and calls[0]["deadline"] is not None
    with pytest.raises(AdminQueryForbidden):
        query.device_inventory_summary(AdminPrincipal("operator"), "f" * 24)
    assert len(calls) == 1


@pytest.mark.parametrize("value", [AdminDeviceInventorySummary(-1, 0), AdminDeviceInventorySummary(1, 2), AdminDeviceInventorySummary(True, 0)])
def test_inventory_invalid_counter_fails_closed(value):
    query, gateway, *_ = _service()
    query._inventory_timezone_name = "Asia/Baku"
    gateway.device_inventory_summary = lambda **kwargs: value
    with pytest.raises(AdminQueryIntegrityUnavailable):
        query.device_inventory_summary(AdminPrincipal("operator"), SITE_ID)


def test_inventory_unknown_timezone_is_unavailable_before_database():
    query, *_ = _service()
    with pytest.raises(AdminQueryUnavailable):
        query.device_inventory_summary(AdminPrincipal("operator"), SITE_ID)


@pytest.mark.parametrize("arguments", ["mac=AA:BB:CC:DD:EE:FF", "limit=1", "cursor=x", "timezone=UTC", "unexpected="])
def test_inventory_route_rejects_all_query_arguments(admin_app, arguments):
    client = admin_app.test_client()
    assert login(client).status_code == 302
    response = client.get(f"/admin/api/v1/sites/{SITE_ID}/devices/inventory-summary?{arguments}", base_url="https://localhost")
    assert response.status_code == 400 and response.json["error"]["code"] == "invalid_request"


@pytest.mark.parametrize("name,digest", [
    ("smartphone", "40fc00b7aa66ec1d548956798379cf84fb99312ff0ec4c27bb25fab275480000"),
    ("tablet", "6ebc93d6779dfc10271e8182c858d4969c37c84b2c7c8146bce57ee88df6abb6"),
    ("laptop", "77531c51c7e76ebe29e7e034bb230ab9490c66145ec972c4748543d4917206fb"),
    ("unresolved", "b81ad849966c7aefe19c74ee6f616b0b24f7b2e5d28bef70087b9135cfd05d82"),
    ("no-result", "47c7bd944686d7f70cf8d8332fbcfd7e08398e95890e92c755a6bd9d35f14b6f"),
    ("unavailable", "18e76d5e11bb354d85fa72e2906ddce9223aa6872587c9040230fd34a9fc28b7"),
])
def test_approved_svg_bytes_unchanged(name, digest):
    import xml.etree.ElementTree as ET
    data = (ROOT / f"app/admin_web/static/icons/device-types/type-{name}.svg").read_bytes()
    assert hashlib.sha256(data).hexdigest() == digest
    assert ET.fromstring(data).tag == "{http://www.w3.org/2000/svg}svg"


@pytest.mark.skipif(NODE is None, reason="Node required for frontend contracts")
def test_machine_icons_and_single_ap_roster_dom():
    program = r'''
const fs=require('fs'), vm=require('vm'), assert=require('assert');
global.window={}; vm.runInThisContext(fs.readFileSync(process.argv[1], 'utf8'));
function node(tag, className, text) {return {tag,className,textContent:text,children:[],attributes:{},style:{},append(...xs){this.children.push(...xs)},replaceChildren(...xs){this.children=xs},setAttribute(k,v){this.attributes[k]=v}}}
const types=window.CaptivPortalDeviceTypePresentation;
for (const [id,label] of [['smartphone','Smartphone'],['tablet','Tablet'],['laptop','Laptop']]) {
  const icon=types.icon(node,{state:'classified',status:'resolved',canonical_value_id:id,value:'NOT USED'});
  assert.equal(icon.attributes['aria-label'],label); assert.equal(icon.title,label);
  assert.equal(icon.children[0].src,'/admin/static/icons/device-types/type-'+id+'.svg');
  assert.equal(icon.children[0].width,22); assert.equal(icon.children[0].height,22);
  assert.equal(icon.children[0].alt,''); assert.equal(icon.children[0].attributes['aria-hidden'],'true');
  assert.equal(icon.textContent,undefined);
}
for(const status of ['unknown','insufficient_evidence','conflicting_evidence','recognized_out_of_scope'])
  assert.equal(types.mapping({state:'classified',status,canonical_value_id:null,value:'Unknown'})[0],'type-unresolved.svg');
for(const state of ['no_result','unavailable'])
  assert.equal(types.mapping({state,status:null,canonical_value_id:null,value:'—'})[0], 'type-'+state.replace('_','-')+'.svg');
for(const invalid of [null,{state:'classified',value:'Smartphone'}, {state:'classified',status:'resolved',canonical_value_id:'desktop',value:'Laptop'}]) assert.equal(types.mapping(invalid),null);
const target=node('div'),footer=node('p'), live=window.CaptivPortalHomeLiveTest;
const rows=[{ap_mac:'AA',name:'AP One',product_status_classification:'online'},{ap_mac:'BB',name:'AP Two',product_status_classification:'online'}];
const client={devices_by_ap:[{ap_mac:'AA',client_count:2},{ap_mac:'UNLOADED',client_count:8}],counts:{ap_unknown:3}};
const traffic=[{ap_mac:'AA',name:'DO NOT DUPLICATE',rate_status:'valid',download_mbps:0,upload_mbps:null,total_mbps:0,selected_source:'lan',observed_at:'NOW'}, {ap_mac:'UNLOADED',rate_status:'valid'}];
function render(c,t,enabled=true){live.renderAccessPointRoster(node,target,footer,rows,client,c,traffic,t,enabled,x=>x===null?'—':x+' Mbps')}
render(true,true); assert.equal(target.children.length,2); assert.equal(footer.textContent,'AP Unknown · 3');
assert.equal(target.children[0].children[2].children[1].children[0].style.width,'25%');
assert.equal(target.children[1].children[2].children[0].textContent,'Devices · 0');
assert.deepEqual(target.children[0].children[4].children.map(x=>x.children[0].textContent),['Download ↓','Upload ↑','Total ↓↑']);
assert.deepEqual(target.children[0].children[4].children.map(x=>x.children[1].textContent),['0 Mbps','—','0 Mbps']);
assert.equal(target.children[0].children[5].textContent,'Source LAN · observed NOW');
assert.equal(target.children[1].children[3].textContent,'Traffic · —');
render(false,false); assert.equal(target.children.length,2); assert.equal(footer.hidden,true);
assert.equal(target.children[0].children[2].children[0].textContent,'Devices · —');
assert.equal(target.children[0].children[2].children[1].children.length,0);
render(true,true); render(true,true); assert.equal(target.children.length,2); assert.equal(target.children[0].children.length,6);
render(true,true,false); assert.equal(target.children[0].children.length,3);
'''
    result = subprocess.run([NODE, "-e", program, str(ROOT / "app/admin_web/static/admin.js")], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_list_and_ap_hooks_no_competing_identity_cards():
    home = (ROOT / "app/admin_web/templates/admin/home.html").read_text(encoding="utf-8")
    devices = (ROOT / "app/admin_web/templates/admin/devices.html").read_text(encoding="utf-8")
    source = (ROOT / "app/admin_web/static/admin.js").read_text(encoding="utf-8")
    css = (ROOT / "app/admin_web/static/admin.css").read_text(encoding="utf-8")
    for obsolete in ["live-devices-by-ap", "traffic-ap-title", "traffic-ap-rows", "traffic-ap-more"]:
        assert obsolete not in home
    assert home.index('id="live-ap-unknown"') < home.index('id="live-ap-more"')
    assert devices.index('id="device-search-form"') < devices.index('id="device-inventory-summary"')
    assert "loadMore(\"traffic\")" not in source
    assert "} while (cursor);" in source and "source.generation !== generation || coordinator.pending" in source
    assert "width: 22px; height: 22px;" in css
    assert "104px minmax(220px, 1.1fr) 72px minmax(105px, .5fr)" in css
    assert ".device-row-type-field, .device-row-platform-field, .device-row-activity, .device-row-stats { grid-column: 2 / 4; }" in css


@pytest.mark.skipif(NODE is None, reason="Node required for frontend contracts")
def test_inventory_failure_and_superseded_response_are_card_local():
    program = r'''
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const source=fs.readFileSync(process.argv[1],'utf8');
const start=source.indexOf('  let inventoryGeneration = 0;');
const end=source.indexOf('  async function loadDevices(',start);
const cards=Object.fromEntries(['total','today','state'].map(k=>['device-inventory-'+k,{textContent:''}]));
global.document={getElementById:k=>cards[k]};global.context={apiBase:'/site'};
const pending=[];global.requestJson=url=>{assert.equal(url,'/site/devices/inventory-summary');return new Promise((resolve,reject)=>pending.push({resolve,reject}))};
vm.runInThisContext(source.slice(start,end));
const valid={result:{total_devices:6,new_devices_today:2,timezone:'Asia/Baku',evaluated_at_utc:'2026-10-06T00:00:00.000Z'}};
(async()=>{
const first=loadDeviceInventory();assert.equal(cards['device-inventory-total'].textContent,'—');
pending[0].reject(new Error('unavailable'));await first;
assert.equal(cards['device-inventory-state'].textContent,'Unavailable');
const old=loadDeviceInventory(),fresh=loadDeviceInventory();pending[2].resolve(valid);await fresh;
pending[1].resolve({result:{...valid.result,total_devices:99}});await old;
assert.equal(cards['device-inventory-total'].textContent,'6');assert.equal(cards['device-inventory-today'].textContent,'2');
assert.equal(cards['device-inventory-state'].textContent,'');
const invalid=loadDeviceInventory();pending[3].resolve({result:{...valid.result,new_devices_today:7}});await invalid;
assert.equal(cards['device-inventory-state'].textContent,'Unavailable');
})().catch(e=>{console.error(e);process.exitCode=1});
'''
    result = subprocess.run([NODE, "-e", program, str(ROOT / "app/admin_web/static/admin.js")], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    source = (ROOT / "app/admin_web/static/admin.js").read_text(encoding="utf-8")
    # Only initial configuration and explicit Refresh invoke inventory: filters
    # and pagination call loadDevices only, never refresh these Site counters.
    assert source.count('if (context.page === "devices") loadDeviceInventory();') == 2
    search = source[source.index('const form = document.getElementById("device-search-form")'):]
    assert 'run(() => loadDevices(false))' in search.split('if (context.page === "device")')[0]
    assert "loadDeviceInventory" not in search.split('if (context.page === "device")')[0]
    pagination = source[source.index('loadMoreButton.addEventListener("click"'):]
    assert "loadDeviceInventory" not in pagination.split('if (legacyHealthCoordinatorEnabled())')[0]


@pytest.mark.skipif(NODE is None, reason="Node required for frontend contracts")
def test_traffic_cursor_chain_is_sequential_atomic_and_generation_owned():
    program = r'''
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const source=fs.readFileSync(process.argv[1],'utf8');
const start=source.indexOf('  async function refreshTraffic(generation)');
const end=source.indexOf('  function nextDelay()',start);
global.document={hidden:false};global.coordinator={pending:false};global.stopped=false;
global.trafficEnabled=true;global.trafficBase='/traffic';global.trafficTimeout=1;global.trafficRefresh=1;global.siteId='SITE';
global.sources={traffic:{rows:['old'],generation:1}};
const pending=[],urls=[];global.requestJson=url=>{urls.push(url);return new Promise((resolve,reject)=>pending.push({resolve,reject}))};
global.validateTrafficSummary=x=>x;global.acceptTrafficSummary=(s,v)=>{s.summary=v};
global.renderTrafficSummary=()=>{};global.renderTrafficRows=()=>{};global.trafficPageEligible=()=>true;
global.trafficParams=(s,c)=>new URLSearchParams(c?{cursor:c}:{});
global.validateTrafficPage=x=>x;global.markSuccess=()=>{};global.pageFailureEffect=()=>'';
let failures=0;global.trafficFailure=()=>{failures++;return false};
vm.runInThisContext(source.slice(start,end));
const summary={snapshot:{freshness_status:'fresh'}},page=(mac,cursor)=>({result:{items:[{ap_mac:mac}]},page:{next_cursor:cursor}});
const tick=()=>new Promise(resolve=>setImmediate(resolve));
(async()=>{
let run=refreshTraffic(1);pending.shift().resolve(summary);await tick();
assert.equal(urls.length,2);pending.shift().resolve(page('AA','next'));await tick();
assert.equal(urls.length,3);assert.equal(urls[2],'/traffic/aps?cursor=next');
assert.deepEqual(sources.traffic.rows,['old']);assert.equal(sources.traffic.rowsReady,false);
pending.shift().resolve(page('BB',null));await run;
assert.deepEqual(sources.traffic.rows.map(x=>x.ap_mac),['AA','BB']);assert.equal(sources.traffic.rowsReady,true);
const accepted=sources.traffic.rows;
run=refreshTraffic(2);pending.shift().resolve(summary);await tick();
pending.shift().resolve(page('CC','next'));await tick();sources.traffic.generation=3;
pending.shift().resolve(page('DD',null));await run;assert.equal(sources.traffic.rows,accepted);
run=refreshTraffic(4);pending.shift().resolve(summary);await tick();
pending.shift().resolve(page('EE','next'));await tick();pending.shift().reject(new Error('page failure'));await run;
assert.equal(sources.traffic.rows,accepted);assert.equal(sources.traffic.rowsReady,false);assert.equal(failures,1);
const before=urls.length;trafficEnabled=false;await refreshTraffic(5);assert.equal(urls.length,before);
})().catch(e=>{console.error(e);process.exitCode=1});
'''
    result = subprocess.run([NODE, "-e", program, str(ROOT / "app/admin_web/static/admin.js")], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
