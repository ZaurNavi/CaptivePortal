#!/usr/bin/env bash
set -Eeuo pipefail

WT="/home/admin/CaptivePortal-Deploy/task04-dormant-fecdb5a7"
CONTROL_DB="/opt/CaptivePortal/data/device_fingerprint_control_plane.sqlite3"
CLASS_DB="/opt/CaptivePortal/data/device_fingerprint_classification.sqlite3"

SITE_ID="6a64f17630da7c70d232187a"
MAC="4C:D3:AF:3C:F2:8F"
CLASSIFICATION_ID="7b25ed80-6794-472e-bf69-a505ab73b997"
RESULT_ID="ClassificationResult:v1:sha256:491df258f5987d27f1e17d8cf39a59417e402edaec6215ed03f03bfc0905e25a"
CRP_ID="ClassificationRuntimeProfile:v1:sha256:1d3a563e7ce3a8afb2ff259e596328b14f5ff5ce9940db703cbb93b12c2cbf6c"
FOUNDATION_ID="FoundationRuntimeProfile:v1:sha256:9287f48e01426a0440c06644821ebbbdf8f052f08d930968748f3bf6c3e9f4d5"
ACTIVATION_ID="c9600739-38c6-4186-b67d-91ada854376f"

AUDIT_DIR="/home/admin/captivportal-recovery/task04-first-production-classification-20261003T160812Z"
RECEIPT="$AUDIT_DIR/first-production-classification-receipt.json"
PRECOMMIT="$AUDIT_DIR/precommit-assembly.json"
BACKUP="$AUDIT_DIR/device_fingerprint_classification.pre-first-production.sqlite3"

REPORT="/home/admin/device-fingerprint-task04-production-closeout-r1.txt"

exec > >(tee "$REPORT") 2>&1

die(){ echo "FATAL: $*" >&2; exit 1; }
step(){ printf '\n===== %s =====\n' "$1"; }

[ "$(id -u)" -eq 0 ] || die "Run with sudo/root."
for p in "$WT" "$CONTROL_DB" "$CLASS_DB" "$AUDIT_DIR" "$RECEIPT" "$PRECOMMIT" "$BACKUP"; do
  [ -e "$p" ] || die "Missing $p"
done

CONTROL_BEFORE="$(sha256sum "$CONTROL_DB" | awk '{print $1}')"
CLASS_BEFORE="$(sha256sum "$CLASS_DB" | awk '{print $1}')"

step "DECLARATION"
date -Is
echo "MODE=READ_ONLY_TASK04_PRODUCTION_CLOSEOUT"
echo "CLASSIFICATION_WRITE=NO"
echo "ACTIVATION_WRITE=NO"
echo "SERVICE_RESTART=NO"

step "READ API + AUDIT CLOSURE"
sudo -u admin env \
  PYTHONPATH="$WT" \
  CONTROL_DB="$CONTROL_DB" CLASS_DB="$CLASS_DB" \
  SITE_ID="$SITE_ID" MAC="$MAC" CLASSIFICATION_ID="$CLASSIFICATION_ID" \
  RESULT_ID="$RESULT_ID" CRP_ID="$CRP_ID" FOUNDATION_ID="$FOUNDATION_ID" \
  ACTIVATION_ID="$ACTIVATION_ID" RECEIPT="$RECEIPT" PRECOMMIT="$PRECOMMIT" BACKUP="$BACKUP" \
  /usr/bin/python3 - <<'PY'
import json, os, sqlite3
from pathlib import Path
from app.device_fingerprint.classification_read import DeviceFingerprintClassificationReadService
from app.device_fingerprint.control_plane_store import DeviceFingerprintControlPlaneStore

class Fail(RuntimeError): pass
def req(v, code):
    if not v: raise Fail(code)

class_db=Path(os.environ["CLASS_DB"])
control_db=Path(os.environ["CONTROL_DB"])
site=os.environ["SITE_ID"]
mac=os.environ["MAC"]
cid=os.environ["CLASSIFICATION_ID"]
rid=os.environ["RESULT_ID"]
crp=os.environ["CRP_ID"]
foundation=os.environ["FOUNDATION_ID"]
activation=os.environ["ACTIVATION_ID"]

c=sqlite3.connect(f"{class_db.resolve().as_uri()}?mode=ro", uri=True)
try:
    req(c.execute("PRAGMA quick_check").fetchone()[0]=="ok", "CLASS_DB_QUICK_CHECK")
    rows=c.execute("SELECT COUNT(*) FROM classifications").fetchone()[0]
    req(rows==1, f"CLASSIFICATION_ROW_COUNT:{rows}")
    core=c.execute(
        "SELECT classification_id,site_id,observed_mac,execution_context,"
        "classification_runtime_profile_id,foundation_runtime_profile_id,"
        "runtime_profile_activation_record_id,classification_result_id "
        "FROM classifications"
    ).fetchone()
    req(core is not None, "CORE_MISSING")
    req(core[0]==cid and core[1]==site and core[2]==mac, "CORE_DEVICE_BINDING")
    req(core[3]=="PRODUCTION", "CORE_EXECUTION_CONTEXT")
    req(core[4]==crp, "CORE_CRP")
    req(core[5]==foundation, "CORE_FOUNDATION")
    req(core[6]==activation, "CORE_ACTIVATION")
    req(core[7]==rid, "CORE_RESULT")
    artifact_rows=c.execute("SELECT COUNT(*) FROM artifacts").fetchone()[0]
    dependency_rows=c.execute("SELECT COUNT(*) FROM artifact_dependencies").fetchone()[0]
    root_rows=c.execute(
        "SELECT COUNT(*) FROM classification_roots WHERE classification_id=?", (cid,)
    ).fetchone()[0]
    req(artifact_rows>0 and dependency_rows>0 and root_rows>0, "AUDIT_CLOSURE_EMPTY")
finally:
    c.close()

read=DeviceFingerprintClassificationReadService(class_db)
current=read.get_current(site, mac)
req(current is not None, "GET_CURRENT_NONE")
req(current.core.classification_id==cid, "GET_CURRENT_ID")
req(current.result.artifact_id==rid, "GET_CURRENT_RESULT")

history=read.list_history(
    site, mac,
    "2026-10-03T00:00:00.000Z",
    "2026-10-04T00:00:00.000Z",
    limit=10,
)
req(len(history.items)==1, f"HISTORY_COUNT:{len(history.items)}")
req(history.items[0].core.classification_id==cid, "HISTORY_ID")
req(history.items[0].result.artifact_id==rid, "HISTORY_RESULT")
req(history.next_cursor is None, "HISTORY_UNEXPECTED_CURSOR")

control=DeviceFingerprintControlPlaneStore(control_db)
p=control.pin_active_profile("classification")
req(p.runtime_profile.artifact_id==crp, "ACTIVE_CRP_CHANGED")
req(p.pointer.activation_record_id==activation, "ACTIVE_ACTIVATION_CHANGED")
req(p.validity_record.semantic_payload["state"]=="ACTIVE", "ACTIVE_VALIDITY_CHANGED")

receipt=json.loads(Path(os.environ["RECEIPT"]).read_text(encoding="utf-8"))
req(receipt.get("status")=="PASS", "RECEIPT_STATUS")
req(receipt.get("action")=="FIRST_PRODUCTION_CLASSIFICATION", "RECEIPT_ACTION")
req(receipt.get("classification_id")==cid, "RECEIPT_CLASSIFICATION_ID")
req(receipt.get("result_artifact",{}).get("artifact_id")==rid, "RECEIPT_RESULT")
req(receipt.get("get_current")=="PASS", "RECEIPT_GET_CURRENT")
req(receipt.get("level_b_replay")=="PASS", "RECEIPT_REPLAY")
req(receipt.get("classification_rows_before")==0, "RECEIPT_ROWS_BEFORE")
req(receipt.get("classification_rows_after")==1, "RECEIPT_ROWS_AFTER")

pre=json.loads(Path(os.environ["PRECOMMIT"]).read_text(encoding="utf-8"))
req(pre.get("status")=="PRECOMMIT_READY", "PRECOMMIT_STATUS")
req(pre.get("site_id")==site and pre.get("observed_mac")==mac, "PRECOMMIT_DEVICE")
req(pre.get("classification_result",{}).get("artifact_id")==rid, "PRECOMMIT_RESULT")

b=sqlite3.connect(f"{Path(os.environ['BACKUP']).resolve().as_uri()}?mode=ro", uri=True)
try:
    req(b.execute("PRAGMA quick_check").fetchone()[0]=="ok", "BACKUP_QUICK_CHECK")
    old=b.execute("SELECT COUNT(*) FROM classifications").fetchone()[0]
    req(old==0, f"BACKUP_NOT_PRISTINE:{old}")
finally:
    b.close()

print("CLASSIFICATION_DB_QUICK_CHECK=PASS")
print("CLASSIFICATION_ROWS=1")
print(f"CLASSIFICATION_ID={cid}")
print(f"CLASSIFICATION_RESULT_ID={rid}")
print("CORE_PRODUCTION_LINEAGE=PASS")
print(f"AUDIT_ARTIFACT_ROWS={artifact_rows}")
print(f"AUDIT_DEPENDENCY_ROWS={dependency_rows}")
print(f"CLASSIFICATION_ROOT_ROWS={root_rows}")
print("GET_CURRENT=PASS")
print("LIST_HISTORY=PASS")
print("HISTORY_ITEMS=1")
print("ACTIVE_CLASSIFICATION_PROFILE=UNCHANGED_EXACT")
print("ACTIVE_CLASSIFICATION_VALIDITY=ACTIVE")
print("FIRST_PRODUCTION_RECEIPT=PASS")
print("PRECOMMIT_AUDIT=PASS")
print("PRE_FIRST_PRODUCTION_BACKUP_PRISTINE=PASS")
PY

step "RUNTIME HEALTH"
for u in captive-portal.service fingerprint-evidence.service fingerprint-sensor.service fingerprint-suricata.service; do
  systemctl is-active --quiet "$u" || die "$u not active"
  systemctl show "$u" -p MainPID -p NRestarts -p ActiveState -p SubState --no-pager
done
echo "SERVICES_ACTIVE=PASS"

LATEST_SENSOR="$(journalctl -u fingerprint-sensor.service -n 800 --no-pager | grep '"event":"fingerprint_sensor_metrics"' | tail -n1 || true)"
[ -n "$LATEST_SENSOR" ] || die "No current sensor metrics"
echo "$LATEST_SENSOR"
LATEST_SENSOR="$LATEST_SENSOR" /usr/bin/python3 - <<'PY'
import json, os
s=os.environ["LATEST_SENSOR"]
o=json.loads(s[s.index("{"):])
assert o["runtime_state"]=="ready", o
assert o["suricata_process_active"] is True, o
assert o["oldest_spool_age"]==0, o
assert o["eve_json_invalid"]==0, o
assert o["eve_datagram_truncated"]==0, o
print("SENSOR_RUNTIME_HEALTH=PASS")
PY

step "READ-ONLY IMMUTABILITY"
CONTROL_AFTER="$(sha256sum "$CONTROL_DB" | awk '{print $1}')"
CLASS_AFTER="$(sha256sum "$CLASS_DB" | awk '{print $1}')"
[ "$CONTROL_BEFORE" = "$CONTROL_AFTER" ] || die "Control DB changed during closeout"
[ "$CLASS_BEFORE" = "$CLASS_AFTER" ] || die "Classification DB changed during closeout"
echo "CONTROL_DB_UNCHANGED=PASS"
echo "CLASSIFICATION_DB_UNCHANGED=PASS"
echo "RECEIPT_SHA256=$(sha256sum "$RECEIPT" | awk '{print $1}')"
echo "PRECOMMIT_SHA256=$(sha256sum "$PRECOMMIT" | awk '{print $1}')"
echo "BACKUP_SHA256=$(sha256sum "$BACKUP" | awk '{print $1}')"

step "FINAL"
echo "TASK04_PRODUCTION_CLOSEOUT=PASS"
echo "TASK04_IMPLEMENTATION=ACCEPTED"
echo "TASK04_PRODUCTION_ACTIVATION=PASS"
echo "FIRST_PRODUCTION_CLASSIFICATION=PASS"
echo "PRODUCTION_READ_CONTRACT=PASS"
echo "PRODUCTION_AUDIT_CLOSURE=PASS"
echo "TASK04_STATUS=CLOSED"
echo "CODER_TASK04_HOLD=NO"
echo "CODER_RELEASED_FOR_OTHER_PORTAL_WORK=YES"
echo "REPORT=$REPORT"
