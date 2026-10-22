#!/usr/bin/env bash
set -Eeuo pipefail

REPO="/opt/CaptivePortal"
PORTAL_SERVICE="captive-portal.service"
WORKER_SERVICE="fingerprint-classification.service"

EXPECTED_OLD_HEAD="20ea385182972e8fb5b204815161bc6a5c7f13fb"
EXPECTED_OLD_TREE="439ab64697f2fcdcd5e822527f287ca5404e45ba"

TARGET_HEAD="7c7c0919c3e546f499b5252ea9479d32c8f494d7"
TARGET_TREE="dbf3e3804931d637ef1ec569128746ebce5c141a"

SITE_ID="6a64f17630da7c70d232187a"
OWNER_MAC="BE:00:7D:9B:04:2E"
CLASSIFICATION_DB="/opt/CaptivePortal/data/device_fingerprint_classification.sqlite3"
PYTHON_BIN="/opt/captiveportal-runtime/device-fingerprint-venv/bin/python"

DEPLOY_SWITCHED=0
OLD_HEAD=""
OLD_TREE=""

git_admin() {
  sudo -u admin -H git -C "$REPO" "$@"
}

rollback_on_error() {
  rc=$?
  trap - ERR
  echo
  echo "===== DEPLOY FAILURE ====="
  echo "EXIT_CODE=$rc"

  if [[ "$DEPLOY_SWITCHED" == "1" && -n "$OLD_HEAD" ]]; then
    echo "ROLLBACK=START"
    systemctl stop "$WORKER_SERVICE" || true
    systemctl stop "$PORTAL_SERVICE" || true
    git_admin checkout --detach "$OLD_HEAD" || true
    systemctl start "$PORTAL_SERVICE" || true
    systemctl start "$WORKER_SERVICE" || true
    echo "ROLLBACK_HEAD=$(git_admin rev-parse HEAD 2>/dev/null || true)"
    echo "ROLLBACK_TREE=$(git_admin rev-parse 'HEAD^{tree}' 2>/dev/null || true)"
    echo "ROLLBACK_PORTAL=$(systemctl is-active "$PORTAL_SERVICE" 2>/dev/null || true)"
    echo "ROLLBACK_WORKER=$(systemctl is-active "$WORKER_SERVICE" 2>/dev/null || true)"
    echo "ROLLBACK=ATTEMPTED"
  else
    echo "ROLLBACK=NOT_REQUIRED"
  fi
  exit "$rc"
}
trap rollback_on_error ERR

echo "===== TASK06 PRODUCTION DEPLOY ====="
echo "TARGET_HEAD=$TARGET_HEAD"
echo "TARGET_TREE=$TARGET_TREE"
echo "FULL_PYTEST_ON_PRODUCTION=NO"
echo "DB_MIGRATION=NO"
echo "CONTROL_PLANE_ACTIVATION=NO"
echo "CLASSIFIER_ADMISSION_CHANGE=NO"
echo "LOCAL_SOURCE_PATCH=NO"
echo

test -d "$REPO/.git"
test -x "$PYTHON_BIN"
test -f "$CLASSIFICATION_DB"

OLD_HEAD="$(git_admin rev-parse HEAD)"
OLD_TREE="$(git_admin rev-parse 'HEAD^{tree}')"

echo "CURRENT_HEAD=$OLD_HEAD"
echo "CURRENT_TREE=$OLD_TREE"

if [[ -n "$(git_admin status --porcelain)" ]]; then
  echo "ERROR=PRODUCTION_WORKTREE_DIRTY"
  exit 21
fi

if [[ "$OLD_HEAD" != "$EXPECTED_OLD_HEAD" && "$OLD_HEAD" != "$TARGET_HEAD" ]]; then
  echo "ERROR=UNEXPECTED_PRODUCTION_HEAD"
  exit 22
fi

if [[ "$OLD_HEAD" == "$EXPECTED_OLD_HEAD" && "$OLD_TREE" != "$EXPECTED_OLD_TREE" ]]; then
  echo "ERROR=UNEXPECTED_OLD_TREE"
  exit 23
fi

if [[ "$OLD_HEAD" == "$TARGET_HEAD" && "$OLD_TREE" != "$TARGET_TREE" ]]; then
  echo "ERROR=TARGET_HEAD_WRONG_TREE"
  exit 24
fi

echo
echo "===== FETCH / EXACT MERGED IDENTITY ====="
git_admin fetch --prune origin main

REMOTE_MAIN="$(git_admin rev-parse origin/main)"
echo "ORIGIN_MAIN=$REMOTE_MAIN"
[[ "$REMOTE_MAIN" == "$TARGET_HEAD" ]] || { echo "ERROR=ORIGIN_MAIN_NOT_EXPECTED_MERGE"; exit 25; }

CANDIDATE_TREE="$(git_admin rev-parse "${TARGET_HEAD}^{tree}")"
echo "TARGET_RESOLVED_TREE=$CANDIDATE_TREE"
[[ "$CANDIDATE_TREE" == "$TARGET_TREE" ]] || { echo "ERROR=TARGET_TREE_MISMATCH"; exit 26; }

echo
echo "===== PRE-DEPLOY SERVICES ====="
echo "PORTAL=$(systemctl is-active "$PORTAL_SERVICE")"
echo "WORKER=$(systemctl is-active "$WORKER_SERVICE")"
systemctl is-active --quiet "$PORTAL_SERVICE"
systemctl is-active --quiet "$WORKER_SERVICE"

if [[ "$OLD_HEAD" != "$TARGET_HEAD" ]]; then
  echo
  echo "===== QUIESCE / EXACT CODE SWITCH ====="
  systemctl stop "$WORKER_SERVICE"
  systemctl stop "$PORTAL_SERVICE"
  echo "WORKER_AFTER_STOP=$(systemctl is-active "$WORKER_SERVICE" || true)"
  echo "PORTAL_AFTER_STOP=$(systemctl is-active "$PORTAL_SERVICE" || true)"

  git_admin checkout --detach "$TARGET_HEAD"
  DEPLOY_SWITCHED=1
else
  echo
  echo "CODE_SWITCH=ALREADY_AT_TARGET"
fi

NEW_HEAD="$(git_admin rev-parse HEAD)"
NEW_TREE="$(git_admin rev-parse 'HEAD^{tree}')"
echo "PRODUCTION_HEAD_AFTER_SWITCH=$NEW_HEAD"
echo "PRODUCTION_TREE_AFTER_SWITCH=$NEW_TREE"
[[ "$NEW_HEAD" == "$TARGET_HEAD" ]]
[[ "$NEW_TREE" == "$TARGET_TREE" ]]
[[ -z "$(git_admin status --porcelain)" ]]
echo "EXACT_CODE_SWITCH=PASS"

echo
echo "===== START SERVICES ====="
systemctl start "$PORTAL_SERVICE"
systemctl start "$WORKER_SERVICE"
sleep 3

PORTAL_STATE="$(systemctl is-active "$PORTAL_SERVICE")"
WORKER_STATE="$(systemctl is-active "$WORKER_SERVICE")"
WORKER_PID="$(systemctl show "$WORKER_SERVICE" -p MainPID --value)"
WORKER_RESTARTS="$(systemctl show "$WORKER_SERVICE" -p NRestarts --value)"

echo "PORTAL_STATE=$PORTAL_STATE"
echo "WORKER_STATE=$WORKER_STATE"
echo "WORKER_PID=$WORKER_PID"
echo "WORKER_NRESTARTS=$WORKER_RESTARTS"

[[ "$PORTAL_STATE" == "active" ]]
[[ "$WORKER_STATE" == "active" ]]
[[ "$WORKER_PID" =~ ^[1-9][0-9]*$ ]]

echo
echo "===== TASK06 READ-ONLY FINGERPRINT SMOKE ====="
export PYTHONPATH="$REPO"
export PYTHONPYCACHEPREFIX="/tmp/captivportal-task06-deploy-pyc-$$"

"$PYTHON_BIN" - <<PY
from app.device_fingerprint.classification_read import DeviceFingerprintClassificationReadService
from app.admin_web.device_fingerprint_presentation import present_classification

db = r"$CLASSIFICATION_DB"
site = r"$SITE_ID"
mac = r"$OWNER_MAC"

reader = DeviceFingerprintClassificationReadService(db)

single = reader.get_current_production(site, mac)
if single is None:
    raise SystemExit("TASK06_SMOKE_FAIL=no_production_classification_for_owner_phone")

batch = reader.get_current_production_many(site, [mac])
if set(batch) != {mac} or batch[mac] is None:
    raise SystemExit("TASK06_SMOKE_FAIL=batch_read_missing_owner_phone")

if batch[mac].core.classification_id != single.core.classification_id:
    raise SystemExit("TASK06_SMOKE_FAIL=single_batch_mismatch")

presentation = present_classification(single)
if presentation.state != "classified":
    raise SystemExit(f"TASK06_SMOKE_FAIL=unexpected_presentation_state:{presentation.state}")

print("TASK06_SMOKE=PASS")
print("CLASSIFICATION_ID=" + single.core.classification_id)
print("CLASSIFICATION_RESULT_ID=" + single.core.classification_result_id)
print("GLOBAL_STATUS=" + str(presentation.global_classification_status))
print("TYPE=" + presentation.device_class_result.value)
print("FINGERPRINT_PLATFORM=" + presentation.platform_result.value)
print("MANUFACTURER=" + presentation.manufacturer_result.value)
print("MODEL_FAMILY=" + presentation.model_result.value)
PY

rm -rf "$PYTHONPYCACHEPREFIX" || true
unset PYTHONPYCACHEPREFIX

echo
echo "===== RECENT SERVICE LOGS ====="
echo "--- portal ---"
journalctl -u "$PORTAL_SERVICE" --since "-2 minutes" --no-pager | tail -40 || true
echo "--- fingerprint worker ---"
journalctl -u "$WORKER_SERVICE" --since "-2 minutes" --no-pager | tail -60 || true

echo
echo "===== FINAL ====="
FINAL_HEAD="$(git_admin rev-parse HEAD)"
FINAL_TREE="$(git_admin rev-parse 'HEAD^{tree}')"
echo "PRODUCTION_HEAD=$FINAL_HEAD"
echo "PRODUCTION_TREE=$FINAL_TREE"
echo "PORTAL_STATE=$(systemctl is-active "$PORTAL_SERVICE")"
echo "WORKER_STATE=$(systemctl is-active "$WORKER_SERVICE")"

[[ "$FINAL_HEAD" == "$TARGET_HEAD" ]]
[[ "$FINAL_TREE" == "$TARGET_TREE" ]]
systemctl is-active --quiet "$PORTAL_SERVICE"
systemctl is-active --quiet "$WORKER_SERVICE"

trap - ERR
echo "TASK06_PRODUCTION_DEPLOY=PASS"
echo "NEXT=OPEN_ADMIN_HOME_AND_DEVICE_CARD_FOR_VISUAL_ACCEPTANCE"
