# TASK-TRAFFIC-09 — Consolidated Traffic Evidence / Quality — ARCHITECTURAL DRAFT

**Project:** CaptivPortal  
**Area:** Admin Console → Traffic  
**TASK candidate:** `TASK-TRAFFIC-09 — Consolidated Traffic Evidence / Quality`  
**State:** `DRAFT — FOR OWNER + TECH LEAD ARCHITECTURAL REVIEW`  
**Prepared:** 2026-09-07  
**Implementation authorization:** `NOT GRANTED`  
**Coder authorization:** `NOT GRANTED`  
**Code / patch / branch / PR / deploy / activation:** `NOT AUTHORIZED`

---

## 1. Architectural applicability verdict

```text
TRAFFIC-09 ARCHITECTURAL APPLICABILITY = CONFIRMED

RECOMMENDED NEXT ROADMAP ITEM =
TASK-TRAFFIC-09 — Consolidated Traffic Evidence / Quality

ROADMAP ASSIGNMENT = PROPOSED / NOT YET ACCEPTED
IMPLEMENTATION = NOT AUTHORIZED
```

Why it still applies after TRAFFIC-08:

- TRAFFIC-01…08 now exist as production product contracts with their own evidence/quality semantics;
- no current production component consolidates those contracts into one operator evidence surface;
- the accepted Traffic Master Roadmap places Consolidated Evidence / Quality after TRAFFIC-08 and before Traffic Section v1 completion;
- current canonical KB deliberately says `next Traffic TASK = NOT YET ASSIGNED`, so this DRAFT proposes the assignment rather than treating it as automatic;
- the product can be built without a new Traffic metric, collector, DB, polling path, or semantic owner.

---

## 2. Current repository / production baseline

Canonical TASK baseline:

```text
TASK_BASELINE_SHA=
f57d3550ffd2e1e48f24092666d861a959c57e40

TASK_BASELINE_TREE=
0b9aac6be763d041e674970d17ce0fd0d6bee557
```

Latest merge:

```text
PR #105
Docs: reconcile TRAFFIC-08 production closure
merge=f57d3550ffd2e1e48f24092666d861a959c57e40
```

Production runtime reference:

```text
PRODUCTION_RUNTIME_SHA=
df91355a99d2561abc9c4d6d4bb6f5a968d327b3

PRODUCTION_RUNTIME_TREE=
1161739c6b4fe90fa08928556746a5a4ea6af4cd
```

Current drift classification:

```text
DOCS_DRIFT=YES
IMPLEMENTATION_DRIFT=NO
RUNTIME_DRIFT=NO
```

TRAFFIC-08 production:

```text
CLOSED / DEPLOYED / ACTIVE / PRODUCTION VERIFIED
WEB_ADMIN_TRAFFIC_COMPLETED_SESSIONS_ENABLED=true
```

---

## 3. Roadmap relationship

Proposed sequence:

```text
TRAFFIC-08
Completed Guest Session Traffic
        ↓
TRAFFIC-09
Consolidated Traffic Evidence / Quality
        ↓
TRAFFIC SECTION v1 COMPLETE
```

Explicitly outside v1 completion:

```text
TRAFFIC-10 — 30-day Enablement
TRAFFIC-11 — Traffic Heatmap
TRAFFIC-12 — Period Comparison
future Home summaries
```

TRAFFIC-09 must not absorb those tasks.

---

## 4. Product goal

Create a standalone operator-facing area:

```text
TRAFFIC EVIDENCE
```

that answers, for every existing Traffic product:

- what scope its current evidence describes;
- what native status/evidence state the owning product returned;
- what freshness/coverage/source-health facts support that state;
- what accepted source-specific reason/provenance explains limitations.

TRAFFIC-09 is evidence aggregation/presentation, not a new quality algorithm.

---

## 5. Permanent semantic constraints

TRAFFIC-09 MUST NOT create a second semantic owner for:

```text
fresh
stale
partial
insufficient_data
unavailable
unsupported_population
complete
counter_reset
gap_too_large
continuity_frozen
source-family selection/fallback
or any other existing product-specific state
```

Those meanings stay with the existing product/read owners.

Forbidden synthetic output:

```text
Traffic Quality = 87%
Traffic Health = 92/100
Overall Traffic Quality = GOOD/BAD
```

Permanent invariant:

```text
missing / unknown / stale / insufficient / unavailable != 0
```

No universal normalized backend quality enum is proposed.

---

## 6. Current production product / owner inventory

| Product | Canonical semantic owner | Native scope |
|---|---|---|
| TRAFFIC-01 Current Network Throughput | `CurrentTrafficReadService` | current / range-insensitive |
| TRAFFIC-02 Network Traffic History | `HistoricalTrafficReadService` | 24h / 7d historical range |
| TRAFFIC-03 Period Statistics | `HistoricalTrafficReadService` | 24h / 7d historical range |
| TRAFFIC-04 Peak Load | `HistoricalTrafficReadService` | 24h / 7d historical range |
| TRAFFIC-05 Traffic by AP | `HistoricalTrafficReadService` | 24h / 7d historical range |
| TRAFFIC-06 AP Traffic Share | `HistoricalTrafficReadService` | 24h / 7d historical range |
| TRAFFIC-07 Online Guests Traffic | `CurrentGuestTrafficReadService` | current authorized guest population |
| TRAFFIC-08 Completed Guest Session Traffic | `CompletedGuestSessionTrafficReadService` | closed-Visit range + keyset page |

TRAFFIC-09 must consume these owners, not raw source tables.

---

## 7. Existing evidence-contract matrix

### TRAFFIC-01 — Current Network Throughput

Existing accepted evidence/provenance includes, where public in the current contract:

```text
snapshot completeness
observed_at / newest_observed_at
age_seconds
source_skew_seconds
freshness_status
freshness_reason
primary_source
selected_source
selection_reason
valid/missing/stale/unavailable/reset AP evidence counts
```

TRAFFIC-09 may present these facts; it must not recalculate current Mbps or invent a new current-health state.

### TRAFFIC-02 — Network Traffic History

Existing evidence includes:

```text
native root status
source_watermark_utc
source_age_seconds
bucket_count
complete_bucket_count
partial_bucket_count
missing_bucket_count
canonical_cycle_count
complete_site_sample_count
excluded_site_sample_count
gap / source-transition / skew exclusions
bucket status
selected_source
selection_reason
source_changed_from_previous
source attempt quality
```

Missing historical buckets remain missing/null, never zero.

### TRAFFIC-03 — Period Statistics

Existing product status family includes:

```text
ok
partial
insufficient_data
```

Existing interval evidence includes:

```text
candidate_interval_count
accepted_interval_count
accepted_interval_seconds
interval_coverage_ratio
excluded_gap_interval_count
excluded_source_transition_interval_count
invalid_period_interval_count
accepted_peak_sample_count
```

TRAFFIC-09 does not recompute Average/Min/Max/Peak.

### TRAFFIC-04 — Peak Load

Canonical metric:

```text
network_traffic_peak_load.v1
```

Peak consumes the same accepted Historical selected-sample / interval foundation. Relevant evidence is its native status plus shared interval/coverage/accepted-peak-sample evidence. Peak formulas and timestamps remain untouched.

### TRAFFIC-05 — Traffic by AP

Existing evidence dimensions include:

```text
native product/root status
population_count
current_population_count
historical_population_count
returned_ap_count
supported_max_ap_count=12
population_complete
per-AP historical/current coverage/freshness
existing per-AP product-status classifications
```

TRAFFIC-09 may count existing classifications; it must not calculate AP Mbps.

### TRAFFIC-06 — AP Traffic Share

Existing status family:

```text
ok
partial
insufficient_data
unsupported_population
```

Existing evidence includes:

```text
shared historical interval evidence
current population status/completeness
range_presence_proven
denominator status:
  positive
  zero_traffic
  insufficient_data
```

Permanent source invariant remains:

```text
sample count != traffic share
```

### TRAFFIC-07 — Online Guests Traffic

Existing root evidence includes:

```text
status
source_health_status
source_health_reason
rate_evidence_status
population_complete
scoped_client_row_count
known_authorized_count
unknown_auth_count
population_count
rate_valid_count
rate_partial_count
rate_unavailable_count
current_capture_started_at
baseline_capture_started_at
elapsed_seconds
```

TRAFFIC-09 should consume root/population-wide evidence only; it must not export identifiable guest rows.

### TRAFFIC-08 — Completed Guest Session Traffic

Current production contract:

```text
range=24h|7d
limit default=100
limit max=100
sort=closed_at DESC, visit_id DESC
```

Root evidence:

```text
status = ok | partial | insufficient_data | unavailable
Visits = healthy | unavailable
Observations = healthy | unavailable | not_required
```

Item evidence:

```text
complete
partial
insufficient_data
unavailable
```

Accepted source-specific reasons remain the TRAFFIC-08 reason set, including:

```text
invalid_elapsed
gap_too_large
authorization_boundary
ssid_transition
ssid_unproven
continuity_frozen
connection_reset
continuity_unproven
counter_missing
counter_reset
start_edge_uncovered
end_edge_uncovered
no_usable_interval
observation_source_unavailable
attribution_window_exceeds_supported_max
```

Its root quality is page-scoped, not a frozen whole-range quality summary.

---

## 8. Scope must remain explicit

The products do not describe one homogeneous population:

```text
Current Network Throughput
→ one current AP/network snapshot

Online Guests
→ current authorized guest population

History / Statistics / Peak / AP / Share
→ one selected 24h/7d historical range

Completed Sessions
→ one keyset page of Visits closed in a selected range
```

Every consolidated product entry must therefore carry explicit scope metadata. TRAFFIC-09 must never imply that all native states cover the same population/time interval.

---

## 9. Proposed Evidence range

TRAFFIC-09 gets its own independent:

```text
24h | 7d
```

Default UI selection:

```text
24h
```

It is page-lifetime state only and does not mutate any existing panel's selected range.

Application:

```text
History / Statistics / Peak / Traffic by AP / AP Share
→ Evidence range

Completed Sessions
→ same Evidence completion range

Current Network / Online Guests
→ range-insensitive current scope
```

---

## 10. Completed Sessions scope in TRAFFIC-09

DRAFT proposal:

```text
range = selected Evidence range
limit = 100
cursor = null
```

TRAFFIC-09 aggregates evidence only from that canonical first page.

Required scope metadata:

```text
scope_kind=completion_first_page
limit=100
returned_count=N
has_more=true|false
```

If `has_more=true`, the UI must not imply whole-cohort quality.

No new whole-range Completed Sessions quality semantic is introduced.

---

## 11. Recommended aggregation architecture

Canonical flow:

```text
accepted product semantic owners
        ↓
bounded application aggregation
        ↓
Admin Traffic Evidence API
        ↓
TRAFFIC EVIDENCE UI
```

Recommended new application component, working name:

```text
TrafficEvidenceAggregator
```

Boundary:

```text
application/composition owner only
NOT an Analytics/Traffic semantic owner
```

It receives canonical product result objects and maps accepted evidence fields into one Admin envelope.

It does not query raw DB tables.

---

## 12. Bounded read strategy — maximum four canonical read groups

With all eight production products enabled:

```text
1. CurrentTrafficReadService
   → Current Network Throughput

2. HistoricalTrafficReadService
   → ONE combined read for:
      History
      Statistics
      Peak
      Traffic by AP
      AP Share

3. CurrentGuestTrafficReadService
   → Online Guests root evidence

4. CompletedGuestSessionTrafficReadService
   → first-page Completed Sessions evidence
```

Permanent proposed gate:

```text
MAX_CANONICAL_READ_GROUPS_PER_EVIDENCE_REQUEST = 4
```

Therefore one Evidence refresh must never become eight unrelated backend reconstructions.

---

## 13. Historical read reuse

The five AP/network historical products MUST come from one canonical combined `HistoricalTrafficReadService` read for the Evidence range.

Forbidden:

```text
History call
+ Statistics call
+ Peak call
+ AP call
+ AP Share call
```

This preserves one common range/source/projection basis and avoids redundant historical work.

---

## 14. Common evaluation point

One Evidence request resolves one internal:

```text
evaluated_at_utc
```

The same evaluation point is used/passed wherever the existing read contracts support it.

No public `evaluated_at` query parameter is proposed.

---

## 15. Sequential orchestration recommendation

DRAFT recommendation:

```text
execute canonical read groups sequentially
inside one bounded Admin query
```

No private thread pool.
No private worker.
No new concurrent SQLite fan-out.

This is recommended for predictable load and failure isolation. Tech Lead may propose an equivalent bounded execution model if measured PERF requires it.

---

## 16. Proposed API

```text
GET /admin/api/v1/sites/<site_id>/traffic/evidence
```

Allowed v1 query:

```text
range=24h|7d
```

Proposal:

```text
range REQUIRED
```

The UI defaults to 24h and always sends the range.

No v1:

```text
products
include
cursor
sort
filter
evaluated_at
```

Unknown or duplicate query parameter:

```text
400 invalid_request
```

---

## 17. Why backend aggregation is recommended

Preferred over browser-only consolidation because it provides:

```text
one authentication/Site boundary
one Admin deadline/concurrency boundary
one evaluation point
central max-fan-out enforcement
one combined historical read
no browser quality composition semantics
no need to expose guest/session identities
```

No new acquisition path is created.

---

## 18. Proposed API envelope

Working API version:

```text
admin.traffic.evidence.v1
```

Top level:

```text
api_version
site_id
evaluated_at_utc
evidence_range
products
```

Deliberately absent:

```text
overall_quality
overall_status
quality_score
```

`evidence_range`:

```text
{
  id,
  from_utc,
  to_utc
}
```

---

## 19. Product wrapper

Each fixed product entry contains:

```text
product_id
exposure_status
delivery_status
scope
metric_version
evidence
failure_category
```

Application/configuration state:

```text
exposure_status = enabled | disabled
```

Aggregation transport state:

```text
delivery_status = available | failed | not_attempted
```

These are NOT product quality states.

If product feature disabled:

```text
exposure_status=disabled
delivery_status=not_attempted
evidence=null
```

No semantic read is executed for that disabled product.

---

## 20. Product-specific evidence, not a universal schema

The common wrapper is stable, but `evidence` remains product-specific.

Examples:

### Current Network

```text
freshness_status
freshness_reason
observed_at
age_seconds
source_skew_seconds
complete
primary_source
selected_source
selection_reason
accepted current AP evidence counts
```

### History

```text
status
source watermark/age
complete/partial/missing bucket counts
canonical/accepted/excluded sample counts
gap/skew/source-attempt evidence
```

### Statistics

```text
status
accepted interval counts/seconds/coverage
excluded gap/source-transition/invalid interval counts
accepted peak sample count
```

### Peak

```text
status
shared interval evidence
accepted peak-sample provenance
```

### Traffic by AP

```text
status
population counts/completeness/supported max
counts of existing per-AP product classifications
```

### AP Share

```text
status
population evidence
range presence
shared interval evidence
download/upload/total denominator states
```

### Online Guests

```text
status
source_health_status/reason
rate_evidence_status
population_complete
population counts
rate valid/partial/unavailable counts
current/baseline timestamps
elapsed_seconds
```

### Completed Sessions

```text
status
Visits source status
Observations source status
limit/returned_count/has_more
counts of complete/partial/insufficient_data/unavailable items
counts of accepted TRAFFIC-08 evidence reason codes
```

No actual Traffic values need to be duplicated in the Evidence response.

---

## 21. Reason preservation / presentation normalization

TRAFFIC-09 may count already accepted source/product reason codes.

Example:

```text
continuity_frozen=94
gap_too_large=3
counter_reset=1
```

It MUST NOT create a new universal machine reason enum.

No backend `normalized_status` is proposed.

Human-readable labels should reuse already accepted product-specific labels where available. Any new label is presentation-only and must preserve the original machine code.

A Web Designer may later choose visual tones, but visual tone must never become semantic truth.

---

## 22. UI proposal

Standalone area:

```text
TRAFFIC EVIDENCE
```

Recommended location:

```text
after the existing eight functional Traffic panels
```

Functional grouping:

```text
TRAFFIC EVIDENCE

Evidence Range: 24h | 7d

Current evidence
  Current Network Throughput
  Online Guests Traffic

Range evidence
  Network Traffic History
  Period Statistics
  Peak Load
  Traffic by AP
  AP Traffic Share
  Completed Guest Session Traffic
```

Minimum row/card fields:

```text
Product
Scope
Native status/evidence
Freshness/source state where applicable
Coverage where applicable
Top/native reasons where applicable
Provenance / observation time where applicable
```

No chart required in v1.
No overall quality banner/score.

Exact visual design is deferred to Web Designer after functional contract acceptance.

---

## 23. Frontend orchestration

TRAFFIC-09 uses the existing:

```text
CaptivPortalTrafficCoordinator
TrafficHistoricalRequestBroker
```

because the Evidence request includes historical/range work.

Current production historical controls remain:

```text
HISTORICAL_TRAFFIC_REQUEST_ADMISSION_GUARD_SECONDS=3
max historical HTTP requests in flight per page=1
```

The Evidence endpoint enters the same lane.

DRAFT recommendation:

```text
non-coalescible endpoint job
```

relative to normal `history,statistics,peak,aps,apshare` browser batches, while still performing one combined Historical semantic read internally.

No second scheduler.
No private timer.
No competing AbortController lifecycle.

Refresh paths:

```text
initial Evidence load
explicit Evidence range change
Global Traffic Refresh
```

No TRAFFIC-09-specific periodic timer is proposed.

---

## 24. Failure isolation

If Current evidence fails, the other product evidence may still render.

If the shared historical read fails, its five wrappers fail together but Current / Online / Completed may still render.

If Online fails, the other seven remain independently available.

If Completed fails, the other seven remain independently available.

Safe underlying read failure proposal:

```text
HTTP 200 Evidence envelope
product delivery_status=failed
failure_category=<safe enum>
```

Proposed safe failure categories:

```text
source_unavailable
query_deadline
integrity_unavailable
runtime_unavailable
unexpected
```

Whole endpoint failures remain normal:

```text
400 invalid_request
401 authentication_required
403 forbidden
429 concurrency_limit
503 query_deadline / endpoint unavailable / wrapper integrity
```

DRAFT recommendation: even if every underlying product group fails, a safely executed aggregation endpoint may return HTTP 200 with all delivery failures represented. This is an explicit review item.

---

## 25. Security / Site isolation

TRAFFIC-09 must not become a privilege bridge.

Existing product families use at least:

```text
admin.read.overview
admin.read.devices
```

Conservative v1 recommendation:

```text
Traffic Evidence endpoint requires BOTH:
admin.read.overview
AND
admin.read.devices
```

Every underlying read receives the same authorized Site.

No cross-Site:

```text
evidence
counts
reasons
provenance
```

TRAFFIC-09 must not serialize:

```text
MAC
Visit ID
guest name
client IP
per-client rates
per-session Traffic bytes
raw cursor
raw source rows
```

---

## 26. Bounded execution / Admin baseline

Current production baseline:

```text
WEB_ADMIN_MAX_CONCURRENT_QUERIES=4
WEB_ADMIN_MAX_QUERY_DURATION_SECONDS=25
WEB_ADMIN_TRAFFIC_REQUEST_TIMEOUT_SECONDS=30
```

One Evidence HTTP request should consume:

```text
one AdminQueryExecutionControls slot
```

Inside it:

```text
max canonical read groups=4
```

Do not recursively reacquire the same Admin semaphore for each underlying semantic owner.

No timeout increase is authorized.

Completed Sessions evidence proposal uses:

```text
limit=100
cursor=null
```

Online Guests should use the smallest safe page limit compatible with its root/population-wide evidence contract; exact internal limit to be frozen after Tech Lead confirms current service behavior.

---

## 27. Performance / payload DRAFT gates

Full authenticated HTTP path, all currently enabled products.

Proposed:

```text
24h Evidence:
p95 <=5.0s
max <=10.0s

7d Evidence:
p95 <=7.0s
max <=12.0s

>=10 runs per range
```

Mandatory:

```text
canonical read groups <=4
historical semantic reads <=1
unexpected 5xx=0
query deadline failures=0 under accepted fixture
source writes=0
```

Response-size acceptance budget:

```text
<=64 KiB
```

No time-series, guest rows, Visit rows, or per-AP Traffic values should be included in the Evidence payload.

Current 25s backend / 30s browser limits are headroom, not performance targets.

---

## 28. Feature flag / exposure model

Proposed:

```text
WEB_ADMIN_TRAFFIC_EVIDENCE_ENABLED=false
```

Default:

```text
false
```

Requires:

```text
WEB_ADMIN_ENABLED=true
WEB_ADMIN_TRAFFIC_ENABLED=true
```

It should not require every individual Traffic product flag.

Disabled products are represented as configuration state and are not queried.

Feature OFF:

```text
Evidence area absent
frontend Evidence job not registered
endpoint disabled/404
no aggregation calls
existing Traffic exact compatibility
```

---

## 29. No new source infrastructure

Frozen default:

```text
NEW COLLECTOR=NO
NEW POLLING=NO
NEW TRAFFIC DB=NO
NEW DERIVED PERSISTENCE=NO
SCHEMA CHANGE=NO
NEW ACQUISITION PATH=NO
QUERY-TIME OMADA=NO
NEW WORKER=NO
```

Historical Traffic Projection remains an implementation detail of `HistoricalTrafficReadService`; TRAFFIC-09 does not read or change projection tables directly.

---

## 30. Testing strategy

Focused mapping tests must cover all eight products and native status/evidence families.

Mandatory invariants:

```text
aggregator does not read raw DBs
does not calculate Mbps
does not calculate AP Share
does not calculate session bytes
does not derive Online Current Rate
```

Fan-out test with all products enabled:

```text
Current calls=1
Historical calls=1
Online calls=1
Completed calls=1
TOTAL=4
```

Historical call must cover the enabled subset of:

```text
history,statistics,peak,aps,apshare
```

Disabled-product tests must prove no semantic read occurs for disabled products.

Scope-honesty tests:

```text
Current scope=current
Online scope=current population
five historical products scope=Evidence range
Completed scope=first page / limit 100 / has_more
```

Missing-vs-zero tests must preserve existing semantics across Current, History, Online and Completed Sessions.

Reason-code tests must preserve exact product codes and reject/private-filter unknown reason leakage.

---

## 31. Regression / acceptance routing

Regression scope includes:

```text
TRAFFIC-01 Current
TRAFFIC-02 History
TRAFFIC-03 Statistics
TRAFFIC-04 Peak
TRAFFIC-05 Traffic by AP
TRAFFIC-06 AP Share
TRAFFIC-07 Online Guests
TRAFFIC-08 Completed Sessions
Historical Traffic Projection
Traffic coordinator/broker
independent ranges
Admin auth/Site isolation
Home overlapping Traffic surfaces
```

Candidate regressions:

```text
0
```

Use current canonical test routing:

```text
focused developer tests
Windows Central Lab
Owner WSL/Linux PERF/acceptance
production smoke/acceptance
```

Production is not a synthetic test host.

---

## 32. Deployment / activation / rollback

Initial production deploy:

```text
FROM GIT
WEB_ADMIN_TRAFFIC_EVIDENCE_ENABLED=false
```

Dormant acceptance:

```text
captive-portal.service healthy
traffic-projection.service healthy
all eight existing Traffic products unchanged
Evidence area absent
Evidence endpoint disabled/404
no new Evidence request
no new source workload
Observation / Current State / Visit Lifecycle healthy
```

Separate activation only after Owner authorization:

```text
WEB_ADMIN_TRAFFIC_EVIDENCE_ENABLED=true
```

Production browser acceptance:

```text
Evidence area present
default Evidence range=24h
24h → 7d → 24h works
existing panel ranges unchanged
all eight product entries represented
native statuses preserved
Current/Online marked current
Completed marked first-page scope
no overall score
no identifiers
Global Refresh works
one product delivery failure does not suppress others
existing eight Traffic panels remain healthy
```

Primary rollback:

```text
WEB_ADMIN_TRAFFIC_EVIDENCE_ENABLED=false
```

No DB/schema/Projection/source rollback.

---

## 33. REUSE boundaries

Reuse without semantic modification:

```text
CurrentTrafficReadService
HistoricalTrafficReadService
CurrentGuestTrafficReadService
CompletedGuestSessionTrafficReadService
Historical Traffic Projection through HistoricalTrafficReadService
AdminQueryExecutionControls
CaptivPortalTrafficCoordinator
TrafficHistoricalRequestBroker
existing Traffic feature flags
existing safe serializers / presentation labels where applicable
```

---

## 34. Proposed new contracts

Only:

```text
Traffic Evidence product exposure
TrafficEvidenceAggregator application mapper/orchestrator
GET /traffic/evidence
admin.traffic.evidence.v1 envelope
independent Evidence 24h|7d range
product wrapper:
  exposure_status
  delivery_status
  scope
  metric_version
  evidence
  failure_category
max canonical read-group fan-out=4
standalone TRAFFIC EVIDENCE UI area
```

No new Traffic metric is introduced.

---

## 35. Explicit no-touch contracts

TRAFFIC-09 MUST NOT change:

```text
Current Network Throughput formulas/freshness/source selection
Historical bucket/source-selection semantics
Statistics formulas
Peak formulas
Traffic by AP population/rates
AP Share contribution/denominator semantics
Online Guest population/current-rate/evidence contract
Completed Session Visit/Traffic/evidence contract
Historical Traffic Projection semantic contract
Observation acquisition/schema
Current State acquisition/schema
Visit Lifecycle
Public Traffic
```

If implementation proves one of these must change:

```text
STOP
→ architecture review
```

---

## 36. Expected implementation scope — only after FINAL + authorization

Likely Admin/application scope:

```text
app/config.py
app/settings.py
.env.example
app/admin_web/config.py
app/admin_web/runtime.py
app/admin_web/query_service.py
app/admin_web/routes.py
new Traffic Evidence aggregation/serialization module(s)
app/admin_web/templates/admin/traffic.html
app/admin_web/static/admin.js
app/admin_web/static/admin.css
focused tests
```

Exact file list is Tech Lead implementation-decomposition work after architecture closure.

No Coder task is authorized by this DRAFT.

---

## 37. Open architecture decisions for Owner + Tech Lead

### Q1 — Roadmap assignment

```text
Assign TRAFFIC-09 as next Traffic item?
```

Architect recommendation:

```text
ACCEPT
```

### Q2 — Backend endpoint vs browser-only aggregation

Recommendation:

```text
new bounded backend /traffic/evidence endpoint
```

### Q3 — Independent Evidence range

Recommendation:

```text
24h | 7d
UI default 24h
```

### Q4 — Completed Sessions quality scope

Recommendation:

```text
canonical first page
limit=100
cursor=null
explicit has_more / first-page scope
```

### Q5 — Capability

Recommendation:

```text
admin.read.overview
AND
admin.read.devices
```

### Q6 — Per-product failure HTTP behavior

Recommendation:

```text
safe underlying failure
→ HTTP 200 Evidence envelope
→ affected delivery_status=failed
```

Whole endpoint/auth/concurrency/integrity failure remains normal 4xx/5xx.

### Q7 — Normalization

Recommendation:

```text
NO backend normalized status
NO synthetic score
```

### Q8 — UI placement

Recommendation:

```text
TRAFFIC EVIDENCE after the eight functional panels
```

### Q9 — PERF/payload gates

Proposal:

```text
24h p95<=5s / max<=10s
7d p95<=7s / max<=12s
payload<=64KiB
max read groups=4
```

Freeze or revise before FINAL.

---

## 38. Acceptance criteria for TRAFFIC-09

Architecture/product acceptance requires:

```text
all eight Traffic products represented
existing product semantics unchanged
no new quality semantic owner
no synthetic overall score
missing != zero
scope explicit per product
source reason codes preserved
no identifying data
max read fan-out bounded
historical five share one read
no new collector/DB/schema/acquisition
```

Execution acceptance requires:

```text
canonical read groups <=4
historical canonical read count <=1
new Omada calls=0
new collection cycles=0
source writes=0
new workers=0
```

Failure-isolation acceptance requires:

```text
individual product/group failure does not suppress unrelated product evidence
TRAFFIC-09 failure does not break existing Traffic panels
Traffic evidence problems do not break Portal / Observation / Current State /
Visit Lifecycle / Home / other Admin sections
```

---

## 39. Traffic Section v1 completion condition

Only after:

```text
TRAFFIC-09 architecture FINAL accepted
separate implementation authorization
implementation complete
mandatory tests/PERF PASS
merge
production dormant PASS
separate activation
production verification
Knowledge Base reconciliation
```

and no remaining accepted v1 blocker:

```text
TRAFFIC SECTION v1 COMPLETE
```

This explicitly excludes TRAFFIC-10/11/12 and future Home summaries.

---

## 40. Current DRAFT state

```text
TASK CANDIDATE:
TASK-TRAFFIC-09 — Consolidated Traffic Evidence / Quality

ARCHITECTURAL APPLICABILITY:
CONFIRMED

ROADMAP ASSIGNMENT:
PROPOSED / NOT YET ACCEPTED

DOCUMENT:
DRAFT — FOR OWNER + TECH LEAD ARCHITECTURAL REVIEW

TASK BASELINE:
f57d3550ffd2e1e48f24092666d861a959c57e40

TASK TREE:
0b9aac6be763d041e674970d17ce0fd0d6bee557

PRODUCTION RUNTIME:
df91355a99d2561abc9c4d6d4bb6f5a968d327b3

PRODUCTION TREE:
1161739c6b4fe90fa08928556746a5a4ea6af4cd

DRIFT:
DOCS ONLY

IN-SCOPE PRODUCTS:
Current
History
Statistics
Peak
Traffic by AP
AP Share
Online Guests
Completed Sessions

PROPOSED API:
GET /admin/api/v1/sites/<site_id>/traffic/evidence?range=24h|7d

PROPOSED MAX READ GROUPS:
4

NEW QUALITY SEMANTICS:
NO

SYNTHETIC SCORE:
NO

NEW COLLECTOR:
NO

NEW DB:
NO

NEW PERSISTENCE:
NO

SCHEMA CHANGE:
NO

QUERY-TIME OMADA:
NO

IMPLEMENTATION:
NOT AUTHORIZED

CODER:
NOT AUTHORIZED

CODE / PATCH / BRANCH / PR / DEPLOY / ACTIVATION:
NOT AUTHORIZED
```

---

## 41. Next allowed step

Owner + Tech Lead review this DRAFT and decide Q1–Q9.

If accepted with corrections:

```text
apply architecture corrections
→ re-fetch/rebind origin/main
→ issue TASK-TRAFFIC-09 FINAL ARCHITECTURE
```

Implementation still requires a separate explicit Owner authorization after FINAL acceptance.

No Coder task may be issued from this DRAFT.
