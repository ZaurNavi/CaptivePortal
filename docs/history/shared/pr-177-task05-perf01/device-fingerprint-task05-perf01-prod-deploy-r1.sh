#!/usr/bin/env bash
set -Eeuo pipefail
export SYSTEMD_PAGER=cat
export PAGER=cat

PORTAL="/opt/CaptivePortal"
BUNDLE="/home/admin/TASK-DEVICE-FINGERPRINT-05-PERF-01-main-20ea.bundle"

OLD_HEAD="97bd1cf924024a38cc3229bfd726a25fe6754b07"
OLD_TREE="545a48caf86adc247083db611e87a8d36820f353"

NEW_HEAD="20ea385182972e8fb5b204815161bc6a5c7f13fb"
NEW_TREE="439ab64697f2fcdcd5e822527f287ca5404e45ba"
CANDIDATE_HEAD="0507a1fd66e84d00f105a53e6c36dec74ea14520"

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
[ -f "$BUNDLE" ] || fail "Git bundle missing: $BUNDLE"
[ -x "$VENV_PY" ] || fail "Production venv missing"

section "DECLARATION"
date --iso-8601=seconds
echo "MODE=TASK05_PERF01_EXACT_MERGED_PRODUCTION_DEPLOY"
echo "LOCAL_SOURCE_PATCH=NO"
echo "FULL_PYTEST=NO"
echo "DB_MIGRATION=NO"
echo "CONFIG_CHANGE=NO"
echo "LEASE_CHANGE=NO"
echo "EXPECTED_OLD_HEAD=$OLD_HEAD"
echo "EXPECTED_NEW_HEAD=$NEW_HEAD"
echo "EXPECTED_NEW_TREE=$NEW_TREE"

section "CURRENT PRODUCTION GUARD"
CURRENT_HEAD="$(git -C "$PORTAL" rev-parse HEAD)"
CURRENT_TREE="$(git -C "$PORTAL" rev-parse 'HEAD^{tree}')"
STATUS="$(git -C "$PORTAL" status --porcelain=v1 --untracked-files=normal)"
echo "CURRENT_HEAD=$CURRENT_HEAD"
echo "CURRENT_TREE=$CURRENT_TREE"
[ "$CURRENT_HEAD" = "$OLD_HEAD" ] || fail "Unexpected current production HEAD"
[ "$CURRENT_TREE" = "$OLD_TREE" ] || fail "Unexpected current production tree"
[ -z "$STATUS" ] || { git -C "$PORTAL" status --short; fail "Production worktree dirty"; }
systemctl is-active --quiet captive-portal.service || fail "Portal inactive before deploy"
systemctl is-active --quiet fingerprint-classification.service || fail "Worker inactive before deploy"
echo "PORTAL_NRESTARTS_BEFORE=$(systemctl show captive-portal.service -p NRestarts --value --no-pager)"
echo "WORKER_NRESTARTS_BEFORE=$(systemctl show fingerprint-classification.service -p NRestarts --value --no-pager)"
echo "CURRENT_PRODUCTION_GUARD=PASS"

section "BUNDLE VERIFY AND IMPORT"
git -C "$PORTAL" bundle verify "$BUNDLE"
echo "BUNDLE_HEADS:"
git -C "$PORTAL" bundle list-heads "$BUNDLE"

git -C "$PORTAL" fetch --no-tags "$BUNDLE" refs/remotes/origin/main
FETCHED="$(git -C "$PORTAL" rev-parse FETCH_HEAD)"
FETCHED_TREE="$(git -C "$PORTAL" rev-parse 'FETCH_HEAD^{tree}')"
FETCHED_PARENTS="$(git -C "$PORTAL" show -s --format='%P' FETCH_HEAD)"
echo "FETCHED_HEAD=$FETCHED"
echo "FETCHED_TREE=$FETCHED_TREE"
echo "FETCHED_PARENTS=$FETCHED_PARENTS"
[ "$FETCHED" = "$NEW_HEAD" ] || fail "Bundle did not import expected merged HEAD"
[ "$FETCHED_TREE" = "$NEW_TREE" ] || fail "Fetched tree mismatch"
[ "$FETCHED_PARENTS" = "$OLD_HEAD $CANDIDATE_HEAD" ] || fail "Merged commit parents mismatch"
echo "BUNDLE_IMPORT=PASS"

section "EXACT DIFF SCOPE"
mapfile -t ACTUAL_FILES < <(git -C "$PORTAL" diff --name-only "$OLD_HEAD" "$NEW_HEAD" | sort)
EXPECTED_FILES=(
  "app/device_fingerprint/fusion.py"
  "app/device_fingerprint/k4_ieee_import.py"
  "app/device_fingerprint/knowledge_artifacts.py"
  "app/device_fingerprint/knowledge_bundle.py"
  "app/device_fingerprint/origin_assessment.py"
  "app/device_fingerprint/request_assembly.py"
  "tests/device_fingerprint_fe1/test_knowledge_artifacts.py"
  "tests/device_fingerprint_fe4/test_k4_ieee_import.py"
  "tests/device_fingerprint_fe7/test_knowledge_bundle.py"
  "tests/device_fingerprint_task04_04d_request/test_request_assembly.py"
  "tests/device_fingerprint_task04_t03/test_origin_assessment.py"
  "tests/device_fingerprint_task04_t04/test_fusion.py"
)
mapfile -t EXPECTED_SORTED < <(printf '%s\n' "${EXPECTED_FILES[@]}" | sort)
printf 'CHANGED_FILE=%s\n' "${ACTUAL_FILES[@]}"
[ "${#ACTUAL_FILES[@]}" -eq "${#EXPECTED_SORTED[@]}" ] || fail "Changed file count mismatch"
for i in "${!EXPECTED_SORTED[@]}"; do
  [ "${ACTUAL_FILES[$i]}" = "${EXPECTED_SORTED[$i]}" ] || fail "Changed file mismatch"
done
echo "EXACT_DIFF_SCOPE=PASS"

section "DATABASE HASHES BEFORE CODE SWITCH"
declare -A BEFORE
for db in "${DBS[@]}"; do
  [ -f "$db" ] || fail "Missing DB: $db"
  sha="$(sha256sum "$db" | awk '{print $1}')"
  BEFORE["$db"]="$sha"
  echo "DB_BEFORE $(basename "$db")=$sha"
done

section "STOP SERVICES"
systemctl stop fingerprint-classification.service
systemctl stop captive-portal.service
if systemctl is-active --quiet fingerprint-classification.service; then fail "Worker failed to stop"; fi
if systemctl is-active --quiet captive-portal.service; then fail "Portal failed to stop"; fi
echo "SERVICES_STOPPED=PASS"

section "EXACT CODE SWITCH"
git -C "$PORTAL" checkout --detach "$NEW_HEAD"
NEW_STATUS="$(git -C "$PORTAL" status --porcelain=v1 --untracked-files=normal)"
HEAD_AFTER="$(git -C "$PORTAL" rev-parse HEAD)"
TREE_AFTER="$(git -C "$PORTAL" rev-parse 'HEAD^{tree}')"
echo "HEAD_AFTER_SWITCH=$HEAD_AFTER"
echo "TREE_AFTER_SWITCH=$TREE_AFTER"
[ "$HEAD_AFTER" = "$NEW_HEAD" ] || fail "HEAD switch mismatch"
[ "$TREE_AFTER" = "$NEW_TREE" ] || fail "Tree switch mismatch"
[ -z "$NEW_STATUS" ] || { git -C "$PORTAL" status --short; fail "Worktree dirty after switch"; }
echo "EXACT_CODE_SWITCH=PASS"

section "DATABASE HASHES AFTER CODE SWITCH BEFORE START"
for db in "${DBS[@]}"; do
  sha="$(sha256sum "$db" | awk '{print $1}')"
  echo "DB_AFTER_SWITCH $(basename "$db")=$sha"
  [ "$sha" = "${BEFORE[$db]}" ] || fail "DB changed during code switch: $db"
done
echo "DATABASES_UNCHANGED_DURING_SWITCH=PASS"

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
systemctl is-active --quiet captive-portal.service || fail "Portal failed after deploy"
systemctl is-active --quiet fingerprint-classification.service || fail "Worker failed after deploy"
echo "PORTAL_NRESTARTS_AFTER=$(systemctl show captive-portal.service -p NRestarts --value --no-pager)"
echo "WORKER_NRESTARTS_AFTER=$(systemctl show fingerprint-classification.service -p NRestarts --value --no-pager)"
echo "WORKER_EXECSTART=$(systemctl show fingerprint-classification.service -p ExecStart --value)"
echo "SERVICES_ACTIVE=PASS"

section "POST-DEPLOY RUNTIME IDENTITY"
echo "PRODUCTION_HEAD=$(git -C "$PORTAL" rev-parse HEAD)"
echo "PRODUCTION_TREE=$(git -C "$PORTAL" rev-parse 'HEAD^{tree}')"
git -C "$PORTAL" status --short
echo "PORTAL_STATE=$(systemctl is-active captive-portal.service)"
echo "WORKER_STATE=$(systemctl is-active fingerprint-classification.service)"

section "RECENT JOURNAL"
journalctl -u captive-portal.service -u fingerprint-classification.service \
  --since '-2 minutes' --no-pager -n 80 || true

section "FINAL"
echo "TASK05_PERF01_MERGED_CODE_DEPLOY=PASS"
echo "PRODUCTION_HEAD=$NEW_HEAD"
echo "PRODUCTION_TREE=$NEW_TREE"
echo "NEXT=RUN_READ_ONLY_PRODUCTION_PERFORMANCE_BENCHMARK"
