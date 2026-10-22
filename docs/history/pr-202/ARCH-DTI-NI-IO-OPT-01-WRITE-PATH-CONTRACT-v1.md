# CAPTIVPORTAL — TASK-DTI-NI-IO-OPT-01
## SAFE WRITE-I/O REDUCTION
### ARCHITECTURE CONTRACT v1
### FOR TECH LEAD REVIEW / PROFILING-FIRST

**Project:** CaptivPortal  
**Role:** Architect  
**Date:** 2026-10-12  
**Task:** `TASK-DTI-NI-IO-OPT-01`  
**Requested input:** `ARCHITECT-REQUEST-DTI-NI-IO-OPT-01-WRITE-PATH-2026-10-12`  
**Technical evidence:** `TASK-DTI-NI-IO-OPT-01-TECHLEAD23-APPLICATION-IO-ANALYSIS-2026-10-12`  
**Re-pinned repository baseline:** `main@88541da8d6952cb91fc945b7f77efcf7e5c46420`  
**TREE:** `d879f5113319c334faf2bf9ae7b8bea7cfdc977e`  
**Implementation authorization:** `NO`  
**Coder production work:** `HOLD`  
**Production mutation:** `NO`  
**NI-05 / NI-06:** `HOLD` until separate Owner decision

---

# 0. EXECUTIVE ARCHITECTURE DECISION

The disk problem is treated as a **write-frequency / synchronous-small-write amplification problem**, not as proof that SQLite `FULL` durability is wrong.

Selected strategy:

```text
KEEP durability and semantic atomicity
        ↓
REDUCE needless transaction / heartbeat / checkpoint / log frequency
        ↓
MEASURE in isolated lab first
        ↓
ONLY THEN allow a bounded production optimization task
```

The first optimization wave MUST NOT change:

```text
SQLite synchronous=FULL
NI-01 source identity
NI-01 checkpoint atomicity
NI-01 generation semantics
NI-01 normalized evidence/provenance
NI-01 privacy retention durations
NI-02A temporal authority
NI-02B immutable edge semantics
NI-02B source checkpoint semantics
NI-02B 14-day edge retention
Site / MAC / device_id authority
CAPPORT / Auth / Portal Core
Fingerprint evidence/classification semantics
```

The first optimization wave MAY experimentally change only:

```text
A1  NI-01 bounded pre-commit coalescing
B1  NI-02B idle successful-poll persistence frequency
B2  NI-02B explicit post-commit PASSIVE checkpoint policy
L1  NI success-telemetry aggregation
```

All four are **lab/profiling candidates first**, not production changes.

Fingerprint spool mutation is NOT part of this contract and remains a separate architecture-owner gate.

---

# 1. VERIFIED CURRENT BASELINE

Repository re-pin confirms:

```text
HEAD = 88541da8d6952cb91fc945b7f77efcf7e5c46420
TREE = d879f5113319c334faf2bf9ae7b8bea7cfdc977e
```

Current source confirms:

## NI-01

```text
SQLite WAL
synchronous=FULL
wal_autocheckpoint=1000
journal_size_limit=64 MiB
one BEGIN IMMEDIATE / COMMIT per ingest batch
batch caps = 256 records / 1 MiB
source record identity + normalized rows + health/fault disposition
+ checkpoint advancement commit atomically
```

Current NI-01 `wal_maintenance()` is already conditional; it is NOT called after every ordinary transaction merely because a commit occurred.

## NI-02B

```text
SQLite WAL
synchronous=FULL
wal_autocheckpoint=1000
poll interval = 1 second
batch max = 256 observations
```

Current empty source poll performs a durable `projection_runtime_state` update.

Current `transaction()` calls `maintain_capacity(post_commit=True)` after every committed transaction, and `maintain_capacity()` executes `PRAGMA wal_checkpoint(PASSIVE)` every time it is called.

## Fingerprint Sensor

Current transport spool uses its own protected durability contract. Its journal mode / enqueue / ACK-delete semantics are outside NI ownership.

---

# 2. PRECEDENCE / NON-REOPEN RULE

This contract is a bounded optimization addendum over already accepted NI-01 and NI-02B semantics.

It does NOT redefine:

```text
NetworkMetadataEnvelopeV1
SourceGenerationV1
SourceRecordIdentityV1
SourceCheckpointV1
DeviceNetworkMetadataEdgeV1
NI-02A temporal attribution
Registry late binding
NI-03 / NI-04 product meaning
```

Where this contract explicitly changes operational persistence cadence, this contract controls that cadence only.

Everything else remains inherited from the accepted parent architecture.

---

# 3. CANDIDATE DISPOSITION REGISTER

| Candidate | Architect disposition | Production authorization |
|---|---|---|
| NI-01 keep `synchronous=FULL` | **APPROVED / REQUIRED** | preserve existing |
| NI-01 atomic observation+identity+checkpoint transaction | **APPROVED / REQUIRED** | preserve existing |
| NI-01 bounded pre-commit coalescing within existing 256/1 MiB caps | **APPROVED FOR LAB** | CONDITIONAL after measurement |
| NI-01 `FULL → NORMAL/OFF` | **REJECTED** | NO |
| NI-02B reduce durable idle-poll heartbeat frequency | **APPROVED FOR LAB** | CONDITIONAL after measurement |
| NI-02B stop explicit PASSIVE after every ordinary commit | **APPROVED FOR LAB** | CONDITIONAL after measurement |
| NI-02B `FULL → NORMAL/OFF` | **REJECTED** | NO |
| NI success-event telemetry aggregation | **APPROVED FOR LAB** | CONDITIONAL after log attribution |
| NI-01/NI-02B retention-duration reduction | **REJECTED IN v1** | NO |
| NI-01/NI-02B schema/index removal/change | **REJECTED IN v1** | NO |
| Retention delete batch/cadence tuning | **HOLD** pending profiling evidence |
| Fingerprint enqueue/ACK batching | **HOLD / SEPARATE OWNER CONTRACT** | NO |
| Fingerprint DELETE→WAL or durability change | **HOLD / SEPARATE OWNER CONTRACT** | NO |
| Dedicated SSD/vDisk comparative study | **APPROVED IN PARALLEL** | migration separately gated |

---

# 4. DECISION 1 — NI-01 DURABILITY / CHECKPOINT AUTHORITY

## 4.1 Authoritative durable unit

For every NI-01 ingest batch the authoritative durable unit remains **one SQLite transaction** containing the accepted prefix's:

```text
source-record identity / digest state
normalized observation rows
family rows
sensitive sidecar rows where applicable
required health/fault state for that committed prefix
checkpoint advancement
source-generation committed offset
```

These MUST NOT be split across weaker stores.

No separate file, memory cache or `NORMAL`-durability database may become authoritative for checkpoint advancement.

## 4.2 Crash envelope

Exact accepted behavior remains:

```text
crash before COMMIT
→ durable checkpoint is unchanged
→ same source bytes replay from checkpoint
→ idempotent result

crash after COMMIT
→ rows + source identity + checkpoint already durable together
→ resume after committed offset
```

For process crash/service restart while the admitted source file remains intact:

```text
permitted semantic data loss = 0 committed source records
```

For host reboot / source-generation loss where transient `/run` source bytes disappear, the already-accepted NI-01 source-gap semantics remain authoritative. No optimization may fabricate recovery.

## 4.3 Weaker durability

```text
separate weak-durability checkpoint = FORBIDDEN
checkpoint-before-observation durability = FORBIDDEN
observation-before-checkpoint as separate durable commits = FORBIDDEN
synchronous=NORMAL/OFF = NOT AUTHORIZED
```

---

# 5. DECISION 2 — NI-01 BOUNDED PRE-COMMIT COALESCING

## 5.1 Selected model

NI-01 MAY experimentally coalesce complete contiguous source records **before opening the SQLite write transaction**.

It MUST NOT hold `BEGIN IMMEDIATE` open while waiting for more source data.

It MUST NOT exceed existing hard batch ceilings:

```text
records <= 256
source bytes <= 1,048,576
```

No architecture version change to source identity or normalized payload is implied.

## 5.2 Closed experimental delay set

Lab candidate values are exactly:

```text
0 ms    # legacy control
100 ms
250 ms
500 ms
```

Production value, if later admitted, MUST be one value from that closed set selected by Tech Lead/Owner from measured evidence.

Coder does not select the production value.

Any value:

```text
> 500 ms
```

requires Architecture return.

## 5.3 Deterministic commit triggers

Once the first complete uncommitted record is available, commit starts on the FIRST condition that becomes true:

```text
record count reaches 256
OR
source bytes reach 1 MiB
OR
configured coalesce deadline expires
OR
source generation must close/transition
OR
gracious stop is requested
OR
uncommitted source backlog high-water is reached
```

Backlog high-water is frozen for this experiment as:

```text
4 MiB of source bytes beyond durable committed_byte_offset
```

At/above high-water:

```text
coalescing wait = 0
```

and the service drains bounded batches immediately.

No CPU-load, HDD-await, queue-length heuristic or machine-learning/adaptive policy may decide the delay.

## 5.4 CPU / memory behavior

Coalescing MUST:

```text
use blocking/timed waits, not busy-spin
retain at most the existing 1 MiB source-byte batch
not create a second durable spool
not create a second checkpoint
not read across a source-generation boundary into one batch
```

Acceptance budget:

```text
additional RSS <= 16 MiB
CPU-seconds per 10,000 processed records <= baseline +10%
```

## 5.5 Interruption behavior

Graceful stop with a non-empty coalescing buffer:

```text
stop waiting
→ immediately attempt the normal atomic batch commit
→ then stop
```

Abrupt crash before commit:

```text
checkpoint unchanged
→ replay from authoritative checkpoint
```

Source rotation/generation transition while records are buffered:

```text
commit eligible old-generation prefix first
→ finish accepted generation transition
→ never mix generations in one transaction
```

## 5.6 Crash-exposure statement

Coalescing can delay durability for records that are already present in the transient source file.

Therefore a later production activation MUST explicitly accept that the additional host-reboot/source-loss exposure is bounded by the selected coalescing delay, with an absolute architecture maximum of 500 ms.

This is not hidden as “zero risk”.

---

# 6. DECISION 3 — NI-02B IDLE-POLL PERSISTENCE

## 6.1 `last_source_poll_at` meaning

`last_source_poll_at` remains:

```text
the most recent source poll that successfully verified the NI-01 source read boundary
```

It is NOT:

```text
proof that network-metadata-projection.service is currently alive
proof that new source observations existed
proof that current Device traffic exists
```

## 6.2 Durable heartbeat interval

The current 1-second source polling cadence remains unchanged.

The durable write cadence for an unchanged successful no-data poll MAY change to:

```text
PROJECTION_DURABLE_IDLE_HEARTBEAT_SECONDS = 10
```

Exact rule:

```text
successful empty poll
+ effective state unchanged
+ no other required projection write
+ <10 s since last durable source-poll heartbeat
→ NO SQLite write transaction
```

When 10 seconds are reached:

```text
persist one durable source-poll heartbeat
```

A real projection batch commit already updates `last_source_poll_at`; it satisfies the heartbeat and no extra heartbeat transaction is created.

If another transaction is already required in the same tick, the heartbeat MAY be piggybacked only if source verification actually succeeded in that tick.

## 6.3 Immediate persistence conditions

Do NOT wait for the 10-second heartbeat on:

```text
runtime-state transition
source failure
attribution failure transition
registry degradation transition
capacity state transition
blocked conflict
startup initializing transition
gracious stopping transition
recovery from non-usable state after successful source verification
```

These remain immediate durable state transitions where storage itself is available.

## 6.4 Startup / restart

On process startup:

```text
runtime effective state = initializing
```

The service MUST NOT expose a newly-started process as `usable` until a successful source verification occurs in that run.

The previous durable `last_source_poll_at` may remain as historical diagnostic evidence; it does not bypass `initializing`.

## 6.5 Cross-process freshness / stale protection

Because Admin/NI readers are in another process, in-memory freshness alone is insufficient.

Readers that consume `projection_runtime_state` MUST derive an effective source state using:

```text
PROJECTION_SOURCE_POLL_STALE_AFTER_SECONDS = 30
```

If persisted state would otherwise be considered source-usable but:

```text
evaluated_at_utc - last_source_poll_at > 30 seconds
```

then effective read state is:

```text
source_unavailable
safe_reason = source_poll_stale
```

No reader may return positive source-health semantics from an indefinitely old persisted `usable` row.

Within the 30-second window, `usable` means only:

```text
source was successfully verified recently enough by policy
```

not “the process is certainly alive at this instant”.

This distinction MUST be preserved in product/operator wording.

## 6.6 Abrupt crash

Abrupt process death cannot write `stopping`.

Therefore:

```text
last durable successful poll ages naturally
→ after 30 s readers fail closed to source_unavailable/source_poll_stale
```

No watchdog DB writer is introduced.

---

# 7. DECISION 4 — NI-02B WAL CHECKPOINT POLICY

## 7.1 Preserve durability primitives

Keep:

```text
journal_mode=WAL
synchronous=FULL
wal_autocheckpoint=1000
16 MiB transaction headroom
combined DB+WAL+SHM footprint accounting
capacity_waiting_reader / capacity_halted fail-closed states
```

## 7.2 Remove redundant explicit checkpoint-on-every-commit behavior

For the optimization candidate:

```text
ordinary successful COMMIT
→ MUST NOT by itself trigger explicit PRAGMA wal_checkpoint(PASSIVE)
```

SQLite's existing `wal_autocheckpoint=1000` remains active.

## 7.3 Explicit PASSIVE triggers

An explicit PASSIVE checkpoint is permitted only when one of these is true:

```text
A. WAL file size >= 16 MiB
B. retention cleanup completed and WAL is non-empty
C. combined footprint + existing 16 MiB transaction headroom approaches configured capacity
D. runtime is already in a capacity_* recovery path
```

Normal soft-maintenance PASSIVE checks are rate-limited to:

```text
at most 1 explicit PASSIVE attempt per 60 seconds
```

except capacity condition C/D, which may bypass that rate limit because it protects bounded storage.

## 7.4 TRUNCATE

`TRUNCATE` remains permitted ONLY under the existing capacity-pressure path after a bounded PASSIVE attempt and only under the existing reader-pin/fail-closed rules.

Forbidden:

```text
periodic unconditional TRUNCATE
TRUNCATE after every commit
startup TRUNCATE “for cleanliness”
manual production checkpoint experiment
```

## 7.5 Reader pin / failure

If PASSIVE reports busy/incomplete while hard capacity headroom is still available:

```text
continue normally
record bounded operational metric
no fake rollback
no checkpoint rewind
```

If capacity headroom can no longer be guaranteed:

```text
existing capacity_waiting_reader / capacity_halted semantics apply
```

No committed projection disposition is ever pretended to have rolled back because post-commit maintenance was incomplete.

## 7.6 Restart

Normal restart relies on SQLite WAL recovery.

No successful restart requires an unconditional manual PASSIVE/TRUNCATE first.

---

# 8. DECISION 5 — FINGERPRINT SPOOL

Fingerprint Sensor is protected and separately owned.

This NI optimization contract authorizes ONLY:

```text
read-only/source inspection
isolated lab profiling of enqueue/ACK/delete/purge transaction counts
fsync/fdatasync measurement
spool depth / delivery latency measurement
crash/replay characterization
```

This contract does NOT authorize:

```text
enqueue batching
ACK/delete batching
journal_mode change
synchronous change
spool schema change
delivery cadence change
retry ordering change
capacity/stale purge change
```

Any such change requires a separate:

```text
TASK-FINGERPRINT-IO-OPT-01
```

owned/reviewed under Fingerprint architecture, with explicit proof of:

```text
non-loss
ordering
idempotent retry
rejection handling
crash atomicity
retained/expired evidence
bounded spool
CAPPORT/Auth isolation
Fingerprint classification non-regression
```

Until that separate contract passes:

```text
FINGERPRINT WRITE-PATH MUTATION = HOLD
```

---

# 9. DECISION 6 — LOGGING / TELEMETRY

## 9.1 Audit authority

Routine journald success events are NOT the authoritative replay/audit store.

Authoritative audit/recovery evidence remains in the owned durable stores:

```text
source generation/checkpoint/source-record lineage
NI-01 health/fault durable records
NI-02B source checkpoints
immutable edges/pending/binding state
runtime failure state
```

## 9.2 Events that remain immediate

The following remain immediate operational events:

```text
service start/stop
generation opened/closed
health/runtime state transition
storage unavailable/corrupt/capacity halt
identity/determinism/conflict fault
projection conflict
source unavailable transition
attribution/registry unavailable transition
recovery transition
```

Repeated identical condition without a new transition may be counted and summarized rather than emitted once per loop.

## 9.3 Success-path aggregation

The following MAY become in-memory counters with periodic summary instead of one journald record per successful batch:

```text
NI-01 batch_committed
NI-01 duplicate_noop success counts
NI-01 repeated bounded fault-aggregate-update notifications
NI-02B batch_committed
NI-02B successful idle poll
NI-02B successful checkpoint-maintenance attempt
```

Summary interval:

```text
60 seconds
```

Normal success-path logging ceiling:

```text
<= 1 summary event per service per 60 seconds
```

Immediate transitions are outside that ceiling.

## 9.4 Required summary fields

Only bounded aggregate fields are needed, for example:

```text
interval_seconds
batch_count
record/observation_count
duplicate_count
fault_count
commit_count
idle_poll_count
checkpoint_attempt_count
checkpoint_busy_count
suppressed_event_count
```

No summary may add raw:

```text
IP
MAC
device_id
DNS name
SNI
raw endpoint
raw Registry record
```

Safe reason codes and source-generation ID remain allowed where already admitted, but high-cardinality per-record identifiers are not required for success summaries.

## 9.5 Reproduction

Dropping per-success-batch journal lines is permitted only because semantic replay/audit does not depend on those lines.

Lab instrumentation MAY separately produce temporary bounded performance traces; they are not production audit authority.

---

# 10. DECISION 7 — RETENTION / SCHEMA / INDEXES

## 10.1 First-wave rule

The first optimization wave MUST have:

```text
schema migration = NONE
index change = NONE
retention-duration change = NONE
privacy-presence semantic change = NONE
DB-engine change = NONE
```

No provenance field is removed from `NetworkMetadataEnvelopeV1`.

No field is removed from `DeviceNetworkMetadataEdgeV1`.

## 10.2 Retention cleanup tuning

Changing only physical cleanup batch size/cadence MAY be reconsidered later, but is currently:

```text
HOLD PENDING P1/P2 PROFILING
```

It may be reopened only if measurements show retention cleanup is a material I/O contributor.

Any future tuning MUST preserve exactly:

```text
eligibility timestamps
14d/30d/45d/90d NI-01 retention semantics
14d NI-02B edge/pending limits
NI-02B existing binding/run/checkpoint retention semantics
FK/reference safety
active checkpoint/generation protection
```

## 10.3 Schema/index optimization

Dropping/rewriting indexes, changing table decomposition, denormalizing provenance, or changing schema version is outside this v1 optimization and requires separate Architecture return.

---

# 11. DECISION 8 — SSD / VDISK SEPARATION VERSUS CODE TUNING

Dedicated storage placement is **NOT a prerequisite** for application write-path optimization.

The two lanes are independent:

```text
Lane S — SysAdmin storage/vDisk benchmark
Lane A/B — NI application write-frequency optimization
```

Either may have higher ROI; neither may claim success for the other without measured evidence.

Existing configurable DB paths remain the location authority.

A future storage move MUST move/use the SQLite database as one coherent database location; DB/WAL/SHM must remain under normal SQLite same-database filesystem semantics.

Production storage migration requires a separate Owner-approved SysAdmin plan with:

```text
writer quiescence / consistent copy or SQLite-safe backup method
pre/post quick_check and FK/integrity validation
exact old/new paths
capacity/free-space proof
rollback path
service-specific restart authorization
no Portal/Auth dependency expansion
```

Fingerprint spool storage movement remains Fingerprint-owner scoped.

---

# 12. DECISION 9 — PROFILING / PERFORMANCE ACCEPTANCE CONTRACT

No optimization may be accepted from one anecdotal sample.

## 12.1 Reproducible lab profiles

For each candidate, run legacy and candidate against the same pinned code/input fixtures and equivalent initial DB state.

Minimum profiles:

```text
P-IDLE   10 minutes no-new-source-data behavior
P-LOW    15 minutes low/normal event replay
P-BURST  15 minutes burst/backlog replay
P-READ   concurrent NI-03/NI-04 bounded reads during write workload
P-CRASH  deterministic crash/restart matrix
```

Each performance profile:

```text
>= 3 independent repetitions
first 60 seconds marked warm-up and excluded from percentile comparison
same input dataset digest
same initial DB snapshot identity
same filesystem/storage class
same CPU/RAM limits
same feature flags except the candidate under test
```

Storage migration comparisons are a separate matrix, not mixed into code-candidate attribution.

## 12.2 Mandatory measured metrics

Per subsystem where applicable:

```text
SQLite transaction / COMMIT count per second
fsync + fdatasync calls per second (lab syscall tracing where possible)
explicit checkpoint attempts / busy / duration
WAL bytes and peak WAL size
write IOPS
write KiB/s
write latency p50 / p95 / p99
CPU seconds
RSS
DB combined footprint
```

Semantic latency:

```text
NI-01 source/event available → ingested_at / durable checkpoint
NI-01 checkpoint lag bytes/records
NI-02B source observation available → projection commit
NI-02B pending-attribution lag
NI-03 read duration / success
NI-04 read duration / success / deadline
```

Safety:

```text
capture drops / source coverage
replay duplicates/conflicts
checkpoint final identity
row/edge semantic equality
retention/privacy invariants
capacity state transitions
```

## 12.3 Hard correctness gate

For identical admitted input and deterministic clock fixtures:

```text
semantic normalized observations = exact expected equality
source record identities = exact equality
final source checkpoint = exact equality
fault/conflict outcome = exact equality
DeviceNetworkMetadataEdge IDs/digests = exact equality
pending/retry disposition = exact equality
Registry late-binding semantics = exact equality
```

Any semantic mismatch:

```text
FAIL
```

regardless of I/O benefit.

## 12.4 Crash/replay matrix

Mandatory NI-01 crash points:

```text
before observation insert
after observation insert / before commit
before checkpoint update
after checkpoint update / before commit
after commit
while coalescing before transaction
```

Required result:

```text
no partial durable checkpoint/data split
same final semantic state after replay
no duplicate observation
```

Mandatory NI-02B crash points:

```text
before projection COMMIT
after projection COMMIT
between empty polls before durable heartbeat
immediately after durable heartbeat
abrupt kill after last usable heartbeat
restart before first source verification
reader-pinned WAL maintenance
```

Required result:

```text
no committed-edge rewind
no duplicate edge
no false permanent usable state
source_poll_stale after 30s without new durable verification
```

## 12.5 Performance value gate

Candidate A1 — NI-01 coalescing proceeds beyond lab only if at the chosen bounded delay:

```text
low/normal workload COMMIT or sync-call rate reduction >= 25%
AND
guest write IOPS reduction attributable to NI-01 >= 15%
```

with no correctness failure.

Candidate B1 — NI-02B idle persistence proceeds beyond lab only if steady no-data source-poll state shows:

```text
idle status-only SQLite write transaction rate <= 0.12 / second
```

and source-health fail-closed tests pass.

Candidate B2 — checkpoint policy proceeds beyond lab only if below capacity pressure:

```text
explicit PASSIVE attempts <= 1 / 60 seconds
```

and no capacity/read-pinning regression occurs.

If a candidate misses its own benefit threshold:

```text
DO NOT SHIP IT merely because it is semantically safe
```

## 12.6 Latency / resource non-regression envelope

A1:

```text
configured coalescing wait <= 500 ms hard
no added wait when 4 MiB backlog high-water reached
high-backlog drain time <= baseline +5%
```

All NI candidates:

```text
CPU per equivalent workload <= baseline +10%
RSS <= baseline +16 MiB
zero new NI-03/NI-04 deadline failures
NI-03/NI-04 p99 read latency <= baseline +10%
no new capture/source/attribution coverage degradation
no increase in semantic conflict rate
```

NI-04 retains its own bounded read deadline; this optimization does not redefine NI-04 product semantics.

---

# 13. DECISION 10 — VERSIONING / REVERSIBILITY / CONFIG

## 13.1 Default-off experimental switches

The profiling/experimental implementation MAY introduce these deployment-only configuration gates:

```text
NETWORK_METADATA_INGEST_COALESCE_ENABLED=false
NETWORK_METADATA_INGEST_COALESCE_MAX_MS=0

NETWORK_METADATA_PROJECTION_IDLE_WRITE_REDUCTION_ENABLED=false
NETWORK_METADATA_PROJECTION_CHECKPOINT_OPT_ENABLED=false

NETWORK_METADATA_TELEMETRY_AGGREGATION_ENABLED=false
NETWORK_METADATA_PROJECTION_TELEMETRY_AGGREGATION_ENABLED=false
```

These are NOT Admin Settings UI keys in this task.

When every gate is false:

```text
legacy write-path behavior must be preserved
```

## 13.2 Closed coalescing config validation

When coalescing is enabled:

```text
NETWORK_METADATA_INGEST_COALESCE_MAX_MS
MUST be one of {100,250,500}
```

`0` is legal only as disabled/legacy behavior.

## 13.3 No schema migration

A1/B1/B2/L1 require:

```text
NI-01 schema version unchanged
NI-02B schema version unchanged
no data rewrite
no backfill
```

Old accepted binaries must remain able to open the same database after the candidate is disabled/rolled back.

## 13.4 Rollback

Future production rollback, if an optimization is ever activated:

```text
disable the exact optimization gate
restart ONLY the affected auxiliary service under Owner authorization
leave DB intact
no VACUUM
no REINDEX
no DB restore solely for rollback
```

Because schema and semantics remain compatible, rollback does not require data migration.

If candidate code creates a semantic or schema dependency that prevents old-code reopen:

```text
candidate violates this v1 contract
→ STOP / Architecture return
```

---

# 14. ALLOWED / FORBIDDEN CHANGE SURFACE

## Allowed after a future Tech Lead profiling task

Lab/test-only changes may touch the narrow modules needed to instrument:

```text
app/network_metadata/*
app/network_metadata_projection/*
focused tests / lab harness
```

Only after profiling acceptance may Tech Lead define exact implementation files.

## Forbidden under this Architecture Contract

```text
CAPPORT/Auth code or configuration
Portal authorization path
Omada/controller behavior
NI-02A authority semantics
Visitor Registry identity semantics
NI-03/NI-04 product semantic widening
NI-05 / NI-06 implementation
Device Fingerprint writer/spool mutation
Suricata production config
network/SPAN/RSPAN
SQLite synchronous weakening
schema migration
index deletion
retention shortening
VACUUM/REINDEX as optimization
manual production checkpointing
production DB relocation
service restart
deploy/merge/PR implied authorization
```

---

# 15. PHASED TASK BREAKDOWN

## Phase P0 — profiling only — NEXT

Tech Lead may prepare:

```text
TASK-DTI-NI-IO-PROFILE-01
```

Scope:

```text
lab harness
transaction/COMMIT counters
fsync/fdatasync tracing
WAL/checkpoint timing
idle-vs-busy NI-02B writes
A1/B1/B2 controlled variants
L1 journald-volume measurement
crash/replay fixtures
NO production behavior change
```

Output:

```text
measured baseline/candidate matrix
recommended candidate values or NO-GO
no production patch authorization inherited
```

## Phase S0 — infrastructure comparison — parallel

SysAdmin-owned:

```text
TASK-INFRA-IO-STORAGE-COMPARE-01
```

Compare HDD baseline with dedicated SSD/vDisk/storage placement in isolated/staging conditions.

No application candidate may claim this benefit as its own.

## Phase F0 — Fingerprint profiling — parallel, owner-specific

```text
TASK-FINGERPRINT-IO-PROFILE-01
```

Profiling only.

No spool semantic mutation.

## Phase A1 — NI-01 optimization candidate

Only if P0 proves value:

```text
bounded coalescing implementation
exact selected delay from {100,250,500}
legacy default OFF
crash/replay acceptance
```

## Phase B1 — NI-02B idle persistence

Only if P0 proves value:

```text
10s durable idle heartbeat
30s fail-closed stale threshold
startup initializing semantics
legacy default OFF
```

## Phase B2 — NI-02B checkpoint policy

Only if P0 proves value:

```text
remove explicit PASSIVE-after-every-commit
keep FULL + WAL autocheckpoint
conditional/rate-limited explicit maintenance
legacy default OFF
```

## Phase L1 — telemetry aggregation

Only if journald attribution demonstrates useful reduction and audit tests pass.

## Phase PROD — separate Owner-controlled production experiment

Not authorized by this contract.

Requires:

```text
Tech Lead source acceptance
exact commit/tree
Owner explicit activation authorization
preflight
one candidate at a time
contemporaneous I/O + semantic metrics
rollback ready
```

---

# 16. PRODUCTION EXPERIMENT SEQUENCING — IF LATER AUTHORIZED

Do not activate A1+B1+B2 simultaneously for the first live experiment.

Required causal sequence:

```text
baseline
→ activate one candidate
→ measure
→ accept/revert
→ only then consider next candidate
```

Preferred order after lab proof:

```text
B1 idle-write reduction
→ B2 checkpoint policy
→ A1 NI-01 coalescing
→ L1 telemetry aggregation
```

Reason:

```text
B1 has the smallest semantic surface and directly removes a proven 1-second status write.
B2 changes maintenance frequency but not projection data semantics.
A1 intentionally adds bounded ingest delay and therefore requires stronger crash/freshness evidence.
L1 should follow journald attribution rather than assumption.
```

This order is a future experimental sequence, not production authorization.

---

# 17. RISK REGISTER

## R1 — intentional NI-01 durability delay

A1 may hold source records up to 500 ms before durable commit.

Mitigation:

```text
closed max delay
zero wait under backlog high-water
durable checkpoint unchanged until commit
crash replay tests
Owner explicit risk acceptance before production
```

## R2 — stale NI-02B usable state after crash

Mitigation:

```text
startup initializing
10s durable heartbeat
30s cross-process stale cutoff
immediate transition persistence
```

## R3 — WAL growth under fewer explicit checkpoints

Mitigation:

```text
wal_autocheckpoint=1000 unchanged
16 MiB soft explicit threshold
60s soft-check rate limit
capacity-pressure bypass
16 MiB transaction headroom unchanged
fail-closed capacity states unchanged
```

## R4 — log reduction hides operational evidence

Mitigation:

```text
durable semantic stores remain audit authority
transitions/errors remain immediate
success counters summarized every 60s
performance traces retained only for bounded experiment evidence
```

## R5 — storage move masks code effect

Mitigation:

```text
storage and code benchmarks are separate experimental lanes
```

## R6 — Fingerprint regression

Mitigation:

```text
no Fingerprint write-path change under this task
separate owner contract required
```

---

# 18. ACCEPTANCE MATRIX

| Case | Required result |
|---|---|
| NI-01 legacy gates OFF | exact legacy batch/write behavior |
| NI-01 coalesce 100/250/500 ms | never exceed 256 / 1 MiB / configured delay |
| NI-01 backlog >=4 MiB | no intentional coalescing wait |
| NI-01 crash before commit | checkpoint unchanged; deterministic replay |
| NI-01 crash after commit | no replay duplication; checkpoint aligned |
| NI-01 generation transition | no cross-generation batch |
| NI-01 conflict in buffered prefix | inherited fail-closed conflict semantics |
| NI-02B idle <10s since heartbeat | no status-only SQLite transaction |
| NI-02B idle at >=10s | exactly one due durable heartbeat transaction |
| NI-02B real batch commit | poll timestamp piggybacks; no extra heartbeat transaction |
| NI-02B source failure | immediate fail-closed transition attempt |
| NI-02B abrupt crash | stale cutoff derives unavailable after 30s |
| NI-02B restart | initializing until new source verification |
| NI-02B ordinary commit below WAL soft threshold | no explicit PASSIVE solely due commit |
| WAL >=16 MiB | bounded PASSIVE eligible |
| capacity pressure | existing PASSIVE/TRUNCATE/fail-closed path preserved |
| pinned reader + enough headroom | committed data remains valid; no fake rollback |
| success telemetry | <=1 normal summary/service/60s |
| state transition/error | immediate operational event |
| privacy sentinels | absent from logs/perf summaries |
| schema/user_version | unchanged |
| retention windows | unchanged |
| NI-03/NI-04 concurrent reads | no new deadline failure / <=10% p99 regression |
| CAPPORT/Auth | zero semantic/runtime dependency introduced |
| Fingerprint | zero write-path mutation |

---

# 19. DIRECT ANSWERS TO TECH LEAD QUESTIONS 1–10

```text
1 DURABILITY/CHECKPOINT
APPROVED = preserve FULL + one atomic source/evidence/checkpoint transaction.
Weaker durability store = NO.

2 NI-01 BATCH PACING
APPROVED FOR LAB = deterministic pre-transaction coalescing.
Hard max delay = 500 ms.
Lab set = 0/100/250/500 ms.
Backlog high-water = 4 MiB → zero wait.

3 NI-02B EMPTY POLL
APPROVED FOR LAB = source still polled every 1s; durable unchanged-success heartbeat every 10s.
Readers fail closed when durable successful poll age >30s.

4 NI-02B CHECKPOINT
APPROVED FOR LAB = no explicit PASSIVE merely because every commit occurred.
Keep FULL/WAL/autocheckpoint; conditional/rate-limited PASSIVE; existing capacity fail-closed path.

5 FINGERPRINT
HOLD for mutation. Profiling only under this stage. Separate Fingerprint contract required.

6 LOGGING
APPROVED FOR LAB = success-path aggregation at 60s; transitions/errors remain immediate; durable DB lineage is audit authority.

7 RETENTION/SCHEMA
Retention-duration/schema/index changes = NO in v1.
Physical retention batching = HOLD until profiling proves material contribution.

8 SSD/VDISK
Not a prerequisite. Independent parallel SysAdmin benchmark/migration lane.

9 METRICS/ACCEPTANCE
Frozen in §§12 and 18. Correctness is hard gate; benefit thresholds are per-candidate; no anecdotal speedup claim.

10 VERSIONING/REVERSIBILITY
Default-off independent feature gates; no schema migration; legacy behavior when disabled; old-code DB compatibility required; production activation separately Owner-controlled.
```

---

# 20. GOVERNANCE / FINAL STATUS

```text
TASK = TASK-DTI-NI-IO-OPT-01

ARCHITECTURE CONTRACT =
ARCH-DTI-NI-IO-OPT-01-WRITE-PATH-CONTRACT-v1

BASELINE HEAD =
88541da8d6952cb91fc945b7f77efcf7e5c46420

BASELINE TREE =
d879f5113319c334faf2bf9ae7b8bea7cfdc977e

ARCHITECTURE_STATUS =
ACCEPTED BY ARCHITECT / READY FOR TECH LEAD REVIEW

OPEN_P0 = 0
OPEN_P1 = 0
OPEN_P2 = 0

READY_FOR_TECH_LEAD_PROFILING_TASK = YES

READY_FOR_TECH_LEAD_PRODUCTION_OPTIMIZATION_TASK =
NO — profiling/benefit/safety gate required first

NI-01 A1 = APPROVED FOR LAB / CONDITIONAL FOR PROD
NI-02B B1 = APPROVED FOR LAB / CONDITIONAL FOR PROD
NI-02B B2 = APPROVED FOR LAB / CONDITIONAL FOR PROD
TELEMETRY L1 = APPROVED FOR LAB / CONDITIONAL FOR PROD

SYNCHRONOUS FULL WEAKENING = REJECTED
SCHEMA/INDEX/RETENTION SEMANTIC CHANGE = REJECTED IN v1
FINGERPRINT WRITE-PATH MUTATION = HOLD / SEPARATE CONTRACT

NI-05 = HOLD
NI-06 = HOLD

IMPLEMENTATION_AUTHORIZATION = NO
CODER_PRODUCTION_IMPLEMENTATION = HOLD
COMMIT/PUSH/PR/MERGE = NO AUTHORIZATION FROM THIS CONTRACT
PRODUCTION_CHANGE = NO
SERVICE_RESTART = NO
PRAGMA MUTATION = NO
STORAGE MIGRATION = NO
```

Next exact governance step:

```text
Architect contract
→ Tech Lead independent architecture review
→ if PASS: profiling-only TASK-DTI-NI-IO-PROFILE-01
→ measured lab evidence
→ Tech Lead + Architect disposition of each candidate
→ only then bounded implementation TASK candidate(s)
→ separate Owner authorization
```

No production optimization is authorized by this document itself.
