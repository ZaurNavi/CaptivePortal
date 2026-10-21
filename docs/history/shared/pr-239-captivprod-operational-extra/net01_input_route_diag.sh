#!/bin/bash
set -euo pipefail
CHAIN=CAPTIV_FLASK_18089
GW=172.18.0.1
BR=br-627e7c1ca6d5
iptables -w -I "$CHAIN" 3 -i "$BR" -s "$GW/32" -d "$GW/32" -p tcp --dport 18089 -j ACCEPT
iptables -w -I "$CHAIN" 4 -s "$GW/32" -d "$GW/32" -p tcp --dport 18089 -j ACCEPT
set +e
runuser -u fingerprint-sensor -- nc -z -w2 172.18.0.1 18089
rc=$?
set -e
echo TEST_CONNECT_RC=$rc
iptables -w -nvL "$CHAIN"
iptables -w -D "$CHAIN" -i "$BR" -s "$GW/32" -d "$GW/32" -p tcp --dport 18089 -j ACCEPT
iptables -w -D "$CHAIN" -s "$GW/32" -d "$GW/32" -p tcp --dport 18089 -j ACCEPT
echo STAGING_DIAGNOSTIC_RULES_REMOVED
