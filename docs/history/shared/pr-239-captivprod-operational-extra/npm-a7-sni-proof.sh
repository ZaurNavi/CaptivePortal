#!/bin/bash
set -euo pipefail
PCAP=/tmp/npm-a7-sni-proof.pcap
rm -f "$PCAP"

sudo -n timeout -s INT 8 tcpdump -i any -nn -s0 -U -w "$PCAP" 'host 192.168.0.202 and tcp port 443' >/tmp/npm-a7-tcpdump.log 2>&1 &
cap_pid=$!
sleep 1

for h in captivportal-navi.duckdns.org navi-cloud.duckdns.org vpn-navi.duckdns.org; do
  curl -sS -o /dev/null --connect-timeout 3 --max-time 6 --resolve "$h:80:192.168.0.99" "http://$h/" || true
done

wait "$cap_pid" || true
echo "=== TCPDUMP ==="
cat /tmp/npm-a7-tcpdump.log
echo "=== PCAP PACKETS ==="
sudo -n tcpdump -nn -r "$PCAP" 2>/dev/null | wc -l
echo "=== SNI ASCII FROM PCAP ==="
sudo -n tcpdump -A -nn -r "$PCAP" 2>/dev/null | grep -Eo 'captivportal-navi[.]duckdns[.]org|navi-cloud[.]duckdns[.]org|vpn-navi[.]duckdns[.]org' | sort -u || true
rm -f /tmp/npm-a7-tcpdump.log
sudo -n rm -f "$PCAP"
