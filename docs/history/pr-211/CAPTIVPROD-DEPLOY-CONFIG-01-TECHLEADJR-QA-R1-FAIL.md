# TASK-CAPTIVPROD-DEPLOY-CONFIG-01 — TechLeadJR Review R1

**Date:** 2026-10-14 (Asia/Baku)  
**Disposition:** **RETURN TO CODER — P1 / SECURITY CODE VALIDATION**  
**Architect contract:** CAPTIVPORTAL-DEPLOY-CONFIG-01-ARCHITECTURE-CONTRACT-v1-FINAL-2026-10-14  
**No architecture return required:** the contract already excludes ambiguous or non-DNS origins.

## Candidate identity and scope

- Starting HEAD: `018985edaa008847b64051dc49c90914d0a60238`
- Starting TREE: `b73f0ed2450e24b7fe4298630999f402a980cce1`
- Submitted patch SHA-256: `c67a323ca1334f9601cecf090d80004901b8be369f74e968ab7c593bf5cd0c23`
- Patch size: 43,376 bytes
- Change scope: exactly 10 files, all on TASK allowlist; no out-of-scope files detected
- Independent WSL git worktree: `/home/zaur_navi/captivportal-lab/worktrees/tljr-deploy-config-qa-01`
- Exact re-generated patch SHA-256 from base after setting `core.abbrev=40`: **identical** to submitted patch
- QA-only clean detached commit: `8002b1d5494ec0a3c50b6795f89c83caa242e7ec`
- QA-only tree: `36936993676880ea3b5513d234478add228cda74`
- QA-only commit is NOT an implementation commit, branch publication, PR, merge or release.

## Executed evidence

- Coder handoff records **146 PASS / 0 FAIL / 0 SKIP** for task-local focused tests; accepted as handoff evidence, not claimed as an independent execution.
- Independent Linux root-level regression: `PYTHONDONTWRITEBYTECODE=1 <qualified-Python-3.10-venv>/bin/python -m pytest -q -p no:cacheprovider tests/test_*.py`, WSL Ubuntu 22.04, Python 3.10.12.
- First attempt from dirty uncommitted checkout: **565 PASS / 1 FAIL**, failure `tests/test_public_traffic.py::test_worker_start_failure_does_not_prevent_flask_start` caused by `capture_loaded_artifact_identity` refusing dirty worktree, not independently established as a code regression.
- Same scope on clean detached LAB ONLY artifact: **566 PASS / 0 FAIL / 0 SKIP**, 19.67 seconds. JUnit: `/home/zaur_navi/captivportal-lab/tmp/tljr-captivprod-qa-root-clean.xml`.
- Exact original patch is unmodified; production, NPM, controller, existing VM and Coder worktree were not changed.
- Windows official Central Lab/full, dedicated final Linux release gate, target security D01-D03: **NOT RUN / HOLD** because P1 prevents source acceptance. No claims of those gates passing.

## P1-01 — CAPPORT numeric/IP-alias authority accepted as DNS

**Location:** `app/config.py::_normalize_capport_public_base_url`.

Architecture requires a canonical HTTPS **DNS** origin, not an IP literal, encoded numeric-IP alternative, or ambiguous authority. Current helper rejects ordinary `https://127.0.0.1`, but it accepts host spellings that browsers/WHATWG URL implementations interpret as a numerical IPv4 address. Direct offline evaluation of the exact candidate function produces:

| Input | Candidate result | WHATWG URL host |
| --- | --- | --- |
| `https://2130706433` | **ACCEPT** | `127.0.0.1` |
| `https://0x7f000001` | **ACCEPT** | `127.0.0.1` |
| `https://0x7f.0.0.1` | **ACCEPT** | `127.0.0.1` |
| `https://127.0.0.1` | REJECT | `127.0.0.1` |
| `https://portal.example` | ACCEPT | `portal.example` |

The numeric aliases are within the current hostname LDH grammar and are not recognized by Python `IPv4Address(host)`. This may publish a CAPPORT `user-portal-url` pointing to a non-DNS/loopback host in browser interpretation. The existing test suite does not cover the aliases.

**Verdict:** P1, security-contract violation. `SECURITY_CODE_REVIEW=FAIL`. Implementation candidate not publishable.

### Bounded Coder Repair Directive R1-01 (copy-paste)

```text
TASK=TASK-CAPTIVPROD-DEPLOY-CONFIG-01
REPAIR=R1-01 / CAPPORT_NUMERIC_IP_ALIAS_REJECTION
SEVERITY=P1
BASE=existing uncommitted candidate / patch c67a323ca1334f9601cecf090d80004901b8be369f74e968ab7c593bf5cd0c23

ALLOWLIST_SOURCE=app/config.py
ALLOWLIST_TESTS=tests/test_deployment_bind_config.py
OTHER_FILES=FROZEN
ARCHITECT_CONTRACT=UNCHANGED

In _normalize_capport_public_base_url(), after the existing validated ASCII LDH
host-label analysis but before accepting/canonicalizing the origin, extract the
last DNS label: host.rsplit('.', 1)[-1]. Reject the entire origin with the
existing generic CAPPORT_PUBLIC_BASE_URL ValueError when this label matches
re.fullmatch(r'(?:[0-9]+|0[xX][0-9a-fA-F]*)', last_label).

Reason: an all-decimal or hex-number trailing label can be interpreted as
an IPv4 address or ambiguous IPv4-host syntax under WHATWG URL semantics.
The empty hex part (0x / 0X) is intentionally rejected as an ambiguous
numeric form. Existing labels such as portal, portal.example, abc123, and
xn--example.test MUST continue passing current grammar and normalization.

Extend URL_INVALID in tests/test_deployment_bind_config.py with at least:
https://2130706433
https://0x7f000001
https://0X7F000001
https://0x7f.0.0.1
https://0x7f.0.0.0x1
https://0x
https://012345
https://192.168.1
https://portal.123

For every added invalid vector verify BOTH:
 - the pure/typed validator rejects with generic non-leaking error;
 - an explicit process-env CAPPORT_PUBLIC_BASE_URL causes non-zero startup
   without default fallback (existing parameterized test already loops URL_INVALID).
Preserve the old default, valid canonical HTTPS DNS origins and valid :port/slash.
Do not modify URL/API paths, CAPPORT service, ProxyFix, Site/CIDR, run.py or Settings.
No third-party URL parser/runtime dependency. No broad refactor.

CODER_VERIFICATION=ONLY_TASK_FOCUSED_TESTS
CODER_BROADER_FULL_WINDOWS_LINUX_GATES=NO
CODER_COMMIT=NO
CODER_PUSH=NO
CODER_PR=NO
CODER_DEPLOY=NO

Deliver: updated uncommitted patch, SHA-256, exact changed-file/line matrix,
focused test results, negative/positive origin vectors, and handoff.
Do not edit/rebase the independent TechLeadJR QA-only worktree.
```

## Final R1 statuses

```text
SOURCE_ALLOWLIST=PASS
PATCH_IDENTITY=PASS
DEFAULT_COMPATIBILITY=TASK_LOCAL_PASS_INDEPENDENT_ROOT_PASS
CAPPORT_REGRESSION=INDEPENDENT_ROOT_PASS
AUTH_REGRESSION=INDEPENDENT_ROOT_PASS
SECURITY_CODE_REVIEW=FAIL_P1_01
CUSTOM_CONFIG_TESTS=FAIL_P1_01_NOT_COVERED_BY_CODER_TESTS
OFFICIAL_WINDOWS_CENTRAL_LAB=HOLD
FINAL_LINUX_RELEASE_GATE=HOLD
TARGET_D01_D02_D03=HOLD_SYSADMIN_OWNER
TECHLEAD_VERDICT=RETURN_TO_CODER
CODER_REPAIR_GO=YES_BOUNDED_R1_01
CODER_COMMIT=HOLD
CODER_PUSH=HOLD
CODER_PR=HOLD
OWNER_MERGE=HOLD
PRODUCTION_CHANGE=NO
```

Full independent acceptance should resume against the *new exact patch* after repair. Do not claim R1's 566 PASS proves a different future patch.
