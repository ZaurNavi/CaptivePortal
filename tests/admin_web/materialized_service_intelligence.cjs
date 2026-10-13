"use strict";
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const full=fs.readFileSync(process.argv[2],'utf8');
const source=full.slice(full.indexOf('/* NI-04: independent bounded Service Intelligence coordinator. */'));
const site='0123456789abcdef01234567',device='10000000-0000-4000-8000-000000000001';
const at='2026-10-12T00:00:00.000000Z',event='2026-10-11T23:59:00.000000Z';
const service={service_id:'service.youtube',display_name:'YouTube',organization_id:'org.google',organization_display_name:'Google',service_category_id:'category.video_streaming',service_category_display_name:'Video Streaming',last_observed_at:event,support_state:'directly_supported'};
const {last_observed_at,...last}=service;
const base={api_version:'admin.device.service-intelligence.v3',request_id:device,site_id:site,page:null,result:{
  schema_version:3,site_id:site,device_id:device,evaluated_at_utc:at,
  window:{from_utc:'2026-10-11T00:00:00.000000Z',to_utc:at,duration_seconds:86400,recent_from_utc:'2026-10-11T23:00:00.000000Z',recent_duration_seconds:3600},
  availability_state:'degraded',evidence_state:'supported_results_present',identity_binding_state:'authoritative',recent_services:[service],
  service_categories:[{service_category_id:service.service_category_id,display_name:service.service_category_display_name,last_observed_at:event}],last_service_observation:{...last,observed_at:event},freshness_state:'fresh',
  coverage:{scope:'confirmed_device_evidence',source_state:'usable',pipeline_attribution_state:'usable',device_evidence_binding_state:'authoritative',device_linked_pending:false,recognition_state:'usable',historical_window_completeness_claimed:false},
  recognition_ruleset_id:'captivportal.network-intelligence.service-recognition',recognition_ruleset_version:1,recognition_ruleset_digest_sha256:'a'.repeat(64),taxonomy_id:'captivportal.network-intelligence.recognition-taxonomy',taxonomy_version:1,taxonomy_digest_sha256:'b'.repeat(64),
  materialization:{state:'lagging',window_coverage_state:'partial',last_successful_update_at_utc:at,lag_seconds:11}}};
class Element {
 constructor(){this.dataset={};this.children=[];this.listeners={};this.text='';}
 get textContent(){return this.text+this.children.map(e=>e.textContent).join(' ');}
 set textContent(v){this.text=String(v);this.children=[];}
 appendChild(e){this.children.push(e);} replaceChildren(...v){this.children=v;this.text='';}
 setAttribute(){} addEventListener(k,f){this.listeners[k]=f;}
}
function fixture(payload,mode='serve'){
 const ids=Object.fromEntries(['admin-page','device-service-intelligence','device-service-content','device-service-state','device-service-refresh'].map(k=>[k,new Element()]));
 ids['admin-page'].dataset={page:'device',siteId:site,deviceId:device};ids['device-service-intelligence'].dataset={materializationMode:mode};
 let observe,calls=0;const timers=new Map();let n=0;
 const document={hidden:false,getElementById:k=>ids[k]||null,createElement:()=>new Element(),addEventListener(){}};
 class Observer{constructor(f){observe=f;}observe(){}}
 class FixedDate extends Date{static now(){return Date.parse(at);}}
 const window={addEventListener(){},setTimeout(f,ms){timers.set(++n,{f,ms});return n;},clearTimeout(k){timers.delete(k);},fetch:async()=>{calls++;return {ok:true,status:200,headers:{get:()=> 'application/json'},text:async()=>JSON.stringify(payload)};}};
 vm.runInNewContext(source,{document,window,Date:FixedDate,AbortController,TextEncoder,IntersectionObserver:Observer});
 return {ids,timers,get calls(){return calls;},visible(){observe([{isIntersecting:true}]);}};
}
const settle=()=>new Promise(r=>setImmediate(r));
(async()=>{
 let f=fixture(base);f.visible();await settle();
 assert.equal(f.ids['device-service-content'].children.length,4);
 assert.match(f.ids['device-service-content'].textContent,/Materialization: lagging/);
 assert.match(f.ids['device-service-state'].textContent,/Confirmed stored service evidence is shown/);
 assert.ok([...f.timers.values()].some(t=>t.ms===120000));
 f.visible();await settle();assert.equal(f.calls,1);
 const empty=structuredClone(base);Object.assign(empty.result,{recent_services:[],service_categories:[],last_service_observation:null,freshness_state:'unavailable',evidence_state:'materialization_incomplete'});
 f=fixture(empty);f.visible();await settle();assert.match(f.ids['device-service-state'].textContent,/not fully materialized.*unknown/);
 const current=structuredClone(base);Object.assign(current.result.materialization,{state:'current',window_coverage_state:'complete',lag_seconds:0});current.result.availability_state='usable';
 f=fixture(current);f.visible();await settle();assert.match(f.ids['device-service-content'].textContent,/Materialization: current/);
 for(const mutate of [p=>p.result.materialization.lag_seconds=true,p=>p.result.materialization.lag_seconds=-1,p=>p.result.materialization.extra='not_allowed',p=>p.result.materialization.state='healthy',p=>p.result.schema_version=2,p=>p.api_version='admin.device.service-intelligence.v2',p=>delete p.result.materialization]){
  const bad=structuredClone(base);mutate(bad);f=fixture(bad);f.visible();await settle();assert.equal(f.ids['device-service-content'].children.length,0);
 }
 for(const mode of ['off','shadow']){f=fixture(base,mode);f.visible();await settle();assert.equal(f.ids['device-service-content'].children.length,0);}
 console.log('NI04_MATERIALIZED_FRONTEND_PASS');
})().catch(error=>{console.error(error);process.exitCode=1;});
