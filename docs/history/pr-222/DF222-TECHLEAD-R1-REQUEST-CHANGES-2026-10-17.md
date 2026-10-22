# PR #222 — Tech Lead Review R1 / REQUEST CHANGES

Project: ZaurNavi/CaptivePortal
Task: DF-DIAGNOSTIC-ORIGIN-ATTRIBUTION-01
PR: https://github.com/ZaurNavi/CaptivePortal/pull/222
BASE: c6db833952d8daabb8fccedb03a774f9277850b6
HEAD reviewed: ba0df5504eee66a2969ac334995f2ba98fc7e58f
Verdict: **CHANGES REQUIRED / MERGE HOLD / NO DEPLOY**.

## Verified PASS

- Changed files: exactly the declared 7; `git diff --check` clean; isolated worktree clean.
- Canonical classification, R14 semantics, Fusion, DB schema, Omada/Guest/Auth, systemd untouched.
- Coder evidence: Linux 120 PASS / Windows 77 PASS (focused).
- Independently run: Linux Fingerprint-focused **77 PASS**; native Windows Fingerprint-focused **77 PASS**; Linux query/api/fingerprint-contract tests **107 PASS**.
- Read-only bounded OriginAssessment diagnostics, failed lookups preserve canonical card, no Home/Online per-row enrichment.

## Regression blocker — NI-04 frozen prefix

Reproducer:

`tests/admin_web/test_device_service_intelligence_frontend.py::test_existing_admin_js_prefix_and_ni03_assets_unchanged`

- baseline `main@c6db833...`: **PASS**;
- candidate `ba0df55...`: **FAIL**, byte difference at offset 7504.
- Existing assertion compares **the entire `admin.js` prefix preceding** `/* NI-04: independent bounded Service Intelligence coordinator. */` to a historical frozen baseline `22cdde5...`.
- The approved Device Fingerprint UI changes legitimately modify one narrower block inside that legacy prefix; therefore blanket byte-frozen test must be reconciled. Production logic appears consistent with the Coder task, but the full regression gate is red.

### Required change (tests only)

Authorize narrowly adding `tests/admin_web/test_device_service_intelligence_frontend.py` to this PR as a **test-only exception**. Do **not** change unrelated production code, classification, or NI-04/NI-03 implementation.

Update that test to preserve the original byte-for-byte comparison **outside** the one approved Fingerprint block, bounded by **unique anchors**:

- start: `  const FINGERPRINT_DIMENSIONS = [`
- end (exclusive): `  function parseVisitFilters(`

On both the candidate pre-NI04 prefix and the baseline frozen pre-NI04 prefix, replace ONLY the bytes between those anchors with the same fixed sentinel; assert the remaining prefix bytes match. Assert that each boundary occurs exactly once and in order. Preserve the test's other NI-03 asset comparisons, and all other NI-04 tests. Add a negative canary: altering a byte outside the allowlisted Fingerprint span must still fail the new guard.

Do **not** `skip`/`xfail` the original test, remove freeze assertions, broadly regenerate baseline hashes, or normalize unrelated JS. If a diff appears outside the approved span, stop and report to Tech Lead.

### Required validation after fix

- Linux + Windows: NI-04/NI-03 frontend compatibility tests PASS.
- Linux + Windows: Fingerprint presentation/diagnostics tests PASS.
- No changed canonical fields, explanations, artifact bytes, query counts or access rules; no new production files outside original seven.
- Push a new commit to the existing PR #222; provide HEAD/TREE, changed-file inventory and focused JUnit evidence. Retain Draft until Tech Lead signs off.
- Full Linux/Windows gates, independent security and HDD performance checks remain Tech Lead responsibility on new pinned HEAD.

## Windows test environment caveat

An independent initial native-Windows full-suite attempt recorded several early FAILs because Windows Git did not trust the UNC-mounted isolated WSL worktree (fatal: dubious ownership, exit 128). This was **not** a code defect: `test_A_T15_protected_non_history_js_blocks_are_byte_identical_to_baseline` PASSED on Linux and PASSED on Windows once Git `safe.directory` was scoped ONLY to the test process (`GIT_CONFIG_COUNT=1`, `GIT_CONFIG_KEY_0=safe.directory`, exact `GIT_CONFIG_VALUE_0='%(prefix)///wsl.localhost/Ubuntu-22.04/home/zaur_navi/captivportal-lab/df222-techlead-gate'`). No global Git configuration was modified. The entire Windows suite was not completed; other earlier Windows failures have not been independently classified.

## Communication status

Tried to post a REQUEST_CHANGES review to GitHub PR #222, but the GitHub integration returned **403 Resource not accessible by integration**. Hence the review is recorded in this handoff and must be conveyed to Coder directly. No PR approval, merge or production changes performed.
