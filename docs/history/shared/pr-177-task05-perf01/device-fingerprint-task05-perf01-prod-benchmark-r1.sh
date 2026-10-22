#!/usr/bin/env bash
set -Eeuo pipefail
export SYSTEMD_PAGER=cat
export PAGER=cat

PORTAL="/opt/CaptivePortal"
VENV_PY="/opt/captiveportal-runtime/device-fingerprint-venv/bin/python"

EXPECTED_HEAD="20ea385182972e8fb5b204815161bc6a5c7f13fb"
EXPECTED_TREE="439ab64697f2fcdcd5e822527f287ca5404e45ba"

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
echo "MODE=TASK05_PERF01_POST_REPAIR_READ_ONLY_BENCHMARK"
echo "DATABASE_WRITE_BY_SCRIPT=NO"
echo "CLASSIFICATION_PERSISTENCE_CALL=NO"
echo "CONFIG_WRITE=NO"
echo "SERVICE_WRITE=NO"
echo "TARGET_INTEGRATION_ID=$TARGET_IID"
echo "BASELINE_ASSEMBLY_WALL_SECONDS=248.522743"
echo "BASELINE_ASSEMBLY_CPU_SECONDS=247.911308"

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
echo "LOADAVG=$(cat /proc/loadavg)"
echo "RUNTIME_GUARD=PASS"

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
import os, sqlite3, time, resource
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
    raise SystemExit("FATAL: target job missing")

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
    return result, wall, cpu

control=ReadOnlyControl(os.environ["CONTROL_DB"])
prepared, preflight_wall, preflight_cpu = timed("PREFLIGHT", lambda: preflight(control))

evidence=DeviceFingerprintReadService(os.environ["EVIDENCE_DB"], retention_days=30)
assembly=DeviceFingerprintRequestAssembly(
    control_plane_store=ExactPinStore(control, prepared.pin),
    read_service=evidence,
    compatibility_hook=prepared.hook,
    utc_clock=utc_now,
    process_memory_guard=process_memory_guard,
)

result, wall, cpu = timed("ASSEMBLY", lambda: assembly.assemble_production(
    job["site_id"], job["observed_mac"],
    job["effective_window_start_utc"], job["effective_window_end_utc"]
))

baseline_wall=248.522743
baseline_cpu=247.911308
print(f"ASSEMBLY_BASELINE_WALL_SECONDS={baseline_wall:.6f}")
print(f"ASSEMBLY_BASELINE_CPU_SECONDS={baseline_cpu:.6f}")
print(f"ASSEMBLY_WALL_SPEEDUP_X={(baseline_wall/wall if wall else 0):.3f}")
print(f"ASSEMBLY_CPU_SPEEDUP_X={(baseline_cpu/cpu if cpu else 0):.3f}")
print(f"ASSEMBLY_WALL_REDUCTION_PERCENT={(100*(baseline_wall-wall)/baseline_wall):.2f}")
print(f"ASSEMBLY_CPU_REDUCTION_PERCENT={(100*(baseline_cpu-cpu)/baseline_cpu):.2f}")

print("ASSEMBLY_EXECUTION_CONTEXT="+result.execution_context)
print("ASSEMBLY_SNAPSHOT_EVIDENCE_COUNT="+str(
    len(result.evidence_snapshot_content.semantic_payload["evidence_descriptors"])))
print("ASSEMBLY_SNAPSHOT_HEALTH_COUNT="+str(
    len(result.evidence_snapshot_content.semantic_payload["source_health_descriptors"])))
print("ASSEMBLY_ORIGIN_ASSESSMENT_COUNT="+str(len(result.origin_assessments)))
print("ASSEMBLY_CLASSIFICATION_RESULT_ID="+result.classification_result.artifact_id)
print("CLASSIFICATION_PERSISTENCE_EXECUTED=NO")
print("POST_REPAIR_ASSEMBLY=PASS")
PY

section "HOST AFTER"
echo "LOADAVG_AFTER=$(cat /proc/loadavg)"
ps -eo pid,comm,%cpu,%mem,stat --sort=-%cpu | head -n 12 || true

section "FINAL"
echo "TASK05_PERF01_POST_REPAIR_BENCHMARK=PASS"
echo "NEXT_DECISION=EVALUATE_REMAINING_RUNTIME_VS_300S_LEASE"
