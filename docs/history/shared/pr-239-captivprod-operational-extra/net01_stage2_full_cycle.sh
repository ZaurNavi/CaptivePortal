#!/bin/bash
set -euo pipefail
P=/tmp/net01-stage/src/NET01_IMPL03_PART_A
R=/usr/local/libexec/captiv-net01
ORIG=627e7c1ca6d557e7522ed3a041f3f6173541fcf18570edd8c33da5ce82432697
NID=$(docker network inspect -f '{{.Id}}' nginx-proxy-manager_default)
cp "$P/firewall/"*.py "$P/firewall/"*.sh "$R/"
cp '/mnt/c/Users/Zaur Navi/Downloads/net01_startupfix_staging_quiescent.py' "$R/net01-quiescent.py"
sed -i "s/$ORIG/$NID/g" "$R/net01-verify.py"
chmod 755 "$R/"*.py "$R/"*.sh
install -d -m 0700 /var/lib/captiv-net01
for n in captiv-net01-firewall.service captiv-net01-watchdog.service captiv-net01-failsafe.service;do cp "$P/systemd/$n" "/run/systemd/system/$n";done
cat >/run/systemd/system/captive-portal.service <<'EOF'
[Unit]
Description=NET01 staging diagnostic HTTP (not CaptivePortal)
[Service]
Type=simple
User=captivportal
Group=captivportal
ExecStart=/usr/bin/python3 -m http.server 18089 --bind 172.18.0.1
Restart=no
TimeoutStopSec=4s
EOF
mkdir -p /run/systemd/system/captive-portal.service.d
cp "$P/systemd/captive-portal-net01.drop-in.conf" /run/systemd/system/captive-portal.service.d/net01.conf
systemctl daemon-reload
python3 "$R/net01-verify.py" --identity
echo PRESTART_READY
if ! systemctl start captive-portal.service;then
 echo STARTUP_HOLD
 journalctl -b --no-pager -u captiv-net01-firewall.service -u captiv-net01-watchdog.service -u captive-portal.service -n 45
 exit 75
fi
sleep 2
systemctl is-active --quiet captive-portal.service
systemctl is-active --quiet captiv-net01-watchdog.service
python3 "$R/net01-verify.py" --all
echo STARTUP_WITH_REAL_SYSTEMD_DOCKER_AND_NFT_PASS
python3 - <<'PY'
import socket
def try_user(uid,expect):
 import os
 pid=os.fork()
 if pid==0:
  os.setgid(uid);os.setuid(uid)
  s=socket.socket();s.settimeout(3)
  r=s.connect_ex(('172.18.0.1',18089));s.close()
  os._exit(0 if r==0 else 1)
 _,s=os.waitpid(pid,0);assert os.waitstatus_to_exitcode(s)==expect,(uid,s)
sensor=int(__import__('subprocess').check_output(['id','-u','fingerprint-sensor']).strip())
for uid,expected in [(sensor,0),(0,1)]:
 try_user(uid,expected)
 print('HOST_UID_TEST',uid, 'ALLOW' if expected==0 else 'DENY',flush=True)
PY
docker_pid=$(docker inspect -f '{{.State.Pid}}' npm)
nsenter -t "$docker_pid" -n python3 - <<'PY'
import socket
s=socket.socket();s.settimeout(5)
rc=s.connect_ex(('172.18.0.1',18089));s.close();assert rc==0,rc
print('REAL_NPM_CONTAINER_TO_CORE=PASS',flush=True)
PY
echo CONNECTIVITY_ACCEPTANCE_PASS
systemctl stop captiv-net01-watchdog.service
sleep 2
! systemctl is-active --quiet captive-portal.service
test -f /var/lib/captiv-net01/HOLD
! ss -H -lnt | grep -q ':18089 '
echo WATCHDOG_STOP_HOLD_LISTENER_DOWN_PASS
"$R/net01-maintenance-enter.sh"
systemctl stop captiv-net01-firewall.service
"$R/net01-fw-rollback.sh"
echo MAINTENANCE_AND_ROLLBACK_PASS
"$R/net01-fw-install.sh" --maintenance-reinstall
python3 "$R/net01-verify.py" --all --ignore-maintenance --ignore-hold
"$R/net01-clear-hold-review-only.sh"
"$R/net01-clear-maintenance-review-only.sh"
systemctl start captive-portal.service
sleep 2
systemctl is-active --quiet captive-portal.service
systemctl is-active --quiet captiv-net01-watchdog.service
python3 "$R/net01-verify.py" --all
echo RESTORE_AND_RESTART_PASS
