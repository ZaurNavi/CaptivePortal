#!/usr/bin/env bash
set -Eeuo pipefail
export SYSTEMD_PAGER=cat
export PAGER=cat

PORTAL="/opt/CaptivePortal"
DEPLOY_ROOT="/home/admin/CaptivePortal-Deploy"
BASE="1d88f4ae947fa95454dbb54c70f9d6bdd13b1d22"
BASE_TREE="8183bf48abfc71c1b488c0667efc0f1ae717003e"
CANDIDATE_TREE="545a48caf86adc247083db611e87a8d36820f353"
PATCH_SHA256="a0e6921809ed8fbea3ca8ce605541180d7a1578ac9d2560d2a993b7cd3e34d37"

CONTROL_DB="/opt/CaptivePortal/data/device_fingerprint_control_plane.sqlite3"
INTEGRATION_DB="/opt/CaptivePortal/data/device_fingerprint_integration.sqlite3"
CFG="/etc/default/captive-portal"
VENV_PY="/opt/captiveportal-runtime/device-fingerprint-venv/bin/python"
CONTROLLED_IID="77dcd849-8855-4dd4-b3ed-9d2c62d86935"

STAMP="$(date '+%Y%m%dT%H%M%S%z')"
WT="$DEPLOY_ROOT/task05-r1-linux-gate-$STAMP"
TMPROOT="/tmp/task05-r1-linux-gate-$STAMP"
PATCH_FILE="$TMPROOT/TASK-DEVICE-FINGERPRINT-05-R1_BASE-to-R1.patch"

section(){ printf '\n===== %s =====\n' "$1"; }
fail(){ echo "FATAL: $*" >&2; exit 1; }

cleanup_patch() {
  rm -rf "$TMPROOT" >/dev/null 2>&1 || true
}
trap cleanup_patch EXIT

[ "$(id -u)" -eq 0 ] || fail "Run with sudo/root"

section "DECLARATION"
date --iso-8601=seconds
echo "MODE=READ_ONLY_PRODUCTION_PLUS_ISOLATED_WORKTREE_TASK05_R1_LINUX_FULL_GATE"
echo "PRODUCTION_CODE_WRITE=NO"
echo "PRODUCTION_DATABASE_WRITE=NO"
echo "PRODUCTION_CONFIG_WRITE=NO"
echo "PRODUCTION_SERVICE_RESTART=NO"
echo "ISOLATED_CLONE_CREATE=YES"
echo "PATCH_APPLY_SCOPE=ISOLATED_CLONE_ONLY"
echo "BROADER_TESTS=YES"
echo "FULL_REPO_TESTS=YES"
echo "PRODUCTION_PREFLIGHT=READ_ONLY"
echo "BASE=$BASE"
echo "EXPECTED_CANDIDATE_TREE=$CANDIDATE_TREE"

section "PRODUCTION HOLD PRECONDITIONS"
HEAD="$(git -C "$PORTAL" rev-parse HEAD)"
TREE="$(git -C "$PORTAL" rev-parse 'HEAD^{tree}')"
echo "CURRENT_PRODUCTION_HEAD=$HEAD"
echo "CURRENT_PRODUCTION_TREE=$TREE"
[ "$HEAD" = "$BASE" ] || fail "Production HEAD is not Task-05 merged baseline"
[ "$TREE" = "$BASE_TREE" ] || fail "Production tree mismatch"
[ -z "$(git -C "$PORTAL" status --porcelain=v1 --untracked-files=normal)" ]   || fail "Production worktree dirty"

grep -qxF 'DEVICE_FINGERPRINT_INTEGRATION_ENABLED=false' "$CFG"   || fail "Task-05 integration is not contained/disabled"
systemctl is-active --quiet captive-portal.service || fail "Portal inactive"
if systemctl is-active --quiet fingerprint-classification.service; then
  fail "Task-05 worker unexpectedly active"
fi
if systemctl is-enabled --quiet fingerprint-classification.service; then
  fail "Task-05 worker unexpectedly enabled"
fi

[ -f "$CONTROL_DB" ] || fail "Control-plane DB missing"
[ -f "$INTEGRATION_DB" ] || fail "Integration DB evidence missing"

CONTROL_SHA_BEFORE="$(sha256sum "$CONTROL_DB" | awk '{print $1}')"
INTEGRATION_SHA_BEFORE="$(sha256sum "$INTEGRATION_DB" | awk '{print $1}')"
PORTAL_RESTARTS_BEFORE="$(systemctl show captive-portal.service -p NRestarts --value --no-pager)"
echo "CONTROL_DB_SHA256_BEFORE=$CONTROL_SHA_BEFORE"
echo "INTEGRATION_DB_SHA256_BEFORE=$INTEGRATION_SHA_BEFORE"
echo "PORTAL_NRESTARTS_BEFORE=$PORTAL_RESTARTS_BEFORE"

INTEGRATION_DB="$INTEGRATION_DB" IID="$CONTROLLED_IID" /usr/bin/python3 - <<'PY'
import os, sqlite3
con=sqlite3.connect(f"file:{os.environ['INTEGRATION_DB']}?mode=ro", uri=True)
con.row_factory=sqlite3.Row
try:
    r=con.execute(
        "SELECT classification_state,last_reason_code,identity_state "
        "FROM integration_jobs WHERE integration_id=?",
        (os.environ["IID"],)
    ).fetchone()
finally:
    con.close()
if r is None:
    raise SystemExit("FATAL: controlled production evidence missing")
print("CONTROLLED_CLASSIFICATION_STATE="+str(r["classification_state"]))
print("CONTROLLED_LAST_REASON_CODE="+str(r["last_reason_code"]))
print("CONTROLLED_IDENTITY_STATE="+str(r["identity_state"]))
if (r["classification_state"], r["last_reason_code"], r["identity_state"]) != (
    "NO_RESULT_FINAL", "runtime_profile_incompatible", "DEVICE_AND_VISIT_RESOLVED"
):
    raise SystemExit("FATAL: controlled production evidence changed")
PY
echo "PRODUCTION_HOLD_PRECONDITIONS=PASS"

section "MATERIALIZE AND VERIFY EXACT PATCH"
install -d -m 0700 -o root -g root "$TMPROOT"
base64 -d > "$PATCH_FILE" <<'PATCH_B64'
ZGlmZiAtLWdpdCBhL2FwcC9kZXZpY2VfZmluZ2VycHJpbnRfaW50ZWdyYXRpb24vY29tcGF0aWJpbGl0eS5weSBiL2FwcC9kZXZpY2VfZmluZ2VycHJpbnRfaW50ZWdyYXRpb24vY29tcGF0aWJpbGl0eS5weQppbmRleCBiMDc2YTQ0YTg0OGQ3ODMwN2Q1OGFmMmIwOTI0NjY4NWMzNDQ0MTJhLi5iNjE1NDg1MWJlNTYyYjU3YTAxNzRlZTJkMTA2YjM0NGU1MGUxNmUyIDEwMDY0NAotLS0gYS9hcHAvZGV2aWNlX2ZpbmdlcnByaW50X2ludGVncmF0aW9uL2NvbXBhdGliaWxpdHkucHkKKysrIGIvYXBwL2RldmljZV9maW5nZXJwcmludF9pbnRlZ3JhdGlvbi9jb21wYXRpYmlsaXR5LnB5CkBAIC00OSw3ICs0OSwxMCBAQCBkZWYgdmVyaWZ5X2V4ZWN1dGFibGVfaWRlbnRpdGllcyhtYW5pZmVzdCwgKiwgcm9vdD1SRVBPU0lUT1JZX1JPT1QpOgogICAgICAgICBpZGVudGl0eSwgZGlnZXN0ID0gZXZpZGVuY2VbbGVuKHByZWZpeCk6XS5yc3BsaXQoIjpzaGEyNTY6IiwgMSkKICAgICAgICAgZW50cmllcyA9IGVudHJpZXMgKyBbeyJpbXBsZW1lbnRhdGlvbl9pZCI6IGlkZW50aXR5LCAiaW1wbGVtZW50YXRpb25fZGlnZXN0IjogZGlnZXN0fV0KICAgICAgICAgZm9yIGVudHJ5IGluIGVudHJpZXM6Ci0gICAgICAgICAgICBwcmVmaXgsIHJlbGF0aXZlLCBxdWFsaWZpZWQgPSBlbnRyeVsiaW1wbGVtZW50YXRpb25faWQiXS5zcGxpdCgiOiIsIDIpCisgICAgICAgICAgICBwcmVmaXgsIHJlbGF0aXZlLCBpZGVudGl0eV90YWlsID0gZW50cnlbImltcGxlbWVudGF0aW9uX2lkIl0uc3BsaXQoIjoiLCAyKQorICAgICAgICAgICAgcXVhbGlmaWVkID0gaWRlbnRpdHlfdGFpbC5wYXJ0aXRpb24oIi8iKVswXQorICAgICAgICAgICAgaWYgbm90IGFsbChjb21wb25lbnQuaXNpZGVudGlmaWVyKCkgZm9yIGNvbXBvbmVudCBpbiBxdWFsaWZpZWQuc3BsaXQoIi4iKSk6CisgICAgICAgICAgICAgICAgcmFpc2UgVmFsdWVFcnJvcigiSW52YWxpZCBQeXRob24gcXVhbGlmaWVkIHN5bWJvbCIpCiAgICAgICAgICAgICBkaWdlc3QgPSBlbnRyeVsiaW1wbGVtZW50YXRpb25fZGlnZXN0Il0KICAgICAgICAgICAgIHBhdGggPSBQdXJlUG9zaXhQYXRoKHJlbGF0aXZlKQogICAgICAgICAgICAgaWYgKHByZWZpeCAhPSAicHl0aG9uIiBvciBwYXRoLmlzX2Fic29sdXRlKCkgb3IgIi4uIiBpbiBwYXRoLnBhcnRzCmRpZmYgLS1naXQgYS90ZXN0cy9kZXZpY2VfZmluZ2VycHJpbnRfaW50ZWdyYXRpb24vdGVzdF9leGVjdXRvcl9wZXJzaXN0ZW5jZS5weSBiL3Rlc3RzL2RldmljZV9maW5nZXJwcmludF9pbnRlZ3JhdGlvbi90ZXN0X2V4ZWN1dG9yX3BlcnNpc3RlbmNlLnB5CmluZGV4IDdhNDdmOGM3ZDQ3NzI4ZTNkYWY2ZGZlNzEyMjQ3MzliZWEzZjI2OTEuLjU4ZTE5ZjMwZjgyMDU4ZjBjNmQ3N2ZlOGNkOTU1MWZlZjc1ZTUyODggMTAwNjQ0Ci0tLSBhL3Rlc3RzL2RldmljZV9maW5nZXJwcmludF9pbnRlZ3JhdGlvbi90ZXN0X2V4ZWN1dG9yX3BlcnNpc3RlbmNlLnB5CisrKyBiL3Rlc3RzL2RldmljZV9maW5nZXJwcmludF9pbnRlZ3JhdGlvbi90ZXN0X2V4ZWN1dG9yX3BlcnNpc3RlbmNlLnB5CkBAIC0zNSw3ICszNSw4IEBAIGRlZiBzb3VyY2VfaWRlbnRpdHkocmVsYXRpdmUsIHF1YWxpZmllZCk6CiBkZWYgcHJlcGFyZWRfcHJvZHVjdGlvbih0bXBfcGF0aCk6CiAgICAgIiIiRnVsbHkgdHlwZWQgbG9jYWwgcHJlZmxpZ2h0IGZpeHR1cmU7IG5ldmVyIHRvZGF5J3MgcHJvZHVjdGlvbiBJRHMuIiIiCiAgICAgc3RvcmUsIGNvbnRyb2wsIGFzc2VtYmx5LCByZXRlbnRpb24gPSBwcm9kdWN0aW9uX3NldHVwKHRtcF9wYXRoKQotICAgIGlkZW50aXR5ID0gc291cmNlX2lkZW50aXR5KCJhcHAvZGV2aWNlX2ZpbmdlcnByaW50L29yaWdpbl9hc3Nlc3NtZW50LnB5IiwgIkRldmljZUZpbmdlcnByaW50T3JpZ2luQXNzZXNzbWVudEJ1aWxkZXIuYnVpbGQiKQorICAgIGlkZW50aXR5ID0gc291cmNlX2lkZW50aXR5KCJhcHAvZGV2aWNlX2ZpbmdlcnByaW50L29yaWdpbl9hc3Nlc3NtZW50LnB5IiwKKyAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAiRGV2aWNlRmluZ2VycHJpbnRPcmlnaW5Bc3Nlc3NtZW50QnVpbGRlci5idWlsZC9kaGNwLzEvRlVTSU9OIikKICAgICBldmlkZW5jZSA9IHNvdXJjZV9pZGVudGl0eSgiYXBwL2RldmljZV9maW5nZXJwcmludC92YWxpZGF0aW9uLnB5IiwgImNhbm9uaWNhbF9qc29uIikKICAgICBtYW5pZmVzdCA9IG1ha2VfYXJ0aWZhY3RfY29udGVudCgiQ2xhc3NpZmllckFydGlmYWN0TWFuaWZlc3QiLCB7CiAgICAgICAgICJhZGFwdGVyX2ltcGxlbWVudGF0aW9uX2lkZW50aXRpZXMiOiBbeyJhZGFwdGVyX2tpbmQiOiAiVEFTSzAxX0VWSURFTkNFIiwgInNvdXJjZV9raW5kIjogImRoY3AiLApAQCAtMTkxLDYgKzE5Miw3MCBAQCBkZWYgdGVzdF9nZXRfYnlfaWRfcmV0YWluZWRfaGFzaF9pbnRlZ3JpdHlfYW5kX21pc3NpbmcodG1wX3BhdGgpOgogICAgICAgICByZWFkZXIuZ2V0X2J5X2lkKGNvcmUuY2xhc3NpZmljYXRpb25faWQpCiAKIAorQHB5dGVzdC5tYXJrLnBhcmFtZXRyaXplKCJxdWFsaWZpZWQiLCBbCisgICAgIkRldmljZUZpbmdlcnByaW50T3JpZ2luQXNzZXNzbWVudEJ1aWxkZXIuYnVpbGQvbWFjX3JlZ2lzdHJ5L0ZVU0lPTiIsCisgICAgIkRldmljZUZpbmdlcnByaW50T3JpZ2luQXNzZXNzbWVudEJ1aWxkZXIuYnVpbGQvZGhjcC8xL0ZVU0lPTiIsCisgICAgIkRldmljZUZpbmdlcnByaW50T3JpZ2luQXNzZXNzbWVudEJ1aWxkZXIuYnVpbGQvcG9ydGFsX2hlYWRlcnMvMi9PUFRJT05BTF9JRl9BRE1JVFRFRCIsCisgICAgIkRldmljZUZpbmdlcnByaW50T3JpZ2luQXNzZXNzbWVudEJ1aWxkZXIuYnVpbGQvdGNwX3N5bi8xL05PTl9GVVNJT05fSEFORExFUiIsCisgICAgIkRldmljZUZpbmdlcnByaW50T3JpZ2luQXNzZXNzbWVudEJ1aWxkZXIuYnVpbGQiLAorXSkKK2RlZiB0ZXN0X3NvdXJjZV9pZGVudGl0eV9yZXNvbHZlc19zeW1ib2xfd2l0aG91dF9jaGFuZ2luZ19hZG1pdHRlZF9pZGVudGl0eSh0bXBfcGF0aCwgcXVhbGlmaWVkKToKKyAgICBfc3RvcmUsIGNvbnRyb2wsIF9hc3NlbWJseSwgX3JldGVudGlvbiA9IHByZXBhcmVkX3Byb2R1Y3Rpb24odG1wX3BhdGgpCisgICAgbWFuaWZlc3QgPSBjb250cm9sLmNvbnRlbnRzW2NvbnRyb2wucGlubmVkLnJ1bnRpbWVfcHJvZmlsZS5zZW1hbnRpY19wYXlsb2FkWyJjbGFzc2lmaWVyX2FydGlmYWN0X21hbmlmZXN0Il1bImFydGlmYWN0X2lkIl1dCisgICAgcGF5bG9hZCA9IG1hbmlmZXN0LnNlbWFudGljX3BheWxvYWQKKyAgICBwYXlsb2FkWyJhZGFwdGVyX2ltcGxlbWVudGF0aW9uX2lkZW50aXRpZXMiXVswXS51cGRhdGUoCisgICAgICAgIHNvdXJjZV9pZGVudGl0eSgiYXBwL2RldmljZV9maW5nZXJwcmludC9vcmlnaW5fYXNzZXNzbWVudC5weSIsIHF1YWxpZmllZCkpCisgICAgY2FuZGlkYXRlID0gbWFrZV9hcnRpZmFjdF9jb250ZW50KCJDbGFzc2lmaWVyQXJ0aWZhY3RNYW5pZmVzdCIsIHBheWxvYWQpCisgICAgYmVmb3JlID0gY2FuZGlkYXRlLnNlbWFudGljX3BheWxvYWQKKyAgICBpZGVudGl0eSA9IGNhbmRpZGF0ZS5hcnRpZmFjdF9pZAorICAgIGFzc2VydCB2ZXJpZnlfZXhlY3V0YWJsZV9pZGVudGl0aWVzKGNhbmRpZGF0ZSkgaXMgTm9uZQorICAgIGFzc2VydCBjYW5kaWRhdGUuc2VtYW50aWNfcGF5bG9hZCA9PSBiZWZvcmUKKyAgICBhc3NlcnQgY2FuZGlkYXRlLmFydGlmYWN0X2lkID09IGlkZW50aXR5CisgICAgYXNzZXJ0IGNhbmRpZGF0ZS5zZW1hbnRpY19wYXlsb2FkWyJhZGFwdGVyX2ltcGxlbWVudGF0aW9uX2lkZW50aXRpZXMiXVswXVsiaW1wbGVtZW50YXRpb25faWQiXSA9PSAoCisgICAgICAgIGYicHl0aG9uOmFwcC9kZXZpY2VfZmluZ2VycHJpbnQvb3JpZ2luX2Fzc2Vzc21lbnQucHk6e3F1YWxpZmllZH0iKQorCisKK0BweXRlc3QubWFyay5wYXJhbWV0cml6ZSgicXVhbGlmaWVkIiwgWworICAgICJEZXZpY2VGaW5nZXJwcmludE9yaWdpbkFzc2Vzc21lbnRCdWlsZGVyLm5vX3N1Y2hfc3ltYm9sL2RoY3AvMS9GVVNJT04iLAorICAgICIvZGhjcC8xL0ZVU0lPTiIsCisgICAgIkRldmljZUZpbmdlcnByaW50T3JpZ2luQXNzZXNzbWVudEJ1aWxkZXIuLmJ1aWxkL2RoY3AvMS9GVVNJT04iLAorXSkKK2RlZiB0ZXN0X2ludmFsaWRfcHl0aG9uX3N5bWJvbF9mYWlsc19jbG9zZWQodG1wX3BhdGgsIHF1YWxpZmllZCk6CisgICAgX3N0b3JlLCBjb250cm9sLCBfYXNzZW1ibHksIF9yZXRlbnRpb24gPSBwcmVwYXJlZF9wcm9kdWN0aW9uKHRtcF9wYXRoKQorICAgIG1hbmlmZXN0ID0gY29udHJvbC5jb250ZW50c1tjb250cm9sLnBpbm5lZC5ydW50aW1lX3Byb2ZpbGUuc2VtYW50aWNfcGF5bG9hZFsiY2xhc3NpZmllcl9hcnRpZmFjdF9tYW5pZmVzdCJdWyJhcnRpZmFjdF9pZCJdXQorICAgIHBheWxvYWQgPSBtYW5pZmVzdC5zZW1hbnRpY19wYXlsb2FkCisgICAgcGF5bG9hZFsiYWRhcHRlcl9pbXBsZW1lbnRhdGlvbl9pZGVudGl0aWVzIl1bMF0udXBkYXRlKAorICAgICAgICBzb3VyY2VfaWRlbnRpdHkoImFwcC9kZXZpY2VfZmluZ2VycHJpbnQvb3JpZ2luX2Fzc2Vzc21lbnQucHkiLCBxdWFsaWZpZWQpKQorICAgIHdpdGggcHl0ZXN0LnJhaXNlcyhJbnRlZ3JhdGlvbkVycm9yLCBtYXRjaD0icnVudGltZV9wcm9maWxlX2luY29tcGF0aWJsZSIpOgorICAgICAgICB2ZXJpZnlfZXhlY3V0YWJsZV9pZGVudGl0aWVzKG1ha2VfYXJ0aWZhY3RfY29udGVudCgiQ2xhc3NpZmllckFydGlmYWN0TWFuaWZlc3QiLCBwYXlsb2FkKSkKKworCitAcHl0ZXN0Lm1hcmsucGFyYW1ldHJpemUoImNvcnJ1cHRlZCIsIFtGYWxzZSwgVHJ1ZV0pCitkZWYgdGVzdF9ldmlkZW5jZV9jYW5vbmljYWxfanNvbl9zb3VyY2VfaWRlbnRpdHlfYW5kX2RpZ2VzdCh0bXBfcGF0aCwgY29ycnVwdGVkKToKKyAgICBfc3RvcmUsIGNvbnRyb2wsIF9hc3NlbWJseSwgX3JldGVudGlvbiA9IHByZXBhcmVkX3Byb2R1Y3Rpb24odG1wX3BhdGgpCisgICAgbWFuaWZlc3QgPSBjb250cm9sLmNvbnRlbnRzW2NvbnRyb2wucGlubmVkLnJ1bnRpbWVfcHJvZmlsZS5zZW1hbnRpY19wYXlsb2FkWyJjbGFzc2lmaWVyX2FydGlmYWN0X21hbmlmZXN0Il1bImFydGlmYWN0X2lkIl1dCisgICAgcGF5bG9hZCA9IG1hbmlmZXN0LnNlbWFudGljX3BheWxvYWQKKyAgICBldmlkZW5jZSA9IHNvdXJjZV9pZGVudGl0eSgiYXBwL2RldmljZV9maW5nZXJwcmludC92YWxpZGF0aW9uLnB5IiwgImNhbm9uaWNhbF9qc29uIikKKyAgICBwYXlsb2FkWyJldmlkZW5jZV9jYW5vbmljYWxfanNvbl9jb21wYXRpYmlsaXR5X2lkZW50aXR5Il0gPSAoCisgICAgICAgIGYiRXZpZGVuY2VDYW5vbmljYWxKc29uVjE6e2V2aWRlbmNlWydpbXBsZW1lbnRhdGlvbl9pZCddfTpzaGEyNTY6IgorICAgICAgICBmInsnMCcgKiA2NCBpZiBjb3JydXB0ZWQgZWxzZSBldmlkZW5jZVsnaW1wbGVtZW50YXRpb25fZGlnZXN0J119IikKKyAgICBjYW5kaWRhdGUgPSBtYWtlX2FydGlmYWN0X2NvbnRlbnQoIkNsYXNzaWZpZXJBcnRpZmFjdE1hbmlmZXN0IiwgcGF5bG9hZCkKKyAgICBpZiBjb3JydXB0ZWQ6CisgICAgICAgIHdpdGggcHl0ZXN0LnJhaXNlcyhJbnRlZ3JhdGlvbkVycm9yLCBtYXRjaD0icnVudGltZV9wcm9maWxlX2luY29tcGF0aWJsZSIpOgorICAgICAgICAgICAgdmVyaWZ5X2V4ZWN1dGFibGVfaWRlbnRpdGllcyhjYW5kaWRhdGUpCisgICAgZWxzZToKKyAgICAgICAgYXNzZXJ0IHZlcmlmeV9leGVjdXRhYmxlX2lkZW50aXRpZXMoY2FuZGlkYXRlKSBpcyBOb25lCisKKworZGVmIHRlc3Rfc291cmNlX29yaWdpbl9taXNtYXRjaF9mYWlsc19jbG9zZWQodG1wX3BhdGgsIG1vbmtleXBhdGNoKToKKyAgICBfc3RvcmUsIGNvbnRyb2wsIF9hc3NlbWJseSwgX3JldGVudGlvbiA9IHByZXBhcmVkX3Byb2R1Y3Rpb24odG1wX3BhdGgpCisgICAgbWFuaWZlc3QgPSBjb250cm9sLmNvbnRlbnRzW2NvbnRyb2wucGlubmVkLnJ1bnRpbWVfcHJvZmlsZS5zZW1hbnRpY19wYXlsb2FkWyJjbGFzc2lmaWVyX2FydGlmYWN0X21hbmlmZXN0Il1bImFydGlmYWN0X2lkIl1dCisgICAgbW9ua2V5cGF0Y2guc2V0YXR0cigiYXBwLmRldmljZV9maW5nZXJwcmludF9pbnRlZ3JhdGlvbi5jb21wYXRpYmlsaXR5Lmluc3BlY3QuZ2V0c291cmNlZmlsZSIsCisgICAgICAgICAgICAgICAgICAgICAgICBsYW1iZGEgX3N5bWJvbDogc3RyKFJFUE9TSVRPUllfUk9PVCAvICJhcHAvZGV2aWNlX2ZpbmdlcnByaW50L3ZhbGlkYXRpb24ucHkiKSkKKyAgICB3aXRoIHB5dGVzdC5yYWlzZXMoSW50ZWdyYXRpb25FcnJvciwgbWF0Y2g9InJ1bnRpbWVfcHJvZmlsZV9pbmNvbXBhdGlibGUiKToKKyAgICAgICAgdmVyaWZ5X2V4ZWN1dGFibGVfaWRlbnRpdGllcyhtYW5pZmVzdCkKKworCiBAcHl0ZXN0Lm1hcmsucGFyYW1ldHJpemUoImJhZCIsIFsiZGlnZXN0IiwgImVzY2FwZSIsICJtaXNzaW5nIl0pCiBkZWYgdGVzdF9tYW5pZmVzdF9zb3VyY2VfbWlzbWF0Y2hfYmxvY2tzX2V4ZWN1dGlvbih0bXBfcGF0aCwgYmFkKToKICAgICBzdG9yZSwgY29udHJvbCwgX2Fzc2VtYmx5LCBfID0gcHJlcGFyZWRfcHJvZHVjdGlvbih0bXBfcGF0aCkK
PATCH_B64
ACTUAL_PATCH_SHA="$(sha256sum "$PATCH_FILE" | awk '{print $1}')"
ACTUAL_PATCH_BYTES="$(stat -c '%s' "$PATCH_FILE")"
echo "PATCH_BYTES=$ACTUAL_PATCH_BYTES"
echo "PATCH_SHA256=$ACTUAL_PATCH_SHA"
[ "$ACTUAL_PATCH_SHA" = "$PATCH_SHA256" ] || fail "Patch SHA256 mismatch"
[ "$ACTUAL_PATCH_BYTES" = "6609" ] || fail "Patch byte-size mismatch"
echo "PATCH_IDENTITY=PASS"

section "CREATE ISOLATED CANDIDATE CLONE"
[ ! -e "$WT" ] || fail "Isolated clone path already exists"
git clone --shared --no-checkout "$PORTAL" "$WT" >/dev/null
git -C "$WT" checkout --detach "$BASE" >/dev/null
echo "ISOLATED_CLONE=$WT"
[ "$(git -C "$WT" rev-parse HEAD)" = "$BASE" ] || fail "Isolated clone base mismatch"
[ -z "$(git -C "$WT" status --porcelain=v1 --untracked-files=normal)" ] || fail "Fresh clone dirty"
echo "ISOLATED_BASE=PASS"

section "APPLY EXACT R1 PATCH"
git -C "$WT" apply --check "$PATCH_FILE"
git -C "$WT" apply --index "$PATCH_FILE"
git -C "$WT" diff --cached --check

echo "PATCHED_NAME_STATUS:"
git -C "$WT" diff --cached --name-status "$BASE"
FILES="$(git -C "$WT" diff --cached --name-only "$BASE")"
EXPECTED=$'app/device_fingerprint_integration/compatibility.py\ntests/device_fingerprint_integration/test_executor_persistence.py'
[ "$FILES" = "$EXPECTED" ] || fail "Patch changed files outside authorized scope"

ACTUAL_TREE="$(git -C "$WT" write-tree)"
echo "ACTUAL_CANDIDATE_TREE=$ACTUAL_TREE"
echo "EXPECTED_CANDIDATE_TREE=$CANDIDATE_TREE"
[ "$ACTUAL_TREE" = "$CANDIDATE_TREE" ] || fail "Patched tree does not equal coder candidate tree"
echo "EXACT_CANDIDATE_TREE=PASS"

section "SELECT LINUX TEST PYTHON"
TEST_PY=""
for p in "$VENV_PY" /usr/bin/python3; do
  if [ -x "$p" ] && sudo -H -u admin "$p" -m pytest --version >/dev/null 2>&1; then
    TEST_PY="$p"
    break
  fi
done
[ -n "$TEST_PY" ] || fail "No production-host Python with pytest available"
echo "TEST_PYTHON=$TEST_PY"
sudo -H -u admin "$TEST_PY" -m pytest --version
echo "LINUX_TEST_PYTHON=PASS"

section "ACTUAL PRODUCTION CONTROL-PLANE PREFLIGHT USING PATCHED CODE"
sudo -H -u admin env   HOME=/nonexistent   PYTHONPATH="$WT"   PYTHONDONTWRITEBYTECODE=1   CONTROL_DB="$CONTROL_DB"   "$VENV_PY" -B - <<'PY'
import os
from app.device_fingerprint.control_plane_store import DeviceFingerprintControlPlaneStore
from app.device_fingerprint_integration.compatibility import ReadOnlyControlPlaneStoreMixin, preflight

class ReadOnlyControl(ReadOnlyControlPlaneStoreMixin, DeviceFingerprintControlPlaneStore):
    pass

prepared = preflight(ReadOnlyControl(os.environ["CONTROL_DB"]))
print("ACTUAL_PREFLIGHT_PROFILE_ID="+prepared.pin.runtime_profile.artifact_id)
print("ACTUAL_PREFLIGHT_RPM_ID="+prepared.pin.admission_manifest.artifact_id)
print("ACTUAL_PREFLIGHT_VALIDITY="+prepared.pin.validity_record.semantic_payload["state"])
print("ACTUAL_PRODUCTION_PREFLIGHT_WITH_R1=PASS")
PY

section "PYTHON COMPILE GATE"
install -d -m 0700 -o admin -g admin "$TMPROOT/pyc"
sudo -H -u admin env   PYTHONPATH="$WT"   PYTHONPYCACHEPREFIX="$TMPROOT/pyc"   "$TEST_PY" -m py_compile   "$WT/app/device_fingerprint_integration/compatibility.py"
echo "PY_COMPILE_LINUX=PASS"

section "BROADER DEVICE-FINGERPRINT INTEGRATION GATE"
install -d -m 0700 -o admin -g admin "$TMPROOT/broad"
(
  cd "$WT"
  sudo -H -u admin env     PYTHONPATH="$WT"     PYTHONPYCACHEPREFIX="$TMPROOT/pyc"     "$TEST_PY" -m pytest -q     -p no:cacheprovider     --basetemp="$TMPROOT/broad"     tests/device_fingerprint_integration
)
echo "BROADER_DEVICE_FINGERPRINT_INTEGRATION_TESTS=PASS"

section "TASK04 COMPATIBILITY GATE"
rm -rf "$TMPROOT/task04"
install -d -m 0700 -o admin -g admin "$TMPROOT/task04"
(
  cd "$WT"
  sudo -H -u admin env     PYTHONPATH="$WT"     PYTHONPYCACHEPREFIX="$TMPROOT/pyc"     "$TEST_PY" -m pytest -q     -p no:cacheprovider     --basetemp="$TMPROOT/task04"     tests/device_fingerprint_task04_04d_request     tests/device_fingerprint_task04_04d_persistence
)
echo "TASK04_COMPATIBILITY_TESTS=PASS"

section "FULL REPOSITORY GATE"
rm -rf "$TMPROOT/full"
install -d -m 0700 -o admin -g admin "$TMPROOT/full"
(
  cd "$WT"
  sudo -H -u admin env     PYTHONPATH="$WT"     PYTHONPYCACHEPREFIX="$TMPROOT/pyc"     "$TEST_PY" -m pytest -q     -p no:cacheprovider     --basetemp="$TMPROOT/full"
)
echo "FULL_REPOSITORY_TESTS=PASS"

section "POST-TEST CANDIDATE INTEGRITY"
ACTUAL_TREE_POST="$(git -C "$WT" write-tree)"
echo "ACTUAL_CANDIDATE_TREE_POST=$ACTUAL_TREE_POST"
[ "$ACTUAL_TREE_POST" = "$CANDIDATE_TREE" ] || fail "Candidate index tree changed during tests"
STATUS="$(git -C "$WT" status --porcelain=v1 --untracked-files=normal)"
printf '%s\n' "$STATUS"
EXPECTED_STATUS=$'M  app/device_fingerprint_integration/compatibility.py\nM  tests/device_fingerprint_integration/test_executor_persistence.py'
[ "$STATUS" = "$EXPECTED_STATUS" ] || fail "Unexpected candidate clone changes after tests"
echo "CANDIDATE_INTEGRITY_POST_TEST=PASS"

section "PRODUCTION HOLD POSTCONDITIONS"
[ "$(git -C "$PORTAL" rev-parse HEAD)" = "$BASE" ] || fail "Production HEAD changed"
[ "$(git -C "$PORTAL" rev-parse 'HEAD^{tree}')" = "$BASE_TREE" ] || fail "Production tree changed"
[ -z "$(git -C "$PORTAL" status --porcelain=v1 --untracked-files=normal)" ] || fail "Production worktree changed"

grep -qxF 'DEVICE_FINGERPRINT_INTEGRATION_ENABLED=false' "$CFG"   || fail "Integration containment flag changed"
systemctl is-active --quiet captive-portal.service || fail "Portal inactive after gate"
if systemctl is-active --quiet fingerprint-classification.service; then
  fail "Worker unexpectedly active after gate"
fi
if systemctl is-enabled --quiet fingerprint-classification.service; then
  fail "Worker unexpectedly enabled after gate"
fi

CONTROL_SHA_AFTER="$(sha256sum "$CONTROL_DB" | awk '{print $1}')"
INTEGRATION_SHA_AFTER="$(sha256sum "$INTEGRATION_DB" | awk '{print $1}')"
PORTAL_RESTARTS_AFTER="$(systemctl show captive-portal.service -p NRestarts --value --no-pager)"
echo "CONTROL_DB_SHA256_AFTER=$CONTROL_SHA_AFTER"
echo "INTEGRATION_DB_SHA256_AFTER=$INTEGRATION_SHA_AFTER"
echo "PORTAL_NRESTARTS_AFTER=$PORTAL_RESTARTS_AFTER"

[ "$CONTROL_SHA_AFTER" = "$CONTROL_SHA_BEFORE" ] || fail "Control-plane DB changed during gate"
[ "$INTEGRATION_SHA_AFTER" = "$INTEGRATION_SHA_BEFORE" ] || fail "Integration DB changed during gate"
[ "$PORTAL_RESTARTS_AFTER" = "$PORTAL_RESTARTS_BEFORE" ] || fail "Portal restarted during gate"
echo "PRODUCTION_HOLD_UNCHANGED=PASS"

section "FINAL"
echo "TASK05_R1_PATCH_IDENTITY=PASS"
echo "TASK05_R1_EXACT_TREE=PASS"
echo "TASK05_R1_ACTUAL_PRODUCTION_PREFLIGHT=PASS"
echo "TASK05_R1_BROADER_INTEGRATION_TESTS=PASS"
echo "TASK05_R1_TASK04_COMPATIBILITY_TESTS=PASS"
echo "TASK05_R1_FULL_REPOSITORY_TESTS=PASS"
echo "TASK05_R1_PRODUCTION_HOLD_UNCHANGED=PASS"
echo "TASK05_R1_LINUX_FULL_GATE=PASS"
echo "MERGE_AUTHORIZATION=PENDING_TECH_LEAD_FINAL_REVIEW"
