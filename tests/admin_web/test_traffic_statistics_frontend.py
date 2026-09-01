from __future__ import annotations

from pathlib import Path

from .test_traffic_history_frontend import (
    ROOT,
    SOURCE,
    _node,
    _foundation_source,
    _panel_source,
    _range_context_source,
    _run_node,
)


def test_statistics_is_passive_history_consumer_without_new_lifecycle_owner():
    panel = _panel_source()
    assert '"statistics"' in panel
    assert "encodeURIComponent(include)" in panel
    assert panel.count("coordinator.registerPanel({") == 2
    assert "if (!independentRanges) {" in panel
    assert "const PRODUCT_ORDER" in panel
    assert "&products=${encodeURIComponent(products)}" in panel
    assert panel.count("const PANEL_KEY = \"network-traffic-history\"") == 1
    assert panel.count("key: PANEL_KEY") == 2
    assert "    return;\n  }\n\n  const PRODUCT_ORDER" in panel
    assert "fetch(" not in panel
    assert "setTimeout(" not in panel and "setInterval(" not in panel
    assert "AbortController" not in panel
    assert "visibilitychange" not in panel and "pagehide" not in panel
    assert "localStorage" not in panel and "sessionStorage" not in panel
    assert "innerHTML" not in panel
    assert "traffic-statistics-average-total" in panel
    assert "traffic-statistics-peak-total" in panel


def test_statistics_real_node_combined_request_validation_and_fail_local(tmp_path: Path):
    harness = r'''
const assert=(value,message)=>{if(!value)throw new Error(message);};
class Element {
  constructor(id,namespaceURI=null){this.id=id;this.namespaceURI=namespaceURI;this.dataset={};this.textContent="";this.attributes={};this.children=[];this.listeners={};}
  setAttribute(key,value){this.attributes[key]=String(value);}
  addEventListener(kind,callback){(this.listeners[kind]??=[]).push(callback);}
  replaceChildren(...children){this.children=children;}
  click(){for(const callback of this.listeners.click||[])callback({preventDefault(){}});}
}
const ids=["admin-page","traffic-history-panel","traffic-history-state","traffic-history-state-title","traffic-history-state-message","traffic-history-applied-range","traffic-history-coverage","traffic-history-watermark","traffic-history-gaps","traffic-history-source-transitions","traffic-history-timezone","traffic-history-chart-svg","traffic-network-range-24h","traffic-network-range-7d","traffic-statistics-panel","traffic-statistics-state","traffic-statistics-state-title","traffic-statistics-state-message","traffic-statistics-average-download","traffic-statistics-average-upload","traffic-statistics-average-total","traffic-statistics-peak-download","traffic-statistics-peak-upload","traffic-statistics-peak-total","traffic-statistics-applied-range","traffic-statistics-coverage","traffic-statistics-interval-coverage","traffic-statistics-watermark"];
const elements=Object.fromEntries(ids.map((id)=>[id,new Element(id)]));
elements["traffic-history-chart-svg"].namespaceURI="http://www.w3.org/2000/svg";
const site="0123456789abcdef01234567";
elements["admin-page"].dataset={page:"traffic",trafficEnabled:"true"};
elements["traffic-history-panel"].dataset={historyEnabled:"true"};
elements["traffic-statistics-panel"].dataset={statisticsEnabled:"true"};
let registrations=[],refreshes=[];
global.window={CaptivPortalTrafficCoordinator:{registerPanel:(spec)=>{registrations.push(spec);return true;},refreshPanel:(key,options)=>{refreshes.push({key,options});return Promise.resolve(false);}}};
global.document={getElementById:(id)=>elements[id]||null,createElementNS:(ns,name)=>new Element(name,ns)};
function payload(mode="ok"){
  const seconds=86400,bucket=300,count=288,end=Date.parse("2026-08-29T12:00:00.000Z"),start=end-seconds*1000;
  const none=mode==="insufficient";
  const buckets=Array.from({length:count},(_item,index)=>({bucket_start_utc:new Date(start+index*bucket*1000).toISOString(),bucket_end_utc:new Date(start+(index+1)*bucket*1000).toISOString(),download_mbps:none?null:1,upload_mbps:none?null:.5,total_mbps:none?null:1.5,status:none?"none":"complete",selected_source:none?null:"wired",selection_reason:none?"no_canonical_samples":"primary_full_coverage",source_changed_from_previous:false,complete_site_sample_count:none?0:1,excluded_site_sample_count:0,gap_count_over_threshold:none?1:0,selected_source_skew_excluded_sample_count:0}));
  const peakCount=none?0:count,candidate=Math.max(peakCount-1,0),partial=mode==="partial",accepted=partial?candidate-1:candidate,acceptedSeconds=accepted*bucket;
  const result={status:none?"insufficient_data":"ok",range:{id:"24h",from_utc:new Date(start).toISOString(),to_utc:new Date(end).toISOString(),evaluated_at_utc:new Date(end).toISOString(),bucket_seconds:bucket,bucket_count:count,unit:"Mbps",aggregation:"mean_of_complete_site_rate_samples",metric_version:"network_traffic_history.v1",source_kind:"observation_ap_dynamic",sample_timestamp_semantics:"cycle_finished_at",bucket_alignment:"range_start_utc",max_site_history_buckets:720,max_site_sample_source_skew_seconds:60},buckets,coverage:{status:none?"none":"complete",available_from_utc:new Date(start).toISOString(),available_through_utc:new Date(end).toISOString(),source_watermark_utc:new Date(end).toISOString(),source_age_seconds:0,bucket_count:count,complete_bucket_count:none?0:count,partial_bucket_count:0,missing_bucket_count:none?count:0,canonical_cycle_count:peakCount,complete_site_sample_count:peakCount,excluded_site_sample_count:0,gap_bucket_count:none?count:0,source_transition_count:0},quality:{}};
  result.period_statistics={status:none?"insufficient_data":(partial?"partial":"ok"),metric_version:"network_traffic_period_statistics.v1",average_method:"right_endpoint_sample_hold_time_weighted.v1",peak_method:"max_accepted_complete_site_sample.v1",unit:"Mbps",average:none?{download_mbps:null,upload_mbps:null,total_mbps:null}:{download_mbps:0,upload_mbps:.5,total_mbps:.5},peak:none?{download_mbps:null,upload_mbps:null,total_mbps:null}:{download_mbps:4,upload_mbps:2,total_mbps:5},interval_evidence:{range_seconds:seconds,candidate_interval_count:candidate,accepted_interval_count:accepted,accepted_interval_seconds:acceptedSeconds,interval_coverage_ratio:acceptedSeconds/seconds,excluded_gap_interval_count:partial?1:0,excluded_source_transition_interval_count:0,invalid_period_interval_count:0,accepted_peak_sample_count:peakCount,leading_unweighted_seconds:none?seconds:0,trailing_unweighted_seconds:none?seconds:bucket}};
  return {api_version:"admin.read.v1",site_id:site,result};
}
'''
    assertions = r'''
(async()=>{
  assert(registrations.length===1,"Statistics creates no second network loader");
  const spec=registrations[0];let requested="";
  const first=await spec.load({siteId:site,apiBase:`/admin/api/v1/sites/${site}`,requestJson:async(url)=>{requested=url;return payload();}});
  assert(requested.endsWith("/traffic/history?range=24h&include=statistics"),"one combined History request");
  spec.render(first);
  assert(elements["traffic-statistics-state-title"].textContent==="Period statistics ready","ready state");
  assert(elements["traffic-statistics-average-download"].textContent==="0.00 Mbps","real zero retained");
  assert(elements["traffic-statistics-peak-total"].textContent==="5.00 Mbps","six metrics rendered");
  assert(elements["traffic-statistics-applied-range"].textContent==="Last 24 hours","shared applied range");
  const partial=await spec.load({siteId:site,apiBase:"/x",requestJson:async()=>payload("partial")});spec.render(partial);
  assert(elements["traffic-statistics-state-title"].textContent==="Period statistics partial","partial visible");
  const insufficient=await spec.load({siteId:site,apiBase:"/x",requestJson:async()=>payload("insufficient")});spec.render(insufficient);
  assert(elements["traffic-statistics-state-title"].textContent==="Period statistics insufficient"&&elements["traffic-statistics-average-total"].textContent==="—","null remains missing");
  const malformed=payload();malformed.result.period_statistics.average.total_mbps=99;
  const local=await spec.load({siteId:site,apiBase:"/x",requestJson:async()=>malformed});spec.render(local);
  assert(elements["traffic-history-state-title"].textContent==="History ready","valid History survives malformed Statistics");
  assert(elements["traffic-statistics-state-title"].textContent==="Period statistics unavailable","Statistics fails locally");
  elements["traffic-network-range-7d"].click();
  assert(refreshes.length===1&&refreshes[0].key==="network-traffic-history","range causes one History refresh only");
  assert(elements["traffic-statistics-applied-range"].textContent==="Last 24 hours","selected range does not fake applied Statistics range");
  console.log("TRAFFIC_STATISTICS_PANEL_OK");
})().catch((error)=>{console.error(error);process.exitCode=1;});
'''
    output = _run_node(
        tmp_path,
        harness + _range_context_source() + _panel_source() + assertions,
    )
    assert "TRAFFIC_STATISTICS_PANEL_OK" in output


def test_statistics_template_has_six_metrics_and_dual_mode_range_selector():
    template = (
        ROOT / "app" / "admin_web" / "templates" / "admin" / "traffic.html"
    ).read_text(encoding="utf-8")
    for identity in (
        "traffic-statistics-average-download", "traffic-statistics-average-upload",
        "traffic-statistics-average-total", "traffic-statistics-peak-download",
        "traffic-statistics-peak-upload", "traffic-statistics-peak-total",
    ):
        assert identity in template
    assert template.count("traffic-network-range-24h") == 1
    assert "traffic-statistics-range-24h" in template
    assert "traffic-statistics-range-7d" in template
    assert "{% if traffic_independent_ranges_enabled %}" in template
    assert _node()


def test_statistics_shares_history_generation_abort_and_single_request(tmp_path: Path):
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
const ids=["admin-page","refresh-button","traffic-global-state","traffic-global-state-title","traffic-global-state-message","traffic-empty-state","traffic-panels","traffic-history-panel","traffic-history-state","traffic-history-state-title","traffic-history-state-message","traffic-history-applied-range","traffic-history-coverage","traffic-history-watermark","traffic-history-gaps","traffic-history-source-transitions","traffic-history-timezone","traffic-history-chart-svg","traffic-network-range-24h","traffic-network-range-7d","traffic-statistics-panel","traffic-statistics-state","traffic-statistics-state-title","traffic-statistics-state-message","traffic-statistics-average-download","traffic-statistics-average-upload","traffic-statistics-average-total","traffic-statistics-peak-download","traffic-statistics-peak-upload","traffic-statistics-peak-total","traffic-statistics-applied-range","traffic-statistics-coverage","traffic-statistics-interval-coverage","traffic-statistics-watermark"];
const elements=Object.fromEntries(ids.map((id)=>[id,new Element(id)]));const site="0123456789abcdef01234567";
elements["traffic-history-chart-svg"].namespaceURI="http://www.w3.org/2000/svg";
elements["admin-page"].dataset={page:"traffic",trafficEnabled:"true",siteId:site,apiBase:`/admin/api/v1/sites/${site}`,trafficRefreshSeconds:"60",trafficRequestTimeoutSeconds:"20"};
elements["traffic-history-panel"].dataset={historyEnabled:"true"};elements["traffic-statistics-panel"].dataset={statisticsEnabled:"true"};
const documentListeners={},windowListeners={};global.document={hidden:false,getElementById:(id)=>elements[id]||null,createElementNS:(ns,name)=>new Element(name,ns),addEventListener:(kind,callback)=>{(documentListeners[kind]??=[]).push(callback);}};
let timerId=0;const timers=new Map();global.window={location:{origin:"https://localhost"},setTimeout:(callback,delay)=>{const id=++timerId;timers.set(id,{callback,delay});return id;},clearTimeout:(id)=>timers.delete(id),addEventListener:(kind,callback)=>{(windowListeners[kind]??=[]).push(callback);}};global.performance={now:()=>1000};
function payload(rangeId){const spec=rangeId==="24h"?{seconds:86400,bucket:300,count:288}:{seconds:604800,bucket:900,count:672};const end=Date.parse("2026-08-29T12:00:00.000Z"),start=end-spec.seconds*1000,candidate=spec.count-1,acceptedSeconds=candidate*spec.bucket;const buckets=Array.from({length:spec.count},(_item,index)=>({bucket_start_utc:new Date(start+index*spec.bucket*1000).toISOString(),bucket_end_utc:new Date(start+(index+1)*spec.bucket*1000).toISOString(),download_mbps:1,upload_mbps:0,total_mbps:1,status:"complete",selected_source:"wired",selection_reason:"primary_full_coverage",source_changed_from_previous:false,complete_site_sample_count:1,excluded_site_sample_count:0,gap_count_over_threshold:0,selected_source_skew_excluded_sample_count:0}));return{api_version:"admin.read.v1",site_id:site,result:{status:"ok",range:{id:rangeId,from_utc:new Date(start).toISOString(),to_utc:new Date(end).toISOString(),evaluated_at_utc:new Date(end).toISOString(),bucket_seconds:spec.bucket,bucket_count:spec.count,unit:"Mbps",aggregation:"mean_of_complete_site_rate_samples",metric_version:"network_traffic_history.v1",source_kind:"observation_ap_dynamic",sample_timestamp_semantics:"cycle_finished_at",bucket_alignment:"range_start_utc",max_site_history_buckets:720,max_site_sample_source_skew_seconds:60},buckets,coverage:{status:"complete",available_from_utc:new Date(start).toISOString(),available_through_utc:new Date(end).toISOString(),source_watermark_utc:new Date(end).toISOString(),source_age_seconds:0,bucket_count:spec.count,complete_bucket_count:spec.count,partial_bucket_count:0,missing_bucket_count:0,canonical_cycle_count:spec.count,complete_site_sample_count:spec.count,excluded_site_sample_count:0,gap_bucket_count:0,source_transition_count:0},quality:{},period_statistics:{status:"ok",metric_version:"network_traffic_period_statistics.v1",average_method:"right_endpoint_sample_hold_time_weighted.v1",peak_method:"max_accepted_complete_site_sample.v1",unit:"Mbps",average:{download_mbps:1,upload_mbps:0,total_mbps:1},peak:{download_mbps:1,upload_mbps:0,total_mbps:1},interval_evidence:{range_seconds:spec.seconds,candidate_interval_count:candidate,accepted_interval_count:candidate,accepted_interval_seconds:acceptedSeconds,interval_coverage_ratio:acceptedSeconds/spec.seconds,excluded_gap_interval_count:0,excluded_source_transition_interval_count:0,invalid_period_interval_count:0,accepted_peak_sample_count:spec.count,leading_unweighted_seconds:0,trailing_unweighted_seconds:spec.bucket}}}};}
const response=(rangeId)=>({ok:true,status:200,headers:{get:()=>null},json:async()=>payload(rangeId)});
let fetchCalls=[],hold7=false,pending7=null;global.fetch=(url,options)=>{fetchCalls.push({url,options});const rangeId=url.includes("range=7d")?"7d":"24h";if(hold7&&rangeId==="7d")return new Promise((resolve,reject)=>{pending7={resolve,reject,signal:options.signal};options.signal.addEventListener("abort",()=>reject(new Error("aborted")),{once:true});});return Promise.resolve(response(rangeId));};
'''
    assertions = r'''
(async()=>{await settle();await settle();
  assert(fetchCalls.length===1&&fetchCalls[0].url.endsWith("/traffic/history?range=24h&include=statistics"),"one combined initial historical request");
  let currentLoads=0;window.CaptivPortalTrafficCoordinator.registerPanel({key:"current-proof",autoRefresh:true,load:async()=>{currentLoads+=1;return{};},render:()=>{}});await settle();await settle();
  assert(currentLoads===1,"Current initial load remains independent");
  hold7=true;elements["traffic-network-range-7d"].click();await settle();
  assert(fetchCalls.length===2&&pending7&&!pending7.signal.aborted&&fetchCalls[1].url.endsWith("range=7d&include=statistics"),"one combined 7d generation");
  elements["traffic-network-range-24h"].click();await settle();await settle();
  assert(pending7.signal.aborted===true,"shared old generation aborted");
  assert(fetchCalls.length===3&&fetchCalls[2].url.endsWith("range=24h&include=statistics"),"one latest combined request");
  assert(elements["traffic-history-applied-range"].textContent==="Last 24 hours"&&elements["traffic-statistics-applied-range"].textContent==="Last 24 hours","one response owns both applied states");
  pending7.resolve(response("7d"));await settle();await settle();
  assert(elements["traffic-history-applied-range"].textContent==="Last 24 hours"&&elements["traffic-statistics-applied-range"].textContent==="Last 24 hours","late response updates neither consumer");
  assert(currentLoads===1,"range does not reload Current");
  assert(elements["refresh-button"].listeners.click.length===1,"foundation owns shared Refresh");
  console.log("TRAFFIC_STATISTICS_COORDINATOR_OK");
})().catch((error)=>{console.error(error);process.exitCode=1;});
'''
    output = _run_node(
        tmp_path,
        harness + _foundation_source() + _range_context_source()
        + _panel_source() + assertions,
    )
    assert "TRAFFIC_STATISTICS_COORDINATOR_OK" in output
