#!/usr/bin/env bash
set -Eeuo pipefail
export SYSTEMD_PAGER=cat
export PAGER=cat

PORTAL="/opt/CaptivePortal"
BAD_HEAD="20ea385182972e8fb5b204815161bc6a5c7f13fb"
BAD_TREE="439ab64697f2fcdcd5e822527f287ca5404e45ba"
GOOD_HEAD="97bd1cf924024a38cc3229bfd726a25fe6754b07"
GOOD_TREE="545a48caf86adc247083db611e87a8d36820f353"
VENV_PY="/opt/captiveportal-runtime/device-fingerprint-venv/bin/python"

section(){ printf '\n===== %s =====\n' "$1"; }
fail(){ echo "FATAL: $*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || fail "Run with sudo/root"
[ -d "$PORTAL/.git" ] || fail "Portal repo missing"
[ -x "$VENV_PY" ] || fail "Production venv missing"

section "DECLARATION"
date --iso-8601=seconds
echo "MODE=ROLLBACK_RUNTIME_TO_LAST_ADMITTED_TASK05_CODE"
echo "LOCAL_SOURCE_PATCH=NO"
echo "DB_MIGRATION=NO"
echo "DB_REWRITE=NO"
echo "CONFIG_CHANGE=NO"
echo "LEASE_CHANGE=NO"
echo "FULL_PYTEST=NO"
echo "HISTORICAL_FAILED_ROWS_PRESERVED=YES"

section "CURRENT GUARD"
HEAD="$(git -C "$PORTAL" rev-parse HEAD)"
TREE="$(git -C "$PORTAL" rev-parse 'HEAD^{tree}')"
STATUS="$(git -C "$PORTAL" status --porcelain=v1 --untracked-files=normal)"
echo "CURRENT_HEAD=$HEAD"
echo "CURRENT_TREE=$TREE"
[ "$HEAD" = "$BAD_HEAD" ] || fail "Unexpected current HEAD; no rollback performed"
[ "$TREE" = "$BAD_TREE" ] || fail "Unexpected current tree; no rollback performed"
[ -z "$STATUS" ] || { git -C "$PORTAL" status --short; fail "Dirty worktree"; }
git -C "$PORTAL" cat-file -e "$GOOD_HEAD^{commit}"
[ "$(git -C "$PORTAL" rev-parse "$GOOD_HEAD^{tree}")" = "$GOOD_TREE" ] || fail "Admitted rollback tree mismatch"
echo "CURRENT_GUARD=PASS"

section "CONTAIN WORKER"
systemctl stop fingerprint-classification.service || true
echo "WORKER_STATE_AFTER_STOP=$(systemctl is-active fingerprint-classification.service || true)"
if systemctl is-active --quiet fingerprint-classification.service; then
  fail "Worker still active"
fi
echo "WORKER_CONTAINMENT=PASS"

section "STOP PORTAL FOR ATOMIC CODE SWITCH"
systemctl stop captive-portal.service
if systemctl is-active --quiet captive-portal.service; then
  fail "Portal still active"
fi
echo "PORTAL_STOPPED=PASS"

section "ROLLBACK EXACT GIT COMMIT"
git -C "$PORTAL" checkout --detach "$GOOD_HEAD"
HEAD2="$(git -C "$PORTAL" rev-parse HEAD)"
TREE2="$(git -C "$PORTAL" rev-parse 'HEAD^{tree}')"
STATUS2="$(git -C "$PORTAL" status --porcelain=v1 --untracked-files=normal)"
echo "ROLLBACK_HEAD=$HEAD2"
echo "ROLLBACK_TREE=$TREE2"
[ "$HEAD2" = "$GOOD_HEAD" ] || fail "Rollback HEAD mismatch"
[ "$TREE2" = "$GOOD_TREE" ] || fail "Rollback tree mismatch"
[ -z "$STATUS2" ] || { git -C "$PORTAL" status --short; fail "Dirty worktree after rollback"; }
echo "EXACT_RUNTIME_ROLLBACK=PASS"

section "IMPORT SMOKE"
sudo -u admin env \
  HOME=/nonexistent \
  PYTHONPATH="$PORTAL" \
  PYTHONDONTWRITEBYTECODE=1 \
  "$VENV_PY" -B - <<'PY'
from app.device_fingerprint.request_assembly import DeviceFingerprintRequestAssembly
from app.device_fingerprint_integration.compatibility import preflight
print("IMPORT_SMOKE=PASS")
PY

section "START PORTAL"
systemctl start captive-portal.service
sleep 2
systemctl is-active --quiet captive-portal.service || fail "Portal failed to start"
echo "PORTAL_STATE=$(systemctl is-active captive-portal.service)"
echo "PORTAL_NRESTARTS=$(systemctl show captive-portal.service -p NRestarts --value --no-pager)"

section "READ-ONLY ACTIVE PROFILE PREFLIGHT"
sudo -u admin env \
  HOME=/nonexistent \
  PYTHONPATH="$PORTAL" \
  PYTHONDONTWRITEBYTECODE=1 \
  "$VENV_PY" -B - <<'PY'
from app.device_fingerprint.control_plane_store import DeviceFingerprintControlPlaneStore
from app.device_fingerprint_integration.compatibility import ReadOnlyControlPlaneStoreMixin, preflight

class RO(ReadOnlyControlPlaneStoreMixin, DeviceFingerprintControlPlaneStore):
    pass

store = RO("/opt/CaptivePortal/data/device_fingerprint_control_plane.sqlite3")
pf = preflight(store)
print("ACTIVE_PROFILE_PREFLIGHT=PASS")
print("ACTIVE_PROFILE_ID="+pf.pin.runtime_profile.artifact_id)
print("ACTIVE_PROFILE_DIGEST="+pf.pin.runtime_profile.content_sha256)
PY

section "START WORKER ONLY AFTER PREFLIGHT PASS"
systemctl start fingerprint-classification.service
sleep 2
systemctl is-active --quiet fingerprint-classification.service || fail "Worker failed to start"
echo "WORKER_STATE=$(systemctl is-active fingerprint-classification.service)"
echo "WORKER_NRESTARTS=$(systemctl show fingerprint-classification.service -p NRestarts --value --no-pager)"
echo "WORKER_EXECSTART=$(systemctl show fingerprint-classification.service -p ExecStart --value)"

section "FINAL IDENTITY"
echo "PRODUCTION_HEAD=$(git -C "$PORTAL" rev-parse HEAD)"
echo "PRODUCTION_TREE=$(git -C "$PORTAL" rev-parse 'HEAD^{tree}')"
git -C "$PORTAL" status --short

section "RECENT JOURNAL"
journalctl -u captive-portal.service -u fingerprint-classification.service \
  --since '-3 minutes' --no-pager -n 100 || true

section "FINAL"
echo "TASK05_PERF01_RUNTIME_ROLLBACK=PASS"
echo "PRODUCTION_RUNTIME_ADMITTED=PASS"
echo "PERF_PATCH_MERGED_IN_GITHUB=YES"
echo "PERF_PATCH_ACTIVE_IN_PRODUCTION=NO"
echo "NEXT=REACCEPT_CLASSIFIER_CODE_AND_BUILD_NEW_ADMISSION_LINEAGE"
