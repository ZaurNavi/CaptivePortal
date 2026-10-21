#!/usr/bin/env bash
set -Eeuo pipefail
export SYSTEMD_PAGER=cat
export PAGER=cat

PORTAL="/opt/CaptivePortal"
CFG="/etc/default/captive-portal"
INTEGRATION_DB="/opt/CaptivePortal/data/device_fingerprint_integration.sqlite3"
TARGET_HEAD="1d88f4ae947fa95454dbb54c70f9d6bdd13b1d22"
TARGET_TREE="8183bf48abfc71c1b488c0667efc0f1ae717003e"

section(){ printf '\n===== %s =====\n' "$1"; }
fail(){ echo "FATAL: $*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || fail "Run with sudo/root"

section "DECLARATION"
date --iso-8601=seconds
echo "MODE=READ_ONLY_TASK05_WORKER_FAILURE_AUDIT"
echo "GIT_WRITE=NO"
echo "CONFIG_WRITE=NO"
echo "SYSTEMD_WRITE=NO"
echo "SERVICE_RESTART=NO"
echo "DATABASE_WRITE=NO"

section "CURRENT PRODUCTION"
HEAD="$(git -C "$PORTAL" rev-parse HEAD)"
TREE="$(git -C "$PORTAL" rev-parse 'HEAD^{tree}')"
STATUS="$(git -C "$PORTAL" status --porcelain=v1 --untracked-files=normal)"
echo "CURRENT_HEAD=$HEAD"
echo "CURRENT_TREE=$TREE"
[ "$HEAD" = "$TARGET_HEAD" ] || fail "Production left accepted Task-05 commit"
[ "$TREE" = "$TARGET_TREE" ] || fail "Production Task-05 tree mismatch"
[ -z "$STATUS" ] || fail "Production worktree dirty"
systemctl is-active --quiet captive-portal.service || fail "captive-portal.service is not active"
echo "PORTAL_ACTIVE=PASS"

section "RESTORED CONFIG STATE"
grep -E '^DEVICE_FINGERPRINT_(INTEGRATION_ENABLED|INTEGRATION_DB_PATH|EVIDENCE_DB_PATH|CLASSIFICATION_DB_PATH|CONTROL_PLANE_DB_PATH)=' "$CFG" || true
CFG_VALUE="$(awk -F= '
  $1=="DEVICE_FINGERPRINT_INTEGRATION_ENABLED" {
    value=substr($0,index($0,"=")+1)
    gsub(/^[ \t]+|[ \t]+$/, "", value)
    print value
  }' "$CFG" | tail -n1)"
if [ -z "$CFG_VALUE" ]; then
  echo "CURRENT_INTEGRATION_ENABLED=ABSENT_DEFAULT_FALSE"
else
  echo "CURRENT_INTEGRATION_ENABLED=$CFG_VALUE"
  case "${CFG_VALUE,,}" in
    false|0|no|off) ;;
    *) fail "Rollback did not restore integration-disabled config" ;;
  esac
fi
echo "CONFIG_ROLLBACK_STATE=PASS"

section "INTEGRATION ARTIFACT STATE"
if [ -e "$INTEGRATION_DB" ]; then
  echo "INTEGRATION_DB_PRESENT=YES"
  stat -c 'INTEGRATION_DB=%n OWNER=%U:%G MODE=%a BYTES=%s' "$INTEGRATION_DB"
else
  echo "INTEGRATION_DB_PRESENT=NO"
fi
if [ -e "${INTEGRATION_DB}.consumer.lock" ]; then
  echo "CONSUMER_LOCK_PRESENT=YES"
  stat -c 'CONSUMER_LOCK=%n OWNER=%U:%G MODE=%a BYTES=%s' "${INTEGRATION_DB}.consumer.lock"
else
  echo "CONSUMER_LOCK_PRESENT=NO"
fi
if systemctl list-unit-files fingerprint-classification.service --no-legend 2>/dev/null \
  | grep -q '^fingerprint-classification.service'; then
  echo "CLASSIFICATION_UNIT_PRESENT=YES"
else
  echo "CLASSIFICATION_UNIT_PRESENT=NO"
fi

section "WORKER JOURNAL AROUND FAILURE"
journalctl -u fingerprint-classification.service \
  --since "2026-10-04 00:50:00" \
  --until "2026-10-04 00:53:30" \
  --no-pager -o short-iso-precise || true

section "WORKER JOURNAL RAW"
journalctl -u fingerprint-classification.service \
  --since "2026-10-04 00:50:00" \
  --until "2026-10-04 00:53:30" \
  --no-pager -o cat || true

section "WORKER FAILURE MARKERS"
journalctl -u fingerprint-classification.service \
  --since "2026-10-04 00:50:00" \
  --until "2026-10-04 00:53:30" \
  --no-pager -o cat 2>/dev/null \
  | grep -E 'Traceback|ModuleNotFoundError|ImportError|ValueError|IntegrationError|PermissionError|FileNotFoundError|failed|Failed|error|Error|fingerprint.integration' \
  | tail -n 120 || true

section "PORTAL ROLLBACK JOURNAL"
journalctl -u captive-portal.service \
  --since "2026-10-04 00:51:45" \
  --until "2026-10-04 00:53:30" \
  --no-pager -o cat 2>/dev/null \
  | grep -E 'captivportal_loaded_artifact_identity|Starting Captive Portal|Configuration loaded|Starting server on |startup_failed' \
  | tail -n 40 || true

section "SYSTEMD HISTORICAL STATUS"
# Unit may already be removed; journal is authoritative. Show any retained failed state if systemd knows it.
systemctl show fingerprint-classification.service \
  -p LoadState -p ActiveState -p SubState -p Result -p ExecMainCode -p ExecMainStatus \
  -p NRestarts -p MainPID -p FragmentPath -p UnitFileState \
  --no-pager 2>/dev/null || true

section "RUNTIME DEPENDENCY IMPORT PROBE AS ADMIN"
sudo -H -u admin env \
  PYTHONPATH="$PORTAL" \
  PYTHONDONTWRITEBYTECODE=1 \
  /usr/bin/python3 -B - <<'PY'
mods = [
    "app.device_fingerprint_integration.cli",
    "app.device_fingerprint_integration.runtime",
    "app.device_fingerprint.classification_read",
    "app.device_fingerprint.classification_persistence",
    "app.device_fingerprint.control_plane_store",
    "app.device_fingerprint.read_service",
    "app.visitor_registry.registry_config",
    "app.visitor_registry.registry_repository",
    "app.visitor_registry.registry_read_service",
    "app.visit_lifecycle.config",
    "app.visit_lifecycle.repository",
    "app.visit_lifecycle.read_service",
]
for name in mods:
    try:
        __import__(name)
    except Exception as exc:
        print(f"IMPORT_FAIL={name}|{type(exc).__name__}|{exc}")
        raise
    else:
        print(f"IMPORT_PASS={name}")
print("WORKER_DEPENDENCY_IMPORT_PROBE=PASS")
PY

section "FINAL"
echo "TASK05_WORKER_FAILURE_AUDIT=COMPLETE"
echo "CHANGES_MADE=NONE"
