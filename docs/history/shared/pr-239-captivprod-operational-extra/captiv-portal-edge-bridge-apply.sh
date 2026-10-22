#!/bin/bash
set -Eeuo pipefail

EXPECTED_HOST="local.domain.az"
EXPECTED_IP="192.168.0.202"
NPM_IP="192.168.0.99"
LISTEN_PORT="18088"
TARGET_ADDR="127.0.0.1:8088"
SOCKET_UNIT="/etc/systemd/system/captive-portal-edge-bridge.socket"
SERVICE_UNIT="/etc/systemd/system/captive-portal-edge-bridge.service"
FW_COMMENT="NPM_CaptivePortal_Direct_18088"
HESTIA_BIN="/usr/local/hestia/bin"
HESTIA_RULES="/usr/local/hestia/data/firewall/rules.conf"

if [[ $EUID -ne 0 ]]; then
  echo "ERROR: run with sudo/root" >&2
  exit 2
fi

[[ "$(hostname -f)" == "$EXPECTED_HOST" ]] || {
  echo "ERROR: unexpected host $(hostname -f)" >&2
  exit 3
}

ip -4 addr show | grep -Fq "$EXPECTED_IP/" || {
  echo "ERROR: expected IP $EXPECTED_IP is not configured" >&2
  exit 4
}

[[ -x /lib/systemd/systemd-socket-proxyd ]] || {
  echo "ERROR: systemd-socket-proxyd not found" >&2
  exit 5
}

ss -lnt | grep -Eq '127\.0\.0\.1:8088[[:space:]]' || {
  echo "ERROR: CaptivePortal is not listening on 127.0.0.1:8088" >&2
  exit 6
}

for f in "$SOCKET_UNIT" "$SERVICE_UNIT"; do
  if [[ -e "$f" ]]; then
    echo "ERROR: refusing to overwrite existing $f" >&2
    exit 7
  fi
done

if ss -lnt | grep -Eq "$EXPECTED_IP:$LISTEN_PORT[[:space:]]"; then
  echo "ERROR: $EXPECTED_IP:$LISTEN_PORT is already in use" >&2
  exit 8
fi

created_units=0
firewall_added=0
firewall_rule=""

rollback() {
  rc=$?
  if (( rc != 0 )); then
    echo "ERROR: bridge preparation failed; rolling back new bridge state" >&2
    systemctl disable --now captive-portal-edge-bridge.socket >/dev/null 2>&1 || true
    rm -f "$SOCKET_UNIT" "$SERVICE_UNIT"
    systemctl daemon-reload >/dev/null 2>&1 || true
    if (( firewall_added == 1 )) && [[ -n "$firewall_rule" ]]; then
      "$HESTIA_BIN/v-delete-firewall-rule" "$firewall_rule" >/dev/null 2>&1 || true
    fi
  fi
  exit "$rc"
}
trap rollback EXIT

cat >"$SOCKET_UNIT" <<EOF
[Unit]
Description=CaptivePortal private NPM edge bridge socket

[Socket]
ListenStream=$EXPECTED_IP:$LISTEN_PORT
NoDelay=true
KeepAlive=true
IPAddressAllow=$NPM_IP
IPAddressAllow=$EXPECTED_IP
IPAddressAllow=127.0.0.1
IPAddressDeny=any

[Install]
WantedBy=sockets.target
EOF

cat >"$SERVICE_UNIT" <<EOF
[Unit]
Description=CaptivePortal private NPM edge bridge
Requires=captive-portal.service
After=captive-portal.service

[Service]
User=admin
Group=admin
ExecStart=/lib/systemd/systemd-socket-proxyd $TARGET_ADDR
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true
RestrictAddressFamilies=AF_INET AF_INET6
IPAddressAllow=127.0.0.1
IPAddressAllow=$NPM_IP
IPAddressAllow=$EXPECTED_IP
IPAddressDeny=any
EOF

chmod 0644 "$SOCKET_UNIT" "$SERVICE_UNIT"
created_units=1

systemd-analyze verify "$SOCKET_UNIT" "$SERVICE_UNIT"
systemctl daemon-reload
systemctl enable --now captive-portal-edge-bridge.socket
systemctl is-active --quiet captive-portal-edge-bridge.socket

code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 5   -H 'Host: captivportal-navi.duckdns.org'   -H 'X-Forwarded-Proto: https'   -H 'X-Forwarded-Host: captivportal-navi.duckdns.org'   -H 'X-Forwarded-Port: 443'   -H 'X-Forwarded-For: 192.168.0.106'   "http://$EXPECTED_IP:$LISTEN_PORT/capport/api" || true)"

if [[ "$code" == "000" || -z "$code" ]]; then
  echo "ERROR: local bridge health request failed" >&2
  exit 9
fi

existing_line="$(grep -F "COMMENT='$FW_COMMENT'" "$HESTIA_RULES" 2>/dev/null || true)"
if [[ -n "$existing_line" ]]; then
  if [[ "$existing_line" != *"ACTION='ACCEPT'"* ||         "$existing_line" != *"PROTOCOL='TCP'"* ||         "$existing_line" != *"PORT='$LISTEN_PORT'"* ||         "$existing_line" != *"IP='$NPM_IP/32'"* ]]; then
    echo "ERROR: firewall comment exists with unexpected semantics" >&2
    exit 10
  fi
  firewall_rule="$(sed -n "s/.*RULE='\([^']*\)'.*/\1/p" <<<"$existing_line")"
else
  "$HESTIA_BIN/v-add-firewall-rule" ACCEPT "$NPM_IP/32" "$LISTEN_PORT" TCP "$FW_COMMENT"
  firewall_added=1
  existing_line="$(grep -F "COMMENT='$FW_COMMENT'" "$HESTIA_RULES")"
  firewall_rule="$(sed -n "s/.*RULE='\([^']*\)'.*/\1/p" <<<"$existing_line")"
fi

[[ -n "$firewall_rule" ]] || {
  echo "ERROR: could not resolve Hestia firewall rule ID" >&2
  exit 11
}

echo "=== BRIDGE STATE ==="
systemctl --no-pager --full status captive-portal-edge-bridge.socket | sed -n '1,16p'
ss -lntp | grep "$EXPECTED_IP:$LISTEN_PORT" || true
echo "LOCAL_BRIDGE_HTTP=$code"
echo "HESTIA_FIREWALL_RULE_ID=$firewall_rule"
echo "BRIDGE_SOURCE_ALLOW=$NPM_IP/32"
echo "BRIDGE_TARGET=$TARGET_ADDR"
echo "CAPTIVE_PORTAL_EDGE_BRIDGE=PASS"

trap - EXIT
