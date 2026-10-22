#!/usr/bin/env bash
set -Eeuo pipefail

BACKUP="/home/admin/captivportal-recovery/foundation-stability-20261003T104609Z"
OLD_UNIT="$BACKUP/fingerprint-suricata.service"
LIVE_UNIT="/etc/systemd/system/fingerprint-suricata.service"
LIVE_CONF="/etc/captive-portal/device-fingerprint/suricata.yaml"
REPORT="/home/admin/device-fingerprint-suricata-rescue-r1.txt"

exec > >(tee "$REPORT") 2>&1

step(){ printf '\n===== %s =====\n' "$1"; }
die(){ echo "FATAL: $*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || die "Run with sudo/root."
[ -r "$OLD_UNIT" ] || die "Backup unit not found: $OLD_UNIT"
[ -r "$LIVE_CONF" ] || die "Live Suricata config not found."

step "PRE-RESCUE STATE"
date -Is
systemctl show fingerprint-suricata.service -p ActiveState -p SubState -p Result -p ExecMainStatus -p MainPID -p NRestarts --no-pager || true
systemctl show fingerprint-evidence.service -p ActiveState -p SubState -p MainPID -p NRestarts --no-pager || true
systemctl show fingerprint-sensor.service -p ActiveState -p SubState -p MainPID -p NRestarts --no-pager || true

step "FAILED START EVIDENCE"
journalctl -u fingerprint-suricata.service --since "2026-10-03 14:45:00" -n 160 --no-pager || true

step "VERIFY SOCKET-ONLY CONFIG IS KEPT"
grep -nE 'filetype:|filename:' "$LIVE_CONF" || true
grep -Fq 'filetype: unix_dgram' "$LIVE_CONF" || die "unix_dgram output missing."
grep -Fq 'filename: /run/captive-portal/fingerprint-sensor/suricata-eve.sock' "$LIVE_CONF" || die "sensor socket path missing."
if grep -Fq 'filetype: regular' "$LIVE_CONF" || grep -Fq 'diag-eve.json' "$LIVE_CONF"; then
  die "Live config unexpectedly contains regular diagnostic output."
fi
echo "SOCKET_ONLY_CONFIG=PASS"

step "ROLL BACK ONLY SYSTEMD READONLY BOUNDARY"
cp -a "$OLD_UNIT" "$LIVE_UNIT"
systemctl daemon-reload
systemd-analyze verify "$LIVE_UNIT" || die "Restored unit fails systemd verify."

if grep -Fq 'ReadOnlyPaths=/run' "$LIVE_UNIT"; then
  die "Backup unit unexpectedly still contains ReadOnlyPaths=/run."
fi
echo "READONLY_RUN_BOUNDARY_ROLLED_BACK=YES"
echo "SOCKET_ONLY_CONFIG_PRESERVED=YES"

step "START SURICATA"
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
  die "Suricata still failed after minimal unit rollback."
}

sleep 20

step "POST-RESCUE VALIDATION"
for u in fingerprint-evidence.service fingerprint-sensor.service fingerprint-suricata.service captive-portal.service; do
  echo "--- $u"
  systemctl show "$u" -p ActiveState -p SubState -p MainPID -p NRestarts --no-pager
done

echo "--- socket"
ls -l /run/captive-portal/fingerprint-sensor/suricata-eve.sock || true

echo "--- /run"
df -h /run

echo "--- diagnostic file"
if [ -e /run/fingerprint-suricata/diag-eve.json ]; then
  stat -c 'DIAG_UNEXPECTED path=%n bytes=%s owner=%U group=%G mode=%a mtime=%y' /run/fingerprint-suricata/diag-eve.json
  die "Diagnostic file was recreated even though socket-only config is installed."
else
  echo "DIAG_EVE_PRESENT=NO"
fi

echo "--- recent Suricata"
journalctl -u fingerprint-suricata.service -n 100 --no-pager || true

echo "--- recent sensor metrics"
journalctl -u fingerprint-sensor.service -n 120 --no-pager \
  | grep -E 'fingerprint_sensor_metrics|fingerprint_delivery_(success|retry)|runtime_state' \
  | tail -n 60 || true

echo "--- recent evidence"
journalctl -u fingerprint-evidence.service -n 100 --no-pager \
  | grep -E 'device_fingerprint_service_started|device_fingerprint_ingest_(accepted|rejected)|concurrency_limit|retention_completed' \
  | tail -n 60 || true

step "FINAL"
echo "SURICATA_CAPTURE_RESTORED=PASS"
echo "SOCKET_ONLY_CONFIG=PASS"
echo "READONLY_RUN_BOUNDARY=ROLLED_BACK_PENDING_LINUX_FIX"
echo "EVIDENCE_REPAIR_REMAINS_DEPLOYED=YES"
echo "CAPTIVE_PORTAL_RESTARTED=NO"
echo "CLASSIFICATION_ACTIVATION=NO"
echo "REPORT=$REPORT"
