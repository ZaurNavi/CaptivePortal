# TASK-CAPTIVPROD-ARCH05-BLOCKER-CLOSURE-06 — targeted SysAdmin execution handoff

**Date:** 2026-10-15 (Asia/Baku). **Executor:** Captiv-Prod SysAdmin. **Owner instruction:** read-only surveys and offline packages allowed; production NPM/firewall/Cisco/certificates/credential provisioning/services require separate scoped GO. CaptivePortal not installed.

## What was *actually completed*

- **Cisco read-only barrier substantially closed.** Reused authorized saved SSH session to Cisco2960 at `192.168.0.6`. Two precise SPAN sessions confirmed: Session1 RSPAN source VLAN20 RX -> VLAN999 on trunk Gi1/0/48; Session2 VLAN20 RX -> Gi1/0/45 dedicated local monitoring port at 1Gb full. No VLAN10 SPAN source. `OutDiscards=1,626,415,261` cumulative on Gi1/0/48; cannot infer current loss rate without delta. Correlation of local Gi1/0/45 outbound and `enp3s0` inbound proves a strongly supported physical path, though no cable photo or peer LLDP was checked. *No Cisco configuration modified.*
- **NET01 focused offline work.** Original REV4.1 clean package on Owner Windows Downloads; it was **not transferred** as binary attachment to another conversation. REV4.2 offline extension prepared adding exact host-local Sensor ingress to existing NPM-only rule and synchronizing installer, verifier, rollback, watchdog and tests. 104 Python offline tests PASS, including mock fixture with **real verifier CLI parser**. But **real on-disk bash syntax FAIL** due Windows CRLF on modified installer and rollback; generated ZIP sha256 `5f03d474...` is **REJECTED**. An offline-only tool to repair, recheck and create a *new* ZIP is attached in this handoff, not yet executed on actual original ZIP. NET01 still HOLD.
- **Real systemd PID1 synthetic staging on Owner WSL:** successful `Type=notify` READY gate, correct dependency startup, BindsTo stop propagation, socket disappearance, failure-to-READY denial; temporary units cleaned up. **Not** actual NET01 Linux PID1/iptables acceptance.
- **Evidence TLS synthetic test:** disposable HTTPS Receiver mock listening on ephemeral `127.0.0.1` port, ECDSA private CA and server leaf with `SAN=IP:127.0.0.1`, separate disposable tokens for Sensor/Portal. TLS peer CA/SAN and wrong-identity/duplicate negative tests: **10/10 PASS**. The real Receiver, credential store, SQLite and Source/F-B1 registration have **not** been provisioned.
- **Omada:** checked new Linux controller API `5.14.32.3` and read-only unauthenticated OpenAPI denial `errorCode=-44116`; actual Site/AP/SSID/Hotspot/permissions still require credentials. New self-signed certificate SAN only `DNS:Omada`, **not** loopback IP or `.99`: verified-HTTPS backend cannot be called PASS. No Omada configuration modified.
- **NPM/webhook:** confirmed earlier three production Proxy Hosts remain existing set and new FQDN lacks TLS route; specified a host-local split-name path preserving original Host and SNI, without hairpin and without IP-only webhook authentication. **No new NPM Proxy Host created**.

## Required Architect report fields

```text
TASK=TASK-CAPTIVPROD-ARCH05-BLOCKER-CLOSURE-06

NET01_REV4_1_INDEPENDENT_REVIEW=HOLD_NOT_TRANSMITTED_FULL_BINARY
NET01_SENSOR_LOCAL_EXTENSION=REV4_2_OFFLINE_104_PASS_BUT_PACKAGED_BASH_CRLF_FAIL
NET01_PID1_STAGING=PASS_SYNTHETIC_WSL_SYSTEMD_PID1_ONLY
NET01_FIREWALL_ACCEPTANCE=HOLD_REAL_PACKET_TESTS_NOT_RUN

NEW_OMADA_SITE_ID=HOLD_UNKNOWN_UNAUTHENTICATED
NEW_OMADA_AP_INVENTORY=HOLD_NO_CREDENTIALED_READ
NEW_OMADA_OPENAPI_TLS=HOLD_SELF_SIGNED_SAN_DNS_OMADA_ONLY
NEW_OMADA_API_PERMISSIONS=HOLD_AUTH_REQUIRED_ERRORCODE_MINUS_44116

CISCO_SPAN_SCOPE=PASS_READONLY_VLAN20_RX_SESSION1_RSPAN999_SESSION2_GI1_0_45
SPAN_FORWARDING_POLICY=PLAN_READY_NOT_APPLIED_ENP3S0_FORWARDING_CURRENTLY_1
SURICATA_EVE_READINESS=SOURCE_TEMPLATE_REVIEWED_NOT_INSTALLED

RECEIVER_BIND_TLS=127.0.0.1_9443_PROPOSED_SYNTHETIC_TLS_PASS_REAL_NOT_PROVISIONED
RECEIVER_CA_SAN=IP_127.0.0.1_SYNTHETIC_10_OF_10_PASS_REAL_CA_HOLD
PRODUCER_CREDENTIALS=SEPARATE_SYNTHETIC_BEARERS_PASS_REAL_NOT_PROVISIONED
SOURCE_REGISTRATION_CONTRACT=REVIEWED_DESIGN_REAL_SITE_AND_WRITER_REQUIRED
F_B1_ADMISSION_CONTRACT=REVIEWED_DESIGN_RUNTIME_BINDING_REQUIRED

OMADA_WEBHOOK_INTERNAL_ROUTE=LOCAL_FQDN_TO_192.168.0.99_443_PROPOSED_NOT_TESTED
NEW_NPM_PROXY_HOST=NOT_CREATED_REQUIRES_NET01_AND_SCOPED_GO
NEW_FQDN_HTTPS_TEST=HOLD_SNI_UNRECOGNIZED_NAME_CURRENTLY

SYSTEMD_STARTUP_TESTS=PASS_REAL_WSL_PID1_SYNTHETIC_NOT_REAL_NET01
BACKUP_ROLLBACK_READINESS=EXISTING_TIMERS_PASS_NEW_COMPONENT_RESTORE_NOT_TESTED
PREINSTALL_PATH_MATRIX_FINAL=UPDATED_WITH_TESTED_AND_UNTESTED_GATES

OPEN_P0=0_IDENTIFIED_FROM_THIS_RUN
OPEN_P1=9_GATED_AREAS
RUNTIME_ONLY_TESTS=REAL_PORTAL_AUTH_CAPPORT_PILOT_AP_RECEIVER_WRITER_REGISTRATION_F_B1_EVENT_HEALTH

PREINSTALL_READY=HOLD
PORTAL_INSTALLATION=NOT_AUTHORIZED
OLD_PRODUCTION_UNCHANGED=YES_NO_MUTATIONS_BY_THIS_TASK
```

## Open P1 gate list (not every item is a code defect)

1. NET01 original REV4.1 binary submission to independent Architect and review closure.
2. NET01 REV4.2 package Bash line-ending defect; repackage and independent review of local-origin source boundary.
3. Actual NET01 PID1 packet-filter/Docker/watchdog/rollback integration and negative tests.
4. New Omada read-only OAuth permissions, actual Site/AP/WLAN/Hotspot identity from real Controller.
5. New Omada TLS trust/SAN and effective Portal SSL verification mechanism.
6. Cisco RSPAN999 consumer justification/large trunk OutDiscards delta and `enp3s0` forwarding hardening.
7. Real Receiver CA/leaf/credential isolation and source registration (synthetic proof is not production).
8. New independent NPM Proxy Host/FQDN certificate with spoof/privacy tests and allowed/denied network routes.
9. Omada local HTTPS webhook SNI/Host and cryptographic sender authentication (IP-only disallowed).

## Runtime-only gates (not a reason to counterfeit PREINSTALL PASS)

One Portal process runtime, actual Portal CAPPORT Site response and OAuth authorize/read-back, owner-phone guest E2E, durable receiver writer/SQLite snapshot/replay, actual Source Health and F-B1 admission, Suricata EVE socket/Sensor producer event chain after approved service installation. All gated to later tasks; initial Portal installation remains NOT_AUTHORIZED until required infrastructure PASS.

## Next immediate actions

- Owner forwards the original **full REV4.1** ZIP from Windows Downloads to the independent Architect. We cannot automatically forward binaries between different ChatGPT conversations.
- Independently repair/review new REV4.2 ZIP offline, validating *actual* Bash scripts and SHA manifest (provided offline tool), then run isolated real NET01 PID1 and firewall negative tests, NOT production.
- Provide a trusted read-only Omada OpenAPI client or separately approve credential provisioning/certificate change. Until then no Site ID or permissions can be claimed.
- Confirm need for RSPAN999 consumer and measure time-delta OutDiscards. Request scoped GO for enp3s0 forwarding change and later synthetic NPM/backend test.

**Architect acceptance request:** accept Cisco SPAN read-only evidence and synthetic feasibility tests as partial gate progress; keep production network mutations and entire PREINSTALL in HOLD until listed tests pass.
