# TECHLEAD22 — TASK-DTI-NI-04-UNIFIED55 / Coder bounded repair R3

**Verdict:** `FULL_ACCEPTANCE=HOLD; SOURCE_REPAIR_REQUIRED; COMMIT/PUSH/PR=HOLD`.

Independent native Linux: exact `CANDIDATE_TREE=a91f9ed93a3602a91473a15b98f1a85c634c7b66`, 224 NI-04 focused PASS, 50 NI-03 PASS, 715 NI-01/NI-02B/Portal/Auth/CAPPORT selected PASS. Entire Admin Web: **1193 PASS / 11 FAIL**. All 11 failures are reproducible, two source-level causes:

**P1-03 — DOM-absent Admin JS initialization.** In the newly appended NI-04 IIFE in `app/admin_web/static/admin.js`, add an early guard before *any* `document` access (e.g. `if (typeof document === "undefined") return;`). Preserve all browser behaviors and established 120/300/600 cadence. Existing Node-based Admin tests must run without a DOM. Add a test for this exact boundary; do not modify legacy tests.

**P1-04 — NI-03 CSS suffix contract.** The NI-04 CSS block was appended after the old `/* NI-03 presentation only;` block in `app/admin_web/static/admin.css`. The unchanged `tests/admin_web/device_protocol_intelligence.cjs` requires the entire NI-03 suffix to be NI-03-scoped, so it fails `scoped protocol CSS only`. Move NI-04 CSS before the NI-03 sentinel, preserving the old NI-03 CSS rules byte-for-byte and ensuring NI-04 selectors remain `#device-service-intelligence` scoped. Do not modify the old NI-03 test.

**Allowed edit scope:** the two named source files and minimal tests under existing NI-04/Admin frontend test files. No other source changes without a new Tech Lead finding. Do not change immutable Lane A JSON, 55-service Registry, manifest, Evidence Pack, feature flag, schema, writers, NI-03 behavior or production.

**Required evidence to return:** full **replacement** `BASE_HEAD -> candidate` patch (not small delta), SHA-256/bytes, exact `CANDIDATE_TREE`, changed-file whitelist, unchanged immutable SHA-256s, native full diff-check result with exactly the preapproved Evidence Pack lines 4–6, Linux/Windows focused tests, all `tests/admin_web` passing, `tests/network_protocol_intelligence` passing, `compileall`, Node syntax. Coder can test locally; Tech Lead will independently rerun full Linux/performance/writer co-existence/browser gates on the repaired freeze.

`COMMIT=NO; PUSH=NO; PR=NO; MERGE=NO; DEPLOY=NO; PRODUCTION_ACTION=NO` until Tech Lead Full Acceptance PASS and separate Owner authority for non-publication actions.
