# TASK-VISIT-WRITER-CONTENTION-01 — Visit Lifecycle Writer Contention / Background Fairness — FINAL

**Project:** CaptivPortal  
**Type:** Corrective / Production concurrency defect  
**Priority:** High  
**Status:** FINAL — Tech Lead R2 corrections incorporated / coder-ready specification  
**Prepared:** 2026-08-27  
**Repository baseline verified:** `origin/main@e34b6d047fec36eca48ebacf3281b95ee5d03474`  
**Affected subsystem:** Visit Lifecycle local SQLite write scheduling  
**Schema:** v2 — MUST remain v2  
**Auth / Omada contract:** MUST remain unchanged  
**Production activation:** Owner-controlled; this FINAL authorizes coder implementation only, not production deployment

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

# 3. Confirmed production mechanism and repository structural risks

This TASK separates what production evidence proves from what current code proves as structural risk.

## 3.1 Confirmed production mechanism

Production evidence proves:

```text
reader BUSY
→ contention_layer = PriorityWriteCoordinator / coordinator-level contention
```

It does NOT prove which specific active holder caused each historical production incident, because the pre-fix coordinator did not expose holder identity/age.

Therefore:

```text
specific production holder = NOT PROVEN by existing telemetry
```

This TASK MUST NOT retrospectively attribute historical incidents to `pending_retry`, `reader`, `reconciliation`, or `start` without direct evidence.

## 3.2 Confirmed repository structural risk — long pending transaction

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

This is a confirmed repository structural risk.

It is NOT claimed to be the proven holder of any specific historical production incident.

A foreground Start arriving after that transaction has begun cannot preempt it and may wait for the entire batch.

## 3.3 Background starvation / false reader failure

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

The confirmed production root cause category is:

```text
coordinator-level Visit writer contention
```

The repository contains structural conditions capable of producing or amplifying that contention:

```text
A. background work can hold a writer lease for too much work
   (`process_pending_events` is a confirmed example)
+
B. foreground priority is absolute with no starvation escape
+
C. expected foreground-driven background deferral is represented
   as a generic storage failure
+
D. contention telemetry cannot identify the active holder precisely
```

The exact holder of historical incidents remains unknown until the new telemetry exists.

The root cause is NOT:

```text
SQLite corruption
insufficient SQLite busy_timeout by itself
insufficient Start retry budget by itself
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

# 6. Scheduler model — FINAL design

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

background starvation credit:
    per background worker/class
    starvation_since / first_deferred_at

fairness latch:
    foreground_grant_required_after_escape
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

Approved constant:

```text
BACKGROUND_STARVATION_AGE_MS = 200
```

## 7.1 Normal scheduling

If no background work class has accumulated starvation credit >= 200 ms:

```text
foreground head wins whenever foreground queue is non-empty
```

This preserves existing Start priority.

## 7.2 Persistent starvation credit

Starvation age MUST NOT be tied only to the lifetime of one waiter object.

For each steady-state background work class at minimum:

```text
reader
pending_retry
reconciliation
```

maintain process-local:

```text
starvation_since / first_deferred_at
```

or equivalent.

When expected foreground priority causes a background acquisition to defer/time out and the work still exists:

```text
starvation credit persists across waiter removal, scan return, sleep, and requeue
```

A newly-created waiter for the same outstanding background class MUST inherit the accumulated starvation age.

Starvation credit resets only when one of these becomes true:

```text
that background class actually acquires the writer lease
AND performs bounded progress

OR

the corresponding work disappears / no longer needs the writer

OR

shutdown/cancellation clears that work
```

A simple:

```text
new waiter → age=0
```

after every 250 ms deferral is forbidden.

No persisted DB state is required.

## 7.3 Aged background waiter

The oldest eligible background FIFO head whose persistent starvation credit reaches:

```text
200 ms
```

may receive one starvation-escape grant even while foreground waiters exist.

The admitted work is still restricted by the short background chunk contract.

## 7.4 Mandatory foreground grant after an escape

After one aged-background escape is granted:

```text
foreground_grant_required_after_escape = true
```

If foreground queue is non-empty, the next successful steady-state writer grant MUST be foreground.

Another aged background waiter MUST NOT receive a second escape before that foreground grant occurs.

Once the required foreground grant succeeds:

```text
foreground_grant_required_after_escape = false
```

If the foreground queue becomes empty before the latch can be satisfied, the latch may clear.

This prevents:

```text
reader escape
→ pending_retry escape
→ reconciliation escape
```

from forming a background burst ahead of queued Starts.

## 7.5 Result

The scheduler therefore guarantees:

```text
normal foreground priority
+
bounded background starvation escape
+
at most one background escape before a queued foreground grant
```

---

# 8. Background chunk contract

Approved shared steady-state background limits:

```text
BACKGROUND_CHUNK_MAX_ITEMS = 25
BACKGROUND_CHUNK_TARGET_MAX_HOLD_MS = 50
```

These are FINAL task constants, not new production knobs in the first implementation.

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

pass_cursor = null

while total_remaining > 0:
    if shared scan deadline reached OR shutdown/cancel requested:
        stop pass

    acquire background lease as pending_retry
        using the same shared scan deadline
        and shutdown cancellation

    BEGIN IMMEDIATE

    select/process:
        <= BACKGROUND_CHUNK_MAX_ITEMS
        after pass_cursor
        stop adding rows when target chunk time reached
        stop adding rows when scan deadline/cancel is reached

    COMMIT
    release lease

    advance pass_cursor by the last EXAMINED row key
    emit outcomes for committed chunk

    if no rows:
        stop

    total_remaining -= examined item count

    reacquire for next chunk if budget remains
```

The configured:

```text
VISIT_LIFECYCLE_PENDING_OFFLINE_BATCH_SIZE
```

remains a per-pass total examination ceiling.

It is NOT a transaction size.

The same reader scan time budget applies simultaneously:

```text
per-pass item ceiling
AND
reader scan monotonic deadline

whichever is reached first
```

---

# 10. Pending retry ordering and per-pass keyset traversal

Preserve deterministic pending ordering:

```text
pending_until ASC
event_id ASC
```

A repeated plain:

```sql
WHERE processing_result='pending_match'
ORDER BY pending_until, event_id
LIMIT 25
```

for each chunk is forbidden.

Reason:

A retry may legitimately leave a row as:

```text
processing_result = pending_match
```

when grace has not expired and no matching Visit exists.

Without a per-pass cursor, the same first 25 pending rows could be re-examined repeatedly and later rows would never be reached.

## 10.1 Canonical per-pass keyset

Maintain an in-memory cursor for the current pending pass only:

```text
after_pending_until
after_event_id
```

First chunk:

```sql
WHERE processing_result='pending_match'
ORDER BY pending_until ASC, event_id ASC
LIMIT <chunk_limit>
```

Subsequent chunks:

```sql
WHERE processing_result='pending_match'
  AND (
      pending_until > ?
      OR (pending_until = ? AND event_id > ?)
  )
ORDER BY pending_until ASC, event_id ASC
LIMIT <chunk_limit>
```

## 10.2 Cursor advances by examined rows

After a chunk commits, advance the pass cursor to:

```text
(pending_until, event_id)
of the last EXAMINED row
```

even if that row remains:

```text
pending_match
```

Therefore:

```text
one pending row
→ at most one examination per pending pass
```

## 10.3 Durable revalidation

The per-pass cursor is NOT durable authority.

It is not stored in the DB.

Every row selected for mutation MUST still be revalidated inside the current transaction:

```text
processing_result == pending_match
```

If another transaction changed it, skip safely.

On:

```text
error
new scan
process restart
```

the next pass begins again from current durable DB state.

The DB remains the source of truth.

## 10.4 Mandatory regression

Required deterministic test:

```text
first 25 rows remain pending_match after retry

same pending pass continues

next 25 rows are still reached

no row is examined twice in that pass
```

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

# 14. Shared reader scan deadline / cancellation contract

`VisitLifecycleWebhookReader.scan_once()` creates one monotonic scan deadline:

```text
scan_deadline =
    scan_started + reader_max_duration_seconds
```

That same deadline and the reader shutdown/cancellation signal MUST propagate through:

```text
scan_once
→ service.retry_pending
→ repository/process_pending_events chunk loop
→ each pending coordinator acquisition
```

Before every new pending chunk:

```text
if scan_deadline reached
OR shutdown/cancel requested:
    do not acquire a new chunk
    stop the pending pass
```

Between items inside a chunk:

```text
if deadline/cancel reached:
    stop adding new items
    commit/rollback current safe work as appropriate
    release writer lease
    stop pass
```

No new chunk may begin after deadline exhaustion.

The same budget therefore bounds:

```text
source processing
+
pending retry
```

within one scan invocation.

The per-pass pending item ceiling and time deadline are simultaneous:

```text
max 500 examined rows by current config
OR
max reader scan duration

whichever comes first
```

No background chunking implementation may extend one scan indefinitely by repeatedly reacquiring the writer.

---

# 15. Reconciliation contract

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

# 16. Coordinator holder telemetry

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

# 17. Contention error/deferral context

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

# 18. Distinguish coordinator BUSY from SQLite BUSY

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

# 18A. Final Start retry-budget blocker aggregation

`LocalVisitStartSubmitter` may perform up to three storage attempts inside one shared 2000 ms Start budget.

The final:

```text
visit.storage_error
operation=start
retry_exhausted=true
```

MUST summarize blocker attribution across ALL BUSY attempts in that one logical Start call.

Required aggregate semantics, with equivalent field names allowed:

```text
coordinator_busy_attempt_count
sqlite_busy_attempt_count

background_blocked_attempt_count
background_blocked_wait_ms

foreground_blocked_attempt_count
foreground_blocked_wait_ms

max_background_holder_age_ms
last_holder_operation
```

Each failed attempt contributes based on its captured contention snapshot.

Example:

```text
attempt1 = pending_retry 700 ms
attempt2 = reader 700 ms
attempt3 = start 500 ms
```

must NOT be summarized as merely:

```text
last_holder_operation=start
```

The final error must still prove that background work consumed part of the overall budget.

This aggregate is per logical `submit_authorized()` call only.

No persisted telemetry state is required.

This contract is necessary to prove:

```text
background-caused Start exhaustion = 0
```

over the whole 2000 ms budget rather than only the final attempt.

---

# 19. Expected reader deferral semantics

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

# 20. What qualifies as expected foreground deferral

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

# 21. Reader degradation after prolonged deferral

Do not hide starvation behind endless `reader_scan_deferred`.

The approved degradation threshold is:

```text
READER_DEFERRAL_DEGRADED_AFTER =
    max(
        30 seconds,
        6 × configured scan_interval_seconds
    )
```

At the current production default:

```text
scan_interval_seconds = 5
```

this remains:

```text
30 seconds
```

## 21.1 Continuous contention episode

Health MUST NOT be based simply on:

```text
time since checkpoint changed
```

because a quiet journal may legitimately produce no checkpoint movement for hours.

Instead track a process-local continuous foreground-contention episode.

Episode starts on:

```text
expected foreground coordinator deferral
```

and preserves:

```text
contention_episode_started_at
consecutive_foreground_deferrals
last_successful_scan_at
last_durable_progress_at
```

The episode resets when any one occurs:

```text
a successful scan completes without that writer contention

OR

successful durable reader progress occurs

OR

the background work/contention that caused the episode disappears

OR

shutdown/cancellation ends the work
```

A short foreground-driven deferral leaves runtime health unchanged while:

```text
continuous episode age < threshold
```

If the reader continuously cannot complete/progress because of coordinator foreground contention for:

```text
>= max(30s, 6 × scan_interval)
```

emit:

```text
visit.reader_scan_failed
or visit.reader_degraded
reason=writer_starvation
```

and call:

```text
health_callback(False)
```

A later successful scan/progress recovers health through the existing callback path.

No persisted health table is required.

---

# 22. Immediate reader degradation cases

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

# 23. Start budget contract

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

# 24. Start writer-slot wait

Existing default:

```text
VISIT_LIFECYCLE_START_WRITER_SLOT_WAIT_MS=750
```

remains unchanged in the initial corrective patch.

A bounded background chunk admitted before a waiting Start should complete comfortably inside that window under normal storage conditions.

Do not "fix" test failures by increasing this value.

---

# 25. Background writer-slot waits

Existing:

```text
reader_writer_slot_wait_ms=250
reconciliation_writer_slot_wait_ms=250
```

remain unchanged in the initial corrective patch.

The scheduler fairness and classification changes must work with them.

If Tech Lead later chooses different values, that is tuning after the root-cause fix, not the fix itself.

---

# 26. Start idempotency / authorization invariants

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

# 27. Reader event idempotency

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

# 28. Checkpoint/evidence atomicity tests

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

# 29. Pending-chunk idempotency tests

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

# 30. Background FIFO tests

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

# 31. Foreground priority tests

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

# 32. Holder telemetry tests

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

# 33. Telemetry volume

Contention telemetry must be useful without log flooding.

Recommended contract:

- Start final storage error: emit every final failure as today.
- Reader expected deferral: one event per scan, not per failed lease attempt.
- Prolonged reader starvation: transition/event on crossing degraded threshold, not every loop.
- Recovery to healthy: existing successful scan/runtime state change is sufficient; optional explicit recovery event is acceptable.
- Overlong background holder: emit at failure/deferral observation point with holder age.

No high-frequency per-lock polling logs.

---

# 34. Runtime health semantics

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

# 35. Schema decision

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

# 36. Auth / Omada boundary

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

# 37. Other subsystem boundaries

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

# 38. Expected implementation surface

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

# 39. Production-compatible concurrency acceptance

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

# 40. Load profile — FINAL acceptance profile

Approved stress profile:

```text
test_start_rate
>= max(
    10 Starts/second,
    2 × measured production 15-minute peak Start rate
)
```

Sustained duration:

```text
60 seconds
```

plus catch-up observation after producers stop.

## 40.1 Canonical production Start-rate evidence

Measured production Start rate MUST represent successful authorizations submitted to the Visit Start sink.

Do NOT derive the peak from:

```text
visit.opened
```

because stale Visit reuse can undercount physical successful authorizations.

Preferred production evidence:

```text
visit.authorization_attached
```

on a corrected runtime, or the corresponding canonical successful Auth telemetry that proves the Start submission path.

`visit.start_reused` / `visit.opened` may be used as supporting breakdown, not as the sole total-load denominator.

The exact source and 15-minute peak used for the load multiplier must be recorded in the test handoff.

---

# 41. Load test data shape

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

# 42. Concurrency acceptance — Start

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

Approved performance target:

```text
p99 Start completion < 750 ms
```

under the accepted test profile.

Hard correctness gate:

```text
no Start exhausts 2000 ms because of background ownership
```

If correctness passes but:

```text
p99 >= 750 ms
```

return performance evidence to Tech Lead.

Do NOT silently increase writer-slot, SQLite, or Start-budget timeouts.

---

# 43. Concurrency acceptance — reader

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

After producers stop, first measure residual lag in:

```text
remaining lines
remaining bytes
```

If residual lag fits within two configured scan budgets:

```text
remaining lines <= 2 × reader_max_lines_per_scan
AND
remaining bytes <= 2 × reader_max_bytes_per_scan
```

then hard catch-up expectation is:

```text
reader reaches final file size within 2 normal scan intervals
```

At current default 5 s scan interval:

```text
<= 10 seconds
```

If residual lag exceeds either two-scan capacity, do NOT fail the reader merely because 10 seconds is physically insufficient under the bounded-reader contract.

Instead calculate:

```text
required_line_scans =
    ceil(remaining_lines / reader_max_lines_per_scan)

required_byte_scans =
    ceil(remaining_bytes / reader_max_bytes_per_scan)

required_scans =
    max(required_line_scans, required_byte_scans)

expected_catchup =
    required_scans × scan_interval_seconds
    + scheduler tolerance
```

Approved scheduler tolerance:

```text
max(1 scan_interval_seconds, 2 seconds)
```

The test handoff must report the calculation and actual catch-up time.

No source line/evidence may be missing.

---

# 44. Concurrency acceptance — pending retry

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

# 45. Concurrency acceptance — reconciliation

Reconciliation must continue making progress under sustained Starts.

It may be deferred.

It MUST NOT prevent Start from completing.

It MUST NOT starve forever.

At end of the accepted run, reconciliation attempt counters/progress must show forward movement.

No Visit start evidence is modified.

---

# 46. Authorization data integrity acceptance

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

# 47. Reader data integrity acceptance

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

# 48. Database integrity acceptance

After concurrency/load test:

```text
PRAGMA user_version = 2
PRAGMA quick_check = ok
PRAGMA foreign_key_check = []
```

Existing exact schema signature remains unchanged.

No migration occurs.

---

# 49. Shutdown acceptance

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

# 50. Regression matrix

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

# 51. New mandatory deterministic tests

At minimum add:

1. pending batch is split into multiple writer leases;
2. pending writer releases between chunks;
3. queued Start runs between chunks;
4. pending processing resumes from durable DB state;
5. chunk failure does not undo earlier committed chunk;
6. first pending chunk rows remain `pending_match`, but later rows are still reached in the same pass;
7. no pending row is examined twice within one pass;
8. per-pass keyset advances by examined `(pending_until,event_id)`;
9. every selected row revalidates `processing_result='pending_match'` before mutation;
10. reader foreground deferral does not advance checkpoint;
11. deferred reader line is later persisted exactly once;
12. expected foreground deferral does not immediately mark runtime degraded;
13. quiet journal with no checkpoint movement does NOT become degraded;
14. continuous foreground-contention episode >= `max(30s,6×scan_interval)` becomes degraded;
15. successful scan/progress resets the contention episode and recovers health;
16. background-holder BUSY remains real degradation;
17. scan deadline propagates through retry_pending/chunk acquire;
18. no new pending chunk starts after scan deadline exhaustion;
19. shutdown cancellation stops pending reacquisition at safe boundary;
20. coordinator snapshot exposes holder operation/age/queue depths;
21. Start final BUSY telemetry aggregates blockers across all retry attempts;
22. background/foreground blocked wait totals equal the classified BUSY attempt evidence;
23. background FIFO remains deterministic;
24. starvation credit persists across expected deferral, waiter removal, and requeue;
25. aged background waiter receives one starvation-escape lease;
26. after escape, queued foreground MUST receive the next successful steady-state grant;
27. second aged background cannot escape before the required foreground grant;
28. fairness latch clears if foreground queue disappears;
29. reconciliation eventually progresses under sustained foreground;
30. shutdown with aged/background/foreground waiters has no deadlock.

---

# 52. No timeout-only acceptance

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

# 53. Performance evidence required from coder

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
production Start-rate evidence source
measured production 15-minute peak
applied test Start rate

Start p50/p95/p99/max
Start retry_exhausted count
background-caused Start exhaustion count

coordinator_busy_attempt_count
sqlite_busy_attempt_count
background_blocked_attempt_count
background_blocked_wait_ms
foreground_blocked_attempt_count
foreground_blocked_wait_ms
max_background_holder_age_ms

reader deferral count
reader real-failure count
reader maximum lag bytes
reader residual lag lines
reader residual lag bytes
reader calculated catch-up scan count
reader calculated catch-up window seconds
reader actual final catch-up seconds

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

# 54. Production telemetry acceptance

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

# 55. Production rollout safety

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

# 56. Rollback

Because schema remains v2:

```text
code rollback does not require DB downgrade
```

Committed chunk results are ordinary valid Visit mutations and remain durable.

Do NOT attempt to reverse already valid Visit starts/source events merely because scheduler code is rolled back.

Rollback reintroduces old contention behavior and is emergency-only.

---

# 57. Explicit non-goals

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

# 58. Architecture stop conditions

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

# 59. Tech Lead-approved numeric decisions

No scheduling/load numeric A/B question remains for coder.

Approved:

```text
BACKGROUND_STARVATION_AGE_MS = 200
BACKGROUND_CHUNK_MAX_ITEMS = 25
BACKGROUND_CHUNK_TARGET_MAX_HOLD_MS = 50

READER_DEFERRAL_DEGRADED_AFTER =
    max(30 seconds, 6 × scan_interval_seconds)

production-compatible load floor = 10 Starts/sec
load multiplier = 2 × measured production 15-minute Start peak
load duration = 60 sec

p99 Start target = < 750 ms
```

`p99 < 750 ms` is a performance target.

Hard correctness gate remains:

```text
no Start exhausts 2000 ms because of background ownership
```

If the performance target misses while correctness passes:

```text
return evidence to Tech Lead
do not silently tune timeouts
```

Structural decisions are FINAL:

```text
foreground priority preserved
persistent background starvation credit
one starvation escape only
mandatory foreground grant after escape when queued
pending retry releases between bounded chunks
per-pass keyset traversal
shared reader scan deadline/cancellation
no mid-transaction preemption
expected foreground deferral != immediate failure
continuous contention episode drives degradation
holder/queue telemetry required
Start blocker aggregation across retries
schema v2 unchanged
Auth/Omada unchanged
```

---

# 60. FINAL acceptance summary

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

# 61. Required coder handoff

This FINAL is ready for coder implementation.

Coder MUST work from the exact verified baseline or return for impact review if `origin/main` changes in relevant Visit/Auth files.

Recommended branch:

```text
fix/visit-writer-contention-v1
```

Return:

```text
BASELINE
origin_main=<SHA>

BRANCH
<name>

COMMIT
<SHA>
<message>

ARCHITECTURE
single coordinator preserved
foreground priority preserved
persistent starvation credit implemented
foreground-after-escape latch implemented
pending keyset/chunking implemented
shared scan deadline/cancellation implemented
no mid-transaction preemption

TELEMETRY
holder_operation
holder_age_ms
foreground_queue_depth
background_queue_depth
contention_layer
Start retry-budget aggregate blockers

LOAD TEST
production peak evidence source
production peak rate
test rate
duration
Start p50/p95/p99/max
background-caused Start exhaustion count
reader deferrals
reader degradation count
reader catch-up calculation/actual
pending chunks
reconciliation progress

INTEGRITY
expected authorization count
actual authorization count
duplicate authorization count
expected source event count
actual source event count
quick_check
foreign_key_check
user_version
schema signature

INVARIANTS
Auth contract changed: NO
Omada contract changed: NO
CAPPORT changed: NO
Visit schema changed: NO
Visit finalization semantics changed: NO
Home Activity formulas changed: NO
new dependency: NO

TEST COMMANDS
TEST RESULTS

WORKING TREE
clean

REPOSITORY ACTIONS
Push: NO unless separately authorized
PR: NO unless separately authorized
Merge: NO
Deploy: NO
```

Coder runs targeted/module tests and the production-compatible load test.

Official full exact-artifact regression remains Central Lab responsibility before merge/production acceptance.
