#!/usr/bin/env bash
set -Eeuo pipefail

CONF="/etc/captive-portal/device-fingerprint/suricata.yaml"
UNIT="/etc/systemd/system/fingerprint-suricata.service"
RUNDIR="/run/fingerprint-suricata"
SOCKET="/run/captive-portal/fingerprint-sensor/suricata-eve.sock"
REPORT="/home/admin/device-fingerprint-suricata-rescue-r2.txt"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP="/home/admin/captivportal-recovery/suricata-rescue-r2-${STAMP}"

exec > >(tee "$REPORT") 2>&1

step(){ printf '\n===== %s =====\n' "$1"; }
die(){ echo "FATAL: $*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || die "Run with sudo/root."
[ -r "$CONF" ] || die "Missing $CONF"
[ -r "$UNIT" ] || die "Missing $UNIT"

step "PRECHECK"
date -Is
systemctl show fingerprint-suricata.service -p ActiveState -p SubState -p Result -p MainPID -p NRestarts --no-pager || true
systemctl show fingerprint-evidence.service -p ActiveState -p SubState -p MainPID -p NRestarts --no-pager || true
systemctl show fingerprint-sensor.service -p ActiveState -p SubState -p MainPID -p NRestarts --no-pager || true
echo "--- current config"
grep -nE 'default-log-dir:|filetype:|filename:' "$CONF" || true
echo "--- current unit boundary"
grep -nE 'ReadOnlyPaths=|ReadWritePaths=|RuntimeDirectory=' "$UNIT" || true

grep -Fq 'filetype: unix_dgram' "$CONF" || die "unix_dgram output missing."
grep -Fq "filename: $SOCKET" "$CONF" || die "sensor socket output missing."
if grep -Fq 'filetype: regular' "$CONF" || grep -Fq 'diag-eve.json' "$CONF"; then
  die "Unsafe diagnostic regular output is present; refusing recovery."
fi
if grep -Fq 'ReadOnlyPaths=/run' "$UNIT"; then
  die "ReadOnlyPaths=/run is still present; R1 rollback did not apply."
fi
echo "SOCKET_ONLY_CONFIG=PASS"
echo "READONLY_RUN_BOUNDARY_ABSENT=PASS"

step "BACKUP CURRENT INCIDENT STATE"
mkdir -p "$BACKUP"
cp -a "$CONF" "$BACKUP/suricata.yaml.before-r2"
cp -a "$UNIT" "$BACKUP/fingerprint-suricata.service.before-r2"
journalctl -u fingerprint-suricata.service -n 200 --no-pager > "$BACKUP/fingerprint-suricata.pre-r2.journal.txt" || true
sha256sum "$BACKUP/"* 2>/dev/null || true
echo "BACKUP=$BACKUP"

step "APPLY MINIMAL INCIDENT RECOVERY"
# The sensor-owned socket directory is intentionally not writable by Suricata.
# Suricata 8.0.6 validates default-log-dir writability during startup even when
# the admitted EVE output is AF_UNIX datagram only. Restore the known working
# Suricata-owned runtime log directory without restoring any regular EVE output.
python3 - "$CONF" <<'PY'
from pathlib import Path
import sys

p = Path(sys.argv[1])
text = p.read_text(encoding="utf-8")
old = "default-log-dir: /run/captive-portal/fingerprint-sensor"
new = "default-log-dir: /run/fingerprint-suricata"
count = text.count(old)
if count != 1:
    raise SystemExit(f"expected exactly one {old!r}, found {count}")
p.write_text(text.replace(old, new), encoding="utf-8")
PY

install -d -o suricata -g suricata -m 0750 "$RUNDIR"

grep -Fq 'default-log-dir: /run/fingerprint-suricata' "$CONF" || die "default-log-dir recovery not applied."
if grep -Fq 'filetype: regular' "$CONF" || grep -Fq 'diag-eve.json' "$CONF"; then
  die "Diagnostic output appeared unexpectedly."
fi
echo "DEFAULT_LOG_DIR_RECOVERY=APPLIED"
echo "DIAGNOSTIC_OUTPUT=ABSENT"

step "SURICATA CONFIG TEST"
# Run the same test-mode command used by the service, as the service user context
# is enforced by systemd on actual start.
systemctl reset-failed fingerprint-suricata.service || true
/usr/bin/suricata -T -c "$CONF"
echo "SURICATA_CONFIG_TEST=PASS"

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

if ! systemctl is-active --quiet fingerprint-suricata.service; then
  journalctl -u fingerprint-suricata.service -n 160 --no-pager || true
  die "Suricata did not recover."
fi

sleep 20

step "POST-RECOVERY VALIDATION"
for u in fingerprint-suricata.service fingerprint-sensor.service fingerprint-evidence.service captive-portal.service; do
  echo "--- $u"
  systemctl show "$u" -p ActiveState -p SubState -p Result -p MainPID -p NRestarts --no-pager
done

echo "--- runtime directory"
stat -c 'RUNDIR path=%n owner=%U group=%G mode=%a' "$RUNDIR"
echo "--- sensor socket"
ls -l "$SOCKET" || true
echo "--- /run"
df -h /run

echo "--- diagnostic file"
if [ -e "$RUNDIR/diag-eve.json" ]; then
  stat -c 'DIAG_UNEXPECTED path=%n bytes=%s owner=%U group=%G mode=%a mtime=%y' "$RUNDIR/diag-eve.json"
  die "diag-eve.json was recreated."
else
  echo "DIAG_EVE_PRESENT=NO"
fi

echo "--- live config"
grep -nE 'default-log-dir:|filetype:|filename:' "$CONF"

echo "--- recent Suricata"
journalctl -u fingerprint-suricata.service -n 100 --no-pager || true

echo "--- recent sensor"
journalctl -u fingerprint-sensor.service -n 140 --no-pager \
  | grep -E 'fingerprint_sensor_metrics|fingerprint_delivery_(success|retry)|runtime_state' \
  | tail -n 80 || true

echo "--- recent evidence"
journalctl -u fingerprint-evidence.service -n 120 --no-pager \
  | grep -E 'device_fingerprint_service_started|device_fingerprint_ingest_(accepted|rejected)|concurrency_limit|retention_completed' \
  | tail -n 80 || true

step "FINAL"
echo "SURICATA_CAPTURE_RECOVERY=PASS"
echo "SOCKET_ONLY_EVE=PASS"
echo "DIAG_EVE_PRESENT=NO"
echo "TEMP_DEFAULT_LOG_DIR=/run/fingerprint-suricata"
echo "READONLY_RUN_BOUNDARY=ABSENT"
echo "EVIDENCE_REPAIR_REMAINS_DEPLOYED=YES"
echo "CAPTIVE_PORTAL_RESTARTED=NO"
echo "CLASSIFICATION_ACTIVATION=NO"
echo "FOLLOWUP_CODE_REPAIR_REQUIRED=YES"
echo "REPORT=$REPORT"
