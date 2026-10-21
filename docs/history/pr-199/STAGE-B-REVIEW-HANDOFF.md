# TASK-TRAFFIC-PARTIAL-COVERAGE-01 — Stage B local review handoff

Status: LOCAL IMPLEMENTATION / INDEPENDENT TECH LEAD REVIEW REQUIRED.
This is not a publication, deployment, feature activation, official Central Lab result, or self-declared acceptance.

Execution capabilities used: local repository read/write, shell, Python/Node focused checks, the explicitly Owner/Tech Lead-authorized ordinary full regression, and one local review commit. No sub-agents, external research, remote Git fetch/push, GitHub actions, production access, restart or deployment. Existing unrelated worktrees were not modified. The complete-regression authorization is specific to this task; it does not authorize running official Central Lab gates.

## Authority and identities

Owner explicitly authorized Stage B from the accepted Stage A commit. Architecture R3 and the Coder Amendment R3 supersede older negative historical range-coverage requirements. The subsequent Tech Lead bounded test reconciliation authorizes excluding only `TRAFFIC_HISTORY_PANEL` from the obsolete Stage-A-only JS identity assertion and renaming that test; the other four protected assertions remain.

```text
ORIGINAL_BASE_HEAD=e8061de9fbd6da8be5cd269779070a4db4d59d64
ORIGINAL_BASE_TREE=d5503fe1f2b5774bbe55cb2d34dba63246f56f6f
STAGE_A_PARENT=39abf52e71f744183297b5a57bfd098845487a2e
STAGE_A_PARENT_TREE=efc6effbc45da1ce3ed61f7c9b7a17549b34f390
STAGE_B_COMMIT=2097d4b971555bc7f6a747faa6562ef4ac59e02a
STAGE_B_TREE=a783d1cb3b2f33107ba64878ae5d3d8b80463f38
BRANCH=feature/traffic-partial-coverage-01
WORKTREE=C:\CaptivPortal-Lab\coder-traffic-partial-coverage-01
```

History remains base → `ade49a171637029f596fe019e73063ce8af76383` → `39abf52e71f744183297b5a57bfd098845487a2e` → `2097d4b971555bc7f6a747faa6562ef4ac59e02a`. Neither accepted Stage A commit was rewritten. The Stage B commit is local review/testing only and has not been pushed.

## Exact Stage B delta

13 files, 1249 insertions, 46 deletions against Stage A:

| Status | Path | Purpose |
|---|---|---|
| M | `app/analytics/models.py` | Frozen historical overlay and strict+overlay composition DTOs. |
| M | `app/analytics/current_traffic.py` | Extract shared pure cycle-header and AP-row validation; preserve Current rules. |
| M | `app/analytics/source_gateway.py` | Explicit raw read boundary, one read-only snapshot, indexed queries, streaming and exact caps. |
| M | `app/traffic_projection/read_service.py` | Reuse existing configured raw Observation path for the overlay; no projection-derived partial values. |
| M | `app/analytics/historical_traffic.py` | Separate positive-evidence overlay owner, per-bucket source selection and independent denominators. |
| M | `app/admin_web/historical_traffic_serialization.py` | Closed safe R3 projection; comparison blocked and public AP-share fractions null in every opt-in state. |
| M | `app/admin_web/query_service.py` | Explicit opt-in composition using the existing shared deadline and historical products. |
| M | `app/admin_web/routes.py` | Single/valid `coverage_mode=partial_v1`, existing flag, ACL and product boundaries. |
| M | `app/admin_web/templates/admin/traffic.html` | Existing flag on History panel; separate legend and complete-coverage-only statistics labels. |
| M | `app/admin_web/static/admin.js` | History block only: validate overlay, sparse distinct markers, tooltips, quality warnings, explicit opt-in requests. |
| M | `tests/admin_web/test_current_partial_coverage.py` | Only approved obsolete identity assertion correction and rename; remaining assertions unchanged. |
| A | `tests/analytics/test_historical_partial_coverage.py` | 39 actual source/owner/serializer/physical-cap tests. |
| A | `tests/admin_web/test_historical_partial_coverage.py` | 17 actual API and Node/browser-rendering contract tests. |

The cumulative replacement against the original base contains Stage A + Stage B: 23 files, 2860 insertions, 45 deletions. This is not a 13-file replacement of Stage A; both patch scopes are supplied separately.

No Observation schema/repository/writer/worker, Traffic Projection schema/repository/projector/writer, Current State schema/repository/collector/status classifier, Omada call behavior, NI, Portal/Auth/CAPPORT, Guest/Session/Public Traffic, deployment, service or environment file was changed by Stage B. Disposable SQLite databases created by tests are test inputs only, not new application databases.

## Architecture → implementation mapping

| Requirement | Implemented boundary |
|---|---|
| Positive evidence only; no full-range negative absence | Historical owner composes unchanged strict result with separately admitted raw partial cycles. Zero admitted means `has_partial_measurements=null`, never false. |
| Read-only retained Observation, not projection partials | `PartialTrafficEvidenceReadBoundaryV1.read_partial_ap_traffic_evidence(...)`; projection gateway opens its existing `_current_path` with `mode=ro` and `query_only=ON`. |
| Same Site, completed partial, incomplete source, stored rows > 0; half-open finished-time range | Indexed raw candidate query and shared structural validation. Failed/shutdown/running/zero-row cycles are not numeric evidence. |
| Integrity checks shared with Current | Extracted exact header predicates and unchanged AP-row validator body: count accounting, unique canonical MAC, Site/cycle identity, flags, finite nonnegative reason/value pairs, valid source timestamps. No Current semantics redesign. |
| Error count > 0 and global row partial/radio quality do not automatically invalidate valid rates | Shared validator preserves the accepted Stage A rules; projection-backed raw partial fixture explicitly uses `error_count=2`. |
| One source family for every bucket | Wired/LAN priority: full bucket, more full cycles, more pairs, more directions, primary tie preference. No AP/direction mixing. |
| Independent directional means, coherent Total only | Each admitted cycle tracks D/U/P populations; Total samples require nonempty equal populations. Means use independent sample counts; D-mean + U-mean need not equal T-mean. |
| Coverage opportunity ratio | Sum paired AP opportunities / sum observed AP opportunities; min/max counts retain variability. |
| No historical Offline promotion | Historical owner does not use Current State status to promote partial cycles. No live AP test or cable disconnection. |
| Strict history/statistics independence | Existing `get_site_history`, strict serialization and all existing historical helper definitions are unchanged. Strict values are validated first and remain separate. |
| Exact bounded scan | 10,080 cycles; 150,000 AP rows; fetchmany ≤ 2,000; local deadline ≤ 5s and parent deadline; bounded per-cycle identity set and ≤720 bucket aggregates. No request-wide raw row list or OFFSET. |
| Fail closed without truncated numbers | Any capacity/deadline failure returns empty overlay buckets and null counters, even after positive accumulation. Source failure returns the separate unavailable envelope. Strict numeric evidence remains independently valid. |
| Retained-prefix shortfall is only positive insufficiency proof | First raw Site/AP-dynamic start later than requested start can produce true; otherwise null. No continuity inference from MIN/MAX, projection bounds, retention configuration or empty result. Positive samples are not erased by prefix shortfall. |
| Exact R3 response states | `partial_evidence`, `source_coverage_insufficient`, `unavailable`, `capacity_limited` with closed reason pairing; nullable booleans cannot be false. |
| Comparison and AP share forbidden in opt-in mode | `comparison_allowed=false`, `ap_share_allowed=false`, categorical comparison state and null public share fractions, including source/capacity/unknown states. No existing numeric comparison field exists in this API. |
| Legacy API / flag | Mode absent remains old strict serialization regardless of flag. Mode invalid/duplicate → 400; valid mode with flag OFF → 404. Same single default-OFF flag. |
| UI contract | Strict paths remain distinct from sparse diamond partial markers. Directional tooltip never invents Total; unmeasured evidence marker is nonnumeric (not a zero-valued point); mixed buckets retain both. No interpolation between partial markers. |
| Exact labels / quality | Complete-coverage-only Average/Peak labels and R3 positive/unknown/prefix warnings; failure/capacity qualifiers, comparison and share messages. Strict numbers are not recalculated in JS. |
| Existing request topology | Existing coordinator and product ranges retained; mode suffix is explicit; no new polling loop or browser-to-source fan-out. |

## Mandatory scenario evidence

All names below refer to the two new Stage B test modules unless stated otherwise.

| Scenario | Concrete evidence |
|---|---|
| R3-T19 | `test_R3_T19_empty_retained_query_is_not_absence`: no admitted rows → unknown/null, not false. |
| R3-T20 / T22 | `test_R3_T20_T22_original_AP4_positive_even_when_prefix_short`: real raw 3/4 subtotal 18/3/21 Mbps, ratio 3/4, positive buckets despite prefix insufficiency. |
| R3-T21 | `test_R3_T21_empty_partial_query_with_positive_prefix_shortage`: retained-prefix proof true, no false absence. |
| R3-T23 / T24 | Five parameterized directional/population cases: no numeric directions → null; asymmetric/independent AP sets → no Total; actual measured 0 stays 0. |
| R3-T25 | Both physical raw caps without patched constants; both owner accumulation/discard cases with reduced test caps; RO snapshot and deadline-after-read discard. |
| R3-T26 | Overlay-only SQLite failure preserves strict numeric result; browser unavailable state preserves strict statistics and shows qualification. |
| R3-T27 | Six source-family selection cases plus both more-full-cycle priority cases. No source mixing. |
| R3-T28 | Exact strict bucket/statistics/Peak equality; strict Average/Peak 24 Mbps and partial subtotal 21 Mbps; comparison and public AP share blocked. |
| R1 historical arithmetic / T25 | Ratio 7/9 (not mean of ratios), observed counts 4–5, measured counts 3–4; independently denominated D=7/U=2/T=6; count integrity, half-open axis and corrupt-neighbor rejection. |
| 4→3→4 recovery | Three separated historical partial cycles produce 24/21/24 Mbps and 1/.75/1 coverage, without stale reuse; 7d uses 672 buckets/900s. Existing Stage A automatic current recovery tests also pass. |
| Real projection composition | Raw-only partial record produces 3 Mbps without projection upsert; Observation and projection DB byte hashes unchanged; query_only rejects writes. |
| API compatibility / security | Legacy results identical with flag OFF/ON absent mode; explicit mode alone extends output; 401/403; invalid/duplicate queries; both 24h/7d; includes/products. |
| Flag OFF JS compatibility | `test_history_browser_flag_off_retains_strict_request_and_numbers`: exactly one legacy request without `coverage_mode`, no partial markers, strict 24 Mbps values. |
| Flag ON JS compatibility | Real renderer requires explicit `coverage_mode=partial_v1`; four sparse states; exact copy; mixed strict/partial tooltip; no false Total or zero marker. |
| Independent product ranges | One grouped request for history/statistics/AP share, explicit mode, null share fractions, malformed numeric fraction rejected. |
| Closed DTO protection | Forbidden false booleans/permissions/old reason rejected; malformed browser envelope rejected; immutable overlay cannot be mutated. |

The original Stage A tests remain in the combined regression: 94 cases. This includes the prior AP4 error-count-2 synthetic incident, aligned status exclusion, unknown/stale status, recovery, corruption, source selection, security and fail-soft storage checks. No accepted numeric assertion was changed.

## Stage A and legacy preservation

- Entire `admin.js` outside `TRAFFIC_HISTORY_PANEL` is byte-content identical to accepted Stage A, including Home/current UI and all four protected blocks.
- Static AST comparison to `39abf52...`: all preexisting functions/methods in `historical_traffic.py` and `historical_traffic_serialization.py` are identical. QueryService changed only its two History methods.
- CurrentTraffic preexisting definitions are identical except `_validate_partial_cycle`, now a header/row wrapper. The extracted AP-row body is AST-identical to the old loop body. Header/count/uniqueness/reason invariants remain and all Stage A tests pass.
- The approved renamed test still compares all four protected JS blocks against original `e8061de...`; no skip/xfail/deselection was added.
- Protected source modules are untouched. No second feature flag. Default remains false. No production activation.

## Verification performed

Environment: Windows; Python 3.10.11 at `C:\CaptivPortal-UI-Preview\.venv\Scripts\python.exe`; Node v24.19.0. All pytest databases/tmp/logs/cache are disposable external Lab state; no production access.

Focused Stage A + B and direct compatibility: **549 passed, 0 failed, 0 skipped**, 144.38s.

- New Stage B: **56 passed** (39 Analytics + 17 Admin/API/browser).
- Existing Stage A: **94 passed**.
- Remaining direct existing compatibility: **399 passed**.
- First approved test-reconciliation run: **39 passed**, 18.90s.

Exact focused command:

```text
python -m pytest -q tests/analytics/test_historical_partial_coverage.py tests/admin_web/test_historical_partial_coverage.py tests/analytics/test_current_partial_coverage.py tests/current_state/test_ap_status_evidence.py tests/admin_web/test_current_partial_coverage.py tests/analytics/test_current_traffic.py tests/analytics/test_current_traffic_runtime.py tests/current_state/test_read_service.py tests/admin_web/test_home_traffic.py tests/admin_web/test_home_traffic_frontend.py tests/admin_web/test_traffic_current.py tests/admin_web/test_traffic_current_frontend.py tests/admin_web/test_traffic_history.py tests/admin_web/test_traffic_history_frontend.py tests/admin_web/test_config.py tests/admin_web/test_web_ux_pack_02.py tests/analytics/test_historical_traffic.py tests/traffic_projection/test_projected_read.py --basetemp=C:\CaptivPortal-Lab\tmp\partial-coverage-stage-b-focused --junitxml=C:\CaptivPortal-Lab\partial-coverage-stage-b-focused.xml --tb=short
```

Static checks: `python -m compileall -q app` and all three changed/new test files with external `PYTHONPYCACHEPREFIX`; `node --check app/admin_web/static/admin.js`; `git diff --check`; staged check; `git diff --check HEAD^ HEAD`: **PASS**.

Complete ordinary local regression was executed on clean immutable `2097d4b...`. This is the expressly authorized full pytest regression, not official Central Lab/V7 or Linux acceptance:

```text
python -m pytest -q -rs --basetemp=C:\CaptivPortal-Lab\tmp\partial-coverage-stage-b-full --junitxml=C:\CaptivPortal-Lab\partial-coverage-stage-b-full.xml
```

**Full result: FAIL — 6674 passed, 186 failed, 36 skipped, 0 errors, 0 deselected, 5 warnings**, 808.67s console elapsed (807.559s JUnit suite duration). Process exit code 1. Total collected outcomes: 6896. No skip/xfail/deselection was added to hide a failure.

Exact comparisons, not merely aggregate count comparisons:

- Candidate failed identities versus original baseline diagnostic XMLs: **186 equal / 0 set differences / 0 new failed IDs**.
- Candidate failed identities versus accepted Stage A full run: **186 equal / 0 set differences**.
- Candidate skipped identities **and skip reasons** versus Stage A full run: **36 equal / 0 differences**.
- All **549 focused** identities occur in the full run and are PASS (0 fail/error/skip).
- All **56 new Stage B** cases are PASS in the full run.
- All **94 Stage A** cases are PASS in the full run, including the approved renamed identity test.
- The prior Stage A full XML hash remains `45206d690514a26c2b771095ae51f36d305e55352aa3e52aaba4ce5ebfb008a7`, unchanged from its original handoff.

`FULL-FAILURE-SKIP-INVENTORY.json` contains every failed JUnit identity/message, every skipped identity/reason, and both failure-set comparisons plus skip-reason comparison. Empty delta arrays are the evidence of equality. It is retained externally, not committed.

Prior Stage A full result was 6618 passed / 186 failed / 36 skipped, with all 186 failures reproduced on exact original baseline. The matching reference is `C:\CaptivPortal-Lab\partial-coverage-review-r1-full.xml`; original baseline diagnostic XMLs are `partial-coverage-baseline-failures-1.xml` through `-4.xml`. Known platform failure sources are the unchanged network_metadata modules (165) and network_metadata_projection/test_projection_source.py (21): POSIX `pread`, `O_NONBLOCK`, `fcntl`, Windows sharing/CLI effects. These are not assigned for repair or skipping by this task. All eleven failing test-module blobs remain identical to the original base. The 56-case increase in passing tests is exactly the new Stage B cases.

| Unchanged baseline failure module | FAIL |
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

Iteration transparency: initial test construction mistakes (synthetic Site and import shape) were corrected before the authoritative focused run. A read-only fixture probe attempted a refused DELETE then left a SQLite transaction open; tests were corrected to rollback that refused probe, not to change application behavior. The last pre-reconciliation combined run was 146 PASS / 1 FAIL due solely to the obsolete Stage-A-only History identity assertion; Tech Lead explicitly authorized the bounded correction. These earlier results are retained as diagnostics, not substituted for the authoritative 549-case result.

## Transport artifacts and identities

| Artifact | Bytes | SHA256 |
|---|---:|---|
| `TASK-TRAFFIC-PARTIAL-COVERAGE-01-BASE-to-STAGE-B.patch` | 223923 | `a5dfd76fd00483e71ac0286a2d5f8b45c4dffd2a730a4ce76a31a7c27d131898` |
| `TASK-TRAFFIC-PARTIAL-COVERAGE-01-STAGE-A-to-B.patch` | 102432 | `b2aa2a2b663869f03ad0d4bee10fbf27c004c2026c5499840ff811b32f677bd4` |
| `C:\CaptivPortal-Lab\partial-coverage-stage-b-focused.log` | 681 | `6a1b0e50b77a76e2cc7212f039c4c2b4dae46bfe08690941237fa0df1d81e87e` |
| `C:\CaptivPortal-Lab\partial-coverage-stage-b-focused.xml` | 88663 | `9d99dd42df1c8731ddadfc16091ae75ef50a8f47e588436108842aa3553b7da6` |
| `C:\CaptivPortal-Lab\partial-coverage-stage-b-full.log` | 361070 | `6140976b4922b14af630f06893a06b40ee0bd10e9650f59d9e1dcb58ef456ba2` |
| `C:\CaptivPortal-Lab\partial-coverage-stage-b-full.xml` | 1480186 | `d77728f1ed6c382eaf2699a9ccd82b118209adeade0368625b67fce607f0b1d6` |
| `FULL-FAILURE-SKIP-INVENTORY.json` | 53390 | `c0f033ca47866a929fa3686785608de26c1d278f6649b477c750092ef0f5bb03` |

Both patches are generated by `git diff --binary --full-index --no-ext-diff --output=...` on the immutable commit. `git apply --reverse --check` on each: **PASS**, check only; neither patch was applied to alter the repository. Paths are under `C:\CaptivPortal-Lab\artifacts\traffic-partial-coverage-01-stage-b\`.

## Limitations / owner actions

- Tech Lead independent Stage B source review and release validation remain required. Stage A source acceptance does not constitute Stage B release acceptance.
- No official V7/Central Lab or Linux admission/performance gate executed by Coder. Full Windows regression cannot be represented as PASS while known platform failures remain.
- Node tests execute the actual History browser code and real backend payloads; they do not replace manual real-browser laptop/mobile visual acceptance. No screenshots or live AP4 disconnect are claimed.
- Retained schema-v1 evidence never proves period-wide absence/continuity. This is the R3 supported unknown state, not an implementation blocker.
- Overlay caps/deadlines can intentionally withhold all overlay numbers; no truncation or relaxation is permitted.
- No new known Stage B architecture ambiguity; protected writes were unnecessary.

## Final control block

```text
TASK=TASK-TRAFFIC-PARTIAL-COVERAGE-01
STAGE=B_HISTORICAL
ARCHITECTURE=R3_TECHLEAD_ACCEPTED
IMPLEMENTATION_COMMIT=2097d4b971555bc7f6a747faa6562ef4ac59e02a
IMPLEMENTATION_TREE=a783d1cb3b2f33107ba64878ae5d3d8b80463f38
PARENT=39abf52e71f744183297b5a57bfd098845487a2e
STAGE_B_CHANGED_FILES=13
FOCUSED=549 PASS / 0 FAIL / 0 SKIP
NEW_STAGE_B_TESTS=56 PASS
STAGE_A_TESTS=94 PASS
FULL_PYTEST=FAIL / 6674 PASS / 186 FAIL / 36 SKIP / 0 ERROR / 0 DESELECTED
NEW_FAILED_IDS=0
BASELINE_FAILED_IDS=186
FAILED_ID_SET_DIFFERENCES=0
SKIPPED_ID_AND_REASON_DIFFERENCES=0
FOCUSED_FULL_RUN_SUBSET=549 PASS
JS_CHECKS=PASS
COMPILEALL=PASS
DIFF_CHECK=PASS
PATCH_REVERSE_APPLY_CHECK=PASS
WORKTREE=CLEAN
NEW_CONFIRMED_STAGE_B_P0_P1=0
ARCHITECTURE_AMBIGUITY=NONE
STAGE_A_CURRENT_SEMANTICS_CHANGED=NO
LEGACY_HISTORY_WITHOUT_MODE_CHANGED=NO
FEATURE_DEFAULT=false
OBSERVATION_SCHEMA_WRITER_CHANGE=NO
PROJECTION_SCHEMA_WRITER_CHANGE=NO
CURRENT_STATE_SCHEMA_COLLECTOR_CHANGE=NO
NEW_OMADA_CALLS=NO
LOCAL_REVIEW_COMMIT=YES
PUSH=NO
PR=NO
MERGE=NO
DEPLOY=NO
RESTART=NO
FEATURE_ACTIVATION=NO
PRODUCTION_ACTION=NO
OFFICIAL_CENTRAL_LAB_RUN=NO
LINUX_ADMISSION_RUN=NO
TECH_LEAD_REVIEW=REQUESTED
```
