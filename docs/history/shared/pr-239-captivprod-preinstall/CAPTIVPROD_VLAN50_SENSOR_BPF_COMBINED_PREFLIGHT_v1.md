# CAPTIV-PROD — VLAN 50 + Sensor BPF, один интегрированный change set

**Статус:** архитектурный план принят; **READ-ONLY PREFLIGHT GO**, конфигурационные изменения **HOLD до единого scoped Owner GO**. Дата: 2026-10-16. Новый сервер `192.168.0.99`. Исходный Git baseline `7e84bc563f1b6dd3d72da66ae25849d9a7d96540`.

## 1. Неизменяемые параметры

- VLAN `50`, name `CAPTIVPROD_GUEST`; Cisco `10.50.0.1/19` (`255.255.224.0`), guest `10.50.0.0/19`.
- DHCP pool `CAPTIVPROD_GUEST_V50`, exclude `10.50.0.1–10.50.0.49`, `lease 0 0 20`, Router `10.50.0.1`, DNS/Option 6 **только** `192.168.0.1`, NTP/Option 42 **только** `192.168.0.1`.
- NAT — только additive scope `10.50.0.0 0.0.31.255` в существующий verified selector, никакого второго overload.
- New SPAN destination Catalyst `Gi1/0/45` → `captiv-prod:enp3s0`, без IP, только VLAN50 в новой свободной сессии.
- Sensor producer **и capture source**: `captivprod-sensor-01`, Site `6acbd7ed0e281b36c6c133f5`, Evidence `https://127.0.0.1:9443`, Core readiness `172.18.0.1:18089`; Suricata 8.0.7.
- Нельзя менять старые VLAN10/999, Gi1/0/48, старые monitor sessions, действующие SSID/AP/Portal и принятые NET-01/Evidence/NPM.

## 2. SysAdmin: единственный READ-ONLY preflight

### Cisco 3845, show only / no config mode

```
show version
show ip interface brief
show ip route 10.50.0.0
show ip route 10.50.0.1
show running-config | include ^interface|encapsulation dot1Q 50|10.50.0.|CAPTIVPROD_GUEST_V50
show running-config | include ^ip nat inside source|^ip nat outside|^ip nat inside|^ip dhcp excluded-address|^ip dns server
show ip dhcp pool
show ip dhcp conflict
show ip nat statistics
show access-lists
show ip route
show ntp status
show processes cpu sorted
show memory summary
```

Локально посмотреть контекст **только** действующего NAT selector/ACL/route-map, ACL на relevant LAN-интерфейсе и WAN-политику. Проверить `ip dhcp` server и синтаксис `option 42 ip ...` через IOS help без конфигурационного изменения; подтверждение Cisco DNS/NTP для гостевых клиентов. Не публиковать полные `show run`/секреты. Проверить отсутствие перекрытия guest `/19` с VPN/remote и Docker/host routes. Подтвердить фактический router parent (`Gi0/1` — кандидат, НЕ константа).

### Catalyst, show only

```
show version
show vlan id 50
show interfaces trunk
show interfaces Gi1/0/45 status
show interfaces Gi1/0/45 switchport
show monitor session all
show cdp neighbors
```

Установить фактический router trunk, один **Owner-designated НЕ production** pilot AP port, его current port mode/native management VLAN, существующую allowed VLAN list и наличие свободного нового SPAN session ID. Команда `show monitor session all` допускается только для определения занятости/ownership, **без** правки старых session. Установить поддержку `source vlan 50`, destination port `Gi1/0/45` и режима `encapsulation` на фактической модели/IOS. Если выделенной session нет и требуется правка старой — `HOLD_SPAN`.

### Linux/source, read-only

```
ip -d link show enp3s0
ip -j address show dev enp3s0
sysctl net.ipv4.conf.enp3s0.forwarding net.ipv6.conf.enp3s0.forwarding
systemctl is-active captiv-net01-firewall captiv-net01-watchdog fingerprint-evidence
systemctl is-active fingerprint-sensor fingerprint-suricata
```

Проверить `capture_filter.py`, `raw-capture.bpf`, `dhcp.py`, `tcp_syn.py`, тесты pinned commit, чистоту vendor source. **Не включать Sensor/Suricata** на старой зеркальной сети и не поднимать отсутствующий Portal. Доказать отсутствие IP/forwarding/DHCP на `enp3s0`. Если per-interface forwarding =1 — отдельная узкая установка 0 войдёт в будущий GO, без выключения global Docker forwarding.

### Краткий вывод preflight (заполнить значениями)

```
ROUTER_PARENT=
ROUTER_TRUNK=
PILOT_AP_ID_AND_OWNERSHIP=
SWITCH_PILOT_AP_PORT=
SWITCH_PILOT_AP_CURRENT_MODE_NATIVE=
VLAN50_FREE=
10.50.0.0/19_NON_OVERLAP=
NAT_STYLE=
NAT_SELECTOR_EXACT=
NAT_EXISTING_OVERLOAD_RULE=
GUEST_ACL_EXISTING_BOUNDARY=
CISCO_DNS_NTP_READY=
IOS_DHCP_OPTION42_SUPPORTED=
SPAN_AVAILABLE_SESSION_ID=
SPAN_SOURCE_VLAN50_SUPPORTED=
SPAN_DESTINATION_TAG_BEHAVIOR=
SPAN_ENP3S0_IPV4_IPV6_FORWARDING=
BPF_TEST_RUNNER_AVAILABLE=
OLD_PRODUCTION_UNTOUCHED=YES
```

## 3. Network candidate command groups — ONLY AFTER preflight + single Owner GO

**Router:** replace `[VERIFIED_ROUTER_PARENT]` with actual, never guess. Commit the exact change sheet after preflight.

```
configure terminal
ip dhcp excluded-address 10.50.0.1 10.50.0.49
ip dhcp pool CAPTIVPROD_GUEST_V50
 network 10.50.0.0 255.255.224.0
 default-router 10.50.0.1
 dns-server 192.168.0.1
 option 42 ip 192.168.0.1
 lease 0 0 20
exit
interface [VERIFIED_ROUTER_PARENT].50
 description CAPTIVPROD_GUEST_VLAN50_NEW_ONLY
 encapsulation dot1Q 50
 ip address 10.50.0.1 255.255.224.0
 ip nat inside
 no ip redirects
 no ip proxy-arp
 ! ip access-group [VERIFIED_NEW_GUEST_INGRESS_ACL] in: exact ACE/ordering only after read-only audit
 no shutdown
exit
end
```

**NAT — not executable until selector is identified.** If currently a **standard ACL** is the NAT selector, the sole new ACE will be `permit 10.50.0.0 0.0.31.255` in that exact ACL (proper sequence/deny order). If extended ACL/route-map, prepare equivalent source rule in current design. **Never add a second `ip nat inside source ... overload`.**

**Guest ACL requirement:** DHCP bootstrap to gateway; DNS UDP/TCP 53 and NTP UDP 123 to `192.168.0.1`; HTTPS TCP 443 to `192.168.0.99`; approved Internet egress; deny other RFC1918/private and router/management services including direct Core `172.18.0.1:18089`. Present *exact numbered ACE*, direction and effective existing policies after preflight. Do not guess sequencing or add permissive catch-all `permit ip any any`.

**Catalyst — only target paths.** New VLAN:

```
configure terminal
vlan 50
 name CAPTIVPROD_GUEST
exit
interface [VERIFIED_ROUTER_TRUNK]
 switchport trunk allowed vlan add 50
exit
end
```

For pilot AP port, use additive `switchport trunk allowed vlan add 50` **only if** read-only proof establishes it is a compatible trunk, with unchanged management/native VLAN. Other port modes need a different exact reviewed block; do not force an unknown production AP port to trunk. New SPAN has the target shape `monitor session [FREE_ID] source vlan 50 both` and `monitor session [FREE_ID] destination interface Gi1/0/45` **only if** verified supported and exclusively owned by new session; tag-preservation syntax is hardware-dependent. Never execute `no monitor session` against an old session.

`write memory` on either device only after all new-path acceptance PASS. Cisco/router reload is **not** part of acceptance.

## 4. BPF issue / proposed versioned contract

Pinned Git baseline:

```
RAW_CAPTURE_FILTER = "(udp and (port 67 or port 68)) or (src net 192.168.8.0/22 and tcp[tcpflags] & (tcp-syn|tcp-ack) == tcp-syn)"
```

This is **not** isolated for DHCP: it captures `0.0.0.0` from any mirrored VLAN. Replacing only `src net` will not fix that. `load_deployed_filter()` and `attach_frozen_filter()` require exact equality of the installed `.bpf` artifact to the compiled-in expression; preserve both guards unchanged.

**Proposed canonical predicate, to compile/replay with real libpcap before PR merge (not deployment approved yet):**

```
P = (udp and (port 67 or port 68) and (src host 0.0.0.0 or src net 10.50.0.0/19)) or (src net 10.50.0.0/19 and tcp[tcpflags] & (tcp-syn|tcp-ack) == tcp-syn)
```

- For **verified native/untagged-only SPAN**, filter `P`, **provided** source session is VLAN50-exclusive; otherwise HOLD. An untagged DHCP Discover from an old VLAN is indistinguishable at packet level from VLAN50 Discover; no BPF can cure an incorrect SPAN source.
- For **verified always-dot1q VLAN50 SPAN** (if actual Catalyst supports it), use `vlan 50 and (P)` and reject any untagged / other-VLAN traffic.
- For **documented mixed untagged+tagged frames**, a single tested dual-branch expression `(P) or (vlan 50 and (P))` is only a candidate; `vlan` alters libpcap offsets, so prove acceptance/rejection with compiled BPF and offline replay before committing. No blind OR/catch-all. If dual-branch semantics are not proven, HOLD until one consistent SPAN encapsulation can be selected.
- `DHCP option54` and server authority stay `10.50.0.1`; source-address-only BPF is a first-stage bounded admission, not application-level acceptance. Existing DHCP scope resolver must still confirm authoritative server and guest lease.
- Double tagging/QinQ must be rejected or proven by explicit tests; not assumed from a single `vlan 50` predicate.

**Minimal Git change:** ONLY `app/device_fingerprint_sensor/capture_filter.py` constant and `deploy/device-fingerprint/raw-capture.bpf` exact artifact, plus focused tests as necessary. No changes to `load_deployed_filter` / `attach_frozen_filter`, readiness, identity, storage, Omada behavior or legacy Site. Normalizer already parses tagged Ethernet frames.

**Tests for versioned PR (positive and negative, libpcap program and normalized output):**

1. Same exact expression in compiled constant and deployed artifact; altered deployed artifact fails closed; unsupported syntax fails compilation.
2. DHCP Discover `src 0.0.0.0`, client REQUEST, new DHCP OFFER/ACK (from authority `10.50.0.1`), renewal, VLAN50 tagged/untagged according to **actual selected** SPAN mode — admitted and normalized/authoritatively scoped.
3. Guest TCP SYN (src `10.50.0.0/19`) admitted, old `192.168.8.0/22` SYN and unrelated sources denied.
4. Tagged VLAN20, VLAN10, VLAN999 DHCP/SYN denied; any old-guest untagged traffic must be absent from verified new SPAN source (the BPF alone cannot distinguish old `0.0.0.0` untagged).
5. Tagged vs untagged libpcap offset behavior, EtherType 0x8100/0x88a8, single/double tags; packet-format mismatches fail acceptance, not bypass filter.
6. On isolated pilot, `enp3s0` packet counts show expected guest DHCP and no old VLAN traffic; Suricata EVE socket/Receiver event and unauthorized source negative test PASS.

After reviewed PR & QA, deploy only accepted merged SHA + exact matching new `.bpf`. Never hot-edit Python on production to bypass frozen validation.

## 5. One Owner GO and rollback

Issue one scoped GO only **after** SysAdmin returns the filled preflight, exact router/trunk/AP interfaces, NAT selector and ACL ACE, free independent SPAN session, and one compiled/tested BPF expression and Git PR+SHA. Scope: additive Cisco `.50`/DHCP/ACL/NAT, VLAN50/trunk/pilot path on Catalyst, independent VLAN50-only SPAN to port45, approved new Sensor/BPF revision + service runtime, combined acceptance. No old production changes, no main CaptivePortal install.

Rollback snapshots before mutation: sanitized config diff plus protected complete Cisco/Catalyst config backups, current Omada AP ownership, NET-01 verification and Sensor original Git/installed filter fingerprint. If a new guest path fails: disable **only** new pilot SSID/port VLAN50 path; remove newly introduced SPAN **by its new session ID only**; revert new Cisco ACL/NAT ACE by its **exact identity**; remove new DHCP pool, new exclusion and `.50` only if no approved dependents; remove VLAN 50 from verified trunks with `allowed vlan remove 50` (not replace old lists); revert Sensor to prior verified disabled state/approved code and filter. No global NAT or DHCP clears, no reload/forget of production AP.

**Acceptance order:** new network IP/DHCP Option 6/42 → DNS/NTP → NAT + negative guest ACL tests → pilot AP management/SSID → new isolated SPAN → DHCP Discover + SYN with BPF → real Sensor + Suricata EVE → Evidence persisted after restart → new NPM HTTPS path → old production unchanged → save configs. NPM may show 502 until main Portal is installed; do not mark Portal E2E PASS.
