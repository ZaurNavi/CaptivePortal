#!/usr/bin/env bash
set -Eeuo pipefail
export SYSTEMD_PAGER=cat
export PAGER=cat

PROD="/opt/CaptivePortal"
PY="/opt/captiveportal-runtime/device-fingerprint-venv/bin/python"
CONTROL_DB="/opt/CaptivePortal/data/device_fingerprint_control_plane.sqlite3"

EXPECTED_HEAD="20ea385182972e8fb5b204815161bc6a5c7f13fb"
EXPECTED_TREE="439ab64697f2fcdcd5e822527f287ca5404e45ba"
EXPECTED_CLASSIFIER="ClassifierArtifactManifest:v1:sha256:8d7fd564a313ba4811003ae359cfb73f815b461484edc72e9c7db8864f307d74"

LIMIT_96M=100663296
LIMIT_512M=536870912
LIMIT_1G=1073741824

fail(){ echo "FATAL: $*" >&2; exit 1; }
section(){ printf '\n===== %s =====\n' "$1"; }

[ "$(id -u)" -eq 0 ] || fail "Run with sudo/root"
[ -d "$PROD/.git" ] || fail "Production repo missing"
[ -x "$PY" ] || fail "Runtime Python missing"

section "DECLARATION"
date --iso-8601=seconds
cat <<EOF
MODE=TASK05_FINAL_OPERATIONAL_MEMORY_POLICY_1G_R2
SOURCE_CODE_CHANGE=NO
LOCAL_SOURCE_PATCH=NO
TASK04_GATE_RERUN=NO
TASK04_SEMANTIC_REACCEPTANCE=NO
TASK04_ACCEPTANCE_REBIND_ONLY=YES
UPDATE_CLASS=SNAPSHOT_EXECUTION_POLICY_CHANGE
TARGET_PROCESS_MEMORY_GUARD_BYTES=$LIMIT_1G
TARGET_PROCESS_MEMORY_GUARD_MIB=1024
RECOVERS_FROM_PARTIAL_512M_ACTIVATION=YES
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

section "1G FOUNDATION + COMPANION CLASSIFICATION REBIND"

sudo -u admin env \
  HOME=/nonexistent \
  PYTHONPATH="$PROD" \
  PYTHONDONTWRITEBYTECODE=1 \
  CONTROL_DB="$CONTROL_DB" \
  EXPECTED_HEAD="$EXPECTED_HEAD" \
  EXPECTED_TREE="$EXPECTED_TREE" \
  EXPECTED_CLASSIFIER="$EXPECTED_CLASSIFIER" \
  LIMIT_96M="$LIMIT_96M" \
  LIMIT_512M="$LIMIT_512M" \
  LIMIT_1G="$LIMIT_1G" \
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
EXPECTED_CLASSIFIER = os.environ["EXPECTED_CLASSIFIER"]
LIMIT_96M = int(os.environ["LIMIT_96M"])
LIMIT_512M = int(os.environ["LIMIT_512M"])
LIMIT_1G = int(os.environ["LIMIT_1G"])

def ref(content):
    return ArtifactRef(content.artifact_id, content.content_sha256).as_dict()

def activate(store, pin, rpm, profile_kind, candidate, now):
    old_head = store.get_validity_head(pin.pointer.activation_record_id)
    if old_head is None or old_head.semantic_payload["state"] != "ACTIVE":
        raise SystemExit(f"FATAL: {profile_kind} predecessor validity is not ACTIVE")

    activation_id = str(uuid.uuid4())
    generation_id = str(uuid.uuid4())

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
        "validity_record_id": str(uuid.uuid4()),
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
        "validity_record_id": str(uuid.uuid4()),
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

# Current classification must still be the exact admitted PERF classifier;
# only its Foundation ref may have moved during the failed 512-MiB run.
class_payload = classification_pin.runtime_profile.semantic_payload
classifier_ref = ArtifactRef.from_dict(class_payload["classifier_artifact_manifest"])
if classifier_ref.artifact_id != EXPECTED_CLASSIFIER:
    raise SystemExit(
        "FATAL: active classifier is not exact Task05 PERF classifier: "
        + classifier_ref.artifact_id
    )

foundation_ref = ArtifactRef.from_dict(class_payload["foundation_runtime_profile"])
if (
    foundation_ref.artifact_id != foundation_pin.runtime_profile.artifact_id
    or foundation_ref.content_sha256 != foundation_pin.runtime_profile.content_sha256
):
    raise SystemExit("FATAL: active classification/foundation pointers are not aligned")

foundation = foundation_pin.runtime_profile
foundation_payload = foundation.semantic_payload
policy_ref = ArtifactRef.from_dict(foundation_payload["snapshot_execution_policy"])
current_policy = store.load_artifact(policy_ref.artifact_id, policy_ref.content_sha256)
current_limit = current_policy.semantic_payload["process_memory_guard_bytes"]

print("CURRENT_CLASSIFICATION_PROFILE_ID=" + classification_pin.runtime_profile.artifact_id)
print("CURRENT_FOUNDATION_PROFILE_ID=" + foundation.artifact_id)
print("CURRENT_SNAPSHOT_EXECUTION_POLICY_ID=" + current_policy.artifact_id)
print("CURRENT_PROCESS_MEMORY_GUARD_BYTES=" + str(current_limit))
print("CURRENT_PROCESS_MEMORY_GUARD_MIB=" + str(current_limit // 1024 // 1024))

if current_limit not in (LIMIT_96M, LIMIT_512M, LIMIT_1G):
    raise SystemExit(
        "FATAL: unexpected current memory guard; refusing to guess: "
        + str(current_limit)
    )

# Resolve the current Task04 acceptance even if current preflight is intentionally
# fail-closed because the failed 512-MiB run reused an acceptance tied to its old CRP.
current_class_rpm = classification_pin.admission_manifest
acceptance_ref = current_class_rpm.semantic_payload["task04_acceptance_manifest"]
if acceptance_ref is None:
    raise SystemExit("FATAL: current classification acceptance missing")
base_acceptance = store.load_artifact(
    acceptance_ref["artifact_id"], acceptance_ref["content_sha256"]
)
if (
    base_acceptance.artifact_type != "Task04AcceptanceManifest"
    or base_acceptance.semantic_payload["classifier_artifact_manifest"] !=
       class_payload["classifier_artifact_manifest"]
):
    raise SystemExit("FATAL: current acceptance/classifier lineage mismatch")

# If already 1 GiB, only repair the acceptance binding if needed.
if current_limit == LIMIT_1G:
    new_policy = current_policy
    new_foundation = foundation
    foundation_rpm = foundation_pin.admission_manifest
    foundation_was_activated = False
else:
    new_policy_payload = dict(current_policy.semantic_payload)
    new_policy_payload["process_memory_guard_bytes"] = LIMIT_1G
    new_policy = make_artifact_content("SnapshotExecutionPolicy", new_policy_payload)

    for key, value in current_policy.semantic_payload.items():
        if key != "process_memory_guard_bytes" and new_policy.semantic_payload[key] != value:
            raise SystemExit("FATAL: forbidden SnapshotExecutionPolicy delta: " + key)

    new_foundation = make_foundation_runtime_profile({
        **foundation_payload,
        "snapshot_execution_policy": ref(new_policy),
    })

    for key, value in foundation_payload.items():
        if key != "snapshot_execution_policy" and new_foundation.semantic_payload[key] != value:
            raise SystemExit("FATAL: forbidden FoundationRuntimeProfile delta: " + key)

    proof = make_artifact_content("GateResultManifest", {
        "gate_id": "OWNER-OPERATIONAL-MEMORY-POLICY-1G-2026-10-04",
        "verdict": "PASS",
        "authority": "OWNER",
        "update_class": "SNAPSHOT_EXECUTION_POLICY_CHANGE",
        "semantic_change": False,
        "previous_process_memory_guard_bytes": current_limit,
        "new_process_memory_guard_bytes": LIMIT_1G,
        "measured_pre_acceptance_maxrss_kb": 456028,
        "measured_fresh_worker_hwm_kb": 306120,
        "measured_fresh_worker_rss_after_10s_kb": 142788,
        "reason":
            "Observed successful classifier peak is about 445 MiB; "
            "96 MiB is proven invalid and 512 MiB leaves insufficient "
            "operational headroom. 1 GiB remains a bounded RSS guard.",
    })

    frpm_payload = foundation_pin.admission_manifest.semantic_payload
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
        "foundation_admission_manifest":
            frpm_payload["foundation_admission_manifest"],
        "task04_acceptance_manifest": None,
        "foundation_runtime_profile_admission_manifest": None,
    })

    store.persist_artifact(proof)
    store.persist_artifact(new_policy)
    store.persist_artifact(
        new_foundation, extract_direct_artifact_refs(new_foundation)
    )
    store.persist_artifact(
        foundation_rpm, extract_direct_artifact_refs(foundation_rpm)
    )

    now = format_utc(datetime.now(timezone.utc))
    foundation_pointer = activate(
        store, foundation_pin, foundation_rpm, "foundation", new_foundation, now
    )
    foundation_was_activated = True
    print("OPERATIONAL_PROOF_ID=" + proof.artifact_id)
    print("NEW_FOUNDATION_ACTIVATION_ID=" + foundation_pointer.activation_record_id)

# Companion classification: only FoundationRuntimeProfile ref changes.
new_classification = make_classification_runtime_profile({
    **class_payload,
    "foundation_runtime_profile": ref(new_foundation),
})
for key, value in class_payload.items():
    if key != "foundation_runtime_profile" and new_classification.semantic_payload[key] != value:
        raise SystemExit("FATAL: forbidden ClassificationRuntimeProfile delta: " + key)

# Current implementation of preflight requires the Task04AcceptanceManifest
# to reference the exact active CRP. Rebind the already-accepted evidence only;
# no gate result, product validation, classifier semantics or schema is changed.
acceptance_payload = dict(base_acceptance.semantic_payload)
acceptance_payload["tested_classification_runtime_profile"] = ref(new_classification)

if acceptance_payload["classifier_artifact_manifest"] != class_payload["classifier_artifact_manifest"]:
    raise SystemExit("FATAL: acceptance rebind changed classifier manifest")

rebound_acceptance = make_artifact_content(
    "Task04AcceptanceManifest", acceptance_payload
)

# Confirm this is a pure CRP-reference rebind of the previous acceptance.
for key, value in base_acceptance.semantic_payload.items():
    if key == "tested_classification_runtime_profile":
        continue
    if rebound_acceptance.semantic_payload[key] != value:
        raise SystemExit("FATAL: forbidden Task04AcceptanceManifest rebind delta: " + key)

current_class_rpm_payload = classification_pin.admission_manifest.semantic_payload
new_classification_rpm = make_runtime_profile_admission_manifest({
    "runtime_profile_admission_contract_version": 1,
    "profile_kind": "classification",
    "candidate_profile": ref(new_classification),
    "previous_active_profile": ref(classification_pin.runtime_profile),
    "expected_previous_activation_record_id":
        classification_pin.pointer.activation_record_id,
    "expected_previous_activation_generation_id":
        classification_pin.pointer.activation_generation_id,
    "update_class": "SNAPSHOT_EXECUTION_POLICY_CHANGE",
    "prerequisite_gate_results":
        foundation_rpm.semantic_payload["prerequisite_gate_results"],
    "compatibility_validation_result": "PASS",
    "candidate_repository_commit_sha": HEAD,
    "candidate_repository_tree_sha": TREE,
    "foundation_admission_manifest":
        foundation_rpm.semantic_payload["foundation_admission_manifest"],
    "task04_acceptance_manifest": ref(rebound_acceptance),
    "foundation_runtime_profile_admission_manifest": ref(foundation_rpm),
})

store.persist_artifact(rebound_acceptance)
store.persist_artifact(
    new_classification, extract_direct_artifact_refs(new_classification)
)
store.persist_artifact(
    new_classification_rpm,
    extract_direct_artifact_refs(new_classification_rpm)
)

# Avoid pointless new activation if current profile is already exact 1-GiB CRP
# and only the acceptance binding was bad: we still need a new RPM/activation,
# because the current pinned admission manifest is incompatible.
now = format_utc(datetime.now(timezone.utc))
classification_pointer = activate(
    store,
    classification_pin,
    new_classification_rpm,
    "classification",
    new_classification,
    now,
)

active_foundation = store.pin_active_profile("foundation")
active_classification = store.pin_active_profile("classification")

if active_foundation.runtime_profile != new_foundation:
    raise SystemExit("FATAL: 1-GiB foundation profile is not active")
if active_classification.runtime_profile != new_classification:
    raise SystemExit("FATAL: 1-GiB companion classification profile is not active")

pf = preflight(store)
if pf.pin.runtime_profile != new_classification:
    raise SystemExit("FATAL: preflight pinned unexpected classification profile")

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

if active_policy.semantic_payload["process_memory_guard_bytes"] != LIMIT_1G:
    raise SystemExit("FATAL: active process memory guard is not 1 GiB")

print("BASE_TASK04_ACCEPTANCE_ID=" + base_acceptance.artifact_id)
print("REBOUND_TASK04_ACCEPTANCE_ID=" + rebound_acceptance.artifact_id)
print("TASK04_GATE_RERUN=NO")
print("TASK04_ACCEPTANCE_REBIND_ONLY=PASS")
print("NEW_SNAPSHOT_EXECUTION_POLICY_ID=" + new_policy.artifact_id)
print("NEW_FOUNDATION_RUNTIME_PROFILE_ID=" + new_foundation.artifact_id)
print("NEW_FOUNDATION_RPM_ID=" + foundation_rpm.artifact_id)
print("NEW_COMPANION_CRP_ID=" + new_classification.artifact_id)
print("NEW_CLASSIFICATION_RPM_ID=" + new_classification_rpm.artifact_id)
print("NEW_CLASSIFICATION_ACTIVATION_ID=" +
      classification_pointer.activation_record_id)
print("ACTIVE_PROCESS_MEMORY_GUARD_BYTES=" +
      str(active_policy.semantic_payload["process_memory_guard_bytes"]))
print("ACTIVE_PROCESS_MEMORY_GUARD_MIB=1024")
print("POST_POLICY_PREFLIGHT=PASS")
print("FOUNDATION_STATE=PASS")
print("COMPANION_CLASSIFICATION_STATE=PASS")
PY

section "START WORKER"
systemctl start fingerprint-classification.service
sleep 3
systemctl is-active --quiet fingerprint-classification.service || fail "Worker failed to start"

PID="$(systemctl show fingerprint-classification.service -p MainPID --value)"
echo "WORKER_STATE=$(systemctl is-active fingerprint-classification.service)"
echo "WORKER_PID=$PID"
echo "WORKER_NRESTARTS=$(systemctl show fingerprint-classification.service -p NRestarts --value --no-pager)"
grep -E '^(VmRSS|VmHWM):' "/proc/$PID/status" || true

section "FINAL"
echo "PRODUCTION_HEAD=$(git -C "$PROD" rev-parse HEAD)"
echo "PRODUCTION_TREE=$(git -C "$PROD" rev-parse 'HEAD^{tree}')"
echo "TASK05_MEMORY_POLICY_1G_UPDATE=PASS"
echo "NEXT=ONE_FRESH_OWNER_PHONE_AUTH_AND_LIVE_WORKER_RESULT"
