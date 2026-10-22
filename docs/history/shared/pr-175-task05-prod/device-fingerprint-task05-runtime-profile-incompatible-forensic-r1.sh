#!/usr/bin/env bash
set -Eeuo pipefail
export SYSTEMD_PAGER=cat
export PAGER=cat

PORTAL="/opt/CaptivePortal"
VENV_PY="/opt/captiveportal-runtime/device-fingerprint-venv/bin/python"
CONTROL_DB="/opt/CaptivePortal/data/device_fingerprint_control_plane.sqlite3"
INTEGRATION_DB="/opt/CaptivePortal/data/device_fingerprint_integration.sqlite3"
CLASS_DB="/opt/CaptivePortal/data/device_fingerprint_classification.sqlite3"

TARGET_HEAD="1d88f4ae947fa95454dbb54c70f9d6bdd13b1d22"
TARGET_TREE="8183bf48abfc71c1b488c0667efc0f1ae717003e"
CONTROLLED_INTEGRATION_ID="77dcd849-8855-4dd4-b3ed-9d2c62d86935"

section(){ printf '\n===== %s =====\n' "$1"; }
fail(){ echo "FATAL: $*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || fail "Run with sudo/root"

section "DECLARATION"
date --iso-8601=seconds
echo "MODE=READ_ONLY_TASK05_RUNTIME_PROFILE_INCOMPATIBLE_FORENSIC_R1"
echo "DATABASE_WRITE=NO"
echo "SERVICE_RESTART=NO"
echo "CONFIG_WRITE=NO"
echo "SYSTEMD_WRITE=NO"
echo "CONTROLLED_INTEGRATION_ID=$CONTROLLED_INTEGRATION_ID"

section "PRODUCTION IDENTITY AND SERVICES"
HEAD="$(git -C "$PORTAL" rev-parse HEAD)"
TREE="$(git -C "$PORTAL" rev-parse 'HEAD^{tree}')"
echo "CURRENT_HEAD=$HEAD"
echo "CURRENT_TREE=$TREE"
[ "$HEAD" = "$TARGET_HEAD" ] || fail "Unexpected production HEAD"
[ "$TREE" = "$TARGET_TREE" ] || fail "Unexpected production tree"
[ -z "$(git -C "$PORTAL" status --porcelain=v1 --untracked-files=normal)" ] || fail "Production worktree dirty"
for unit in captive-portal.service fingerprint-classification.service fingerprint-evidence.service fingerprint-sensor.service fingerprint-suricata.service; do
  systemctl is-active --quiet "$unit" || fail "$unit not active"
  echo "$unit NRestarts=$(systemctl show "$unit" -p NRestarts --value --no-pager)"
done
echo "PRODUCTION_RUNTIME=PASS"

section "CONTROLLED JOB CURRENT STATE"
INTEGRATION_DB="$INTEGRATION_DB" IID="$CONTROLLED_INTEGRATION_ID" /usr/bin/python3 - <<'PY'
import os, sqlite3
con=sqlite3.connect(f"file:{os.environ['INTEGRATION_DB']}?mode=ro",uri=True)
con.row_factory=sqlite3.Row
try:
    r=con.execute("SELECT * FROM integration_jobs WHERE integration_id=?",(os.environ["IID"],)).fetchone()
finally:
    con.close()
if r is None:
    raise SystemExit("FATAL: controlled integration job missing")
for k in (
    "integration_id","auth_session_id","auth_run_number","site_id","observed_mac",
    "authorized_at_utc","planned_classification_id","classification_state","attempt_count",
    "last_reason_code","identity_state","registry_snapshot_id","device_id","visit_id"
):
    print(k.upper()+"="+("" if r[k] is None else str(r[k])))
PY

section "DETAILED PREFLIGHT INVARIANTS"
sudo -u admin env \
  HOME=/nonexistent \
  PYTHONPATH="$PORTAL" \
  PYTHONDONTWRITEBYTECODE=1 \
  CONTROL_DB="$CONTROL_DB" \
  PORTAL="$PORTAL" \
  "$VENV_PY" -B - <<'PY'
import hashlib, importlib, inspect, os
from pathlib import Path, PurePosixPath

from app.device_fingerprint.artifact_content import ArtifactRef
from app.device_fingerprint.control_plane_store import DeviceFingerprintControlPlaneStore
from app.device_fingerprint.runtime_profile_artifacts import (
    make_classification_runtime_profile,
    make_foundation_runtime_profile,
    make_runtime_profile_admission_manifest,
    make_runtime_profile_validity_record,
)

control = DeviceFingerprintControlPlaneStore(os.environ["CONTROL_DB"])
root = Path(os.environ["PORTAL"]).resolve()

def check(name, cond, detail=""):
    status = "PASS" if cond else "FAIL"
    print(f"{name}={status}" + (f"|{detail}" if detail else ""))
    return bool(cond)

def load_ref(value, kind):
    ref = ArtifactRef.from_dict(value)
    content = control.load_artifact(ref.artifact_id, ref.content_sha256)
    ref.resolve(content, kind)
    print(f"REF_{kind}_ID={content.artifact_id}")
    print(f"REF_{kind}_DIGEST={content.content_sha256}")
    return content

pin = control.pin_active_profile("classification")
profile = pin.runtime_profile
rpm = pin.admission_manifest
validity = pin.validity_record

print("ACTIVE_PROFILE_ID="+profile.artifact_id)
print("ACTIVE_PROFILE_DIGEST="+profile.content_sha256)
print("ACTIVE_RPM_ID="+rpm.artifact_id)
print("ACTIVE_RPM_DIGEST="+rpm.content_sha256)
print("ACTIVE_VALIDITY_ID="+validity.artifact_id)
print("ACTIVE_VALIDITY_STATE="+str(validity.semantic_payload.get("state")))
print("ACTIVATION_GENERATION_ID="+str(pin.pointer.activation_generation_id))
print("ACTIVATION_RECORD_ID="+str(pin.pointer.activation_record_id))

all_ok = True
all_ok &= check("CANONICAL_CLASSIFICATION_PROFILE",
                make_classification_runtime_profile(profile.semantic_payload) == profile)
all_ok &= check("CANONICAL_CLASSIFICATION_RPM",
                make_runtime_profile_admission_manifest(rpm.semantic_payload) == rpm)
all_ok &= check("CANONICAL_CLASSIFICATION_VALIDITY",
                make_runtime_profile_validity_record(validity.semantic_payload) == validity)
all_ok &= check("VALIDITY_ACTIVE", validity.semantic_payload.get("state") == "ACTIVE")

rp = rpm.semantic_payload
candidate_ref = ArtifactRef(profile.artifact_id, profile.content_sha256).as_dict()
all_ok &= check("RPM_PROFILE_KIND", rp.get("profile_kind") == "classification",
                str(rp.get("profile_kind")))
all_ok &= check("RPM_CANDIDATE_EQUALS_ACTIVE_PROFILE",
                rp.get("candidate_profile") == candidate_ref)
all_ok &= check("RPM_COMPATIBILITY_RESULT_PASS",
                rp.get("compatibility_validation_result") == "PASS",
                str(rp.get("compatibility_validation_result")))

try:
    accepted = load_ref(rp["task04_acceptance_manifest"], "Task04AcceptanceManifest")
    foundation_rpm = load_ref(
        rp["foundation_runtime_profile_admission_manifest"],
        "RuntimeProfileAdmissionManifest",
    )
    p = profile.semantic_payload
    foundation = load_ref(p["foundation_runtime_profile"], "FoundationRuntimeProfile")

    all_ok &= check("CANONICAL_FOUNDATION_PROFILE",
                    make_foundation_runtime_profile(foundation.semantic_payload) == foundation)
    all_ok &= check("CANONICAL_FOUNDATION_RPM",
                    make_runtime_profile_admission_manifest(foundation_rpm.semantic_payload) == foundation_rpm)
    all_ok &= check("FOUNDATION_RPM_PROFILE_KIND",
                    foundation_rpm.semantic_payload.get("profile_kind") == "foundation",
                    str(foundation_rpm.semantic_payload.get("profile_kind")))
    all_ok &= check(
        "FOUNDATION_RPM_CANDIDATE_MATCH",
        foundation_rpm.semantic_payload.get("candidate_profile") == p.get("foundation_runtime_profile"),
    )
    all_ok &= check(
        "CLASSIFICATION_RPM_FOUNDATION_ADMISSION_MATCH",
        rp.get("foundation_admission_manifest")
        == foundation_rpm.semantic_payload.get("foundation_admission_manifest"),
    )
    all_ok &= check(
        "TASK04_ACCEPTANCE_FOUNDATION_ADMISSION_MATCH",
        accepted.semantic_payload.get("foundation_admission_manifest")
        == rp.get("foundation_admission_manifest"),
    )
    all_ok &= check(
        "TASK04_ACCEPTANCE_TESTED_CRP_MATCH",
        accepted.semantic_payload.get("tested_classification_runtime_profile")
        == rp.get("candidate_profile"),
    )
    all_ok &= check(
        "TASK04_ACCEPTANCE_CLASSIFIER_MANIFEST_MATCH",
        accepted.semantic_payload.get("classifier_artifact_manifest")
        == p.get("classifier_artifact_manifest"),
    )

    for field, kind in (
        ("knowledge_bundle", "KnowledgeBundle"),
        ("classification_policy", "ClassificationPolicy"),
        ("evidence_adapter_contract_set", "EvidenceAdapterContractSet"),
        ("classifier_artifact_manifest", "ClassifierArtifactManifest"),
    ):
        load_ref(p[field], kind)

    classifier = load_ref(p["classifier_artifact_manifest"], "ClassifierArtifactManifest")
    cp = classifier.semantic_payload
    print("CLASSIFIER_MANIFEST_ID="+classifier.artifact_id)
    entries = cp.get("adapter_implementation_identities")
    print("ADAPTER_IMPLEMENTATION_IDENTITY_COUNT="+
          (str(len(entries)) if isinstance(entries,list) else "INVALID"))
    evidence = cp.get("evidence_canonical_json_compatibility_identity")
    print("EVIDENCE_CANONICAL_IDENTITY="+str(evidence))

    source_entries = []
    if isinstance(entries, list):
        source_entries.extend(entries)
    if isinstance(evidence, str) and evidence.startswith("EvidenceCanonicalJsonV1:"):
        identity, digest = evidence[len("EvidenceCanonicalJsonV1:"):].rsplit(":sha256:",1)
        source_entries.append({
            "implementation_id": identity,
            "implementation_digest": digest,
            "_kind":"evidence_canonical_json",
        })

    source_all_ok = True
    for idx, entry in enumerate(source_entries,1):
        impl_id = entry.get("implementation_id")
        expected = entry.get("implementation_digest")
        print(f"SOURCE_{idx}_IMPLEMENTATION_ID={impl_id}")
        print(f"SOURCE_{idx}_EXPECTED_SHA256={expected}")
        try:
            prefix, relative, qualified = impl_id.split(":",2)
            target = (root / relative).resolve(strict=True)
            actual = hashlib.sha256(target.read_bytes()).hexdigest()
            module = importlib.import_module(relative[:-3].replace("/","."))
            symbol = module
            for component in qualified.split("."):
                symbol = getattr(symbol, component)
            loaded_source = Path(inspect.getsourcefile(symbol)).resolve()
            path_ok = (
                prefix == "python"
                and PurePosixPath(relative).suffix == ".py"
                and str(PurePosixPath(relative)).startswith("app/")
                and target.is_relative_to(root)
            )
            origin_ok = loaded_source == target
            digest_ok = actual == expected
            print(f"SOURCE_{idx}_ACTUAL_PATH={target}")
            print(f"SOURCE_{idx}_LOADED_SOURCE={loaded_source}")
            print(f"SOURCE_{idx}_ACTUAL_SHA256={actual}")
            print(f"SOURCE_{idx}_PATH_VALID={'PASS' if path_ok else 'FAIL'}")
            print(f"SOURCE_{idx}_ORIGIN_MATCH={'PASS' if origin_ok else 'FAIL'}")
            print(f"SOURCE_{idx}_DIGEST_MATCH={'PASS' if digest_ok else 'FAIL'}")
            source_all_ok &= path_ok and origin_ok and digest_ok
        except Exception as exc:
            source_all_ok = False
            print(f"SOURCE_{idx}_CHECK_EXCEPTION={type(exc).__name__}:{exc}")
    print("EXECUTABLE_SOURCE_IDENTITY_SET="+("PASS" if source_all_ok else "FAIL"))
    all_ok &= source_all_ok

except Exception as exc:
    all_ok = False
    print("PREFLIGHT_GRAPH_EXCEPTION="+type(exc).__name__+":"+str(exc))

print("DETAILED_PREFLIGHT_STATIC_INVARIANTS="+("PASS" if all_ok else "FAIL"))
PY

section "OFFICIAL PREFLIGHT CALL"
sudo -u admin env \
  HOME=/nonexistent \
  PYTHONPATH="$PORTAL" \
  PYTHONDONTWRITEBYTECODE=1 \
  CONTROL_DB="$CONTROL_DB" \
  "$VENV_PY" -B - <<'PY'
import os
from app.device_fingerprint.control_plane_store import DeviceFingerprintControlPlaneStore
from app.device_fingerprint_integration.compatibility import ReadOnlyControlPlaneStoreMixin, preflight

class ReadOnlyControl(ReadOnlyControlPlaneStoreMixin, DeviceFingerprintControlPlaneStore):
    pass

control = ReadOnlyControl(os.environ["CONTROL_DB"])
try:
    prepared=preflight(control)
except Exception as exc:
    print("OFFICIAL_PREFLIGHT=FAIL")
    print("OFFICIAL_PREFLIGHT_EXCEPTION="+type(exc).__name__)
    print("OFFICIAL_PREFLIGHT_REASON="+str(getattr(exc,"reason_code",exc)))
else:
    print("OFFICIAL_PREFLIGHT=PASS")
    print("OFFICIAL_PREFLIGHT_PROFILE_ID="+prepared.pin.runtime_profile.artifact_id)
PY

section "TASK05 WORKER TELEMETRY FOR CONTROLLED JOB"
journalctl -u fingerprint-classification.service \
  --since "2026-10-04 01:15:00" \
  --no-pager -o cat 2>/dev/null \
  | grep -E '77dcd849-8855-4dd4-b3ed-9d2c62d86935|runtime_profile_incompatible|profile_changed_during_job' \
  | tail -n 80 || true

section "GIT SOURCE DELTA FROM ACCEPTED TASK04 BASELINE"
git -C "$PORTAL" diff --name-status fecdb5a7c79e56bb49be4797ca875d6720670042 "$TARGET_HEAD" -- app/device_fingerprint/ || true
echo "--- relevant diff stats ---"
git -C "$PORTAL" diff --stat fecdb5a7c79e56bb49be4797ca875d6720670042 "$TARGET_HEAD" -- app/device_fingerprint/ || true

section "FINAL"
echo "TASK05_RUNTIME_PROFILE_INCOMPATIBLE_FORENSIC=COMPLETE"
echo "CHANGES_MADE=NONE"
