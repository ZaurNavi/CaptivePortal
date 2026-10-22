#!/usr/bin/env bash
set -Eeuo pipefail

export SYSTEMD_PAGER=cat
export PAGER=cat

PORTAL="/opt/CaptivePortal"
DEPLOY_ROOT="/home/admin/CaptivePortal-Deploy"
STAGE_DIR="$DEPLOY_ROOT/task05-merged-1d88f4ae"
TMP_DIR="$DEPLOY_ROOT/.task05-stage-$$"

EXPECTED_CURRENT_HEAD="f5e3d194ebffb3c6c1e1cd8afc31f80911e2ce71"
EXPECTED_CURRENT_TREE="02b6af353643a4321a6f14d01735b9c0e305842e"
EXPECTED_TASK05_COMMIT="1d88f4ae947fa95454dbb54c70f9d6bdd13b1d22"
EXPECTED_TASK05_TREE="8183bf48abfc71c1b488c0667efc0f1ae717003e"
HTTPS_ORIGIN="https://github.com/ZaurNavi/CaptivePortal.git"

section() { printf '\n===== %s =====\n' "$1"; }
fail() { echo "FATAL: $*" >&2; exit 1; }

cleanup() {
  if [ -d "$TMP_DIR" ]; then
    rm -rf -- "$TMP_DIR"
  fi
}
trap cleanup EXIT

section "DECLARATION"
date --iso-8601=seconds
echo "MODE=TASK05_PROD_STAGE_EXACT_ARTIFACT"
echo "PORTAL_SWITCH=NO"
echo "CONFIG_WRITE=NO"
echo "SYSTEMD_WRITE=NO"
echo "SERVICE_RESTART=NO"
echo "DATABASE_WRITE=NO"
echo "STAGING_WRITE=YES"
echo "TARGET_STAGE_DIR=$STAGE_DIR"

section "PRECONDITION CURRENT PRODUCTION"
[ -d "$PORTAL/.git" ] || fail "$PORTAL is not a Git worktree"
CURRENT_HEAD="$(git -C "$PORTAL" rev-parse HEAD)"
CURRENT_TREE="$(git -C "$PORTAL" rev-parse 'HEAD^{tree}')"
CURRENT_STATUS="$(git -C "$PORTAL" status --porcelain=v1 --untracked-files=normal)"
echo "CURRENT_HEAD=$CURRENT_HEAD"
echo "CURRENT_TREE=$CURRENT_TREE"
[ "$CURRENT_HEAD" = "$EXPECTED_CURRENT_HEAD" ] || fail "Current production HEAD changed"
[ "$CURRENT_TREE" = "$EXPECTED_CURRENT_TREE" ] || fail "Current production tree changed"
[ -z "$CURRENT_STATUS" ] || fail "Current production worktree is not clean"
echo "CURRENT_PRODUCTION_PRECONDITION=PASS"

section "REMOTE EXACT IDENTITY"
REMOTE_MAIN="$(git ls-remote "$HTTPS_ORIGIN" refs/heads/main | awk '{print $1}')"
[ -n "$REMOTE_MAIN" ] || fail "Cannot read GitHub main over HTTPS"
echo "REMOTE_MAIN=$REMOTE_MAIN"
echo "EXPECTED_TASK05_COMMIT=$EXPECTED_TASK05_COMMIT"
echo "EXPECTED_TASK05_TREE=$EXPECTED_TASK05_TREE"
if [ "$REMOTE_MAIN" = "$EXPECTED_TASK05_COMMIT" ]; then
  echo "REMOTE_MAIN_IS_TASK05_MERGE=YES"
else
  echo "REMOTE_MAIN_IS_TASK05_MERGE=NO"
  echo "NOTE=Main advanced after Task-05; exact Task-05 commit will still be staged"
fi

section "STAGE EXACT ARTIFACT"
install -d -m 0755 -o admin -g admin "$DEPLOY_ROOT"

if [ -e "$STAGE_DIR" ]; then
  [ -d "$STAGE_DIR/.git" ] || fail "Existing stage path is not a Git clone"
  STAGE_HEAD="$(git -C "$STAGE_DIR" rev-parse HEAD)"
  STAGE_TREE="$(git -C "$STAGE_DIR" rev-parse 'HEAD^{tree}')"
  STAGE_STATUS="$(git -C "$STAGE_DIR" status --porcelain=v1 --untracked-files=normal)"
  echo "EXISTING_STAGE=YES"
  echo "STAGE_HEAD=$STAGE_HEAD"
  echo "STAGE_TREE=$STAGE_TREE"
  [ "$STAGE_HEAD" = "$EXPECTED_TASK05_COMMIT" ] || fail "Existing stage HEAD is not exact Task-05 merge"
  [ "$STAGE_TREE" = "$EXPECTED_TASK05_TREE" ] || fail "Existing stage tree is not exact Task-05 tree"
  [ -z "$STAGE_STATUS" ] || fail "Existing stage worktree is not clean"
else
  echo "EXISTING_STAGE=NO"
  rm -rf -- "$TMP_DIR"
  sudo -u admin git clone --filter=blob:none --no-checkout "$HTTPS_ORIGIN" "$TMP_DIR"
  sudo -u admin git -C "$TMP_DIR" checkout --detach "$EXPECTED_TASK05_COMMIT"

  TMP_HEAD="$(git -C "$TMP_DIR" rev-parse HEAD)"
  TMP_TREE="$(git -C "$TMP_DIR" rev-parse 'HEAD^{tree}')"
  TMP_STATUS="$(git -C "$TMP_DIR" status --porcelain=v1 --untracked-files=normal)"
  echo "TMP_HEAD=$TMP_HEAD"
  echo "TMP_TREE=$TMP_TREE"
  [ "$TMP_HEAD" = "$EXPECTED_TASK05_COMMIT" ] || fail "Fetched commit identity mismatch"
  [ "$TMP_TREE" = "$EXPECTED_TASK05_TREE" ] || fail "Fetched tree identity mismatch"
  [ -z "$TMP_STATUS" ] || fail "Fetched stage worktree is not clean"

  mv "$TMP_DIR" "$STAGE_DIR"
  chown -R admin:admin "$STAGE_DIR"
fi

section "TASK05 ARTIFACT CONTENT CHECK"
[ -f "$STAGE_DIR/deploy/device-fingerprint/INTEGRATION.md" ] \
  || fail "Task-05 integration deployment documentation missing"
[ -f "$STAGE_DIR/deploy/device-fingerprint/fingerprint-classification.service" ] \
  || fail "Task-05 classification service unit missing"
[ -d "$STAGE_DIR/app/device_fingerprint_integration" ] \
  || fail "Task-05 integration package missing"
grep -q '^DEVICE_FINGERPRINT_INTEGRATION_ENABLED=false$' "$STAGE_DIR/.env.example" \
  || fail "Expected disabled-by-default integration setting missing"
grep -q '^ExecStart=/usr/bin/python3 -m app.device_fingerprint_integration.cli run$' \
  "$STAGE_DIR/deploy/device-fingerprint/fingerprint-classification.service" \
  || fail "Unexpected classification worker ExecStart"
echo "TASK05_ARTIFACT_CONTENT=PASS"

section "POST-STAGE PRODUCTION INVARIANTS"
POST_HEAD="$(git -C "$PORTAL" rev-parse HEAD)"
POST_TREE="$(git -C "$PORTAL" rev-parse 'HEAD^{tree}')"
POST_STATUS="$(git -C "$PORTAL" status --porcelain=v1 --untracked-files=normal)"
echo "POST_PRODUCTION_HEAD=$POST_HEAD"
echo "POST_PRODUCTION_TREE=$POST_TREE"
[ "$POST_HEAD" = "$EXPECTED_CURRENT_HEAD" ] || fail "Production HEAD changed during staging"
[ "$POST_TREE" = "$EXPECTED_CURRENT_TREE" ] || fail "Production tree changed during staging"
[ -z "$POST_STATUS" ] || fail "Production worktree changed during staging"

systemctl is-active --quiet captive-portal.service \
  || fail "captive-portal.service is not active after staging"
echo "PORTAL_SERVICE_ACTIVE=PASS"

if [ -e /opt/CaptivePortal/data/device_fingerprint_integration.sqlite3 ]; then
  fail "Integration DB appeared during artifact-only staging"
fi
echo "INTEGRATION_DB_STILL_ABSENT=PASS"

if systemctl cat fingerprint-classification.service --no-pager >/dev/null 2>&1; then
  fail "fingerprint-classification.service unexpectedly appeared during staging"
fi
echo "CLASSIFICATION_UNIT_STILL_ABSENT=PASS"

section "FINAL"
echo "TASK05_STAGED_HEAD=$(git -C "$STAGE_DIR" rev-parse HEAD)"
echo "TASK05_STAGED_TREE=$(git -C "$STAGE_DIR" rev-parse 'HEAD^{tree}')"
echo "TASK05_STAGED_PATH=$STAGE_DIR"
echo "CURRENT_PRODUCTION_ROLLBACK_POINT=$EXPECTED_CURRENT_HEAD"
echo "TASK05_PROD_STAGE_EXACT_ARTIFACT=PASS"
echo "PRODUCTION_CODE_SWITCHED=NO"
echo "CONFIG_CHANGED=NO"
echo "SYSTEMD_CHANGED=NO"
echo "SERVICES_RESTARTED=NO"
echo "DATABASES_CHANGED=NO"
