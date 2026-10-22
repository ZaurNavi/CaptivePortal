# TASK-TRAFFIC-PARTIAL-COVERAGE-01 — ARCHITECTURE ADDENDUM R2
## Raw Observation Range Coverage Authority

**Project:** CaptivPortal  
**Parent:** `TASK-TRAFFIC-PARTIAL-COVERAGE-01-ARCHITECTURE-CONTRACT-v1-R1`  
**Type:** Narrow normative architecture clarification  
**Status:** `ARCHITECTURE HOLD / PREREQUISITE REQUIRED`  
**Prepared:** 2026-10-11  
**Architecture owner:** CaptivPortal Architect  
**Implementation authorization:** `NO`  
**Coder:** `HOLD`  
**Production change:** `NO`  
**Baseline:** `main@e8061de9fbd6da8be5cd269779070a4db4d59d64`  
**Tree:** `d5503fe1f2b5774bbe55cb2d34dba63246f56f6f`  
**Review basis:** `TASK-TRAFFIC-PARTIAL-COVERAGE-01-ARCHITECTURE-CLARIFICATION-R2-RAW-RANGE-COVERAGE`  

---

# 0. Executive disposition

The R1 architecture remains accepted in principle and is not redesigned.

The only question resolved by this addendum is:

```text
Can the current authorized CaptivPortal facts prove
raw_observation_range_covered(site_id, from_utc, to_utc, evaluated_at_utc)
for the Historical Partial Coverage overlay?
```

Final answer on the pinned baseline:

```text
NO.
```

The current Observation schema can prove that particular rows/cycles **exist**.
It cannot prove that the complete raw AP-dynamic lifecycle for an arbitrary
requested historical range is preserved without an unrecorded gap, deletion,
configuration-generation transition or storage-uncertainty interval.

Therefore the following R1 state is not safely reachable from the current
schema alone:

```json
{
  "status": "ok",
  "reason": "no_partial_measurements",
  "has_partial_measurements": false,
  "source_coverage_insufficient": false
}
```

Emitting that state from only `MIN/MAX`, current retention configuration,
strict-success history bounds, Traffic Projection bounds, or a Coder-defined
cadence heuristic is forbidden.

The architecture consequence is:

```text
TASK-TRAFFIC-PARTIAL-COVERAGE-01 main implementation = HOLD

MANDATORY PREREQUISITE =
TASK-TRAFFIC-PARTIAL-COVERAGE-01A
RAW OBSERVATION RANGE COVERAGE AUTHORITY
```

The prerequisite is a **protected Observation metadata authority**, not a new
traffic collector, not a new Omada request path and not a new traffic source.
It necessarily requires a reviewed Observation schema/writer change, because
no existing persisted object carries the missing proof.

---

# 1. Supersession scope

This R2 addendum supersedes only the raw-range-coverage assumptions in R1:

```text
§17.2-B
§17.2-E
§18 where it assumes source-range completeness can already be proved
§19
T19
T21
§40 only where acceptance depended on an unspecified raw-range proof
```

All other R1 decisions remain unchanged, including:

```text
Option 3 / combination
confirmed Offline exclusion only for aligned current status
no fake zero
no Wired/LAN mixing
historical partial overlay read-only
strict Projection statistics unchanged
no retroactive historical Offline inference
R1 partial bucket arithmetic and denominators
R1 failure-state UI semantics
feature default OFF
independent Owner approval for implementation/merge/deploy/activation
```

This R2 does not reopen NI-04 or any other DTI task.

---

# 2. Re-pinned baseline and verified source facts

Repository and production remain pinned to:

```text
HEAD = e8061de9fbd6da8be5cd269779070a4db4d59d64
TREE = d5503fe1f2b5774bbe55cb2d34dba63246f56f6f
```

Verified current Observation facts:

```text
observation_cycles schema version = v1
cycle_id = UUID/text primary key
kind = client | ap_dynamic | ap_config
site_id is persisted
state = running | completed | abandoned
result = success | partial | failed | shutdown for completed cycles
started_at / finished_at / abandoned_at are persisted
```

The schema does **not** persist:

```text
collection generation id
monotonic per-generation attempt sequence
source-scope hash on ap_dynamic cycles
AP worker configuration generation/version
raw-retention coverage watermark
contiguous-covered-from watermark
contiguous-covered-through watermark
cleanup deletion watermark
collection-break marker covering storage-unavailable attempts
```

Current indexes include:

```text
idx_cycles_site_kind_started(site_id, kind, started_at)
idx_cycles_state_started(state, started_at)
idx_ap_site_time(site_id, observed_at, row_id)
```

These support bounded retrieval, but they do not create missing semantic
authority.

Current cleanup behavior is:

```text
DELETE non-running cycles
WHERE kind is selected
AND started_at < cutoff_utc
ORDER BY started_at, cycle_id
bounded by limit
```

Deletion does not persist a raw coverage/deletion watermark.

Current AP-dynamic scheduling is fixed-delay after a run, but the persisted
cycle rows do not contain a scheduler generation or attempt sequence. The same
worker can also run AP-config work, and configuration is process/environment
configuration rather than historical per-cycle coverage metadata.

---

# 3. Why existing facts are insufficient

## 3.1 Existence is not completeness authority

A query such as:

```sql
SELECT MIN(started_at), MAX(started_at)
FROM observation_cycles
WHERE site_id=? AND kind='ap_dynamic';
```

proves only the earliest/latest currently visible row.

It does not prove:

```text
no intermediate cycle was removed
no storage failure prevented a cycle from being created
no process/config generation boundary occurred
no Site collection gap exists inside the range
no earlier retention policy removed a prefix that overlaps the range
no out-of-band mutation removed evidence
```

Therefore `MIN/MAX` alone MUST NOT establish `has_partial_measurements=false`.

## 3.2 Current retention configuration is not historical retention evidence

`dynamic_retention_days` is an active configuration value.

It does not prove that:

```text
the same retention was active for the entire requested period
cleanup actually retained all required rows
an earlier shorter retention did not remove evidence
raw storage was already initialized at range start
```

The fact that the repository default is 180 days is therefore not a range
coverage proof for a 24h or 7d request.

## 3.3 Strict History bounds are forbidden substitutes

The existing historical source bounds are derived from validated
success/complete traffic evidence.

They cannot prove preservation of partial/failed/shutdown/abandoned raw
cycles and therefore MUST NOT be reused as a raw coverage authority.

## 3.4 Traffic Projection bounds are forbidden substitutes

Traffic Projection is a derived store. Its bounds and health may prove the
projection's own usable range, but they are not an independent proof that the
raw Observation store still contains every relevant partial lifecycle fact.

## 3.5 Cadence-gap heuristics are not proof

The current AP worker interval and cycle-duration bounds are useful operational
facts, but the v1 raw rows do not persist the configuration generation that
created each interval.

A rule such as:

```text
adjacent gap < N seconds => raw range complete
```

would leave `N` semantically dependent on unrecorded historical scheduler
configuration and would not provide an authoritative deletion/attempt lineage.

R2 therefore forbids cadence-only proof on schema v1.

---

# 4. Frozen coverage-proof result model

The internal architecture result for:

```text
raw_observation_range_coverage(
    site_id,
    from_utc,
    to_utc,
    evaluated_at_utc
)
```

is the following closed enum:

```text
covered
incomplete
indeterminate
source_unavailable
capacity_limited
```

Meaning:

```text
covered
= an authoritative persisted coverage object proves the entire requested
  [from_utc,to_utc) range under one compatible AP-dynamic coverage segment.

incomplete
= authoritative evidence positively proves that at least part of the
  requested range is outside retained/continuous coverage.

indeterminate
= the source can be read, but the current authorized facts do not contain
  enough authority to prove covered or positively prove the exact gap.

source_unavailable
= the raw source / required coverage authority cannot be read or validated.

capacity_limited
= the bounded determination cannot complete inside the frozen caps/deadline.
```

On the current schema v1:

```text
covered = UNREACHABLE
```

unless and until the prerequisite in §8 is accepted and implemented.

---

# 5. Exact current-baseline decision predicate

The following is normative for R2 before the prerequisite exists.

Inputs must first satisfy:

```text
canonical site_id
from_utc < to_utc
to_utc <= evaluated_at_utc
kind = ap_dynamic
```

Then:

```text
1. If observations.sqlite3 cannot be opened/read safely,
   schema/integrity validation fails, or required tables/indexes are absent:
      => source_unavailable

2. If the local 5s overlay budget or frozen query caps are exceeded before a
   complete determination:
      => capacity_limited

3. If a successful bounded raw query proves that no target-Site ap_dynamic
   lifecycle evidence exists at or before the requested range start, while
   target-Site ap_dynamic evidence begins only after from_utc:
      => incomplete

   This is a positive boundary failure: the beginning of the requested range
   is not represented by retained target-Site raw lifecycle evidence.

4. Otherwise, with schema v1 and no protected coverage authority:
      => indeterminate

5. schema-v1 raw rows MUST NOT yield:
      => covered
```

An empty partial-cycle query by itself is never step 3 and never means
`covered`.

---

# 6. Exact wire mapping amendment to R1 §17.2

R1's top-level `partial_coverage.status` enum remains:

```text
ok
unavailable
capacity_limited
source_coverage_insufficient
```

R2 extends the closed `reason` enum by exactly one value:

```text
raw_observation_range_unproven
```

The relevant reason set is therefore:

```text
partial_measurements_present
no_partial_measurements
overlay_source_unavailable
overlay_capacity_limited
raw_observation_range_incomplete
raw_observation_range_unproven
```

## 6.1 `covered` + no admitted partial cycles

Only after prerequisite authority returns `covered` and the complete bounded
raw evaluation finds zero admitted partial cycles:

```json
{
  "status": "ok",
  "reason": "no_partial_measurements",
  "has_partial_measurements": false,
  "source_coverage_insufficient": false,
  "buckets": [],
  "bucket_count_returned": 0
}
```

`comparison_allowed` and `ap_share_allowed` are then copied from unchanged
strict eligibility exactly as R1 specifies.

## 6.2 `covered` + admitted partial evidence exists

Only after prerequisite authority returns `covered`:

```json
{
  "status": "ok",
  "reason": "partial_measurements_present",
  "has_partial_measurements": true,
  "source_coverage_insufficient": false,
  "comparison_allowed": false,
  "ap_share_allowed": false
}
```

R1 bucket arithmetic remains unchanged.

## 6.3 Positively proven incomplete raw range

Internal `incomplete` maps exactly to:

```json
{
  "status": "source_coverage_insufficient",
  "reason": "raw_observation_range_incomplete",
  "partial_cycle_count_examined": null,
  "partial_cycle_count_admitted": null,
  "partial_cycle_count_integrity_rejected": null,
  "partial_ap_rows_examined": null,
  "bucket_count_returned": 0,
  "buckets": [],
  "has_partial_measurements": null,
  "source_coverage_insufficient": true,
  "statistics_scope": "complete_coverage_intervals_only",
  "comparison_allowed": false,
  "ap_share_allowed": false
}
```

## 6.4 Indeterminate raw range proof

Internal `indeterminate` maps exactly to:

```json
{
  "status": "source_coverage_insufficient",
  "reason": "raw_observation_range_unproven",
  "partial_cycle_count_examined": null,
  "partial_cycle_count_admitted": null,
  "partial_cycle_count_integrity_rejected": null,
  "partial_ap_rows_examined": null,
  "bucket_count_returned": 0,
  "buckets": [],
  "has_partial_measurements": null,
  "source_coverage_insufficient": null,
  "statistics_scope": "complete_coverage_intervals_only",
  "comparison_allowed": false,
  "ap_share_allowed": false
}
```

This state means:

```text
The raw source is readable, but complete raw-range preservation is not proven.
```

It MUST NOT be serialized as:

```text
source_coverage_insufficient=true
```

because actual incompleteness was not positively established.

It MUST NOT be serialized as:

```text
has_partial_measurements=false
```

because absence was not proven.

## 6.5 Source unavailable

Internal `source_unavailable` remains the R1 envelope:

```json
{
  "status": "unavailable",
  "reason": "overlay_source_unavailable",
  "has_partial_measurements": null,
  "source_coverage_insufficient": null,
  "buckets": [],
  "bucket_count_returned": 0,
  "comparison_allowed": false,
  "ap_share_allowed": false
}
```

## 6.6 Capacity limited

Internal `capacity_limited` remains the R1 envelope:

```json
{
  "status": "capacity_limited",
  "reason": "overlay_capacity_limited",
  "has_partial_measurements": null,
  "source_coverage_insufficient": null,
  "buckets": [],
  "bucket_count_returned": 0,
  "comparison_allowed": false,
  "ap_share_allowed": false
}
```

---

# 7. Historical UI amendment for indeterminate proof

R1 UI copy for positively incomplete raw coverage remains unchanged.

For:

```text
status = source_coverage_insufficient
reason = raw_observation_range_unproven
```

exact visible quality copy is:

```text
Partial-coverage evidence could not be fully verified for this period.
```

Strict Average label:

```text
Average · complete-coverage intervals only · partial coverage not verified
```

Strict Peak label:

```text
Max observed with complete AP coverage · partial coverage not verified
```

Comparison copy:

```text
Comparison unavailable because partial-coverage status is not verified.
```

AP-share copy:

```text
AP share unavailable because partial-coverage status is not verified.
```

No wording may say:

```text
no partial traffic
no partial cycles
full-period coverage
whole-period Average
whole-period Peak
```

unless the prerequisite coverage authority returned `covered`.

---

# 8. Mandatory prerequisite

## 8.1 Task identity

```text
TASK-TRAFFIC-PARTIAL-COVERAGE-01A
RAW OBSERVATION RANGE COVERAGE AUTHORITY
```

This prerequisite must be separately reviewed and Owner-authorized before any
main TASK implementation resumes.

## 8.2 Purpose

Create one protected persisted authority able to prove, for AP-dynamic raw
Observation facts:

```text
Site identity
source scope/config generation
continuous collection/storage generation
retained coverage start
covered-through boundary
absence of unrecorded intermediate lifecycle loss inside the proven segment
```

## 8.3 Minimal architecture change class

Required:

```text
Observation schema change = YES
Observation writer/lifecycle metadata change = YES
```

Not required:

```text
new traffic collector = NO
new Omada request = NO
new traffic source = NO
new traffic DB = NO
Traffic Projection schema change = NO
Current State schema change = NO
packet capture = NO
```

The protected metadata stays owned by Observation Foundation in the existing
Observation persistence domain.

## 8.4 Required persisted logical contract

The prerequisite must provide a durable logical object equivalent to:

```text
RawObservationCoverageSegmentV1
```

with at least:

```text
coverage_segment_id
site_id
kind = ap_dynamic
coverage_contract_version
coverage_contract_sha256
segment_started_at
retained_from_utc
covered_through_utc
next_due_at_utc | NULL
state = active | closed | broken
break_reason | NULL
first_sequence
last_sequence
retained_first_sequence
updated_at
```

Every AP-dynamic cycle covered by the authority must additionally have a
protected association equivalent to:

```text
coverage_segment_id
coverage_sequence
```

with a strictly increasing, gap-detectable sequence inside one segment.

The physical representation may be columns plus one metadata table, or an
equivalent normalized schema, but the semantic fields/invariants above are
mandatory and are not optional implementation choices.

## 8.5 Coverage contract fingerprint

`coverage_contract_sha256` must identify the semantic configuration used to
make coverage claims.

Canonical logical content must include at least:

```json
{
  "coverage_contract_version": 1,
  "site_id": "<canonical-site-id>",
  "kind": "ap_dynamic",
  "scope": "site_ap_inventory",
  "worker_schedule": "fixed_delay_after_run.v1",
  "ap_interval_seconds": "<exact configured numeric value>",
  "dynamic_retention_days": "<exact configured integer>"
}
```

Canonical serialization for the prerequisite is:

```text
UTF-8 JSON
object keys sorted lexicographically
no insignificant whitespace
numbers serialized in one canonical project-defined form
lowercase SHA-256 hex
```

A semantic change to any included value starts a new coverage segment.

## 8.6 Segment-break rules

A new segment is mandatory after any event for which continuity cannot be
proved, including:

```text
process start/restart unless continuity is explicitly re-adopted by the
coverage authority under a separately proved handoff rule

AP-dynamic enable/disable transition
Site added/removed from Observation scope
coverage-contract fingerprint change
Observation storage write uncertainty
cycle-creation failure where no authoritative lifecycle row was persisted
schema/integrity recovery where continuity is not independently proved
explicit detected sequence gap
```

A broken segment can never later be relabeled contiguous by inference.

## 8.7 Cleanup rule

Observation cleanup remains time-based, but prerequisite metadata must make
retention truncation explicit.

When cleanup removes the retained prefix of an AP-dynamic segment, the
coverage authority must atomically advance:

```text
retained_from_utc
retained_first_sequence
```

or close the old segment and publish an equivalent successor retained segment.

Cleanup MUST NOT leave metadata claiming coverage for a deleted prefix.

## 8.8 Manual/intermediate deletion

The supported trust boundary is the CaptivPortal Observation repository and
its protected SQLite schema.

A detectable sequence gap or coverage-metadata inconsistency is:

```text
coverage state = broken
```

and the affected range cannot be `covered`.

Undetectable hostile filesystem/SQLite tampering is outside this product
metric's threat model; if storage integrity or schema checks expose such
tampering, the result is `source_unavailable`, never `covered`.

---

# 9. Exact post-prerequisite predicate

After TASK-...-01A is accepted and implemented, the main overlay may implement:

```text
raw_observation_range_coverage(site_id, from_utc, to_utc, evaluated_at_utc)
```

as follows.

## 9.1 Input/time contract

```text
from_utc inclusive
to_utc exclusive
from_utc < to_utc
to_utc <= evaluated_at_utc
all timestamps canonical UTC
```

## 9.2 Site/scope contract

Only coverage metadata with:

```text
site_id == requested site_id
kind == ap_dynamic
coverage_contract_version == 1
scope == site_ap_inventory through the fingerprinted contract
```

may participate.

Another Site never contributes.

A different coverage contract fingerprint cannot be merged into one proof.

A range crossing a segment/config/scope boundary is **not covered** by v1.
It is deliberately conservative; no cross-segment stitching exists in v1.

## 9.3 Single-segment proof rule

The result is `covered` if and only if one compatible, non-broken coverage
segment proves all of the following in the same read snapshot:

```text
A. segment.site_id == site_id
B. segment.kind == ap_dynamic
C. segment.retained_from_utc <= from_utc
D. segment.covered_through_utc >= to_utc
E. segment.state in {active, closed}
F. no break marker intersects [from_utc,to_utc)
G. retained sequence floor is not after the sequence covering from_utc
H. persisted sequence lineage through the range has no gap according to the
   prerequisite authority
I. coverage contract fingerprint is internally valid and supported
```

Otherwise:

```text
positive retained/break boundary evidence => incomplete
metadata present but proof cannot be completed => indeterminate
authority unreadable/invalid => source_unavailable
bounded evaluation exhausted => capacity_limited
```

## 9.4 Now-boundary rule

`to_utc` commonly equals `evaluated_at_utc`.

The prerequisite authority must represent the scheduled idle tail explicitly.
No arbitrary grace seconds are permitted in the main overlay.

For an active segment:

```text
covered_through_utc
```

may include the interval after the last terminal cycle only up to the exact
persisted `next_due_at_utc` established by the same scheduler generation.

Therefore a request ending at `now` is covered when:

```text
now <= covered_through_utc
```

and not merely because the last cycle is "recent".

No main-task constant such as `30s`, `60s`, `2*interval` or
`rate_max_gap_seconds` may be invented as a substitute.

---

# 10. SQL-implementable retrieval semantics after prerequisite

The main overlay read must stay read-only and bounded.

Conceptually, coverage proof is one indexed lookup equivalent to:

```sql
SELECT coverage_segment_id,
       site_id,
       kind,
       coverage_contract_version,
       coverage_contract_sha256,
       retained_from_utc,
       covered_through_utc,
       next_due_at_utc,
       state,
       break_reason,
       retained_first_sequence,
       last_sequence
FROM observation_raw_coverage_segments
WHERE site_id = ?
  AND kind = 'ap_dynamic'
  AND retained_from_utc <= ?
  AND covered_through_utc >= ?
  AND state IN ('active','closed')
ORDER BY retained_from_utc DESC, coverage_segment_id DESC
LIMIT 2;
```

The actual prerequisite schema may use equivalent names, but the query must
resolve to **exactly one** compatible segment.

```text
0 matching segments => incomplete or indeterminate according to persisted
                       boundary/break evidence
1 matching segment  => validate contract + coverage lineage
2 matching segments => integrity ambiguity => source_unavailable
```

The main overlay then reads partial cycles only inside the already-proven
range and remains subject to the R1 caps.

Strict-success history bounds and Traffic Projection bounds do not enter this
predicate.

---

# 11. Lifecycle/result classes for range proof versus numeric overlay

Coverage proof and numeric admission are separate.

## 11.1 Lifecycle rows represented by coverage authority

The coverage authority must track every AP-dynamic collection lifecycle attempt
that successfully enters the protected Observation persistence generation,
regardless of eventual semantic result:

```text
running
completed/success
completed/partial
completed/failed
completed/shutdown
abandoned
```

A lifecycle result does not by itself break raw-range coverage.

Example:

```text
completed/failed
```

may prove that the attempt is known and preserved, even though it contributes
no numeric partial bucket.

## 11.2 Numeric overlay admission remains R1

Only R1-admitted `completed/partial` AP-dynamic evidence may produce partial
numeric/evidence-only bucket material.

The following never become numeric overlay samples merely because they count
for lifecycle coverage:

```text
completed/failed
completed/shutdown
abandoned
running
```

---

# 12. Retention and range-start semantics

## 12.1 Current schema v1

Current `dynamic_retention_days` does not prove a range.

If raw rows visibly begin after `from_utc`, the range is positively incomplete.

If rows visibly bracket the range but no coverage authority exists, the state
is indeterminate, not covered.

## 12.2 Post-prerequisite

The only authoritative retention boundary for this product is:

```text
RawObservationCoverageSegmentV1.retained_from_utc
```

not:

```text
current configured retention days
filesystem mtime
MIN(started_at) alone
strict history available_from
projection available_from
```

Range logic:

```text
from_utc < retained_from_utc
=> incomplete

from_utc == retained_from_utc
=> allowed only if all other segment proof conditions pass

from_utc > retained_from_utc
=> may be covered if all other segment proof conditions pass
```

Cleanup lag may retain *more* rows than policy requires. It does not extend the
coverage claim unless the protected coverage segment says so.

---

# 13. Exact failure/state matrix

| Internal proof result | Wire status | Wire reason | `has_partial_measurements` | `source_coverage_insufficient` | Buckets | Comparison | AP share |
|---|---|---|---:|---:|---|---:|---:|
| `covered` + admitted partials | `ok` | `partial_measurements_present` | `true` | `false` | R1 buckets | `false` | `false` |
| `covered` + zero admitted partials | `ok` | `no_partial_measurements` | `false` | `false` | `[]` | strict eligibility | strict eligibility |
| `incomplete` | `source_coverage_insufficient` | `raw_observation_range_incomplete` | `null` | `true` | `[]` | `false` | `false` |
| `indeterminate` | `source_coverage_insufficient` | `raw_observation_range_unproven` | `null` | `null` | `[]` | `false` | `false` |
| `source_unavailable` | `unavailable` | `overlay_source_unavailable` | `null` | `null` | `[]` | `false` | `false` |
| `capacity_limited` | `capacity_limited` | `overlay_capacity_limited` | `null` | `null` | `[]` | `false` | `false` |

Precedence when multiple failures are discovered:

```text
source_unavailable
> capacity_limited
> incomplete
> indeterminate
> covered
```

This precedence is about safe response classification, not source severity.

No partially accumulated counts are returned for any non-`ok` state.

---

# 14. Deterministic acceptance fixtures

## R2-T19 — strict-only, proven fully covered

This fixture is **post-prerequisite** and proves that R1's negative assertion
remains reachable.

Input:

```text
site = S1
range = [2026-10-10T12:00:00.000Z, 2026-10-11T12:00:00.000Z)
evaluated_at = 2026-10-11T12:00:00.000Z

coverage segment G1:
  site_id = S1
  kind = ap_dynamic
  supported coverage_contract_version = 1
  retained_from_utc = 2026-10-10T11:00:00.000Z
  covered_through_utc = 2026-10-11T12:00:00.000Z
  state = active
  no break in range
  sequence lineage = contiguous under authority

raw bounded partial query:
  admitted partial cycle count = 0
```

Expected exact wire subset:

```json
{
  "status": "ok",
  "reason": "no_partial_measurements",
  "has_partial_measurements": false,
  "source_coverage_insufficient": false,
  "buckets": [],
  "bucket_count_returned": 0
}
```

PASS only if `comparison_allowed` and `ap_share_allowed` are the unchanged
strict eligibility booleans.

The same raw cycle rows **without** G1 coverage authority are not this PASS
fixture; they yield R2-T19B below.

## R2-T19B — same visible rows, schema-v1 authority absent

Input:

```text
same visible target-Site cycles as R2-T19
no RawObservationCoverageSegmentV1 authority
zero visible partial cycles
```

Expected:

```json
{
  "status": "source_coverage_insufficient",
  "reason": "raw_observation_range_unproven",
  "has_partial_measurements": null,
  "source_coverage_insufficient": null,
  "buckets": [],
  "bucket_count_returned": 0,
  "comparison_allowed": false,
  "ap_share_allowed": false
}
```

FAIL if `has_partial_measurements=false`.

## R2-T21 — positively incomplete raw range

Input:

```text
requested range starts 2026-10-04T12:00:00.000Z
protected retained_from_utc = 2026-10-06T08:00:00.000Z
strict Projection remains healthy for its own accepted samples
```

Expected exact wire subset:

```json
{
  "status": "source_coverage_insufficient",
  "reason": "raw_observation_range_incomplete",
  "has_partial_measurements": null,
  "source_coverage_insufficient": true,
  "buckets": [],
  "bucket_count_returned": 0,
  "comparison_allowed": false,
  "ap_share_allowed": false
}
```

No numeric partial bucket from the covered suffix is returned.

## R2-T26 — now boundary within persisted next-due coverage

Input:

```text
range.to_utc = evaluated_at_utc = NOW
segment active
last terminal AP-dynamic cycle finished before NOW
persisted next_due_at_utc >= NOW
covered_through_utc >= NOW
no break
```

Expected:

```text
range tail may be covered
```

If the partial query finds no admitted partials, the negative R2-T19 wire state
is allowed.

No hard-coded "recent enough" seconds are used by the main overlay.

## R2-T27 — now boundary beyond covered-through

Input:

```text
segment.covered_through_utc < NOW
no successor compatible segment covers NOW
```

Expected:

```text
proof != covered
```

If metadata positively marks the gap/break:

```text
status = source_coverage_insufficient
reason = raw_observation_range_incomplete
source_coverage_insufficient = true
```

If metadata is readable but does not prove the exact gap:

```text
status = source_coverage_insufficient
reason = raw_observation_range_unproven
source_coverage_insufficient = null
```

## R2-T28 — internal gap with cycles on both sides

Input:

```text
same Site / ap_dynamic
cycle evidence exists before and after the gap
coverage sequence authority contains a missing sequence or segment break
```

Expected:

```json
{
  "status": "source_coverage_insufficient",
  "reason": "raw_observation_range_incomplete",
  "has_partial_measurements": null,
  "source_coverage_insufficient": true,
  "buckets": [],
  "comparison_allowed": false,
  "ap_share_allowed": false
}
```

Schema-v1-only timestamps on both sides, without the sequence/segment authority,
yield `raw_observation_range_unproven`, not a guessed gap threshold.

## R2-T29 — only failed/shutdown/abandoned/running lifecycle evidence

Input:

```text
coverage segment fully covers the requested range
all lifecycle attempts are preserved
no R1-admitted completed/partial numeric cycles
some cycles are completed/failed, completed/shutdown, abandoned or running
```

Coverage proof result:

```text
covered
```

Numeric overlay admission:

```text
0 admitted partial cycles
```

Expected wire:

```text
status = ok
reason = no_partial_measurements
has_partial_measurements = false
```

This does **not** make strict Average/Peak healthy. Their unchanged strict
eligibility independently determines their availability and comparison/AP-share
eligibility.

## R2-T30 — retention trim before / at / after retained boundary

Given:

```text
retained_from_utc = 2026-10-05T00:00:00.000Z
covered_through_utc = 2026-10-11T12:00:00.000Z
```

Case A:

```text
from = 2026-10-04T23:59:59.999Z
=> incomplete
```

Case B:

```text
from = 2026-10-05T00:00:00.000Z
=> may be covered if all other proof conditions pass
```

Case C:

```text
from = 2026-10-06T00:00:00.000Z
=> may be covered if all other proof conditions pass
```

Current configured `dynamic_retention_days` cannot override these outcomes.

## R2-T31 — Site/scope transition

Input:

```text
range = 24h
Site S1 has a compatible coverage segment for only the last 18h
another Site S2 has full 24h coverage
or S1 crosses a different coverage_contract_sha256 generation
```

Expected:

```text
S2 evidence ignored
cross-generation stitching forbidden
S1 range != covered
```

With a positive S1 segment boundary:

```text
raw_observation_range_incomplete
source_coverage_insufficient = true
```

Without positive boundary proof:

```text
raw_observation_range_unproven
source_coverage_insufficient = null
```

## R2-T32 — capacity limit

Input:

```text
required overlay evaluation reaches
MAX_PARTIAL_CYCLES_PER_REQUEST = 10_080
or MAX_PARTIAL_AP_ROWS_PER_REQUEST = 150_000
or PARTIAL_OVERLAY_LOCAL_TIME_BUDGET_SECONDS = 5
before complete evaluation
```

Expected exactly:

```text
status = capacity_limited
reason = overlay_capacity_limited
has_partial_measurements = null
source_coverage_insufficient = null
buckets = []
comparison_allowed = false
ap_share_allowed = false
```

No earlier positive/negative partial-presence assertion escapes.

## R2-T33 — raw source failure

Input:

```text
observations.sqlite3 / coverage authority cannot be opened or validated
```

Expected exactly:

```text
status = unavailable
reason = overlay_source_unavailable
has_partial_measurements = null
source_coverage_insufficient = null
buckets = []
comparison_allowed = false
ap_share_allowed = false
```

## R2-T34 — empty partial query is not absence proof

Input:

```text
raw partial-cycle SELECT returns zero rows
coverage proof result = indeterminate
```

Expected:

```text
status = source_coverage_insufficient
reason = raw_observation_range_unproven
has_partial_measurements = null
```

FAIL if false/ok/no_partial_measurements is emitted.

---

# 15. Performance and hard-cap disposition

The R2 blocker is semantic authority, not query throughput.

Current indexes are sufficient for bounded retrieval of target-Site/time raw
cycles and AP rows, and R1's caps remain:

```text
MAX_PARTIAL_CYCLES_PER_REQUEST = 10_080
MAX_PARTIAL_AP_ROWS_PER_REQUEST = 150_000
PARTIAL_AP_ROW_BATCH_SIZE = 2_000
PARTIAL_OVERLAY_LOCAL_TIME_BUDGET_SECONDS = 5
```

However, scanning visible rows within those caps cannot manufacture a trusted
coverage watermark.

The prerequisite must therefore expose range coverage through O(1) or bounded
indexed metadata lookup rather than requiring a full 7-day continuity scan of
all lifecycle rows on every Admin request.

The main overlay remains bounded by the existing caps after the prerequisite
coverage lookup succeeds.

If the prerequisite cannot provide the proof within the existing local budget,
its architecture must return HOLD rather than expanding the main-task budget.

---

# 16. No-schema-change feasibility decision

Exact answer required by Tech Lead:

```text
ORIGINAL NO-SCHEMA-CHANGE HISTORICAL NEGATIVE-PRESENCE IMPLEMENTATION = NO
```

Reason:

```text
schema v1 has no independent persisted authority capable of proving the
negative statement "there were no raw partial cycles in the complete range".
```

The following remain feasible without new acquisition:

```text
Current Traffic live combination semantics
reading existing raw partial cycles
R1 partial-bucket arithmetic
UI/API failure-safe representation
```

But the parent implementation TASK is not split or resumed under this R2.
Tech Lead/Owner must first decide and authorize the prerequisite.

---

# 17. Protected components and non-effects

R2 does not authorize changes to:

```text
Portal/Auth/CAPPORT
Omada Controller behavior
Current State collector
Observation AP/client acquisition requests
Traffic Projection writer semantics
strict Historical Average/Peak/AP-share
NI-01/NI-02B/NI-03/NI-04
Fingerprint Sensor / Suricata
production configuration
```

The future prerequisite is metadata authority only; it must not reinterpret
existing traffic values.

---

# 18. Governance / sequencing

Required sequence:

```text
1. Tech Lead reviews this R2 addendum.
2. Owner accepts or rejects the prerequisite architecture direction.
3. If accepted, Tech Lead issues a bounded prerequisite implementation task
   for TASK-TRAFFIC-PARTIAL-COVERAGE-01A based on a reviewed exact schema/
   lifecycle contract.
4. Owner separately authorizes prerequisite implementation.
5. Prerequisite implementation + tests + review complete.
6. RawObservationCoverageAuthorityV1 acceptance gate passes.
7. Tech Lead reopens/resumes the parent partial-coverage implementation task.
8. Owner separately authorizes parent implementation/merge/deploy/activation.
```

Until step 6:

```text
CODER = HOLD
PRODUCTION = NO CHANGE
```

No production restart or database migration is authorized by this addendum.

---

# 19. Final verdict

```text
TASK =
TASK-TRAFFIC-PARTIAL-COVERAGE-01

ADDENDUM =
TASK-TRAFFIC-PARTIAL-COVERAGE-01-ARCHITECTURE-ADDENDUM-R2-RAW-RANGE-COVERAGE

BASELINE =
main@e8061de9fbd6da8be5cd269779070a4db4d59d64
TREE d5503fe1f2b5774bbe55cb2d34dba63246f56f6f

R1 CORE ARCHITECTURE = PRESERVED
OPTION 3 / COMBINATION = PRESERVED
OWNER ZERO-CONTRIBUTION APPROACH = ACCEPT WITH LIMITS / PRESERVED

RAW RANGE COVERAGE PROOF ON CURRENT SCHEMA V1 = NOT AVAILABLE
MIN/MAX PROOF = FORBIDDEN
CURRENT RETENTION CONFIG AS PROOF = FORBIDDEN
STRICT HISTORY BOUNDS AS PROOF = FORBIDDEN
TRAFFIC PROJECTION BOUNDS AS PROOF = FORBIDDEN
CODER-DEFINED GAP TOLERANCE = FORBIDDEN

CURRENT-SCHEMA `covered` RESULT = UNREACHABLE
NEGATIVE `has_partial_measurements=false` WITHOUT COVERAGE AUTHORITY = FORBIDDEN

MANDATORY PREREQUISITE =
TASK-TRAFFIC-PARTIAL-COVERAGE-01A
RAW OBSERVATION RANGE COVERAGE AUTHORITY

PREREQUISITE CLASS =
PROTECTED OBSERVATION METADATA / SCHEMA + WRITER LIFECYCLE AUTHORITY

NEW COLLECTOR = NO
NEW OMADA REQUEST = NO
NEW TRAFFIC SOURCE = NO
NEW TRAFFIC DB = NO
OBSERVATION SCHEMA CHANGE IN PREREQUISITE = YES
OBSERVATION WRITER METADATA CHANGE IN PREREQUISITE = YES
TRAFFIC PROJECTION SCHEMA CHANGE = NO
CURRENT STATE SCHEMA CHANGE = NO

OPEN ARCHITECTURE P0 = 0
OPEN ARCHITECTURE P1 = 0
OPEN ARCHITECTURE P2 = 0

ARCHITECTURE CLARIFICATION = COMPLETE

FINAL VERDICT =
ARCHITECTURE HOLD / PREREQUISITE REQUIRED

READY_FOR_TECH_LEAD_PREREQUISITE_TASK = YES
READY_FOR_PARENT_CODER_RESUME = NO
IMPLEMENTATION_AUTHORIZATION = NO
CODER = HOLD
PRODUCTION_CHANGE = NO
```

