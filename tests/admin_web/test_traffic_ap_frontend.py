from __future__ import annotations

from .test_traffic_history_frontend import _panel_source, _run_node


def test_ap_frontend_uses_combined_history_loader_and_bounded_safe_dom():
    source = _panel_source()
    assert '"statistics,peak,aps"' in source
    assert "encodeURIComponent(include)" in source
    assert 'apEnabled ? "aps" : null' in source
    assert source.count("coordinator.registerPanel({") == 2
    assert "if (!independentRanges) {" in source
    assert "const PRODUCT_ORDER" in source
    assert "&products=${encodeURIComponent(products)}" in source
    assert source.count("const PANEL_KEY = \"network-traffic-history\"") == 1
    assert source.count("key: PANEL_KEY") == 2
    assert "    return;\n  }\n\n  const PRODUCT_ORDER" in source
    assert "fetch(" not in source
    assert "AbortController" not in source
    assert "setInterval(" not in source and "setTimeout(" not in source
    assert "visibilitychange" not in source and "pagehide" not in source
    assert "innerHTML" not in source
    assert "ap_limit" not in source and "ap_cursor" not in source
    assert "traffic-ap-selector" not in source
    assert "traffic-ap-next" not in source and "traffic-ap-previous" not in source
    assert "document.createElementNS(elements.chart.namespaceURI" in source


def test_ap_real_node_renders_all_twelve_cards_with_two_paths_each(tmp_path):
    harness = r'''
const assert=(value,message)=>{if(!value)throw new Error(message);};
class Element {
  constructor(id,namespaceURI=null){this.id=id;this.namespaceURI=namespaceURI;this.dataset={};this.textContent="";this.attributes={};this.children=[];this.listeners={};this.className="";}
  setAttribute(key,value){this.attributes[key]=String(value);}
  replaceChildren(...children){this.children=[...children];}
  appendChild(child){this.children.push(child);return child;}
  addEventListener(type,handler){this.listeners[type]=handler;}
}
const svgNamespace="urn:test-svg";
const ids={};
function add(id,namespace=null){const item=new Element(id,namespace);ids[id]=item;return item;}
const root=add("admin-page");root.dataset.page="traffic";root.dataset.trafficEnabled="true";
const history=add("traffic-history-panel");history.dataset.historyEnabled="true";
const statistics=add("traffic-statistics-panel");statistics.dataset.statisticsEnabled="true";
const peak=add("traffic-peak-panel");peak.dataset.peakEnabled="true";
const ap=add("traffic-ap-panel");ap.dataset.apEnabled="true";
for(const id of ["traffic-history-state","traffic-history-state-title","traffic-history-state-message",
  "traffic-history-applied-range","traffic-history-coverage","traffic-history-watermark","traffic-history-gaps",
  "traffic-history-source-transitions","traffic-history-timezone",
  "traffic-statistics-state","traffic-statistics-state-title","traffic-statistics-state-message",
  "traffic-statistics-average-download","traffic-statistics-average-upload","traffic-statistics-average-total",
  "traffic-statistics-peak-download","traffic-statistics-peak-upload","traffic-statistics-peak-total",
  "traffic-statistics-applied-range","traffic-statistics-coverage","traffic-statistics-interval-coverage",
  "traffic-statistics-watermark","traffic-peak-state","traffic-peak-state-title","traffic-peak-state-message",
  "traffic-peak-download","traffic-peak-download-at","traffic-peak-upload","traffic-peak-upload-at",
  "traffic-peak-total","traffic-peak-total-at","traffic-peak-bucket","traffic-peak-bucket-range",
  "traffic-peak-hour","traffic-peak-hour-range","traffic-peak-applied-range","traffic-peak-coverage",
  "traffic-peak-watermark","traffic-peak-source-transitions","traffic-ap-state","traffic-ap-state-title",
  "traffic-ap-state-message","traffic-ap-applied-range","traffic-ap-population","traffic-ap-coverage",
  "traffic-ap-current","traffic-ap-items"]){add(id);}
add("traffic-history-chart-svg",svgNamespace);
let registered=null,requests=[];
const coordinator={registerPanel(value){registered=value;},refreshPanel(){}};
const range={selected(){return "24h";},subscribe(){}};
global.window={CaptivPortalTrafficCoordinator:coordinator,CaptivPortalTrafficNetworkRange:range};
global.document={
  getElementById(id){return ids[id]||null;},
  createElement(name){return new Element(name);},
  createElementNS(namespace,name){return new Element(name,namespace);},
};
global.Intl={DateTimeFormat(){return{resolvedOptions(){return{timeZone:"UTC"};}}}};
function payload(){
  const count=288,start=Date.parse("2026-08-29T12:00:00.000Z"),bucket=300;
  const buckets=Array.from({length:count},(_,index)=>({
    bucket_start_utc:new Date(start+index*bucket*1000).toISOString(),
    bucket_end_utc:new Date(start+(index+1)*bucket*1000).toISOString(),
    download_mbps:12,upload_mbps:3,total_mbps:15,status:"complete",selected_source:"wired",
    selection_reason:"primary_full_coverage",source_changed_from_previous:false,
    complete_site_sample_count:1,excluded_site_sample_count:0,gap_count_over_threshold:0,
    selected_source_skew_excluded_sample_count:0,
  }));
  const item=(index)=>({
    ap_mac:`02:AA:BB:CC:DD:${index.toString(16).padStart(2,"0").toUpperCase()}`,
    display_name:`AP ${index}`,display_name_source:"current",status:"complete",
    history:{status:"complete",series:{encoding:"outer_history_bucket_aligned_du.v1",bucket_count:count,
      status:Array(count).fill("complete"),download_mbps:Array(count).fill(1),upload_mbps:Array(count).fill(.25)},
      average:{download_mbps:1,upload_mbps:.25,total_mbps:1.25},
      peak:{download_mbps:1,upload_mbps:.25,total_mbps:1.25},
      coverage:{status:"complete",bucket_count:count,complete_bucket_count:count,partial_bucket_count:0,
        missing_bucket_count:0,sample_opportunity_count:count,accepted_sample_count:count,
        site_accepted_interval_seconds:86100,ap_accepted_interval_seconds:86100,ap_interval_coverage_ratio:1,
        no_baseline_count:0,counter_reset_count:0,gap_too_large_count:0,invalid_elapsed_count:0,
        source_unavailable_count:0,missing_selected_source_sample_count:0,source_transition_excluded_interval_count:0}},
    now:{status:"valid",download_mbps:1,upload_mbps:.25,total_mbps:1.25,download_reason:"ok",
      upload_reason:"ok",observed_at:new Date(start+count*bucket*1000).toISOString(),age_seconds:0,selected_source:"wired"},
  });
  return {api_version:"admin.read.v1",site_id:"site-a",result:{status:"ok",
    range:{id:"24h",from_utc:new Date(start).toISOString(),to_utc:new Date(start+86400000).toISOString(),
      evaluated_at_utc:new Date(start+86400000).toISOString(),bucket_seconds:bucket,bucket_count:count,unit:"Mbps",
      aggregation:"mean_of_complete_site_rate_samples",metric_version:"network_traffic_history.v1",
      source_kind:"observation_ap_dynamic",sample_timestamp_semantics:"cycle_finished_at",bucket_alignment:"range_start_utc",
      max_site_history_buckets:720,max_site_sample_source_skew_seconds:60},
    buckets,coverage:{status:"complete",available_from_utc:buckets[0].bucket_start_utc,
      available_through_utc:buckets[count-1].bucket_end_utc,source_watermark_utc:buckets[count-1].bucket_end_utc,
      source_age_seconds:0,bucket_count:count,complete_bucket_count:count,partial_bucket_count:0,missing_bucket_count:0,
      canonical_cycle_count:count,complete_site_sample_count:count,excluded_site_sample_count:0,gap_bucket_count:0,
      source_transition_count:0},quality:{},
    ap_traffic:{status:"ok",metric_version:"network_traffic_by_ap.v1",unit:"Mbps",
      history_series_encoding:"outer_history_bucket_aligned_du.v1",
      history_bucket_method:"mean_of_accepted_ap_rates_for_canonical_site_bucket_samples.v1",
      average_method:"right_endpoint_ap_sample_hold_time_weighted.v1",peak_method:"max_accepted_complete_ap_sample.v1",
      ap_order_method:"ap_mac_ascending.v1",population:{population_method:"current_union_historical_validated.v1",
        population_count:12,current_population_count:12,historical_population_count:12,supported_max_ap_count:12,
        returned_ap_count:12,population_complete:true},current_snapshot:{source_kind:"observation_ap_dynamic",
          cycle_id:"current-cycle",evaluated_at:new Date(start+86400000).toISOString(),
          observed_at:new Date(start+86400000).toISOString(),newest_observed_at:new Date(start+86400000).toISOString(),
          freshness_status:"fresh",freshness_reason:"within_freshness_window",selected_source:"wired"},
        items:Array.from({length:12},(_,index)=>item(index))}}};
}
'''
    script = harness + _panel_source() + r'''
assert(registered!==null,"history panel registered");
(async()=>{
  const result=await registered.load({apiBase:"/admin/api/v1/sites/site-a",siteId:"site-a",requestJson:async(url)=>{requests.push(url);return payload();}});
  registered.render(result);
  assert(requests.length===1,"one combined request");
  assert(requests[0].includes("include=statistics%2Cpeak%2Caps"),"canonical encoded combined include");
  assert(decodeURIComponent(requests[0]).includes("include=statistics,peak,aps"),"canonical decoded combined include");
  const cards=ids["traffic-ap-items"].children;
  assert(cards.length===12,"all twelve AP cards");
  for(const card of cards){const svg=card.children.find((child)=>child.id==="svg");assert(svg,"one AP svg");assert(svg.children.length===2,"two AP paths");}
  console.log("traffic-ap-node-ok");
})().catch((error)=>{console.error(error);process.exit(1);});
'''
    assert "traffic-ap-node-ok" in _run_node(tmp_path, script)
