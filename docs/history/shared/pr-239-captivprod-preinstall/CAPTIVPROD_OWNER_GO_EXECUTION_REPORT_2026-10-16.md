# Captiv-Prod Owner GO — Omada / Evidence / Suricata / NPM

**Date:** 2026-10-16  
**Host:** `captiv-prod` / `192.168.0.99`  
**Scope:** current Owner GO only; old Portal/Cisco/old NPM Proxy Hosts unchanged.

## Completed / verified live

### Omada 5.14.32.3
- Controller active and `/api/info` returned `errorCode=0`.
- Verified pinned TLS leaf at `/etc/captive-portal/omada-trust/omada-leaf-pinned.pem`, SNI `Omada`, certificate verification return 0.
- Read-only DB inventory: only Site `Zefer_Parki`, ID `6acbd7ed0e281b36c6c133f5`; saved records of AP-1 EAP613, AP-2 EAP613, AP-3 EAP225, AP-4 EAP110-Outdoor; SSIDs Zefer_Parki and Welcome, Portal Zefer enabled.
- **Not OpenAPI-verified.** No new minimally privileged OpenAPI client created: approved administrative web/API authentication not available to this session. Existing clients `Repeater Scanner`, `Portal` have admin role; not reused for the new read-only audit.
- AP live/adopted state not claimed based on the database records.

### Evidence Receiver
- Existing preparation checked: OS account `captiv-evidence` (UID 996, nologin); dedicated private CA, TLS certificate `IP:127.0.0.1`, cert verified, secret files root-only 0600; independent Sensor/Portal bearer credentials generated (never output or shared).
- Receiver has **not been installed or launched**. The accepted project commit includes `app.device_fingerprint.cli` but its runtime depends on project settings, identity and other modules; no approved standalone install/package with independent identity handling was available. No fake Receiver, fake Site, or synthetic ingestion PASS claimed.
- No listener on `127.0.0.1:9443`; new databases not initialized.

### Suricata / EVE
- Added official OISF stable PPA for Jammy after verifying signing fingerprint `121504ADE276E141AD704A75AC10378CF205C960`; apt signed index update succeeded.
- Installed exact `suricata` package version `1:8.0.7-0ubuntu2`. The package service was prevented from starting during apt and is disabled/inactive.
- Production config at `/etc/captivprod-suricata/captivprod-suricata.yaml`: `enp3s0`, `HOME_NET=[10.50.0.0/19]`, `bpf-filter: net 10.50.0.0/19`, single EVE `unix_dgram` path `/run/captive-portal/fingerprint-sensor/suricata-eve.sock`. Original 192.168.8.0/22 config backed up as `suricata-pre-vlan50-backup-20261016.yaml`.
- `suricata -T` successfully loaded VLAN50 config, with an expected warning that the real Sensor Unix socket is absent.
- Prepared `fingerprint-sensor.service` and `fingerprint-suricata.service` sourced from approved commit `7e84bc563f1b6dd3d72da66ae25849d9a7d96540`; only Suricata interface, config path, and 8.0.7 version gate adapted. Both installed `disabled/inactive`. Their dependency and isolation boundaries retained. `fingerprint-eve` OS group created; `suricata` user added to group.
- **No capture started**, no old guest network captured, no fake EVE socket. The real Sensor application and event stream remain pending.

### NPM
- Before-change online SQLite backup created at `/root/npm-proxy-backup-20261016/database-before-proxyhost.sqlite` and integrity checked; existing Proxy Host count 3.
- Existing certificate NPM ID 4 verified: SAN `captivprod-navi.duckdns.org`, expiry `2027-01-12`. Existing host routing records unchanged, new host count 0.
- With temporary diagnostic backend on `172.18.0.1:18089`, direct request from NPM container succeeded and returned expected `Host` / forwarded test headers. A request from unauthorized local `nobody` UID was blocked. **Not a proxy-host end-to-end test.** Diagnostic backend service and script then stopped/removed; port 18089 no longer listening.
- NPM administration API `/api/nginx/proxy-hosts` without login returns HTTP 403. New Proxy Host was **not created**, because no authorized NPM admin session/token was available; direct SQLite mutation not attempted.
- All three old HTTPS Proxy Hosts still respond with their prior status classes (400, 302, 200 respectively).

### Safety and final verification
- `captiv-net01-firewall.service` active; watchdog active; exact NET-01 verifier: `DOCKER_IDENTITY=PASS` and `FIREWALL_FAIL_CLOSED=PASS`.
- Omada, Docker/NPM active. No sticky HOLD. No modification to Cisco, legacy production, or old Proxy Hosts. CaptivePortal not installed or started.

## Remaining concrete dependencies
1. Authorized new Omada Global Settings → Platform Integration → Open API admin session to create a **limited read-only** client and verify Site/AP online/WLAN/Hotspot through the actual OpenAPI; keep credentials locally.
2. A deployable **independent real Receiver** runtime based on approved source with its dependencies and protected systemd credentials, then actual registration for Site `6acbd7ed0e281b36c6c133f5` and durable synthetic ingestion; never substitute test harness for production.
3. Real Sensor runtime to own `/run/captive-portal/fingerprint-sensor/suricata-eve.sock`; enable Suricata only after real socket readiness. Do not activate VLAN20 capture.
4. An authenticated NPM admin session/token to **create** only `captivprod-navi.duckdns.org` forwarding to `http://172.18.0.1:18089` with certificate ID 4; then repeat full HTTPS/SNI/Host/forwarded-header tests with short-lived diagnostic backend and clean it up.

**Status:** `OMADA_API=HOLD_AUTH`, `EVIDENCE_RECEIVER=HOLD_INDEPENDENT_RUNTIME`, `SURICATA_PACKAGE_CONFIG=PASS`, `SURICATA_CAPTURE=DEFERRED_DEPENDENCIES`, `NPM_NEW_PROXY=HOLD_AUTH`, `NET01=PASS`.
