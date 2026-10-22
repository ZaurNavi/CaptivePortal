#!/usr/bin/env bash
set -Eeuo pipefail
export SYSTEMD_PAGER=cat
export PAGER=cat

PORTAL="/opt/CaptivePortal"
OLD_HEAD="f5e3d194ebffb3c6c1e1cd8afc31f80911e2ce71"
OLD_TREE="02b6af353643a4321a6f14d01735b9c0e305842e"
TARGET_HEAD="1d88f4ae947fa95454dbb54c70f9d6bdd13b1d22"
TARGET_TREE="8183bf48abfc71c1b488c0667efc0f1ae717003e"
INTEGRATION_DB="/opt/CaptivePortal/data/device_fingerprint_integration.sqlite3"
CONTROL_DB="/opt/CaptivePortal/data/device_fingerprint_control_plane.sqlite3"
CLASS_DB="/opt/CaptivePortal/data/device_fingerprint_classification.sqlite3"

section(){ printf '\n===== %s =====\n' "$1"; }
fail(){ echo "FATAL: $*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || fail "Run with sudo/root"

section "DECLARATION"
date --iso-8601=seconds
echo "MODE=READ_ONLY_TASK05_SWITCH_FAILURE_AUDIT"
echo "GIT_WRITE=NO"
echo "CONFIG_WRITE=NO"
echo "SYSTEMD_WRITE=NO"
echo "SERVICE_RESTART=NO"
echo "DATABASE_WRITE=NO"

section "CURRENT PRODUCTION GIT"
HEAD="$(git -C "$PORTAL" rev-parse HEAD)"
TREE="$(git -C "$PORTAL" rev-parse 'HEAD^{tree}')"
STATUS="$(git -C "$PORTAL" status --porcelain=v1 --untracked-files=normal)"
echo "CURRENT_HEAD=$HEAD"
echo "CURRENT_TREE=$TREE"
[ -z "$STATUS" ] || { echo "$STATUS"; fail "Production worktree is dirty"; }

case "$HEAD:$TREE" in
  "$OLD_HEAD:$OLD_TREE")
    echo "CURRENT_CODE_STATE=ROLLBACK_POINT"
    ;;
  "$TARGET_HEAD:$TARGET_TREE")
    echo "CURRENT_CODE_STATE=TASK05_TARGET"
    ;;
  *)
    fail "Current production code is neither approved rollback point nor Task-05 target"
    ;;
esac
echo "CURRENT_GIT_STATE=PASS"

section "RECENT HEAD REFLOG"
git -C "$PORTAL" reflog show HEAD --date=iso-strict --format='%H|%gd|%gs' -n 8

section "SERVICE STATES"
for unit in captive-portal.service fingerprint-evidence.service fingerprint-sensor.service fingerprint-suricata.service; do
  echo "--- $unit ---"
  systemctl show "$unit" \
    -p MainPID -p NRestarts -p ActiveState -p SubState -p Result \
    -p ExecMainCode -p ExecMainStatus -p ExecMainStartTimestamp \
    -p WorkingDirectory -p StandardOutput -p StandardError -p FragmentPath \
    --no-pager
  echo "EXECSTART=$(systemctl show "$unit" -p ExecStart --value --no-pager)"
done

section "PORTAL PROCESS BINDING"
PORTAL_PID="$(systemctl show captive-portal.service -p MainPID --value --no-pager)"
if [[ "$PORTAL_PID" =~ ^[0-9]+$ ]] && [ "$PORTAL_PID" -gt 0 ] && [ -d "/proc/$PORTAL_PID" ]; then
  echo "PORTAL_PID=$PORTAL_PID"
  echo "PORTAL_PROC_CWD=$(readlink -f "/proc/$PORTAL_PID/cwd" || true)"
  echo -n "PORTAL_PROC_CMDLINE="
  tr '\0' ' ' < "/proc/$PORTAL_PID/cmdline" || true
  echo
else
  echo "PORTAL_PID=$PORTAL_PID"
  echo "PORTAL_PROCESS_PRESENT=NO"
fi

section "TARGETED PORTAL LOG VISIBILITY"
echo "JOURNAL_IDENTITY_LINES:"
journalctl -u captive-portal.service --since "2026-10-04 00:25:00" --no-pager -o cat 2>/dev/null \
  | grep -E 'captivportal_loaded_artifact_identity|captivportal_artifact_identity_startup_failed' \
  | tail -n 10 || true
echo "JOURNAL_STARTUP_MARKERS:"
journalctl -u captive-portal.service --since "2026-10-04 00:25:00" --no-pager -o cat 2>/dev/null \
  | grep -E 'Starting Captive Portal|Configuration loaded|Starting server on ' \
  | tail -n 20 || true

section "ACTIVE PROCESS PROVENANCE FALLBACK"
if systemctl is-active --quiet captive-portal.service; then
  START_RAW="$(systemctl show captive-portal.service -p ExecMainStartTimestamp --value --no-pager)"
  START_EPOCH="$(date -d "$START_RAW" +%s 2>/dev/null || true)"
  echo "PORTAL_START_TIMESTAMP=$START_RAW"
  echo "PORTAL_START_EPOCH=$START_EPOCH"
  [[ "$START_EPOCH" =~ ^[0-9]+$ ]] || fail "Cannot parse Portal process start timestamp"

  REFLOG="$(git -C "$PORTAL" reflog show HEAD --date=unix --format='%H|%gd|%gs' 2>/dev/null || true)"
  [ -n "$REFLOG" ] || fail "HEAD reflog unavailable"

  REFLOG="$REFLOG" START_EPOCH="$START_EPOCH" CURRENT_HEAD="$HEAD" \
  /usr/bin/python3 - <<'PY'
import os, re
start = int(os.environ["START_EPOCH"])
current = os.environ["CURRENT_HEAD"]
entries = []
for raw in os.environ["REFLOG"].splitlines():
    parts = raw.split("|", 2)
    if len(parts) != 3:
        continue
    sha, selector, action = parts
    m = re.search(r"HEAD@\{(\d+)\}", selector)
    if m:
        entries.append((int(m.group(1)), sha, action))
at_or_before = next((e for e in entries if e[0] <= start), None)
if at_or_before is None:
    raise SystemExit("FATAL: No reflog state at/before active Portal start")
ts, sha, action = at_or_before
print("HEAD_AT_ACTIVE_PORTAL_START="+sha)
print("HEAD_AT_ACTIVE_PORTAL_START_ACTION="+action)
print("HEAD_TO_PORTAL_START_DELTA_SECONDS="+str(start-ts))
if sha != current:
    raise SystemExit(
        f"FATAL: active Portal started with {sha}, but current worktree is {current}"
    )
print("ACTIVE_PORTAL_START_HEAD_MATCH=PASS")
PY

  grep -q 'capture_loaded_artifact_identity("captive-portal.service")' "$PORTAL/run.py" \
    || fail "Startup identity capture call missing"
  grep -q 'captivportal_artifact_identity_startup_failed' "$PORTAL/run.py" \
    || fail "Fail-closed startup identity guard missing"
  echo "STARTUP_IDENTITY_FAIL_CLOSED_GUARD=PASS"
else
  echo "ACTIVE_PROCESS_PROVENANCE_FALLBACK=SKIPPED_PORTAL_INACTIVE"
fi

section "TASK05 MUST STILL BE INACTIVE"
if [ -e "$INTEGRATION_DB" ]; then
  echo "INTEGRATION_DB_PRESENT=YES"
  stat -c 'INTEGRATION_DB_OWNER=%U:%G MODE=%a BYTES=%s' "$INTEGRATION_DB"
else
  echo "INTEGRATION_DB_PRESENT=NO"
fi

if systemctl list-unit-files fingerprint-classification.service --no-legend 2>/dev/null \
  | grep -q '^fingerprint-classification.service'; then
  echo "CLASSIFICATION_UNIT_PRESENT=YES"
else
  echo "CLASSIFICATION_UNIT_PRESENT=NO"
fi

section "TASK04 READ-ONLY STATE"
sudo -H -u admin env \
  PYTHONPATH="$PORTAL" \
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
con=sqlite3.connect(f"file:{os.environ['CLASS_DB']}?mode=ro", uri=True)
try:
    rows=con.execute("SELECT COUNT(*) FROM classifications").fetchone()[0]
finally:
    con.close()
print("CLASSIFICATION_ROWS="+str(rows))
if pin.validity_record.semantic_payload["state"] != "ACTIVE":
    raise SystemExit("FATAL: Task-04 active validity is not ACTIVE")
if rows != 1:
    raise SystemExit("FATAL: Task-04 classification row count changed")
print("TASK04_READ_STATE=PASS")
PY

section "FINAL"
if systemctl is-active --quiet captive-portal.service \
   && systemctl is-active --quiet fingerprint-evidence.service \
   && systemctl is-active --quiet fingerprint-sensor.service \
   && systemctl is-active --quiet fingerprint-suricata.service; then
  echo "ALL_EXPECTED_SERVICES_ACTIVE=YES"
else
  echo "ALL_EXPECTED_SERVICES_ACTIVE=NO"
fi
echo "TASK05_SWITCH_FAILURE_AUDIT=COMPLETE"
echo "CHANGES_MADE=NONE"
