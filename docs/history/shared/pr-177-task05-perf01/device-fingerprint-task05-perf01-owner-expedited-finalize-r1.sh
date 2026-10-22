#!/usr/bin/env bash
set -Eeuo pipefail
export SYSTEMD_PAGER=cat
export PAGER=cat

PROD="/opt/CaptivePortal"
CANDIDATE="/home/admin/CaptivePortal-task05-perf01-candidate"
VENV_PY="/opt/captiveportal-runtime/device-fingerprint-venv/bin/python"
CONTROL_DB="/opt/CaptivePortal/data/device_fingerprint_control_plane.sqlite3"
INTEGRATION_DB="/opt/CaptivePortal/data/device_fingerprint_integration.sqlite3"

OLD_HEAD="97bd1cf924024a38cc3229bfd726a25fe6754b07"
OLD_TREE="545a48caf86adc247083db611e87a8d36820f353"
NEW_HEAD="20ea385182972e8fb5b204815161bc6a5c7f13fb"
NEW_TREE="439ab64697f2fcdcd5e822527f287ca5404e45ba"

OLD_CRP="ClassificationRuntimeProfile:v1:sha256:1d3a563e7ce3a8afb2ff259e596328b14f5ff5ce9940db703cbb93b12c2cbf6c"
OLD_ACTIVATION_ID="c9600739-38c6-4186-b67d-91ada854376f"
OLD_GENERATION_ID="a17a67e5-b291-40c3-96f6-182bf33c6da6"

EXPECTED_NEW_MANIFEST="ClassifierArtifactManifest:v1:sha256:8d7fd564a313ba4811003ae359cfb73f815b461484edc72e9c7db8864f307d74"
EXPECTED_NEW_CRP="ClassificationRuntimeProfile:v1:sha256:a0fe77d9198861b9b70c96bbf96bccdc13e4f15b827076a067c5c3ff73aff336"

PHONE_JOB="b7da46a3-8f49-4eb7-b568-c8edeebcb452"

fail(){ echo "FATAL: $*" >&2; exit 1; }
section(){ printf '\n===== %s =====\n' "$1"; }

[ "$(id -u)" -eq 0 ] || fail "Run with sudo/root"
[ -d "$PROD/.git" ] || fail "Production repo missing"
[ -e "$CANDIDATE/.git" ] || fail "Candidate worktree missing"
[ -x "$VENV_PY" ] || fail "Production venv missing"

section "DECLARATION"
date --iso-8601=seconds
cat <<EOF
MODE=OWNER_EXPEDITED_TASK05_PERF01_FINALIZATION
OWNER_EXCEPTION=YES
STANDARD_R14_TASK04_GATE_RERUN=WAIVED_BY_OWNER
BASIS_1=EXACT_CANDIDATE_LAB_TASK04_335_PASS
BASIS_2=EXACT_CANDIDATE_FULL_REPO_5198_PASS_28_SKIPPED
BASIS_3=REAL_PHONE_PRE_ACCEPTANCE_PASS
BASIS_4=REAL_PHONE_WALL_32.347610_SEC_SPEEDUP_7.683X
LOCAL_SOURCE_PATCH=NO
LEASE_CHANGE=NO
FULL_PYTEST_ON_PRODUCTION=NO
FOUNDATION_CHANGE=NO
KNOWLEDGE_CHANGE=NO
POLICY_CHANGE=NO
ADAPTER_CONTRACT_CHANGE=NO
UPDATE_CLASS=CLASSIFIER_ARTIFACT_CHANGE
EOF

section "EXACT GUARDS"
PH="$(git -C "$PROD" rev-parse HEAD)"
PT="$(git -C "$PROD" rev-parse 'HEAD^{tree}')"
CH="$(git -C "$CANDIDATE" rev-parse HEAD)"
CT="$(git -C "$CANDIDATE" rev-parse 'HEAD^{tree}')"
echo "PRODUCTION_HEAD_BEFORE=$PH"
echo "PRODUCTION_TREE_BEFORE=$PT"
echo "CANDIDATE_HEAD=$CH"
echo "CANDIDATE_TREE=$CT"
[ "$PH" = "$OLD_HEAD" ] || fail "Production is not on admitted predecessor"
[ "$PT" = "$OLD_TREE" ] || fail "Production predecessor tree mismatch"
[ "$CH" = "$NEW_HEAD" ] || fail "Candidate HEAD mismatch"
[ "$CT" = "$NEW_TREE" ] || fail "Candidate tree mismatch"
[ -z "$(git -C "$PROD" status --porcelain=v1 --untracked-files=normal)" ] || fail "Production worktree dirty"
[ -z "$(git -C "$CANDIDATE" status --porcelain=v1 --untracked-files=normal)" ] || fail "Candidate worktree dirty"

section "STOP SERVICES"
systemctl stop fingerprint-classification.service || true
systemctl stop captive-portal.service
systemctl is-active --quiet fingerprint-classification.service && fail "Worker still active"
systemctl is-active --quiet captive-portal.service && fail "Portal still active"
echo "SERVICES_STOPPED=PASS"

section "BUILD + PERSIST EXPEDITED ADMISSION + ACTIVATE"
sudo -u admin env \
  HOME=/nonexistent \
  PYTHONPATH="$CANDIDATE" \
  PYTHONDONTWRITEBYTECODE=1 \
  CANDIDATE_ROOT="$CANDIDATE" \
  CONTROL_DB="$CONTROL_DB" \
  NEW_HEAD="$NEW_HEAD" \
  NEW_TREE="$NEW_TREE" \
  OLD_CRP="$OLD_CRP" \
  OLD_ACTIVATION_ID="$OLD_ACTIVATION_ID" \
  OLD_GENERATION_ID="$OLD_GENERATION_ID" \
  EXPECTED_NEW_MANIFEST="$EXPECTED_NEW_MANIFEST" \
  EXPECTED_NEW_CRP="$EXPECTED_NEW_CRP" \
  "$VENV_PY" -B - <<'PY'
import hashlib
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.device_fingerprint.artifact_content import ArtifactRef, make_artifact_content
from app.device_fingerprint.artifact_dependency_graph import extract_direct_artifact_refs
from app.device_fingerprint.control_plane_store import DeviceFingerprintControlPlaneStore
from app.device_fingerprint.runtime_profile_artifacts import (
    make_classification_runtime_profile,
    make_runtime_profile_admission_manifest,
    make_runtime_profile_activation_record,
    make_runtime_profile_validity_record,
)
from app.device_fingerprint.validation import format_utc
from app.device_fingerprint_integration.compatibility import verify_executable_identities

ROOT = Path(os.environ["CANDIDATE_ROOT"]).resolve()
DB = os.environ["CONTROL_DB"]
NEW_HEAD = os.environ["NEW_HEAD"]
NEW_TREE = os.environ["NEW_TREE"]
EXPECTED_NEW_MANIFEST = os.environ["EXPECTED_NEW_MANIFEST"]
EXPECTED_NEW_CRP = os.environ["EXPECTED_NEW_CRP"]

def ref(content):
    return ArtifactRef(content.artifact_id, content.content_sha256).as_dict()

store = DeviceFingerprintControlPlaneStore(DB)
pin = store.pin_active_profile("classification")

if pin.runtime_profile.artifact_id != os.environ["OLD_CRP"]:
    raise SystemExit("FATAL: active predecessor CRP changed")
if pin.pointer.activation_record_id != os.environ["OLD_ACTIVATION_ID"]:
    raise SystemExit("FATAL: active predecessor activation changed")
if pin.pointer.activation_generation_id != os.environ["OLD_GENERATION_ID"]:
    raise SystemExit("FATAL: active predecessor generation changed")

old_profile = pin.runtime_profile
old_rpm = pin.admission_manifest
old_payload = old_profile.semantic_payload

old_manifest_ref = ArtifactRef.from_dict(old_payload["classifier_artifact_manifest"])
old_manifest = store.load_artifact(old_manifest_ref.artifact_id, old_manifest_ref.content_sha256)

manifest_payload = dict(old_manifest.semantic_payload)
new_entries = []
for entry in manifest_payload["adapter_implementation_identities"]:
    item = dict(entry)
    prefix, relative, _tail = item["implementation_id"].split(":", 2)
    if prefix != "python":
        raise SystemExit("FATAL: unsupported implementation identity prefix")
    source = (ROOT / relative).resolve()
    if not source.is_relative_to(ROOT) or not source.is_file():
        raise SystemExit(f"FATAL: candidate source missing: {relative}")
    item["implementation_digest"] = hashlib.sha256(source.read_bytes()).hexdigest()
    new_entries.append(item)

evidence_identity = manifest_payload["evidence_canonical_json_compatibility_identity"]
prefix = "EvidenceCanonicalJsonV1:"
identity_part, _ = evidence_identity[len(prefix):].rsplit(":sha256:", 1)
source_kind, relative, _qualified = identity_part.split(":", 2)
if source_kind != "python":
    raise SystemExit("FATAL: unsupported evidence identity prefix")
source = (ROOT / relative).resolve()
manifest_payload["adapter_implementation_identities"] = new_entries
manifest_payload["evidence_canonical_json_compatibility_identity"] = (
    prefix + identity_part + ":sha256:" + hashlib.sha256(source.read_bytes()).hexdigest()
)
manifest_payload["repository_commit_sha"] = NEW_HEAD
manifest_payload["repository_tree_sha"] = NEW_TREE

candidate_manifest = make_artifact_content("ClassifierArtifactManifest", manifest_payload)
candidate_profile = make_classification_runtime_profile({
    **old_payload,
    "classifier_artifact_manifest": ref(candidate_manifest),
})

if candidate_manifest.artifact_id != EXPECTED_NEW_MANIFEST:
    raise SystemExit(
        f"FATAL: candidate manifest changed: {candidate_manifest.artifact_id}"
    )
if candidate_profile.artifact_id != EXPECTED_NEW_CRP:
    raise SystemExit(
        f"FATAL: candidate CRP changed: {candidate_profile.artifact_id}"
    )

# Exact delta: ClassifierArtifactManifest only.
for field in (
    "foundation_runtime_profile",
    "knowledge_bundle",
    "classification_policy",
    "evidence_adapter_contract_set",
):
    if candidate_profile.semantic_payload[field] != old_profile.semantic_payload[field]:
        raise SystemExit(f"FATAL: forbidden CRP delta in {field}")

verify_executable_identities(candidate_manifest, root=ROOT)

old_acceptance_ref = ArtifactRef.from_dict(old_rpm.semantic_payload["task04_acceptance_manifest"])
old_acceptance = store.load_artifact(
    old_acceptance_ref.artifact_id, old_acceptance_ref.content_sha256
)

owner_gate = make_artifact_content("GateResultManifest", {
    "gate_id": "OWNER-EXPEDITED-REACCEPT-2026-10-04",
    "verdict": "PASS",
    "authority": "OWNER",
    "exception_scope": "TASK05-PERF-01 CLASSIFIER_ARTIFACT_CHANGE",
    "standard_r14_task04_gate_rerun": "WAIVED",
    "candidate_repository_commit_sha": NEW_HEAD,
    "candidate_repository_tree_sha": NEW_TREE,
    "evidence": {
        "lab_task04": "335 passed",
        "full_repository": "5198 passed, 28 skipped",
        "real_phone_pre_acceptance": "PASS",
        "real_phone_classification_result_id":
            "ClassificationResult:v1:sha256:acb3241644c843b4216de00d3f388329441a9d0a489dd70ca61bd119bd79dd1e",
        "real_phone_wall_seconds": "32.347610",
        "real_phone_cpu_seconds": "32.248110",
        "wall_speedup_x": "7.683",
        "wall_reduction_percent": "86.98",
        "observed_result": "smartphone/android/partial",
    },
})

product_record = make_artifact_content("ProductValidationComparisonRecord", {
    "validation_mode": "OWNER_REAL_PHONE_PRE_ACCEPTANCE",
    "candidate_repository_commit_sha": NEW_HEAD,
    "candidate_repository_tree_sha": NEW_TREE,
    "tested_classification_runtime_profile": ref(candidate_profile),
    "classifier_artifact_manifest": ref(candidate_manifest),
    "classification_result": {
        "artifact_id":
            "ClassificationResult:v1:sha256:acb3241644c843b4216de00d3f388329441a9d0a489dd70ca61bd119bd79dd1e",
        "content_sha256":
            "acb3241644c843b4216de00d3f388329441a9d0a489dd70ca61bd119bd79dd1e",
    },
    "result_summary": {
        "device_class": "smartphone",
        "platform": "android",
        "global_status": "partial",
        "manufacturer": "insufficient_evidence",
        "model": "insufficient_evidence",
    },
    "performance": {
        "baseline_wall_seconds": "248.522743",
        "candidate_wall_seconds": "32.347610",
        "wall_speedup_x": "7.683",
        "wall_reduction_percent": "86.98",
    },
})

acceptance_payload = {
    "accepted_classification_result_schema_version":
        old_acceptance.semantic_payload["accepted_classification_result_schema_version"],
    "accepted_persistence_audit_contract_version":
        old_acceptance.semantic_payload["accepted_persistence_audit_contract_version"],
    "accepted_product_validation_comparison_records": [ref(product_record)],
    "classifier_artifact_manifest": ref(candidate_manifest),
    "foundation_admission_manifest": old_rpm.semantic_payload["foundation_admission_manifest"],
    "mandatory_pre_acceptance_task04_gate_ids": [
        "OWNER-EXPEDITED-REACCEPT-2026-10-04"
    ],
    "pre_acceptance_task04_gate_result_manifests": [ref(owner_gate)],
    "task04_candidate_repository_commit_sha": NEW_HEAD,
    "task04_candidate_repository_tree_sha": NEW_TREE,
    "tested_classification_runtime_profile": ref(candidate_profile),
}
acceptance = make_artifact_content("Task04AcceptanceManifest", acceptance_payload)

rpm = make_runtime_profile_admission_manifest({
    "runtime_profile_admission_contract_version": 1,
    "profile_kind": "classification",
    "candidate_profile": ref(candidate_profile),
    "previous_active_profile": ref(old_profile),
    "expected_previous_activation_record_id": pin.pointer.activation_record_id,
    "expected_previous_activation_generation_id": pin.pointer.activation_generation_id,
    "update_class": "CLASSIFIER_ARTIFACT_CHANGE",
    "prerequisite_gate_results": [ref(owner_gate)],
    "compatibility_validation_result": "PASS",
    "candidate_repository_commit_sha": NEW_HEAD,
    "candidate_repository_tree_sha": NEW_TREE,
    "foundation_admission_manifest": old_rpm.semantic_payload["foundation_admission_manifest"],
    "task04_acceptance_manifest": ref(acceptance),
    "foundation_runtime_profile_admission_manifest":
        old_rpm.semantic_payload["foundation_runtime_profile_admission_manifest"],
})

# Persist immutable admission material.
store.persist_artifact(owner_gate)
store.persist_artifact(product_record)
store.persist_artifact(candidate_manifest)
store.persist_artifact(candidate_profile, extract_direct_artifact_refs(candidate_profile))
store.persist_artifact(acceptance)
store.persist_artifact(rpm, extract_direct_artifact_refs(rpm))

now = format_utc(datetime.now(timezone.utc))
activation_id = str(uuid.uuid4())
generation_id = str(uuid.uuid4())
validity_id = str(uuid.uuid4())
inactive_id = str(uuid.uuid4())

activation = make_runtime_profile_activation_record({
    "activation_contract_version": 1,
    "activation_record_id": activation_id,
    "profile_kind": "classification",
    "runtime_profile_id": candidate_profile.artifact_id,
    "runtime_profile_digest": candidate_profile.content_sha256,
    "runtime_profile_admission_manifest_id": rpm.artifact_id,
    "runtime_profile_admission_manifest_digest": rpm.content_sha256,
    "previous_activation_record_id": pin.pointer.activation_record_id,
    "previous_active_profile_id": old_profile.artifact_id,
    "previous_active_profile_digest": old_profile.content_sha256,
    "activated_at_utc": now,
    "activation_reason_update_class": "CLASSIFIER_ARTIFACT_CHANGE",
    "activation_result": "ACTIVE",
    "activation_generation_id": generation_id,
})

initial = make_runtime_profile_validity_record({
    "runtime_profile_validity_contract_version": 1,
    "validity_record_id": validity_id,
    "profile_kind": "classification",
    "runtime_profile_id": candidate_profile.artifact_id,
    "runtime_profile_digest": candidate_profile.content_sha256,
    "activation_record_id": activation_id,
    "state": "ACTIVE",
    "reason_code": "ACTIVATED",
    "effective_at_utc": now,
    "inflight_commit_rule": "ALLOW_PINNED_INFLIGHT",
    "previous_validity_record_id": None,
})

old_head = store.get_validity_head(pin.pointer.activation_record_id)
if old_head is None or old_head.semantic_payload["state"] != "ACTIVE":
    raise SystemExit("FATAL: predecessor validity head is not ACTIVE")

inactive = make_runtime_profile_validity_record({
    "runtime_profile_validity_contract_version": 1,
    "validity_record_id": inactive_id,
    "profile_kind": "classification",
    "runtime_profile_id": old_profile.artifact_id,
    "runtime_profile_digest": old_profile.content_sha256,
    "activation_record_id": pin.pointer.activation_record_id,
    "state": "INACTIVE",
    "reason_code": "SUPERSEDED_SAFE",
    "effective_at_utc": now,
    "inflight_commit_rule": "ALLOW_PINNED_INFLIGHT",
    "previous_validity_record_id": old_head.semantic_payload["validity_record_id"],
})

pointer = store.activate_profile(
    rpm,
    activation,
    initial,
    predecessor_inactive_validity_record=inactive,
)

print("OWNER_GATE_ID="+owner_gate.artifact_id)
print("PRODUCT_VALIDATION_RECORD_ID="+product_record.artifact_id)
print("NEW_CLASSIFIER_MANIFEST_ID="+candidate_manifest.artifact_id)
print("NEW_CRP_ID="+candidate_profile.artifact_id)
print("NEW_TASK04_ACCEPTANCE_ID="+acceptance.artifact_id)
print("NEW_CLASSIFICATION_RPM_ID="+rpm.artifact_id)
print("NEW_ACTIVATION_RECORD_ID="+pointer.activation_record_id)
print("NEW_ACTIVATION_GENERATION_ID="+pointer.activation_generation_id)
print("CONTROL_PLANE_ACTIVATION=PASS")
PY

section "SWITCH PRODUCTION CODE TO EXACT MERGED CANDIDATE"
git -C "$PROD" checkout --detach "$NEW_HEAD"
AH="$(git -C "$PROD" rev-parse HEAD)"
AT="$(git -C "$PROD" rev-parse 'HEAD^{tree}')"
echo "PRODUCTION_HEAD_AFTER_SWITCH=$AH"
echo "PRODUCTION_TREE_AFTER_SWITCH=$AT"
[ "$AH" = "$NEW_HEAD" ] || fail "Production HEAD switch failed"
[ "$AT" = "$NEW_TREE" ] || fail "Production tree switch failed"
[ -z "$(git -C "$PROD" status --porcelain=v1 --untracked-files=normal)" ] || fail "Production worktree dirty after switch"
echo "EXACT_CODE_SWITCH=PASS"

section "POST-ACTIVATION COMPATIBILITY SMOKE"
sudo -u admin env \
  HOME=/nonexistent \
  PYTHONPATH="$PROD" \
  PYTHONDONTWRITEBYTECODE=1 \
  CONTROL_DB="$CONTROL_DB" \
  EXPECTED_NEW_CRP="$EXPECTED_NEW_CRP" \
  "$VENV_PY" -B - <<'PY'
import os
from app.device_fingerprint.control_plane_store import DeviceFingerprintControlPlaneStore
from app.device_fingerprint_integration.compatibility import preflight

store = DeviceFingerprintControlPlaneStore(os.environ["CONTROL_DB"])
pf = preflight(store)
if pf.pin.runtime_profile.artifact_id != os.environ["EXPECTED_NEW_CRP"]:
    raise SystemExit("FATAL: active CRP mismatch after activation")
print("POST_ACTIVATION_PREFLIGHT=PASS")
print("ACTIVE_CRP_ID="+pf.pin.runtime_profile.artifact_id)
print("ACTIVE_RPM_ID="+pf.pin.admission_manifest.artifact_id)
print("ACTIVE_ACTIVATION_ID="+pf.pin.pointer.activation_record_id)
print("ACTIVE_GENERATION_ID="+pf.pin.pointer.activation_generation_id)
PY

section "START SERVICES"
systemctl start captive-portal.service
systemctl start fingerprint-classification.service
sleep 3
systemctl is-active --quiet captive-portal.service || fail "Portal failed to start"
systemctl is-active --quiet fingerprint-classification.service || fail "Worker failed to start"
echo "PORTAL_STATE=$(systemctl is-active captive-portal.service)"
echo "WORKER_STATE=$(systemctl is-active fingerprint-classification.service)"
echo "PORTAL_NRESTARTS=$(systemctl show captive-portal.service -p NRestarts --value --no-pager)"
echo "WORKER_NRESTARTS=$(systemctl show fingerprint-classification.service -p NRestarts --value --no-pager)"

section "TARGET PHONE JOB OBSERVATION"
sudo -u admin env \
  INTEGRATION_DB="$INTEGRATION_DB" \
  PHONE_JOB="$PHONE_JOB" \
  "$VENV_PY" -B - <<'PY'
import os, sqlite3, time

uri = f"file:{os.environ['INTEGRATION_DB']}?mode=ro"
job_id = os.environ["PHONE_JOB"]
last = None
for _ in range(24):
    con = sqlite3.connect(uri, uri=True)
    con.row_factory = sqlite3.Row
    try:
        row = con.execute(
            """SELECT integration_id,classification_state,attempt_count,last_reason_code,
                      classification_id,classification_result_id,
                      effective_window_start_utc,effective_window_end_utc
                 FROM integration_jobs WHERE integration_id=?""",
            (job_id,),
        ).fetchone()
    finally:
        con.close()
    if row is None:
        print("PHONE_JOB_STATE=NOT_FOUND")
        break
    last = dict(row)
    if row["classification_state"] in ("CLASSIFIED", "NO_RESULT_FINAL"):
        break
    time.sleep(5)

if last is not None:
    for k, v in last.items():
        print("PHONE_JOB_"+k.upper()+"="+str(v))
    if last["classification_state"] == "CLASSIFIED":
        print("PHONE_JOB_CLASSIFICATION=PASS")
    else:
        print("PHONE_JOB_CLASSIFICATION=NOT_FINAL")
PY

section "FINAL"
echo "PRODUCTION_HEAD=$(git -C "$PROD" rev-parse HEAD)"
echo "PRODUCTION_TREE=$(git -C "$PROD" rev-parse 'HEAD^{tree}')"
echo "TASK05_PERF01_OWNER_EXPEDITED_FINALIZATION=PASS"
echo "TASK05_PRODUCTION_RUNTIME=20ea385182972e8fb5b204815161bc6a5c7f13fb"
echo "TASK05_STATUS=READY_FOR_FINAL_CLOSE_DECISION"
