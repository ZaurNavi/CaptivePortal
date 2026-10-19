# ARCHITECTURE FINAL — TASK-TRAFFIC-PROJECTION-LIFECYCLE-CONSISTENCY-01

**Project:** CaptivPortal  
**Priority:** `P0 / PRODUCTION INCIDENT`  
**Area:** Historical Traffic / Traffic Projection / lifecycle / operational health  
**Architecture lineage:** DRAFT-R1 → DRAFT-R2 → Tech Lead final precision review  
**Status:** `FINAL — ARCHITECT + TECH LEAD REVIEW INCORPORATED`  
**Architecture verdict:** `PASS`  
**Implementation authorization:** `NOT GRANTED`  
**Coder authorization:** `NOT GRANTED`  
**Coder:** `HOLD`  
**Production repair:** `HOLD`  
**Projection rebuild/repair:** `HOLD`  
**Manual diverged reset:** `FORBIDDEN`  
**Authoritative Observation mutation:** `FORBIDDEN`  
**KB final closure for PR #110:** `HOLD`  
**Prepared:** 2026-09-10

---

# 0. Final architectural decision

The production incident is classified as:

```text
ROOT_CAUSE =
RETENTION CLEANUP / FROZEN RECONCILE WINDOW RACE

CONFIDENCE =
VERY HIGH / SUFFICIENT FOR P0 PERMANENT FIX
```

The permanent architecture is frozen as:

```text
Observation
=
authoritative Historical Traffic evidence

Traffic Projection
=
derived / rebuildable read model

Consistency fix
=
per-Site / per-Projection-version durable cleanup fence

Active frozen reconcile fence
=
effective_cleanup_cutoff =
min(
    normal_retention_cutoff,
    reconcile_sweep_from_utc
)

Existing delete_before() terminal/timestamp predicate
=
UNCHANGED

Divergence
=
fail-closed + latched

Normal cleanup while diverged
=
BLOCKED

Normal cleanup while explicit repair_active
=
BLOCKED

One diverged Site
=
worker remains running
other Sites continue

Historical read
=
accepted only when canonical computed Site health == healthy

Product health authority
=
existing canonical Projection health classifier

Process health
!=
Product health

Reconcile stuck
=
cursor-specific progress,
not generic incremental progress

Telemetry
=
canonical traffic_projection_* events
+
immediate state transition events
+
product-health heartbeat
maximum interval <= 60 seconds

Logging acceptance
=
event + safe machine fields survive
journal → Alloy → Loki → Grafana

Loaded artifact identity
=
captured once at process startup
immutable for process lifetime

Mutable checkout deployment
=
all artifact-owned long-running processes quiesced
before artifact mutation

Current incident recovery
=
FIX FIRST
→ forensic manifest + consistent Projection backup
→ coherent fixed artifact
→ one canonical repair-site entry
→ normal worker continues durable repair
→ full new proof
```

No change to Historical Traffic formulas or business semantics is authorized.

---

# 1. Repository baseline

Architecture FINAL is bound to:

```text
main =
ff39fe888c53361a7c65a034eaddb0ce92cc4a12

tree =
f6f1068a579c1f1c6f1debeae2e6a1e0da4823b8
```

This is the current merged PR #110 state.

Current evidence does not support attributing the Projection incident to Device List / UI work.

Canonical statement:

```text
PR_110_DIRECT_PROJECTION_REGRESSION =
NO EVIDENCE
```

A fresh repository rebind is still mandatory before the implementation-ready TASK.

---

# 2. Production incident scope

Working Traffic products:

```text
Current Network Throughput
Online Guests Traffic
Completed Guest Session Traffic
```

Unavailable Historical Projection-backed products:

```text
Network Traffic History
Period Statistics
Peak Load
Traffic by AP
AP Traffic Share
```

Common failure boundary:

```text
HistoricalTrafficReadService
        ↓
TrafficProjectionReadService
        ↓
active Traffic Projection
```

This is not a presentation-layer incident.

---

# 3. Confirmed process/storage state

Production Projection worker:

```text
traffic-projection.service = enabled
traffic-projection.service = active
PID alive
NRestarts = 0
writer lock owned
```

Projection storage:

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

stored status =
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

Failed frozen proof:

```text
reconcile_sweep_from_utc =
2026-08-27T08:26:05.244Z

reconcile_sweep_source_head_utc =
2026-09-10T08:26:05.244Z
```

Identity comparison:

```text
SOURCE_COUNT = 34340
PROJECTION_COUNT = 34338
COUNT_DELTA = 2

SOURCE_ONLY_COUNT = 2
PROJECTION_ONLY_COUNT = 0
```

Authoritative source-only cycles:

```text
72dbc45a-97ff-43c9-80fd-ef9a9b41907c
started 2026-08-27T08:26:28.388Z

34e7cd85-f890-4227-9433-12c65129af5a
started 2026-08-27T08:27:02.854Z
```

Both are valid complete successful Observation evidence.

---

# 5. Root-cause topology

Canonical failure sequence:

```text
full reconcile begins
        ↓
lower retained-window boundary T0 is frozen durably
        ↓
sweep spans multiple worker iterations
        ↓
wall clock advances
        ↓
normal cleanup derives moving cutoff T1
where T1 > T0
        ↓
cleanup is allowed to mutate Projection data
without reconcile-window protection
        ↓
Projection loses rows still inside frozen proof window
        ↓
authoritative source still compares from T0
        ↓
source_count != projection_count
        ↓
source_identity
        ↓
Site diverged
        ↓
Historical Projection reads fail closed
```

The permanent fix protects the proof window rather than weakening the identity proof.

---

# 6. Observation authority

Permanent:

```text
observations.sqlite3
=
authoritative source of Historical Traffic evidence
```

Projection:

```text
derived
rebuildable
non-authoritative
```

Forbidden repair technique:

```text
mutate/delete Observation
to make Projection match
```

---

# 7. Proof-window integrity invariant

A missing derived Projection row is evidence of Projection/source identity mismatch only if the comparison is performed over one coherent protected proof window.

Permanent:

```text
cleanup MUST NOT invalidate
an active frozen reconcile proof window
```

No Device Online/Offline terminology is used in Projection consistency semantics.

---

# 8. Existing delete semantics remain authoritative

The P0 fix changes only:

```text
maximum cleanup boundary
```

It does NOT replace the existing repository row-eligibility predicate.

Existing `delete_before()` terminal/timestamp eligibility remains unchanged.

Conceptually:

```text
effective cleanup cutoff
        ↓
existing delete_before() eligibility predicate
        ↓
actual row deletion
```

Do not simplify this to:

```text
source_started_at < cutoff
→ definitely delete
```

---

# 9. Normal retention cutoff

Canonical:

```text
normal_cutoff =
now - retention_days
```

The configured retention duration remains unchanged.

---

# 10. Active frozen reconcile cleanup fence

If:

```text
reconcile_sweep_started_at IS NOT NULL
AND
reconcile_sweep_from_utc = T0
```

then:

```text
effective_cleanup_cutoff =
min(
    normal_cutoff,
    T0
)
```

This is per:

```text
Projection version
+
Site
```

No process-global fence.

---

# 11. Cleanup boundary meaning

If a row's lifecycle is wholly before `T0`:

```text
the row is no longer protected
by the active reconcile fence
```

but the repository's existing normal delete eligibility still decides whether deletion is allowed.

A row whose relevant terminal lifecycle crosses the protected boundary remains subject to existing deletion protections.

Permanent:

```text
FENCE =
MAXIMUM BOUNDARY

DELETE PREDICATE =
EXISTING REPOSITORY SEMANTICS
```

---

# 12. Cleanup state must be read durably per Site/version

For every Site/version cleanup operation:

```text
1. read current durable Site/version state;

2. determine current lifecycle:
   - diverged
   - explicit repair_active
   - active frozen reconcile
   - ordinary

3. derive effective cutoff;

4. invoke existing delete_before eligibility.
```

Forbidden:

```text
compute all Site fences once
cache them
later mutate using stale decisions
```

Fence authority is:

```text
current durable Projection state
```

not an in-memory value from an earlier worker iteration.

The existing single-writer boundary remains the mutation-ordering authority.

---

# 13. Cleanup while active normal reconcile

For a normal active frozen reconcile:

```text
cleanup may continue
```

but only using the protected:

```text
effective_cleanup_cutoff
```

This permits safe cleanup of sufficiently old rows without crossing the frozen proof window.

---

# 14. Cleanup while diverged

For exact Site/version:

```text
canonical Site health lineage = diverged
```

normal retention cleanup is:

```text
BLOCKED
```

Reason:

```text
after a consistency failure,
normal retention must stop changing
forensic/recovery evidence
until controlled repair.
```

This may temporarily exceed configured retention and is accepted during the incident.

---

# 15. Exact meaning of `repair_active`

`repair_active` means:

```text
the explicit durable active-version Site repair lineage
```

It does NOT mean:

```text
every row with status=rebuilding
```

and MUST NOT cause unrelated target/build versions to disable cleanup merely because they are rebuilding.

Current repository lineage is based on the active Projection version plus Site repair state, currently represented by:

```text
active Projection version
+
Site status=rebuilding
+
(
    last_error_category=repair_delete
    OR
    durable repair/reconcile sweep state
)
```

Before implementation-ready TASK, Tech Lead fresh rebind MUST freeze the exact existing predicate.

If repository source contains a more precise existing durable repair predicate, that exact predicate becomes authoritative.

Coder does not invent or reinterpret `repair_active`.

---

# 16. Cleanup while explicit repair_active

For:

```text
repair_active=true
```

normal retention cleanup for that Site/version is:

```text
BLOCKED
```

Repair owns the derived-state mutation lifecycle.

Do not interleave:

```text
normal retention mutation
+
repair deletion
+
repair reconcile
```

as independent destructive actors for one Site/version.

---

# 17. Target/build versions are not generic repair

A target Projection version may legitimately be:

```text
building
rebuilding
catching up
```

without being in explicit active-version repair lineage.

Permanent:

```text
target-version build
!=
repair_active
```

No cleanup block may be inferred from the word `rebuilding` alone.

---

# 18. Restart safety of cleanup fence

The active proof boundary is durable:

```text
reconcile_sweep_started_at
reconcile_sweep_from_utc
```

Therefore a worker restart must not remove protection.

On every cleanup operation after restart:

```text
re-read durable Site/version state
→ derive fence again
```

No in-memory-only protection.

---

# 19. Startup cleanup hazard

Current worker initialization has:

```text
_last_cleanup = 0
```

and cleanup scheduling is based on monotonic time.

Therefore after a process restart:

```text
cleanup MAY be due
during the first worker lifecycle iteration
```

depending on host monotonic uptime.

Architecture MUST NOT assume:

```text
restart grants 24-hour cleanup grace
```

Permanent startup invariant:

```text
restart/startup is safe
even if cleanup becomes due
immediately after first active maintenance quantum
```

---

# 20. Single writer remains authoritative

No second Projection writer is introduced.

Permanent:

```text
one writer lock
one Projection mutation ownership boundary
```

The P0 fence must work inside this existing single-writer architecture.

---

# 21. Divergence remains fail-closed

Consistency divergence categories include:

```text
source_identity
ready_source_identity
deep_fingerprint
future explicit proof mismatch categories
```

Behavior:

```text
Historical Site read unavailable
divergence latched
normal Site cleanup blocked
normal worker does not silently repair
critical telemetry
Owner-authorized recovery required
```

---

# 22. Divergence remains latched

Normal worker maintenance does not clear:

```text
diverged
```

Read-only diagnostics may gather evidence.

Forbidden automatic behavior:

```text
clear diverged
insert missing rows
delete/rebuild Site automatically
serve as healthy without new proof
```

---

# 23. Temporary execution failures are not divergence by default

Examples:

```text
source temporarily unavailable
Projection storage unavailable
SQLite busy/locked
I/O execution failure
```

These are not automatically:

```text
source_identity
```

They retain retry/stale/unavailable behavior.

Permanent:

```text
execution unavailable
!=
identity diverged
```

---

# 24. Canonical repair entry

Existing:

```text
repair-site
```

is the canonical recovery entry point.

It is explicitly bounded/durable.

One command invocation is NOT defined as complete recovery.

---

# 25. Exact repair lifecycle

Canonical:

```text
worker stopped
writer lock released
        ↓
Owner-authorized repair-site invoked once
under fixed artifact
        ↓
previous Site proof invalidated
        ↓
Site enters durable repair_delete/rebuilding lineage
        ↓
bounded deletion/rebuild quantum executes
        ↓
repair state remains durable if incomplete
        ↓
normal fixed worker starts
        ↓
worker detects durable repair_active lineage
        ↓
worker continues bounded repair/reconcile
across subsequent iterations
        ↓
new proof completes
        ↓
canonical computed health becomes healthy
```

Do not require operators to repeatedly invoke repair-site unless exact implementation rebind proves the current durable resume contract differs.

---

# 26. `repair-site` completion is not recovery

Permanent:

```text
repair-site process exits successfully
!=
Historical Traffic recovered
```

Recovery is proof-based.

---

# 27. Recovery proof

Required:

```text
explicit repair lineage exists

new full reconcile completed

source/projection retained-window identity matches

SOURCE_ONLY_COUNT=0
PROJECTION_ONLY_COUNT=0

deep audit PASS

canonical computed Site health=healthy

backlog=0

head/freshness satisfy healthy classifier

Historical Projection read accepts Site

five affected Admin Historical products PASS
```

Only then is the P0 Site recovery valid.

---

# 28. Historical read health contract remains unchanged

Current accepted read state remains exactly:

```text
canonical computed Site health == healthy
```

This TASK does NOT broaden accepted read states.

Therefore:

```text
catching_up
rebuilding
stale
diverged
unavailable
```

remain unavailable for accepted Historical Projection delivery.

---

# 29. Canonical Site health authority

Telemetry, product-health monitoring, alerting and read-health interpretation MUST use the existing canonical Projection health classifier.

The authority is NOT merely:

```text
traffic_projection_site_state.status
```

Canonical health incorporates existing persisted/runtime inputs including:

```text
stored Site state
current source availability
source/projection head lag
full reconcile age
incremental progress age
version/build state
```

No second health algorithm is authorized.

---

# 30. Computed-health transition requirement

A computed transition such as:

```text
healthy → stale
```

must become observable even if no SQL row literally changes:

```text
stored status='healthy'
```

Therefore transition monitoring compares:

```text
previous canonical computed health
vs
current canonical computed health
```

not merely database status-field mutations.

---

# 31. Process health is separate

Process health answers:

> Is the worker process alive and successfully owning its runtime/writer boundary?

Conceptual:

```text
PROCESS_UP
PROCESS_DOWN
```

This does not certify Historical Traffic consistency.

---

# 32. Site product health

For a Site:

```text
PRODUCT_HEALTHY
iff
active Projection version valid
AND
canonical computed Site health == healthy
AND
Historical Projection read boundary available
```

Otherwise:

```text
PRODUCT_UNHEALTHY
```

---

# 33. Multi-Site isolation

If:

```text
Site A = diverged
Site B = healthy
```

required:

```text
worker process remains running

Site A read = unavailable
Site A cleanup = blocked

Site B maintenance = continues
Site B cleanup = continues
Site B read = available
```

One Site incident must not stop unrelated healthy Site reads.

---

# 34. Aggregate health is operations-only

Operations may report:

```text
Historical Traffic fleet aggregate = unhealthy
```

if any required production Site is unhealthy.

But:

```text
aggregate unhealthy
MUST NOT
gate healthy Site-scoped Historical reads
```

Aggregate health is:

```text
alerting / operations state
```

only.

---

# 35. Reconcile-specific progress identity

Active reconcile:

```text
reconcile_sweep_started_at IS NOT NULL
```

Reconcile progress identity:

```text
(
  reconcile_cursor_started_at,
  reconcile_cursor_cycle_id
)
```

This tuple is the canonical evidence that the reconcile proof itself advances.

---

# 36. Generic incremental progress cannot prove reconcile progress

Permanent:

```text
last_incremental_progress_at
MUST NOT
be the sole reconcile-stuck signal
```

It may advance because of unrelated Projection maintenance.

Therefore:

```text
progress signal
=
reconcile cursor identity

progress threshold
=
accepted time budget
```

These are separate concepts.

---

# 37. Reconcile-stuck default architecture

Default non-schema architecture:

```text
periodic canonical product-health monitoring
observes durable reconcile cursor tuple
```

If active sweep cursor remains unchanged across the accepted progress window:

```text
traffic_projection_reconcile_stuck
```

A cursor change resets the stuck timer.

---

# 38. Reconcile-stuck threshold

Architecture may reuse the current accepted maintenance progress time budget:

```text
INCREMENTAL_PROGRESS_MAX_AGE_SECONDS
```

current repository value:

```text
60 seconds
```

only as threshold duration.

It does not change the progress signal.

---

# 39. Reconcile progress after worker restart

The persisted reconcile cursor survives restart.

Runtime repeated-observation timer may restart at process startup.

This may delay stuck detection by at most one accepted progress interval after worker restart.

That is acceptable for the default non-schema architecture.

---

# 40. Persisted-state/schema gate

For the retention fix:

```text
RETENTION-FENCE SCHEMA CHANGE =
NOT REQUIRED
```

For additional durable health/progress state:

```text
NEW PERSISTED STATE =
NOT AUTHORIZED BY DEFAULT
```

During Tech Lead fresh repository rebind, BEFORE issuing implementation-ready TASK:

```text
if existing durable reconcile cursor state is sufficient
→ freeze non-schema contract

if not sufficient
→ STOP before Coder
→ return exact missing persisted-state requirement
→ narrow Architect review
→ freeze exact schema change
→ only then issue FINAL TASK
```

Coder never receives:

```text
add a field if you think necessary
```

---

# 41. Canonical telemetry namespace

Permanent prefix:

```text
traffic_projection_
```

Required events:

```text
traffic_projection_site_diverged
traffic_projection_source_identity_failed
traffic_projection_stale
traffic_projection_reconcile_stuck
traffic_projection_worker_source_unavailable
traffic_projection_worker_storage_unavailable
traffic_projection_recovered
traffic_projection_worker_started
traffic_projection_worker_stopped
traffic_projection_product_health
```

No parallel new:

```text
projection_*
```

namespace.

---

# 42. Product-health authority for telemetry

`traffic_projection_product_health` and state transition events MUST be driven from the canonical computed Projection health classifier result.

Forbidden:

```text
second independently-coded health interpretation
based only on stored status
```

---

# 43. Immediate transition events

Critical computed state changes emit immediate events.

Examples:

```text
canonical health healthy → stale
→ traffic_projection_stale

consistency proof → diverged
→ traffic_projection_site_diverged

explicit repair lineage completes new proof
and canonical health returns healthy
→ traffic_projection_recovered
```

Do not wait for next heartbeat to expose a critical transition.

---

# 44. Source identity event

At retained-window identity mismatch emit:

```text
traffic_projection_source_identity_failed
```

Safe machine fields include:

```text
projection_version
site_id
error_category=source_identity
source_count
projection_count
count_delta
reconcile_sweep_from_utc
reconcile_sweep_source_head_utc
```

No raw Observation rows.

A resulting Site divergence additionally emits:

```text
traffic_projection_site_diverged
```

---

# 45. Source/storage events

Separate:

```text
traffic_projection_worker_source_unavailable
traffic_projection_worker_storage_unavailable
```

These are execution failures, not consistency divergence by themselves.

---

# 46. Product-health heartbeat

Required event:

```text
traffic_projection_product_health
```

Canonical timing:

```text
maximum heartbeat interval = 60 seconds
```

Therefore:

```text
state transition
→ immediate event

PLUS

periodic product-health heartbeat
at interval <= 60 seconds
```

Bounded per Site/version.

---

# 47. Worker started event

`traffic_projection_worker_started` may be emitted only after all of:

```text
startup loaded-artifact identity captured

configuration accepted

writer lock successfully acquired

required worker initialization completed
```

Do not emit a successful start event before writer ownership exists.

---

# 48. Worker stopped event

`traffic_projection_worker_stopped` is:

```text
BEST-EFFORT GRACEFUL STOP EVENT
```

It is not an authoritative detector for every process death.

For:

```text
SIGKILL
process crash
host failure
kernel/OOM kill
```

the worker may be physically unable to emit it.

---

# 49. Abnormal process-loss detection

Abnormal process loss is detected through:

```text
systemd process state
and/or
missing bounded heartbeat
```

Architecture acceptance MUST NOT require an impossible graceful-stop event from an abruptly killed process.

---

# 50. Recovered event exact meaning

`traffic_projection_recovered` is NOT emitted for every ordinary transition ending in healthy.

Canonical meaning:

```text
a previously incident/unhealthy explicit repair lineage
has completed the required new proof
and returned to accepted healthy delivery
```

For the current P0 divergence path it requires:

```text
explicit repair lineage
+
new full reconcile
+
identity proof
+
deep audit
+
canonical computed health=healthy
```

Ordinary:

```text
startup catching_up → healthy
```

must not emit `traffic_projection_recovered`.

It remains visible through normal product-health events.

---

# 51. Structured logging wire contract

It is insufficient that:

```text
Python LogRecord contains extra fields
```

Required:

```text
event name
+
all approved safe machine fields
```

must survive into the actual journal record.

Accepted wire form:

```text
structured JSON
```

or deterministic bounded:

```text
key=value
```

or equivalent machine-readable format.

---

# 52. Logging architecture compatibility

Prefer reuse/extension of CaptivPortal canonical logging infrastructure.

Do not create a separate unrelated logging architecture only for Projection.

But reuse is acceptable only if required structured fields survive into journal output.

---

# 53. End-to-end telemetry acceptance

Accepted only if:

```text
Projection worker event
        ↓
systemd journal:
event + required fields
        ↓
Alloy
        ↓
Loki query can identify:
event
site_id
projection_version
site/product status
error_category
        ↓
Grafana can panel/alert
```

In-process logging tests alone are insufficient for production acceptance.

---

# 54. Alert destination — frozen P0 scope

Required P0 operational path:

```text
journal
→ Alloy
→ Loki
→ Grafana
```

Required:

```text
Grafana-visible/queryable unhealthy state
```

External notification routing is:

```text
OUT OF SCOPE
```

for this P0 unless Owner separately expands scope.

Therefore Coder does not choose:

```text
email
messenger
NOC integration
```

---

# 55. systemd topology

Keep separate:

```text
captive-portal.service
traffic-projection.service
```

Do not embed the Projection writer in Flask/Web.

---

# 56. Artifact-owned service discovery gate

Before implementation/deploy acceptance, production inventory MUST discover every long-running process executing code directly from the mutable CaptivPortal artifact.

Known minimum:

```text
captive-portal.service
traffic-projection.service
```

This list is not assumed permanently exhaustive.

---

# 57. Deployment manifest

The verified service inventory becomes authoritative:

```text
ARTIFACT_OWNED_LONG_RUNNING_SERVICES
```

It controls:

```text
quiesce
stop
artifact mutation
start
startup artifact identity validation
rollback
```

Embedded workers inside `captive-portal.service` remain owned by that process and are not separate units merely because they are internal worker objects.

---

# 58. Startup-captured loaded artifact identity

Each artifact-owned long-running process MUST capture loaded artifact identity exactly once at startup.

Permanent:

```text
LOADED_ARTIFACT_IDENTITY
=
startup captured
+
immutable for process lifetime
```

Minimum:

```text
artifact SHA
artifact tree/release identity
service name
process start timestamp
```

---

# 59. Dynamic checkout identity is forbidden as loaded-code proof

Later:

```text
git rev-parse HEAD
```

against the mutable checkout cannot be used as the process's loaded-artifact identity.

Failure model:

```text
process loads artifact A
checkout becomes B
dynamic git query returns B
process still executes A
```

Deploy acceptance compares:

```text
EXPECTED_DEPLOYED_ARTIFACT
=
STARTUP_CAPTURED_LOADED_ARTIFACT
```

---

# 60. Mutable-checkout deploy invariant

Current production architecture uses one mutable CaptivPortal checkout.

Permanent:

```text
NO checkout/artifact mutation
while any artifact-owned long-running process
continues executing code loaded from that checkout
```

---

# 61. Controlled maintenance downtime — frozen decision

For this P0 and the current mutable-checkout architecture:

```text
SHORT CONTROLLED MAINTENANCE DOWNTIME =
ACCEPTED
```

Correctness and artifact coherence take priority over avoiding a short maintenance interruption.

Zero-downtime immutable-release directories are future architecture work.

Coder does not choose this policy.

---

# 62. Coherent deployment lifecycle

Canonical:

```text
1. verify approved target artifact

2. discover/verify artifact-owned service manifest

3. quiesce Projection/background writer

4. stop all remaining artifact-owned long-running processes

5. prove no old manifest process remains

6. mutate/install exact approved artifact

7. verify target SHA/tree on filesystem

8. start artifact-owned services in approved order

9. each process reports startup-captured loaded identity

10. require expected artifact
    =
    startup-captured loaded artifact

11. verify base application readiness

12. verify Projection process health

13. verify Projection product health

14. run post-deploy gates
```

---

# 63. Artifact-coherent rollback

All running services using one mutable checkout must execute one coherent deployed artifact.

Forbidden:

```text
Web loaded artifact A
Projection loaded artifact B
```

while both rely on one mutable checkout.

---

# 64. Rollback target predating P0 fix

If the broader rollback target predates the accepted P0 Projection fix:

```text
captive-portal may be coherently rolled back
under approved rollback procedure
```

but:

```text
traffic-projection.service MUST remain STOPPED
```

rather than restart known-vulnerable Projection code.

Historical Traffic may remain unavailable.

That is safer than knowingly reintroducing the P0 race.

---

# 65. Current incident recovery ordering

Permanent:

```text
FIX FIRST
REPAIR SECOND
```

Do not repair production before the cleanup/reconcile lifecycle fix is implemented and accepted.

---

# 66. Forensic incident manifest before repair

Before first repair mutation preserve an immutable compact incident manifest containing at least:

```text
production Git SHA
production tree/release identity

Projection DB checksum
Projection DB size

Projection version

Site state
status
last_error_category
projection_revision
source/projection heads
backlog

reconcile_sweep_started_at
reconcile_sweep_from_utc
reconcile_sweep_source_head_utc
reconcile_sweep_source_head_cycle_id

SOURCE_COUNT
PROJECTION_COUNT
SOURCE_ONLY_COUNT
PROJECTION_ONLY_COUNT

source-only cycle IDs

bounded source metadata necessary
to reproduce the incident classification

repair start timestamp
```

No unnecessary raw Observation payload.

This is forensic evidence, not a new source of truth.

---

# 67. Consistent Projection backup before repair

Also take a SQLite-consistent derived Projection backup.

Required:

```text
writer stopped/quiesced
writer lock released
consistent backup/snapshot
```

Do not rely on blind file copy with active WAL/writer activity.

Observation remains untouched.

---

# 68. Current production recovery sequence

## Phase A — fixed artifact

```text
Architecture FINAL
→ implementation-ready TASK
→ Owner authorization
→ implementation
→ Owner + Tech Lead P0 acceptance
→ approve fixed artifact
```

## Phase B — preserve incident

```text
stop Projection writer
verify lock released
capture incident manifest
take consistent Projection backup
```

## Phase C — coherent fixed deploy

```text
inventory artifact-owned services
quiesce all manifest services
deploy exact fixed artifact
verify SHA/tree
start required base service
verify startup-loaded artifact identity
```

## Phase D — repair entry

```text
Projection worker stopped
writer lock free
invoke Owner-authorized repair-site ONCE
under fixed artifact
```

## Phase E — worker continuation

```text
start fixed Projection worker

worker detects durable repair_active lineage

worker continues bounded repair/reconcile
until proof completes
```

## Phase F — proof

```text
full reconcile PASS
identity match
deep audit PASS
canonical health=healthy
backlog=0
Historical read PASS
five affected Admin Historical products PASS
traffic_projection_recovered visible
```

Only then incident closure.

---

# 69. Manual repair shortcuts remain forbidden

Forbidden:

```text
manual INSERT of two missing cycles
manual status=healthy
manual clear last_error_category
alter/delete authoritative Observation
reduce comparison window to force equality
disable identity proof
disable deep audit
serve inconsistent Projection as healthy
```

---

# 70. Retention-fence regression — actual worker lifecycle

Mandatory test reproduces real scheduling topology:

```text
worker iteration N:
active frozen reconcile exists / advances

same normal worker lifecycle:
cleanup becomes due

cleanup executes while durable
reconcile_sweep_from_utc remains active

worker iteration N+1:
reconcile continues and completes
```

Required:

```text
cleanup uses protected effective cutoff
existing row eligibility unchanged
protected rows survive
source/projection identity matches
Site does not diverge
```

---

# 71. Immediate-cleanup-after-restart regression

Mandatory startup topology:

```text
durable unfinished reconcile exists
        ↓
worker stops
        ↓
worker restarts
        ↓
_last_cleanup initialized
        ↓
cleanup is immediately due
        ↓
first active maintenance quantum occurs
        ↓
cleanup runs
```

Required:

```text
cleanup re-reads durable Site/version state
persisted reconcile fence is honored
protected rows survive
identity proof remains coherent
```

No 24-hour post-restart grace assumption.

---

# 72. Restart-during-sweep regression

Mandatory:

```text
multi-iteration reconcile begins
reconcile_sweep_* durable

worker restarts

cleanup executes after restart

reconcile resumes
```

Required:

```text
same frozen lower-bound protection
no in-memory fence dependency
proof completes coherently
```

---

# 73. Terminal-boundary cleanup regression

Test boundary values around:

```text
T0 - epsilon
T0
T0 + epsilon
T1 - epsilon
T1
T1 + epsilon
```

with:

```text
T0 = frozen reconcile lower bound
T1 = moving normal cutoff
T1 > T0
```

Exercise combinations of:

```text
source_started_at
source_finished_at
source_abandoned_at
terminal/non-terminal lifecycle
```

Required:

```text
fence controls only maximum cutoff

existing delete_before terminal/timestamp predicate
still controls actual deletion
```

---

# 74. Direct incident-topology regression fixture

Permanent regression fixture modeled on production timing:

```text
frozen lower bound:
2026-08-27T08:26:05.244Z

rows immediately after boundary:
08:26:28.388Z
08:27:02.854Z

moving normal cutoff advances past both
before frozen sweep completes
```

After fix:

```text
both derived rows remain protected
until proof completes

SOURCE_ONLY_COUNT=0
PROJECTION_ONLY_COUNT=0

Site remains non-diverged
```

Production UUIDs are not required in fixture data.

---

# 75. Diverged cleanup regression

Given:

```text
Site A diverged
Site B healthy
```

normal cleanup:

```text
Site A = zero normal cleanup mutation
Site B = normal/fenced cleanup as applicable
```

No process-wide cleanup freeze.

---

# 76. Explicit repair cleanup regression

When exact:

```text
repair_active=true
```

normal retention cleanup does not mutate that Site/version.

Also test a normal target/build version with:

```text
status=rebuilding
but repair_active=false
```

to prove it is NOT incorrectly classified as repair.

---

# 77. Canonical-health transition regression

Test canonical health changes caused by:

```text
source availability
head lag
reconcile age
incremental progress age
version/build state
```

even when stored Site `status` does not change.

Required:

```text
product-health event reflects canonical computed health
```

No stored-status-only health monitor.

---

# 78. Healthy-only read regression

For computed Site health:

```text
healthy
→ Historical read allowed

catching_up
rebuilding
stale
diverged
unavailable
→ Historical read unavailable
```

This TASK must not broaden read semantics.

---

# 79. Reconcile-stuck regression

Active sweep with unchanged:

```text
(reconcile_cursor_started_at, reconcile_cursor_cycle_id)
```

across threshold:

```text
traffic_projection_reconcile_stuck
```

must be emitted even if:

```text
last_incremental_progress_at
```

changes.

Cursor advancement resets stuck detection.

---

# 80. Worker-start regression

Prove `traffic_projection_worker_started` is absent before:

```text
writer lock acquisition
required initialization completion
```

and emitted only after valid ownership/startup.

---

# 81. Abrupt worker-loss regression

Terminate worker without graceful shutdown.

Acceptance MUST NOT require:

```text
traffic_projection_worker_stopped
```

Instead operational loss must become visible through:

```text
systemd state
and/or
heartbeat timeout
```

---

# 82. Recovered-event regression

Scenario:

```text
startup catching_up → healthy
```

must NOT emit:

```text
traffic_projection_recovered
```

Scenario:

```text
latched incident
→ explicit repair lineage
→ new full proof
→ canonical healthy
```

MUST emit:

```text
traffic_projection_recovered
```

---

# 83. Product-health heartbeat regression

Required:

```text
maximum interval <= 60 seconds
```

per Site/version.

Critical transitions still emit immediately.

---

# 84. Structured logging regression

Verify journal wire record contains:

```text
event name
+
approved safe machine fields
```

not merely a generic textual event name with lost `extra` fields.

---

# 85. End-to-end observability gate

Owner + Tech Lead production acceptance:

```text
worker
→ journal
→ Alloy
→ Loki
→ Grafana
```

must support identification/filtering by at least:

```text
event
site_id
projection_version
canonical site/product health
error_category
```

---

# 86. Startup artifact identity regression

Scenario:

```text
process starts on artifact A
captures A

filesystem later moves to B
```

Required:

```text
running process keeps reporting loaded artifact A
```

It must not dynamically become B.

---

# 87. Artifact-owned service discovery regression

Production inventory before deployment must verify all long-running processes executing code from mutable CaptivPortal artifact.

The resulting manifest becomes deploy/rollback authority.

Service-topology changes require re-inventory.

---

# 88. Deploy coherence regression

Starting:

```text
all manifest services loaded artifact A
```

Deploy B:

```text
all manifest services stopped/quiesced
before artifact mutation
```

After start:

```text
every manifest service startup identity = B
```

No mixed loaded artifact set.

---

# 89. Repair lifecycle regression

From a diverged Site:

```text
stop worker
free writer lock
invoke repair-site once
```

Required:

```text
durable repair lineage seeded/advanced
```

Then start normal worker:

```text
worker resumes durable bounded repair
without repeated manual repair-site calls
```

Recovery only after new proof.

---

# 90. Multi-Site read isolation regression

Given:

```text
Site A computed health=diverged
Site B computed health=healthy
```

required:

```text
aggregate operations health may be unhealthy

Site A Historical read unavailable
Site B Historical read available
```

No aggregate global read gate.

---

# 91. Schema policy

Frozen:

```text
RETENTION-FENCE SCHEMA CHANGE =
NOT REQUIRED

NEW PERSISTED STATE =
NOT AUTHORIZED BY DEFAULT
```

Tech Lead must settle the durable reconcile-progress representation before Coder receives implementation-ready TASK.

If existing durable state is insufficient:

```text
STOP BEFORE CODER
→ narrow Architecture review
→ exact persisted-state contract
```

---

# 92. Operational decisions frozen before Coder

## Maintenance downtime

```text
ACCEPTED:
short controlled downtime
for coherent mutable-checkout deployment
```

## Alert destination

```text
REQUIRED:
journal → Alloy → Loki → Grafana
Grafana-visible operational unhealthy state

OUT OF SCOPE:
external email/messenger/NOC routing
```

## Reconcile progress persistence

```text
default:
existing durable reconcile cursor tuple
+
runtime repeated observation

must be verified by Tech Lead fresh rebind
before FINAL implementation TASK
```

No unresolved choice reaches Coder.

---

# 93. Explicit non-goals

This P0 TASK does not:

```text
change Historical Traffic formulas
change Historical Traffic business meaning
change Observation schema by default
change retention_days duration
rewrite Admin Traffic UI
introduce degraded Historical read fallback
embed Projection writer in Flask
weaken consistency proof
broaden read states
auto-heal divergence
create a second writer
create a new Projection DB
introduce zero-downtime immutable releases
add external notification integrations
```

---

# 94. Stop conditions before implementation-ready TASK

Tech Lead MUST STOP before Coder if fresh rebind shows any of:

```text
repair_active exact durable lineage differs materially
from current architecture assumption

cleanup fence cannot be implemented
without changing delete eligibility semantics

required fence needs new schema

reconcile-stuck invariant cannot be represented
safely from existing durable fields

canonical health classifier cannot provide required authority
without semantic redesign

structured logging cannot preserve required fields
without a new logging architecture

startup artifact identity cannot be made immutable
within current deployment boundary

artifact-owned process inventory reveals
an unhandled long-running mutable-checkout consumer

fix requires broadening Historical read states

fix requires Observation mutation

fix requires new writer/concurrency model
```

Return to Architect for narrow review.

Coder must not choose a workaround.

---

# 95. Architecture FINAL summary

```text
TASK =
TASK-TRAFFIC-PROJECTION-LIFECYCLE-CONSISTENCY-01

STATUS =
ARCHITECTURE FINAL
PASS

REPOSITORY BASELINE =
ff39fe888c53361a7c65a034eaddb0ce92cc4a12

TREE =
f6f1068a579c1f1c6f1debeae2e6a1e0da4823b8

ROOT CAUSE =
RETENTION CLEANUP / FROZEN RECONCILE WINDOW RACE

CONSISTENCY FIX =
PER-SITE / PER-VERSION DURABLE CLEANUP FENCE

NORMAL CUTOFF =
now - retention_days

ACTIVE SWEEP FENCE =
min(normal_cutoff, reconcile_sweep_from_utc)

DELETE PREDICATE =
EXISTING repository terminal/timestamp semantics
UNCHANGED

CLEANUP FENCE SOURCE =
CURRENT DURABLE Site/version state
READ PER CLEANUP OPERATION

CACHED STALE FENCE =
FORBIDDEN

STARTUP CLEANUP IMMEDIATELY DUE =
MUST BE SAFE

DIVERGED =
FAIL-CLOSED + LATCHED

DIVERGED NORMAL CLEANUP =
BLOCKED

REPAIR ACTIVE =
EXPLICIT DURABLE ACTIVE-VERSION REPAIR LINEAGE

GENERIC rebuilding =
NOT repair_active

EXPLICIT REPAIR NORMAL CLEANUP =
BLOCKED

REPAIR ENTRY =
repair-site once

REPAIR CONTINUATION =
normal worker resumes durable bounded repair

repair-site COMPLETION =
NOT recovery

RECOVERY =
explicit repair lineage
+
new full proof
+
canonical health=healthy

HISTORICAL READ =
canonical computed Site health MUST equal healthy

PRODUCT HEALTH AUTHORITY =
existing canonical Projection health classifier

STORED status ALONE =
NOT health authority

AGGREGATE HEALTH =
OPERATIONS ONLY
NOT GLOBAL READ GATE

PROCESS HEALTH != PRODUCT HEALTH =
MANDATORY

RECONCILE PROGRESS =
reconcile cursor tuple

last_incremental_progress_at AS SOLE PROOF =
FORBIDDEN

SCHEMA =
retention fence requires none
new persisted state not authorized by default

TELEMETRY PREFIX =
traffic_projection_

STATE TRANSITIONS =
IMMEDIATE

HEARTBEAT =
maximum interval <=60 seconds

worker_started =
only after artifact capture
+ config
+ writer lock
+ initialization

worker_stopped =
best-effort graceful event only

ABNORMAL PROCESS LOSS =
systemd / heartbeat

recovered =
incident/repair lineage only
after new proof

LOGGING =
machine fields survive journal wire record

OBSERVABILITY =
journal → Alloy → Loki → Grafana

EXTERNAL ALERT ROUTING =
OUT OF P0 SCOPE

LOADED ARTIFACT IDENTITY =
captured once at startup
immutable per process

DYNAMIC checkout HEAD AS LOADED IDENTITY =
FORBIDDEN

ARTIFACT-OWNED SERVICE DISCOVERY =
MANDATORY

MUTABLE DEPLOY =
all artifact-owned long-running processes
quiesced before artifact mutation

CONTROLLED MAINTENANCE DOWNTIME =
ACCEPTED

MIXED LOADED ARTIFACTS =
FORBIDDEN

ROLLBACK WITHOUT P0 FIX =
Projection worker remains STOPPED

CURRENT INCIDENT =
FIX FIRST
→ forensic manifest
→ consistent Projection backup
→ coherent fixed deploy
→ repair-site once
→ worker-continued repair
→ full re-proof

OBSERVATION MUTATION =
FORBIDDEN

MANUAL ROW INSERT =
FORBIDDEN

MANUAL HEALTH RESET =
FORBIDDEN

IMPLEMENTATION AUTHORIZATION =
NOT GRANTED

CODER AUTHORIZATION =
NOT GRANTED

PRODUCTION REPAIR =
HOLD
```

---

# 96. Current production incident gate

Until fixed implementation is accepted and Owner separately authorizes repair:

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

IMPLEMENTATION = NOT AUTHORIZED

CODER = HOLD

KB FINAL CLOSURE FOR PR #110 = HOLD
```

---

# 97. Workflow after Architecture FINAL

```text
Architecture FINAL
        ↓
Tech Lead fresh repository rebind
        ↓
Tech Lead verifies:
repair_active exact predicate
durable reconcile-progress sufficiency
cleanup repository binding
canonical health integration
logging/output infrastructure
artifact-owned service inventory
        ↓
if no architecture contradiction:
Architect + Tech Lead implementation-ready FINAL TASK
        ↓
Owner review/implementation authorization
        ↓
Coder receives only exact implementation TASK
        ↓
Coder writes code
        ↓
narrow implementation tests
        ↓
Coder handoff
        ↓
Owner + Tech Lead official:
race
restart/startup
cleanup boundary
canonical health
telemetry
artifact identity
deploy/rollback
repair
Historical read
multi-Site
regression
acceptance
        ↓
controlled production repair
        ↓
new healthy proof
        ↓
incident closure
```

This Architecture FINAL does not authorize implementation or production repair.
