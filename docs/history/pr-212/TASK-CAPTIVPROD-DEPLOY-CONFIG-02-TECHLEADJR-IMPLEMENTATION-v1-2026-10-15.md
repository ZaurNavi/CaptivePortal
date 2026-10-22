# CaptivPortal — TASK-CAPTIVPROD-DEPLOY-CONFIG-02-v1
## TechLeadJR implementation directive for Coder — FINAL FOR IMPLEMENTATION

**Issued:** 2026-10-15 (Asia/Baku)  
**Role:** TechLeadJR, implementation-contract owner and independent acceptance reviewer  
**Architect authority:** `CAPTIVPORTAL-DEPLOY-CONFIG-02-CHIEF-ARCHITECT-CONTRACT-v1-FINAL-2026-10-15.md`, verdict `MODIFY → APPROVE FOR TECH LEAD TASK PREPARATION`  
**Repo:** `ZaurNavi/CaptivePortal`  
**Exact verified origin/main HEAD:** `84b80376b13002d435be28eec98b91b9cbf71c63`  
**Exact verified origin/main TREE:** `fda2f2dad7c1f9c89d383ef0bef63f8aebfc93b8`  
**Known merged dependency:** PR #211, `DEPLOY-CONFIG-01`; this new task does not activate or change that deployment.  
**Implementation permission:** `CODER_LOCAL_IMPLEMENTATION_GO`, only within this TASK.  
**Publication permission:** `COMMIT/PUSH/PR=HOLD_PENDING_INDEPENDENT_QA_AND_OWNER_AUTHORIZATION`.  
**Merge:** `OWNER_ONLY`. **Production/Sensor/Portal Producer modification or activation:** `NOT_AUTHORIZED`.

## 1. Goal and boundaries

Enable **startup-only** environment-driven deployment configuration for the **existing** Network Sensor and optional Portal Evidence Producer, preserving old VM behavior when new/overriding variables are absent. Keep existing immutable models and producers; all changes are parse/validation or the one hidden interface-name preflight guard. No live reconfiguration, no producer identity switching, no schema/API, no auto-registration, no cross-site admission.

- Sensor uses `DEVICE_FINGERPRINT_SENSOR_*` namespace and stays independent of `app.settings`, `app.config`, writable Admin Settings.
- Portal Evidence Producer uses its own `DEVICE_FINGERPRINT_PORTAL_*` parser; it is optional and remains fail-soft to guest Auth.
- **New credentials, Evidence receiver registration, F-B1 source binding, SPAN/NIC/topology and future activation are separate operational and governance decisions.** Accepting a config string never constitutes admission.

This directive is for a development worktree and laboratories only. **Do not SSH to production, inspect or touch existing Sensor spool, activate workers or modify Omada/network.**

## 2. Chain-of-custody and worktree preparation

1. Coder independently fetches and checks `origin/main`, and logs **HEAD and TREE**. Both must equal the pinned IDs above before work begins. An unexpected main movement or mismatched baseline = **HOLD** and report to TechLeadJR. Do not silently rebase onto a new tree.
2. Create a separate feature branch/worktree from exact pinned main, e.g. `task/captivprod-deploy-config-02`. Do not change the owner-controlled Windows Central Lab runner, production checkout or QA worktree.
3. Preserve test source integrity and start with a clean worktree. Before handoff capture `git diff --name-only`, `git diff --check`, file hashes, dependency/runtime version, focused command/result and exact candidate TREE generated for **lab-only** verification (do not publish commit without separate GO).
4. If actual code constraints cannot be met within the closed source allowlist, stop and request amendment; no workaround by editing another module.

**Verified current test runners:** Windows Central Lab `C:\CaptivPortal-Lab\lab-test-v7-strict.cmd`, SHA256 `45d3b37150a2c3b3d3e95460b2a1c6cab8d97aa333c3d3e0cd3507ef1c994f77`; Windows canonical Python 3.10.11 / Node v24.19.0. Linux Lab (WSL Ubuntu) Python 3.10.12 at `/home/zaur_navi/captivportal-lab/test-gate-platform-01-r1-venv/bin/python`. Before official QA run, re-confirm versions, dependency set and runner hash; do not presume historic gate output applies to a new candidate.

## 3. EXACT allowed implementation files

**Closed production file allowlist — only 3:**

1. `app/device_fingerprint_sensor/config.py`
2. `app/device_fingerprint_sensor/capture.py`
3. `app/device_fingerprint_portal/config.py`

**Permitted focused tests:**

- `tests/device_fingerprint_sensor/test_config.py`
- `tests/device_fingerprint_sensor/test_runtime.py`
- `tests/device_fingerprint_sensor/test_cli.py`
- `tests/device_fingerprint_sensor/test_producer.py`
- `tests/device_fingerprint_portal/test_config.py`
- `tests/device_fingerprint_portal/test_privacy.py`
- `tests/device_fingerprint_portal/test_producer.py` (confirmed present)

New focused tests may be created **only** beneath `tests/device_fingerprint_sensor/` or `tests/device_fingerprint_portal/` for this task. Existing test names can only be refined to actual names without widening scope; never delete or weaken strict negative tests. Note that the existing `test_invalid_sensor_configuration_fails_closed` includes newly valid `enp1s0`, producer/source IDs and Site: **split/reclassify these old fixed-authority expectations as positive tests** while keeping genuinely invalid vectors negative. The existing Portal fixed-override test for `BATCH_SIZE=51` must **continue failing**.

**Permitted docs:** `.env.example`, `docs/configuration.md`, `docs/modules/device-fingerprint-portal.md`, narrowly relevant `docs/modules/device-fingerprint.md`. Document exact legacy defaults, valid custom examples with **dummy IDs and no credentials**, separation of syntactic validation vs Evidence receiver/F-B1 admissions, and restart-only effect. Avoid suggesting that a new config automatically registers or authorizes source identities.

**Forbidden:** `run.py`, `app/config.py`, `app/settings.py`, `app/device_fingerprint/{api,config,service,repository,models,schema}.py`, Sensor/Portal Producer `runtime.py`, `producer.py`, `cli.py`, `scope.py`, spool, capture filter/BPF, normalizer, source-health or binding, fingerprint classification, all Auth/Omada/CAPPORT code, all SQL/schema/migration, systemd/NPM/Docker/Suricata/NI changes. The existing test paths may be edited; forbidden **production** modules may be read and tested without modifying them.

## 4. Implementation A — Sensor parser (`app/device_fingerprint_sensor/config.py`)

**Do not change `SensorConfig` dataclass shape** or its default, enabled/disabled behavior. Preserve typed values and existing field semantics. Absent variables must reproduce the existing config exactly, including:

```text
INTERFACE=enp8s0
PRODUCER_ID=sensor-zefer-01
CAPTURE_SOURCE_ID=zefer-span-01
SITE_ID=6a64f17630da7c70d232187a
GUEST_CIDRS=192.168.8.0/22
DHCP_SERVER_AUTHORITY=192.168.10.1
DHCP_OPTION54_AUTHORITY=192.168.10.1
EVIDENCE_BASE_URL=https://192.168.0.202:9443/api/internal/device-fingerprint/v1
CA_CERT_PATH=/etc/captive-portal/device-fingerprint/sensor-ca.crt
SPOOL_PATH=/var/lib/captive-portal/fingerprint-sensor/spool.sqlite3
EVE_SOCKET_PATH=/run/captive-portal/fingerprint-sensor/suricata-eve.sock
CORE_READY_HOST=127.0.0.1
CORE_READY_PORT=8088
```

**Required formerly pinned overrides with strict validation:**

| Existing environment key | Acceptance contract |
|---|---|
| `DEVICE_FINGERPRINT_SENSOR_INTERFACE` | Linux netdevice string 1–15 ASCII bytes; permitted `[A-Za-z0-9_.-]`, **first character alphanumeric**; reject exact `lo`, `any`, wildcard, space, slash/path separator, controls, Unicode lookalikes, oversize, empty. Do not infer physical existence or route during parsing. |
| `DEVICE_FINGERPRINT_SENSOR_CORE_READY_HOST` | **Exact canonical dotted IPv4 literal**, either `127.0.0.1` or RFC1918 unicast. Reject DNS names, IPv6, other loopback, `0.0.0.0`, public/broadcast/multicast/link-local, numeric aliases or octal/hex/short forms; don't resolve names in parser. |
| `DEVICE_FINGERPRINT_SENSOR_CORE_READY_PORT` | Canonical ASCII digits for `1024..65535`, no sign, zero padding, whitespace or non-string numeric coercion. Retain typed integer model. |
| `DEVICE_FINGERPRINT_SENSOR_EVIDENCE_BASE_URL` | Strict HTTPS canonical origin + **exact** `/api/internal/device-fingerprint/v1` suffix; optional single terminal `/` may normalize, but no other path. Host is unambiguous valid DNS authority or canonical private IPv4/loopback literal; optional valid port, reject scheme downgrade, userinfo, query, fragment, percent-encoding, traversal, whitespace/control, invalid numeric alias/host. URL parse alone does **not** attest TLS trust. |
| `DEVICE_FINGERPRINT_SENSOR_SITE_ID` | Exact ASCII lowercase `[0-9a-f]{24}`; no implicit casting/uppercasing. |
| `DEVICE_FINGERPRINT_SENSOR_GUEST_CIDRS` | Canonical comma-separated **1..16** IPv4 **networks**, strict host bits, no `/0`, no empty member, no duplicates, no overlaps, no IPv6, no hidden widening. Typed result remains tuple of networks. |
| `DEVICE_FINGERPRINT_SENSOR_DHCP_SERVER_AUTHORITY` | Canonical IPv4 unicast literal; no DNS name, unspecified address, broadcast/multicast, leading zeros or noncanonical aliases. Do not add an undocumented RFC1918-only restriction; actual DHCP server evidence is a separate operational gate. |
| `DEVICE_FINGERPRINT_SENSOR_DHCP_OPTION54_AUTHORITY` | Same strict canonical IPv4 grammar, **independently configured**; it may differ from observed source authority when approved evidence supports it. |
| `DEVICE_FINGERPRINT_SENSOR_PRODUCER_ID` | Existing machine ID grammar `[a-z0-9][a-z0-9._-]{0,63}`. |
| `DEVICE_FINGERPRINT_SENSOR_CAPTURE_SOURCE_ID` | Same machine ID grammar; no aliasing or auto-claim of another source. |

Input handling: distinguish **absent** from **present but invalid**; explicit empty, leading/trailing whitespace, control/non-string and hidden normalization are negative tests. Only document-approved single terminal slash on Evidence URL may normalize. Use an existing typed model and controlled `SensorConfigError`; do not echo secrets, certificates, credential paths' contents or submitted hostile bytes. Preserve existing explicit disabled-path behavior: `SENSOR_ENABLED=false` ignores all deployment override values except currently validated Wave-2 booleans (`IO_STALE_PURGE_GATE_ENABLED`, `IO_TELEMETRY_AGGREGATION_ENABLED`, `IO_INGRESS_COALESCE_ENABLED`); invalid booleans remain errors even when Sensor disabled.

**Already configurable Sensor paths**, `CA_CERT_PATH`, `SPOOL_PATH`, `EVE_SOCKET_PATH`: preserve their original absolute-path contracts, spool budgets and socket behavior, no new inline bearer env. `CREDENTIALS_DIRECTORY` + `device-fingerprint-bearer` (systemd `LoadCredential`) remains the sole Sensor bearer source. Keep all queue, timeout, spool, dedup, EVE and Wave-2 tuning logic frozen.

## 5. Implementation B — Sensor preflight (`app/device_fingerprint_sensor/capture.py`)

Observed upstream today: `InterfacePreflight._validate()` contains `if self.interface != "enp8s0": self._fail()` while `RawCapture.open()` already binds to `self.interface`. **Remove only the fixed-name denial**. Existing syntactically valid alternate interface must pass only when it satisfies **every unchanged** runtime safety check:

- device exists in `sys_root/class/net/<selected>` and `operstate=up`;
- no master/bridge/bond, IPv4/IPv6 L3 addresses, default IPv4/IPv6 routes;
- IPv4/IPv6 forwarding off, `netplan` DHCPv4/DHCPv6 false;
- no active DHCP-client process for the selected interface and no active NetworkManager profile;
- unchanged fail-closed on missing/invalid `/sys`, `/proc`, `ip`, `netplan`, `nmcli`, errors/nonzero subprocess result;
- AF_PACKET bind continues on **selected** interface, frozen BPF/capture filter unchanged, no fallback/autopick to another NIC.

Tests must use synthetic `/sys` + `/proc` and mocked `ip`, `netplan`, `nmcli`; prove alternate clean interface passes and each unsafe property rejects. Don't require a live SPAN or raw socket on production to prove parser/preflight.

## 6. Implementation C — Portal Producer parser (`app/device_fingerprint_portal/config.py`)

Preserve isolated `PortalEvidenceConfig` dataclass and source filtering/admission (no change to runtime/producer). Default `DEVICE_FINGERPRINT_PORTAL_ENABLED=false` and all old typed defaults remain identical when absent; disabled ignores bad override values and starts no worker. Valid enabled configuration supports only:

| Existing key | Acceptance contract |
|---|---|
| `DEVICE_FINGERPRINT_PORTAL_PRODUCER_ID` | Existing `[a-z0-9][a-z0-9._-]{0,63}` machine grammar. Default `portal-zefer-01`. |
| `DEVICE_FINGERPRINT_PORTAL_CAPTURE_SOURCE_ID` | Same grammar; default `zefer-portal-http-01`, distinct from Sensor identity. |
| `DEVICE_FINGERPRINT_PORTAL_SITE_ID` | Exact ASCII lowercase `[0-9a-f]{24}`; default `6a64f17630da7c70d232187a`. |
| `DEVICE_FINGERPRINT_PORTAL_GUEST_CIDRS` | Canonical CSV 1..16 strict IPv4 networks; no `/0`, overlap/duplicate, empty/host-bits/widening; default `192.168.8.0/22`. |
| `DEVICE_FINGERPRINT_PORTAL_ALLOWED_SSIDS` | CSV 1..16 distinct **exact** SSIDs, 1..32 UTF-8 **bytes each**, case-sensitive, no NUL/control, commas, blank member or wildcard; default `Zefer_Parki`. Missing SSID in a valid session preserves **optional corroboration**, not a new auth requirement. |
| `DEVICE_FINGERPRINT_PORTAL_EVIDENCE_BASE_URL` | Exact same strict canonical direct-TLS HTTPS Evidence URL policy as Sensor; default `https://192.168.0.202:9443/api/internal/device-fingerprint/v1`. |
| `DEVICE_FINGERPRINT_PORTAL_CA_CERT_PATH` | Deployment-specific absolute Linux path; default `/etc/captive-portal/device-fingerprint/portal-ca.crt`. No inline CA bypass. |
| `DEVICE_FINGERPRINT_PORTAL_CREDENTIAL_PATH` | Deployment-specific **absolute protected external bearer file** path; default `/etc/captive-portal/device-fingerprint/portal.bearer`. Never log/read contents in configuration reporting. |

**Remain exactly pinned**: `QUEUE_MAX_EVENTS=256`, `BATCH_SIZE=50`, `QUEUE_MAX_AGE_SECONDS=300`, `COALESCE_SECONDS=21600`, `COALESCE_MAX_ENTRIES=8192`, `CONNECT_TIMEOUT_SECONDS=0.5`, `READ_TIMEOUT_SECONDS=2.0`, `TRANSIENT_COOLDOWN_SECONDS=30`, `REJECT_COOLDOWN_SECONDS=300`. Coder must not generalize other Portal Producer parameters, introduce hot-swapping or change guest Auth/Omada/CAPPORT behavior. Enabled malformed config raises controlled `PortalEvidenceConfigError` within the optional component; guest auth remains unaffected by producer delivery failures (verified separately).

## 7. Non-code invariants — strict security and provenance

**Producer admission is not configuration parsing.** The Evidence receiver must separately admit registered `(producer_id, bearer token, site_id, capture_source_id, permitted source kinds, allowed_guest_cidrs)` in `DEVICE_FINGERPRINT_PRODUCERS_JSON`. TLS peer allowlist and CA/SAN trust remain separate. Invalid token, identity, source kind, Site or IP must remain 401/403 as applicable. Do not implement a registration/mutation endpoint or fallback to another producer ID.

**F-B1/source-health/classification remains a separate downstream authority.** No creation of evidence-source binding timelines, source-health emitter contracts, clock profiles or admitted classification profile in this task. A receiver HTTP 200 is not proof of classification authorization.

**Spool safety.** Do not relabel, drain, replay, purge or reinterpret old spool events when Site/source/producer/guest scope changes. New installation requires its own empty spool. If a deployment identity changes against a nonempty spool, operations HOLD for separate lineage/cutover disposition; no automatic reset or bypass in this task.

**Direct TLS.** Keep original verified `requests.post(..., verify=<trusted CA file>)`, valid certificate SAN matching hostname/IP SAN, no `verify=False` or `trust_env` downgrade; no NPM/Core relay. Lab-only test certificates/receivers prove good/bad CA, SAN, expiry, missing or wrong bearer file.

**Core readiness.** Existing `wait_for_core()` remains raw bounded **TCP-connect only**, **not** HTTP health. Sensor uses configured Core host/port; invalid/unreachable endpoint must not start capture. Live network/host firewall policy, trusted Sensor-to-Core path and negative Guest/WAN tests belong to SysAdmin, not Coder.

**Suricata/NI.** `DEVICE_FINGERPRINT_SENSOR_INTERFACE` does **not** rewrite Suricata's interface, unit, EVE source or NI DHCP assumptions. No edits of these components. Operational source/config alignment must be accepted later.

## 8. Mandatory acceptance matrix (all gates T01–T12)

| Gate | Coder focused proof | Independent TechLeadJR / Owner lab acceptance |
|---|---|---|
| **T01 Defaults / disabled** | Exact snapshots of entire typed Sensor and Portal dataclass on absent env; disabled Sensor ignores bad deployment strings but still validates Wave-2 booleans; disabled Portal no worker. | Compare baseline snapshots and default behavior, check no other imports. |
| **T02 Sensor valid** | Custom NIC, private TCP core, strict port, Evidence URL, Site, CIDR, DHCP authorities, producer/source; typed result no socket side effects. | Validate multiple independent values and default-fallback mix. |
| **T03 Portal valid** | Custom Site, IDs, CIDRs, SSIDs, HTTPS CA/bearer paths; frozen tuning fields unchanged. | Check optional SSID and per-request filter with existing tests. |
| **T04 Reject malformed** | Parameterized negative matrix for all fields, empty/nonstring/Unicode/whitespace, URL ambiguous authorities, CIDR overlaps/host bits, bad names/ports/Site. | Independent boundary and injection review, fail-closed exceptions, no secrets. |
| **T05 Interface preflight** | Synthetic `/sys`/`/proc` + mocked `ip`/`netplan`/`nmcli`; new NIC passes; every old guard and AF_PACKET target holds. | Mandatory Linux Lab proof. |
| **T06 Core ready** | Mock `socket.create_connection` retries/timeouts; chosen host and port; no HTTP success interpretation. | Negative unreachable test; no real production capture. |
| **T07 Receiver identity** | Focused fixture/mock transport verifies propagated configured tuple, no fallback, existing receiver contract unchanged. | Cross-module **disposable** direct-TLS receiver exact-admission and denial proofs; receiver code read-only. |
| **T08 TLS/credentials** | Verify unchanged CA/credential injection, no inline bearer or `verify=False`; missing files fail safe. | Lab certificates: good CA/SAN and wrong CA/SAN/expired + missing/wrong secret, redacted logs. |
| **T09 Provenance/spool** | Events and source health retain exact configured Site/source/producer, old on-disk spool payloads not re-labeled; parser never opens spool. | Separate isolated spool scenarios and rollback/cutover HOLD checks. |
| **T10 Auth isolation** | Portal disabled/enabled invalid/delivery-failed cases do not change guest Auth, Omada, CAPPORT outcomes. | Targeted integration Auth/CAPPORT regression suite, no production mutations. |
| **T11 Regression** | Coder executes **focused Sensor/Portal tests only**, records command, counts, versions and raw logs; `compileall`. | TechLeadJR/Owner: official Linux Lab, cross-module binding/receiver and Auth/CAPPORT, full Windows V7 strict + full Linux suite under project governance. **Any strict Windows FAIL remains FAIL**; DEPLOY-CONFIG-01 exception does **not** transfer. New issue requires separately authorized task-specific Architect/Owner disposition. |
| **T12 Exact immutable candidate** | Full allowed-files diff, `git diff --check`, no secrets, no forbidden file modified; candidate patch with SHA256, exact lab artifact TREE. | Reconstruct in clean lab, verify HEAD/TREE, independent source/security QA and evidence ownership. |

**Release blocking:** no open P0/P1, all T01–T12 demonstrated, official project-gate status must be explicitly accepted. Never report `PASS` for an official gate that reports `FAIL`.

## 9. Coder deliverables and handoff

Deliver to TechLeadJR, **without commit/push/PR**, until independent evidence and Owner publication approval:

1. Proposed working branch/worktree, pinned base HEAD/TREE, Git status and exact list of touched files.
2. **Uncommitted** candidate patch with SHA256 plus tree identity for a clean lab-only reconstruction; include all changes to tests/docs. No production edits or environment changes.
3. Positive/negative test matrix T01–T10, exact focused test command/counts/results, Python/pytest versions, full traceback for any FAIL, `compileall` and `git diff --check`.
4. Explained migration of formerly negative fixed-interface/identity tests to **positive** approved behavior, preserving negative coverage. Explicit note that Portal tuning overrides still reject.
5. No credentials/keys/test private keys committed; ephemeral certificates only in isolated lab artifacts, outside Git.
6. Risk/evidence notes for T07/T08/T09/T10 requiring independent Lab proof; no claim of real source admission.
7. Suggested release PR subject (for **later**, after GO): `Deploy Config 02: configurable Device Fingerprint sensor and portal producers`.

Coder MUST HOLD on any required production-file modification beyond the 3-file allowlist, change to receiver registration API/schema, unproven disabled-path regression, runtime network exposure, inability to preserve spool provenance, unexpected main movement or any newly open P0/P1.

## 10. Next authorization state

```text
TASK=TASK-CAPTIVPROD-DEPLOY-CONFIG-02-v1
ARCHITECT_CONTRACT=FINAL_APPROVED_FOR_TECHLEAD_TASK
BASE_MAIN_HEAD=84b80376b13002d435be28eec98b91b9cbf71c63
BASE_MAIN_TREE=fda2f2dad7c1f9c89d383ef0bef63f8aebfc93b8
CODER_LOCAL_IMPLEMENTATION=GO
PRODUCTION_CODE_ALLOWLIST=3_FILES
CODER_OFFICIAL_CENTRAL_LAB_RUN=NO
INDEPENDENT_T01_T12_QA=PENDING
OFFICIAL_WINDOWS_V7_ACCEPTANCE=PENDING_NO_CARRYOVER_EXCEPTION
OWNER_COMMIT_PUSH_PR=HOLD
OWNER_MERGE=HOLD
NEW_SOURCE_RECEIVER_REGISTRATION=SEPARATE_HOLD
F_B1_SOURCE_ADMISSION=SEPARATE_HOLD
NEW_SENSOR_OR_PORTAL_ACTIVATION=HOLD
EXISTING_PRODUCTION_VM_MODIFICATION=NO
```

**TechLeadJR ruling:** This implementation task removes only hard-coded deployment pins under strict validation and the one interface-name preflight check, without changing security authority, source lineage or operations. Forward to Coder for local work. Return exact candidate and focused results for independent QA before any publication decision.
