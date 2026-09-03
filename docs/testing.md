# Testing

Status: current
Updated: 2026-09-03
Central Lab governance effective: 2026-08-27
Documentation/current-state implementation baseline: `main@6425988b5b4ec5ff38bf9c67c74846c3806f668f`
Production deployed HEAD: `6425988b5b4ec5ff38bf9c67c74846c3806f668f`
Production tree: `b669f368b0062fcb100b24758cf05e2c4b500144`

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

As of 2026-08-29, the verified current Windows Central Lab runner is:

```text
C:\CaptivPortal-Lab\lab-test-v6-fixed.cmd
```

Canonical invocation:

```bat
call C:\CaptivPortal-Lab\lab-test-v6-fixed.cmd C:\CaptivPortal-UI-Preview
```

V6 owns its own isolated temp directory. Manual `--basetemp` policy must not be
blindly injected into the runner if the runner already owns temp isolation.

V4 is a historical previous runner. It must not be presented as the current/default
gate.

V6 is current because the reviewed Windows compatibility model now includes the
known Home Health baseline case:

```text
tests/admin_web/test_home_health.py::test_unavailable_analytics_is_one_component_not_health_503
```

On the exact baseline this case has the same expected/observed delta and is treated
as reviewed compatibility behavior rather than a new TASK regression. Compatibility
handling must never be broadened merely to make a failing candidate green.

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
5. runner strict/compatibility contract against the known compatibility baseline;
6. whether a new reviewed compatibility case exists;
7. current repository test set;
8. TASK-specific / cross-surface acceptance invariants.

Canonical state is the combination:

```text
TEST RUNNER
+
REPOSITORY BASELINE
+
KNOWN COMPATIBILITY BASELINE
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

### Latest Traffic acceptance evidence

Current accepted repository / production artifact:

```text
HEAD: 6425988b5b4ec5ff38bf9c67c74846c3806f668f
tree: b669f368b0062fcb100b24758cf05e2c4b500144
TASK-TRAFFIC-07-READ: DONE / READ FOUNDATION IMPLEMENTED
TASK-TRAFFIC-07: COMPLETE / PRODUCTION ACTIVE
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

The reviewed Windows/SQLite infinity behavior reproduced on the exact PR #98
baseline and is not a candidate regression.

Source/semantic acceptance:

```text
Current State only
CurrentGuestTrafficReadService = semantic owner
no query-time Omada
no Observation/Visit/Registry/AuthSession calculation source
no browser-side rate calculation
```

Owner-confirmed closure:
`IMPLEMENTED → TESTED → MERGED → PRODUCTION DEPLOYED → ACTIVATED → COMPLETE`.

## Test Set Maintenance Rule

For the current TRAFFIC-07 state, relevant coverage includes at minimum:

- `tests/analytics/test_current_guest_traffic.py`;
- `tests/admin_web/test_traffic_online_guests.py`;
- `tests/admin_web/test_traffic_online_guests_frontend.py`;
- current guest traffic capacity/PERF benchmark coverage;
- Current State read-service regressions;
- Admin config/routes/query/capability/pagination regressions;
- existing Traffic regressions proving isolation from historical products.

Permanent invariants:
- `CurrentGuestTrafficReadService` remains semantic owner;
- Current State remains the calculation source;
- numeric rates require valid counter/continuity evidence;
- missing/frozen/reset evidence must not fabricate numeric zero;
- cursor chains remain deterministic and bounded;
- Online Guests Traffic remains range-insensitive;
- query-time Omada isolation remains intact.

No next Traffic TASK is currently assigned. When one is approved, Tech Lead
reviews the targeted command/test set for that exact TASK.

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