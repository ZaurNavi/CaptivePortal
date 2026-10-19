# TASK-TRAFFIC-PROJECTION-01 — Historical Traffic Materialized Projection Foundation — FINAL ARCHITECTURE

**Project:** CaptivPortal  
**Area:** Traffic / Analytics / Derived Read Models  
**TASK:** `TASK-TRAFFIC-PROJECTION-01`  
**Canonical name:** `Historical Traffic Materialized Projection Foundation`  
**State:** `FINAL ARCHITECTURE — FOR OWNER + TECH LEAD FINAL REVIEW`  
**Prepared:** 2026-09-03  
**Implementation authorization:** `NOT GRANTED`  
**Coder authorization:** `NOT GRANTED`  
**Publication / merge / production deployment / activation:** `NOT AUTHORIZED`

---

# 1. Repository binding

`origin/main` was re-fetched immediately before this FINAL.

```text
main =
e196b042515498c5cd9143a9962f6aed90f31566

tree =
f88ee1f854135107c647ccd9d346be2b2ba504b9
```

Current main commit:

```text
Merge pull request #100
Docs: reconcile TRAFFIC-07 Online Guests Traffic production state
```

Functional TRAFFIC-07 production parent:

```text
6425988b5b4ec5ff38bf9c67c74846c3806f668f

tree:
b669f368b0062fcb100b24758cf05e2c4b500144
```

Repository drift since DRAFT:

```text
NONE
```

Before any later implementation authorization:

```text
re-fetch origin/main
re-pin exact SHA/tree
impact-review drift
```

---

# 2. Roadmap state

Canonical planning state:

```text
TASK-TRAFFIC-08 — Completed Guest Session Traffic
=
ARCHITECTURE FROZEN / ON HOLD
```

TRAFFIC-08 is not cancelled.

Preserve:

```text
Visit/session identity research
completed-session semantics
Observation Traffic evidence research
correlation research
quality/evidence research
source inventory
```

Do NOT continue:

```text
TRAFFIC-08 FINAL
implementation decomposition
Coder TASK
branch
patch
PR
publication
implementation
```

until this Projection Foundation is architecturally accepted and implemented.

---

# 3. Foundation goal

Shift expensive historical Traffic work:

```text
FROM:
Admin request-time raw historical reconstruction

TO:
incremental/recoverable background materialization
```

Target steady state:

```text
accepted persisted Observation evidence
        ↓
TrafficProjectionService
        ↓
durable versioned projection DB
        ↓
TrafficProjectionReadService
        ↓
light request-relative range assembly
        ↓
HistoricalTrafficReadService
        ↓
existing Admin API
        ↓
browser
```

Optional RAM cache may sit above durable projection.

RAM is never authoritative.

---

# 4. Authoritative truth

Permanent:

```text
accepted persisted Observation evidence
=
authoritative Traffic source truth
```

Projection is:

```text
derived
versioned
discardable
rebuildable
replaceable
```

Projection never becomes primary truth.

If projection conflicts with accepted source evidence:

```text
source wins
projection becomes untrusted
affected Site/version cannot claim healthy
```

---

# 5. Migration bundle

One shared historical projection cutover covers:

```text
Network Traffic History

Period Statistics

Peak Load
— compatibility consumer only

Traffic by AP

AP Traffic Share
```

Peak is included so ordinary historical Admin loading does not retain a heavy raw
Historical Traffic reconstruction path.

---

# 6. Public semantics remain unchanged

Wave 1 MUST preserve existing public product semantics and versions:

```text
network_traffic_history.v1

network_traffic_period_statistics.v1

network_traffic_peak_load.v1
or the exact existing Peak metric identifier

network_traffic_by_ap.v1

network_traffic_ap_share.v1
```

No public metric version changes merely because persistence/read architecture
changes.

---

# 7. Peak compatibility decision

Frozen:

```text
Peak Load = projection compatibility consumer
```

Peak:

```text
is NOT redesigned
```

Its existing:

```text
formula
quality
evidence
metric version
response semantics
```

remain unchanged.

Peak consumes the same:

```text
ProjectedRangeSelection
selected Site samples
interval classification
```

used by Period Statistics.

---

# 8. Current raw demand-time path

Current historical read conceptually performs:

```text
Observation raw cycle/AP reads
→ candidate cycle selection
→ cycle/AP integrity validation
→ wired/LAN completeness validation
→ request-relative bucket assignment
→ bucket selected_source choice
→ sample ordering
→ interval classification
→ History / Statistics / Peak / AP / Share calculations
→ serialization
```

The expensive raw validation/aggregation is repeated on demand.

---

# 9. Critical request-relative source-selection invariant

Existing historical source selection is bucket-relative.

The selected source:

```text
wired | lan
```

depends on the set of cycles in the exact request-relative bucket.

Therefore:

```text
selected_source is NOT a global immutable property of one source cycle
```

and MUST NOT be persisted as one universal final truth.

---

# 10. No fixed final request buckets in v1

Existing bucket boundaries depend on:

```text
request from_utc
+
bucket_seconds
```

Therefore v1 does NOT store one fixed UTC-aligned final History bucket truth.

Frozen:

```text
final fixed request buckets = NO
```

Canonical request-relative bucket/source selection remains in the read semantic
path, but over compact projected facts rather than raw AP evidence.

---

# 11. Durable projection grain

Frozen v1 durable grain:

```text
validated source-neutral AP-dynamic cycle facts

+

validated per-AP cycle facts
```

The worker moves expensive source-side validation into materialization once per
new/changed source cycle.

---

# 12. Component ownership

## 12.1 Observation

Owns:

```text
raw source acquisition
source DB
source schema
source retention
source cycle lifecycle
```

No change.

## 12.2 TrafficProjectionService

Owns:

```text
incremental discovery
source revision discovery
deep semantic fingerprint
cycle/AP projection calculation
derived DB persistence
checkpoint
reconciliation
rebuild
retention
version lifecycle
projection health
```

## 12.3 TrafficProjectionReadService

Owns:

```text
read-only projection DB access
projection version validation
Site isolation
coherent read snapshot
bounded range reads
projection health/provenance
```

## 12.4 HistoricalTrafficReadService

Remains product semantic owner for:

```text
History
Statistics
Peak
Traffic by AP
AP Share
```

## 12.5 Admin

Owns:

```text
auth
Site authorization
request control
serialization
browser delivery
```

No projection math belongs in Admin UI.

---

# 13. Worker topology

Frozen:

```text
one separate projection process/service
```

Working service identity:

```text
traffic-projection.service
```

The projection worker is not a thread owned by the portal process.

Reasons:

```text
failure isolation
independent restart
independent resource limits
clear single-writer ownership
```

---

# 14. Dedicated derived DB

Frozen path:

```text
/opt/CaptivePortal/data/traffic_projection.sqlite3
```

Working config:

```text
TRAFFIC_PROJECTION_DB_PATH
```

This DB is explicitly:

```text
DERIVED
```

It does not replace or back up Observation truth.

---

# 15. Why projection is not stored in Observation DB

Rejected:

```text
projection tables inside observations.sqlite3
```

because it would:

```text
mix raw and derived truth
increase authoritative DB writer contention
couple projection migrations to source schema
weaken discard/rebuild boundary
```

Projection worker reads Observation DB read-only.

---

# 16. Projection DB schema version

Frozen v1:

```text
PRAGMA user_version = 1
```

Independent identifiers:

```text
projection_schema_version = 1

projection_version =
historical_traffic_projection.v1

source_schema_version =
observations.v1
```

Public metric versions remain separate.

---

# 17. Projection version lifecycle

Exact lifecycle:

```text
building
ready
active
retired
failed
```

Rules:

```text
one active compatible projection_version for normal Admin cutover

new version is built side-by-side

ready requires rebuild/parity/integrity gates

activation is atomic

old active version may remain retained for rollback

retired version is no longer selected for reads
```

---

# 18. Schema table 1 — `traffic_projection_versions`

Exact logical contract:

```text
projection_version              TEXT PRIMARY KEY

projection_schema_version       INTEGER NOT NULL

source_schema_version           INTEGER NOT NULL

semantic_contract_sha256        TEXT NOT NULL

status                          TEXT NOT NULL
                                CHECK status IN (
                                  'building',
                                  'ready',
                                  'active',
                                  'retired',
                                  'failed'
                                )

created_at                      TEXT NOT NULL UTC

ready_at                        TEXT NULL UTC

activated_at                    TEXT NULL UTC

retired_at                      TEXT NULL UTC

build_from_utc                  TEXT NULL UTC

build_through_utc               TEXT NULL UTC

last_validation_at              TEXT NULL UTC
```

There must never be two `active` rows for the same runtime semantic family.

Implementation may enforce this with a partial unique index or equivalent
transactional invariant.

---

# 19. Schema table 2 — `traffic_projection_site_state`

Primary key:

```text
(projection_version, site_id)
```

Exact logical fields:

```text
projection_version                  TEXT NOT NULL

site_id                             TEXT NOT NULL

projection_revision                 INTEGER NOT NULL >=0

status                              TEXT NOT NULL

fast_checkpoint_started_at          TEXT NULL UTC

fast_checkpoint_cycle_id            TEXT NULL

source_head_utc                     TEXT NULL UTC

source_head_cycle_id                TEXT NULL

projection_head_utc                 TEXT NULL UTC

projection_head_cycle_id            TEXT NULL

last_incremental_scan_at            TEXT NULL UTC

last_incremental_progress_at        TEXT NULL UTC

reconcile_cursor_started_at         TEXT NULL UTC

reconcile_cursor_cycle_id           TEXT NULL

reconcile_sweep_started_at          TEXT NULL UTC

reconcile_sweep_source_head_utc     TEXT NULL UTC

reconcile_sweep_source_head_cycle_id TEXT NULL

reconcile_sweep_from_utc            TEXT NULL UTC

last_full_reconcile_completed_at    TEXT NULL UTC

last_full_reconcile_source_head_utc TEXT NULL UTC

last_full_reconcile_source_head_cycle_id TEXT NULL

last_deep_audit_at                  TEXT NULL UTC

last_success_at                     TEXT NULL UTC

backlog_cycle_count                 INTEGER NULL >=0

last_error_category                 TEXT NULL
```

No single field is a completeness watermark.

---

# 20. Head semantics

Freeze distinct HEAD concepts.

```text
source_head_utc
=
started_at of latest currently visible ap_dynamic source cycle
under canonical Site source scope
```

Tie breaker:

```text
source_head_cycle_id
```

```text
projection_head_utc
=
started_at of latest source cycle represented
in the active projection
```

Tie breaker:

```text
projection_head_cycle_id
```

---

# 21. Head lag

Exact:

```text
head_lag_seconds
=
max(source_head_utc - projection_head_utc, 0)
```

when both heads are known.

If source head cannot be safely read:

```text
head_lag_seconds = null
```

Head lag measures:

```text
head/catch-up only
```

It does NOT establish completeness behind the head.

---

# 22. No projection completeness watermark claim

`projection_head_utc` MUST NOT be described as:

```text
complete through
verified through
contiguous watermark
```

Example:

```text
source head = 10:01
projection head = 10:01
head lag = 0

but 09:35 cycle missing
```

is possible until reconciliation discovers it.

Therefore:

```text
head equality != full retained-horizon reconciliation
```

---

# 23. Full reconciliation sweep horizon

Frozen safety horizon:

```text
14 days
```

At sweep start, the worker captures:

```text
reconcile_sweep_source_head_utc
reconcile_sweep_source_head_cycle_id
```

and sets:

```text
reconcile_sweep_from_utc
=
reconcile_sweep_source_head_utc - 14d
```

The sweep is bounded to that captured source-head snapshot.

---

# 24. Reconciliation cursor

Canonical key:

```text
(started_at, cycle_id)
```

State:

```text
reconcile_cursor_started_at
reconcile_cursor_cycle_id
```

The cursor advances by keyset order.

No OFFSET-based correctness dependency.

---

# 25. Full sweep completion

A full reconciliation is complete only when the cursor has examined every
`ap_dynamic` cycle metadata row in:

```text
[reconcile_sweep_from_utc,
 reconcile_sweep_source_head]
```

for the Site/source-head snapshot captured at sweep start.

Only then set:

```text
last_full_reconcile_completed_at

last_full_reconcile_source_head_utc

last_full_reconcile_source_head_cycle_id
```

and reset/start the next sweep cursor.

---

# 26. One chunk is never a full reconcile

Processing one reconciliation chunk may update:

```text
reconcile_cursor_*
```

but MUST NOT update:

```text
last_full_reconcile_completed_at
```

unless the entire captured horizon was traversed.

Therefore:

```text
fresh chunk timestamp != healthy reconciliation proof
```

---

# 27. Reconciliation target cadence

Frozen target:

```text
FULL_RECONCILE_TARGET_INTERVAL_SECONDS = 300
```

One full retained-horizon metadata sweep per Site/version should normally complete
at least every:

```text
5 minutes
```

This is feasible because reconciliation reads cycle metadata, not every AP row.

---

# 28. Reconciliation health age

Frozen:

```text
HEALTHY_FULL_RECONCILE_MAX_AGE_SECONDS = 600
```

Healthy requires a full sweep completed within:

```text
10 minutes
```

of health evaluation.

Grace for active catch-up:

```text
CATCHING_UP_FULL_RECONCILE_MAX_AGE_SECONDS = 900
```

Beyond:

```text
15 minutes
```

without a completed full sweep:

```text
projection status cannot be healthy/catching_up
→ stale
```

unless a higher-precedence unavailable/diverged/rebuilding state applies.

---

# 29. Pre-FINAL reconciliation capacity evidence

Architecture probe used:

```text
14 days
30-second source cadence
40,320 ap_dynamic cycle metadata rows
12 AP per cycle source density
```

Observed full keyset metadata traversal:

```text
~0.11s to ~0.28s
```

depending on chunk size on the synthetic SQLite fixture.

Deep read/fingerprint of one 12-AP cycle was orders of magnitude smaller than the
5-minute sweep budget.

Therefore the 5-minute full-sweep target is deliberately conservative.

Official candidate PERF must still re-measure production-compatible hardware/data.

---

# 30. Source cadence basis

Current repository default AP dynamic interval:

```text
30 seconds
```

Health head thresholds are frozen relative to this existing source cadence.

TRAFFIC-PROJECTION-01 does NOT change Observation scheduling.

---

# 31. Fast source-head scan cadence

Frozen worker target:

```text
SOURCE_HEAD_SCAN_INTERVAL_SECONDS = 15
```

This is projection discovery cadence only.

It does not poll Omada.

It reads persisted Observation metadata.

---

# 32. Healthy head lag

Frozen:

```text
HEALTHY_HEAD_LAG_MAX_SECONDS = 90
```

Equivalent to:

```text
3 current 30-second AP intervals
```

under the accepted current source cadence.

---

# 33. Catch-up head lag

Frozen:

```text
CATCHING_UP_HEAD_LAG_MAX_SECONDS = 300
```

Equivalent to:

```text
10 source intervals
```

under current cadence.

---

# 34. Progress freshness

Frozen:

```text
INCREMENTAL_PROGRESS_MAX_AGE_SECONDS = 60
```

A `catching_up` projection must show progress within the previous:

```text
60 seconds
```

unless no backlog remains and reconciliation itself is the only work in progress.

---

# 35. Projection health precedence

Exact precedence:

```text
1. diverged
2. unavailable
3. rebuilding
4. healthy
5. catching_up
6. stale
```

Evaluation stops at the first matching state.

---

# 36. `diverged`

`diverged` when any known authoritative-source contradiction exists for the active
Site/version, including:

```text
deep fingerprint mismatch not yet reconciled

parity/audit mismatch

impossible projection/source identity

projection row retained after source correction proves it invalid
```

Effect:

```text
active projection is not trusted for normal product reads
```

No automatic raw fallback.

---

# 37. `unavailable`

`unavailable` when no safe projection read can be established because:

```text
projection DB cannot open

projection DB schema is corrupt/incompatible

active version missing/incompatible

Site state missing/corrupt

read-only transaction cannot be established after bounded busy handling
```

Projection content is not served as trusted historical data.

---

# 38. `rebuilding`

`rebuilding` is the primary health state only when:

```text
no trusted active serving version is available
AND
a target version/Site rebuild is actively in progress.
```

Preferred side-by-side rebuild with a healthy active version does NOT change the
active serving health to `rebuilding`.

Instead:

```text
active health remains healthy/catching_up/stale

build_state = rebuilding
```

is separate operational provenance.

---

# 39. `healthy`

ALL must be true:

```text
active compatible projection version exists

projection DB is readable

source metadata is readable

no known divergence

head_lag_seconds <= 90

last_full_reconcile_completed_at exists

now - last_full_reconcile_completed_at <= 600s
```

and no higher-precedence state applies.

Healthy therefore requires:

```text
head catch-up
+
recent completed full reconciliation sweep
```

---

# 40. `catching_up`

All must be true:

```text
active compatible projection is readable

source metadata is readable

no known divergence

not healthy

head_lag_seconds <= 300

last incremental/reconciliation progress <=60s ago

full reconcile age <=900s
```

or:

```text
the previous full reconcile age is <=900s
and a new full sweep is actively progressing
```

`catching_up` may represent:

```text
head backlog
or
temporarily overdue-but-progressing reconciliation
```

within frozen grace bounds.

---

# 41. `stale`

Projection is readable but freshness/reconciliation proof is not sufficient.

Stale if any of the following applies and no higher-precedence state does:

```text
source metadata cannot currently be read

head_lag_seconds > 300

last_full_reconcile_completed_at missing after initial ready activation

full reconcile age >900s

required catch-up/reconciliation progress has stopped

freshness proof otherwise cannot be established
```

Stale is not the same as unavailable:

```text
derived rows may still be readable
but are not asserted healthy/current enough.
```

---

# 42. Initial build health

Before a projection version becomes `ready`:

```text
it is not eligible for normal Admin projection reads.
```

Initial build/reconciliation is operationally:

```text
rebuilding/building
```

not `catching_up`.

`ready` requires a completed initial full reconcile.

---

# 43. Source head unavailable

If projection DB is readable but current Observation metadata head cannot be read:

```text
status = stale
```

not healthy.

No head lag is fabricated.

If projection DB itself is also unavailable:

```text
status = unavailable
```

---

# 44. Cheap source revision marker

Normal source-change discovery MUST NOT deep-hash historical AP rows.

Introduce:

```text
source_revision_marker
```

computed only from `observation_cycles` metadata.

---

# 45. Exact source revision marker inputs

Canonical ordered tuple:

```text
cycle_id
kind
site_id
state
started_at
finished_at
abandoned_at
complete
result
source_rows_reported
items_seen
items_stored
items_skipped
error_count
data_quality_warning_count
updated_at
```

Marker:

```text
SHA-256(canonical encoding of the tuple)
```

No AP-row read is needed to compute it.

---

# 46. Why `updated_at` participates

Observation cycle schema already persists:

```text
created_at
updated_at
```

alongside lifecycle/count fields.

`updated_at` is part of the cheap revision marker.

The marker still includes all relevant lifecycle/count fields so correctness does
not depend on one timestamp alone.

---

# 47. Source semantic fingerprint

Separate:

```text
source_semantic_fingerprint
```

Deep deterministic SHA-256 over every projection-relevant semantic source fact
for one cycle.

It is calculated only when:

```text
cycle is newly projected

revision marker changed

cycle is explicitly rebuilt

cycle is selected for deep audit
```

---

# 48. Deep fingerprint metadata inputs

Includes the exact cycle metadata tuple from `source_revision_marker`.

---

# 49. Deep fingerprint AP inputs

Sorted by canonical:

```text
ap_mac ASC
```

For every source AP row, include projection-relevant fields:

```text
site_id
ap_mac
name

partial
overview_ok
wired_uplink_ok
lan_traffic_ok
radios_ok

wired_observed_at
lan_observed_at

wired_download_mbps
wired_upload_mbps
wired_download_rate_reason
wired_upload_rate_reason

lan_rx_mbps
lan_tx_mbps
lan_rx_rate_reason
lan_tx_rate_reason
```

No raw JSON blob.

No unrelated radio/config payload.

---

# 50. Normal reconciliation algorithm

For each metadata row:

```text
calculate source_revision_marker
```

Then:

```text
projection row missing
→ candidate for deep projection

marker differs
→ candidate for deep reprojection

marker identical
→ no AP deep read in normal sweep
```

This keeps full reconciliation metadata-cheap.

---

# 51. Deep candidate handling

For a candidate:

```text
read source cycle + projection-relevant AP rows

calculate source_semantic_fingerprint

derive validated source-neutral cycle/AP facts

transactionally replace/upsert projection
```

If marker changed but deep fingerprint ultimately yields same projected semantics:

```text
projection_revision need not increment
```

unless durable semantic content changed.

---

# 52. Deep audit

Normal metadata marker cannot detect out-of-contract direct AP-row corruption that
does not update cycle metadata.

Therefore add a bounded sampled deep audit.

Frozen minimum per completed full reconciliation sweep:

```text
sample_count =
min(
  100,
  max(
    10,
    ceil(1% of projected canonical cycles in the 14d horizon)
  )
)
```

Sample selection must be deterministic for:

```text
Site
projection_version
sweep source head
```

so tests are reproducible.

---

# 53. Deep audit mismatch

If sampled deep fingerprint differs while cheap revision marker is unchanged:

```text
status = diverged
```

for the affected Site/version until:

```text
reprojection/rebuild
+
parity/integrity proof
```

restores trust.

This is treated as source/projection integrity anomaly, not normal late evidence.

---

# 54. Fast checkpoint

Fast checkpoint key:

```text
(fast_checkpoint_started_at,
 fast_checkpoint_cycle_id)
```

It accelerates normal append discovery.

It is NEVER correctness authority.

---

# 55. At-least-once + idempotent processing

Frozen:

```text
at-least-once source discovery

+

idempotent transactional projection
```

A cycle may be discovered/processed repeatedly.

Final durable projection for:

```text
projection_version + site_id + cycle_id
```

must be deterministic.

No distributed exactly-once protocol.

---

# 56. Schema table 3 — `traffic_projection_cycles`

Primary key:

```text
(projection_version, site_id, cycle_id)
```

Exact logical source fields:

```text
projection_version              TEXT NOT NULL
site_id                         TEXT NOT NULL
cycle_id                        TEXT NOT NULL
source_kind                     TEXT NOT NULL

source_state                    TEXT NOT NULL
source_started_at               TEXT NOT NULL UTC
source_finished_at              TEXT NULL UTC
source_abandoned_at             TEXT NULL UTC
source_complete                 INTEGER NULL
source_result                   TEXT NULL

source_rows_reported            INTEGER NULL
items_seen                      INTEGER NOT NULL
items_stored                    INTEGER NOT NULL
items_skipped                   INTEGER NOT NULL
error_count                     INTEGER NOT NULL
data_quality_warning_count      INTEGER NOT NULL

source_updated_at               TEXT NOT NULL UTC
source_revision_marker          TEXT NOT NULL SHA256
source_semantic_fingerprint     TEXT NULL SHA256

projected_at                    TEXT NOT NULL UTC
```

---

# 57. Cycle projected integrity fields

Exact logical fields:

```text
integrity_ok                    INTEGER NOT NULL 0|1

stored_row_count                INTEGER NOT NULL >=0

bad_site_count                  INTEGER NOT NULL >=0
bad_mac_count                   INTEGER NOT NULL >=0
duplicate_mac_count             INTEGER NOT NULL >=0
bad_flag_count                  INTEGER NOT NULL >=0
bad_rate_count                  INTEGER NOT NULL >=0
bad_time_count                  INTEGER NOT NULL >=0
```

For non-deep/noncanonical states where AP source rows are intentionally not
materialized, the projection must retain an explicit:

```text
metric_facts_present            INTEGER NOT NULL 0|1
```

to avoid interpreting absent facts as zero.

---

# 58. Cycle source-family fields

When `metric_facts_present=1`, persist BOTH families:

```text
wired_complete                  INTEGER NOT NULL 0|1
lan_complete                    INTEGER NOT NULL 0|1

wired_pair_count                INTEGER NOT NULL >=0
lan_pair_count                  INTEGER NOT NULL >=0

wired_oldest_at                 TEXT NULL UTC
wired_newest_at                 TEXT NULL UTC
lan_oldest_at                   TEXT NULL UTC
lan_newest_at                   TEXT NULL UTC

wired_download_mbps             REAL NULL >=0
wired_upload_mbps               REAL NULL >=0
lan_download_mbps               REAL NULL >=0
lan_upload_mbps                 REAL NULL >=0
```

Do not persist one selected source.

---

# 59. Cycle source-family quality fields

Persist exact reason totals required by existing historical quality semantics for
both source families:

```text
wired_no_baseline_count
wired_counter_reset_count
wired_gap_too_large_count
wired_invalid_elapsed_count
wired_source_unavailable_count
wired_ok_count

lan_no_baseline_count
lan_counter_reset_count
lan_gap_too_large_count
lan_invalid_elapsed_count
lan_source_unavailable_count
lan_ok_count
```

All non-negative integers.

---

# 60. Schema table 4 — `traffic_projection_ap_cycles`

Primary key:

```text
(projection_version, site_id, cycle_id, ap_mac)
```

Fields:

```text
projection_version              TEXT NOT NULL
site_id                         TEXT NOT NULL
cycle_id                        TEXT NOT NULL
ap_mac                          TEXT NOT NULL canonical

historical_name                 TEXT NULL

partial                         INTEGER NOT NULL 0|1
overview_ok                     INTEGER NOT NULL 0|1
wired_uplink_ok                 INTEGER NOT NULL 0|1
lan_traffic_ok                  INTEGER NOT NULL 0|1
radios_ok                       INTEGER NOT NULL 0|1

wired_observed_at               TEXT NULL UTC
lan_observed_at                 TEXT NULL UTC

wired_download_mbps             REAL NULL >=0
wired_upload_mbps               REAL NULL >=0
wired_download_reason           TEXT NULL
wired_upload_reason             TEXT NULL

lan_download_mbps               REAL NULL >=0
lan_upload_mbps                 REAL NULL >=0
lan_download_reason             TEXT NULL
lan_upload_reason               TEXT NULL

projected_at                    TEXT NOT NULL UTC
```

No Share fraction is stored.

---

# 61. Projection DB indexes

Frozen minimum index contract:

```text
traffic_projection_cycles:
(projection_version, site_id, source_started_at, cycle_id)

traffic_projection_cycles:
(projection_version, site_id, source_finished_at, cycle_id)

traffic_projection_cycles:
(projection_version, site_id, source_state, source_result, source_started_at)

traffic_projection_ap_cycles:
(projection_version, site_id, cycle_id, ap_mac)

traffic_projection_ap_cycles:
(projection_version, site_id, ap_mac, cycle_id)
```

Exact SQL names may be implementation-defined.

Query-plan gates must prove these or equivalent indexes are used.

---

# 62. Foreign-key/replace semantics

`traffic_projection_ap_cycles` rows are owned by their projected cycle.

Preferred relational contract:

```text
FOREIGN KEY
(projection_version, site_id, cycle_id)
→ traffic_projection_cycles(...)
ON DELETE CASCADE
```

Reprojection may safely:

```text
replace one cycle
+
replace its AP child rows
```

inside one writer transaction.

---

# 63. Single writer ownership

Frozen:

```text
exactly one process owns writes to traffic_projection.sqlite3
```

Owner:

```text
TrafficProjectionService
```

Admin/portal processes are read-only.

No second writer without architecture review.

---

# 64. Writer-process exclusivity

Implementation must enforce one writer using BOTH:

```text
single systemd service instance

+
exclusive non-blocking process lock
```

Working lock path:

```text
/opt/CaptivePortal/data/traffic_projection.writer.lock
```

If lock cannot be acquired:

```text
worker does not start a second writer
```

It reports typed writer-owner unavailable state.

---

# 65. SQLite journal/sync mode

Frozen:

```text
PRAGMA journal_mode=WAL

PRAGMA synchronous=NORMAL
```

for the projection DB.

This matches existing CaptivPortal SQLite concurrency conventions.

---

# 66. SQLite busy timeout

Frozen:

```text
PRAGMA busy_timeout=500
```

milliseconds on writer and Admin projection-read connections.

Repeated BUSY/LOCKED after this bounded window is a typed unavailable condition,
not an unbounded wait.

---

# 67. Admin projection read connection

Admin/read service opens projection DB:

```text
read-only

URI mode=ro or equivalent

PRAGMA query_only=ON
```

One historical projection result must use:

```text
one coherent SQLite read transaction
```

covering:

```text
active version
Site state/revision
cycle facts
AP facts
```

No independently reopened projection transactions inside one semantic result.

---

# 68. WAL auto-checkpoint

Frozen:

```text
PRAGMA wal_autocheckpoint=1000
```

pages.

Also:

```text
PRAGMA journal_size_limit=67108864
```

bytes:

```text
64 MiB
```

This is a post-checkpoint journal-size target, not a promise that an active WAL can
never temporarily exceed 64 MiB.

---

# 69. Explicit WAL checkpoint policy

The single writer performs:

```text
PRAGMA wal_checkpoint(PASSIVE)
```

at least:

```text
every 60 seconds
```

while active, and:

```text
after major rebuild/backfill phase boundaries
after retention cleanup
```

No blocking:

```text
FULL
RESTART
TRUNCATE
```

checkpoint is used during normal active Admin read operation.

---

# 70. Controlled WAL truncate

`TRUNCATE` checkpoint is allowed only during a controlled maintenance/quiescent
state where:

```text
Admin projection read cutover is OFF
or
readers are explicitly quiesced
```

It is not part of normal request-time behavior.

---

# 71. WAL acceptance bounds

With normal short Admin read transactions:

```text
steady-state WAL after checkpoint cycle
<= 64 MiB target
```

Hard candidate acceptance:

```text
WAL must not exceed 256 MiB
during supported concurrent rebuild/catch-up PERF fixtures.
```

If exceeded:

```text
FAIL
→ transaction/checkpoint/profile review
```

Do not increase the bound without review.

---

# 72. Bounded write transactions — steady state

Normal new/changed source cycle:

```text
one source cycle projection
=
one bounded write transaction
```

Cycle transaction includes:

```text
cycle row
AP child rows
Site revision/state update
checkpoint advancement as appropriate
```

No partial cycle commit.

---

# 73. Bounded write transactions — bulk build/rebuild

Bulk build/rebuild commits at:

```text
max 100 source cycles
OR
max 1.0 second accumulated write-transaction work
```

whichever boundary is reached first.

One unusually expensive cycle may complete its own transaction and must still
obey the per-cycle PERF/failure gates.

No transaction spans an entire:

```text
7d
14d
full rebuild
```

horizon.

---

# 74. Rebuild concurrency model

Frozen preferred model:

```text
side-by-side target projection_version
```

Active version remains readable.

Single writer builds:

```text
target version
```

inside bounded transactions.

Admin continues reading:

```text
active version
```

until target version is `ready`.

---

# 75. Atomic version switch

After:

```text
target rebuild complete
integrity PASS
parity PASS
PERF PASS
```

one short writer transaction changes version lifecycle:

```text
old active → retired/rollback-retained

target ready → active
```

Admin read transaction sees one active version consistently.

No partial cross-version read.

---

# 76. No online DDL during normal read cutover

v1 projection schema is created/migrated before active cutover.

Do not run long schema DDL concurrently with normal Admin projection reads.

Future projection schema migrations require a separately reviewed migration plan.

---

# 77. Startup/open integrity behavior

Writer startup must validate:

```text
file/path ownership and mode
PRAGMA user_version
required tables
required columns
required indexes
active version invariants
foreign-key configuration
```

Then run bounded:

```text
PRAGMA quick_check
```

before claiming storage healthy.

---

# 78. Typed storage failures

Architecture requires distinct internal failure classes or equivalent:

```text
TrafficProjectionStorageUnavailable

TrafficProjectionStorageCorrupt

TrafficProjectionVersionUnavailable

TrafficProjectionDiverged

TrafficProjectionWriterUnavailable
```

Public Admin errors remain safe and do not leak DB details.

---

# 79. Per-cycle atomic reprojection

When one source cycle must be reprojected:

```text
BEGIN IMMEDIATE

re-read/validate source identity as required

calculate deep fingerprint

upsert/replace cycle projection

delete/replace AP child projection

increment Site projection_revision only if semantic content changed

update state/checkpoint

COMMIT
```

Crash before COMMIT:

```text
old complete projection remains
or target-cycle change is absent
```

Never half a cycle.

---

# 80. Projection revision

Per Site/version:

```text
projection_revision
```

is monotonically increasing.

Increment only when durable semantic projection content changes.

Do not increment for:

```text
no-op replay
same semantic fingerprint
metadata scan with no content change
```

---

# 81. Incremental fast path

Every:

```text
15s
```

worker scans source metadata after fast checkpoint.

For each discovered cycle:

```text
compute source_revision_marker

missing/changed
→ deep projection candidate
```

Then checkpoint advances by:

```text
(started_at, cycle_id)
```

after durable processing.

---

# 82. Late/recovered evidence path

Fast checkpoint does not guarantee older coverage.

Rotating full reconciliation detects:

```text
missing older cycle

running → completed

partial/failed lifecycle change

late recovered source cycle

changed revision marker
```

and deep-reprojects candidates.

---

# 83. Source lifecycle marker vs deep fingerprint

Permanent distinction:

```text
source_revision_marker
=
cheap candidate discovery

source_semantic_fingerprint
=
deep semantic identity
```

Never make normal full reconciliation deep-read every AP row merely to discover
changes.

---

# 84. Source correction with unchanged metadata

Such a condition is outside normal repository source lifecycle.

It can still be discovered through:

```text
sampled deep audit
parity audit
explicit rebuild
```

If found:

```text
diverged
```

until corrected.

---

# 85. Full rebuild

Supported:

```text
all Sites / one target version / 14d horizon
```

Reads raw source.

Writes only target projection version.

Does not mutate source.

---

# 86. Site rebuild

Supported:

```text
one Site
```

Active projection for other Sites remains readable.

Preferred:

```text
target version/site side-by-side
```

then controlled activation/replacement.

---

# 87. Range rebuild

Supported on source cycle time:

```text
Site + source_started_at range
```

Reprojects cycle/AP facts.

It does not prebuild all possible public request buckets.

---

# 88. Version rebuild

Formula/projection-contract change:

```text
new projection_version

side-by-side build

parity/acceptance

atomic activation
```

Never reinterpret old rows in place.

---

# 89. Retention

Frozen:

```text
maximum served historical range = 7d

projection retention = 14d
```

Raw Observation retention remains unchanged.

Projection retention must remain:

```text
<= raw authoritative retention
```

for supported rebuildability.

---

# 90. Retention time basis

Retain source-cycle projection if any applies:

```text
source cycle is nonterminal/running

source_finished_at >= retention_cutoff

source_abandoned_at >= retention_cutoff

otherwise source_started_at >= retention_cutoff
```

This avoids dropping a cycle merely because it started before cutoff but
terminated inside retained history.

---

# 91. Retention cleanup

Cleanup:

```text
deletes derived projection rows only
```

Never deletes Observation source evidence.

Cleanup is:

```text
version-aware
Site-aware
bounded transactionally
```

Active/building/rollback-retained versions are protected according to lifecycle.

---

# 92. Optional RAM cache

Frozen:

```text
optional
non-authoritative
not required for foundation acceptance
```

No correctness/availability requirement depends on RAM cache.

Restart:

```text
cache empty
→ durable projection read
→ optional repopulation
```

---

# 93. RAM cache key

If later enabled, key must include:

```text
Site
projection_version
projection_revision
absolute range
bucket size
requested product bundle
```

AP Share cache must additionally account for current AP population/context if the
cached object includes Share/current enrichment.

---

# 94. Cache invalidation

Any semantic projection change:

```text
projection_revision++
```

automatically invalidates prior-revision cache entries.

No mutable in-place cache truth.

---

# 95. Shared `ProjectedRangeSelection`

One internal range primitive must be the common consumer foundation.

Working name:

```text
ProjectedRangeSelection
```

It reads compact projected facts and performs:

```text
request-relative bucket assignment
bucket source-family selection
selected Site sample sequence
period interval classification
AP selected-source contributions
```

---

# 96. History migration

History reads:

```text
projected source-neutral cycle facts
```

then reproduces exact current:

```text
bucket boundaries
selected_source
selection_reason
sample counts
coverage
quality
```

No raw AP reconstruction in normal projection-backed read.

---

# 97. Period Statistics migration

Statistics consumes the SAME:

```text
selected Site sample sequence
interval classification
```

as History.

Existing:

```text
right_endpoint_sample_hold_time_weighted.v1
```

remains unchanged.

No second raw truth.

---

# 98. Peak Load compatibility migration

Peak consumes the SAME projected:

```text
selected Site samples
period interval evidence
```

needed by existing Peak formulas.

Peak public contract remains unchanged.

No raw Heavy Historical Traffic reconstruction for normal Peak request after
cutover.

---

# 99. Traffic by AP migration

Per-AP historical facts come from:

```text
traffic_projection_ap_cycles
```

Using the SAME request bucket:

```text
selected_source
```

chosen at Site level.

Current AP Now/current name/current population remain current-owner facts.

---

# 100. AP Traffic Share migration

AP Share uses the SAME:

```text
AP accepted interval basis
AP weighted D/U
Site accepted interval basis
Site weighted D/U
```

as projected Traffic by AP.

No persisted standalone Share fraction.

No second weight pipeline.

---

# 101. AP Share conservation

Existing conservation remains mandatory.

Conceptually:

```text
SITE_WEIGHT_k
=
fsum(AP_WEIGHT_(a,k))
```

within existing accepted tolerance.

No projection-specific renormalization.

---

# 102. One shared production cutover

Frozen:

```text
one shared historical projection read-path switch
```

Migration bundle:

```text
History
Statistics
Peak
Traffic by AP
AP Share
```

must not be independently split into mixed normal-production truth paths.

---

# 103. Working feature controls

Materialization:

```text
TRAFFIC_PROJECTION_ENABLED=false
```

Read-path cutover:

```text
WEB_ADMIN_TRAFFIC_PROJECTION_READ_ENABLED=false
```

Exact names remain implementation-level naming candidates, but two distinct
control planes are mandatory.

---

# 104. No automatic raw fallback

Frozen after projection read cutover:

```text
NO automatic demand-time raw fallback
```

If projection is stale/unavailable/diverged:

```text
failure/health is visible
```

Admin request does not secretly execute the old expensive raw path.

---

# 105. Explicit rollback path

During migration-period operational rollback:

```text
WEB_ADMIN_TRAFFIC_PROJECTION_READ_ENABLED=false
```

returns the whole shared historical bundle to the old raw path.

This is:

```text
explicit controlled rollback
```

not per-request fallback.

---

# 106. Historical broker unchanged

Frozen in this TASK:

```text
TrafficHistoricalRequestBroker remains

max historical HTTP in-flight = 1

10-second admission guard remains
```

No relaxation.

---

# 107. Why broker remains

Even with cheaper reads it still owns/protects:

```text
intent/coalescing
generation mapping
visibility lifecycle
request ordering
backoff
bounded concurrency
```

A future separate architecture task may reassess guard/concurrency after
production evidence.

---

# 108. Projection health vs public source freshness

Keep two concepts separate:

```text
historical Traffic source freshness
=
accepted Observation evidence semantics

projection health
=
derived read model currency/integrity
```

Existing public source watermark/age fields must retain their current meaning.

Do NOT redefine them as worker timestamps.

---

# 109. Internal projection health DTO

Exact internal shape:

```text
projection_health: {
  status,
  projection_version,
  projection_revision,
  source_head_utc,
  projection_head_utc,
  head_lag_seconds,
  last_incremental_progress_at,
  reconcile_sweep_started_at,
  last_full_reconcile_completed_at,
  last_full_reconcile_source_head_utc,
  last_deep_audit_at,
  backlog_cycle_count,
  build_state
}
```

This need not be added to existing public product DTOs in wave 1.

---

# 110. Worker failure isolation

If worker stops:

```text
Portal authorization continues
Observation acquisition continues
Current State continues
Visit Lifecycle continues
raw Traffic evidence continues accumulating
```

Projection head stops advancing.

Health degrades according to the frozen matrix.

Restart catches up.

---

# 111. Projection DB failure isolation

Projection DB failure must not:

```text
write/corrupt Observation
stop Observation collector
stop Current State
stop Visit Lifecycle
stop Portal authorization
```

Migrated historical Admin reads become unavailable/stale as appropriate.

---

# 112. Source DB unavailable

If Observation source metadata is unavailable:

```text
projection DB remains intact
head verification is unavailable
status cannot be healthy/catching_up
```

With readable projection:

```text
status=stale
```

No new source head is fabricated.

---

# 113. Deployment phase 0 — dormant code

Deploy:

```text
FROM GIT
```

with both controls OFF.

Expected:

```text
no worker
no projection writes
Admin still raw
public Traffic semantics unchanged
```

---

# 114. Deployment phase 1 — worker activation

Separate Owner authorization:

```text
TRAFFIC_PROJECTION_ENABLED=true
```

Admin remains:

```text
projection read cutover OFF
```

Worker builds/catches up/reconciles projection in shadow.

---

# 115. Initial build ready gate

A target version cannot be `ready` until:

```text
14d build complete
head catch-up PASS
one full reconciliation sweep PASS
deep audit PASS
storage integrity PASS
rebuild immutability PASS
```

No Admin cutover before ready.

---

# 116. Deployment phase 2 — parity

Run raw vs projection-backed historical parity for exact candidate.

No permanent dual request-time computation.

Preferred:

```text
Lab parity
offline diagnostic parity
bounded explicitly approved production sample
```

---

# 117. Deployment phase 3 — read cutover

Separate Owner authorization:

```text
WEB_ADMIN_TRAFFIC_PROJECTION_READ_ENABLED=true
```

Whole shared bundle switches:

```text
History
Statistics
Peak
Traffic by AP
AP Share
```

Existing route/API/UI contracts remain unchanged.

---

# 118. Read-cutover eligibility

Projection cutover may be enabled only when active projection health is:

```text
healthy
```

at activation.

Do not activate from:

```text
catching_up
stale
unavailable
rebuilding
diverged
```

---

# 119. Rebuild while production reads active

Preferred:

```text
active version remains readable
target version builds side-by-side
```

Admin must not wait behind a giant rebuild transaction.

Short bounded writer transactions + WAL allow readers to continue.

---

# 120. Rebuild failure

Target version failure:

```text
target → failed
active version unchanged
```

No automatic activation.

No raw mutation.

No Admin cutover change.

---

# 121. Projection read coherent snapshot

One `HistoricalTrafficReadService` projection-backed result MUST obtain projection
facts from one read-only SQLite snapshot.

It must not compose:

```text
cycle rows from revision N
AP rows from revision N+1
```

inside one result.

---

# 122. Current AP context remains external/current

Where existing AP products require current population/Now/name:

```text
current context remains owned by existing Current Traffic service
```

Projection snapshot does not persist or redefine current state.

---

# 123. Query-plan contract

Normal projection-backed migrated reads MUST use projection DB indexes.

Forbidden after cutover:

```text
raw ap_observations historical reconstruction
```

for normal migrated products.

Raw source reads are allowed only for:

```text
worker
rebuild
parity
audit
explicit operational diagnostics
```

---

# 124. Projection update PERF — exact gate

Production-compatible source cycle/AP count.

At least:

```text
100 measured cycle updates
```

Hard:

```text
p95 <= 250 ms
max <= 1.0 s
```

Measured boundary includes:

```text
source metadata/deep source read
validation
fingerprint
projection transaction
AP child rows
Site-state update
commit
```

No source write.

---

# 125. Full reconciliation PERF — exact gate

14d / one Site / current 30s source cadence.

No semantic source changes.

At least:

```text
10 full sweeps
```

Hard:

```text
p95 <= 2.0 s
max <= 3.0 s
```

This measures:

```text
metadata keyset traversal
revision marker comparison
required deterministic deep-audit sample
state update
```

Changed candidates are additionally subject to normal per-cycle update gates.

---

# 126. Catch-up PERF — exact gates

Production-compatible AP count/source density.

Hard per Site:

```text
1h backlog
<= 10 s

24h backlog
<= 60 s

7d backlog
<= 300 s
```

Portal/Observation/Current State must remain healthy during the test.

---

# 127. Admin projection-read PERF — exact gates

Full authenticated Admin endpoint path.

Combined bundle:

```text
History
Statistics
Peak
Traffic by AP
AP Share
```

24h:

```text
>=10 measured runs

p95 <= 1.0 s
max <= 1.5 s
```

7d:

```text
>=10 measured runs

p95 <= 1.5 s
max <= 2.0 s
```

No query deadline increase.

---

# 128. Admin PERF timing boundary

Include:

```text
HTTP auth/session
Site resolution
policy
Admin execution controls
projection read transaction
ProjectedRangeSelection
History/Statistics/Peak/AP/Share composition
serializer
JSON
response-size enforcement
final HTTP response
```

Direct service timing alone is insufficient.

---

# 129. Full rebuild PERF — exact gate

One Site:

```text
14d retained horizon
12 AP supported-capacity fixture
30s source cadence
```

Hard:

```text
full side-by-side rebuild <= 600 s
```

while:

```text
Portal healthy
Observation healthy
Current State healthy
```

No raw source write.

---

# 130. Storage capacity — exact gate

Fixture:

```text
14d
30s cadence
12 AP
one active version
```

Main projection DB:

```text
<= 2 GiB
```

No raw JSON duplication.

---

# 131. WAL capacity gates

Under steady state and supported concurrent Admin reads:

```text
post-checkpoint target <=64 MiB
```

During rebuild/catch-up fixture:

```text
WAL hard max <=256 MiB
```

No unbounded WAL growth.

---

# 132. SQLite contention gate

Concurrent:

```text
writer incremental/rebuild work
+
Admin projection reads
```

must produce:

```text
0 unexpected SQLITE_BUSY/LOCKED failures
```

in official supported PERF runs.

If bounded 500ms busy timeout is exhausted:

```text
typed unavailable/error
```

never indefinite blocking.

---

# 133. Projection storage integrity gate

Mandatory:

```text
schema contract PASS
foreign-key check PASS
quick_check PASS
single active version invariant PASS
Site-state/version consistency PASS
no orphan AP rows
```

---

# 134. Source immutability gate

Hash/size or equivalent accepted immutability proof for authoritative source DB.

Worker/rebuild/parity must show:

```text
Observation source unchanged by projection
```

---

# 135. Idempotency gate

Process same source cycle:

```text
1x
2x
10x
```

Expected:

```text
same projection semantic rows
no duplicate AP rows
projection_revision unchanged for no-op replay
```

---

# 136. Restart gate

Kill worker:

```text
before transaction
during transaction
after commit before checkpoint state progresses
```

Restart:

```text
no partial cycle
safe replay
head catch-up
full reconciliation eventually healthy
```

---

# 137. Late/recovered evidence gate

Fixtures:

```text
late older cycle behind fast checkpoint

running → completed

incomplete → valid

metadata revision change

missing projection row
```

Must be discovered through full reconciliation.

---

# 138. Deep-audit divergence gate

Mutate controlled source semantic AP evidence without changing cheap cycle marker.

Required sampled/explicit deep audit:

```text
detect fingerprint mismatch
→ diverged
```

No healthy status until corrected/rebuilt.

---

# 139. History parity gate

Raw vs projection-backed exact parity for:

```text
status
range
bucket boundaries
selected_source
selection_reason
coverage
quality
null/zero
source transitions
source skew
```

Same existing numeric tolerances only.

---

# 140. Statistics parity gate

Exact existing:

```text
Average
Min
Max
interval evidence
accepted seconds
gap exclusions
source-transition exclusions
weighted D/U
```

No changed formula.

---

# 141. Peak parity gate

Peak compatibility consumer must match raw current Peak:

```text
status
peak values
busiest bucket/hour/event
interval evidence
quality
null behavior
```

Exact current metric/version.

---

# 142. Traffic by AP parity gate

Must match:

```text
historical population
MAC identity
historical name provenance
series
coverage
Average
weighted facts
quality
null behavior
```

---

# 143. AP Share parity gate

Must match:

```text
population
range_presence_proven
D/U/Total fractions
denominator states
current-context behavior
null/zero
conservation
```

No renormalization.

---

# 144. Shared primitive identity gate

For a fixed Site/range/bucket:

```text
History
Statistics
Peak
Traffic by AP
AP Share
```

must use the same:

```text
projected source-cycle set
bucket source selection
selected Site sample basis
```

No product-specific alternate source selection.

---

# 145. Historical broker regression gate

Must prove unchanged:

```text
max historical HTTP in-flight = 1
10s admission guard
waiting != loading
generation ownership
Retry-After/backoff
Global Refresh behavior
```

Cheaper projection reads do not change scheduler policy in this TASK.

---

# 146. Site isolation gate

Site A must never see Site B:

```text
cycle projection
AP projection
state
revision
head
reconciliation
cache
Admin payload
```

Version rebuild for one Site must not disturb another Site.

---

# 147. Security boundary

Projection DB is sensitive operational data.

Required:

```text
non-world-readable file
CaptivPortal-controlled ownership
Admin access only through existing authenticated Site-scoped API
```

No direct file exposure.

---

# 148. Telemetry — exact safe fields

Worker/health telemetry may include:

```text
projection_version
site_id
status
build_state
projection_revision
source_head_utc
projection_head_utc
head_lag_seconds
last_incremental_progress_at
reconcile_sweep_started_at
last_full_reconcile_completed_at
last_full_reconcile_source_head_utc
last_deep_audit_at
backlog_cycle_count
cycles_examined
cycles_projected
cycles_replayed
cycles_corrected
cycles_invalidated
deep_audit_checked
rebuild_progress
duration_ms
db_bytes
wal_bytes
error_category
```

---

# 149. Telemetry forbidden fields

Do NOT log:

```text
AP MAC lists
AP names
raw per-cycle rate arrays
raw SQL
raw source rows
raw projection rows
exception dumps containing source data
```

Cycle ID may be debug-only if explicitly safe.

---

# 150. Divergence telemetry

High-severity event:

```text
traffic_projection_divergence_detected
```

Safe dimensions:

```text
Site
projection_version
source time
reason category
```

No raw evidence payload.

---

# 151. Feature-off backward compatibility

With both projection controls OFF:

```text
existing Traffic products behave exactly as current production
no worker
no projection read
no projection DB workload required
```

---

# 152. Worker-on / read-off compatibility

With:

```text
projection worker ON
Admin projection read OFF
```

required:

```text
existing Admin products still use raw path
projection builds in shadow
public outputs unchanged
```

This is mandatory pre-cutover production state.

---

# 153. Read-cutover failure behavior

After cutover:

```text
projection health problem
```

must not silently trigger raw demand-time reconstruction.

The shared migrated bundle follows explicit projection health/error behavior.

Operational rollback is feature-controlled.

---

# 154. Rollback

Primary read rollback:

```text
WEB_ADMIN_TRAFFIC_PROJECTION_READ_ENABLED=false
```

Primary worker rollback:

```text
TRAFFIC_PROJECTION_ENABLED=false
```

Projection DB may remain on disk.

No raw DB rollback.

---

# 155. Projection DB rebuild rollback

If projection DB is corrupt:

```text
disable projection read cutover
quiesce/stop worker as needed
build clean target derived DB/version
verify
reactivate worker
parity
re-enable cutover
```

Raw Observation remains untouched.

---

# 156. NO-TOUCH — Observation

No changes in this foundation to:

```text
Observation acquisition
Omada polling
Observation schema
Observation AP formulas
Observation source retention
AP dynamic cadence
```

Projection only reads source.

---

# 157. NO-TOUCH — Current State / TRAFFIC-07

No changes to:

```text
Current State
CurrentGuestTrafficReadService
Online Guests Traffic
TRAFFIC-07 semantics
```

---

# 158. NO-TOUCH — Visit Lifecycle / TRAFFIC-08

No Visit changes.

TRAFFIC-08 remains:

```text
FROZEN / ON HOLD
```

No completed-session implementation during this foundation.

---

# 159. NO-TOUCH — Public Traffic

No changes to:

```text
Public Traffic worker
public_traffic.sqlite3
public Traffic semantics
```

---

# 160. NO-TOUCH — historical product formulas

No formula changes to:

```text
History
Statistics
Peak
Traffic by AP
AP Share
```

unless a separate architecture amendment is approved.

---

# 161. NO-TOUCH — broker protections

No changes to:

```text
max historical in-flight
10s admission guard
```

inside this TASK.

---

# 162. Migration phase A

Projection storage foundation:

```text
derived DB schema
version model
Site state
cycle/AP rows
read-only projection repository
storage integrity tests
```

No worker activation.

No Admin cutover.

---

# 163. Migration phase B

Worker:

```text
fast head scan
revision marker
deep fingerprint
idempotent projection
checkpoint
full reconciliation sweep
deep audit
retention
rebuild
health
WAL/checkpoint controls
```

Admin still raw.

---

# 164. Migration phase C

Projection-backed semantic reader:

```text
TrafficProjectionReadService
ProjectedRangeSelection
```

Run raw/projection parity.

No public route/UI change.

---

# 165. Migration phase D

Shared historical product migration:

```text
History
Statistics
Peak compatibility
Traffic by AP
AP Share
```

behind one shared cutover.

---

# 166. Migration phase E

Production shadow worker:

```text
worker ON
read cutover OFF
```

Prove catch-up/reconciliation/restart/rebuild/parity.

---

# 167. Migration phase F

Separate production read cutover.

Only after all mandatory gates PASS.

---

# 168. Central Lab

Official current Central Lab or successor:

```text
PASS
strict regressions = 0
```

on exact candidate tree.

Coder does not own official PASS/FAIL.

---

# 169. Production dormant acceptance

Code deployed with worker/read cutover OFF.

Prove:

```text
portal service healthy
Observation healthy
Current State healthy
Visit Lifecycle healthy
all Traffic products healthy
no public semantic change
```

---

# 170. Worker production acceptance

After separate worker activation, read cutover still OFF.

Prove:

```text
projection builds
active version becomes healthy
head lag <=90s
full reconcile age <=600s
restart safe
WAL bounded
source immutable
raw Admin products unchanged
```

---

# 171. Read-cutover production acceptance

After separate Owner authorization:

```text
shared projection read cutover ON
```

Prove:

```text
History healthy
Statistics healthy
Peak healthy
Traffic by AP healthy
AP Share healthy

24h/7d range switching unchanged

independent panel ranges unchanged

browser semantics unchanged

no normal raw historical AP reconstruction
```

---

# 172. TRAFFIC-08 effect

Frozen:

```text
TRAFFIC-08 remains ON HOLD
until this foundation is accepted and implemented.
```

After foundation production acceptance:

```text
re-open TRAFFIC-08
rebind repository
preserve Visit/session decisions
review whether completed-session Traffic should consume or extend
the new projection/materialization architecture
```

Do not discard prior TRAFFIC-08 work.

---

# 173. Final frozen architecture decisions

1. Accepted persisted Observation evidence remains authoritative truth.
2. Projection is derived/versioned/discardable/rebuildable.
3. Dedicated `/opt/CaptivePortal/data/traffic_projection.sqlite3`.
4. `TrafficProjectionService` owns materialization.
5. `TrafficProjectionReadService` owns projection reads.
6. `HistoricalTrafficReadService` remains public product semantic owner.
7. Separate projection service/process.
8. Exactly one projection DB writer.
9. WAL + `synchronous=NORMAL`.
10. `busy_timeout=500ms`.
11. Admin projection reads are read-only/query-only coherent transactions.
12. `wal_autocheckpoint=1000`.
13. `journal_size_limit=64MiB`.
14. PASSIVE checkpoint at least every 60s.
15. No giant rebuild transaction.
16. Steady cycle update is one transaction.
17. Bulk rebuild max 100 cycles or 1s write transaction.
18. Side-by-side target-version rebuild is preferred/frozen.
19. Active version remains readable during side-by-side rebuild.
20. Durable grain is source-neutral cycle + per-AP cycle facts.
21. No fixed final request buckets in v1.
22. Request-relative bucket/source selection remains canonical.
23. Both wired/LAN families are persisted.
24. One `ProjectedRangeSelection` is shared by all migrated products.
25. History migrated.
26. Statistics migrated.
27. Peak migrated as compatibility consumer.
28. Traffic by AP migrated.
29. AP Share migrated from same AP contribution primitive.
30. One shared read cutover for all five products.
31. No automatic raw fallback after cutover.
32. Explicit rollback flag returns entire bundle to raw path.
33. Processing is at-least-once + idempotent.
34. Fast checkpoint is optimization only.
35. Cheap `source_revision_marker` uses cycle metadata only.
36. Deep `source_semantic_fingerprint` is calculated only for candidates/audits.
37. Full reconciliation is metadata-first.
38. Full reconciliation safety horizon is 14d.
39. Full reconciliation target interval is 300s.
40. Healthy full-reconcile max age is 600s.
41. Catch-up reconciliation grace max is 900s.
42. Source-head scan target is 15s.
43. Healthy head lag max is 90s.
44. Catching-up head lag max is 300s.
45. Catching-up progress max age is 60s.
46. Head equality does not prove completeness.
47. No projection completeness-watermark claim is made.
48. Full sweep completion is separately recorded.
49. Deep audit checks 1%, min10/max100 cycles per full sweep.
50. `diverged` has highest health precedence.
51. Health states are exact: healthy/catching_up/stale/unavailable/rebuilding/diverged.
52. Projection retention is 14d.
53. Maximum served historical product range remains 7d.
54. Raw retention unchanged.
55. RAM cache optional/non-authoritative.
56. Historical Broker remains.
57. Max historical in-flight=1 remains.
58. 10s admission guard remains.
59. No Observation schema/acquisition change.
60. No query-time Omada.
61. No Current State change.
62. No Visit Lifecycle change.
63. TRAFFIC-07 unchanged.
64. TRAFFIC-08 frozen/on hold.
65. Implementation is not authorized by this FINAL.

---

# 174. Final PERF/storage gates

```text
per-cycle projection:
p95 <=250ms
max <=1s

full 14d metadata reconciliation sweep:
p95 <=2s
max <=3s

catch-up:
1h <=10s
24h <=60s
7d <=300s

Admin 24h combined bundle:
p95 <=1.0s
max <=1.5s

Admin 7d combined bundle:
p95 <=1.5s
max <=2.0s

14d/12AP full rebuild:
<=600s

14d/12AP projection DB:
<=2GiB

steady post-checkpoint WAL target:
<=64MiB

supported rebuild/catch-up WAL hard max:
<=256MiB

unexpected SQLite contention failures:
0

source writes:
0
```

All official measurements use the exact candidate tree and
production-compatible Linux environment.

---

# 175. Final state

```text
TASK:
TASK-TRAFFIC-PROJECTION-01

NAME:
Historical Traffic Materialized Projection Foundation

DOCUMENT:
FINAL ARCHITECTURE
FOR OWNER + TECH LEAD FINAL REVIEW

BOUND TO:
main@e196b042515498c5cd9143a9962f6aed90f31566

TREE:
f88ee1f854135107c647ccd9d346be2b2ba504b9

DRIFT:
NONE

AUTHORITATIVE SOURCE:
accepted persisted Observation evidence

DERIVED DB:
/opt/CaptivePortal/data/traffic_projection.sqlite3

PROJECTION VERSION:
historical_traffic_projection.v1

SCHEMA VERSION:
1

PROJECTION OWNER:
TrafficProjectionService

READ OWNER:
TrafficProjectionReadService

PRODUCT SEMANTIC OWNER:
HistoricalTrafficReadService

MIGRATION BUNDLE:
History
Statistics
Peak compatibility consumer
Traffic by AP
AP Share

DURABLE GRAIN:
source-neutral validated cycle facts
+
per-AP cycle facts

FIXED FINAL REQUEST BUCKETS:
NO

REQUEST-RELATIVE SOURCE SELECTION:
PRESERVED

PROCESSING:
at-least-once
+
idempotent transactional projection

CHECKPOINT:
optimization only

REVISION DISCOVERY:
cheap cycle metadata marker

DEEP IDENTITY:
semantic source fingerprint

FULL RECONCILIATION:
14d metadata sweep

FULL SWEEP TARGET:
300s

HEALTHY RECONCILE AGE:
<=600s

CATCH-UP RECONCILE GRACE:
<=900s

SOURCE HEAD SCAN:
15s

HEALTHY HEAD LAG:
<=90s

CATCHING_UP HEAD LAG:
<=300s

HEALTH:
healthy
catching_up
stale
unavailable
rebuilding
diverged

ONE WRITER:
YES

SQLITE:
WAL
synchronous=NORMAL
busy_timeout=500ms
wal_autocheckpoint=1000
journal_size_limit=64MiB

ADMIN READ:
read-only
query_only
one coherent transaction

REBUILD:
side-by-side target version
bounded transactions

RETENTION:
14d

MAX SERVED RANGE:
7d

RAM CACHE:
optional
non-authoritative

AUTO RAW FALLBACK:
NO

SHARED READ CUTOVER:
YES

HISTORICAL BROKER:
UNCHANGED

HISTORICAL IN-FLIGHT:
1

ADMISSION GUARD:
10s

OBSERVATION CHANGE:
NO

CURRENT STATE CHANGE:
NO

VISIT CHANGE:
NO

TRAFFIC-07 CHANGE:
NO

TRAFFIC-08:
FROZEN / ON HOLD

IMPLEMENTATION:
NOT AUTHORIZED

CODER:
NOT AUTHORIZED

PUBLICATION:
NOT AUTHORIZED

MERGE:
NOT AUTHORIZED

PRODUCTION DEPLOY:
NOT AUTHORIZED

ACTIVATION:
NOT AUTHORIZED
```

---

# 176. Next allowed step

Owner + Tech Lead perform FINAL architecture review.

If accepted:

```text
FINAL:
OWNER + TECH LEAD ACCEPTED

ARCHITECTURE:
CLOSED

IMPLEMENTATION:
READY FOR SEPARATE OWNER AUTHORIZATION
```

Only after separate explicit Owner implementation authorization:

```text
re-fetch / re-pin origin/main

impact-review drift

Tech Lead implementation decomposition

Coder task
```

No implementation may begin from this FINAL alone.
