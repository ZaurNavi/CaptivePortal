from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess


ROOT = Path(__file__).parents[2]
SOURCE = ROOT / "app" / "admin_web" / "static" / "admin.js"
START = "/* TRAFFIC_HISTORY_PANEL_START */"
END = "/* TRAFFIC_HISTORY_PANEL_END */"
RANGE_START = "/* TRAFFIC_NETWORK_RANGE_CONTEXT_START */"
RANGE_END = "/* TRAFFIC_NETWORK_RANGE_CONTEXT_END */"


def _node() -> str:
    value = shutil.which("node")
    if value:
        return value
    bundled = (
        Path(os.environ.get("LOCALAPPDATA", ""))
        / "Codex" / "dependencies" / "node" / "bin" / "node.exe"
    )
    assert bundled.exists(), "Node is mandatory for the Traffic frontend gate"
    return str(bundled)


def _panel_source() -> str:
    source = SOURCE.read_text(encoding="utf-8")
    return source.split(START, 1)[1].split(END, 1)[0]


def _foundation_source() -> str:
    source = SOURCE.read_text(encoding="utf-8")
    current_at = source.index("/* TRAFFIC_CURRENT_PANEL_START */")
    foundation_at = source.rfind("(function ()", 0, current_at)
    return source[foundation_at:current_at]


def _range_context_source() -> str:
    source = SOURCE.read_text(encoding="utf-8")
    return source.split(RANGE_START, 1)[1].split(RANGE_END, 1)[0]


def _run_node(tmp_path: Path, source: str) -> str:
    probe = tmp_path / "traffic-history-probe.js"
    probe.write_text(source, encoding="utf-8")
    completed = subprocess.run(
        [_node(), str(probe)], cwd=ROOT, capture_output=True, text=True,
        timeout=30, check=False, env={**os.environ, "NODE_NO_WARNINGS": "1"},
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    return completed.stdout


def test_history_javascript_uses_only_shared_coordinator_and_safe_dom():
    completed = subprocess.run(
        [_node(), "--check", str(SOURCE)], cwd=ROOT,
        capture_output=True, text=True, timeout=30, check=False,
    )
    assert completed.returncode == 0, completed.stderr
    panel = _panel_source()
    assert "fetch(" not in panel
    assert "setTimeout(" not in panel and "setInterval(" not in panel
    assert "AbortController" not in panel
    assert "visibilitychange" not in panel and "pagehide" not in panel
    assert "localStorage" not in panel and "sessionStorage" not in panel
    assert "innerHTML" not in panel
    assert 'key: PANEL_KEY' in panel and 'autoRefresh: false' in panel
    assert 'context.requestJson(`${context.apiBase}/traffic/history?range=' in panel
    assert 'let selectedRange' not in panel
    assert 'rangeContext.selected()' in panel


def test_history_real_node_range_validation_chart_and_failure_isolation(tmp_path):
    harness = r'''
const assert=(value,message)=>{if(!value)throw new Error(message);};
class Element {
  constructor(id,namespaceURI=null){this.id=id;this.namespaceURI=namespaceURI;this.dataset={};this.textContent="";this.attributes={};this.children=[];this.listeners={};}
  setAttribute(key,value){this.attributes[key]=String(value);}
  addEventListener(kind,callback){(this.listeners[kind]??=[]).push(callback);}
  replaceChildren(...children){this.children=children;}
  click(){for(const callback of this.listeners.click||[])callback({preventDefault(){}});}
}
const ids=["admin-page","traffic-history-panel","traffic-history-state","traffic-history-state-title","traffic-history-state-message","traffic-history-applied-range","traffic-history-coverage","traffic-history-watermark","traffic-history-gaps","traffic-history-source-transitions","traffic-history-timezone","traffic-history-chart-svg","traffic-network-range-24h","traffic-network-range-7d"];
const elements=Object.fromEntries(ids.map((id)=>[id,new Element(id)]));
elements["traffic-history-chart-svg"].namespaceURI="http://www.w3.org/2000/svg";
const site="0123456789abcdef01234567";
elements["admin-page"].dataset={page:"traffic",trafficEnabled:"true"};
elements["traffic-history-panel"].dataset={historyEnabled:"true"};
let registrations=[];let refreshes=[];
global.window={CaptivPortalTrafficCoordinator:{registerPanel:(spec)=>{registrations.push(spec);return true;},refreshPanel:(key,options)=>{refreshes.push({key,options});return Promise.resolve(false);}}};
global.document={getElementById:(id)=>elements[id]||null,createElementNS:(ns,name)=>new Element(name,ns)};
function makePayload(rangeId,mode="ok"){
  const spec=rangeId==="24h"?{seconds:86400,bucket:300,count:288}:{seconds:604800,bucket:900,count:672};
  const end=Date.parse("2026-08-29T12:00:00.000Z");const start=end-spec.seconds*1000;const buckets=[];
  for(let index=0;index<spec.count;index++){
    const none=mode==="gap"&&index===1;const partial=(mode==="partial"||mode==="gap")&&index===2;
    buckets.push({bucket_start_utc:new Date(start+index*spec.bucket*1000).toISOString(),bucket_end_utc:new Date(start+(index+1)*spec.bucket*1000).toISOString(),download_mbps:none?null:(index===0?0:1.25),upload_mbps:none?null:.25,total_mbps:none?null:(index===0?.25:1.5),status:none?"none":(partial?"partial":"complete"),selected_source:none?null:"wired",selection_reason:none?"no_canonical_samples":"primary_full_coverage",source_changed_from_previous:false,complete_site_sample_count:none?0:1,excluded_site_sample_count:0,gap_count_over_threshold:none?1:0,selected_source_skew_excluded_sample_count:0});
  }
  const missing=mode==="gap"?1:0,partialCount=(mode==="partial"||mode==="gap")?1:0;
  return {api_version:"admin.read.v1",site_id:site,result:{status:mode==="ok"?"ok":"partial",range:{id:rangeId,from_utc:new Date(start).toISOString(),to_utc:new Date(end).toISOString(),evaluated_at_utc:new Date(end).toISOString(),bucket_seconds:spec.bucket,bucket_count:spec.count,unit:"Mbps",aggregation:"mean_of_complete_site_rate_samples",metric_version:"network_traffic_history.v1",source_kind:"observation_ap_dynamic",sample_timestamp_semantics:"cycle_finished_at",bucket_alignment:"range_start_utc",max_site_history_buckets:720,max_site_sample_source_skew_seconds:60},buckets,coverage:{status:mode==="ok"?"complete":"partial",available_from_utc:new Date(start).toISOString(),available_through_utc:new Date(end).toISOString(),source_watermark_utc:new Date(end).toISOString(),source_age_seconds:0,bucket_count:spec.count,complete_bucket_count:spec.count-missing-partialCount,partial_bucket_count:partialCount,missing_bucket_count:missing,canonical_cycle_count:spec.count,complete_site_sample_count:spec.count-missing,excluded_site_sample_count:0,gap_bucket_count:missing,source_transition_count:0},quality:{}}};
}
'''
    assertions = r'''
(async()=>{
  assert(registrations.length===1,"history registers once");
  const spec=registrations[0];assert(spec.key==="network-traffic-history"&&spec.autoRefresh===false,"canonical registration");
  let requested=null;const first=await spec.load({siteId:site,apiBase:`/admin/api/v1/sites/${site}`,requestJson:async(url)=>{requested=url;return makePayload("24h");}});
  assert(requested.endsWith("/traffic/history?range=24h"),"server-owned range id only");
  spec.render(first);
  assert(elements["traffic-history-state-title"].textContent==="History ready","ready state");
  assert(elements["traffic-history-applied-range"].textContent==="Last 24 hours","applied 24h");
  assert(elements["traffic-history-chart-svg"].children.some((item)=>item.id==="polyline"),"SVG line rendered");
  const points=elements["traffic-history-chart-svg"].children.filter((item)=>item.id==="polyline").map((item)=>item.attributes.points).join(" ");
  assert(points.includes(",284.00"),"real zero plots on zero axis");

  elements["traffic-network-range-7d"].click();
  assert(refreshes.length===1&&refreshes[0].key==="network-traffic-history"&&refreshes[0].options.manual===true,"only History refresh requested");
  assert(elements["traffic-network-range-7d"].attributes["aria-pressed"]==="true","shared selected range changes");
  assert(elements["traffic-history-applied-range"].textContent==="Last 24 hours","false admission does not fake applied range");
  assert(elements["traffic-history-state-title"].textContent==="History ready","false admission does not fake Loading");
  requested=null;const second=await spec.load({siteId:site,apiBase:"/x",requestJson:async(url)=>{requested=url;return makePayload("7d","partial");}});
  assert(requested.endsWith("/traffic/history?range=7d"),"selected range captured per execution");
  spec.render(second);
  assert(elements["traffic-history-applied-range"].textContent==="Last 7 days","success commits applied range");
  assert(elements["traffic-history-state-title"].textContent==="History partial"&&elements["traffic-history-state-message"].textContent.includes("gaps"),"partial evidence visible in text");
  const normalLines=elements["traffic-history-chart-svg"].children.filter((item)=>item.id==="polyline");
  assert(normalLines.length===2&&normalLines.every((item)=>!String(item.attributes.class).includes("partial")),"one partial bucket does not restyle complete series");
  const partialMarkers=elements["traffic-history-chart-svg"].children.filter((item)=>item.id==="circle");
  assert(partialMarkers.length===2&&partialMarkers.some((item)=>String(item.attributes.class).includes("download"))&&partialMarkers.some((item)=>String(item.attributes.class).includes("upload")),"partial evidence has source-series-specific markers");
  const gapValue=await spec.load({siteId:site,apiBase:"/x",requestJson:async()=>makePayload("7d","gap")});spec.render(gapValue);
  assert(elements["traffic-history-chart-svg"].children.filter((item)=>item.id==="polyline").length>2,"null creates separate SVG path gaps");
  const selectedNone=makePayload("7d","gap");selectedNone.result.buckets[1].selected_source="wired";selectedNone.result.buckets[1].selection_reason="primary_preferred_tie_or_higher";
  await spec.load({siteId:site,apiBase:"/x",requestJson:async()=>selectedNone});
  assert(elements["traffic-history-chart-svg"].children[0].id==="title"&&elements["traffic-history-chart-svg"].children[1].id==="desc","accessible SVG title and description");
  assert(elements["traffic-history-chart-svg"].children.some((item)=>item.id==="text"&&item.textContent==="Mbps"),"visible Mbps axis unit");
  assert(elements["traffic-history-chart-svg"].children.filter((item)=>item.id==="text").some((item)=>item.textContent.includes("2026")),"time axis uses returned evidence boundaries");

  const malformed=makePayload("24h");malformed.result.buckets[0].download_mbps=null;
  let rejected=false;try{await spec.load({siteId:site,apiBase:"/x",requestJson:async()=>malformed});}catch(_error){rejected=true;}
  assert(rejected,"malformed HTTP 200 rejected before DOM mutation");
  spec.renderFailure({kind:"unavailable"});
  assert(elements["traffic-history-state-title"].textContent==="History unavailable"&&elements["traffic-history-applied-range"].textContent==="Last 7 days","failure is panel-local and preserves accepted chart");
  console.log("TRAFFIC_HISTORY_PANEL_OK");
})().catch((error)=>{console.error(error);process.exitCode=1;});
'''
    output = _run_node(
        tmp_path,
        harness + _range_context_source() + _panel_source() + assertions,
    )
    assert "TRAFFIC_HISTORY_PANEL_OK" in output


def test_history_template_owns_shared_range_not_private_range():
    template = (ROOT / "app" / "admin_web" / "templates" / "admin" / "traffic.html").read_text(encoding="utf-8")
    assert "traffic-network-range-24h" in template and "traffic-network-range-7d" in template
    assert "traffic-history-range-24h" not in template
    assert "Download" in template and "Upload" in template
    assert "Period Average" not in template and "Peak" not in template


def test_history_uses_foundation_for_one_initial_load_and_range_refresh(tmp_path):
    harness = r'''
const assert=(value,message)=>{if(!value)throw new Error(message);};
const settle=()=>new Promise((resolve)=>setImmediate(resolve));
class Element{
  constructor(id,namespaceURI=null){this.id=id;this.namespaceURI=namespaceURI;this.dataset={};this.textContent="";this.hidden=false;this.disabled=false;this.attributes={};this.children=[];this.listeners={};}
  setAttribute(key,value){this.attributes[key]=String(value);}
  addEventListener(kind,callback){(this.listeners[kind]??=[]).push(callback);}
  replaceChildren(...children){this.children=children;}
  click(){for(const callback of this.listeners.click||[])callback({preventDefault(){}});}
}
const ids=["admin-page","refresh-button","traffic-global-state","traffic-global-state-title","traffic-global-state-message","traffic-empty-state","traffic-panels","traffic-history-panel","traffic-history-state","traffic-history-state-title","traffic-history-state-message","traffic-history-applied-range","traffic-history-coverage","traffic-history-watermark","traffic-history-gaps","traffic-history-source-transitions","traffic-history-timezone","traffic-history-chart-svg","traffic-network-range-24h","traffic-network-range-7d"];
const elements=Object.fromEntries(ids.map((id)=>[id,new Element(id)]));const site="0123456789abcdef01234567";
elements["traffic-history-chart-svg"].namespaceURI="http://www.w3.org/2000/svg";
elements["admin-page"].dataset={page:"traffic",trafficEnabled:"true",siteId:site,apiBase:`/admin/api/v1/sites/${site}`,trafficRefreshSeconds:"60",trafficRequestTimeoutSeconds:"20"};
elements["traffic-history-panel"].dataset={historyEnabled:"true"};
const documentListeners={},windowListeners={};global.document={hidden:false,getElementById:(id)=>elements[id]||null,createElementNS:(ns,name)=>new Element(name,ns),addEventListener:(kind,callback)=>{(documentListeners[kind]??=[]).push(callback);}};
let timerId=0;const timers=new Map();global.window={location:{origin:"https://localhost"},setTimeout:(callback,delay)=>{const id=++timerId;timers.set(id,{callback,delay});return id;},clearTimeout:(id)=>timers.delete(id),addEventListener:(kind,callback)=>{(windowListeners[kind]??=[]).push(callback);}};global.performance={now:()=>1000};
function payload(rangeId){const spec=rangeId==="24h"?{seconds:86400,bucket:300,count:288}:{seconds:604800,bucket:900,count:672};const end=Date.parse("2026-08-29T12:00:00.000Z"),start=end-spec.seconds*1000;const buckets=Array.from({length:spec.count},(_item,index)=>({bucket_start_utc:new Date(start+index*spec.bucket*1000).toISOString(),bucket_end_utc:new Date(start+(index+1)*spec.bucket*1000).toISOString(),download_mbps:1,upload_mbps:0,total_mbps:1,status:"complete",selected_source:"wired",selection_reason:"primary_full_coverage",source_changed_from_previous:false,complete_site_sample_count:1,excluded_site_sample_count:0,gap_count_over_threshold:0,selected_source_skew_excluded_sample_count:0}));return{api_version:"admin.read.v1",site_id:site,result:{status:"ok",range:{id:rangeId,from_utc:new Date(start).toISOString(),to_utc:new Date(end).toISOString(),evaluated_at_utc:new Date(end).toISOString(),bucket_seconds:spec.bucket,bucket_count:spec.count,unit:"Mbps",aggregation:"mean_of_complete_site_rate_samples",metric_version:"network_traffic_history.v1",source_kind:"observation_ap_dynamic",sample_timestamp_semantics:"cycle_finished_at",bucket_alignment:"range_start_utc",max_site_history_buckets:720,max_site_sample_source_skew_seconds:60},buckets,coverage:{status:"complete",available_from_utc:new Date(start).toISOString(),available_through_utc:new Date(end).toISOString(),source_watermark_utc:new Date(end).toISOString(),source_age_seconds:0,bucket_count:spec.count,complete_bucket_count:spec.count,partial_bucket_count:0,missing_bucket_count:0,canonical_cycle_count:spec.count,complete_site_sample_count:spec.count,excluded_site_sample_count:0,gap_bucket_count:0,source_transition_count:0},quality:{}}};}
const response=(rangeId)=>({ok:true,status:200,headers:{get:()=>null},json:async()=>payload(rangeId)});
let fetchCalls=[],hold7=false,pending7=null;global.fetch=(url,options)=>{fetchCalls.push({url,options});const rangeId=url.endsWith("range=7d")?"7d":"24h";if(hold7&&rangeId==="7d")return new Promise((resolve,reject)=>{pending7={resolve,reject,signal:options.signal};options.signal.addEventListener("abort",()=>reject(new Error("aborted")),{once:true});});return Promise.resolve(response(rangeId));};
'''
    assertions = r'''
(async()=>{await settle();await settle();
  assert(fetchCalls.length===1&&fetchCalls[0].url.endsWith("/traffic/history?range=24h"),"registration causes exactly one initial History load");
  let currentLoads=0;window.CaptivPortalTrafficCoordinator.registerPanel({key:"current-proof",autoRefresh:true,load:async()=>{currentLoads+=1;return{};},render:()=>{}});await settle();await settle();
  assert(currentLoads===1,"representative Current panel initial load");
  hold7=true;elements["traffic-network-range-7d"].click();await settle();
  assert(fetchCalls.length===2&&fetchCalls[1].url.endsWith("/traffic/history?range=7d")&&pending7&&!pending7.signal.aborted,"7d request remains in flight");
  elements["traffic-network-range-24h"].click();await settle();await settle();
  assert(pending7.signal.aborted===true,"old 7d generation aborted on supersession");
  assert(fetchCalls.length===3&&fetchCalls[2].url.endsWith("/traffic/history?range=24h"),"latest 24h generation executes");
  assert(elements["traffic-history-applied-range"].textContent==="Last 24 hours","latest successful generation owns applied range");
  pending7.resolve(response("7d"));await settle();await settle();
  assert(elements["traffic-history-applied-range"].textContent==="Last 24 hours","stale 7d completion cannot render");
  assert(currentLoads===1,"range supersession does not refresh Current");
  assert(elements["refresh-button"].listeners.click.length===1,"foundation remains sole global Refresh owner");
  assert((documentListeners.visibilitychange||[]).length===1&&(windowListeners.pagehide||[]).length===1,"foundation remains sole lifecycle owner");
  console.log("TRAFFIC_HISTORY_COORDINATOR_OK");
})().catch((error)=>{console.error(error);process.exitCode=1;});
'''
    output = _run_node(
        tmp_path,
        harness + _foundation_source() + _range_context_source()
        + _panel_source() + assertions,
    )
    assert "TRAFFIC_HISTORY_COORDINATOR_OK" in output
