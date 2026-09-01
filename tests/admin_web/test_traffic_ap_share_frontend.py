from __future__ import annotations

from .test_traffic_history_frontend import _panel_source, _run_node


def test_ap_share_frontend_uses_broker_and_renders_null_and_true_zero(tmp_path):
    harness = r'''
const assert=(value,message)=>{if(!value)throw new Error(message);};
class Element {
  constructor(id,namespaceURI=null){this.id=id;this.namespaceURI=namespaceURI;this.dataset={};this.textContent="";this.attributes={};this.children=[];this.listeners={};this.className="";}
  setAttribute(key,value){this.attributes[key]=String(value);}
  replaceChildren(...children){this.children=[...children];}
  appendChild(child){this.children.push(child);return child;}
  addEventListener(type,handler){(this.listeners[type]??=[]).push(handler);}
  click(){for(const callback of this.listeners.click||[])callback({preventDefault(){}});}
}
const ids={};
function add(id,namespace=null){const item=new Element(id,namespace);ids[id]=item;return item;}
const root=add("admin-page");root.dataset={page:"traffic",trafficEnabled:"true",trafficIndependentRangesEnabled:"true"};
const history=add("traffic-history-panel");history.dataset.historyEnabled="true";
const share=add("traffic-apshare-panel");share.dataset.apshareEnabled="true";
for(const id of ["traffic-history-state","traffic-history-state-title","traffic-history-state-message",
  "traffic-history-applied-range","traffic-history-coverage","traffic-history-watermark","traffic-history-gaps",
  "traffic-history-source-transitions","traffic-history-timezone","traffic-history-range-24h",
  "traffic-history-range-7d","traffic-apshare-state","traffic-apshare-state-title",
  "traffic-apshare-state-message","traffic-apshare-applied-range","traffic-apshare-population",
  "traffic-apshare-coverage","traffic-apshare-current","traffic-apshare-items",
  "traffic-apshare-range-24h","traffic-apshare-range-7d"]){add(id);}
add("traffic-history-chart-svg","urn:test-svg");
let registered=null,requests=[];const queued=[];let now=0,invalidPresence=false;
global.performance={now:()=>now};
global.window={CaptivPortalTrafficCoordinator:{
  registerPanel(value){registered=value;return true;},
  refreshPanel(){return Promise.resolve(false);},
  queuePanel(key,options){queued.push({key,options});return true;},
}};
global.document={
  getElementById(id){return ids[id]||null;},
  createElement(name){return new Element(name);},
  createElementNS(namespace,name){return new Element(name,namespace);},
};
global.Intl={DateTimeFormat(){return{resolvedOptions(){return{timeZone:"UTC"};}}}};
function payload(products,range="24h"){
  const count=range==="24h"?288:672,bucket=range==="24h"?300:900;
  const end=Date.parse("2026-08-29T12:00:00.000Z"),start=end-(range==="24h"?86400:604800)*1000;
  const buckets=Array.from({length:count},(_,index)=>({
    bucket_start_utc:new Date(start+index*bucket*1000).toISOString(),
    bucket_end_utc:new Date(start+(index+1)*bucket*1000).toISOString(),
    download_mbps:4,upload_mbps:1,total_mbps:5,status:"complete",selected_source:"wired",
    selection_reason:"primary_full_coverage",source_changed_from_previous:false,
    canonical_cycle_count:1,complete_site_sample_count:1,excluded_site_sample_count:0,
    total_ap_opportunities:2,selected_pair_valid_ap_opportunities:2,
    first_complete_sample_at:new Date(start+index*bucket*1000).toISOString(),
    last_complete_sample_at:new Date(start+(index+1)*bucket*1000-1000).toISOString(),
    leading_gap_seconds:0,trailing_gap_seconds:0,max_inter_sample_gap_seconds:0,
    gap_count_over_threshold:0,selected_source_skew_excluded_sample_count:0,
    rate_reason_counts:{ok:2,no_baseline:0,counter_reset:0,gap_too_large:0,invalid_elapsed:0,source_unavailable:0},
    source_selection:{primary_source:"wired",selected_source:"wired",selection_reason:"primary_full_coverage",
      wired_complete_site_cycle_count:1,lan_complete_site_cycle_count:0,
      wired_pair_valid_ap_opportunities:2,lan_pair_valid_ap_opportunities:0},
  }));
  const accepted=count-1,seconds=(count-1)*bucket;
  const evidence={range_seconds:(range==="24h"?86400:604800),candidate_interval_count:accepted,
    accepted_interval_count:accepted,accepted_interval_seconds:seconds,
    interval_coverage_ratio:seconds/(range==="24h"?86400:604800),excluded_gap_interval_count:0,
    excluded_source_transition_interval_count:0,invalid_period_interval_count:0,
    accepted_endpoint_sample_count:count,leading_unweighted_seconds:0,trailing_unweighted_seconds:bucket};
  const result={status:"ok",requested_products:products,
    range:{id:range,from_utc:new Date(start).toISOString(),to_utc:new Date(end).toISOString(),
      evaluated_at_utc:new Date(end).toISOString(),bucket_seconds:bucket,bucket_count:count,unit:"Mbps",
      aggregation:"mean_of_complete_site_rate_samples",metric_version:"network_traffic_history.v1",
      source_kind:"observation_ap_dynamic",sample_timestamp_semantics:"cycle_finished_at",
      bucket_alignment:"range_start_utc",max_site_history_buckets:720,max_site_sample_source_skew_seconds:60},
    coverage:{status:"complete",available_from_utc:buckets[0].bucket_start_utc,
      available_through_utc:buckets.at(-1).bucket_end_utc,source_watermark_utc:buckets.at(-1).bucket_end_utc,
      source_age_seconds:0,bucket_count:count,complete_bucket_count:count,partial_bucket_count:0,
      missing_bucket_count:0,canonical_cycle_count:count,complete_site_sample_count:count,
      excluded_site_sample_count:0,gap_bucket_count:0,source_transition_count:0},
    quality:{partial_cycle_count:0,failed_cycle_count:0,shutdown_cycle_count:0,abandoned_cycle_count:0,
      running_cycle_count:0,no_baseline_count:0,counter_reset_count:0,gap_too_large_count:0,
      invalid_elapsed_count:0,source_unavailable_count:0,source_skew_excluded_sample_count:0,
      integrity_failure_count:0}};
  if(products.includes("history"))result.buckets=buckets;
  if(products.includes("apshare"))result.ap_traffic_share={status:"ok",
    metric_version:"network_traffic_ap_share.v1",unit:"fraction",display_unit:"percent",
    share_method:"accepted_site_interval_integrated_ap_contribution_ratio.v1",
    temporal_method:"right_endpoint_sample_hold_time_weighted.v1",
    presence_method:"accepted_selected_source_historical_presence_in_range.v1",
    absence_method:"proven_population_member_absent_from_trusted_complete_site_sample_zero_contribution.v1",
    population_method:"current_union_historical_validated.v1",
    order_method:"total_share_desc_nulls_last_ap_mac_ascending.v1",
    population:{population_method:"current_union_historical_validated.v1",population_count:3,
      historical_population_count:2,current_population_status:"available",current_population_count:3,
      supported_max_ap_count:12,returned_ap_count:3,population_complete:true},coverage:evidence,
    denominators:{download_status:"positive",upload_status:"positive",total_status:"positive"},
    items:[
      {ap_mac:"02:AA:BB:CC:DD:10",display_name:"Main AP",display_name_source:"current",
        range_presence_proven:true,evidence_status:"accepted",accepted_presence_interval_count:accepted,
        accepted_presence_seconds:seconds,download_share_fraction:1,upload_share_fraction:1,total_share_fraction:1},
      {ap_mac:"02:AA:BB:CC:DD:20",display_name:"Zero AP",display_name_source:"historical",
        range_presence_proven:true,evidence_status:"accepted",accepted_presence_interval_count:0,
        accepted_presence_seconds:0,download_share_fraction:0,upload_share_fraction:0,total_share_fraction:0},
      {ap_mac:"02:AA:BB:CC:DD:30",display_name:"Current only",display_name_source:"current",
        range_presence_proven:false,evidence_status:"insufficient_data",accepted_presence_interval_count:0,
        accepted_presence_seconds:0,download_share_fraction:null,upload_share_fraction:null,total_share_fraction:null},
    ]};
  return {api_version:"admin.read.v1",site_id:"site-a",result};
}
'''
    assertions = r'''
assert(registered&&registered.key==="network-traffic-history","one shared broker registered");
(async()=>{
  const context={apiBase:"/admin/api/v1/sites/site-a",siteId:"site-a",requestJson:async(url)=>{
    requests.push(url);const parsed=new URL(url,"https://localhost");
    const products=decodeURIComponent(parsed.searchParams.get("products")).split(",");
    const response=payload(products,parsed.searchParams.get("range"));
    if(invalidPresence){
      response.result.ap_traffic_share.items[0].accepted_presence_interval_count=0;
      response.result.ap_traffic_share.items[0].accepted_presence_seconds=1;
    }
    return response;
  }};
  const first=await registered.load(context);registered.render(first);
  assert(requests.length===1,"one initial request");
  assert(requests[0].endsWith("range=24h&products=history%2Capshare"),"initial ALL24 subset is canonical");
  const cards=ids["traffic-apshare-items"].children;
  assert(cards.length===3,"all supported APs are shown");
  assert(cards[0].children[2].children[0].textContent.endsWith("100.00%"),"positive Share rendered");
  assert(cards[1].children[2].children[0].textContent.endsWith("0.00%"),"true zero is rendered as zero");
  assert(cards[2].children[2].children[0].textContent.endsWith("—"),"unproven Share stays unavailable");
  assert(cards[2].children[3].textContent.includes("Insufficient"),"unproven evidence is qualified");
  ids["traffic-apshare-range-7d"].click();
  assert(ids["traffic-apshare-state-title"].textContent.includes("waiting"),"selected and applied ranges stay separate");
  assert(ids["traffic-apshare-applied-range"].textContent==="Last 24 hours","prior applied payload remains visible");
  now=10000;const second=await registered.load(context);registered.render(second);
  assert(requests[1].endsWith("range=7d&products=apshare"),"Share range is independently requested");
  assert(ids["traffic-apshare-applied-range"].textContent==="Last 7 days","validated range becomes applied");
  ids["traffic-apshare-range-24h"].click();now=20000;invalidPresence=true;
  let rejected=false;try{await registered.load(context);}catch(error){rejected=true;}
  assert(rejected,"impossible presence count/seconds is rejected before render");
  console.log("TRAFFIC_AP_SHARE_FRONTEND_OK");
})().catch((error)=>{console.error(error);process.exit(1);});
'''
    assert "TRAFFIC_AP_SHARE_FRONTEND_OK" in _run_node(
        tmp_path, harness + _panel_source() + assertions
    )


def test_ap_share_frontend_has_no_independent_network_or_lifecycle_owner():
    source = _panel_source()
    share = source.split("function validateApShare", 1)[1]
    assert "fetch(" not in share
    assert "AbortController" not in share
    assert "setTimeout(" not in share and "setInterval(" not in share
    assert "localStorage" not in share and "sessionStorage" not in share
    assert "innerHTML" not in share
    assert 'apshare: "ap_traffic_share"' in source
    assert 'PRODUCT_ORDER = Object.freeze(["history", "statistics", "peak", "aps", "apshare"])' in source
    assert "item.accepted_presence_interval_count > coverage.accepted_interval_count" in source
    assert "item.accepted_presence_seconds > coverage.accepted_interval_seconds + 1e-9" in source
    assert "Math.abs(item.accepted_presence_seconds) <= 1e-9" in source


def test_ap_and_share_same_range_intents_coalesce_canonically(tmp_path):
    harness = r'''
const assert=(value,message)=>{if(!value)throw new Error(message);};
class Element {
  constructor(id){this.id=id;this.dataset={};this.textContent="";this.attributes={};this.children=[];this.listeners={};this.namespaceURI=id==="traffic-history-chart-svg"?"urn:test-svg":null;}
  setAttribute(key,value){this.attributes[key]=String(value);}
  addEventListener(kind,callback){(this.listeners[kind]??=[]).push(callback);}
  replaceChildren(...children){this.children=children;}
  click(){for(const callback of this.listeners.click||[])callback({preventDefault(){}});}
}
const elements={};function element(id){if(!elements[id])elements[id]=new Element(id);return elements[id];}
element("admin-page").dataset={page:"traffic",trafficEnabled:"true",trafficIndependentRangesEnabled:"true"};
element("traffic-history-panel").dataset.historyEnabled="true";
element("traffic-statistics-panel").dataset.statisticsEnabled="true";
element("traffic-peak-panel").dataset.peakEnabled="true";
element("traffic-ap-panel").dataset.apEnabled="true";
element("traffic-apshare-panel").dataset.apshareEnabled="true";
for(const id of ["traffic-history-state","traffic-history-state-title","traffic-history-state-message",
  "traffic-history-applied-range","traffic-history-coverage","traffic-history-watermark","traffic-history-gaps",
  "traffic-history-source-transitions","traffic-history-timezone","traffic-history-range-24h","traffic-history-range-7d",
  "traffic-statistics-state","traffic-statistics-state-title","traffic-statistics-state-message",
  "traffic-statistics-average-download","traffic-statistics-average-upload","traffic-statistics-average-total",
  "traffic-statistics-peak-download","traffic-statistics-peak-upload","traffic-statistics-peak-total",
  "traffic-statistics-applied-range","traffic-statistics-coverage","traffic-statistics-interval-coverage",
  "traffic-statistics-watermark","traffic-statistics-range-24h","traffic-statistics-range-7d",
  "traffic-peak-state","traffic-peak-state-title","traffic-peak-state-message","traffic-peak-download",
  "traffic-peak-download-at","traffic-peak-upload","traffic-peak-upload-at","traffic-peak-total",
  "traffic-peak-total-at","traffic-peak-bucket","traffic-peak-bucket-range","traffic-peak-hour",
  "traffic-peak-hour-range","traffic-peak-applied-range","traffic-peak-coverage","traffic-peak-watermark",
  "traffic-peak-source-transitions","traffic-peak-range-24h","traffic-peak-range-7d",
  "traffic-ap-state","traffic-ap-state-title","traffic-ap-state-message","traffic-ap-applied-range",
  "traffic-ap-population","traffic-ap-coverage","traffic-ap-current","traffic-ap-items",
  "traffic-ap-range-24h","traffic-ap-range-7d","traffic-apshare-state","traffic-apshare-state-title",
  "traffic-apshare-state-message","traffic-apshare-applied-range","traffic-apshare-population",
  "traffic-apshare-coverage","traffic-apshare-current","traffic-apshare-items",
  "traffic-apshare-range-24h","traffic-apshare-range-7d"]){element(id);}
global.document={getElementById:element,createElement:(name)=>new Element(name),createElementNS:(_namespace,name)=>new Element(name)};
let now=0;global.performance={now:()=>now};let registered=null;
global.window={CaptivPortalTrafficCoordinator:{registerPanel:(value)=>{registered=value;return true;},
  refreshPanel:()=>Promise.resolve(false),queuePanel:()=>true}};
'''
    assertions = r'''
(async()=>{
  const urls=[];const neutral={trafficNeutral:true};
  const context={apiBase:"/admin/api/v1/sites/site-a",siteId:"site-a",requestJson:async(url)=>{urls.push(url);throw neutral;}};
  try{await registered.load(context);}catch(error){assert(error===neutral,"neutral initial abort");}
  assert(urls[0].endsWith("range=24h&products=history%2Cstatistics%2Cpeak%2Caps%2Capshare"),"initial ALL24 uses canonical order");
  element("traffic-ap-range-7d").click();element("traffic-apshare-range-7d").click();
  now=10000;try{await registered.load(context);}catch(error){assert(error===neutral,"neutral coalesced abort");}
  assert(urls[1].endsWith("range=7d&products=aps%2Capshare"),"AP and Share coalesce in one canonical request");
  assert(urls.length===2,"one request per admitted batch");
  console.log("TRAFFIC_AP_SHARE_COALESCE_OK");
})().catch((error)=>{console.error(error);process.exit(1);});
'''
    assert "TRAFFIC_AP_SHARE_COALESCE_OK" in _run_node(
        tmp_path, harness + _panel_source() + assertions
    )
