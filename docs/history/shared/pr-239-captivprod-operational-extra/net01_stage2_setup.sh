#!/bin/bash
set -euo pipefail
P=/tmp/net01-stage/src/NET01_IMPL03_PART_A
R=/usr/local/libexec/captiv-net01
NET=nginx-proxy-manager_default
ORIG=627e7c1ca6d557e7522ed3a041f3f6173541fcf18570edd8c33da5ce82432697
IMAGE=jc21/nginx-proxy-manager:2.16.0@sha256:4393e642e233e5efd5adeb7f10918d4aaea71c9ed875b94190273fc8e87f9594
test -d "$P/firewall"
test ! -e "$R"
test ! -e /run/systemd/system/captive-portal.service
test ! -e /var/lib/captiv-net01
systemctl start docker.service
docker network create --driver bridge --subnet 172.18.0.0/16 --gateway 172.18.0.1 --opt com.docker.network.bridge.name=br-627e7c1ca6d5 "$NET"
docker run -d --name npm --network "$NET" --ip 172.18.0.2 --mac-address b2:fa:fc:bf:d5:bc --entrypoint /bin/sleep "$IMAGE" 1200
NID=$(docker network inspect -f '{{.Id}}' "$NET")
install -d "$R"
cp "$P/firewall/"* "$R/"
cp '/mnt/c/Users/Zaur Navi/Downloads/net01_startupfix_staging_quiescent.py' "$R/net01-quiescent.py"
sed -i "s/$ORIG/$NID/g" "$R/net01-verify.py"
chmod 755 "$R/"*.py "$R/"*.sh
id fingerprint-sensor >/dev/null
id captivportal >/dev/null
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
echo STAGE_IDENTITY_READY
