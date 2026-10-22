#!/usr/bin/env bash
set -Eeuo pipefail

PORTAL="/opt/CaptivePortal"
CFG="/etc/default/captive-portal"

EXPECTED_CURRENT_HEAD="f5e3d194ebffb3c6c1e1cd8afc31f80911e2ce71"
EXPECTED_CURRENT_TREE="02b6af353643a4321a6f14d01735b9c0e305842e"
EXPECTED_MERGED_MAIN="1d88f4ae947fa95454dbb54c70f9d6bdd13b1d22"
EXPECTED_MERGED_TREE="8183bf48abfc71c1b488c0667efc0f1ae717003e"

TASK04_WT="/home/admin/CaptivePortal-Deploy/task04-dormant-fecdb5a7"
CONTROL_DB="/opt/CaptivePortal/data/device_fingerprint_control_plane.sqlite3"
CLASS_DB="/opt/CaptivePortal/data/device_fingerprint_classification.sqlite3"
EVIDENCE_DB="/opt/CaptivePortal/data/device_fingerprint_evidence.sqlite3"
INTEGRATION_DB="/opt/CaptivePortal/data/device_fingerprint_integration.sqlite3"

fail(){ echo "FATAL: $*" >&2; exit 1; }
section(){ printf '\n===== %s =====\n' "$1"; }

[ "$(id -u)" -eq 0 ] || fail "Run with sudo/root"
[ -d "$PORTAL/.git" ] || fail "$PORTAL is not a Git checkout"
[ -f "$CFG" ] || fail "$CFG missing"

section "DECLARATION"
date -Is
echo "MODE=READ_ONLY_TASK05_PROD_PREDEPLOY"
echo "GIT_WORKTREE_WRITE=NO"
echo "CONFIG_WRITE=NO"
echo "SERVICE_RESTART=NO"
echo "DATABASE_WRITE=NO"

section "CURRENT PRODUCTION CODE"
HEAD="$(git -C "$PORTAL" rev-parse HEAD)"
TREE="$(git -C "$PORTAL" rev-parse 'HEAD^{tree}')"
STATUS="$(git -C "$PORTAL" status --porcelain=v1 --untracked-files=normal)"
echo "CURRENT_HEAD=$HEAD"
echo "CURRENT_TREE=$TREE"
[ "$HEAD" = "$EXPECTED_CURRENT_HEAD" ] || fail "Unexpected current production HEAD"
[ "$TREE" = "$EXPECTED_CURRENT_TREE" ] || fail "Unexpected current production tree"
[ -z "$STATUS" ] || { git -C "$PORTAL" status --short; fail "Production worktree dirty"; }
echo "CURRENT_PRODUCTION_IDENTITY=PASS"

section "MERGED TASK-05 GIT PROVENANCE"
# PR #175 / merge commit were independently verified by Tech Lead through GitHub.
# Do not call the production host's SSH Git remote here: this gate is intentionally
# read-only and must continue even when that host lacks a usable GitHub SSH key.
echo "EXPECTED_MERGED_MAIN=$EXPECTED_MERGED_MAIN"
echo "EXPECTED_MERGED_TREE=$EXPECTED_MERGED_TREE"
echo "GITHUB_PR=175"
echo "GITHUB_PR_MERGED=YES"
echo "GITHUB_PR_MERGED_AT_UTC=2026-10-03T19:11:57Z"
echo "GITHUB_MERGE_COMMIT=$EXPECTED_MERGED_MAIN"
echo "GITHUB_MERGE_TREE=$EXPECTED_MERGED_TREE"
echo "REMOTE_MERGE_IDENTITY=PASS_EXTERNAL_TECHLEAD_VERIFICATION"

ORIGIN_URL="$(git -C "$PORTAL" remote get-url origin 2>/dev/null || true)"
echo "PRODUCTION_ORIGIN_URL=$ORIGIN_URL"
if git -C "$PORTAL" cat-file -e "${EXPECTED_MERGED_MAIN}^{commit}" 2>/dev/null; then
  LOCAL_MERGED_TREE="$(git -C "$PORTAL" rev-parse "${EXPECTED_MERGED_MAIN}^{tree}")"
  echo "MERGED_COMMIT_OBJECT_LOCAL=YES"
  echo "MERGED_COMMIT_LOCAL_TREE=$LOCAL_MERGED_TREE"
  [ "$LOCAL_MERGED_TREE" = "$EXPECTED_MERGED_TREE" ] || fail "Local merged commit tree mismatch"
else
  echo "MERGED_COMMIT_OBJECT_LOCAL=NO"
  echo "MERGED_COMMIT_LOCAL_TREE=NOT_PRESENT"
fi

section "PORTAL SERVICE"
systemctl is-active --quiet captive-portal.service || fail "captive-portal.service is not active"
systemctl show captive-portal.service \
  -p FragmentPath -p User -p Group -p MainPID -p NRestarts -p ActiveState -p SubState \
  --no-pager
echo "EFFECTIVE_EXECSTART=$(systemctl show captive-portal.service -p ExecStart --value)"
echo "DROPINS:"
systemctl show captive-portal.service -p DropInPaths --value
echo "CAPTIVE_PORTAL_SERVICE_BASELINE=PASS"

section "CURRENT LOADED ARTIFACT IDENTITY"
LATEST_IDENTITY="$(journalctl -u captive-portal.service -n 1000 --no-pager \
  | grep '"event":"captivportal_loaded_artifact_identity"' | tail -n1 || true)"
[ -n "$LATEST_IDENTITY" ] || fail "No captive portal loaded-artifact identity found"
echo "$LATEST_IDENTITY"
LATEST_IDENTITY="$LATEST_IDENTITY" EXPECTED_CURRENT_HEAD="$EXPECTED_CURRENT_HEAD" EXPECTED_CURRENT_TREE="$EXPECTED_CURRENT_TREE" \
/usr/bin/python3 - <<'PY'
import json, os
s=os.environ["LATEST_IDENTITY"]
o=json.loads(s[s.index("{"):])
assert o["artifact_sha"] == os.environ["EXPECTED_CURRENT_HEAD"], o
assert o["artifact_tree"] == os.environ["EXPECTED_CURRENT_TREE"], o
assert o["service_name"] == "captive-portal.service", o
print("LOADED_ARTIFACT_IDENTITY=PASS")
PY

section "SAFE CONFIG INVENTORY"
# Only non-secret deployment keys are printed.
grep -E '^(DEVICE_FINGERPRINT_(INTEGRATION_ENABLED|INTEGRATION_DB_PATH|EVIDENCE_DB_PATH|CLASSIFICATION_DB_PATH|CONTROL_PLANE_DB_PATH|DB_PATH)|VISITOR_REGISTRY_DB_PATH|VISIT_LIFECYCLE_DB_PATH|CURRENT_STATE_DB_PATH)=' "$CFG" || true

get_cfg(){
  local key="$1" default="$2" line value
  line="$(grep -E "^${key}=" "$CFG" | tail -n1 || true)"
  if [ -z "$line" ]; then
    printf '%s' "$default"
    return
  fi
  value="${line#*=}"
  value="${value%$'\r'}"
  if [[ "$value" == \"*\" && "$value" == *\" ]]; then value="${value:1:${#value}-2}"; fi
  if [[ "$value" == \'*\' && "$value" == *\' ]]; then value="${value:1:${#value}-2}"; fi
  printf '%s' "$value"
}

REGISTRY_DB="$(get_cfg VISITOR_REGISTRY_DB_PATH /opt/CaptivePortal/data/visitor_registry.sqlite3)"
VISIT_DB="$(get_cfg VISIT_LIFECYCLE_DB_PATH /opt/CaptivePortal/data/visits.sqlite3)"
CURRENT_DB="$(get_cfg CURRENT_STATE_DB_PATH /opt/CaptivePortal/data/current_state.sqlite3)"
echo "RESOLVED_REGISTRY_DB=$REGISTRY_DB"
echo "RESOLVED_VISIT_DB=$VISIT_DB"
echo "RESOLVED_CURRENT_STATE_DB=$CURRENT_DB"

section "DOMAIN DATABASES"
for p in "$EVIDENCE_DB" "$CLASS_DB" "$CONTROL_DB" "$REGISTRY_DB" "$VISIT_DB"; do
  [ -f "$p" ] || fail "Required DB missing: $p"
  stat -c 'DB=%n OWNER=%U:%G MODE=%a BYTES=%s' "$p"
done
if [ -e "$INTEGRATION_DB" ]; then
  stat -c 'UNEXPECTED_INTEGRATION_DB=%n OWNER=%U:%G MODE=%a BYTES=%s' "$INTEGRATION_DB"
  fail "Integration DB already exists before Task-05 deployment"
else
  echo "INTEGRATION_DB_PRISTINE=ABSENT"
fi

section "SQLITE READ-ONLY INTEGRITY"
/usr/bin/python3 - "$EVIDENCE_DB" "$CLASS_DB" "$CONTROL_DB" "$REGISTRY_DB" "$VISIT_DB" <<'PY'
import sqlite3, sys
from pathlib import Path
for raw in sys.argv[1:]:
    p=Path(raw)
    con=sqlite3.connect(f"{p.resolve().as_uri()}?mode=ro", uri=True)
    try:
        q=con.execute("PRAGMA quick_check").fetchone()[0]
        if q != "ok":
            raise SystemExit(f"FATAL: quick_check failed: {p}: {q}")
        print(f"QUICK_CHECK=PASS DB={p}")
    finally:
        con.close()
PY

section "TASK04 CLASSIFICATION STATE"
[ -d "$TASK04_WT" ] || fail "Task-04 production worktree missing"
sudo -u admin env PYTHONPATH="$TASK04_WT" CONTROL_DB="$CONTROL_DB" CLASS_DB="$CLASS_DB" /usr/bin/python3 - <<'PY'
import os, sqlite3
from app.device_fingerprint.control_plane_store import DeviceFingerprintControlPlaneStore

control=DeviceFingerprintControlPlaneStore(os.environ["CONTROL_DB"])
pin=control.pin_active_profile("classification")
print("ACTIVE_CRP="+pin.runtime_profile.artifact_id)
print("ACTIVE_RPM="+pin.admission_manifest.artifact_id)
print("ACTIVE_VALIDITY="+pin.validity_record.semantic_payload["state"])
if pin.validity_record.semantic_payload["state"] != "ACTIVE":
    raise SystemExit("FATAL: classification validity not ACTIVE")

con=sqlite3.connect(f"file:{os.environ['CLASS_DB']}?mode=ro", uri=True)
try:
    rows=con.execute("SELECT COUNT(*) FROM classifications").fetchone()[0]
finally:
    con.close()
print(f"CLASSIFICATION_ROWS={rows}")
if rows != 1:
    raise SystemExit("FATAL: expected exactly first controlled production classification row")
print("TASK04_ACTIVE_STATE=PASS")
PY

section "FINGERPRINT SERVICES"
for u in fingerprint-evidence.service fingerprint-sensor.service fingerprint-suricata.service; do
  systemctl is-active --quiet "$u" || fail "$u not active"
  systemctl show "$u" -p MainPID -p NRestarts -p ActiveState -p SubState --no-pager
done
if systemctl list-unit-files fingerprint-classification.service --no-legend 2>/dev/null | grep -q '^fingerprint-classification.service'; then
  echo "FINGERPRINT_CLASSIFICATION_UNIT_PRESENT=YES"
  systemctl is-active fingerprint-classification.service || true
  fail "Task-05 worker unit unexpectedly already installed"
else
  echo "FINGERPRINT_CLASSIFICATION_UNIT_PRESENT=NO"
fi
echo "FOUNDATION_RUNTIME_HEALTH=PASS"

section "FILESYSTEM"
df -h /opt/CaptivePortal
test -w /opt/CaptivePortal/data || fail "/opt/CaptivePortal/data is not writable"
echo "DATA_DIRECTORY_WRITABLE=PASS"

section "FINAL"
echo "POST_MERGE_PROVENANCE=PASS"
echo "CURRENT_PRODUCTION_ROLLBACK_POINT=$EXPECTED_CURRENT_HEAD"
echo "TASK05_MERGED_DEPLOYMENT_COMMIT=$EXPECTED_MERGED_MAIN"
echo "TASK05_MERGED_DEPLOYMENT_TREE=$EXPECTED_MERGED_TREE"
echo "TASK05_PROD_PREDEPLOY=PASS"
echo "CHANGES_MADE=NONE"
