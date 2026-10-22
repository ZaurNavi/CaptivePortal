#!/usr/bin/env bash
set -Eeuo pipefail
export SYSTEMD_PAGER=cat
export PAGER=cat

PORTAL="/opt/CaptivePortal"
VENV_PY="/opt/captiveportal-runtime/device-fingerprint-venv/bin/python"

EXPECTED_HEAD="97bd1cf924024a38cc3229bfd726a25fe6754b07"
EXPECTED_TREE="545a48caf86adc247083db611e87a8d36820f353"

INTEGRATION_DB="/opt/CaptivePortal/data/device_fingerprint_integration.sqlite3"
CONTROL_DB="/opt/CaptivePortal/data/device_fingerprint_control_plane.sqlite3"
EVIDENCE_DB="/opt/CaptivePortal/data/device_fingerprint_evidence.sqlite3"
TARGET_IID="e8ac5702-6ab5-4af9-94ae-0582df4666af"

section(){ printf '\n===== %s =====\n' "$1"; }
fail(){ echo "FATAL: $*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || fail "Run with sudo/root"
[ -x "$VENV_PY" ] || fail "Production venv missing"

section "DECLARATION"
date --iso-8601=seconds
echo "MODE=TASK05_PERF_PHASE1_READ_ONLY"
echo "DATABASE_WRITE_BY_SCRIPT=NO"
echo "CLASSIFICATION_PERSISTENCE_CALL=NO"
echo "CONFIG_WRITE=NO"
echo "SERVICE_WRITE=NO"
echo "ENVIRONMENT_FILE_SOURCE=NO"
echo "SECRETS_READ_BY_SHELL=NO"
echo "TARGET_INTEGRATION_ID=$TARGET_IID"

section "RUNTIME GUARD"
HEAD="$(git -C "$PORTAL" rev-parse HEAD)"
TREE="$(git -C "$PORTAL" rev-parse 'HEAD^{tree}')"
echo "PRODUCTION_HEAD=$HEAD"
echo "PRODUCTION_TREE=$TREE"
[ "$HEAD" = "$EXPECTED_HEAD" ] || fail "Unexpected production HEAD"
[ "$TREE" = "$EXPECTED_TREE" ] || fail "Unexpected production tree"
systemctl is-active --quiet captive-portal.service || fail "Portal inactive"
systemctl is-active --quiet fingerprint-classification.service || fail "Worker inactive"
echo "PORTAL_NRESTARTS=$(systemctl show captive-portal.service -p NRestarts --value --no-pager)"
echo "WORKER_NRESTARTS=$(systemctl show fingerprint-classification.service -p NRestarts --value --no-pager)"
echo "RUNTIME_GUARD=PASS"

section "HOST BASELINE"
echo "HOSTNAME=$(hostname)"
echo "KERNEL=$(uname -r)"
echo "LOADAVG=$(cat /proc/loadavg)"
echo "CPU_MODEL=$(awk -F: '/model name/{gsub(/^[ \t]+/,"",$2); print $2; exit}' /proc/cpuinfo)"
echo "CPU_LOGICAL=$(getconf _NPROCESSORS_ONLN)"
echo "MEMORY:"
free -h || true
echo "FILESYSTEM:"
df -hT "$PORTAL" "$EVIDENCE_DB" 2>/dev/null || true
echo "BLOCK_DEVICES:"
lsblk -o NAME,TYPE,SIZE,ROTA,FSTYPE,MOUNTPOINTS 2>/dev/null || true
echo "TOP_CPU_SNAPSHOT:"
ps -eo pid,comm,%cpu,%mem,stat --sort=-%cpu | head -n 12 || true

section "TARGET JOB"
INTEGRATION_DB="$INTEGRATION_DB" TARGET_IID="$TARGET_IID" /usr/bin/python3 - <<'PY'
import os, sqlite3
con=sqlite3.connect(f"file:{os.environ['INTEGRATION_DB']}?mode=ro",uri=True)
con.row_factory=sqlite3.Row
try:
    r=con.execute("""SELECT integration_id,site_id,observed_mac,authorized_at_utc,
        effective_window_start_utc,effective_window_end_utc,classification_state,
        attempt_count,planned_classification_id,classification_id
        FROM integration_jobs WHERE integration_id=?""",
        (os.environ["TARGET_IID"],)).fetchone()
finally:
    con.close()
if r is None: raise SystemExit("FATAL: target job missing")
for k in r.keys():
    print(f"{k.upper()}={'' if r[k] is None else r[k]}")
assert r["classification_state"]=="CLASSIFIED"
assert r["effective_window_start_utc"] and r["effective_window_end_utc"]
PY

section "READ-ONLY PRECHECK SQL"
INTEGRATION_DB="$INTEGRATION_DB" EVIDENCE_DB="$EVIDENCE_DB" TARGET_IID="$TARGET_IID" /usr/bin/python3 - <<'PY'
import os, sqlite3, time
idb=os.environ["INTEGRATION_DB"]; edb=os.environ["EVIDENCE_DB"]; iid=os.environ["TARGET_IID"]
ic=sqlite3.connect(f"file:{idb}?mode=ro",uri=True); ic.row_factory=sqlite3.Row
try:
    j=ic.execute("""SELECT site_id,observed_mac,effective_window_start_utc,effective_window_end_utc
                    FROM integration_jobs WHERE integration_id=?""",(iid,)).fetchone()
finally: ic.close()
con=sqlite3.connect(f"file:{edb}?mode=ro",uri=True)
try:
    tests=[
      ("EVIDENCE_EXACT_WINDOW",
       "SELECT count(*) FROM device_fingerprint_evidence "
       "WHERE site_id=? AND observed_mac=? AND observed_at>=? AND observed_at<?",
       (j["site_id"],j["observed_mac"],j["effective_window_start_utc"],j["effective_window_end_utc"])),
      ("HEALTH_SITE_WINDOW",
       "SELECT count(*) FROM device_fingerprint_source_health_events "
       "WHERE site_id=? AND observed_at>=? AND observed_at<?",
       (j["site_id"],j["effective_window_start_utc"],j["effective_window_end_utc"])),
    ]
    for name,sql,args in tests:
        w0=time.perf_counter(); c0=time.process_time()
        n=con.execute(sql,args).fetchone()[0]
        wall=time.perf_counter()-w0; cpu=time.process_time()-c0
        print(f"{name}_ROWS={n}")
        print(f"{name}_WALL_SECONDS={wall:.6f}")
        print(f"{name}_CPU_SECONDS={cpu:.6f}")
        print(f"{name}_CPU_TO_WALL_RATIO={(cpu/wall if wall else 0):.6f}")
finally:
    con.close()
PY

section "IN-MEMORY PRODUCTION ASSEMBLY BENCHMARK"
sudo -u admin env \
  HOME=/nonexistent \
  PYTHONPATH="$PORTAL" \
  PYTHONDONTWRITEBYTECODE=1 \
  INTEGRATION_DB="$INTEGRATION_DB" \
  CONTROL_DB="$CONTROL_DB" \
  EVIDENCE_DB="$EVIDENCE_DB" \
  TARGET_IID="$TARGET_IID" \
  "$VENV_PY" -B - <<'PY'
import os, sqlite3, time, resource, json
from app.device_fingerprint.control_plane_store import DeviceFingerprintControlPlaneStore
from app.device_fingerprint.read_service import DeviceFingerprintReadService
from app.device_fingerprint.request_assembly import DeviceFingerprintRequestAssembly
from app.device_fingerprint_integration.compatibility import (
    ReadOnlyControlPlaneStoreMixin, preflight, ExactPinStore,
)
from app.device_fingerprint_integration.executor import process_memory_guard
from app.device_fingerprint_integration.models import utc_now

class ReadOnlyControl(ReadOnlyControlPlaneStoreMixin, DeviceFingerprintControlPlaneStore):
    pass

idb=os.environ["INTEGRATION_DB"]
iid=os.environ["TARGET_IID"]
con=sqlite3.connect(f"file:{idb}?mode=ro",uri=True)
con.row_factory=sqlite3.Row
try:
    job=con.execute("""SELECT site_id,observed_mac,effective_window_start_utc,effective_window_end_utc
                       FROM integration_jobs WHERE integration_id=?""",(iid,)).fetchone()
finally:
    con.close()
if job is None:
    raise SystemExit("FATAL: job missing")

def timed(label, fn):
    w0=time.perf_counter()
    c0=time.process_time()
    r0=resource.getrusage(resource.RUSAGE_SELF)
    result=fn()
    r1=resource.getrusage(resource.RUSAGE_SELF)
    wall=time.perf_counter()-w0
    cpu=time.process_time()-c0
    print(f"{label}_WALL_SECONDS={wall:.6f}", flush=True)
    print(f"{label}_CPU_SECONDS={cpu:.6f}", flush=True)
    print(f"{label}_CPU_TO_WALL_RATIO={(cpu/wall if wall else 0):.6f}", flush=True)
    print(f"{label}_MAJFLT_DELTA={r1.ru_majflt-r0.ru_majflt}", flush=True)
    print(f"{label}_MINFLT_DELTA={r1.ru_minflt-r0.ru_minflt}", flush=True)
    print(f"{label}_MAXRSS_KB={r1.ru_maxrss}", flush=True)
    return result

control=ReadOnlyControl(os.environ["CONTROL_DB"])

prepared=timed("PREFLIGHT", lambda: preflight(control))
print("PREFLIGHT_PROFILE_ID="+prepared.contents[0].artifact_id)
print("PREFLIGHT_FOUNDATION_ID="+prepared.contents[1].artifact_id)

evidence=DeviceFingerprintReadService(os.environ["EVIDENCE_DB"], retention_days=30)
assembly=DeviceFingerprintRequestAssembly(
    control_plane_store=ExactPinStore(control, prepared.pin),
    read_service=evidence,
    compatibility_hook=prepared.hook,
    utc_clock=utc_now,
    process_memory_guard=process_memory_guard,
)

def do_assembly():
    return assembly.assemble_production(
        job["site_id"], job["observed_mac"],
        job["effective_window_start_utc"], job["effective_window_end_utc"]
    )

result=timed("ASSEMBLY", do_assembly)

print("ASSEMBLY_EXECUTION_CONTEXT="+result.execution_context)
print("ASSEMBLY_SNAPSHOT_ID="+result.evidence_snapshot_content.artifact_id)
print("ASSEMBLY_SNAPSHOT_EVIDENCE_COUNT="+str(
    len(result.evidence_snapshot_content.semantic_payload["evidence_descriptors"])))
print("ASSEMBLY_SNAPSHOT_HEALTH_COUNT="+str(
    len(result.evidence_snapshot_content.semantic_payload["source_health_descriptors"])))
print("ASSEMBLY_ORIGIN_ASSESSMENT_COUNT="+str(len(result.origin_assessments)))
print("ASSEMBLY_CLASSIFICATION_RESULT_ID="+result.classification_result.artifact_id)
payload=result.classification_result.semantic_payload
for key in ("device_class","device_type","os_family","manufacturer","model"):
    if key in payload:
        value=payload[key]
        if isinstance(value,(dict,list)):
            value=json.dumps(value,ensure_ascii=False,separators=(",",":"))
        print("RESULT_"+key.upper()+"="+str(value))
print("CLASSIFICATION_PERSISTENCE_EXECUTED=NO")
print("IN_MEMORY_ASSEMBLY=PASS")
PY

section "HOST AFTER"
echo "LOADAVG_AFTER=$(cat /proc/loadavg)"
echo "TOP_CPU_AFTER:"
ps -eo pid,comm,%cpu,%mem,stat --sort=-%cpu | head -n 12 || true

section "FINAL"
echo "TASK05_PERF_PHASE1_READ_ONLY=PASS"
echo "NEXT_DECISION=COMPARE_ASSEMBLY_WALL_VS_CPU_AND_342S_PRODUCTION_ATTEMPT"
