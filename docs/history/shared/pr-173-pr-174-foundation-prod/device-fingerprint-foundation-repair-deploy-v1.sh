#!/usr/bin/env bash
set -Eeuo pipefail

TARGET_SHA="810484e69baa371c4696c3b46654199631538fc4"
TARGET_TREE="6816e73148c91c1e2e778613067a41d8c973c03d"
APP="/opt/CaptivePortal"
DEPLOY_PARENT="/home/admin/CaptivePortal-Deploy"
WT="${DEPLOY_PARENT}/foundation-stability-810484e6"
EVIDENCE_DROPIN="/etc/systemd/system/fingerprint-evidence.service.d/20-task01-v2.conf"
SURICATA_UNIT="/etc/systemd/system/fingerprint-suricata.service"
SURICATA_CONF="/etc/captive-portal/device-fingerprint/suricata.yaml"
DIAG_FILE="/run/fingerprint-suricata/diag-eve.json"
LOG="/home/admin/device-fingerprint-foundation-repair-deploy.txt"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP="/home/admin/captivportal-recovery/foundation-stability-${STAMP}"
DEPLOY_START="$(date '+%Y-%m-%d %H:%M:%S')"

exec > >(tee "$LOG") 2>&1

step() { printf '\n===== %s =====\n' "$1"; }
die() { echo "FATAL: $*" >&2; exit 1; }

trap 'rc=$?; echo; echo "===== ABORT ====="; echo "EXIT_CODE=$rc"; echo "NO_CLASSIFICATION_ACTIVATION=YES"; echo "BACKUP=$BACKUP"; exit $rc' ERR

[ "$(id -u)" -eq 0 ] || die "Run with sudo/root."
[ -d "$APP/.git" ] || [ -f "$APP/.git" ] || die "$APP is not a Git worktree."

step "IDENTITY / SAFETY"
echo "TARGET_SHA=$TARGET_SHA"
echo "TARGET_TREE=$TARGET_TREE"
echo "APP=$APP"
echo "FOUNDATION_WORKTREE=$WT"
echo "BACKUP=$BACKUP"
echo "CLASSIFICATION_ACTIVATION=NO"
echo "CAPTIVE_PORTAL_RESTART=NO"

CURRENT_HEAD="$(sudo -u admin git -C "$APP" rev-parse HEAD)"
CURRENT_TREE="$(sudo -u admin git -C "$APP" rev-parse 'HEAD^{tree}')"
echo "CURRENT_APP_HEAD=$CURRENT_HEAD"
echo "CURRENT_APP_TREE=$CURRENT_TREE"

if [ -n "$(sudo -u admin git -C "$APP" status --porcelain=v1)" ]; then
  sudo -u admin git -C "$APP" status --porcelain=v1
  die "$APP worktree is dirty."
fi
echo "CURRENT_APP_CLEAN=YES"

step "FETCH EXACT OWNER-MERGED MAIN"
sudo -u admin git -C "$APP" fetch --prune origin '+refs/heads/main:refs/remotes/origin/main'
REMOTE_MAIN="$(sudo -u admin git -C "$APP" rev-parse refs/remotes/origin/main)"
REMOTE_TREE="$(sudo -u admin git -C "$APP" rev-parse "${TARGET_SHA}^{tree}")"
echo "ORIGIN_MAIN=$REMOTE_MAIN"
echo "TARGET_SHA_TREE=$REMOTE_TREE"
[ "$REMOTE_MAIN" = "$TARGET_SHA" ] || die "origin/main moved away from approved merge SHA."
[ "$REMOTE_TREE" = "$TARGET_TREE" ] || die "approved merge tree mismatch."
echo "REMOTE_PROVENANCE=PASS"

step "PRE-CHANGE SERVICE STATE"
for u in captive-portal.service fingerprint-evidence.service fingerprint-sensor.service fingerprint-suricata.service; do
  echo "--- $u"
  systemctl show "$u" -p ActiveState -p SubState -p MainPID -p NRestarts --no-pager || true
done
echo "--- /run"
df -h /run || true
if [ -e "$DIAG_FILE" ]; then
  stat -c 'DIAG_BEFORE path=%n bytes=%s owner=%U group=%G mode=%a mtime=%y' "$DIAG_FILE"
else
  echo "DIAG_BEFORE=ABSENT"
fi

step "BACKUP INSTALLED FOUNDATION FILES"
mkdir -p "$BACKUP"
chown admin:admin "$(dirname "$BACKUP")" "$BACKUP" || true
systemctl cat fingerprint-evidence.service > "$BACKUP/fingerprint-evidence.systemctl-cat.txt"
systemctl cat fingerprint-suricata.service > "$BACKUP/fingerprint-suricata.systemctl-cat.txt"
cp -a "$EVIDENCE_DROPIN" "$BACKUP/" 2>/dev/null || true
cp -a "$SURICATA_UNIT" "$BACKUP/" 2>/dev/null || true
cp -a "$SURICATA_CONF" "$BACKUP/" 2>/dev/null || true
{
  echo "CURRENT_APP_HEAD=$CURRENT_HEAD"
  echo "CURRENT_APP_TREE=$CURRENT_TREE"
  echo "TARGET_SHA=$TARGET_SHA"
  echo "TARGET_TREE=$TARGET_TREE"
  sha256sum "$EVIDENCE_DROPIN" "$SURICATA_UNIT" "$SURICATA_CONF" 2>/dev/null || true
} > "$BACKUP/manifest.txt"
chown -R admin:admin "$BACKUP"
echo "BACKUP_CREATED=$BACKUP"

step "QUIESCE ONLY FOUNDATION COMPONENTS THAT WILL CHANGE"
systemctl stop fingerprint-suricata.service
systemctl stop fingerprint-evidence.service
systemctl is-active fingerprint-suricata.service || true
systemctl is-active fingerprint-evidence.service || true
[ "$(systemctl is-active fingerprint-suricata.service || true)" != "active" ] || die "Suricata did not stop."
[ "$(systemctl is-active fingerprint-evidence.service || true)" != "active" ] || die "Evidence service did not stop."
echo "FOUNDATION_QUIESCED=YES"
echo "CAPTIVE_PORTAL_STATE=$(systemctl is-active captive-portal.service || true)"
echo "SENSOR_STATE=$(systemctl is-active fingerprint-sensor.service || true)"

step "MATERIALIZE EXACT MERGED GIT WORKTREE"
install -d -o admin -g admin "$DEPLOY_PARENT"
if [ -e "$WT" ]; then
  [ -e "$WT/.git" ] || die "Target worktree path exists but is not a Git worktree."
else
  sudo -u admin git -C "$APP" worktree add --detach "$WT" "$TARGET_SHA"
fi
WT_HEAD="$(sudo -u admin git -C "$WT" rev-parse HEAD)"
WT_TREE="$(sudo -u admin git -C "$WT" rev-parse 'HEAD^{tree}')"
echo "WORKTREE_HEAD=$WT_HEAD"
echo "WORKTREE_TREE=$WT_TREE"
[ "$WT_HEAD" = "$TARGET_SHA" ] || die "Foundation worktree HEAD mismatch."
[ "$WT_TREE" = "$TARGET_TREE" ] || die "Foundation worktree tree mismatch."
[ -z "$(sudo -u admin git -C "$WT" status --porcelain=v1)" ] || die "Foundation worktree is dirty."
echo "WORKTREE_CLEAN=YES"

step "INSTALL FOUNDATION REPAIR FROM EXACT GIT TREE"
# Preserve existing ownership/mode by truncating and replacing content in place.
cat "$WT/deploy/device-fingerprint/suricata.yaml" > "$SURICATA_CONF"
cat "$WT/deploy/device-fingerprint/fingerprint-suricata.service" > "$SURICATA_UNIT"
cat > "$EVIDENCE_DROPIN" <<EOF
[Service]
WorkingDirectory=$WT
EOF

cmp -s "$WT/deploy/device-fingerprint/suricata.yaml" "$SURICATA_CONF" || die "Installed Suricata config differs from exact Git artifact."
cmp -s "$WT/deploy/device-fingerprint/fingerprint-suricata.service" "$SURICATA_UNIT" || die "Installed Suricata unit differs from exact Git artifact."

grep -Fq 'filetype: unix_dgram' "$SURICATA_CONF" || die "UNIX datagram EVE output missing."
grep -Fq 'filename: /run/captive-portal/fingerprint-sensor/suricata-eve.sock' "$SURICATA_CONF" || die "Sensor socket path missing."
if grep -Fq 'filetype: regular' "$SURICATA_CONF" || grep -Fq 'diag-eve.json' "$SURICATA_CONF"; then
  die "Unsafe regular diagnostic EVE output still present."
fi
grep -Fq 'ReadOnlyPaths=/run' "$SURICATA_UNIT" || die "ReadOnlyPaths=/run missing."

rm -f "$DIAG_FILE"
echo "DIAGNOSTIC_FILE_REMOVED=YES"

step "SYSTEMD VALIDATION / RELOAD"
systemctl daemon-reload
systemd-analyze verify "$SURICATA_UNIT"
echo "SYSTEMD_VERIFY=PASS"
echo "--- effective evidence unit"
systemctl cat fingerprint-evidence.service
echo "--- effective Suricata boundary"
systemctl cat fingerprint-suricata.service | grep -E '^(ExecStart|ExecStartPre|ReadOnlyPaths|User|Group|SupplementaryGroups|AmbientCapabilities|CapabilityBoundingSet)=' || true

step "START EVIDENCE ON MERGED ARTIFACT"
systemctl start fingerprint-evidence.service

evidence_ready=0
for i in $(seq 1 24); do
  if systemctl is-active --quiet fingerprint-evidence.service; then
    if journalctl -u fingerprint-evidence.service --since "$DEPLOY_START" --no-pager \
      | grep -F "$TARGET_SHA" \
      | grep -Fq '"event":"device_fingerprint_service_started"'; then
      evidence_ready=1
      break
    fi
  fi
  echo "WAIT_EVIDENCE_READY attempt=$i/24"
  sleep 10
done

if [ "$evidence_ready" -ne 1 ]; then
  echo "--- evidence journal tail"
  journalctl -u fingerprint-evidence.service -n 120 --no-pager || true
  die "Evidence service did not publish ready identity for target SHA."
fi

echo "EVIDENCE_ACTIVE=$(systemctl is-active fingerprint-evidence.service)"
echo "EVIDENCE_PID=$(systemctl show fingerprint-evidence.service -p MainPID --value)"
echo "EVIDENCE_TARGET_IDENTITY=PASS"

step "START SURICATA WITH SOCKET-ONLY /RUN BOUNDARY"
systemctl start fingerprint-suricata.service

suricata_ready=0
for i in $(seq 1 12); do
  if systemctl is-active --quiet fingerprint-suricata.service; then
    suricata_ready=1
    break
  fi
  echo "WAIT_SURICATA_ACTIVE attempt=$i/12"
  sleep 5
done

if [ "$suricata_ready" -ne 1 ]; then
  echo "--- Suricata journal tail"
  journalctl -u fingerprint-suricata.service -n 120 --no-pager || true
  die "Suricata failed to become active."
fi

sleep 20

step "POST-DEPLOY IMMEDIATE VALIDATION"
for u in captive-portal.service fingerprint-evidence.service fingerprint-sensor.service fingerprint-suricata.service; do
  echo "--- $u"
  systemctl show "$u" -p ActiveState -p SubState -p MainPID -p NRestarts --no-pager
done

echo "--- worktree identity"
sudo -u admin git -C "$WT" rev-parse HEAD
sudo -u admin git -C "$WT" rev-parse 'HEAD^{tree}'
echo "--- evidence listener"
ss -lntp | grep ':9443' || true
echo "--- sensor socket"
ls -l /run/captive-portal/fingerprint-sensor/suricata-eve.sock
echo "--- /run"
df -h /run
echo "--- diagnostic output"
if [ -e "$DIAG_FILE" ]; then
  stat -c 'DIAG_AFTER_UNEXPECTED path=%n bytes=%s owner=%U group=%G mode=%a mtime=%y' "$DIAG_FILE"
  die "diag-eve.json was recreated."
else
  echo "DIAG_AFTER=ABSENT"
fi

echo "--- current Suricata config safety"
grep -nE 'filetype:|filename:|ReadOnlyPaths=' "$SURICATA_CONF" "$SURICATA_UNIT" || true

echo "--- new evidence events"
journalctl -u fingerprint-evidence.service --since "$DEPLOY_START" -n 120 --no-pager || true
echo "--- new sensor events"
journalctl -u fingerprint-sensor.service --since "$DEPLOY_START" -n 120 --no-pager || true
echo "--- new Suricata events"
journalctl -u fingerprint-suricata.service --since "$DEPLOY_START" -n 120 --no-pager || true

if journalctl -u fingerprint-evidence.service --since "$DEPLOY_START" --no-pager \
  | grep -Fq '"error_category":"concurrency_limit"'; then
  echo "IMMEDIATE_429=YES"
else
  echo "IMMEDIATE_429=NO"
fi

LATEST_SENSOR_METRIC="$(journalctl -u fingerprint-sensor.service --since "$DEPLOY_START" --no-pager \
  | grep -F '"event":"fingerprint_sensor_metrics"' | tail -n 1 || true)"
if [ -n "$LATEST_SENSOR_METRIC" ]; then
  echo "LATEST_SENSOR_METRIC=$LATEST_SENSOR_METRIC"
else
  echo "LATEST_SENSOR_METRIC=NOT_OBSERVED_YET"
fi

step "FINAL"
echo "FOUNDATION_REPAIR_DEPLOY=PASS"
echo "TARGET_SHA=$TARGET_SHA"
echo "TARGET_TREE=$TARGET_TREE"
echo "EVIDENCE_LOADED_TARGET=YES"
echo "SURICATA_SOCKET_ONLY=YES"
echo "SURICATA_RUN_READONLY=YES"
echo "DIAG_EVE_PRESENT=NO"
echo "CAPTIVE_PORTAL_RESTARTED=NO"
echo "CLASSIFICATION_ACTIVATION=NO"
echo "BACKUP=$BACKUP"
echo "LOG=$LOG"
