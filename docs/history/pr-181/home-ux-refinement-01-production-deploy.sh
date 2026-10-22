#!/usr/bin/env bash
set -Eeuo pipefail

REPO="/opt/CaptivePortal"
PORTAL_SERVICE="captive-portal.service"

OLD_RUNTIME_HEAD="7c7c0919c3e546f499b5252ea9479d32c8f494d7"
OLD_RUNTIME_TREE="dbf3e3804931d637ef1ec569128746ebce5c141a"

DOCS_MAIN_HEAD="c2635b467dc83e3f574ed204184a2e982f925a9a"
DOCS_MAIN_TREE="bb1d5f7951d77e8a65a6af4856b07d80fc9122f0"

TARGET_HEAD="c8d8d620dfed06caee92a498b891bf2faa37a6a9"
TARGET_TREE="be3470c378180aa215d527c6de6b686583ae0d79"

CLASSIFICATION_DB="/opt/CaptivePortal/data/device_fingerprint_classification.sqlite3"
PYTHON_BIN="/opt/captiveportal-runtime/device-fingerprint-venv/bin/python"

SITE_ID="6a64f17630da7c70d232187a"
OWNER_MAC="BE:00:7D:9B:04:2E"

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
    systemctl stop "$PORTAL_SERVICE" || true
    git_admin checkout --detach "$OLD_HEAD" || true
    systemctl start "$PORTAL_SERVICE" || true
    echo "ROLLBACK_HEAD=$(git_admin rev-parse HEAD 2>/dev/null || true)"
    echo "ROLLBACK_TREE=$(git_admin rev-parse 'HEAD^{tree}' 2>/dev/null || true)"
    echo "ROLLBACK_PORTAL=$(systemctl is-active "$PORTAL_SERVICE" 2>/dev/null || true)"
    echo "ROLLBACK=ATTEMPTED"
  else
    echo "ROLLBACK=NOT_REQUIRED"
  fi
  exit "$rc"
}
trap rollback_on_error ERR

echo "===== HOME-UX-REFINEMENT-01 PRODUCTION DEPLOY ====="
echo "TARGET_HEAD=$TARGET_HEAD"
echo "TARGET_TREE=$TARGET_TREE"
echo "FULL_PYTEST_ON_PRODUCTION=NO"
echo "DB_MIGRATION=NO"
echo "CLASSIFIER_ADMISSION_CHANGE=NO"
echo "FINGERPRINT_SERVICE_RESTART=NO"
echo "SURICATA_RESTART=NO"
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

case "$OLD_HEAD" in
  "$OLD_RUNTIME_HEAD")
    [[ "$OLD_TREE" == "$OLD_RUNTIME_TREE" ]] || { echo "ERROR=OLD_RUNTIME_TREE_MISMATCH"; exit 22; }
    ;;
  "$DOCS_MAIN_HEAD")
    [[ "$OLD_TREE" == "$DOCS_MAIN_TREE" ]] || { echo "ERROR=DOCS_MAIN_TREE_MISMATCH"; exit 23; }
    ;;
  "$TARGET_HEAD")
    [[ "$OLD_TREE" == "$TARGET_TREE" ]] || { echo "ERROR=TARGET_TREE_MISMATCH_LOCAL"; exit 24; }
    ;;
  *)
    echo "ERROR=UNEXPECTED_PRODUCTION_HEAD"
    exit 25
    ;;
esac

echo
echo "===== FETCH / EXACT MERGED IDENTITY ====="
git_admin fetch --prune origin main

REMOTE_MAIN="$(git_admin rev-parse origin/main)"
REMOTE_TREE="$(git_admin rev-parse 'origin/main^{tree}')"

echo "ORIGIN_MAIN=$REMOTE_MAIN"
echo "ORIGIN_MAIN_TREE=$REMOTE_TREE"

[[ "$REMOTE_MAIN" == "$TARGET_HEAD" ]] || { echo "ERROR=ORIGIN_MAIN_NOT_EXPECTED_MERGE"; exit 26; }
[[ "$REMOTE_TREE" == "$TARGET_TREE" ]] || { echo "ERROR=ORIGIN_MAIN_TREE_MISMATCH"; exit 27; }

echo
echo "===== PRE-DEPLOY PORTAL ====="
PORTAL_BEFORE="$(systemctl is-active "$PORTAL_SERVICE")"
echo "PORTAL_BEFORE=$PORTAL_BEFORE"
[[ "$PORTAL_BEFORE" == "active" ]]

if [[ "$OLD_HEAD" != "$TARGET_HEAD" ]]; then
  echo
  echo "===== QUIESCE / EXACT CODE SWITCH ====="
  systemctl stop "$PORTAL_SERVICE"
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
echo "===== TARGETED PYTHON IMPORT / PRESENTATION SMOKE ====="
export PYTHONPATH="$REPO"
export PYTHONPYCACHEPREFIX="/tmp/captivportal-home-ux-pyc-$$"

"$PYTHON_BIN" -m py_compile \
  "$REPO/app/admin_web/device_fingerprint_presentation.py" \
  "$REPO/app/admin_web/query_service.py"

"$PYTHON_BIN" - <<'PY'
from app.admin_web.device_fingerprint_presentation import home_platform_presentation

def fp(state, status=None, canonical=None, value="—"):
    return {
        "state": state,
        "status": status,
        "canonical_value_id": canonical,
        "value": value,
    }

cases = [
    (
        "controller_wins",
        home_platform_presentation(
            "Android", "android",
            fp("classified", "resolved", "chromeos", "ChromeOS"),
        ),
        {"source": "controller", "value": "Android", "key": "android"},
    ),
    (
        "fingerprint_fallback",
        home_platform_presentation(
            "Unknown", "unknown",
            fp("classified", "resolved", "android", "Android"),
        ),
        {"source": "fingerprint", "value": "Android", "key": "android"},
    ),
    (
        "fingerprint_unresolved",
        home_platform_presentation(
            None, None,
            fp("classified", "conflicting_evidence", None, "Unknown"),
        ),
        {"source": "none", "value": "Unknown", "key": None},
    ),
    (
        "no_result",
        home_platform_presentation(
            None, None,
            fp("no_result"),
        ),
        {"source": "none", "value": "—", "key": None},
    ),
]

for name, actual, expected in cases:
    if actual != expected:
        raise SystemExit(f"HOME_PLATFORM_SMOKE_FAIL:{name}:{actual!r}")
    print(f"{name}=PASS")

print("HOME_PLATFORM_PRESENTATION_SMOKE=PASS")
PY

echo
echo "===== REAL PRODUCTION FINGERPRINT READ SMOKE ====="
"$PYTHON_BIN" - <<PY
from app.device_fingerprint.classification_read import DeviceFingerprintClassificationReadService
from app.admin_web.device_fingerprint_presentation import present_classification

db = r"$CLASSIFICATION_DB"
site = r"$SITE_ID"
mac = r"$OWNER_MAC"

reader = DeviceFingerprintClassificationReadService(db)
record = reader.get_current_production(site, mac)

if record is None:
    print("REAL_FINGERPRINT_RESULT=NO_RESULT")
else:
    projection = present_classification(record)
    compact = projection.compact_platform()
    print("REAL_FINGERPRINT_RESULT=FOUND")
    print("CLASSIFICATION_ID=" + record.core.classification_id)
    print("FINGERPRINT_PLATFORM_STATE=" + str(compact["state"]))
    print("FINGERPRINT_PLATFORM_STATUS=" + str(compact["status"]))
    print("FINGERPRINT_PLATFORM_CANONICAL=" + str(compact["canonical_value_id"]))
    print("FINGERPRINT_PLATFORM_VALUE=" + str(compact["value"]))

print("REAL_FINGERPRINT_READ_SMOKE=PASS")
PY

rm -rf "$PYTHONPYCACHEPREFIX" || true
unset PYTHONPYCACHEPREFIX

echo
echo "===== START PORTAL ====="
systemctl start "$PORTAL_SERVICE"
sleep 3

PORTAL_AFTER="$(systemctl is-active "$PORTAL_SERVICE")"
PORTAL_PID="$(systemctl show "$PORTAL_SERVICE" -p MainPID --value)"
PORTAL_RESTARTS="$(systemctl show "$PORTAL_SERVICE" -p NRestarts --value)"

echo "PORTAL_AFTER=$PORTAL_AFTER"
echo "PORTAL_PID=$PORTAL_PID"
echo "PORTAL_NRESTARTS=$PORTAL_RESTARTS"

[[ "$PORTAL_AFTER" == "active" ]]
[[ "$PORTAL_PID" =~ ^[1-9][0-9]*$ ]]

echo
echo "===== UNTOUCHED FINGERPRINT SERVICES ====="
for svc in fingerprint-classification.service fingerprint-sensor.service fingerprint-suricata.service; do
  state="$(systemctl is-active "$svc" 2>/dev/null || true)"
  echo "$svc=$state"
done

echo
echo "===== RECENT PORTAL LOGS ====="
journalctl -u "$PORTAL_SERVICE" --since "-3 minutes" --no-pager | tail -80 || true

echo
echo "===== FINAL ====="
FINAL_HEAD="$(git_admin rev-parse HEAD)"
FINAL_TREE="$(git_admin rev-parse 'HEAD^{tree}')"

echo "PRODUCTION_HEAD=$FINAL_HEAD"
echo "PRODUCTION_TREE=$FINAL_TREE"
echo "PORTAL_STATE=$(systemctl is-active "$PORTAL_SERVICE")"

[[ "$FINAL_HEAD" == "$TARGET_HEAD" ]]
[[ "$FINAL_TREE" == "$TARGET_TREE" ]]
systemctl is-active --quiet "$PORTAL_SERVICE"

trap - ERR
echo "HOME_UX_REFINEMENT_01_DEPLOY=PASS"
echo "NEXT=OWNER_VISUAL_PRODUCTION_ACCEPTANCE"
