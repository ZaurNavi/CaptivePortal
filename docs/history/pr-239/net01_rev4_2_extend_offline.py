from pathlib import Path
import shutil
src=Path.home()/"Downloads"/"NET01_REV4_1_WORKING"/"NET01_IMPL03_PART_A"
dst=Path.home()/"Downloads"/"NET01_REV4_2_WORKING"/"NET01_IMPL03_PART_A"
if dst.exists():raise SystemExit("STOP existing working tree")
shutil.copytree(src,dst)
def edit(f,old,new,count=1):
 p=dst/f;s=p.read_text(encoding="utf-8");actual=s.count(old)
 if actual!=count:raise RuntimeError(f"{f} expected {count} matches found {actual} {old[:65]}")
 p.write_text(s.replace(old,new),encoding="utf-8")
local_insert="""iptables -w -I "$CHAIN" 2 \
  -i lo -s 172.18.0.1/32 -d 172.18.0.1/32 \
  -p tcp --dport 18089 -m conntrack --ctstate NEW,ESTABLISHED -j ACCEPT
"""
edit("firewall/net01-fw-install.sh",
 'ip6tables -w -I INPUT 1 -p tcp --dport 18089 -j REJECT --reject-with tcp-reset',
 local_insert+'ip6tables -w -I INPUT 1 -p tcp --dport 18089 -j REJECT --reject-with tcp-reset')
local_remove="""iptables -w -D "$CHAIN" -i lo -s 172.18.0.1/32 -d 172.18.0.1/32 \
  -p tcp --dport 18089 -m conntrack --ctstate NEW,ESTABLISHED -j ACCEPT
"""
edit("firewall/net01-fw-rollback.sh",
 'iptables -w -D "$CHAIN" -j REJECT --reject-with tcp-reset',
 local_remove+'iptables -w -D "$CHAIN" -j REJECT --reject-with tcp-reset')
edit("firewall/net01-verify.py",
 "must(len(chain) == 2, 'Dedicated chain must contain EXACTLY allow + terminal REJECT')",
 "must(len(chain) == 3, 'Chain requires exact NPM + lo Sensor + terminal deny')")
edit("firewall/net01-verify.py",
 """    exact(chain[1], ['-A', CHAIN, '-j', 'REJECT', '--reject-with', 'tcp-reset'],
          'terminal catch-all IPv4 REJECT')""",
 """    exact(chain[1], ['-A', CHAIN, '-i', 'lo',
                     '-s', GATEWAY + '/32', '-d', GATEWAY + '/32',
                     '-p', 'tcp', '--dport', PORT,
                     '-m', 'conntrack', '--ctstate', 'NEW,ESTABLISHED',
                     '-j', 'ACCEPT'], 'host-local Sensor readiness allow')
    exact(chain[2], ['-A', CHAIN, '-j', 'REJECT', '--reject-with', 'tcp-reset'],
          'terminal catch-all IPv4 REJECT')""")
edit("firewall/net01-runtime-watchdog.py",
 "GUARD = ROOT / 'net01-verify.py'",
 "# REV4.2: --all guard MUST validate exact NPM+lo Sensor+REJECT chain.\nGUARD = ROOT / 'net01-verify.py'")
edit("tests/test_guard_offline.py",
 "-A CAPTIV_FLASK_18089 -j REJECT --reject-with tcp-reset\n'''",
 "-A CAPTIV_FLASK_18089 -i lo -s 172.18.0.1/32 -d 172.18.0.1/32 -p tcp -m tcp --dport 18089 -m conntrack --ctstate NEW,ESTABLISHED -j ACCEPT\n-A CAPTIV_FLASK_18089 -j REJECT --reject-with tcp-reset\n'''")
edit("tests/test_guard_offline.py",
 "cases = [\n",
 """sensorallow = '-A CAPTIV_FLASK_18089 -i lo -s 172.18.0.1/32 -d 172.18.0.1/32 -p tcp -m tcp --dport 18089 -m conntrack --ctstate NEW,ESTABLISHED -j ACCEPT'
assert CHAIN.index(baseallow) < CHAIN.index(sensorallow) < CHAIN.index('-A CAPTIV_FLASK_18089 -j REJECT')
cases = [
    dict(name='missing_sensor', chain=CHAIN.replace(sensorallow + '\\n', '')),
    dict(name='wide_source', chain=CHAIN.replace(sensorallow, sensorallow.replace(' -s 172.18.0.1/32', ' -s 172.18.0.0/16'))),
    dict(name='wrong_interface', chain=CHAIN.replace(sensorallow, sensorallow.replace(' -i lo', ' -i br-627e7c1ca6d5'))),
    dict(name='wrong_destination', chain=CHAIN.replace(sensorallow, sensorallow.replace(' -d 172.18.0.1/32', ' -d 0.0.0.0/0'))),
    dict(name='missing_conntrack', chain=CHAIN.replace(sensorallow, sensorallow.replace(' -m conntrack --ctstate NEW,ESTABLISHED', ''))),
    dict(name='duplicate_sensor', chain=CHAIN.replace(sensorallow, sensorallow + '\\n' + sensorallow)),
    dict(name='reordered_after_reject', chain=CHAIN.replace(sensorallow + '\\n', '').replace('-A CAPTIV_FLASK_18089 -j REJECT --reject-with tcp-reset', '-A CAPTIV_FLASK_18089 -j REJECT --reject-with tcp-reset\\n' + sensorallow)),
""")
for name in ("tests/test_rev3_rollback_offline.py","tests/test_rev4_negative_offline.py"):
 p=dst/name;s=p.read_text(encoding="utf-8")
 if "len(mut)==5" not in s:raise RuntimeError("test fixture mutation counts missing "+name)
 p.write_text(s.replace("len(mut)==5","len(mut)==6").replace("five_owned_mutations","six_owned_mutations"),encoding="utf-8")
(dst/"NET01_REV4_2_EXTENSION_CONTRACT.md").write_text(
 "# REV4.2 Sensor local-origin extension (offline candidate)\n"
 "Chain: NPM-only allow, exact lo host-local allow src=dst=172.18.0.1/32 TCP 18089, terminal REJECT.\n"
 "IPv6: unconditional deny. Watchdog: real verifier --all checks exact ordered 3-rule chain.\n"
 "Local-origin is not Sensor-UID-only: any local host process can connect; strict Sensor identity requires a separate accepted boundary.\n"
 "Update installer, rollback, verifier, watchdog, fixtures and six-command mutation count together.\n"
 "DO NOT INSTALL on captiv-prod until independent review and real isolated PID1 and packet-filter tests.\n",encoding="utf-8")
print("REV4_2_WORKTREE="+str(dst))
