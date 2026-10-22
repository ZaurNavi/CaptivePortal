# TASK-DEVICE-FINGERPRINT-06 — implementation handoff

```text
TASK = TASK-DEVICE-FINGERPRINT-06
BASE_COMMIT = 20ea385182972e8fb5b204815161bc6a5c7f13fb
BASE_TREE = 439ab64697f2fcdcd5e822527f287ca5404e45ba
BRANCH = feat/device-fingerprint-06-presentation-integration
COMMIT = bf4eba5973c6f23b8939396249fac987ae88bdf1
TREE = 53f8d463eab6dff413e8bbdcc6e181bd2bc25d7f
PARENT = 20ea385182972e8fb5b204815161bc6a5c7f13fb
FILES_CHANGED = 14

PART_A_1G_REPO_CONVERGENCE = PASS
OLD_96M_ACTIVE_OCCURRENCES = 0
HISTORICAL_96M_OCCURRENCES = 0 (remaining exact 100663296 literal in tracked repository)

PRODUCTION_ONLY_READ = PASS
HOME_BATCH_READ = PASS
NO_N_PLUS_1 = PASS

HOME_TYPE_FROM_FINGERPRINT = PASS
HOME_PLATFORM_EXISTING_CONTROLLER = PASS
NO_CONTROLLER_FALLBACK_TO_TYPE = PASS

DEVICE_CARD_FINGERPRINT_INFORMATION = PASS
CONTROLLER_PLATFORM_SEPARATE = PASS
FINGERPRINT_PLATFORM_SEPARATE = PASS
DIAGNOSTIC_DETAILS = PASS

NO_QUERY_TIME_CLASSIFICATION = PASS
NO_CLASSIFICATION_WRITE = PASS
FAIL_SOFT_PRESENTATION = PASS
AUTH_CAPPORT_UNCHANGED = PASS

FOCUSED_TESTS = 189 passed / 0 skipped / 0 failed / 0 errors
PY_COMPILE = PASS
GIT_DIFF_CHECK = PASS
WORKING_TREE = CLEAN

PUSH = NO
PR = NO
MERGE = NO
DEPLOY = NO
FULL_REPO_TESTS = NO
CENTRAL_LAB_RUN = NO
PRODUCTION_ACTIONS = NONE
KNOWN_BLOCKERS = NONE
TECH_LEAD_ACCEPTANCE = PENDING
```

## Architecture / result

The existing read service now exposes explicit single/batch PRODUCTION-only
methods without changing unrestricted `get_current()` or historical reads.
Latest production selection is Site/MAC-scoped and deterministic by timestamp
then classification UUID. A newer candidate cannot shadow production. The batch
accepts at most 250 input MACs, validates/canonicalizes/deduplicates them, opens
one read-only SQLite connection and transaction and executes at most two SELECTs
(core rows plus retained result artifacts), not one artifact read per device.
Existing persisted artifact identity/integrity and core validation are reused.

One typed Admin adapter projects the four dimensions and preserves classifier
metadata. Home receives only fingerprint Type state/value; controller Platform
retains the original field, normalization and Android icon. Device Card keeps
Controller Platform separate from Fingerprint Information, support badges and
expandable exact diagnostics. Values may disagree without reconciliation.
No result is `—`; completed unresolved dimensions are `Unknown`; storage or
projection failure is advisory `Unavailable`, with core page data preserved.
All reads remain under existing Admin Site authorization. No integration-job
read, query-time classification, DB initialization, persistence write, new public
endpoint or activation was added.

The current FA4 builder now materializes the already accepted 1 GiB guard.
Historical external acceptance evidence was not changed or regenerated. Updated
deterministic identity assertions still verify exact payload, repeated build and
recomputed hash. Current SnapshotExecutionPolicy identity:

```text
SnapshotExecutionPolicy:v1:sha256:36074993bb86daca8c43268c19ce0efab7e0e3ef5d644e07b9b6e65f5fff7f77
```

No Task-04 semantic acceptance, real gate or production policy activation was
performed. `rg -n '100663296' .` and `git grep -n '100663296' HEAD` found no
remaining exact old numeric occurrences. No historical document/evidence was
rewritten to remove an old value.

## Changed files / exact name-status

```text
A app/admin_web/device_fingerprint_presentation.py
M app/admin_web/query_service.py
M app/admin_web/runtime.py
M app/admin_web/static/admin.css
M app/admin_web/static/admin.js
M app/device_fingerprint/classification_read.py
M docs/modules/admin-web.md
M docs/modules/device-fingerprint.md
M research/device_fingerprint_fa4/finalization.py
M tests/admin_web/test_admin_ui_frontend.py
A tests/admin_web/test_device_fingerprint_frontend.py
A tests/admin_web/test_device_fingerprint_presentation.py
M tests/device_fingerprint_fa4/test_finalization.py
M tests/device_fingerprint_task04_04e_read/test_classification_read.py
```

Production/read code: typed presentation adapter; optional readonly composition;
Home/device API overlay; bounded batch reads; separate UI fields and scoped CSS.
Research: current operational memory policy convergence only. Documentation:
current Task-06 semantics and 1 GiB policy. Tests: focused presentation/read,
frontend and deterministic policy regressions.

New test files:

- `tests/admin_web/test_device_fingerprint_frontend.py`
- `tests/admin_web/test_device_fingerprint_presentation.py`

Modified existing test files:

- `tests/admin_web/test_admin_ui_frontend.py`
- `tests/device_fingerprint_fa4/test_finalization.py`
- `tests/device_fingerprint_task04_04e_read/test_classification_read.py`

## Exact focused verification

Workspace: `C:\CaptivPortal-Lab\coder-task05-identity-session`.
Platform: Windows / PowerShell; Python 3.10.11; Node v24.19.0.
No full suite, Central Lab, official Task-04 gate or production test was run.

Final command on the committed content:

```powershell
$env:PYTHONPYCACHEPREFIX='C:\CaptivPortal-Lab\tmp\task06-pyc'
& 'C:\CaptivPortal-UI-Preview\.venv\Scripts\python.exe' -m pytest -q tests/device_fingerprint_fa4/test_finalization.py tests/device_fingerprint_task04_04e_read/test_classification_read.py tests/admin_web/test_device_fingerprint_presentation.py tests/admin_web/test_device_fingerprint_frontend.py tests/admin_web/test_home_live.py tests/admin_web/test_query_service.py tests/admin_web/test_runtime.py tests/admin_web/test_admin_ui_frontend.py tests/admin_web/test_device_current_context_frontend.py tests/admin_web/test_home_traffic_frontend.py --basetemp='C:\CaptivPortal-Lab\tmp\task06-focused-final' --junitxml='C:\CaptivPortal-Lab\artifacts\TASK-DEVICE-FINGERPRINT-06-focused-final.xml'
```

Result: **189 passed, 0 skipped, 0 failed, 0 errors** in 29.89 seconds.
No source changes were made after this final focused run.

Per-file counts (all passed):

| Test file | Passed |
| --- | ---: |
| tests/device_fingerprint_fa4/test_finalization.py | 7 |
| tests/device_fingerprint_task04_04e_read/test_classification_read.py | 43 |
| tests/admin_web/test_device_fingerprint_presentation.py | 17 |
| tests/admin_web/test_device_fingerprint_frontend.py | 4 |
| tests/admin_web/test_home_live.py | 58 |
| tests/admin_web/test_query_service.py | 35 |
| tests/admin_web/test_runtime.py | 19 |
| tests/admin_web/test_admin_ui_frontend.py | 2 |
| tests/admin_web/test_device_current_context_frontend.py | 2 |
| tests/admin_web/test_home_traffic_frontend.py | 2 |

Implementation-stage reruns were limited to this same focused scope. Initial
failures were corrected: a mistaken static variable-name assertion, DOM helper
compatibility, and the Windows command-line length limit in a new Node fixture.
The latter fixture now executes a disposable external temporary script. No
skip/xfail/deselection or weakened expected behavior was introduced.

Syntax verification:

```powershell
$env:PYTHONPYCACHEPREFIX='C:\CaptivPortal-Lab\tmp\task06-pyc'
& 'C:\CaptivPortal-UI-Preview\.venv\Scripts\python.exe' -m py_compile app/admin_web/device_fingerprint_presentation.py app/admin_web/query_service.py app/admin_web/runtime.py app/device_fingerprint/classification_read.py research/device_fingerprint_fa4/finalization.py tests/admin_web/test_device_fingerprint_presentation.py tests/admin_web/test_device_fingerprint_frontend.py tests/admin_web/test_admin_ui_frontend.py tests/device_fingerprint_task04_04e_read/test_classification_read.py tests/device_fingerprint_fa4/test_finalization.py
git diff --check 20ea385182972e8fb5b204815161bc6a5c7f13fb bf4eba5973c6f23b8939396249fac987ae88bdf1
```

Both PASS. Pycache and test temporary state are outside the repository.

## Complete review patch

```text
PATCH_PATH = C:\CaptivPortal-Lab\artifacts\TASK-DEVICE-FINGERPRINT-06_BASE-to-TASK06.patch
PATCH_BYTES = 67333
PATCH_SHA256 = c1c5601603a9342451578f620fd8f6993ae60b5602c9b9e45a4cfb51fd7f7c1a
PATCH_FORMAT = git diff --binary --full-index BASE COMMIT
REVERSE_APPLY_CHECK = PASS
GIT_STATUS_SHORT = <empty>
```

Exported with:

```powershell
git diff --binary --full-index --output='C:/CaptivPortal-Lab/artifacts/TASK-DEVICE-FINGERPRINT-06_BASE-to-TASK06.patch' 20ea385182972e8fb5b204815161bc6a5c7f13fb bf4eba5973c6f23b8939396249fac987ae88bdf1
git apply --reverse --check 'C:/CaptivPortal-Lab/artifacts/TASK-DEVICE-FINGERPRINT-06_BASE-to-TASK06.patch'
```

Exact aggregate stat:

```text
 app/admin_web/device_fingerprint_presentation.py   | 137 +++++++++++++++
 app/admin_web/query_service.py                     |   7 +
 app/admin_web/runtime.py                           |  13 ++
 app/admin_web/static/admin.css                     |   6 +
 app/admin_web/static/admin.js                      |  87 +++++++++-
 app/device_fingerprint/classification_read.py      |  63 ++++++-
 docs/modules/admin-web.md                          |  31 ++++
 docs/modules/device-fingerprint.md                 |  20 +++
 research/device_fingerprint_fa4/finalization.py    |   2 +-
 tests/admin_web/test_admin_ui_frontend.py          |  16 +-
 .../admin_web/test_device_fingerprint_frontend.py  | 141 ++++++++++++++++
 .../test_device_fingerprint_presentation.py        | 188 +++++++++++++++++++++
 tests/device_fingerprint_fa4/test_finalization.py  |   6 +-
 .../test_classification_read.py                    |  88 ++++++++++
 14 files changed, 784 insertions(+), 21 deletions(-)
```

## Acceptance / next action

Implementation local self-check is complete; this is not a Task-06 acceptance or
publication declaration. Tech Lead reviews the exact candidate patch/tree and
owns any cross-surface, browser, broader/Central Lab or release acceptance.
Repository actions: dedicated feature branch and one local implementation commit
only. No push, PR, merge, deployment, activation or production access.

Agent: Codex / Windows, implementation mode. No delegated agent work. Existing
Auth/CAPPORT, collector, classifier/fusion, persistence schemas, retention,
integration job/lease/retry semantics and production configuration were unchanged.
