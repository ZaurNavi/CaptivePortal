# Testing

Status: current
Updated: 2026-09-13
Central Lab governance effective: 2026-08-27
Documentation/current-state implementation baseline: `main@3dc85735ddf5d05dd20733d15dfe1c22c9c4fde5`
Production deployed HEAD: `3dc85735ddf5d05dd20733d15dfe1c22c9c4fde5`
Production tree: `8312658be3ba272998f46212d9bad76950e3867e`

## Responsibility model

`AGENTS.md` is the universal entry contract. This document is the detailed testing authority.

The current project model is:

```text
Coder / executor
→ minimal TASK/module-scoped automated tests
→ tests created/changed for the implementation
→ exact candidate / patch

Tech Lead
→ defines exact artifact, official gate procedure/commands and acceptance criteria

Owner
→ physical operator of C:\CaptivPortal-Lab
→ prepares/verifies exact Lab artifact
→ physically launches official regression

Owner + Tech Lead
→ analyze evidence
→ PASS / FAIL / return to Coder
```

Cross-module regression, broader regression, full repository suite, release gate, differential baseline/candidate gate and official acceptance are outside Coder test execution.

### Coder / executor

The Coder keeps both the right and the responsibility to perform the **minimum local automated verification of the work being implemented**.

Allowed Coder verification:

- focused tests for the module/component changed by the TASK;
- the minimum TASK-scoped set needed for local self-check;
- tests for files/classes/scenarios directly affected by the change;
- regression cases created with the implementation;
- repeated local runs of those same TASK/module-scoped tests during development/fixes;
- relevant static/syntax/frontend checks;
- `git diff --check`.

Coder may create and modify automated tests that belong to the implemented change.

Coder must **not** independently expand execution to:

- unrelated modules;
- cross-module regression;
- broader regression;
- full `pytest` / full repository suite;
- release gate;
- differential baseline/candidate gate;
- official acceptance.

If a required proof test crosses the TASK/module boundary, exactly two normal paths exist:

1. Coder identifies the additional test/gate and requests Owner/Tech Lead/Central Lab execution.
2. Coder implements or prepares the required cross-module/regression test, but does **not** execute it; execution remains Owner/Tech Lead/Central Lab responsibility.

### Tech Lead / Reviewer

The Tech Lead normally verifies architecture, TASK/ADR conformance, implementation boundaries/DIFF, contracts, risk, Coder focused evidence and whether changed tests cover the intended behavior.

The Tech Lead owns the technical direction of broad/system testing: exact artifact, gate procedure/commands, acceptance criteria and evidence analysis. The Owner is the default physical Central Lab operator.

Owner / Tech Lead / Central Lab own:

- cross-module regression;
- broader regression;
- full `pytest` / full repository suite;
- release gate;
- differential baseline/candidate gate;
- official PASS / FAIL and acceptance.

### Central Lab ownership rule

**CURRENT governance state, effective 2026-08-27.**

`C:\CaptivPortal-Lab` and the official full repository regression cycle are controlled exclusively by **Owner / Tech Lead**.

```text
Tech Lead
→ exact artifact
→ gate procedure / commands
→ acceptance criteria
→ evidence analysis

Owner
→ physical Lab operator
→ prepares / verifies C:\CaptivPortal-Lab exact artifact
→ launches official regression
→ captures raw result/evidence

Owner + Tech Lead
→ PASS / FAIL / return to Coder
```

Coder is not an operator of the official Central Lab gate.

Coder may touch `C:\CaptivPortal-Lab` only after an explicit Owner/Tech Lead prep-only instruction, for example to prepare an exact candidate, patch a specified Lab working directory, or place required artifacts. After that preparation Coder stops; the official cycle returns to Owner/Tech Lead **before execution**.

Coder-run focused/module tests are development evidence, never the official repository regression gate.

A successful full gate on an unchanged exact artifact must not be duplicated merely for formality.

## Official Windows Central Lab

### Canonical directories

```text
Central Lab repository:
C:\CaptivPortal-UI-Preview

Central Lab support directory:
C:\CaptivPortal-Lab
```

### Manual pytest environment

Current verified environment on 2026-08-29:

```text
Python: 3.10.11
pytest: 9.1.1
canonical interpreter:
C:\CaptivPortal-UI-Preview\.venv\Scripts\python.exe
```

Repository development dependencies are restored from:

```text
requirements-dev.txt
```

Current repository constraint:

```text
-r requirements.txt
pytest>=8.0,<10.0
```

Recommended new CMD session:

```bat
cd /d C:\CaptivPortal-UI-Preview
call .venv\Scripts\activate.bat
where python
```

The first `where python` result must be:

```text
C:\CaptivPortal-UI-Preview\.venv\Scripts\python.exe
```

A user/system Python such as `...AppData\Local\Programs\Python\Python310\python.exe`
is not the canonical Central Lab interpreter.

Environment restore:

```bat
C:\CaptivPortal-UI-Preview\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

Do not install an arbitrary pytest version separately when `requirements-dev.txt`
already defines the supported range.

### Manual pytest temp isolation

Manual Central Lab pytest runs must use:

```text
repository .venv
+
explicit --basetemp under C:\CaptivPortal-Lab\tmp\<run-name>
```

Example:

```bat
if exist "C:\CaptivPortal-Lab\tmp\traffic01-cross-surface" rmdir /s /q "C:\CaptivPortal-Lab\tmp\traffic01-cross-surface"
mkdir "C:\CaptivPortal-Lab\tmp\traffic01-cross-surface"

C:\CaptivPortal-UI-Preview\.venv\Scripts\python.exe -m pytest -q -rs ^
  tests\admin_web ^
  --basetemp="C:\CaptivPortal-Lab\tmp\traffic01-cross-surface"
```

Use a dedicated descriptive directory per independent run and clean it before reuse.

### Current verified full runner

As of 2026-09-12, the current Windows Central Lab full-regression runner is:

```text
C:\CaptivPortal-Lab\lab-test-v7-strict.cmd
SHA256=45d3b37150a2c3b3d3e95460b2a1c6cab8d97aa333c3d3e0cd3507ef1c994f77
```

Canonical invocation:

```bat
call C:\CaptivPortal-Lab\lab-test-v7-strict.cmd C:\CaptivPortal-UI-Preview
```

V7 contract:

```text
[1/4] ordinary full strict pytest
[2/4] compileall
[3/4] branch diff check
[4/4] exact-artifact immutability
```

The six former Windows compatibility exclusions are now ordinary strict tests:

```text
SQLite infinity edge
Node retry async timing
Visitor Registry long audit
Visitor Registry previous-ready
Visitor Registry previous-stopping
Home Health unavailable analytics baseline
```

Current handling for those six:

```text
compatibility allowlist=EMPTY
special --deselect path=NO
separate compatibility stage=NO
compatibility WARN counter/path=NO
strict failure degrades to WARN=NO
```

A failure in any of these cases is a normal strict regression failure.

Accepted TASK-TEST-BASELINE-CLEANUP-01 V7 evidence:

```text
3129 passed
30 skipped
0 failed
0 deselected
strict regressions=0
compileall=PASS
branch diff=PASS
exact-artifact immutability=PASS
```

The exact `3129 / 30` counts are evidence of that accepted run, not a permanent
hardcoded acceptance invariant. The durable invariant is that the former six
cases execute in the ordinary strict suite and cannot escape as compatibility
WARN.

Historical runner:

```text
C:\CaptivPortal-Lab\lab-test-v6-fixed.cmd
status=HISTORICAL / AUDIT ONLY
```

V6 is deliberately retained and not rewritten because it records the older
compatibility contract. It is no longer the current/default gate.

### Gate-version anti-drift rule

Permanent invariant:

```text
CURRENT GATE IS DISCOVERED AND VERIFIED,
NOT BLINDLY TRUSTED FROM DOCUMENTATION.
```

Before every official full regression, Owner / Tech Lead must verify:

1. exact candidate;
2. exact approved baseline;
3. actual runner files present in `C:\CaptivPortal-Lab`;
4. which runner was last reviewed/approved successfully;
5. runner strict/platform-exception contract against the current approved baseline;
6. reviewed platform exception list (EMPTY for the former six compatibility cases);
7. current repository test set;
8. TASK-specific / cross-surface acceptance invariants.

Canonical state is the combination:

```text
TEST RUNNER
+
REPOSITORY BASELINE
+
REVIEWED PLATFORM EXCEPTIONS (if any)
+
CURRENT TEST SET
+
TASK-SPECIFIC / CROSS-SURFACE ACCEPTANCE INVARIANTS
```

A higher filename version is not automatically correct. A documented current version
is not permanently current either.

If documentation names an older runner than verified Lab state:

```text
classify as documentation/tooling drift
→ use verified current runner
→ update canonical KB
```

### Clean-candidate requirement

The official full runner requires a clean candidate tree.

A patch only applied through `git apply --index ...` is still a staged modification,
not a clean immutable candidate.

For Central Lab acceptance a local detached LAB ONLY candidate commit is allowed:

```bat
git -c user.name="CaptivPortal Central Lab" ^
    -c user.email="central-lab@local.invalid" ^
    commit -m "LAB ONLY: <TASK> candidate"
```

Required before gate:

```text
git status --short → empty
HEAD^ → exact approved baseline
```

LAB ONLY commit:
- is not pushed;
- is not a PR;
- is not merged;
- does not change origin/main;
- is not production deployment;
- exists only to provide an immutable Central Lab candidate.

Official repository publication remains a separate workflow.

### Failure classification

An infrastructure failure before test logic is not automatically a candidate regression.

Infrastructure examples:
- wrong Python interpreter;
- pytest missing;
- inaccessible pytest temp directory;
- malformed Lab environment;
- official runner refusing a dirty candidate.

Canonical response:

1. identify infrastructure cause;
2. restore canonical Lab environment;
3. rerun the same test scope;
4. classify actual assertion/product-behavior failures as candidate regressions;
5. if origin is disputed, compare candidate and exact baseline in the same environment.

### Historical TRAFFIC-00 Windows incident

During TRAFFIC-00 acceptance:
- an initial manual `python -m pytest` resolved to system Python and returned `No module named pytest`;
- repository `.venv` then confirmed Python 3.10.11 / pytest 9.1.1;
- a shared Admin run later hit `PermissionError: [WinError 5]` in the user's pytest temp directory during fixture setup;
- visible progress included 244 passed and 142 setup errors from the common temp infrastructure failure;
- this was not classified as a TRAFFIC-00 product regression;
- the rerun was moved to a dedicated `C:\CaptivPortal-Lab\tmp\...` basetemp.

This is troubleshooting history, not a current product defect.

### Latest Windows baseline cleanup acceptance — TASK-TEST-BASELINE-CLEANUP-01

Artifact identity:

```text
accepted baseline=75df5af1500ebcaf7d4950abccbaabc0a03610e1
publication commit=ef3e8ca20e2303c29437c6c087919a6715afac96
PR #116=MERGED
merge / production=c1dc3344bc778a32cdc6b0edce278ee40b287c29
accepted / merged / production tree=0563f58cf2a5c961e1dedb52cfa2b4b298dd2c1c
```

Current Windows gate:

```text
V7 strict=PASS
runner SHA256=45d3b37150a2c3b3d3e95460b2a1c6cab8d97aa333c3d3e0cd3507ef1c994f77
former six compatibility exclusions=ordinary strict tests
compatibility allowlist for former six=EMPTY
WARN escape for former six=REMOVED
```

Accepted run evidence:

```text
3129 passed
30 skipped
0 failed
0 deselected
strict regressions=0
compileall=PASS
branch diff=PASS
exact-artifact immutability=PASS
```

Production acceptance:

```text
traffic-projection.service=active
Projection status=healthy
backlog=0
captive-portal.service=active
analytics.api_runtime_active
127.0.0.1:8088 LISTEN
HTTP readiness=400
```

Historical `Windows Central Full V6=PASS` entries below remain valid evidence for
the older TASKs that actually used V6; they do not define the current runner.

### Home operational implementation evidence — repository inventory correction

The current repository also contains earlier merged Home subsystems that were
underrepresented in the current KB inventory:

```text
PR #74  Home System Health                    MERGED
PR #78  Home AP-24H                           MERGED
PR #79  AP-24H duration-partition fix         MERGED
PR #80  AP-24H frontend activation fix        MERGED
PR #81  AP-24H operational telemetry          MERGED
```

Their historical PR test/acceptance evidence remains valid. This reconciliation
only restores current documentation routing; it does not invent current
production feature-flag values.

### Latest Device Type / Home presentation acceptance — PR #118 / #119 / #120

PR #118:

```text
Home Online Devices presentation=PASS
narrow frontend gate=4/4 PASS
Owner visual acceptance=PASS
Central Lab V7 strict=PASS
strict regressions=0
```

PR #119:

```text
TASK-DEVICE-TYPE-NORMALIZATION-01=CLOSED
Coder focused tests=38 PASS
compileall=PASS
git diff --check=PASS
Central Lab V7 strict=PASS
accepted tree=2349838d7e524efd3fb2e0433a7111553f195e71
```

PR #120:

```text
Owner Visual Acceptance=PASS
Central Lab V7 strict=PASS
strict regressions=0
LAB commit=b6bf602873fcf4a41e21ced6c0fe1be18ce0f483
accepted / merge tree=8312658be3ba272998f46212d9bad76950e3867e
production visual acceptance=PASS
```

The older `case-insensitive Android matching=PASS` evidence below belongs to the
historical WEB-ASSET-LIBRARY/FIX acceptance. It does **not** define the current
browser contract after PR #119/#120.

Current browser contract:

```text
Android machine decision=device_type_key === "android"
raw browser trim/lower/casefold normalization=NO
```

### Latest Admin Web presentation acceptance — WEB-ASSET-LIBRARY-01 + FIX

```text
TASK-WEB-ASSET-LIBRARY-01=CLOSED / PRODUCTION PASS
TASK-WEB-ASSET-LIBRARY-01-FIX-ANDROID-PRESENTATION=CLOSED / PRODUCTION PASS
PR #113 accepted=0b3a692684d5d87ca7b96cf75c722dda7e2e8cf3
PR #113 merge=5d1a590d1d575eeea8148ca868b9de5183c0fff5
FIX patch SHA256=c11bba2544124bc448f1d1a63a295dda479f0ab81cd430e2dbd6cc829509189b
PR #114 accepted=d207e048f0fcdec685d3bae1f8497fdbdcd611d4
PR #114 merge / production=043a13bc1e3aa3353e27af1859dc0bb698df4955
```

```text
patch application=PASS
git diff --check=PASS
bounded Admin Web tests=12/12 PASS
case-insensitive Android matching=PASS
Devices list LAB visual=PASS
Device Detail Identity LAB visual=PASS
Device Detail evidence LAB visual=PASS
Owner visual acceptance=PASS
production delivery verification=PASS
Owner production visual acceptance=PASS
```

The production defect was presentation matching only. Backend/API/data semantics
were not changed.

### Latest Projection lifecycle P0 acceptance — TASK-TRAFFIC-PROJECTION-LIFECYCLE-CONSISTENCY-01

Artifact identity:

```text
baseline=ff39fe888c53361a7c65a034eaddb0ce92cc4a12
accepted PR head=a0dc02d5ae0ff16c250cf46a7e7a610c24e6f433
accepted tree=3950df6d400049ed16a823032c6740396cd61137
PR #111=MERGED
merge / production=7472d67274ea5aaea2a20df6b613b78d5bb70f42
```

Pre-publication acceptance:

```text
Source Review=PASS
Windows Central Full V6=PASS
strict regressions=0
Linux targeted=132 PASS
Linux full=3154 PASS, 1 SKIP
3 known baseline/environment failures reproduced on clean base
candidate-specific regressions=0
```

Production recovery acceptance:

```text
forensic preflight/backup=PASS
exact deployed artifact identity=PASS
first durable repair quantum=PASS
persisted repair continuation=PASS
bounded delete phase=PASS
rebuild=PASS
full reconcile=PASS
deep audit=PASS
source/projection head coherence=PASS
backlog=0
DB quick_check=ok
Projection health=healthy
Historical Web panels=PASS
worker active=PASS
worker enabled/autostart=PASS
```

Final Site sample:

```text
projection_revision=123634
status=healthy
last_error_category=NULL
projection_head_utc=2026-09-11T13:18:00.739Z
source_head_utc=2026-09-11T13:18:00.739Z
last_full_reconcile_completed_at=2026-09-11T13:17:46.393Z
last_deep_audit_at=2026-09-11T13:17:46.393Z
backlog_cycle_count=0
```

Owner manual Web verification proved the restored path:

```text
Observation
→ Traffic Projection
→ Historical read service
→ Web UI panels
```

Final verdict:

```text
P0 INCIDENT=CLOSED
PRODUCTION ACCEPTANCE=PASS
```

Non-blocking telemetry observation:

```text
healthy → stale → healthy
during active reconcile sweep
```

With no error category, no worker failure and final healthy state, this remains
an observation only, not a regression/incident.

### Latest Device acceptance evidence — TASK-DEVICE-CARD-01

```text
TASK=TASK-DEVICE-CARD-01 — Current Device Context
PR=#108
PR base=3eac6f13d5f3966574f6d1b0a10f531d988f91ec
implementation commit=1a3f2b8a844f2ce1c26cbdd9e4c44d17a201ac14
accepted / production tree=8f1342f0a0f1e8242642161e02b2f3276e6ddf51
merge / production commit=7df71a8e807efd74b123117e78cb8d992c190fa1
```

Acceptance:

```text
implementation=PASS
Owner + Tech Lead acceptance=PASS
cross-surface focused gate=178 passed
Official Windows Central Full V6=PASS
strict regressions=0
bounded exact-read/query-plan gate=PASS
Controlled Browser acceptance=PASS
production deploy=PASS
production activation=PASS
Owner manual production Web UI verification=PASS
```

Controlled Browser scenarios explicitly covered:

```text
online
pending
offline
stale
invalid timestamp
Current endpoint 503
Traffic technical failure
valid numeric zero
manual Refresh
no Current overlap
no automatic polling
```

Semantic acceptance:

```text
historical Device context != current Device context
offline requires fresh + complete managed scope
stale/unavailable/invalid timestamp != offline
traffic failure does not erase Current State
0 Mbps != unavailable
Current State execution failure is controlled independently
```

No schema/index/migration/write path or query-time Omada was introduced.

At DEVICE-CARD-01 acceptance time, `TASK-WEB-DEVICE-UI-01` was a separate pending follow-on. It later closed through PR #110:

```text
IN PROGRESS / LAB REVIEW PENDING
NOT MERGED
NOT DEPLOYED
```

### Latest Traffic acceptance evidence — TRAFFIC-09

Canonical artifact:

```text
TASK=TASK-TRAFFIC-09 — Consolidated Traffic Evidence
previous baseline=f57d3550ffd2e1e48f24092666d861a959c57e40
implementation commit=6729e5bc45c810423cf739ebd8fc2685f6098a3d
accepted / production tree=2766139c83965dcf2f80e0c8084b3fb363dbd781
PR #106=merged
merge / production commit=e32ade378bdbfc9f8458db9c18221958f4552718
TASK-TRAFFIC-09=COMPLETED / PRODUCTION ACTIVE
TASK_TRAFFIC_09_PRODUCTION=ACTIVE
```

Acceptance:

```text
Architecture/specification=accepted
Implementation=accepted
Windows Central Full=PASS
Windows regressions=0
Linux Full=PASS WITH BASELINE EXCEPTIONS
Linux full=2921 passed, 1 skipped, 3 known baseline failures
Linux new failures=0
Linux regressions=0
Official production-size PERF=PASS
Publication=PASS
PR merged=PASS
Production deploy=PASS
Production activation=PASS
Authenticated production smoke=PASS
Owner manual Web UI verification=PASS
```

Official production-size PERF used an immutable approximately 572 MiB snapshot
of:

```text
observations
visits
traffic_projection
current_state
visitor_registry
```

Results:

```text
24h runs=10
24h p95=0.0730241s
24h max=0.0730241s
24h max response=4813 bytes
24h HTTP failures=0
24h deadline failures=0

7d runs=10
7d p95=0.0724418s
7d max=0.0724418s
7d max response=4806 bytes
7d HTTP failures=0
7d deadline failures=0

payload <=65536 bytes=PASS
```

Thresholds:

```text
24h p95<=5s; max<=10s
7d p95<=7s; max<=12s
```

Read-call contract across 20 Evidence requests:

```text
current_site_calls=20
current_ap_calls=0
historical_calls=20
online_calls=20
completed_calls=20
provider_calls=0
writes=0
collection_cycles=0
source DB fingerprints=UNCHANGED
```

Production authenticated smoke:

```text
Admin login GET=200
Admin login POST=302
authenticated session=200
Traffic page=200
Evidence UI=PASS
Evidence 24h=200
Evidence 7d=200
logout=302
api_version=admin.read.v1=PASS
contract_version=admin.traffic.evidence.v1=PASS
exact 8 products=PASS
canonical product_id validation=PASS
TASK_TRAFFIC_09_PRODUCTION_SMOKE=PASS
```

For both ranges every canonical product returned:

```text
exposure=enabled
delivery=available
failure=None
```

The three Linux failures are existing documented baseline exceptions, not
TASK-TRAFFIC-09 regressions.

### Previous Traffic acceptance evidence — TRAFFIC-08

Canonical artifact:

```text
TASK: TASK-TRAFFIC-08 — Completed Guest Session Traffic
parent baseline: 3761981f4b1ec30b330abe1eec1713f15191c711
accepted implementation commit: 8cfe30c2bcb13bf3ca7e001238991abd5943ea08
accepted / production tree: 1161739c6b4fe90fa08928556746a5a4ea6af4cd
PR #104: merged
merge / production commit: df91355a99d2561abc9c4d6d4bb6f5a968d327b3
R6 patch SHA256: 6077ea09f6f1421d43f2602cbea6beeae436faf5dc19a032ed520cf348efbbfa
production deployment: PASS
feature activation: PASS
production verification: PASS
new failures: 0
regressions: 0
```

Windows acceptance:

```text
reconstruction: PASS
focused: 50 passed
regression: PASS_WITH_BASELINE_EXCEPTIONS
canonical PERF: PASS
full suite: PASS_WITH_BASELINE_EXCEPTIONS
TASK-TRAFFIC-08 regressions: 0
```

Owner Linux Lab:

```text
reconstruction: PASS
focused: 50 passed
regression: PASS_WITH_BASELINE_EXCEPTIONS
PERF: PASS
full suite: 2892 passed, 1 skipped, 3 baseline failures
TASK-TRAFFIC-08 new failures: 0
```

Canonical Linux PERF:

```text
API50 p95=1.3743s <=2.0s
API50 max=1.3743s <=3.0s
API100 p95=2.3960s <=4.0s
API100 max=2.3960s <=6.0s
deadline failures=0
unexpected HTTP statuses=0
provider calls=0
payload <=256KiB=PASS
five source DB fingerprints unchanged=PASS
```

Required existing indexes confirmed:

```text
idx_visits_site_closed
idx_visit_auth_visit_time
idx_client_site_mac_time
```

TRAFFIC-08 added no new index.

Confirmed baseline exceptions outside TRAFFIC-08:

1. `tests/analytics/test_current_traffic.py::test_sql_integrity_aggregates_reject_corrupt_rate_and_null_values[wired_download_mbps-inf-bad_rate_count]`
2. `tests/test_auth_retry_frontend.py::test_lost_retry_response_reconciles_active_run`
3. Linux SQLite EXPLAIN planner:
   `tests/analytics/test_historical_traffic_peak.py::test_peak_projection_reuses_one_materialized_requested_range_validation`
4. Linux SQLite EXPLAIN planner:
   `tests/analytics/test_historical_traffic_statistics.py::test_combined_projection_materializes_one_expensive_validation_path`
5. Visitor Registry `[stopping]` timing race — baseline-flaky.

These exceptions must not be attributed to TRAFFIC-08 and were neither fixed nor
suppressed by the TASK.

Production closure:

```text
WEB_ADMIN_TRAFFIC_COMPLETED_SESSIONS_ENABLED=true
traffic page=HTTP 200
completed-sessions API=HTTP 200
panel/heading=FOUND
Visits source=healthy
Observation source=healthy
API_PARSE=PASS
```

### Previous Traffic acceptance evidence — TRAFFIC-07

Current accepted repository / production artifact:

```text
HEAD: 6425988b5b4ec5ff38bf9c67c74846c3806f668f
tree: b669f368b0062fcb100b24758cf05e2c4b500144
TRAFFIC-07-READ: DONE / READ FOUNDATION IMPLEMENTED
TRAFFIC-07: COMPLETE / PRODUCTION ACTIVE
PR #98: merged
PR #99: merged
production deployment / activation: PASS
```

TASK-TRAFFIC-07 product gate evidence:

```text
Static review: PASS
Focused acceptance: 49 passed
Targeted regression: 175 passed
Central Lab V6: PASS
strict regressions: 0
Linux authenticated API PERF: PASS
payload <= 256 KiB: PASS
read-only: PASS
provider isolation: PASS
```

TRAFFIC-07-READ foundation evidence from PR #98:

```text
focused regression: 47 passed
broader Current State + Analytics: 783 passed / 3 skipped
candidate regressions: 0
Windows Central Lab V6: PASS
exact-artifact immutability: PASS
Linux 10k-row read-only PERF/capacity: PASS
```

The known Windows/SQLite infinity behavior reproduced on the exact PR #98
baseline and is not a candidate regression.

### Previous Traffic acceptance evidence — TRAFFIC-06

Current accepted repository / production artifact:

```text
HEAD: c5f9dc39bbf399847f147526c9c7ae15769a198c
tree: 0831ecf598b5760e8ede2e9e94a25b926480c2dd
TASK-TRAFFIC-06: DONE / PRODUCTION ACTIVE
PR #96: merged
production activation / browser acceptance: PASS
```

Gate matrix:

```text
Tech Lead Static Review: PASS
Targeted Traffic Regression: PASS WITH REVIEWED COMPATIBILITY
Candidate regressions: 0
Windows Central Lab V6-FIXED: PASS
Strict regressions: 0
Exact-artifact immutability: PASS
Linux production-size PERF: PASS
CORE_PERF_GATE=PASS
ALL24_CAPABILITY=PASS
G1_G2_FALLBACK_CAPABILITY=PASS
IMMUTABILITY=PASS
RESULT=PASS
```

Production-size snapshot:

```text
bytes: 273235968
SHA256: b65a2ce7718454571f08c474c1b59045c3da415d1e160a55725d5095e49287eb
```

Key measured p95/max:

```text
SH24 0.614524s / 0.698018s
SH7  2.751386s / 2.795773s
CA7  3.057368s / 3.291041s
AS7  3.099320s / 3.113963s
E24-C 0.740699s / 0.830057s
ALL24 0.584355s / 0.595118s
```

All measured variants completed `10/10` successfully with `query_deadline=0`, `source_integrity=0`, `unexpected_5xx=0`; semantic stability PASS.

Accepted ALL24 grouping: `history,statistics,peak,aps,apshare`.

The reviewed Windows compatibility cases are not candidate regressions.

Production closure: deploy FROM GIT → dormant PASS → separate activation → browser/product PASS.

## Test environment routing and production boundary

Canonical detailed contract: `testing-environments.md`.

Permanent three-contour model:

```text
Windows Central Lab
→ Windows/general acceptance and browser/UI gates

Dedicated laptop WSL/Linux Lab
→ Linux/pre-production/PERF/SQLite/WAL/storage/concurrency gates

Production 192.168.0.202
→ production runtime / separately authorized production validation only
```

Dedicated Linux Lab identity:

```text
host: DESKTOP-7C8M3BS
user: zaur_navi
known workdirs:
  ~/captivportal-lab
  ~/captivportal-traffic07-perf
```

Permanent invariant:

```text
PRODUCTION IS NOT AN ACCEPTANCE OR PERFORMANCE TEST HOST.
```

SSH access and Linux availability on production do not authorize using it as a
Linux acceptance/PERF machine.

When production-like data is required:

```text
Production
→ safe/read-only snapshot or approved copy
→ dedicated WSL/Linux Lab
→ isolated candidate DB/output
```

Before using an allowlisted worktree path, check `git worktree list` and path
occupancy. Prefer a new detached worktree in the required path over
`git worktree move`.

Command/paste/permission/interpreter/readiness failures are harness or
infrastructure errors until product behavior is actually exercised. Permanent
execution lessons are in `operations-command-lessons-learned.md`.

## Test Set Maintenance Rule

Every accepted TASK / module / Admin panel / API / read-service change requires a
fresh review of the actual test set.

Coder handoff must explicitly list:
- new test files;
- existing test files changed;
- exact focused/minimal command;
- result of the allowed focused run.

After implementation handoff, Tech Lead / Assistant Tech Lead must determine:
1. which new tests belong to TASK-focused verification;
2. which existing modules belong to targeted Central Lab regression;
3. which new cross-surface invariants exist;
4. which test files belong in the current targeted regression command;
5. whether the full repository test set changed;
6. whether the Central Lab runner itself changed, or only the targeted command/test set changed.

Permanent flow:

```text
NEW MODULE / PANEL / FEATURE
→ NEW OR CHANGED TESTS
→ TECH LEAD TEST-SET REVIEW
→ UPDATED TARGETED REGRESSION COMMAND
→ CENTRAL LAB ACCEPTANCE
```

Do not keep using an old targeted command merely because it was correct for the
previous TASK.

Adding an ordinary pytest file does not by itself require editing the full runner
when normal full discovery already includes that file.

Change the Central Lab runner only when its own contract changes, for example:
- reviewed compatibility case/classification changes;
- a new mandatory acceptance phase;
- changed isolation/execution model;
- repository/test-layout assumptions change;
- new mandatory gate environment/dependency.

Never add a new failure to compatibility merely to obtain a green candidate.

### Current TRAFFIC-07 targeted set

For the current TRAFFIC-07 state, relevant coverage includes at minimum:

- `tests/analytics/test_current_guest_traffic.py`;
- `tests/admin_web/test_traffic_online_guests.py`;
- `tests/admin_web/test_traffic_online_guests_frontend.py`;
- current guest traffic capacity/PERF benchmark coverage;
- Current State read-service regressions;
- Admin config/routes/query/capability/pagination regressions;
- existing Traffic regressions proving historical/current product isolation.

Permanent TRAFFIC-07 invariants:
- `CurrentGuestTrafficReadService` remains semantic owner;
- persisted Current State remains the calculation source;
- numeric rates require valid counter/continuity evidence;
- missing/frozen/reset evidence must not fabricate numeric zero;
- cursor chains remain deterministic and bounded;
- Online Guests Traffic remains range-insensitive;
- query-time Omada isolation remains intact.

`TASK-DB-BASELINE-SYNC-01` is CLOSED / PASS, `TASK-TRAFFIC-08` is
CLOSED / DEPLOYED / ACTIVE / PRODUCTION VERIFIED, and `TASK-TRAFFIC-09` is
COMPLETED / PRODUCTION ACTIVE. No next Traffic TASK is currently assigned;
Tech Lead must define a fresh targeted set when a successor TASK is separately
approved.

## Acceptance before Publication

This is permanent project governance.

Candidate acceptance means:

```text
ALL mandatory gates required by TASK / FINAL / release contract
PASS on the exact candidate tree
```

Mandatory gates may include:

- focused / targeted;
- Central Lab full/V6;
- cross-surface regression;
- Linux/production-compatible;
- production-size PERF/capacity;
- migration/schema compatibility;
- security/browser acceptance;
- any explicit TASK-specific gate.

Canonical invariant:

```text
Patch → Lab.
All mandatory gates → PASS.
Accepted candidate → Git.
Git → Production.
Activation → separate step.
```

A successful V6/full gate does **not** by itself authorize publication when a
mandatory PERF/Linux/security/etc. gate remains.

Example:

```text
targeted PASS
V6 PASS
PERF FAIL
=
candidate REJECTED
publication NOT AUTHORIZED
```

After remediation, a changed tree is a new candidate. Tech Lead determines the
required rerun matrix; if FINAL requires the same official PERF matrix, it must be
repeated before acceptance.

### Linux / production-compatible mandatory gates

A mandatory Linux/PERF gate is pre-publication acceptance.

Normal workflow must not be:

```text
publish candidate to GitHub
→ fetch on production
→ perform still-pending mandatory acceptance
```

Use an isolated Linux Central Lab or equivalent controlled acceptance environment.

Candidate transport may be patch/local bundle/controlled worktree materialization
with exact tree verification. GitHub publication is not required as Lab transport.

Production-size data may be supplied as an immutable/read-only snapshot. Evidence
must prove candidate tree identity, snapshot identity, no production DB writes,
snapshot unchanged after test, production checkout unchanged and service unchanged
where the gate contract requires those checks.

### Experimental publication exception

A pre-acceptance GitHub publication is allowed only as explicit:

```text
TEST-ONLY / EXPERIMENTAL PUBLICATION
NOT ACCEPTED
NOT MERGEABLE
NOT DEPLOYABLE
```

with Owner + Tech Lead authorization.

It is not the normal release workflow.

### Chain-of-custody after acceptance

Where merge strategy preserves the tree:

```text
accepted candidate tree
=
publication commit tree
=
PR head tree
=
accepted merge tree
```

If a production/test file changes after acceptance, it is a new candidate tree
and necessary gates must be reconsidered/repeated.

## Linux / production-compatible gate

The Windows Local Gate does **not** replace, weaken or waive Linux pre-production acceptance.

When a deploy/release contract requires a Linux or other production-compatible full gate, it is executed separately on the exact artifact in the required environment.

Canonical Linux gate remains:

```bash
python -m pytest -q -rs
PYTHONPYCACHEPREFIX=/tmp/captivportal-pyc python -m compileall -q app
git diff --check
```

The deploy/release TASK identifies who executes that environment-specific acceptance. It is not automatically assigned to the Coder or Tech Lead merely because they implemented/reviewed the change.

Windows compatibility WARNs do not automatically transfer to Linux; platform-specific results are classified in their own evidence.

## Evidence contract

Every claimed targeted or full test result must identify, as applicable:

- exact artifact/baseline;
- exact command or approved lab gate version;
- environment;
- passed/skipped/failed or strict-regression result;
- compatibility classification;
- `compileall` / `git diff --check` status where included;
- whether the result is Coder targeted evidence, Central Lab official evidence, or Linux pre-production evidence.

Historical green results remain historical. Never present a prior count as a current exact-artifact result after runtime/test changes.

## Reuse and non-duplication

Do not repeat an identical targeted or full run only to duplicate another role's evidence.

A rerun is justified when it provides new information, for example:

- a new patch/commit changed the tested artifact;
- a new risk or previously uncovered scenario must be checked;
- a different platform/environment is required;
- previous evidence is incomplete, contradictory or suspect;
- a deploy/production contract explicitly requires the independent environment gate.

## Current test map

Repository test root: `tests/`.

Coverage groups include:

- Portal/Auth/retry/session ownership;
- CAPPORT/discovery/frontend;
- telemetry/counters;
- Omada provider and webhook;
- Visitor Snapshot/Registry;
- Pending Session Cleaner;
- Visit Lifecycle including schema/write contention/reader/reconciliation;
- Observation;
- Current State;
- Analytics/API/Current Traffic;
- Admin Web/Home Live/Home Traffic;
- Traffic Foundation / Current / History / Period Statistics.

## CI

`.github/workflows` is absent at the documented runtime baseline. Automated GitHub release gating is not implemented; this remains process debt, not a runtime defect.

The Central Lab is the official manual full-regression source until a separately approved CI/release-gate architecture changes that responsibility.

## Documentation-only tasks

For a pure documentation change:

- no runtime pytest claim is required from the documentation executor;
- validate paths/links/claims against current sources;
- run Markdown/link tooling only if already available/relevant;
- run `git diff --check`;
- request a fresh Central Lab or Linux gate only when an owner/release contract requires exact-artifact runtime evidence.