#!/usr/bin/env bash
set -Eeuo pipefail

export SYSTEMD_PAGER=cat
export PAGER=cat

PORTAL="/opt/CaptivePortal"
CFG="/etc/default/captive-portal"
UNIT_SRC="$PORTAL/deploy/device-fingerprint/fingerprint-classification.service"
UNIT_DST="/etc/systemd/system/fingerprint-classification.service"
DEPLOY_ROOT="/home/admin/CaptivePortal-Deploy"

TARGET_HEAD="1d88f4ae947fa95454dbb54c70f9d6bdd13b1d22"
TARGET_TREE="8183bf48abfc71c1b488c0667efc0f1ae717003e"

INTEGRATION_DB="/opt/CaptivePortal/data/device_fingerprint_integration.sqlite3"
EVIDENCE_DB="/opt/CaptivePortal/data/device_fingerprint_evidence.sqlite3"
CLASS_DB="/opt/CaptivePortal/data/device_fingerprint_classification.sqlite3"
CONTROL_DB="/opt/CaptivePortal/data/device_fingerprint_control_plane.sqlite3"
REGISTRY_DB="/opt/CaptivePortal/data/visitor_registry.sqlite3"
VISIT_DB="/opt/CaptivePortal/data/visits.sqlite3"
CURRENT_STATE_DB="/opt/CaptivePortal/data/current_state.sqlite3"
CONSUMER_LOCK="${INTEGRATION_DB}.consumer.lock"

TASK04_WT="/home/admin/CaptivePortal-Deploy/task04-dormant-fecdb5a7"

STAMP="$(date '+%Y%m%dT%H%M%S%z')"
BACKUP_DIR="$DEPLOY_ROOT/task05-activation-backup-$STAMP"
CFG_BACKUP="$BACKUP_DIR/captive-portal.env.before"
ROLLBACK_DIR="$DEPLOY_ROOT/task05-activation-rollback-$STAMP"

MUTATION_STARTED=0
COMPLETED=0

section(){ printf '\n===== %s =====\n' "$1"; }
fail(){ echo "FATAL: $*" >&2; return 1; }

wait_active() {
  local unit="$1" timeout="${2:-30}"
  local i
  for ((i=1; i<=timeout; i++)); do
    systemctl is-active --quiet "$unit" && return 0
    sleep 1
  done
  return 1
}

wait_portal_identity() {
  local expected_head="$1" expected_tree="$2" since="$3" timeout="${4:-45}"
  local i line
  echo "PORTAL_IDENTITY_JOURNAL_SINCE=$since"
  for ((i=1; i<=timeout; i++)); do
    line="$(journalctl -u captive-portal.service --since "$since" --no-pager -o cat 2>/dev/null \
      | grep '"event":"captivportal_loaded_artifact_identity"' | tail -n1 || true)"
    if [ -n "$line" ]; then
      echo "PORTAL_IDENTITY_RAW=$line"
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
  echo "RECENT_PORTAL_LOG:"
  journalctl -u captive-portal.service --since "$since" --no-pager -o cat 2>/dev/null | tail -n 60 || true
  return 1
}

wait_portal_server_start() {
  local since="$1" timeout="${2:-45}"
  local i
  for ((i=1; i<=timeout; i++)); do
    journalctl -u captive-portal.service --since "$since" --no-pager -o cat 2>/dev/null \
      | grep -q 'Starting server on ' && return 0
    systemctl is-active --quiet captive-portal.service || return 1
    sleep 1
  done
  return 1
}

wait_worker_ready() {
  local since="$1" timeout="${2:-20}"
  local i line
  echo "WORKER_HEALTH_JOURNAL_SINCE=$since"
  for ((i=1; i<=timeout; i++)); do
    line="$(journalctl -u fingerprint-classification.service --since "$since" --no-pager -o cat 2>/dev/null \
      | grep '"event":"fingerprint.integration_worker_health"' \
      | grep '"reason_code":"ready"' | tail -n1 || true)"
    if [ -n "$line" ]; then
      echo "WORKER_READY_RAW=$line"
      return 0
    fi
    systemctl is-active --quiet fingerprint-classification.service || return 1
    sleep 1
  done
  echo "RECENT_WORKER_LOG:"
  journalctl -u fingerprint-classification.service --since "$since" --no-pager -o cat 2>/dev/null | tail -n 80 || true
  return 1
}

restore_config() {
  if [ -f "$CFG_BACKUP" ]; then
    cp -a "$CFG_BACKUP" "$CFG"
  fi
}

rollback_activation() {
  local reason="$1"
  trap - ERR
  set +e

  section "AUTOMATIC ACTIVATION ROLLBACK"
  echo "ROLLBACK_REASON=$reason"

  systemctl stop fingerprint-classification.service >/dev/null 2>&1 || true
  systemctl disable fingerprint-classification.service >/dev/null 2>&1 || true
  systemctl stop captive-portal.service >/dev/null 2>&1 || true

  restore_config

  if [ -e "$INTEGRATION_DB" ] || [ -e "$CONSUMER_LOCK" ]; then
    install -d -m 0700 -o root -g root "$ROLLBACK_DIR"
    [ -e "$INTEGRATION_DB" ] && mv "$INTEGRATION_DB" "$ROLLBACK_DIR/" || true
    [ -e "$CONSUMER_LOCK" ] && mv "$CONSUMER_LOCK" "$ROLLBACK_DIR/" || true
    echo "ROLLBACK_INTEGRATION_ARTIFACTS_QUARANTINED=$ROLLBACK_DIR"
  else
    echo "ROLLBACK_INTEGRATION_ARTIFACTS_QUARANTINED=NONE"
  fi

  rm -f "$UNIT_DST"
  systemctl daemon-reload >/dev/null 2>&1 || true
  systemctl reset-failed fingerprint-classification.service >/dev/null 2>&1 || true

  local rb_since
  rb_since="$(date -d '2 seconds ago' '+%Y-%m-%d %H:%M:%S')"
  systemctl start captive-portal.service
  local rollback_ok=1
  wait_active captive-portal.service 30 || rollback_ok=0
  wait_portal_identity "$TARGET_HEAD" "$TARGET_TREE" "$rb_since" 45 || rollback_ok=0
  wait_portal_server_start "$rb_since" 45 || rollback_ok=0

  if [ -e "$INTEGRATION_DB" ]; then
    echo "ROLLBACK_CANONICAL_INTEGRATION_DB_PRESENT=YES"
    rollback_ok=0
  else
    echo "ROLLBACK_CANONICAL_INTEGRATION_DB_PRESENT=NO"
  fi

  if systemctl list-unit-files fingerprint-classification.service --no-legend 2>/dev/null \
      | grep -q '^fingerprint-classification.service'; then
    echo "ROLLBACK_CLASSIFICATION_UNIT_PRESENT=YES"
    rollback_ok=0
  else
    echo "ROLLBACK_CLASSIFICATION_UNIT_PRESENT=NO"
  fi

  if [ "$rollback_ok" -eq 1 ]; then
    echo "TASK05_ACTIVATION_ROLLBACK=PASS"
  else
    echo "TASK05_ACTIVATION_ROLLBACK=FAILED"
  fi
  echo "TASK05_PROD_ACTIVATION=FAILED_ROLLED_BACK"
  exit 1
}

on_error() {
  local rc=$? line="$1"
  if [ "$MUTATION_STARTED" -eq 1 ] && [ "$COMPLETED" -eq 0 ]; then
    rollback_activation "line_${line}_exit_${rc}"
  fi
  exit "$rc"
}
trap 'on_error $LINENO' ERR

[ "$(id -u)" -eq 0 ] || { echo "FATAL: Run with sudo/root" >&2; exit 1; }

section "DECLARATION"
date --iso-8601=seconds
echo "MODE=TASK05_PROD_ACTIVATE_INTEGRATION_R1"
echo "PRODUCTION_CODE_SWITCH=NO"
echo "CONFIG_WRITE=YES"
echo "SYSTEMD_UNIT_INSTALL=YES"
echo "SYSTEMD_ENABLE=YES"
echo "WORKER_START=YES"
echo "PORTAL_RESTART=YES"
echo "DATABASE_WRITE=TASK05_INTEGRATION_DB_ONLY"
echo "TASK04_SOURCE_DATABASE_WRITE=NO_BY_DEPLOY_SCRIPT"
echo "AUTOMATIC_ROLLBACK=YES"
echo "CONFIG_BACKUP_DIR=$BACKUP_DIR"

section "PRECONDITIONS"
HEAD="$(git -C "$PORTAL" rev-parse HEAD)"
TREE="$(git -C "$PORTAL" rev-parse 'HEAD^{tree}')"
STATUS="$(git -C "$PORTAL" status --porcelain=v1 --untracked-files=normal)"
echo "CURRENT_HEAD=$HEAD"
echo "CURRENT_TREE=$TREE"
[ "$HEAD" = "$TARGET_HEAD" ] || fail "Production is not on accepted Task-05 commit"
[ "$TREE" = "$TARGET_TREE" ] || fail "Production Task-05 tree mismatch"
[ -z "$STATUS" ] || fail "Production worktree dirty"
[ -f "$CFG" ] || fail "$CFG missing"
[ -f "$UNIT_SRC" ] || fail "Accepted Task-05 worker unit missing"
[ -d "$TASK04_WT" ] || fail "Accepted Task-04 frozen worktree missing"
[ ! -e "$INTEGRATION_DB" ] || fail "Integration DB already exists"
[ ! -e "$CONSUMER_LOCK" ] || fail "Integration consumer lock already exists"

for path in "$EVIDENCE_DB" "$CLASS_DB" "$CONTROL_DB" "$REGISTRY_DB" "$VISIT_DB" "$CURRENT_STATE_DB"; do
  [ -f "$path" ] || fail "Required source DB missing: $path"
done

for unit in captive-portal.service fingerprint-evidence.service fingerprint-sensor.service fingerprint-suricata.service; do
  systemctl is-active --quiet "$unit" || fail "$unit is not active"
done

if systemctl list-unit-files fingerprint-classification.service --no-legend 2>/dev/null \
  | grep -q '^fingerprint-classification.service'; then
  fail "fingerprint-classification.service already installed"
fi

echo "PRECONDITIONS=PASS"

section "CURRENT CONFIG MUST BE DISABLED"
DUP_COUNT="$(grep -c '^DEVICE_FINGERPRINT_INTEGRATION_ENABLED=' "$CFG" || true)"
[ "$DUP_COUNT" -le 1 ] || fail "Duplicate DEVICE_FINGERPRINT_INTEGRATION_ENABLED keys"

CFG_VALUE="$(awk -F= '
  $1=="DEVICE_FINGERPRINT_INTEGRATION_ENABLED" {
    value=substr($0,index($0,"=")+1)
    gsub(/^[ \t]+|[ \t]+$/, "", value)
    print value
  }' "$CFG" | tail -n1)"

if [ -z "$CFG_VALUE" ]; then
  echo "CURRENT_INTEGRATION_ENABLED=ABSENT_DEFAULT_FALSE"
else
  case "${CFG_VALUE,,}" in
    false|0|no|off) echo "CURRENT_INTEGRATION_ENABLED=$CFG_VALUE" ;;
    *) fail "Integration unexpectedly enabled before activation" ;;
  esac
fi
echo "CURRENT_CONFIG_DISABLED=PASS"

section "PROPOSED CONFIG VALIDATION"
sudo -H -u admin env \
  PYTHONPATH="$PORTAL" \
  PYTHONDONTWRITEBYTECODE=1 \
  INTEGRATION_DB="$INTEGRATION_DB" \
  EVIDENCE_DB="$EVIDENCE_DB" \
  CLASS_DB="$CLASS_DB" \
  CONTROL_DB="$CONTROL_DB" \
  REGISTRY_DB="$REGISTRY_DB" \
  VISIT_DB="$VISIT_DB" \
  CURRENT_STATE_DB="$CURRENT_STATE_DB" \
  /usr/bin/python3 -B - <<'PY'
import os
from app.device_fingerprint_integration.config import integration_config_from_settings

settings = {
    "device_fingerprint_integration_enabled": True,
    "device_fingerprint_integration_db_path": os.environ["INTEGRATION_DB"],
    "device_fingerprint_evidence_db_path": os.environ["EVIDENCE_DB"],
    "device_fingerprint_classification_db_path": os.environ["CLASS_DB"],
    "device_fingerprint_control_plane_db_path": os.environ["CONTROL_DB"],
    "visitor_registry_db_path": os.environ["REGISTRY_DB"],
    "visit_lifecycle_db_path": os.environ["VISIT_DB"],
    "current_state_db_path": os.environ["CURRENT_STATE_DB"],
}
cfg = integration_config_from_settings(settings)
assert cfg.enabled is True
assert cfg.db_path == os.environ["INTEGRATION_DB"]
print("PROPOSED_INTEGRATION_ENABLED=TRUE")
print("PROPOSED_INTEGRATION_DB="+cfg.db_path)
print("PROPOSED_EVIDENCE_DB="+cfg.evidence_db_path)
print("PROPOSED_CLASSIFICATION_DB="+cfg.classification_db_path)
print("PROPOSED_CONTROL_PLANE_DB="+cfg.control_plane_db_path)
print("PROPOSED_CONFIG_VALIDATION=PASS")
PY

section "TASK04 PRE-ACTIVATION STATE"
sudo -H -u admin env \
  PYTHONPATH="$TASK04_WT" \
  PYTHONDONTWRITEBYTECODE=1 \
  CONTROL_DB="$CONTROL_DB" \
  CLASS_DB="$CLASS_DB" \
  /usr/bin/python3 -B - <<'PY'
import os, sqlite3
from app.device_fingerprint.control_plane_store import DeviceFingerprintControlPlaneStore

control = DeviceFingerprintControlPlaneStore(os.environ["CONTROL_DB"])
pin = control.pin_active_profile("classification")
print("ACTIVE_CRP="+pin.runtime_profile.artifact_id)
print("ACTIVE_RPM="+pin.admission_manifest.artifact_id)
print("ACTIVE_VALIDITY="+pin.validity_record.semantic_payload["state"])
if pin.validity_record.semantic_payload["state"] != "ACTIVE":
    raise SystemExit("FATAL: Task-04 classification profile is not ACTIVE")

con=sqlite3.connect(f"file:{os.environ['CLASS_DB']}?mode=ro", uri=True)
try:
    rows=con.execute("SELECT COUNT(*) FROM classifications").fetchone()[0]
finally:
    con.close()
print("PRE_ACTIVATION_CLASSIFICATION_ROWS="+str(rows))
if rows < 1:
    raise SystemExit("FATAL: accepted Task-04 classification baseline missing")
print("TASK04_PRE_ACTIVATION_STATE=PASS")
PY

section "CREATE SECURE BACKUP"
MUTATION_STARTED=1
install -d -m 0700 -o root -g root "$BACKUP_DIR"
cp -a "$CFG" "$CFG_BACKUP"
echo "CONFIG_BACKUP_CREATED=$CFG_BACKUP"

section "WRITE TASK05 INTEGRATION CONFIG"
CFG="$CFG" /usr/bin/python3 - <<'PY'
import os, stat, tempfile
from pathlib import Path

path = Path(os.environ["CFG"])
st = path.stat()
raw = path.read_text(encoding="utf-8")

updates = {
    "DEVICE_FINGERPRINT_INTEGRATION_ENABLED": "true",
    "DEVICE_FINGERPRINT_INTEGRATION_DB_PATH": "/opt/CaptivePortal/data/device_fingerprint_integration.sqlite3",
    "DEVICE_FINGERPRINT_EVIDENCE_DB_PATH": "/opt/CaptivePortal/data/device_fingerprint_evidence.sqlite3",
    "DEVICE_FINGERPRINT_CLASSIFICATION_DB_PATH": "/opt/CaptivePortal/data/device_fingerprint_classification.sqlite3",
    "DEVICE_FINGERPRINT_CONTROL_PLANE_DB_PATH": "/opt/CaptivePortal/data/device_fingerprint_control_plane.sqlite3",
}

lines = raw.splitlines()
seen = {k: 0 for k in updates}
out = []

for line in lines:
    replaced = False
    for key, value in updates.items():
        if line.startswith(key + "="):
            seen[key] += 1
            if seen[key] > 1:
                raise SystemExit(f"FATAL: duplicate config key {key}")
            out.append(f"{key}={value}")
            replaced = True
            break
    if not replaced:
        out.append(line)

missing = [key for key, count in seen.items() if count == 0]
if missing:
    if out and out[-1] != "":
        out.append("")
    out.append("# TASK-DEVICE-FINGERPRINT-05 production integration")
    for key in missing:
        out.append(f"{key}={updates[key]}")

payload = "\n".join(out) + "\n"
tmp = path.with_name(path.name + ".task05.tmp")
tmp.write_text(payload, encoding="utf-8")
os.chown(tmp, st.st_uid, st.st_gid)
os.chmod(tmp, stat.S_IMODE(st.st_mode))
os.replace(tmp, path)
PY

for expected in \
  'DEVICE_FINGERPRINT_INTEGRATION_ENABLED=true' \
  'DEVICE_FINGERPRINT_INTEGRATION_DB_PATH=/opt/CaptivePortal/data/device_fingerprint_integration.sqlite3' \
  'DEVICE_FINGERPRINT_EVIDENCE_DB_PATH=/opt/CaptivePortal/data/device_fingerprint_evidence.sqlite3' \
  'DEVICE_FINGERPRINT_CLASSIFICATION_DB_PATH=/opt/CaptivePortal/data/device_fingerprint_classification.sqlite3' \
  'DEVICE_FINGERPRINT_CONTROL_PLANE_DB_PATH=/opt/CaptivePortal/data/device_fingerprint_control_plane.sqlite3'
do
  grep -qxF "$expected" "$CFG" || fail "Missing exact Task-05 config: $expected"
done
echo "TASK05_CONFIG_WRITE=PASS"

section "INSTALL EXACT WORKER UNIT"
install -m 0644 -o root -g root "$UNIT_SRC" "$UNIT_DST"
cmp -s "$UNIT_SRC" "$UNIT_DST" || fail "Installed worker unit differs from accepted artifact"
systemd-analyze verify "$UNIT_DST" >/dev/null
systemctl daemon-reload
echo "WORKER_UNIT_EXACT_INSTALL=PASS"

section "START WORKER BEFORE PORTAL ENQUEUE"
WORKER_START_SINCE="$(date -d '2 seconds ago' '+%Y-%m-%d %H:%M:%S')"
systemctl enable fingerprint-classification.service >/dev/null
systemctl start fingerprint-classification.service
wait_active fingerprint-classification.service 30 || fail "fingerprint-classification.service did not become active"
wait_worker_ready "$WORKER_START_SINCE" 20 || fail "Task-05 worker ready telemetry not observed"

WORKER_PID="$(systemctl show fingerprint-classification.service -p MainPID --value --no-pager)"
WORKER_RESTARTS="$(systemctl show fingerprint-classification.service -p NRestarts --value --no-pager)"
echo "WORKER_PID=$WORKER_PID"
echo "WORKER_NRESTARTS=$WORKER_RESTARTS"
[ "$WORKER_RESTARTS" = "0" ] || fail "Task-05 worker restarted unexpectedly"

[ -f "$INTEGRATION_DB" ] || fail "Worker did not create integration DB"
echo "INTEGRATION_DB_STAT=$(stat -c '%U:%G mode=%a bytes=%s' "$INTEGRATION_DB")"
[ "$(stat -c '%U:%G' "$INTEGRATION_DB")" = "admin:admin" ] || fail "Integration DB owner mismatch"
[ "$(stat -c '%a' "$INTEGRATION_DB")" = "600" ] || fail "Integration DB mode is not 600"

INTEGRATION_DB="$INTEGRATION_DB" /usr/bin/python3 - <<'PY'
import os, sqlite3
path=os.environ["INTEGRATION_DB"]
con=sqlite3.connect(f"file:{path}?mode=ro", uri=True)
try:
    quick=con.execute("PRAGMA quick_check").fetchone()[0]
    version=con.execute("PRAGMA user_version").fetchone()[0]
    rows=con.execute("SELECT COUNT(*) FROM integration_jobs").fetchone()[0]
finally:
    con.close()
print("INTEGRATION_DB_QUICK_CHECK="+quick)
print("INTEGRATION_DB_USER_VERSION="+str(version))
print("INTEGRATION_JOBS_BEFORE_PORTAL_RESTART="+str(rows))
if quick != "ok":
    raise SystemExit("FATAL: integration DB quick_check failed")
if version != 1:
    raise SystemExit("FATAL: integration DB schema version mismatch")
if rows != 0:
    raise SystemExit("FATAL: integration DB not pristine before Portal activation")
print("INTEGRATION_DB_INITIALIZATION=PASS")
PY

section "RESTART PORTAL WITH TASK05 INTEGRATION ENABLED"
PORTAL_START_SINCE="$(date -d '2 seconds ago' '+%Y-%m-%d %H:%M:%S')"
systemctl restart captive-portal.service
wait_active captive-portal.service 30 || fail "captive-portal.service did not become active"
wait_portal_identity "$TARGET_HEAD" "$TARGET_TREE" "$PORTAL_START_SINCE" 45 \
  || fail "Fresh Task-05 Portal artifact identity not observed"
wait_portal_server_start "$PORTAL_START_SINCE" 45 \
  || fail "Portal did not reach server start after Task-05 activation"
sleep 5
systemctl is-active --quiet captive-portal.service || fail "Portal not stable after integration activation"

PORTAL_PID="$(systemctl show captive-portal.service -p MainPID --value --no-pager)"
PORTAL_RESTARTS="$(systemctl show captive-portal.service -p NRestarts --value --no-pager)"
echo "PORTAL_PID=$PORTAL_PID"
echo "PORTAL_NRESTARTS=$PORTAL_RESTARTS"
[ "$PORTAL_RESTARTS" = "0" ] || fail "Portal automatic restart count is non-zero"
echo "PORTAL_INTEGRATION_START=PASS"

section "POST-ACTIVATION WORKER HEALTH"
systemctl is-active --quiet fingerprint-classification.service || fail "Task-05 worker is not active"
sleep 2
WORKER_RESTARTS_POST="$(systemctl show fingerprint-classification.service -p NRestarts --value --no-pager)"
echo "WORKER_NRESTARTS_POST=$WORKER_RESTARTS_POST"
[ "$WORKER_RESTARTS_POST" = "0" ] || fail "Task-05 worker restarted after Portal activation"

journalctl -u fingerprint-classification.service --since "$WORKER_START_SINCE" --no-pager -o cat 2>/dev/null \
  | grep '"event":"fingerprint.integration_worker_health"' \
  | tail -n 5 || true

INTEGRATION_DB="$INTEGRATION_DB" CLASS_DB="$CLASS_DB" /usr/bin/python3 - <<'PY'
import os, sqlite3

icon=sqlite3.connect(f"file:{os.environ['INTEGRATION_DB']}?mode=ro", uri=True)
try:
    jobs=icon.execute("SELECT COUNT(*) FROM integration_jobs").fetchone()[0]
    states=icon.execute(
        "SELECT classification_state,COUNT(*) FROM integration_jobs GROUP BY classification_state ORDER BY classification_state"
    ).fetchall()
finally:
    icon.close()

ccon=sqlite3.connect(f"file:{os.environ['CLASS_DB']}?mode=ro", uri=True)
try:
    classifications=ccon.execute("SELECT COUNT(*) FROM classifications").fetchone()[0]
finally:
    ccon.close()

print("POST_ACTIVATION_INTEGRATION_JOBS="+str(jobs))
print("POST_ACTIVATION_JOB_STATES="+(",".join(f"{s}:{n}" for s,n in states) if states else "NONE"))
print("POST_ACTIVATION_CLASSIFICATION_ROWS="+str(classifications))
if classifications < 1:
    raise SystemExit("FATAL: Task-04 classification baseline disappeared")
print("POST_ACTIVATION_DB_STATE=PASS")
PY

section "FINAL INVARIANTS"
[ "$(git -C "$PORTAL" rev-parse HEAD)" = "$TARGET_HEAD" ] || fail "Production HEAD changed"
[ "$(git -C "$PORTAL" rev-parse 'HEAD^{tree}')" = "$TARGET_TREE" ] || fail "Production tree changed"
[ -z "$(git -C "$PORTAL" status --porcelain=v1 --untracked-files=normal)" ] || fail "Production worktree dirty"

for unit in captive-portal.service fingerprint-evidence.service fingerprint-sensor.service fingerprint-suricata.service fingerprint-classification.service; do
  systemctl is-active --quiet "$unit" || fail "$unit not active at final gate"
done

systemctl is-enabled --quiet fingerprint-classification.service || fail "Task-05 worker not enabled for boot"
cmp -s "$UNIT_SRC" "$UNIT_DST" || fail "Installed worker unit drifted"

grep -qxF 'DEVICE_FINGERPRINT_INTEGRATION_ENABLED=true' "$CFG" \
  || fail "Task-05 integration not enabled in environment file"

[ -f "$INTEGRATION_DB" ] || fail "Integration DB missing at final gate"

echo "FINAL_RUNTIME_INVARIANTS=PASS"

COMPLETED=1
trap - ERR

section "FINAL"
echo "CURRENT_PRODUCTION_HEAD=$TARGET_HEAD"
echo "CURRENT_PRODUCTION_TREE=$TARGET_TREE"
echo "TASK05_INTEGRATION_ENABLED=YES"
echo "TASK05_CLASSIFICATION_WORKER_ACTIVE=YES"
echo "TASK05_CLASSIFICATION_WORKER_ENABLED_FOR_BOOT=YES"
echo "TASK05_INTEGRATION_DB_SCHEMA=1"
echo "TASK05_PROD_ACTIVATION=PASS"
echo "OWNER_CONTROLLED_AUTH_PROOF=PENDING"
echo "AUTOMATIC_ROLLBACK_USED=NO"
