#!/usr/bin/env bash
set -Eeuo pipefail
export SYSTEMD_PAGER=cat
export PAGER=cat

PORTAL="/opt/CaptivePortal"
CONTROL_DB="/opt/CaptivePortal/data/device_fingerprint_control_plane.sqlite3"
EXPECTED_HEAD="97bd1cf924024a38cc3229bfd726a25fe6754b07"
EXPECTED_TREE="545a48caf86adc247083db611e87a8d36820f353"
VENV_PY="/opt/captiveportal-runtime/device-fingerprint-venv/bin/python"

fail(){ echo "FATAL: $*" >&2; exit 1; }
section(){ printf '\n===== %s =====\n' "$1"; }

[ "$(id -u)" -eq 0 ] || fail "Run with sudo/root"
[ -x "$VENV_PY" ] || fail "Missing production venv"

section "DECLARATION"
date --iso-8601=seconds
echo "MODE=TASK05_PERF01_ADMISSION_LINEAGE_READ_ONLY"
echo "DB_WRITE=NO"
echo "SERVICE_WRITE=NO"
echo "CONFIG_WRITE=NO"
echo "SOURCE_WRITE=NO"
echo "LEASE_CHANGE=NO"

section "RUNTIME GUARD"
HEAD="$(git -C "$PORTAL" rev-parse HEAD)"
TREE="$(git -C "$PORTAL" rev-parse 'HEAD^{tree}')"
echo "PRODUCTION_HEAD=$HEAD"
echo "PRODUCTION_TREE=$TREE"
[ "$HEAD" = "$EXPECTED_HEAD" ] || fail "Unexpected production HEAD"
[ "$TREE" = "$EXPECTED_TREE" ] || fail "Unexpected production tree"
systemctl is-active --quiet captive-portal.service || fail "Portal inactive"
systemctl is-active --quiet fingerprint-classification.service || fail "Worker inactive"
echo "RUNTIME_GUARD=PASS"

section "ACTIVE CLASSIFICATION LINEAGE"
sudo -u admin env \
  HOME=/nonexistent \
  PYTHONPATH="$PORTAL" \
  PYTHONDONTWRITEBYTECODE=1 \
  CONTROL_DB="$CONTROL_DB" \
  "$VENV_PY" -B - <<'PY'
import json, os
from app.device_fingerprint.artifact_content import ArtifactRef
from app.device_fingerprint.control_plane_store import DeviceFingerprintControlPlaneStore

store = DeviceFingerprintControlPlaneStore(os.environ["CONTROL_DB"])
pin = store.pin_active_profile("classification")

def dump(label, content):
    print(f"{label}_ID={content.artifact_id}")
    print(f"{label}_DIGEST={content.content_sha256}")
    print(f"{label}_PAYLOAD={json.dumps(content.semantic_payload, sort_keys=True, separators=(',', ':'))}")

p = pin.runtime_profile.semantic_payload

classifier_ref = ArtifactRef.from_dict(p["classifier_artifact_manifest"])
classifier = store.load_artifact(classifier_ref.artifact_id, classifier_ref.content_sha256)

rpm = pin.admission_manifest
rp = rpm.semantic_payload

accept_ref = ArtifactRef.from_dict(rp["task04_acceptance_manifest"])
acceptance = store.load_artifact(accept_ref.artifact_id, accept_ref.content_sha256)

foundation_rpm_ref = ArtifactRef.from_dict(rp["foundation_runtime_profile_admission_manifest"])
foundation_rpm = store.load_artifact(
    foundation_rpm_ref.artifact_id, foundation_rpm_ref.content_sha256
)

foundation_admission_ref = ArtifactRef.from_dict(rp["foundation_admission_manifest"])
foundation_admission = store.load_artifact(
    foundation_admission_ref.artifact_id, foundation_admission_ref.content_sha256
)

dump("ACTIVE_CRP", pin.runtime_profile)
dump("ACTIVE_CLASSIFIER_MANIFEST", classifier)
dump("ACTIVE_TASK04_ACCEPTANCE", acceptance)
dump("ACTIVE_CLASSIFICATION_RPM", rpm)
dump("ACTIVE_FOUNDATION_RPM", foundation_rpm)
dump("ACTIVE_FOUNDATION_ADMISSION", foundation_admission)
dump("ACTIVE_ACTIVATION", pin.activation_record)
dump("ACTIVE_VALIDITY", pin.validity_record)

ptr = pin.pointer
print("ACTIVE_POINTER_PROFILE_KIND="+ptr.profile_kind)
print("ACTIVE_POINTER_RUNTIME_PROFILE_ID="+ptr.runtime_profile_id)
print("ACTIVE_POINTER_RUNTIME_PROFILE_DIGEST="+ptr.runtime_profile_digest)
print("ACTIVE_POINTER_ACTIVATION_RECORD_ID="+ptr.activation_record_id)
print("ACTIVE_POINTER_ACTIVATION_GENERATION_ID="+ptr.activation_generation_id)
print("ACTIVE_POINTER_UPDATED_AT_UTC="+ptr.updated_at_utc)

print("CLASSIFIER_IMPLEMENTATION_IDENTITIES_BEGIN")
for row in classifier.semantic_payload.get("adapter_implementation_identities", []):
    print(json.dumps(row, sort_keys=True, separators=(",", ":")))
print("CLASSIFIER_IMPLEMENTATION_IDENTITIES_END")
print("EVIDENCE_CANONICAL_IDENTITY="+str(
    classifier.semantic_payload.get("evidence_canonical_json_compatibility_identity")
))

print("ADMISSION_LINEAGE_READ_ONLY=PASS")
PY

section "FINAL"
echo "TASK05_PERF01_ADMISSION_LINEAGE_READ_ONLY=PASS"
