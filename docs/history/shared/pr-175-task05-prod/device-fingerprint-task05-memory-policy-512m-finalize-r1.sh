#!/usr/bin/env bash
set -Eeuo pipefail
export SYSTEMD_PAGER=cat
export PAGER=cat

PROD="/opt/CaptivePortal"
PY="/opt/captiveportal-runtime/device-fingerprint-venv/bin/python"
CONTROL_DB="/opt/CaptivePortal/data/device_fingerprint_control_plane.sqlite3"

EXPECTED_HEAD="20ea385182972e8fb5b204815161bc6a5c7f13fb"
EXPECTED_TREE="439ab64697f2fcdcd5e822527f287ca5404e45ba"
EXPECTED_CRP="ClassificationRuntimeProfile:v1:sha256:a0fe77d9198861b9b70c96bbf96bccdc13e4f15b827076a067c5c3ff73aff336"

OLD_LIMIT=100663296
NEW_LIMIT=536870912

fail(){ echo "FATAL: $*" >&2; exit 1; }
section(){ printf '\n===== %s =====\n' "$1"; }

[ "$(id -u)" -eq 0 ] || fail "Run with sudo/root"
[ -d "$PROD/.git" ] || fail "Production repo missing"
[ -x "$PY" ] || fail "Runtime Python missing"

section "DECLARATION"
date --iso-8601=seconds
cat <<EOF
MODE=TASK05_FINAL_OPERATIONAL_MEMORY_POLICY_UPDATE
SOURCE_CODE_CHANGE=NO
LOCAL_SOURCE_PATCH=NO
TASK04_SEMANTIC_REACCEPTANCE=NO
TASK04_ACCEPTANCE_REUSE=YES
UPDATE_CLASS=SNAPSHOT_EXECUTION_POLICY_CHANGE
OLD_PROCESS_MEMORY_GUARD_BYTES=$OLD_LIMIT
NEW_PROCESS_MEMORY_GUARD_BYTES=$NEW_LIMIT
NEW_PROCESS_MEMORY_GUARD_MIB=512
MEASURED_PRE_ACCEPTANCE_MAXRSS_KB=456028
MEASURED_FRESH_WORKER_HWM_KB=306120
MEASURED_FRESH_WORKER_RSS_AFTER_10S_KB=142788
EOF

section "EXACT CODE GUARD"
HEAD="$(git -C "$PROD" rev-parse HEAD)"
TREE="$(git -C "$PROD" rev-parse 'HEAD^{tree}')"
STATUS="$(git -C "$PROD" status --porcelain=v1 --untracked-files=normal)"
echo "PRODUCTION_HEAD=$HEAD"
echo "PRODUCTION_TREE=$TREE"
[ "$HEAD" = "$EXPECTED_HEAD" ] || fail "Unexpected production HEAD"
[ "$TREE" = "$EXPECTED_TREE" ] || fail "Unexpected production tree"
[ -z "$STATUS" ] || fail "Production worktree dirty"

section "SERVICE QUIESCE"
systemctl is-active --quiet captive-portal.service || fail "Portal is not active"
systemctl stop fingerprint-classification.service || true
systemctl is-active --quiet fingerprint-classification.service && fail "Worker did not stop"
echo "PORTAL_STATE=$(systemctl is-active captive-portal.service)"
echo "WORKER_STATE=$(systemctl is-active fingerprint-classification.service)"
echo "SERVICE_QUIESCE=PASS"

section "ATOMIC FOUNDATION + COMPANION CLASSIFICATION ACTIVATION"

sudo -u admin env \
  HOME=/nonexistent \
  PYTHONPATH="$PROD" \
  PYTHONDONTWRITEBYTECODE=1 \
  CONTROL_DB="$CONTROL_DB" \
  EXPECTED_HEAD="$EXPECTED_HEAD" \
  EXPECTED_TREE="$EXPECTED_TREE" \
  EXPECTED_CRP="$EXPECTED_CRP" \
  OLD_LIMIT="$OLD_LIMIT" \
  NEW_LIMIT="$NEW_LIMIT" \
  "$PY" -B - <<'PY'
import os
import uuid
from datetime import datetime, timezone

from app.device_fingerprint.artifact_content import ArtifactRef, make_artifact_content
from app.device_fingerprint.artifact_dependency_graph import extract_direct_artifact_refs
from app.device_fingerprint.control_plane_store import DeviceFingerprintControlPlaneStore
from app.device_fingerprint.runtime_profile_artifacts import (
    make_foundation_runtime_profile,
    make_classification_runtime_profile,
    make_runtime_profile_admission_manifest,
    make_runtime_profile_activation_record,
    make_runtime_profile_validity_record,
)
from app.device_fingerprint.validation import format_utc
from app.device_fingerprint_integration.compatibility import preflight

DB = os.environ["CONTROL_DB"]
HEAD = os.environ["EXPECTED_HEAD"]
TREE = os.environ["EXPECTED_TREE"]
EXPECTED_CRP = os.environ["EXPECTED_CRP"]
OLD_LIMIT = int(os.environ["OLD_LIMIT"])
NEW_LIMIT = int(os.environ["NEW_LIMIT"])

def ref(content):
    return ArtifactRef(content.artifact_id, content.content_sha256).as_dict()

def activate(store, pin, rpm, profile_kind, candidate, now):
    old_head = store.get_validity_head(pin.pointer.activation_record_id)
    if old_head is None or old_head.semantic_payload["state"] != "ACTIVE":
        raise SystemExit(f"FATAL: {profile_kind} predecessor validity is not ACTIVE")

    activation_id = str(uuid.uuid4())
    generation_id = str(uuid.uuid4())
    active_validity_id = str(uuid.uuid4())
    inactive_validity_id = str(uuid.uuid4())

    activation = make_runtime_profile_activation_record({
        "activation_contract_version": 1,
        "activation_record_id": activation_id,
        "profile_kind": profile_kind,
        "runtime_profile_id": candidate.artifact_id,
        "runtime_profile_digest": candidate.content_sha256,
        "runtime_profile_admission_manifest_id": rpm.artifact_id,
        "runtime_profile_admission_manifest_digest": rpm.content_sha256,
        "previous_activation_record_id": pin.pointer.activation_record_id,
        "previous_active_profile_id": pin.runtime_profile.artifact_id,
        "previous_active_profile_digest": pin.runtime_profile.content_sha256,
        "activated_at_utc": now,
        "activation_reason_update_class": "SNAPSHOT_EXECUTION_POLICY_CHANGE",
        "activation_result": "ACTIVE",
        "activation_generation_id": generation_id,
    })

    initial = make_runtime_profile_validity_record({
        "runtime_profile_validity_contract_version": 1,
        "validity_record_id": active_validity_id,
        "profile_kind": profile_kind,
        "runtime_profile_id": candidate.artifact_id,
        "runtime_profile_digest": candidate.content_sha256,
        "activation_record_id": activation_id,
        "state": "ACTIVE",
        "reason_code": "ACTIVATED",
        "effective_at_utc": now,
        "inflight_commit_rule": "ALLOW_PINNED_INFLIGHT",
        "previous_validity_record_id": None,
    })

    inactive = make_runtime_profile_validity_record({
        "runtime_profile_validity_contract_version": 1,
        "validity_record_id": inactive_validity_id,
        "profile_kind": profile_kind,
        "runtime_profile_id": pin.runtime_profile.artifact_id,
        "runtime_profile_digest": pin.runtime_profile.content_sha256,
        "activation_record_id": pin.pointer.activation_record_id,
        "state": "INACTIVE",
        "reason_code": "SUPERSEDED_SAFE",
        "effective_at_utc": now,
        "inflight_commit_rule": "ALLOW_PINNED_INFLIGHT",
        "previous_validity_record_id": old_head.semantic_payload["validity_record_id"],
    })

    return store.activate_profile(
        rpm,
        activation,
        initial,
        predecessor_inactive_validity_record=inactive,
    )

store = DeviceFingerprintControlPlaneStore(DB)

classification_pin = store.pin_active_profile("classification")
foundation_pin = store.pin_active_profile("foundation")

if classification_pin.runtime_profile.artifact_id != EXPECTED_CRP:
    raise SystemExit("FATAL: classification active CRP changed")

class_payload = classification_pin.runtime_profile.semantic_payload
foundation_ref = ArtifactRef.from_dict(class_payload["foundation_runtime_profile"])
if (
    foundation_ref.artifact_id != foundation_pin.runtime_profile.artifact_id
    or foundation_ref.content_sha256 != foundation_pin.runtime_profile.content_sha256
):
    raise SystemExit("FATAL: classification/foundation active pointers are not aligned")

foundation = foundation_pin.runtime_profile
foundation_payload = foundation.semantic_payload
policy_ref = ArtifactRef.from_dict(foundation_payload["snapshot_execution_policy"])
old_policy = store.load_artifact(policy_ref.artifact_id, policy_ref.content_sha256)

if old_policy.artifact_type != "SnapshotExecutionPolicy":
    raise SystemExit("FATAL: wrong snapshot execution policy type")
if old_policy.semantic_payload["process_memory_guard_bytes"] != OLD_LIMIT:
    raise SystemExit(
        "FATAL: old memory guard is not expected 96 MiB: "
        + str(old_policy.semantic_payload["process_memory_guard_bytes"])
    )

new_policy_payload = dict(old_policy.semantic_payload)
new_policy_payload["process_memory_guard_bytes"] = NEW_LIMIT
new_policy = make_artifact_content("SnapshotExecutionPolicy", new_policy_payload)

# Exact operational delta: one field only.
for key, old_value in old_policy.semantic_payload.items():
    if key == "process_memory_guard_bytes":
        continue
    if new_policy.semantic_payload[key] != old_value:
        raise SystemExit(f"FATAL: forbidden SnapshotExecutionPolicy delta: {key}")

new_foundation = make_foundation_runtime_profile({
    **foundation_payload,
    "snapshot_execution_policy": ref(new_policy),
})

# Exact FRP delta: SnapshotExecutionPolicy ref only.
for key, old_value in foundation_payload.items():
    if key == "snapshot_execution_policy":
        continue
    if new_foundation.semantic_payload[key] != old_value:
        raise SystemExit(f"FATAL: forbidden FoundationRuntimeProfile delta: {key}")

proof = make_artifact_content("GateResultManifest", {
    "gate_id": "OWNER-OPERATIONAL-MEMORY-POLICY-2026-10-04",
    "verdict": "PASS",
    "authority": "OWNER",
    "update_class": "SNAPSHOT_EXECUTION_POLICY_CHANGE",
    "semantic_change": False,
    "old_process_memory_guard_bytes": OLD_LIMIT,
    "new_process_memory_guard_bytes": NEW_LIMIT,
    "measured_pre_acceptance_maxrss_kb": 456028,
    "measured_fresh_worker_hwm_kb": 306120,
    "measured_fresh_worker_rss_after_10s_kb": 142788,
    "reason":
        "96MiB guard is below observed steady/working RSS and causes "
        "retryable snapshot_memory_pressure before snapshot execution",
})

old_foundation_rpm = foundation_pin.admission_manifest
frpm_payload = old_foundation_rpm.semantic_payload

foundation_rpm = make_runtime_profile_admission_manifest({
    "runtime_profile_admission_contract_version": 1,
    "profile_kind": "foundation",
    "candidate_profile": ref(new_foundation),
    "previous_active_profile": ref(foundation),
    "expected_previous_activation_record_id":
        foundation_pin.pointer.activation_record_id,
    "expected_previous_activation_generation_id":
        foundation_pin.pointer.activation_generation_id,
    "update_class": "SNAPSHOT_EXECUTION_POLICY_CHANGE",
    "prerequisite_gate_results": [ref(proof)],
    "compatibility_validation_result": "PASS",
    "candidate_repository_commit_sha": HEAD,
    "candidate_repository_tree_sha": TREE,
    "foundation_admission_manifest": frpm_payload["foundation_admission_manifest"],
    "task04_acceptance_manifest": None,
    "foundation_runtime_profile_admission_manifest": None,
})

# Persist foundation operational update.
store.persist_artifact(proof)
store.persist_artifact(new_policy)
store.persist_artifact(new_foundation, extract_direct_artifact_refs(new_foundation))
store.persist_artifact(foundation_rpm, extract_direct_artifact_refs(foundation_rpm))

now = format_utc(datetime.now(timezone.utc))
new_foundation_pointer = activate(
    store, foundation_pin, foundation_rpm, "foundation", new_foundation, now
)

# Companion classification profile: ONLY FoundationRuntimeProfile ref changes.
new_classification = make_classification_runtime_profile({
    **class_payload,
    "foundation_runtime_profile": ref(new_foundation),
})
for key, old_value in class_payload.items():
    if key == "foundation_runtime_profile":
        continue
    if new_classification.semantic_payload[key] != old_value:
        raise SystemExit(f"FATAL: forbidden ClassificationRuntimeProfile delta: {key}")

old_class_rpm = classification_pin.admission_manifest
crpm_payload = old_class_rpm.semantic_payload
acceptance_ref = crpm_payload["task04_acceptance_manifest"]
if acceptance_ref is None:
    raise SystemExit("FATAL: current classification acceptance missing")

classification_rpm = make_runtime_profile_admission_manifest({
    "runtime_profile_admission_contract_version": 1,
    "profile_kind": "classification",
    "candidate_profile": ref(new_classification),
    "previous_active_profile": ref(classification_pin.runtime_profile),
    "expected_previous_activation_record_id":
        classification_pin.pointer.activation_record_id,
    "expected_previous_activation_generation_id":
        classification_pin.pointer.activation_generation_id,
    "update_class": "SNAPSHOT_EXECUTION_POLICY_CHANGE",
    "prerequisite_gate_results": [ref(proof)],
    "compatibility_validation_result": "PASS",
    "candidate_repository_commit_sha": HEAD,
    "candidate_repository_tree_sha": TREE,
    "foundation_admission_manifest": frpm_payload["foundation_admission_manifest"],
    "task04_acceptance_manifest": acceptance_ref,
    "foundation_runtime_profile_admission_manifest": ref(foundation_rpm),
})

store.persist_artifact(
    new_classification, extract_direct_artifact_refs(new_classification)
)
store.persist_artifact(
    classification_rpm, extract_direct_artifact_refs(classification_rpm)
)

new_classification_pointer = activate(
    store,
    classification_pin,
    classification_rpm,
    "classification",
    new_classification,
    now,
)

# Exact post-activation checks.
active_foundation = store.pin_active_profile("foundation")
active_classification = store.pin_active_profile("classification")

if active_foundation.runtime_profile != new_foundation:
    raise SystemExit("FATAL: new foundation profile not active")
if active_classification.runtime_profile != new_classification:
    raise SystemExit("FATAL: companion classification profile not active")

pf = preflight(store)
if pf.pin.runtime_profile != new_classification:
    raise SystemExit("FATAL: production preflight did not pin new companion CRP")

active_fref = ArtifactRef.from_dict(
    pf.pin.runtime_profile.semantic_payload["foundation_runtime_profile"]
)
active_frp = store.load_artifact(
    active_fref.artifact_id, active_fref.content_sha256
)
active_pref = ArtifactRef.from_dict(
    active_frp.semantic_payload["snapshot_execution_policy"]
)
active_policy = store.load_artifact(
    active_pref.artifact_id, active_pref.content_sha256
)
if active_policy.semantic_payload["process_memory_guard_bytes"] != NEW_LIMIT:
    raise SystemExit("FATAL: active memory limit is not 512 MiB")

print("OPERATIONAL_PROOF_ID=" + proof.artifact_id)
print("NEW_SNAPSHOT_EXECUTION_POLICY_ID=" + new_policy.artifact_id)
print("NEW_FOUNDATION_RUNTIME_PROFILE_ID=" + new_foundation.artifact_id)
print("NEW_FOUNDATION_RPM_ID=" + foundation_rpm.artifact_id)
print("NEW_FOUNDATION_ACTIVATION_ID=" +
      new_foundation_pointer.activation_record_id)
print("REUSED_TASK04_ACCEPTANCE_ID=" + acceptance_ref["artifact_id"])
print("NEW_COMPANION_CRP_ID=" + new_classification.artifact_id)
print("NEW_CLASSIFICATION_RPM_ID=" + classification_rpm.artifact_id)
print("NEW_CLASSIFICATION_ACTIVATION_ID=" +
      new_classification_pointer.activation_record_id)
print("ACTIVE_PROCESS_MEMORY_GUARD_BYTES=" +
      str(active_policy.semantic_payload["process_memory_guard_bytes"]))
print("ACTIVE_PROCESS_MEMORY_GUARD_MIB=512")
print("POST_POLICY_PREFLIGHT=PASS")
print("FOUNDATION_ACTIVATION=PASS")
print("COMPANION_CLASSIFICATION_ACTIVATION=PASS")
PY

section "START WORKER"
systemctl start fingerprint-classification.service
sleep 3
systemctl is-active --quiet fingerprint-classification.service || fail "Worker failed to start"
PID="$(systemctl show fingerprint-classification.service -p MainPID --value)"
echo "WORKER_STATE=$(systemctl is-active fingerprint-classification.service)"
echo "WORKER_PID=$PID"
grep -E '^(VmRSS|VmHWM):' "/proc/$PID/status" || true

section "FINAL"
echo "PRODUCTION_HEAD=$(git -C "$PROD" rev-parse HEAD)"
echo "PRODUCTION_TREE=$(git -C "$PROD" rev-parse 'HEAD^{tree}')"
echo "TASK05_MEMORY_POLICY_UPDATE=PASS"
echo "NEXT=ONE_FRESH_OWNER_PHONE_AUTH_AND_LIVE_WORKER_RESULT"
