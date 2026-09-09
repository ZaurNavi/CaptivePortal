from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess


ROOT = Path(__file__).parents[2]
SOURCE = ROOT / "app" / "admin_web" / "static" / "admin.js"


def _node() -> str:
    value = shutil.which("node")
    if value:
        return value
    bundled = (
        Path(os.environ.get("LOCALAPPDATA", ""))
        / "Codex" / "dependencies" / "node" / "bin" / "node.exe"
    )
    assert bundled.exists(), "Node is mandatory for the Device Current frontend gate"
    return str(bundled)


def _legacy_admin_source() -> str:
    source = SOURCE.read_text(encoding="utf-8")
    boundary = source.index("\n(function ()", 1)
    return source[:boundary]


def test_device_current_real_node_fetch_dom_isolation_and_no_overlap(tmp_path):
    harness = r'''
const assert=(value,message)=>{if(!value)throw new Error(message);};
const settle=()=>new Promise((resolve)=>setImmediate(resolve));
class Element {
  constructor(id=null){this.id=id;this.dataset={};this.textContent="";this.hidden=false;this.disabled=false;this.children=[];this.listeners={};this.className="";}
  addEventListener(kind,callback){(this.listeners[kind]??=[]).push(callback);}
  append(...items){this.children.push(...items);}
  prepend(...items){this.children.unshift(...items);}
  replaceChildren(...items){this.children=[...items];}
  querySelector(){return null;}
}
const ids=["admin-page","page-content","page-state","state-title","state-message","refresh-button","pagination","load-more-button","device-current-context","device-current-content","device-current-state","device-current-state-title","device-current-state-message"];
const elements=Object.fromEntries(ids.map((id)=>[id,new Element(id)]));
const site="0123456789abcdef01234567";
const device="10000000-0000-4000-8000-000000000001";
elements["admin-page"].dataset={page:"device",siteId:site,apiBase:`/admin/api/v1/sites/${site}`,deviceId:device};
global.document={getElementById:(id)=>elements[id]||null,createElement:()=>new Element(),hidden:false};
global.window={location:{pathname:"/admin/device",search:""},addEventListener:()=>{},setTimeout,clearTimeout};
const historical={result:{identity:{canonical_mac:"02:00:00:00:00:01",device_type:"phone",site_first_seen_at:"x",site_last_seen_at:"y",site_snapshot_count:1,site_visit_count:1},latest_snapshot:{active:true},latest_client_observation:{observed_at:"old"},recent_visits:[]}};
const current={result:{contract_version:"admin.device.current.v1",site_id:site,device_id:device,evaluated_at_utc:"2026-09-08T16:00:00.000Z",scope:{scope_type:"client_ssid_allowlist",site_id:site,ssids:["Zefer_Parki"]},current_state:{presence_status:"online",presence_reason:"present_in_fresh_complete_scope",snapshot:{cycle_id:"cycle-a",observed_at:"2026-09-08T16:00:00.000Z",capture_finished_at:"2026-09-08T16:00:00.000Z",age_seconds:0,freshness_status:"fresh",freshness_reason:"within_freshness_window",complete:true},authorization:{classification:"authorized",reason:"current_row"},client:{client_mac:"02:00:00:00:00:01",ip:"192.0.2.1",ssid:"Zefer_Parki",ap_name:"AP",ap_mac:"AA:BB:CC:DD:EE:FF",radio_id:1,band:"5GHz",channel:44,rssi:-50,snr:30,controller_uptime:10,controller_traffic_down_bytes:0,controller_traffic_up_bytes:0,controller_traffic_total_bytes:0,active:true,wireless:true}},current_guest_traffic:{applicability:"applicable",applicability_reason:"authorized_current_guest",source_health_status:"healthy",source_health_reason:"within_freshness_window",rate_evidence_status:"complete",current_cycle_id:"cycle-a",baseline_cycle_id:"cycle-b",elapsed_seconds:60,item:{download_mbps:0,upload_mbps:0,total_mbps:0,rate_status:"valid",source_progress_status:"advanced",connection_continuity_status:"proven",continuity_basis:"uptime_progress",download_reason:"valid",upload_reason:"valid",total_reason:"valid"},failure_reason:null}}};
let currentPayload=current;
let historyCalls=0,currentCalls=0,pendingResolve=null,holdCurrent=false,failCurrent=false;
global.fetch=async(url)=>{
  const isCurrent=url.endsWith("/current");
  if(isCurrent){
    currentCalls+=1;
    if(failCurrent)return {ok:false,status:503,headers:{get:()=>null},json:async()=>({error:{code:"source_unavailable"}})};
    if(holdCurrent)await new Promise((resolve)=>{pendingResolve=resolve;});
  }else historyCalls+=1;
  return {ok:true,status:200,headers:{get:()=>null},json:async()=>isCurrent?currentPayload:historical};
};
'''
    assertions = r'''
(async()=>{
  await settle();await settle();
  assert(historyCalls===1&&currentCalls===1,"one independent initial request per endpoint");
  assert(elements["page-content"].children.length>0,"historical Device cards remain visible");
  assert(elements["device-current-content"].children.length===7,"Current groups render through safe DOM");
  holdCurrent=true;
  elements["refresh-button"].listeners.click[0]();
  await settle();
  elements["refresh-button"].listeners.click[0]();
  await settle();
  assert(currentCalls===2,"manual Refresh cannot overlap Current requests");
  assert(historyCalls>=2,"historical refresh remains independent");
  pendingResolve();holdCurrent=false;await settle();await settle();
  failCurrent=true;
  elements["refresh-button"].listeners.click[0]();
  await settle();await settle();
  assert(elements["page-content"].children.length>0,"Current failure does not clear history");
  assert(elements["device-current-state-title"].textContent.includes("unavailable"),"Current failure is panel-local");
  failCurrent=false;
  const clone=()=>JSON.parse(JSON.stringify(current));
  const invalidTimestamp=clone();
  invalidTimestamp.result.current_state.presence_status="unknown";
  invalidTimestamp.result.current_state.presence_reason="current_state_unknown";
  invalidTimestamp.result.current_state.snapshot.observed_at=null;
  invalidTimestamp.result.current_state.snapshot.capture_finished_at=null;
  invalidTimestamp.result.current_state.snapshot.age_seconds=null;
  invalidTimestamp.result.current_state.snapshot.freshness_status="unavailable";
  invalidTimestamp.result.current_state.snapshot.freshness_reason="invalid_timestamp";
  invalidTimestamp.result.current_state.authorization={classification:"unknown",reason:"current_state_unknown"};
  invalidTimestamp.result.current_state.client=null;
  invalidTimestamp.result.current_guest_traffic={applicability:"unknown",applicability_reason:"current_state_unknown",source_health_status:null,source_health_reason:null,rate_evidence_status:"not_applicable",current_cycle_id:"cycle-a",baseline_cycle_id:null,elapsed_seconds:null,item:null,failure_reason:null};
  currentPayload=invalidTimestamp;
  elements["refresh-button"].listeners.click[0]();
  await settle();await settle();
  assert(elements["device-current-content"].children.length===7,"safe invalid_timestamp shape renders");
  assert(elements["device-current-state-title"].textContent.includes("limited"),"invalid_timestamp remains semantic");

  const invalidSourceScope=JSON.parse(JSON.stringify(invalidTimestamp));
  invalidSourceScope.result.current_state.snapshot.freshness_reason="invalid_source_scope";
  currentPayload=invalidSourceScope;
  elements["refresh-button"].listeners.click[0]();
  await settle();await settle();
  assert(elements["device-current-content"].children.length===7,"sanitized invalid_source_scope renders");
  assert(elements["device-current-state-title"].textContent.includes("limited"),"invalid_source_scope remains semantic");

  async function expectRejected(mutator,message){
    const candidate=clone();
    mutator(candidate.result);
    currentPayload=candidate;
    elements["refresh-button"].listeners.click[0]();
    await settle();await settle();
    assert(elements["device-current-content"].children.length===0,message);
    assert(elements["device-current-state-title"].textContent.includes("unavailable"),message);
  }
  await expectRejected((value)=>{value.current_state.presence_reason="current_state_unknown";},"presence pair rejected");
  await expectRejected((value)=>{value.current_state.snapshot.freshness_reason="invalid_timestamp";},"freshness pair rejected");
  await expectRejected((value)=>{value.current_state.authorization.reason="offline";},"authorization pair rejected");
  await expectRejected((value)=>{value.current_guest_traffic.applicability_reason="offline";},"applicability pair rejected");
  await expectRejected((value)=>{value.current_guest_traffic.source_health_reason="newer_degraded_attempt";},"source pair rejected");
  await expectRejected((value)=>{value.current_guest_traffic.baseline_cycle_id=null;},"baseline elapsed mismatch rejected");
  await expectRejected((value)=>{value.current_guest_traffic.current_cycle_id="cycle-other";},"cycle mismatch rejected");
  await expectRejected((value)=>{
    const traffic=value.current_guest_traffic;
    traffic.failure_reason="query_deadline";
    traffic.item=null;traffic.rate_evidence_status=null;
    traffic.source_health_status="healthy";traffic.source_health_reason=null;
    traffic.baseline_cycle_id=null;traffic.elapsed_seconds=null;
  },"technical failure null shape enforced");
  await expectRejected((value)=>{value.current_state.client.controller_traffic_total_bytes=-1;},"negative byte counter rejected");
  await expectRejected((value)=>{value.current_state.client.controller_traffic_total_bytes=1.5;},"fractional byte counter rejected");
  await expectRejected((value)=>{value.current_state.snapshot.observed_at="2026-02-30T16:00:00.000Z";},"calendar-invalid timestamp rejected");
  await expectRejected((value)=>{value.current_state.snapshot.capture_finished_at="2026-09-08T15:59:59.999Z";},"reversed normal interval rejected");
  console.log("DEVICE_CURRENT_FRONTEND_OK");
})().catch((error)=>{console.error(error);process.exitCode=1;});
'''
    probe = tmp_path / "device-current-frontend.js"
    probe.write_text(harness + _legacy_admin_source() + assertions, encoding="utf-8")
    completed = subprocess.run(
        [_node(), str(probe)], cwd=ROOT, capture_output=True, text=True,
        timeout=30, check=False, env={**os.environ, "NODE_NO_WARNINGS": "1"},
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "DEVICE_CURRENT_FRONTEND_OK" in completed.stdout


def test_device_current_static_contract_has_no_polling_or_unsafe_dom():
    source = _legacy_admin_source()
    current = source.split("async function loadDeviceCurrent()", 1)[1]
    current = current.split("\n  function observationRow", 1)[0]
    assert "setTimeout" not in current
    assert "setInterval" not in current
    assert "innerHTML" not in current
    assert "CaptivPortalTrafficCoordinator" not in current
    assert "/current`" in current
