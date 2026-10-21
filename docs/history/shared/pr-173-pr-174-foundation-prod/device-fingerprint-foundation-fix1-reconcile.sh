#!/usr/bin/env bash
set -Eeuo pipefail

TARGET_SHA="fecdb5a7c79e56bb49be4797ca875d6720670042"
TARGET_TREE="85d7d41e1ad19c079cad0ae819a3fe38a068e242"
APP="/opt/CaptivePortal"
WT="/home/admin/CaptivePortal-Deploy/foundation-fix1-fecdb5a7"
LIVE_UNIT="/etc/systemd/system/fingerprint-suricata.service"
LIVE_CONF="/etc/captive-portal/device-fingerprint/suricata.yaml"
REPORT="/home/admin/device-fingerprint-foundation-fix1-reconcile.txt"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP="/home/admin/captivportal-recovery/foundation-fix1-reconcile-${STAMP}"

exec > >(tee "$REPORT") 2>&1

step(){ printf '\n===== %s =====\n' "$1"; }
die(){ echo "FATAL: $*" >&2; exit 1; }

trap 'rc=$?; echo; echo "===== ABORT ====="; echo "EXIT_CODE=$rc"; echo "BACKUP=$BACKUP"; echo "CLASSIFICATION_ACTIVATION=NO"; exit $rc' ERR

[ "$(id -u)" -eq 0 ] || die "Run as root/sudo."
[ -d "$APP/.git" ] || [ -f "$APP/.git" ] || die "$APP is not a Git worktree."

step "SAFETY / CURRENT STATE"
date -Is
echo "TARGET_SHA=$TARGET_SHA"
echo "TARGET_TREE=$TARGET_TREE"
echo "CLASSIFICATION_ACTIVATION=NO"
echo "CAPTIVE_PORTAL_RESTART=NO"
echo "EVIDENCE_RESTART=NO"

for u in captive-portal.service fingerprint-evidence.service fingerprint-sensor.service fingerprint-suricata.service; do
  echo "--- $u"
  systemctl show "$u" -p ActiveState -p SubState -p MainPID -p NRestarts --no-pager || true
done

systemctl is-active --quiet captive-portal.service || die "captive-portal.service is not active."
systemctl is-active --quiet fingerprint-evidence.service || die "fingerprint-evidence.service is not active."
systemctl is-active --quiet fingerprint-sensor.service || die "fingerprint-sensor.service is not active."
systemctl is-active --quiet fingerprint-suricata.service || die "fingerprint-suricata.service is not active."

echo "--- current live config"
grep -nE 'default-log-dir:|filetype:|filename:' "$LIVE_CONF" || true
echo "--- current live unit"
grep -nE 'RuntimeDirectory=|RuntimeDirectoryMode=|ReadOnlyPaths=|ReadWritePaths=|BindPaths=' "$LIVE_UNIT" || true
echo "--- /run"
df -h /run
if [ -e /run/fingerprint-suricata/diag-eve.json ]; then
  stat -c 'DIAG_BEFORE path=%n bytes=%s owner=%U group=%G mode=%a mtime=%y' /run/fingerprint-suricata/diag-eve.json
  die "diag-eve.json unexpectedly exists before reconciliation."
fi
echo "DIAG_BEFORE=ABSENT"

step "VERIFY EXACT OWNER-MERGED GIT TARGET"
sudo -u admin git -C "$APP" fetch --prune origin '+refs/heads/main:refs/remotes/origin/main'
REMOTE_MAIN="$(sudo -u admin git -C "$APP" rev-parse refs/remotes/origin/main)"
REMOTE_TREE="$(sudo -u admin git -C "$APP" rev-parse "${TARGET_SHA}^{tree}")"
echo "ORIGIN_MAIN=$REMOTE_MAIN"
echo "TARGET_SHA_TREE=$REMOTE_TREE"
[ "$REMOTE_MAIN" = "$TARGET_SHA" ] || die "origin/main moved away from approved FIX1 merge."
[ "$REMOTE_TREE" = "$TARGET_TREE" ] || die "FIX1 merge tree mismatch."
echo "POST_MERGE_PROVENANCE=PASS"

step "MATERIALIZE EXACT FIX1 MERGE"
install -d -o admin -g admin /home/admin/CaptivePortal-Deploy
if [ -e "$WT" ]; then
  [ -e "$WT/.git" ] || die "Target worktree path exists but is not a Git worktree."
else
  sudo -u admin git -C "$APP" worktree add --detach "$WT" "$TARGET_SHA"
fi

WT_HEAD="$(sudo -u admin git -C "$WT" rev-parse HEAD)"
WT_TREE="$(sudo -u admin git -C "$WT" rev-parse 'HEAD^{tree}')"
echo "WORKTREE_HEAD=$WT_HEAD"
echo "WORKTREE_TREE=$WT_TREE"
[ "$WT_HEAD" = "$TARGET_SHA" ] || die "Worktree HEAD mismatch."
[ "$WT_TREE" = "$TARGET_TREE" ] || die "Worktree tree mismatch."
[ -z "$(sudo -u admin git -C "$WT" status --porcelain=v1)" ] || die "FIX1 worktree is dirty."
echo "WORKTREE_CLEAN=YES"

step "VERIFY SOURCE ARTIFACT CONTRACT"
SRC_CONF="$WT/deploy/device-fingerprint/suricata.yaml"
SRC_UNIT="$WT/deploy/device-fingerprint/fingerprint-suricata.service"

grep -Fq 'default-log-dir: /run/fingerprint-suricata' "$SRC_CONF" || die "Source default-log-dir mismatch."
grep -Fq 'filetype: unix_dgram' "$SRC_CONF" || die "Source unix_dgram missing."
grep -Fq 'filename: /run/captive-portal/fingerprint-sensor/suricata-eve.sock' "$SRC_CONF" || die "Source sensor socket missing."
if grep -Fq 'filetype: regular' "$SRC_CONF" || grep -Fq 'diag-eve.json' "$SRC_CONF"; then
  die "Unsafe diagnostic EVE output exists in source."
fi

grep -Fq 'RuntimeDirectory=fingerprint-suricata' "$SRC_UNIT" || die "RuntimeDirectory missing."
grep -Fq 'RuntimeDirectoryMode=0750' "$SRC_UNIT" || die "RuntimeDirectoryMode missing."
if grep -Eq '^(ReadOnlyPaths|ReadWritePaths|BindPaths)=' "$SRC_UNIT"; then
  die "Unexpected /run filesystem workaround present in source unit."
fi
echo "SOURCE_ARTIFACT_CONTRACT=PASS"

step "BACKUP CURRENT INSTALLED FILES"
mkdir -p "$BACKUP"
cp -a "$LIVE_CONF" "$BACKUP/suricata.yaml.before"
cp -a "$LIVE_UNIT" "$BACKUP/fingerprint-suricata.service.before"
{
  echo "TARGET_SHA=$TARGET_SHA"
  echo "TARGET_TREE=$TARGET_TREE"
  sha256sum "$LIVE_CONF" "$LIVE_UNIT" "$SRC_CONF" "$SRC_UNIT"
} > "$BACKUP/manifest.txt"
chown -R admin:admin "$BACKUP"
echo "BACKUP=$BACKUP"

step "RECONCILE SURICATA FROM EXACT GIT MERGE"
systemctl stop fingerprint-suricata.service
[ "$(systemctl is-active fingerprint-suricata.service || true)" != "active" ] || die "Suricata did not stop."

# Replace contents while preserving existing file ownership/mode.
cat "$SRC_CONF" > "$LIVE_CONF"
cat "$SRC_UNIT" > "$LIVE_UNIT"

cmp -s "$SRC_CONF" "$LIVE_CONF" || die "Installed config differs from Git artifact."
cmp -s "$SRC_UNIT" "$LIVE_UNIT" || die "Installed unit differs from Git artifact."
echo "INSTALLED_CONFIG_GIT_IDENTITY=PASS"
echo "INSTALLED_UNIT_GIT_IDENTITY=PASS"

rm -f /run/fingerprint-suricata/diag-eve.json

step "SYSTEMD VALIDATE / START"
systemctl daemon-reload
systemd-analyze verify "$LIVE_UNIT"
echo "SYSTEMD_VERIFY=PASS"

# Config syntax verification before service start.
runuser -u suricata -- /usr/bin/suricata -T -c "$LIVE_CONF"
echo "SURICATA_T_AS_SERVICE_USER=PASS"

systemctl reset-failed fingerprint-suricata.service || true
systemctl start fingerprint-suricata.service

for i in $(seq 1 12); do
  if systemctl is-active --quiet fingerprint-suricata.service; then
    echo "SURICATA_ACTIVE=YES"
    break
  fi
  echo "WAIT_SURICATA attempt=$i/12"
  sleep 5
done
systemctl is-active --quiet fingerprint-suricata.service || {
  journalctl -u fingerprint-suricata.service -n 160 --no-pager || true
  die "Suricata failed after exact Git reconciliation."
}

sleep 70

step "POST-RECONCILIATION VALIDATION"
for u in captive-portal.service fingerprint-evidence.service fingerprint-sensor.service fingerprint-suricata.service; do
  echo "--- $u"
  systemctl show "$u" -p ActiveState -p SubState -p MainPID -p NRestarts -p Result --no-pager
done

echo "--- exact installed hashes"
sha256sum "$SRC_CONF" "$LIVE_CONF" "$SRC_UNIT" "$LIVE_UNIT"

echo "--- effective config"
grep -nE 'default-log-dir:|filetype:|filename:' "$LIVE_CONF"

echo "--- effective unit"
grep -nE 'RuntimeDirectory=|RuntimeDirectoryMode=|ReadOnlyPaths=|ReadWritePaths=|BindPaths=' "$LIVE_UNIT" || true

echo "--- runtime dir"
stat -c 'RUNDIR path=%n owner=%U group=%G mode=%a' /run/fingerprint-suricata

echo "--- sensor socket"
ls -l /run/captive-portal/fingerprint-sensor/suricata-eve.sock

echo "--- /run"
df -h /run

echo "--- diagnostic file"
if [ -e /run/fingerprint-suricata/diag-eve.json ]; then
  stat -c 'DIAG_AFTER_BAD path=%n bytes=%s owner=%U group=%G mode=%a mtime=%y' /run/fingerprint-suricata/diag-eve.json
  die "diag-eve.json recreated."
else
  echo "DIAG_EVE_PRESENT=NO"
fi

echo "--- latest sensor metrics"
journalctl -u fingerprint-sensor.service -n 400 --no-pager \
  | grep '"event":"fingerprint_sensor_metrics"' \
  | tail -n 3 || true

echo "--- evidence maintenance / rejects since target evidence start"
journalctl -u fingerprint-evidence.service --since "2026-10-03 14:48:25" --no-pager \
  | grep -E 'device_fingerprint_service_started|device_fingerprint_retention_completed|concurrency_limit|device_fingerprint_ingest_rejected' \
  | tail -n 80 || true

echo "--- recent Suricata"
journalctl -u fingerprint-suricata.service -n 80 --no-pager || true

step "FINAL"
echo "FIX1_POST_MERGE_PROVENANCE=PASS"
echo "SURICATA_GIT_RECONCILIATION=PASS"
echo "SURICATA_RUNTIME=PASS"
echo "DIAG_EVE_PRESENT=NO"
echo "CAPTIVE_PORTAL_RESTARTED=NO"
echo "EVIDENCE_RESTARTED=NO"
echo "CLASSIFICATION_ACTIVATION=NO"
echo "TARGET_SHA=$TARGET_SHA"
echo "TARGET_TREE=$TARGET_TREE"
echo "REPORT=$REPORT"
