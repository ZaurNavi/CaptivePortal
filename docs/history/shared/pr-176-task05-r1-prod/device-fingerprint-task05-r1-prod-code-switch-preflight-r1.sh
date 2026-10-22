#!/usr/bin/env bash
set -Eeuo pipefail
export SYSTEMD_PAGER=cat
export PAGER=cat

PORTAL="/opt/CaptivePortal"
CFG="/etc/default/captive-portal"
VENV_PY="/opt/captiveportal-runtime/device-fingerprint-venv/bin/python"

OLD_HEAD="1d88f4ae947fa95454dbb54c70f9d6bdd13b1d22"
OLD_TREE="8183bf48abfc71c1b488c0667efc0f1ae717003e"
TARGET_HEAD="97bd1cf924024a38cc3229bfd726a25fe6754b07"
TARGET_TREE="545a48caf86adc247083db611e87a8d36820f353"

CONTROL_DB="/opt/CaptivePortal/data/device_fingerprint_control_plane.sqlite3"
INTEGRATION_DB="/opt/CaptivePortal/data/device_fingerprint_integration.sqlite3"
CONTROLLED_IID="77dcd849-8855-4dd4-b3ed-9d2c62d86935"

section(){ printf '\n===== %s =====\n' "$1"; }
fail(){ echo "FATAL: $*" >&2; exit 1; }

ORIGINAL_BRANCH=""
SWITCH_DONE=0
PORTAL_RESTARTED=0
ROLLBACK_USED=0

wait_active() {
  local unit="$1" timeout="${2:-30}" i
  for ((i=0; i<timeout; i++)); do
    if systemctl is-active --quiet "$unit"; then return 0; fi
    sleep 1
  done
  return 1
}

wait_loaded_identity() {
  local expected_head="$1" expected_tree="$2" since="$3" timeout="${4:-45}"
  local i line
  for ((i=0; i<timeout; i++)); do
    line="$(journalctl -u captive-portal.service --since "$since" --no-pager -o cat 2>/dev/null \
      | grep '"event":"captivportal_loaded_artifact_identity"' | tail -n1 || true)"
    if [ -n "$line" ]; then
      IDENTITY_LINE="$line" EXPECTED_HEAD="$expected_head" EXPECTED_TREE="$expected_tree" \
      /usr/bin/python3 - <<'PY'
import json, os
s=os.environ["IDENTITY_LINE"]
o=json.loads(s[s.index("{"):])
assert o["artifact_sha"] == os.environ["EXPECTED_HEAD"], o
assert o["artifact_tree"] == os.environ["EXPECTED_TREE"], o
assert o["service_name"] == "captive-portal.service", o
print("LOADED_ARTIFACT_SHA="+o["artifact_sha"])
print("LOADED_ARTIFACT_TREE="+o["artifact_tree"])
PY
      return 0
    fi
    sleep 1
  done
  return 1
}

restore_old_code() {
  ROLLBACK_USED=1
  echo "ROLLBACK: restoring $OLD_HEAD"
  if [ -n "$ORIGINAL_BRANCH" ]; then
    git -C "$PORTAL" checkout -q "$ORIGINAL_BRANCH" || true
    git -C "$PORTAL" reset --hard "$OLD_HEAD" || true
  else
    git -C "$PORTAL" checkout -q --detach "$OLD_HEAD" || true
  fi
  if [ "$PORTAL_RESTARTED" -eq 1 ] || [ "$SWITCH_DONE" -eq 1 ]; then
    systemctl restart captive-portal.service || true
  fi
}

on_error() {
  local rc=$?
  trap - ERR
  echo
  echo "===== AUTOMATIC ROLLBACK ====="
  restore_old_code
  echo "AUTOMATIC_ROLLBACK_USED=YES"
  echo "TASK05_R1_PROD_CODE_SWITCH_PREFLIGHT=FAIL"
  exit "$rc"
}
trap on_error ERR

[ "$(id -u)" -eq 0 ] || fail "Run with sudo/root"

section "DECLARATION"
date --iso-8601=seconds
echo "MODE=TASK05_R1_PROD_CODE_SWITCH_AND_READ_ONLY_PREFLIGHT"
echo "PRODUCTION_TARGET=/opt/CaptivePortal"
echo "CODE_SWITCH=YES"
echo "INTEGRATION_ACTIVATION=NO"
echo "WORKER_START=NO"
echo "WORKER_ENABLE=NO"
echo "CONFIG_WRITE=NO"
echo "DATABASE_WRITE_BY_SCRIPT=NO"
echo "SYSTEMD_UNIT_WRITE=NO"
echo "PORTAL_RESTART=YES"
echo "AUTOMATIC_ROLLBACK=YES"
echo "EXPECTED_OLD_HEAD=$OLD_HEAD"
echo "EXPECTED_TARGET_HEAD=$TARGET_HEAD"
echo "EXPECTED_TARGET_TREE=$TARGET_TREE"

section "CURRENT PRODUCTION HOLD"
CURRENT_HEAD="$(git -C "$PORTAL" rev-parse HEAD)"
CURRENT_TREE="$(git -C "$PORTAL" rev-parse 'HEAD^{tree}')"
CURRENT_STATUS="$(git -C "$PORTAL" status --porcelain=v1 --untracked-files=normal)"
ORIGINAL_BRANCH="$(git -C "$PORTAL" symbolic-ref -q --short HEAD || true)"
echo "CURRENT_HEAD=$CURRENT_HEAD"
echo "CURRENT_TREE=$CURRENT_TREE"
echo "CURRENT_BRANCH=${ORIGINAL_BRANCH:-DETACHED}"
[ "$CURRENT_HEAD" = "$OLD_HEAD" ] || fail "Unexpected production HEAD"
[ "$CURRENT_TREE" = "$OLD_TREE" ] || fail "Unexpected production tree"
[ -z "$CURRENT_STATUS" ] || { git -C "$PORTAL" status --short; fail "Production worktree dirty"; }

grep -qxF 'DEVICE_FINGERPRINT_INTEGRATION_ENABLED=false' "$CFG" \
  || fail "Task-05 integration HOLD flag is not exactly false"
systemctl is-active --quiet captive-portal.service || fail "Portal inactive before switch"
if systemctl is-active --quiet fingerprint-classification.service; then
  fail "Classification worker unexpectedly active"
fi
if systemctl is-enabled --quiet fingerprint-classification.service; then
  fail "Classification worker unexpectedly enabled"
fi
echo "TASK05_INTEGRATION_ENABLED=NO"
echo "TASK05_WORKER_ACTIVE=NO"
echo "TASK05_WORKER_ENABLED=NO"

PORTAL_NRESTARTS_BEFORE="$(systemctl show captive-portal.service -p NRestarts --value --no-pager)"
CONTROL_SHA_BEFORE="$(sha256sum "$CONTROL_DB" | awk '{print $1}')"
INTEGRATION_SHA_BEFORE="$(sha256sum "$INTEGRATION_DB" | awk '{print $1}')"
echo "PORTAL_NRESTARTS_BEFORE=$PORTAL_NRESTARTS_BEFORE"
echo "CONTROL_DB_SHA256_BEFORE=$CONTROL_SHA_BEFORE"
echo "INTEGRATION_DB_SHA256_BEFORE=$INTEGRATION_SHA_BEFORE"

INTEGRATION_DB="$INTEGRATION_DB" IID="$CONTROLLED_IID" /usr/bin/python3 - <<'PY'
import os, sqlite3
con=sqlite3.connect(f"file:{os.environ['INTEGRATION_DB']}?mode=ro", uri=True)
con.row_factory=sqlite3.Row
try:
    q=con.execute("PRAGMA quick_check").fetchone()[0]
    r=con.execute(
        "SELECT classification_state,last_reason_code,identity_state,"
        "registry_snapshot_id,device_id,visit_id "
        "FROM integration_jobs WHERE integration_id=?",
        (os.environ["IID"],)
    ).fetchone()
finally:
    con.close()
print("INTEGRATION_QUICK_CHECK="+str(q))
if q != "ok":
    raise SystemExit("FATAL: integration DB quick_check failed")
if r is None:
    raise SystemExit("FATAL: controlled failed job missing")
for k in r.keys():
    print("CONTROLLED_"+k.upper()+"="+("" if r[k] is None else str(r[k])))
if (r["classification_state"], r["last_reason_code"], r["identity_state"]) != (
    "NO_RESULT_FINAL", "runtime_profile_incompatible", "DEVICE_AND_VISIT_RESOLVED"
):
    raise SystemExit("FATAL: preserved failure evidence changed")
PY
echo "PRODUCTION_HOLD=PASS"

section "VERIFY MERGED MAIN"
REMOTE_MAIN="$(git -C "$PORTAL" ls-remote origin refs/heads/main | awk '{print $1}')"
echo "REMOTE_MAIN_HEAD=$REMOTE_MAIN"
[ "$REMOTE_MAIN" = "$TARGET_HEAD" ] || fail "origin/main is not expected merged repair commit"

git -C "$PORTAL" fetch --no-tags origin refs/heads/main
git -C "$PORTAL" cat-file -e "$TARGET_HEAD^{commit}"
FETCHED_TREE="$(git -C "$PORTAL" rev-parse "$TARGET_HEAD^{tree}")"
echo "FETCHED_TARGET_TREE=$FETCHED_TREE"
[ "$FETCHED_TREE" = "$TARGET_TREE" ] || fail "Merged target tree mismatch"

PARENTS="$(git -C "$PORTAL" show -s --format='%P' "$TARGET_HEAD")"
echo "TARGET_PARENTS=$PARENTS"
case " $PARENTS " in
  *" $OLD_HEAD "*" 1bb7f73d9977c457da05af26bf28b30c3c7e06d8 "*) ;;
  *) fail "Merge commit parents do not match expected old production + accepted candidate" ;;
esac

CHANGED="$(git -C "$PORTAL" diff --name-only "$OLD_HEAD" "$TARGET_HEAD")"
printf 'TARGET_CHANGED_FILES:\n%s\n' "$CHANGED"
EXPECTED=$'app/device_fingerprint_integration/compatibility.py\ntests/device_fingerprint_integration/test_executor_persistence.py'
[ "$CHANGED" = "$EXPECTED" ] || fail "Merged target contains unexpected file changes"
echo "MERGED_MAIN_IDENTITY=PASS"

section "SWITCH PRODUCTION CODE WHILE HOLD REMAINS"
if [ -n "$ORIGINAL_BRANCH" ]; then
  git -C "$PORTAL" reset --hard "$TARGET_HEAD"
else
  git -C "$PORTAL" checkout -q --detach "$TARGET_HEAD"
fi
SWITCH_DONE=1

NEW_HEAD="$(git -C "$PORTAL" rev-parse HEAD)"
NEW_TREE="$(git -C "$PORTAL" rev-parse 'HEAD^{tree}')"
NEW_STATUS="$(git -C "$PORTAL" status --porcelain=v1 --untracked-files=normal)"
echo "NEW_HEAD=$NEW_HEAD"
echo "NEW_TREE=$NEW_TREE"
[ "$NEW_HEAD" = "$TARGET_HEAD" ] || fail "Production HEAD switch failed"
[ "$NEW_TREE" = "$TARGET_TREE" ] || fail "Production tree switch failed"
[ -z "$NEW_STATUS" ] || fail "Production worktree dirty after switch"
grep -qxF 'DEVICE_FINGERPRINT_INTEGRATION_ENABLED=false' "$CFG" \
  || fail "Integration HOLD changed during code switch"
echo "CODE_SWITCH=PASS"

section "RESTART PORTAL WITH INTEGRATION STILL DISABLED"
SINCE="$(date -d '2 seconds ago' '+%Y-%m-%d %H:%M:%S')"
PORTAL_RESTARTED=1
systemctl restart captive-portal.service
wait_active captive-portal.service 30 || fail "Portal failed to become active"
wait_loaded_identity "$TARGET_HEAD" "$TARGET_TREE" "$SINCE" 45 \
  || fail "Fresh target artifact identity not observed"

sleep 3
PORTAL_NRESTARTS_AFTER_RESTART="$(systemctl show captive-portal.service -p NRestarts --value --no-pager)"
echo "PORTAL_NRESTARTS_AFTER_RESTART=$PORTAL_NRESTARTS_AFTER_RESTART"
[ "$PORTAL_NRESTARTS_AFTER_RESTART" = "0" ] || fail "Portal entered automatic restart loop"
grep -qxF 'DEVICE_FINGERPRINT_INTEGRATION_ENABLED=false' "$CFG" \
  || fail "Integration unexpectedly enabled"
if systemctl is-active --quiet fingerprint-classification.service; then
  fail "Worker unexpectedly active"
fi
echo "PORTAL_TARGET_RUNTIME_HOLD=PASS"

section "REAL PRODUCTION CONTROL-PLANE PREFLIGHT"
sudo -u admin env \
  HOME=/nonexistent \
  PYTHONPATH="$PORTAL" \
  PYTHONDONTWRITEBYTECODE=1 \
  CONTROL_DB="$CONTROL_DB" \
  "$VENV_PY" -B - <<'PY'
import os
from app.device_fingerprint.control_plane_store import DeviceFingerprintControlPlaneStore
from app.device_fingerprint_integration.compatibility import (
    ReadOnlyControlPlaneStoreMixin, preflight,
)

class ReadOnlyControl(ReadOnlyControlPlaneStoreMixin, DeviceFingerprintControlPlaneStore):
    pass

control=ReadOnlyControl(os.environ["CONTROL_DB"])
prepared=preflight(control)
print("PREFLIGHT_PROFILE_ID="+prepared.pin.runtime_profile.artifact_id)
print("PREFLIGHT_RPM_ID="+prepared.pin.admission_manifest.artifact_id)
print("PREFLIGHT_VALIDITY="+prepared.pin.validity_record.semantic_payload["state"])
print("REAL_PRODUCTION_PREFLIGHT=PASS")
PY

section "POSTCONDITIONS"
FINAL_HEAD="$(git -C "$PORTAL" rev-parse HEAD)"
FINAL_TREE="$(git -C "$PORTAL" rev-parse 'HEAD^{tree}')"
FINAL_STATUS="$(git -C "$PORTAL" status --porcelain=v1 --untracked-files=normal)"
[ "$FINAL_HEAD" = "$TARGET_HEAD" ] || fail "Final production HEAD mismatch"
[ "$FINAL_TREE" = "$TARGET_TREE" ] || fail "Final production tree mismatch"
[ -z "$FINAL_STATUS" ] || fail "Final production worktree dirty"

grep -qxF 'DEVICE_FINGERPRINT_INTEGRATION_ENABLED=false' "$CFG" \
  || fail "Final integration HOLD flag not false"
if systemctl is-active --quiet fingerprint-classification.service; then
  fail "Worker active at end of HOLD gate"
fi
if systemctl is-enabled --quiet fingerprint-classification.service; then
  fail "Worker enabled at end of HOLD gate"
fi

CONTROL_SHA_AFTER="$(sha256sum "$CONTROL_DB" | awk '{print $1}')"
INTEGRATION_SHA_AFTER="$(sha256sum "$INTEGRATION_DB" | awk '{print $1}')"
PORTAL_NRESTARTS_FINAL="$(systemctl show captive-portal.service -p NRestarts --value --no-pager)"
echo "CONTROL_DB_SHA256_AFTER=$CONTROL_SHA_AFTER"
echo "INTEGRATION_DB_SHA256_AFTER=$INTEGRATION_SHA_AFTER"
echo "PORTAL_NRESTARTS_FINAL=$PORTAL_NRESTARTS_FINAL"

[ "$CONTROL_SHA_AFTER" = "$CONTROL_SHA_BEFORE" ] || fail "Control-plane DB changed during read-only gate"
[ "$INTEGRATION_SHA_AFTER" = "$INTEGRATION_SHA_BEFORE" ] || fail "Integration DB changed during HOLD gate"
[ "$PORTAL_NRESTARTS_FINAL" = "0" ] || fail "Portal automatic restart count non-zero"

section "FINAL"
echo "PRODUCTION_HEAD=$FINAL_HEAD"
echo "PRODUCTION_TREE=$FINAL_TREE"
echo "TASK05_R1_CODE_SWITCH=PASS"
echo "TASK05_R1_REAL_PRODUCTION_PREFLIGHT=PASS"
echo "TASK05_INTEGRATION_ENABLED=NO"
echo "TASK05_WORKER_ACTIVE=NO"
echo "TASK05_WORKER_ENABLED_FOR_BOOT=NO"
echo "CONTROLLED_FAILURE_EVIDENCE_PRESERVED=YES"
echo "PRODUCTION_HOLD_PRESERVED=YES"
echo "AUTOMATIC_ROLLBACK_USED=$([ "$ROLLBACK_USED" -eq 1 ] && echo YES || echo NO)"
echo "TASK05_R1_PROD_CODE_SWITCH_PREFLIGHT=PASS"
