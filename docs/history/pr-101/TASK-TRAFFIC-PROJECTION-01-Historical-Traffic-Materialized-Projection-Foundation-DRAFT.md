# TASK-TRAFFIC-PROJECTION-01 — Historical Traffic Materialized Projection Foundation — ARCHITECTURAL DRAFT

**Project:** CaptivPortal  
**Area:** Traffic / Analytics / Derived Read Models  
**TASK:** `TASK-TRAFFIC-PROJECTION-01`  
**Working name:** `Historical Traffic Materialized Projection Foundation`  
**State:** `ARCHITECTURAL DRAFT — FOR OWNER + TECH LEAD REVIEW`  
**Prepared:** 2026-09-03  
**Implementation authorization:** `NOT GRANTED`  
**Coder authorization:** `NOT GRANTED`  
**Production / publication / merge / deployment / activation:** `NOT AUTHORIZED`

---

# 1. Immediate roadmap state

This DRAFT supersedes the previous immediate implementation priority.

Canonical planning state:

```text
TASK-TRAFFIC-08 — Completed Guest Session Traffic
=
ARCHITECTURE FROZEN / ON HOLD
```

TRAFFIC-08 is NOT cancelled.

Its completed work remains valid source material:

```text
Visit/session identity research
completed-session semantics
Observation Traffic evidence research
source inventory
correlation analysis
quality model research
```

But:

```text
no TRAFFIC-08 FINAL continuation

no TRAFFIC-08 implementation decomposition

no TRAFFIC-08 Coder TASK

no TRAFFIC-08 branch / patch / PR / publication / implementation
```

until this Projection Foundation is architecturally accepted and implemented.

After Projection Foundation:

```text
re-open TRAFFIC-08
→ repository rebind
→ impact review
→ adapt only affected read/materialization portions
→ FINAL
```

---

# 2. Repository baseline

`origin/main` was re-fetched before this DRAFT.

Current main:

```text
e196b042515498c5cd9143a9962f6aed90f31566
```

Current tree:

```text
f88ee1f854135107c647ccd9d346be2b2ba504b9
```

Current main commit:

```text
Merge pull request #100
Docs: reconcile TRAFFIC-07 Online Guests Traffic production state
```

Functional production reference below that docs merge:

```text
6425988b5b4ec5ff38bf9c67c74846c3806f668f

tree:
b669f368b0062fcb100b24758cf05e2c4b500144
```

Repository drift relative to the last Traffic architecture work:

```text
NONE
```

Before FINAL:

```text
re-fetch / re-pin origin/main
impact-review drift
```

Before any later implementation authorization:

```text
repeat repository rebind
```

---

# 3. Architecture goal

Introduce a reusable derived historical Traffic read model that shifts expensive
work:

```text
FROM:
Admin request-time raw evidence reconstruction

TO:
incremental / recoverable background materialization
```

Target steady-state path:

```text
authoritative persisted Observation evidence
        ↓
TrafficProjectionService
        ↓
durable versioned traffic projection
        ↓
TrafficProjectionReadService
        ↓
lightweight range assembly
        ↓
existing HistoricalTrafficReadService product semantics
        ↓
Admin API
        ↓
browser rendering
```

Optional:

```text
small RAM hot cache
```

may sit above durable projection.

It is never authoritative.

---

# 4. Fundamental truth rule

Permanent:

```text
RAW ACCEPTED PERSISTED EVIDENCE
=
AUTHORITATIVE TRUTH
```

Projection:

```text
derived

versioned

discardable

rebuildable

replaceable
```

If projection conflicts with raw source evidence:

```text
raw accepted evidence wins
```

Projection must be marked:

```text
diverged / unavailable / rebuild-required
```

according to the future frozen status contract.

No silent preference for projection over contradictory raw evidence.

---

# 5. Scope of migration wave 1

Primary product migration candidates:

```text
Network Traffic History

Period Statistics

Traffic by AP

AP Traffic Share
```

Product meanings and existing public metric contracts MUST remain unchanged.

Existing metric versions remain:

```text
network_traffic_history.v1

network_traffic_period_statistics.v1

network_traffic_by_ap.v1

network_traffic_ap_share.v1
```

This TASK is an internal architecture migration.

It is NOT a v2 product semantics change.

---

# 6. Explicitly out of migration wave 1

```text
TRAFFIC-08
```

remains frozen/on hold.

Also not automatically migrated by this DRAFT:

```text
Current Network Throughput

Online Guests Traffic

CurrentGuestTrafficReadService

Visit Lifecycle products

Public Traffic

Home Analytics products
```

Peak Load requires a dedicated compatibility decision because it currently shares
the same historical Traffic request/foundation.

That decision is an explicit open question in this DRAFT.

---

# 7. Current demand-time architecture

Current historical path conceptually:

```text
Admin Traffic request
        ↓
HistoricalTrafficReadService
        ↓
AnalyticsSourceGateway
        ↓
Observation raw AP dynamic cycles + AP rows
        ↓
candidate cycle selection
        ↓
cycle integrity validation
        ↓
wired/LAN completeness validation
        ↓
request-relative bucket assignment
        ↓
bucket source-family selection
        ↓
sample / interval ordering
        ↓
gap / source-transition / evidence classification
        ↓
History / Statistics / AP / Share calculations
        ↓
serialization
        ↓
browser
```

The expensive source-side validation/aggregation repeats for normal historical
requests.

---

# 8. Important current semantic constraint — bucket-relative source selection

Current historical source selection is not globally fixed per source cycle.

For each request-relative bucket, existing semantics choose:

```text
wired
or
LAN
```

from the set of cycles inside that bucket using:

```text
full coverage

relative coverage

pair counts

primary-source preference
```

Therefore:

```text
the selected source for a cycle may depend on the request bucket
in which that cycle is evaluated.
```

This has a major architecture consequence.

---

# 9. Why v1 MUST NOT persist one global final selected_source per cycle

A projection row such as:

```text
cycle X → selected_source=wired
```

would be semantically unsafe because current source selection is:

```text
bucket-relative
```

not an invariant source-cycle property.

Likewise a single universal precomputed final interval:

```text
cycle A → cycle B
```

with already-selected Traffic family would risk changing current semantics.

Therefore v1 must retain enough source-neutral materialized facts to reproduce the
existing request-relative selection exactly.

---

# 10. Why v1 MUST NOT blindly persist only fixed wall-clock History buckets

Existing bucket index is derived from:

```text
request from_utc
+
bucket_seconds
```

Therefore fixed UTC-aligned persisted 5m/15m buckets are not guaranteed to be
identical to current range-relative bucket boundaries.

Wave 1 MUST NOT change:

```text
bucket boundaries

selected-source decision

sample membership

interval classification
```

merely for storage convenience.

---

# 11. Chosen v1 projection level

Canonical proposed durable materialization level:

```text
VALIDATED SOURCE-NEUTRAL CYCLE FACTS

+

VALIDATED PER-AP CYCLE FACTS
```

Not final product payloads.

The background layer performs the expensive source-side work once:

```text
raw cycle/AP validation

integrity checks

per-cycle AP aggregation

wired/LAN completeness

wired/LAN Site rates

per-AP source-family facts

quality/reason extraction

source provenance
```

Admin request-time work becomes:

```text
indexed read of compact projection rows

→ request-relative bucket assignment

→ existing bucket source selection

→ lightweight interval classification/aggregation

→ serializer
```

No raw AP evidence reconstruction in normal migrated reads.

---

# 12. Architecture name

Recommended component owner:

```text
TrafficProjectionService
```

Reason:

```text
Projection
```

is broader and more accurate than `Rollup`.

v1 does not guarantee that every public product bucket itself is durably stored.

Recommended read owner:

```text
TrafficProjectionReadService
```

Existing product semantic owner remains:

```text
HistoricalTrafficReadService
```

This preserves existing public Traffic semantics.

---

# 13. Responsibility split

## 13.1 Observation acquisition

Owns:

```text
raw AP dynamic cycles
raw persisted AP facts
source schema
source retention
```

No change.

## 13.2 TrafficProjectionService

Owns:

```text
incremental source discovery

source-cycle validation projection

per-cycle materialization

per-AP materialization

projection persistence

checkpoints

reconciliation

rebuild

projection version lifecycle
```

## 13.3 TrafficProjectionReadService

Owns:

```text
read-only projection DB access

single coherent read snapshot

Site/version isolation

bounded range reads

projection freshness/provenance
```

## 13.4 HistoricalTrafficReadService

Continues to own:

```text
Network Traffic History semantics

Period Statistics semantics

Traffic by AP semantics

AP Traffic Share semantics
```

It must consume projected primitives without changing output meaning.

## 13.5 Admin

Owns only:

```text
authorization

request contract

execution controls

serialization

presentation
```

No projection calculation in Admin UI.

---

# 14. Recommended durable storage

Recommended:

```text
/opt/CaptivePortal/data/traffic_projection.sqlite3
```

Working config name:

```text
TRAFFIC_PROJECTION_DB_PATH
```

This path/name is DRAFT, not implementation authorization.

---

# 15. Storage option comparison

## Option A — dedicated derived projection DB

```text
traffic_projection.sqlite3
```

Advantages:

```text
clear authoritative-vs-derived boundary

delete/rebuild safely

separate schema lifecycle

side-by-side projection versions

isolated retention

isolated indexes

low coupling to Observation schema

projection failure does not mutate raw source

simpler rollback
```

Disadvantages:

```text
new derived DB lifecycle

new worker write path

disk capacity/backup policy must be explicit
```

Architect recommendation:

```text
PREFERRED
```

---

# 16. Storage option B — persist projection inside Observation DB

Rejected for v1.

Reasons:

```text
mixes raw truth and derived read model

couples projection migrations to source schema

creates additional writer contention in authoritative DB

makes discard/rebuild semantics less clear

complicates raw retention cleanup
```

No projection tables should be added to Observation DB by default.

---

# 17. Storage option C — existing Analytics DB

Current Analytics architecture is primarily read-only composition over source DBs.

There is no canonical existing persisted Analytics DB whose ownership cleanly fits
this foundation.

Creating an "Analytics DB" for this feature would effectively be creating a new
projection DB under a less precise name.

Recommendation:

```text
do not create a generic Analytics persistence layer merely to host Traffic.
```

Use dedicated derived Traffic projection storage.

---

# 18. Projection DB truth classification

The DB must be explicitly documented as:

```text
DERIVED DATA
```

It is NOT:

```text
source-of-truth backup

Observation replacement

disaster-recovery source for raw evidence
```

Backup is optional for operational recovery speed, but correctness must not depend
on backup availability.

---

# 19. Projection schema version

Separate:

```text
projection_schema_version
```

from:

```text
projection_version
metric_version
source_schema_version
```

Example working values:

```text
projection_schema_version = 1

projection_version =
historical_traffic_projection.v1

source_schema:
observations=1
```

Existing public product metric versions remain unchanged.

---

# 20. Projection versioning rule

Any change that alters materialized meaning must create:

```text
new projection_version
```

Examples:

```text
new source validation formula

different completeness rule

new source-family selection prerequisite

changed AP contribution primitive

new interval-support facts
```

Never silently reinterpret old projection rows.

---

# 21. Metric version rule

Public metric version changes only when product semantics change.

Internal materialization refactor:

```text
does NOT by itself change metric_version.
```

Therefore wave 1 target remains:

```text
network_traffic_history.v1

network_traffic_period_statistics.v1

network_traffic_by_ap.v1

network_traffic_ap_share.v1
```

---

# 22. Side-by-side version strategy

Projection DB should allow:

```text
v1 active

v2 building
```

simultaneously.

New version lifecycle:

```text
building

ready

active

retired
```

Activation of a new projection version occurs only after:

```text
rebuild PASS

parity PASS

PERF PASS

Owner-controlled activation
```

Old version may remain temporarily for rollback.

---

# 23. Proposed table — projection_versions

Conceptual fields:

```text
projection_version

projection_schema_version

source_schema_version

status

created_at

ready_at

activated_at

retired_at

build_from_utc

build_through_utc

notes/version_hash
```

No raw product payload stored here.

---

# 24. Proposed table — site projection state

Conceptual:

```text
traffic_projection_site_state
```

Key:

```text
projection_version
site_id
```

Fields:

```text
projection_revision

fast_checkpoint_started_at

fast_checkpoint_cycle_id

source_watermark_utc

projection_watermark_utc

last_incremental_scan_at

last_reconcile_at

reconcile_cursor_started_at

reconcile_cursor_cycle_id

last_success_at

status

last_error_category
```

Checkpoint is an acceleration aid.

It is NOT proof that no older/late source evidence exists.

---

# 25. Proposed table — source cycle projection

Conceptual:

```text
traffic_projection_cycles
```

Primary key:

```text
projection_version
site_id
cycle_id
```

Required source identity/provenance:

```text
source_kind

cycle_id

started_at

finished_at

state

complete

result

source_updated_at

source_fingerprint

projected_at
```

---

# 26. Materialized cycle integrity facts

The cycle projection must persist enough validated facts to avoid repeating raw
AP-table integrity work.

Conceptual:

```text
integrity_ok

stored_row_count

source_rows_reported

items_seen

items_stored

items_skipped

error_count

data_quality_warning_count

bad_site_count

bad_mac_count

duplicate_mac_count

bad_flag_count

bad_rate_count

bad_time_count
```

Exact private field set may be optimized, but public semantics must remain
reconstructable.

---

# 27. Materialized source-family Site facts

For each canonical/validated cycle retain BOTH families.

Conceptual:

```text
wired_complete

lan_complete

wired_pair_count

lan_pair_count

wired_oldest_at

wired_newest_at

lan_oldest_at

lan_newest_at

wired_download_mbps

wired_upload_mbps

lan_download_mbps

lan_upload_mbps
```

Do NOT persist only one selected family.

---

# 28. Materialized rate-quality facts

Retain source-family reason totals needed by existing History quality semantics:

```text
no_baseline_count

counter_reset_count

gap_too_large_count

invalid_elapsed_count

source_unavailable_count

ok_count
```

for wired/LAN as required.

This prevents raw evidence re-scan at Admin request time.

---

# 29. Attempt/noncanonical cycle projection

Historical quality currently includes source attempt state such as:

```text
partial

failed

shutdown

abandoned

running
```

Therefore the projection cannot store only accepted successful cycles.

It must retain lightweight attempt/cycle state required to reproduce existing
quality metadata.

Noncanonical attempts need not produce AP metric facts.

---

# 30. Proposed table — per-AP cycle facts

Conceptual:

```text
traffic_projection_ap_cycles
```

Primary key:

```text
projection_version
site_id
cycle_id
ap_mac
```

Required reusable facts:

```text
historical_name

wired_download_mbps
wired_upload_mbps
wired_download_reason
wired_upload_reason

lan_download_mbps
lan_upload_mbps
lan_download_reason
lan_upload_reason

wired_observed_at
lan_observed_at

validated presence/completeness provenance
```

No final AP Share fraction is stored here.

---

# 31. Why AP Share itself should NOT be an independent persisted truth

AP Share is range-dependent:

```text
AP_WEIGHT / SITE_WEIGHT
```

and also has current-population enrichment/completeness semantics.

Persisting a standalone Share table risks:

```text
separate truth

stale denominator

stale current population

formula drift from Traffic by AP
```

Therefore wave 1 should persist:

```text
the shared AP contribution primitives
```

and derive Share cheaply from the SAME request-level projected AP weights used by
Traffic by AP.

---

# 32. Request-level canonical range assembly

Introduce one internal projected-range primitive, working name:

```text
ProjectedHistoricalTrafficRange
```

or:

```text
ProjectedRangeSelection
```

For one Site/range request it performs:

```text
read compact projected cycles

assign request-relative bucket_index

run existing bucket source-family selection

select Site samples

classify period intervals

read projected AP rows only for selected cycles

build shared AP contribution weights
```

This happens from projection DB, not raw Observation DB.

---

# 33. Shared semantic relationship — History

`Network Traffic History` consumes:

```text
ProjectedRangeSelection.bucket facts
```

and returns the same:

```text
network_traffic_history.v1
```

bucket DTOs.

Current:

```text
aggregation =
mean_of_complete_site_rate_samples
```

must remain unchanged.

---

# 34. Shared semantic relationship — Period Statistics

Period Statistics MUST use the same:

```text
ProjectedRangeSelection.selected samples
+
interval classification
```

as History.

Average remains:

```text
right_endpoint_sample_hold_time_weighted.v1
```

No second raw recomputation.

No separate independent source selection.

---

# 35. Shared semantic relationship — Traffic by AP

Traffic by AP uses:

```text
the same bucket selected_source
```

for every AP in that bucket.

Historical AP facts come from:

```text
traffic_projection_ap_cycles
```

not raw AP rows.

Existing AP identity/population/quality semantics remain unchanged.

---

# 36. Shared semantic relationship — AP Traffic Share

AP Share consumes the SAME:

```text
Site accepted interval basis

AP accepted interval basis

ap_weighted_download

ap_weighted_upload
```

created by the projected range primitive used by Traffic by AP.

Permanent:

```text
no second AP rate × elapsed pipeline
```

Existing conservation law remains mandatory.

---

# 37. Current-context facts remain current

The projection does not own:

```text
Current AP population

Current AP names

AP Now
```

Those remain with existing current Traffic owner.

Projection migration changes historical read work only.

---

# 38. Incremental source unit

Primary source unit:

```text
Observation cycle
kind=ap_dynamic
```

Normal new source event:

```text
new/updated source cycle
→ project/reproject only that cycle
→ project/reproject its AP rows
```

No full 24h/7d recalculation is needed for each new cycle.

---

# 39. Exactly-once decision

Do NOT attempt distributed exactly-once semantics.

Canonical proposed processing model:

```text
at-least-once discovery

+

idempotent transactional projection
```

A source cycle may be processed repeatedly.

The final projection rows for:

```text
projection_version + Site + cycle_id
```

must be deterministic.

---

# 40. Per-cycle atomic update

One source-cycle projection transaction should conceptually:

```text
BEGIN

validate current source cycle identity/fingerprint

upsert cycle projection

delete/replace or deterministic-upsert AP projection rows for that cycle

increment Site projection_revision if semantic content changed

update checkpoint metadata

COMMIT
```

Crash before COMMIT:

```text
no partial projection cycle
```

Replay after restart:

```text
safe
```

---

# 41. Source fingerprint

Each projected source cycle should persist:

```text
source_fingerprint
```

Deterministically derived from semantic source inputs required by projection.

It must detect relevant source correction.

Possible inputs:

```text
cycle metadata

cycle updated_at

canonical AP row identities

required Traffic/rate fields

required completeness/reason fields
```

Exact hash construction is implementation detail after review.

---

# 42. Checkpoint principle

Checkpoint is:

```text
performance optimization
```

not correctness authority.

Forbidden assumption:

```text
everything older than checkpoint can never change/appear
```

because architecture must support:

```text
late

recovered

corrected
```

source evidence.

---

# 43. Fast incremental checkpoint

Working key:

```text
(started_at, cycle_id)
```

The worker quickly discovers normal newly appended cycles after the last processed
key.

After restart it resumes from persisted checkpoint.

---

# 44. Reconciliation cursor

To catch late/older source evidence without scanning all AP rows each pass, use a
second persisted:

```text
reconciliation cursor
```

over source cycle METADATA within the projection retention horizon.

Conceptual process:

```text
scan bounded metadata chunk

compare source cycle identity/update/fingerprint marker with projection

enqueue missing/changed cycles

advance reconciliation cursor

wrap after horizon end
```

This guarantees eventual coverage independent of the fast checkpoint.

---

# 45. Why metadata reconciliation is acceptable

Reconciliation scans:

```text
observation_cycles metadata
```

not full historical:

```text
ap_observations reconstruction
```

for every Admin request.

Heavy AP reads occur only for:

```text
new

changed

missing

explicit rebuild
```

cycles.

---

# 46. Missed-cycle recovery

If the worker was down:

```text
raw Observation continues accumulating
```

On restart:

```text
read persisted projection state

discover source head

process backlog incrementally

reconciliation cursor eventually proves retained horizon coverage
```

No full rebuild is required merely because of process restart.

---

# 47. Late cycle handling

Late source cycle inside projection retention:

```text
metadata reconciliation discovers missing cycle

→ project cycle

→ increment projection_revision

→ update projection/source watermark as appropriate

→ invalidate affected RAM cache entries
```

Because final buckets are request-relative, no fixed persisted bucket repair is
required in v1.

---

# 48. Corrected source cycle handling

If an already projected cycle changes semantically:

```text
fingerprint mismatch
```

then:

```text
reproject exactly that cycle/AP rows atomically

increment projection_revision

invalidate affected hot cache

record correction telemetry
```

No silent stale row.

---

# 49. Previously incomplete → valid handling

If a cycle previously projected as:

```text
running
partial
failed
incomplete
```

later becomes:

```text
canonical valid complete success
```

the same source cycle identity is reprocessed.

It may then gain:

```text
Site source-family metric facts

per-AP projection rows
```

No duplicate cycle.

---

# 50. Valid → invalid/corrected handling

If source correction makes previously usable evidence no longer canonical:

```text
cycle projection is updated

AP metric rows for that cycle are removed/invalidated

attempt provenance remains
```

Projection must never retain a metric fact that raw accepted source no longer
supports.

---

# 51. Reconciliation sweep freshness

Site state should retain:

```text
last_reconcile_at
```

and:

```text
reconciliation_sweep_age
```

Admin freshness can distinguish:

```text
source head caught up

but safety reconciliation overdue
```

from fully healthy projection.

Exact DRAFT statuses follow below.

---

# 52. Projection retention model

Wave 1 maximum product range:

```text
7 days
```

Recommended projection retention:

```text
14 days
```

Working rationale:

```text
2 × maximum served product range

one full extra 7d safety horizon for catch-up/reconciliation/rebuild overlap
```

Raw Observation dynamic retention currently remains much longer.

Projection retention MUST NOT become the only surviving historical truth.

---

# 53. Retention invariant

Required:

```text
projection retention
<=
authoritative raw evidence retention
```

for any range expected to be fully rebuildable.

Current raw Observation dynamic retention default is:

```text
180 days
```

Wave 1 14d projection therefore remains fully rebuildable from retained raw
evidence under current defaults.

---

# 54. Projection retention cleanup

Cleanup deletes derived rows only.

It MUST NOT delete raw source evidence.

Version-aware cleanup:

```text
active version

building version

temporary rollback version
```

must be safe.

Do not delete a version still required for rollback/rebuild validation.

---

# 55. Full rebuild

Supported operation:

```text
REBUILD ALL SITES / ACTIVE RETENTION HORIZON
```

Semantics:

```text
create/clear target projection version

read authoritative raw source

recompute derived cycle/AP projection

validate

mark ready

never mutate raw evidence
```

---

# 56. Site rebuild

Supported:

```text
REBUILD Site X
```

Only target Site rows/version are replaced.

Other Sites continue serving from their projection.

Site isolation is preserved.

---

# 57. Range rebuild

Supported:

```text
REBUILD Site X / source-time range
```

Reprojects source cycles whose semantic source identity falls in the selected
source window.

Because durable rows are source-neutral per-cycle facts, range rebuild does not
need to precompute every possible request bucket.

---

# 58. Product rebuild

Wave 1 durable primitives are shared.

Therefore:

```text
History rebuild

Statistics rebuild

AP Share rebuild
```

do not normally rebuild separate persisted product tables.

A "product rebuild" means one of:

```text
invalidate product RAM cache

re-evaluate shared projection compatibility

build a new projection_version if product-required primitive semantics changed
```

---

# 59. Version rebuild

Recommended safe metric/projection formula change:

```text
build v2 side-by-side

backfill from raw

run exact parity/new-semantic tests

switch active pointer

keep v1 temporarily

retire later
```

Never mutate v1 semantics in place.

---

# 60. Rebuild execution isolation

Rebuild must be:

```text
lower priority than source acquisition

lower priority than portal authorization

bounded

interruptible

restartable
```

Projection rebuild failure must not affect:

```text
Observation

Current State

Visit Lifecycle

Portal authorization
```

---

# 61. Worker topology

Architect recommendation:

```text
separate traffic-projection process/service
```

Working service:

```text
traffic-projection.service
```

Reason:

```text
strong failure isolation

independent restart

independent resource limits

portal process does not own catch-up loop
```

This is DRAFT, not implementation authorization.

---

# 62. Worker input

Worker reads:

```text
Observation DB
```

read-only.

Worker writes:

```text
traffic_projection.sqlite3
```

only.

No Omada call.

No source DB write.

---

# 63. Worker scheduling

Recommended polling/reconciliation model:

```text
frequent small incremental source-head scan

+

bounded rotating metadata reconciliation
```

No requirement for an event bus in v1.

Exact poll intervals should be finalized after workload measurement.

---

# 64. Projection freshness fields

Every Site/version projection state should expose at least:

```text
source_watermark_utc

projection_watermark_utc

last_processed_at

last_reconcile_at

projection_revision

backlog_cycle_count or bounded backlog estimate

lag_seconds
```

These are internal/read provenance.

---

# 65. Watermark meanings

```text
source_watermark_utc
=
latest source evidence time currently visible to the worker
under the canonical source scope.
```

```text
projection_watermark_utc
=
latest source evidence time represented in the active projection.
```

Watermark alone does NOT prove no older late evidence exists.

That is why:

```text
last_reconcile_at
```

is separate.

---

# 66. Proposed projection status model

Working DRAFT:

```text
healthy

catching_up

stale

unavailable

rebuilding

diverged
```

Definitions must be finalized after worker cadence/PERF evidence.

---

# 67. `healthy`

Conceptually:

```text
active projection version ready

projection DB readable

lag within accepted freshness budget

no known unresolved source/projection divergence

reconciliation sweep sufficiently recent
```

Admin may serve migrated products normally.

---

# 68. `catching_up`

Conceptually:

```text
projection is valid/readable

worker is behind source

progress is occurring

lag has not crossed stale/fail-safe threshold
```

Admin may:

```text
serve projection with explicit lag/provenance
```

only if product freshness rules approve.

No fabricated "fresh" status.

---

# 69. `stale`

Projection is internally valid but beyond accepted freshness.

Admin must not present it as fresh historical state.

Wave 1 should prefer:

```text
explicit stale/partial/unavailable product status
```

over silent raw fallback.

---

# 70. `unavailable`

Examples:

```text
projection DB unreadable

active version missing

worker state structurally unavailable

projection source dependency unavailable for required catch-up
```

Admin does not rebuild raw history inside the request.

---

# 71. `rebuilding`

Active serving version may remain available while a new version/site rebuild occurs.

If rebuilding the only available version:

```text
Admin gets explicit rebuilding/unavailable semantics
```

not on-demand raw reconstruction.

---

# 72. `diverged`

Projection audit detects contradiction with authoritative raw evidence.

Required:

```text
projection loses trusted-serving eligibility for affected Site/version

telemetry raises high-priority condition

rebuild/reconciliation required
```

No silently served conflicting projection.

---

# 73. Automatic raw fallback decision

Architect recommendation:

```text
NO automatic demand-time raw fallback
after projection read path is activated.
```

Reason:

```text
automatic fallback recreates the expensive path unpredictably

creates dual production truth paths

hides projection failure

makes PERF/load behavior non-deterministic
```

Rollback to old raw path remains an explicit feature-controlled operational action
during migration.

---

# 74. RAM cache role

RAM cache is:

```text
OPTIONAL
```

and:

```text
NON-AUTHORITATIVE
```

Recommended wave 1:

```text
do not require RAM cache for correctness or PERF acceptance.
```

Add only if profiling shows additional benefit.

---

# 75. Safe RAM cache candidates

Possible:

```text
recent compact projected cycle slice

recent Site+range ProjectedRangeSelection

recent serialized History/Statistics payload
```

Cache key MUST include at least:

```text
Site

projection_version

projection_revision

absolute range

product/projection set
```

AP Share cache must also consider current-population provenance if cached.

---

# 76. Cache invalidation

Any semantic projection change increments:

```text
projection_revision
```

Cache entries from previous revision become invalid.

Restart:

```text
RAM cache empty

→ read durable projection

→ optionally repopulate
```

No raw rebuild required.

---

# 77. Network Traffic History migration

Current expensive raw cycle validation moves to worker.

Normal History read:

```text
read projected cycle facts for requested Site/range

→ assign request-relative buckets

→ choose selected source per existing formula

→ aggregate prepared Site rates

→ existing DTO
```

No raw AP table scan.

No metric/version change.

---

# 78. History evidence preservation

Must preserve exactly:

```text
bucket count

bucket boundaries

selected_source

selection_reason

complete/partial/none

complete sample counts

source quality reason counts

source skew behavior

source transition behavior

source watermark semantics
```

Projection implementation must prove exact parity against the existing raw path.

---

# 79. Period Statistics migration

Statistics MUST consume the SAME request-level selected projected samples as
History.

Then:

```text
candidate intervals

accepted intervals

gap exclusions

source-transition exclusions

weighted D/U

Average

Min/Max/Peak inputs
```

come from one canonical projected range assembly.

No separate raw SQL truth.

---

# 80. Statistics invariants

Exact existing:

```text
right_endpoint_sample_hold_time_weighted.v1
```

remains unchanged.

Existing Period interval evidence identity remains mandatory.

History and Statistics cannot select different source families for the same
Site/range/bucket context.

---

# 81. Traffic by AP migration

AP historical reads use:

```text
traffic_projection_ap_cycles
```

plus the SAME bucket selected_source from Site projected range.

No raw historical AP reconstruction at Admin request-time.

Historical AP population remains derived from validated projected historical AP
presence under existing rules.

---

# 82. AP current enrichment

Current:

```text
Now
current AP population
current AP name
```

remain owned by existing current Traffic service.

Projection does not persist current facts as historical truth.

---

# 83. AP Traffic Share migration

Share uses the same projected AP interval/contribution basis as Traffic by AP.

No independent persisted fraction.

No second source-selection path.

No second weight pipeline.

Existing:

```text
AP_WEIGHT_D
AP_WEIGHT_U
SITE_WEIGHT_D
SITE_WEIGHT_U
```

identities/conservation remain mandatory.

---

# 84. Share conservation

Before division, exact existing conservation law remains:

```text
SITE_WEIGHT_k
=
fsum(AP_WEIGHT_(a,k))
```

within the existing accepted tolerance.

Projection must not introduce renormalization.

Projection mismatch causing conservation failure:

```text
fail closed
```

---

# 85. Projection-native read API impact

Public Admin HTTP endpoints and response DTOs should remain unchanged for wave 1.

Recommended internal replacement:

```text
HistoricalTrafficReadService
    raw gateway path
```

→

```text
HistoricalTrafficReadService
    projection reader path
```

under migration feature control.

Browser should not need to know storage changed.

---

# 86. Public provenance

Existing public:

```text
metric_version
source_kind
method identifiers
```

remain stable unless an explicit public provenance field is separately approved.

Internal/telemetry may expose:

```text
projection_version
projection_revision
projection lag
```

without changing product meaning.

---

# 87. Historical Traffic broker — default decision

Do NOT remove or relax:

```text
TrafficHistoricalRequestBroker

max historical HTTP in-flight=1

10-second Historical Request Admission Guard
```

inside this foundation TASK.

They remain frozen during migration.

---

# 88. Why broker protections remain initially

Even after materialization, they still provide:

```text
request ordering

intent coalescing

generation mapping

visibility lifecycle

error/backoff discipline

bounded concurrency
```

and protect against:

```text
rebuild state

projection catch-up

large AP payloads

unexpected query-plan regressions
```

Performance architecture changes first.

Scheduler policy changes later, only with separate evidence/review.

---

# 89. Future broker simplification

After projection migration production evidence demonstrates cheap stable reads, a
separate future TASK MAY reassess:

```text
10s admission guard

max historical in-flight
```

This DRAFT does not authorize that change.

---

# 90. Current ALL24 / Peak Load compatibility issue

Current historical Traffic orchestration can request:

```text
History
Statistics
Peak
Traffic by AP
AP Share
```

together.

Wave 1 product list does NOT nominate Peak Load for migration.

This creates a residual architecture question.

---

# 91. Peak compatibility — Option A

Keep Peak on raw demand-time path.

Advantages:

```text
strict wave-1 scope
```

Disadvantage:

```text
normal combined request may still trigger expensive raw historical reconstruction
```

This partially defeats the primary performance goal.

---

# 92. Peak compatibility — Option B

Allow Peak Load to consume the same projected selected sample/interval primitive
as a compatibility consumer.

Public Peak product semantics remain unchanged.

It is not redesigned.

Advantages:

```text
normal combined request can avoid raw history reconstruction entirely
```

Disadvantage:

```text
technically shifts Peak's internal read source in wave 1
```

Architect recommendation:

```text
Option B is preferable
IF Owner + Tech Lead allow Peak as a compatibility consumer,
not a separately redesigned product.
```

This is an explicit review question.

---

# 93. Worker failure isolation

If projection worker stops:

```text
Portal authorization continues

Observation acquisition continues

Current State continues

Visit Lifecycle continues

raw source evidence continues accumulating
```

Projection DB stops advancing.

Admin migrated historical products show:

```text
lag / catching_up / stale / unavailable
```

according to the frozen future contract.

---

# 94. Projection DB failure isolation

Projection corruption/unavailability must NOT:

```text
corrupt Observation

stop Observation collector

stop Current State

stop Visit Lifecycle

stop Portal authorization
```

Optional migrated Admin products become unavailable.

---

# 95. Source DB failure

If Observation source unavailable:

```text
worker cannot advance

existing durable projection remains intact

lag grows

freshness status degrades
```

Projection does not fabricate new source watermark.

---

# 96. Projection reconciliation audit

In addition to normal incremental processing, architecture should support
periodic integrity audit:

```text
projected source identity/fingerprint
vs
authoritative source metadata/facts
```

A sampled deep audit may be used between full reconciliations.

Any mismatch:

```text
reproject
or
mark diverged
```

according to safety classification.

---

# 97. Initial build

First activation of worker:

```text
projection DB initialized

target projection_version enters building

backfill configured retention horizon from raw

query-plan/capacity monitored

mark ready only after complete build validation
```

Admin remains on existing raw path during build.

---

# 98. Migration activation separation

Foundation worker activation and Admin read-path migration are separate steps.

Required sequence:

```text
deploy code / worker OFF / Admin raw

→ dormant acceptance

→ activate projection worker

→ build/catch up

→ projection acceptance + parity

→ separately activate Admin projection reads
```

No one-step cutover.

---

# 99. Recommended feature/config controls

Working DRAFT:

```text
TRAFFIC_PROJECTION_ENABLED=false
```

controls materialization worker.

Separate read-path migration control:

```text
WEB_ADMIN_TRAFFIC_PROJECTION_READ_ENABLED=false
```

or equivalent.

Exact names require review.

A single flag should preferably switch the shared migrated historical foundation
rather than allow incompatible per-product truth paths.

---

# 100. Why one shared read-path switch is preferred

History/Statistics/AP/Share share one semantic foundation.

Independent source flags could create:

```text
History from projection

Statistics from raw

AP from projection

Share from raw
```

which increases semantic drift risk.

Recommended:

```text
migrate the shared historical foundation atomically
```

for the accepted product bundle.

---

# 101. Shadow parity mode

Before Admin cutover, projection must be compared against the current raw path.

Do NOT run expensive dual computation on every production Admin request by
default.

Preferred:

```text
controlled Lab parity

offline/diagnostic parity command

bounded sampled production parity if explicitly approved
```

No permanent duplicate demand-time load.

---

# 102. Required exact parity dimensions

For fixed:

```text
Site
from/to
evaluated_at
bucket_seconds
product set
current AP context where applicable
```

raw vs projected result must match:

```text
status

range

buckets

selected_source

selection_reason

coverage

quality

Period Statistics

Traffic by AP

AP Traffic Share

population/provenance

null/zero behavior

weights/conservation
```

within exact existing numeric tolerances.

---

# 103. Projection source revision

Site/version state has monotonic:

```text
projection_revision
```

Increment only when durable semantic projection content changes.

Admin read transaction can return/use one revision internally.

This supports:

```text
coherent cache key

telemetry

same-request consistency
```

---

# 104. Read consistency

One historical projection request should use:

```text
one read-only SQLite transaction / coherent projection DB snapshot
```

for:

```text
cycle projection

attempt quality

AP projection

site state/revision
```

Current AP context may still come from its own current owner as already designed.

---

# 105. Source/projection watermark in Admin semantics

Existing historical products already expose source watermark/age semantics.

Migration must preserve their meaning.

Do NOT redefine existing public:

```text
source_watermark_utc
source_age_seconds
```

to mean projection worker time.

Projection-specific lag is separate internal/telemetry provenance.

---

# 106. Projection freshness vs Traffic source freshness

Important distinction:

```text
Traffic source freshness
=
freshness of accepted Observation evidence

Projection freshness
=
how current the derived projection is relative to that source
```

Both can independently degrade.

No conflation.

---

# 107. Proposed internal freshness DTO

Working internal:

```text
projection_health: {
    status,
    projection_version,
    projection_revision,
    source_watermark_utc,
    projection_watermark_utc,
    lag_seconds,
    last_processed_at,
    last_reconcile_at,
    backlog_cycle_count,
}
```

Not necessarily public API.

---

# 108. Initial freshness budget proposal

Current AP dynamic source cadence is substantially shorter than one minute.

Working target:

```text
healthy projection lag <= 90 seconds
```

Working states:

```text
healthy:
lag <= 90s and reconciliation current

catching_up:
lag >90s but worker advancing and still within safe serving policy

stale:
lag beyond accepted serving threshold

unavailable:
projection cannot be safely read

rebuilding:
known rebuild state

diverged:
raw/projection contradiction
```

Exact stale threshold remains an Owner + Tech Lead review item.

---

# 109. Incremental update PERF objective

Steady state new terminal/corrected cycle:

```text
source discovery
+
projection transaction
```

should be cheap enough to remain comfortably ahead of source arrival cadence.

DRAFT candidate gate:

```text
per-cycle projection update
p95 <= 250 ms
max <= 1.0 s
```

measured without worker sleep.

This is a proposal, not FINAL.

---

# 110. Catch-up PERF objective

Candidate backlog fixtures:

```text
1h

24h

7d
```

of retained AP dynamic source cycles.

DRAFT objectives per Site:

```text
1h backlog:
<= 10s

24h backlog:
<= 60s

7d backlog:
<= 5min
```

while portal/acquisition continue normally.

Must validate on production-size AP count/source density.

---

# 111. Admin projection-read PERF objective

Normal projection-backed Admin historical reads should primarily be:

```text
indexed projection reads
+
light range assembly
+
serialization
```

DRAFT gates:

```text
24h combined migrated product request:
p95 <= 1.0s
max <= 1.5s

7d combined migrated product request:
p95 <= 1.5s
max <= 2.0s
```

Exact product bundle must be frozen after Peak compatibility decision.

---

# 112. Full rebuild PERF objective

DRAFT target for one Site / 14d projection horizon:

```text
full rebuild <= 10 minutes
```

while:

```text
Portal authorization remains healthy

Observation acquisition remains healthy
```

A more aggressive target may be established by benchmark.

Correctness takes priority over rebuild speed.

---

# 113. Rebuild resource controls

Rebuild must have bounded:

```text
batch size

transaction duration

sleep/yield policy

SQLite busy handling

CPU utilization

memory
```

No single giant transaction across full retention.

---

# 114. Projection DB storage capacity model

At current AP dynamic cadence, durable cycle projection stores:

```text
one compact Site cycle row per AP dynamic cycle

+
one compact AP row per AP per cycle
```

Wave 1 retention is bounded.

Capacity benchmark must test at least:

```text
1 Site / 12 supported APs / 14d
```

even though current deployment has fewer APs.

---

# 115. Storage budget proposal

DRAFT acceptance target:

```text
14d projection DB
at 12 AP supported population
<= 2 GiB
```

This is intentionally generous.

If exceeded:

```text
profile row/index design
```

before increasing budget.

No raw JSON blobs should be duplicated into projection.

---

# 116. Projection DB indexes — proposed

Expected indexes should be projection-local.

Conceptual:

```text
cycles:
(projection_version, site_id, finished_at, cycle_id)

cycles:
(projection_version, site_id, started_at, cycle_id)

cycles:
(projection_version, site_id, state, result, started_at)

AP facts:
(projection_version, site_id, ap_mac, finished_at/cycle relation)

AP facts:
(projection_version, site_id, cycle_id, ap_mac)
```

Exact schema/index set must follow EXPLAIN QUERY PLAN.

No raw-source index change by default.

---

# 117. Security / file ownership

Projection DB contains:

```text
Site identifiers

AP MACs

AP names

historical Traffic facts
```

It is sensitive Admin telemetry.

File permissions should follow CaptivPortal data storage security conventions.

No world-readable DB.

---

# 118. Site isolation

Every projection primary/query key includes:

```text
site_id
```

Worker processes only configured Sites.

Admin:

```text
authorizes canonical Site first

reads only that Site projection
```

No cross-Site fallback.

---

# 119. Projection telemetry

Safe worker telemetry:

```text
projection_version

site_id

status

projection_revision

source_watermark

projection_watermark

lag_seconds

backlog_cycle_count

cycles_examined

cycles_projected

cycles_replayed

cycles_corrected

cycles_invalidated

reconcile_progress

rebuild_progress

duration_ms

projection_db_bytes

error_category
```

---

# 120. Telemetry privacy

Do NOT log:

```text
AP MAC lists

AP names

raw rate arrays

raw SQL

full source rows

DB contents

secret paths if current logging policy forbids them
```

Per-cycle ID logging should be debug-only if needed and safe.

---

# 121. Divergence telemetry

High-severity event:

```text
traffic_projection_divergence_detected
```

Safe fields:

```text
Site
projection_version
source cycle time
reason class
```

No raw source payload.

---

# 122. Operational status endpoint

A future internal/Admin health projection may expose aggregate state.

This TASK does NOT require a public new user-facing page.

At minimum operations must be able to inspect:

```text
worker active

version

watermarks

lag

last reconcile

rebuild status

last safe error
```

---

# 123. Deployment phase 0 — code dormant

Deploy foundation code:

```text
FROM GIT
```

with:

```text
TRAFFIC_PROJECTION_ENABLED=false

WEB_ADMIN_TRAFFIC_PROJECTION_READ_ENABLED=false
```

No projection worker activity.

No Admin semantic change.

---

# 124. Dormant acceptance

Required:

```text
captive-portal.service healthy

Observation healthy

Current State healthy

Visit Lifecycle healthy

all current Traffic products healthy

no projection DB write workload

no projection worker active

no Traffic API/DTO change
```

---

# 125. Deployment phase 1 — worker activation

Separate Owner-controlled activation:

```text
TRAFFIC_PROJECTION_ENABLED=true
```

Admin remains:

```text
raw historical read path
```

Worker:

```text
creates/opens derived DB

builds projection

catches up

reconciles
```

No product cutover yet.

---

# 126. Worker acceptance

Before Admin migration:

```text
projection version ready

lag healthy

reconciliation PASS

restart recovery PASS

idempotent replay PASS

late-cycle recovery PASS

correction replay PASS

full rebuild PASS

source DB immutability PASS

projection DB integrity PASS
```

---

# 127. Deployment phase 2 — parity

Run mandatory parity suite:

```text
raw historical result
vs
projection-backed result
```

for:

```text
24h

7d

quality edge fixtures

source transitions

AP population 0/1/2/12

current AP context cases
```

No read cutover until parity PASS.

---

# 128. Deployment phase 3 — Admin projection cutover

Separate Owner authorization enables:

```text
WEB_ADMIN_TRAFFIC_PROJECTION_READ_ENABLED=true
```

Existing public:

```text
routes

products

DTOs

UI
```

remain the same.

Only internal historical read source changes.

---

# 129. Rollback

Primary read-path rollback:

```text
WEB_ADMIN_TRAFFIC_PROJECTION_READ_ENABLED=false
```

returns migrated products to existing raw path during the migration period.

Worker may remain active.

Worker rollback:

```text
TRAFFIC_PROJECTION_ENABLED=false
```

stops materialization.

Existing raw evidence continues.

---

# 130. Projection DB rollback

Because projection DB is derived:

```text
it may be deleted/recreated
```

only through controlled rebuild procedure.

No raw DB rollback is required.

No projection rollback may mutate Observation.

---

# 131. Rebuild after corruption

Procedure:

```text
disable projection read cutover

stop/quiesce projection worker if required

create clean target version/DB

rebuild from raw

verify

reactivate worker

parity

restore projection read cutover
```

Raw path remains operational rollback until migration is fully accepted.

---

# 132. NO-TOUCH — Observation

No change in foundation DRAFT to:

```text
Observation collector

Omada polling

Observation schema

Observation raw rate formulas

Observation source retention

source AP dynamic semantics
```

A projection implementation may only READ accepted source evidence.

---

# 133. NO-TOUCH — Current State / TRAFFIC-07

No change to:

```text
Current State

CurrentGuestTrafficReadService

Online Guests Traffic

TRAFFIC-07 semantics
```

---

# 134. NO-TOUCH — Visit Lifecycle / TRAFFIC-08

No Visit changes.

TRAFFIC-08 remains frozen.

No completed-session Traffic implementation during Projection Foundation.

---

# 135. NO-TOUCH — Public Traffic

No changes to:

```text
public traffic counter

public_traffic.sqlite3

public Traffic semantics
```

---

# 136. NO-TOUCH — public metric semantics

No changes merely because of materialization to:

```text
History meaning

Statistics formulas

Traffic by AP meaning

AP Share formulas

null/zero semantics

source selection rules

quality rules

AP population rules
```

---

# 137. NO-TOUCH — historical broker contracts

During this foundation migration:

```text
max historical in-flight = 1

10s admission guard
```

remain unchanged.

Any relaxation is a later separate architecture task.

---

# 138. Migration phase A — projection storage foundation

Scope:

```text
derived DB schema

version tables

Site state

cycle projection

AP cycle projection

read-only projection gateway

tests
```

No worker activation.

No Admin change.

---

# 139. Migration phase B — projection worker

Scope:

```text
incremental scan

idempotent transaction

checkpoint

reconciliation cursor

restart recovery

retention cleanup

rebuild commands

health/telemetry
```

Still no Admin cutover.

---

# 140. Migration phase C — raw/projection parity reader

Build:

```text
projection-backed range assembly
```

inside Analytics domain.

Run against existing raw `HistoricalTrafficReadService` semantics.

No UI change.

---

# 141. Migration phase D — History + Statistics consumption

Switch shared historical range primitive internally to projection after parity.

Public output unchanged.

If the architecture uses one atomic shared read cutover, AP consumers may switch
in the same accepted candidate rather than separate commits.

---

# 142. Migration phase E — Traffic by AP + AP Share

Consume the same projected range/source-selection/AP-contribution primitive.

Share conservation/parity mandatory.

---

# 143. Migration phase F — Peak compatibility

Depends on Owner + Tech Lead decision:

```text
compatibility consumer of projection
```

or:

```text
legacy raw residual consumer
```

Must be resolved before claiming that normal historical Admin page opening no
longer performs heavy raw reconstruction.

---

# 144. Migration phase G — production read cutover

Only after:

```text
worker production healthy

projection parity

Central Lab

Linux PERF

dormant product behavior

Owner activation
```

---

# 145. Acceptance gate — source truth

Must prove:

```text
projection DB deletion does not delete raw evidence

projection rebuild from raw reproduces accepted projection

raw/projection divergence fails safe

projection never writes Observation
```

---

# 146. Acceptance gate — idempotency

Repeatedly process same source cycle:

```text
1x
2x
10x
```

Expected:

```text
identical projection rows

no duplicate AP rows

same semantic revision unless source meaning changed
```

---

# 147. Acceptance gate — restart

Kill worker:

```text
before cycle transaction

during cycle transaction

after transaction before checkpoint advance
```

Restart:

```text
no partial cycle

replay safe

projection catches up
```

---

# 148. Acceptance gate — late/recovered evidence

Fixtures:

```text
late older cycle

running → complete

partial → valid

failed → corrected/new valid state as supported by source lifecycle

missing projected cycle behind fast checkpoint
```

Must be discovered through reconciliation.

---

# 149. Acceptance gate — source correction

Change source evidence in controlled fixture.

Expected:

```text
fingerprint/update detected

cycle reprojected

AP rows replaced safely

projection_revision advances

cached data invalidated

parity restored
```

---

# 150. Acceptance gate — source retention

Projection cleanup:

```text
does not delete source

does not retain unsupported orphan references incorrectly

preserves full 7d product read horizon
```

Rebuild from current raw retention succeeds.

---

# 151. Acceptance gate — exact History parity

For canonical fixtures and production-size immutable snapshot:

```text
raw History DTO
==
projection-backed History DTO
```

except any explicitly internal/non-public projection provenance.

No changed bucket/source/quality semantics.

---

# 152. Acceptance gate — Statistics parity

Exact:

```text
Average

Min

Max

interval evidence

accepted seconds

gap counts

source-transition counts

peak inputs where shared
```

must match current raw semantics.

---

# 153. Acceptance gate — Traffic by AP parity

Exact:

```text
population

MAC identity

display provenance where historical

bucket series

Average

coverage

weighted contribution facts

quality/null behavior
```

must match.

---

# 154. Acceptance gate — AP Share parity

Exact:

```text
D Share

U Share

Total Share

range presence

population

source/current provenance

conservation

null/zero semantics
```

must match.

No independent normalization.

---

# 155. Acceptance gate — Site isolation

Site A source/project/rebuild/read must never expose Site B:

```text
cycle facts

AP facts

watermarks

cache

status

payload
```

---

# 156. Acceptance gate — worker failure isolation

Stop projection worker for controlled period.

Prove:

```text
Portal auth works

Observation continues

Current State continues

Visit Lifecycle continues

raw evidence accumulates

projection lag grows

restart catches up
```

---

# 157. Acceptance gate — full rebuild

Delete target derived projection version.

Rebuild from raw retained source.

Prove:

```text
same final projection fingerprint/semantic result

source DB unchanged

Admin raw path unaffected
```

---

# 158. Acceptance gate — query plan

Projection-backed reads must use projection indexes.

Forbidden normal read:

```text
full raw ap_observations reconstruction
```

for migrated products.

Raw source may be consulted only for:

```text
worker

rebuild

explicit parity/audit
```

---

# 159. Acceptance gate — Admin read PERF

Final gates must be evidence-backed.

Initial proposed target:

```text
24h combined projection-backed migrated request:
p95 <= 1.0s
max <= 1.5s

7d:
p95 <= 1.5s
max <= 2.0s

>=10 measured runs
```

No query deadline increase.

---

# 160. Acceptance gate — projection update PERF

Initial proposal:

```text
single new cycle projection:
p95 <=250ms
max <=1s
```

Must include:

```text
Site cycle fact

AP cycle facts

transaction/checkpoint
```

No source write.

---

# 161. Acceptance gate — catch-up

Measure at least:

```text
1h backlog

24h backlog

7d backlog
```

Initial goals:

```text
1h <=10s

24h <=60s

7d <=5min
```

while acquisition/portal remain healthy.

---

# 162. Acceptance gate — storage

14d / 12 AP capacity fixture.

Initial budget:

```text
projection DB <=2 GiB
```

No raw JSON duplication.

WAL/checkpoint behavior bounded.

---

# 163. Acceptance gate — Central Lab

Official Central Lab:

```text
PASS

strict regressions=0
```

on exact candidate.

Coder does not self-certify.

---

# 164. Acceptance gate — production dormant

Before worker activation:

```text
no behavior change
```

Before Admin read cutover:

```text
projection worker can run without changing existing products
```

Both are separate gates.

---

# 165. Risks — semantic duplication

Biggest risk:

```text
projection code reimplements Historical Traffic formulas differently
from raw service
```

Mitigation:

```text
extract/reuse canonical validation/source-selection primitives where safe

golden raw-vs-projection parity

do not create product-specific second formulas
```

---

# 166. Risks — source-relative bucket semantics

Fixed precomputed buckets would be attractive but can change source selection.

Mitigation:

```text
v1 materializes source-neutral validated cycle/AP facts

request-relative bucket/source selection remains canonical lightweight assembly
```

This is a deliberate architecture decision.

---

# 167. Risks — checkpoint data loss

Fast checkpoint can miss late old cycles.

Mitigation:

```text
checkpoint never correctness authority

bounded rotating metadata reconciliation

source fingerprints

rebuild operation
```

---

# 168. Risks — projection lag hidden from Admin

Mitigation:

```text
explicit projection health/watermarks/lag

no silent stale-as-fresh

no automatic hidden raw fallback
```

---

# 169. Risks — projection version mismatch

Mitigation:

```text
projection_version separate from metric_version

side-by-side build

active version pointer

fail closed on incompatible source/schema/version
```

---

# 170. Risks — AP Share current population

AP Share includes current population provenance.

Mitigation:

```text
projection persists only historical AP primitives

current context remains query-time Current Traffic owner

Share composed from both without persisting stale current population
```

---

# 171. Risks — Peak Load residual raw reconstruction

If Peak remains raw in normal ALL24 grouping:

```text
main performance objective may be only partially achieved.
```

This requires explicit architecture decision before FINAL migration plan is
closed.

---

# 172. Open question 1 — Peak compatibility

Choose:

```text
A. Peak stays raw in wave 1

B. Peak consumes projection as compatibility consumer
```

Architect recommendation:

```text
B
```

if the goal is to remove normal Admin raw historical reconstruction.

No Peak product semantic redesign is needed.

---

# 173. Open question 2 — projection retention

Proposed:

```text
14 days
```

Accept or change?

Architect recommendation:

```text
14d
```

because maximum product range is 7d and raw source retention is currently much
longer.

---

# 174. Open question 3 — freshness thresholds

Proposed healthy lag:

```text
<=90s
```

Need freeze:

```text
healthy threshold

catching_up serving threshold

stale threshold

reconciliation-age threshold
```

after worker cadence benchmark.

---

# 175. Open question 4 — worker topology

Recommended:

```text
separate systemd service/process
```

rather than captive-portal process thread.

Accept?

Architect recommendation:

```text
YES
```

for failure isolation.

---

# 176. Open question 5 — projection DB path/name

Proposed:

```text
/opt/CaptivePortal/data/traffic_projection.sqlite3
```

Accept?

Architect recommendation:

```text
YES
```

as explicit derived-store identity.

---

# 177. Open question 6 — automatic raw fallback

Recommended:

```text
NO automatic fallback
```

Use explicit read-path rollback flag.

Accept?

Architect recommendation:

```text
YES
```

---

# 178. Open question 7 — one shared migration flag

Recommended:

```text
one shared historical projection read-path flag
```

to prevent mixed historical truths.

If Peak remains raw, internal mixed source composition requires additional review.

---

# 179. Open question 8 — RAM cache

Architect recommendation:

```text
OPTIONAL / NOT REQUIRED IN FOUNDATION ACCEPTANCE
```

Add only after projection read PERF profiling.

---

# 180. Effect on TRAFFIC-08

Frozen canonical planning:

```text
TRAFFIC-08 remains ON HOLD
```

No work is discarded.

After Projection Foundation:

```text
re-open TRAFFIC-08

preserve:
  Visit identity
  closed_at cohort
  session semantics
  source research
  evidence research

reassess:
  historical read owner integration
  whether session Traffic should be materialized
  whether Observation per-session projection belongs in a future projection
  version
```

No TRAFFIC-08 implementation is part of this TASK.

---

# 181. Proposed TASK identity

Recommended canonical candidate name:

```text
TASK-TRAFFIC-PROJECTION-01
Historical Traffic Materialized Projection Foundation
```

Alternative:

```text
Traffic Projection / Rollup Foundation
```

Architect recommendation:

```text
use "Materialized Projection"
```

because it accurately describes v1 source-neutral durable facts without implying
unsafe fixed final bucket rollups.

---

# 182. DRAFT state

```text
TASK:
TASK-TRAFFIC-PROJECTION-01

NAME:
Historical Traffic Materialized Projection Foundation

STATUS:
ARCHITECTURAL DRAFT
FOR OWNER + TECH LEAD REVIEW

TASK DEVELOPMENT PARENT:
main@e196b042515498c5cd9143a9962f6aed90f31566

TREE:
f88ee1f854135107c647ccd9d346be2b2ba504b9

AUTHORITATIVE SOURCE:
Observation persisted raw AP dynamic evidence

DERIVED STORE:
proposed traffic_projection.sqlite3

PROJECTION OWNER:
TrafficProjectionService

PROJECTION READ OWNER:
TrafficProjectionReadService

PRODUCT SEMANTIC OWNER:
HistoricalTrafficReadService remains canonical

DURABLE V1 GRAIN:
source-neutral validated cycle facts
+
per-AP cycle facts

FINAL FIXED BUCKET STORAGE:
NO v1

REQUEST-RELATIVE BUCKET SELECTION:
PRESERVED

HISTORY:
projection consumer wave 1

STATISTICS:
same projection/range selection

TRAFFIC BY AP:
same projection/AP primitives

AP SHARE:
same projected AP contribution basis

PEAK:
OPEN compatibility decision

CHECKPOINT:
optimization only

PROCESSING:
at-least-once discovery
+
idempotent transactional projection

LATE/CORRECTED SOURCE:
reconciliation + reproject

REBUILD:
full / Site / range / version

RETENTION:
proposed 14d

RAW RETENTION:
unchanged

RAM CACHE:
optional / non-authoritative

AUTOMATIC RAW FALLBACK:
recommended NO

HISTORICAL BROKER:
unchanged initially

MAX HISTORICAL IN-FLIGHT:
1 unchanged

ADMISSION GUARD:
10s unchanged

NEW COLLECTOR:
NO

OBSERVATION SCHEMA CHANGE:
NO

CURRENT STATE CHANGE:
NO

VISIT LIFECYCLE CHANGE:
NO

TRAFFIC-07 CHANGE:
NO

TRAFFIC-08:
FROZEN / ON HOLD

IMPLEMENTATION:
NOT AUTHORIZED

CODER:
NOT AUTHORIZED

PRODUCTION:
NOT AUTHORIZED
```

---

# 183. Next allowed step

Owner + Tech Lead review this architecture DRAFT.

Required review should freeze at minimum:

```text
projection grain

projection DB decision

version model

checkpoint/reconciliation model

retention

freshness thresholds

worker topology

Peak compatibility

raw fallback policy

migration flag/cutover design

PERF budgets
```

Then:

```text
DRAFT corrections if required

→ repository re-fetch/rebind

→ FINAL architecture

→ separate explicit Owner implementation authorization

→ Tech Lead decomposition

→ Coder
```

No implementation may begin from this DRAFT.
