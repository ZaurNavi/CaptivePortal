# TASK-CAPTIVPROD-FULL-PREINSTALL-ARCH-05 — consolidated SysAdmin handoff

**Date:** 2026-10-15, Baku. **Role:** Captiv-Prod SysAdmin. **Execution:** live read-only inspection on `captiv-prod` and isolated offline NET01 patch/tests on owner's Windows workstation WSL. **Important:** no new Portal installed, no production NPM/Omada firewall/route/AP changes from this task. Owner gave broad action authorization in chat, but specific mutating infrastructure gates and exact objects still require scoped change authorization per Architect TASK. Do not represent documentation as runtime PASS.

## Release and preflight identity

```text
TASK=TASK-CAPTIVPROD-FULL-PREINSTALL-ARCH-05
HOST=captiv-prod
MANAGEMENT_IP=192.168.0.99/24
OS=Ubuntu_22.04.5_LTS
PYTHON=3.10.12
APPROVED_COMMIT=7e84bc563f1b6dd3d72da66ae25849d9a7d96540
APPROVED_TREE=ea664b1d49ace86fc8a0c4ab2fc52945531e574a
INSTALLATION=NOT_AUTHORIZED
HOST_UPTIME_AT_INSPECTION=1d14h
DISK_ROOT_FREE=~82GiB
DISK_BACKUP_FREE=~897GiB
CLOCK=NTP_SYNCHRONIZED_UTC
PUBLIC_IP=85.132.110.97 (DNS resolved; public ownership from Architect task)
NEW_FQDN=captivprod-navi.duckdns.org
OLD_FQDN=captivportal-navi.duckdns.org (protected)
```

## Executed commands and compact observed outputs (secrets excluded)

1. `hostnamectl`, `cat /etc/os-release`, `python3 --version`, `ip -br addr`, `ip -4 route`, `df -hT`, `free -h`, `timedatectl status`: Ubuntu 22.04.5, network `enp2s0=192.168.0.99`, `enp3s0` no L3, default route `192.168.0.1`, NTP synchronized. Root ext4 used 11/98 GiB; mounted `/srv/backups` ext4 11/916 GiB.
2. `sudo ss -lntup`, `systemctl is-active tpeap.service`, `docker ps`: new Omada `tpeap.service=active`, NPM Docker Up, `*:8043`, `*:8088` and `*:8843` Omada; new `18089`, `9443` not listening. `captive-portal.service=inactive` and install paths absent. `suricata.service=inactive`.
3. `curl -ksS https://127.0.0.1:8043/api/info`: `errorCode=0`, `controllerVer=5.14.32.3`, controller ID `68ba0bb73ec9f9f0add0a21382f1b810`. Old `.222:8043/api/info`: version 5.14.32.3, ID `fe6867ddf84e4c18c4e280e984e4266d` (read-only). The identity API does not show Site/AP permissions; these remain HOLD.
4. `docker network inspect nginx-proxy-manager_default`, `docker inspect npm`, `docker image inspect`: Bridge ID `627e7c1ca6d557e7522ed3a041f3f6173541fcf18570edd8c33da5ce82432697`, IP/MAC `172.18.0.2/b2:fa:fc:bf:d5:bc`, gateway `172.18.0.1`, NPM image and digest pinned `sha256:4393e642e233e5efd5adeb7f10918d4aaea71c9ed875b94190273fc8e87f9594`. `docker exec npm nginx -t`: PASS. Active host Proxy Hosts count 3, for **old** Portal, cloud and VPN only.
5. `getent ahostsv4 captivprod-navi.duckdns.org`: `85.132.110.97`; `curl --resolve ... https://captivprod-navi.duckdns.org/`: TLS `unrecognized name`, HTTP `000`. This proves **new** NPM HTTPS not yet served, even if some unassigned certificate exists in certificate store.
6. `ip -br link`, `networkctl status enp3s0`, `ethtool`, `ip -s link`: capture MAC `00:0a:cd:00:0c:ce`, `UP, LOWER_UP, PROMISC`, 1000/full, no IP, no master, RX ~34,718,694 packets / ~30.4 GB, drops 1,575; profile `10-captiv-span-enp3s0.network` applied. Cisco SPAN source config NOT inspected.
7. `sysctl net.ipv4.ip_forward`, `/proc/sys/net/ipv4/conf/enp3s0/forwarding`: both 1. Do NOT disable global forwarding used by Docker; require per-interface policy review.
8. `iptables -S INPUT`, `iptables -S DOCKER-USER`, `iptables -S CAPTIV_OMADA_GUARD`: Omada only initial INPUT hook, NPM admin TCP81 DOCKER-USER ACL; NET01 exact chain absent. No firewall changed.
9. `systemctl list-timers`: Omada native mirror, NPM online backup and host snapshot backup timers active. Backup disk mounted. Restore smoke of **new Portal** not possible before installation.
10. GitHub `fetch_commit` verified approved merge PR #212 commit release identity; exact `app/config.py`, `app/settings.py`, Sensor deploy configurability, `deploy/device-fingerprint/suricata.yaml` and Suricata service template reviewed. Suricata template still requires changing `enp8s0` to actual `enp3s0` under later controlled deploy override.

## NET01 focused offline work completed

Original REV4 ZIP was present in workstation Downloads, and independent Architect review (2026-10-15) marked P1: CLI flag disagreement between installer and real verifier. On an **isolated copy** of REV4 created in Windows Downloads:

- `net01-verify.py` changed so `--identity --ignore-maintenance --ignore-hold` is accepted ONLY with verified root ownership, 0600 MAINTENANCE marker and root execution. `--all --ignore-hold --ignore-maintenance` receives same constraints. Normal startup remains fail closed.
- Existing marker fixture tests tightened to mode 0600; a cross-file test calls actual verifier parser against installer's exact recovery flag combination and negative scenarios.
- Test runner: workstation WSL Ubuntu-22.04, temporary `/tmp/net01_rev41_suite`; `/tmp/net01_rev41_venv/bin/python -m pytest -q tests`; **104 passed in 11.48s**. Earlier direct run from `/mnt/c/...` produced 8 failures mostly due fixture path with spaces; corrected run from Linux `/tmp` passed. No production host CLI or packet filter was touched.
- Offline ZIP on workstation: `C:\Users\Zaur Navi\Downloads\TASK-CAPTIVPROD-NET01-IMPLEMENTATION-03_PART-A_REV4_1_OFFLINE_CLEAN.zip` (100145 bytes). Contents still require independent review; full maintenance-install shell using actual verifier under real systemd PID1, negative firewall tests and sensor-origin NET01 extension are **not yet accepted**.

## Mandatory status ledger

```text
TASK=TASK-CAPTIVPROD-FULL-PREINSTALL-ARCH-05
ARCHITECTURE_PATH_MATRIX=PREPARED_WITH_HOLDS
NPM_TO_FLASK_ROUTE=DESIGNED_NOT_ACTIVATED
NET01_FINAL_PACKAGE=HOLD_REV4_1_OFFLINE_CANDIDATE_ONLY
NET01_REAL_SYSTEMD_ACCEPTANCE=HOLD
SENSOR_TO_CORE_ROUTE=HOST_LOOPBACK_PROVEN_POLICY_DESIGN_HOLD
SENSOR_LOCAL_FIREWALL_POLICY=P1_EXACT_MATCH_REVISION_REQUIRED
SPAN_INTERFACE_IDENTITY=PASS
SPAN_PHYSICAL_PATH=LINK_AND_RX_PASS_CISCO_SCOPE_HOLD
SURICATA_EVE_PATH=DESIGNED_NOT_INSTALLED
SENSOR_TO_EVIDENCE_PATH=DESIGNED_LOOPBACK_TLS_NOT_TESTED
PORTAL_PRODUCER_TO_EVIDENCE_PATH=DESIGNED_LOOPBACK_TLS_NOT_TESTED
RECEIVER_TLS_CA_SAN=HOLD_NOT_PROVISIONED
RECEIVER_IDENTITY_POLICY=DESIGNED_NOT_REGISTERED
SOURCE_REGISTRATION_PLAN=PREPARED_ACTIVATION_HOLD
F_B1_ADMISSION_PLAN=PREPARED_ACTIVATION_HOLD
OMADA_SITE_ID=HOLD_UNVERIFIED
OMADA_OPENAPI_PATH=API_INFO_PASS_OAUTH_READONLY_HOLD
OMADA_WEBHOOK_PATH=DESIGNED_HOST_LOCAL_NPM_HTTPS_HOLD
GUEST_FQDN_TLS_PATH=DNS_A_PASS_TLS_SNI_FAIL
CAPPORT_PATH=DESIGNED_SITE_CIDR_HOLD
PILOT_AP_ISOLATION_PLAN=PREPARED_PILOT_NOT_AUTHORIZED
SYSTEMD_DEPENDENCY_GRAPH=PREPARED_REAL_PID1_HOLD
OPTIONAL_COMPONENTS_MATRIX=PREPARED_ALL_NEW_FEATURES_OFF
DATA_STORAGE_PLAN=PREPARED_NEW_WRITER_STORES_NOT_INITIALIZED
SECRET_STORAGE_PLAN=PREPARED_NO_NEW_SECRETS_WRITTEN
BACKUP_RESTORE_PLAN=PREPARED_NEW_PORTAL_RESTORE_NOT_TESTED
LOGGING_MONITORING_PLAN=PREPARED_LOG_AGENT_NOT_DEPLOYED
ROUTE_TESTS_COMPLETED=READ_ONLY_DNS_TLS_IP_ROUTE_DOCKER_ID_SPAN_LINK_OMADA_INFO
RUNTIME_ONLY_TESTS_REMAINING=NEW_FLASK_LOCAL_HTTP_CAPPORT_EVIDENCE_INGEST_SOURCE_ADMISSION_OWNER_PHONE
OPEN_ARCHITECTURE_ISSUES=NET01_LOCAL_ORIGIN,WEBHOOK_LOCAL_SNI,SURICATA_ORDER,RECEIVER_IDENTITY,SITE_AND_SPAN_SCOPE
OPEN_SECURITY_ISSUES=NEW_FQDN_TLS,NET01_LIVE_NEGATIVES,ROOT_MAINT_REINSTALL,RECEIVER_CA,CAPTURE_FORWARDING,LOG_PRIVACY
OPEN_P0=0_CONFIRMED_BY_THIS_SNAPSHOT
OPEN_P1=7_GATED_AREAS_LISTED_IN_TEST_PLAN
INFRASTRUCTURE_PREINSTALL_READY=HOLD
ARCHITECTURE_COMPLETE=HOLD
CAPTIVEPORTAL_INSTALLATION=NOT_AUTHORIZED
OWNER_GO_REQUIRED_FOR_CHANGES=YES_SCOPED_OBJECTS
OLD_PRODUCTION_UNCHANGED=YES_BY_THIS_EXECUTION
NEW_PORTAL_NOT_INSTALLED=YES
SECRETS_IN_REPORT=NO
```

## Explicit next operations requiring scoped change order

1. NET01: Architect/Coder/QA review REV4.1 offline candidate, then design extension of exact chain + verifier/installer/rollback/watchdog for Sensor local `lo` path. Run isolated real PID1 Docker/network/firewall tests. Do not change production NPM while P1 remains.
2. Cisco: authorized read-only switch evidence, exact SPAN source/destination + ingress/egress/VLAN10/999; approve passive scope and per-interface forwarding setting before capture services.
3. New Omada: credentialed read-only UI/OpenAPI actual Site/AP inventory, hotspot rights, controller cert; no tokens in report.
4. Receiver: approve loopback `127.0.0.1:9443`, SAN/CA, separate producer bearer, registration control-plane and F-B1 health/admission contract; no old credentials.
5. New FQDN: confirm cert coverage and create dedicated NPM Proxy Host **after** safe backend test under Owner scoped GO; never touch old Proxy Host.
6. SysAdmin+Architect jointly accept matrix and preinstall tests; only after full PREINSTALL PASS is separate application installation allowed. All optional modules and pilot AP remain disabled in ARCH-05.

## Deliverables in this folder

- `CAPTIVPROD_COMPLETE_NETWORK_AND_SERVICE_PATH_MATRIX.md`
- `CAPTIVPROD_SYSTEMD_DEPENDENCY_AND_STARTUP_PLAN.md`
- `CAPTIVPROD_FINGERPRINT_SPAN_SURICATA_EVIDENCE_PLAN.md`
- `CAPTIVPROD_OMADA_CAPPORT_WEBHOOK_ROUTING.md`
- `CAPTIVPROD_SOURCE_IDENTITY_AND_ADMISSION_PLAN.md`
- `CAPTIVPROD_CONFIG_STORAGE_BACKUP_MANIFEST.md`
- `CAPTIVPROD_PREINSTALL_TEST_AND_ROLLBACK_PLAN.md`
- `CAPTIVPROD_FIREWALL_DOCKER_NET01_REVIEW_BUNDLE.zip` (not executable/final, review pointer + findings)

**Decision:** `HOLD`, not partial GO for Portal installation. User's broad permission was used for read-only host inspections and offline workstation package correction/testing; production remains running as before.
