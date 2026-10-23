"use strict";
const assert=require("node:assert/strict"),fs=require("node:fs"),vm=require("node:vm");
const [sourcePath,fixturePath,scenario]=process.argv.slice(2);
const source=fs.readFileSync(sourcePath,"utf8"),payload=JSON.parse(fs.readFileSync(fixturePath,"utf8")),fixture=payload.snapshot;
class Node {
  constructor(tag){this.tagName=tag;this.children=[];this.dataset={};this.handlers={};this.textContent="";this.hidden=false;this.className="";}
  append(...values){this.children.push(...values);} replaceChildren(...values){this.children=[...values];}
  addEventListener(name,fn){this.handlers[name]=fn;} setAttribute(name,value){this[name]=String(value);if(name==="class")this.className=String(value);}
  get classList(){return {toggle:()=>{}};} get style(){return {setProperty:()=>{}};}
  getBoundingClientRect(){return {left:10,top:100,right:200,bottom:300,width:190,height:200};}
  scrollIntoView(){} focus(){} set innerHTML(value){throw Error("innerHTML forbidden");}
}
const ids=new Map(["db-services-page","ops-status-title","ops-updated","ops-warning","refresh-button","ops-summary","ops-services","ops-databases","ops-topology-board","ops-flow-relations","ops-flow-context"].map(name=>[name,new Node("div")]));
const root=ids.get("db-services-page");
root.dataset={apiBase:"/admin/api/v1/operations/db-services",apiV2:"/admin/api/v2/operations/db-services",apiV3:"/admin/api/v3/operations/db-services"};
const document={hidden:false,handlers:{},getElementById:id=>ids.get(id),createElement:tag=>new Node(tag),createElementNS:(_,tag)=>new Node(tag),addEventListener(name,fn){this.handlers[name]=fn;}};
const window={innerWidth:1440,handlers:{},addEventListener(name,fn){this.handlers[name]=fn;},requestAnimationFrame:()=>1,cancelAnimationFrame:()=>{}};
const all=node=>[node,...node.children.flatMap(all)],text=node=>all(node).map(n=>n.textContent).join(" ");
let sequence=0,calls=[],timers=new Map(),active=0,maxActive=0;
let wall=Date.parse(fixture.sampling_completed_at_utc);
class Clock extends Date {static now(){return wall;}}
const context={document,window,Map,Set,Number,String,Array,Math,Promise,Date:Clock,
 setTimeout:(fn,ms)=>{timers.set(++sequence,{fn,ms});return sequence;},clearTimeout:id=>timers.delete(id),
 AbortController:class {constructor(){this.signal={};}abort(){}},
 fetch:async(url,options)=>{
  calls.push(url);active+=1;maxActive=Math.max(maxActive,active);
  try {
   assert.equal(options.credentials,"same-origin");assert.equal(options.cache,"no-store");
   if((scenario==="fallback-v2" || scenario==="fallback-v1") && url.includes("/v3/") || scenario==="fallback-v1" && url.includes("/v2/"))
    return {status:404,ok:false,json:async()=>({})};
   if(["401","403","500","503"].includes(scenario) || scenario==="stale-refresh" && calls.length>1)
    return {status:scenario==="stale-refresh"?503:Number(scenario),ok:false,json:async()=>({error:{code:"operations_unavailable"}})};
   if(scenario==="network")throw Error("offline");
   if(scenario==="bad-json")return {status:200,ok:true,json:async()=>{throw Error("invalid");}};
   const model=structuredClone(fixture);
   if(url.includes("/v2/") || url.includes("/v1/")){
    model.api_version=`admin.operations.db-services.${url.includes("/v2/")?"v2":"v1"}`;delete model.workload;
   }
   if(scenario==="bad-count")model.workload.network_metadata_projection.pending_attribution_count=true;
   if(scenario==="extra-workload")model.workload.raw="PRIVATE";
   if(scenario==="bad-health")model.services[0].application_health_evidence.pid=123;
   if(scenario==="bad-check")model.databases[0].store_verification.scope=["PRIVATE"];
   return {status:200,ok:true,json:async()=>model};
  }finally {active-=1;}
 }};
const tick=async()=>{await new Promise(resolve=>setImmediate(resolve));};
(async()=>{
 // Expose only to this VM harness; shipped source remains byte-unmodified.
 const at=source.lastIndexOf("  load();");assert(at>0);
 vm.runInNewContext(source.slice(0,at)+payload.legacy_database_condition+"\n  globalThis.conditions={databaseCondition,serviceCondition,legacyDatabaseCondition};\n"+source.slice(at),context,{timeout:1000});
 await tick();
 const fallback=scenario==="fallback-v1"?3:scenario==="fallback-v2"?2:1;
 assert.equal(calls.length,fallback);assert(calls[0].includes("/v3/"));assert.equal(maxActive,1);
 const rejected=["401","403","500","503","network","bad-json","bad-count","extra-workload","bad-health","bad-check"].includes(scenario);
 if(rejected){assert.equal(ids.get("ops-services").children.length,0);assert.equal(ids.get("ops-status-title").textContent,"Unavailable");}
 else {
  assert.equal(ids.get("ops-services").children.length,9);assert.equal(ids.get("ops-databases").children.length,17);
  const count=scenario.startsWith("fallback-")?"Unknown":String(fixture.workload.network_metadata_projection.pending_attribution_count??"Unknown");
  for(const id of ["ops-services","ops-topology-board"])assert(text(ids.get(id)).includes(`Pending attribution: ${count}`));
  const ni02db=all(ids.get("ops-topology-board")).find(n=>n.dataset.nodeId==="db:network_metadata_projection");
  const expected=scenario==="failed-check" || scenario==="unsafe-file" ? "failed" :
   ["stale-check","stopped-writer","missing-check","changed-check"].includes(scenario)?"unknown":
   scenario==="degraded-writer"?"degraded":"operating";
  assert.equal(ni02db.dataset.condition,expected);
  if(expected==="operating")assert(text(ni02db).includes("Operating · startup check OK"));
  assert(text(ids.get("ops-services")).includes("Degraded")); // APP issue stays visible, independently.
 }
 // Other 16 stores still inherit real writer APP degradation.
 for(const original of fixture.databases.filter(r=>r.id!=="network_metadata_projection")){
  const model=structuredClone(fixture),row=model.databases.find(r=>r.id===original.id);
  row.operational_state="present_unverified";row.file_presence="present";row.reason_code=null;
  row.store_verification={status:"not_attested",scope:null,as_of:null,source:"none"};
  for(const owner of model.services.filter(r=>row.writer_service_ids.includes(r.id))){owner.operational_state="running";owner.application_health="degraded";}
  assert.equal(context.conditions.databaseCondition(row,model),context.conditions.legacyDatabaseCondition(row,model),original.id);
  for(const state of ["failed","stopped","degraded"]){
   for(const owner of model.services.filter(r=>row.writer_service_ids.includes(r.id)))owner.operational_state=state;
   assert.equal(context.conditions.databaseCondition(row,model),context.conditions.legacyDatabaseCondition(row,model),`${original.id}/${state}`);
  }
 }
 assert.equal(timers.size,1);assert.equal([...timers.values()][0].ms,15000);
 const before=calls.length;document.hidden=true;document.handlers.visibilitychange();assert.equal(timers.size,0);
 await ids.get("refresh-button").handlers.click();assert.equal(calls.length,before);
 if(scenario==="stale-refresh")wall+=91_000;
 document.hidden=false;document.handlers.visibilitychange();await tick();
 assert.equal(calls.length,before+1); // Sticky version; no retry loop on refresh.
 assert(calls.at(-1).includes(scenario==="fallback-v1"?"/v1/":scenario==="fallback-v2"?"/v2/":"/v3/"));
 if(scenario==="stale-refresh")for(const id of ["ops-services","ops-topology-board"])assert(text(ids.get(id)).includes("Pending attribution: Unknown"));
 assert(!text(ids.get("ops-services")).includes("PRIVATE"));
 console.log("PASS v3 workload / NI02 independent DB / strict fallback / unchanged polling");
})().catch(error=>{console.error(error);process.exitCode=1;});
