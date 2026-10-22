# Captiv-Prod NET-01 — Live Read-Only Preflight / Owner GO

**Date:** 2026-10-16 Asia/Baku (target observed 2026-10-15 22:24 UTC).  
**Scope:** read-only review of `captiv-prod`; NO live NET-01 installation or firewall modification.  
**Owner GO:** received for the approved scoped NET-01 integration, subject to all hard preflight gates.

## Verified target identity

| Check | Observation |
|---|---|
| Host / management | `captiv-prod` / `192.168.0.99`, Ubuntu 22.04.5 LTS |
| SSH identity | `chatgpt-admin`; `sudo -n` available |
| Root / backup free | approx. 82 GiB / 897 GiB |
| Docker / Compose | 29.1.3 / 2.40.3 |
| NPM container | `npm`, `jc21/nginx-proxy-manager:2.16.0`, running |
| Exact NPM digest | `sha256:4393e642e233e5efd5adeb7f10918d4aaea71c9ed875b94190273fc8e87f9594` |
| Docker network | `nginx-proxy-manager_default`, ID `627e7c1ca6d557e7522ed3a041f3f6173541fcf18570edd8c33da5ce82432697` |
| Bridge / gateway | `br-627e7c1ca6d5` / `172.18.0.1` |
| NPM IP/MAC / members | `172.18.0.2` / `b2:fa:fc:bf:d5:bc`; one network member |
| Listener NPM | `192.168.0.99:80,81,443` |
| Flask diagnostic | no TCP 18089 listener |
| Netfilter | `iptables v1.8.7 (nf_tables)`, INPUT/OUTPUT policy ACCEPT, preexisting `CAPTIV_OMADA_GUARD` INPUT jump; no NET01 chains |
| IPv6 | INPUT policy ACCEPT, no NET01 hook |
| NPM backup | latest observed `20261015T031035Z` with SHA256SUMS, timer active, service result success |
| Old Portal NPM TLS spot check | `SSLVERIFY=0`, HTTP 400 on bare `/` (requires Omada context; **not** an E2E health PASS) |
| New Omada | `tpeap.service` running |
| Final ZIP on authorized Windows | SHA-256 `a2904ea42f7985ec266c803d81ff76e19ce563a89f300878418668eff3599e59`, matches accepted artifact |

## Hard prerequisites not yet met

1. `getent passwd fingerprint-sensor` / `id fingerprint-sensor`: **missing**. The accepted verifier/installer requires an existing unprivileged numeric nonzero UID and must HOLD if absent. The user must not be fabricated or substituted inside the firewall implementation.
2. `captive-portal.service`: **absent by design**, since new CaptivePortal must NOT be installed. However the accepted `net01-quiescent.py` requires the app unit to have `LoadState=loaded`; real staging therefore needs an expressly scoped **temporary diagnostic stand-in** unit for the entire startup/watchdog/rollback tests (never production Portal code).
3. `/var/lib/captiv-net01` and NET01 units: **absent as expected** before first installer start; `StateDirectory=captiv-net01` must provision root:root 0700 at approved activation, the lock must remain root:root 0600 and persistent.

**Current gate:** `NET01_LIVE_PREFLIGHT=HOLD_STAGING_PREREQUISITES`; `NET01_FIREWALL_MUTATION=NONE`.

## Minimal action to close prerequisites (not yet executed)

- Approve creation of dedicated non-login OS account/group `fingerprint-sensor` on **new** `.99` only, obtain OS-assigned UID, verify it is nonzero and not a member of Docker or privileged groups; do not start Sensor.
- Approve temporary diagnostic `captive-portal.service` unit and unprivileged disposable HTTP backend that listens exclusively on `172.18.0.1:18089`, with the approved watchdog/stop dependencies, without copying/installing CaptivePortal code, and with explicit post-staging cleanup.
- Take protected before-snapshots of affected target files/rules/units, fresh NPM-aware backup prior to any network mutation, exact ZIP+manifest verification on target; install exclusively accepted runtime files with per-file modes; execute positive/negative firewall tests, drift/HOLD, maintenance and exact rollback; verify old sites and Omada preserved.
- Any unexpected identity, existing conflicting unit/UID, rollback uncertainty, failed negative test => stop diagnostic backend, HOLD and leave original NPM/old production untouched.

**No Cisco, old Omada, old Portal, AP, public NPM Proxy Host, or guest VLAN changes.**

## Status

```
OWNER_GO=RECEIVED_FOR_SCOPED_NET01
NET01_FINAL_OFFLINE_BASELINE=ACCEPTED_FROZEN
DOCKER_NPM_IDENTITY=PASS
NET01_PACKAGE_SHA256=PASS
SENSOR_SYSTEM_UID=MISSING
DIAGNOSTIC_APP_UNIT=ABSENT_BY_DESIGN
LOCK_DIRECTORY=ABSENT_EXPECTED
LIVE_FIREWALL_CHANGE=NONE
NET01_CONTROLLED_STAGING=HOLD_PREREQUISITES
OLD_PRODUCTION=UNCHANGED_BY_THIS_RUN
CAPTIVEPORTAL_INSTALL=NOT_AUTHORIZED
```
