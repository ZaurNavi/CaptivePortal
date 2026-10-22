#!/usr/bin/env bash
set -Eeuo pipefail

WT="/home/admin/CaptivePortal-Deploy/task04-dormant-fecdb5a7"
TARGET_SHA="fecdb5a7c79e56bb49be4797ca875d6720670042"
TARGET_TREE="85d7d41e1ad19c079cad0ae819a3fe38a068e242"

CONTROL_DB="/opt/CaptivePortal/data/device_fingerprint_control_plane.sqlite3"
CLASS_DB="/opt/CaptivePortal/data/device_fingerprint_classification.sqlite3"
EVIDENCE_DB="/opt/CaptivePortal/data/device_fingerprint_evidence.sqlite3"

CRP_ID="ClassificationRuntimeProfile:v1:sha256:1d3a563e7ce3a8afb2ff259e596328b14f5ff5ce9940db703cbb93b12c2cbf6c"
CRP_SHA="1d3a563e7ce3a8afb2ff259e596328b14f5ff5ce9940db703cbb93b12c2cbf6c"
RPM_ID="RuntimeProfileAdmissionManifest:v1:sha256:7873028b2c3a85bf152c9bc4ea057e476591ab87d3c3a52b8cdff654beb8c98b"
ACTIVATION_ID="c9600739-38c6-4186-b67d-91ada854376f"
GENERATION_ID="a17a67e5-b291-40c3-96f6-182bf33c6da6"

REPORT="/home/admin/device-fingerprint-task04-first-production-readiness-r1.txt"

exec > >(tee "$REPORT") 2>&1
die(){ echo "FATAL: $*" >&2; exit 1; }
step(){ printf '\n===== %s =====\n' "$1"; }

[ "$(id -u)" -eq 0 ] || die "Run with sudo/root."

step "DECLARATION"
date -Is
echo "MODE=READ_ONLY_FIRST_PRODUCTION_CLASSIFICATION_READINESS"
echo "CLASSIFICATION_WRITE=NO"
echo "SERVICE_RESTART=NO"

for f in "$CONTROL_DB" "$CLASS_DB" "$EVIDENCE_DB"; do
  [ -f "$f" ] || die "Missing $f"
done
[ -e "$WT/.git" ] || die "Exact worktree missing"

HEAD="$(sudo -u admin git -C "$WT" rev-parse HEAD)"
TREE="$(sudo -u admin git -C "$WT" rev-parse 'HEAD^{tree}')"
[ "$HEAD" = "$TARGET_SHA" ] || die "HEAD mismatch"
[ "$TREE" = "$TARGET_TREE" ] || die "TREE mismatch"
[ -z "$(sudo -u admin git -C "$WT" status --porcelain=v1)" ] || die "worktree dirty"
echo "WORKTREE_PROVENANCE=PASS"

CONTROL_BEFORE="$(sha256sum "$CONTROL_DB"|awk '{print $1}')"
CLASS_BEFORE="$(sha256sum "$CLASS_DB"|awk '{print $1}')"

step "ACTIVE CLASSIFICATION LINEAGE"
sudo -u admin env PYTHONPATH="$WT" \
  CONTROL_DB="$CONTROL_DB" CLASS_DB="$CLASS_DB" \
  CRP_ID="$CRP_ID" CRP_SHA="$CRP_SHA" RPM_ID="$RPM_ID" \
  ACTIVATION_ID="$ACTIVATION_ID" GENERATION_ID="$GENERATION_ID" \
  /usr/bin/python3 - <<'PY'
import os, sqlite3
from app.device_fingerprint.control_plane_store import DeviceFingerprintControlPlaneStore
from app.device_fingerprint.classification_read import DeviceFingerprintClassificationReadService
from app.device_fingerprint.classification_persistence import DeviceFingerprintClassificationStore
from app.device_fingerprint.request_assembly import DeviceFingerprintRequestAssembly
from app.device_fingerprint.read_service import DeviceFingerprintReadService
from app.device_fingerprint.classification_retention_policy import build_initial_classification_retention_policy_v1

store=DeviceFingerprintControlPlaneStore(os.environ["CONTROL_DB"])
p=store.pin_active_profile("classification")
assert p.pointer.runtime_profile_id == os.environ["CRP_ID"]
assert p.pointer.runtime_profile_digest == os.environ["CRP_SHA"]
assert p.pointer.activation_record_id == os.environ["ACTIVATION_ID"]
assert p.pointer.activation_generation_id == os.environ["GENERATION_ID"]
assert p.admission_manifest.artifact_id == os.environ["RPM_ID"]
assert p.validity_record.semantic_payload["state"] == "ACTIVE"
assert p.validity_record.semantic_payload["reason_code"] == "ACTIVATED"
assert p.validity_record.semantic_payload["inflight_commit_rule"] == "ALLOW_PINNED_INFLIGHT"

c=sqlite3.connect(f"file:{os.environ['CLASS_DB']}?mode=ro", uri=True)
try:
    assert c.execute("PRAGMA quick_check").fetchone()[0] == "ok"
    row_count=c.execute("SELECT COUNT(*) FROM classifications").fetchone()[0]
finally:
    c.close()

# Import the exact production execution building blocks.
assert DeviceFingerprintRequestAssembly is not None
assert DeviceFingerprintClassificationStore is not None
assert DeviceFingerprintClassificationReadService is not None
assert DeviceFingerprintReadService is not None
retention=build_initial_classification_retention_policy_v1()
assert retention.artifact_type == "ClassificationRetentionPolicy"

print("CLASSIFICATION_POINTER=ACTIVE_EXACT")
print("CLASSIFICATION_VALIDITY=ACTIVE")
print("CLASSIFICATION_RPM=EXACT")
print(f"CLASSIFICATION_ROWS_CURRENT={row_count}")
print("PRODUCTION_EXECUTION_IMPORTS=PASS")
print(f"RETENTION_POLICY_ID={retention.artifact_id}")
PY

step "FOUNDATION SERVICES"
for u in captive-portal.service fingerprint-evidence.service fingerprint-sensor.service fingerprint-suricata.service; do
  systemctl is-active --quiet "$u" || die "$u not active"
  systemctl show "$u" -p MainPID -p NRestarts -p ActiveState -p SubState --no-pager
done
echo "SERVICES_ACTIVE=PASS"

LATEST_SENSOR="$(journalctl -u fingerprint-sensor.service -n 600 --no-pager | grep '"event":"fingerprint_sensor_metrics"' | tail -n1 || true)"
[ -n "$LATEST_SENSOR" ] || die "No sensor metrics"
echo "$LATEST_SENSOR"
LATEST_SENSOR="$LATEST_SENSOR" python3 - <<'PY'
import json,os
s=os.environ["LATEST_SENSOR"]
o=json.loads(s[s.index("{"):])
assert o["runtime_state"]=="ready",o
assert o["suricata_process_active"] is True,o
assert o["oldest_spool_age"]==0,o
assert o["eve_json_invalid"]==0,o
assert o["eve_datagram_truncated"]==0,o
print("SENSOR_READY=PASS")
PY

if journalctl -u fingerprint-evidence.service --since "20 minutes ago" --no-pager | grep -Fq '"error_category":"concurrency_limit"'; then
  die "Recent evidence concurrency limit"
fi
echo "EVIDENCE_RECENT_CONCURRENCY_LIMIT=NONE"

step "IMMUTABILITY"
CONTROL_AFTER="$(sha256sum "$CONTROL_DB"|awk '{print $1}')"
CLASS_AFTER="$(sha256sum "$CLASS_DB"|awk '{print $1}')"
[ "$CONTROL_BEFORE" = "$CONTROL_AFTER" ] || die "Control DB changed"
[ "$CLASS_BEFORE" = "$CLASS_AFTER" ] || die "Classification DB changed"
echo "CONTROL_DB_UNCHANGED=PASS"
echo "CLASS_DB_UNCHANGED=PASS"

step "FINAL"
echo "TASK04_FIRST_PRODUCTION_CLASSIFICATION_READINESS=PASS"
echo "CONTROLLED_DEVICE_REQUIRED=YES"
echo "CLASSIFICATION_EXECUTED=NO"
echo "REPORT=$REPORT"
