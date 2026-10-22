# TASK-DEVICE-FINGERPRINT-05 — implementation candidate handoff

This is Coder implementation evidence, not TechLead/Owner acceptance or production activation.

## Exact identity

```text
BASELINE_HEAD=fecdb5a7c79e56bb49be4797ca875d6720670042
BASELINE_TREE=85d7d41e1ad19c079cad0ae819a3fe38a068e242
BRANCH=feature/device-fingerprint-05-identity-session-integration
CANDIDATE_COMMIT=e23250b37419e11f8be2ddb170d1ea8e037628a3
CANDIDATE_PARENT=fecdb5a7c79e56bb49be4797ca875d6720670042
CANDIDATE_TREE=1101ee765ca6fdb53582639d581b029a1e229605
WORKSPACE=C:\CaptivPortal-Lab\coder-task05-identity-session
INTEGRATION_SCHEMA_VERSION=1
CHANGED_FILES=26
NEW_FILES=18
ADDITIONS=1743
DELETIONS=1
```

## Changes / exact name-status

```text
M .env.example
M app/auth/worker.py
M app/config.py
M app/device_fingerprint/classification_persistence.py
M app/device_fingerprint/classification_read.py
A app/device_fingerprint_integration/__init__.py
A app/device_fingerprint_integration/cli.py
A app/device_fingerprint_integration/compatibility.py
A app/device_fingerprint_integration/config.py
A app/device_fingerprint_integration/executor.py
A app/device_fingerprint_integration/identity_resolver.py
A app/device_fingerprint_integration/models.py
A app/device_fingerprint_integration/read_service.py
A app/device_fingerprint_integration/repository.py
A app/device_fingerprint_integration/runtime.py
A app/device_fingerprint_integration/submitter.py
A app/device_fingerprint_integration/worker.py
M app/settings.py
M app/web/web.py
A deploy/device-fingerprint/INTEGRATION.md
A deploy/device-fingerprint/fingerprint-classification.service
M run.py
A tests/device_fingerprint_integration/__init__.py
A tests/device_fingerprint_integration/test_auth_hook.py
A tests/device_fingerprint_integration/test_executor_persistence.py
A tests/device_fingerprint_integration/test_repository_identity.py
```

The integration package separates relation contracts/config, short SQLite operations,
Auth submitter, exact Registry/Visit reads, admitted-profile/source preflight, normal
Task-04 execution, worker/leases, typed result reads and auxiliary composition/CLI.
The eight existing files change only configuration/composition, the post-Auth hook,
explicit optional classification ID and exact retained-result read by ID.
The deployment unit/documentation are supplied but NOT installed or activated.
No existing test file was changed; the three new test modules and package marker
are listed above. No public API, UI, classifier, Registry/Visit/Task-01 schema changes.

Exact `git diff --stat BASELINE_HEAD CANDIDATE_COMMIT`:

```text
 .env.example                                       |   5 +
 app/auth/worker.py                                 |  26 ++
 app/config.py                                      |  10 +
 .../classification_persistence.py                  |   6 +-
 app/device_fingerprint/classification_read.py      |  11 +
 app/device_fingerprint_integration/__init__.py     |   7 +
 app/device_fingerprint_integration/cli.py          |  22 ++
 .../compatibility.py                               | 156 +++++++++++
 app/device_fingerprint_integration/config.py       |  43 +++
 app/device_fingerprint_integration/executor.py     |  67 +++++
 .../identity_resolver.py                           |  58 ++++
 app/device_fingerprint_integration/models.py       | 164 +++++++++++
 app/device_fingerprint_integration/read_service.py |  31 ++
 app/device_fingerprint_integration/repository.py   | 179 ++++++++++++
 app/device_fingerprint_integration/runtime.py      |  62 ++++
 app/device_fingerprint_integration/submitter.py    |  46 +++
 app/device_fingerprint_integration/worker.py       | 111 ++++++++
 app/settings.py                                    |   8 +
 app/web/web.py                                     |   2 +
 deploy/device-fingerprint/INTEGRATION.md           |  33 +++
 .../fingerprint-classification.service             |  22 ++
 run.py                                             |   3 +
 tests/device_fingerprint_integration/__init__.py   |   1 +
 .../test_auth_hook.py                              |  54 ++++
 .../test_executor_persistence.py                   | 298 ++++++++++++++++++++
 .../test_repository_identity.py                    | 319 +++++++++++++++++++++
 26 files changed, 1743 insertions(+), 1 deletion(-)
```

## Integration database / execution boundary

Own SQLite schema v1: `integration_jobs`, unique `(auth_session_id, auth_run_number)`
and unique planned UUIDv4, fixed Auth/due/window identifiers, classification state,
attempts/retry/lease state, exact identity anchors and timestamps. No raw/result
payload, classification dimensions, explanation/knowledge bodies are copied.
FULL synchronous; foreign keys enabled; default 100ms bounded contention timeout.
Only the dedicated integration DB is initialized; other domain DBs are not migrated.

The successful AuthRun hook follows existing Registry and Visit submissions, is
default-disabled, and catches submission failures after Authorization is successful.
Portal composition never starts the classifier. The auxiliary worker atomically
claims durable jobs, holds a kernel consumer lock, uses token/expiry CAS, supports
expired lease recovery and makes at most five assembly attempts. Retry delays are
30/120/300/600 seconds. The fixed window is Auth-300s to Auth+120s, due Auth+150s;
Foundation valid-from clamps only its start. Identity retries are independent and
bounded to Auth+1h, using only exact session/Site/MAC Registry snapshots and exact
Visit start session/run tuples, not a bare MAC or nearest-timestamp inference.

Dynamic admitted profile preflight checks canonical profile/validity/admission,
exact dependencies, source-backed implementation file SHA256 and loaded origin.
The normal `assemble_production` path and normal atomic `persist` remain authoritative;
an exact preflight pin rejects intervening activation generation drift/ABA. Linux
current RSS is measured using `/proc/self/statm` and `SC_PAGE_SIZE`, unavailable
measurement fails closed. A persisted planned classification ID is recovered before
assembly; Site/MAC/window conflict fails closed without overwriting the result.

## Verification commands / results

Environment: Windows, Python 3.10.11,
`C:\CaptivPortal-UI-Preview\.venv\Scripts\python.exe`.
`PYTHONPYCACHEPREFIX=C:\CaptivPortal-Lab\tmp\task05-pyc`.
Each pytest run uses a distinct external `--basetemp`; no evidence/temp DB goes into Git.
The current TASK §36 explicitly requests the direct compatibility and full repository
pytest runs below. They are local Coder checks, not an official Central Lab gate.

Focused command:

```text
python -m pytest -q --basetemp=C:\CaptivPortal-Lab\tmp\task05-focused-20261003-04 tests/device_fingerprint_integration
```

Result: **60 passed / 0 skipped / 0 failed**, 40.08 seconds.

Direct compatibility command on clean immutable candidate:

```text
python -m pytest -q -rs --basetemp=C:\CaptivPortal-Lab\tmp\task05-compat-20261003-03 --junitxml=C:\CaptivPortal-Lab\artifacts\TASK-DEVICE-FINGERPRINT-05-compat-pytest.xml tests/device_fingerprint_task04_04d_persistence tests/device_fingerprint_task04_04e_read tests/visitor_registry tests/visit_lifecycle tests/test_auth_retry.py
```

DIRECT_COMPATIBILITY_RESULT=625 passed / 21 skipped / 0 failed (208.77 seconds)

All 21 skips are existing POSIX-specific directory/file modes, symlinks, FIFOs,
Unix socket/device and Visit repository mode/symlink checks under Windows.

Full repository command:

```text
python -m pytest -q -rs --basetemp=C:\CaptivPortal-Lab\tmp\task05-full-20261003-02 --junitxml=C:\CaptivPortal-Lab\artifacts\TASK-DEVICE-FINGERPRINT-05-full-final-pytest.xml
```

FULL_TEST_RESULT=FAIL — 5166 passed / 30 skipped / 5 failed / 0 errors / 0 deselected (1061.92 seconds)

Full JUnit evidence (outside Git):
`C:\CaptivPortal-Lab\artifacts\TASK-DEVICE-FINGERPRINT-05-full-final-pytest.xml`.
Direct compatibility JUnit evidence:
`C:\CaptivPortal-Lab\artifacts\TASK-DEVICE-FINGERPRINT-05-compat-pytest.xml`.
Thirty full-suite skips: 29 existing Windows/POSIX mode, symlink, FIFO, Unix socket,
device checks; one opt-in Analytics HTTP performance benchmark. No skip/deselection
was added to make the new tests pass.

### Full-regression blocker — untouched Traffic Projection fixture

All five failures are in `tests/traffic_projection/test_projected_read.py`:

```text
test_projection_reuses_existing_historical_semantic_owner
test_projected_all_products_match_canonical_raw_semantics
test_projected_all_products_reuse_one_range_and_one_ap_evidence_read
test_projection_read_uses_one_outer_transaction_and_pins_revision
test_all_historical_semantic_statements_run_inside_outer_snapshot
```

Underlying failure: `TrafficProjectionStorageUnavailable("Projection Site is not healthy")`,
wrapped as `AnalyticsSourceUnavailable` / `HistoricalTrafficSourceUnavailable`.
The fixture evaluates module-level `NOW = datetime.now(...)` at test collection and
persists it as reconciliation/progress freshness timestamps. The reader correctly
uses its actual wall clock, and `HEALTHY_FULL_RECONCILE_MAX_AGE_SECONDS=600` remains
frozen. A long complete run lets this synthetic timestamp expire before those tests.
The completed full run took 1061.92 seconds; changing production freshness semantics
or hiding these failures is not authorized.

Read-only/source-unchanged differential evidence:

- No baseline-to-candidate diff in that test file or
  `app/traffic_projection/{read_service,health,models}.py`.
- Existing clean FIX1 worktree at commit
  `b53fedb0a56f7be45b31e0ee9d4f1d034a684ef1` has tree
  `85d7d41e1ad19c079cad0ae819a3fe38a068e242`, EXACTLY the TASK-05 baseline tree.
  This is a baseline-equivalent source tree, not a claim that its commit SHA equals
  the baseline merge SHA.
- On that unmodified baseline-equivalent tree, an isolated disposable fixture read
  succeeds at fixture age 0 seconds and returns unavailable at age 601 seconds.
  This diagnostic uses the existing injected clock boundary; it changes no source,
  real clock or production state and is not a substitute for the failed full run.
- The existing file alone on that baseline-equivalent tree passes **10 / 0 / 0**,
  3.75 seconds:

```text
python -m pytest -q --basetemp=C:\CaptivPortal-Lab\tmp\task05-baseline-projection-20261003-01 --junitxml=C:\CaptivPortal-Lab\artifacts\TASK-DEVICE-FINGERPRINT-05-baseline-projection-pytest.xml tests/traffic_projection/test_projected_read.py
```

Both worktrees remain clean. Analytics/Traffic Projection code/tests are NOT repaired
in this Task-05 candidate. Required next decision: TechLead/Owner disposition of this
duration-sensitive baseline fixture and, if approved, a separately bounded baseline
test repair/revalidation. TASK-05 master full-regression PASS is **HOLD**, not PASS.

```text
python -m compileall -q app
git diff --check fecdb5a7c79e56bb49be4797ca875d6720670042 HEAD
git apply --reverse --check C:/CaptivPortal-Lab/artifacts/TASK-DEVICE-FINGERPRINT-05_BASE-to-CANDIDATE.patch
```

COMPILEALL_RESULT=PASS
DIFF_CHECK_RESULT=PASS
PATCH_REVERSE_APPLY_CHECK=PASS (check only; no file alteration)
GIT_STATUS_SHORT=<empty>
WORKTREE=CLEAN

Initial implementation self-check exposed a Python 3.10 SQLite error-code portability
defect in the new integration module, fixed within scope before the final focused run.
An initial direct compatibility run on the uncommitted worktree reported 617 passed /
21 skipped / 8 failed: the eight startup cases correctly refused dirty Git identity
in existing `capture_loaded_artifact_identity`. No startup protection or existing
tests were weakened. The suite is repeated on the clean local candidate above.

Final self-review corrected the new telemetry logger's name to inherit the existing
configured `captivportal` application logger, and added one configuration inheritance
regression. The earlier local commit was amended (not published); baseline parent
remains exact. One incomplete full run was stopped to bind final verification to the
corrected candidate; it is NOT counted as a full test result. Both compatibility and
full runs above use the final immutable candidate.

## Bounded proof inventory (local synthetic fixtures, not live production)

```text
Task04 persist backward compatibility=PASS
Task04 get_current/list_history backward compatibility=PASS
get_by_id retained result integrity=PASS
Auth fail-open / existing submission ordering=PASS
Job idempotency / distinct subsequent AuthRun=PASS
Fixed timing / not-before-due / Foundation start clamp=PASS
Normal production assembly + persist / planned UUIDv4=PASS
Automatic auxiliary worker classification=PASS
Persist COMMIT / lost job update / no duplicate recovery=PASS
Planned ID Site/MAC conflict rejected=PASS
Lease no-steal / expired reclaim / token CAS / bounded retries=PASS
Exact Registry Site/session/MAC proof=PASS
Exact Visit session/run proof / mismatch rejection=PASS
Immutable identity conflict anchors preserved=PASS
Site isolation / randomized MAC no merge inference=PASS
Classified + unresolved identity allowed=PASS
Task05 typed read returns authoritative Task04 read object=PASS
No other domain database initialization/mutation in composition=PASS
No hardcoded active CRP/RPM / source digest mismatch blocks=PASS
Activation generation drift/ABA rejects torn assembly=PASS
Real RSS measurement mechanism / unavailable fails closed=PASS
Safe structured telemetry / lost lease not reported as terminal success=PASS
Worker telemetry inherits configured application logger=PASS
```

## Complete review patch

```text
PATCH_PATH=C:\CaptivPortal-Lab\artifacts\TASK-DEVICE-FINGERPRINT-05_BASE-to-CANDIDATE.patch
PATCH_BYTES=107133
PATCH_SHA256=a0161ad98b956bbeb7a1f055ded0c4229d48aabb2f84744f04a5ceba9004126e
PATCH_FORMAT=git diff --binary --full-index BASELINE_HEAD CANDIDATE_COMMIT
```

## Scope / governance

```text
AUTH_OUTCOME_CHANGED=NO
CAPPORT_OMADA_SEMANTICS_CHANGED=NO
REGISTRY_VISIT_SCHEMA_OR_IDENTITY_SEMANTICS_CHANGED=NO
TASK01_SCHEMA_CHANGED=NO
TASK04_CLASSIFIER_OR_ACTIVE_PROFILE_SEMANTICS_CHANGED=NO
UI_PUBLIC_ADMIN_API_ADDED=NO
REPOSITORY_DEFAULT_INTEGRATION_ENABLED=FALSE
CENTRAL_LAB_RUN=NO
LINUX_PRODUCTION_GATE_RUN=NO
TECHLEAD_ACCEPTANCE=PENDING
TASK05_MASTER_PASS_CRITERIA=HOLD_FULL_REGRESSION
KNOWN_BLOCKERS=Duration-sensitive untouched Traffic Projection baseline fixture (five full-suite failures)
PRODUCTION_ACCESS=NO
PRODUCTION_CONFIGURATION_CHANGED=NO
SERVICE_ACTIVATED=NO
PUSH=NO
PR=NO
MERGE=NO
DEPLOY=NO
```

Local branch and one local implementation commit only. Original UI-Preview and earlier
task worktrees were not modified. This candidate requires independent TechLead/Owner
review/gates; publication/deployment/service activation require separate authorization.

Agent execution: Codex / Windows / implementation. No delegated agents, no external
source downloads, no production actions, no official acceptance artifacts created.
