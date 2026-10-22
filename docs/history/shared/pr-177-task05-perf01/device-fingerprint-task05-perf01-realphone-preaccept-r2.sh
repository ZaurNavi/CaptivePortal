#!/usr/bin/env bash
set -Eeuo pipefail
export SYSTEMD_PAGER=cat
export PAGER=cat

MODE="${1:-}"
TARGET_MAC="${2:-}"

PROD="/opt/CaptivePortal"
CANDIDATE="/home/admin/CaptivePortal-task05-perf01-candidate"
CANDIDATE_HEAD="20ea385182972e8fb5b204815161bc6a5c7f13fb"
CANDIDATE_TREE="439ab64697f2fcdcd5e822527f287ca5404e45ba"
PROD_HEAD="97bd1cf924024a38cc3229bfd726a25fe6754b07"
PROD_TREE="545a48caf86adc247083db611e87a8d36820f353"

VENV_PY="/opt/captiveportal-runtime/device-fingerprint-venv/bin/python"
CONTROL_DB="/opt/CaptivePortal/data/device_fingerprint_control_plane.sqlite3"
EVIDENCE_DB="/opt/CaptivePortal/data/device_fingerprint_evidence.sqlite3"
INTEGRATION_DB="/opt/CaptivePortal/data/device_fingerprint_integration.sqlite3"

fail(){ echo "FATAL: $*" >&2; exit 1; }
section(){ printf '\n===== %s =====\n' "$1"; }

[ "$(id -u)" -eq 0 ] || fail "Run with sudo/root"
[ -d "$PROD/.git" ] || fail "Production repo missing"
[ -x "$VENV_PY" ] || fail "Production venv missing"

guard_prod() {
  local h t s
  h="$(git -C "$PROD" rev-parse HEAD)"
  t="$(git -C "$PROD" rev-parse 'HEAD^{tree}')"
  s="$(git -C "$PROD" status --porcelain=v1 --untracked-files=normal)"
  echo "PRODUCTION_HEAD=$h"
  echo "PRODUCTION_TREE=$t"
  [ "$h" = "$PROD_HEAD" ] || fail "Production is not on admitted runtime"
  [ "$t" = "$PROD_TREE" ] || fail "Production tree mismatch"
  [ -z "$s" ] || fail "Production worktree dirty"
  systemctl is-active --quiet captive-portal.service || fail "Portal inactive"
}

case "$MODE" in
  prepare)
    section "DECLARATION"
    echo "MODE=PREPARE_ISOLATED_PRE_ACCEPTANCE_CANDIDATE"
    echo "PRODUCTION_CODE_SWITCH=NO"
    echo "CONTROL_PLANE_WRITE=NO"
    echo "DB_WRITE=NO"
    echo "SERVICE_WRITE=NO"
    guard_prod

    section "CANDIDATE OBJECT GUARD"
    git -C "$PROD" cat-file -e "$CANDIDATE_HEAD^{commit}"
    [ "$(git -C "$PROD" rev-parse "$CANDIDATE_HEAD^{tree}")" = "$CANDIDATE_TREE" ] \
      || fail "Candidate tree mismatch"

    section "ISOLATED WORKTREE"
    if [ -d "$CANDIDATE" ]; then
      H="$(git -C "$CANDIDATE" rev-parse HEAD 2>/dev/null || true)"
      T="$(git -C "$CANDIDATE" rev-parse 'HEAD^{tree}' 2>/dev/null || true)"
      if [ "$H" = "$CANDIDATE_HEAD" ] && [ "$T" = "$CANDIDATE_TREE" ]; then
        echo "CANDIDATE_WORKTREE_ALREADY_READY=YES"
      else
        fail "Candidate path exists but is not exact accepted candidate"
      fi
    else
      git -C "$PROD" worktree add --detach "$CANDIDATE" "$CANDIDATE_HEAD"
    fi

    [ "$(git -C "$CANDIDATE" rev-parse HEAD)" = "$CANDIDATE_HEAD" ] \
      || fail "Candidate HEAD mismatch"
    [ "$(git -C "$CANDIDATE" rev-parse 'HEAD^{tree}')" = "$CANDIDATE_TREE" ] \
      || fail "Candidate tree mismatch"
    [ -z "$(git -C "$CANDIDATE" status --porcelain=v1 --untracked-files=normal)" ] \
      || fail "Candidate worktree dirty"

    echo "CANDIDATE_HEAD=$CANDIDATE_HEAD"
    echo "CANDIDATE_TREE=$CANDIDATE_TREE"
    echo "PREPARE_PRE_ACCEPTANCE_CANDIDATE=PASS"
    ;;

  run)
    [ -n "$TARGET_MAC" ] || fail "Usage: $0 run AA:BB:CC:DD:EE:FF"

    section "DECLARATION"
    date --iso-8601=seconds
    echo "MODE=REAL_PHONE_PRE_ACCEPTANCE_CANDIDATE"
    echo "ACTIVE_PROFILE_CHANGE=NO"
    echo "PRODUCTION_CODE_SWITCH=NO"
    echo "CONTROL_PLANE_WRITE=NO"
    echo "CLASSIFICATION_PERSISTENCE=NO"
    echo "INTEGRATION_DB_WRITE=NO"
    echo "EVIDENCE_DB_WRITE=NO"
    echo "TARGET_MAC=$TARGET_MAC"

    guard_prod

    [ -d "$CANDIDATE" ] || fail "Candidate worktree missing; run prepare first"
    [ "$(git -C "$CANDIDATE" rev-parse HEAD)" = "$CANDIDATE_HEAD" ] \
      || fail "Candidate HEAD mismatch"
    [ "$(git -C "$CANDIDATE" rev-parse 'HEAD^{tree}')" = "$CANDIDATE_TREE" ] \
      || fail "Candidate tree mismatch"
    [ -z "$(git -C "$CANDIDATE" status --porcelain=v1 --untracked-files=normal)" ] \
      || fail "Candidate worktree dirty"

    if systemctl is-active --quiet fingerprint-classification.service; then
      fail "Fingerprint worker must be stopped for uncontended real-phone benchmark"
    fi
    echo "WORKER_STATE=inactive"
    echo "PORTAL_STATE=$(systemctl is-active captive-portal.service)"

    section "PRE_ACCEPTANCE EXECUTION"
    sudo -u admin env \
      HOME=/nonexistent \
      PYTHONPATH="$CANDIDATE" \
      PYTHONDONTWRITEBYTECODE=1 \
      CANDIDATE_ROOT="$CANDIDATE" \
      CANDIDATE_HEAD="$CANDIDATE_HEAD" \
      CANDIDATE_TREE="$CANDIDATE_TREE" \
      CONTROL_DB="$CONTROL_DB" \
      EVIDENCE_DB="$EVIDENCE_DB" \
      INTEGRATION_DB="$INTEGRATION_DB" \
      TARGET_MAC="$TARGET_MAC" \
      "$VENV_PY" -B - <<'PY'
import hashlib
import json
import os
import resource
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

from app.device_fingerprint.artifact_content import ArtifactRef, make_artifact_content
from app.device_fingerprint.control_plane_store import DeviceFingerprintControlPlaneStore
from app.device_fingerprint.read_service import DeviceFingerprintReadService
from app.device_fingerprint.request_assembly import DeviceFingerprintRequestAssembly
from app.device_fingerprint.runtime_profile_artifacts import make_classification_runtime_profile
from app.device_fingerprint_integration.compatibility import (
    ReadOnlyControlPlaneStoreMixin, verify_executable_identities,
)
from app.device_fingerprint_integration.executor import process_memory_guard
from app.device_fingerprint_integration.models import plus, parse_utc

ROOT = Path(os.environ["CANDIDATE_ROOT"]).resolve()
HEAD = os.environ["CANDIDATE_HEAD"]
TREE = os.environ["CANDIDATE_TREE"]
MAC = os.environ["TARGET_MAC"].upper().replace("-", ":")

def utc(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))

class ReadOnlyStore(ReadOnlyControlPlaneStoreMixin, DeviceFingerprintControlPlaneStore):
    pass

con = sqlite3.connect(f"file:{os.environ['INTEGRATION_DB']}?mode=ro", uri=True)
con.row_factory = sqlite3.Row
try:
    row = con.execute(
        """SELECT integration_id, site_id, observed_mac, authorized_at_utc, due_at_utc,
                  effective_window_start_utc, effective_window_end_utc,
                  classification_state, attempt_count
             FROM integration_jobs
            WHERE upper(observed_mac)=?
            ORDER BY authorized_at_utc DESC
            LIMIT 1""",
        (MAC,),
    ).fetchone()
finally:
    con.close()

if row is None:
    raise SystemExit("FATAL: no integration job exists for supplied MAC")

now = datetime.now(timezone.utc)
authorized = utc(row["authorized_at_utc"])
age = (now - authorized).total_seconds()
if age < -5 or age > 900:
    raise SystemExit(f"FATAL: latest Auth for supplied MAC is not fresh enough; age_seconds={age:.1f}")

print("INTEGRATION_ID="+row["integration_id"])
print("SITE_ID="+row["site_id"])
print("OBSERVED_MAC="+row["observed_mac"])
print("AUTHORIZED_AT_UTC="+row["authorized_at_utc"])
print("DUE_AT_UTC="+row["due_at_utc"])
print("DB_EFFECTIVE_WINDOW_START_UTC="+str(row["effective_window_start_utc"]))
print("DB_EFFECTIVE_WINDOW_END_UTC="+str(row["effective_window_end_utc"]))
print("CURRENT_JOB_STATE="+row["classification_state"])
print("CURRENT_JOB_ATTEMPT_COUNT="+str(row["attempt_count"]))

due = utc(row["due_at_utc"])
wait = (due - datetime.now(timezone.utc)).total_seconds()
if wait > 0:
    print(f"WAIT_UNTIL_POST_AUTH_WINDOW_SECONDS={wait:.1f}", flush=True)
    time.sleep(wait + 1.0)

store = ReadOnlyStore(os.environ["CONTROL_DB"])
active = store.pin_active_profile("classification")
old_profile = active.runtime_profile
old_payload = old_profile.semantic_payload

foundation_ref = ArtifactRef.from_dict(old_payload["foundation_runtime_profile"])
foundation_for_window = store.load_artifact(
    foundation_ref.artifact_id, foundation_ref.content_sha256
)
window_end = plus(row["authorized_at_utc"], 120)
window_start = max(
    plus(row["authorized_at_utc"], -300),
    foundation_for_window.semantic_payload["classification_foundation_valid_from_utc"],
)
if parse_utc(window_start) >= parse_utc(window_end):
    raise SystemExit("FATAL: integration_window_not_authoritative")

print("COMPUTED_WINDOW_START_UTC="+window_start)
print("COMPUTED_WINDOW_END_UTC="+window_end)
print("WINDOW_SOURCE=EXACT_CLASSIFICATION_EXECUTOR_FORMULA")

old_manifest_ref = ArtifactRef.from_dict(old_payload["classifier_artifact_manifest"])
old_manifest = store.load_artifact(old_manifest_ref.artifact_id, old_manifest_ref.content_sha256)

manifest_payload = dict(old_manifest.semantic_payload)
new_entries = []
for entry in manifest_payload["adapter_implementation_identities"]:
    item = dict(entry)
    prefix, rel, _tail = item["implementation_id"].split(":", 2)
    if prefix != "python":
        raise SystemExit("FATAL: unsupported implementation identity prefix")
    source = (ROOT / rel).resolve()
    if not source.is_relative_to(ROOT) or not source.is_file():
        raise SystemExit(f"FATAL: candidate implementation source missing: {rel}")
    item["implementation_digest"] = hashlib.sha256(source.read_bytes()).hexdigest()
    new_entries.append(item)

evidence_identity = manifest_payload["evidence_canonical_json_compatibility_identity"]
prefix = "EvidenceCanonicalJsonV1:"
if not evidence_identity.startswith(prefix) or ":sha256:" not in evidence_identity:
    raise SystemExit("FATAL: malformed evidence canonical identity")
identity_part, _old_digest = evidence_identity[len(prefix):].rsplit(":sha256:", 1)
source_kind, rel, _qualified = identity_part.split(":", 2)
if source_kind != "python":
    raise SystemExit("FATAL: unsupported evidence canonical implementation prefix")
source = (ROOT / rel).resolve()
if not source.is_relative_to(ROOT) or not source.is_file():
    raise SystemExit(f"FATAL: candidate evidence canonical source missing: {rel}")
new_evidence_digest = hashlib.sha256(source.read_bytes()).hexdigest()

manifest_payload["adapter_implementation_identities"] = new_entries
manifest_payload["evidence_canonical_json_compatibility_identity"] = (
    prefix + identity_part + ":sha256:" + new_evidence_digest
)
manifest_payload["repository_commit_sha"] = HEAD
manifest_payload["repository_tree_sha"] = TREE

candidate_manifest = make_artifact_content("ClassifierArtifactManifest", manifest_payload)
candidate_profile = make_classification_runtime_profile({
    **old_payload,
    "classifier_artifact_manifest": ArtifactRef(
        candidate_manifest.artifact_id, candidate_manifest.content_sha256
    ).as_dict(),
})

class OverlayStore(ReadOnlyStore):
    def load_artifact(self, artifact_id, expected_digest=None):
        if artifact_id == candidate_manifest.artifact_id:
            if expected_digest is not None and expected_digest != candidate_manifest.content_sha256:
                raise RuntimeError("candidate manifest digest mismatch")
            return candidate_manifest
        return super().load_artifact(artifact_id, expected_digest)

overlay = OverlayStore(os.environ["CONTROL_DB"])

expected = {}
for field in (
    "foundation_runtime_profile",
    "knowledge_bundle",
    "classification_policy",
    "evidence_adapter_contract_set",
):
    ref = ArtifactRef.from_dict(old_payload[field])
    expected[field] = store.load_artifact(ref.artifact_id, ref.content_sha256)

def compatibility_hook(profile, foundation, bundle, knowledge, policy, adapters, classifier):
    if profile != candidate_profile or classifier != candidate_manifest:
        return False
    if foundation != expected["foundation_runtime_profile"]:
        return False
    if bundle != expected["knowledge_bundle"]:
        return False
    if policy != expected["classification_policy"]:
        return False
    if adapters != expected["evidence_adapter_contract_set"]:
        return False
    verify_executable_identities(candidate_manifest, root=ROOT)
    return True

print("ACTIVE_CRP_ID="+old_profile.artifact_id)
print("CANDIDATE_CLASSIFIER_MANIFEST_ID="+candidate_manifest.artifact_id)
print("CANDIDATE_CRP_ID="+candidate_profile.artifact_id)
print("CANDIDATE_REPOSITORY_COMMIT_SHA="+HEAD)
print("CANDIDATE_REPOSITORY_TREE_SHA="+TREE)
print("ACTIVE_POINTER_MUTATED=NO")

evidence = DeviceFingerprintReadService(os.environ["EVIDENCE_DB"], retention_days=30)
assembly = DeviceFingerprintRequestAssembly(
    control_plane_store=overlay,
    read_service=evidence,
    compatibility_hook=compatibility_hook,
    process_memory_guard=process_memory_guard,
)

w0 = time.perf_counter()
c0 = time.process_time()
r0 = resource.getrusage(resource.RUSAGE_SELF)

result = assembly.assemble_pre_acceptance_candidate(
    candidate_profile,
    row["site_id"],
    row["observed_mac"],
    window_start,
    window_end,
)

r1 = resource.getrusage(resource.RUSAGE_SELF)
wall = time.perf_counter() - w0
cpu = time.process_time() - c0

print(f"ASSEMBLY_WALL_SECONDS={wall:.6f}")
print(f"ASSEMBLY_CPU_SECONDS={cpu:.6f}")
print(f"ASSEMBLY_CPU_TO_WALL_RATIO={(cpu/wall if wall else 0):.6f}")
print(f"ASSEMBLY_MAJFLT_DELTA={r1.ru_majflt-r0.ru_majflt}")
print(f"ASSEMBLY_MINFLT_DELTA={r1.ru_minflt-r0.ru_minflt}")
print(f"ASSEMBLY_MAXRSS_KB={r1.ru_maxrss}")

baseline_wall = 248.522743
baseline_cpu = 247.911308
print(f"BASELINE_WALL_SECONDS={baseline_wall:.6f}")
print(f"BASELINE_CPU_SECONDS={baseline_cpu:.6f}")
print(f"WALL_SPEEDUP_X={(baseline_wall/wall if wall else 0):.3f}")
print(f"CPU_SPEEDUP_X={(baseline_cpu/cpu if cpu else 0):.3f}")
print(f"WALL_REDUCTION_PERCENT={(100*(baseline_wall-wall)/baseline_wall):.2f}")
print(f"CPU_REDUCTION_PERCENT={(100*(baseline_cpu-cpu)/baseline_cpu):.2f}")

print("EXECUTION_CONTEXT="+result.execution_context)
print("EVIDENCE_COUNT="+str(len(result.evidence_snapshot_content.semantic_payload["evidence_descriptors"])))
print("HEALTH_COUNT="+str(len(result.evidence_snapshot_content.semantic_payload["source_health_descriptors"])))
print("ORIGIN_ASSESSMENT_COUNT="+str(len(result.origin_assessments)))
print("CLASSIFICATION_REQUEST_ID="+result.classification_request_manifest.artifact_id)
print("CLASSIFICATION_RESULT_ID="+result.classification_result.artifact_id)

print("CLASSIFICATION_RESULT_JSON="+json.dumps(
    result.classification_result.semantic_payload, sort_keys=True, separators=(",", ":")
))
for i, assessment in enumerate(result.origin_assessments, 1):
    print(f"ORIGIN_{i}_JSON="+json.dumps(
        assessment.semantic_payload, sort_keys=True, separators=(",", ":")
    ))

print("CLASSIFICATION_PERSISTENCE_EXECUTED=NO")
print("PRE_ACCEPTANCE_REAL_PHONE_RESULT=PASS")
PY

    section "FINAL"
    echo "TASK05_PERF01_REAL_PHONE_PRE_ACCEPTANCE=PASS"
    echo "PRODUCTION_ACTIVE_PROFILE_CHANGED=NO"
    echo "PRODUCTION_RUNTIME_CHANGED=NO"
    echo "NEXT=RESTART_WORKER_AFTER_RESULT_CAPTURE"
    ;;

  cleanup)
    section "DECLARATION"
    echo "MODE=CLEANUP_ISOLATED_PRE_ACCEPTANCE_CANDIDATE"
    guard_prod
    if [ -d "$CANDIDATE" ]; then
      git -C "$PROD" worktree remove --force "$CANDIDATE"
    fi
    echo "CANDIDATE_WORKTREE_REMOVED=YES"
    echo "CLEANUP=PASS"
    ;;

  *)
    echo "Usage:"
    echo "  sudo bash $0 prepare"
    echo "  sudo bash $0 run AA:BB:CC:DD:EE:FF"
    echo "  sudo bash $0 cleanup"
    exit 2
    ;;
esac
