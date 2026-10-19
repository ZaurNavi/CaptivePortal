# DRAFT — TASK-TRAFFIC-PROJECTION-LIFECYCLE-CONSISTENCY-01

**Project:** CaptivPortal  
**Priority:** `P0 / PRODUCTION INCIDENT`  
**Area:** Historical Traffic / Traffic Projection / lifecycle / operational health  
**Deliverable:** Architecture DRAFT for Owner + Tech Lead review  
**Status:** `DRAFT — ARCHITECTURAL REVIEW REQUIRED`  
**Implementation authorization:** `NOT GRANTED`  
**Coder:** `HOLD`  
**Production repair:** `HOLD`  
**Projection rebuild/repair:** `HOLD`  
**Manual diverged reset:** `FORBIDDEN`  
**Authoritative Observation mutation:** `FORBIDDEN`  
**Prepared:** 2026-09-10

---

# 0. Executive decision

The incident is accepted architecturally as:

```text
ROOT_CAUSE_CLASS =
RETENTION CLEANUP / FROZEN RECONCILE WINDOW RACE

CONFIDENCE =
VERY HIGH / SUFFICIENT FOR P0 PERMANENT FIX DESIGN
```

The permanent solution is:

```text
1. KEEP Observation as authoritative source of truth.

2. KEEP Traffic Projection as derived/materialized read model.

3. KEEP separate traffic-projection.service.

4. KEEP consistency divergence fail-closed and latched.

5. MAKE retention reconcile-safe:
   active frozen reconcile sweep
   → cleanup fence at reconcile_sweep_from_utc.

6. FREEZE destructive cleanup for:
   diverged Site
   active repair/rebuild Site.

7. KEEP worker process alive on one Site divergence,
   but separate PROCESS HEALTH from PRODUCT HEALTH.

8. ADD explicit projection product-health telemetry
   visible through journal → Alloy → Loki → Grafana.

9. MAKE artifact deployment lifecycle-coherent:
   no in-place application artifact replacement
   while artifact-owned long-running Python processes remain running.

10. RECOVER current Site only after fixed artifact:
    consistent derived-DB backup
    → canonical repair-site
    → full source/projection re-proof
    → Historical Traffic validation.
```

No Historical Traffic semantic calculation changes are authorized by this architecture.

---

# 1. Current repository / incident baseline

Fresh repository rebind for this DRAFT:

```text
CURRENT MAIN =
ff39fe888c53361a7c65a034eaddb0ce92cc4a12

TREE =
f6f1068a579c1f1c6f1debeae2e6a1e0da4823b8
```

This is the merged PR #110 state.

Incident handoff states, and current source review confirms, that PR #110 did not modify the core Projection writer files implicated by the failure mechanism:

```text
app/traffic_projection/service.py
app/traffic_projection/repository.py
app/traffic_projection/source.py
```

Therefore:

```text
PR_110_DIRECT_PROJECTION_REGRESSION =
NO EVIDENCE
```

Do not attribute the incident to Device List / Web UI work without new evidence.

---

# 2. Production problem statement

Historical Traffic branch is unavailable while non-projection Traffic products remain operational.

Working:

```text
Current Network Throughput
Online Guests Traffic
Completed Guest Session Traffic
```

Unavailable:

```text
Network Traffic History
Period Statistics
Peak Load
Traffic by AP
AP Traffic Share
```

Consolidated Traffic Evidence reports Historical delivery/source unavailable.

The common failure boundary is:

```text
HistoricalTrafficReadService
        ↓
TrafficProjectionReadService
        ↓
active Traffic Projection
```

This is not a UI/CSS failure.

---

# 3. Confirmed incident evidence

Production worker:

```text
traffic-projection.service = enabled
traffic-projection.service = active
PID alive
NRestarts = 0
writer lock owned
```

Projection DB:

```text
PRAGMA user_version = 1
PRAGMA quick_check = ok
active version = historical_traffic_projection.v1
version status = active
```

Production Site:

```text
site_id =
6a64f17630da7c70d232187a

status =
diverged

last_error_category =
source_identity

source_head_utc =
2026-09-10T08:28:45.566Z

projection_head_utc =
2026-09-10T08:28:45.566Z

backlog_cycle_count =
0
```

Therefore:

```text
PROCESS DEAD = NO
DB CORRUPTION = NO EVIDENCE
NORMAL BACKLOG = NO
HEAD CATCH-UP FAILURE = NO
CONSISTENCY PROOF FAILURE = YES
```

---

# 4. Frozen reconcile evidence

Failed sweep was frozen at:

```text
reconcile_sweep_from_utc =
2026-08-27T08:26:05.244Z

reconcile_sweep_source_head_utc =
2026-09-10T08:26:05.244Z
```

Read-only identity comparison inside that frozen window:

```text
SOURCE_COUNT      = 34340
PROJECTION_COUNT  = 34338
COUNT_DELTA       = 2

SOURCE_ONLY_COUNT     = 2
PROJECTION_ONLY_COUNT = 0
```

The two exact authoritative source-only cycles are:

```text
72dbc45a-97ff-43c9-80fd-ef9a9b41907c
started 2026-08-27T08:26:28.388Z

34e7cd85-f890-4227-9433-12c65129af5a
started 2026-08-27T08:27:02.854Z
```

Both are:

```text
completed
complete=1
result=success
items_stored=2
error_count=0
AP rows present
```

They are authoritative valid Observation evidence.

---

# 5. Retention-boundary evidence

Near the lower frozen boundary:

```text
08:25:22  projection=NO   outside frozen window
08:25:55  projection=NO   outside frozen window

08:26:28  projection=NO   inside frozen window
08:27:02  projection=NO   inside frozen window

08:27:36  projection=YES  first surviving projection cycle
```

This is exactly consistent with:

```text
frozen lower bound = 08:26:05.244
moving cleanup cutoff later crosses above that bound
two earliest in-window projection cycles disappear
source proof still starts from frozen lower bound
identity count differs by 2
```

No literal DELETE audit record exists for the two UUIDs, but the combined evidence is sufficient to treat this race as the operative root cause for architecture hardening.

---

# 6. Confirmed current code mechanism

Current reconcile behavior:

```text
start full reconcile
        ↓
freeze:
reconcile_sweep_from_utc
reconcile_sweep_source_head_utc
reconcile_sweep_source_head_cycle_id
        ↓
advance durable cursor across worker iterations
        ↓
at completion compare:
source count over frozen window
projection count over same frozen window
```

If counts differ:

```text
status=diverged
last_error_category=source_identity
raise TrafficProjectionDiverged
```

Current cleanup behavior is independent:

```text
cutoff =
current wall clock - retention_days

for each Site:
delete_before(site_id, cutoff)
```

Cleanup does not currently fence itself against the active frozen reconcile lower boundary.

This is the consistency defect.

---

# 7. Root-cause model

Canonical failure sequence:

```text
reconcile freezes lower boundary T0
        ↓
reconcile spans multiple worker iterations
        ↓
wall clock advances
        ↓
cleanup computes T1 = now - retention
where T1 > T0
        ↓
projection cleanup deletes cycles:
T0 <= cycle < T1
        ↓
authoritative source count still evaluates from T0
        ↓
projection count evaluates after deletion
        ↓
source_count != projection_count
        ↓
source_identity
        ↓
Site = diverged
        ↓
Historical Traffic read fails closed
```

The cleanup operation is individually valid against a moving retention window.

The reconcile operation is individually valid against a frozen identity window.

The bug is the absence of a shared retention/reconcile consistency contract between them.

---

# 8. Architectural invariants

The following are permanent.

## 8.1 Authoritative source

```text
observations.sqlite3
=
authoritative Historical Traffic evidence
```

Traffic Projection is derived.

Projection data may be rebuilt.

Observation evidence must not be altered to repair Projection.

## 8.2 Active proof protection

```text
No projection row participating in an active frozen reconcile proof
may be deleted by normal retention cleanup.
```

## 8.3 Offline-style absence principle for projection identity

```text
missing derived row
cannot be interpreted as source absence
if the proof window itself was invalidated by cleanup.
```

## 8.4 Divergence remains fail-closed

```text
diverged
!=
partial
!=
healthy enough
```

Historical read surfaces must not silently serve a consistency-invalid projection.

## 8.5 Divergence is latched

Normal worker maintenance does not automatically clear:

```text
status=diverged
```

A read-only diagnostic/re-proof may gather evidence, but only an explicit Owner-authorized repair operation may restore the Site from a divergence latch.

## 8.6 Process health is not product health

```text
systemd active
writer PID alive
writer lock held

DO NOT imply

Historical Traffic product healthy
```

## 8.7 Artifact coherence

```text
A production checkout/artifact must not be replaced in-place
while a long-running process continues executing code loaded
from the previous artifact.
```

---

# 9. Retention/reconcile consistency solution

## 9.1 Chosen model

Architecture chooses:

```text
PER-SITE CLEANUP FENCE
```

rather than globally postponing all retention during every reconcile.

For each:

```text
projection_version
+
site_id
```

normal current retention cutoff is:

```text
current_retention_cutoff =
now - retention_days
```

If an active reconcile sweep has:

```text
reconcile_sweep_from_utc = T0
```

then:

```text
effective_cleanup_cutoff =
min(
    current_retention_cutoff,
    T0
)
```

Cleanup may delete only cycles:

```text
strictly older than effective_cleanup_cutoff
```

Therefore rows at or after `T0` survive until the frozen proof completes or is explicitly abandoned by repair.

---

# 10. Why cleanup fence is chosen

The fence preserves all required properties.

It allows:

```text
retention cleanup to continue for safely old data
```

while protecting:

```text
the exact active reconcile identity horizon
```

Compared with postponing the entire Site cleanup, it produces less temporary over-retention.

Compared with a new generation/snapshot persistence model, it closes the confirmed race without introducing a new Projection generation domain or schema requirement.

Therefore the P0 architecture does NOT require:

```text
new DB
new generation table
new reconcile snapshot schema
```

---

# 11. Boundary semantics of the fence

Given:

```text
T0 = reconcile_sweep_from_utc
T1 = current moving retention cutoff
T1 > T0
```

during active sweep:

```text
cycle < T0
→ normal retention deletion allowed

cycle = T0
→ protected

T0 < cycle < T1
→ protected

cycle = T1
→ protected by ordinary delete-before boundary

cycle > T1
→ retained
```

After successful reconcile completion clears the frozen sweep state:

```text
next normal cleanup
may advance to current_retention_cutoff
```

At that point those rows are no longer members of an active frozen identity proof.

---

# 12. Cleanup behavior by Site state

Canonical Site cleanup policy:

```text
status=diverged
→ cleanup prohibited for that Site

active explicit repair / rebuilding
→ cleanup prohibited for that Site

active normal reconcile sweep
→ cleanup allowed only with frozen lower-bound fence

healthy with no active sweep
→ normal moving retention cutoff

catching_up with active sweep
→ fenced cleanup

other non-diverged state with no active sweep
→ normal retention policy
```

This policy is per Site and per Projection version.

One unhealthy Site does not freeze retention for unrelated Sites.

---

# 13. Why cleanup freezes on `diverged`

Once consistency has failed, destructive cleanup must not continue changing the forensic/recovery evidence set.

Permanent:

```text
diverged Site
→ no normal retention mutation
until explicit repair begins
```

This can temporarily exceed the nominal retention horizon.

That temporary storage growth is accepted because:

```text
product is already P0 unhealthy
alerting is mandatory
repair requires operator action
preserving evidence has priority over retention exactness
```

A prolonged ignored divergence is an operational incident, not a normal retention state.

---

# 14. Cleanup behavior during explicit repair

Normal retention cleanup does not run against a Site while the Site is in explicit repair/rebuild.

Repair owns its own deliberate derived-data invalidation/rebuild lifecycle.

Do not combine:

```text
normal retention deletion
+
repair deletion
+
reconcile proof
```

as independent destructive actors on the same Site.

---

# 15. Single-writer invariant remains

The existing single writer lock remains authoritative.

No new concurrent Projection writer is introduced.

Permanent:

```text
one Projection writer ownership boundary
```

The cleanup fence does not authorize parallel cleanup and reconcile writers.

---

# 16. Divergence taxonomy

Architecture distinguishes:

## Consistency divergence

Examples:

```text
source_identity
ready_source_identity
deep_fingerprint
other future proof mismatch
```

Meaning:

```text
Projection cannot prove identity with authoritative source.
```

Behavior:

```text
status=diverged
Historical reads fail closed
normal Site projection maintenance blocked
normal Site cleanup blocked
critical telemetry emitted
manual Owner-authorized repair required
```

## Temporary source/storage execution failure

Examples:

```text
source temporarily unavailable
Projection SQLite busy/unavailable
read/write I/O failure
```

These are NOT automatically `diverged`.

They retain existing retry/stale semantics.

Normal bounded automatic retry is allowed.

---

# 17. Automatic recovery decision

Architecture does NOT allow automatic mutation-based recovery from:

```text
diverged
```

even when the observed incident class appears repairable.

Reason:

`source_identity` can indicate more than the confirmed cleanup race:

```text
projection corruption
unexpected source mutation
software defect
identity bug
wrong semantic contract
```

Automatic rebuild could erase forensic evidence and hide a real consistency defect.

Allowed automatic behavior:

```text
read-only health/re-proof diagnostics
telemetry
continued maintenance of unaffected Sites
```

Forbidden automatic behavior:

```text
clear diverged
delete/rebuild Site
insert missing cycles
resume normal reads as healthy
```

---

# 18. Explicit recovery semantics

Recovery from `diverged` requires:

```text
Owner authorization
+
canonical repair operation
+
fresh full proof
```

The existing semantic repair primitive:

```text
repair-site
```

is accepted as the correct recovery operation for this incident class because it:

```text
invalidates previous Site proof
deletes derived Site facts
reprojects from authoritative Observation
runs reconciliation
requires healthy proof
```

A narrow manual INSERT of the two missing cycles is NOT canonical recovery.

`rebuild-range` is not the recovery operation for a latched diverged Site.

---

# 19. Recovery completion rule

A Site is not recovered merely because:

```text
missing rows were repopulated
heads match
worker runs
```

Recovery completes only after new consistency proof establishes:

```text
status=healthy
last_error_category cleared

source/projection retained-window identity match

SOURCE_ONLY_COUNT=0
PROJECTION_ONLY_COUNT=0

full reconcile completed after repair
deep audit passes

backlog=0

source/projection head relationship satisfies healthy contract

Historical Traffic read path accepts Projection as healthy
```

Only then emit:

```text
projection_recovered
```

---

# 20. Worker lifecycle after Site divergence

Architecture chooses:

```text
DO NOT terminate the entire worker process
solely because one Site becomes diverged.
```

Reason:

```text
future multi-Site compatibility
unaffected Sites must remain maintainable
separate version/build work may still exist
process crash/restart would not repair a latched divergence
restart loop would confuse liveness with consistency
```

Instead:

```text
diverged Site
→ fail closed locally
→ skip normal destructive cleanup
→ keep worker alive
→ maintain unaffected Sites
→ expose PRODUCT_UNHEALTHY
→ emit critical telemetry
```

Systemd process liveness remains a separate signal only.

---

# 21. Process health model

Canonical process health answers:

> Is the worker process running and able to own its writer boundary?

Machine concept:

```text
PROCESS_UP
PROCESS_DOWN
```

Evidence includes:

```text
systemd unit state
PID
writer lock ownership
worker startup heartbeat
```

This is not a Historical Traffic availability verdict.

---

# 22. Projection Site maintenance health

Reuse the existing projection health domain:

```text
healthy
catching_up
rebuilding
stale
diverged
unavailable
```

Do not invent a conflicting second Site health machine.

Existing health classification remains the semantic source.

---

# 23. Historical Traffic product health

Add an explicit product-level interpretation.

For one requested Site:

```text
PRODUCT_HEALTHY
only if
active Projection version is valid
AND
Projection Site health == healthy
AND
Historical projection read boundary is available
```

Otherwise:

```text
PRODUCT_UNHEALTHY
```

This mirrors current read behavior, which accepts only healthy Projection for Historical Traffic delivery.

`catching_up` may be useful maintenance progress, but while the read boundary rejects it:

```text
product availability = unhealthy
```

---

# 24. Aggregate product health

For the deployed Historical Traffic product:

```text
overall product health =
unhealthy
if any production-active configured Site
required by Admin product is unhealthy
```

Per-Site health must still be available so one Site failure does not hide healthy Sites.

Multi-Site future:

```text
worker process may be UP
Site A product unhealthy
Site B product healthy
```

---

# 25. Reconcile-stuck definition

Use existing maintenance timing contract rather than introducing an unrelated threshold family.

A reconcile is considered stuck when:

```text
reconcile_sweep_started_at exists
AND
no reconcile/incremental progress
for longer than the accepted
INCREMENTAL_PROGRESS_MAX_AGE_SECONDS
```

Current repository value:

```text
60 seconds
```

This classification is operational health only.

It does not automatically mutate Projection state.

---

# 26. Stale / backlog product signals

Existing health thresholds remain authoritative.

Current repository includes:

```text
HEALTHY_HEAD_LAG_MAX_SECONDS = 90
CATCHING_UP_HEAD_LAG_MAX_SECONDS = 300

HEALTHY_FULL_RECONCILE_MAX_AGE_SECONDS = 600
CATCHING_UP_FULL_RECONCILE_MAX_AGE_SECONDS = 900

INCREMENTAL_PROGRESS_MAX_AGE_SECONDS = 60
```

Do not create a second contradictory timing policy merely for alerts.

Persistent excessive backlog/lag becomes an operational failure through the existing health transition toward `stale`.

---

# 27. Canonical telemetry contract

Required events:

```text
projection_site_diverged
projection_source_identity_failed
projection_stale
projection_reconcile_stuck
projection_worker_source_unavailable
projection_worker_storage_unavailable
projection_recovered
```

Also required operational lifecycle events:

```text
projection_worker_started
projection_worker_stopped
projection_product_health
```

---

# 28. Event semantics

## `projection_source_identity_failed`

Emit at the exact retained-window identity proof failure.

Safe fields include:

```text
projection_version
site_id
error_category
source_count
projection_count
count_delta
reconcile_sweep_from_utc
reconcile_sweep_source_head_utc
```

No raw source rows.

## `projection_site_diverged`

Emit when a Site transitions into `diverged`.

Do not rely only on a repeated generic scan-failed message.

## `projection_recovered`

Emit only after explicit repair and a new healthy proof.

## `projection_reconcile_stuck`

Emit when an active sweep exceeds the accepted progress-age contract.

## Source/storage events

Use separate categories:

```text
source unavailable
storage unavailable
```

Do not collapse them into `diverged`.

---

# 29. Product-health heartbeat

The worker must emit a structured:

```text
projection_product_health
```

heartbeat no less frequently than:

```text
60 seconds
```

for each active Site/version.

Required concepts:

```text
process_up
product_status
site health status
projection_version
projection_revision
source_head_utc
projection_head_utc
head_lag_seconds
reconcile_sweep_started_at
last_full_reconcile_completed_at
last_incremental_progress_at
backlog_cycle_count
error_category
artifact identity
```

This is observability.

It does not change read semantics.

---

# 30. Logging delivery contract

The standalone Projection worker must explicitly initialize production logging so INFO-level Projection telemetry reaches:

```text
systemd journal
```

and from there:

```text
Alloy
→ Loki
→ Grafana
```

Architecture does not accept:

```text
telemetry event exists in source code
```

as sufficient.

The acceptance requirement is:

```text
event emitted by worker
→ visible in journal
→ visible in Loki
→ usable by Grafana alert/panel
```

---

# 31. Telemetry safety

Projection telemetry must remain secret-safe.

Forbidden telemetry:

```text
raw Observation payloads
raw AP/client JSON
OAuth/token data
filesystem secrets
raw exception trace as machine field
SQL dumps
```

Use bounded safe error categories.

---

# 32. Alerting contract

At minimum critical alert conditions:

```text
Site diverged
active version unavailable
Projection storage unavailable
source unavailable beyond accepted health window
Site stale
reconcile stuck
```

Recovery notification:

```text
projection_recovered
```

Process-only alert:

```text
worker process down
```

must be separate from:

```text
Historical Traffic product unhealthy
```

---

# 33. Operational invariant

The following state must become directly visible and alertable:

```text
PROCESS=UP
PRODUCT=UNHEALTHY
SITE=diverged
```

This is the exact state missed by the current operational model.

---

# 34. systemd topology decision

Keep:

```text
captive-portal.service
traffic-projection.service
```

as separate units.

Do NOT embed the Projection writer in the Flask/Web process.

Reasons:

```text
single-writer isolation
fault isolation
independent restart
web availability independence
clear writer ownership
multi-Site maintenance isolation
```

No architecture change makes Projection a child thread of the web service.

---

# 35. Service dependency semantics

The two units belong to one deployed application artifact but remain separate processes.

Ordering may exist, but:

```text
traffic-projection failure
must not force captive-portal process failure
```

and:

```text
web process health
must not be used as Projection product health
```

---

# 36. Artifact-owned service contract

Production deployment must maintain an explicit list of long-running processes that execute code from the deployed CaptivPortal artifact.

At minimum:

```text
captive-portal.service
traffic-projection.service
```

Future artifact-owned long-running units must be added to the same deploy manifest.

---

# 37. Permanent deploy invariant

With the current mutable checkout model:

```text
NO in-place checkout/artifact replacement
while any artifact-owned long-running Python process
continues running from that checkout.
```

This closes the stale-loaded-code-object gap.

---

# 38. General controlled deployment lifecycle

Canonical deployment order for the current mutable `/opt/CaptivePortal` artifact:

```text
pre-deploy validation
        ↓
quiesce artifact-owned background writer(s)
        ↓
stop remaining artifact-owned long-running process(es)
        ↓
verify no old artifact-owned process remains
        ↓
install/checkout exact approved artifact
        ↓
verify exact SHA/tree
        ↓
start captive-portal.service
        ↓
base application readiness
        ↓
start traffic-projection.service
        ↓
verify worker process identity
        ↓
verify Projection product health
        ↓
post-deploy gates
```

The important invariant is not the specific systemd syntax.

It is:

```text
artifact mutation occurs only while old artifact processes are quiesced
```

---

# 39. Artifact identity observability

Each long-running artifact-owned service must report the deployed artifact identity at startup.

Required concepts:

```text
repository SHA
code/tree identity or release identity
service name
process start time
```

Deploy acceptance requires:

```text
expected artifact identity
=
reported loaded service artifact identity
```

This prevents:

```text
filesystem says new SHA
worker still executing old loaded Python modules
```

---

# 40. Restart semantics after deploy

A deploy that changes the CaptivPortal application artifact is incomplete until every artifact-owned long-running service has undergone the controlled lifecycle.

Restarting only:

```text
captive-portal.service
```

is not sufficient while:

```text
traffic-projection.service
```

continues running code from the same mutated checkout.

---

# 41. Current incident recovery principle

The current production Site is recoverable because:

```text
Observation source is intact
Projection is derived
```

Recovery must not begin until the repeatable cleanup/reconcile race is fixed and accepted.

Permanent order:

```text
FIX FIRST
REPAIR SECOND
```

Never:

```text
repair with known-broken retention/reconcile lifecycle
```

---

# 42. Current production recovery strategy

Architecture approves the following incident recovery sequence.

## Phase 1 — fix acceptance

```text
1. Implement reconcile-safe retention and lifecycle/health hardening.
2. Run Owner + Tech Lead acceptance gates.
3. Approve exact fixed artifact.
```

No production repair yet.

## Phase 2 — quiesce and preserve incident evidence

```text
4. Stop/quiesce traffic-projection writer.
5. Verify exclusive writer ownership is released.
6. Take a consistent backup/snapshot of the derived Projection store
   before first repair mutation.
7. Record:
   DB identity/checksum/size,
   active version,
   Site state,
   incident proof values.
```

The backup is a forensic/rollback artifact.

## Phase 3 — deploy fixed artifact

```text
8. Quiesce remaining artifact-owned processes as required.
9. Deploy exact fixed artifact.
10. Verify exact artifact identity.
11. Start/verify captive-portal base application.
12. Keep Projection writer under controlled repair gate
    until canonical repair is initiated.
```

## Phase 4 — canonical Site repair

```text
13. Invoke the existing canonical Owner-authorized repair-site operation
    under the fixed artifact and exclusive writer ownership.
14. Allow durable bounded repair to rebuild Site derived facts
    only from authoritative Observation.
15. Start/resume the fixed Projection worker to continue
    the durable repair lifecycle when required.
```

## Phase 5 — proof

```text
16. Wait for new full reconcile proof.
17. Verify source/projection identity.
18. Verify deep audit.
19. Verify healthy Site state.
20. Verify backlog/head/freshness.
21. Verify Historical Traffic read path.
22. Verify all five affected Admin Historical Traffic products.
23. Verify product-health telemetry and recovered event.
```

Only after all proof gates may the incident be closed.

---

# 43. Backup rule

Projection backup must be consistent.

Do not take a blind single-file copy while an active writer may have WAL state in flight.

Architecture requirement:

```text
writer quiesced
+
SQLite-consistent Projection backup/snapshot
```

The backup is of derived state only.

Observation source is not changed.

---

# 44. Why manual two-row insertion is forbidden

Although exactly two source cycles are currently missing, manually inserting only those facts would not establish:

```text
full retained-window identity
deep semantic fingerprint consistency
correct repair lifecycle state
correct Projection proof metadata
future race immunity
```

Therefore:

```text
manual INSERT of missing cycles
=
not a recovery proof
```

---

# 45. Why blind diverged reset is forbidden

Changing:

```text
status=diverged
→ healthy
```

without rebuild/re-proof would make the product claim consistency that has not been established.

Permanent:

```text
health state follows proof
proof does not follow manually edited health state
```

---

# 46. Failure mode matrix

## Active reconcile + moving cleanup cutoff

Before fix:

```text
can delete in-window rows
→ false identity mismatch
```

After fix:

```text
cleanup fenced at frozen lower boundary
```

## Site diverged

```text
Historical read fail closed
normal cleanup frozen
worker process may remain up
critical health signal
manual repair required
```

## Source temporary failure

```text
no false divergence
retry/stale/unavailable health path
```

## Projection storage temporary failure

```text
product unhealthy/unavailable
worker telemetry
no fabricated historical data
```

## Reconcile no progress

```text
projection_reconcile_stuck
product unhealthy according to existing health/read contract
```

## Worker process dead

```text
PROCESS_DOWN
product unhealthy
systemd restart policy applies
```

## Old code process after artifact replacement

```text
forbidden by deploy contract
```

---

# 47. Compatibility constraints

The P0 fix must preserve:

```text
Historical Traffic calculations
Historical Traffic business semantics
Traffic Evidence semantics
Observation schema
Observation writer behavior
retention_days configured value
Projection semantic contract
Projection active version model
single-writer model
Admin Historical Traffic fail-closed consistency gate
```

No change to:

```text
Current Network Throughput
Online Guests Traffic
Completed Guest Session Traffic
```

except ordinary regression safety.

---

# 48. Projection schema decision

Architecture does NOT require a Projection DB schema migration for the retention fence.

Existing durable fields already provide:

```text
reconcile_sweep_from_utc
reconcile_sweep_started_at
reconcile cursor
status
last_error_category
```

If Tech Lead repository rebind finds a factual need for new persisted state:

```text
return for architecture review
```

Do not add schema “for convenience”.

---

# 49. Observation boundary

No repair path may:

```text
DELETE Observation evidence
rewrite historical Observation cycles
fabricate Observation cycles
change Observation retention to hide mismatch
```

Observation remains source of truth.

---

# 50. Historical read boundary remains fail-closed

Current Projection read behavior rejects a Site whose health is not:

```text
healthy
```

This architecture preserves that principle.

Do not turn:

```text
diverged
stale
unavailable
rebuilding
catching_up
```

into synthetic valid Historical Traffic merely to restore UI availability.

---

# 51. Test architecture — retention race reproduction

Mandatory future implementation acceptance scenario:

```text
retention = 14d

full reconcile begins
frozen lower bound = T0

sweep requires multiple worker iterations

wall clock advances

moving retention cutoff = T1
where T1 > T0

cleanup runs before sweep completes
```

After fix:

```text
no projection cycle in [T0, T1)
is deleted by normal cleanup

source_count == projection_count

Site does not diverge from this race
```

---

# 52. Exact retention boundary test

Create source/projection cycles at:

```text
T0 - epsilon
T0
T0 + epsilon
T1 - epsilon
T1
T1 + epsilon
```

While sweep active:

```text
T0 - epsilon
→ eligible for cleanup

T0
T0 + epsilon
T1 - epsilon
T1
T1 + epsilon
→ retained
```

After sweep completes and normal moving cutoff applies:

```text
normal retention behavior resumes
```

---

# 53. Diverged cleanup test

Given:

```text
Site status=diverged
```

normal cleanup:

```text
must delete zero rows for that Site
```

and must not clear divergence.

Other healthy Sites remain eligible for normal cleanup.

---

# 54. Repair cleanup isolation test

During:

```text
explicit rebuilding/repair
```

normal retention cleanup must not independently delete Site rows.

Repair owns the derived-data mutation lifecycle.

---

# 55. Multi-Site isolation test

Given:

```text
Site A = diverged
Site B = healthy
```

required:

```text
worker process remains alive

Site A:
Historical product unhealthy
normal cleanup blocked
normal consistency maintenance blocked

Site B:
maintenance continues
normal cleanup continues
product may remain healthy
```

No process-wide false failure or process-wide automatic repair.

---

# 56. Divergence latch test

For:

```text
source_identity
deep_fingerprint
ready_source_identity
```

required:

```text
status remains diverged
until explicit repair
```

Worker iteration must not silently clear it.

Read-only diagnostics may run but may not restore health.

---

# 57. Source/storage failure test

Temporary source/storage execution failure must not be reclassified as a consistency divergence unless an actual consistency proof fails.

Required distinction:

```text
execution unavailable
!=
identity diverged
```

---

# 58. Product health test

Required exact operational case:

```text
worker PID alive
systemd active
writer lock held
Site status=diverged
```

must produce:

```text
PROCESS=UP
PRODUCT=UNHEALTHY
SITE_HEALTH=diverged
```

This is a P0 acceptance invariant.

---

# 59. Reconcile-stuck health test

Given active sweep with no progress beyond the accepted progress-age threshold:

```text
projection_reconcile_stuck
```

must become observable.

No automatic proof reset.

---

# 60. Telemetry delivery test

For each critical event class, acceptance is end-to-end:

```text
worker emits event
→ systemd journal receives it
→ Alloy forwards it
→ Loki query sees it
→ Grafana can consume it
```

A unit-test logger capture alone is not production observability acceptance.

---

# 61. Deploy/restart acceptance

Operational test must prove:

```text
artifact A processes running

deploy artifact B

no artifact-A long-running Python process
continues executing through the artifact replacement

after deployment:
captive-portal reports B
traffic-projection reports B
```

The filesystem SHA alone is insufficient.

---

# 62. Recovery acceptance

From a controlled diverged Projection fixture:

```text
authoritative Observation complete
derived Projection missing data
```

run canonical repair under fixed code.

Required:

```text
derived Site rebuilt
source/projection identity match
deep audit PASS
status=healthy
backlog=0
normal incremental maintenance resumes
Historical Traffic read PASS
projection_recovered emitted
```

---

# 63. Regression architecture

Owner + Tech Lead acceptance must include at minimum:

```text
Historical Network Traffic
Period Statistics
Peak
Traffic by AP
AP Traffic Share
Traffic Evidence
```

and verify no regression in:

```text
Current Network Throughput
Online Guests Traffic
Completed Guest Session Traffic
Observation acquisition
```

Coder does not own official full acceptance under the project's current workflow.

---

# 64. Product-health acceptance before incident closure

Incident cannot be marked closed if Historical Traffic happens to render but operational product-health remains unable to distinguish:

```text
process up
product unhealthy
```

Observability hardening is part of the permanent P0 solution, not optional follow-up polish.

---

# 65. Deployment-lifecycle acceptance before incident closure

Incident closure also requires the deployment procedure to prevent stale worker code across artifact replacement.

A repaired DB with the old deployment contract is not a complete permanent solution.

---

# 66. Rollback strategy — before repair

If the candidate fixed artifact fails acceptance before production repair:

```text
do not repair
do not clear diverged
keep Observation untouched
keep Projection incident state preserved
```

Production Historical Traffic remains intentionally degraded until a corrected artifact is available.

---

# 67. Rollback strategy — fixed artifact deployment failure

Do not restart the known-vulnerable Projection writer merely to restore process liveness.

If a broader application rollback is required, the Projection service must either:

```text
remain stopped
```

or run an artifact that still contains the accepted retention/reconcile safety fix.

Permanent:

```text
rollback must not reintroduce the confirmed P0 race
```

---

# 68. Rollback strategy — repair failure

If repair fails:

```text
do not manually mark healthy
do not alter Observation
do not serve inconsistent Projection
```

Keep:

```text
rebuilding/diverged/unavailable
```

as proved by state.

Use the pre-repair consistent Projection backup for forensic rollback only if Owner + Tech Lead explicitly choose it.

Restoring a divergent backup does not constitute product recovery.

---

# 69. Non-goals

This incident TASK does NOT:

```text
change Historical Traffic formulas
change Traffic business meaning
change Observation schema
change retained history duration
rewrite Admin Traffic UI
introduce UI fallback for failed Historical data
move Projection writer into Flask
weaken consistency proof
make divergence auto-heal
create a second Projection writer
create a new derived DB
redesign Traffic Section
```

---

# 70. Explicit forbidden recovery shortcuts

Forbidden:

```text
manual INSERT of two missing cycles
manual status=healthy
manual clear last_error_category
delete authoritative Observation evidence
reduce source comparison window to make counts match
disable identity/deep-audit guard
serve partial projection as healthy
repair before fixed code is approved
```

---

# 71. Architecture relation to PR #110

The incident DRAFT treats PR #110 as:

```text
current repository/deployed artifact context
```

but not as the Projection root cause.

No rollback of Device List Context / Web UI is justified by current evidence solely to address this Projection incident.

If future evidence proves interaction, return to architecture review.

---

# 72. Open question 1 — deploy downtime policy

Recommended P0 contract is:

```text
stop artifact-owned long-running processes
before mutable checkout replacement
```

This may create a short controlled Admin/Portal downtime during deployment.

Owner + Tech Lead should confirm:

```text
ACCEPT short controlled maintenance downtime
for artifact-coherent deploy
```

or request a separate immutable-release-directory architecture.

This question does not block the retention-race architecture itself.

---

# 73. Open question 2 — alert destination

Architecture freezes:

```text
journal → Alloy → Loki → Grafana
```

and the event/health contract.

Owner + Tech Lead still need to choose the operational notification destination/severity routing, for example:

```text
Grafana alert only
email
messaging integration
other NOC path
```

This is operations policy, not Projection semantic design.

---

# 74. Open question 3 — direct operator health surface

The durable source for product health is:

```text
Projection state + canonical health classifier
```

and the required operational route is telemetry/Grafana.

Owner + Tech Lead may additionally request a dedicated operator CLI/API health surface in the implementation round.

It is not required to solve the P0 consistency race and must not delay the core fix unless operational policy requires it.

---

# 75. Architecture verdict

```text
TASK =
TASK-TRAFFIC-PROJECTION-LIFECYCLE-CONSISTENCY-01

PRIORITY =
P0

ROOT CAUSE =
RETENTION CLEANUP / FROZEN RECONCILE WINDOW RACE

ROOT-CAUSE CONFIDENCE =
VERY HIGH / SUFFICIENT FOR FIX

AUTHORITATIVE SOURCE =
Observation

PROJECTION =
derived / rebuildable

RETENTION SOLUTION =
per-Site cleanup fence

ACTIVE SWEEP FENCE =
effective cutoff =
min(current retention cutoff, reconcile_sweep_from_utc)

DIVERGED CLEANUP =
BLOCKED

REPAIR/REBUILD CLEANUP =
BLOCKED

DIVERGENCE =
FAIL-CLOSED
LATCHED
MANUAL OWNER-AUTHORIZED REPAIR

AUTO REBUILD FROM DIVERGED =
NO

PROCESS ON ONE SITE DIVERGENCE =
REMAIN ALIVE

PROCESS HEALTH != PRODUCT HEALTH =
PERMANENT

PRODUCT HEALTH =
healthy only when accepted Projection read health is healthy

TELEMETRY =
direct product-health + critical transition events

JOURNAL DELIVERY =
MANDATORY

SYSTEMD TOPOLOGY =
separate captive-portal.service
+
traffic-projection.service

DEPLOY CONTRACT =
all artifact-owned long-running processes
must be quiesced/restarted around mutable artifact replacement

RECOVERY PRIMITIVE =
canonical repair-site

MANUAL MISSING-CYCLE INSERT =
FORBIDDEN

BLIND DIVERGED RESET =
FORBIDDEN

OBSERVATION MUTATION =
FORBIDDEN

PROJECTION SCHEMA CHANGE =
NOT REQUIRED BY ARCHITECTURE

HISTORICAL BUSINESS SEMANTICS CHANGE =
NO

PRODUCTION REPAIR =
HOLD

IMPLEMENTATION =
NOT AUTHORIZED

CODER =
HOLD
```

---

# 76. Current incident gate

Until Owner + Tech Lead approve architecture and a fixed implementation is accepted:

```text
HISTORICAL_TRAFFIC_PRODUCTION = DEGRADED
TRAFFIC_PROJECTION_SITE = DIVERGED
OBSERVATION_SOURCE = INTACT
PROJECTION_DB_INTEGRITY = PASS
WORKER_PROCESS = ACTIVE
PROCESS_HEALTH = UP
PRODUCT_HEALTH = FAIL

REPAIR = HOLD
REBUILD = HOLD
MANUAL STATUS RESET = FORBIDDEN

KB FINAL CLOSURE FOR PR #110 = HOLD
```

---

# 77. Next workflow

```text
Architect DRAFT
        ↓
Owner + Tech Lead architecture review
        ↓
Architecture FINAL
        ↓
Tech Lead fresh repository rebind
        ↓
Architect + Tech Lead implementation-ready specification
        ↓
Owner implementation authorization
        ↓
Coder writes code
        ↓
narrow implementation tests only
        ↓
Coder handoff
        ↓
Owner + Tech Lead
full regression / race / capacity /
observability / deploy / recovery acceptance
        ↓
controlled production repair
        ↓
incident closure
```

This DRAFT does not authorize production repair or implementation.
