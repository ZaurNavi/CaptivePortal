#!/usr/bin/env bash
set -Eeuo pipefail

export SYSTEMD_PAGER=cat
export PAGER=cat

PORTAL="/opt/CaptivePortal"
STAGE="/home/admin/CaptivePortal-Deploy/task05-merged-1d88f4ae"
CFG="/etc/default/captive-portal"
INTEGRATION_DB="/opt/CaptivePortal/data/device_fingerprint_integration.sqlite3"

EXPECTED_CURRENT_HEAD="f5e3d194ebffb3c6c1e1cd8afc31f80911e2ce71"
EXPECTED_CURRENT_TREE="02b6af353643a4321a6f14d01735b9c0e305842e"
EXPECTED_TASK05_HEAD="1d88f4ae947fa95454dbb54c70f9d6bdd13b1d22"
EXPECTED_TASK05_TREE="8183bf48abfc71c1b488c0667efc0f1ae717003e"

section(){ printf '\n===== %s =====\n' "$1"; }
fail(){ echo "FATAL: $*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || fail "Run with sudo/root"

section "DECLARATION"
date --iso-8601=seconds
echo "MODE=READ_ONLY_TASK05_PROD_PRESWITCH_COMPAT"
echo "PORTAL_SWITCH=NO"
echo "CONFIG_WRITE=NO"
echo "SYSTEMD_WRITE=NO"
echo "SERVICE_RESTART=NO"
echo "DATABASE_WRITE=NO"
echo "STAGE_WRITE=NO"

section "EXACT ARTIFACTS"
[ -d "$PORTAL/.git" ] || fail "Production Git worktree missing"
[ -d "$STAGE/.git" ] || fail "Task-05 staged Git clone missing"

PROD_HEAD="$(git -C "$PORTAL" rev-parse HEAD)"
PROD_TREE="$(git -C "$PORTAL" rev-parse 'HEAD^{tree}')"
PROD_STATUS="$(git -C "$PORTAL" status --porcelain=v1 --untracked-files=normal)"
STAGE_HEAD="$(git -C "$STAGE" rev-parse HEAD)"
STAGE_TREE="$(git -C "$STAGE" rev-parse 'HEAD^{tree}')"
STAGE_STATUS="$(git -C "$STAGE" status --porcelain=v1 --untracked-files=normal)"

echo "PRODUCTION_HEAD=$PROD_HEAD"
echo "PRODUCTION_TREE=$PROD_TREE"
echo "STAGED_HEAD=$STAGE_HEAD"
echo "STAGED_TREE=$STAGE_TREE"

[ "$PROD_HEAD" = "$EXPECTED_CURRENT_HEAD" ] || fail "Production HEAD changed"
[ "$PROD_TREE" = "$EXPECTED_CURRENT_TREE" ] || fail "Production tree changed"
[ -z "$PROD_STATUS" ] || fail "Production worktree dirty"
[ "$STAGE_HEAD" = "$EXPECTED_TASK05_HEAD" ] || fail "Staged Task-05 HEAD mismatch"
[ "$STAGE_TREE" = "$EXPECTED_TASK05_TREE" ] || fail "Staged Task-05 tree mismatch"
[ -z "$STAGE_STATUS" ] || fail "Staged Task-05 worktree dirty"
echo "EXACT_ARTIFACTS=PASS"

section "INTEGRATION MUST REMAIN DISABLED"
[ -f "$CFG" ] || fail "$CFG missing"

CFG_VALUE="$(awk -F= '
  $1=="DEVICE_FINGERPRINT_INTEGRATION_ENABLED" {
    value=substr($0,index($0,"=")+1)
    gsub(/^[ \t]+|[ \t]+$/, "", value)
    print value
  }' "$CFG" | tail -n1)"
UNIT_VALUES="$(systemctl cat captive-portal.service --no-pager 2>/dev/null \
  | sed -n 's/^[[:space:]]*Environment=["'\'']\?DEVICE_FINGERPRINT_INTEGRATION_ENABLED=\([^"'\'']*\)["'\'']\?/\1/p' \
  || true)"

if [ -z "$CFG_VALUE" ]; then
  echo "ENVFILE_INTEGRATION_ENABLED=ABSENT_DEFAULT_FALSE"
else
  case "${CFG_VALUE,,}" in
    false|0|no|off)
      echo "ENVFILE_INTEGRATION_ENABLED=$CFG_VALUE"
      ;;
    *)
      fail "DEVICE_FINGERPRINT_INTEGRATION_ENABLED is not disabled in $CFG"
      ;;
  esac
fi

if [ -z "$UNIT_VALUES" ]; then
  echo "UNIT_INTEGRATION_OVERRIDE=ABSENT"
else
  echo "UNIT_INTEGRATION_OVERRIDE_PRESENT=YES"
  while IFS= read -r value; do
    case "${value,,}" in
      false|0|no|off) ;;
      *) fail "captive-portal.service has an enabled integration override" ;;
    esac
  done <<< "$UNIT_VALUES"
fi

[ ! -e "$INTEGRATION_DB" ] || fail "Integration DB already exists before code-only switch"
echo "INTEGRATION_DISABLED_PRECONDITION=PASS"

section "STAGED PYTHON SYNTAX"
STAGE="$STAGE" /usr/bin/python3 -B - <<'PY'
import os
from pathlib import Path

root = Path(os.environ["STAGE"])
paths = [root / "run.py"]
paths.extend(sorted((root / "app").rglob("*.py")))
count = 0
for path in paths:
    source = path.read_text(encoding="utf-8")
    compile(source, str(path), "exec")
    count += 1
print(f"PYTHON_FILES_COMPILED_IN_MEMORY={count}")
print("STAGED_PYTHON_SYNTAX=PASS")
PY

section "RUNTIME PYTHON IDENTITY"
echo "SERVICE_USER=$(systemctl show captive-portal.service -p User --value --no-pager)"
[ "$(systemctl show captive-portal.service -p User --value --no-pager)" = "admin" ] \
  || fail "Unexpected captive-portal runtime user"

sudo -H -u admin env PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -B - <<'PY'
import sys
print("PYTHON_EXECUTABLE="+sys.executable)
print("PYTHON_VERSION="+sys.version.split()[0])
try:
    import flask
    import werkzeug
except Exception as exc:
    raise SystemExit(f"FATAL: runtime user cannot import Flask/Werkzeug: {type(exc).__name__}: {exc}")
print("FLASK_MODULE="+str(getattr(flask, "__file__", "")))
print("WERKZEUG_MODULE="+str(getattr(werkzeug, "__file__", "")))
print("RUNTIME_DEPENDENCY_IMPORTS=PASS")
PY

section "STAGED RUNTIME IMPORT SMOKE"
DB_BEFORE="ABSENT"
[ -e "$INTEGRATION_DB" ] && DB_BEFORE="PRESENT"
echo "INTEGRATION_DB_BEFORE_SMOKE=$DB_BEFORE"

sudo -H -u admin env \
  PYTHONPATH="$STAGE" \
  PYTHONDONTWRITEBYTECODE=1 \
  DEVICE_FINGERPRINT_INTEGRATION_ENABLED=false \
  STAGE="$STAGE" \
  /usr/bin/python3 -B - <<'PY'
import inspect
import os
import sys

stage = os.environ["STAGE"]
os.chdir(stage)
if sys.path[0] != "":
    # PYTHONPATH already pins the staged source; this is diagnostic only.
    pass

import run
from app.web.web import create_app
from app.device_fingerprint_integration.config import integration_config_from_settings
from app.device_fingerprint_integration.runtime import create_fingerprint_integration_submitter
from app.device_fingerprint_integration.submitter import (
    DISABLED_FINGERPRINT_INTEGRATION_SUBMITTER,
)

settings = {
    "device_fingerprint_integration_enabled": False,
}
config = integration_config_from_settings(settings)

if config.enabled is not False:
    raise SystemExit("FATAL: staged integration config did not resolve disabled")

if "fingerprint_integration_submitter" not in inspect.signature(create_app).parameters:
    raise SystemExit("FATAL: create_app Task-05 hook missing")

submitter = create_fingerprint_integration_submitter(settings)
if submitter is not DISABLED_FINGERPRINT_INTEGRATION_SUBMITTER:
    raise SystemExit("FATAL: disabled configuration created a live submitter")

if not callable(run.main):
    raise SystemExit("FATAL: staged run.main is unavailable")

run_path = os.path.realpath(run.__file__)
if not run_path.startswith(os.path.realpath(stage) + os.sep):
    raise SystemExit(f"FATAL: run imported from unexpected path: {run_path}")

print("STAGED_RUN_MODULE="+run_path)
print("STAGED_IMPORT_RUN=PASS")
print("STAGED_CREATE_APP_TASK05_HOOK=PASS")
print("STAGED_INTEGRATION_CONFIG=DISABLED")
print("STAGED_DISABLED_SUBMITTER=PASS")
print("STAGED_RUNTIME_IMPORT_SMOKE=PASS")
PY

[ ! -e "$INTEGRATION_DB" ] || fail "Runtime import smoke created integration DB"
echo "INTEGRATION_DB_AFTER_SMOKE=ABSENT"

section "CURRENT SERVICE TOPOLOGY"
systemctl is-active --quiet captive-portal.service || fail "captive-portal.service not active"
systemctl show captive-portal.service \
  -p MainPID -p NRestarts -p ActiveState -p SubState -p WorkingDirectory -p FragmentPath \
  --no-pager
echo "CAPTIVE_PORTAL_EXECSTART=$(systemctl show captive-portal.service -p ExecStart --value --no-pager)"

for unit in fingerprint-evidence.service fingerprint-sensor.service fingerprint-suricata.service; do
  echo "--- $unit ---"
  systemctl is-active --quiet "$unit" || fail "$unit not active"
  systemctl show "$unit" \
    -p MainPID -p NRestarts -p ActiveState -p SubState -p WorkingDirectory -p FragmentPath \
    --no-pager
  echo "EXECSTART=$(systemctl show "$unit" -p ExecStart --value --no-pager)"
done

if systemctl list-unit-files fingerprint-classification.service --no-legend 2>/dev/null \
  | grep -q '^fingerprint-classification.service'; then
  fail "Task-05 classification unit appeared before activation"
fi
echo "CLASSIFICATION_UNIT_STILL_ABSENT=PASS"

section "POSTCHECK"
[ "$(git -C "$PORTAL" rev-parse HEAD)" = "$EXPECTED_CURRENT_HEAD" ] \
  || fail "Production HEAD changed during read-only gate"
[ "$(git -C "$PORTAL" rev-parse 'HEAD^{tree}')" = "$EXPECTED_CURRENT_TREE" ] \
  || fail "Production tree changed during read-only gate"
[ -z "$(git -C "$PORTAL" status --porcelain=v1 --untracked-files=normal)" ] \
  || fail "Production worktree changed during read-only gate"
[ -z "$(git -C "$STAGE" status --porcelain=v1 --untracked-files=normal)" ] \
  || fail "Staged worktree changed during read-only gate"
[ ! -e "$INTEGRATION_DB" ] || fail "Integration DB appeared during read-only gate"
systemctl is-active --quiet captive-portal.service || fail "Portal stopped during read-only gate"
echo "READ_ONLY_INVARIANTS=PASS"

section "FINAL"
echo "CURRENT_PRODUCTION_ROLLBACK_POINT=$EXPECTED_CURRENT_HEAD"
echo "TASK05_TARGET_COMMIT=$EXPECTED_TASK05_HEAD"
echo "TASK05_TARGET_TREE=$EXPECTED_TASK05_TREE"
echo "TASK05_PROD_PRESWITCH_COMPAT=PASS"
echo "CHANGES_MADE=NONE"
