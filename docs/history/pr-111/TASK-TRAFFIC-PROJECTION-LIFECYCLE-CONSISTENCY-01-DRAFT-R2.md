# DRAFT-R2 — TASK-TRAFFIC-PROJECTION-LIFECYCLE-CONSISTENCY-01

**Project:** CaptivPortal  
**Priority:** `P0 / PRODUCTION INCIDENT`  
**Area:** Historical Traffic / Traffic Projection / lifecycle / operational health  
**Architecture source:** DRAFT-R1 + Tech Lead required corrections  
**Status:** `DRAFT-R2 — FOR FINAL OWNER + TECH LEAD ARCHITECTURE REVIEW`  
**Architecture direction:** `ACCEPTED / HARDENED`  
**Architecture FINAL:** `NOT YET ISSUED`  
**Implementation authorization:** `NOT GRANTED`  
**Coder:** `HOLD`  
**Production repair:** `HOLD`  
**Projection rebuild/repair:** `HOLD`  
**Manual diverged reset:** `FORBIDDEN`  
**Authoritative Observation mutation:** `FORBIDDEN`  
**KB final closure for PR #110:** `HOLD`  
**Prepared:** 2026-09-10

---

# 0. DRAFT-R2 executive decision

The production incident is architecturally classified as:

```text
ROOT_CAUSE_CLASS =
RETENTION CLEANUP / FROZEN RECONCILE WINDOW RACE

CONFIDENCE =
VERY HIGH / SUFFICIENT FOR P0 PERMANENT FIX
```

The accepted permanent architecture is:

```text
Observation
=
authoritative Historical Traffic source

Traffic Projection
=
derived / rebuildable read model

Retention fix
=
per-Site / per-Projection-version cleanup fence

Divergence
=
fail-closed + latched

Normal cleanup while diverged
=
blocked

Normal cleanup while explicit repair/rebuild
=
blocked

One Site diverged
=
worker remains running
other Sites continue

Process health
!=
Projection product health

Historical Projection reads
=
remain accepted only when Site health == healthy

Observability
=
immediate state-transition events
+
periodic product-health heartbeat
maximum interval = 60 seconds
+
end-to-end journal / Alloy / Loki / Grafana proof

Projection worker
=
separate systemd unit

Mutable artifact deployment
=
all artifact-owned long-running processes quiesced
before artifact mutation

Loaded artifact identity
=
captured once at process startup
immutable for process lifetime

Current incident recovery
=
FIX FIRST
then forensic capture + backup
then canonical repair-site entry
then worker-continued durable repair
then full re-proof
```

No Historical Traffic business-semantic or calculation change is authorized.

---

# 1. Repository baseline

Fresh repository baseline for DRAFT-R2:

```text
main =
ff39fe888c53361a7c65a034eaddb0ce92cc4a12

tree =
f6f1068a579c1f1c6f1debeae2e6a1e0da4823b8
```

This is the merged PR #110 state.

No new evidence links PR #110 Device List / Admin UI work to the Projection root cause.

Current architecture therefore keeps:

```text
PR_110_DIRECT_PROJECTION_REGRESSION =
NO EVIDENCE
```

---

# 2. Production incident statement

The Historical Traffic branch is unavailable while non-Projection Traffic products continue to work.

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

This is a common failure of the accepted Projection-backed Historical read path, not a UI/CSS failure.

---

# 3. Confirmed process and storage state

Production diagnostics establish:

```text
traffic-projection.service = enabled
traffic-projection.service = active
worker PID alive
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
WORKER_PROCESS_DEAD = NO
PROJECTION_DB_CORRUPTION = NO EVIDENCE
NORMAL_BACKLOG = NO
HEAD_CATCHUP_FAILURE = NO
CONSISTENCY_PROOF_FAILURE = YES
```

---

# 4. Frozen reconcile evidence

Failed reconcile proof was frozen at:

```text
reconcile_sweep_from_utc =
2026-08-27T08:26:05.244Z

reconcile_sweep_source_head_utc =
2026-09-10T08:26:05.244Z

reconcile_sweep_source_head_cycle_id =
db9b7983-356b-47ce-8748-34a50d86842e
```

Read-only identity comparison inside that exact proof window:

```text
SOURCE_COUNT = 34340
PROJECTION_COUNT = 34338
COUNT_DELTA = 2

SOURCE_ONLY_COUNT = 2
PROJECTION_ONLY_COUNT = 0
```

Missing derived cycles:

```text
72dbc45a-97ff-43c9-80fd-ef9a9b41907c
started = 2026-08-27T08:26:28.388Z

34e7cd85-f890-4227-9433-12c65129af5a
started = 2026-08-27T08:27:02.854Z
```

Both remain valid complete authoritative Observation cycles.

---

# 5. Retention-boundary forensic topology

Around the frozen lower boundary:

```text
08:25:22  projection=NO   outside frozen proof window
08:25:55  projection=NO   outside frozen proof window

08:26:28  projection=NO   inside frozen proof window
08:27:02  projection=NO   inside frozen proof window

08:27:36  projection=YES  first surviving Projection cycle
```

Frozen lower bound:

```text
08:26:05.244Z
```

The exact two-row in-window Projection deficit matches:

```text
SOURCE_COUNT - PROJECTION_COUNT = 2
```

The absence of a literal DELETE audit record prevents absolute event reconstruction, but the evidence is sufficiently strong to define the P0 permanent consistency fix.

---

# 6. Current reconcile model

Current full reconcile:

```text
freeze source head
freeze lower retained-window boundary
persist reconcile_sweep_*
persist cursor
advance across multiple worker iterations
```

Completion proof compares:

```text
authoritative source count
vs
Projection count
```

over the same frozen:

```text
[from_utc, frozen source head]
```

Count mismatch causes:

```text
status=diverged
last_error_category=source_identity
```

This fail-closed identity guard remains correct and is not weakened by this TASK.

---

# 7. Current cleanup model

Normal cleanup independently derives:

```text
normal_cutoff =
current wall clock - retention_days
```

and invokes the existing repository:

```text
delete_before(site_id, cutoff)
```

The P0 defect is not the existence of normal retention cleanup.

The P0 defect is:

```text
normal cleanup boundary can advance through
an active frozen reconcile proof window.
```

---

# 8. Architectural invariants

## 8.1 Observation authority

```text
observations.sqlite3
=
canonical authoritative evidence
```

Projection is derived and rebuildable.

Observation must not be altered to make Projection identity appear valid.

## 8.2 Active proof protection

```text
Normal retention cleanup MUST NOT delete
Projection rows protected by an active frozen reconcile proof.
```

## 8.3 Proof-window integrity invariant

A missing derived row is evidence of Projection/source identity mismatch only if the comparison was performed over one coherent protected proof window.

Cleanup must not invalidate that proof window while the proof is active.

Do not import Device Online/Offline terminology into this domain.

## 8.4 Divergence fail-closed

```text
diverged
!=
partial
!=
acceptable historical source
```

## 8.5 Divergence latch

Normal worker maintenance cannot silently clear divergence.

## 8.6 Site-scoped availability

One unhealthy Site must not globally disable healthy Site reads.

## 8.7 Process/product separation

```text
systemd active
!=
Historical Traffic healthy
```

## 8.8 Artifact coherence

One mutable CaptivPortal checkout cannot safely back multiple simultaneously running loaded code versions.

---

# 9. Chosen retention/reconcile consistency model

Architecture chooses:

```text
PER-SITE
+
PER-PROJECTION-VERSION
CLEANUP FENCE
```

For each Site/version:

```text
normal_cutoff =
now - retention_days
```

If no active frozen reconcile:

```text
effective_cutoff =
normal_cutoff
```

If:

```text
reconcile_sweep_started_at IS NOT NULL
AND
reconcile_sweep_from_utc = T0
```

then:

```text
effective_cutoff =
min(
    normal_cutoff,
    T0
)
```

The effective cutoff is the maximum boundary that normal cleanup may use.

---

# 10. Important cleanup semantic preservation

The P0 fix changes:

```text
the maximum cleanup boundary
```

and does NOT change:

```text
the existing historical-row delete eligibility semantics
```

Current repository `delete_before()` has an existing terminal-state/timestamp safety predicate.

Therefore architecture MUST preserve the repository's existing eligibility logic unchanged.

Conceptually:

```text
effective_cutoff
        ↓
existing delete_before eligibility rules
        ↓
actual deletion
```

Do not replace the current repository eligibility predicate with a simplified:

```text
source_started_at < cutoff
```

rule.

---

# 11. Exact meaning of the cleanup fence

With:

```text
active frozen lower bound = T0
moving normal cutoff = T1
T1 > T0
```

then a row whose lifecycle is wholly before `T0`:

```text
is no longer protected by the reconcile fence
```

but deletion still depends on the existing normal `delete_before()` predicate, including relevant source terminal timestamps/state.

A row that is not wholly before the protected boundary remains protected even if its start time is older.

Permanent:

```text
FENCE DECIDES MAXIMUM PROTECTED BOUNDARY

EXISTING delete_before() SEMANTICS
DECIDE ACTUAL ROW ELIGIBILITY
```

---

# 12. Active-sweep cleanup rule

During an active normal reconcile sweep:

```text
cleanup MAY continue
```

but only through:

```text
effective_cutoff =
min(normal_cutoff, reconcile_sweep_from_utc)
```

This prevents temporary over-retention from growing more than necessary while still protecting the full active proof window.

---

# 13. Diverged cleanup rule

For:

```text
Site status=diverged
```

normal retention cleanup for that exact Site/version is:

```text
BLOCKED
```

Reason:

```text
after consistency failure,
normal cleanup must not continue mutating
the forensic/recovery evidence set.
```

This may temporarily exceed nominal retention.

That is accepted incident behavior.

---

# 14. Explicit repair/rebuild cleanup rule

During the explicit durable Site repair lifecycle:

```text
status=rebuilding
+
repair state active
```

normal retention cleanup for that Site/version is blocked.

Repair owns the destructive derived-state lifecycle.

Do not run independent normal retention mutation against the same Site while repair deletion/rebuild is active.

---

# 15. Healthy/no-sweep cleanup rule

For a Site/version with no active reconcile or repair/divergence restriction:

```text
effective_cutoff =
normal_cutoff
```

and the existing repository deletion predicate applies unchanged.

The P0 fix does not change the normal retained history duration or terminal eligibility.

---

# 16. Why cleanup fence is accepted over alternatives

The per-Site/per-version fence:

```text
preserves active proof identity
keeps normal cleanup running for safely old rows
requires no new generation model
does not require a schema change for the retention fix
is restart-safe because the boundary is already durable
```

Architecture therefore rejects, for this P0 fix:

```text
global cleanup pause for all Sites
new projection-generation/snapshot domain
new cleanup database
new second writer
```

---

# 17. Restart safety of retention fence

Fence authority is persisted:

```text
reconcile_sweep_started_at
reconcile_sweep_from_utc
```

Therefore:

```text
worker process restart
MUST NOT
remove cleanup protection from an unfinished sweep.
```

After worker restart, normal cleanup must re-read the durable frozen boundary before deleting Site/version data.

No in-memory-only protection is acceptable.

---

# 18. Divergence taxonomy

## Consistency divergence

Examples:

```text
source_identity
ready_source_identity
deep_fingerprint
future explicit proof mismatch categories
```

Behavior:

```text
Site status=diverged
Historical read unavailable for that Site
normal destructive cleanup blocked
normal Site maintenance does not clear status
critical transition telemetry
Owner-authorized repair required
```

## Temporary execution failure

Examples:

```text
source unavailable
Projection storage unavailable
SQLite busy/locked
I/O/read/write execution failure
```

These do not automatically mean source/projection identity divergence.

They retain temporary retry/stale/unavailable behavior.

---

# 19. Automatic recovery decision

No automatic mutation-based recovery from:

```text
diverged
```

is authorized.

Allowed:

```text
read-only diagnostic/re-proof evidence
health classification
telemetry
healthy-Site maintenance
```

Forbidden:

```text
automatic clear diverged
automatic Site delete/rebuild
automatic missing-row insertion
serve Projection as healthy without proof
```

Reason:

`source_identity` may represent a real software, source, semantic-contract, or storage consistency defect beyond the currently confirmed retention race.

---

# 20. Canonical recovery primitive

Existing:

```text
repair-site
```

is accepted as the canonical **repair entry point**.

It is NOT defined as:

```text
one command invocation
=
entire Site rebuilt and recovered
```

The existing repair contract is bounded and durable.

---

# 21. Exact repair-site lifecycle

Canonical lifecycle:

```text
Owner-authorized repair-site entry
        ↓
invalidate prior Site proof
        ↓
Site enters rebuilding / repair_delete lifecycle
        ↓
delete derived Site cycles in bounded chunks
        ↓
repair state remains durable
        ↓
normal fixed worker detects repair state
        ↓
worker continues bounded repair/delete/reconcile quanta
across subsequent iterations as required
        ↓
full proof completes
        ↓
Site becomes healthy
```

Do not require operators to repeatedly invoke `repair-site` manually unless a later exact source rebind proves that the current implementation cannot resume the seeded repair state.

---

# 22. `repair-site` command success is not product recovery

Permanent:

```text
repair-site command returned
!=
Site recovered
```

Recovery is proof-based.

The Site is recovered only after:

```text
new full reconcile proof completes
deep audit succeeds
identity matches
health becomes healthy
Historical reads succeed
```

---

# 23. `rebuild-range` is not diverged recovery

A narrow range rebuild is not the recovery primitive for a latched diverged Site.

Forbidden current-incident shortcut:

```text
rebuild only the two known missing cycles
then clear divergence
```

That would not prove the rest of the retained identity window.

---

# 24. Recovery completion contract

Required recovery proof:

```text
status=healthy

last_error_category cleared

source/projection retained-window identity matches

SOURCE_ONLY_COUNT=0
PROJECTION_ONLY_COUNT=0

new full reconcile completed

deep audit PASS

backlog=0

head/freshness satisfy healthy classifier

Historical Projection read accepts Site

all five affected Admin Historical products PASS

traffic_projection_recovered emitted
and observable end-to-end
```

Only after this may production incident closure proceed.

---

# 25. Worker behavior after one Site divergence

Architecture keeps worker process alive.

For one diverged Site:

```text
that Site remains fail-closed
normal cleanup blocked
normal mutation-based recovery blocked
```

But worker may continue:

```text
other configured Sites
other allowed Projection version/build responsibilities
product-health emission
```

Do not crash/restart-loop the worker merely because one Site is latched diverged.

---

# 26. Multi-Site isolation

Example:

```text
Site A = diverged
Site B = healthy
```

Required:

```text
worker process = running

Site A Historical read = unavailable
Site B Historical read = available

Site A cleanup = blocked
Site B cleanup = normal

Site A product health = unhealthy
Site B product health = healthy
```

No aggregate health state may be used as a global read gate.

---

# 27. Process health

Process health answers only:

> Is the Projection worker process alive and functioning as a process/writer owner?

Conceptual machine result:

```text
PROCESS_UP
PROCESS_DOWN
```

Possible evidence:

```text
systemd state
PID
writer lock ownership
startup lifecycle signal
heartbeat delivery
```

It does not certify Projection consistency.

---

# 28. Site Projection health

Reuse the existing canonical Site health machine:

```text
healthy
catching_up
rebuilding
stale
diverged
unavailable
```

No parallel Site-health enum is introduced.

---

# 29. Historical Projection read acceptance

This TASK explicitly preserves the current read contract:

```text
Historical Projection delivery accepted
ONLY WHEN
Site Projection health == healthy
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

Any future relaxation requires a separate architecture decision.

---

# 30. Product health

For a Site-scoped Historical Traffic product:

```text
PRODUCT_HEALTHY
iff
active Projection version valid
AND
Site health == healthy
AND
Projection read boundary available
```

Otherwise:

```text
PRODUCT_UNHEALTHY
```

This is consistent with the existing Historical Projection read gate.

---

# 31. Aggregate operational health

Operations may expose:

```text
Historical Traffic aggregate/fleet health = unhealthy
```

if any required configured production Site is unhealthy.

But:

```text
AGGREGATE UNHEALTHY
MUST NOT
make healthy Site B's Site-scoped Historical read unavailable
because Site A failed.
```

Aggregate health is only:

```text
operations / alerting state
```

not a read-availability gate.

---

# 32. Reconcile progress identity

An active reconcile is:

```text
reconcile_sweep_started_at IS NOT NULL
```

The reconcile-specific progress identity is:

```text
(
  reconcile_cursor_started_at,
  reconcile_cursor_cycle_id
)
```

This cursor/proof position is the canonical signal of actual reconcile advancement.

---

# 33. `last_incremental_progress_at` restriction

Permanent:

```text
last_incremental_progress_at
MUST NOT
be the sole proof that an active reconcile is progressing.
```

It can advance because of maintenance activity outside the exact reconcile cursor progression.

Therefore:

```text
progress signal
!=
progress threshold
```

The accepted time budget may reuse an existing threshold family, but progress must be measured from reconcile-specific evidence.

---

# 34. Reconcile-stuck detection model

DRAFT-R2 chooses as the default non-schema architecture:

```text
structured periodic health observation
of the persisted reconcile cursor tuple
```

For each active Site/version, worker product-health monitoring tracks:

```text
reconcile_sweep_started_at
reconcile_cursor_started_at
reconcile_cursor_cycle_id
```

If the reconcile cursor/proof identity remains unchanged across the accepted progress window:

```text
traffic_projection_reconcile_stuck
```

is emitted.

A cursor change resets the reconcile-progress timer.

---

# 35. Reconcile-stuck process restart semantics

The persisted cursor survives process restart.

The runtime stuck observer may restart its local elapsed timer after process startup.

Therefore worst-case re-detection may be delayed by one accepted progress interval after restart, but the active sweep and its cursor remain visible immediately.

This is accepted for the default DRAFT-R2 observability design.

If Tech Lead rebind proves that durable across-restart elapsed reconcile-progress age is a required P0 invariant and cannot be represented unambiguously using current durable state:

```text
STOP
→ return exact persisted-state requirement
→ narrow Architecture review
```

No convenience schema migration is authorized.

---

# 36. Reconcile-stuck threshold

The threshold may reuse the current accepted maintenance progress window:

```text
INCREMENTAL_PROGRESS_MAX_AGE_SECONDS
```

current repository value:

```text
60 seconds
```

but only as a time budget.

The signal remains:

```text
reconcile cursor/proof advancement
```

not `last_incremental_progress_at`.

---

# 37. Schema policy

For the retention fence itself:

```text
RETENTION-FENCE SCHEMA CHANGE =
NOT REQUIRED
```

For all new persisted state:

```text
NEW PERSISTED STATE =
NOT AUTHORIZED BY DEFAULT
```

If implementation rebind proves that a required P0 invariant cannot be represented safely and unambiguously using current durable fields:

```text
Tech Lead MUST STOP
→ document exact missing persisted state
→ return for narrow Architecture review
before implementation
```

No migration merely for convenience.

---

# 38. Canonical telemetry namespace

Permanent event namespace:

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

Do not introduce parallel:

```text
projection_*
```

events.

Existing compatible `traffic_projection_*` events may remain where useful.

---

# 39. State-transition event semantics

State transition events are immediate.

Examples:

```text
healthy → diverged
→ traffic_projection_site_diverged immediately

healthy/catching → stale
→ traffic_projection_stale immediately

repair/rebuild proof → healthy
→ traffic_projection_recovered immediately
```

Repeated scan loops must not be the only observable signal.

---

# 40. Source identity failure telemetry

At exact retained-window identity mismatch emit:

```text
traffic_projection_source_identity_failed
```

Required safe concepts:

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

The Site transition into diverged must additionally produce:

```text
traffic_projection_site_diverged
```

---

# 41. Source/storage availability telemetry

Do not collapse temporary execution failures into one generic consistency event.

Use:

```text
traffic_projection_worker_source_unavailable
traffic_projection_worker_storage_unavailable
```

with bounded safe category fields.

These events do not themselves mark a Site as `diverged`.

---

# 42. Product-health heartbeat

Canonical heartbeat:

```text
traffic_projection_product_health
```

Maximum heartbeat interval:

```text
60 seconds
```

Required operational pattern:

```text
state transition
→ immediate event

PLUS

periodic product-health heartbeat
at interval <= 60 seconds
```

This provides:

```text
fast incident visibility
+
proof that a healthy worker is still reporting
```

Heartbeat is bounded per:

```text
Site
Projection version
```

---

# 43. Product-health heartbeat fields

Approved concepts include:

```text
projection_version
site_id

process_up
product_status
site_health_status

projection_revision

source_head_utc
projection_head_utc
head_lag_seconds

reconcile_sweep_started_at
reconcile_cursor_started_at
reconcile_cursor_cycle_id

last_full_reconcile_completed_at
backlog_cycle_count

error_category

startup_captured_artifact_sha
startup_captured_artifact_tree_or_release
service_name
process_started_at
```

No raw source payloads.

---

# 44. Structured logging transport contract

It is insufficient that Python:

```text
logger.info(...)
```

received event fields in `extra`.

Required production acceptance is:

```text
event name
+
all approved machine fields
```

survive into the actual journal record.

Accepted representation may be:

```text
structured JSON
```

or deterministic bounded:

```text
key=value
```

or an equivalent machine-readable representation.

---

# 45. Logging architecture compatibility

Prefer reuse or extension of the project's canonical logging infrastructure.

Do not create a second unrelated logging system solely for Projection.

But canonical infrastructure is acceptable only if it preserves the required structured event fields in the emitted journal wire record.

---

# 46. End-to-end telemetry acceptance

Telemetry is accepted only when:

```text
Projection worker emits event
        ↓
systemd journal contains event + required fields
        ↓
Alloy ships meaningful record/fields
        ↓
Loki query can identify:
Site
Projection version
health/status
error category
        ↓
Grafana can panel/alert it
```

Unit-test logger capture alone is insufficient.

---

# 47. Telemetry safety

Never expose:

```text
raw Observation payload
raw AP/client source JSON
OAuth/token data
secrets
full SQL text
raw source DB contents
unbounded exception text
```

Only bounded safe fields/categories.

---

# 48. systemd topology

Keep separate:

```text
captive-portal.service
traffic-projection.service
```

Do not embed Projection writer into Flask/Web.

Reasons remain:

```text
single-writer ownership
fault isolation
independent restart
Web availability independent from writer
multi-Site maintenance isolation
```

---

# 49. Artifact-owned service discovery gate

Before implementation/deploy acceptance, production service inventory MUST determine all long-running processes that execute Python/code directly from the mutable CaptivPortal artifact.

Known minimum:

```text
captive-portal.service
traffic-projection.service
```

But this list is not permanently assumed complete.

The discovery gate must inspect the actual production service/process topology.

---

# 50. Deployment manifest authority

After inventory proof, establish an authoritative deployment manifest:

```text
ARTIFACT_OWNED_LONG_RUNNING_SERVICES
```

This manifest controls:

```text
quiesce
stop
artifact mutation
start
startup artifact identity verification
post-deploy readiness
```

Embedded internal worker objects inside:

```text
captive-portal.service
```

remain owned by that process and do not become separate units merely because code calls them workers.

---

# 51. Loaded artifact identity invariant

Each artifact-owned long-running process MUST capture its loaded artifact identity once at process startup.

Permanent:

```text
LOADED_ARTIFACT_IDENTITY
=
STARTUP-CAPTURED
+
IMMUTABLE FOR PROCESS LIFETIME
```

Never derive this health field dynamically from a mutable checkout after startup.

---

# 52. Minimum startup artifact identity

At minimum capture:

```text
artifact SHA
artifact tree/release identity
service name
process start timestamp
```

Exact capture mechanism may use:

```text
startup environment
immutable deployment manifest
bootstrap-provided identity
release metadata
```

and belongs to implementation design.

But later:

```text
git rev-parse HEAD
```

against mutable working directory is NOT accepted as loaded-code proof.

---

# 53. Why dynamic Git identity is forbidden

Failure model:

```text
process starts on artifact A
Python imports A

filesystem checkout becomes B

later git rev-parse HEAD reports B

process still executes loaded A code
```

This produces false confidence.

Therefore deploy acceptance compares:

```text
EXPECTED_DEPLOYED_ARTIFACT
=
STARTUP_CAPTURED_LOADED_ARTIFACT
```

for every artifact-owned long-running service.

---

# 54. Mutable-checkout deployment invariant

Under current mutable `/opt/CaptivePortal` production architecture:

```text
NO artifact mutation
while any artifact-owned long-running process
continues running code loaded from that checkout.
```

The deployment lifecycle must quiesce/stop all manifest services before changing the artifact.

---

# 55. Controlled deploy lifecycle

Canonical lifecycle:

```text
1. verify approved target artifact

2. discover/verify authoritative artifact-owned service manifest

3. quiesce Projection/background writer

4. stop remaining artifact-owned long-running processes

5. verify no manifest process from old artifact remains

6. mutate/install exact CaptivPortal artifact

7. verify filesystem target SHA/tree

8. start required services in controlled order

9. each service reports immutable startup-captured artifact identity

10. require:
    expected SHA/tree
    =
    startup-captured loaded identity

11. verify base readiness

12. verify Projection process health

13. verify Projection product health

14. run post-deploy gates
```

Exact service start order may be hardened in implementation/deploy design but cannot violate artifact coherence.

---

# 56. Current-incident recovery principle

Permanent:

```text
FIX FIRST
REPAIR SECOND
```

Do not repair production using the known vulnerable retention/reconcile lifecycle.

---

# 57. Forensic evidence manifest before repair

Before any repair mutation, create a compact immutable incident manifest.

Minimum fields:

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

frozen reconcile bounds:
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
to reproduce incident classification

repair start timestamp
```

No unnecessary raw Observation payloads.

This manifest is forensic evidence, not a second source of truth.

---

# 58. Consistent Projection backup before repair

Also preserve a consistent derived Projection backup before repair mutation.

Requirement:

```text
Projection writer quiesced/stopped
+
writer lock released
+
SQLite-consistent backup/snapshot
```

Do not rely on blind file copy while WAL/writer activity may be in flight.

The authoritative Observation store remains untouched.

---

# 59. Exact current-incident recovery sequence

## Phase A — fixed implementation acceptance

```text
1. Architecture FINAL.
2. Implementation-ready TASK.
3. Owner implementation authorization.
4. Implement P0 fix.
5. Owner + Tech Lead race/lifecycle/observability acceptance.
6. Approve exact fixed artifact.
```

No repair yet.

## Phase B — forensic preservation

```text
7. Stop/quiesce traffic-projection writer.
8. Verify exclusive writer lock released.
9. Capture immutable incident manifest.
10. Take consistent Projection backup.
```

## Phase C — coherent fixed-artifact deploy

```text
11. Apply artifact-owned service discovery/manifest.
12. Quiesce all artifact-owned long-running processes.
13. Deploy exact fixed artifact.
14. Verify filesystem SHA/tree.
15. Start required base service(s).
16. Verify startup-captured loaded artifact identity.
```

Keep repair under explicit Owner gate.

## Phase D — seed canonical repair

```text
17. Ensure normal Projection worker is stopped
    and writer lock is free.

18. Invoke Owner-authorized repair-site ONCE
    under the fixed artifact and exclusive writer lock.

19. repair-site seeds/advances the durable
    rebuilding/repair_delete lifecycle.
```

## Phase E — worker-continued durable repair

```text
20. Start fixed normal traffic-projection worker.

21. Worker detects durable repair state.

22. Worker continues bounded repair/delete/reconcile
    across normal iterations until proof completes.
```

Do not require repeated manual `repair-site` commands by default.

## Phase F — recovery proof

```text
23. New full reconcile PASS.
24. Source/projection identity match.
25. Deep audit PASS.
26. Site health=healthy.
27. backlog=0.
28. Healthy head/freshness.
29. Historical read PASS.
30. All affected Admin Historical panels PASS.
31. traffic_projection_recovered visible end-to-end.
```

Only then close incident.

---

# 60. Manual two-row repair remains forbidden

Do not manually insert the two missing cycles.

It would not establish:

```text
full retained-window identity
semantic fingerprint consistency
proper durable repair state
future race immunity
new health proof
```

---

# 61. Manual healthy reset remains forbidden

Do not edit:

```text
status=diverged
→ healthy
```

or clear:

```text
last_error_category
```

without proof.

Permanent:

```text
health follows proof
```

---

# 62. Historical read contract regression protection

The Projection read path continues to require:

```text
Site health == healthy
```

This incident TASK must not introduce fallback delivery from:

```text
catching_up
rebuilding
stale
diverged
unavailable
```

No UI masking.

---

# 63. P0 race test — actual worker lifecycle ordering

Mandatory regression must reproduce the real maintenance ordering, not only isolated method calls.

Required topology:

```text
worker iteration N:
active reconcile sweep exists
and advances

same normal worker lifecycle:
cleanup becomes due

cleanup runs
while durable reconcile_sweep_from_utc remains active

worker iteration N+1:
reconcile resumes
and completes
```

After fix:

```text
cleanup uses protected effective cutoff

no protected Projection row is removed

source/projection identity proof matches

Site remains non-diverged
```

---

# 64. P0 restart-during-sweep test

Required:

```text
worker begins multi-iteration reconcile

durable reconcile_sweep_* exists

worker process stops/restarts

cleanup becomes due after restart

reconcile resumes from durable state
```

Required result:

```text
cleanup reads persisted frozen lower boundary
effective fence remains active
protected rows survive
reconcile completes
identity proof matches
```

Protection cannot depend on pre-restart in-memory state.

---

# 65. Exact terminal-boundary cleanup tests

Boundary tests must cover both the fence and existing delete eligibility.

Test lifecycle timestamps around:

```text
T0 - epsilon
T0
T0 + epsilon

T1 - epsilon
T1
T1 + epsilon
```

where:

```text
T0 = frozen reconcile lower bound
T1 = moving normal retention cutoff
T1 > T0
```

Include relevant combinations of:

```text
source_started_at
source_finished_at
source_abandoned_at
terminal/non-terminal state
```

Expected:

```text
fence prevents delete_before from crossing T0

rows wholly before T0
are merely no longer protected by the reconcile fence

existing delete_before terminal eligibility
still decides whether they actually delete
```

No test may encode the false simplification:

```text
source_started_at < T0
→ definitely deleted
```

---

# 66. Direct production-incident topology fixture

Mandatory permanent regression fixture modeled on the incident:

```text
frozen lower bound:
2026-08-27T08:26:05.244Z

authoritative rows immediately after boundary:
08:26:28.388Z
08:27:02.854Z

moving cleanup cutoff advances past both
while sweep remains active
```

After fix:

```text
both Projection rows remain protected
until frozen proof completes

SOURCE_ONLY_COUNT=0
PROJECTION_ONLY_COUNT=0

Site does not diverge
```

Production UUIDs need not be copied into test fixtures.

The timing topology is the regression contract.

---

# 67. Diverged cleanup test

Given:

```text
Site A = diverged
Site B = healthy
```

normal cleanup:

```text
Site A deletes zero rows
Site B uses normal/fenced policy as applicable
```

No process-wide cleanup freeze.

---

# 68. Repair cleanup-isolation test

During explicit durable repair:

```text
normal cleanup does not independently mutate repaired Site/version
```

Worker repair operations alone own the derived-state mutation sequence.

---

# 69. Divergence latch test

For each consistency divergence category:

```text
source_identity
ready_source_identity
deep_fingerprint
```

normal worker maintenance must not silently clear divergence.

Only Owner-authorized canonical repair may establish a new healthy proof.

---

# 70. Reconcile-stuck test

An active reconcile with unchanged:

```text
(reconcile_cursor_started_at, reconcile_cursor_cycle_id)
```

across the accepted progress window must become observable as:

```text
traffic_projection_reconcile_stuck
```

Even if:

```text
last_incremental_progress_at
```

changes for unrelated maintenance.

Conversely:

```text
reconcile cursor advancement
```

must reset the stuck timer.

---

# 71. Process/product health test

Required exact case:

```text
systemd active
PID alive
writer lock held
Site status=diverged
```

must expose:

```text
PROCESS=UP
SITE_HEALTH=diverged
SITE_PRODUCT=UNHEALTHY
```

No false operational PASS.

---

# 72. Aggregate health / Site-read isolation test

Given:

```text
Site A = diverged
Site B = healthy
```

operations may report:

```text
aggregate Historical Traffic = unhealthy
```

but:

```text
Site B Historical read
MUST remain available
```

No global product-health read gate.

---

# 73. Telemetry namespace test

Critical events must use canonical names:

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

No new `projection_*` parallel event family.

---

# 74. Heartbeat timing test

Required:

```text
maximum heartbeat interval <= 60 seconds
```

and:

```text
critical state transition
→ immediate event
```

A transition must not wait for the next heartbeat.

---

# 75. Structured logging test

A test/acceptance step must prove:

```text
event name
+
required safe fields
```

reach the journal wire record.

It is not enough to inspect an in-process Python LogRecord.

---

# 76. End-to-end observability gate

Owner + Tech Lead acceptance:

```text
worker
→ journal
→ Alloy
→ Loki
→ Grafana
```

Must allow query/alert by at least:

```text
event
site_id
projection_version
site/product status
error_category
```

---

# 77. Startup artifact identity test

Test:

```text
process starts from artifact A
captures startup identity A

filesystem later changes to artifact B
```

Required:

```text
running process continues reporting loaded artifact=A
```

It must not dynamically report B.

This proves the health field describes loaded code identity, not current filesystem HEAD.

---

# 78. Deploy artifact-coherence test

Starting with artifact A:

```text
all artifact-owned services running A
```

Deploy B:

```text
all manifest long-running processes quiesced/stopped
before checkout mutation
```

After B start:

```text
each running artifact-owned service
startup-captured loaded artifact=B
```

No mixed loaded A/B process set.

---

# 79. Artifact-owned service discovery acceptance

Before production deploy acceptance, inventory must verify whether any additional process beyond:

```text
captive-portal.service
traffic-projection.service
```

executes code directly from the mutable CaptivPortal artifact.

The resulting manifest is recorded and used by deploy/rollback.

This check is repeated when service topology changes.

---

# 80. Repair lifecycle test

From a diverged fixture:

```text
worker stopped
writer lock released

invoke repair-site once
```

Required:

```text
durable repair state seeded
```

Then:

```text
start normal worker
```

Required:

```text
worker resumes bounded repair/reconcile
without repeated manual repair commands
```

Recovery is not declared until full proof completes.

---

# 81. Recovery proof test

After repair lifecycle:

```text
status=healthy
source/projection identity match
deep audit PASS
backlog=0
normal incremental maintenance resumes
Historical Projection read PASS
traffic_projection_recovered emitted
```

---

# 82. Failure mode matrix

## Active sweep + moving retention

Before:

```text
proof window could be invalidated
```

After:

```text
maximum cleanup cutoff fenced
existing row eligibility unchanged
```

## Diverged Site

```text
read fail-closed
cleanup blocked
worker alive
repair required
```

## Repairing Site

```text
normal cleanup blocked
repair owns mutation
```

## Temporary source failure

```text
source unavailable/stale path
not automatic divergence
```

## Temporary storage failure

```text
product unavailable
storage event
not automatic source identity mismatch
```

## Reconcile stuck

```text
detected from reconcile cursor identity
not incremental progress field
```

## Worker process down

```text
PROCESS_DOWN
systemd restart policy may apply
```

## Mutable artifact replaced under live process

```text
forbidden deployment state
```

---

# 83. Rollback — pre-repair candidate failure

If fixed candidate fails before production repair:

```text
do not repair
do not clear diverged
Observation remains untouched
preserve incident state
```

Historical Traffic remains intentionally degraded.

---

# 84. Rollback — coherent mutable-checkout invariant

All running services using the one mutable CaptivPortal checkout must execute one coherent deployed artifact.

Forbidden:

```text
Web process loaded old artifact
+
Projection worker loaded newer artifact

or reverse
```

while both point to one mutable checkout.

---

# 85. Rollback when target predates P0 fix

If broader application rollback target predates the accepted P0 Projection fix:

```text
captive-portal may be coherently rolled back
only through approved artifact-coherent rollback
```

But:

```text
traffic-projection.service
MUST remain STOPPED
```

rather than restart on the known-vulnerable Projection implementation.

Do not run mixed loaded versions from the same mutable checkout.

Historical Traffic may remain unavailable during this rollback state.

That is preferable to knowingly reintroducing the confirmed P0 race.

---

# 86. Immutable-release future

A future immutable release-directory architecture could bind separate services to separate immutable releases.

That is not the current production model and is out of scope for this incident fix.

Current mutable-checkout coherence remains mandatory.

---

# 87. Rollback — repair failure

If canonical repair fails:

```text
do not mark healthy
do not alter Observation
do not serve inconsistent Projection
```

Keep state as proved:

```text
rebuilding
diverged
or unavailable
```

The pre-repair Projection backup is forensic/rollback material.

Restoring a divergent derived backup is not product recovery.

---

# 88. Compatibility constraints

Preserve:

```text
Historical Traffic formulas
Historical Traffic business semantics
Traffic Evidence semantics
Observation schema
Observation writer behavior
retention_days configured duration
Projection semantic contract
Projection version model
single-writer model
healthy-only Historical read gate
```

Do not change:

```text
Current Network Throughput
Online Guests Traffic
Completed Guest Session Traffic
```

except normal regression safety.

---

# 89. Schema compatibility contract

```text
RETENTION-FENCE SCHEMA CHANGE = NOT REQUIRED

NEW PERSISTED STATE = NOT AUTHORIZED BY DEFAULT
```

A narrowly justified schema requirement may return to Architecture only if exact repository rebind proves a required P0 invariant cannot be represented safely using existing durable fields.

Coder must never add it opportunistically.

---

# 90. Explicit non-goals

This P0 TASK does not:

```text
change Traffic calculations

change Historical Traffic meaning

change Observation schema by default

change retention duration

rewrite Admin Traffic UI

add UI fallback for failed Historical Projection

embed Projection writer into Flask

weaken consistency guard

broaden accepted Historical health states

auto-heal divergence

create a new Projection DB

create a new writer

redesign Traffic Section
```

---

# 91. Forbidden production shortcuts

Forbidden:

```text
manual INSERT of the two missing cycles

manual status=healthy

manual clear last_error_category

delete/alter authoritative Observation evidence

reduce comparison window to force counts equal

disable count identity guard

disable deep audit

serve diverged Projection as partial/healthy

repair before fixed code is accepted

restart known-vulnerable Projection writer
as rollback convenience
```

---

# 92. Open question — controlled maintenance downtime

Current mutable checkout model requires all artifact-owned long-running processes to be quiesced before artifact mutation.

Owner + Tech Lead should confirm operational acceptance of:

```text
short controlled maintenance downtime
```

during coherent deployment/rollback.

Alternative zero-downtime immutable-release architecture is a separate future design.

This question does not block Architecture FINAL for the retention fix.

---

# 93. Open question — alert notification destination

Architecture freezes:

```text
journal
→ Alloy
→ Loki
→ Grafana
```

and the event/heartbeat contract.

Owner + Tech Lead may separately choose notification routing:

```text
Grafana alert only
email
messaging/NOC destination
```

This does not change Projection semantics.

---

# 94. Open question — durable reconcile-progress timestamp

Default DRAFT-R2 architecture uses:

```text
persisted reconcile cursor tuple
+
runtime repeated-observation timer
```

for stuck detection.

If Tech Lead implementation rebind proves this cannot satisfy the required P0 observability contract unambiguously, return only the exact missing persisted-state requirement for narrow Architecture review.

No schema change is pre-authorized.

---

# 95. DRAFT-R2 acceptance summary

```text
TASK =
TASK-TRAFFIC-PROJECTION-LIFECYCLE-CONSISTENCY-01

STATUS =
DRAFT-R2
FOR FINAL OWNER + TECH LEAD ARCHITECTURE REVIEW

REPOSITORY BASELINE =
ff39fe888c53361a7c65a034eaddb0ce92cc4a12

TREE =
f6f1068a579c1f1c6f1debeae2e6a1e0da4823b8

ROOT CAUSE =
RETENTION CLEANUP / FROZEN RECONCILE WINDOW RACE

RETENTION FIX =
PER-SITE / PER-VERSION CLEANUP FENCE

NORMAL CUTOFF =
now - retention_days

ACTIVE SWEEP EFFECTIVE CUTOFF =
min(normal_cutoff, reconcile_sweep_from_utc)

DELETE ELIGIBILITY =
EXISTING delete_before() TERMINAL/TIMESTAMP SEMANTICS
UNCHANGED

DIVERGED CLEANUP =
BLOCKED

EXPLICIT REPAIR CLEANUP =
BLOCKED

PROOF-WINDOW INTEGRITY =
MANDATORY

DIVERGENCE =
FAIL-CLOSED
LATCHED

AUTO RECOVERY FROM DIVERGED =
NO

REPAIR ENTRY =
repair-site

ONE repair-site INVOCATION =
SEEDS/ADVANCES DURABLE REPAIR
DOES NOT EQUAL RECOVERY

NORMAL WORKER AFTER repair-site =
CONTINUES DURABLE BOUNDED REPAIR

RECOVERY =
FULL NEW HEALTHY PROOF

PROCESS ON ONE SITE DIVERGENCE =
REMAINS RUNNING

OTHER SITES =
CONTINUE

SITE READ AVAILABILITY =
SITE-SCOPED

AGGREGATE HEALTH =
OPERATIONS ONLY
NOT GLOBAL READ GATE

HISTORICAL READ ACCEPTANCE =
Site health MUST remain healthy

RECONCILE PROGRESS IDENTITY =
(reconcile_cursor_started_at, reconcile_cursor_cycle_id)

last_incremental_progress_at AS SOLE STUCK PROOF =
FORBIDDEN

RECONCILE STUCK =
UNCHANGED RECONCILE CURSOR ACROSS ACCEPTED WINDOW

RETENTION-FENCE SCHEMA CHANGE =
NOT REQUIRED

NEW PERSISTED STATE =
NOT AUTHORIZED BY DEFAULT

TELEMETRY PREFIX =
traffic_projection_

HEARTBEAT =
traffic_projection_product_health
maximum interval <= 60 seconds

STATE TRANSITIONS =
IMMEDIATE EVENTS

LOGGING ACCEPTANCE =
STRUCTURED EVENT + SAFE FIELDS
MUST SURVIVE INTO JOURNAL
THEN ALLOY / LOKI / GRAFANA

SYSTEMD TOPOLOGY =
SEPARATE PROJECTION WORKER

LOADED ARTIFACT IDENTITY =
CAPTURED ONCE AT PROCESS START
IMMUTABLE FOR PROCESS LIFETIME

DYNAMIC git rev-parse AS LOADED IDENTITY =
FORBIDDEN

MUTABLE CHECKOUT DEPLOY =
ALL ARTIFACT-OWNED LONG-RUNNING PROCESSES
QUIESCED BEFORE MUTATION

ARTIFACT-OWNED SERVICE DISCOVERY =
MANDATORY

ROLLBACK MIXED LOADED VERSIONS =
FORBIDDEN

ROLLBACK TARGET WITHOUT P0 FIX =
traffic-projection.service REMAINS STOPPED

CURRENT INCIDENT =
FIX FIRST
FORENSIC MANIFEST + BACKUP
THEN REPAIR

FORENSIC MANIFEST =
MANDATORY BEFORE REPAIR

OBSERVATION MUTATION =
FORBIDDEN

MANUAL TWO-ROW INSERT =
FORBIDDEN

MANUAL HEALTH RESET =
FORBIDDEN

IMPLEMENTATION AUTHORIZATION =
NOT GRANTED

PRODUCTION REPAIR =
HOLD

CODER =
HOLD
```

---

# 96. Current incident gate

Until Architecture FINAL, accepted implementation, and explicit recovery authorization:

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

# 97. Next workflow

```text
DRAFT-R2
        ↓
Owner + Tech Lead final architecture review
        ↓
Architecture FINAL
        ↓
Tech Lead fresh repository rebind
        ↓
Architect + Tech Lead implementation-ready TASK
        ↓
Owner implementation authorization
        ↓
Coder writes code
        ↓
narrow implementation tests
        ↓
Coder handoff
        ↓
Owner + Tech Lead official:
race
restart
cleanup boundary
health
logging
deploy
rollback
recovery
regression
acceptance
        ↓
controlled production repair
        ↓
full proof
        ↓
incident closure
```

This DRAFT-R2 does not authorize implementation or production repair.
