# CaptivPortal — QIO-05 P2 / Independent Tech Lead Review

**Date:** 2026-10-17 (Asia/Baku)  
**Review scope:** synchronous atomic `SensorSpool.enqueue` for existing lists, LAB-only  
**Production / merge / deploy:** NOT AUTHORIZED

## Frozen candidate identity

- Repository `ZaurNavi/CaptivePortal`.
- Parent HEAD: `cd83c3e04233593126d247b0c96c1135f4233072`.
- Parent TREE: `86a2e005b2d250b9580f1e76a80b380d1d69a635`.
- Candidate TREE independently reproduced using isolated Git index: `a9ea6dbf7a19a843e34882ba68f70c8ff2b67d92` on Linux and Windows Git.
- Original patch SHA256: `cd79f05033aa425f3f6bffe52f3641c75657641ad448bdc56e937ce3d8f5816f` (23,173 bytes), independently verified.
- Candidate worktree has only three modified files: `app/device_fingerprint_sensor/spool.py`, `tests/device_fingerprint_sensor/test_spool.py`, `tests/device_fingerprint_sensor/test_runtime.py`. No commit/push/PR/merge/deploy.
- Source SHA256 independently verified for all three candidate files against handoff. `git diff --check` PASS. Existing Coder worktree and real index unchanged by Tech Lead.

## Handoff evidence integrity

- ZIP `QIO05-P2-LAB-20261017.zip`: 874 file entries, no duplicate names, 872/872 listed internal SHA256 entries verified independently.
- ZIP includes a byte-identical copy of patch, JUnit XML/logs for both focused suites, provenance, execution ledger, raw syscall traces, and fault evidence.
- Coder focused suites: Linux 97 PASS / 0 FAIL / 0 SKIP; Windows 97 PASS / 0 FAIL / 0 SKIP; 97/97 test IDs match.
- All 272 declared Coder research executions have returncode 0, consisting of 256 ordinary A/B processes and 16 fault-traced processes. An exit-zero fault probe represents expected error/rollback validation, not a successful application insert.
- For each gate (ON/OFF), baseline failure at second / last proposed row leaves 1 / 2 durable survivors; candidate leaves 0 / 0. Synthetic results independently verified from raw `fault-evidence.json`.

## Production source change assessment

**PASS at source-review level:** only 3 lines added, 1 deleted in production source. The code checks the cardinality of the already-materialized incoming list and calls existing `_insert_coalesced_rows` when there are >=2 elements. This existing helper performs explicit `BEGIN IMMEDIATE`, `INSERT OR IGNORE` loop, `COMMIT`, rollback and connection-discard on unrecoverable rollback, and post-commit memo update. A singleton continues its original immediate path. No cross-request memory buffer, new background worker, changed SQLite PRAGMA, changed `IngressCoalescer`, NI-02A or source-health contract. This complies with Chief Architect QIO-05 P1 A6 allowance for **synchronous bounded existing-list batching** and respects prohibition of pre-durable volatile acceptance.

**Explicit semantics change on failure:** old autocommit could persist the first N rows when a later row failed. The candidate makes the new proposed list all-or-nothing; previously committed retention/capacity housekeeping remains independently durable, as stated in handoff. A post-COMMIT lost response can still result in durable rows; retry is idempotent by event identity. Code review and supplied failure tests support this intent. Generalized power-loss hardware validation is not claimed.

**Performance, LAB only:** for 8 synthetic events, `pwrite64 208 -> 26`, total `fdatasync 32 -> 4`; for single-event input, syscall results are unchanged. For 100-event fixture, reductions are larger. These are WSL/SSD syscall numbers, **not physical HDD write savings**. Frequency of multi-event submissions in production is not measured.

## Independent full-gate execution

### Linux

**PASS:** 8,474 PASS / 130 SKIP / 0 FAIL, 12 warnings, 1,079.38 s. Original exact LAB candidate. JUnit independently parsed: 8,604 unique test IDs, 0 failures, 0 errors, 130 skips; all 97 focused IDs present. No test/source edits or xfail/skip injection; `-x`, `-p no:cacheprovider`, external basetemp and pycache. Evidence: `C:\CaptivPortal-Lab\tmp\qio05-p2-tl-linux-full-20261017.xml` and `.log` on authorized Windows test workstation.

### Windows

**PASS:** 8,195 PASS / 409 SKIP / 0 FAIL, six warnings, 1,198.10 s, return code 0. Exact original WSL candidate content imported by native Windows Python 3.10.11 with Git-history lookups provided through a separate Windows Git object store, using `GIT_DIR` and `GIT_WORK_TREE` environment variables. No test, production source, assertion or platform skip rules changed. Evidence: `C:\CaptivPortal-Lab\tmp\qio05-p2-tl-windows-unc-git-full-20261017.xml` and `.log`, plus script `qio05-p2-tl-windows-unc-git-full-20261017.ps1` on the authorized workstation.

**Environment troubleshooting, retained without suppression:** (1) Direct native Windows Git from the WSL-linked worktree failed historic `git show` at 176 PASS (`git` exit 128). (2) An independent Windows-native cloned checkout checked out protected SVG text with CRLF, failing a source-byte SHA256 invariant after 1,208 PASS. These are actual test-environment failures, not considered passing regression gates. (3) Exact WSL candidate bytes + independent Windows Git object store passed seven targeted historical-Git/SVG controls, then the entire Windows suite above. Full source SHA256 remains exact for the original candidate; changes to the private Windows test clone did not change the source worktree.

### Independent cross-platform JUnit reconciliation

- Both Linux and Windows collected **8,604 test cases**, with no failures or errors.
- **8,602 test IDs match literally**. Two IDs on each platform differ only in runtime-generated UUID parameter values under `tests/device_fingerprint_integration/test_executor_persistence.py::test_explicit_classification_id_rejected_without_change_to_default`; both parameterizations are PASS on both platforms. Do not claim 8,604 literal ID equality.
- All **97/97** handed-off focused IDs occur as PASS in **both** independent full suites.
- Exactly 130 skips are shared across platforms. An additional 279 Windows skips correspond to Linux PASS, i.e. the expected platform-dependent eligibility, not new candidate skip edits. Source skips/xfail were not modified.
- Independent pairing artifact: `C:\CaptivPortal-Lab\tmp\qio05-p2-tl-cross-platform-final-20261017.json`.
- Post-test original LAB candidate still reports HEAD and origin/main both `cd83c3e04233593126d247b0c96c1135f4233072`, same three modified files and the same source SHA256; `git diff --check` returns success.

## Open release gates

- Formal release/deploy authority remains with Owner. No application or production setting has been changed.
- Windows full is independently recorded as PASS on the exact candidate source.
- Canonical Windows V7 runner was not invoked; direct independent full runs are not represented as official V7. If formal V7 is mandatory for merge, complete it separately in a supported isolated worktree.
- `PRODUCTION_PHYSICAL_HDD_SAVINGS_BOUND=NOT_QUANTIFIABLE`; before merge/deploy, distinguish code correctness from operational benefit and preserve existing rollback/Owner change control.

## Current directive

**TECHNICAL VERDICT = LAB PASS; OPEN P0=0; OPEN P1=0 within the reviewed source/contract scope.** Independent Linux and Windows full suites passed; candidate source, frozen tree and patch agree.

**CODER PUBLICATION PREPARATION = GO, conditional on unchanged `origin/main` and Owner's established publication authority.** Coder may create a **new clean publication branch/normal commit** based on `main@cd83c3e04233593126d247b0c96c1135f4233072`, apply exactly the approved 23,173-byte patch with SHA256 `cd79f05033aa425f3f6bffe52f3641c75657641ad448bdc56e937ce3d8f5816f`, and verify that the resulting source tree is exactly `a9ea6dbf7a19a843e34882ba68f70c8ff2b67d92`, with only the three authorized file differences. Preserve this independent QA report and both complete JUnit suites in the PR evidence. If `main` or patch/tree diverges, stop and return for Tech Lead review. Do not publish the dirty LAB worktree as a commit, do not silently expand scope or waive the official V7 requirement.

**MERGE / DEPLOY / SYSTEMD RESTART / PRODUCTION CONFIG = NO.** Owner alone authorizes merge/production actions. The official canonical V7 gate, if non-waivable, remains to be separately satisfied before merge. Neither LAB syscall reduction nor QA PASS establishes a numerical production HDD benefit.
