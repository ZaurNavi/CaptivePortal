#!/bin/bash
set -euo pipefail
iptables -N CAPTIV_OMADA_GUARD 2>/dev/null || true
iptables -F CAPTIV_OMADA_GUARD
iptables -A CAPTIV_OMADA_GUARD -s 192.168.0.0/24 -p tcp -m multiport --dports 8043,8088,8843 -j RETURN
iptables -A CAPTIV_OMADA_GUARD -p tcp -m multiport --dports 8043,8088,8843 -j REJECT --reject-with tcp-reset
iptables -A CAPTIV_OMADA_GUARD -p tcp -m multiport --dports 29811:29817 -j REJECT --reject-with tcp-reset
iptables -A CAPTIV_OMADA_GUARD -p udp -m multiport --dports 29810,27001 -j DROP
iptables -A CAPTIV_OMADA_GUARD -j RETURN
iptables -C INPUT -i enp2s0 -d 192.168.0.99 -j CAPTIV_OMADA_GUARD 2>/dev/null || iptables -I INPUT 1 -i enp2s0 -d 192.168.0.99 -j CAPTIV_OMADA_GUARD
echo OMADA_MANAGEMENT_GUARD=ACTIVE
