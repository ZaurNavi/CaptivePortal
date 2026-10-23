"use strict";
const assert=require("node:assert/strict"),fs=require("node:fs"),vm=require("node:vm");
const [sourcePath,fixturePath,scenario]=process.argv.slice(2);
const source=fs.readFileSync(sourcePath,"utf8"),fixture=JSON.parse(fs.readFileSync(fixturePath,"utf8"));
class Node {
 constructor(tag){this.tagName=tag;this.children=[];this.dataset={};this.handlers={};this.textContent="";this.hidden=false;}
 append(...values){this.children.push(...values);} replaceChildren(...values){this.children=[...values];}
 addEventListener(name,fn){this.handlers[name]=fn;} setAttribute(name,value){this[name]=String(value);}
 get classList(){return {toggle:()=>{}};} get style(){return {setProperty:()=>{}};}
 getBoundingClientRect(){return {left:10,top:100,right:200,bottom:300,width:190,height:200};}
 scrollIntoView(){} focus(){} set innerHTML(value){throw Error("innerHTML forbidden");}
}
const ids=new Map(["db-services-page","ops-status-title","ops-updated","ops-warning","refresh-button","ops-summary","ops-services","ops-databases","ops-topology-board","ops-flow-relations","ops-flow-context"].map(id=>[id,new Node("div")]));
const root=ids.get("db-services-page");
root.dataset={apiBase:"/admin/api/v1/operations/db-services",apiV2:"/admin/api/v2/operations/db-services",apiV3:"/admin/api/v3/operations/db-services",apiV4:"/admin/api/v4/operations/db-services"};
const document={hidden:false,handlers:{},getElementById:id=>ids.get(id),createElement:tag=>new Node(tag),createElementNS:(_,tag)=>new Node(tag),addEventListener(name,fn){this.handlers[name]=fn;}};
const window={handlers:{},addEventListener(name,fn){this.handlers[name]=fn;},requestAnimationFrame:()=>1,cancelAnimationFrame:()=>{}};
const all=node=>[node,...node.children.flatMap(all)],text=node=>all(node).map(n=>n.textContent).join(" ");
let serial=0,calls=[],timers=new Map(),active=0,maxActive=0;
const target=scenario.startsWith("fallback-")?Number(scenario.at(-1)):4;
const context={document,window,Map,Set,Number,String,Array,Math,Promise,Date,
 setTimeout:(fn,ms)=>{timers.set(++serial,{fn,ms});return serial;},clearTimeout:id=>timers.delete(id),
 AbortController:class {constructor(){this.signal={};}abort(){}},
 fetch:async(url,options)=>{
  calls.push(url);active++;maxActive=Math.max(maxActive,active);
  try{
   assert.equal(options.credentials,"same-origin");assert.equal(options.cache,"no-store");
   const version=Number(url.match(/\/v(\d)\//)[1]);
   if(version>target)return {status:404,ok:false,json:async()=>({})};
   if(["401","403","500","503"].includes(scenario) || scenario==="refresh-failure" && calls.length>1)
    return {status:scenario==="refresh-failure"?503:Number(scenario),ok:false,json:async()=>({error:{code:"operations_unavailable"}})};
   if(scenario==="bad-json")return {status:200,ok:true,json:async()=>{throw Error("invalid");}};
   const value=structuredClone(fixture);value.api_version=`admin.operations.db-services.v${version}`;
   if(version===3)value.workload={network_metadata_projection:value.workload.network_metadata_projection};
   if(version<3)delete value.workload;
   if(scenario==="bad-version")value.api_version="admin.operations.db-services.v3";
   if(scenario==="bad-count")value.workload.network_service_recognition.feed_backlog_entries=true;
   if(scenario==="bad-tuple")value.workload.fingerprint_sensor.spool_pending_rows=null;
   if(scenario==="bad-check")value.databases[0].store_verification.scope=["PRIVATE"];
   if(scenario==="extra-workload")value.workload.private="PRIVATE";
   return {status:200,ok:true,json:async()=>value};
  }finally{active--;}
 }};
const tick=async()=>{await new Promise(resolve=>setImmediate(resolve));};
function checkMetrics(known){
 const sensorCard=ids.get("ops-services").children.find(n=>n.id==="ops-service-row-fingerprint_sensor");
 const ownerCard=ids.get("ops-services").children.find(n=>n.id==="ops-service-row-network_service_recognition");
 const nodes=all(ids.get("ops-topology-board"));
 const sensorNode=nodes.find(n=>n.dataset.nodeId==="svc:fingerprint_sensor");
 const ownerNode=nodes.find(n=>n.dataset.nodeId==="svc:network_service_recognition");
 const rows=known?fixture.workload.fingerprint_sensor.spool_pending_rows:null;
 for(const item of [sensorCard,sensorNode]){
  assert(text(item).includes(`Spool pending: ${rows??"Unknown"}`));
  assert(text(item).includes(`Spool size: ${known?"1.0 MB":"Unknown"}`));
  assert(text(item).includes(`Oldest pending: ${known && rows>0?"42s":"Unknown"}`));
 }
 for(const item of [ownerCard,ownerNode])assert(text(item).includes("Feed backlog: Unknown"));
 assert(!text(ids.get("ops-databases")).includes("Spool pending:"));
 assert(!text(ids.get("ops-databases")).includes("Feed backlog:"));
 assert.equal(nodes.filter(n=>n.dataset.nodeType).length,31);
 assert.equal(nodes.filter(n=>n.dataset.edgeId).length,45);
}
(async()=>{
 vm.runInNewContext(source,context,{timeout:1000});await tick();
 assert.equal(calls.length,5-target);assert(calls[0].includes("/v4/"));assert.equal(maxActive,1);
 const rejected=["401","403","500","503","bad-json","bad-version","bad-count","bad-tuple","bad-check","extra-workload"].includes(scenario);
 if(rejected){assert.equal(ids.get("ops-services").children.length,0);assert.equal(ids.get("ops-status-title").textContent,"Unavailable");}
 else{
  assert.equal(ids.get("ops-services").children.length,9);assert.equal(ids.get("ops-databases").children.length,17);
  checkMetrics(target===4 && !["unknown","stale"].includes(scenario));
 }
 assert.equal(timers.size,1);assert.equal([...timers.values()][0].ms,15000);
 const before=calls.length;document.hidden=true;document.handlers.visibilitychange();assert.equal(timers.size,0);
 await ids.get("refresh-button").handlers.click();assert.equal(calls.length,before);
 document.hidden=false;document.handlers.visibilitychange();await tick();
 assert.equal(calls.length,before+1);assert(calls.at(-1).includes(`/v${target}/`));
 if(scenario==="refresh-failure")checkMetrics(false);
 console.log("PASS v4 closed workload / same cards and topology / sticky 404-only negotiation");
})().catch(error=>{console.error(error);process.exitCode=1;});
