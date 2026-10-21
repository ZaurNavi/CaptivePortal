#!/usr/bin/env bash
set -Eeuo pipefail

TARGET_SHA="fecdb5a7c79e56bb49be4797ca875d6720670042"
TARGET_TREE="85d7d41e1ad19c079cad0ae819a3fe38a068e242"

APP="/opt/CaptivePortal"
WT="/home/admin/CaptivePortal-Deploy/task04-dormant-fecdb5a7"
DATA_DIR="/opt/CaptivePortal/data"
EVIDENCE_DB="${DATA_DIR}/device_fingerprint_evidence.sqlite3"
CLASS_DB="${DATA_DIR}/device_fingerprint_classification.sqlite3"
CONTROL_DB="${DATA_DIR}/device_fingerprint_control_plane.sqlite3"

REPORT="/home/admin/device-fingerprint-task04-dormant-deploy.txt"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
MANIFEST="/home/admin/captivportal-recovery/task04-dormant-${STAMP}"

SITE_ID="6a64f17630da7c70d232187a"
TEST_MAC="02:00:00:00:00:01"
FROM_UTC="2026-10-03T00:00:00.000Z"
TO_UTC="2026-10-04T00:00:00.000Z"

CREATED_CLASS_DB=0

exec > >(tee "$REPORT") 2>&1

step(){ printf '\n===== %s =====\n' "$1"; }
die(){ echo "FATAL: $*" >&2; exit 1; }

cleanup_on_error() {
  rc=$?
  if [ "$rc" -ne 0 ]; then
    echo
    echo "===== ABORT / CLEANUP ====="
    echo "EXIT_CODE=$rc"
    if [ "$CREATED_CLASS_DB" -eq 1 ]; then
      rm -f "$CLASS_DB" "$CLASS_DB-wal" "$CLASS_DB-shm"
      echo "NEW_CLASSIFICATION_DB_REMOVED=YES"
    fi
    echo "CLASSIFICATION_ACTIVATION=NO"
    echo "CONTROL_PLANE_CREATED=NO"
  fi
  exit "$rc"
}
trap cleanup_on_error EXIT

[ "$(id -u)" -eq 0 ] || die "Run with sudo/root."
[ -d "$APP/.git" ] || [ -f "$APP/.git" ] || die "$APP is not a Git worktree."
[ -d "$DATA_DIR" ] || die "Missing production data directory: $DATA_DIR"
[ -f "$EVIDENCE_DB" ] || die "Task-01 evidence DB is missing: $EVIDENCE_DB"

step "DORMANT DEPLOYMENT SAFETY"
date -Is
echo "TARGET_SHA=$TARGET_SHA"
echo "TARGET_TREE=$TARGET_TREE"
echo "WORKTREE=$WT"
echo "CLASS_DB=$CLASS_DB"
echo "CONTROL_DB=$CONTROL_DB"
echo "CLASSIFICATION_ACTIVATION=NO"
echo "CLASSIFICATION_DAEMON=NO"
echo "CAPTIVE_PORTAL_RESTART=NO"
echo "EVIDENCE_RESTART=NO"
echo "SENSOR_RESTART=NO"
echo "SURICATA_RESTART=NO"

PORTAL_PID_BEFORE="$(systemctl show captive-portal.service -p MainPID --value)"
EVIDENCE_PID_BEFORE="$(systemctl show fingerprint-evidence.service -p MainPID --value)"
SENSOR_PID_BEFORE="$(systemctl show fingerprint-sensor.service -p MainPID --value)"
SURICATA_PID_BEFORE="$(systemctl show fingerprint-suricata.service -p MainPID --value)"

for u in captive-portal.service fingerprint-evidence.service fingerprint-sensor.service fingerprint-suricata.service; do
  echo "--- $u"
  systemctl show "$u" -p ActiveState -p SubState -p MainPID -p NRestarts --no-pager
  systemctl is-active --quiet "$u" || die "$u is not active."
done

if [ -e "$CLASS_DB" ] || [ -e "$CLASS_DB-wal" ] || [ -e "$CLASS_DB-shm" ]; then
  ls -l "$CLASS_DB"* 2>/dev/null || true
  die "Classification DB already exists; refusing non-idempotent first deployment."
fi

if [ -e "$CONTROL_DB" ] || [ -e "$CONTROL_DB-wal" ] || [ -e "$CONTROL_DB-shm" ]; then
  ls -l "$CONTROL_DB"* 2>/dev/null || true
  die "Production classification control-plane DB unexpectedly exists."
fi

echo "CLASSIFICATION_DB_PRESTATE=ABSENT"
echo "CONTROL_PLANE_PRESTATE=ABSENT"

step "VERIFY EXACT OWNER-MERGED GIT TARGET"
sudo -u admin git -C "$APP" fetch --prune origin '+refs/heads/main:refs/remotes/origin/main'
REMOTE_MAIN="$(sudo -u admin git -C "$APP" rev-parse refs/remotes/origin/main)"
REMOTE_TREE="$(sudo -u admin git -C "$APP" rev-parse "${TARGET_SHA}^{tree}")"
echo "ORIGIN_MAIN=$REMOTE_MAIN"
echo "TARGET_SHA_TREE=$REMOTE_TREE"
[ "$REMOTE_MAIN" = "$TARGET_SHA" ] || die "origin/main moved away from approved Task-04 deployment baseline."
[ "$REMOTE_TREE" = "$TARGET_TREE" ] || die "Task-04 deployment tree mismatch."
echo "GIT_PROVENANCE=PASS"

step "MATERIALIZE DORMANT TASK-04 CODE"
install -d -o admin -g admin /home/admin/CaptivePortal-Deploy
if [ -e "$WT" ]; then
  [ -e "$WT/.git" ] || die "Target worktree path exists but is not a Git worktree."
else
  sudo -u admin git -C "$APP" worktree add --detach "$WT" "$TARGET_SHA"
fi

WT_HEAD="$(sudo -u admin git -C "$WT" rev-parse HEAD)"
WT_TREE="$(sudo -u admin git -C "$WT" rev-parse 'HEAD^{tree}')"
echo "WORKTREE_HEAD=$WT_HEAD"
echo "WORKTREE_TREE=$WT_TREE"
[ "$WT_HEAD" = "$TARGET_SHA" ] || die "Dormant worktree HEAD mismatch."
[ "$WT_TREE" = "$TARGET_TREE" ] || die "Dormant worktree tree mismatch."
[ -z "$(sudo -u admin git -C "$WT" status --porcelain=v1)" ] || die "Dormant worktree is dirty."
echo "WORKTREE_CLEAN=YES"

step "STATIC IMPORT / COMPILE SMOKE"
PYC="/tmp/task04-dormant-pyc-${STAMP}"
install -d -o admin -g admin "$PYC"
sudo -u admin env PYTHONPYCACHEPREFIX="$PYC" PYTHONPATH="$WT" /usr/bin/python3 -m compileall -q \
  "$WT/app/device_fingerprint/classification_persistence.py" \
  "$WT/app/device_fingerprint/classification_read.py" \
  "$WT/app/device_fingerprint/control_plane_store.py" \
  "$WT/app/device_fingerprint/request_assembly.py"
sudo -u admin env PYTHONPYCACHEPREFIX="$PYC" PYTHONPATH="$WT" /usr/bin/python3 - <<'PY'
from app.device_fingerprint.classification_persistence import DeviceFingerprintClassificationStore
from app.device_fingerprint.classification_read import DeviceFingerprintClassificationReadService
from app.device_fingerprint.control_plane_store import DeviceFingerprintControlPlaneStore
from app.device_fingerprint.request_assembly import DeviceFingerprintRequestAssembly
print("TASK04_IMPORT_SMOKE=PASS")
PY
rm -rf "$PYC"
echo "TASK04_COMPILE_IMPORT=PASS"

step "CREATE DORMANT CLASSIFICATION SQLITE ONLY"
install -d -o admin -g admin "$MANIFEST"
{
  echo "TARGET_SHA=$TARGET_SHA"
  echo "TARGET_TREE=$TARGET_TREE"
  echo "EVIDENCE_DB=$EVIDENCE_DB"
  echo "CLASS_DB=$CLASS_DB"
  echo "CONTROL_DB=$CONTROL_DB"
  stat -c 'EVIDENCE_DB bytes=%s owner=%U group=%G mode=%a mtime=%y' "$EVIDENCE_DB"
  sha256sum "$WT/app/device_fingerprint/classification_persistence.py" \
            "$WT/app/device_fingerprint/classification_read.py" \
            "$WT/app/device_fingerprint/control_plane_store.py" \
            "$WT/app/device_fingerprint/request_assembly.py"
} > "$MANIFEST/predeploy-manifest.txt"
chown -R admin:admin "$MANIFEST"

sudo -u admin env PYTHONPATH="$WT" \
  CLASS_DB="$CLASS_DB" EVIDENCE_DB="$EVIDENCE_DB" CONTROL_DB="$CONTROL_DB" \
  /usr/bin/python3 - <<'PY'
import os
from app.device_fingerprint.classification_persistence import DeviceFingerprintClassificationStore
from app.device_fingerprint.control_plane_store import DeviceFingerprintControlPlaneStore

control = DeviceFingerprintControlPlaneStore(os.environ["CONTROL_DB"])
store = DeviceFingerprintClassificationStore(
    os.environ["CLASS_DB"],
    os.environ["EVIDENCE_DB"],
    control_plane_store=control,
)
store.initialize()
print("CLASSIFICATION_STORE_INITIALIZE=PASS")
PY

CREATED_CLASS_DB=1
chmod 0640 "$CLASS_DB"
chown admin:admin "$CLASS_DB"

[ -f "$CLASS_DB" ] || die "Classification DB was not created."
[ ! -e "$CONTROL_DB" ] || die "Dormant initialization unexpectedly created control-plane DB."
echo "CONTROL_PLANE_CREATED=NO"
echo "ACTIVE_CLASSIFICATION_POINTER=IMPOSSIBLE_CONTROL_DB_ABSENT"

step "CLASSIFICATION SQLITE STRUCTURE"
sqlite3 "$CLASS_DB" <<'SQL'
.headers on
.mode list
SELECT 'quick_check' AS check_name, quick_check FROM pragma_quick_check;
SELECT name,type FROM sqlite_master
 WHERE type IN ('table','index')
 ORDER BY type,name;
SELECT 'artifacts' AS object_name, COUNT(*) AS rows FROM artifacts
UNION ALL SELECT 'artifact_dependencies', COUNT(*) FROM artifact_dependencies
UNION ALL SELECT 'classifications', COUNT(*) FROM classifications
UNION ALL SELECT 'classification_roots', COUNT(*) FROM classification_roots;
SQL

TABLE_COUNT="$(sqlite3 "$CLASS_DB" "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name IN ('artifacts','artifact_dependencies','classifications','classification_roots');")"
CLASS_COUNT="$(sqlite3 "$CLASS_DB" "SELECT COUNT(*) FROM classifications;")"
ARTIFACT_COUNT="$(sqlite3 "$CLASS_DB" "SELECT COUNT(*) FROM artifacts;")"
ROOT_COUNT="$(sqlite3 "$CLASS_DB" "SELECT COUNT(*) FROM classification_roots;")"

[ "$TABLE_COUNT" = "4" ] || die "Classification schema table count mismatch."
[ "$CLASS_COUNT" = "0" ] || die "Dormant DB unexpectedly contains classifications."
[ "$ARTIFACT_COUNT" = "0" ] || die "Dormant DB unexpectedly contains artifacts."
[ "$ROOT_COUNT" = "0" ] || die "Dormant DB unexpectedly contains classification roots."
echo "DORMANT_DB_EMPTY=PASS"

step "INTERNAL READ CONTRACT ON EMPTY DATABASE"
sudo -u admin env PYTHONPATH="$WT" \
  CLASS_DB="$CLASS_DB" SITE_ID="$SITE_ID" TEST_MAC="$TEST_MAC" \
  FROM_UTC="$FROM_UTC" TO_UTC="$TO_UTC" /usr/bin/python3 - <<'PY'
import os
from app.device_fingerprint.classification_read import DeviceFingerprintClassificationReadService

service = DeviceFingerprintClassificationReadService(os.environ["CLASS_DB"])
current = service.get_current(os.environ["SITE_ID"], os.environ["TEST_MAC"])
history = service.list_history(
    os.environ["SITE_ID"], os.environ["TEST_MAC"],
    os.environ["FROM_UTC"], os.environ["TO_UTC"], limit=100,
)
assert current is None, current
assert history.items == (), history
assert history.next_cursor is None, history
print("GET_CURRENT_EMPTY=PASS")
print("LIST_HISTORY_EMPTY=PASS")
print("INTERNAL_READ_CONTRACT=PASS")
PY

step "PROVE NO ACTIVATION / NO RUNTIME INTEGRATION"
[ ! -e "$CONTROL_DB" ] || die "Control plane unexpectedly exists."
if systemctl list-unit-files --type=service --no-legend \
  | awk '{print $1}' \
  | grep -Eq '^fingerprint-classification\.service$|^device-fingerprint-classification\.service$'; then
  die "Unexpected classification service unit exists."
fi
echo "CLASSIFICATION_SERVICE_UNIT=ABSENT"

if pgrep -af '[d]evice_fingerprint.*classification|[c]lassification.*device_fingerprint' >/tmp/task04-classification-processes.txt; then
  cat /tmp/task04-classification-processes.txt
  die "Unexpected classification runtime process exists."
else
  echo "CLASSIFICATION_PROCESS=ABSENT"
fi
rm -f /tmp/task04-classification-processes.txt

step "POST-DEPLOY SERVICE IMMUTABILITY"
PORTAL_PID_AFTER="$(systemctl show captive-portal.service -p MainPID --value)"
EVIDENCE_PID_AFTER="$(systemctl show fingerprint-evidence.service -p MainPID --value)"
SENSOR_PID_AFTER="$(systemctl show fingerprint-sensor.service -p MainPID --value)"
SURICATA_PID_AFTER="$(systemctl show fingerprint-suricata.service -p MainPID --value)"

for u in captive-portal.service fingerprint-evidence.service fingerprint-sensor.service fingerprint-suricata.service; do
  echo "--- $u"
  systemctl show "$u" -p ActiveState -p SubState -p MainPID -p NRestarts --no-pager
  systemctl is-active --quiet "$u" || die "$u changed out of active state."
done

[ "$PORTAL_PID_BEFORE" = "$PORTAL_PID_AFTER" ] || die "captive-portal.service restarted unexpectedly."
[ "$EVIDENCE_PID_BEFORE" = "$EVIDENCE_PID_AFTER" ] || die "fingerprint-evidence.service restarted unexpectedly."
[ "$SENSOR_PID_BEFORE" = "$SENSOR_PID_AFTER" ] || die "fingerprint-sensor.service restarted unexpectedly."
[ "$SURICATA_PID_BEFORE" = "$SURICATA_PID_AFTER" ] || die "fingerprint-suricata.service restarted unexpectedly."
echo "EXISTING_SERVICE_PIDS_UNCHANGED=PASS"

echo "--- classification DB"
stat -c 'CLASS_DB path=%n bytes=%s owner=%U group=%G mode=%a mtime=%y' "$CLASS_DB"
sha256sum "$CLASS_DB"

echo "--- /run"
df -h /run
if [ -e /run/fingerprint-suricata/diag-eve.json ]; then
  die "diag-eve.json unexpectedly reappeared."
fi
echo "DIAG_EVE_PRESENT=NO"

step "FINAL"
echo "TASK04_DORMANT_CODE_DEPLOY=PASS"
echo "TASK04_CLASSIFICATION_DB_INITIALIZED=PASS"
echo "TASK04_CLASSIFICATION_ROWS=0"
echo "TASK04_ARTIFACT_ROWS=0"
echo "TASK04_CONTROL_PLANE_DB=ABSENT"
echo "TASK04_ACTIVE_POINTER=ABSENT_BY_CONSTRUCTION"
echo "TASK04_CLASSIFICATION_PROCESS=ABSENT"
echo "TASK04_INTERNAL_READ_EMPTY=PASS"
echo "CLASSIFICATION_ACTIVATION=NO"
echo "EXISTING_SERVICES_RESTARTED=NO"
echo "TARGET_SHA=$TARGET_SHA"
echo "TARGET_TREE=$TARGET_TREE"
echo "REPORT=$REPORT"

CREATED_CLASS_DB=0
trap - EXIT
