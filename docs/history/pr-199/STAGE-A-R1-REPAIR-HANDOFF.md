# TASK-TRAFFIC-PARTIAL-COVERAGE-01 — Stage A R1 repair handoff

This is the replacement source-review handoff for the bounded P1-01/P2-01 repair requested in `TASK-TRAFFIC-PARTIAL-COVERAGE-01-STAGE-A-TECHLEAD-REVIEW-R1.md`. Owner explicitly authorized this repair in the current chat. Architecture R3 is unchanged. Stage B remains HOLD.

This document and the `STAGE-A-R1.patch` replace the earlier candidate identity/patch for review. Earlier handoff, patches, logs and baseline diagnostics are retained as historical evidence; they were not overwritten.

## Exact candidate / local actions

```text
BASE_HEAD=e8061de9fbd6da8be5cd269779070a4db4d59d64
BASE_TREE=d5503fe1f2b5774bbe55cb2d34dba63246f56f6f
REVIEWED_PREDECESSOR=ade49a171637029f596fe019e73063ce8af76383
REVIEWED_PREDECESSOR_TREE=383cf2f1ca2a510811b66f9f4d96c9235f6b24b4
LOCAL_REVIEW_COMMIT=39abf52e71f744183297b5a57bfd098845487a2e
PARENT=ade49a171637029f596fe019e73063ce8af76383
CANDIDATE_TREE=efc6effbc45da1ce3ed61f7c9b7a17549b34f390
BRANCH=feature/traffic-partial-coverage-01
WORKTREE=C:\CaptivPortal-Lab\coder-traffic-partial-coverage-01
WORKTREE_CLEAN=YES
```

The local history is BASE -> reviewed Stage A commit -> bounded repair review commit. No amend, rebase, merge, push, PR or history rewrite was performed in this round. The repair is a local immutable review candidate, not an accepted publication/release commit.

## Exact repair scope

Relative to the reviewed predecessor: **4 files, 149 insertions, 3 deletions**.

| File | Bounded repair |
|---|---|
| `app/analytics/current_traffic.py` | Handle expected SQLite / OS status-only storage failures without erasing valid Observation measurements; explicitly propagate SQLite programming/interface failures; retain deadline check. |
| `app/analytics/source_gateway.py` | Reuse Observation `MAX_AP_ROWS=10000` as a read-side pre-materialization cap. |
| `tests/analytics/test_current_partial_coverage.py` | Fourteen parameterized regression cases for storage errors, deadlines, programming errors and hard-cap behavior. |
| `tests/admin_web/test_current_partial_coverage.py` | Six real HTTP regressions for locked/OS status failures across the three current routes. |

No other predecessor source file changed during this repair. No unrelated formatting, dependency/config/schema/writer changes or Stage B work.

## P1-01 — status storage failure isolation

The existing default `CurrentApStatusEvidenceV1(site)` remains unavailable when the status read fails with expected `CurrentStateStorageError`, `CurrentStateSchemaError`, `CurrentStateValidationError`, SQLite storage error or OS I/O/open error. No status evidence or Offline exclusion is inferred.

`sqlite3.ProgrammingError`, `sqlite3.InterfaceError` and arbitrary programming exceptions propagate. Request deadline exceptions are not caught. The mandatory `deadline.require_remaining()` immediately after the boundary also rejects an expired SQLite-interrupted read. No deadline extension or retry was added.

Exact proof:

- `test_R1_P1_status_storage_failure_preserves_measured_partial` (5 cases): real Current State read service with locked/malformed SQLite, permission, absent-file and OS open failures. AP1..AP3 retained 18 down / 3 up / **21 total Mbps**; `partial_measured`, `measured_only`, `status_evidence_unavailable`, `offline_excluded_ap_count=0`; AP4 is not excluded.
- `test_R1_P1_status_timeout_is_not_partial_fallback` (2 cases): direct timeout and SQLite interruption at deadline both raise `AnalyticsQueryDeadlineExceeded`.
- `test_R1_P1_status_programming_error_is_not_swallowed` (3 cases): RuntimeError and SQLite programming/interface errors remain visible.
- `test_R1_P1_status_open_failure_is_safe_partial_200` (6 cases): all three current HTTP routes return safe partial 21 Mbps rather than 503; raw status-storage error details are absent from JSON.
- Existing aligned-fresh AP4 incident remains `complete_online_population` / 21 Mbps / one confirmed Offline exclusion; the previously accepted AP4 recovery, strict and History tests remain in the focused suite.

## P2-01 — independent bulk-read bound

`AnalyticsSourceGateway.read_current_partial_traffic_evidence()` performs the existing coherent count under its shared SQLite deadline, then rejects `count > MAX_AP_ROWS` before `_all()` can materialize rows. `MAX_AP_ROWS` is imported from the existing Observation configuration; no new limit/config, writer change, index, schema or worker.

Rejection returns an empty row set with the actual count and candidate metadata. Existing structural validation yields safe `unavailable` / `source_integrity_unavailable` / null numeric aggregate. It does not truncate, silently choose an older cycle or fabricate zero. Public pagination remains capped at 250 and is not mistaken for the coherent-read limit.

Exact proof:

- `test_R1_P2_oversized_count_never_materializes_rows` (2 cases): matching metadata/count 10001 and 1000000000; `_all()` must not be called; an older valid candidate is not reused.
- `test_R1_P2_retained_rows_at_hard_limit_and_above` (2 cases): actual disposable persisted cycles at 10000 and 10001 rows. At 10000: measured 30000 Mbps, all 10000 valid pairs, SQL row fetch bounded at 10001, page 250 with cursor and exact same aggregate context. At 10001: no bulk row fetch and no numeric aggregate.

## Full BASE-to-candidate inventory

**18 files: 1638 insertions, 26 deletions.**

Modified production files (14):

1. `app/admin_web/config.py` — separate default-OFF current-mode flag.
2. `app/admin_web/current_traffic_serialization.py` — closed current/page DTO serialization.
3. `app/admin_web/query_service.py` — explicit opt-in current dispatch and status boundary.
4. `app/admin_web/routes.py` — three current routes, existing ACL/deadline/response limits.
5. `app/admin_web/static/admin.js` — current-only validation and presentation.
6. `app/admin_web/templates/admin/home.html` — current flag/context.
7. `app/admin_web/templates/admin/traffic.html` — current flag/context.
8. `app/analytics/current_traffic.py` — immutable partial current/page behavior, population proof and bounded P1 repair.
9. `app/analytics/models.py` — current/page DTOs.
10. `app/analytics/source_gateway.py` — coherent read-only current evidence and bounded P2 repair.
11. `app/config.py` — default-OFF flag.
12. `app/current_state/models.py` — immutable status-evidence DTO.
13. `app/current_state/read_service.py` — bounded, prior, aligned status evidence; unchanged in this repair.
14. `app/settings.py` — existing flag propagation.

New tests (3):

15. `tests/admin_web/test_current_partial_coverage.py`
16. `tests/analytics/test_current_partial_coverage.py`
17. `tests/current_state/test_ap_status_evidence.py`

Existing directly affected fixture (1):

18. `tests/admin_web/test_web_ux_pack_02.py` — prior accepted synthetic legacy fixture `global.partialMode=false`; unchanged in this repair.

## Verification actually performed

Environment: Windows PowerShell; Python **3.10.11**, `C:\CaptivPortal-UI-Preview\.venv\Scripts\python.exe`; Node **v24.19.0**. External `PYTHONPYCACHEPREFIX=C:\CaptivPortal-Lab\tmp\partial-coverage-pycache`, external disposable basetemp/log/XML paths. No external network/Omada/production operations.

- All new Stage A modules including this repair: **94 passed, 0 failed, 0 skipped**, 85.07s. Log/XML: `C:\CaptivPortal-Lab\partial-coverage-review-r1-new-02.log` / `.xml`.
- Current / legacy / History / config / directly affected WEB-UX compatibility: **427 passed, 0 failed, 0 skipped**, 162.22s. Log/XML: `C:\CaptivPortal-Lab\partial-coverage-review-r1-focused.log` / `.xml`.
- `python -m compileall -q app tests/analytics/test_current_partial_coverage.py tests/admin_web/test_current_partial_coverage.py tests/current_state/test_ap_status_evidence.py`: PASS.
- `node --check app/admin_web/static/admin.js`: PASS.
- `git diff --check` and `git diff --check HEAD^ HEAD`: PASS.
- Replacement patch reverse-apply check: PASS. Check only; no application/repository mutation.
- Full ordinary local pytest on the clean immutable repair commit: **FAIL — 6618 passed, 186 failed, 36 skipped, 0 errors, 0 deselected**, 5 warnings, 1593.29s. Evidence paths: `C:\CaptivPortal-Lab\partial-coverage-review-r1-full.log` / `.xml`. Exact failed-ID set equals the 186 baseline failed IDs; **0 set differences / 0 new failed IDs**. All 427 focused cases and all 94 new Stage A cases are PASS in the full-run XML, with 0 skips/errors/failures in those subsets. This is the explicitly requested local full regression, **not** official V7/Central Lab or Linux acceptance.

Focused command (427):

```text
python -m pytest -q tests/analytics/test_current_partial_coverage.py tests/current_state/test_ap_status_evidence.py tests/admin_web/test_current_partial_coverage.py tests/analytics/test_current_traffic.py tests/analytics/test_current_traffic_runtime.py tests/current_state/test_read_service.py tests/admin_web/test_home_traffic.py tests/admin_web/test_home_traffic_frontend.py tests/admin_web/test_traffic_current.py tests/admin_web/test_traffic_current_frontend.py tests/admin_web/test_traffic_history.py tests/admin_web/test_traffic_history_frontend.py tests/admin_web/test_config.py tests/admin_web/test_web_ux_pack_02.py --basetemp C:\CaptivPortal-Lab\tmp\partial-coverage-review-r1-focused --junitxml C:\CaptivPortal-Lab\partial-coverage-review-r1-focused.xml
```

New modules command (94):

```text
python -m pytest -q tests/analytics/test_current_partial_coverage.py tests/admin_web/test_current_partial_coverage.py tests/current_state/test_ap_status_evidence.py --basetemp C:\CaptivPortal-Lab\tmp\partial-coverage-review-r1-new-02 --junitxml C:\CaptivPortal-Lab\partial-coverage-review-r1-new-02.xml
```

Full local command:

```text
python -m pytest -q -rs --basetemp C:\CaptivPortal-Lab\tmp\partial-coverage-review-r1-full --junitxml C:\CaptivPortal-Lab\partial-coverage-review-r1-full.xml
```

Implementation iteration transparency: first new-test run was **79 passed / 13 failed** because the newly written disposable fixtures used the wrong repository `_connect` keyword and wrong synthetic Site. Those fixture construction mistakes were corrected (no assertion weakening); three additional programming-error cases were added. The authoritative new run is 94 PASS above. First run retained at `C:\CaptivPortal-Lab\partial-coverage-review-r1-new-01.log` / `.xml`.

## Baseline / release limitations

Historical clean predecessor full run: **6598 passed / 186 failed / 36 skipped**. All 186 failed IDs were reproduced on exact clean BASE in four earlier differential batches (`C:\CaptivPortal-Lab\partial-coverage-baseline-failures-1.xml` through `-4.xml`). That diagnostic evidence remains retained, not relabeled as a fresh supported-platform gate.

Known baseline classes: 129 `os.pread`, 51 `os.O_NONBLOCK`, 2 `fcntl`, 3 Windows file sharing, 1 CLI exit assertion. All 11 source test files and protected NI production paths are unchanged. Comparison of exact JUnit classname + parameterized test name identities proves **186 baseline failed IDs = 186 current failed IDs, zero set differences**. This is an exact local failed-ID differential, not a universal assertion that every possible regression is excluded.

Full-run failure inventory (unchanged source test files):

| Module | Failed cases |
|---|---:|
| `tests/network_metadata/test_capacity.py` | 1 |
| `tests/network_metadata/test_checkpoint_crash.py` | 18 |
| `tests/network_metadata/test_cli.py` | 2 |
| `tests/network_metadata/test_health.py` | 18 |
| `tests/network_metadata/test_privacy.py` | 2 |
| `tests/network_metadata/test_read_service.py` | 3 |
| `tests/network_metadata/test_repository.py` | 25 |
| `tests/network_metadata/test_retention.py` | 31 |
| `tests/network_metadata/test_service.py` | 60 |
| `tests/network_metadata/test_source.py` | 5 |
| `tests/network_metadata_projection/test_projection_source.py` | 21 |

All 11 module blobs were checked against exact BASE and are identical. The diagnostic baseline worktree remains `C:\CaptivPortal-Lab\partial-coverage-baseline-20261011`, clean/detached at the exact base identity recorded above. The original baseline runs are historical diagnostics, not a new official gate.

## Retained verification-file identities

All following files are under `C:\CaptivPortal-Lab\`, outside the application repository. XML files retain exact per-case outcomes/IDs, including failure detail and skips.

| File | Bytes | SHA256 |
|---|---:|---|
| `partial-coverage-review-r1-new-02.log` | 193 | `b86971bdb7313b3b2f2fda9e89a46ed11198420f6fd8704e9aab81c2847ee638` |
| `partial-coverage-review-r1-new-02.xml` | 15927 | `5b07f772371d8f2c502a7458743e98887f32d85d4f5dbc054b0a99c62a3abaca` |
| `partial-coverage-review-r1-focused.log` | 519 | `cb53e6a05ca290a313dcaf4349fe71adf838a706030f1665a8e98367fccdb51f` |
| `partial-coverage-review-r1-focused.xml` | 68933 | `982a97a82e1706d55b03d145eceed5e51d9f82afa877f3e3cca7cb4f6bdade9e` |
| `partial-coverage-review-r1-full.log` | 361480 | `6d57cfad3ae18a02a4113d4a8d0725813b08abb4baac1a6195058c4c7994df3b` |
| `partial-coverage-review-r1-full.xml` | 1470568 | `45206d690514a26c2b771095ae51f36d305e55352aa3e52aaba4ce5ebfb008a7` |

No blanket waiver, custom skip/deselection or DRAFT platform-transfer plugin was applied. A failing Windows full run must be reported as FAIL. Independent supported Linux/Central Lab (or explicitly admitted platform-composite gate) and manual normal/mobile UI review remain required before release readiness. Neither was performed by Coder.

## Replacement patch

```text
PATCH_PATH=C:\CaptivPortal-Lab\artifacts\traffic-partial-coverage-01-stage-a\TASK-TRAFFIC-PARTIAL-COVERAGE-01-STAGE-A-R1.patch
PATCH_BYTES=129073
PATCH_SHA256=ca2fb88ac75ce3796c983921c8fe8f0c16afe5a2cf73b44992d43bf43370aa48
PATCH_REVERSE_APPLY_CHECK=PASS
```

This is the full binary/full-index BASE-to-current-candidate unified patch, not only the four-file repair delta. Generated from the committed immutable candidate. No diagnostic artifacts are tracked in the repository.

## Preserved boundaries / disposition

Feature remains `WEB_ADMIN_TRAFFIC_PARTIAL_COVERAGE_ENABLED=false` by default; `partial_v1` is explicit current-only opt-in. No-mode strict dispatch and History behavior are unchanged. Current UI, route, serialization, status read service and DTO bytes equal the reviewed predecessor.

Observation config/schema/repository/writer/worker, Current State schema/repository/collector/status classifier, Traffic Projection schema/repository/projector/writer, NI/Fingerprint, Guest/Session, Auth/CAPPORT/Portal and Omada calls are unchanged. No new runtime DB, worker, index, flag, backfill, retention or provider calls. Existing `MAX_AP_ROWS` is read/imported only.

No live AP cable/disconnection test, production DB copy, service command, feature activation, push, PR, merge or deploy. AP4 and large-cycle fixtures are disposable synthetic retained facts. No UI semantic change in this repair; no new screenshot/visual acceptance claimed.

Local known P1/P2 review items are corrected and focused-tested, but Stage A acceptance is **not** self-declared. STOP after handoff for Tech Lead R1 repair review; Stage B remains HOLD. Architecture ambiguity: NONE for this authorized repair scope.

## Result block

```text
TASK=TASK-TRAFFIC-PARTIAL-COVERAGE-01
STAGE=A_CURRENT
REPAIR=P1_01_AND_P2_01_ONLY
BASE_HEAD=e8061de9fbd6da8be5cd269779070a4db4d59d64
BASE_TREE=d5503fe1f2b5774bbe55cb2d34dba63246f56f6f
IMPLEMENTATION_COMMIT=39abf52e71f744183297b5a57bfd098845487a2e
IMPLEMENTATION_TREE=efc6effbc45da1ce3ed61f7c9b7a17549b34f390
PARENT=ade49a171637029f596fe019e73063ce8af76383
WORKTREE_CLEAN=YES
REPAIR_FILES=4
FULL_CANDIDATE_FILES=18
DIFF_STAT=1638 insertions / 26 deletions
P1_01=CORRECTED / FOCUSED PASS
P2_01=CORRECTED / FOCUSED PASS
TARGETED_COMPATIBILITY=427 PASS / 0 FAIL / 0 SKIP
NEW_STAGE_A_TESTS=94 PASS / 0 FAIL / 0 SKIP
FULL_LOCAL_PYTEST=FAIL / 6618 PASS / 186 FAIL / 36 SKIP / 0 ERROR / 0 DESELECTED
BASELINE_FAILED_IDS=186
NEW_FAILED_IDS=0
FAILED_ID_SET_DIFFERENCES=0
FOCUSED_FULL_RUN_SUBSET=427 PASS / 0 FAIL / 0 SKIP
NEW_STAGE_A_FULL_RUN_SUBSET=94 PASS / 0 FAIL / 0 SKIP
JS_CHECKS=PASS
COMPILEALL=PASS
DIFF_CHECK=PASS
PATCH_REVERSE_APPLY_CHECK=PASS
FEATURE_DEFAULT=false
CURRENT_AP4_REPLAY=PASS
LEGACY_HISTORY_UNCHANGED=PASS
OFFICIAL_CENTRAL_LAB=NOT_RUN
SUPPORTED_LINUX_ACCEPTANCE=PENDING_OWNER_TECHLEAD
MANUAL_NORMAL_MOBILE_UI_REVIEW=PENDING
STAGE_B_STARTED=NO
TECH_LEAD_REVIEW=REQUESTED
STATUS=HOLD_FOR_TECH_LEAD_R1_REPAIR_REVIEW
PUSH=NO
PR=NO
MERGE=NO
DEPLOY=NO
PRODUCTION_ACTIONS=NO
```
