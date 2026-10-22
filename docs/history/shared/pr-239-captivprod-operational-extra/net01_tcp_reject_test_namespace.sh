#!/bin/bash
set -euo pipefail
BR=br-627e7c1ca6d5; IN=CAPTIV_FLASK_18089; OUT=CAPTIV_SENSOR_OUT_18089; G=172.18.0.1; NPM=172.18.0.2; MAC=b2:fa:fc:bf:d5:bc
p='';srv=''
cleanup(){ if [[ -n "$p" ]];then kill "$p" 2>/dev/null || true;fi;if [[ -n "$srv" ]];then kill "$srv" 2>/dev/null || true;fi; }
trap cleanup EXIT
ip link set lo up
ip link add "$BR" type bridge
ip link set "$BR" up
ip addr add "$G/16" dev "$BR"
ip link add hveth type veth peer name nveth
ip link set hveth master "$BR";ip link set hveth up
unshare -n sleep 80 & p=$!;sleep 0.25
ip link set nveth netns "$p"
nsenter -t "$p" -n ip link set lo up
nsenter -t "$p" -n ip link set nveth address "$MAC"
nsenter -t "$p" -n ip addr add "$NPM/16" dev nveth
nsenter -t "$p" -n ip link set nveth up
install(){
 if iptables -S "$IN" >/dev/null 2>&1;then echo ALREADY_INSTALLED;return;fi
 iptables -w -N "$IN"
 iptables -w -A "$IN" -p tcp -j REJECT --reject-with tcp-reset
 iptables -w -I INPUT 1 -p tcp --dport 18089 -j "$IN"
 iptables -w -I "$IN" 1 -i "$BR" -s "$NPM/32" -d "$G/32" -p tcp --dport 18089 -m mac --mac-source "$MAC" -m conntrack --ctstate NEW,ESTABLISHED -j ACCEPT
 iptables -w -I "$IN" 2 -i lo -s "$G/32" -d "$G/32" -p tcp --dport 18089 -m conntrack --ctstate NEW,ESTABLISHED -j ACCEPT
 iptables -w -N "$OUT"
 iptables -w -A "$OUT" -p tcp -j REJECT --reject-with tcp-reset
 iptables -w -I OUTPUT 1 -d "$G/32" -p tcp --dport 18089 -j "$OUT"
 iptables -w -I "$OUT" 1 -o lo -s "$G/32" -d "$G/32" -p tcp --dport 18089 -m owner --uid-owner 1002 -m conntrack --ctstate NEW,ESTABLISHED -j ACCEPT
 ip6tables -w -I INPUT 1 -p tcp --dport 18089 -j REJECT --reject-with tcp-reset
}
verify(){
 iptables -S INPUT | grep -Fx -- "-A INPUT -p tcp -m tcp --dport 18089 -j $IN" >/dev/null
 iptables -S OUTPUT | grep -Fx -- "-A OUTPUT -d $G/32 -p tcp -m tcp --dport 18089 -j $OUT" >/dev/null
 iptables -S "$IN" | grep -Fx -- "-A $IN -p tcp -j REJECT --reject-with tcp-reset" >/dev/null
 iptables -S "$OUT" | grep -Fx -- "-A $OUT -p tcp -j REJECT --reject-with tcp-reset" >/dev/null
 ip6tables -S INPUT | grep -Fx -- "-A INPUT -p tcp -m tcp --dport 18089 -j REJECT --reject-with tcp-reset" >/dev/null
 [[ "$(iptables -S "$IN" | grep -c '^-A ')" == 3 ]]
 [[ "$(iptables -S "$OUT" | grep -c '^-A ')" == 2 ]]
}
rollback(){
 verify || { echo ROLLBACK_HOLD;return 75; }
 iptables -w -D INPUT -p tcp --dport 18089 -j "$IN"
 iptables -w -D "$IN" -i "$BR" -s "$NPM/32" -d "$G/32" -p tcp --dport 18089 -m mac --mac-source "$MAC" -m conntrack --ctstate NEW,ESTABLISHED -j ACCEPT
 iptables -w -D "$IN" -i lo -s "$G/32" -d "$G/32" -p tcp --dport 18089 -m conntrack --ctstate NEW,ESTABLISHED -j ACCEPT
 iptables -w -D "$IN" -p tcp -j REJECT --reject-with tcp-reset
 iptables -w -X "$IN"
 iptables -w -D OUTPUT -d "$G/32" -p tcp --dport 18089 -j "$OUT"
 iptables -w -D "$OUT" -o lo -s "$G/32" -d "$G/32" -p tcp --dport 18089 -m owner --uid-owner 1002 -m conntrack --ctstate NEW,ESTABLISHED -j ACCEPT
 iptables -w -D "$OUT" -p tcp -j REJECT --reject-with tcp-reset
 iptables -w -X "$OUT"
 ip6tables -w -D INPUT -p tcp --dport 18089 -j REJECT --reject-with tcp-reset
}
install;verify;echo INSTALL_EXACT_PASS
python3 -m http.server 18089 --bind "$G" >/dev/null 2>&1 & srv=$!;sleep .5
nsenter -t "$p" -n python3 -c 'import socket;s=socket.socket();s.settimeout(3);r=s.connect_ex(("172.18.0.1",18089));s.close();assert r==0,r;print("NPM_ALLOW_PASS")'
python3 - <<'PY'
import os,socket
for uid,expected in ((1002,0),(1003,1),(0,1)):
 pid=os.fork()
 if pid==0:
  try:
   os.setgid(uid);os.setuid(uid);s=socket.socket();s.settimeout(2);r=s.connect_ex(("172.18.0.1",18089));s.close();os._exit(0 if r==0 else 1)
  except Exception:os._exit(2)
 _,status=os.waitpid(pid,0)
 actual=os.waitstatus_to_exitcode(status)
 assert actual==expected,(uid,actual)
 print("UID_"+str(uid)+("_ALLOW" if actual==0 else "_DENY")+"_PASS",flush=True)
PY
nsenter -t "$p" -n ip addr del "$NPM/16" dev nveth
nsenter -t "$p" -n ip addr add 172.18.0.3/16 dev nveth
nsenter -t "$p" -n python3 -c 'import socket;s=socket.socket();s.settimeout(2);r=s.connect_ex(("172.18.0.1",18089));s.close();assert r!=0;print("OTHER_CONTAINER_DENIED_PASS")'
nsenter -t "$p" -n ip addr del 172.18.0.3/16 dev nveth
nsenter -t "$p" -n ip addr add "$NPM/16" dev nveth
nsenter -t "$p" -n ip link set nveth address b2:fa:fc:bf:d5:bd
nsenter -t "$p" -n python3 -c 'import socket;s=socket.socket();s.settimeout(2);r=s.connect_ex(("172.18.0.1",18089));s.close();assert r!=0;print("WRONG_MAC_DENIED_PASS")'
kill "$srv";wait "$srv" 2>/dev/null || true;srv=''
install;verify;echo REINSTALL_IDEMPOTENT_PASS
iptables -I "$OUT" 2 -p tcp -j ACCEPT
if verify;then echo DRIFT_NOT_DETECTED;exit 9;fi
if rollback;then echo UNSAFE_ROLLBACK;exit 10;fi
echo DRIFT_ROLLBACK_HOLD_PASS
iptables -D "$OUT" -p tcp -j ACCEPT
verify;rollback
if iptables -S "$IN" >/dev/null 2>&1;then exit 11;fi
if iptables -S "$OUT" >/dev/null 2>&1;then exit 12;fi
echo ROLLBACK_EXACT_PASS
install;verify;rollback
echo REINSTALL_AFTER_ROLLBACK_PASS
