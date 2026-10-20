# CaptivPortal — TASK-TEST-GATE-PLATFORM-COMPAT-01

**Title:** Windows/Linux full-regression baseline repair and explicit POSIX test routing  
**Version:** v1.0 / 2026-10-15  
**Issuer:** Tech Lead (Optimization)  
**Requested by:** Owner  
**Execution mode:** `implementation` — repository test and test-support changes only  
**Coder responsibility:** implementation + focused/minimal local tests **only**  
**Independent full gates, official Central Lab runner, acceptance:** Tech Lead / Owner  
**GitHub publication / merge / deploy:** **NOT AUTHORIZED** by this TASK. Publication requires later exact-tree acceptance + separate GO.  
**Relationship to QIO-01A:** **independent TASK**; do not alter QIO-01A accepted candidate, feature PR, source, test or its tree.

## 0. Objective and why this TASK exists

Stop repeating the same failed full-suite admission in every subsequent CaptivPortal/QIO release. Create a test contract where the **supported Windows full suite passes with zero failures** and the **Linux/POSIX full suite passes with zero failures**, while genuinely Linux-only safety assertions still execute under Linux. This is a **test-platform repair**, not authorization to refactor application logic or make a failed test disappear.

This TASK corrects three problems:

- 238 inherited native-Windows failures due to Linux/POSIX I/O and one platform-dependent fixture;
- four observed Linux full-suite failures: two brittle SQLite `EXPLAIN` planner assertions, one timing-sensitive Current State worker assertion, and one AF_UNIX temporary path too long;
- outdated acceptance documentation/routing that permits these same baseline failures to recur.

The **official** Windows runner's local allowlist/path admission defect belongs to Tech Lead / Owner, **not Coder**; §7 defines the handoff and the separate acceptance action.

## 1. Verified source/baseline and evidence

Historical reproduction baseline (the QIO-01A pre-publication parent):

```ini
BASE_HEAD=7e84bc563f1b6dd3d72da66ae25849d9a7d96540
BASE_TREE=ea664b1d49ace86fc8a0c4ab2fc52945531e574a
QIO01A_ACCEPTED_TREE=301e5fd934e92162a868315775a1646711ba8fab
WINDOWS_BASELINE=7956_PASS_238_FAIL_34_SKIP
WINDOWS_QIO01A=7996_PASS_238_FAIL_34_SKIP
WINDOWS_DIFFERENTIAL=ZERO_NEW_FAILURES
LINUX_QIO01A=8263_PASS_4_FAIL_1_SKIP
```

All 238 Windows failures were independently paired by test identity + normalized root-cause category against the pristine baseline; no candidate-only failures:

| Family | Cases | Observed source family |
| --- | ---: | --- |
| Native Windows lacks `os.pread` | 168 | `tests/network_metadata` source/worker/storage tests |
| Native Windows lacks `os.O_NONBLOCK` | 63 | `tests/network_metadata` file-source/nonblocking contracts |
| Native Windows lacks `fcntl` | 2 | `tests/network_metadata` writer lock / CLI |
| WinError 32 (rename/remove open file) | 3 | `tests/network_metadata/test_service.py` |
| Linux-specific service CLI fails on Windows | 1 | `tests/network_metadata/test_cli.py::test_enabled_clean_stop_and_signal_binding` |
| Windows path validation masks intended scope error | 1 | `tests/network_metadata_projection/test_external_peer_v2.py::test_synthetic_scope_fixture_canonical_identity_and_disabled_boundary` |
| **Total** | **238** | |

Linux full exceptions observed in WSL:

1. `tests/analytics/test_historical_traffic_peak.py::test_peak_projection_reuses_one_materialized_requested_range_validation` — exact `EXPLAIN` text `MATERIALIZE validated_cycles` absent on installed SQLite planner.
2. `tests/analytics/test_historical_traffic_statistics.py::test_combined_projection_materializes_one_expensive_validation_path` — same planner variance.
3. `tests/current_state/test_workers.py::test_background_schedule_is_fixed_delay_not_overlap` — under full-suite load the fixed `time.sleep(0.13)` / exact two-callback count is timing-sensitive. It passes in isolated baseline and candidate runs.
4. `tests/visitor_registry/test_device_registry.py::test_unix_socket_source_candidate_is_ignored` — `AF_UNIX path too long` when full pytest uses a long `--basetemp`. It passes in both baseline and candidate with short `/tmp` path.

The two planner failures reproduce on both pristine Linux baseline and QIO-01A candidate with isolated execution. Current State and AF_UNIX pass on both in the same short-path focused run. These are *baseline/test-harness phenomena*, **not demonstrated defects of QIO-01A**.

Supporting Tech Lead files: `QIO-01A-WINDOWS-GATE-TRIAGE-2026-10-15.md` and `QIO-01A-TECHLEAD-ACCEPTANCE-DISPOSITION-2026-10-15.md`. The raw logs are on the Owner Central Lab at:

```text
C:\CaptivPortal-Lab\logs\qio-01a-techlead-independent-v7-equivalent-20261015.log
C:\CaptivPortal-Lab\logs\qio-01a-techlead-baseline-strict-comparison.log
C:\CaptivPortal-Lab\logs\qio-01a-techlead-linux-full-20261015.log
```

Windows PowerShell redirect produced UTF-16LE logs; decode those as `utf-16` when parsing.

### Baseline pinning for this new TASK

At implementation start, Coder must refresh/read `origin/main`, record exact HEAD/TREE and identify whether QIO-01A was merged. Create an **independent clean worktree and branch** from the latest Owner-approved baseline. Do **not** use the QIO-01A worktree, an acceptance-only commit, or a dirty/UI worktree. The above SHAs are **reproduction identities, not permission to override newer main**. On baseline drift or concurrent modification of affected tests, stop and request Tech Lead reconciliation; do not silently rebase.

## 2. Permitted scope

**Candidate repo paths:** minimum subset of:

- `tests/network_metadata/**` — platform-specific test markers/fixtures and real cross-platform tests;
- `tests/network_metadata_projection/test_external_peer_v2.py` — scope fixture only;
- `tests/analytics/test_historical_traffic_peak.py` and `tests/analytics/test_historical_traffic_statistics.py` — two planner-sensitive regression checks;
- `tests/current_state/test_workers.py` — deterministic fixed-delay test;
- `tests/visitor_registry/test_device_registry.py` — AF_UNIX test-scoped short socket path;
- `tests/conftest.py` or a narrowly scoped support helper, and `pytest.ini` **only if needed** for an explicit, reviewable capability marker;
- `docs/testing.md`, `docs/testing-environments.md` **only for the exact resulting gate contract**.

**Forbidden without a new Tech Lead/Architect decision:** changes to `app/**`, production code, SQL query/runtime logic, schemas, config defaults, `run.py`, `systemd`, Omada, durability/checkpoint/cursor/replay semantics, QIO-01A files, dependencies, CI deployment or production assets. No changes to external `C:\CaptivPortal-Lab\lab-test-v7-strict.cmd` from Coder; this is controlled by Tech Lead/Owner.

Use the smallest modifications that satisfy the explicit contract. Each touched existing test must retain its intended security/integrity/performance property.

## 3. Implementation contract A — Windows vs POSIX test selection

### A1. Diagnose and label **only** truly POSIX-required tests

The Network Metadata reader uses `os.pread`, `os.O_NONBLOCK` and `fcntl`; several tests additionally require POSIX semantics for source file replacement while an fd is open. These **must be tested on Linux**. Do **not** introduce fake/monkeypatched Windows implementations of `pread`/`fcntl` or alter production behavior simply to make Windows pytest green.

- Build an explicit inventory of impacted test IDs (including parameter variants) and mark those requiring POSIX kernel/file-descriptor semantics with *narrow* `pytest.mark.skipif(os.name != "posix", reason="Linux/POSIX Network Metadata I/O contract")`, or an equivalently reviewable named pytest capability marker whose evaluation is explicit. Prefer **test-function-level** declaration; a module-level mark is allowed only with evidence **every test in that module** requires POSIX behavior. Do **not** blanket-skip `tests/network_metadata` or entire projection suites: disabled-mode, parsing, validation and other platform-neutral assertions remain active on Windows.
- For the three WinError 32 cases, retain actual file-handle/replacement semantics on Linux; route only truly unsupported platform cases, not all related service tests.
- Explicitly keep tests that are cross-platform running under both systems; if a failing test can be repaired with portable test-only setup and retain its assertion, **prefer repair over skip**.
- Every Windows platform skip must have an explicit reason and corresponding Linux execution evidence in the final gate report. Count and inventory skips; **no global deselect**, `pytest_ignore_collect`, broad `-k` filtering, catch-all conftest hook, skip-all/xfail-all or environment-driven concealment.
- Add minimal focused validation where necessary to show: pure Network Metadata tests remain runnable on Windows; POSIX-only tests are collected but explicitly skipped on Windows, and **execute normally on Linux**.

### A2. Fix cross-platform projection fixture (do not skip)

`tests/network_metadata_projection/test_external_peer_v2.py::test_synthetic_scope_fixture_canonical_identity_and_disabled_boundary` expects `ProjectionConflict("scope_admission_untrusted")`, but native Windows rejects a default POSIX-form database path first (`ProjectionValidationError` from `Path.is_absolute`). Supply **valid, distinct, platform-native absolute temporary database paths** for every enabled-mode path involved, so the intended missing/untrusted scope admission check is reached on Windows and Linux. Keep the disabled-mode no-side-effect test and `scope_admission_untrusted` assertion intact. Do not relax the production path validation.

### A3. Preserve strict V7 historical regression invariants

The **six formerly tolerated Windows compatibility cases** must continue to execute as ordinary strict tests; they are not to be added to the POSIX skip set:

- SQLite infinity edge;
- Node retry async timing;
- Visitor Registry long audit;
- Visitor Registry previous-ready;
- Visitor Registry previous-stopping;
- Home Health unavailable analytics baseline.

No `xfail`, no removing assertions, no mass conditional skip, no ignored failures. Required Windows outcome: `0 failed / 0 error`, with only individually justified actual-platform skips recorded. Existing 34 legitimate skips are not evidence that newly invented skips are acceptable.

## 4. Implementation contract B — Linux full-suite stability

### B1. Two Analytics SQLite plan tests

`tests/analytics/test_historical_traffic_peak.py` and `tests/analytics/test_historical_traffic_statistics.py` currently require the literal `MATERIALIZE validated_cycles` exactly once; on the Linux SQLite planner this node can be absent despite existing `candidate_cycles`, `cycle_aggregates`, required indexes and result equivalence.

- First capture both raw plans, SQLite/Python versions and explain the planner transformations; compare the intended expensive validation work with its actual implementation. Determine whether it was genuinely duplicated or merely inlined/optimized in a version-specific plan.
- Repair the tests **without discarding their regression protection**: ensure the expensive requested-range integrity/validation path is not duplicated; index use remains checked; shared-vs-separate workload and returned results remain correct. Do not simply delete the two `validated_cycles` assertions, replace them with tautology or unconditional `0 or 1`, or skip by SQLite version. A planner-independent invariant (possibly combined with a bounded execution/semantic probe) is preferred, but must *actually establish* the non-duplication property.
- If the current plan makes that property impossible to prove without changing application SQL, **HOLD B1 and raise the precise evidence and minimal proposal to Tech Lead/Architect**. Product SQL mutation is not authorized by this TASK.

### B2. Current State background scheduling test

`tests/current_state/test_workers.py::test_background_schedule_is_fixed_delay_not_overlap` uses a 30 ms blocking provider, a 40 ms interval, `time.sleep(0.13)` and expects exactly two callbacks. Under full-suite CPU/IO contention it sometimes observes one.

Replace wall-clock scheduling guesswork with deterministic, bounded coordination (`threading.Event`, synchronization hook or controlled scheduler/clock as supported by existing code). Keep these *observable* assertions: no overlapping cycle invocation; after cycle completion there is a positive fixed delay before the next cycle; stop terminates properly, without duplicate/late calls or leaked threads. Bounded waits for synchronization are permitted; arbitrary sleep-padding/retry-until-green is not. Avoid altering worker runtime and config unless separately authorized.

### B3. Visitor Registry UNIX socket path length

`tests/visitor_registry/test_device_registry.py::test_unix_socket_source_candidate_is_ignored` should still create a **real AF_UNIX socket** and assert reader ignores it. Use a test-controlled *short*, safe, disposable directory/path for the socket independent of pytest's potentially long `--basetemp`; preserve trust/path constraints and ensure cleanup even on failure. Do not skip on Linux, fake a socket, or weaken the reader's safety check. Keep the existing skip for non-POSIX or missing `AF_UNIX`.

## 5. Coder's allowed focused checks

Coder executes **only focused tests for the test files/functions changed in this TASK** and appropriate static checks. Suggested narrow sets are: (a) a handful of POSIX-only and cross-platform Network Metadata examples; (b) the one projection fixture; (c) the two Analytics plan tests; (d) the Current State timing test, multiple times; and (e) the AF_UNIX socket test. A Coder local Linux/Windows targeted run of **the changed tests** is permitted. Record exact platform, Python, SQLite, pytest and path.

Coder **must not** independently run unrelated modules, full repo pytest, Windows official V7, full Linux suites, broad cross-module/differential or PERF/release gates. Tech Lead conducts those. If B1 cannot be fixed without possible performance-contract change, stop that part and return evidence; complete the independent safe parts.

Coder supplies a full patch, new file inventory and a handoff showing source baseline/HEAD/TREE, changed paths, targeted commands/results, platform routing skip rationale, SQL plan evidence, thread/socket cleanup proof and the precise remaining gates. **No commit/push/PR/merge/deploy** unless separately approved following Tech Lead acceptance.

## 6. Independent acceptance owned by Tech Lead / Owner

After Coder's patch handoff, Tech Lead independently materializes the exact candidate tree in clean Windows and WSL/Linux Lab worktrees and performs:

1. **Windows full strict pytest:** `0 failed, 0 error`; all platform skips individually justified and reported; six historical strict V7 cases remain executed; no default blanket exclusion. Record actual collected/passed/skipped/deselected counts and list.
2. **Linux full pytest:** `0 failed, 0 error`; at most the separately documented opt-in benchmark skip (`tests/analytics/test_api_performance.py`) if unchanged; **every Windows-skipped POSIX Network Metadata case executed under Linux**. Check that no intended coverage was silently lost. No automatic acceptance of the four earlier Linux failures.
3. Repeat the Current State fixed-delay test under both light and contended conditions; repeat AF_UNIX with both short and intentionally long pytest temp roots (test's own socket path stays short). Verify no worker/thread/file descriptor leaks.
4. Verify both Analytics expensive-validation assertions remain materially protective (deliberate negative/mutation case or equivalent independent oracle/plan-analysis evidence); compare important source-output and query characteristics to baseline. No weakening of workload protections for a purely cosmetic green suite.
5. Verify `git diff --check`, `compileall`, exact tree, clean worktrees, changed-file allowlist, no production code/config changes, and documentation/test-set inventory.
6. **Official Central Lab gate:** Tech Lead/Owner, not Coder, separately repair/review the machine-local runner's safe worktree allowlist/path admission and issue a newly checksummed/versioned runner or an Owner-reviewed safe equivalent. Keep strict four steps (full pytest, compileall, diff, immutability), current-main ancestry, artifact identity and safety checks. Never silently edit the approved V7 file and continue calling it the old checksum.
7. If a later `main` includes QIO-01A while this TASK was developed against its earlier parent, reconcile the exact tree/parent under Tech Lead control, then repeat affected gates on the accepted tree.

**No acceptance on just a zero-exit pytest created by deleting/skipping meaningful tests.** Zero failures **plus retained coverage plus exact evidence** is the acceptance criterion.

## 7. Ownership and publication gates

```ini
CODER_WORK=REPO_TESTS_AND_TEST_SUPPORT_ONLY
CODER_TEST_SCOPE=FOCUSED_CHANGED_TESTS_ONLY
TECHLEAD_TEST_SCOPE=WINDOWS_FULL_LINUX_FULL_DIFFERENTIAL_STABILITY
OFFICIAL_WINDOWS_RUNNER_OWNER=TECHLEAD_AND_OWNER
QIO01A_SOURCE_CHANGES=FORBIDDEN
PRODUCTION=FORBIDDEN
COMMIT=NO
PUSH=NO
PR=NO
MERGE=NO
DEPLOY=NO
```

This TASK is authorized **to implement** in an isolated worktree. It does not authorize publication, merge, system changes, official runner changes or tests on production. When the full gates pass and the exact tree is accepted, Tech Lead will issue a separate **commit → push → Draft PR** instruction; Owner performs merge. Owner's one-time QIO-01A acceptance exception is **not** transferred automatically to this TASK or future QIO acceptance.

## 8. Required Coder handoff format

Return:

```ini
TASK=TASK-TEST-GATE-PLATFORM-COMPAT-01
IMPLEMENTATION_BASE_HEAD=
IMPLEMENTATION_BASE_TREE=
CANDIDATE_TREE=
WORKTREE=
CHANGED_FILES=
FOCUSED_WINDOWS=
FOCUSED_LINUX=
WINDOWS_POSIX_SKIP_INVENTORY=
LINUX_CORRESPONDING_TEST_EXECUTION=
ANALYTICS_PLAN_EVIDENCE=
CURRENT_STATE_TIMING_PROOF=
AF_UNIX_SHORT_PATH_PROOF=
DIFF_CHECK=
COMPILEALL=
COMMIT=NO
PUSH=NO
PR=NO
MERGE=NO
DEPLOY=NO
PRODUCTION_ACTION=NO
INDEPENDENT_GATES=PENDING_TECHLEAD
```

Any unresolved conflict in the source contract, particularly B1 query-plan non-duplication, is a **specific HOLD**, not an invitation to weaken assertions or silently expand product code scope.
