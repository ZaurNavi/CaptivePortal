#!/usr/bin/env bash
set -Eeuo pipefail

export SYSTEMD_PAGER=cat
export PAGER=cat

PORTAL="/opt/CaptivePortal"
STAGE="/home/admin/CaptivePortal-Deploy/task05-merged-1d88f4ae"
CFG="/etc/default/captive-portal"

OLD_HEAD="f5e3d194ebffb3c6c1e1cd8afc31f80911e2ce71"
OLD_TREE="02b6af353643a4321a6f14d01735b9c0e305842e"
TARGET_HEAD="1d88f4ae947fa95454dbb54c70f9d6bdd13b1d22"
TARGET_TREE="8183bf48abfc71c1b488c0667efc0f1ae717003e"
HTTPS_ORIGIN="https://github.com/ZaurNavi/CaptivePortal.git"

CONTROL_DB="/opt/CaptivePortal/data/device_fingerprint_control_plane.sqlite3"
CLASS_DB="/opt/CaptivePortal/data/device_fingerprint_classification.sqlite3"
INTEGRATION_DB="/opt/CaptivePortal/data/device_fingerprint_integration.sqlite3"
SENSOR_SOCKET="/run/captive-portal/fingerprint-sensor/suricata-eve.sock"

SWITCH_STARTED=0
COMPLETED=0

section(){ printf '\n===== %s =====\n' "$1"; }
fail(){ echo "FATAL: $*" >&2; return 1; }

wait_active() {
  local unit="$1" timeout="${2:-30}"
  local i
  for ((i=1; i<=timeout; i++)); do
    if systemctl is-active --quiet "$unit"; then
      return 0
    fi
    sleep 1
  done
  return 1
}

wait_socket() {
  local path="$1" timeout="${2:-60}"
  local i
  for ((i=1; i<=timeout; i++)); do
    if [ -S "$path" ]; then
      return 0
    fi
    sleep 1
  done
  return 1
}

wait_portal_identity() {
  local expected_head="$1" expected_tree="$2" since="$3" timeout="${4:-45}"
  local i line
  for ((i=1; i<=timeout; i++)); do
    line="$(journalctl -u captive-portal.service --since "$since" --no-pager -o cat 2>/dev/null \
      | grep '"event":"captivportal_loaded_artifact_identity"' | tail -n1 || true)"
    if [ -n "$line" ]; then
      IDENTITY_LINE="$line" EXPECTED_HEAD="$expected_head" EXPECTED_TREE="$expected_tree" \
      /usr/bin/python3 - <<'PY'
import json, os
s = os.environ["IDENTITY_LINE"]
obj = json.loads(s[s.index("{"):])
assert obj["artifact_sha"] == os.environ["EXPECTED_HEAD"], obj
assert obj["artifact_tree"] == os.environ["EXPECTED_TREE"], obj
assert obj["service_name"] == "captive-portal.service", obj
print("PORTAL_LOADED_ARTIFACT_SHA="+obj["artifact_sha"])
print("PORTAL_LOADED_ARTIFACT_TREE="+obj["artifact_tree"])
print("PORTAL_LOADED_PROCESS_STARTED_AT="+obj["process_started_at"])
PY
      return 0
    fi
    sleep 1
  done
  return 1
}

wait_portal_server_start() {
  local since="$1" timeout="${2:-45}"
  local i
  for ((i=1; i<=timeout; i++)); do
    if journalctl -u captive-portal.service --since "$since" --no-pager -o cat 2>/dev/null \
      | grep -q 'Starting server on '; then
      return 0
    fi
    if ! systemctl is-active --quiet captive-portal.service; then
      return 1
    fi
    sleep 1
  done
  return 1
}

rollback() {
  local reason="$1"
  trap - ERR
  set +e

  section "AUTOMATIC ROLLBACK"
  echo "ROLLBACK_REASON=$reason"
  echo "ROLLBACK_TARGET=$OLD_HEAD"

  systemctl stop fingerprint-suricata.service >/dev/null 2>&1 || true
  systemctl stop fingerprint-sensor.service >/dev/null 2>&1 || true
  systemctl stop captive-portal.service >/dev/null 2>&1 || true

  sudo -H -u admin git -C "$PORTAL" checkout --detach "$OLD_HEAD"
  local checkout_rc=$?

  local rb_head rb_tree rb_status
  rb_head="$(git -C "$PORTAL" rev-parse HEAD 2>/dev/null)"
  rb_tree="$(git -C "$PORTAL" rev-parse 'HEAD^{tree}' 2>/dev/null)"
  rb_status="$(git -C "$PORTAL" status --porcelain=v1 --untracked-files=normal 2>/dev/null)"

  echo "ROLLBACK_HEAD=$rb_head"
  echo "ROLLBACK_TREE=$rb_tree"

  local rollback_ok=1
  [ "$checkout_rc" -eq 0 ] || rollback_ok=0
  [ "$rb_head" = "$OLD_HEAD" ] || rollback_ok=0
  [ "$rb_tree" = "$OLD_TREE" ] || rollback_ok=0
  [ -z "$rb_status" ] || rollback_ok=0

  local rb_since
  rb_since="$(date --iso-8601=seconds)"
  systemctl start captive-portal.service
  wait_active captive-portal.service 30 || rollback_ok=0
  wait_portal_identity "$OLD_HEAD" "$OLD_TREE" "$rb_since" 45 || rollback_ok=0
  wait_portal_server_start "$rb_since" 45 || rollback_ok=0

  systemctl start fingerprint-sensor.service
  wait_active fingerprint-sensor.service 30 || rollback_ok=0
  wait_socket "$SENSOR_SOCKET" 60 || rollback_ok=0

  /usr/bin/timeout 60 systemctl start fingerprint-suricata.service
  wait_active fingerprint-suricata.service 30 || rollback_ok=0

  if [ -e "$INTEGRATION_DB" ]; then
    echo "ROLLBACK_WARNING_INTEGRATION_DB_PRESENT=YES"
    rollback_ok=0
  else
    echo "ROLLBACK_INTEGRATION_DB_PRESENT=NO"
  fi

  if [ "$rollback_ok" -eq 1 ]; then
    echo "TASK05_CODE_SWITCH_ROLLBACK=PASS"
  else
    echo "TASK05_CODE_SWITCH_ROLLBACK=FAILED"
  fi
  echo "TASK05_CODE_SWITCH=FAILED_ROLLED_BACK"
  exit 1
}

on_error() {
  local rc=$? line="$1"
  if [ "$SWITCH_STARTED" -eq 1 ] && [ "$COMPLETED" -eq 0 ]; then
    rollback "line_${line}_exit_${rc}"
  fi
  exit "$rc"
}
trap 'on_error $LINENO' ERR

[ "$(id -u)" -eq 0 ] || { echo "FATAL: Run with sudo/root" >&2; exit 1; }

section "DECLARATION"
date --iso-8601=seconds
echo "MODE=TASK05_PROD_CODE_SWITCH_INTEGRATION_DISABLED"
echo "PRODUCTION_CODE_SWITCH=YES"
echo "CONFIG_WRITE=NO"
echo "SYSTEMD_UNIT_WRITE=NO"
echo "PORTAL_RESTART=YES"
echo "SENSOR_RESTART=YES"
echo "SURICATA_RESTART=YES"
echo "EVIDENCE_SERVICE_RESTART=NO"
echo "TASK05_INTEGRATION_ACTIVATION=NO"
echo "TASK05_INTEGRATION_DB_CREATION_EXPECTED=NO"
echo "AUTOMATIC_ROLLBACK=YES"

section "PRECONDITIONS"
[ -d "$PORTAL/.git" ] || fail "Production Git worktree missing"
[ -d "$STAGE/.git" ] || fail "Staged Task-05 artifact missing"
[ -f "$CFG" ] || fail "$CFG missing"

CURRENT_HEAD="$(git -C "$PORTAL" rev-parse HEAD)"
CURRENT_TREE="$(git -C "$PORTAL" rev-parse 'HEAD^{tree}')"
CURRENT_STATUS="$(git -C "$PORTAL" status --porcelain=v1 --untracked-files=normal)"
STAGE_HEAD="$(git -C "$STAGE" rev-parse HEAD)"
STAGE_TREE="$(git -C "$STAGE" rev-parse 'HEAD^{tree}')"
STAGE_STATUS="$(git -C "$STAGE" status --porcelain=v1 --untracked-files=normal)"

echo "CURRENT_HEAD=$CURRENT_HEAD"
echo "CURRENT_TREE=$CURRENT_TREE"
echo "STAGED_HEAD=$STAGE_HEAD"
echo "STAGED_TREE=$STAGE_TREE"

[ "$CURRENT_HEAD" = "$OLD_HEAD" ] || fail "Production is not at approved rollback point"
[ "$CURRENT_TREE" = "$OLD_TREE" ] || fail "Production rollback tree mismatch"
[ -z "$CURRENT_STATUS" ] || fail "Production worktree dirty"
[ "$STAGE_HEAD" = "$TARGET_HEAD" ] || fail "Staged Task-05 HEAD mismatch"
[ "$STAGE_TREE" = "$TARGET_TREE" ] || fail "Staged Task-05 tree mismatch"
[ -z "$STAGE_STATUS" ] || fail "Staged Task-05 worktree dirty"
[ ! -e "$INTEGRATION_DB" ] || fail "Integration DB exists before activation"
echo "EXACT_ARTIFACT_PRECONDITION=PASS"

section "INTEGRATION DISABLED PRECONDITION"
CFG_VALUE="$(awk -F= '
  $1=="DEVICE_FINGERPRINT_INTEGRATION_ENABLED" {
    value=substr($0,index($0,"=")+1)
    gsub(/^[ \t]+|[ \t]+$/, "", value)
    print value
  }' "$CFG" | tail -n1)"

if [ -z "$CFG_VALUE" ]; then
  echo "ENVFILE_INTEGRATION_ENABLED=ABSENT_DEFAULT_FALSE"
else
  case "${CFG_VALUE,,}" in
    false|0|no|off) echo "ENVFILE_INTEGRATION_ENABLED=$CFG_VALUE" ;;
    *) fail "Integration is enabled in environment file" ;;
  esac
fi

UNIT_VALUES="$(systemctl cat captive-portal.service --no-pager 2>/dev/null \
  | sed -n 's/^[[:space:]]*Environment=["'\'']\?DEVICE_FINGERPRINT_INTEGRATION_ENABLED=\([^"'\'']*\)["'\'']\?/\1/p' \
  || true)"
if [ -z "$UNIT_VALUES" ]; then
  echo "UNIT_INTEGRATION_OVERRIDE=ABSENT"
else
  while IFS= read -r value; do
    case "${value,,}" in
      false|0|no|off) ;;
      *) fail "Integration is enabled by captive-portal systemd Environment override" ;;
    esac
  done <<< "$UNIT_VALUES"
  echo "UNIT_INTEGRATION_OVERRIDE=DISABLED"
fi
echo "INTEGRATION_DISABLED_PRECONDITION=PASS"

section "SERVICE BASELINE"
for unit in captive-portal.service fingerprint-evidence.service fingerprint-sensor.service fingerprint-suricata.service; do
  systemctl is-active --quiet "$unit" || fail "$unit is not active"
done

PORTAL_BASE_RESTARTS="$(systemctl show captive-portal.service -p NRestarts --value --no-pager)"
EVIDENCE_BASE_PID="$(systemctl show fingerprint-evidence.service -p MainPID --value --no-pager)"
EVIDENCE_BASE_RESTARTS="$(systemctl show fingerprint-evidence.service -p NRestarts --value --no-pager)"
SENSOR_BASE_RESTARTS="$(systemctl show fingerprint-sensor.service -p NRestarts --value --no-pager)"
SURICATA_BASE_RESTARTS="$(systemctl show fingerprint-suricata.service -p NRestarts --value --no-pager)"

echo "PORTAL_BASE_NRESTARTS=$PORTAL_BASE_RESTARTS"
echo "EVIDENCE_BASE_PID=$EVIDENCE_BASE_PID"
echo "EVIDENCE_BASE_NRESTARTS=$EVIDENCE_BASE_RESTARTS"
echo "SENSOR_BASE_NRESTARTS=$SENSOR_BASE_RESTARTS"
echo "SURICATA_BASE_NRESTARTS=$SURICATA_BASE_RESTARTS"
echo "SERVICE_BASELINE=PASS"

section "FETCH EXACT TARGET INTO PRODUCTION GIT OBJECT STORE"
sudo -H -u admin git -C "$PORTAL" fetch --no-tags "$HTTPS_ORIGIN" "$TARGET_HEAD"
git -C "$PORTAL" cat-file -e "${TARGET_HEAD}^{commit}"
FETCHED_TREE="$(git -C "$PORTAL" rev-parse "${TARGET_HEAD}^{tree}")"
echo "FETCHED_TARGET_HEAD=$TARGET_HEAD"
echo "FETCHED_TARGET_TREE=$FETCHED_TREE"
[ "$FETCHED_TREE" = "$TARGET_TREE" ] || fail "Fetched target tree mismatch"
[ "$(git -C "$PORTAL" rev-parse HEAD)" = "$OLD_HEAD" ] || fail "Fetch changed production HEAD"
[ -z "$(git -C "$PORTAL" status --porcelain=v1 --untracked-files=normal)" ] \
  || fail "Fetch changed production worktree"
echo "TARGET_FETCH=PASS"

section "CONTROLLED SERVICE QUIESCE"
SWITCH_STARTED=1
systemctl stop fingerprint-suricata.service
systemctl stop fingerprint-sensor.service
systemctl stop captive-portal.service

systemctl is-active --quiet fingerprint-suricata.service && fail "Suricata did not stop" || true
systemctl is-active --quiet fingerprint-sensor.service && fail "Sensor did not stop" || true
systemctl is-active --quiet captive-portal.service && fail "Portal did not stop" || true
echo "CONTROLLED_SERVICE_QUIESCE=PASS"

section "PRODUCTION CODE SWITCH"
sudo -H -u admin git -C "$PORTAL" checkout --detach "$TARGET_HEAD"

NEW_HEAD="$(git -C "$PORTAL" rev-parse HEAD)"
NEW_TREE="$(git -C "$PORTAL" rev-parse 'HEAD^{tree}')"
NEW_STATUS="$(git -C "$PORTAL" status --porcelain=v1 --untracked-files=normal)"
echo "NEW_HEAD=$NEW_HEAD"
echo "NEW_TREE=$NEW_TREE"
[ "$NEW_HEAD" = "$TARGET_HEAD" ] || fail "Production HEAD did not switch to Task-05"
[ "$NEW_TREE" = "$TARGET_TREE" ] || fail "Production tree did not switch to Task-05"
[ -z "$NEW_STATUS" ] || fail "Production worktree dirty after Task-05 checkout"
[ ! -e "$INTEGRATION_DB" ] || fail "Integration DB appeared during code checkout"
echo "PRODUCTION_CODE_SWITCH=PASS"

section "START PORTAL ON TASK05 CODE"
PORTAL_START_SINCE="$(date --iso-8601=seconds)"
systemctl start captive-portal.service
wait_active captive-portal.service 30 || fail "captive-portal.service did not become active"
wait_portal_identity "$TARGET_HEAD" "$TARGET_TREE" "$PORTAL_START_SINCE" 45 \
  || fail "Fresh Task-05 loaded-artifact identity not observed"
wait_portal_server_start "$PORTAL_START_SINCE" 45 \
  || fail "Portal did not reach server start on Task-05 code"
sleep 5
systemctl is-active --quiet captive-portal.service || fail "Portal not stable after startup"

PORTAL_POST_PID="$(systemctl show captive-portal.service -p MainPID --value --no-pager)"
PORTAL_POST_RESTARTS="$(systemctl show captive-portal.service -p NRestarts --value --no-pager)"
echo "PORTAL_POST_PID=$PORTAL_POST_PID"
echo "PORTAL_POST_NRESTARTS=$PORTAL_POST_RESTARTS"
[ "$PORTAL_POST_RESTARTS" = "$PORTAL_BASE_RESTARTS" ] \
  || fail "Portal automatic restart count increased"
[ ! -e "$INTEGRATION_DB" ] || fail "Disabled integration created its DB"
echo "PORTAL_TASK05_CODE_ONLY_START=PASS"

section "RESTART SENSOR AND SURICATA"
systemctl start fingerprint-sensor.service
wait_active fingerprint-sensor.service 30 || fail "fingerprint-sensor.service did not become active"
wait_socket "$SENSOR_SOCKET" 60 || fail "Sensor EVE socket did not return"

SENSOR_POST_RESTARTS="$(systemctl show fingerprint-sensor.service -p NRestarts --value --no-pager)"
echo "SENSOR_POST_NRESTARTS=$SENSOR_POST_RESTARTS"
[ "$SENSOR_POST_RESTARTS" = "$SENSOR_BASE_RESTARTS" ] \
  || fail "Sensor automatic restart count increased"

 /usr/bin/timeout 60 systemctl start fingerprint-suricata.service
wait_active fingerprint-suricata.service 30 || fail "fingerprint-suricata.service did not become active"
sleep 3
systemctl is-active --quiet fingerprint-suricata.service || fail "Suricata not stable"

SURICATA_POST_RESTARTS="$(systemctl show fingerprint-suricata.service -p NRestarts --value --no-pager)"
echo "SURICATA_POST_NRESTARTS=$SURICATA_POST_RESTARTS"
[ "$SURICATA_POST_RESTARTS" = "$SURICATA_BASE_RESTARTS" ] \
  || fail "Suricata automatic restart count increased"
echo "SENSOR_SURICATA_RECOVERY=PASS"

section "UNCHANGED EVIDENCE SERVICE"
systemctl is-active --quiet fingerprint-evidence.service || fail "fingerprint-evidence.service lost"
EVIDENCE_POST_PID="$(systemctl show fingerprint-evidence.service -p MainPID --value --no-pager)"
EVIDENCE_POST_RESTARTS="$(systemctl show fingerprint-evidence.service -p NRestarts --value --no-pager)"
echo "EVIDENCE_POST_PID=$EVIDENCE_POST_PID"
echo "EVIDENCE_POST_NRESTARTS=$EVIDENCE_POST_RESTARTS"
[ "$EVIDENCE_POST_PID" = "$EVIDENCE_BASE_PID" ] || fail "Evidence service PID changed unexpectedly"
[ "$EVIDENCE_POST_RESTARTS" = "$EVIDENCE_BASE_RESTARTS" ] \
  || fail "Evidence service restart count changed unexpectedly"
echo "EVIDENCE_SERVICE_UNTOUCHED=PASS"

section "TASK04 READ COMPATIBILITY AFTER SWITCH"
sudo -H -u admin env \
  PYTHONPATH="$PORTAL" \
  PYTHONDONTWRITEBYTECODE=1 \
  CONTROL_DB="$CONTROL_DB" \
  CLASS_DB="$CLASS_DB" \
  /usr/bin/python3 -B - <<'PY'
import os
import sqlite3
from app.device_fingerprint.control_plane_store import DeviceFingerprintControlPlaneStore

control = DeviceFingerprintControlPlaneStore(os.environ["CONTROL_DB"])
pin = control.pin_active_profile("classification")
print("ACTIVE_CRP="+pin.runtime_profile.artifact_id)
print("ACTIVE_RPM="+pin.admission_manifest.artifact_id)
print("ACTIVE_VALIDITY="+pin.validity_record.semantic_payload["state"])
if pin.validity_record.semantic_payload["state"] != "ACTIVE":
    raise SystemExit("FATAL: active classification validity changed")

con = sqlite3.connect(f"file:{os.environ['CLASS_DB']}?mode=ro", uri=True)
try:
    rows = con.execute("SELECT COUNT(*) FROM classifications").fetchone()[0]
finally:
    con.close()
print(f"CLASSIFICATION_ROWS={rows}")
if rows != 1:
    raise SystemExit("FATAL: classification row count changed before Task-05 activation")
print("TASK04_POST_SWITCH_READ_COMPAT=PASS")
PY

section "FINAL INVARIANTS"
[ "$(git -C "$PORTAL" rev-parse HEAD)" = "$TARGET_HEAD" ] || fail "Final production HEAD mismatch"
[ "$(git -C "$PORTAL" rev-parse 'HEAD^{tree}')" = "$TARGET_TREE" ] || fail "Final production tree mismatch"
[ -z "$(git -C "$PORTAL" status --porcelain=v1 --untracked-files=normal)" ] \
  || fail "Final production worktree dirty"
[ ! -e "$INTEGRATION_DB" ] || fail "Integration DB exists while integration is disabled"

for unit in captive-portal.service fingerprint-evidence.service fingerprint-sensor.service fingerprint-suricata.service; do
  systemctl is-active --quiet "$unit" || fail "$unit is not active at final gate"
done

if systemctl list-unit-files fingerprint-classification.service --no-legend 2>/dev/null \
  | grep -q '^fingerprint-classification.service'; then
  fail "Task-05 classification unit unexpectedly installed during code-only switch"
fi

echo "TASK05_INTEGRATION_ENABLED=NO"
echo "INTEGRATION_DB_PRESENT=NO"
echo "CLASSIFICATION_UNIT_PRESENT=NO"
echo "FINAL_RUNTIME_INVARIANTS=PASS"

COMPLETED=1
trap - ERR

section "FINAL"
echo "PREVIOUS_PRODUCTION_HEAD=$OLD_HEAD"
echo "PREVIOUS_PRODUCTION_TREE=$OLD_TREE"
echo "CURRENT_PRODUCTION_HEAD=$TARGET_HEAD"
echo "CURRENT_PRODUCTION_TREE=$TARGET_TREE"
echo "TASK05_PROD_CODE_SWITCH=PASS"
echo "TASK05_INTEGRATION_ACTIVATED=NO"
echo "CONFIG_CHANGED=NO"
echo "SYSTEMD_UNIT_FILES_CHANGED=NO"
echo "AUTOMATIC_ROLLBACK_USED=NO"
