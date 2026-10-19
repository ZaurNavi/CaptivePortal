# CAPTIVPORTAL — DEPLOY-CONFIG-02
## Chief Architect Decision & Implementation Architecture Contract v1 FINAL

**Date:** 2026-10-15 (Asia/Baku)  
**Repository:** `ZaurNavi/CaptivePortal`  
**Request:** `CAPTIVPROD-DEPLOY-CONFIG-02` — Device Fingerprint deployment configurability  
**Requested by:** Captiv-Prod Architect  
**Authority:** Chief Architect → Tech Lead implementation TASK → Coder → independent QA → Owner-controlled publication/activation  
**VERDICT:** **MODIFY → APPROVE FOR TECH LEAD TASK PREPARATION**  
**Coder authorization:** **HOLD until Tech Lead issues exact TASK**  
**Release/merge:** **HOLD pending gates and Owner authorization**  
**New-system Sensor/Portal Producer activation:** **SEPARATE HOLD pending deployment/source admission**  
**Existing production VM or Sensor modification:** **NOT AUTHORIZED**

---

## 1. Decision in brief

Approve **startup-only, backward-compatible** configurability for the two existing Device Fingerprint evidence producers:

1. **Network Sensor:** interface, private Core TCP-readiness destination, direct-TLS Evidence API base URL, Site, guest IPv4 CIDRs, DHCP authority, Producer ID and Capture Source ID.
2. **Portal Producer:** Site, guest CIDRs, allowed SSIDs, direct-TLS Evidence API base URL, Producer ID, Capture Source ID, CA file and external credential file paths.

This is **not** generic mutable settings, automatic producer registration, dynamic source identity switching, cross-site admission, Source Binding migration or automatic enablement. No additional daemon, transport, API or database schema is authorized.

**Important correction to request:** `app/device_fingerprint_sensor/capture.py` also hard-rejects `interface != 'enp8s0'` in `InterfacePreflight._validate()`. Changing only the sensor config parser would create a misleading accepted configuration that always fails preflight. This one guard must become interface-relative **without weakening any other read-only security checks**.

The principal safety distinction is:

> A syntactically accepted producer configuration does not establish that the Evidence receiver has admitted that producer, and receiver registration does not establish downstream F-B1 source-binding / classification admission. These are separate, explicitly verified operations.

### Complexity judgment

**Code:** small and localized (three production Python files).  
**Acceptance:** moderate, because identity/provenance, interface safety, HTTPS identity and cross-process isolation must be proven.  
**Operations:** staged; no approval to migrate or activate current production sources.

## 2. Evidence / reviewed code

Reviewed current repository files via GitHub on 2026-10-15:

- `app/device_fingerprint_sensor/config.py`: default constants, fixed-value guards, independent env parser and disabled behavior.
- `app/device_fingerprint_sensor/capture.py`: second hardcoded interface gate plus extensive non-L3/SPAN preflight.
- `app/device_fingerprint_sensor/cli.py`: Core readiness is **TCP connect only**, not HTTP health; no new endpoint required.
- `app/device_fingerprint_sensor/runtime.py`, `normalizer.py`, `scope.py`, `producer.py`, `spool.py`: consumers of the already typed SensorConfig; direct verified HTTPS producer; durable local transport spool.
- `app/device_fingerprint_portal/config.py`, `runtime.py`, `producer.py`: existing optional, fail-soft Portal Producer, exact pinned defaults and request-side Site/IP/SSID filtering.
- `app/device_fingerprint/config.py`, `api.py`, `service.py`: independently configured direct-TLS receiver; `DEVICE_FINGERPRINT_PRODUCERS_JSON` governs token, producer, Site, capture source, source kinds and guest scope. Ingest re-verifies exact identity/scope.
- `app/device_fingerprint/binding_contracts.py`, `source_health_emitter_contracts.py`: later evidence-source binding epochs and clock/emitter admission are distinct from receiver transport credentials.
- `deploy/device-fingerprint/fingerprint-sensor.service`: independent service, `EnvironmentFile`, `LoadCredential`, limited raw-socket capability.
- `.env.example`, `docs/configuration.md`, `docs/modules/device-fingerprint-portal.md`, relevant existing tests.

**Prior dependency:** [PR #211](https://github.com/ZaurNavi/CaptivePortal/pull/211) is merged (merge commit reported by GitHub `84b80376b13002d435be28eec98b91b9cbf71c63`; prior accepted R1 implementation tree `fda2f2dad7c1f9c89d383ef0bef63f8aebfc93b8`). This is evidence of DEPLOY-CONFIG-01 publication, **not** an assertion that the new deployment is network-ready or that this task's baseline equals that earlier tree. **Tech Lead must pin fresh exact main HEAD/TREE before issuing TASK.**

## 3. Formal architecture decisions

### D02-01 — Owner and lifetime of configuration

- Use **existing** `DEVICE_FINGERPRINT_SENSOR_*` and `DEVICE_FINGERPRINT_PORTAL_*` process-environment namespaces.
- Sensor must **not** import `app.settings`, `app.config`, or the main writable Admin Settings control plane.
- Portal Producer retains its isolated parser; no new Admin settings mutator.
- All changes take effect only when the owning service/process starts or is explicitly restarted. No hot swap and no automatic `reload` of producer identity.
- Absent variables preserve all current constants **exactly**, including the old VM's interface, Site ID, CIDR, DHCP authorities, URLs, readiness `127.0.0.1:8088`, external credential paths and flags.
- Disabled behavior stays invariant: Sensor disabled configuration ignores deployment overrides except existing explicitly validated Wave-2 boolean flags; Portal Producer disabled ignores deployment overrides and does not start a worker. Invalid enabled configuration fails appropriately in its own component; no guest-auth failure introduced by optional passive evidence.

### D02-02 — Sensor accepted deployment parameters

| Existing environment key | Legacy default | New scope / validation |
|---|---|---|
| `DEVICE_FINGERPRINT_SENSOR_INTERFACE` | `enp8s0` | Exact Linux netdevice name, 1..15 ASCII bytes; safe `[A-Za-z0-9_.-]` alphabet with alphanumeric first character; reject `lo`, `any`, wildcard/path/control/whitespace. Real interface/L2 safety remains **runtime preflight**. |
| `DEVICE_FINGERPRINT_SENSOR_CORE_READY_HOST` | `127.0.0.1` | Canonical IPv4 literal only: `127.0.0.1` or RFC1918 unicast; reject `0.0.0.0`, public, other loopback, broadcast/multicast, DNS, IPv6, whitespace, leading-zero aliases. No hidden DNS/network I/O during parsing. |
| `DEVICE_FINGERPRINT_SENSOR_CORE_READY_PORT` | `8088` | Canonical ASCII decimal integer `1024..65535`; no padding, sign or whitespace. |
| `DEVICE_FINGERPRINT_SENSOR_EVIDENCE_BASE_URL` | `https://192.168.0.202:9443/api/internal/device-fingerprint/v1` | Strict, canonical HTTPS base URL for the **exact existing** direct-TLS API prefix. Host may be a valid verified DNS authority or private IPv4/loopback literal with matching certificate SAN. Optional valid port; reject userinfo, fragment, query, ambiguous path, redirects-as-configuration, control chars, URL escaping ambiguity, wildcard/unspecified host. See §5. |
| `DEVICE_FINGERPRINT_SENSOR_SITE_ID` | `6a64f17630da7c70d232187a` | Exact `[0-9a-f]{24}`; no coercion; must match separately admitted receiver registration. |
| `DEVICE_FINGERPRINT_SENSOR_GUEST_CIDRS` | `192.168.8.0/22` | CSV of 1..16 strict, canonical IPv4 network CIDRs; no `/0`, duplicate, overlap, host bits, blank member or implicit broadening. Scope remains an allowlist, not packet-filter bypass. |
| `DEVICE_FINGERPRINT_SENSOR_DHCP_SERVER_AUTHORITY` | `192.168.10.1` | Canonical IPv4 unicast authority; must be verified from real DHCP ACK source; not inferred from router/portal host. |
| `DEVICE_FINGERPRINT_SENSOR_DHCP_OPTION54_AUTHORITY` | `192.168.10.1` | Same canonical IPv4 grammar, independently configured; may legitimately differ from packet source but requires actual evidence. |
| `DEVICE_FINGERPRINT_SENSOR_PRODUCER_ID` | `sensor-zefer-01` | Existing strict machine-ID grammar `[a-z0-9][a-z0-9._-]{0,63}`, plus distinct receiver registration; no silent alias. |
| `DEVICE_FINGERPRINT_SENSOR_CAPTURE_SOURCE_ID` | `zefer-span-01` | Same existing machine-ID grammar; exact source identity and producer/source admission required; no reuse across unrelated physical captures. |

`DEVICE_FINGERPRINT_SENSOR_CA_CERT_PATH` and `SPOOL_PATH` are **already configurable** as absolute paths and must stay so; do not invent new secret-valued environment variables. The Bearer credential remains delivered via `CREDENTIALS_DIRECTORY` / systemd `LoadCredential=device-fingerprint-bearer` and cannot be included in Git or logs. Preserve existing socket path, spool durability and all resource limits.

**Interface preflight contract:** remove *only* the exact-name check inside `InterfacePreflight._validate()`; continue to require the selected interface is `up`, has no master, no IPv4/IPv6 L3 address, no default route, forwarding disabled for IPv4/IPv6, DHCP disabled, no active DHCP client/NetworkManager profile; preserve AF_PACKET binding to the selected interface, frozen BPF filter and preflight fail-closed behavior. Do not auto-pick `eth0`, first NIC, default route or a network bridge.

### D02-03 — Portal Producer accepted deployment parameters

| Existing environment key | Legacy default | New scope / validation |
|---|---|---|
| `DEVICE_FINGERPRINT_PORTAL_PRODUCER_ID` | `portal-zefer-01` | Same existing machine-ID grammar and receiver registration requirement. |
| `DEVICE_FINGERPRINT_PORTAL_CAPTURE_SOURCE_ID` | `zefer-portal-http-01` | Same machine-ID grammar, separate from Sensor capture source. |
| `DEVICE_FINGERPRINT_PORTAL_SITE_ID` | `6a64f17630da7c70d232187a` | Exact `[0-9a-f]{24}`; must equal the intended authenticated Omada Site for admitted requests. |
| `DEVICE_FINGERPRINT_PORTAL_GUEST_CIDRS` | `192.168.8.0/22` | CSV 1..16 strict canonical CIDRs, nonempty/unique/nonoverlapping, no `/0`; preserve per-request source IP membership (IPv4 and IPv6 only where represented by explicitly admitted scope). |
| `DEVICE_FINGERPRINT_PORTAL_ALLOWED_SSIDS` | `Zefer_Parki` | CSV 1..16 distinct nonempty exact SSIDs; 1..32 UTF-8 bytes each; no NUL/control, commas or implicit wildcard; case-sensitive comparison unchanged. A missing session SSID retains existing semantics (SSID is optional corroboration, not a new auth requirement). |
| `DEVICE_FINGERPRINT_PORTAL_EVIDENCE_BASE_URL` | `https://192.168.0.202:9443/api/internal/device-fingerprint/v1` | Identical strict direct-TLS base URL contract as Sensor (§5). |
| `DEVICE_FINGERPRINT_PORTAL_CA_CERT_PATH` | `/etc/captive-portal/device-fingerprint/portal-ca.crt` | Already a path setting, now permit deployment-specific **absolute** CA path; runtime trusted CA verification unchanged. |
| `DEVICE_FINGERPRINT_PORTAL_CREDENTIAL_PATH` | `/etc/captive-portal/device-fingerprint/portal.bearer` | Already a path setting, now permit deployment-specific **absolute** external bearer file; do not add inline token env or log content. |

Existing bounds and semantics for queue, coalescer, batch, timeouts, cooldowns are **frozen**; the current parser deliberately pins them. This TASK does **not** turn all Portal Producer fields into a generic configurability framework. `DEVICE_FINGERPRINT_PORTAL_ENABLED=false` remains the default.

### D02-04 — Identity cannot be made self-authorizing

1. Producer and capture-source names in environment are **claims**, not authority. A verified `DEVICE_FINGERPRINT_PRODUCERS_JSON` record at the destination Evidence receiver must admit exactly that `producer_id`, its **unique** Bearer token, `site_id`, `capture_source_id`, permitted source kinds and `allowed_guest_cidrs`.
2. Evidence receiver's existing direct-peer network allowlist and certificate/key configuration remain a separate deployment responsibility. Producer/source/token uniqueness in the receiver must not be weakened. Wrong IDs, wrong token, Site, capture source, source kind or observed client scope must continue to fail **403/401 as applicable**; no retry-as-another-identity.
3. New clean deployment: create **new credentials and new receiver registration** by separately approved operational procedure *before* enabling delivery; never reuse old credentials or implicitly point a new producer at the old receiver.
4. Existing durable Sensor spool holds per-event provenance. **Do not change Producer/Site/Capture Source or guest scope against an existing nonempty spool.** New deployment starts with its own empty spool. Any later identity/scope change requires an explicit source cutover, drain/archive decision and lineage review; no silent relabel, replay or purge in this TASK.
5. Downstream F-B1 EvidenceSourceBindingTimeline, SourceHealthEmitterContract, BindingClockPolicy and admitted runtime profile are **distinct** authority. Enabling the new consumer/classifier under new identity is HOLD until the appropriate Site/origin/source-kind producer epoch, clock domain and emitter contract have been admitted for the target deployment. Config parser success or receiver `HTTP 200` does **not** create such bindings.
6. Do not create an automatic registration or mutation API, write source-binding records, change fingerprint SQLite schemas, promote classification profile or re-label old evidence in this TASK.

### D02-05 — Core readiness: topology-dependent deployment gate

`wait_for_core()` is presently a **raw TCP-connect** to `core_ready_host:core_ready_port`. It proves socket reachability only, not Flask business health, reverse proxy correctness, CAPPORT or Omada readiness. Keep the same code and semantics; no HTTP health request and no new relay/service/process.

On Captiv-Prod, `HOST=172.18.0.1`, `PORT=18089` is the planned Flask bind. The Sensor, which runs as a **host systemd service**, must use an actually reachable destination and must pass the target firewall policy. A Docker-only NPM allow rule may **block the host Sensor**, even though the address parses successfully.

**Approved topology choices are deployment-only:**
- explicitly allow this *local trusted Sensor process* to make a narrowly constrained host-origin TCP connection to the Flask bind, while continuing to deny Guest/WAN/other LAN and unapproved containers; **or**
- provide an already-approved local interface/path which reaches the same real core listener without exposing a new public ingress.

Do **not** point readiness at the NPM HTTPS listener merely because it accepts TCP: that could yield a false positive when Core is down. Do not claim `127.0.0.1:8088` is available on the new host. If network isolation cannot accommodate a proven local core path, **Sensor activation remains HOLD**. SysAdmin supplies route, firewall/cgroup policy and positive/negative socket evidence, not Coder changes.

### D02-06 — Direct TLS / credential trust

- Both producers continue `requests.post(..., verify=<trusted CA file>)`; no `verify=False`, insecure `http://`, disabling hostname checking, `trust_env` downgrade or accepting certificates by address alone.
- Endpoint URL is **scheme + canonical hostname/IP + optional valid port + exactly `/api/internal/device-fingerprint/v1`** (optionally normalize a *single* terminal slash). Reject query, fragment, userinfo, path extensions, traversal, percent encoding ambiguity, invalid ports/hostnames and unsafe whitespace/control bytes; do not silently switch scheme or receiver.
- Certificate must actually cover the configured endpoint authority (DNS SAN/IP SAN) and chain to the separately provisioned trusted CA; parser alone cannot prove it. Test valid CA, wrong CA, wrong SAN, expired cert, no credential, wrong credential with lab-only receiver.
- For Sensor, systemd `LoadCredential` remains the sole defined bearer ingress. For Portal Producer, an absolute protected credential file path remains the sole credential ingress. No copy of old private keys. Credentials never appear in log events, diagnostics, test output or `.env.example`.
- Evidence traffic is the direct-TLS Task-01 service, **not** the NPM/Core Flask ingress. No NPM routing dependency is introduced for Evidence.

### D02-07 — Suricata / Network Intelligence boundary

Sensor raw capture selects `config.interface`, but the current deployment templates for **Suricata** also contain the old interface name. Changing Sensor's name **does not change Suricata**, its unit, EVE socket path, NI source binding, NI-02A DHCP authority, or downstream coverage. These are separate SysAdmin/source-admission checks. This TASK must not silently edit `deploy/device-fingerprint/suricata.yaml`, `fingerprint-suricata.service`, NI readers or their schema.

## 4. Exact allowed file scope

**Production implementation (closed allowlist, three files):**

- `app/device_fingerprint_sensor/config.py`
- `app/device_fingerprint_sensor/capture.py`
- `app/device_fingerprint_portal/config.py`

**Focused tests (changes permitted as needed; no removal of strict negative coverage):**

- `tests/device_fingerprint_sensor/test_config.py`
- `tests/device_fingerprint_sensor/test_runtime.py`
- `tests/device_fingerprint_sensor/test_cli.py`
- `tests/device_fingerprint_sensor/test_producer.py`
- `tests/device_fingerprint_portal/test_config.py`
- `tests/device_fingerprint_portal/test_privacy.py`
- `tests/device_fingerprint_portal/test_producer.py` (only if existing)

**Documentation:**

- `.env.example`
- `docs/configuration.md`
- `docs/modules/device-fingerprint-portal.md`
- `docs/modules/device-fingerprint.md` (only narrowly relevant deployment note)

**Prohibited production changes:** `run.py`, `app/config.py`, `app/settings.py`, `app/device_fingerprint/{api,config,service,repository,models,schema}.py`, Sensor/Portal Producer networking implementations, Sensor spool, capture filter, normalizer, scope, source-health, fingerprint classification/binding/control plane, auth/CAPPORT/Omada, all database schemas/migrations, systemd units, Suricata and NI. Any necessary exception is a fresh Architect review, not Coder discretion.

**Tech Lead may refine only test-file names to match actually existing repository files, with a recorded no-scope-expansion justification.** New tests can be added strictly within the two producer test directories without broadening production scope.

## 5. Acceptance matrix — mandatory before accepted candidate

| Gate | Proof required |
|---|---|
| T01 Default compatibility | Every legacy typed Sensor and Portal config field equals unchanged defaults with absent keys. Production-facing disabled paths remain no-op / fail-soft. Wave-2 invalid booleans still reject as before. |
| T02 Valid Sensor deployment | New interface, private Core destination, valid port, CA path, Evidence HTTPS URL, producer/source/site, CIDRs and DHCP authorities parse to the existing immutable model without import of `app.settings`. No new socket during parse. |
| T03 Valid Portal deployment | Independently configured Site, Producer ID, Capture Source ID, CIDRs/SSIDs, HTTPS origin and CA/credential file paths; existing worker admission and optional corroborating SSID semantics. |
| T04 Strict invalid config | Empty/whitespace/Unicode spoofing/length/malformed IDs; invalid 24-hex Site; wildcard/loopback/public Core host; invalid ports; CIDR host-bit/widening/overlap/duplicates; unsafe interface names; empty/duplicate SSIDs; wrong Evidence URL authority/scheme/path/query/userinfo/fragment. Controlled fail-closed on enabled path. |
| T05 Actual interface preflight | Synthetic `/sys`/`/proc` + `ip/netplan/nmcli` for a valid alternative interface; retains **all** existing L2 safety denials. Different interface does not become an exception to forbidden L3 address, DHCP, route, master, forwarding or active NetworkManager profile. Frozen BPF unchanged. |
| T06 Core readiness | Same bounded `socket.create_connection` retry/timeout contract with configured host/port; invalid/unreachable destination rejects before capture; test does not treat TCP reachability as HTTP health. |
| T07 Producer↔receiver identity | Disposable direct-TLS receiver with exact registered tuple; accepted new Site/source/kinds/guest CIDR returns expected ingest result, wrong token/Site/source/kind/peer rejected; no alternate identity fallback. Credentials not printed. |
| T08 TLS security | Verified CA and matching SAN success; wrong CA/SAN, expired certificate, missing/unreadable credential fail safe; original `verify=<CA file>` preserved. Lab-only certificates. |
| T09 Provenance / spool | Sensor emitted evidence and source health carry exactly configured Site/source; persistent spool remains separate; new identity on nonempty old spool is an operational HOLD and never relabels existing event payloads. |
| T10 Portal auth isolation | When portal evidence configuration/delivery fails, guest Auth, Omada, CAPPORT and login responses unchanged; no worker when disabled. Source Site/IP/SSID filtering does not broaden. |
| T11 Regression / build | Focused Sensor/Portal producer suite, binding/receiver security tests, Linux Lab (required for AF_PACKET/netplan), independent QA, relevant Auth/CAPPORT regression and official project release gates. Failed Windows-only baseline issues are **not** silently waived by precedent from DEPLOY-CONFIG-01. |
| T12 Exact artifact | Git `HEAD`/`TREE`, clean worktree, allowed-files diff, no secrets, `diff --check`, independent review and chain-of-custody. |

**Live infrastructure checks are separate and required for later activation, not to implement parser code:** actual SPAN interface & Suricata NIC/EVE setup, host Sensor→Core TCP path with negative Guest/LAN/WAN tests, certificate/SAN/CA permissions, receiver allowlist and new token mapping, new empty spool, F-B1 lineage/admission if classifier enabled. No production-side invasive tests in this TASK.

## 6. Publication and rollout gates

1. **Tech Lead:** pin fresh exact `main` HEAD/TREE; issue unambiguous `TASK-CAPTIVPROD-DEPLOY-CONFIG-02-v1` within §4, and confirm test runner versions. May split into two reviewable commits (Sensor and Portal) under one PR if history stays auditable.
2. **Coder:** feature branch, only allowed code/docs/tests. Local focused proof; no access to production host, receiver credentials, secrets or current Sensor spool; no self-merge or production activation.
3. **Independent QA:** security, strict defaults, negative parsing, interface preflight, producer/receiver identity and auth isolation; official Lab release gate remains authoritative unless an explicit, new and task-specific Owner-approved exception is issued.
4. **Owner:** separately authorizes Git publication/PR/merge after mandatory gate PASS; accepted SHA/TREE returned to Captiv-Prod.
5. **Captiv-Prod SysAdmin:** provisions new Sensor environment and identity registration, TLS/credentials, network/SPAN path. **Enable remains HOLD** until all topology and provenance gates pass. No old production VM stop/restart/modification.
6. **Source Governance Owner:** separately admits new F-B1/source-health/clock binding and runtime profile before relying on new evidence for classification; that operation is *not* part of this PR.

**Rollback:** revert deployment env/start-up setting only under authorized restart for a fresh unactivated installation; do not change a running identity or restore old values over a nonempty spool. If source identity or allowed CIDR changes after activation, stop and request explicit lineage/cutover disposition rather than blind rollback.

## 7. Tech Lead handoff — exact status

```text
REQUEST=CAPTIVPROD-DEPLOY-CONFIG-02
ARCHITECT_VERDICT=MODIFIED_APPROVED_FOR_TASK_PREPARATION
IMPLEMENTATION_TASK_ID=TASK-CAPTIVPROD-DEPLOY-CONFIG-02-v1 (TECH_LEAD_TO_ISSUE)
CODE_SCOPE=3_PRODUCTION_FILES_ONLY
SENSOR_CONFIG=APPROVED_WITH_IDENTITY_AND_NETWORK_GATES
PORTAL_CONFIG=APPROVED_WITH_IDENTITY_AND_TLS_GATES
INTERFACE_PREFLIGHT_HIDDEN_PIN=CONFIRMED_MUST_CORRECT
PRODUCER_IDENTITY_ENV=ALLOWED_SYNTAX_ONLY_NOT_ADMISSION
SOURCE_BINDING_F-B1=SEPARATE_ADMISSION_HOLD
CORE_READINESS_TOPOLOGY=SYSADMIN_GATE_HOLD
OLD_DEFAULTS=FROZEN
GUEST_AUTH_OMADA_CAPPORT=UNCHANGED
SCHEMA_MIGRATION=NO
ADDITIONAL_DAEMONS_OR_APIS=NO
NEW_FEATURE_FLAGS=NO
PR_URL=NOT_CREATED
ACCEPTED_COMMIT=NOT_YET_AVAILABLE
ACCEPTED_TREE=NOT_YET_AVAILABLE
CODER_GO=NO_UNTIL_TECH_LEAD_TASK
OWNER_MERGE_GO=NO
PRODUCTION_CHANGE=NO
ACTIVATION_GO=NO
```

**Chief Architect final directive:** Tech Lead may prepare the exact Coder TASK on this contract. This verdict authorizes only development of configuration validation and the one-interface preflight generalization, not producer/source admission, release-gate relaxation or real deployment activation.
