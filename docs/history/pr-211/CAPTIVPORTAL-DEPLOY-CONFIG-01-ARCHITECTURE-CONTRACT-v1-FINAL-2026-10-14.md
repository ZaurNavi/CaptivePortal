# CAPTIVPORTAL — DEPLOY-CONFIG-01
## Architecture Contract v1 FINAL · Flask HOST/PORT + CAPPORT Site/FQDN/Guest Scope

**Decision:** `MODIFY → APPROVE`  
**Architecture status:** `FINAL / READY FOR TECH LEAD IMPLEMENTATION TASK`  
**Date:** 2026-10-14 · Asia/Baku  
**Owner request:** independent Captiv-Prod deployment, no old-VM change, no data migration  
**Repository:** `ZaurNavi/CaptivePortal`  
**Reviewed repository ref:** `27087766d3f2e104a44da3f36aa6e72a082b12de` (source-level verification through GitHub)  
**TREE:** `UNVERIFIED_BY_ARCHITECT — TECH LEAD MUST PIN AND RECORD EXACT TREE BEFORE TASK`  
**Authorization:** architect approves *bounded architecture only*. **No Coder GO, merge, release, or production change.**

---

## 1. Approved purpose and deployment topology

Enable one CaptivPortal codebase to run concurrently in two independent deployments:

| Dimension | Existing VM — must remain unchanged without new env | Captiv-Prod — intended operator values, not code defaults |
|---|---|---|
| Portal host | `192.168.0.202` | `captiv-prod / 192.168.0.99` |
| Flask bind | `127.0.0.1:8088` | candidate `172.18.0.1:18089` **only after host/NPM/firewall verification** |
| Public ingress | existing HTTPS endpoint | NPM 2.16.0, Docker bridge, HTTPS via `captivprod-navi.duckdns.org` |
| CAPPORT Site ID | `6a64f17630da7c70d232187a` | exact ID proven on new Omada 5.14.32.3; never guess |
| CAPPORT origin | `https://captivportal-navi.duckdns.org` | `https://captivprod-navi.duckdns.org` |
| Guest IP scope | existing two CIDRs below | actual provisioned guest CIDRs, approved by SysAdmin |
| Omada | existing Controller | separate Linux Controller; OpenAPI permissions need live validation |
| Databases | untouched | clean new stores; **no migration in this TASK** |

`172.18.0.1` is a **deployment candidate, not a universal requirement or guaranteed existing interface**. Confirm NPM can route to the selected host-local interface and that it exists before starting Flask. Port 18089 is only a requested candidate; verify non-conflict on the host. Do not assume Docker gateway stability or prescribe `0.0.0.0`.

### Ownership and hard boundary

* Flask remains a **single process**, started via unchanged `run.py`; `use_reloader=False`.
* One already-owned NPM ingress/TLS hop. No new reverse proxy/relay, no Dockerized Flask and no extra application worker.
* CAPPORT and classic Omada External Portal keep one AuthSessionManager/AuthWorker/OmadaProvider authority.
* Configuration is **startup-time process environment**; no writable Settings Store/Admin mutation, no hot reload.
* No changes to existing VM, old Omada/NPM/Cisco, DHCP option 114, SQLite schemas/data, Portal/Admin UI.

---

## 2. Verified source findings and necessary correction to request

At the reviewed commit:

1. `app/config.py` binds `HOST='127.0.0.1'`, `PORT=8088`, `CAPPORT_SITE_ID='6a64f17630da7c70d232187a'`, `CAPPORT_PUBLIC_BASE_URL='https://captivportal-navi.duckdns.org'`, and `CAPPORT_ALLOWED_CLIENT_NETWORKS=('192.168.1.0/24','192.168.8.0/22')` as Python constants.
2. `app/settings.py:get_settings()` already exports `host`, `port`, `capport_site_id`, `capport_public_base_url`, `capport_allowed_client_networks` in its dictionary. **Do not change this mapping.**
3. `run.py` already obtains effective startup settings and calls `app.run(host=settings['host'],port=settings['port'],...,use_reloader=False)`. **Do not change it.**
4. `app/capport/models.py:CapportConfig.from_settings` **explicitly rejects any `host != '127.0.0.1'`**. This must change, otherwise a configurable bind cannot run with CAPPORT enabled (CAPPORT is true by repository default).
5. CAPPORT currently validates only that Site ID is nonempty and that origin starts with a parsed HTTPS scheme/netloc; it **does not** reject URL paths, query, fragment or credentials. New deployment inputs require closed, stricter validation.
6. CAPPORT's allowed-client-networks string is treated as **one** network, not as CSV. A process-env network list needs an explicit parser; simply assigning `os.getenv('CAPPORT_ALLOWED_CLIENT_NETWORKS')` is wrong.
7. `app/capport/routes.py` builds `user-portal-url` from `CapportConfig.login_url`, which uses configured `public_base_url + login_path`. CAPPORT client lookup is keyed by configured Site ID. No separate hard-coded old FQDN/Site ID was found in CAPPORT route/service implementation during repository search.
8. A search of the reviewed repository did **not** establish any Flask handler for `/.well-known/captive-portal`. It may belong to external infrastructure. **Do not claim support or add a new route under this TASK.** Operator validates its actual existence if deployment requires it.
9. `app/device_fingerprint_portal/config.py` contains an independently **exact-pinned** old Site ID, guest CIDR and old evidence URL, and `app/device_fingerprint_sensor/config.py` defaults core readiness to `127.0.0.1:8088`. These are **independent feature contracts**, not fixed by CAPPORT configurability. See §8.

---

## 3. Closed deployment configuration contract

| Environment key | Default if absent (byte-compatible) | Accepted explicit value | Activation |
|---|---|---|---|
| `HOST` | `127.0.0.1` | canonical dotted IPv4 `127.0.0.1` **or an exact IPv4 address inside RFC1918**; not wildcard/public/FQDN/IPv6 | restart |
| `PORT` | `8088` (integer) | canonical ASCII decimal integer `1024..65535`; no signs, whitespace, leading zeros or non-digits | restart |
| `CAPPORT_SITE_ID` | `6a64f17630da7c70d232187a` | exact **24-character lowercase hex** canonical Omada Site ID; no whitespace, placeholders or automatic case conversion | restart |
| `CAPPORT_PUBLIC_BASE_URL` | `https://captivportal-navi.duckdns.org` | validated HTTPS origin `https://<dns-name>` optionally with valid explicit TCP port; no userinfo, password, path other than optional `/`, query, fragment, whitespace or control characters; canonical return has no trailing `/` | restart |
| `CAPPORT_ALLOWED_CLIENT_NETWORKS` | existing exact `('192.168.1.0/24','192.168.8.0/22')` | comma-separated **one to sixteen** exact canonical IPv4/IPv6 CIDRs, no empty/duplicate values, no wildcard `/0`; only operator-verified guest ranges. Parse to **tuple**, never one string | restart |

### Decision C1 — HOST/PORT

Implement via the existing `app/config.py` env reading and strict validation, propagate through already existing `get_settings()` into unchanged `run.py`.

* `HOST` cannot be `0.0.0.0`, `::`, a public IP, a hostname, an interface name, loopback aliases (only exact `127.0.0.1`), or a malformed/multihomed value. `172.18.0.1` is within allowed RFC1918 addresses, **not auto-selected**.
* A valid private IPv4 is necessary but **not sufficient** for permission to deploy it. Host firewall/Docker isolation must separately prove only approved NPM path can reach Flask.
* Invalid **explicit** `HOST` or `PORT` => startup configuration error, non-zero exit, no fallback to default; do not log raw secrets. Validation must run regardless of whether CAPPORT is enabled.
* Keep one `ProxyFix` hop untouched (`x_for=1,x_proto=1,x_host=1,x_port=1`). Do not change its trust count, nor introduce a user-facing Flask listener.

### Decision C2 — CAPPORT Site ID

`CAPPORT_SITE_ID` is read from environment if explicitly provided. A malformed explicit Site ID is rejected (no fallback to old). The normative actual controller Site form for this deployment is `^[0-9a-f]{24}$`; adapt existing CAPPORT unit fixtures that used `site-1` to a valid synthetic Site ID **if** the CAPPORT typed validator is strengthened. No controller connectivity attempt, blind ID discovery or Omada mutation in config validation. Owner/SysAdmin must verify exact ID against the new controller before activation.

### Decision C3 — CAPPORT public origin

`CAPPORT_PUBLIC_BASE_URL` is deployment-configurable; origin grammar above is enforced using a parsed URL **and** authority checks (a mere `scheme=https`/`netloc` test is not sufficient). Reject credentials, malformed ports, percent-escaped authority tricks, query/fragment, unexpected path and malformed DNS authority. Preserve old default exactly. CAPPORT's `user-portal-url` is derived **only** from selected config; when custom origin is supplied, no old-origin URL may appear in CAPPORT responses. Keep `/capport/api` and `/capport/login` routes, response media type, cache policy and authorization path unchanged. `/.well-known/captive-portal` remains a deployment discovery verification item only, not a newly claimed Flask API.

### Decision C4 — CAPPORT guest-scope input (**one justified scope extension**)

Approve the *fifth* optional deployment env key `CAPPORT_ALLOWED_CLIENT_NETWORKS`. It is important because a valid new Omada Site ID alone cannot make a guest from a new subnet pass CAPPORT's existing source-IP allowlist. The current two-network default stays **exactly unchanged** when absent. The CSV is parsed once at startup into a tuple; check exact CIDR grammar, nonempty/duplicate/`/0` and bounded entries; malformed explicit value => startup failure, **not** silent permission expansion or reverting to old CIDRs. IP matching remains existing strict actual client IP ∈ selected network semantics. Operator supplies CIDRs from factual DHCP/gateway scope, not by guessing.

**Note:** If Captiv-Prod guests use only the original ranges, the new network variable may be omitted. Its presence in the code merely makes an independently configured subnet possible; it does not move clients, modify Cisco/DHCP or permit arbitrary source addresses.

### Default compatibility

With all five new env keys **absent**:

```
HOST                      = 127.0.0.1
PORT                      = 8088
CAPPORT_SITE_ID           = 6a64f17630da7c70d232187a
CAPPORT_PUBLIC_BASE_URL   = https://captivportal-navi.duckdns.org
CAPPORT_ALLOWED_CLIENT_NETWORKS = 192.168.1.0/24, 192.168.8.0/22 (tuple)
```

No settings-generation/managed-Settings mutation mechanism is introduced. These five keys remain deployment-owned, not Admin-editable.

---

## 4. Approved exact file scope for Tech Lead

**Production changes permitted** (minimum):

1. `app/config.py`: environment opt-in + strict scalar/CIDR parse/validation; preserve typed defaults.
2. `app/capport/models.py`: remove **only** the obsolete `HOST == 127.0.0.1` guard (new validated HOST is composed at startup), harden exact Site ID/HTTPS origin validation without changing CAPPORT resolution/route behavior, and enforce safe typed guest scope as needed.

**Tests/docs allowed** (bounded):

3. `tests/test_capport_service.py` and `tests/test_capport_routes.py` for old/default and new config, including conversion of synthetic fixture Site IDs to canonical form as needed.
4. `tests/test_proxy_headers.py` for confirming unchanged one-hop source IP/scheme/host interpretation.
5. `tests/test_deployment_bind_config.py` (**new**), focused on import-time env config, exact typed value validation, startup propagation, failure modes and defaults. If existing `tests/test_config.py`/`tests/test_settings.py` are a better matching test home, Tech Lead may name them precisely instead; no broad test refactor.
6. `.env.example`, `docs/configuration.md`, `docs/modules/capport.md`: clear deployment notes, no secrets; document default and custom behavior and NPM boundary. A short link in `docs/deployment.md` is allowed only when Tech Lead explicitly includes that file in TASK.

**Explicitly excluded from production source edits:**

`run.py`, `app/settings.py`, `app/web/web.py`, `app/capport/routes.py`, `app/capport/service.py`, `app/controllers/*`, `app/auth/*`, `app/settings_control/*`, `app/device_fingerprint*`, any SQL schema/DB/storage files, NPM/Docker/Cisco/Omada/Flask process-topology changes.

If implementation cannot satisfy the contract within this whitelist, Coder must **HOLD and seek Tech Lead/Architect scope amendment**, not silently modify unrelated code. UI and public DTOs are frozen.

---

## 5. Security / reverse-proxy deployment gates (SysAdmin-owned)

The code-level HOST setting does **not** authorize exposing Flask. Captiv-Prod SysAdmin must verify:

* selected bind IPv4 exists on the host before Flask starts; bind port does not conflict with Omada or anything else; NPM-to-host route works over the selected Docker bridge network;
* only exact approved NPM container/network traffic can reach the Flask backend, including **from other containers, other interfaces and host forwarding paths**; default deny from Guest VLAN, LAN outside approved path, WAN and arbitrary Docker networks;
* proxy never passes untrusted external spoofed `X-Forwarded-*` as trusted identity: for exactly one trusted hop it overwrites forwarded client IP/scheme/host/port with its **verified** real ingress peer and public HTTPS origin; no bypass request can directly send trusted headers to Flask;
* test CAPPORT real source IP seen by Flask via `ProxyFix` on a controlled guest test phone; without correct source IP the allowed-network / Site resolution fails, irrespective of correct NPM connectivity;
* TLS valid for `captivprod-navi.duckdns.org`; pre-auth guest can reach NPM HTTPS; public CAPPORT API and login are same-origin as configured; sensitive request access-log policy unchanged;
* DHCP option 114 is **not** changed by this patch; if enabled later, its URL must point to the verified new `/capport/api` (never the old host), with separately approved network change;
* old VM/Controller path and old DNS behavior remain unaffected.

No code validation can guarantee firewall correctness. **If network isolation/proxy spoof resistance has not been demonstrated: Captiv-Prod activation = HOLD.** No special Docker systemd dependency is imposed on core code; SysAdmin handles actual interface readiness/boot ordering in the deployment runbook if required.

---

## 6. Acceptance matrix (mandatory, lab first)

| ID | Test | Required outcome |
|---|---|---|
| T01 | All 5 vars absent | Exact old typed defaults; old Site/CAPPORT generated URLs; unchanged start path |
| T02 | `HOST=172.18.0.1`, `PORT=18089` | Typed values reach `app.run`; `debug=False`, `use_reloader=False`, one process |
| T03 | Invalid HOST: `0.0.0.0`, `::`, hostname, public IP, blank/space, malformed | controlled non-zero startup, no fallback, no listener |
| T04 | Invalid PORT: `0`, `80`, `65536`, negative, whitespace, plus sign, decimal text, leading zero | fail-closed |
| T05 | Custom Site exact `^[0-9a-f]{24}$` vs empty/uppercase/wrong length/unknown characters | accepted/rejected as specified; no automatic old Site fallback |
| T06 | Custom origin `https://captivprod-navi.duckdns.org`; malformed scheme, credentials, path, query, fragment, authority, port | only valid HTTPS origin accepted; `user-portal-url` points to new host only |
| T07 | Allowed-network tuple absent, one subnet, multiple CIDRs; malformed comma syntax, duplicate, `/0`, hostbits | accepted scope typed tuple; reject bad; no permissive fallback |
| T08 | CAPPORT state, authorized/pending/unknown, discovery, login, no-store/media-type | unchanged RFC 8908 semantics and shared Auth flow |
| T09 | One-hop ProxyFix: IP/proto/host/port and controlled spoofed upstream case | no trust-count regression; forwarded source IP from approved NPM trust contract |
| T10 | Old classic External Portal flow (`/?site=...&clientMac=...`) and Auth retry | unchanged |
| T11 | No port / route / Settings Store / SQLite or OmadaProvider new behavior | static and integration checks PASS |
| T12 | Linux/Python 3.10 compatible, focused suites + official Central Lab/release gates | Tech Lead/QA acceptance, exact commit/tree recorded |
| D01 | Target NPM→HOST:PORT plus real guest IP/HSTS/TLS/CAPPORT semantics | separate Captiv-Prod SysAdmin acceptance |
| D02 | Guest VLAN/WAN/unauthorized containers cannot reach Flask | separate Captiv-Prod security acceptance |
| D03 | New Omada Site ID and OpenAPI access verified; no old production mutation | separate Captiv-Prod readiness evidence |

Repository tests must not bind new IP on production, require actual NPM or make real Omada client changes. Network integration D-gates are performed by target SysAdmin. A correct unit test does not prove Docker reachability or firewall isolation.

**Regression acceptance remains `HOLD`, not `PASS`, until tests have actually run on the accepted code tree.** Architecture acceptance is not test acceptance.

---

## 7. Deployment handoff values (example only)

```dotenv
HOST=172.18.0.1
PORT=18089
CAPPORT_SITE_ID=<24-character-lowercase-hex-from-new-Omada>
CAPPORT_PUBLIC_BASE_URL=https://captivprod-navi.duckdns.org
# Only if new guest ranges differ from current defaults:
CAPPORT_ALLOWED_CLIENT_NETWORKS=192.168.8.0/22
```

Placeholders are **not valid literal runtime values**. Service environment must also provide independently verified `OMADA_URL`, `OMADA_ID`, `OMADA_CLIENT_ID`, `OMADA_CLIENT_SECRET`; `.env.example` is not auto-loaded. Keep credentials outside Git, ensure service uses an approved secret mechanism. Restart is required after changing startup-owned values. The new Omada Controller's v5.14.32.3 compatibility/permissions are **deployment validation**, not a claim proven by this code review.

### Separation from other features / known traps

* CAPPORT guest allowlist is separate from `WEB_ADMIN_ALLOWED_NETWORKS`, `ANALYTICS_API_ALLOWED_NETWORKS`, webhook source allowlist, Portal Fingerprint guest scope, NI capture scope and Omada access control. **Do not reuse or silently mutate them.**
* `DEVICE_FINGERPRINT_PORTAL_ENABLED=true` on the new installation is **HOLD**: at reviewed commit its config pins old production Site/guest/evidence endpoint with exact-equality validation. Do not expand this TASK into that frozen module. Separate review and acceptance are needed before enabling it.
* `DEVICE_FINGERPRINT_SENSOR_*` defaults include `CORE_READY_HOST=127.0.0.1`, `CORE_READY_PORT=8088`; if the sensor is later deployed with Flask on 18089, its independent readiness wiring needs a separate approved configuration/architecture check. Do not assume this deployment fix makes Fingerprint/NI ready.
* Documentation `docs/CAPPORT.md` is historical/superseded; the current normative CAPPORT module document is `docs/modules/capport.md`. Old FQDN mentions in historical docs/test fixtures are not proof of runtime hard-coding.
* `/.well-known/captive-portal` was not found as a Flask application route at inspected ref. Its applicability and serving location belong to a separate ingress acceptance check. Avoid inventing a new app route or declaring it operational without live evidence.

---

## 8. Execution/authority order

1. **Tech Lead** pins actual current `main` HEAD/TREE; compares against reviewed commit; confirms allowed file list and any intervening configuration changes.
2. Tech Lead issues implementation task **`TASK-CAPTIVPROD-DEPLOY-CONFIG-01`** (suggested ID) with scope, test matrix, and per-stage gates.
3. **Coder** implements on an isolated feature branch; unit/focused regression evidence; PR, no production access/activation.
4. **QA/Tech Lead** run the mandatory Central Lab and Linux/release checks against an exact tree, adjudicate compatibility/security.
5. **Owner** separately authorizes merge/release, if all gates pass.
6. **Captiv-Prod SysAdmin** independently applies configuration to new machine, checks NPM isolation, new controller Site and live guest behavior; existing VM remains untouched unless independently authorized.

Tech Lead must report real PR URL, accepted merge SHA/tree and PASS/FAIL evidence **after** those steps. This architecture document does not and cannot supply them in advance.

---

## 9. Machine-readable handoff status for TechLead23

```text
REQUEST=CAPTIVPROD-DEPLOY-CONFIG-01
ARCHITECT_VERDICT=MODIFIED_APPROVED
ARCHITECTURE_CONTRACT=CAPTIVPORTAL-DEPLOY-CONFIG-01-ARCHITECTURE-CONTRACT-v1-FINAL-2026-10-14
REVIEWED_BASE_HEAD=27087766d3f2e104a44da3f36aa6e72a082b12de
REVIEWED_BASE_TREE=NOT_VERIFIED_TECHLEAD_MUST_PIN
CHANGE01_HOST_PORT=APPROVED_STRICT_ENV_DEFAULT_PRESERVING
CHANGE02_CAPPORT_SITE_FQDN=APPROVED_STRICT_ENV_DEFAULT_PRESERVING
CAPPORT_ALLOWED_CLIENT_NETWORKS_FINDING=APPROVED_FIFTH_OPTIONAL_ENV_WITH_STRICT_CSV_PARSER
IMPLEMENTATION_TASK_ID=TASK-CAPTIVPROD-DEPLOY-CONFIG-01_SUGGESTED_TECHLEAD_TO_ISSUE
PR_URL=NOT_CREATED
MERGE_COMMIT=NOT_CREATED
MERGE_TREE=NOT_CREATED
DEFAULT_COMPATIBILITY=HOLD_UNTIL_QA
CUSTOM_CONFIG_TESTS=HOLD_UNTIL_QA
CAPPORT_REGRESSION=HOLD_UNTIL_QA
AUTH_REGRESSION=HOLD_UNTIL_QA
SECURITY_REVIEW=HOLD_UNTIL_QA_AND_TARGET_NETWORK_GATES
NEW_ENV_VARIABLES=HOST,PORT,CAPPORT_SITE_ID,CAPPORT_PUBLIC_BASE_URL,CAPPORT_ALLOWED_CLIENT_NETWORKS
DEPLOYMENT_NOTES=PRIVATE_IPV4_BACKEND_REQUIRES_NPM_ONLY_FIREWALL_PROOF;EXACT_NEW_OMADA_SITE_ID;NO_OLD_VM_CHANGE
OPEN_ISSUES=TARGET_NPM_DOCKER_ROUTABILITY_FIREWALL;WELL_KNOWN_INGRESS_DISCOVERY;FP_SEPARATE_CONFIGURATION;SOURCE_TREE_REPIN
CODER_GO=NO
PRODUCTION_CHANGE=NO
NEXT=TECHLEAD_IMPLEMENTATION_TASK_TO_CODER_QA_OWNER_RELEASE
```

**Final Architect verdict:** bounded generic deployment configurability **approved**. No architecture dependency on `captiv-prod`, `172.18.0.1`, NPM, Omada Controller version or current project guest SSID may be hard-coded into app implementation. Preserve existing default deployment and one-proxy security model. Implementation, accepted commit and deployment remain separate authorities.
