#!/usr/bin/env bash
set -Eeuo pipefail
export SYSTEMD_PAGER=cat
export PAGER=cat

PORTAL="/opt/CaptivePortal"
CFG="/etc/default/captive-portal"
WORKER="fingerprint-classification.service"
PORTAL_UNIT="captive-portal.service"
VENV_PY="/opt/captiveportal-runtime/device-fingerprint-venv/bin/python"

EXPECTED_HEAD="97bd1cf924024a38cc3229bfd726a25fe6754b07"
EXPECTED_TREE="545a48caf86adc247083db611e87a8d36820f353"

INTEGRATION_DB="/opt/CaptivePortal/data/device_fingerprint_integration.sqlite3"
CONTROL_DB="/opt/CaptivePortal/data/device_fingerprint_control_plane.sqlite3"
CONTROLLED_IID="77dcd849-8855-4dd4-b3ed-9d2c62d86935"

STAMP="$(date '+%Y%m%dT%H%M%S%z')"
CFG_BACKUP="${CFG}.task05-r1-reactivate-backup-${STAMP}"

section(){ printf '\n===== %s =====\n' "$1"; }
fail(){ echo "FATAL: $*" >&2; exit 1; }

MUTATION_STARTED=0

wait_active() {
  local unit="$1" timeout="${2:-30}" i
  for ((i=0; i<timeout; i++)); do
    if systemctl is-active --quiet "$unit"; then return 0; fi
    sleep 1
  done
  return 1
}

rollback() {
  local rc=$?
  trap - ERR
  echo
  if [ "$MUTATION_STARTED" -eq 0 ]; then
    echo "===== PRECONDITION ABORT ====="
    echo "PRECONDITION_ABORT_NO_MUTATION=YES"
    echo "TASK05_R1_REACTIVATION=FAIL"
    exit "$rc"
  fi
  echo "===== AUTOMATIC CONTAINMENT ROLLBACK ====="
  if [ -f "$CFG_BACKUP" ]; then
    cp -a "$CFG_BACKUP" "$CFG" || true
  else
    sed -i 's/^DEVICE_FINGERPRINT_INTEGRATION_ENABLED=.*/DEVICE_FINGERPRINT_INTEGRATION_ENABLED=false/' "$CFG" || true
  fi
  systemctl stop "$WORKER" || true
  systemctl disable "$WORKER" || true
  systemctl restart "$PORTAL_UNIT" || true
  echo "TASK05_INTEGRATION_ENABLED=NO"
  echo "TASK05_WORKER_ACTIVE=NO"
  echo "TASK05_WORKER_ENABLED_FOR_BOOT=NO"
  echo "TASK05_R1_REACTIVATION=FAIL"
  exit "$rc"
}
trap rollback ERR

[ "$(id -u)" -eq 0 ] || fail "Run with sudo/root"

section "DECLARATION"
date --iso-8601=seconds
echo "MODE=TASK05_R1_PRODUCTION_REACTIVATION"
echo "EXPECTED_HEAD=$EXPECTED_HEAD"
echo "EXPECTED_TREE=$EXPECTED_TREE"
echo "CONFIG_CHANGE=false_to_true"
echo "PORTAL_RESTART=YES"
echo "WORKER_ENABLE_START=YES"
echo "AUTH_PROOF_IN_THIS_STEP=NO"
echo "OLD_TERMINAL_JOB_MUTATION_ALLOWED=NO"

section "PRECONDITIONS"
HEAD="$(git -C "$PORTAL" rev-parse HEAD)"
TREE="$(git -C "$PORTAL" rev-parse 'HEAD^{tree}')"
STATUS="$(git -C "$PORTAL" status --porcelain=v1 --untracked-files=normal)"
echo "PRODUCTION_HEAD=$HEAD"
echo "PRODUCTION_TREE=$TREE"
[ "$HEAD" = "$EXPECTED_HEAD" ] || fail "Unexpected production HEAD"
[ "$TREE" = "$EXPECTED_TREE" ] || fail "Unexpected production tree"
[ -z "$STATUS" ] || fail "Production worktree dirty"

grep -qxF 'DEVICE_FINGERPRINT_INTEGRATION_ENABLED=false' "$CFG" \
  || fail "Integration flag is not exactly false before reactivation"
systemctl is-active --quiet "$PORTAL_UNIT" || fail "Portal inactive before reactivation"
if systemctl is-active --quiet "$WORKER"; then
  fail "Worker unexpectedly active before reactivation"
fi
if systemctl is-enabled --quiet "$WORKER"; then
  fail "Worker unexpectedly enabled before reactivation"
fi

[ -x "$VENV_PY" ] || fail "Production Task-05 venv Python missing"
sudo -u admin env   HOME=/nonexistent   PYTHONPATH="$PORTAL"   PYTHONDONTWRITEBYTECODE=1   "$VENV_PY" -B - <<'PY'
import flask
import app.device_fingerprint_integration.compatibility
print("PRODUCTION_VENV_IMPORTS=PASS")
PY

systemctl cat "$WORKER" --no-pager
systemctl cat "$PORTAL_UNIT" --no-pager >/dev/null
echo "SYSTEMD_UNITS_PRESENT=PASS"

CONTROL_SHA_BEFORE="$(sha256sum "$CONTROL_DB" | awk '{print $1}')"
PORTAL_RESTARTS_BEFORE="$(systemctl show "$PORTAL_UNIT" -p NRestarts --value --no-pager)"
WORKER_RESTARTS_BEFORE="$(systemctl show "$WORKER" -p NRestarts --value --no-pager)"
echo "CONTROL_DB_SHA256_BEFORE=$CONTROL_SHA_BEFORE"
echo "PORTAL_NRESTARTS_BEFORE=$PORTAL_RESTARTS_BEFORE"
echo "WORKER_NRESTARTS_BEFORE=$WORKER_RESTARTS_BEFORE"

INTEGRATION_DB="$INTEGRATION_DB" IID="$CONTROLLED_IID" /usr/bin/python3 - <<'PY'
import os, sqlite3
con=sqlite3.connect(f"file:{os.environ['INTEGRATION_DB']}?mode=ro", uri=True)
con.row_factory=sqlite3.Row
try:
    q=con.execute("PRAGMA quick_check").fetchone()[0]
    count=con.execute("SELECT COUNT(*) FROM integration_jobs").fetchone()[0]
    r=con.execute(
        "SELECT classification_state,attempt_count,last_reason_code,identity_state,"
        "planned_classification_id,classification_id,classification_result_id,"
        "registry_snapshot_id,device_id,visit_id "
        "FROM integration_jobs WHERE integration_id=?",
        (os.environ["IID"],)
    ).fetchone()
finally:
    con.close()
print("INTEGRATION_QUICK_CHECK="+str(q))
print("INTEGRATION_JOB_COUNT_BEFORE="+str(count))
if q != "ok":
    raise SystemExit("FATAL: integration DB quick_check failed")
if r is None:
    raise SystemExit("FATAL: preserved controlled failure missing")
for k in r.keys():
    print("OLD_JOB_BEFORE_"+k.upper()+"="+("" if r[k] is None else str(r[k])))
expected=("NO_RESULT_FINAL",1,"runtime_profile_incompatible","DEVICE_AND_VISIT_RESOLVED")
actual=(r["classification_state"],r["attempt_count"],r["last_reason_code"],r["identity_state"])
if actual != expected:
    raise SystemExit(f"FATAL: old job precondition mismatch: {actual!r}")
PY

section "BACKUP CONFIG"
cp -a "$CFG" "$CFG_BACKUP"
echo "CONFIG_BACKUP=$CFG_BACKUP"
MUTATION_STARTED=1

section "ENABLE TASK05 SUBMITTER"
sed -i 's/^DEVICE_FINGERPRINT_INTEGRATION_ENABLED=false$/DEVICE_FINGERPRINT_INTEGRATION_ENABLED=true/' "$CFG"
grep -qxF 'DEVICE_FINGERPRINT_INTEGRATION_ENABLED=true' "$CFG" \
  || fail "Failed to set integration flag true"
echo "TASK05_CONFIG_ENABLED=YES"

section "RESTART PORTAL"
SINCE_PORTAL="$(date -d '2 seconds ago' '+%Y-%m-%d %H:%M:%S')"
systemctl restart "$PORTAL_UNIT"
wait_active "$PORTAL_UNIT" 30 || fail "Portal failed to become active"
sleep 3
PORTAL_RESTARTS_AFTER="$(systemctl show "$PORTAL_UNIT" -p NRestarts --value --no-pager)"
echo "PORTAL_NRESTARTS_AFTER=$PORTAL_RESTARTS_AFTER"
[ "$PORTAL_RESTARTS_AFTER" = "0" ] || fail "Portal automatic restart count non-zero"

IDENTITY_LINE="$(journalctl -u "$PORTAL_UNIT" --since "$SINCE_PORTAL" --no-pager -o cat \
  | grep '"event":"captivportal_loaded_artifact_identity"' | tail -n1 || true)"
[ -n "$IDENTITY_LINE" ] || fail "Fresh portal artifact identity not found"
IDENTITY_LINE="$IDENTITY_LINE" EXPECTED_HEAD="$EXPECTED_HEAD" EXPECTED_TREE="$EXPECTED_TREE" /usr/bin/python3 - <<'PY'
import json, os
s=os.environ["IDENTITY_LINE"]
o=json.loads(s[s.index("{"):])
assert o["artifact_sha"] == os.environ["EXPECTED_HEAD"], o
assert o["artifact_tree"] == os.environ["EXPECTED_TREE"], o
print("PORTAL_LOADED_ARTIFACT_SHA="+o["artifact_sha"])
print("PORTAL_LOADED_ARTIFACT_TREE="+o["artifact_tree"])
PY
echo "PORTAL_WITH_TASK05_SUBMITTER=PASS"

section "ENABLE AND START CLASSIFICATION WORKER"
systemctl enable "$WORKER"
systemctl start "$WORKER"
wait_active "$WORKER" 30 || fail "Classification worker failed to become active"
sleep 5

systemctl is-enabled --quiet "$WORKER" || fail "Worker not enabled for boot"
WORKER_RESTARTS_AFTER="$(systemctl show "$WORKER" -p NRestarts --value --no-pager)"
echo "WORKER_NRESTARTS_AFTER=$WORKER_RESTARTS_AFTER"
[ "$WORKER_RESTARTS_AFTER" = "0" ] || fail "Worker automatic restart count non-zero"

echo "WORKER_STATUS:"
systemctl --no-pager --full status "$WORKER" | sed -n '1,18p'

WORKER_HEALTH="$(journalctl -u "$WORKER" --since '-2 min' --no-pager -o cat \
  | grep '"event":"fingerprint.integration_worker_health"' | tail -n1 || true)"
echo "LATEST_WORKER_HEALTH=${WORKER_HEALTH:-<none>}"
if [ -n "$WORKER_HEALTH" ]; then
  case "$WORKER_HEALTH" in
    *'"reason_code":"ready"'*) ;;
    *) fail "Latest worker health is not ready" ;;
  esac
fi
echo "WORKER_RUNTIME=PASS"

section "STABILITY AND OLD TERMINAL JOB IMMUTABILITY"
sleep 10

systemctl is-active --quiet "$PORTAL_UNIT" || fail "Portal inactive after stabilization"
systemctl is-active --quiet "$WORKER" || fail "Worker inactive after stabilization"
systemctl is-enabled --quiet "$WORKER" || fail "Worker no longer enabled"
grep -qxF 'DEVICE_FINGERPRINT_INTEGRATION_ENABLED=true' "$CFG" \
  || fail "Integration flag not true after stabilization"

PORTAL_RESTARTS_FINAL="$(systemctl show "$PORTAL_UNIT" -p NRestarts --value --no-pager)"
WORKER_RESTARTS_FINAL="$(systemctl show "$WORKER" -p NRestarts --value --no-pager)"
echo "PORTAL_NRESTARTS_FINAL=$PORTAL_RESTARTS_FINAL"
echo "WORKER_NRESTARTS_FINAL=$WORKER_RESTARTS_FINAL"
[ "$PORTAL_RESTARTS_FINAL" = "0" ] || fail "Portal restart loop detected"
[ "$WORKER_RESTARTS_FINAL" = "0" ] || fail "Worker restart loop detected"

CONTROL_SHA_AFTER="$(sha256sum "$CONTROL_DB" | awk '{print $1}')"
echo "CONTROL_DB_SHA256_AFTER=$CONTROL_SHA_AFTER"
[ "$CONTROL_SHA_AFTER" = "$CONTROL_SHA_BEFORE" ] || fail "Control-plane DB changed during activation"

INTEGRATION_DB="$INTEGRATION_DB" IID="$CONTROLLED_IID" /usr/bin/python3 - <<'PY'
import os, sqlite3
con=sqlite3.connect(f"file:{os.environ['INTEGRATION_DB']}?mode=ro", uri=True)
con.row_factory=sqlite3.Row
try:
    q=con.execute("PRAGMA quick_check").fetchone()[0]
    count=con.execute("SELECT COUNT(*) FROM integration_jobs").fetchone()[0]
    r=con.execute(
        "SELECT classification_state,attempt_count,last_reason_code,identity_state,"
        "planned_classification_id,classification_id,classification_result_id,"
        "registry_snapshot_id,device_id,visit_id "
        "FROM integration_jobs WHERE integration_id=?",
        (os.environ["IID"],)
    ).fetchone()
finally:
    con.close()
print("INTEGRATION_QUICK_CHECK_AFTER="+str(q))
print("INTEGRATION_JOB_COUNT_AFTER="+str(count))
if q != "ok":
    raise SystemExit("FATAL: integration DB quick_check failed after activation")
if r is None:
    raise SystemExit("FATAL: preserved controlled failure disappeared")
for k in r.keys():
    print("OLD_JOB_AFTER_"+k.upper()+"="+("" if r[k] is None else str(r[k])))
expected=("NO_RESULT_FINAL",1,"runtime_profile_incompatible","DEVICE_AND_VISIT_RESOLVED")
actual=(r["classification_state"],r["attempt_count"],r["last_reason_code"],r["identity_state"])
if actual != expected:
    raise SystemExit(f"FATAL: old terminal job mutated after worker activation: {actual!r}")
PY

section "FINAL"
echo "PRODUCTION_HEAD=$(git -C "$PORTAL" rev-parse HEAD)"
echo "PRODUCTION_TREE=$(git -C "$PORTAL" rev-parse 'HEAD^{tree}')"
echo "TASK05_INTEGRATION_ENABLED=YES"
echo "TASK05_WORKER_ACTIVE=YES"
echo "TASK05_WORKER_ENABLED_FOR_BOOT=YES"
echo "TASK05_PORTAL_NRESTARTS=0"
echo "TASK05_WORKER_NRESTARTS=0"
echo "OLD_FAILED_JOB_PRESERVED=YES"
echo "CONTROL_PLANE_UNCHANGED=YES"
echo "AUTH_PROOF_PENDING=YES"
echo "TASK05_R1_REACTIVATION=PASS"
