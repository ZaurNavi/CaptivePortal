#!/usr/bin/env bash
set -Eeuo pipefail

TARGET_SHA="fecdb5a7c79e56bb49be4797ca875d6720670042"
TARGET_TREE="85d7d41e1ad19c079cad0ae819a3fe38a068e242"
WT="/home/admin/CaptivePortal-Deploy/task04-dormant-fecdb5a7"

CONTROL_DB="/opt/CaptivePortal/data/device_fingerprint_control_plane.sqlite3"
CLASS_DB="/opt/CaptivePortal/data/device_fingerprint_classification.sqlite3"
EVIDENCE_DB="/opt/CaptivePortal/data/device_fingerprint_evidence.sqlite3"

EXPECTED_CONTROL_PRE_SHA="091334a08bde5099c26c5f53252fb83d656f9c71b8ee28f4b0a03db46483ba28"
EXPECTED_CLASS_DB_SHA="f28817e529026c43808cbc75ae39641c8656da4f7aeebb579d79fe55a4018505"

CRP_ID="ClassificationRuntimeProfile:v1:sha256:1d3a563e7ce3a8afb2ff259e596328b14f5ff5ce9940db703cbb93b12c2cbf6c"
CRP_SHA="1d3a563e7ce3a8afb2ff259e596328b14f5ff5ce9940db703cbb93b12c2cbf6c"
CLASS_RPM_ID="RuntimeProfileAdmissionManifest:v1:sha256:7873028b2c3a85bf152c9bc4ea057e476591ab87d3c3a52b8cdff654beb8c98b"
CLASS_RPM_SHA="7873028b2c3a85bf152c9bc4ea057e476591ab87d3c3a52b8cdff654beb8c98b"
ACCEPTANCE_ID="Task04AcceptanceManifest:v1:sha256:ca2712fbd643b332594990e67dc95ec017507d2d4d51d61f549d357bad18ca54"
TACCEPT_GATE_ID="GateResultManifest:v1:sha256:02634373a1c0cfbade887ed68263cd3b72c6c92b8180dcab57e63067fa5d31eb"

FOUNDATION_PROFILE_ID="FoundationRuntimeProfile:v1:sha256:9287f48e01426a0440c06644821ebbbdf8f052f08d930968748f3bf6c3e9f4d5"
FOUNDATION_PROFILE_SHA="9287f48e01426a0440c06644821ebbbdf8f052f08d930968748f3bf6c3e9f4d5"
FOUNDATION_RPM_ID="RuntimeProfileAdmissionManifest:v1:sha256:95231fa3dee79b8d0b00a4f645664d3d80d3d4b1b6ca48fc4865191d24b12db6"
FOUNDATION_ACTIVATION_ID="76ec5dd6-a1a7-4107-8c4d-e1401f064e84"
TTL_ID="TTLCapturePlacementProof:v1:sha256:c48ffafa3856c4708a35e644bb4cc2b468275af9790df579a366d7ac71fc0ca2"

PREACTIVATE_REPORT="/home/admin/device-fingerprint-task04-preactivate-r2.txt"

REPORT="/home/admin/device-fingerprint-task04-production-activation-r1.txt"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
AUDIT_DIR="/home/admin/captivportal-recovery/task04-production-activation-${STAMP}"
BACKUP_DB="${AUDIT_DIR}/device_fingerprint_control_plane.pre-activation.sqlite3"
DECISION_JSON="${AUDIT_DIR}/owner-production-activation-decision.json"
ACTIVATION_JSON="${AUDIT_DIR}/classification-runtime-profile-activation-record.json"
VALIDITY_JSON="${AUDIT_DIR}/classification-runtime-profile-initial-validity-record.json"
RECEIPT_JSON="${AUDIT_DIR}/production-activation-receipt.json"

exec > >(tee "$REPORT") 2>&1

step(){ printf '\n===== %s =====\n' "$1"; }
die(){ echo "FATAL: $*" >&2; exit 1; }

on_abort() {
  rc=$?
  if [ "$rc" -ne 0 ]; then
    echo
    echo "===== ACTIVATION ABORT ====="
    echo "EXIT_CODE=$rc"
    echo "NOTE=Inspect pointer/control-plane state before any retry."
  fi
  exit "$rc"
}
trap on_abort EXIT

[ "$(id -u)" -eq 0 ] || die "Run with sudo/root."

step "OWNER AUTHORIZATION / ACTIVATION SCOPE"
date -Is
echo "OWNER_TOPOLOGY_NO_CHANGE_ASSERTION=YES"
echo "OWNER_PRODUCTION_ACTIVATION_AUTHORIZED=YES"
echo "OWNER_AUTHORIZATION_SOURCE=project_chat_immediately_before_script_generation"
echo "ACTION=INITIAL_CLASSIFICATION"
echo "TARGET_SHA=$TARGET_SHA"
echo "TARGET_TREE=$TARGET_TREE"
echo "CRP_ID=$CRP_ID"
echo "CLASS_RPM_ID=$CLASS_RPM_ID"
echo "NO_PROFILE_REBUILD=YES"
echo "NO_SERVICE_RESTART=YES"
echo "NO_CLASSIFICATION_DAEMON_START=YES"

[ -f "$CONTROL_DB" ] || die "Control-plane DB missing."
[ -f "$CLASS_DB" ] || die "Classification DB missing."
[ -f "$EVIDENCE_DB" ] || die "Evidence DB missing."
[ -f "$PREACTIVATE_REPORT" ] || die "PRE-ACTIVATE R2 report missing."
[ -e "$WT/.git" ] || die "Exact Task-04 worktree missing."

WT_HEAD="$(sudo -u admin git -C "$WT" rev-parse HEAD)"
WT_TREE="$(sudo -u admin git -C "$WT" rev-parse 'HEAD^{tree}')"
[ "$WT_HEAD" = "$TARGET_SHA" ] || die "Worktree HEAD mismatch."
[ "$WT_TREE" = "$TARGET_TREE" ] || die "Worktree tree mismatch."
[ -z "$(sudo -u admin git -C "$WT" status --porcelain=v1)" ] || die "Worktree dirty."
echo "WORKTREE_PROVENANCE=PASS"

CONTROL_PRE_SHA="$(sha256sum "$CONTROL_DB" | awk '{print $1}')"
CLASS_PRE_SHA="$(sha256sum "$CLASS_DB" | awk '{print $1}')"
PREACTIVATE_SHA="$(sha256sum "$PREACTIVATE_REPORT" | awk '{print $1}')"

echo "CONTROL_DB_SHA_PRE=$CONTROL_PRE_SHA"
echo "CLASS_DB_SHA_PRE=$CLASS_PRE_SHA"
echo "PREACTIVATE_REPORT_SHA256=$PREACTIVATE_SHA"

[ "$CONTROL_PRE_SHA" = "$EXPECTED_CONTROL_PRE_SHA" ] || die "Control-plane pre-activation SHA changed since PRE-ACTIVATE."
[ "$CLASS_PRE_SHA" = "$EXPECTED_CLASS_DB_SHA" ] || die "Classification DB SHA changed since PRE-ACTIVATE."

grep -Fq 'TASK04_PREACTIVATE_TECHNICAL_GATE=PASS' "$PREACTIVATE_REPORT" || die "PRE-ACTIVATE PASS marker absent."
grep -Fq 'CURRENT_SAFETY_COMPATIBILITY_RECHECK=PASS_HOST_AND_CONTROL_PLANE' "$PREACTIVATE_REPORT" || die "PRE-ACTIVATE safety PASS marker absent."
grep -Fq 'CLASSIFICATION_POINTER=ABSENT' "$PREACTIVATE_REPORT" || die "PRE-ACTIVATE pointer-absent marker absent."
grep -Fq 'CLASSIFICATION_DB_PRISTINE=PASS' "$PREACTIVATE_REPORT" || die "PRE-ACTIVATE pristine DB marker absent."
echo "PREACTIVATE_R2_EVIDENCE=PASS"

PORTAL_PID_BEFORE="$(systemctl show captive-portal.service -p MainPID --value)"
EVIDENCE_PID_BEFORE="$(systemctl show fingerprint-evidence.service -p MainPID --value)"
SENSOR_PID_BEFORE="$(systemctl show fingerprint-sensor.service -p MainPID --value)"
SURICATA_PID_BEFORE="$(systemctl show fingerprint-suricata.service -p MainPID --value)"

for u in captive-portal.service fingerprint-evidence.service fingerprint-sensor.service fingerprint-suricata.service; do
  systemctl is-active --quiet "$u" || die "$u is not active."
done

step "PRE-TRANSACTION EXACT PRECONDITIONS"
sudo -u admin env PYTHONPATH="$WT" \
  CONTROL_DB="$CONTROL_DB" CLASS_DB="$CLASS_DB" \
  CRP_ID="$CRP_ID" CRP_SHA="$CRP_SHA" \
  CLASS_RPM_ID="$CLASS_RPM_ID" CLASS_RPM_SHA="$CLASS_RPM_SHA" \
  ACCEPTANCE_ID="$ACCEPTANCE_ID" TACCEPT_GATE_ID="$TACCEPT_GATE_ID" \
  FOUNDATION_PROFILE_ID="$FOUNDATION_PROFILE_ID" FOUNDATION_PROFILE_SHA="$FOUNDATION_PROFILE_SHA" \
  FOUNDATION_RPM_ID="$FOUNDATION_RPM_ID" FOUNDATION_ACTIVATION_ID="$FOUNDATION_ACTIVATION_ID" \
  TTL_ID="$TTL_ID" \
  /usr/bin/python3 - <<'PY'
import os, sqlite3
from app.device_fingerprint.control_plane_store import DeviceFingerprintControlPlaneStore

store=DeviceFingerprintControlPlaneStore(os.environ["CONTROL_DB"])

conn=sqlite3.connect(f"file:{os.environ['CONTROL_DB']}?mode=ro", uri=True)
try:
    assert conn.execute("PRAGMA quick_check").fetchone()[0] == "ok"
    assert conn.execute("SELECT COUNT(*) FROM active_pointers WHERE profile_kind='classification'").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM activations WHERE profile_kind='classification'").fetchone()[0] == 0
finally:
    conn.close()

foundation=store.pin_active_profile("foundation")
assert foundation.pointer.runtime_profile_id == os.environ["FOUNDATION_PROFILE_ID"]
assert foundation.pointer.runtime_profile_digest == os.environ["FOUNDATION_PROFILE_SHA"]
assert foundation.pointer.activation_record_id == os.environ["FOUNDATION_ACTIVATION_ID"]
assert foundation.admission_manifest.artifact_id == os.environ["FOUNDATION_RPM_ID"]
assert foundation.validity_record.semantic_payload["state"] == "ACTIVE"

rpm=store.load_artifact(os.environ["CLASS_RPM_ID"], os.environ["CLASS_RPM_SHA"])
crp=store.load_artifact(os.environ["CRP_ID"], os.environ["CRP_SHA"])
acceptance=store.load_artifact(os.environ["ACCEPTANCE_ID"])
taccept=store.load_artifact(os.environ["TACCEPT_GATE_ID"])
ttl=store.load_artifact(os.environ["TTL_ID"])

rp=rpm.semantic_payload
assert rp["profile_kind"] == "classification"
assert rp["update_class"] == "INITIAL_CLASSIFICATION"
assert rp["compatibility_validation_result"] == "PASS"
assert rp["candidate_profile"] == {
    "artifact_id": os.environ["CRP_ID"],
    "content_sha256": os.environ["CRP_SHA"],
}
assert rp["previous_active_profile"] is None
assert rp["expected_previous_activation_record_id"] is None
assert rp["expected_previous_activation_generation_id"] is None
assert rp["task04_acceptance_manifest"]["artifact_id"] == acceptance.artifact_id
assert rp["foundation_runtime_profile_admission_manifest"]["artifact_id"] == os.environ["FOUNDATION_RPM_ID"]
assert crp.semantic_payload["foundation_runtime_profile"] == {
    "artifact_id": os.environ["FOUNDATION_PROFILE_ID"],
    "content_sha256": os.environ["FOUNDATION_PROFILE_SHA"],
}
assert taccept.semantic_payload["gate_id"] == "T-ACCEPT"
assert taccept.semantic_payload["status"] == "PASS"
assert ttl.semantic_payload["capture_distance_l3_hops"] == 0
assert ttl.semantic_payload["capture_topology_descriptor"]["mirror_position_relative_to_first_l3"] == "BEFORE_FIRST_L3"
assert store.get_active_pointer("classification") is None

with store._connect() as c:
    store._closure(c, crp)
    store._closure(c, rpm)

c=sqlite3.connect(f"file:{os.environ['CLASS_DB']}?mode=ro", uri=True)
try:
    assert c.execute("PRAGMA quick_check").fetchone()[0] == "ok"
    counts={t:c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            for t in ("artifacts","artifact_dependencies","classifications","classification_roots")}
    assert counts == {"artifacts":0,"artifact_dependencies":0,"classifications":0,"classification_roots":0}, counts
finally:
    c.close()

print("PRECONDITION_CONTROL_PLANE=PASS")
print("PRECONDITION_FOUNDATION_PIN=PASS")
print("PRECONDITION_TACCEPT=PASS")
print("PRECONDITION_CLASSIFICATION_RPM=PASS")
print("PRECONDITION_INITIAL_PREDECESSOR_ABSENT=PASS")
print("PRECONDITION_TTL_TOPOLOGY=PASS")
print("PRECONDITION_CLASSIFICATION_DB_PRISTINE=PASS")
PY

step "CREATE PRE-ACTIVATION RECOVERY SNAPSHOT"
install -d -o admin -g admin "$AUDIT_DIR"
CONTROL_DB="$CONTROL_DB" BACKUP_DB="$BACKUP_DB" /usr/bin/python3 - <<'PY'
import os, sqlite3
src=sqlite3.connect(f"file:{os.environ['CONTROL_DB']}?mode=ro", uri=True)
dst=sqlite3.connect(os.environ["BACKUP_DB"])
try:
    src.backup(dst)
    dst.commit()
finally:
    dst.close()
    src.close()
PY
chown admin:admin "$BACKUP_DB"
chmod 0640 "$BACKUP_DB"
BACKUP_QUICK="$(python3 - "$BACKUP_DB" <<'PY'
import sqlite3,sys
c=sqlite3.connect(f"file:{sys.argv[1]}?mode=ro", uri=True)
try: print(c.execute("PRAGMA quick_check").fetchone()[0])
finally: c.close()
PY
)"
[ "$BACKUP_QUICK" = "ok" ] || die "Recovery snapshot quick_check failed."
BACKUP_SHA="$(sha256sum "$BACKUP_DB" | awk '{print $1}')"
echo "PREACTIVATION_BACKUP_DB=$BACKUP_DB"
echo "PREACTIVATION_BACKUP_SHA256=$BACKUP_SHA"
echo "PREACTIVATION_BACKUP_QUICK_CHECK=PASS"

step "PRECOMPUTE OWNER DECISION + ACTIVATION ARTIFACTS AND COMMIT"
sudo -u admin env PYTHONPATH="$WT" \
  CONTROL_DB="$CONTROL_DB" \
  CRP_ID="$CRP_ID" CRP_SHA="$CRP_SHA" \
  CLASS_RPM_ID="$CLASS_RPM_ID" CLASS_RPM_SHA="$CLASS_RPM_SHA" \
  ACCEPTANCE_ID="$ACCEPTANCE_ID" TACCEPT_GATE_ID="$TACCEPT_GATE_ID" \
  FOUNDATION_PROFILE_ID="$FOUNDATION_PROFILE_ID" FOUNDATION_RPM_ID="$FOUNDATION_RPM_ID" \
  TTL_ID="$TTL_ID" PREACTIVATE_SHA="$PREACTIVATE_SHA" \
  DECISION_JSON="$DECISION_JSON" ACTIVATION_JSON="$ACTIVATION_JSON" VALIDITY_JSON="$VALIDITY_JSON" \
  /usr/bin/python3 - <<'PY'
import hashlib
import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.device_fingerprint.artifact_content import canonical_artifact_json
from app.device_fingerprint.control_plane_store import DeviceFingerprintControlPlaneStore
from app.device_fingerprint.runtime_profile_artifacts import (
    make_runtime_profile_activation_record,
    make_runtime_profile_validity_record,
)

def utc_ms(dt):
    return dt.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00","Z")

def fsync_json(path: Path, obj):
    raw=(json.dumps(obj, ensure_ascii=True, sort_keys=True, indent=2) + "\n").encode("utf-8")
    with path.open("xb") as f:
        f.write(raw)
        f.flush()
        os.fsync(f.fileno())

def envelope(content):
    return {
        "artifact_type": content.artifact_type,
        "artifact_schema_version": content.artifact_schema_version,
        "semantic_payload": content.semantic_payload,
        "content_sha256": content.content_sha256,
        "artifact_id": content.artifact_id,
    }

store=DeviceFingerprintControlPlaneStore(os.environ["CONTROL_DB"])
rpm=store.load_artifact(os.environ["CLASS_RPM_ID"], os.environ["CLASS_RPM_SHA"])
crp=store.load_artifact(os.environ["CRP_ID"], os.environ["CRP_SHA"])

# Capture exact Foundation pointer before classification activation.
foundation_before=store.get_active_pointer("foundation")
assert foundation_before is not None

# UUIDs are precomputed before the transaction; all are canonical UUIDv4.
activation_id=str(uuid.uuid4())
generation_id=str(uuid.uuid4())
validity_id=str(uuid.uuid4())

decision_time=datetime.now(timezone.utc)
activation_time=decision_time + timedelta(milliseconds=1)
decided_at=utc_ms(decision_time)
activated_at=utc_ms(activation_time)

activation=make_runtime_profile_activation_record({
    "activation_contract_version": 1,
    "activation_record_id": activation_id,
    "profile_kind": "classification",
    "runtime_profile_id": crp.artifact_id,
    "runtime_profile_digest": crp.content_sha256,
    "runtime_profile_admission_manifest_id": rpm.artifact_id,
    "runtime_profile_admission_manifest_digest": rpm.content_sha256,
    "previous_activation_record_id": None,
    "previous_active_profile_id": None,
    "previous_active_profile_digest": None,
    "activated_at_utc": activated_at,
    "activation_reason_update_class": "INITIAL_CLASSIFICATION",
    "activation_result": "ACTIVE",
    "activation_generation_id": generation_id,
})
validity=make_runtime_profile_validity_record({
    "runtime_profile_validity_contract_version": 1,
    "validity_record_id": validity_id,
    "profile_kind": "classification",
    "runtime_profile_id": crp.artifact_id,
    "runtime_profile_digest": crp.content_sha256,
    "activation_record_id": activation_id,
    "state": "ACTIVE",
    "reason_code": "ACTIVATED",
    "effective_at_utc": activated_at,
    "inflight_commit_rule": "ALLOW_PINNED_INFLIGHT",
    "previous_validity_record_id": None,
})

# Owner DecisionRecord is audit association, not embedded in semantic runtime content.
referenced_artifacts=sorted({
    os.environ["CRP_ID"],
    os.environ["CLASS_RPM_ID"],
    os.environ["ACCEPTANCE_ID"],
    os.environ["TACCEPT_GATE_ID"],
    os.environ["FOUNDATION_PROFILE_ID"],
    os.environ["FOUNDATION_RPM_ID"],
    os.environ["TTL_ID"],
    activation.artifact_id,
    validity.artifact_id,
})
reason=(
    "Owner explicitly confirmed no change to the accepted Catalyst SPAN/RSPAN, Guest VLAN 20, "
    "mirror destination, AP observation path, Cisco 3845 first-L3 placement, or pre-router "
    "BEFORE_FIRST_L3 topology, and explicitly authorized Task-04 production activation. "
    "Read-only PRE-ACTIVATE R2 technical gate PASS report SHA-256="
    + os.environ["PREACTIVATE_SHA"]
)
unsigned={
    "decision_record_id": str(uuid.uuid4()),
    "decision_subject_type": "TASK04_PRODUCTION_ACTIVATION",
    "decision_subject_id": os.environ["CRP_ID"],
    "decision": "ACCEPT",
    "decided_at_utc": decided_at,
    "actor_role": "OWNER",
    "referenced_artifact_ids": referenced_artifacts,
    "referenced_gate_ids": ["T-ACCEPT"],
    "reason_reference_text": reason,
}
decision={**unsigned, "record_sha256": hashlib.sha256(canonical_artifact_json(unsigned)).hexdigest()}

# Persist audit decision and exact precomputed artifacts BEFORE the activation transaction.
fsync_json(Path(os.environ["DECISION_JSON"]), decision)
fsync_json(Path(os.environ["ACTIVATION_JSON"]), envelope(activation))
fsync_json(Path(os.environ["VALIDITY_JSON"]), envelope(validity))

# Recheck the INITIAL_CLASSIFICATION predecessor immediately before BEGIN.
assert store.get_active_pointer("classification") is None

pointer=store.activate_profile(
    rpm,
    activation,
    validity,
    predecessor_inactive_validity_record=None,
)

# Exact post-commit verification.
assert pointer.profile_kind == "classification"
assert pointer.runtime_profile_id == crp.artifact_id
assert pointer.runtime_profile_digest == crp.content_sha256
assert pointer.activation_record_id == activation_id
assert pointer.activation_generation_id == generation_id
assert pointer.updated_at_utc == activated_at

pinned=store.pin_active_profile("classification")
assert pinned.pointer == pointer
assert pinned.runtime_profile == crp
assert pinned.admission_manifest == rpm
assert pinned.activation_record == activation
assert pinned.validity_record == validity
assert pinned.validity_record.semantic_payload["state"] == "ACTIVE"
assert pinned.validity_record.semantic_payload["reason_code"] == "ACTIVATED"
assert pinned.validity_record.semantic_payload["inflight_commit_rule"] == "ALLOW_PINNED_INFLIGHT"

head=store.get_validity_head(activation_id)
assert head == validity

foundation_after=store.get_active_pointer("foundation")
assert foundation_after == foundation_before

print(f"OWNER_DECISION_RECORD_ID={decision['decision_record_id']}")
print(f"OWNER_DECISION_RECORD_SHA256={decision['record_sha256']}")
print(f"OWNER_DECISION_FILE={os.environ['DECISION_JSON']}")
print(f"ACTIVATION_ARTIFACT_ID={activation.artifact_id}")
print(f"ACTIVATION_RECORD_ID={activation_id}")
print(f"ACTIVATION_GENERATION_ID={generation_id}")
print(f"VALIDITY_ARTIFACT_ID={validity.artifact_id}")
print(f"VALIDITY_RECORD_ID={validity_id}")
print(f"ACTIVATED_AT_UTC={activated_at}")
print("ATOMIC_ACTIVATE_PROFILE=PASS")
print("CLASSIFICATION_POINTER_POSTCOMMIT=PASS")
print("CLASSIFICATION_PIN_POSTCOMMIT=PASS")
print("CLASSIFICATION_VALIDITY_HEAD_POSTCOMMIT=PASS")
print("FOUNDATION_POINTER_UNCHANGED=PASS")
PY

step "POST-COMMIT SQLITE / RUNTIME VERIFICATION"
sudo -u admin env PYTHONPATH="$WT" \
  CONTROL_DB="$CONTROL_DB" CLASS_DB="$CLASS_DB" \
  CRP_ID="$CRP_ID" CRP_SHA="$CRP_SHA" \
  CLASS_RPM_ID="$CLASS_RPM_ID" CLASS_RPM_SHA="$CLASS_RPM_SHA" \
  FOUNDATION_PROFILE_ID="$FOUNDATION_PROFILE_ID" FOUNDATION_PROFILE_SHA="$FOUNDATION_PROFILE_SHA" \
  FOUNDATION_ACTIVATION_ID="$FOUNDATION_ACTIVATION_ID" \
  /usr/bin/python3 - <<'PY'
import os, sqlite3
from app.device_fingerprint.control_plane_store import DeviceFingerprintControlPlaneStore

db=os.environ["CONTROL_DB"]
conn=sqlite3.connect(f"file:{db}?mode=ro", uri=True)
conn.row_factory=sqlite3.Row
try:
    assert conn.execute("PRAGMA quick_check").fetchone()[0] == "ok"
    rows=conn.execute("SELECT * FROM active_pointers ORDER BY profile_kind").fetchall()
    assert len(rows)==2, [dict(r) for r in rows]
    kinds={r["profile_kind"] for r in rows}
    assert kinds=={"foundation","classification"}, kinds
    assert conn.execute("SELECT COUNT(*) FROM activations WHERE profile_kind='classification'").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM validity_heads h JOIN activations a "
                        "ON a.activation_record_id=h.activation_record_id "
                        "WHERE a.profile_kind='classification'").fetchone()[0] == 1
finally:
    conn.close()

store=DeviceFingerprintControlPlaneStore(db)
fp=store.pin_active_profile("foundation")
cp=store.pin_active_profile("classification")
assert fp.pointer.runtime_profile_id == os.environ["FOUNDATION_PROFILE_ID"]
assert fp.pointer.runtime_profile_digest == os.environ["FOUNDATION_PROFILE_SHA"]
assert fp.pointer.activation_record_id == os.environ["FOUNDATION_ACTIVATION_ID"]
assert cp.pointer.runtime_profile_id == os.environ["CRP_ID"]
assert cp.pointer.runtime_profile_digest == os.environ["CRP_SHA"]
assert cp.admission_manifest.artifact_id == os.environ["CLASS_RPM_ID"]
assert cp.admission_manifest.content_sha256 == os.environ["CLASS_RPM_SHA"]
assert cp.validity_record.semantic_payload["state"] == "ACTIVE"

# Activation alone must not fabricate derived classifications.
c=sqlite3.connect(f"file:{os.environ['CLASS_DB']}?mode=ro", uri=True)
try:
    assert c.execute("PRAGMA quick_check").fetchone()[0] == "ok"
    counts={t:c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            for t in ("artifacts","artifact_dependencies","classifications","classification_roots")}
    assert counts == {"artifacts":0,"artifact_dependencies":0,"classifications":0,"classification_roots":0}, counts
finally:
    c.close()

print("POST_CONTROL_QUICK_CHECK=PASS")
print("ACTIVE_POINTER_COUNT=2")
print("FOUNDATION_POINTER=ACTIVE_EXACT")
print("CLASSIFICATION_POINTER=ACTIVE_EXACT")
print("CLASSIFICATION_ACTIVATION_ROWS=1")
print("CLASSIFICATION_VALIDITY_HEAD=ACTIVE")
print("CLASSIFICATION_DB_STILL_EMPTY=PASS")
PY

step "SERVICE IMMUTABILITY / LIVE FOUNDATION HEALTH"
PORTAL_PID_AFTER="$(systemctl show captive-portal.service -p MainPID --value)"
EVIDENCE_PID_AFTER="$(systemctl show fingerprint-evidence.service -p MainPID --value)"
SENSOR_PID_AFTER="$(systemctl show fingerprint-sensor.service -p MainPID --value)"
SURICATA_PID_AFTER="$(systemctl show fingerprint-suricata.service -p MainPID --value)"

[ "$PORTAL_PID_BEFORE" = "$PORTAL_PID_AFTER" ] || die "Portal restarted unexpectedly."
[ "$EVIDENCE_PID_BEFORE" = "$EVIDENCE_PID_AFTER" ] || die "Evidence restarted unexpectedly."
[ "$SENSOR_PID_BEFORE" = "$SENSOR_PID_AFTER" ] || die "Sensor restarted unexpectedly."
[ "$SURICATA_PID_BEFORE" = "$SURICATA_PID_AFTER" ] || die "Suricata restarted unexpectedly."

for u in captive-portal.service fingerprint-evidence.service fingerprint-sensor.service fingerprint-suricata.service; do
  systemctl is-active --quiet "$u" || die "$u not active after activation."
  systemctl show "$u" -p ActiveState -p SubState -p MainPID -p NRestarts --no-pager
done
echo "SERVICE_PIDS_UNCHANGED=PASS"

LATEST_SENSOR="$(journalctl -u fingerprint-sensor.service -n 600 --no-pager | grep '"event":"fingerprint_sensor_metrics"' | tail -n 1 || true)"
[ -n "$LATEST_SENSOR" ] || die "No sensor metrics after activation."
echo "$LATEST_SENSOR"
LATEST_SENSOR="$LATEST_SENSOR" /usr/bin/python3 - <<'PY'
import json,os
line=os.environ["LATEST_SENSOR"]
obj=json.loads(line[line.index("{"):])
assert obj["runtime_state"]=="ready", obj
assert obj["suricata_process_active"] is True, obj
assert obj["oldest_spool_age"]==0, obj
print("FOUNDATION_LIVE_SENSOR_HEALTH=PASS")
PY

if journalctl -u fingerprint-evidence.service --since "10 minutes ago" --no-pager \
   | grep -Fq '"error_category":"concurrency_limit"'; then
  die "Recent evidence concurrency_limit observed."
fi
echo "FOUNDATION_LIVE_EVIDENCE_HEALTH=PASS"

step "WRITE ACTIVATION RECEIPT"
CONTROL_POST_SHA="$(sha256sum "$CONTROL_DB" | awk '{print $1}')"
CLASS_POST_SHA="$(sha256sum "$CLASS_DB" | awk '{print $1}')"
DECISION_FILE_SHA="$(sha256sum "$DECISION_JSON" | awk '{print $1}')"
ACTIVATION_FILE_SHA="$(sha256sum "$ACTIVATION_JSON" | awk '{print $1}')"
VALIDITY_FILE_SHA="$(sha256sum "$VALIDITY_JSON" | awk '{print $1}')"

sudo -u admin env PYTHONPATH="$WT" \
  CONTROL_DB="$CONTROL_DB" CLASS_DB="$CLASS_DB" \
  CONTROL_PRE_SHA="$CONTROL_PRE_SHA" CONTROL_POST_SHA="$CONTROL_POST_SHA" \
  CLASS_PRE_SHA="$CLASS_PRE_SHA" CLASS_POST_SHA="$CLASS_POST_SHA" \
  PREACTIVATE_SHA="$PREACTIVATE_SHA" BACKUP_DB="$BACKUP_DB" BACKUP_SHA="$BACKUP_SHA" \
  DECISION_JSON="$DECISION_JSON" DECISION_FILE_SHA="$DECISION_FILE_SHA" \
  ACTIVATION_JSON="$ACTIVATION_JSON" ACTIVATION_FILE_SHA="$ACTIVATION_FILE_SHA" \
  VALIDITY_JSON="$VALIDITY_JSON" VALIDITY_FILE_SHA="$VALIDITY_FILE_SHA" \
  RECEIPT_JSON="$RECEIPT_JSON" \
  TARGET_SHA="$TARGET_SHA" TARGET_TREE="$TARGET_TREE" \
  /usr/bin/python3 - <<'PY'
import json,os,sqlite3
from datetime import datetime,timezone
from pathlib import Path
from app.device_fingerprint.control_plane_store import DeviceFingerprintControlPlaneStore

store=DeviceFingerprintControlPlaneStore(os.environ["CONTROL_DB"])
cp=store.pin_active_profile("classification")
fp=store.pin_active_profile("foundation")
decision=json.loads(Path(os.environ["DECISION_JSON"]).read_text(encoding="utf-8"))
activation=json.loads(Path(os.environ["ACTIVATION_JSON"]).read_text(encoding="utf-8"))
validity=json.loads(Path(os.environ["VALIDITY_JSON"]).read_text(encoding="utf-8"))

receipt={
  "receipt_version":1,
  "status":"PASS",
  "action":"INITIAL_CLASSIFICATION",
  "recorded_at_utc":datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00","Z"),
  "target_commit":os.environ["TARGET_SHA"],
  "target_tree":os.environ["TARGET_TREE"],
  "owner_decision_record_id":decision["decision_record_id"],
  "owner_decision_record_sha256":decision["record_sha256"],
  "owner_decision_file_sha256":os.environ["DECISION_FILE_SHA"],
  "classification_runtime_profile_id":cp.runtime_profile.artifact_id,
  "classification_runtime_profile_digest":cp.runtime_profile.content_sha256,
  "classification_rpm_id":cp.admission_manifest.artifact_id,
  "classification_rpm_digest":cp.admission_manifest.content_sha256,
  "activation_artifact_id":cp.activation_record.artifact_id,
  "activation_record_id":cp.pointer.activation_record_id,
  "activation_generation_id":cp.pointer.activation_generation_id,
  "validity_artifact_id":cp.validity_record.artifact_id,
  "validity_record_id":cp.validity_record.semantic_payload["validity_record_id"],
  "validity_state":cp.validity_record.semantic_payload["state"],
  "foundation_runtime_profile_id":fp.runtime_profile.artifact_id,
  "foundation_activation_record_id":fp.pointer.activation_record_id,
  "control_db_sha256_before":os.environ["CONTROL_PRE_SHA"],
  "control_db_sha256_after":os.environ["CONTROL_POST_SHA"],
  "classification_db_sha256_before":os.environ["CLASS_PRE_SHA"],
  "classification_db_sha256_after":os.environ["CLASS_POST_SHA"],
  "preactivate_report_sha256":os.environ["PREACTIVATE_SHA"],
  "preactivation_backup_db":os.environ["BACKUP_DB"],
  "preactivation_backup_sha256":os.environ["BACKUP_SHA"],
  "activation_artifact_file_sha256":os.environ["ACTIVATION_FILE_SHA"],
  "validity_artifact_file_sha256":os.environ["VALIDITY_FILE_SHA"],
  "classification_db_rows_after":0,
  "autonomous_classification_process_started":False,
}
raw=(json.dumps(receipt,ensure_ascii=True,sort_keys=True,indent=2)+"\n").encode("utf-8")
p=Path(os.environ["RECEIPT_JSON"])
with p.open("xb") as f:
    f.write(raw); f.flush(); os.fsync(f.fileno())
print("ACTIVATION_RECEIPT_WRITE=PASS")
PY

RECEIPT_SHA="$(sha256sum "$RECEIPT_JSON" | awk '{print $1}')"
chown -R admin:admin "$AUDIT_DIR"

step "FINAL"
echo "TASK04_PRODUCTION_ACTIVATION=PASS"
echo "OWNER_PRODUCTION_ACTIVATION_DECISION=ACCEPT"
echo "OWNER_TOPOLOGY_NO_CHANGE_ASSERTION=YES"
echo "CLASSIFICATION_PROFILE_ACTIVE=YES"
echo "CLASSIFICATION_POINTER=ACTIVE_EXACT"
echo "CLASSIFICATION_ACTIVATION_ROWS=1"
echo "CLASSIFICATION_VALIDITY=ACTIVE"
echo "FOUNDATION_POINTER_UNCHANGED=PASS"
echo "CLASSIFICATION_DB_ROWS=0"
echo "AUTONOMOUS_CLASSIFICATION_PROCESS_STARTED=NO"
echo "SERVICES_RESTARTED=NO"
echo "CONTROL_DB_SHA_BEFORE=$CONTROL_PRE_SHA"
echo "CONTROL_DB_SHA_AFTER=$CONTROL_POST_SHA"
echo "CLASS_DB_SHA_BEFORE=$CLASS_PRE_SHA"
echo "CLASS_DB_SHA_AFTER=$CLASS_POST_SHA"
echo "OWNER_DECISION_JSON=$DECISION_JSON"
echo "ACTIVATION_JSON=$ACTIVATION_JSON"
echo "VALIDITY_JSON=$VALIDITY_JSON"
echo "ACTIVATION_RECEIPT=$RECEIPT_JSON"
echo "ACTIVATION_RECEIPT_SHA256=$RECEIPT_SHA"
echo "PREACTIVATION_BACKUP=$BACKUP_DB"
echo "REPORT=$REPORT"

trap - EXIT
