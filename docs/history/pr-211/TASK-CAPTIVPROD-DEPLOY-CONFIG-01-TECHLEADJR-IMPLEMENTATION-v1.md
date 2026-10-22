# TASK-CAPTIVPROD-DEPLOY-CONFIG-01
## Tech Lead implementation contract v1 — Coder

**Project:** CaptivPortal / independent Captiv-Prod deployment
**Issuer:** Junior Tech Lead, 2026-10-14 (Asia/Baku)
**Status:** IMPLEMENTATION TASK ISSUED — bounded Coder development GO; not an acceptance or release
**Architecture authority:** `CAPTIVPORTAL-DEPLOY-CONFIG-01-ARCHITECTURE-CONTRACT-v1-FINAL-2026-10-14` (Architect `MODIFIED_APPROVED`)
**Repository:** `ZaurNavi/CaptivePortal`
**Exact starting HEAD:** `018985edaa008847b64051dc49c90914d0a60238`
**Exact starting TREE:** `b73f0ed2450e24b7fe4298630999f402a980cce1`
**Architect-reviewed historical HEAD:** `27087766d3f2e104a44da3f36aa6e72a082b12de`; its original tree is documented as `3fe941f1962e6df72d102ba36da60bf25f3bd70a` in repository KB; this is NOT the Coder base.
**Baseline reconciliation:** `27087766... → 018985ed...` = 5 commits ahead; only `docs/configuration.md` and `docs/deployment.md` among this task's allowlisted paths changed (Network Intelligence/NI performance documentation additions). The actual `app/config.py`, `app/capport/models.py`, `app/settings.py`, `run.py`, CAPPORT tests and ProxyFix test were unchanged within this comparison. Preserve all newer docs and code.
**Source of truth:** current pinned code/tests plus approved architecture; this TASK does not supersede architecture.

## 0. Instructions and authorization boundary

- Use isolated local feature worktree rooted at the exact HEAD/TREE above. If either differs at starting checkout or `main` advances before publication, **STOP and report exact drift to Tech Lead**; do not silently rebase or discard intervening work.
- Scope is one application-code configurability change. No ad-hoc refactor, no hidden new features, no new dependencies, no new SQLite objects, no runtime endpoints, no network/Omada operations.
- **Coder GO = YES, implementation and task-local focused tests only.** Initial handoff MUST be an uncommitted exact patch/diff with SHA-256 and reproducible test evidence. **No commit, push, PR, merge, deploy, production restart, firewall/Docker/NPM/Cisco/Omada change** in this first phase. Tech Lead will authorize Git publication after independent candidate acceptance; merge remains Owner-only.
- Source and tests must be deterministic under Python 3.10 on Windows and Ubuntu/Linux. No connection to real Omada and no bind/listen on production. Do not print credentials, environment dumps or secret values.
- If any required behavior cannot fit the below file allowlist without changing semantics, STOP with the precise blocker and a bounded Tech Lead/Architect question. Never choose broader scope yourself.

## 1. Product objective / frozen architecture

One unchanged codebase must support old CaptivPortal VM (default `127.0.0.1:8088`, existing Site/FQDN/guest CIDRs) and an independently configured Captiv-Prod host with a **private IPv4 backend** and site-specific CAPPORT origin/guest CIDRs. New Captiv-Prod operator candidates `172.18.0.1:18089` and `https://captivprod-navi.duckdns.org` are **examples in docs/tests only**; NEVER hard-code them as repository defaults. The new Omada Site ID is supplied and verified independently by SysAdmin; no literal Site ID is invented in product code. Independent Captiv-Prod stores are initialized separately, without data migration in this TASK.

Permanently preserve: one existing `run.py` composition root and one Flask process, `debug=False` as current config, `use_reloader=False`, shared OmadaProvider/authorization/CAPPORT flow, current `app/settings.py:get_settings()` mapping, current one-hop ProxyFix (`x_for=x_proto=x_host=x_port=1`), existing public routes/media-type/no-store/security semantics. `/.well-known/captive-portal` is NOT a newly implemented route. HOST may be valid without being deployable; NPM isolation is a separate SysAdmin proof.

## 2. Exact modification allowlist

**Source (ONLY):**
1. `app/config.py`
2. `app/capport/models.py`

**Tests (ONLY):**
3. `tests/test_deployment_bind_config.py` — create
4. `tests/test_capport_service.py` — existing CAPPORT fixture migration + focused behavior checks
5. `tests/test_capport_routes.py` — existing CAPPORT fixture migration + focused route checks
6. `tests/test_proxy_headers.py` — focused one-hop compatibility cases

**Documentation (ONLY):**
7. `.env.example`
8. `docs/configuration.md` — **preserve all 2026-10-14 NI-01 performance and Network Intelligence additions**
9. `docs/modules/capport.md`
10. `docs/deployment.md` — only a short cross-reference/target deployment separation notice, if needed; no infrastructure reconfiguration instructions masquerading as completed proof

Explicit prohibition: changing `run.py`, `app/settings.py`, `app/web/web.py`, `app/capport/routes.py`, `app/capport/service.py`, `app/controllers/**`, `app/auth/**`, `app/settings_control/**`, `app/device_fingerprint*/**`, other test files, DB/schema, UI, NPM, Docker, Cisco, DHCP 114, Omada, production systemd. The existing `app/web/web.py` old-loopback comment does NOT authorize a source edit under this TASK.

## 3. Design to implement exactly

### 3.1 One pure parser/validator home

In `app/config.py`, implement private, side-effect-free helpers (names below are normative for this TASK) using stdlib only: `os`, `re`, `ipaddress`, `urllib.parse.urlsplit`.

- `_parse_bind_host(value: str) -> str`
- `_parse_bind_port(value: str) -> int`
- `_validate_capport_site_id(value: str) -> str`
- `_normalize_capport_public_base_url(value: str) -> str`
- `_validate_capport_allowed_network_values(values: tuple[str, ...]) -> tuple[str, ...]`
- `_parse_capport_allowed_networks_csv(value: str) -> tuple[str, ...]`

These helpers are pure (no calls to getenv or I/O); `app/config.py` owns the canonical lexical rules. `app/capport/models.py` imports and reuses the Site/origin/network-tuple helpers instead of introducing a competing policy implementation. No new package/file is required; never import `app.capport` from `app/config.py` (its package `__init__` imports routes/service). Errors are `ValueError` with **key and generic reason only**, never raw submitted bytes or secrets. Do not silently strip, coerce, repair, casefold a Site ID or widen a CIDR. Document accepted origin canonicalization separately below.

### 3.2 Startup reading, eager failures and defaults

Define in `app/config.py` the original typed defaults as literals, with identical values when keys are absent:

```python
HOST = "127.0.0.1"                        # absent
PORT = 8088                                # absent (int)
CAPPORT_SITE_ID = "6a64f17630da7c70d232187a"
CAPPORT_PUBLIC_BASE_URL = "https://captivportal-navi.duckdns.org"
CAPPORT_ALLOWED_CLIENT_NETWORKS = (
    "192.168.1.0/24",
    "192.168.8.0/22",
)
```

Use `if "KEY" in os.environ` to distinguish **absent** from **explicit empty**. For present keys only, call the matching validator using `os.environ["KEY"]`. This operation happens at module import/startup before Flask is composed. Every malformed explicit key fails startup with nonzero process exit; no default fallback, no listener and no client changes, including invalid HOST/PORT while CAPPORT is disabled. For consistency the remaining three explicitly supplied CAPPORT keys are also parsed eagerly; this must not introduce any new feature flags or Settings Store generation.

`app/settings.py:get_settings()` already exports all five values; DO NOT edit it. `run.py` already consumes `settings['host']`, `settings['port']` in `app.run`, with `use_reloader=False`; DO NOT edit it. Do not add a `load_dotenv()` call or override existing Settings Store semantics.

### 3.3 `_parse_bind_host`

Accept ONLY literal `127.0.0.1` OR a **canonical dotted-decimal IPv4 address strictly contained** in one of RFC1918: `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`. Use `ipaddress.IPv4Address(value)`, require `str(parsed) == value`, and require one of those network memberships unless exact literal loopback. Return the same string. Reject non-`str`; blank, whitespace, leading/trailing whitespace, multi-address, DNS/interface names, malformed IPv4, octal/leading-zero-like forms, IPv6, public/multicast/link-local, `0.0.0.0`, any `127.*` other than exact `127.0.0.1`. Do not test actual interface existence in application code.

### 3.4 `_parse_bind_port`

Accept only nonempty canonical ASCII decimal with regex `[1-9][0-9]*`, at most 5 digits, integer range `[1024,65535]`, and return Python `int`. Reject `0`, `80`, `65536`, `+18089`, `-1`, ` 18089`, `18089 `, `018089`, `18089.0`, unicode digits, empty, non-string. No implicit `int()`-based acceptance of whitespace/signs. Do not try to bind a socket during parsing.

### 3.5 `_validate_capport_site_id`

Require `str` and `re.fullmatch(r"[0-9a-f]{24}", value)`; return unchanged. Reject empty, whitespace/padded, uppercase, wrong length, nonhex, placeholders, `None`. Do not contact Omada or infer/replace a real Site ID. Existing Site default matches this grammar.

### 3.6 `_normalize_capport_public_base_url`

Accept a **single HTTPS DNS origin**, optionally followed by an explicit valid TCP port and optionally one final `/`. Reject malformed, ambiguous or potentially dangerous input. Precise implementation:

1. Require `str`, ASCII-only, no whitespace or C0/C1 control characters. Require literal lowercase `https://` prefix; no extra leading/trailing bytes. Reject raw `%`, `\\`, `@`, `?`, `#` anywhere (including empty `?`/`#` suffix); reject any embedded control (URL parsers may otherwise strip controls).
2. Call `urlsplit(value)` with error handling; require scheme `https`, nonempty `netloc`, empty username/password, empty query/fragment, `path in ('','/')` only. Reject IPv6 bracket syntax, an IP literal instead of DNS, and any unrecognized authority material.
3. DNS hostname uses ASCII LDH labels (`a-z`, `A-Z`, digits and inner hyphens), each label 1..63, not beginning/ending in `-`; join with dots, no empty labels, no trailing dot, overall hostname length <=253. At least one nonempty label is required. Reject underscores, spaces, raw non-ASCII Unicode and invalid punctuation. Lowercase host in canonical return (DNS case-insensitivity; no encoded/IDNA conversion). If DNS spelling is all numeric dotted IPv4 or matches any IPv4Address, reject because product contract calls for a DNS hostname; punycode ASCII `xn--...` labels follow ordinary LDH rules.
4. Explicit port, when present, is a non-zero canonical ASCII decimal `[1-9][0-9]*` without padding, integer 1..65535. Reject bare `:` and invalid/out-of-range port. Check raw authority explicitly, not just `parsed.port`, because parsed properties can normalize malformed input.
5. Return `https://` + canonical lowercase DNS hostname + `:port` if explicitly present. Drop **only** the permitted single trailing `/`. Never add an implicit port, path, query or fragment. For the old default the output must remain byte-for-byte `https://captivportal-navi.duckdns.org`.

Acceptance examples: `https://captivprod-navi.duckdns.org`, `https://portal.example:8443/`; rejection examples: `http://portal.example`, `https://user:pass@portal.example`, `https://portal.example/a`, `https://portal.example?`, `https://portal.example#`, `https://portal.example//`, `https://portal.example:0`, `https://portal.example:65536`, `https://portal.example:abc`, `https://portal.example:`, `https://portal.example:0443`, `https://portal_example`, `https://[::1]`, `https://192.168.0.1`, `https://%65xample.com`, `https://portal.example\\evil`.

No normalization of userinfo, path or escaped authority into a seemingly safe origin is permitted.

### 3.7 `_validate_capport_allowed_network_values` and CSV

Raw explicit env grammar: one to sixteen **exact canonical IPv4 or IPv6 CIDRs**, comma-separated with **no spaces**, empty item, leading/trailing comma, duplicate or wildcard prefix `/0`. Implement CSV with `value.split(',')` then call `_validate_capport_allowed_network_values(tuple(parts))`. Typed helper requires a tuple of 1..16 `str` CIDRs; for each require a literal slash, reject all whitespace/control; validate with `ipaddress.ip_network(value, strict=True)` and require `str(parsed_network) == value` (lowercase compressed canonical IPv6 and canonical dotted IPv4); reject `prefixlen == 0`, duplicate network objects and duplicates of canonical values. Return original strings as a tuple, preserving order.

Examples accepted: `192.168.8.0/22`; `192.168.1.0/24,192.168.8.0/22`; `2001:db8::/64` (synthetic unit test). Reject `192.168.8.2/22` (host bits), `192.168.8.0/22,` (empty item), `,192.168.8.0/22`, `192.168.8.0/22, 192.168.1.0/24` (whitespace), duplicates, `0.0.0.0/0`, `::/0`, bare `192.168.8.1`, `192.168.008.0/22`, IPv6 uncompressed/noncanonical forms, more than 16 entries.

Store `CAPPORT_ALLOWED_CLIENT_NETWORKS` in `app/config.py` as `tuple[str, ...]` (same existing type); **never** a CSV string. The CAPPORT typed runtime still converts these into `tuple[IPv4Network | IPv6Network, ...]` for its **unchanged actual source-IP membership check**. No change to any other allowlists (Admin, Analytics, webhook, Fingerprint, NI).

### 3.8 `CapportConfig.from_settings()` in `app/capport/models.py`

- Preserve current dataclass fields, TTL parsing, api/login path checks, `login_url` computation and return DTO.
- Remove ONLY the old `settings.get('host') != '127.0.0.1'` rejection and its error message. Do not move the host setting into the CAPPORT DTO; global config validates it once.
- Validate site with shared `_validate_capport_site_id` **without `.strip()`**.
- Validate/canonicalize origin with shared `_normalize_capport_public_base_url` **without `.rstrip('/')`**; generated `login_url` must use this origin and existing `login_path` only.
- Accept the existing typed sequence of network CIDR strings and validate it with shared `_validate_capport_allowed_network_values`, then convert each `str` to `ipaddress.ip_network(value, strict=True)` for CAPPORT's existing membership operations. To preserve historical direct typed-call compatibility, a single `str` CIDR may be converted into a singleton tuple first; a comma-containing `str` is **not** split here and is rejected. Do not silently normalize `192.168.8.2/22`. Reject empty/non-string/non-tuple arbitrary types. Do not relax the allowed-networks check when CAPPORT is disabled or omit any real source-IP validation.
- Do not edit CAPPORT routes/service. Public `user-portal-url`, Site-bound Omada client lookup, pending/authorized/unknown/discovery/login and media type/no-store are existing contracts.

## 4. Test fixture migration and exact Coder focused test scope

**Coder may run only these task-local files:**

```text
tests/test_deployment_bind_config.py
tests/test_capport_service.py
tests/test_capport_routes.py
tests/test_proxy_headers.py
```

There are currently 15 `site-1` occurrences in `tests/test_capport_service.py` and 8 in `tests/test_capport_routes.py`. Replace their synthetic CAPPORT Site identity consistently with a fixed synthetic canonical value `aaaaaaaaaaaaaaaaaaaaaaaa` (24 lowercase hex) in fixtures, mock controller returns and assertions. Do not change `site-1` in unrelated test suites or real production Site defaults. `tests/test_proxy_headers.py` has independent `site-1` Portal Fingerprint test context; do **not** touch those unrelated fixtures. Do not weaken, skip or delete tests; only change synthetic identity where strict new CAPPORT validation requires it.

### 4.1 `tests/test_deployment_bind_config.py` (create)

Use **fresh isolated subprocesses** or a carefully isolated import/reload harness with restoration of `app.config` and `app.settings` state. Preferred: subprocess with inherited ordinary nonsecret test environment and exactly the five keys cleared/set for a specific case, running an `import app.settings; from app.settings import get_settings; ...` snippet (nonzero for invalid). Never depend on a production `.env`, real Omada/controller, localhost listeners, or filesystem writes. Avoid global `sys.modules` contamination of other tests.

Test matrix (parametrized where practical):

- **T01** all five keys absent: old typed constants and `get_settings()` typed mapping exactly; `CapportConfig.from_settings()` gives old `login_url` and both existing network membership scopes; no new config data.
- **T02** HOST `172.18.0.1` and PORT `18089` accepted with correct `str/int` typing and mapping. Verify with **isolated mocked `run.main()` integration or a no-listen capture stub** that unchanged `run.py` supplies those values to Flask `app.run` with debug false and reloader false; do not start background workers, sockets or services. Preserve any existing run.py identity and settings-control bootstrap side-effect guards.
- **T03** invalid explicit HOST cases from §3.3 including empty and public/wildcard/loopback aliases; nonzero and no fallback even if CAPPORT is configured disabled in a separately controlled test fixture.
- **T04** invalid explicit PORT cases from §3.4 incl leading zeros, Unicode numerals, extra whitespace; nonzero/no fallback.
- **T05** Site valid/invalid exact regex; old default preserved; custom Site arrives unchanged at typed CAPPORT lookup in tests; no implicit old-Site fallback.
- **T06** accepted custom HTTPS DNS origin (with/without optional `/` and port), all rejection vectors in §3.6, generated `user-portal-url` with custom host and `/capport/login` only, not the old host.
- **T07** absent, one/two/16 canonical CIDRs, mixed IPv4/IPv6 typed tuples; invalid comma, whitespace, duplication, wildcard, hostbits and 17 networks; `ip_network(strict=True)` checked. Outside-scope addresses denied without Omada lookup, in-scope source selection stays exact.
- Explicit invalid CAPPORT env keys must fail startup rather than defaulting, even when old defaults are syntactically valid. Exercise direct typed `CapportConfig.from_settings()` for invalid Site/origin/CIDR inputs as well as env parser.

### 4.2 Existing CAPPORT task-local module tests

- `tests/test_capport_service.py`: retain original authorization, cache, fallback, deny-before-lookup and newly/custom-allowed CIDR tests, and add narrow Site/origin validation as needed.
- `tests/test_capport_routes.py`: retain original RFC 8908 response content type, Cache-Control no-store, captive/authorized/unknown, discovery, login retry and shared `PortalEntryHandler/AuthSession` cases. Add **one custom-origin `user-portal-url` assertion** that cannot contain `captivportal-navi.duckdns.org`, and custom valid Site bound to CAPPORT service. Do not use Flask server socket.
- `tests/test_proxy_headers.py`: retain original one-hop tests and add one narrow adversarial header test proving only the *rightmost/one configured hop* is honored in Flask test-client semantics. If chain supplied, never claim NPM really sanitized inbound headers; that is D01/D02 SysAdmin security proof. Check forwarded IP, HTTPS scheme, host and port values; ensure no ProxyFix parameter changes.

### 4.3 Coder permitted commands

Run only the task scope, in the standard project lab/venv if available:

```bash
python -m pytest -q tests/test_deployment_bind_config.py tests/test_capport_service.py tests/test_capport_routes.py tests/test_proxy_headers.py
python -m compileall -q app/config.py app/capport/models.py tests/test_deployment_bind_config.py tests/test_capport_service.py tests/test_capport_routes.py tests/test_proxy_headers.py
git diff --check
```

Run `compileall` only with external/disabled bytecode output (e.g., `PYTHONPYCACHEPREFIX` in isolated lab directory); do not dirty the candidate or include pycache. Report exact interpreter, Python/SQLite version if relevant, commands, pass/fail/skips; **no full repo or cross-module pytest, no production test**. Where a scoped test fails, correct only within allowlist, rerun impacted scoped cases and report complete distinct case evidence.

## 5. Documentation acceptance

- `.env.example`: add a compact, commented group for five optional deployment-owned keys (describe defaults; use examples only; do not enable these five by default merely because they appear in an example; **avoid listing HOST=172.18.0.1 as a generic suggested default**). Clearly say `.env.example` is not automatically loaded; no secrets or real controller IDs.
- `docs/configuration.md`: add a single Core/CAPPORT deployment row/table with five defaults, typed explicit grammar, restart-only activation, and note that this config remains outside editable Admin Settings. Preserve recent Network Intelligence docs and all unrelated sections.
- `docs/modules/capport.md`: describe configurable Site, strict HTTPS origin, IP scope, `user-portal-url`, fail-closed invalid explicit values and common Auth flow; no new route.
- Optional `docs/deployment.md`: short pointer and separation between code acceptance and target SysAdmin D01/D02/D03; no claim D gates passed.
- Document fingerprint-portal exact old-Site pins and sensor independent readiness as separate HOLD, not this TASK implementation.

## 6. Coder handoff — first phase

Do NOT commit or publish. Return one exact:

```text
TASK=TASK-CAPTIVPROD-DEPLOY-CONFIG-01
BASE_HEAD=018985edaa008847b64051dc49c90914d0a60238
BASE_TREE=b73f0ed2450e24b7fe4298630999f402a980cce1
WORKTREE_CLEAN_BEFORE=YES/NO
PATCH_SHA256=<actual SHA-256 of exported unified diff>
PATCH_BYTES=<actual bytes>
CHANGED_FILES=<exact list, allowlist only>
CODER_FOCUSED_COMMAND=<exact command>
CODER_FOCUSED_PASSED=<number>
CODER_FOCUSED_FAILED=<number>
CODER_FOCUSED_SKIPPED=<number>
SYNTAX_CHECK=PASS/FAIL
DIFF_CHECK=PASS/FAIL
DEFAULT_COMPATIBILITY_TEST=PASS/FAIL/NOT_RUN
CUSTOM_CONFIG_TEST=PASS/FAIL/NOT_RUN
CAPPORT_TASK_LOCAL=PASS/FAIL/NOT_RUN
PROXY_TASK_LOCAL=PASS/FAIL/NOT_RUN
BROADER_REGRESSION=NOT_RUN_BY_CODER
CENTRAL_LAB=NOT_RUN_BY_CODER
LINUX_RELEASE_GATE=NOT_RUN_BY_CODER
PR=NOT_CREATED
COMMIT=NOT_CREATED
DEPLOY=NO
ISSUES=<exact blockers, if any>
```

Provide the patch file itself and concise module/test evidence (no secrets/log dumps). Do not mark code as accepted because local tests pass. The Tech Lead reviews exact file diff, source-level conformance and evidence before independent tests.

## 7. Independent Tech Lead / QA gates (NOT Coder)

After Coder's patch handoff, the Junior Tech Lead independently runs/checks on the **same exact candidate bytes**:

1. Verify patch digest, allowlist, no hidden off-scope files, correct old defaults, eager failure; compare no new mutation/route/schema/Settings/Omada behavior. Pin exact candidate tree in isolated lab candidate (not a production checkout).
2. Execute independent custom-config and default-compatibility tests T01–T07 on Windows official Central Lab and Linux Python 3.10 lab; specifically check imports, networking validation, origin injection bypasses, and URL/CIDR canonicalization. **Do not** use actual Captiv-Prod NPM or Omada from code tests.
3. Run CAPPORT regression T08 across API state, unauthorized/authorized/unknown, discovery, login retries, content-type/cache-control, and one-hop ProxyFix spoof-model T09. Run old classic External Portal/Auth retry regression T10, provider/shared auth invariants T11.
4. Run cross-module integration, official complete Central Lab/Windows gate and separate Linux production-compatible gate per current `docs/testing-environments.md`, `docs/testing.md`, accepted lab runner and project governance. If performance/release-specific gates are required by actual effects, execute those; never claim they ran merely because test files exist. Keep production off limits for acceptance load testing.
5. Classify and record `DEFAULT_COMPATIBILITY`, `CUSTOM_CONFIG_TESTS`, `CAPPORT_REGRESSION`, `AUTH_REGRESSION`, `SECURITY_CODE_REVIEW`, exact commands/case counts, frozen candidate SHA/tree and independently observed PASS/FAIL. Do not silently weaken failed tests.

After **all mandatory code gates PASS on unchanged candidate**, Junior Tech Lead may authorize Coder to make the reviewed commit on feature branch and create a reviewable PR (without rewriting accepted history). **Owner alone merges** after explicit authorization. Tech Lead independently obtains actual merge commit and tree; **merge does not authorize old-VM changes**.

Separate **Captiv-Prod SysAdmin** deployment gates on target host, only after Owner deploy approval: D01 proven selected bind IP/interface and free port, NPM host routing, real guest source via one-hop proxy, actual TLS/HSTS/CAPPORT/login; D02 positive default-deny for unauthorized containers/interfaces/VLAN/WAN and header spoof isolation; D03 exact new Omada Site ID and OpenAPI permissions. Verify startup readiness, HTTP/HTTPS smoke, service identity and rollback. `DEVICE_FINGERPRINT_PORTAL_ENABLED` stays disabled pending its own compatibility contract; independent sensor readiness remains separate. No data migration. No operation on existing VM unless separately authorized.

## 8. Decision/status block (at issuance)

```text
REQUEST=CAPTIVPROD-DEPLOY-CONFIG-01
ARCHITECT_VERDICT=MODIFIED_APPROVED
IMPLEMENTATION_TASK_ID=TASK-CAPTIVPROD-DEPLOY-CONFIG-01
IMPLEMENTATION_TASK_STATUS=ISSUED
CODER_GO=YES_DEV_AND_FOCUSED_TESTS_ONLY
CODER_COMMIT=HOLD_UNTIL_TECHLEAD_ACCEPTANCE
CODER_PR=HOLD_UNTIL_TECHLEAD_ACCEPTANCE
MERGE=OWNER_ONLY_HOLD
PRODUCTION_CHANGE=NO
CURRENT_MAIN_HEAD=018985edaa008847b64051dc49c90914d0a60238
CURRENT_MAIN_TREE=b73f0ed2450e24b7fe4298630999f402a980cce1
PR_URL=NOT_CREATED
MERGE_COMMIT=NOT_CREATED
MERGE_TREE=NOT_CREATED
DEFAULT_COMPATIBILITY=HOLD_UNTIL_QA
CUSTOM_CONFIG_TESTS=HOLD_UNTIL_QA
CAPPORT_REGRESSION=HOLD_UNTIL_QA
AUTH_REGRESSION=HOLD_UNTIL_QA
SECURITY_REVIEW=HOLD_UNTIL_QA_AND_TARGET_NETWORK_GATES
D01_D02_D03=HOLD_SYSADMIN_OWNER
```

**No architectural request/clarification is blocking this bounded implementation task. If an unforeseen source conflict appears, return its exact facts without expanding scope.**
