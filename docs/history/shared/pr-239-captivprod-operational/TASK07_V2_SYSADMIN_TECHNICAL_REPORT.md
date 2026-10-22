# Captiv-Prod SysAdmin — TASK-07 v2 focused follow-up

**Scope:** NET01 integrated NPM + local Sensor, new Omada TLS, Suricata/EVE,
Evidence and isolated staging tests. Date: 2026-10-15. **No production changes.**

## 1. NET-01 integrated review candidate

- Baseline: previously independently reviewed, reconstructed REV4.1
  `SHA256=0bb12d269f8ae0826786c71c3ba2bb3f43ac54dc4c3c1a26500bf2d67a155687`.
- New dedicated IPv4 INPUT allow sequence: pinned NPM bridge/IP/MAC;
  then exact host-local `iif=lo,src=172.18.0.1/32,dst=172.18.0.1/32`;
  unconditional terminal TCP REJECT. No `lo ACCEPT` without conditions.
- New first IPv4 OUTPUT hook protects local destination
  `172.18.0.1:18089`; only `fingerprint-sensor` numeric non-root UID,
  `oif=lo` and exact src/dst gateway/32 allowed, then terminal REJECT.
- IPv6 INPUT first rule remains TCP18089 REJECT. Runtime watchdog still
  calls the **same exact verifier --all**, now covering both owned chains.
- Installer and rollback updated synchronously, including sensor UID fail-closed
  preflight, owned-chain exact-match rollback, MAINTENANCE and no-service/jobs/
  listener conditions. Existing NPM network identity remains unchanged.
- Old fixtures preserved, new positive and negative tests PASS **141/141**.
- Caveat: iptables owner matching, packet traversal, real systemd PID1,
  installation, rollback and negative traffic are **NOT_TESTED live**.

## 2. New Omada identity

Anonymous `GET /api/info` returned controller 5.14.32.3 / apiVer=3 and
`omadacId` (32 hex, not Site ID). Certificate remains self-signed
(CN localhost, DNS SAN Omada). Strict `https://Omada:8043/api/info`,
controlled `Omada -> 192.168.0.99`, explicitly supplied temporary leaf
trust, returned HTTP200 and curl ssl_verify_result=0. Cert fingerprint equals
prior observed `EE:07:E9:1D:2B:A9:62:81:3E:EA:10:23:E2:66:72:BC:
76:1E:21:A9:61:CF:5D:E4:6F:14:80:89:D3:BC:28:DB`.

**Caveat:** trusting a leaf retrieved from the same TLS path is not independent
identity verification. Owner must approve pinned fingerprint or new CA-issued
certificate before sending client credentials. No credentialed API requests
made; Site ID, AP count, WLAN, hotspot, external portal, webhook and scopes
are **UNKNOWN/NOT_TESTED**, not filled from legacy controller. Secure secret
placement and pre-go-live rotation required.

## 3. New host Sensor/Suricata/EVE

Read-only new host: `enp3s0` is the selected passive NIC without L3 address.
Global IPv4 forwarding=1 and enp3s0.forwarding=1; changing only per-interface
forwarding requires scoped Owner GO. Accepted Git code at
`7e84bc563f1b6dd3d72da66ae25849d9a7d96540` uses old default `enp8s0`;
new candidate unit and Suricata socket-only EVE config use `enp3s0`.

Source code proves Sensor runtime opens EVE Unix datagram socket
`/run/captive-portal/fingerprint-sensor/suricata-eve.sock` (group
`fingerprint-eve`, mode 0660). Suricata is a consumer; `Type=simple`/`After`
requires bounded positive ready check. Candidate helper checks inode,
owner/group/mode and AF_UNIX datagram connect without sending evidence.
Candidate timeout=45 sec, requires real staging timing; do not reproduce old
1830-second wait under effective 90-second start timeout. No permanent
services configured or started.

## 4. Evidence receiver

Candidate direct TLS `127.0.0.1:9443`; server certificate SAN IP:127.0.0.1,
independent CA and distinct protected Sensor vs Portal Producer bearers.
New empty receiver store/spool, new producer identities and 24-hex new Site,
source registration and F-B1 binding/clock/emitter/retention admission are
separate explicit approvals. No listener currently at :9443.

## 5. NPM and new public hostname

`captivprod-navi.duckdns.org` DNS/certificate prepared earlier, new NPM Proxy
Host **not created**. Diagnostic synthetic backend and positive/negative
network tests only after scoped GO and isolated PID1 review. Existing routes,
Omada and old production unchanged by this task.

## 6. Hardware/storage

Read-only `lsblk`: root resides on `sda` ROTA=0, `/srv/backups` on `sdb`
ROTA=1. No system-level HDD assumption for root. Plan metrics-driven
Suricata/Sensor CPU/IO budget acceptance in staging.

## Formal gates

```text
TASK=TASK-CAPTIVPROD-ARCH06-TARGETED-CLOSURE-07_v2
MODE=READ_ONLY_AND_OFFLINE
NET01_INTEGRATED_ZIP=ATTACHED
NET01_BASE_REV4_1_SHA256=0bb12d269f8ae0826786c71c3ba2bb3f43ac54dc4c3c1a26500bf2d67a155687
NET01_INTEGRATED_OFFLINE_TESTS=141_PASS
NET01_SENSOR_LOCAL_POLICY=REVIEW_CANDIDATE
NET01_REAL_KERNEL_NETWORK_TESTS=NOT_TESTED
NET01_REAL_PID1_STAGING=NOT_TESTED
OMADA_STRICT_TLS_BY_SAN=PASS_FOR_EXPLICIT_TRUSTED_LEAF
OMADA_INDEPENDENT_CERT_PIN_APPROVAL=HOLD
NEW_OMADA_SITE_ID=UNKNOWN
NEW_OMADA_AP_WLAN_INVENTORY=NOT_TESTED
NEW_OMADA_OPENAPI_PERMISSIONS=NOT_TESTED
NEW_SURICATA_SOCKET_CREATOR=SENSOR_EVE_RECEIVER
SURICATA_NEW_CONFIG=PREPARED_OFFLINE
EVIDENCE_RECEIVER_TLS_PLAN=PREPARED_OFFLINE
SOURCE_REGISTRATION_F_B1_PLAN=PREPARED_OFFLINE
NEW_FQDN_PROXY_HOST=NOT_CREATED
CISCO_ACTIONS=NONE
LEGACY_CISCO_UNTOUCHED=YES
OLD_PORTAL_AND_OMADA_UNCHANGED=YES
PRODUCTION_MODIFICATIONS=NONE
CAPTIVEPORTAL_INSTALL=NOT_AUTHORIZED
PART_B=NOT_AUTHORIZED
PREINSTALL_READY=HOLD
OWNER_GO_REQUIRED=YES
```

## Critical next gates for Architect

1. Independent review integrated firewall installer/verifier/watchdog/rollback;
   kernel-owned UID semantics proven on isolated staging.
2. Owner-approved Omada leaf fingerprint and secure access to new controller
   client credentials; then read-only authenticated Site/AP/WLAN/scopes.
3. Real PID1 staging and diagnostic backend negative tests, exact owned
   rollback and cold restart/cycle checks.
4. Site/guest scope approval, new Evidence cert/admission and unique empty
   storage identities. No legacy Cisco investigation.
