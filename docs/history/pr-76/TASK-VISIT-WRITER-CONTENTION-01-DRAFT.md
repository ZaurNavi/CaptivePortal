# TASK-VISIT-WRITER-CONTENTION-01 — Visit Lifecycle Writer Contention / Background Fairness — DRAFT

**Project:** CaptivPortal  
**Type:** Corrective / Production concurrency defect  
**Priority:** High  
**Status:** DRAFT — architecture review required before coder authorization  
**Prepared:** 2026-08-27  
**Repository baseline verified:** `origin/main@e34b6d047fec36eca48ebacf3281b95ee5d03474`  
**Affected subsystem:** Visit Lifecycle local SQLite write scheduling  
**Schema:** v2 — MUST remain v2  
**Auth / Omada contract:** MUST remain unchanged  
**Production activation:** Owner-controlled; not authorized by this DRAFT

---

# 1. Goal

Eliminate recurring Visit Lifecycle writer-contention failure modes while preserving the existing product contracts:

```text
foreground Visit Start has priority
guest authorization remains fail-open relative to Visit storage
Visit authorizations remain idempotent
reader evidence/checkpoint remains durable
reconciliation remains background work
SQLite remains the single local Visit store
schema remains v2
```

Production evidence reports recurring:

```text
visit.reader_scan_failed
storage_category=busy
```

and historical:

```text
visit.storage_error
operation=start
retry_exhausted=true
budget_ms=2000
```

with the Start total budget exhausted.

Investigation has confirmed that current reader `busy` events occur at the in-process:

```text
PriorityWriteCoordinator
```

rather than from SQLite corruption.

The corrective task MUST remove false/avoidable contention failures and prevent background writer starvation without solving the problem by merely increasing timeouts.

---

# 2. Confirmed current repository state

At:

```text
origin/main@e34b6d047fec36eca48ebacf3281b95ee5d03474
```

Visit Lifecycle uses a single process-local:

```text
PriorityWriteCoordinator
```

with:

```text
one active writer
foreground queue = Visit Start
background queue = reader/reconciliation/startup
```

Current scheduling rule is effectively:

```text
if any foreground waiter exists:
    background waiter cannot acquire
```

until the foreground queue becomes empty.

Current defaults include:

```text
VISIT_LIFECYCLE_START_WRITER_SLOT_WAIT_MS=750
VISIT_LIFECYCLE_READER_WRITER_SLOT_WAIT_MS=250
VISIT_LIFECYCLE_RECONCILIATION_WRITER_SLOT_WAIT_MS=250
VISIT_LIFECYCLE_SQLITE_BUSY_TIMEOUT_MS=500
VISIT_LIFECYCLE_START_MAX_ATTEMPTS=3
VISIT_LIFECYCLE_START_TOTAL_BUDGET_MS=2000
VISIT_LIFECYCLE_PENDING_OFFLINE_BATCH_SIZE=500
VISIT_LIFECYCLE_SCAN_INTERVAL_SECONDS=5
```

Current `LocalVisitStartSubmitter` retries `BUSY` under a hard total Start budget and remains fail-open by returning:

```text
VisitStartOutcome(status="unavailable")
```

if storage cannot be recorded safely.

---

# 3. Confirmed contention mechanisms

This TASK addresses two different mechanisms.

## 3.1 Long background lease / transaction

Current:

```text
VisitRepository.process_pending_events()
```

does:

```text
acquire one WRITE_OPERATION_READER lease
open one connection
BEGIN IMMEDIATE
SELECT pending rows LIMIT pending_offline_batch_size
process every selected row
COMMIT
release writer lease
```

Therefore a configured batch of up to:

```text
500 pending events
```

may be processed under one writer lease / one SQLite write transaction.

This violates the desired "short serialized write transactions" property in practice.

A foreground Start arriving after that transaction has begun cannot preempt it and may wait for the entire batch.

## 3.2 Background starvation / false reader failure

The coordinator gives strict foreground priority.

A reader waiter has a current writer-slot wait budget of:

```text
250 ms
```

If foreground Starts keep arriving, the background waiter can time out as `BUSY`.

Current `VisitLifecycleWebhookReader.scan_once()` catches that as a generic exception and emits:

```text
visit.reader_scan_failed
level=error
storage_category=busy
```

then immediately reports reader health:

```text
False
```

to `VisitLifecycleRuntime`.

The runtime then becomes:

```text
degraded
```

even when the actual condition was temporary intentional foreground priority and no reader evidence/checkpoint was lost.

This produces false scan failures while also leaving a real starvation risk if foreground load is sustained.

---

# 4. Root-cause statement

The root cause is NOT:

```text
SQLite corruption
insufficient SQLite busy_timeout by itself
insufficient Start retry budget by itself
```

The root cause is the current scheduling/transaction contract:

```text
A. background work can hold a writer lease for too much work
+
B. foreground priority is absolute with no starvation escape
+
C. expected foreground-driven background deferral is represented
   as a generic storage failure
+
D. contention telemetry cannot identify the active holder precisely
```

Increasing:

```text
writer-slot timeout
SQLite busy timeout
Start total budget
```

without changing those properties is NOT an acceptable root-cause fix.

---

# 5. Required architectural properties

The final implementation MUST satisfy all of these simultaneously.

## 5.1 Foreground priority

Visit Start remains foreground.

Under ordinary contention:

```text
waiting Start
>
new background acquisition
```

A background worker MUST NOT continuously reacquire ahead of an already waiting Start.

## 5.2 No indefinite background starvation

Foreground priority MUST NOT mean:

```text
background may wait forever while Starts continue arriving
```

The scheduler needs a bounded starvation escape for background work.

## 5.3 Bounded background ownership

No routine background function may hold:

```text
one writer lease
+
one BEGIN IMMEDIATE transaction
```

across an unbounded or large configured batch.

## 5.4 Yield only at safe transaction boundaries

There is NO mid-transaction forced preemption in this TASK.

"Preemption" / "yield" means:

```text
finish current bounded atomic chunk
COMMIT or ROLLBACK
release writer lease
allow scheduler to choose next waiter
```

Never interrupt a transaction after partial durable mutation merely to let Start pass.

## 5.5 Fail-open Auth contract

Visit persistence remains auxiliary to successful guest authorization.

No Visit storage error may convert a successfully verified Omada authorization into an authorization failure.

## 5.6 Durable reader contract

Background deferral MUST NOT cause:

```text
lost source evidence
skipped journal bytes
checkpoint advance without evidence persistence
duplicate durable event insertion
```

## 5.7 Real degradation remains visible

Expected short foreground-driven deferral is not a storage failure.

However repeated/prolonged deferral that prevents durable reader progress MUST eventually be reported as degradation.

---

# 6. Scheduler model — proposed DRAFT design

Retain one process-local writer coordinator.

Do NOT add a second Visit writer pool.

The coordinator becomes:

```text
foreground-priority
+
FIFO within each class
+
bounded background starvation escape
+
holder introspection
```

Conceptually:

```text
PriorityWriteCoordinator

active holder:
    operation
    priority class
    acquired_at

foreground FIFO
background FIFO
```

Priority classes:

```text
FOREGROUND:
    start

BACKGROUND:
    reader
    pending_retry
    reconciliation

STARTUP:
    startup
```

Startup is not part of normal steady-state contention.

---

# 7. Background starvation escape

## 7.1 Normal scheduling

If no background waiter has reached starvation age:

```text
foreground head wins whenever foreground queue is non-empty
```

This preserves existing Start priority.

## 7.2 Aged background waiter

The oldest background FIFO head becomes eligible after a bounded wait.

Proposed DRAFT constant:

```text
BACKGROUND_STARVATION_AGE_MS = 200
```

Rationale:

- below current background 250 ms writer-slot timeout;
- allows a background waiter to become eligible before it is converted into BUSY;
- still gives Start the normal priority window;
- an admitted background transaction is separately bounded to a short chunk.

This is a DRAFT value subject to Tech Lead review.

## 7.3 One escape, then foreground resumes

When a background waiter wins by aging:

```text
grant exactly one bounded background lease/chunk
```

After it releases:

```text
foreground priority is reevaluated from scratch
```

Do NOT grant a burst of aged background chunks while foreground waiters remain queued.

This creates:

```text
foreground priority
without
background starvation
```

---

# 8. Background chunk contract

Proposed shared steady-state background limits:

```text
BACKGROUND_CHUNK_MAX_ITEMS = 25
BACKGROUND_CHUNK_TARGET_MAX_HOLD_MS = 50
```

These are DRAFT constants, not new production knobs in the first implementation unless Tech Lead explicitly requests configuration.

## 8.1 Meaning of item bound

A background transaction MUST process no more than:

```text
25 logical write items
```

before commit/release.

## 8.2 Meaning of time bound

Before beginning each next item inside a chunk:

```text
if elapsed lease/transaction time >= 50 ms:
    stop adding work to the chunk
    COMMIT
    release
```

The implementation cannot safely abort a single row mutation mid-statement.

Therefore:

```text
50 ms is a target boundary checked between atomic items,
not a hard kill timer inside SQLite.
```

One unusually slow item may exceed it and MUST be observable via holder age telemetry.

## 8.3 No lease chaining

A background caller that has more work MUST:

```text
release
return to coordinator queue
reacquire
```

It MUST NOT keep the lease and simply start another transaction.

---

# 9. `process_pending_events` — mandatory redesign

The current one-lease batch is explicitly prohibited.

Current unacceptable shape:

```text
lease
BEGIN IMMEDIATE
SELECT up to 500 pending
for all rows:
    process
COMMIT
release
```

New required shape:

```text
total_remaining =
    VISIT_LIFECYCLE_PENDING_OFFLINE_BATCH_SIZE

while total_remaining > 0:
    acquire background lease as pending_retry
    BEGIN IMMEDIATE

    select/process:
        <= BACKGROUND_CHUNK_MAX_ITEMS
        and stop adding rows when target chunk time reached

    COMMIT
    release lease

    emit outcomes for committed chunk

    if no rows:
        stop

    total_remaining -= committed item count

    if caller scan budget / shutdown says stop:
        stop

    reacquire for next chunk
```

The configured:

```text
VISIT_LIFECYCLE_PENDING_OFFLINE_BATCH_SIZE
```

remains a per-pass total work ceiling.

It is NOT a transaction size.

---

# 10. Pending retry ordering

Preserve deterministic pending ordering:

```text
pending_until ASC
event_id ASC
```

Each new chunk re-selects the next still-pending rows using the same ordering.

Committed rows are no longer `pending_match` where applicable and therefore naturally leave the next query.

No in-memory cursor is authoritative across transactions.

Durable DB state remains the source of truth.

---

# 11. Reader journal-line transaction contract

The normal live reader path already has an important safety property:

```text
one journal line
+
source event mutation
+
reader checkpoint upsert
```

are committed in the same repository transaction.

This TASK MUST preserve that atomicity.

Do NOT split:

```text
event persistence
```

from:

```text
checkpoint persistence
```

for the same consumed line.

---

# 12. Reader deferral before acquisition

If foreground priority prevents the reader from acquiring the writer lease before the expected background wait boundary:

```text
no transaction has started
```

The in-memory file stream may already have read the line, but its durable checkpoint MUST still point before that uncommitted line.

The scan may return/incomplete.

On the next scan:

```text
reader opens durable state
seeks to last committed offset
re-reads the same line
```

Event ID idempotency remains the second protection.

Required invariant:

```text
defer before commit
→ no checkpoint advance
→ no evidence loss
```

---

# 13. No rollback-as-preemption

If a background writer already owns a lease and has started:

```text
BEGIN IMMEDIATE
```

a newly arriving foreground Start does NOT forcibly cancel that transaction.

The current background atomic item/chunk must:

```text
commit or rollback normally
release
```

Then foreground wins the next normal scheduler decision.

Reason:

- avoids partially applied source-event/checkpoint state;
- avoids ambiguous commit recovery;
- avoids extra SQLite rollback churn;
- preserves simple idempotency reasoning.

The fix is to make each background chunk small enough that Start never waits on a large batch.

---

# 14. Reconciliation contract

Current reconciliation already writes one candidate at a time through:

```text
record_reconciliation_attempt()
```

with a separate writer acquisition/transaction for each candidate.

Preserve that basic shape.

Do NOT convert reconciliation into one batch transaction.

Reconciliation participates in background FIFO and starvation escape like reader work.

If a Start is waiting after one reconciliation write commits:

```text
Start must be eligible before reconciliation reacquires normally.
```

---

# 15. Coordinator holder telemetry

The coordinator currently exposes queue counts only for tests.

This TASK MUST make contention diagnosis first-class.

Track an immutable snapshot containing at least:

```text
holder_operation
holder_age_ms
foreground_queue_depth
background_queue_depth
waiter_operation
waiter_wait_ms
```

Equivalent names are acceptable if semantics are identical.

## Holder operation granularity

At minimum distinguish:

```text
start
reader_line
reader_checkpoint
pending_retry
reconciliation
startup
```

If implementation retains existing scheduling operation constants, it may add a separate:

```text
operation_detail
```

for telemetry.

No schema change is required.

---

# 16. Contention error/deferral context

When a waiter cannot acquire, the resulting internal contention object / `VisitStorageError` metadata MUST carry a snapshot taken at the decision point.

Required fields:

```text
storage_category=busy
operation=<waiter operation>
lock_wait_ms

holder_operation
holder_age_ms
foreground_queue_depth
background_queue_depth
```

If no holder exists because the background waiter is blocked only by queued foreground priority:

```text
holder_operation = null
```

and the queue depths still explain the block.

Optional explicit field:

```text
contention_reason=active_holder|foreground_priority|sqlite_busy
```

is recommended.

---

# 17. Distinguish coordinator BUSY from SQLite BUSY

Telemetry must allow operators to tell whether a `busy` originated from:

```text
PriorityWriteCoordinator
```

or:

```text
SQLite BEGIN/statement lock result
```

Recommended safe field:

```text
contention_layer=coordinator|sqlite
```

This is important because the current production incident has been proven to be coordinator contention.

Do not collapse both into an indistinguishable `storage_category=busy`.

---

# 18. Expected reader deferral semantics

A short reader delay caused by foreground scheduling is not equivalent to a failed scan.

Introduce or equivalent:

```text
visit.reader_scan_deferred
```

Recommended level:

```text
info
```

or low-volume `warning` only when needed.

Required fields:

```text
operation=reader
contention_layer=coordinator
holder_operation
holder_age_ms
foreground_queue_depth
background_queue_depth
wait_ms
processed_line_count
```

A foreground-driven expected deferral MUST NOT immediately emit:

```text
visit.reader_scan_failed level=error
```

and MUST NOT immediately call:

```text
health_callback(False)
```

provided no actual storage/read integrity error occurred.

---

# 19. What qualifies as expected foreground deferral

Expected deferral is narrowly defined.

All must be true:

```text
VisitStorageCategory.BUSY
contention_layer=coordinator
```

and the blocking reason is demonstrably foreground:

```text
holder_operation=start
OR
foreground_queue_depth > 0 with no background holder
```

If actual holder is:

```text
pending_retry
reader_line
reader_checkpoint
reconciliation
startup
```

then a reader timeout is NOT reclassified as benign foreground deferral.

That indicates background hold contention and remains degradation evidence.

---

# 20. Reader degradation after prolonged deferral

Do not hide starvation behind endless `reader_scan_deferred`.

The reader/runtime must track durable progress in-process.

Proposed DRAFT threshold:

```text
READER_DEFERRAL_DEGRADED_AFTER_SECONDS = 30
```

This is a DRAFT value subject to Tech Lead review.

Track at least:

```text
last_successful_scan_at
last_durable_progress_at
foreground_deferral_started_at
consecutive_foreground_deferrals
```

A foreground-driven deferral may leave runtime health unchanged while:

```text
deferral_age < 30 seconds
```

If no successful durable reader progress occurs for:

```text
>= 30 seconds
```

because of writer deferral:

emit:

```text
visit.reader_scan_failed
or visit.reader_degraded
reason=writer_starvation
```

and:

```text
health_callback(False)
```

A later successful scan/progress returns health to normal through the existing callback path.

No persisted health table is required.

---

# 21. Immediate reader degradation cases

The following remain immediate failures:

```text
SQLite IO/CORRUPT/FULL/CANTOPEN/etc.
checkpoint integrity error
source read failure
unexpected exception
BUSY caused by overlong background holder
invalid internal state
```

Do not relabel them as expected scheduling.

---

# 22. Start budget contract

Existing default total budget remains:

```text
VISIT_LIFECYCLE_START_TOTAL_BUDGET_MS=2000
```

This TASK MUST NOT increase it as the fix.

Existing Start retry/idempotency behavior remains.

Acceptance requirement:

```text
a Start MUST NOT exhaust its 2000 ms total budget
because a background operation held/reacquired the writer
```

If Start exhaustion occurs due foreground-vs-foreground saturation beyond tested capacity, that is a separate capacity result.

Telemetry must make that distinction provable.

---

# 23. Start writer-slot wait

Existing default:

```text
VISIT_LIFECYCLE_START_WRITER_SLOT_WAIT_MS=750
```

remains unchanged in the initial corrective patch.

A bounded background chunk admitted before a waiting Start should complete comfortably inside that window under normal storage conditions.

Do not "fix" test failures by increasing this value.

---

# 24. Background writer-slot waits

Existing:

```text
reader_writer_slot_wait_ms=250
reconciliation_writer_slot_wait_ms=250
```

remain unchanged in the initial corrective patch.

The scheduler fairness and classification changes must work with them.

If Tech Lead later chooses different values, that is tuning after the root-cause fix, not the fix itself.

---

# 25. Start idempotency / authorization invariants

Existing unique authorization identity remains:

```text
(auth_session_id, auth_run_number)
```

Concurrent retry must preserve:

```text
exactly one visit_authorizations row
```

for one logical Start.

Ambiguous commit retry continues to resolve through existing duplicate detection.

No duplicate authorization may be introduced by scheduler retries.

No accepted authorization may disappear merely because the reader/reconciler was active.

---

# 26. Reader event idempotency

Existing normalized:

```text
event_id
```

remains the idempotency key.

A deferred/replayed line:

```text
same event_id
```

must not create a second source event or second close.

No change to offline matching semantics in this TASK.

`TASK-VISIT-FINALIZATION-DRIFT-01` semantics on current `main` are preserved.

---

# 27. Checkpoint/evidence atomicity tests

Required explicit test:

1. reader reads a normalized line;
2. force coordinator foreground contention before reader write acquisition;
3. reader defers;
4. verify durable `source_offset` did not pass the line;
5. verify source event is absent if transaction never began;
6. release/start contention;
7. next scan re-reads line;
8. source event is persisted exactly once;
9. checkpoint advances exactly once to correct offset.

Also test failure after:

```text
BEGIN IMMEDIATE
```

but before commit:

```text
transaction rolls back
checkpoint remains old
next scan safely retries
```

No lost evidence.

---

# 28. Pending-chunk idempotency tests

Populate more than one chunk of:

```text
pending_match
```

events.

Force a foreground Start between chunks.

Required sequence:

```text
pending chunk A commits
lease releases
Start acquires and commits
pending chunk B later reacquires
```

Verify:

```text
no pending row processed twice
no row skipped
event ordering remains deterministic
source results are valid
```

A forced failure in chunk B must not roll back committed chunk A.

Re-running pending processing finishes from durable state.

---

# 29. Background FIFO tests

With:

```text
reader waiter A
reconciliation waiter B
```

in background FIFO, and no foreground:

```text
A then B
```

remains the order.

A background worker that releases and immediately requests another lease is appended to the background queue and does not jump ahead of already queued background work.

---

# 30. Foreground priority tests

Required deterministic tests:

## Normal priority

Active background chunk + queued Start + queued background:

```text
current background finishes
→ Start
→ next background
```

## New background while Start waits

New background cannot acquire ahead of waiting Start unless the background FIFO head has reached the explicit starvation escape age.

## Starvation escape

Under a continuously non-empty foreground queue:

```text
oldest background head
```

must eventually receive one bounded chunk.

After that one chunk:

```text
foreground priority resumes.
```

---

# 31. Holder telemetry tests

Use a controllable monotonic clock.

Verify coordinator snapshot during contention identifies:

```text
holder_operation=pending_retry
holder_age_ms=<expected>
foreground_queue_depth=<expected>
background_queue_depth=<expected>
```

and separately:

```text
holder_operation=start
```

for foreground-driven reader deferral.

Verify fields propagate to:

```text
visit.storage_error
visit.reader_scan_deferred
visit.reader_scan_failed / degraded
```

where applicable.

Do not include tokens, credentials, raw webhook payloads.

---

# 32. Telemetry volume

Contention telemetry must be useful without log flooding.

Recommended contract:

- Start final storage error: emit every final failure as today.
- Reader expected deferral: one event per scan, not per failed lease attempt.
- Prolonged reader starvation: transition/event on crossing degraded threshold, not every loop.
- Recovery to healthy: existing successful scan/runtime state change is sufficient; optional explicit recovery event is acceptable.
- Overlong background holder: emit at failure/deferral observation point with holder age.

No high-frequency per-lock polling logs.

---

# 33. Runtime health semantics

Keep Visit runtime states:

```text
active
degraded
unavailable
...
```

No new public Home Health status is introduced.

Change only the evidence driving reader health:

```text
short expected foreground deferral
≠
immediate reader unhealthy
```

But:

```text
prolonged no-progress writer starvation
=
degraded
```

No change to Home Health API contract is required.

---

# 34. Schema decision

FINAL requirement for this TASK:

```text
PRAGMA user_version remains 2
```

No:

```text
new Visit table
new Visit column
new index
migration
```

is currently required.

Scheduler state and health/holder data remain in-process.

If implementation discovers a schema requirement, STOP and return for architecture review.

---

# 35. Auth / Omada boundary

Forbidden:

```text
AuthWorker decision changes
Omada provider/client changes
Omada timeout changes
Omada authorize/readback changes
CAPPORT changes
session semantics changes
```

The Visit Start sink interface presented to Auth remains semantically unchanged.

Guest authorization success remains independent of whether the auxiliary Visit record can be persisted.

---

# 36. Other subsystem boundaries

No changes required to:

```text
Current State
Observation schema/collector
Analytics formulas
Home Activity formulas
Visitor Registry schema
CAPPORT
Admin frontend
Omada webhook normalization contract
```

Reconciliation Registry reads remain as today.

---

# 37. Expected implementation surface

Likely files:

```text
app/visit_lifecycle/repository.py
app/visit_lifecycle/models.py
app/visit_lifecycle/webhook_reader.py
app/visit_lifecycle/runtime.py
app/visit_lifecycle/service.py
app/visit_lifecycle/reconciliation.py
```

Possibly:

```text
app/visit_lifecycle/telemetry.py
```

only for safe field plumbing.

Tests:

```text
tests/visit_lifecycle/test_writer_contention.py
tests/visit_lifecycle/test_webhook_reader.py
tests/visit_lifecycle/test_repository.py
tests/visit_lifecycle/test_reconciliation.py
tests/visit_lifecycle/test_runtime.py
```

Add a dedicated opt-in load test/benchmark if appropriate:

```text
tests/visit_lifecycle/writer_contention_load.py
```

No external dependency.

---

# 38. Production-compatible concurrency acceptance

The acceptance test must exercise all three steady-state write producers concurrently:

```text
foreground Start
reader
reconciliation
```

and include a durable pending-offline backlog so:

```text
pending_retry
```

also participates.

Required dimensions:

```text
sustained Start traffic
reader journal growth
pending_match backlog
reconciliation backlog
real Visit schema v2
real SQLite WAL configuration
real PriorityWriteCoordinator
```

No mocked lock coordinator for the acceptance run.

Mocks may be used only for external Registry read data and for deterministic unit tests.

---

# 39. Load profile — DRAFT proposal

Because the supplied production evidence establishes contention but does not include a canonical observed Start-per-second peak, the final acceptance rate MUST be tied to measured production evidence before FINAL approval.

Proposed rule:

```text
test_start_rate
>= 2 × measured production 15-minute peak Start rate
```

with a conservative floor:

```text
10 Start submissions / second
```

if no higher measured peak is available.

Proposed sustained duration:

```text
60 seconds
```

plus catch-up observation after producers stop.

This rate/duration is a DRAFT proposal for Tech Lead validation, not a claim about current production traffic.

---

# 40. Load test data shape

Use unique:

```text
auth_session_id + auth_run_number
```

for each logical Start.

To test realistic reuse safely, distribute Starts across a bounded set of Site+MAC pairs rather than forcing all requests to one MAC.

The test must verify both:

```text
opened
reused
```

paths without violating the single-open Site+MAC invariant.

Feed normalized reader data through a temporary regular JSONL source using the same reader code.

Seed:

```text
>= current pending_offline_batch_size
```

pending rows so chunk/yield is exercised.

Seed reconciliation candidates sufficient to keep reconciliation active during the sustained window.

---

# 41. Concurrency acceptance — Start

At accepted load:

```text
0 Start outcomes may exhaust the 2000 ms budget
because holder_operation is background
```

Required telemetry/assertion:

```text
no visit.storage_error
where:
    operation=start
    retry_exhausted=true
    and contention source/holder is
        reader_line
        reader_checkpoint
        pending_retry
        reconciliation
```

Also record:

```text
Start count
opened count
reused count
duplicate retry recovery count
p50/p95/p99 total Start wait
max total Start wait
```

DRAFT target:

```text
p99 Start completion < 750 ms
```

under the accepted test profile.

The hard product acceptance remains:

```text
no background-caused 2000 ms exhaustion
```

---

# 42. Concurrency acceptance — reader

During sustained Start load:

```text
reader must continue making durable progress
```

It may emit bounded expected deferral telemetry.

It MUST NOT remain permanently stuck at one source offset.

Required metrics:

```text
reader durable source_offset over time
input file size over time
reader lag bytes
deferred scan count
failed/degraded scan count
```

Acceptance:

```text
reader progress occurs during sustained load
```

and after test producers stop:

```text
reader reaches final file size within 2 normal scan intervals
```

Using current default scan interval this is:

```text
<= 10 seconds
```

unless the test intentionally overrides scan cadence.

No source line/evidence may be missing.

---

# 43. Concurrency acceptance — pending retry

Seed a backlog large enough to require multiple chunks.

Verify:

```text
more than one writer lease is used
```

for one overall pending pass.

A waiting foreground Start must be observed acquiring between pending chunks.

At end:

```text
eligible pending rows are processed
or remain durably pending according to their real matching semantics
```

No rows vanish.

---

# 44. Concurrency acceptance — reconciliation

Reconciliation must continue making progress under sustained Starts.

It may be deferred.

It MUST NOT prevent Start from completing.

It MUST NOT starve forever.

At end of the accepted run, reconciliation attempt counters/progress must show forward movement.

No Visit start evidence is modified.

---

# 45. Authorization data integrity acceptance

If:

```text
N
```

unique logical successful Start submissions are accepted by the test sink, then durable:

```text
visit_authorizations
```

must contain exactly:

```text
N unique (auth_session_id, auth_run_number)
```

for those submissions, excluding only deliberately simulated fail-open storage-unavailable cases.

For the primary acceptance profile, expected deliberately unavailable count is:

```text
0
```

Verify:

```text
no duplicate key
no missing authorization
no duplicate Visit opening from retries
```

---

# 46. Reader data integrity acceptance

For every generated normalized offline event ID expected to be consumed:

```text
COUNT(visit_source_events WHERE event_id = ?) <= 1
```

and for every fully consumed line after catch-up:

```text
durable checkpoint offset
```

must be at/after that line exactly according to the current reader contract.

No checkpoint may jump over an event whose durable processing did not commit.

---

# 47. Database integrity acceptance

After concurrency/load test:

```text
PRAGMA user_version = 2
PRAGMA quick_check = ok
PRAGMA foreign_key_check = []
```

Existing exact schema signature remains unchanged.

No migration occurs.

---

# 48. Shutdown acceptance

Under active contention:

1. background holder active;
2. foreground Start waiting;
3. reader/reconciliation waiting;
4. request shutdown.

Required:

```text
stop_accepting wakes waiters
Start returns fail-open/shutting-down as existing contract requires
background loops stop at safe boundaries
no deadlock
no partially committed chunk
writer coordinator queues drain
```

No new shutdown timeout increase as the fix.

---

# 49. Regression matrix

At minimum retain/pass:

- existing writer contention tests;
- ambiguous commit retry idempotency;
- waiting Start precedes normal background;
- current Start fail-open tests;
- webhook reader checkpoint rotation/truncation tests;
- offline finalization tests including `TASK-VISIT-FINALIZATION-DRIFT-01`;
- reconciliation bounded pass tests;
- Visit repository exact schema tests;
- Visit runtime state tests;
- Auth integration proving Visit failure does not fail Omada authorization;
- Home Activity / Visit Analytics targeted regressions affected only by Visit source correctness.

Existing tests that intentionally hold a background lease beyond Start budget may continue to prove fail-open behavior as a pathological fixture.

They MUST NOT be interpreted as desired production scheduling behavior.

---

# 50. New mandatory deterministic tests

At minimum add:

1. pending batch is split into multiple writer leases;
2. pending writer releases between chunks;
3. queued Start runs between chunks;
4. pending processing resumes from durable DB state;
5. chunk failure does not undo earlier committed chunk;
6. reader foreground deferral does not advance checkpoint;
7. deferred reader line is later persisted exactly once;
8. expected foreground deferral does not immediately mark runtime degraded;
9. prolonged no-progress deferral eventually marks runtime degraded;
10. successful later scan recovers reader health;
11. background-holder BUSY remains real degradation;
12. coordinator snapshot exposes holder operation/age/queue depths;
13. Start final BUSY telemetry identifies blocker;
14. background FIFO remains deterministic;
15. aged background waiter receives one starvation-escape lease;
16. only one escape chunk is granted before foreground priority resumes;
17. reconciliation eventually progresses under sustained foreground;
18. shutdown with aged/background/foreground waiters has no deadlock.

---

# 51. No timeout-only acceptance

A candidate implementation FAILS architecture review if its effective solution is only any combination of:

```text
250 ms → larger reader wait
750 ms → larger Start slot wait
500 ms → larger SQLite busy timeout
2000 ms → larger Start total budget
500 pending rows → same transaction with longer timeout
```

Timeout changes may be considered later as evidence-driven tuning only after:

```text
chunk/yield
fairness
deferral classification
holder telemetry
```

are implemented and proven.

---

# 52. Performance evidence required from coder

Coder handoff must include:

```text
baseline SHA
candidate SHA
Python version
SQLite version
journal_mode
synchronous setting
Start load profile
reader input rate/profile
pending backlog count
reconciliation candidate count
duration
```

Report:

```text
Start p50/p95/p99/max
Start retry_exhausted count
background-caused Start exhaustion count

reader deferral count
reader real-failure count
reader maximum lag bytes
reader final catch-up seconds

pending chunks committed
maximum pending chunk item count
maximum observed background holder_age_ms by operation

reconciliation processed count

authorization expected/actual
source events expected/actual
quick_check
foreign_key_check
schema version/signature
```

---

# 53. Production telemetry acceptance

After eventual deployment, observe at minimum:

```text
visit.storage_error operation=start
visit.reader_scan_deferred
visit.reader_scan_failed / reader degradation
visit.reconciliation_degraded
writer contention fields
```

Acceptance intent:

- background-caused Start `retry_exhausted=true` disappears;
- short foreground reader deferrals may still occur and are identifiable;
- repeated reader error-level `busy` due ordinary Start contention disappears;
- no sustained reader lag;
- no overlong `pending_retry` holder;
- holder metadata identifies any remaining contention source.

---

# 54. Production rollout safety

This TASK changes in-process scheduling and transaction chunking only.

No DB migration is expected.

Owner-controlled rollout should include:

1. exact artifact/Central Lab PASS;
2. DB backup under existing approved SQLite-safe procedure;
3. service restart;
4. runtime health check;
5. initial Start + reader sanity check;
6. telemetry observation window;
7. DB integrity check if required by deployment plan.

No manual DB mutation is part of this TASK.

---

# 55. Rollback

Because schema remains v2:

```text
code rollback does not require DB downgrade
```

Committed chunk results are ordinary valid Visit mutations and remain durable.

Do NOT attempt to reverse already valid Visit starts/source events merely because scheduler code is rolled back.

Rollback reintroduces old contention behavior and is emergency-only.

---

# 56. Explicit non-goals

This TASK does NOT:

- change Visit offline matching policy;
- change `reported_connected_seconds` semantics;
- reconstruct historical Visits;
- change Home Activity coverage;
- change Home Activity formulas;
- change Auth success criteria;
- change Omada calls;
- add a distributed lock;
- add Redis/PostgreSQL;
- add a second Visit writer;
- change SQLite schema;
- make background equal-priority to foreground;
- guarantee success under unbounded foreground overload;
- solve host-level disk failure;
- hide genuine SQLite `BUSY`/IO errors.

---

# 57. Architecture stop conditions

Return to Tech Lead/Architect instead of expanding scope if implementation requires:

```text
schema v3
new persistence service
multiprocess writer coordination
changes to AuthWorker
changes to Omada provider/client
changes to CAPPORT
changes to Visit matching/finalization semantics
changes to Analytics formulas
new external dependency
```

---

# 58. Questions for Tech Lead review before FINAL

The architectural direction is proposed, but these numeric scheduling values are intentionally marked DRAFT and should be approved or adjusted before FINAL:

```text
BACKGROUND_STARVATION_AGE_MS = 200
BACKGROUND_CHUNK_MAX_ITEMS = 25
BACKGROUND_CHUNK_TARGET_MAX_HOLD_MS = 50
READER_DEFERRAL_DEGRADED_AFTER_SECONDS = 30
production-compatible load floor = 10 Starts/sec
load duration = 60 sec
p99 Start target = < 750 ms
```

The structural decisions should remain regardless of tuning:

```text
foreground priority preserved
background starvation escape exists
pending retry releases between bounded chunks
no mid-transaction preemption
expected foreground deferral != immediate failure
prolonged no-progress deferral = degradation
holder/queue telemetry required
schema v2 unchanged
Auth/Omada unchanged
```

---

# 59. DRAFT acceptance summary

The corrective design is successful only if a sustained mixed workload can demonstrate:

```text
Start remains preferred foreground work
+
no Start exhausts 2000 ms because of background writer ownership
+
background work cannot starve indefinitely
+
pending retry cannot monopolize one lease across a large batch
+
reader durable offset continues to move
+
reader catches up
+
foreground deferral is distinguishable from real degradation
+
contention source is diagnosable from telemetry
+
no duplicate/missing Visit authorization
+
no lost/skipped reader evidence
+
schema remains v2
+
Auth/Omada contracts remain unchanged
```

---

# 60. Required next step

Tech Lead reviews this DRAFT against production contention evidence.

After numeric scheduling/load thresholds and deferral-health semantics are approved, Architect issues:

```text
TASK-VISIT-WRITER-CONTENTION-01-FINAL
```

Only FINAL authorizes an implementation handoff to coder.
