# TASK-TRAFFIC-PARTIAL-COVERAGE-01 — ARCHITECTURE DECISION R3
## Minimal Safe Traffic Fix / Positive-Evidence-Only History

**Role:** CaptivPortal Architect  
**Date:** 2026-10-11  
**Parent:** `TASK-TRAFFIC-PARTIAL-COVERAGE-01-ARCHITECTURE-CONTRACT-v1-R1`  
**Clarification superseded where conflicting:** `TASK-TRAFFIC-PARTIAL-COVERAGE-01-ARCHITECTURE-ADDENDUM-R2-RAW-RANGE-COVERAGE`  
**Tech Lead input:** `TASK-TRAFFIC-PARTIAL-COVERAGE-01-TECHLEAD-ARCH-REVIEW-R2`  
**Pinned baseline:** `main@e8061de9fbd6da8be5cd269779070a4db4d59d64`  
**Tree:** `d5503fe1f2b5774bbe55cb2d34dba63246f56f6f`

---

# 1. Decision

```text
PREFERRED OPTION = OPTION A — MINIMAL SAFE TRAFFIC FIX

OPTION A SAFE = YES
OPTION B REQUIRED FOR THIS TASK = NO
TASK-TRAFFIC-PARTIAL-COVERAGE-01A = NOT A PREREQUISITE

NEW COLLECTOR = NO
NEW OMADA REQUEST = NO
NEW DATABASE = NO
OBSERVATION SCHEMA CHANGE = NO
OBSERVATION WRITER CHANGE = NO
TRAFFIC PROJECTION SCHEMA/WRITER CHANGE = NO
CURRENT STATE SCHEMA/COLLECTOR CHANGE = NO
RETENTION CHANGE = NO
BACKFILL = NO
NI-04 CHANGE = NO
```

The original problem is simple:

> one AP is confirmed Offline, the remaining APs still have trustworthy traffic measurements, therefore the working AP measurements must remain visible rather than making Site traffic blank.

The current system already has enough facts to solve that problem.

The inability of schema v1 to prove the **negative historical claim** “no partial cycle existed anywhere in the full requested range” does not invalidate a **positive claim** backed by an actual retained row: “this partial traffic measurement was observed at this timestamp.”

R3 therefore separates those claims and removes full-range negative proof from the critical path.

---

# 2. Precedence

Where documents conflict:

```text
R3 > R2 addendum > R1 contract > original v1 contract
```

R3 changes only:

1. implementation sequencing;
2. historical positive-evidence behavior when full raw-range coverage is unproven/incomplete;
3. T19/T21 and associated historical wire/UI semantics;
4. status enum additions required by the positive-evidence-only mode.

All other R1 decisions remain unchanged.

In particular, R3 preserves:

```text
no fake zero
no Wired/LAN mixing
no retroactive historical Offline inference
strict legacy metrics unchanged
strict legacy routes unchanged without coverage_mode=partial_v1
feature default OFF
bounded reads only
partial raw source never becomes strict full-period history
```

---

# 3. Option comparison

## 3.1 Option A — selected

```text
Current correction:
  use existing time-aligned Current State AP status + existing AP traffic rows

Historical correction:
  expose only positively observed and individually validated partial evidence
  never claim absence unless an actual future coverage authority exists
```

Why selected:

- directly fixes the AP-4 incident;
- uses only already persisted facts;
- does not modify acquisition or protected writers;
- remains fail-closed for unknown absence;
- can show the October 10 partial measurements because those rows already exist;
- one feature flag remains sufficient;
- rollback remains flag OFF + normal application restart authorization.

## 3.2 Option B — not selected for this task

Option B adds a future raw-range coverage authority capable of proving negative whole-range claims.

It is **not proportionate to the triggering problem** and is not a prerequisite for showing positive evidence.

If Option B were implemented later with non-stitchable coverage generations:

```text
earliest genuinely covered 24h range
  = not earlier than 24h after a valid post-activation coverage generation begins

earliest genuinely covered 7d range
  = not earlier than 168h after that generation begins

October 10 pre-instrumentation incident
  = can never receive fabricated full-range negative proof from the new authority

one ordinary restart that breaks generation continuity
  = 24h negative proof unavailable for the next 24h
  = 7d negative proof unavailable for the next 168h
```

Therefore Option B does not solve the historical October 10 evidence problem better than Option A and creates a much larger protected implementation surface.

`TASK-TRAFFIC-PARTIAL-COVERAGE-01A` is deferred as an optional future capability only if Owner later needs authoritative whole-range negative assertions.

---

# 4. Implementation sequencing

R3 freezes two bounded stages under the existing parent task.

## Stage A — Current-first incident fix

Scope:

```text
Home → Traffic Now
Traffic → Current
current per-AP traffic details
```

Authority:

```text
existing AP Observation traffic rows
+
existing CurrentStateReadService AP status facts
```

Historical endpoint/UI is not changed by Stage A.

Stage A is independently useful and MUST NOT wait for Stage B.

## Stage B — Historical positive-evidence-only overlay

Scope:

```text
Traffic → History only when coverage_mode=partial_v1
```

Authority:

```text
existing immutable completed raw ap_dynamic cycles/rows in observations.sqlite3
```

Stage B does not change strict projected history or its Average/Peak calculations.

Both stages use the single existing R1 gate:

```text
WEB_ADMIN_TRAFFIC_PARTIAL_COVERAGE_ENABLED=false
```

No second feature flag is introduced.

### Stage A route behavior

When the flag is `false`:

```text
all existing routes retain legacy strict behavior
```

When the flag is `true`, these current routes accept:

```text
coverage_mode=partial_v1
```

- `/admin/api/v1/sites/<site_id>/current-traffic/summary`
- `/admin/api/v1/sites/<site_id>/current-traffic/aps`
- `/admin/api/v1/sites/<site_id>/traffic/current`

During Stage A, the historical route remains unchanged and does not expose the new historical overlay.

### Stage B route behavior

Stage B additionally allows:

```text
GET /admin/api/v1/sites/<site_id>/traffic/history?...&coverage_mode=partial_v1
```

Absence of `coverage_mode` always means legacy strict semantics.

---

# 5. Current Traffic contract — unchanged from R1

No R3 redesign is made to Current Traffic.

Exact closed state remains:

```text
complete_installed
complete_online_population
partial_measured
unavailable
```

The AP-4 incident target behavior remains:

```text
aligned fresh Current State proves:
  AP-1 online
  AP-2 online
  AP-3 online
  AP-4 offline

same Observation cycle contains:
  AP-1 valid selected-source pair
  AP-2 valid selected-source pair
  AP-3 valid selected-source pair
  AP-4 selected-source source_unavailable + no numeric rate

=> measurement_state = complete_online_population
=> Site Download = AP-1 + AP-2 + AP-3 Download
=> Site Upload   = AP-1 + AP-2 + AP-3 Upload
=> Site Total    = Download + Upload
=> AP-4 is excluded from the online denominator
=> AP-4 is NOT materialized as 0 Mbps
```

If AP-4 is `online`, `other`, `unknown`, status is stale/unavailable, population does not match, or the missing AP does not satisfy the exact R1 Offline exclusion rule:

```text
=> partial_measured if trustworthy numeric evidence remains
=> unavailable if no trustworthy numeric evidence remains
```

This is the minimal current fix.

---

# 6. Historical positive-evidence-only contract

## 6.1 Core rule

For `coverage_mode=partial_v1`:

```text
positive retained evidence MAY be asserted
negative whole-range absence MUST NOT be asserted on schema v1
```

Therefore:

```text
found + validated partial cycle(s)
  => show them

found none
  => has_partial_measurements = null
  => never false
```

No coverage watermark is required to make a positive statement about an actual selected row.

## 6.2 Numeric admission remains R1

A raw partial cycle is admitted only if it passes the already frozen R1 gates:

```text
Site identity
kind='ap_dynamic'
completed lifecycle
result='partial'
cycle/row structural integrity
requested time predicate
single selected source per cycle/bucket
rate reason/value consistency
temporal validity
hard cycle/row limits
query deadline
```

Bucket arithmetic remains exactly R1:

```text
partial_measured
partial_directional
partial_unmeasured
```

No new averaging formula is introduced by R3.

## 6.3 New overlay status for positive evidence

R3 extends the historical `partial_coverage.status` closed enum to:

```text
partial_evidence
source_coverage_insufficient
unavailable
capacity_limited
```

The old R1/R2 `status=ok` states are not reachable on schema v1 because they required a full-range negative proof.

Exact `reason` closed enum under R3:

```text
partial_measurements_observed
raw_observation_range_unproven
raw_observation_range_incomplete
overlay_source_unavailable
overlay_capacity_limited
```

## 6.4 Positive evidence envelope

When at least one partial cycle is admitted and the bounded query completes:

```json
{
  "partial_coverage": {
    "metric_version": "network_traffic_partial_coverage_overlay.v1",
    "status": "partial_evidence",
    "reason": "partial_measurements_observed",
    "source_kind": "observation_ap_dynamic",
    "range_from_utc": "<UTC>",
    "range_to_utc": "<UTC>",
    "partial_cycle_count_examined": "<integer>",
    "partial_cycle_count_admitted": "<integer >= 1>",
    "partial_cycle_count_integrity_rejected": "<integer>",
    "partial_ap_rows_examined": "<integer>",
    "bucket_count_returned": "<integer >= 1>",
    "buckets": ["<R1 partial bucket DTOs>"],
    "has_partial_measurements": true,
    "source_coverage_insufficient": null,
    "statistics_scope": "complete_coverage_intervals_only",
    "comparison_allowed": false,
    "ap_share_allowed": false
  }
}
```

The count fields mean exactly:

> counts of retained rows/cycles actually examined by the completed bounded query; they are not a claim that the requested historical interval is fully retained.

The default `source_coverage_insufficient=null` means full-range coverage is unproven, not that it is complete.

### Positively incomplete range plus positive evidence

If a simple edge fact proves that part of the requested range is not available in the retained raw source — for example the requested `from_utc` is earlier than the earliest retained target-Site `ap_dynamic.started_at` — positive buckets are still returned.

Only this field changes:

```json
"source_coverage_insufficient": true
```

The status remains:

```text
partial_evidence
```

No `MIN/MAX` check may ever convert the field to `false` or prove continuity.

## 6.5 No positive partial evidence found

If the bounded query completes, no admissible partial cycle is found, and full-range retention cannot be proven:

```json
{
  "partial_coverage": {
    "metric_version": "network_traffic_partial_coverage_overlay.v1",
    "status": "source_coverage_insufficient",
    "reason": "raw_observation_range_unproven",
    "partial_cycle_count_examined": "<integer>",
    "partial_cycle_count_admitted": 0,
    "partial_cycle_count_integrity_rejected": "<integer>",
    "partial_ap_rows_examined": "<integer>",
    "bucket_count_returned": 0,
    "buckets": [],
    "has_partial_measurements": null,
    "source_coverage_insufficient": null,
    "statistics_scope": "complete_coverage_intervals_only",
    "comparison_allowed": false,
    "ap_share_allowed": false
  }
}
```

This means:

```text
No partial evidence was found in the retained rows examined.
The architecture does not assert that no partial evidence existed in the full requested range.
```

If an edge fact positively proves the retained raw source does not cover part of the requested range:

```text
reason = raw_observation_range_incomplete
source_coverage_insufficient = true
```

All other fields remain as above.

## 6.6 Source failure

Unchanged safe envelope:

```json
{
  "status": "unavailable",
  "reason": "overlay_source_unavailable",
  "partial_cycle_count_examined": null,
  "partial_cycle_count_admitted": null,
  "partial_cycle_count_integrity_rejected": null,
  "partial_ap_rows_examined": null,
  "bucket_count_returned": 0,
  "buckets": [],
  "has_partial_measurements": null,
  "source_coverage_insufficient": null,
  "comparison_allowed": false,
  "ap_share_allowed": false
}
```

## 6.7 Capacity/deadline failure

Unchanged safe envelope:

```json
{
  "status": "capacity_limited",
  "reason": "overlay_capacity_limited",
  "partial_cycle_count_examined": null,
  "partial_cycle_count_admitted": null,
  "partial_cycle_count_integrity_rejected": null,
  "partial_ap_rows_examined": null,
  "bucket_count_returned": 0,
  "buckets": [],
  "has_partial_measurements": null,
  "source_coverage_insufficient": null,
  "comparison_allowed": false,
  "ap_share_allowed": false
}
```

No truncated partial buckets are returned after deadline/cap exhaustion.

---

# 7. Historical strict metrics remain separate

The positive overlay never changes strict projected calculations.

```text
strict History buckets = unchanged
strict Average         = unchanged numeric algorithm
strict Peak            = unchanged numeric algorithm
partial overlay        = separate evidence layer
```

Whenever R3 partial mode is requested and full-range raw coverage is not proven:

```text
Average label = "Average · complete-coverage intervals only"
Peak label    = "Max observed with complete AP coverage"
```

If positive partial evidence exists, UI adds:

```text
"Observed partial AP measurements are shown separately; they are not included in the strict Average or Peak."
```

If no positive partial evidence is found but coverage is unproven:

```text
"No partial AP measurements were found in retained evidence; full-period partial coverage is not verified."
```

If retained range is positively incomplete:

```text
"Partial-coverage evidence is incomplete for part of this period."
```

In all three schema-v1 cases:

```text
comparison_allowed = false
ap_share_allowed = false
```

Public comparison numeric fields are `NULL` and public AP-share fractions are `NULL`.

Legacy strict requests without `coverage_mode=partial_v1` remain unchanged.

---

# 8. Historical chart rules

A `partial_evidence` response draws only the returned R1 partial bucket DTOs.

Exact presentation remains:

```text
partial_measured    => numeric partial subtotal marker/series
partial_directional => only available direction(s), Total absent
partial_unmeasured  => evidence marker, no numeric zero point
```

Legend:

```text
Measured partial coverage
```

Tooltip MUST communicate that the point is an observed subtotal/evidence point, not a complete Site total.

A strict complete bucket and a partial overlay bucket may coexist for the same chart interval; they are never averaged together.

---

# 9. Raw read bounds / performance

No new range-proof scan is added.

The Stage B read is exactly the bounded positive-evidence query already contemplated by R1:

```text
Site = exact requested site_id
kind = 'ap_dynamic'
requested time range
candidate cycle hard cap = 10,080
partial AP row hard cap = 150,000
local overlay deadline = 5 seconds
```

Existing Site/time indexes are used.

If hard cap or deadline prevents completing the requested positive-evidence scan:

```text
capacity_limited
buckets=[]
```

If source/SQLite/integrity access fails:

```text
unavailable
buckets=[]
```

Because R3 does not attempt to prove continuity or negative absence, no new index, schema, writer, watermark or background process is required.

---

# 10. Revised deterministic fixtures

## R3-T01 — AP-4 physical Offline, three APs measured

Input:

```text
aligned fresh Current State:
  AP1 online
  AP2 online
  AP3 online
  AP4 offline

selected traffic source:
  AP1 pair ok
  AP2 pair ok
  AP3 pair ok
  AP4 both source_unavailable and numeric NULL
```

Expected:

```text
measurement_state = complete_online_population
current total = sum(AP1..AP3)
AP4 contribution = excluded, not zero
```

## R3-T02 — same missing rates but AP-4 Online

Expected:

```text
measurement_state = partial_measured
numeric subtotal from valid APs remains visible
```

No promotion to complete population.

## R3-T03 — AP status stale/unknown

Expected:

```text
partial_measured if valid numeric evidence exists
unavailable otherwise
```

## R3-T04 — feature disabled

```text
WEB_ADMIN_TRAFFIC_PARTIAL_COVERAGE_ENABLED=false
```

Expected:

```text
legacy strict behavior unchanged
partial_v1 route behavior remains feature-gated
```

## R3-T19 — strict-only-looking range, no partial rows found

Input:

```text
bounded raw query completes
0 admitted partial cycles
schema v1 has no full-range negative coverage authority
```

Expected exact fields:

```json
{
  "status": "source_coverage_insufficient",
  "reason": "raw_observation_range_unproven",
  "has_partial_measurements": null,
  "source_coverage_insufficient": null,
  "bucket_count_returned": 0,
  "buckets": [],
  "comparison_allowed": false,
  "ap_share_allowed": false
}
```

PASS if strict history itself remains visible with complete-coverage-only labels.

FAIL if `has_partial_measurements=false` is emitted.

## R3-T20 — October 10 style positive partial evidence

Input:

```text
one or more retained structurally valid result=partial cycles
AP1/AP2/AP3 selected-source rates valid
AP4 source_unavailable
full raw-range continuity unproven
```

Expected:

```json
{
  "status": "partial_evidence",
  "reason": "partial_measurements_observed",
  "has_partial_measurements": true,
  "source_coverage_insufficient": null,
  "comparison_allowed": false,
  "ap_share_allowed": false
}
```

`buckets` contains the exact R1 partial bucket(s).

The October 10 positive measurements are displayable; no claim is made that every instant in the requested 24h/7d range is covered.

## R3-T21 — requested range starts before earliest retained raw target-Site cycle, no partials found

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

No absence claim.

## R3-T22 — same incomplete range, but positive partials exist in retained suffix

Expected:

```json
{
  "status": "partial_evidence",
  "reason": "partial_measurements_observed",
  "has_partial_measurements": true,
  "source_coverage_insufficient": true,
  "comparison_allowed": false,
  "ap_share_allowed": false
}
```

Validated partial buckets are returned.

This is the key R3 change from R1/R2.

## R3-T23 — partial cycle with no valid directions

Expected R1 bucket:

```text
partial_unmeasured
Download = NULL
Upload = NULL
Total = NULL
no zero point
```

Outer overlay remains `partial_evidence`.

## R3-T24 — download-only / upload-only evidence

Expected R1 bucket:

```text
partial_directional
only measured direction numeric
Total = NULL
```

Never sum unrelated directional means into Total.

## R3-T25 — capacity/deadline hit after some candidates were scanned

Expected:

```text
status = capacity_limited
all count fields = NULL
buckets = []
has_partial_measurements = NULL
```

No truncated positive subset is exposed.

## R3-T26 — raw source unavailable/integrity failure

Expected:

```text
status = unavailable
all count fields = NULL
buckets = []
has_partial_measurements = NULL
```

## R3-T27 — no Wired/LAN mixing

If Wired is selected for a cycle/bucket, LAN values cannot fill its missing direction; and vice versa.

Expected:

```text
R1 source-selection semantics preserved exactly
```

## R3-T28 — strict statistics isolation

With one or more partial overlay buckets:

Expected:

```text
strict Average numeric value unchanged
strict Peak numeric value unchanged
partial rows excluded from those strict formulas
comparison_allowed=false
ap_share_allowed=false
```

---

# 11. Allowed implementation surface

Stage A may touch only the subset needed for Current:

```text
app/analytics/current_traffic.py
app/analytics/models.py
app/analytics/source_gateway.py
app/current_state/read_service.py
app/current_state/models.py
app/admin_web/current_traffic_serialization.py
app/admin_web/query_service.py
app/admin_web/routes.py
app/admin_web/config.py
app/admin_web/templates/admin/home.html
app/admin_web/templates/admin/traffic.html
app/admin_web/static/admin.js
app/config.py
app/settings.py
relevant tests
```

Stage B may additionally touch:

```text
app/analytics/historical_traffic.py
app/traffic_projection/read_service.py   # read-only support only
app/admin_web/historical_traffic_serialization.py
relevant tests
```

No implementation under this task may modify:

```text
app/observations/ap_worker.py
Observation repository/schema/writer
Traffic Projection repository/schema/projector/writer
Current State collector/repository/schema
OmadaProvider request behavior
NI modules
Portal/Auth/CAPPORT
```

---

# 12. Handoff / rollout

After Tech Lead accepts R3 and Owner separately authorizes implementation:

```text
1. Tech Lead minimally amends/reattaches existing Coder task to R3.
2. Implement Stage A with feature default OFF.
3. Run current-specific + regression tests.
4. Tech Lead reviews Stage A.
5. Owner controls merge/deploy/restart/activation gates.
6. Only after Stage A is accepted, implement Stage B positive-evidence overlay.
7. Stage B keeps the same feature flag and strict-route compatibility.
```

Stage A may be merged/activated independently of Stage B if Owner authorizes it.

Rollback remains:

```text
WEB_ADMIN_TRAFFIC_PARTIAL_COVERAGE_ENABLED=false
```

plus only the normal authorized application restart when required.

No database rollback/backfill exists because no database is changed.

---

# 13. Governance

This architecture decision does not itself authorize code or production mutation.

```text
TECH LEAD R2 QUESTIONS TL-R2-01..04 = ANSWERED
OPTION A = SELECTED
OPTION B / 01A = DEFERRED, NOT PREREQUISITE

ARCHITECTURE_STATUS = R3 READY FOR TECH LEAD REVIEW
OPEN_P0 = 0
OPEN_P1 = 0
OPEN_P2 = 0

READY_FOR_BOUNDED_CODER_TASK_AMENDMENT = YES, AFTER TECH LEAD ACCEPTS R3
CURRENT-FIRST STAGE = READY FOR TASK DEFINITION
HISTORICAL POSITIVE-EVIDENCE STAGE = READY FOR TASK DEFINITION

IMPLEMENTATION_AUTHORIZATION = NO
CODER = HOLD UNTIL TECH LEAD R3 ACCEPTANCE + OWNER AUTHORIZATION
MERGE = NO
DEPLOY = NO
PRODUCTION_CHANGE = NO
```

---

# 14. Final architectural statement

The minimal solution is intentionally narrow:

```text
Current:
  confirmed Offline AP does not blank traffic from healthy Online APs.

History:
  show partial measurements that actually exist and pass validation.
  if none are found, say UNKNOWN — never invent “none existed”.

Everything else:
  unchanged.
```

That solves the real AP-4 failure without turning a traffic-display correction into a new data-acquisition architecture project.
