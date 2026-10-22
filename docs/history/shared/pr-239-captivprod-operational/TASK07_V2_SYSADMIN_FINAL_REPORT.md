# SYSADMIN — TARGETED CLOSURE 07 v2: read-only and offline handoff

**Date:** 2026-10-15 (Asia/Baku). **Mode:** READ-ONLY + OFFLINE. **Production modifications:** NONE. **Portal install:** NOT AUTHORIZED. **Cisco:** already closed under corrected owner scope; NO Cisco commands issued during this continuation, legacy Cisco wholly excluded.

## Executive status

`PREINSTALL_READY=HOLD`, not PASS: new Omada does not yet offer a validated TLS identity at its IP URL for credentialed Site/AP/WLAN verification; next NET01 integrated Sensor-local allowance has not been reviewed; real PID1 tests, Evidence CA/Source Admission, and diagnostic network tests remain incomplete. Proposed route is approved; not live. The return of this handoff does not authorize deployment.

## Verified basis

- Host `captiv-prod` new Linux: `192.168.0.99`; NPM exists and is running Docker with static public ports 80,81,443 on management IP; no new Flask listener :18089 and no Evidence listener :9443.
- New Omada `5.14.32.3`, anonymous info API returns `apiVer=3` and controller `omadacId=68ba0bb73ec9f9f0add0a21382f1b810` (32-hex, **not** Site ID). OpenAPI doc probe returns 401 without credentials. Strict TLS on IP fails on self-signed cert, SAN DNS:Omada only. Token exchange and Site/AP/WLAN/OpenAPI scope were NOT attempted. Correct Site ID remains UNKNOWN.
- Accepted Git SHA/tree source scanned read-only. Sensor wait-for-Core is TCP-only; runtime/EveReceiver **creates** UNIX_DGRAM socket, then Suricata sends to it. Old template uses `enp8s0` and waits socket 1830s with unproven systemd start timeout; this must be adapted to `enp3s0` as a distinct future deployment artifact.
- Host `ip -4 route get 172.18.0.1` returns `local ... dev lo src 172.18.0.1`. Current proposed REV4.1 `INPUT` firewall allows NPM bridge only; Sensor host-local permission needs independently reviewed exact OUTPUT/INPUT solution. Original Sensor `127.0.0.1:8088` would connect to Omada, not Portal.
- `net.ipv4.conf.enp3s0.forwarding=1`; scoped 0 proposal subject to GO only, no global Docker forwarding change.
- Read-only storage: root `/` 100 GB LV on non-rotating 476.9 GB sda (`ROTA=0`), backups `sdb` HDD 931.5 GB (`ROTA=1`), 15 GiB RAM. `captiv-npm-backup-online.timer` and `captiv-backup.timer` enabled. No new Portal/Suricata/Evidence services installed.

## Artifact matrix

| Artifact | Content | Status |
|---|---|---|
| `NET01_REV4_1_FULL.zip` | Full offline candidate package, source scripts/systemd/tests, SHA256 manifest; REV4 P1 maintenance CLI fixed | 105/105 pytest OFFLINE PASS, not PID1 |
| `OMADA_NEW_SITE_API_INVENTORY_READONLY.md` | Anonymous controller identity, precise TLS blocker and credentialed verification plan | `HOLD_TLS` |
| `NET01_SENSOR_LOCAL_PATH_DESIGN.md` | Loopback route, proposed UID/OUTPUT and INPUT boundary; diagnostic backend tests | DESIGNED_NOT_APPROVED |
| `NEW_HOST_SYSTEMD_SURICATA_EVE_DEPENDENCIES.md` | Repo-based socket creator proof and new host startup graph | DESIGNED_NOT_TESTED |
| `EVIDENCE_RECEIVER_TLS_AND_SOURCE_ADMISSION_PLAN.md` | 127.0.0.1:9443, local CA, Sensor/Portal separated credentials, empty stores, F-B1 | DESIGNED_NOT_APPROVED |
| `NEW_FQDN_NPM_WEBHOOK_SNI_PLAN.md` | Separate new FQDN, cert, synthetic SNI/Host/XFF and webhook trust | DESIGNED_NOT_TESTED |
| `PREINSTALL_GATES_AND_GO_SEQUENCE.md` | Explicit Owner GO gates, storage, secrets, monitoring, rollback | PREPARED |

`REV4_1_FULL.zip` here was **reconstructed locally** from preserved REV4 SHA256 `d958d029456bcca7235ae218094c049b5e2ee6edd33ce668b463838bc9daacb9`, using the verified Windows REV4.1 correction for the real verifier CLI and equivalent tests. It is complete and newly hashed, **not bit-for-bit identical** to the Windows workstation's independently observed candidate `TASK-CAPTIVPROD-NET01-IMPLEMENTATION-03_PART-A_REV4_1_OFFLINE_CLEAN.zip` SHA256 `422f2cbc1a37535c26c934ddcd244740d6c2408940a57269350c075e4ae68ee7` (100145 bytes). The exact Windows file remains on that workstation and is available separately for independent cross-check; no binary-transfer equivalence is claimed. Our reconstructed ZIP is a different revision artifact with 105 passing tests.

## Mandatory key/value report

```text
TASK=TASK-CAPTIVPROD-ARCH06-TARGETED-CLOSURE-07_v2
MODE=READ_ONLY_AND_OFFLINE
NEW_OMADA_API_IDENTITY=ANON_API_VERSION_5.14.32.3_VERIFIED_CREDENTIALED_HOLD_TLS
NEW_OMADA_SITE_ID=UNKNOWN_24_HEX_NOT_OBTAINED
NEW_OMADA_SITE_NAME=UNKNOWN
NEW_OMADA_AP_INVENTORY=NOT_TESTED_HOLD_TLS
NEW_OMADA_OPENAPI_SCOPE=NOT_TESTED_AUTH_REQUIRED
NEW_OMADA_TLS_IDENTITY=HOLD_TLS_SELF_SIGNED_SAN_DNS_OMADA_ONLY
OMADA_ID_VS_CONTROLLER_ID_VS_SITE_ID=OMADACID_32HEX_OBSERVED_SITE_ID_UNVERIFIED
LEGACY_SYSTEMD_REFERENCE_RECONCILED=DESIGN_LEVEL_ONLY_NO_OLD_HOST_CONTACT
NEW_SURICATA_SOCKET_CREATOR=fingerprint-sensor_EveReceiver.open_UNIX_DGRAM
NEW_SURICATA_STARTUP_ORDER=CORE_READY_THEN_SENSOR_SOCKET_THEN_SURICATA_DESIGN
NEW_SYSTEMD_DEPENDENCY_GRAPH=OFFLINE_DESIGN_PID1_NOT_TESTED
REV4_REUPLOADED_DUPLICATE=YES_SHA256_D958D029456BCCA7
REV4_1_FULL_PACKAGE_ATTACHED=YES_RECONSTRUCTED_OFFLINE_CANDIDATE_NOT_WINDOWS_BYTE_COPY
NET01_REV4_1_ARCH_REVIEW=PENDING
NET01_SENSOR_LOCAL_POLICY=DESIGN_PREPARED_SEPARATE_NEXT_REVISION_REQUIRED
NET01_REAL_PID1_STAGING=NOT_TESTED
SPAN_NEW_PORT45_ONLY=PREVIOUSLY_READONLY_CONFIRMED_NO_NEW_CISCO_ACTIONS
NEW_HOST_ENP3S0_FORWARDING_DECISION=SCOPED_ZERO_PROPOSED_OWNER_GO_REQUIRED
EVIDENCE_RECEIVER_TLS_PLAN=PREPARED_HOLD_CA_SAN_SOURCE_ID
SOURCE_REGISTRATION_F_B1_PLAN=PREPARED_NOT_ADMITTED
NEW_FQDN_PROXY_SNI_PLAN=PREPARED_NO_PROXY_HOST_CREATED
RUNTIME_ONLY_TESTS=NOT_TESTED
OPEN_P0=NONE_IDENTIFIED_BY_THIS_READONLY_REVIEW
OPEN_P1=OMADA_TRUST_AND_SITE,NET01_SENSOR_LOCAL_FIREWALL,REAL_SYSTEMD_PID1,RECEIVER_CA_F_B1,CONTROLLED_DIAGNOSTIC_GATE
PREINSTALL_READY=HOLD
CAPTIVEPORTAL_INSTALL=NOT_AUTHORIZED
OLD_PRODUCTION_UNCHANGED=YES_NO_LEGACY_ACTIONS
SECRETS_IN_REPORT=NO
PART_B=NOT_AUTHORIZED
PRODUCTION_MODIFICATIONS=NONE
```

## Next decisions Architect / Owner

1. TLS identity and protected Client Credentials procedure for new Omada; Site ID/WLAN/AP/webhook GET read-only follow-up and secret rotation before go-live.
2. Independent review of full REV4.1 maintenance CLI package and complete next synchronized Sensor-local firewall revision. No partial rule changes.
3. Real isolated systemd PID1 approval and tests (startup, stop, OnFailure, fail-closed, maintenance, rollback, socket creator).
4. Owner scoped GO for diagnostic backend + firewall/network work and negative tests, then only later GO for NPM Proxy Host and Portal install.
5. Evidence Receiver private CA/SAN, empty stores and F-B1 producer/source admissions in a separate approval.

**SYSADMIN:** READ-ONLY/OFFLINE CHECKS COMPLETED TO SAFE LIMIT. PREINSTALL FINAL PASS **NOT** CLAIMED.
