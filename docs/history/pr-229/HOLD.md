# DF-RICH-HINTS-01 — bounded test-contract disposition needed

Date: 2026-10-18 Asia/Baku. WSL access restored. Cleanup stopped.

BASE_HEAD=c6db833952d8daabb8fccedb03a774f9277850b6
BASE_TREE=a9ea6dbf7a19a843e34882ba68f70c8ff2b67d92
BRANCH=task/df-rich-hints-01
WORKTREE=/home/zaur_navi/captivportal-lab/worktrees/df-rich-hints-01
DRAFT_TREE=08cbffc16a50b6b3164107d45334eca74d73c052
PATCH_SHA256=533476fe3a6bdbce3c4fb2d7cc93383e8cebd89b03e45ca44739a3d86912713e

This is an unfinished, uncommitted implementation draft, not an accepted final candidate. Nine files: the five permitted production files, the permitted documentation page and three new focused test modules. Real worktree index remains unstaged; draft tree generated with a separate temporary index. No changes to PR #222, canonical Fingerprint semantics, CSS, frozen schemas, producers, services or production.

## Current implementation

Single existing-index-backed read, 256-row total cap, read-only helper, exact integrity/schema checks, latest-per-source/no bad-record fallback, independent Portal model/OS provenance, same-record platform rule, bounded additive projection and optional failure isolation. Device Card adds summary and native collapsed five-source details using existing text helpers and wrapping styles. No additional frontend requests.

## Focused execution so far (Linux only)

Initial reader RED: 11 failed / 1 passed. The first deadline test was overly broad (`Exception`) and was subsequently corrected to require `AnalyticsQueryDeadlineExceeded`; do not treat that initial pass as valid deadline evidence.

Reader first implementation: 12 passed.

Expanded reader + new Admin tests: 20 passed / 5 failed. All five were a confirmed local integration NameError (using a local-only timestamp helper); production caller corrected to use the existing module-level canonical-millisecond UTC formatter.

Latest expanded reader module: 17 passed (in the expanded run; unaffected by the caller-only correction).
Latest Admin run: 29 passed / 1 failed, consisting of new Admin/API and DOM tests plus existing Fingerprint/NI-04 frontend modules.
Current distinct checked cases: 46 passed / 1 failed across these runs. These are not full gates. Windows, live browser, final performance/cap measurements and the rest of the mandatory acceptance matrix remain pending; no P0/P1=0 or final acceptance claim.

Commands used with `-q -p no:cacheprovider` and external per-run basetemp/PYTHONPYCACHEPREFIX:

- python -m pytest tests/device_fingerprint/test_observed_hints.py tests/admin_web/test_observed_device_hints.py
- python -m pytest tests/admin_web/test_observed_device_hints.py tests/admin_web/test_observed_device_hints_frontend.py tests/admin_web/test_device_fingerprint_frontend.py tests/admin_web/test_device_service_intelligence_frontend.py

`git diff --check`: PASS. No final syntax/full gate claim.

## Confirmed blocker

Existing test, unchanged:

`tests/admin_web/test_device_service_intelligence_frontend.py::test_existing_admin_js_prefix_and_ni03_assets_unchanged`

It compares the entire historical pre-NI04 admin.js prefix against commit 22cdde5d4168de02d142c840028a4d66167e47f7. The authorized new UI adds a function block and a Device Card invocation inside that prefix, so strict full-prefix equality fails at byte offset 10001. All other tests in that latest run pass. No skip/xfail/assertion change applied.

## Requested bounded disposition

Authorize changing this exact existing test to remove ONLY the two new insertions from the candidate before comparing every remaining byte to the historical baseline:

1. The uniquely delimited additive block `// DF-RICH-HINTS-01:BEGIN` through `// DF-RICH-HINTS-01:END`, with exact unique ordered anchors.
2. The single exact insertion `    content.append(observedDeviceHintsCard(result.observed_device_hints));`.

Keep existing NI-03 assets, NI-04 lifecycle/runtime and all other prefix bytes frozen. Add negative tests that mutations outside those additions fail; existing canonical Fingerprint code must remain byte-identical. This is a test-contract request, not permission to change production scope.

COMMIT=NO
PUSH=NO
PR=NO
MERGE=NO
DEPLOY=NO
PRODUCTION_ACTION=NO

Preserve the dirty implementation draft pending Tech Lead disposition; do not reset or discard it.
