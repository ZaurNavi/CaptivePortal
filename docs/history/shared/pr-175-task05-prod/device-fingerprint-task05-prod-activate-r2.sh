#!/usr/bin/env bash
set -Eeuo pipefail

export SYSTEMD_PAGER=cat
export PAGER=cat

PORTAL="/opt/CaptivePortal"
CFG="/etc/default/captive-portal"
UNIT_SRC="$PORTAL/deploy/device-fingerprint/fingerprint-classification.service"
UNIT_DST="/etc/systemd/system/fingerprint-classification.service"
DROPIN_DIR="/etc/systemd/system/fingerprint-classification.service.d"
DROPIN_DST="$DROPIN_DIR/10-python-runtime.conf"
VENV_PY="/opt/captiveportal-runtime/device-fingerprint-venv/bin/python"
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
BACKUP_DIR="$DEPLOY_ROOT/task05-activation-r2-backup-$STAMP"
CFG_BACKUP="$BACKUP_DIR/captive-portal.env.before"
ROLLBACK_DIR="$DEPLOY_ROOT/task05-activation-r2-rollback-$STAMP"

MUTATION_STARTED=0
COMPLETED=0

section(){ printf '\n===== %s =====\n' "$1"; }
fail(){ echo "FATAL: $*" >&2; return 1; }

wait_active() {
  local unit="$1" timeout="${2:-30}" i
  for ((i=1; i<=timeout; i++)); do
    systemctl is-active --quiet "$unit" && return 0
    sleep 1
  done
  return 1
}

wait_worker_ready() {
  local since="$1" timeout="${2:-25}" i line
  echo "WORKER_HEALTH_JOURNAL_SINCE=$since"
  for ((i=1; i<=timeout; i++)); do
    line="$(journalctl -u fingerprint-classification.service --since "$since" --no-pager -o cat 2>/dev/null \
      | grep '"event":"fingerprint.integration_worker_health"' \
      | grep '"reason_code":"ready"' | tail -n1 || true)"
    if [ -n "$line" ]; then
      echo "WORKER_READY_RAW=$line"
      return 0
    fi
    systemctl is-active --quiet fingerprint-classification.service || {
      echo "RECENT_WORKER_LOG:"
      journalctl -u fingerprint-classification.service --since "$since" --no-pager -o cat 2>/dev/null | tail -n 100 || true
      return 1
    }
    sleep 1
  done
  echo "RECENT_WORKER_LOG:"
  journalctl -u fingerprint-classification.service --since "$since" --no-pager -o cat 2>/dev/null | tail -n 100 || true
  return 1
}

wait_portal_identity() {
  local expected_head="$1" expected_tree="$2" since="$3" timeout="${4:-45}" i line
  echo "PORTAL_IDENTITY_JOURNAL_SINCE=$since"
  for ((i=1; i<=timeout; i++)); do
    line="$(journalctl -u captive-portal.service --since "$since" --no-pager -o cat 2>/dev/null \
      | grep '"event":"captivportal_loaded_artifact_identity"' | tail -n1 || true)"
    if [ -n "$line" ]; then
      echo "PORTAL_IDENTITY_RAW=$line"
      IDENTITY_LINE="$line" EXPECTED_HEAD="$expected_head" EXPECTED_TREE="$expected_tree" \
      /usr/bin/python3 - <<'PY'
import json, os
s=os.environ["IDENTITY_LINE"]
o=json.loads(s[s.index("{"):])
assert o["artifact_sha"] == os.environ["EXPECTED_HEAD"], o
assert o["artifact_tree"] == os.environ["EXPECTED_TREE"], o
assert o["service_name"] == "captive-portal.service", o
print("PORTAL_LOADED_ARTIFACT_SHA="+o["artifact_sha"])
print("PORTAL_LOADED_ARTIFACT_TREE="+o["artifact_tree"])
print("PORTAL_LOADED_PROCESS_STARTED_AT="+o["process_started_at"])
PY
      return 0
    fi
    sleep 1
  done
  echo "RECENT_PORTAL_LOG:"
  journalctl -u captive-portal.service --since "$since" --no-pager -o cat 2>/dev/null | tail -n 100 || true
  return 1
}

wait_portal_server_start() {
  local since="$1" timeout="${2:-45}" i
  for ((i=1; i<=timeout; i++)); do
    journalctl -u captive-portal.service --since "$since" --no-pager -o cat 2>/dev/null \
      | grep -q 'Starting server on ' && return 0
    systemctl is-active --quiet captive-portal.service || return 1
    sleep 1
  done
  return 1
}

restore_config() {
  [ -f "$CFG_BACKUP" ] && cp -a "$CFG_BACKUP" "$CFG"
}

rollback_activation() {
  local reason="$1"
  trap - ERR
  set +e

  section "AUTOMATIC ACTIVATION ROLLBACK"
  echo "ROLLBACK_REASON=$reason"
  local rollback_ok=1

  systemctl stop fingerprint-classification.service >/dev/null 2>&1 || true
  systemctl disable fingerprint-classification.service >/dev/null 2>&1 || true
  systemctl stop captive-portal.service >/dev/null 2>&1 || true

  restore_config || rollback_ok=0

  if [ -e "$INTEGRATION_DB" ] || [ -e "$CONSUMER_LOCK" ]; then
    install -d -m 0700 -o root -g root "$ROLLBACK_DIR" || rollback_ok=0
    [ -e "$INTEGRATION_DB" ] && mv "$INTEGRATION_DB" "$ROLLBACK_DIR/" || true
    [ -e "$CONSUMER_LOCK" ] && mv "$CONSUMER_LOCK" "$ROLLBACK_DIR/" || true
    echo "ROLLBACK_INTEGRATION_ARTIFACTS_QUARANTINED=$ROLLBACK_DIR"
  else
    echo "ROLLBACK_INTEGRATION_ARTIFACTS_QUARANTINED=NONE"
  fi

  rm -f "$DROPIN_DST"
  rmdir "$DROPIN_DIR" 2>/dev/null || true
  rm -f "$UNIT_DST"
  systemctl daemon-reload >/dev/null 2>&1 || rollback_ok=0
  systemctl reset-failed fingerprint-classification.service >/dev/null 2>&1 || true

  local rb_since
  rb_since="$(date -d '2 seconds ago' '+%Y-%m-%d %H:%M:%S')"
  systemctl start captive-portal.service || rollback_ok=0
  wait_active captive-portal.service 30 || rollback_ok=0
  wait_portal_identity "$TARGET_HEAD" "$TARGET_TREE" "$rb_since" 45 || rollback_ok=0
  wait_portal_server_start "$rb_since" 45 || rollback_ok=0

  if [ -e "$INTEGRATION_DB" ]; then
    echo "ROLLBACK_CANONICAL_INTEGRATION_DB_PRESENT=YES"
    rollback_ok=0
  else
    echo "ROLLBACK_CANONICAL_INTEGRATION_DB_PRESENT=NO"
  fi

  local load_state
  load_state="$(systemctl show fingerprint-classification.service -p LoadState --value 2>/dev/null || true)"
  echo "ROLLBACK_CLASSIFICATION_LOAD_STATE=${load_state:-not-found}"
  [ -z "$load_state" ] || [ "$load_state" = "not-found" ] || rollback_ok=0

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
echo "MODE=TASK05_PROD_ACTIVATE_INTEGRATION_R2"
echo "PRODUCTION_CODE_SWITCH=NO"
echo "CONFIG_WRITE=YES"
echo "BASE_UNIT_INSTALL=EXACT_ACCEPTED_ARTIFACT"
echo "SYSTEMD_DROPIN_WRITE=EXECSTART_ONLY"
echo "DROPIN_EXECSTART=$VENV_PY -m app.device_fingerprint_integration.cli run"
echo "PROTECTHOME_RELAXATION=NO"
echo "PACKAGE_INSTALL=NO"
echo "SYSTEMD_ENABLE=YES"
echo "WORKER_START=YES"
echo "PORTAL_RESTART=YES"
echo "DATABASE_WRITE=TASK05_INTEGRATION_DB_ONLY"
echo "AUTOMATIC_ROLLBACK=YES"
echo "CONFIG_BACKUP_DIR=$BACKUP_DIR"

section "PRECONDITIONS"
HEAD="$(git -C "$PORTAL" rev-parse HEAD)"
TREE="$(git -C "$PORTAL" rev-parse 'HEAD^{tree}')"
STATUS="$(git -C "$PORTAL" status --porcelain=v1 --untracked-files=normal)"
echo "CURRENT_HEAD=$HEAD"
echo "CURRENT_TREE=$TREE"
[ "$HEAD" = "$TARGET_HEAD" ] || fail "Production not on accepted Task-05 commit"
[ "$TREE" = "$TARGET_TREE" ] || fail "Production tree mismatch"
[ -z "$STATUS" ] || fail "Production worktree dirty"
[ -f "$CFG" ] || fail "$CFG missing"
[ -f "$UNIT_SRC" ] || fail "Accepted Task-05 worker unit missing"
[ -x "$VENV_PY" ] || fail "Existing device-fingerprint venv Python missing"
[ -d "$TASK04_WT" ] || fail "Accepted Task-04 frozen worktree missing"
[ ! -e "$INTEGRATION_DB" ] || fail "Canonical integration DB already exists"
[ ! -e "$CONSUMER_LOCK" ] || fail "Canonical integration consumer lock already exists"

for path in "$EVIDENCE_DB" "$CLASS_DB" "$CONTROL_DB" "$REGISTRY_DB" "$VISIT_DB" "$CURRENT_STATE_DB"; do
  [ -f "$path" ] || fail "Required source DB missing: $path"
done

for unit in captive-portal.service fingerprint-evidence.service fingerprint-sensor.service fingerprint-suricata.service; do
  systemctl is-active --quiet "$unit" || fail "$unit is not active"
done

load_state="$(systemctl show fingerprint-classification.service -p LoadState --value 2>/dev/null || true)"
[ -z "$load_state" ] || [ "$load_state" = "not-found" ] \
  || fail "fingerprint-classification.service unexpectedly present"

echo "PRECONDITIONS=PASS"

section "VENV RUNTIME REPAIR PROOF"
sudo -u admin env \
  HOME=/nonexistent \
  PYTHONPATH="$PORTAL" \
  PYTHONDONTWRITEBYTECODE=1 \
  "$VENV_PY" -B - <<'PY'
mods = [
    "flask",
    "werkzeug",
    "app.device_fingerprint_integration.cli",
    "app.device_fingerprint_integration.runtime",
    "app.device_fingerprint.classification_read",
    "app.device_fingerprint.classification_persistence",
    "app.device_fingerprint.control_plane_store",
    "app.device_fingerprint.read_service",
    "app.visitor_registry.registry_read_service",
    "app.visit_lifecycle.read_service",
]
for name in mods:
    __import__(name)
    print("IMPORT_PASS="+name)
print("VENV_RUNTIME_REPAIR_PROOF=PASS")
PY

section "CURRENT CONFIG MUST BE DISABLED"
DUP_COUNT="$(grep -c '^DEVICE_FINGERPRINT_INTEGRATION_ENABLED=' "$CFG" || true)"
[ "$DUP_COUNT" -le 1 ] || fail "Duplicate integration enabled keys"
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
    *) fail "Integration unexpectedly enabled" ;;
  esac
fi
echo "CURRENT_CONFIG_DISABLED=PASS"

section "TASK04 PRE-ACTIVATION STATE"
sudo -H -u admin env \
  PYTHONPATH="$TASK04_WT" \
  PYTHONDONTWRITEBYTECODE=1 \
  CONTROL_DB="$CONTROL_DB" \
  CLASS_DB="$CLASS_DB" \
  /usr/bin/python3 -B - <<'PY'
import os, sqlite3
from app.device_fingerprint.control_plane_store import DeviceFingerprintControlPlaneStore
control=DeviceFingerprintControlPlaneStore(os.environ["CONTROL_DB"])
pin=control.pin_active_profile("classification")
print("ACTIVE_CRP="+pin.runtime_profile.artifact_id)
print("ACTIVE_RPM="+pin.admission_manifest.artifact_id)
print("ACTIVE_VALIDITY="+pin.validity_record.semantic_payload["state"])
if pin.validity_record.semantic_payload["state"] != "ACTIVE":
    raise SystemExit("FATAL: Task-04 profile not ACTIVE")
con=sqlite3.connect(f"file:{os.environ['CLASS_DB']}?mode=ro", uri=True)
try:
    rows=con.execute("SELECT COUNT(*) FROM classifications").fetchone()[0]
finally:
    con.close()
print("PRE_ACTIVATION_CLASSIFICATION_ROWS="+str(rows))
if rows != 1:
    raise SystemExit("FATAL: expected pre-activation classification baseline row count 1")
print("TASK04_PRE_ACTIVATION_STATE=PASS")
PY

section "CREATE SECURE BACKUP"
MUTATION_STARTED=1
install -d -m 0700 -o root -g root "$BACKUP_DIR"
cp -a "$CFG" "$CFG_BACKUP"
echo "CONFIG_BACKUP_CREATED=$CFG_BACKUP"

section "WRITE TASK05 CONFIG"
CFG="$CFG" /usr/bin/python3 - <<'PY'
import os, stat
from pathlib import Path
path=Path(os.environ["CFG"])
st=path.stat()
raw=path.read_text(encoding="utf-8")
updates={
"DEVICE_FINGERPRINT_INTEGRATION_ENABLED":"true",
"DEVICE_FINGERPRINT_INTEGRATION_DB_PATH":"/opt/CaptivePortal/data/device_fingerprint_integration.sqlite3",
"DEVICE_FINGERPRINT_EVIDENCE_DB_PATH":"/opt/CaptivePortal/data/device_fingerprint_evidence.sqlite3",
"DEVICE_FINGERPRINT_CLASSIFICATION_DB_PATH":"/opt/CaptivePortal/data/device_fingerprint_classification.sqlite3",
"DEVICE_FINGERPRINT_CONTROL_PLANE_DB_PATH":"/opt/CaptivePortal/data/device_fingerprint_control_plane.sqlite3",
}
lines=raw.splitlines()
seen={k:0 for k in updates}
out=[]
for line in lines:
    matched=False
    for key,value in updates.items():
        if line.startswith(key+"="):
            seen[key]+=1
            if seen[key] > 1:
                raise SystemExit(f"FATAL: duplicate config key {key}")
            out.append(f"{key}={value}")
            matched=True
            break
    if not matched:
        out.append(line)
missing=[k for k,v in seen.items() if v == 0]
if missing:
    if out and out[-1] != "":
        out.append("")
    out.append("# TASK-DEVICE-FINGERPRINT-05 production integration")
    for key in missing:
        out.append(f"{key}={updates[key]}")
tmp=path.with_name(path.name+".task05-r2.tmp")
tmp.write_text("\n".join(out)+"\n",encoding="utf-8")
os.chown(tmp,st.st_uid,st.st_gid)
os.chmod(tmp,stat.S_IMODE(st.st_mode))
os.replace(tmp,path)
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

section "INSTALL ACCEPTED UNIT PLUS NARROW RUNTIME DROPIN"
install -m 0644 -o root -g root "$UNIT_SRC" "$UNIT_DST"
cmp -s "$UNIT_SRC" "$UNIT_DST" || fail "Base worker unit differs from accepted artifact"
install -d -m 0755 -o root -g root "$DROPIN_DIR"
cat > "$DROPIN_DST" <<EOF
[Service]
ExecStart=
ExecStart=$VENV_PY -m app.device_fingerprint_integration.cli run
EOF
chmod 0644 "$DROPIN_DST"
chown root:root "$DROPIN_DST"

systemctl daemon-reload
systemd-analyze verify "$UNIT_DST" >/dev/null

echo "BASE_UNIT_SHA256=$(sha256sum "$UNIT_DST" | awk '{print $1}')"
echo "DROPIN_SHA256=$(sha256sum "$DROPIN_DST" | awk '{print $1}')"
echo "EFFECTIVE_EXECSTART=$(systemctl show fingerprint-classification.service -p ExecStart --value --no-pager)"
echo "EFFECTIVE_PROTECTHOME=$(systemctl show fingerprint-classification.service -p ProtectHome --value --no-pager)"
echo "EFFECTIVE_WORKINGDIRECTORY=$(systemctl show fingerprint-classification.service -p WorkingDirectory --value --no-pager)"
echo "DROPIN_PATHS=$(systemctl show fingerprint-classification.service -p DropInPaths --value --no-pager)"

EFFECTIVE_EXEC="$(systemctl show fingerprint-classification.service -p ExecStart --value --no-pager)"
[[ "$EFFECTIVE_EXEC" == *"$VENV_PY -m app.device_fingerprint_integration.cli run"* ]] \
  || fail "Effective worker ExecStart is not repaired venv runtime"
[ "$(systemctl show fingerprint-classification.service -p ProtectHome --value --no-pager)" = "yes" ] \
  || fail "ProtectHome was not preserved"
echo "NARROW_RUNTIME_DROPIN=PASS"

section "START WORKER BEFORE PORTAL ENQUEUE"
WORKER_START_SINCE="$(date -d '2 seconds ago' '+%Y-%m-%d %H:%M:%S')"
systemctl enable fingerprint-classification.service >/dev/null
systemctl start fingerprint-classification.service
wait_active fingerprint-classification.service 30 || fail "worker did not become active"
wait_worker_ready "$WORKER_START_SINCE" 25 || fail "worker ready telemetry not observed"

WORKER_PID="$(systemctl show fingerprint-classification.service -p MainPID --value --no-pager)"
WORKER_RESTARTS="$(systemctl show fingerprint-classification.service -p NRestarts --value --no-pager)"
echo "WORKER_PID=$WORKER_PID"
echo "WORKER_NRESTARTS=$WORKER_RESTARTS"
[ "$WORKER_RESTARTS" = "0" ] || fail "worker restarted unexpectedly"

[ -f "$INTEGRATION_DB" ] || fail "worker did not initialize integration DB"
echo "INTEGRATION_DB_STAT=$(stat -c '%U:%G mode=%a bytes=%s' "$INTEGRATION_DB")"
[ "$(stat -c '%U:%G' "$INTEGRATION_DB")" = "admin:admin" ] || fail "integration DB owner mismatch"
[ "$(stat -c '%a' "$INTEGRATION_DB")" = "600" ] || fail "integration DB mode mismatch"

INTEGRATION_DB="$INTEGRATION_DB" /usr/bin/python3 - <<'PY'
import os, sqlite3
con=sqlite3.connect(f"file:{os.environ['INTEGRATION_DB']}?mode=ro",uri=True)
try:
    quick=con.execute("PRAGMA quick_check").fetchone()[0]
    version=con.execute("PRAGMA user_version").fetchone()[0]
    rows=con.execute("SELECT COUNT(*) FROM integration_jobs").fetchone()[0]
finally:
    con.close()
print("INTEGRATION_DB_QUICK_CHECK="+quick)
print("INTEGRATION_DB_USER_VERSION="+str(version))
print("INTEGRATION_JOBS_BEFORE_PORTAL_RESTART="+str(rows))
if quick != "ok" or version != 1 or rows != 0:
    raise SystemExit("FATAL: integration DB initialization gate failed")
print("INTEGRATION_DB_INITIALIZATION=PASS")
PY

section "RESTART PORTAL WITH INTEGRATION ENABLED"
PORTAL_START_SINCE="$(date -d '2 seconds ago' '+%Y-%m-%d %H:%M:%S')"
systemctl restart captive-portal.service
wait_active captive-portal.service 30 || fail "Portal did not become active"
wait_portal_identity "$TARGET_HEAD" "$TARGET_TREE" "$PORTAL_START_SINCE" 45 \
  || fail "fresh Portal identity not observed"
wait_portal_server_start "$PORTAL_START_SINCE" 45 \
  || fail "Portal did not reach server start"
sleep 5
systemctl is-active --quiet captive-portal.service || fail "Portal not stable"
systemctl is-active --quiet fingerprint-classification.service || fail "worker not active after Portal restart"

PORTAL_RESTARTS="$(systemctl show captive-portal.service -p NRestarts --value --no-pager)"
WORKER_RESTARTS_POST="$(systemctl show fingerprint-classification.service -p NRestarts --value --no-pager)"
echo "PORTAL_NRESTARTS=$PORTAL_RESTARTS"
echo "WORKER_NRESTARTS_POST=$WORKER_RESTARTS_POST"
[ "$PORTAL_RESTARTS" = "0" ] || fail "Portal automatic restart count non-zero"
[ "$WORKER_RESTARTS_POST" = "0" ] || fail "worker automatic restart count non-zero"
echo "PORTAL_AND_WORKER_STABLE=PASS"

section "POST-ACTIVATION DATABASE STATE"
INTEGRATION_DB="$INTEGRATION_DB" CLASS_DB="$CLASS_DB" /usr/bin/python3 - <<'PY'
import os, sqlite3
icon=sqlite3.connect(f"file:{os.environ['INTEGRATION_DB']}?mode=ro",uri=True)
try:
    quick=icon.execute("PRAGMA quick_check").fetchone()[0]
    jobs=icon.execute("SELECT COUNT(*) FROM integration_jobs").fetchone()[0]
    states=icon.execute(
        "SELECT classification_state,COUNT(*) FROM integration_jobs GROUP BY classification_state ORDER BY classification_state"
    ).fetchall()
finally:
    icon.close()
ccon=sqlite3.connect(f"file:{os.environ['CLASS_DB']}?mode=ro",uri=True)
try:
    classifications=ccon.execute("SELECT COUNT(*) FROM classifications").fetchone()[0]
finally:
    ccon.close()
print("POST_ACTIVATION_INTEGRATION_QUICK_CHECK="+quick)
print("POST_ACTIVATION_INTEGRATION_JOBS="+str(jobs))
print("POST_ACTIVATION_JOB_STATES="+(",".join(f"{s}:{n}" for s,n in states) if states else "NONE"))
print("POST_ACTIVATION_CLASSIFICATION_ROWS="+str(classifications))
if quick != "ok":
    raise SystemExit("FATAL: integration DB quick_check failed")
if classifications != 1:
    raise SystemExit("FATAL: classification baseline changed before controlled proof")
print("POST_ACTIVATION_DB_STATE=PASS")
PY

section "FINAL INVARIANTS"
[ "$(git -C "$PORTAL" rev-parse HEAD)" = "$TARGET_HEAD" ] || fail "production HEAD changed"
[ "$(git -C "$PORTAL" rev-parse 'HEAD^{tree}')" = "$TARGET_TREE" ] || fail "production tree changed"
[ -z "$(git -C "$PORTAL" status --porcelain=v1 --untracked-files=normal)" ] || fail "production worktree dirty"

for unit in captive-portal.service fingerprint-evidence.service fingerprint-sensor.service fingerprint-suricata.service fingerprint-classification.service; do
  systemctl is-active --quiet "$unit" || fail "$unit not active"
done
systemctl is-enabled --quiet fingerprint-classification.service || fail "worker not enabled for boot"
cmp -s "$UNIT_SRC" "$UNIT_DST" || fail "base worker unit drift"
[ -f "$DROPIN_DST" ] || fail "runtime drop-in missing"
grep -qxF 'DEVICE_FINGERPRINT_INTEGRATION_ENABLED=true' "$CFG" || fail "integration config not enabled"
[ -f "$INTEGRATION_DB" ] || fail "integration DB missing"

echo "FINAL_EFFECTIVE_EXECSTART=$(systemctl show fingerprint-classification.service -p ExecStart --value --no-pager)"
echo "FINAL_PROTECTHOME=$(systemctl show fingerprint-classification.service -p ProtectHome --value --no-pager)"
echo "FINAL_RUNTIME_INVARIANTS=PASS"

COMPLETED=1
trap - ERR

section "FINAL"
echo "CURRENT_PRODUCTION_HEAD=$TARGET_HEAD"
echo "CURRENT_PRODUCTION_TREE=$TARGET_TREE"
echo "TASK05_BASE_UNIT=EXACT_ACCEPTED_ARTIFACT"
echo "TASK05_RUNTIME_REPAIR=SYSTEMD_DROPIN_EXECSTART_ONLY"
echo "TASK05_RUNTIME_PYTHON=$VENV_PY"
echo "TASK05_PROTECTHOME_PRESERVED=YES"
echo "TASK05_INTEGRATION_ENABLED=YES"
echo "TASK05_CLASSIFICATION_WORKER_ACTIVE=YES"
echo "TASK05_CLASSIFICATION_WORKER_ENABLED_FOR_BOOT=YES"
echo "TASK05_INTEGRATION_DB_SCHEMA=1"
echo "TASK05_PROD_ACTIVATION=PASS"
echo "OWNER_CONTROLLED_AUTH_PROOF=PENDING"
echo "AUTOMATIC_ROLLBACK_USED=NO"
