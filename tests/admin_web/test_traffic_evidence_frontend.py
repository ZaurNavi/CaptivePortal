from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ADMIN_JS = ROOT / "app" / "admin_web" / "static" / "admin.js"
TRAFFIC_TEMPLATE = ROOT / "app" / "admin_web" / "templates" / "admin" / "traffic.html"
BASE_TEMPLATE = ROOT / "app" / "admin_web" / "templates" / "admin" / "base.html"


def _block(source: str, name: str) -> str:
    start = f"/* {name}_START */"
    end = f"/* {name}_END */"
    assert source.count(start) == source.count(end) == 1
    return source.split(start, 1)[1].split(end, 1)[0]


def test_template_places_evidence_after_all_traffic_products_and_uses_real_dataset():
    template = TRAFFIC_TEMPLATE.read_text(encoding="utf-8")
    base = BASE_TEMPLATE.read_text(encoding="utf-8")
    assert 'data-traffic-evidence-enabled="' in base
    assert template.index('id="traffic-evidence-panel"') > template.index(
        'id="traffic-apshare-panel"'
    )
    assert "No overall score is calculated" in template
    for product in (
        "current", "history", "statistics", "peak", "aps", "apshare",
        "online_guests", "completed_sessions",
    ):
        assert f"('{product}'," in template
    assert 'data-product-id="{{ product_id }}"' in template


def test_evidence_real_node_validation_render_range_and_security_clear(tmp_path):
    panel = _block(ADMIN_JS.read_text(encoding="utf-8"), "TRAFFIC_EVIDENCE_PANEL")
    script = r'''
"use strict";
class Element {
  constructor(id="") { this.id=id;this.dataset={};this.hidden=false;this.disabled=false;this.textContent="";this.listeners={};this.attrs={}; }
  addEventListener(name,callback){this.listeners[name]=callback;}
  click(){if(this.listeners.click)this.listeners.click();}
  setAttribute(name,value){this.attrs[name]=String(value);}
}
const products=["current","history","statistics","peak","aps","apshare","online_guests","completed_sessions"];
const ids=new Map();function element(id){if(!ids.has(id))ids.set(id,new Element(id));return ids.get(id);}
const root=element("admin-page");root.dataset={page:"traffic",trafficEnabled:"true",trafficEvidenceEnabled:"true"};
for(const name of ["panel","state","state-title","state-message","range","range-24h","range-7d","range-note","products"])element(`traffic-evidence-${name}`);
for(const id of products)for(const name of ["exposure","delivery","native","detail"])element(`traffic-evidence-${id}-${name}`);
global.document={getElementById:element};let spec=null;const refreshes=[];
global.window={CaptivPortalTrafficCoordinator:{registerPanel(value){spec=value;return true;},refreshPanel(key,options){refreshes.push([key,options]);return Promise.resolve(true);}}};
eval(PANEL);
if(!spec||spec.autoRefresh!==false||spec.historicalLane!==true||spec.historicalLaneGuard!==true)throw new Error("registration");
const evaluated="2026-09-07T10:00:00.000Z",from24="2026-09-06T10:00:00.000Z",from7="2026-08-31T10:00:00.000Z";
function historicalScope(range,from){return {kind:"historical_range",range_id:range,from_utc:from,to_utc:evaluated,evaluated_at_utc:evaluated};}
function wrapper(id,range,from){let scope=historicalScope(range,from);if(id==="current")scope={kind:"current_snapshot",evaluated_at_utc:evaluated};if(id==="online_guests")scope={kind:"current_authorized_population",evaluated_at_utc:evaluated};if(id==="completed_sessions")scope=null;return {product_id:id,exposure_status:"disabled",delivery_status:"not_attempted",scope,evidence:null,failure_category:null};}
function payload(range="24h"){const from=range==="24h"?from24:from7;const resultProducts=Object.fromEntries(products.map((id)=>[id,wrapper(id,range,from)]));resultProducts.current={product_id:"current",exposure_status:"enabled",delivery_status:"available",scope:{kind:"current_snapshot",evaluated_at_utc:evaluated},failure_category:null,evidence:{freshness_status:"fresh",freshness_reason:"within_freshness_window",observed_at:evaluated,newest_observed_at:evaluated,age_seconds:0,source_skew_seconds:0,complete:true,primary_source:"wired",selected_source:"wired",selection_reason:"primary_full_coverage",coverage_status:"complete",total_ap_count:2,valid_rate_ap_count:2,missing_rate_ap_count:0,stale_ap_count:0,unavailable_ap_count:0,reset_ap_count:0,gap_rejected_ap_count:0,no_baseline_ap_count:0,source_unavailable_ap_count:0,invalid_elapsed_ap_count:0}};resultProducts.online_guests={product_id:"online_guests",exposure_status:"enabled",delivery_status:"available",scope:{kind:"current_authorized_population",evaluated_at_utc:evaluated},failure_category:null,evidence:{status:"insufficient_data",metric_version:"network_traffic_online_guest_current_rate.v1",population_method:"fresh_complete_current_state_authorized_guest_scope.v1",rate_method:"current_connection_counter_delta_interval_average.v1",baseline_method:"nearest_previous_complete_same_site_scope_cycle.v1",continuity_method:"omada_controller_connection_progress_v1",connection_boundary_observation:"sampled_current_state_evidence_v1",source_health_status:"healthy",source_health_reason:"within_freshness_window",rate_evidence_status:"insufficient_data",population_complete:true,scoped_client_row_count:2,known_authorized_count:2,unknown_auth_count:0,population_count:2,rate_valid_count:0,rate_partial_count:0,rate_unavailable_count:2,current_capture_started_at:evaluated,baseline_capture_started_at:null,elapsed_seconds:null}};resultProducts.completed_sessions={product_id:"completed_sessions",exposure_status:"enabled",delivery_status:"available",scope:{kind:"completion_first_page",range_id:range,from_utc:from,to_utc:evaluated,evaluated_at_utc:evaluated,limit:100,returned_count:100,has_more:true},failure_category:null,evidence:{status:"partial",metric_version:"network_traffic_completed_guest_session_observed_bytes.v1",session_method:"closed_visit_completion_cohort.v1",attribution_method:"visit_window_observation_counter_interval_sum.v1",continuity_method:"observation_uptime_progress.v1",visits_source_status:"healthy",observations_source_status:"healthy",complete_count:0,partial_count:94,insufficient_data_count:6,unavailable_count:0,reason_counts:{continuity_frozen:94,gap_too_large:3}}};return {api_version:"admin.read.v1",request_id:"request",site_id:"aaaaaaaaaaaaaaaaaaaaaaaa",page:null,result:{contract_version:"admin.traffic.evidence.v1",evaluated_at_utc:evaluated,evidence_range:{id:range,from_utc:from,to_utc:evaluated},products:resultProducts}};}
const requested=[];const context={siteId:"aaaaaaaaaaaaaaaaaaaaaaaa",apiBase:"/admin/api/v1/sites/aaaaaaaaaaaaaaaaaaaaaaaa",requestJson:async(url)=>{requested.push(url);return payload(url.includes("range=7d")?"7d":"24h");}};
(async()=>{
 const first=await spec.load(context);spec.render(first);
 if(element("traffic-evidence-current-delivery").textContent!=="available")throw new Error("delivery render");
 if(!element("traffic-evidence-current-detail").textContent.includes("Freshness: fresh")||!element("traffic-evidence-current-detail").textContent.includes("Coverage: complete"))throw new Error("current evidence render");
 if(element("traffic-evidence-history-delivery").textContent!=="not_attempted")throw new Error("disabled render");
 if(!element("traffic-evidence-online_guests-detail").textContent.includes("Source: healthy")||!element("traffic-evidence-online_guests-detail").textContent.includes("Rate evidence: insufficient_data"))throw new Error("online evidence render");
 if(element("traffic-evidence-completed_sessions-native").textContent!=="partial")throw new Error("native completed render");
 const completedDetail=element("traffic-evidence-completed_sessions-detail").textContent;
 if(!completedDetail.includes("First page · Returned: 100 · More available: Yes")||!completedDetail.includes("Reasons: continuity_frozen 94 · gap_too_large 3"))throw new Error("first-page evidence render");
 element("traffic-evidence-range-7d").click();if(refreshes.length!==1)throw new Error("range schedules coordinator");
 const second=await spec.load(context);spec.render(second);if(!requested[1].endsWith("range=7d"))throw new Error("range request");
 const malformed=payload("7d");malformed.result.products.current.evidence.freshness_reason="private_reason";
 let rejected=false;try{await spec.load({...context,requestJson:async()=>malformed});}catch(_error){rejected=true;}if(!rejected)throw new Error("private reason accepted");
 spec.renderGlobalFailure({kind:"forbidden"});if(element("traffic-evidence-current-delivery").textContent!=="—")throw new Error("security clear");
 console.log("PASS");
})().catch((error)=>{console.error(error);process.exit(1);});
'''.replace("PANEL", json.dumps(panel))
    script_path = tmp_path / "traffic-evidence-frontend.js"
    script_path.write_text(script, encoding="utf-8")
    result = subprocess.run(
        ["node", str(script_path)], cwd=ROOT, text=True,
        capture_output=True, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == "PASS"


def test_evidence_has_no_private_fetch_timer_or_controller_owner():
    panel = _block(ADMIN_JS.read_text(encoding="utf-8"), "TRAFFIC_EVIDENCE_PANEL")
    assert "omada" not in panel.lower()
    assert "fetch(" not in panel
    assert "new AbortController" not in panel
    assert "setTimeout" not in panel
    assert "localStorage" not in panel and "sessionStorage" not in panel
    assert 'historicalLane: true' in panel
    assert 'historicalLaneGuard: true' in panel
    assert "First page ·" in panel


def test_evidence_range_is_page_local_and_legacy_guard_contracts_remain_distinct():
    source = ADMIN_JS.read_text(encoding="utf-8")
    evidence = _block(source, "TRAFFIC_EVIDENCE_PANEL")
    history = _block(source, "TRAFFIC_HISTORY_PANEL")
    completed = _block(source, "TRAFFIC_COMPLETED_SESSIONS_PANEL")
    assert 'key: "traffic-evidence"' in evidence
    assert 'autoRefresh: false' in evidence
    assert 'historicalLaneGuard: true' in evidence
    assert 'historicalLaneGuard: false' in history
    assert 'historicalLaneGuard: true' in completed
    assert "traffic-history-range-" not in evidence
    assert "traffic-statistics-range-" not in evidence
    assert "traffic-peak-range-" not in evidence
    assert "traffic-ap-range-" not in evidence
    assert "traffic-apshare-range-" not in evidence
