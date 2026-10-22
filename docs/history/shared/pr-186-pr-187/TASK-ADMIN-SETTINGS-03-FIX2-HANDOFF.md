# TASK-ADMIN-SETTINGS-03-FIX2 — local source-review candidate

```ini
TASK=TASK-ADMIN-SETTINGS-03-FIX2
BASE_HEAD=b6927cf70207810cec9d6a8186e92f131ca1392f
BASE_TREE=06611fff6650fa0eb3be2e5ff301010146413fe7
BRANCH=fix/admin-settings-03-observation-read-boundary
CANDIDATE_COMMIT=94cce826e58752b3338fa312befc0f345a23ceef
CANDIDATE_PARENT=b6927cf70207810cec9d6a8186e92f131ca1392f
CANDIDATE_TREE=f965d4604652db52d5f97b1f5d3abe36263ee78b
WORKTREE=C:\CaptivPortal-Lab\coder-admin-settings-03-fix2
WORKTREE_STATE=CLEAN
GIT_STATUS_PORCELAIN=<empty>
CHANGED_FILES=7
FULL_BASE_TO_CANDIDATE_PATCH_PATH=C:\CaptivPortal-Lab\artifacts\TASK-ADMIN-SETTINGS-03-FIX2_BASE-to-CANDIDATE.patch
FULL_PATCH_BYTES=24693
FULL_PATCH_SHA256=79e89f04ec2095f03f1953a54f6256f91a4f7b67513afb7d50aeb206bb2db52a
PATCH_REVERSE_APPLY_CHECK=PASS
ROOT_CAUSE=Observation local repository initialization was deferred with provider-capable start until after adoption; pre-adoption Analytics rejected disabled Observation and Admin read composition became unavailable.
FIX_STRATEGY=Idempotent local preparation before Analytics/Admin; cached InitializationResult reused by start; explicit read-boundary readiness accepted by Analytics with normal source validation preserved.
PRE_ADOPTION_PROVIDER_CALLS=0 (disposable regression spies)
OBSERVATION_READ_BOUNDARY_PREPARED=YES (disposable healthy configuration)
ANALYTICS_STATE_AFTER_PREPARE=active
ADMIN_STATE_AFTER_PREPARE=active; source prerequisites ready; query_service present
HOME_AP24_STATE_AFTER_PREPARE=active; service present; telemetry worker composed and not started
FOCUSED_TESTS=1865 passed / 2 skipped / 1 baseline-known failed; 0 new failures
FULL_PYTEST=5514 passed / 30 skipped / 1 baseline-known failed / 0 errors / 0 deselected; 0 new failures
COMPILEALL=PASS
NODE_CHECK=PASS
GIT_DIFF_CHECK=PASS
OPEN_P0=0 identified in FIX2 candidate; Tech Lead review pending
OPEN_P1=0 identified in FIX2 candidate; Tech Lead review pending
PUSH=NO
PR=NO
MERGE=NO
DEPLOY=NO
PRODUCTION_ACTION=NO
```

## Changed files and complete diff

Exact `git diff --name-status b6927cf70207810cec9d6a8186e92f131ca1392f 94cce826e58752b3338fa312befc0f345a23ceef`:

```text
M app/analytics/runtime.py
M app/observations/runtime.py
M run.py
A tests/analytics/test_prepared_observation_runtime.py
A tests/observations/test_read_boundary_preparation.py
M tests/observations/test_runtime.py
M tests/settings_control/test_run_integration.py
```

Exact aggregate stat: **7 files changed, 379 insertions(+), 5 deletions(-)**.

```text
 app/analytics/runtime.py                           |   3 +-
 app/observations/runtime.py                        |  42 ++++++-
 run.py                                             |   4 +
 tests/analytics/test_prepared_observation_runtime.py |  91 +++++++++++++++
 tests/observations/test_read_boundary_preparation.py | 123 +++++++++++++++++++++
 tests/observations/test_runtime.py                  |   3 +-
 tests/settings_control/test_run_integration.py      | 118 +++++++++++++++++++-
```

The patch is binary-capable/full-index and covers the entire baseline-to-candidate diff, including both new test files. Reverse application was checked without applying anything.

Production scope is exactly the three authorized files. No Current State preparation, Settings schema/API/read-model/mutation/idempotency/secret change, Admin authorization change, deployment or service change was made. No externally visible `prepared` runtime state was added. Successful preparation leaves Observation disabled until normal start.

Preparation performs only existing local repository initialization and caches its InitializationResult; repeated preparation and start do not initialize twice. Failed preparation retains unavailable/fail-open lifecycle behavior. Successful stop clears preparation so a later lifecycle validates local storage again. Worker start and startup telemetry retain abandoned-cycle information.

## Verification environment and commands

Windows, PowerShell; Python **3.10.11**, Node **v24.19.0**.
Python executable: `C:\Users\Zaur Navi\AppData\Local\Programs\Python\Python310\python.exe`.
All candidate commands ran in the isolated worktree shown above; no production access.

Direct repair/startup checks:

```text
python -m pytest -q tests/observations/test_read_boundary_preparation.py tests/analytics/test_prepared_observation_runtime.py tests/settings_control/test_run_integration.py --basetemp C:/CaptivPortal-Lab/tmp/as03-fix2-direct-02 --tb=short
```

Result: **22 passed**, 1.95 seconds, exit 0.

Required focused suite on the clean real candidate commit:

```text
python -m pytest -q tests/observations tests/analytics tests/admin_web tests/settings_control tests/test_admin_controller_settings.py --basetemp C:/CaptivPortal-Lab/tmp/as03-fix2-focused-clean-01 --tb=short --junitxml=C:/CaptivPortal-Lab/artifacts/TASK-ADMIN-SETTINGS-03-FIX2-focused-clean.xml
```

Result: **1865 passed, 2 skipped, 1 failed**, 214.49 seconds, exit 1. The sole failure is the independently reproduced baseline Home ordering assertion described below; no new failure.

Required full repository run (explicitly authorized by this TASK, not an official Central Lab gate):

```text
python -m pytest -q --basetemp C:/CaptivPortal-Lab/tmp/as03-fix2-full-01 --tb=short --junitxml=C:/CaptivPortal-Lab/artifacts/TASK-ADMIN-SETTINGS-03-FIX2-full.xml
```

Full result: **5514 passed, 30 skipped, 1 failed, 0 errors, 0 deselected**, 630.64 seconds, exit 1. The only failure is `tests/admin_web/test_home_traffic.py::test_home_template_delivers_traffic_only_when_enabled`, with the exact baseline assertion values shown below. **No new failures.** This is not a wholly green full run: the unrelated known defect remains and was not modified. No tests were excluded, skipped via a new marker, or xfailed by this repair.

Static checks:

```powershell
$env:PYTHONPYCACHEPREFIX='C:\CaptivPortal-Lab\tmp\as03-fix2-pycache'
python -m compileall -q app run.py
node --check app/admin_web/static/controller_settings.js
git diff --check
git diff --check HEAD^ HEAD
git apply --reverse --check C:/CaptivPortal-Lab/artifacts/TASK-ADMIN-SETTINGS-03-FIX2_BASE-to-CANDIDATE.patch
```

Each completed successfully, exit 0. No source change followed these checks or the candidate commit.

Retained local test evidence:

- Focused XML: `C:\CaptivPortal-Lab\artifacts\TASK-ADMIN-SETTINGS-03-FIX2-focused-clean.xml`, SHA256 `d0e86b39875517e828b1ba0788133bee3c2184539c7d3c2c7d4f0a148511cea1`.
- Full XML: `C:\CaptivPortal-Lab\artifacts\TASK-ADMIN-SETTINGS-03-FIX2-full.xml`, SHA256 `e0f931dcb757a3aec2e5fcbab276be043c278e64fb7682c002dc42c436d836ba`.

Final post-test identity/status checks and patch hash/reverse-apply check matched the recorded candidate; working tree remained clean.

### Baseline-known Home failure

Independent clean detached baseline worktree:
`C:\CaptivPortal-Lab\as03-fix2-baseline-verification`.
Verified HEAD `b6927cf70207810cec9d6a8186e92f131ca1392f`, tree `06611fff6650fa0eb3be2e5ff301010146413fe7`, status empty.

```text
python -m pytest -q tests/admin_web/test_home_traffic.py::test_home_template_delivers_traffic_only_when_enabled --basetemp C:/CaptivPortal-Lab/tmp/as03-fix2-baseline-home-01 --tb=short --junitxml=C:/CaptivPortal-Lab/artifacts/TASK-ADMIN-SETTINGS-03-FIX2-baseline-home.xml
```

Result: **1 failed**, 0.66 seconds, exit 1. Exact assertion at `tests/admin_web/test_home_traffic.py:629`:
actual `[6850, 10547, 10471]`, expected `[6850, 10471, 10547]`.
The clean-candidate focused failure is identical. The unrelated test and Home markup were not changed.
Baseline XML SHA256: `5e1ec9a78166f9ddfb5b1e7010a8c6c23a9ab4183730942badb53bb450340649`.

### Iterations disclosed

The initial direct check caught an error in the new test assertion (`HomeAP24TelemetryWorker` has no `running` property); the assertion was corrected to its actual unstarted thread field. The final direct run passed all 22 tests.
The initial focused run before the commit additionally failed the startup artifact-identity gate because the worktree was dirty. The clean immutable candidate repeat removed that infrastructure failure without weakening the gate; its only remaining failure is baseline-known Home.

## Mandatory FIX2 coverage

| Requirement | Evidence |
|---|---|
| FIX2-01 | Fresh runtime disabled, workers not running, ProviderSpy untouched. |
| FIX2-02 | Real disposable SQLite preparation, readiness true, state still disabled, no worker/thread/provider access. |
| FIX2-03 | Repeated preparation initializes exactly once. |
| FIX2-04 | Prepared start initializes once, starts all configured workers, preserves abandoned_cycles=1 startup telemetry. |
| FIX2-05 | Same start regression parameterized without preparation; backward-compatible result. |
| FIX2-06 | Local initialization failure becomes unavailable, one failure event, no worker/provider calls. |
| FIX2-07 | Prepared-but-not-started actual Observation produces active actual Analytics, query-only schema-validated source. |
| FIX2-08 | Unprepared disabled runtime remains unavailable; prepared wrong-schema source also remains rejected. |
| FIX2-09 | Actual Analytics/Admin composition yields ready sources, non-null query service and active HomeAP24 service. |
| FIX2-10 | Actual HomeAP24 telemetry worker composes without starting or emitting composition-failure symptoms. |
| FIX2-11 | run.main integration orders prepare < Analytics < Admin < durable adoption < Observation start. |
| FIX2-12 | Provider spy asserts durable adoption before every simulated provider call; adoption-failure case produces zero calls. |
| FIX2-13 | Pending cleaner, Observation, Current State and Visitor collector starts all follow durable adoption. |
| FIX2-14 | app.run is last after worker-start phase; not invoked on adoption failure. |
| FIX2-15 | Existing Stage3 Controller Settings coverage included in clean focused run. |
| FIX2-16 | Existing Stage1 General Settings coverage included in clean focused run. |
| FIX2-17 | Observation/Analytics/Admin/HomeAP24 coverage included; sole focused failure is exact baseline-known Home ordering defect. |

No production behavior has been verified on Linux/production; this is local regression evidence, not production acceptance. Official Central Lab was not run. Candidate acceptance and publication remain pending Tech Lead review. Production remains untouched; no earlier startup-delay claim is made.

## Repository actions and Owner/Tech Lead next step

Created a separate isolated repair worktree/branch and one local commit; created a separate clean detached baseline verification worktree. Existing Settings/DTI/other worktrees were not edited. No push, PR, merge, deploy, service restart or production operation.

Tech Lead: review exact complete patch/candidate and the reported baseline-known failure before any publication authorization.

Agent execution summary: Coder / Codex on Windows; bounded lifecycle implementation; 3 production files, 4 test files (2 new); local focused/static/full verification as expressly assigned by this TASK; no official Central Lab, Linux/PERF or production gate; local immutable candidate only; no subagents.

```ini
PUSH=NO
PR=NO
MERGE=NO
DEPLOY=NO
PRODUCTION_ACTION=NO
```
