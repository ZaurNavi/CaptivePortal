# QIO-01A — implementation R1 / focused handoff

Date: 2026-10-15. Execution mode: isolated Lab implementation and module-scoped tests only. **Not an accepted/released/performance-proven candidate.**

## Result / exact identity

Implemented invocation-local lock-owned health observation and positive-only 60-second ready heartbeat. Public activity return, constructor, stop, lock protocol and all domain processing remain unchanged.

```ini
BASE_HEAD=7e84bc563f1b6dd3d72da66ae25849d9a7d96540
BASE_TREE=ea664b1d49ace86fc8a0c4ab2fc52945531e574a
WORKTREE=/home/zaur_navi/captivportal-lab/worktrees/qio-01a
BRANCH=task/qio-01a-worker-health
HEAD=7e84bc563f1b6dd3d72da66ae25849d9a7d96540
WORKTREE_STATE=DIRTY_UNCOMMITTED
CANDIDATE_TREE=301e5fd934e92162a868315775a1646711ba8fab
PATCH_BYTES=23151
PATCH_SHA256=89f423c7175a13df06393e42ae7e4fd4a820cdbca41f975ae6453db843f5c04a
```

Baseline main HEAD/tree were freshly fetched and matched before creating this new clean worktree. The prior Deploy Config worktree was not reused or edited. No baseline drift detected at implementation start.

Full patch: `C:\CaptivPortal-Lab\handoffs\qio-01a-20261015\QIO-01A-R1.patch`.

Generated with an **external GIT_INDEX_FILE**, containing exactly the two allowed files, using `git diff --cached --binary --full-index --output=<patch> HEAD`. A second fresh external index reconstructed exact candidate tree from this patch and the pinned base. Reverse check PASS. No implementation/Lab commit was created and the real index remains unstaged. Tree objects are Lab transport identities, not publication commits.

## Exact file inventory

2 files, 439 insertions(+), 4 deletions(-):

| File | Change |
| --- | --- |
| `/home/zaur_navi/captivportal-lab/worktrees/qio-01a/app/device_fingerprint_integration/worker.py` | Only production file: private per-call ownership result and loop-local ready cadence. |
| `/home/zaur_navi/captivportal-lab/worktrees/qio-01a/tests/device_fingerprint_integration/test_worker_health.py` | New 40-case deterministic focused regression file. |

No existing test file modified. No config, docs, emitter, runtime, repository, executor, schema, service, authentication, Portal, CAPPORT, NI or capture change. Full per-file byte counts/SHA256 values and hashes of the three normative input documents are retained in `verification.json`.

## Private outcome design / public compatibility

`_run_cycle()` returns `(activity_bool, owned_completed_bool)` after the existing `consumer_lock` context finishes. Lock miss returns `(False, False)`; owned idle returns `(False, True)`; claimed and/or identity work returns `(True, True)` after the original bounded body. Exceptions still propagate. No shared `_last_outcome` attribute exists.

Public `run_once()` is a thin adapter returning only activity. Its return remains literal bool: False for owned idle and lock miss, True for classification and/or due identity work. Existing constructor parameters and stop() are unchanged. `run()` deliberately uses the private current-cycle observation, not a public `run_once()` boolean/stub. A public test double cannot invent ownership. Concurrent/direct invocations cannot overwrite another invocation's result.

`run()` stores only its own `last_ready_at` local value:

- unknown/start → first completed owned cycle: ready immediately;
- steady owned success: ready suppressed until `time.monotonic() - last_ready_at >= 60`;
- heartbeat is emitted once on the next eligible completed cycle, not a catch-up burst;
- lock miss: clear positive series and emit `consumer_lock_unavailable` every miss;
- unhandled Exception: clear positive series and emit `integration_unavailable` every failed cycle;
- recovery: immediate ready and a fresh 60-second anchor;
- backward clock readings cannot meet elapsed >=60 early; the prior emitted anchor is retained conservatively;
- no timer interrupts a long job; no shutdown/finally code fabricates ready/failure;
- existing `stop_event.wait(1)` remains unchanged.

A lock miss describes this consumer, not global failure of a pipeline being processed by another legal consumer. Handled durable retry/no-result and existing lease_lost warning do not automatically imply infrastructure failure.

## Architecture A1–A4 mapping

| Requirement | Implementation and focused evidence |
| --- | --- |
| A1: readiness only on current invocation's completed owned cycle | Private tuple; real lock-owned idle; legal lock holder; direct-success then loop-miss; public True/False stubs cannot grant ownership; synchronized direct lock miss during loop-owned completion. |
| A1: preserve public activity and domain paths | Existing 71 tests pass; new direct adapter/identity activity assertions; AST equivalence proof of entire original cycle after removing only the private return packaging/docstring. |
| A2: 60-second monotonic cadence | Fixed `READY_HEARTBEAT_MAX_INTERVAL_SECONDS=60`; fake clocks cover 0, 59.999, 60, 60.001, next interval, large forward and backward jumps, restart and long cycle completion. UTC changes do not schedule heartbeat. |
| A3: minimal telemetry envelope | Actual emitter test asserts exactly event/reason_code for loop health; no new timestamps/fields/counters. submitter.py is byte-identical to base; existing sanitization test remains green. Existing lease_lost retains integration_id. |
| A4: do not throttle failures/domain events | Repeated same/different exceptions and misses emit every iteration; immediate recovery. Real file-backed classification success/retry/no-result/lease-lost/finish-failure and identity resolved/conflict/unavailable/expiry tests preserve fields, count and order. |

Monitoring disposition is taken from the supplied A1–A4 document: PRTG is **Owner-asserted non-consumer / technically unverified**, limited-risk accepted. The scoped consumer inventory reported by Tech Lead is not a global proof. No live Grafana/PRTG/Loki inspection or configuration change was performed by Coder. No deployed stale alert is claimed. The suggested future age>180s alert is outside this implementation.

## Focused verification — actually executed

Environment: dedicated WSL Ubuntu-22.04; Python 3.10.12; pytest 9.1.1; SQLite 3.37.2. Qualified interpreter:
`/home/zaur_navi/captivportal-lab/test-gate-platform-01-r1-venv/bin/python`.

Interpreter SHA256: `a2f33a6e006989270f4340528eb61f8f97366e00a5d1b602ac8672ea44fc56ae`.

From `/home/zaur_navi/captivportal-lab/worktrees/qio-01a`:

```bash
export PYTHONPATH="$PWD"
export PYTHONPYCACHEPREFIX=/home/zaur_navi/captivportal-lab/tmp/qio-01a-pycache
/home/zaur_navi/captivportal-lab/test-gate-platform-01-r1-venv/bin/python -m pytest -q -p no:cacheprovider tests/device_fingerprint_integration --junitxml=/mnt/c/CaptivPortal-Lab/handoffs/qio-01a-20261015/integration-focused.xml
```

**111 PASS / 0 FAIL / 0 ERROR / 0 SKIP, 22.98s**: 71 unchanged existing module cases + 40 new cases. This is only the task's Integration module suite, not a full/cross-module gate. Full stdout is `integration-focused.log`; per-case JUnit in `integration-focused.xml`. New exact test names are listed in `verification.json`.

Initial development run of the new file: **38 PASS / 2 FAIL**. Both new synthetic success fixtures had used an invalid placeholder ClassificationResult artifact reference, rejected by existing IntegrationJob validation. Only those disposable fixture references were corrected to canonical `ClassificationResult:v1:sha256:<64 hex>` form. No production validation/assertion was weakened. Initial logs/JUnit are retained as `worker-health-initial.log/xml`; the final complete module run above is on the exact handed-off source.

The concurrent direct-call case uses Events and bounded join/wait **only for deterministic synchronization**, not sleeps or wall-clock heartbeat timing. Both invocations use the actual consumer lock. Independent process/service lifecycle admission remains pending; the unit thread case is not represented as that gate.

Additional focused/static command:

```bash
/home/zaur_navi/captivportal-lab/test-gate-platform-01-r1-venv/bin/python -m compileall -q app/device_fingerprint_integration/worker.py tests/device_fingerprint_integration/test_worker_health.py
git diff --check
```

With the same external bytecode prefix: compileall PASS, exit 0 (`compileall.log` empty). `git diff --check` PASS. External-index `git diff --cached --check` also PASS, including the new test file omitted by ordinary unstaged diff.

## Invariant and durable-state proof

- External `verify_handoff.py` parsed baseline/current code and proved the original public run_once body is AST-identical to new `_run_cycle()` after removing only its explanatory docstring and tuple packaging of the two returns. Thus all lock acquisition, claim/finish/identity calls, retry conditions, event payload expressions, exception handling and transaction boundaries inside the cycle are unchanged.
- `consumer_lock`, `__init__` and `stop` ASTs are identical to baseline. Public argument lists unchanged.
- Protected integration runtime, submitter, repository, executor, models, resolver, compatibility, config and read_service files are byte-identical to base. No other tracked source/test/docs path changed; only the allowed new test is untracked.
- File-backed tests exercise real IntegrationRepository leases, fixed due/retry schedule, identity 30-second retry / one-hour expiry and CAS lease-loss behavior; existing normal executor/persistence tests remain green.
- The idle-DB test compares database bytes and full schema before/after 121 owned cycles: identical DB, zero jobs, schema v1, no extra durable health data. Only the existing consumer lock file appears; no new store/table/logger is introduced. **Original idle claim/DB activity is preserved**, not optimized by this task.
- New tests contain no skip/skipif/xfail/sleep. Real emitter tests show no exception text or new optional JSON fields. No credentials/private keys or production data were used.
- Patch reconstruction and reverse check PASS; exact two-path tree scope verified. Verification output retained in `verification.log` and `verification.json`.

## Mandatory gate matrix / ownership

All following rows refer to candidate TREE `301e5fd934e92162a868315775a1646711ba8fab` unless a later independently reviewed candidate replaces it.

| Gate | Operator / environment | Current result |
| --- | --- | --- |
| Scoped source/diff and architectural invariant review | Tech Lead | PENDING; Coder static proof supplied, not a Tech Lead verdict |
| Coder focused unit/module tests | Coder / isolated WSL Lab | PASS, 111/111, exact patch evidence above |
| Independent Linux concurrency and service lifecycle | Owner/Tech Lead / clean dedicated WSL Lab materialization | PENDING |
| Windows official strict V7 with runner checksum verification | Owner physical operator, Owner+Tech Lead verdict | PENDING / NOT RUN BY CODER |
| Matched Linux/PERF log-rate, journald I/O and service outcomes | Owner/Tech Lead / isolated production-compatible Lab | PENDING / NOT RUN |
| Physical host HDD /dev/sda write IOPS/await/busy | Owner/Tech Lead / separately approved suitable isolated HDD environment | PENDING / NOT PROVEN; WSL event-count evidence cannot substitute |
| Normal publication/PR | Separate Owner authorization after required gates | NOT AUTHORIZED |
| Production deployment and activation | Separate Owner GO, verified Git source, health/rollback | NOT AUTHORIZED / NOT EXECUTED |

Candidate accepted: **NO**. All mandatory gates PASS: **NO** (pending independent acceptance, not a focused implementation blocker). No full/Central suite, profiling, production measurement, production access or service action was performed. Do not transfer the previous Deploy Config exception or its results to QIO-01A.

## Risks / limits / rollback

This reduces repeated positive health **event count**, not a measured amount of journald, guest block or physical HDD I/O. It does not remove original DB polling, locks or transactions. No HDD performance PASS or percentage improvement is claimed. Physical monitoring has layered accounting and unrelated writers; Owner/Tech Lead must supply matched evidence and any necessary sequencing disposition before publication.

No heartbeat wall-clock SLA is invented: a long cycle, stop, overload or failure can yield a gap greater than 60 seconds. Backward readings conservatively delay a heartbeat rather than emit early. Repeated failures/misses are deliberately unthrottled. Discovery of an external 1/s event consumer restores the monitoring gate HOLD per A2.

Rollback after a separately authorized release is a narrow independently accepted Git revision restoring prior worker health logic; no schema/data rollback or journal truncation is required. This handoff does not perform any rollback, reset, service restart or activation.

## Actions / next owner step

Agent execution summary: Coder in implementation mode; inspected the three QIO documents, pinned governance and directly related worker/repository/emitter/tests; created a clean isolated local branch/worktree; changed only worker.py and one new test; ran focused module tests and syntax/static checks; generated external patch/tree/evidence. No subagents, dependencies, schema or operational changes. No commit/push/PR/merge/deploy. Hand off to Tech Lead for scoped source review and independent acceptance gates; preserve this dirty draft.

```ini
COMMIT=NO
PUSH=NO
PR=NO
MERGE=NO
DEPLOY=NO
SERVICE_RESTART=NO
PRODUCTION_ACTION=NO
PUBLICATION_STATUS=NOT_AUTHORIZED
PRODUCTION=UNTOUCHED
CODER_HOLD=YES
NEXT_ACTION=TECHLEAD_SOURCE_REVIEW_AND_INDEPENDENT_GATES
```
