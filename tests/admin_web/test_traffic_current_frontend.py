from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess


ROOT = Path(__file__).parents[2]
SOURCE = ROOT / "app" / "admin_web" / "static" / "admin.js"
START = "/* TRAFFIC_CURRENT_PANEL_START */"
END = "/* TRAFFIC_CURRENT_PANEL_END */"


def _node() -> str:
    value = shutil.which("node")
    if value:
        return value
    bundled = (
        Path(os.environ.get("LOCALAPPDATA", ""))
        / "Codex"
        / "dependencies"
        / "node"
        / "bin"
        / "node.exe"
    )
    assert bundled.exists(), "Node is mandatory for the Traffic frontend gate"
    return str(bundled)


def _panel_source() -> str:
    source = SOURCE.read_text(encoding="utf-8")
    return source.split(START, 1)[1].split(END, 1)[0]


def _run_node(tmp_path: Path, name: str, source: str) -> str:
    probe = tmp_path / name
    probe.write_text(source, encoding="utf-8")
    completed = subprocess.run(
        [_node(), str(probe)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
        env={**os.environ, "NODE_NO_WARNINGS": "1"},
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    return completed.stdout


def test_traffic_current_javascript_syntax_and_lifecycle_ownership():
    completed = subprocess.run(
        [_node(), "--check", str(SOURCE)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    panel = _panel_source()
    assert "fetch(" not in panel
    assert "setTimeout(" not in panel
    assert "setInterval(" not in panel
    assert "AbortController" not in panel
    assert "addEventListener(" not in panel
    assert "localStorage" not in panel and "sessionStorage" not in panel
    assert "innerHTML" not in panel


def test_traffic_current_panel_real_node_validation_and_rendering(tmp_path):
    harness = r'''
const assert = (value, message) => { if (!value) throw new Error(message); };
class Element { constructor(id) { this.id=id; this.dataset={}; this.textContent=""; this.hidden=false; } }
const ids=["admin-page","traffic-current-panel","traffic-current-state","traffic-current-state-title","traffic-current-state-message","traffic-current-download","traffic-current-upload","traffic-current-total","traffic-current-source","traffic-current-freshness","traffic-current-coverage","traffic-current-updated"];
const elements=Object.fromEntries(ids.map((id)=>[id,new Element(id)]));
elements["admin-page"].dataset={page:"traffic",trafficEnabled:"true"};
let registrations=[];
global.window={CaptivPortalTrafficCoordinator:{registerPanel:(spec)=>{registrations.push(spec);return true;}}};
global.document={getElementById:(id)=>elements[id]||null};
'''
    assertions = r'''
const clone=(value)=>JSON.parse(JSON.stringify(value));
const payload={api_version:"admin.read.v1",site_id:"0123456789abcdef01234567",result:{
  traffic:{download_mbps:12.437,upload_mbps:0,total_mbps:12.437,unit:"Mbps"},
  snapshot:{freshness_status:"fresh",selected_source:"wired",selection_reason:"primary_full_coverage",evaluated_at:"2026-08-29T10:00:00.000Z",observed_at:"2026-08-29T09:59:50.000Z"},
  source_selection:{selected_source:"wired",selection_reason:"primary_full_coverage"},
  coverage:{coverage_status:"complete"}
}};
(async()=>{
  assert(registrations.length===1,"panel registers exactly once");
  const spec=registrations[0];
  assert(spec.key==="current-network-throughput"&&spec.autoRefresh===true,"canonical registration");
  let requested=null;
  const result=await spec.load({siteId:payload.site_id,apiBase:`/admin/api/v1/sites/${payload.site_id}`,requestJson:async(url)=>{requested=url;return payload;}});
  assert(requested===`/admin/api/v1/sites/${payload.site_id}/traffic/current`,"coordinator requestJson URL");
  spec.render(result);
  assert(elements["traffic-current-download"].textContent==="12.44 Mbps","download formatting");
  assert(elements["traffic-current-upload"].textContent==="0.00 Mbps","real zero preserved");
  assert(elements["traffic-current-total"].textContent==="12.44 Mbps","backend total displayed");
  assert(elements["traffic-current-source"].textContent==="Wired","wired label");
  assert(elements["traffic-current-state"].dataset.state==="ready","fresh complete ready");

  const partial=clone(payload);partial.result.traffic={download_mbps:0,upload_mbps:12.437,total_mbps:null,unit:"Mbps"};partial.result.coverage.coverage_status="partial";partial.result.snapshot.selected_source="lan";partial.result.snapshot.selection_reason="fallback_partial_coverage";partial.result.source_selection={selected_source:"lan",selection_reason:"fallback_partial_coverage"};
  spec.render(await spec.load({siteId:payload.site_id,apiBase:"/x",requestJson:async()=>partial}));
  assert(elements["traffic-current-download"].textContent==="0.00 Mbps"&&elements["traffic-current-total"].textContent==="—","zero/null formatting");
  assert(elements["traffic-current-source"].textContent==="LAN fallback","LAN label");
  assert(elements["traffic-current-state"].dataset.state==="warning","fresh partial degraded");

  const stale=clone(payload);stale.result.snapshot.freshness_status="stale";
  spec.render(await spec.load({siteId:payload.site_id,apiBase:"/x",requestJson:async()=>stale}));
  assert(elements["traffic-current-state"].dataset.state==="warning","stale degraded");

  const unavailable=clone(payload);unavailable.result.traffic={download_mbps:null,upload_mbps:null,total_mbps:null,unit:"Mbps"};unavailable.result.snapshot.freshness_status="unavailable";unavailable.result.snapshot.selected_source=null;unavailable.result.snapshot.selection_reason="no_complete_snapshot";unavailable.result.snapshot.observed_at=null;unavailable.result.source_selection={selected_source:null,selection_reason:"no_complete_snapshot"};unavailable.result.coverage.coverage_status="none";
  spec.render(await spec.load({siteId:payload.site_id,apiBase:"/x",requestJson:async()=>unavailable}));
  assert(elements["traffic-current-state"].dataset.state==="error","unavailable state");
  assert(elements["traffic-current-download"].textContent==="—"&&elements["traffic-current-source"].textContent==="Source unavailable","unavailable values hidden");

  const malformed=clone(payload);malformed.result.source_selection.selected_source="lan";
  let rejected=false;try{await spec.load({siteId:payload.site_id,apiBase:"/x",requestJson:async()=>malformed});}catch(_error){rejected=true;}
  assert(rejected,"mismatched DTO rejected before render");
  spec.renderFailure({kind:"busy"});
  assert(elements["traffic-current-state"].dataset.state==="error"&&elements["traffic-current-state-title"].textContent.includes("busy"),"panel-local failure");
  console.log("TRAFFIC_CURRENT_PANEL_OK");
})().catch((error)=>{console.error(error);process.exitCode=1;});
'''
    output = _run_node(
        tmp_path,
        "traffic-current-panel-probe.js",
        harness + _panel_source() + assertions,
    )
    assert "TRAFFIC_CURRENT_PANEL_OK" in output


def test_traffic_current_panel_uses_foundation_for_single_initial_execution(tmp_path):
    source = SOURCE.read_text(encoding="utf-8")
    marker_at = source.index(START)
    foundation_at = source.rfind("(function ()", 0, marker_at)
    combined = source[foundation_at:marker_at] + _panel_source()
    harness = r'''
const assert=(value,message)=>{if(!value)throw new Error(message);};
const settle=()=>new Promise((resolve)=>setImmediate(resolve));
class Element{constructor(id){this.id=id;this.dataset={};this.textContent="";this.hidden=false;this.disabled=false;this.listeners={};}addEventListener(kind,callback){(this.listeners[kind]??=[]).push(callback);}}
const ids=["admin-page","refresh-button","traffic-global-state","traffic-global-state-title","traffic-global-state-message","traffic-empty-state","traffic-panels","traffic-current-panel","traffic-current-state","traffic-current-state-title","traffic-current-state-message","traffic-current-download","traffic-current-upload","traffic-current-total","traffic-current-source","traffic-current-freshness","traffic-current-coverage","traffic-current-updated"];
const elements=Object.fromEntries(ids.map((id)=>[id,new Element(id)]));
const site="0123456789abcdef01234567";elements["admin-page"].dataset={page:"traffic",trafficEnabled:"true",siteId:site,apiBase:`/admin/api/v1/sites/${site}`,trafficRefreshSeconds:"60",trafficRequestTimeoutSeconds:"20"};
const documentListeners={};const windowListeners={};global.document={hidden:false,getElementById:(id)=>elements[id]||null,addEventListener:(kind,callback)=>{(documentListeners[kind]??=[]).push(callback);}};
let timerId=0;const timers=new Map();global.window={location:{origin:"https://localhost"},setTimeout:(callback,delay)=>{const id=++timerId;timers.set(id,{callback,delay});return id;},clearTimeout:(id)=>timers.delete(id),addEventListener:(kind,callback)=>{(windowListeners[kind]??=[]).push(callback);}};global.performance={now:()=>1000};
const payload={api_version:"admin.read.v1",site_id:site,result:{traffic:{download_mbps:1,upload_mbps:2,total_mbps:3,unit:"Mbps"},snapshot:{freshness_status:"fresh",selected_source:"wired",selection_reason:"primary_full_coverage",evaluated_at:"2026-08-29T10:00:00.000Z",observed_at:"2026-08-29T09:59:50.000Z"},source_selection:{selected_source:"wired",selection_reason:"primary_full_coverage"},coverage:{coverage_status:"complete"}}};
let fetchCalls=[];global.fetch=async(url,options)=>{fetchCalls.push({url,options});return{ok:true,status:200,headers:{get:()=>null},json:async()=>payload};};
'''
    assertions = r'''
(async()=>{await settle();await settle();
assert(fetchCalls.length===1,"registration causes exactly one initial execution");
assert(fetchCalls[0].url===`/admin/api/v1/sites/${site}/traffic/current`,"only canonical product URL fetched");
assert(elements["refresh-button"].listeners.click.length===1,"foundation is sole Refresh owner");
assert((documentListeners.visibilitychange||[]).length===1,"foundation is sole visibility owner");
assert((windowListeners.pagehide||[]).length===1,"foundation is sole pagehide owner");
assert(elements["traffic-empty-state"].hidden===true&&elements["refresh-button"].disabled===false,"registration activates Foundation shell");
assert(Array.from(timers.values()).filter((item)=>item.delay===60000).length===1,"one periodic scheduler");
console.log("TRAFFIC_CURRENT_INTEGRATION_OK");
})().catch((error)=>{console.error(error);process.exitCode=1;});
'''
    output = _run_node(
        tmp_path,
        "traffic-current-integration-probe.js",
        harness + combined + assertions,
    )
    assert "TRAFFIC_CURRENT_INTEGRATION_OK" in output
