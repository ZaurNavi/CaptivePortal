#!/bin/bash
set -euo pipefail
R=/usr/local/libexec/captiv-net01
echo INITIAL_SYSTEMD
systemctl show -p ActiveState -p SubState captive-portal.service captiv-net01-watchdog.service captiv-net01-firewall.service
echo ENTER_MAINTENANCE
if ! "$R/net01-maintenance-enter.sh";then
 echo RESET_FAILED_IN_ISOLATED_STAGING_ONLY
 systemctl reset-failed captive-portal.service captiv-net01-watchdog.service captiv-net01-firewall.service || true
 "$R/net01-quiescent.py" --mode quiescent
fi
systemctl stop captiv-net01-firewall.service
"$R/net01-fw-rollback.sh"
echo FULL_SCRIPT_ROLLBACK_PASS
"$R/net01-fw-install.sh" --maintenance-reinstall
python3 "$R/net01-verify.py" --all --ignore-maintenance --ignore-hold
echo FULL_SCRIPT_REINSTALL_EXACT_PASS
"$R/net01-clear-hold-review-only.sh"
"$R/net01-clear-maintenance-review-only.sh"
systemctl reset-failed captive-portal.service captiv-net01-watchdog.service captiv-net01-firewall.service || true
systemctl start captive-portal.service
sleep 2
systemctl is-active --quiet captive-portal.service
systemctl is-active --quiet captiv-net01-watchdog.service
python3 "$R/net01-verify.py" --all
echo RESTART_WITH_WATCHDOG_PASS
DPID=$(docker inspect -f '{{.State.Pid}}' npm)
nsenter -t "$DPID" -n python3 - <<'PY'
import socket
s=socket.socket();s.settimeout(4)
r=s.connect_ex(('172.18.0.1',18089))
s.close()
assert r==0,r
print('NPM_CONTAINER_TO_BACKEND=PASS')
PY
echo CYCLE_EXCEPT_SENSOR_NETFILTER_PASS
"$R/net01-maintenance-enter.sh"
systemctl stop captiv-net01-firewall.service
"$R/net01-fw-rollback.sh"
systemctl stop captive-portal.service captiv-net01-watchdog.service captiv-net01-failsafe.service || true
systemctl reset-failed captive-portal.service captiv-net01-watchdog.service captiv-net01-firewall.service captiv-net01-failsafe.service || true
for n in captive-portal.service captiv-net01-watchdog.service captiv-net01-firewall.service captiv-net01-failsafe.service;do rm -f /run/systemd/system/"$n";done
rm -f /run/systemd/system/captive-portal.service.d/net01.conf
rmdir /run/systemd/system/captive-portal.service.d 2>/dev/null || true
systemctl daemon-reload
docker rm -f npm
docker network rm nginx-proxy-manager_default
rm -rf "$R" /var/lib/captiv-net01
! ss -H -lnt | grep -q ':18089 '
! iptables -S | grep -q 'CAPTIV_FLASK_18089'
! iptables -S | grep -q 'CAPTIV_SENSOR_OUT_18089'
echo STAGING_CLEANUP_PASS
