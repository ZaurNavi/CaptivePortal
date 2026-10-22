# DF-RICH-HINTS-01 — focused implementation handoff / read-only boundary HOLD

Date: 2026-10-18 Asia/Baku.

## Identity and scope

BASE_HEAD / current implementation HEAD: `c6db833952d8daabb8fccedb03a774f9277850b6`
BASE_TREE: `a9ea6dbf7a19a843e34882ba68f70c8ff2b67d92`
DRAFT_CANDIDATE_TREE: `6324d6e94dbe8d7fd528c392cf1d0813522864eb`
BRANCH: `task/df-rich-hints-01`
WORKTREE: `/home/zaur_navi/captivportal-lab/worktrees/df-rich-hints-01`
STATE: DIRTY / UNCOMMITTED; normal index not staged. Candidate tree constructed using an isolated index, not a commit.
LATEST_FETCHED_ORIGIN_MAIN: `c6db833952d8daabb8fccedb03a774f9277850b6` (no drift at this handoff).

Full replacement patch: `replacement.patch`
SHA256: `39e4e702c138bd79fd8cd1e05e33650020f38a20458fa595b558223be60395bf`
Stat: **10 files, 842 insertions, 6 deletions**.

Changed production files (exact original five-file allowlist):

- app/device_fingerprint/read_service.py
- app/admin_web/device_fingerprint_presentation.py
- app/admin_web/runtime.py
- app/admin_web/query_service.py
- app/admin_web/static/admin.js

New focused test files:

- tests/device_fingerprint/test_observed_hints.py
- tests/admin_web/test_observed_device_hints.py
- tests/admin_web/test_observed_device_hints_frontend.py

Modified existing test: tests/admin_web/test_device_service_intelligence_frontend.py — only the subsequently approved narrow byte-freeze exception and its positive/negative canaries.
Documentation: docs/modules/admin-web.md — one bounded additive-read section.

Production source is byte-identical to the prior HOLD draft tree `08cbffc16a50b6b3164107d45334eca74d73c052`; only authorized tests changed after the test-contract disposition. No PR #222 source was incorporated. Existing canonical Fingerprint UI and the entire other historical JS prefix remain byte-frozen by the amended test.

## Completed focused verification

| Execution | PASS | FAIL | SKIP | Evidence |
| --- | ---: | ---: | ---: | --- |
| Linux affected focused set | 191 | 0 | 0 | linux-focused.xml |
| Windows same affected set | 191 | 0 | 0 | windows-focused.xml |
| Additional strict no-sidecar contract (Linux) | 0 | 1 | 0 | linux-wal-contract.xml |
| Additional strict no-sidecar contract (Windows) | 0 | 1 | 0 | windows-wal-contract.xml |

All 191 focused test IDs match literally across platforms. Full focused durations: Linux 10.04 s; Windows 33.66 s. The failing sidecar test was added AFTER the 191-case runs. Do not represent either XML as an all-green run including that new test; the five production files were unchanged throughout these runs.

Linux: Python 3.10.12 / SQLite 3.37.2 / Node v24.20.0.
Windows: Python 3.10.11 / SQLite 3.40.1. Windows Git history access used exact process-local GIT_DIR/GIT_WORK_TREE plus exact safe.directory; no global Git configuration was changed.

Linux compileall of all changed Python files: PASS. Windows compileall of the changed production Python files: PASS. Node --check: PASS. Working and isolated-staged git diff --check: PASS.

Focused command (same 11 modules on both platforms):

```text
python -m pytest
  tests/device_fingerprint/test_observed_hints.py
  tests/device_fingerprint/test_read_service.py
  tests/admin_web/test_observed_device_hints.py
  tests/admin_web/test_observed_device_hints_frontend.py
  tests/admin_web/test_device_service_intelligence_frontend.py
  tests/admin_web/test_device_protocol_intelligence_frontend.py
  tests/admin_web/test_device_fingerprint_frontend.py
  tests/admin_web/test_device_fingerprint_presentation.py
  tests/admin_web/test_device_current_context_frontend.py
  tests/admin_web/test_query_service.py
  tests/admin_web/test_runtime.py
  -q -p no:cacheprovider --basetemp=<fresh external Lab directory>
  --junitxml=<external platform-focused.xml>
```

Additional executed exact ID:
`tests/device_fingerprint/test_observed_hints.py::test_A15_checkpointed_wal_read_must_not_create_new_sidecars`

## Test-contract exception: completed

The existing NI04 test strips only the uniquely delimited rich-hints addition (including its inserted line endings) and the single exact rendering invocation. Every other prefix byte still matches the unchanged historic commit. Six external-mutation canaries include the canonical Fingerprint function, title and invocation; ten malformed/duplicate/missing/reordered boundary cases reject invalid exceptions; one positive canary verifies the authorized addition only. Existing NI03 asset and NI04 lifecycle/runtime checks remain intact. No skips, xfails or broad normalization added.

## Implemented read / presentation

- One existing RO connection and one necessary-column SELECT, exact Site/canonical MAC, lower inclusive max(retention cutoff, known first-seen), upper exclusive pinned millisecond UTC as-of.
- ORDER BY observed_at DESC,evidence_id DESC LIMIT 256, using existing idx_df_evidence_site_mac_time. EXPLAIN, one SELECT, no SQL writes and connection closure checked by focused tests.
- SQL payload transfer cap 65,536 bytes; exact verify_persisted_payload plus frozen production registry; at most 256 validations; five ordered groups; response cap 65,536 bytes; all 40 schema-admitted TCP options retained.
- Latest bad/unsupported selected source is not silently replaced. Conservative Portal summary search stops at corrupt/unsupported required candidates; other sources remain independent.
- Portal model/OS have their own source/schema/quality/time, and platform only comes from the exact OS-major record. No classifier or Controller synthesis.
- Authenticated Site/device resolution precedes the optional read, sharing the actual deadline object/slot. Exhausted/too-small remaining busy budget skips the optional read safely. Missing/corrupt/busy/permission failures preserve the core HTTP 200 card and canonical fingerprint.
- DOM tests cover five ordered groups, historical timestamps, literal markup through text nodes, false/zero/null and all 40 structured options. Native collapsed details and existing wrapping classes used. No new fetch/polling or CSS changes.

## New confirmed contract blocker — native SQLite RO sidecars

Base Architecture v1 §3.1 says the new method uses the existing `open_read_only()` and does not create DB/WAL. The existing helper is outside the five-file production allowlist and is unchanged.

On BOTH platforms, after normal writer shutdown of a WAL-mode synthetic evidence DB, only the 69,632-byte main database remains. Opening through the existing helper and executing one ordinary SELECT creates:

```text
synthetic.sqlite3-wal       0 bytes
synthetic.sqlite3-shm   32768 bytes
```

The new optional read does exactly the same. Main database bytes remain identical. This is native SQLite WAL coordination behavior, not an INSERT/UPDATE, checkpoint, migration or app-created database. A separate helper-only reproduction confirms it is not introduced by the new selection/projection logic.

Reproduction script: `wal_boundary_probe.py` (disposable synthetic databases only), executed with both qualified interpreters. It checks both the unchanged helper alone and the new read. The new explicit no-sidecar test fails on both platforms without skip/xfail or weakened assertions.

**Required Tech Lead/Architect disposition:** clarify whether native SQLite coordination-sidecar creation by the mandated mode=ro helper is permitted, while main DB content, WAL frames, schema and durability stay unchanged. If strict no-file-creation is mandatory, provide an approved safe reading boundary / scope disposition. Coder has NOT changed the helper, pragmas, locks or permissions, used immutable on an active WAL, copied the database or silently hidden retained observations.

## Pending gates / limitations

- A15 strict no-WAL-creation: BLOCKED by the reproduced contract conflict; not PASS.
- Final measured query/fetch/parsed-byte/DTO caps and p50/p95 file-backed Lab report: pending disposition. Existing deterministic SQL/cap tests pass; not an independent HDD performance acceptance.
- Real browser narrow-screen/keyboard screenshots: pending; current frontend evidence is real Node + synthetic DOM, not a browser screenshot.
- Full Project/Central/security/performance acceptance: Tech Lead only; NOT RUN by Coder.
- No P0/P1=0 or final acceptance claim. Existing read-only-vs-sidecar semantics require a bounded decision first.

COMMIT=NO
PUSH=NO
PR=NO
MERGE=NO
DEPLOY=NO
PRODUCTION_ACTION=NO

Preserve the dirty draft. No cleanup, source workaround, rollback or production activation is authorized by this handoff.
