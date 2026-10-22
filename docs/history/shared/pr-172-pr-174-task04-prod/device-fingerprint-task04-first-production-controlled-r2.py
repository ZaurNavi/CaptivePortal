#!/usr/bin/env python3
from __future__ import annotations

import argparse, hashlib, json, os, re, sqlite3, subprocess, sys
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from app.device_fingerprint.artifact_content import ArtifactContent, ArtifactRef
from app.device_fingerprint.classification_persistence import DeviceFingerprintClassificationStore
from app.device_fingerprint.classification_read import DeviceFingerprintClassificationReadService
from app.device_fingerprint.classification_retention_policy import build_initial_classification_retention_policy_v1
from app.device_fingerprint.control_plane_store import DeviceFingerprintControlPlaneStore
from app.device_fingerprint.read_service import DeviceFingerprintReadService
from app.device_fingerprint.request_assembly import DeviceFingerprintRequestAssembly
from app.device_fingerprint.runtime_profile_artifacts import make_classification_runtime_profile
from app.device_fingerprint.validation import format_utc, validate_mac

CURRENT_COMMIT="fecdb5a7c79e56bb49be4797ca875d6720670042"
CURRENT_TREE="85d7d41e1ad19c079cad0ae819a3fe38a068e242"
ACCEPTED_COMMIT="8a39459be3ce7ed40e325736034245f0025cf249"
ACCEPTED_TREE="e2521f27c9f91978e381bce202ab3e3c83aa6dad"
CRP_ID="ClassificationRuntimeProfile:v1:sha256:1d3a563e7ce3a8afb2ff259e596328b14f5ff5ce9940db703cbb93b12c2cbf6c"
CRP_SHA="1d3a563e7ce3a8afb2ff259e596328b14f5ff5ce9940db703cbb93b12c2cbf6c"
RPM_ID="RuntimeProfileAdmissionManifest:v1:sha256:7873028b2c3a85bf152c9bc4ea057e476591ab87d3c3a52b8cdff654beb8c98b"
ACCEPTANCE_ID="Task04AcceptanceManifest:v1:sha256:ca2712fbd643b332594990e67dc95ec017507d2d4d51d61f549d357bad18ca54"
FOUNDATION_RPM_ID="RuntimeProfileAdmissionManifest:v1:sha256:95231fa3dee79b8d0b00a4f645664d3d80d3d4b1b6ca48fc4865191d24b12db6"
FOUNDATION_ADMISSION_ID="FoundationAdmissionManifest:v1:sha256:44f2b26b297c7c126a7b224b8db8f88873893a0cc6819e4e18f6106af00de4ff"
T06A_ID="GateResultManifest:v1:sha256:cd102f0fca7adb9e09ce1ff69d2109b34691e7362fd071a0617fc300547db406"
T09_ID="GateResultManifest:v1:sha256:d231fd0729c1820788f2f708c1135f04d4891d7033c1b3aeb76591fbbe7e895e"
TACCEPT_ID="GateResultManifest:v1:sha256:02634373a1c0cfbade887ed68263cd3b72c6c92b8180dcab57e63067fa5d31eb"
A1_EACS_ID="EvidenceAdapterContractSet:v1:sha256:c9711a816fddae6a8d22f2a07c8561fc363c76f7b39f95cde62b66d9957ef32f"
HIST_EACS_ID="EvidenceAdapterContractSet:v1:sha256:7cca6802ebc5839317643dcb584173b75d985477da687ab0d8fe5802b181f788"
ACTIVATION_ID="c9600739-38c6-4186-b67d-91ada854376f"
GENERATION_ID="a17a67e5-b291-40c3-96f6-182bf33c6da6"
SITE_ID="6a64f17630da7c70d232187a"
MANDATORY={"T-01","T-02","T-03","T-04","T-05","T-06","T-06A","T-07","T-08","T-09"}
ALLOWED_DIFF={
 "app/device_fingerprint/repository.py",
 "deploy/device-fingerprint/README.md",
 "deploy/device-fingerprint/fingerprint-suricata.service",
 "deploy/device-fingerprint/suricata.yaml",
 "tests/device_fingerprint/test_repository.py",
 "tests/device_fingerprint/test_service.py",
 "tests/device_fingerprint_sensor/test_deployment_outputs.py",
}

class Blocked(RuntimeError): pass
def req(v,c):
    if not v: raise Blocked(c)
def digest(a): return a.rsplit(":",1)[1]
def ref(c): return {"artifact_id":c.artifact_id,"content_sha256":c.content_sha256}
def load_id(s,a): return s.load_artifact(a,digest(a))
def load_ref(s,v):
    r=ArtifactRef.from_dict(v); return s.load_artifact(r.artifact_id,r.content_sha256)
def sha(p):
    h=hashlib.sha256()
    with Path(p).open("rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""): h.update(b)
    return h.hexdigest()
def contains(v,a):
    if isinstance(v,dict):
        if v.get("artifact_id")==a:
            return v.get("content_sha256") in (None,digest(a))
        return any(contains(x,a) for x in v.values())
    if isinstance(v,list): return any(contains(x,a) for x in v)
    return v==a

def verify_repo(repo:Path):
    head=subprocess.check_output(["git","-C",str(repo),"rev-parse","HEAD"],text=True).strip()
    tree=subprocess.check_output(["git","-C",str(repo),"rev-parse","HEAD^{tree}"],text=True).strip()
    dirty=subprocess.check_output(["git","-C",str(repo),"status","--porcelain=v1"],text=True)
    req(head==CURRENT_COMMIT,f"DEPLOY_HEAD:{head}")
    req(tree==CURRENT_TREE,f"DEPLOY_TREE:{tree}")
    req(not dirty,"DEPLOY_WORKTREE_DIRTY")
    changed={x for x in subprocess.check_output(
        ["git","-C",str(repo),"diff","--name-only",f"{ACCEPTED_COMMIT}..HEAD"],text=True
    ).splitlines() if x}
    req(changed==ALLOWED_DIFF,"POST_ACCEPTANCE_DIFF:"+",".join(sorted(changed)))

def source_identity_check(repo:Path, manifest:ArtifactContent)->int:
    found={}
    def walk(v):
        if isinstance(v,dict):
            d=v.get("implementation_digest"); p=v.get("repository_relative_source_path")
            i=v.get("implementation_id")
            if isinstance(d,str) and re.fullmatch(r"[0-9a-f]{64}",d):
                if isinstance(p,str) and p: found[p]=d
                elif isinstance(i,str) and i.startswith("python:"):
                    q=i[7:].split(":",1)[0]
                    if q.endswith(".py"): found[q]=d
            for x in v.values(): walk(x)
        elif isinstance(v,list):
            for x in v: walk(x)
    walk(manifest.semantic_payload)
    req(bool(found),"CLASSIFIER_SOURCE_IDENTITIES_ABSENT")
    for rel,expected in sorted(found.items()):
        p=(repo/rel).resolve(strict=True)
        req(p.is_relative_to(repo.resolve(strict=True)),"SOURCE_PATH_ESCAPE")
        req(sha(p)==expected,f"SOURCE_DIGEST:{rel}")
    return len(found)

def count(path:Path,table:str)->int:
    c=sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro",uri=True)
    try:
        req(c.execute("PRAGMA quick_check").fetchone()[0]=="ok",f"{table}_QUICK_CHECK")
        return int(c.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
    finally: c.close()

def accepted_lineage(repo:Path,s:DeviceFingerprintControlPlaneStore):
    p=s.pin_active_profile("classification")
    req(p.pointer.runtime_profile_id==CRP_ID,"ACTIVE_CRP")
    req(p.pointer.runtime_profile_digest==CRP_SHA,"ACTIVE_CRP_SHA")
    req(p.pointer.activation_record_id==ACTIVATION_ID,"ACTIVE_ACTIVATION")
    req(p.pointer.activation_generation_id==GENERATION_ID,"ACTIVE_GENERATION")
    req(p.admission_manifest.artifact_id==RPM_ID,"ACTIVE_RPM")
    req(p.validity_record.semantic_payload["state"]=="ACTIVE","ACTIVE_VALIDITY")

    profile=p.runtime_profile
    req(make_classification_runtime_profile(profile.semantic_payload)==profile,"CRP_NONCANONICAL")
    pp=profile.semantic_payload
    req(pp["evidence_adapter_contract_set"]["artifact_id"]==A1_EACS_ID,"CRP_NOT_A1_EACS")
    direct={k:load_ref(s,v) for k,v in pp.items()
            if isinstance(v,dict) and set(v)=={"artifact_id","content_sha256"}}
    req(direct["evidence_adapter_contract_set"].artifact_id==A1_EACS_ID,"A1_EACS_LOAD")

    rpm=p.admission_manifest; rp=rpm.semantic_payload
    req(rp["profile_kind"]=="classification","RPM_KIND")
    req(rp["candidate_profile"]==ref(profile),"RPM_PROFILE")
    req(rp["update_class"]=="INITIAL_CLASSIFICATION","RPM_UPDATE")
    req(rp["compatibility_validation_result"]=="PASS","RPM_COMPAT")
    req(rp["candidate_repository_commit_sha"]==ACCEPTED_COMMIT,"RPM_COMMIT")
    req(rp["candidate_repository_tree_sha"]==ACCEPTED_TREE,"RPM_TREE")
    req(rp["previous_active_profile"] is None,"RPM_PREVIOUS")
    req(rp["expected_previous_activation_record_id"] is None,"RPM_PREVIOUS_ACTIVATION")
    req(rp["expected_previous_activation_generation_id"] is None,"RPM_PREVIOUS_GENERATION")
    req(rp["foundation_runtime_profile_admission_manifest"]["artifact_id"]==FOUNDATION_RPM_ID,"RPM_FOUNDATION")
    req(rp["task04_acceptance_manifest"]["artifact_id"]==ACCEPTANCE_ID,"RPM_ACCEPTANCE")

    a=load_id(s,ACCEPTANCE_ID); ap=a.semantic_payload
    req(ap["task04_candidate_repository_commit_sha"]==ACCEPTED_COMMIT,"ACC_COMMIT")
    req(ap["task04_candidate_repository_tree_sha"]==ACCEPTED_TREE,"ACC_TREE")
    req(ap["tested_classification_runtime_profile"]==ref(profile),"ACC_PROFILE")
    req(ap["classifier_artifact_manifest"]==ref(direct["classifier_artifact_manifest"]),"ACC_CLASSIFIER")
    req(ap["foundation_admission_manifest"]["artifact_id"]==FOUNDATION_ADMISSION_ID,"ACC_FOUNDATION")
    req(set(ap["mandatory_pre_acceptance_task04_gate_ids"])==MANDATORY,"ACC_GATE_SET")

    gates={}
    for gr in ap["pre_acceptance_task04_gate_result_manifests"]:
        g=load_ref(s,gr); gp=g.semantic_payload
        req(g.artifact_type=="GateResultManifest" and gp.get("status")=="PASS","ACC_GATE_PASS")
        gid=gp.get("gate_id"); req(gid in MANDATORY and gid not in gates,f"ACC_GATE_ID:{gid}")
        gates[gid]=g
    req(set(gates)==MANDATORY,"ACC_GATE_LOAD")
    req(gates["T-06A"].artifact_id==T06A_ID,"T06A_ID")
    req(gates["T-09"].artifact_id==T09_ID,"T09_ID")
    req(contains(gates["T-06A"].semantic_payload,CRP_ID),"T06A_PROFILE_BINDING")
    req(contains(gates["T-09"].semantic_payload,CRP_ID),"T09_PROFILE_BINDING")

    ta=load_id(s,TACCEPT_ID); tp=ta.semantic_payload
    req(tp.get("gate_id")=="T-ACCEPT" and tp.get("status")=="PASS","TACCEPT_PASS")
    req(tp.get("candidate_repository_commit_sha")==ACCEPTED_COMMIT,"TACCEPT_COMMIT")
    req(tp.get("candidate_repository_tree_sha")==ACCEPTED_TREE,"TACCEPT_TREE")
    req(contains(tp,ACCEPTANCE_ID) and contains(tp,RPM_ID) and contains(tp,CRP_ID),"TACCEPT_BINDING")

    fa=load_id(s,FOUNDATION_ADMISSION_ID)
    req(fa.semantic_payload["evidence_adapter_contract_set"]["artifact_id"]==HIST_EACS_ID,"HIST_FOUNDATION_EACS")

    with s._connect() as c:
        s._closure(c,profile); s._closure(c,rpm)

    n=source_identity_check(repo,direct["classifier_artifact_manifest"])
    return p,direct,{
      "active_crp":ref(profile),"active_rpm":ref(rpm),"task04_acceptance":ref(a),
      "final_t06a":ref(gates["T-06A"]),"final_t09":ref(gates["T-09"]),
      "final_taccept":ref(ta),"a1_eacs":ref(direct["evidence_adapter_contract_set"]),
      "historical_foundation_eacs":fa.semantic_payload["evidence_adapter_contract_set"],
      "classifier_source_identities_checked":n,
    }

def rss_guard(limit:int)->bool:
    req(type(limit) is int and limit>0 and os.name=="posix","MEMORY_MEASUREMENT_UNAVAILABLE")
    try:
        pages=int(Path("/proc/self/statm").read_text(encoding="ascii").split()[1])
        rss=pages*int(os.sysconf("SC_PAGE_SIZE"))
    except Exception as e: raise Blocked("MEMORY_MEASUREMENT_UNAVAILABLE") from e
    return rss<=limit

def evidence(path:Path,mac:str,start:str,end:str):
    c=sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro",uri=True); c.row_factory=sqlite3.Row
    try:
        req(c.execute("PRAGMA quick_check").fetchone()[0]=="ok","EVIDENCE_QUICK_CHECK")
        n=int(c.execute("SELECT COUNT(*) FROM device_fingerprint_evidence WHERE site_id=? AND observed_mac=? AND observed_at>=? AND observed_at<?",
                        (SITE_ID,mac,start,end)).fetchone()[0])
        kinds=[dict(r) for r in c.execute("SELECT source_kind,COUNT(*) AS rows FROM device_fingerprint_evidence WHERE site_id=? AND observed_mac=? AND observed_at>=? AND observed_at<? GROUP BY source_kind ORDER BY source_kind",
                                          (SITE_ID,mac,start,end))]
        return n,kinds
    finally: c.close()

def backup(src:Path,dst:Path):
    a=sqlite3.connect(f"{src.resolve().as_uri()}?mode=ro",uri=True); b=sqlite3.connect(dst)
    try:
        a.backup(b); b.commit(); req(b.execute("PRAGMA quick_check").fetchone()[0]=="ok","BACKUP_QUICK_CHECK")
    finally: b.close(); a.close()

def write_json(path:Path,v:Any):
    raw=(json.dumps(v,ensure_ascii=True,sort_keys=True,indent=2)+"\n").encode()
    with path.open("xb") as f: f.write(raw); f.flush(); os.fsync(f.fileno())

def main():
    p=argparse.ArgumentParser()
    m=p.add_mutually_exclusive_group(required=True); m.add_argument("--verify-only",action="store_true"); m.add_argument("--commit",action="store_true")
    p.add_argument("--repo",type=Path,default=Path("/home/admin/CaptivePortal-Deploy/task04-dormant-fecdb5a7"))
    p.add_argument("--control-db",type=Path,default=Path("/opt/CaptivePortal/data/device_fingerprint_control_plane.sqlite3"))
    p.add_argument("--classification-db",type=Path,default=Path("/opt/CaptivePortal/data/device_fingerprint_classification.sqlite3"))
    p.add_argument("--evidence-db",type=Path,default=Path("/opt/CaptivePortal/data/device_fingerprint_evidence.sqlite3"))
    p.add_argument("--mac"); p.add_argument("--window-minutes",type=int,default=15); p.add_argument("--confirm",default="")
    p.add_argument("--audit-root",type=Path,default=Path("/home/admin/captivportal-recovery"))
    a=p.parse_args()
    for x in (a.repo,a.control_db,a.classification_db,a.evidence_db): req(x.exists(),f"MISSING:{x}")

    verify_repo(a.repo)
    control_before=sha(a.control_db); class_before=sha(a.classification_db)
    rows_before=count(a.classification_db,"classifications")
    control=DeviceFingerprintControlPlaneStore(a.control_db)
    pinned,direct,lineage=accepted_lineage(a.repo,control)

    print("POST_ACCEPTANCE_DIFF_SCOPE=PASS")
    print("ACTIVE_CLASSIFICATION_POINTER=EXACT")
    print("ACTIVE_CLASSIFICATION_VALIDITY=ACTIVE")
    print("ACTIVE_CRP="+pinned.runtime_profile.artifact_id)
    print("ACTIVE_RPM="+pinned.admission_manifest.artifact_id)
    print("ACTIVE_A1_EACS="+direct["evidence_adapter_contract_set"].artifact_id)
    print("HISTORICAL_FOUNDATION_EACS="+lineage["historical_foundation_eacs"]["artifact_id"])
    print("FINAL_T06A_EXACT_PROFILE_BINDING=PASS")
    print("FINAL_T09_EXACT_PROFILE_BINDING=PASS")
    print("FINAL_TACCEPT_LINEAGE=PASS")
    print("ACTIVE_CRP_CLOSURE=PASS")
    print("CLASSIFIER_EXECUTABLE_IDENTITIES_CHECKED="+str(lineage["classifier_source_identities_checked"]))
    print("CURRENT_EXECUTABLE_IDENTITY=PASS")
    print("CLASSIFICATION_ROWS_CURRENT="+str(rows_before))

    if a.verify_only:
        req(rows_before==0,"FIRST_PRODUCTION_DB_NOT_PRISTINE")
        req(sha(a.control_db)==control_before,"CONTROL_DB_CHANGED")
        req(sha(a.classification_db)==class_before,"CLASS_DB_CHANGED")
        print("DATABASES_UNCHANGED=PASS")
        print("FIRST_PRODUCTION_RUNNER_R2_READINESS=PASS")
        print("CLASSIFICATION_EXECUTED=NO")
        return 0

    req(a.confirm=="FIRST_PRODUCTION_CLASSIFICATION","EXPLICIT_CONFIRMATION_REQUIRED")
    req(a.mac is not None,"MAC_REQUIRED"); req(2<=a.window_minutes<=120,"WINDOW_2_TO_120")
    req(rows_before==0,"FIRST_PRODUCTION_DB_NOT_PRISTINE")
    mac=validate_mac(a.mac)
    nowdt=datetime.now(timezone.utc); enddt=nowdt-timedelta(seconds=2); startdt=enddt-timedelta(minutes=a.window_minutes)
    now=format_utc(nowdt); start=format_utc(startdt); end=format_utc(enddt)
    n,kinds=evidence(a.evidence_db,mac,start,end); req(n>0,"NO_CONTROLLED_DEVICE_EVIDENCE")
    print("CONTROLLED_MAC="+mac); print("WINDOW_START_UTC="+start); print("WINDOW_END_UTC="+end)
    print("EVIDENCE_ROWS="+str(n)); print("EVIDENCE_BY_SOURCE_KIND="+json.dumps(kinds,sort_keys=True,separators=(",",":")))

    audit=a.audit_root/("task04-first-production-classification-"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    audit.mkdir(parents=True,exist_ok=False); bak=audit/"device_fingerprint_classification.pre-first-production.sqlite3"; backup(a.classification_db,bak)

    def compatible(profile,foundation,bundle,_knowledge,policy,adapters,manifest):
        return (profile==pinned.runtime_profile and foundation==direct["foundation_runtime_profile"]
                and bundle==direct["knowledge_bundle"] and policy==direct["classification_policy"]
                and adapters==direct["evidence_adapter_contract_set"] and manifest==direct["classifier_artifact_manifest"])

    read=DeviceFingerprintReadService(str(a.evidence_db),retention_days=30)
    service=DeviceFingerprintRequestAssembly(control_plane_store=control,read_service=read,
        compatibility_hook=compatible,utc_clock=lambda:now,process_memory_guard=rss_guard)
    store=DeviceFingerprintClassificationStore(a.classification_db,a.evidence_db,control_plane_store=control,utc_clock=lambda:now)
    assembled=service.assemble_production(SITE_ID,mac,start,end)
    req(assembled.execution_context=="PRODUCTION","ASSEMBLY_CONTEXT")
    req(assembled.classification_runtime_profile==pinned.runtime_profile,"ASSEMBLY_PROFILE")
    req(assembled.runtime_profile_activation_record==pinned.activation_record,"ASSEMBLY_ACTIVATION")
    req(assembled.classification_result.semantic_payload["classification_request_digest"]==assembled.classification_request_manifest.content_sha256,"ASSEMBLY_DIGEST")
    write_json(audit/"precommit-assembly.json",{
      "status":"PRECOMMIT_READY","site_id":SITE_ID,"observed_mac":mac,"window_start_utc":start,"window_end_utc":end,
      "knowledge_evaluation_at_utc":assembled.knowledge_evaluation_at_utc,
      "classification_runtime_profile":ref(assembled.classification_runtime_profile),
      "runtime_profile_activation_record":ref(assembled.runtime_profile_activation_record),
      "classification_request_manifest":ref(assembled.classification_request_manifest),
      "classification_result":ref(assembled.classification_result),
      "classification_result_payload":assembled.classification_result.semantic_payload,
      "evidence_rows_precheck":n,"evidence_by_source_kind":kinds,"accepted_lineage":lineage})

    core=store.persist(assembled,retention_policy=build_initial_classification_retention_policy_v1())
    print("ATOMIC_CLASSIFICATION_PERSIST=PASS")
    rb=DeviceFingerprintClassificationReadService(a.classification_db); cur=rb.get_current(SITE_ID,mac)
    req(cur is not None and cur.core==core and cur.result==assembled.classification_result,"GET_CURRENT_MISMATCH")
    req(store.replay_level_b(core.classification_id)==assembled.classification_result,"LEVEL_B_REPLAY")
    rows_after=count(a.classification_db,"classifications"); req(rows_after==1,f"ROWS_AFTER:{rows_after}")
    req(sha(a.control_db)==control_before,"CONTROL_DB_CHANGED_BY_CLASSIFICATION")
    receipt=audit/"first-production-classification-receipt.json"
    write_json(receipt,{
      "status":"PASS","action":"FIRST_PRODUCTION_CLASSIFICATION","classification_id":core.classification_id,
      "core":asdict(core),"result_artifact":ref(assembled.classification_result),
      "result_payload":assembled.classification_result.semantic_payload,
      "request_artifact":ref(assembled.classification_request_manifest),"snapshot_record":ref(assembled.snapshot_record),
      "active_profile":ref(pinned.runtime_profile),"activation_record_id":pinned.pointer.activation_record_id,
      "activation_generation_id":pinned.pointer.activation_generation_id,"accepted_lineage":lineage,
      "level_b_replay":"PASS","get_current":"PASS","classification_rows_before":rows_before,
      "classification_rows_after":rows_after,"control_db_sha256_unchanged":control_before,
      "classification_db_backup":str(bak),"classification_db_backup_sha256":sha(bak)})
    print("FIRST_PRODUCTION_CLASSIFICATION=PASS")
    print("CLASSIFICATION_ID="+core.classification_id)
    print("CLASSIFICATION_RESULT_ID="+assembled.classification_result.artifact_id)
    print("GET_CURRENT=PASS"); print("LEVEL_B_REPLAY=PASS"); print("CLASSIFICATION_ROWS_AFTER=1")
    print("CONTROL_DB_UNCHANGED=PASS")
    print("RESULT_PAYLOAD="+json.dumps(assembled.classification_result.semantic_payload,sort_keys=True,separators=(",",":")))
    print("AUDIT_DIR="+str(audit)); print("RECEIPT="+str(receipt))
    return 0

if __name__=="__main__":
    try: raise SystemExit(main())
    except Blocked as e:
        print("FIRST_PRODUCTION_HARNESS_R2=BLOCKED:"+str(e),file=sys.stderr)
        raise SystemExit(2)
