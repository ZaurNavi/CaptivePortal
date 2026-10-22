#!/usr/bin/env bash
set -Eeuo pipefail
export SYSTEMD_PAGER=cat
export PAGER=cat

PORTAL="/opt/CaptivePortal"
VENV_PY="/opt/captiveportal-runtime/device-fingerprint-venv/bin/python"
TARGET_HEAD="1d88f4ae947fa95454dbb54c70f9d6bdd13b1d22"
TARGET_TREE="8183bf48abfc71c1b488c0667efc0f1ae717003e"

section(){ printf '\n===== %s =====\n' "$1"; }
fail(){ echo "FATAL: $*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || fail "Run with sudo/root"

section "DECLARATION"
date --iso-8601=seconds
echo "MODE=READ_ONLY_TASK05_WORKER_PYTHON_RUNTIME_PROBE"
echo "CONFIG_WRITE=NO"
echo "SYSTEMD_WRITE=NO"
echo "SERVICE_RESTART=NO"
echo "DATABASE_WRITE=NO"

section "PRODUCTION IDENTITY"
HEAD="$(git -C "$PORTAL" rev-parse HEAD)"
TREE="$(git -C "$PORTAL" rev-parse 'HEAD^{tree}')"
echo "CURRENT_HEAD=$HEAD"
echo "CURRENT_TREE=$TREE"
[ "$HEAD" = "$TARGET_HEAD" ] || fail "Unexpected production HEAD"
[ "$TREE" = "$TARGET_TREE" ] || fail "Unexpected production tree"
[ -z "$(git -C "$PORTAL" status --porcelain=v1 --untracked-files=normal)" ] || fail "Production worktree dirty"
echo "PRODUCTION_IDENTITY=PASS"

section "VENV PYTHON"
[ -x "$VENV_PY" ] || fail "Existing device-fingerprint venv Python missing"
"$VENV_PY" - <<'PY'
import sys
print("VENV_PYTHON_EXECUTABLE="+sys.executable)
print("VENV_PYTHON_VERSION="+sys.version.split()[0])
PY

section "DEPENDENCY IMPORTS UNDER EXISTING VENV"
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
    "app.visitor_registry.registry_config",
    "app.visitor_registry.registry_repository",
    "app.visitor_registry.registry_read_service",
    "app.visit_lifecycle.config",
    "app.visit_lifecycle.repository",
    "app.visit_lifecycle.read_service",
]
for name in mods:
    try:
        module = __import__(name)
    except Exception as exc:
        print(f"IMPORT_FAIL={name}|{type(exc).__name__}|{exc}")
        raise
    else:
        path = getattr(module, "__file__", None)
        print(f"IMPORT_PASS={name}|{path}")
print("TASK05_WORKER_IMPORTS_EXISTING_VENV=PASS")
PY

section "SENSOR UNIT CURRENT EXECSTART"
echo "SENSOR_EXECSTART=$(systemctl show fingerprint-sensor.service -p ExecStart --value --no-pager)"
systemctl is-active --quiet fingerprint-sensor.service || fail "fingerprint-sensor.service not active"
echo "SENSOR_ACTIVE=PASS"

section "PROTECTHOME COMPATIBILITY FACT"
echo "TASK05_ACCEPTED_UNIT_PROTECTHOME=$(grep -E '^ProtectHome=' "$PORTAL/deploy/device-fingerprint/fingerprint-classification.service" || true)"
echo "TASK05_ACCEPTED_UNIT_EXECSTART=$(grep -E '^ExecStart=' "$PORTAL/deploy/device-fingerprint/fingerprint-classification.service" || true)"
echo "ADMIN_USER_SITE_FLASK=$(
  sudo -H -u admin /usr/bin/python3 - <<'PY'
import flask
print(flask.__file__)
PY
)"
echo "NOTE=Accepted unit hides /home while /usr/bin/python3 currently depends on admin user-site Flask"

section "FINAL"
echo "TASK05_WORKER_PYTHON_RUNTIME_PROBE=PASS"
echo "CHANGES_MADE=NONE"
