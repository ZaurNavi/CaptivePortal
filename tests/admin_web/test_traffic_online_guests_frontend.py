from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess


ROOT = Path(__file__).parents[2]
SOURCE = ROOT / "app" / "admin_web" / "static" / "admin.js"
TEMPLATE = ROOT / "app" / "admin_web" / "templates" / "admin" / "traffic.html"
START = "/* TRAFFIC_ONLINE_GUESTS_PANEL_START */"
END = "/* TRAFFIC_ONLINE_GUESTS_PANEL_END */"


def _node() -> str:
    found = shutil.which("node")
    if found:
        return found
    bundled = (
        Path(os.environ.get("LOCALAPPDATA", ""))
        / "Codex" / "dependencies" / "node" / "bin" / "node.exe"
    )
    assert bundled.exists(), "Node is mandatory for the Traffic frontend gate"
    return str(bundled)


def _source() -> str:
    text = SOURCE.read_text(encoding="utf-8")
    return text.split(START, 1)[1].split(END, 1)[0]


def _run(tmp_path: Path, body: str) -> str:
    path = tmp_path / "traffic-online-guests-probe.js"
    path.write_text(body, encoding="utf-8")
    completed = subprocess.run(
        [_node(), str(path)], cwd=ROOT, text=True, capture_output=True,
        timeout=30, check=False, env={**os.environ, "NODE_NO_WARNINGS": "1"},
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    return completed.stdout


def test_online_guests_uses_coordinator_and_safe_dom_only():
    source = _source()
    assert "fetch(" not in source
    assert "setTimeout(" not in source and "setInterval(" not in source
    assert "AbortController" not in source
    assert "HistoricalRequestBroker" not in source
    assert "localStorage" not in source and "sessionStorage" not in source
    assert "innerHTML" not in source
    assert 'key:"online-guests-traffic",autoRefresh:true' in source
    assert 'coordinator.refreshPanel("online-guests-traffic",{manual:true})' in source
    template = TEMPLATE.read_text(encoding="utf-8")
    assert template.index("traffic-current-panel") < template.index("traffic-online-guests-panel") < template.index("traffic-history-panel")
    assert "traffic_online_guests_allowed" in template


def test_online_guests_real_node_root_append_format_and_fail_closed(tmp_path):
    harness = r'''
const assert=(v,m)=>{if(!v)throw new Error(m);};
class Element{
  constructor(id){this.id=id;this.dataset={};this.textContent="";this.hidden=false;this.disabled=false;this.children=[];this.listeners={};this.className="";}
  appendChild(child){this.children.push(child);return child;}
  replaceChildren(...children){this.children=children;}
  addEventListener(kind,callback){(this.listeners[kind]??=[]).push(callback);}
}
const ids=["admin-page","traffic-online-guests-panel","traffic-online-guests-state","traffic-online-guests-state-title","traffic-online-guests-state-message","traffic-online-guests-population","traffic-online-guests-population-note","traffic-online-guests-rate-evidence","traffic-online-guests-rate-counts","traffic-online-guests-source-health","traffic-online-guests-source-reason","traffic-online-guests-observed","traffic-online-guests-interval","traffic-online-guests-previous","traffic-online-guests-caption","traffic-online-guests-items","traffic-online-guests-more"];
const elements=Object.fromEntries(ids.map((id)=>[id,new Element(id)]));
elements["admin-page"].dataset={page:"traffic",trafficOnlineGuestsEnabled:"true"};
let registrations=[];let refreshes=[];
global.window={CaptivPortalTrafficCoordinator:{registerPanel:(spec)=>{registrations.push(spec);return true;},refreshPanel:(key,options)=>{refreshes.push({key,options});return Promise.resolve(true);}}};
global.document={getElementById:(id)=>elements[id]||null,createElement:(name)=>new Element(name)};
const clone=(v)=>JSON.parse(JSON.stringify(v));
const site="0123456789abcdef01234567";
const item=(mac,name,download,upload,total)=>({client_mac:mac,name,ssid:"Zefer_Parki",ap_mac:"AA:BB:CC:DD:EE:10",download_mbps:download,upload_mbps:upload,total_mbps:total,source_progress_status:"advanced",connection_continuity_status:"proven",continuity_basis:"uptime_progress",download_reason:"valid",upload_reason:"valid",total_reason:"valid",rate_status:"valid"});
const payload=(items,cursor=null)=>({api_version:"admin.read.v1",site_id:site,result:{metric_version:"network_traffic_online_guest_current_rate.v1",population_method:"fresh_complete_current_state_authorized_guest_scope.v1",rate_method:"current_connection_counter_delta_interval_average.v1",baseline_method:"nearest_previous_complete_same_site_scope_cycle.v1",continuity_method:"omada_controller_connection_progress_v1",connection_boundary_observation:"sampled_current_state_evidence_v1",unit:"Mbps",site_id:site,evaluated_at_utc:"2026-09-02T10:00:00.000Z",current_cycle_id:"current",baseline_cycle_id:"baseline",current_capture_started_at:"2026-09-02T09:59:50.000Z",baseline_capture_started_at:"2026-09-02T09:58:50.000Z",elapsed_seconds:60,status:"ok",source_health_status:"healthy",source_health_reason:"within_freshness_window",rate_evidence_status:"complete",population_complete:true,scoped_client_row_count:2,known_authorized_count:2,unknown_auth_count:0,population_count:2,supported_max_population:10000,rate_valid_count:2,rate_partial_count:0,rate_unavailable_count:0,items},page:{limit:50,returned_count:items.length,next_cursor:cursor,sort:"total_rate_desc"}});
'''
    assertions = r'''
(async()=>{
  assert(registrations.length===1,"one registration");
  const spec=registrations[0];assert(spec.key==="online-guests-traffic"&&spec.autoRefresh===true,"canonical registration");
  let url="";const first=payload([item("AA:BB:CC:DD:EE:01","Phone",0,0.000106,0.000106)],"opaque+/=");
  const root=await spec.load({siteId:site,apiBase:`/admin/api/v1/sites/${site}`,requestJson:async(value)=>{url=value;return first;}});
  assert(url.endsWith("/traffic/online-guests/current?limit=50"),"root has no cursor");spec.render(root);
  const firstRow=elements["traffic-online-guests-items"].children[0];
  assert(firstRow.children[3].textContent==="0.00 Mbps","true zero preserved");
  assert(firstRow.children[4].textContent==="<0.001 Mbps","positive small rate never zero");
  assert(elements["traffic-online-guests-more"].hidden===false,"pagination visible");
  elements["traffic-online-guests-more"].listeners.click[0]();
  assert(refreshes.length===1&&refreshes[0].key==="online-guests-traffic","append uses coordinator");
  const second=payload([item("AA:BB:CC:DD:EE:02",null,100.25,2,102.25)],"third");
  const appended=await spec.load({siteId:site,apiBase:`/admin/api/v1/sites/${site}`,requestJson:async(value)=>{url=value;return second;}});
  assert(url.includes("cursor=opaque%2B%2F%3D"),"opaque cursor passed without decoding");spec.render(appended);
  assert(elements["traffic-online-guests-items"].children.length===2,"page appended");
  assert(elements["traffic-online-guests-items"].children[1].children[3].textContent==="100.3 Mbps","large rate formatting");

  const mismatched=payload([],null);mismatched.result.evaluated_at_utc="2026-09-02T10:01:00.000Z";
  elements["traffic-online-guests-more"].listeners.click[0]();let rejected=false;
  try{await spec.load({siteId:site,apiBase:"/x",requestJson:async()=>mismatched});}catch(_error){rejected=true;}
  assert(rejected,"append root mismatch fails closed");
  spec.renderFailure({kind:"invalid",status:400,code:"cursor_expired"});
  assert(elements["traffic-online-guests-items"].children.length===0&&elements["traffic-online-guests-more"].hidden===true,"expired cursor fails closed");

  const retained=[
    {kind:"unavailable",status:0,code:null},
    {kind:"busy",status:429,code:"concurrency_limit"},
    {kind:"unavailable",status:503,code:"source_unavailable"},
    {kind:"timeout",status:503,code:"query_deadline"},
  ];
  for(const failure of retained){spec.render({...root,operation:"replace_root"});spec.renderFailure(failure);assert(elements["traffic-online-guests-items"].children.length===1&&!elements["traffic-online-guests-previous"].hidden,"approved transient demotes");}
  spec.render({...root,operation:"replace_root"});
  spec.renderFailure({kind:"unavailable",status:503,code:"response_too_large"});
  assert(elements["traffic-online-guests-items"].children.length===0,"response too large clears identities");
  assert(elements["traffic-online-guests-more"].hidden===true&&elements["traffic-online-guests-previous"].hidden===true,"response too large clears cursor chain");
  let staleAppendAccepted=true;try{spec.render({...root,operation:"APPEND_CURSOR"});}catch(_error){staleAppendAccepted=false;}
  assert(!staleAppendAccepted,"response too large clears root identity");

  spec.render({...root,operation:"replace_root"});
  spec.renderFailure({kind:"forbidden",status:403,code:"site_forbidden"});
  assert(elements["traffic-online-guests-items"].children.length===0,"forbidden clears identities");
  assert(elements["traffic-online-guests-population"].textContent!=="0 guests","unavailable never fabricates zero");
  console.log("ONLINE_GUESTS_FRONTEND_OK");
})().catch((error)=>{console.error(error);process.exitCode=1;});
'''
    assert "ONLINE_GUESTS_FRONTEND_OK" in _run(tmp_path, harness + _source() + assertions)


def test_online_guests_javascript_syntax():
    completed = subprocess.run(
        [_node(), "--check", str(SOURCE)], cwd=ROOT, text=True,
        capture_output=True, timeout=30, check=False,
    )
    assert completed.returncode == 0, completed.stderr


def test_online_guests_real_coordinator_supersedes_append_and_clears_on_403(tmp_path):
    complete = SOURCE.read_text(encoding="utf-8")
    current_marker = complete.index("/* TRAFFIC_CURRENT_PANEL_START */")
    foundation_start = complete.rfind("(function ()", 0, current_marker)
    foundation = complete[foundation_start:current_marker]
    harness = r'''
const assert=(v,m)=>{if(!v)throw new Error(m);};const settle=()=>new Promise((resolve)=>setImmediate(resolve));
class Element{constructor(id){this.id=id;this.dataset={};this.textContent="";this.hidden=false;this.disabled=false;this.children=[];this.listeners={};this.className="";}appendChild(c){this.children.push(c);return c;}replaceChildren(...c){this.children=c;}addEventListener(k,c){(this.listeners[k]??=[]).push(c);}}
const ids=["admin-page","refresh-button","traffic-global-state","traffic-global-state-title","traffic-global-state-message","traffic-empty-state","traffic-panels","traffic-online-guests-panel","traffic-online-guests-state","traffic-online-guests-state-title","traffic-online-guests-state-message","traffic-online-guests-population","traffic-online-guests-population-note","traffic-online-guests-rate-evidence","traffic-online-guests-rate-counts","traffic-online-guests-source-health","traffic-online-guests-source-reason","traffic-online-guests-observed","traffic-online-guests-interval","traffic-online-guests-previous","traffic-online-guests-caption","traffic-online-guests-items","traffic-online-guests-more"];
const elements=Object.fromEntries(ids.map((id)=>[id,new Element(id)]));const site="0123456789abcdef01234567";
elements["admin-page"].dataset={page:"traffic",trafficEnabled:"true",trafficOnlineGuestsEnabled:"true",siteId:site,apiBase:`/admin/api/v1/sites/${site}`,trafficRefreshSeconds:"60",trafficRequestTimeoutSeconds:"20"};
const documentListeners={};const windowListeners={};global.document={hidden:false,getElementById:(id)=>elements[id]||null,createElement:(name)=>new Element(name),addEventListener:(k,c)=>{(documentListeners[k]??=[]).push(c);}};
let clock=1000;let timerId=0;const timers=new Map();global.performance={now:()=>clock};global.window={location:{origin:"https://localhost"},setTimeout:(c,d)=>{const id=++timerId;timers.set(id,{c,d});return id;},clearTimeout:(id)=>timers.delete(id),addEventListener:(k,c)=>{(windowListeners[k]??=[]).push(c);}};
const item=(mac)=>({client_mac:mac,name:null,ssid:"Guest",ap_mac:null,download_mbps:0,upload_mbps:0,total_mbps:0,source_progress_status:"advanced",connection_continuity_status:"proven",continuity_basis:"uptime_progress",download_reason:"valid",upload_reason:"valid",total_reason:"valid",rate_status:"valid"});
const payload=(items,cursor,at="2026-09-02T10:00:00.000Z")=>({api_version:"admin.read.v1",site_id:site,result:{metric_version:"network_traffic_online_guest_current_rate.v1",population_method:"fresh_complete_current_state_authorized_guest_scope.v1",rate_method:"current_connection_counter_delta_interval_average.v1",baseline_method:"nearest_previous_complete_same_site_scope_cycle.v1",continuity_method:"omada_controller_connection_progress_v1",connection_boundary_observation:"sampled_current_state_evidence_v1",unit:"Mbps",site_id:site,evaluated_at_utc:at,current_cycle_id:"current",baseline_cycle_id:"baseline",current_capture_started_at:"2026-09-02T09:59:50.000Z",baseline_capture_started_at:"2026-09-02T09:58:50.000Z",elapsed_seconds:60,status:"ok",source_health_status:"healthy",source_health_reason:"within_freshness_window",rate_evidence_status:"complete",population_complete:true,scoped_client_row_count:2,known_authorized_count:2,unknown_auth_count:0,population_count:2,supported_max_population:10000,rate_valid_count:2,rate_partial_count:0,rate_unavailable_count:0,items},page:{limit:50,returned_count:items.length,next_cursor:cursor,sort:"total_rate_desc"}});
let resolveAppend;let calls=[];let mode="root";
global.fetch=async(url,options)=>{calls.push({url,options});if(mode==="append"){mode="root2";return await new Promise((resolve)=>{resolveAppend=()=>resolve({ok:true,status:200,headers:{get:()=>null},json:async()=>payload([item("AA:BB:CC:DD:EE:02")],null)});});}if(mode==="forbidden")return{ok:false,status:403,headers:{get:()=>null},json:async()=>({error:{code:"site_forbidden"}})};return{ok:true,status:200,headers:{get:()=>null},json:async()=>payload([item("AA:BB:CC:DD:EE:01")],"opaque")};};
'''
    assertions = r'''
(async()=>{await settle();await settle();assert(calls.length===1,"one initial root");assert(elements["traffic-online-guests-items"].children.length===1,"initial row rendered");
mode="append";elements["traffic-online-guests-more"].listeners.click[0]();await settle();assert(calls.length===2&&calls[1].url.includes("cursor=opaque"),"append started");
elements["refresh-button"].listeners.click[0]();await settle();await settle();assert(calls.length===3&&!calls[2].url.includes("cursor="),"global refresh supersedes append with root");
resolveAppend();await settle();await settle();assert(elements["traffic-online-guests-items"].children.length===1,"late append cannot overwrite root");
mode="forbidden";elements["refresh-button"].listeners.click[0]();await settle();await settle();assert(elements["traffic-online-guests-items"].children.length===0,"403 clears identifying rows");assert(elements["traffic-online-guests-more"].hidden===true,"403 clears cursor");assert(elements["traffic-global-state"].hidden===false,"403 pauses shared Traffic lifecycle");console.log("ONLINE_GUESTS_COORDINATOR_OK");})().catch((error)=>{console.error(error);process.exitCode=1;});
'''
    output = _run(tmp_path, harness + foundation + _source() + assertions)
    assert "ONLINE_GUESTS_COORDINATOR_OK" in output
