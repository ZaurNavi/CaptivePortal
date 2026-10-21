# TASK-TRAFFIC-PARTIAL-COVERAGE-01 — Stage A review handoff

Architecture: accepted R3 + unchanged current-specific R1 contracts.
Owner authorized resumption in this thread. Stage B has NOT started.

## Identity / governance

- Worktree: `C:\CaptivPortal-Lab\coder-traffic-partial-coverage-01`
- Branch: `feature/traffic-partial-coverage-01`
- Base HEAD: `e8061de9fbd6da8be5cd269779070a4db4d59d64`
- Base tree: `d5503fe1f2b5774bbe55cb2d34dba63246f56f6f`
- Local review commit: `ade49a171637029f596fe019e73063ce8af76383`
- Candidate tree: `383cf2f1ca2a510811b66f9f4d96c9235f6b24b4`
- Parent: exact accepted base HEAD.
- 18 files changed, 1492 insertions, 26 deletions.
- No push, PR, merge, deployment, production access, restart or activation.
- Current feature defaults OFF. History remains strict even when current partial mode is ON.

## Complete changed-file inventory

Modified production files (14):

1. `app/admin_web/config.py` — separate exact default-OFF flag.
2. `app/admin_web/current_traffic_serialization.py` — independent minimized closed current/page serializers, fail-closed value/count/context validation.
3. `app/admin_web/query_service.py` — explicit mode dispatch; aligned status reader supplied; legacy dispatch retained.
4. `app/admin_web/routes.py` — three current opt-in routes; mode validation, feature gate, existing ACL/deadlines/response cap; current template context.
5. `app/admin_web/static/admin.js` — current-only validation/presentation; existing coordinators; authoritative coverage/Offline labels.
6. `app/admin_web/templates/admin/home.html` — current-only flag and existing freshness thresholds.
7. `app/admin_web/templates/admin/traffic.html` — current-only flag.
8. `app/analytics/current_traffic.py` — separate partial service/page path; structural admission, one-family source choice, population proof, directional sums, freshness/skew, status conflicts and pinned paging.
9. `app/analytics/models.py` — immutable opt-in current/page DTOs.
10. `app/analytics/source_gateway.py` — coherent read-only completed success/partial candidate read, under the existing deadline.
11. `app/config.py` — `WEB_ADMIN_TRAFFIC_PARTIAL_COVERAGE_ENABLED=false`.
12. `app/current_state/models.py` — immutable `CurrentApStatusEvidenceV1`.
13. `app/current_state/read_service.py` — bounded prior successful AP inventory; exact Site/MAC/scope/count/time validation; no future backfill or corrupt-status fallback.
14. `app/settings.py` — existing env/config/settings propagation.

New tests (3):

15. `tests/admin_web/test_current_partial_coverage.py`
16. `tests/analytics/test_current_partial_coverage.py`
17. `tests/current_state/test_ap_status_evidence.py`

Existing directly affected test (1):

18. `tests/admin_web/test_web_ux_pack_02.py` — one explicit `global.partialMode=false` in the isolated legacy Home cursor-chain JavaScript fixture. No assertion, expected result, skip or production code changed in this correction.

## Stage A acceptance mapping

| Requirement | Actual production-path proof |
|---|---|
| A-T01 | `test_A_T01_all_four_pairs_prove_installed_even_when_global_partial`: four valid AP pairs, 20/4/24 Mbps; global partial result preserved. |
| A-T02 | `test_A_T02_AP4_incident_exact_null_not_zero_and_pinned_page`: three Online, one Offline; 18/3/21 Mbps; AP4 null directions; immutable summary/page context. |
| A-T03/04 | `test_A_T03_T04_no_unproven_offline_exclusion`: Online/other/unknown/stale/missing/future status cannot authorize exclusion. |
| A-T05 | `test_A_T05_actual_zero_vs_no_measurements`: measured zero is zero; missing measurements are null/unavailable. |
| A-T06/14 | `test_A_T06_T14_original_incident_replay_and_automatic_recovery`: completed partial cycles with error_count=2; 24 → 21 → 21 → 21 → 24; no old-rate reuse during no_baseline/counter_reset. |
| A-T07 | population mismatch, strict-success inventory conflict, same MAC on another Site and wrong-Site isolation tests. |
| A-T08 | actual prior Current State selection, age at finish, exact 90-second status boundary, no future snapshot; traffic fresh/stale/expired/future/skew tests. |
| A-T09 | six exact Wired/LAN selection branches, no source mixing, independent directional sums. |
| A-T10 | corrupt newest metadata and retained row shapes fail closed without older numeric fallback. |
| A-T11 | Offline counter_reset/no_baseline/gap/invalid_elapsed/numeric conflicts retain `status_measurement_conflict`. |
| A-T12 | three real HTTP route paths: authentication/Site ACL/mode dispatch; disabled/invalid/duplicate mode; page bound; absent-mode strict response identical. Existing response-bound/deadline contracts exercised by legacy focused tests. |
| A-T13 | real Node current renderer and AP roster; exact titles/coverage/Offline details; partial validators; templates; legacy OFF request behavior; no History opt-in. |
| A-T15 | changed paths constrained to approved surfaces; source DB hashes unchanged by new readers; History/range/Guest/Session/Evidence JS blocks byte-identical to baseline. |

Historical-only tests/overlays are deferred, NOT reported as passed.

Architecture-to-code map: R1 §5 → Current State DTO/read boundary; §6 → analytics population matching; §7 → selected-family validation/selection; §8 → gateway lifecycle and service structural admission; §§9–12 → immutable current metrics, freshness/skew, reasons and closed serialization; §13.5 → separate current service methods; §§20.1–20.5/20.7 → explicit current-only mode routing with unchanged ACL and no browser source fan-out; §21 → one default-OFF config/settings/Admin flag; §§22–23 → exact current UI copy; §§24–25 historical behavior → unchanged/deferred under R3 Stage A; §§26–28 → recovery, Site population and fail-closed tests. R3 A1–A5 and A-T01–A-T15 take precedence over original historical-stage obligations.

## Verification actually performed

Environment: Windows PowerShell; Python 3.10.11 at `C:\CaptivPortal-UI-Preview\.venv\Scripts\python.exe`; Node v24.19.0. External temporary roots and pycache used.

- Focused current/legacy/History/config suite: **347 passed** in 62.52 seconds. XML: `C:\CaptivPortal-Lab\partial-coverage-targeted-final-02.xml`.
- After final bounded serializer checks/current age-display refinement, all new Stage A tests: **74 passed** in 25.68 seconds. XML: `C:\CaptivPortal-Lab\partial-coverage-new-final-04.xml`. No production source bytes changed after this run.
- Legacy WEB-UX-PACK-02 plus new Admin partial-coverage tests after the isolated fixture correction: **76 passed** in 13.52 seconds. XML: `C:\CaptivPortal-Lab\partial-coverage-js-fixture-01.xml`.
- Earlier real current + History coordinator/browser compatibility after helper positioning: **23 passed**.
- `node --check app/admin_web/static/admin.js`: PASS.
- `python -m compileall -q app` + the three new test modules, external `PYTHONPYCACHEPREFIX`: PASS.
- `git diff --check` and committed `git diff --check HEAD^ HEAD`: PASS.
- Patch reverse-apply check: PASS; check only, no application/repository mutation.
- First full local repository pytest: **6597 passed, 187 failed, 36 skipped, 0 errors** in 784.84 seconds. All 187 failed IDs were re-executed on the exact clean baseline: **186 failed, 1 passed**. The one candidate-only failure was the isolated JS fixture described above and is corrected without assertion weakening.
- Final clean-candidate full repository pytest: **FAIL — 6598 passed, 186 failed, 36 skipped, 0 errors, 0 deselected**, 5 warnings, in 849.10 seconds. XML: `C:\CaptivPortal-Lab\partial-coverage-full-02.xml`; log: `C:\CaptivPortal-Lab\partial-coverage-full-02.log`. The exact 186 failed node-ID set equals the baseline diagnostic failure set, with **0 set differences / 0 new failed IDs**. This is NOT an official V7/Central Lab PASS.
- The final full-run XML also confirms all **347 focused current/legacy/History/config tests PASS with 0 skips**, including all 74 new Stage A tests. The corrected legacy Home cursor-chain test is PASS in the final full run.

Focused command:

```text
python -m pytest -q tests/analytics/test_current_partial_coverage.py tests/current_state/test_ap_status_evidence.py tests/admin_web/test_current_partial_coverage.py tests/analytics/test_current_traffic.py tests/analytics/test_current_traffic_runtime.py tests/current_state/test_read_service.py tests/admin_web/test_home_traffic.py tests/admin_web/test_home_traffic_frontend.py tests/admin_web/test_traffic_current.py tests/admin_web/test_traffic_current_frontend.py tests/admin_web/test_traffic_history.py tests/admin_web/test_traffic_history_frontend.py tests/admin_web/test_config.py
```

Full local command:

```text
python -m pytest -q -rs --basetemp C:\CaptivPortal-Lab\tmp\partial-coverage-full-01 --junitxml C:\CaptivPortal-Lab\partial-coverage-full-01.xml
```

First full output retained at `C:\CaptivPortal-Lab\partial-coverage-full-01.log`. Final run uses the same command with `full-02` in basetemp/XML/log paths, executed on the final clean review commit.

Exact-baseline diagnostic: detached clean worktree `C:\CaptivPortal-Lab\partial-coverage-baseline-20261011`, HEAD `e8061de9fbd6da8be5cd269779070a4db4d59d64`, tree `d5503fe1f2b5774bbe55cb2d34dba63246f56f6f`. Only the 187 failed node IDs were executed, in four batches of 50/50/50/37, same interpreter, external temp/cache, `-q -rs`. Results: 49 FAIL + 1 PASS; 50 FAIL; 50 FAIL; 37 FAIL. XML/logs: `C:\CaptivPortal-Lab\partial-coverage-baseline-failures-1` through `-4` with `.xml`/`.log` extensions. These are local differential diagnostics, not official platform acceptance.

Baseline failure classes: 129 `os.pread` unavailable; 51 `os.O_NONBLOCK` unavailable; 2 missing `fcntl`; 3 Windows file-sharing `PermissionError`; 1 CLI exit-code assertion. These 186 failed baseline cases are in unchanged Network Metadata / Network Metadata Projection tests. No attempt was made to repair protected NI code, skip/deselect these failures, change platform semantics or claim full-gate PASS.

All 11 test source files contributing those 186 baseline failures have identical Git blob IDs at baseline and final candidate. Protected production directories also have no diff. The one candidate-only legacy JS fixture failure is not classified as baseline; it was explicitly repaired and rechecked.

## Patch

- `C:\CaptivPortal-Lab\artifacts\traffic-partial-coverage-01-stage-a\TASK-TRAFFIC-PARTIAL-COVERAGE-01-STAGE-A.patch`
- Bytes: **120717**
- SHA256: **ec1b543051de2e0506a28661d09dd7bdf3783851c740c4842b533a35a718403a**
- Full BASE→candidate diff, including all three new tests and the one-line existing fixture adaptation. Replaces the earlier interim 119762-byte patch.

## Boundaries / remaining acceptance

- Observation schema/repository/writer/worker: unchanged.
- Current State schema/repository/collector/status classifier: unchanged.
- Traffic Projection schema/repository/projector/writer: unchanged.
- Omada calls/cadence, NI, Fingerprint, Guest/Session, Portal/Auth/CAPPORT: unchanged.
- No new runtime DB, schema, data source, worker, polling, retention, migration or backfill.
- AP4 replay uses disposable deterministic facts, not production DB copies or cable disconnection.
- New service paths perform only read-only source reads; writes in disposable fixture creation are test setup, not application reader behavior.
- Source selection uses the entire selected coherent cycle; page output remains bounded at 250. Reads share the existing deadline, and status inventory uses existing `ap_max_rows`.
- Stage A is not self-declared accepted. Independent Tech Lead review and full-regression disposition remain required.
- Stage B is HOLD pending Stage A acceptance + separate Owner GO.
- Feature activation/service restart/deployment require separate Owner authorization.

## Synthetic current DTO / UI evidence

The following complete summary was emitted by the actual production serializer over disposable retained SQLite fixtures, not hand-written service arithmetic. Synthetic dates are fixture dates, not claimed execution dates. All-four summary is 20/4/24 Mbps with `complete_installed`; the exact AP4 Offline summary is:

```json
{
  "metric_version": "network_traffic_current_partial_coverage.v1",
  "site_id": "0123456789abcdef01234567",
  "evaluated_at_utc": "2026-01-01T12:01:00.000Z",
  "measurement_state": "complete_online_population",
  "population_scope": "confirmed_online",
  "snapshot": {
    "cycle_id": "incident",
    "started_at": "2026-01-01T12:00:00.000Z",
    "finished_at": "2026-01-01T12:00:40.000Z",
    "source_result": "partial",
    "source_complete": false,
    "latest_attempt_state": "completed",
    "latest_attempt_result": "partial",
    "latest_attempt_at": "2026-01-01T12:00:40.000Z",
    "using_previous_snapshot": false,
    "observed_at": "2026-01-01T12:00:30.000Z",
    "newest_observed_at": "2026-01-01T12:00:30.000Z",
    "age_seconds": 30.0,
    "source_skew_seconds": 0.0,
    "freshness_status": "fresh",
    "freshness_reason": "within_freshness_window"
  },
  "traffic": {"download_mbps": 18.0, "upload_mbps": 3.0, "total_mbps": 21.0, "unit": "Mbps"},
  "source_selection": {
    "primary_source": "wired", "selected_source": "wired",
    "selection_reason": "primary_full_online_coverage",
    "source_mixing_allowed": false,
    "wired_pair_valid_ap_count": 3, "lan_pair_valid_ap_count": 0
  },
  "coverage": {
    "observation_ap_count": 4, "installed_ap_count": 4,
    "online_ap_count": 3, "offline_ap_count": 1,
    "other_ap_count": 0, "unknown_ap_count": 0,
    "measured_pair_ap_count": 3, "measured_download_ap_count": 3,
    "measured_upload_ap_count": 3, "required_measurement_ap_count": 3,
    "missing_required_ap_count": 0, "offline_excluded_ap_count": 1,
    "observation_only_ap_count": 0, "inventory_only_ap_count": 0,
    "population_match_state": "matched",
    "coverage_reasons": ["complete_confirmed_online_population", "confirmed_offline_excluded", "source_cycle_partial"]
  },
  "status_evidence": {
    "state": "aligned_fresh", "cycle_id": "status-incident",
    "capture_started_at": "2026-01-01T12:00:30.000Z",
    "capture_finished_at": "2026-01-01T12:00:30.000Z",
    "age_at_traffic_seconds": 10.0,
    "source_scope_hash": "524ced18ae546400b9436f09a2a003b8fd6b26756ae5ee9ff79f9137cbf58f8c"
  }
}
```

The actual page serializer emits AP4 with `download_mbps=null`, `upload_mbps=null`, `total_mbps=null`, both reasons `source_unavailable`, `coverage_role=offline_excluded`, `status_classification=offline`. Page summary context is identical to the summary above.

Node DOM/coordinator evidence covers the actual current renderer and AP roster, ON/OFF requests, stale/unavailable/partial/complete labels and existing coordinator registration. Exact visible copy includes `3 Online / 4 total · 1 Offline excluded` and `All confirmed Online APs are measured.` No manual normal/mobile screenshot or visual acceptance is claimed. No historical opt-in DTO is generated in Stage A.

## Proposed rollout / rollback — review only

1. Tech Lead reviews this exact patch/tree and disposes regression/platform evidence. Owner separately authorizes publication and merge.
2. Any subsequently authorized deployment starts with the repository default flag OFF; no database migration/backfill or other pipeline service restart.
3. Current-mode activation and CaptivPortal restart require a separate Owner action. Verify the strict OFF baseline, ON 4/4 and confirmed-Offline 3/4 behavior, null AP4 rates and unchanged strict History.
4. Semantic rollback is flag OFF plus an explicitly Owner-approved CaptivPortal restart. Do not delete, rebuild or rewrite any source database.

None of these operational steps was executed by Coder.

## Agent execution summary

Repository read/write, local shell, Python/Node checks and an isolated local review commit were available and used within the TASK. Publication and production actions were not authorized and were not used. The intermediate local review commit was amended only to record the one-line directly affected synthetic JS fixture adaptation; the final candidate has one commit on the exact TASK base. A separate detached baseline diagnostic worktree was created without editing/resetting any existing worktree. All logs, XML, patch and handoff files are external to the application repository. No external network/Omada calls, production DB copies or service operations were used for implementation or evidence.

## Unresolved acceptance / known limitations

- Full Windows repository gate remains FAIL on 186 reproducible baseline cases. This is an acceptance blocker requiring Tech Lead disposition / appropriate independent platform evidence, not a claim that full acceptance passed.
- No new confirmed Stage A production P0/P1/P2 was identified in the executed checks; counts below are Coder-known defects, not a substitute for independent source review.
- Manual visual review at normal/mobile width, official Central Lab and Linux release acceptance were not performed by Coder. Actual Node DOM/renderer evidence is described above.
- Historical Stage B is deliberately not implemented, tested or accepted by this handoff.
- Architecture ambiguity: NONE remaining for the authorized Stage A scope.

## Required Stage A result block

```text
TASK=TASK-TRAFFIC-PARTIAL-COVERAGE-01
STAGE=A_CURRENT
ARCHITECTURE=R3_TECHLEAD_ACCEPTED
IMPLEMENTATION_AUTHORIZATION=EXPLICIT_OWNER_GO_IN_THIS_THREAD
BASE_HEAD=e8061de9fbd6da8be5cd269779070a4db4d59d64
BASE_TREE=d5503fe1f2b5774bbe55cb2d34dba63246f56f6f
IMPLEMENTATION_COMMIT=ade49a171637029f596fe019e73063ce8af76383
IMPLEMENTATION_TREE=383cf2f1ca2a510811b66f9f4d96c9235f6b24b4
BRANCH=feature/traffic-partial-coverage-01
WORKTREE_CLEAN=YES
CHANGED_FILES=18 (14 production, 3 new test files, 1 existing test fixture)
DIFF_STAT=1492 insertions, 26 deletions
TARGETED_TESTS=347 PASS / 0 FAIL / 0 SKIP; final full-run subset also 347 PASS
NEW_STAGE_A_TESTS=74 PASS / 0 FAIL / 0 SKIP
WEB_UX_COMPATIBILITY_PLUS_NEW_ADMIN=76 PASS / 0 FAIL / 0 SKIP
FULL_PYTEST=FAIL / 6598 PASS / 186 FAIL / 36 SKIP / 0 ERROR / 0 DESELECTED
BASELINE_FAILED_IDS=186
NEW_FAILED_IDS=0
JS_CHECKS=PASS
COMPILEALL=PASS
DIFF_CHECK=PASS
PATCH_REVERSE_APPLY_CHECK=PASS
CURRENT_AP4_REPLAY=PASS
LEGACY_HISTORY_UNCHANGED=PASS
FEATURE_DEFAULT=false
COVERAGE_MODE=partial_v1 (explicit current opt-in only)
OBSERVATION_SCHEMA/WRITER_CHANGE=NO
TRAFFIC_PROJECTION_SCHEMA/WRITER_CHANGE=NO
CURRENT_STATE_SCHEMA/COLLECTOR_CHANGE=NO
NEW_OMADA_CALLS=NO
PRODUCTION_ACTIONS=NO
PUSH=NO
PR=NO
MERGE=NO
DEPLOY=NO
OPEN_P0=0
OPEN_P1=0
OPEN_P2=0
FULL_GATE_BASELINE_BLOCKER=186 WINDOWS BASELINE FAILURES; TECH_LEAD DISPOSITION REQUIRED
STAGE_B_STARTED=NO
TECH_LEAD_REVIEW=REQUESTED
```

TECH_LEAD_REVIEW=REQUESTED
PUSH=NO
PR=NO
MERGE=NO
DEPLOY=NO
PRODUCTION_ACTIONS=NO
