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
echo "MODE=TASK05_PERF_PHASE2_CPROFILE_READ_ONLY"
echo "DATABASE_WRITE=NO"
echo "CLASSIFICATION_PERSISTENCE_CALL=NO"
echo "CONFIG_WRITE=NO"
echo "SERVICE_WRITE=NO"
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
echo "LOADAVG_BEFORE=$(cat /proc/loadavg)"
echo "RUNTIME_GUARD=PASS"

section "PROFILE IN-MEMORY ASSEMBLY"
sudo -u admin env \
  HOME=/nonexistent \
  PYTHONPATH="$PORTAL" \
  PYTHONDONTWRITEBYTECODE=1 \
  INTEGRATION_DB="$INTEGRATION_DB" \
  CONTROL_DB="$CONTROL_DB" \
  EVIDENCE_DB="$EVIDENCE_DB" \
  TARGET_IID="$TARGET_IID" \
  "$VENV_PY" -B - <<'PY'
import os, sqlite3, time, cProfile, pstats, io, resource
from collections import defaultdict

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
con=sqlite3.connect(f"file:{idb}?mode=ro", uri=True)
con.row_factory=sqlite3.Row
try:
    job=con.execute(
        """SELECT site_id,observed_mac,effective_window_start_utc,effective_window_end_utc
           FROM integration_jobs WHERE integration_id=?""",
        (iid,)
    ).fetchone()
finally:
    con.close()
if job is None:
    raise SystemExit("FATAL: target job missing")

control=ReadOnlyControl(os.environ["CONTROL_DB"])

# Measure preflight separately; do not include it in assembly profile.
w0=time.perf_counter()
c0=time.process_time()
prepared=preflight(control)
print(f"PREFLIGHT_WALL_SECONDS={time.perf_counter()-w0:.6f}")
print(f"PREFLIGHT_CPU_SECONDS={time.process_time()-c0:.6f}")

# Count/timestamp control-plane artifact loads during assembly.
load_stats=defaultdict(float)
load_counts=defaultdict(int)
orig_load=control.load_artifact
def timed_load(artifact_id, content_sha256):
    t0=time.perf_counter()
    try:
        return orig_load(artifact_id, content_sha256)
    finally:
        dt=time.perf_counter()-t0
        kind=artifact_id.split(":",1)[0] if isinstance(artifact_id,str) else "<unknown>"
        load_stats[kind]+=dt
        load_counts[kind]+=1
control.load_artifact=timed_load

evidence=DeviceFingerprintReadService(os.environ["EVIDENCE_DB"], retention_days=30)
assembly=DeviceFingerprintRequestAssembly(
    control_plane_store=ExactPinStore(control, prepared.pin),
    read_service=evidence,
    compatibility_hook=prepared.hook,
    utc_clock=utc_now,
    process_memory_guard=process_memory_guard,
)

prof=cProfile.Profile()
r0=resource.getrusage(resource.RUSAGE_SELF)
wall0=time.perf_counter()
cpu0=time.process_time()

prof.enable()
result=assembly.assemble_production(
    job["site_id"], job["observed_mac"],
    job["effective_window_start_utc"], job["effective_window_end_utc"]
)
prof.disable()

wall=time.perf_counter()-wall0
cpu=time.process_time()-cpu0
r1=resource.getrusage(resource.RUSAGE_SELF)

print(f"PROFILED_ASSEMBLY_WALL_SECONDS={wall:.6f}")
print(f"PROFILED_ASSEMBLY_CPU_SECONDS={cpu:.6f}")
print(f"PROFILED_ASSEMBLY_CPU_TO_WALL_RATIO={(cpu/wall if wall else 0):.6f}")
print(f"PROFILED_ASSEMBLY_MAJFLT_DELTA={r1.ru_majflt-r0.ru_majflt}")
print(f"PROFILED_ASSEMBLY_MINFLT_DELTA={r1.ru_minflt-r0.ru_minflt}")
print(f"PROFILED_ASSEMBLY_MAXRSS_KB={r1.ru_maxrss}")
print(f"SNAPSHOT_EVIDENCE_COUNT={len(result.evidence_snapshot_content.semantic_payload['evidence_descriptors'])}")
print(f"SNAPSHOT_HEALTH_COUNT={len(result.evidence_snapshot_content.semantic_payload['source_health_descriptors'])}")
print(f"ORIGIN_ASSESSMENT_COUNT={len(result.origin_assessments)}")
print(f"RESULT_ID={result.classification_result.artifact_id}")
print("CLASSIFICATION_PERSISTENCE_EXECUTED=NO")

print("\n=== CONTROL ARTIFACT LOAD SUMMARY ===")
for kind in sorted(load_counts, key=lambda k: load_stats[k], reverse=True):
    print(f"CONTROL_LOAD kind={kind} count={load_counts[kind]} wall_seconds={load_stats[kind]:.6f}")
print(f"CONTROL_LOAD_TOTAL_COUNT={sum(load_counts.values())}")
print(f"CONTROL_LOAD_TOTAL_WALL_SECONDS={sum(load_stats.values()):.6f}")

def dump_stats(sort_key, title, limit=60):
    s=io.StringIO()
    ps=pstats.Stats(prof, stream=s).strip_dirs().sort_stats(sort_key)
    ps.print_stats(limit)
    print(f"\n=== {title} ===")
    print(s.getvalue())

dump_stats("cumulative", "CPROFILE TOP 60 CUMULATIVE")
dump_stats("tottime", "CPROFILE TOP 60 SELF TIME")

# Focused view for project code only.
s=io.StringIO()
ps=pstats.Stats(prof, stream=s).strip_dirs().sort_stats("cumulative")
ps.print_stats("app/")
print("\n=== CPROFILE PROJECT APP FUNCTIONS ===")
print(s.getvalue())

print("TASK05_PERF_PHASE2_PROFILE=PASS")
PY

section "HOST AFTER"
echo "LOADAVG_AFTER=$(cat /proc/loadavg)"
ps -eo pid,comm,%cpu,%mem,stat --sort=-%cpu | head -n 12 || true

section "FINAL"
echo "TASK05_PERF_PHASE2_CPROFILE_READ_ONLY=PASS"
echo "NEXT_DECISION=IDENTIFY_TOP_CPU_HOTSPOT_AND_DECIDE_CODE_FIX_VS_HARDWARE_LIMIT"
