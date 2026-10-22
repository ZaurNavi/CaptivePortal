# TASK-DTI-NI-04-UNIFIED55 — TECHLEAD22 NATIVE LINUX LAB REVIEW R3

**Date:** 2026-10-12 (Asia/Baku)  
**Disposition:** **REPAIR REQUIRED / FULL ACCEPTANCE HOLD / PUBLICATION HOLD**  
**Environment:** independently cloned native Ubuntu 22.04 WSL2 lab on authorized Desktop Commander host; Python 3.10.12; Node 24.20.0. All test data disposable; no production access.

## 1. Exact tested identity

- Base HEAD: `22cdde5d4168de02d142c840028a4d66167e47f7`.
- Base TREE: `a783d1cb3b2f33107ba64878ae5d3d8b80463f38`.
- Source R1 complete patch SHA-256: `aa6d6dd6039da6c5dcca3c6d8881cd12355939fdf55582bfe114bfa0d8047385` (276,260 bytes), independently verified.
- Independently reconstructed lab candidate TREE: **`a91f9ed93a3602a91473a15b98f1a85c634c7b66` — PASS**.
- Native staged `git diff --check`: **FAIL**, *only* preapproved two-space Markdown linebreaks in `docs/network-service-recognition/lane-a-evidence-pack-v1.md`, lines 4–6. Exact approved exception retains status `FAIL_WITH_APPROVED_EXACT_EXCEPTION`; no global waiver.
- Native lab checkout: `/home/zaur_navi/captivportal-lab/ni04-unified55-acceptance-20261012`. Independent baseline: `/home/zaur_navi/captivportal-lab/ni04-unified55-baseline-20261012`.
- Neither the Coder worktree nor the production host was changed; the lab index alone was staged to independently calculate `git write-tree`. No commit.

## 2. Independently executed gates

| Gate | Native Linux result | Admission |
|---|---|---|
| Exact Git candidate reconstruction | Candidate TREE exact PASS | PASS |
| NI-04 focused kernel/read/API/frontend pytest | **224 passed** | PASS |
| NI-03 protocol intelligence pytest | **50 passed** | PASS |
| NI-01 + NI-02B + Portal/Auth/CAPPORT targeted pytest | **715 passed** | PASS for executed regression slice; not live writer-pressure proof |
| Entire `tests/admin_web` pytest | **1193 passed, 11 failed** | **FAIL** |
| Python `compileall -q app` | Exit 0 | PASS |
| Node `--check app/admin_web/static/admin.js` | Exit 0 | PASS (syntax only) |
| Main repository-wide pytest | Started; first environment missing `cryptography`; retried with a venv including it; reproducible failures observed; **stopped near 53% when blocking regression independently confirmed** | **INCOMPLETE / FAILING, NOT PASS** |
| Separate full baseline regression | Stopped after targeted differential verified baseline passes; no claim of full baseline run | PARTIAL |
| Actual concurrent NI-01/NI-02B writers, WAL/checkpoint/retention/capacity | Not executed on this failing candidate | PENDING |
| NI-04 peak incremental RSS <=64 MiB, max endpoint <=5s, p50/p95 | Not executed on this failing candidate | PENDING |
| Portal/Auth/CAPPORT differential latency under concurrent load | Not executed | PENDING |
| Desktop/mobile real-browser, focus and accessibility acceptance | Not executed | PENDING |
| Central official full-gate acceptance | Not passed | HOLD |

Test environments were separate from the production system. Reported counts correspond to *different test selections* and must not be summed as a unique full-suite total.

## 3. P1-03 — NI-04 JavaScript breaks pre-existing Node/no-DOM contracts

**Source anchor:** `app/admin_web/static/admin.js`, appended NI-04 coordinator, new IIFE, first `document.getElementById("device-service-intelligence")` around source line 6697.

The script unconditionally evaluates `document` at module load, even when existing JS contract suites intentionally run the Admin bundle in Node with `window` but without a DOM. Result: `ReferenceError: document is not defined`.

**Ten independently observed failures from the 1204-test Admin Web suite:**

1. `tests/admin_web/test_admin_ui_frontend.py::test_admin_javascript_syntax_and_state_contract`
2. `tests/admin_web/test_admin_ui_frontend.py::test_home_live_javascript_validation_freshness_and_retry_contract`
3. `tests/admin_web/test_current_partial_coverage.py::test_A_T13_real_frontend_validator_labels_and_offline_details`
4. `tests/admin_web/test_device_fingerprint_frontend.py::test_fingerprint_summary_details_and_separate_controller_surface`
5. `tests/admin_web/test_home_activity_frontend.py::test_home_activity_real_node_contract`
6. `tests/admin_web/test_home_ap_24h_frontend.py::test_home_ap_24h_real_node_contract`
7. `tests/admin_web/test_home_health_frontend.py::test_home_health_real_node_contract`
8. `tests/admin_web/test_home_traffic_frontend.py::test_home_traffic_node_state_machine_and_validation`
9. `tests/admin_web/test_web_ux_pack_02.py::test_machine_icons_and_single_ap_roster_dom`
10. `tests/admin_web/test_web_ux_pack_03.py::test_roster_exact_join_timeline_before_devices_and_history_failure_is_local`

**Baseline differential:** `test_admin_javascript_syntax_and_state_contract` PASS (1/1) on exact baseline HEAD; FAIL on candidate with `ReferenceError`. This is a candidate-induced regression.

**Required bounded repair:** guard against absent DOM **before the first access to `document`** in the NI-04 IIFE, preserving the existing actual browser path, visibility/IntersectionObserver logic, 120-second automatic cadence, backoff and manual Refresh. No change to earlier Admin JS modules. Ensure the full existing Node suites run unchanged. Add a new NI-04 regression assertion that the complete Admin JS bundle can be evaluated without global `document` and that the NI-04 coordinator safely skips itself.

## 4. P1-04 — NI-04 CSS appended after normative NI-03 section breaks NI-03 scope

**Source anchors:** `app/admin_web/static/admin.css` and unchanged `tests/admin_web/device_protocol_intelligence.cjs`, around line 209–212.

The existing NI-03 frontend contract slices CSS beginning at `/* NI-03 presentation only;` and asserts that all subsequent selectors belong to `#device-protocol-intelligence`. The new NI-04 `#device-service-intelligence` CSS was appended *after* the NI-03 block. The legacy contract therefore fails at `scoped protocol CSS only`.

**Failure:** `tests/admin_web/test_device_protocol_intelligence_frontend.py::test_real_node_protocol_frontend_contract`.

**Baseline differential:** exact same NI-03 test PASS (1/1) on baseline HEAD; FAIL on candidate.

**Required bounded repair:** relocate the entire added NI-04 CSS block before the existing NI-03 sentinel section (or an equivalently narrow placement preserving the old NI-03 CSS suffix contract). Keep the original NI-03 CSS byte content/semantics intact, and continue to scope all new rules to `#device-service-intelligence`. Do not change the existing NI-03 test to accommodate source code.

## 5. What remains frozen

- Unified55 remains **one TASK** and one eventual candidate/PR, not two Coder tasks.
- Existing Lane A 5-rule taxonomy/manifest/ruleset v1 raw bytes, semantic digests, research registry and Evidence Pack **must remain immutable**.
- 55 registered Service IDs != 55 admitted runtime rules; runtime retains only the five accepted direct exact-SNI rules.
- Default feature flag remains OFF, no schema/writer changes, no IP/DNS/CDN guesses, no sensitive hostname leakage.
- Do not touch Portal/Auth/CAPPORT, NI-01/NI-02B writer/retention, NI-03 semantics, Traffic, Settings, Omada, production or deployment configs.

## 6. Binding disposition / next action

```text
SOURCE_CANDIDATE_R1_FINAL_ACCEPTANCE = NO
NATIVE_LINUX_EXACT_TREE = PASS
NI04_FOCUSED_LINUX = 224 PASS
NI03_LINUX = 50 PASS
NI01_NI02B_PORTAL_AUTH_CAPPORT_SLICE = 715 PASS
ADMIN_WEB_FULL = 1193 PASS / 11 FAIL
P1-03_NODE_NO_DOM = OPEN
P1-04_NI03_CSS_SECTION_SCOPE = OPEN
WHOLE_REPOSITORY_FULL_PYTEST = NOT_COMPLETED / NOT_PASS
PERF_RSS = PENDING
WRITER_READER_LIVE_PRESSURE = PENDING
BROWSER_ACCESSIBILITY = PENDING
PUBLICATION_COMMIT_PUSH_PR = HOLD
MERGE_DEPLOY_PRODUCTION_ACTIVATION = NOT_AUTHORIZED
```

Authorize **only the bounded P1-03/P1-04 local repairs** in the existing Coder worktree, with regression tests in already allowed test folders. Receive a new complete replacement patch, SHA-256, candidate TREE, diff/whitelist report and focused + full Admin evidence. Then rematerialize the exact new candidate in clean Linux and repeat all mandatory gates. **No publication instruction may be issued until PASS.**
