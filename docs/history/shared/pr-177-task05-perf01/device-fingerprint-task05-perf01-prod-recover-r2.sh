#!/usr/bin/env bash
set -Eeuo pipefail
export SYSTEMD_PAGER=cat
export PAGER=cat

PORTAL="/opt/CaptivePortal"
EXPECTED_HEAD="20ea385182972e8fb5b204815161bc6a5c7f13fb"
EXPECTED_TREE="439ab64697f2fcdcd5e822527f287ca5404e45ba"
VENV_PY="/opt/captiveportal-runtime/device-fingerprint-venv/bin/python"

DBS=(
  "/opt/CaptivePortal/data/visitor_registry.sqlite3"
  "/opt/CaptivePortal/data/visits.sqlite3"
  "/opt/CaptivePortal/data/current_state.sqlite3"
  "/opt/CaptivePortal/data/device_fingerprint_evidence.sqlite3"
  "/opt/CaptivePortal/data/device_fingerprint_classification.sqlite3"
  "/opt/CaptivePortal/data/device_fingerprint_control_plane.sqlite3"
  "/opt/CaptivePortal/data/device_fingerprint_integration.sqlite3"
)

section(){ printf '\n===== %s =====\n' "$1"; }
fail(){ echo "FATAL: $*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || fail "Run with sudo/root"
[ -d "$PORTAL/.git" ] || fail "Portal repo missing"
[ -x "$VENV_PY" ] || fail "Production venv missing"

section "DECLARATION"
date --iso-8601=seconds
echo "MODE=TASK05_PERF01_POST_ABORT_RECOVERY"
echo "LOCAL_SOURCE_PATCH=NO"
echo "DB_WRITE_BY_SCRIPT=NO"
echo "DB_MIGRATION=NO"
echo "CONFIG_CHANGE=NO"
echo "LEASE_CHANGE=NO"
echo "FULL_PYTEST=NO"

section "EXACT CODE GUARD"
HEAD="$(git -C "$PORTAL" rev-parse HEAD)"
TREE="$(git -C "$PORTAL" rev-parse 'HEAD^{tree}')"
STATUS="$(git -C "$PORTAL" status --porcelain=v1 --untracked-files=normal)"
echo "CURRENT_HEAD=$HEAD"
echo "CURRENT_TREE=$TREE"
[ "$HEAD" = "$EXPECTED_HEAD" ] || fail "Unexpected HEAD"
[ "$TREE" = "$EXPECTED_TREE" ] || fail "Unexpected tree"
[ -z "$STATUS" ] || { git -C "$PORTAL" status --short; fail "Production worktree dirty"; }
echo "EXACT_CODE_GUARD=PASS"

section "CURRENT SERVICE STATE"
echo "PORTAL_STATE_BEFORE=$(systemctl is-active captive-portal.service || true)"
echo "WORKER_STATE_BEFORE=$(systemctl is-active fingerprint-classification.service || true)"
echo "PORTAL_NRESTARTS_BEFORE=$(systemctl show captive-portal.service -p NRestarts --value --no-pager)"
echo "WORKER_NRESTARTS_BEFORE=$(systemctl show fingerprint-classification.service -p NRestarts --value --no-pager)"

section "READ-ONLY SQLITE INTEGRITY"
DB_LIST="$(printf '%s\n' "${DBS[@]}")" /usr/bin/python3 - <<'PY'
import os, sqlite3, hashlib
for path in os.environ["DB_LIST"].splitlines():
    if not os.path.isfile(path):
        raise SystemExit(f"FATAL: missing DB {path}")
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        row = con.execute("PRAGMA quick_check").fetchone()
    finally:
        con.close()
    result = row[0] if row else None
    print(f"DB_SHA256 {os.path.basename(path)}={h.hexdigest()}")
    print(f"DB_QUICK_CHECK {os.path.basename(path)}={result}")
    if result != "ok":
        raise SystemExit(f"FATAL: quick_check failed for {path}: {result}")
print("ALL_DB_QUICK_CHECK=PASS")
PY

section "IMPORT SMOKE"
sudo -u admin env \
  HOME=/nonexistent \
  PYTHONPATH="$PORTAL" \
  PYTHONDONTWRITEBYTECODE=1 \
  "$VENV_PY" -B - <<'PY'
from app.device_fingerprint.request_assembly import DeviceFingerprintRequestAssembly
from app.device_fingerprint.origin_assessment import DeviceFingerprintOriginAssessmentBuilder
from app.device_fingerprint.fusion import fuse_classification
from app.device_fingerprint.knowledge_bundle import _ValidatedKnowledgeBundle
print("IMPORT_SMOKE=PASS")
PY

section "START SERVICES"
systemctl start captive-portal.service
systemctl start fingerprint-classification.service
sleep 3
systemctl is-active --quiet captive-portal.service || fail "Portal failed to start"
systemctl is-active --quiet fingerprint-classification.service || fail "Worker failed to start"

echo "PORTAL_STATE_AFTER=$(systemctl is-active captive-portal.service)"
echo "WORKER_STATE_AFTER=$(systemctl is-active fingerprint-classification.service)"
echo "PORTAL_NRESTARTS_AFTER=$(systemctl show captive-portal.service -p NRestarts --value --no-pager)"
echo "WORKER_NRESTARTS_AFTER=$(systemctl show fingerprint-classification.service -p NRestarts --value --no-pager)"
echo "WORKER_EXECSTART=$(systemctl show fingerprint-classification.service -p ExecStart --value)"

section "POST-START RUNTIME IDENTITY"
echo "PRODUCTION_HEAD=$(git -C "$PORTAL" rev-parse HEAD)"
echo "PRODUCTION_TREE=$(git -C "$PORTAL" rev-parse 'HEAD^{tree}')"
git -C "$PORTAL" status --short

section "RECENT JOURNAL"
journalctl -u captive-portal.service -u fingerprint-classification.service \
  --since '-3 minutes' --no-pager -n 120 || true

section "FINAL"
echo "TASK05_PERF01_POST_ABORT_RECOVERY=PASS"
echo "PRODUCTION_HEAD=$EXPECTED_HEAD"
echo "PRODUCTION_TREE=$EXPECTED_TREE"
echo "SERVICES_ACTIVE=PASS"
echo "NEXT=RUN_READ_ONLY_PRODUCTION_PERFORMANCE_BENCHMARK"
