# TASK-TRAFFIC-09 — Consolidated Traffic Evidence / Quality — ARCHITECTURAL DRAFT R2

**Project:** CaptivPortal  
**Area:** Admin Console → Traffic  
**TASK candidate:** `TASK-TRAFFIC-09 — Consolidated Traffic Evidence / Quality`  
**State:** `DRAFT R2 — FOR OWNER + TECH LEAD ARCHITECTURAL REVIEW`  
**Prepared:** 2026-09-07  
**Revision:** `R2 — Architect reconciliation against current repository contracts`  
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
- the product can be built without a new Traffic metric, collector, DB, polling path, or semantic owner;
- current implementation already provides the semantic owners and most evidence primitives needed for bounded composition.

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

Repository-level Admin API boundary relevant to TRAFFIC-09:

```text
external Admin API version = admin.read.v1
common outer envelope =
  api_version
  request_id
  site_id
  result
  page
```

TRAFFIC-09 MUST remain inside this existing Admin API boundary.

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

TRAFFIC-09 is:

```text
evidence aggregation
+
bounded orchestration
+
safe Admin projection
+
operator presentation
```

It is NOT a new quality algorithm.

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

TRAFFIC-09 MAY:

```text
select
count
group
label
project
present
```

already accepted evidence.

TRAFFIC-09 MUST NOT:

```text
reinterpret
recalculate
normalize into a new semantic family
manufacture missing evidence
convert unknown into zero
```

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

Where an accepted product currently composes evidence from more than one existing read primitive, TRAFFIC-09 must reuse that accepted composition contract rather than replace it with a simplified private algorithm.

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

TRAFFIC-09 may present these facts.

It must not:

```text
recalculate current Mbps
change wired/lan selection
change freshness thresholds
invent a new current-health state
```

The existing Current Network public result does not require a universal `metric_version` field. TRAFFIC-09 must not invent one merely to satisfy its wrapper.

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

Accepted metric/method identifiers already exposed by the product remain product-owned.

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

TRAFFIC-09 does not recompute Average/Peak or redefine accepted interval evidence.

### TRAFFIC-04 — Peak Load

Canonical metric includes:

```text
network_traffic_peak_load.v1
```

Peak consumes the same accepted Historical selected-sample / interval foundation.

Relevant Evidence presentation may include:

```text
native status
shared interval evidence
accepted peak-sample provenance
accepted method/version identifiers
```

Peak formulas, ordering rules and timestamps remain untouched.

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

TRAFFIC-09 may count existing classifications.

It must not calculate AP Mbps or introduce a second AP population algorithm.

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

TRAFFIC-09 does not calculate contribution fractions or denominators.

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

TRAFFIC-09 should consume root/population-wide evidence only.

It must not export identifiable guest rows.

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

Visits =
healthy | unavailable

Observations =
healthy | unavailable | not_required
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

TRAFFIC-09 must preserve that limitation explicitly.

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

Every consolidated product entry must therefore carry explicit scope metadata.

TRAFFIC-09 must never imply:

```text
all products cover the same population
all products cover the same time interval
Current products describe the historical Evidence range
Completed first-page evidence describes the entire closed-Visit cohort
```

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

It is page-lifetime state only and does not mutate any existing panel's selected or applied range.

Application:

```text
History / Statistics / Peak / Traffic by AP / AP Share
→ Evidence range

Completed Sessions
→ same Evidence completion cohort range

Current Network / Online Guests
→ current scope, not range-derived
```

Existing independent ranges of functional Traffic panels remain authoritative for those panels.

Changing Evidence range:

```text
MUST NOT change
History panel range
Statistics panel range
Peak panel range
Traffic by AP range
AP Share range
Completed Sessions functional-panel range
```

---

## 10. Completed Sessions scope in TRAFFIC-09

Proposed v1 contract:

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

Evidence may aggregate the returned first-page item classifications and accepted reason codes.

If:

```text
has_more=true
```

the UI must explicitly avoid implying whole-cohort quality.

No new:

```text
whole-range Completed Sessions quality semantic
full-cohort scan
all-pages aggregation
```

is introduced.

---

## 11. Recommended aggregation architecture

Canonical flow:

```text
accepted product semantic owners
        ↓
bounded application aggregation
        ↓
safe Admin serialization
        ↓
existing admin.read.v1 outer envelope
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

NOT:
Analytics semantic owner
Traffic metric owner
source owner
persistence owner
scheduler owner
```

Responsibilities:

```text
determine enabled product families
invoke/reuse bounded canonical read groups
map accepted evidence fields
preserve product scopes
preserve product-specific statuses/reasons
isolate safe per-group failures
produce one internal Traffic Evidence result
```

It does not query raw DB tables.

It does not call Omada.

It does not create collection cycles.

It does not derive Traffic metrics.

---

## 12. Bounded read strategy — maximum four canonical read groups

The term:

```text
canonical read group
```

means one semantic-owner family needed by TRAFFIC-09.

It does NOT mean that every group is restricted to exactly one Python method invocation when the existing accepted owner contract requires a bounded companion read.

With all eight products enabled:

```text
GROUP 1 — Current Traffic owner
CurrentTrafficReadService

provides:
  Current Network Throughput
  +
  bounded Current AP population/evidence needed by the existing
  Traffic by AP / AP Share composition contract
```

Current group may therefore use, at most:

```text
current Site summary <= 1
current AP bounded page <= 1
```

only when the latter is required by enabled AP/AP Share semantics.

No duplicate Current Site read may be performed solely for Evidence presentation.

```text
GROUP 2 — Historical Traffic owner
HistoricalTrafficReadService

ONE combined historical semantic read for enabled subset of:
  History
  Statistics
  Peak
  Traffic by AP
  AP Share
```

```text
GROUP 3 — Online Guest owner
CurrentGuestTrafficReadService

ONE Online Guest evidence read
```

```text
GROUP 4 — Completed Session owner
CompletedGuestSessionTrafficReadService

ONE first-page Completed Sessions evidence read
```

Permanent proposed gate:

```text
MAX_CANONICAL_READ_GROUPS_PER_EVIDENCE_REQUEST = 4
```

Therefore one Evidence refresh must never become eight unrelated backend reconstructions.

Additional invariant:

```text
no N+1
no per-AP semantic read loop
no per-guest read loop
no per-Visit read loop
```

---

## 13. Historical read reuse and Current dependency reuse

The five AP/network historical products MUST come from one canonical combined `HistoricalTrafficReadService` read for the Evidence range.

Forbidden:

```text
History call
+ Statistics call
+ Peak call
+ AP call
+ AP Share call
```

Required conceptually:

```text
HistoricalTrafficReadService
  include enabled subset:
    history
    statistics
    peak
    aps
    apshare
→ one historical result family
```

Where enabled `Traffic by AP` or `AP Share` requires current population evidence under the already accepted implementation contract:

```text
reuse GROUP 1 Current owner evidence
→ feed existing historical composition
```

Forbidden:

```text
Current read for Current panel
+
second duplicate Current read for AP
+
third duplicate Current read for AP Share
```

TRAFFIC-09 does not redefine AP/AP Share composition.

---

## 14. One range resolver and one evaluation context

One Evidence HTTP request must establish one server-owned range/evaluation context.

Canonical resolver:

```text
existing resolve_traffic_network_range()
or the exact current accepted equivalent used by Admin Historical Traffic
```

Resolve once:

```text
range_id
→ from_utc
→ to_utc
→ evaluated_at_utc
```

The resolved interval uses the existing historical range contract and remains:

```text
[from_utc, to_utc)
```

The same:

```text
from_utc
to_utc
evaluated_at_utc
```

must be reused wherever the relevant existing semantic owner accepts those values.

Application:

```text
Historical group
→ exact resolved Evidence range

Completed Sessions
→ same Evidence from/to cohort boundary semantics

Current Traffic
→ same evaluated_at_utc where supported

Online Guests
→ same evaluated_at_utc where supported by accepted service contract
```

TRAFFIC-09 MUST NOT independently calculate its own alternate `24h` or `7d` boundaries.

No public:

```text
evaluated_at
from
to
```

query parameters are proposed in v1.

---

## 15. Sequential orchestration recommendation

DRAFT R2 recommendation:

```text
execute canonical read groups sequentially
inside one bounded Admin query
```

Reasons:

```text
predictable DB load
simple deadline accounting
no private concurrency domain
clear failure isolation
easier exact fan-out proof
no accidental amplification against SQLite sources
```

No:

```text
private thread pool
private worker
new process
new scheduler
new concurrent SQLite fan-out
```

is proposed.

Tech Lead may recommend an equivalent bounded execution strategy if measured mandatory PERF proves sequential orchestration insufficient.

Such a change requires:

```text
same semantic ownership
same max fan-out
same Admin concurrency ownership
no new worker/scheduler
measured justification
architecture review before FINAL freeze
```

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

The UI defaults to `24h` and always sends the range.

No v1:

```text
products
include
cursor
sort
filter
evaluated_at
from
to
```

Unknown query parameter:

```text
400 invalid_request
```

Duplicate query parameter:

```text
400 invalid_request
```

Malformed range:

```text
400 invalid_request
```

The endpoint remains inside the existing Admin:

```text
authentication
Site resolution
Site authorization
Admin query concurrency
Admin query deadline
no-store
safe serialization
response-size
```

boundary.

---

## 17. Why backend aggregation is recommended

Preferred over browser-only consolidation because it provides:

```text
one authentication/Site boundary
one Admin deadline/concurrency boundary
one range resolver
one evaluation context
central max-fan-out enforcement
one combined historical read
server-side failure isolation
no browser quality composition semantics
no need to expose guest/session identities
```

It also allows the browser to remain presentation-only:

```text
browser displays accepted evidence
browser does not infer Traffic quality
```

No new acquisition path is created.

---

## 18. API envelope — preserve existing Admin boundary

TRAFFIC-09 MUST NOT introduce a replacement top-level Admin API version.

Existing outer envelope remains:

```text
api_version = admin.read.v1
request_id = <existing Admin request id>
site_id = <authorized Site>
result = <Traffic Evidence result>
page = null
```

TRAFFIC-09's own contract version lives INSIDE `result`.

Proposed:

```text
result.contract_version =
admin.traffic.evidence.v1
```

Conceptual response:

```text
{
  api_version: "admin.read.v1",
  request_id: "...",
  site_id: "...",
  result: {
    contract_version: "admin.traffic.evidence.v1",
    evaluated_at_utc: "...",
    evidence_range: {
      id: "24h",
      from_utc: "...",
      to_utc: "..."
    },
    products: {
      ...
    }
  },
  page: null
}
```

Deliberately absent from the Traffic Evidence result:

```text
overall_quality
overall_status
quality_score
normalized_quality
```

The outer `admin.read.v1` contract must not be changed solely for TRAFFIC-09.

---

## 19. Product wrapper

Each fixed product entry contains:

```text
product_id
exposure_status
delivery_status
scope
evidence
failure_category
```

Application/configuration state:

```text
exposure_status =
enabled | disabled
```

Aggregation transport state:

```text
delivery_status =
available | failed | not_attempted
```

These are NOT product quality states.

If product feature disabled:

```text
exposure_status=disabled
delivery_status=not_attempted
evidence=null
failure_category=null
```

No semantic read is executed solely for that disabled product.

### Metric/method/version metadata rule

There is NO mandatory universal wrapper field:

```text
metric_version
```

because not every existing Traffic public product contract exposes one.

TRAFFIC-09 may expose existing accepted product-specific:

```text
metric_version
method
population_method
continuity_method
other versioned provenance
```

only where those identifiers already exist in the accepted owner/serializer contract.

They belong inside:

```text
product-specific evidence/provenance
```

or another explicitly mapped product-specific structure.

Forbidden:

```text
inventing a new metric_version
only to make all wrappers look uniform
```

---

## 20. Product-specific evidence, not a universal schema

The common wrapper is stable, but:

```text
evidence
```

remains product-specific.

No requirement exists for every product to have the same evidence fields.

### Current Network

Possible accepted projection:

```text
freshness_status
freshness_reason
observed_at
newest_observed_at
age_seconds
source_skew_seconds
complete
primary_source
selected_source
selection_reason
accepted/missing/stale/unavailable/reset AP evidence counts
```

No Traffic Mbps values need to be duplicated.

### History

Possible accepted projection:

```text
status
existing metric/method provenance
source_watermark_utc
source_age_seconds
bucket_count
complete_bucket_count
partial_bucket_count
missing_bucket_count
canonical_cycle_count
complete_site_sample_count
excluded_site_sample_count
gap/skew/source-transition/source-attempt evidence
```

### Statistics

Possible accepted projection:

```text
status
existing metric/method provenance
candidate_interval_count
accepted_interval_count
accepted_interval_seconds
interval_coverage_ratio
excluded_gap_interval_count
excluded_source_transition_interval_count
invalid_period_interval_count
accepted_peak_sample_count
```

### Peak

Possible accepted projection:

```text
status
existing metric/method provenance
shared interval evidence
accepted peak-sample provenance
```

No Peak value itself is required merely for Evidence presentation.

### Traffic by AP

Possible accepted projection:

```text
status
existing product provenance
population_count
current_population_count
historical_population_count
returned_ap_count
supported_max_ap_count
population_complete
counts of existing per-AP product classifications
```

No per-AP identifiers or Mbps values are required.

### AP Share

Possible accepted projection:

```text
status
existing metric/method provenance
population evidence
range presence
shared interval evidence
download denominator state
upload denominator state
total denominator state
```

No AP share values are required.

### Online Guests

Possible accepted projection:

```text
status
existing metric/method provenance
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

### Completed Sessions

Possible accepted projection:

```text
status
Visits source status
Observations source status

scope:
  limit
  returned_count
  has_more

item evidence counts:
  complete
  partial
  insufficient_data
  unavailable

accepted reason counts:
  <existing TRAFFIC-08 reason code> = N
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

No backend:

```text
normalized_status
normalized_reason
quality_grade
```

is proposed.

Human-readable labels should reuse already accepted product-specific labels where available.

Any new label introduced solely for the Evidence UI is:

```text
presentation-only
```

and must preserve the original machine code.

A Web Designer may later choose:

```text
visual tones
icons
layout
emphasis
```

but visual treatment must never become semantic truth.

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

Minimum row/card concepts:

```text
Product
Scope
Native status/evidence
Freshness/source state where applicable
Coverage where applicable
Top/native reasons where applicable
Provenance / observation time where applicable
```

Completed Sessions must visibly communicate:

```text
First page
N returned
More available: yes/no
```

when relevant.

No chart required in v1.

No overall quality banner.

No overall quality score.

Exact visual design is deferred to Web Designer after functional/semantic contract acceptance.

---

## 23. Frontend orchestration and historical broker interaction

TRAFFIC-09 reuses the existing:

```text
CaptivPortalTrafficCoordinator
TrafficHistoricalRequestBroker
```

because the Evidence request includes historical/range work.

Current permanent historical controls remain:

```text
max historical HTTP requests in flight from one page = 1

HISTORICAL_TRAFFIC_REQUEST_ADMISSION_GUARD_SECONDS = 3
```

TRAFFIC-09 MUST enter this existing historical request lane.

No:

```text
second historical scheduler
second admission guard
private timer
independent historical AbortController lifecycle
```

may be introduced.

### Evidence job identity

Recommended DRAFT behavior:

```text
Evidence = one endpoint job
```

It is distinct from ordinary browser historical projection batches:

```text
history
statistics
peak
aps
apshare
```

because its response contract and range state differ.

Recommended:

```text
non-coalescible with ordinary panel historical product HTTP batches
```

while still being controlled by the same broker/admission lane.

Inside the Evidence backend request, the historical semantic owner is called only once for the enabled historical Evidence subset.

### Required broker invariants

TRAFFIC-09 must preserve:

```text
one historical HTTP request in flight per Traffic page
existing dispatch admission guard
existing backoff / Retry-After rules
existing intent-generation safety
existing supersession safety
existing Global Refresh ownership
```

Evidence range changes must not modify existing panel range state.

Shared in-flight work must not be aborted merely because an unrelated existing panel intent becomes obsolete.

Evidence must not create unbounded queued work.

Repeated same-Evidence-panel pending intents may collapse to latest where consistent with the existing broker model.

### Required starvation check

The implementation/acceptance plan must demonstrate that:

```text
Evidence requests do not permanently starve
existing History / Statistics / Peak / AP / AP Share panel intents
```

and existing panels do not permanently starve explicit Evidence range intent.

Exact queue priority implementation remains Tech Lead decomposition work, but the fairness/admission invariant is architecture-level.

### Refresh paths

Allowed:

```text
initial Evidence load
explicit Evidence range change
Global Traffic Refresh
```

No TRAFFIC-09-specific periodic timer is proposed.

---

## 24. Failure isolation

If Current evidence fails:

```text
other independent product groups may still render
```

If the shared Historical group fails:

```text
History
Statistics
Peak
Traffic by AP
AP Share
```

may all report delivery failure together, because they share one semantic read.

Current / Online / Completed may still render.

If Online fails:

```text
other product groups remain available
```

If Completed fails:

```text
other product groups remain available
```

### Safe underlying read failure

Proposed:

```text
HTTP 200
existing admin.read.v1 envelope
result.contract_version=admin.traffic.evidence.v1

affected product:
  delivery_status=failed
  evidence=null
  failure_category=<safe category>
```

Proposed safe aggregation failure categories:

```text
source_unavailable
query_deadline
integrity_unavailable
runtime_unavailable
unexpected
```

These describe delivery of a product into Evidence.

They are NOT replacements for the product's own machine statuses/reasons.

### Whole endpoint failures

Normal Admin behavior remains for failures where a safe Evidence result cannot be produced:

```text
400 invalid_request
401 authentication_required
403 site_forbidden
429 concurrency_limit
503 source/query/runtime/integrity failure at endpoint boundary
```

Exact existing error-code mapping must be reused rather than silently introducing incompatible Admin error semantics.

### All product groups fail

DRAFT R2 recommendation:

```text
if aggregation itself executed safely
and every product/group failure is safely classified
→ HTTP 200 Evidence result with failed delivery states
```

This is intentionally separated from:

```text
aggregator/wrapper integrity failure
authorization failure
Admin concurrency failure
request validation failure
```

which remain normal endpoint errors.

This behavior remains an Owner + Tech Lead review decision before FINAL.

---

## 25. Security / Site isolation

TRAFFIC-09 must not become a privilege bridge.

Existing product families use capabilities including:

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

Every underlying read receives the exact same resolved and authorized:

```text
site_id
```

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
authorization tokens
cookies
credentials
```

Per-product aggregate counts must not contain identifiers.

Existing:

```text
Admin auth
Site isolation
no-store
security headers
request-id boundary
```

remain authoritative.

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
canonical read groups <=4
```

Do not recursively reacquire the same Admin semaphore for each underlying semantic owner.

No timeout increase is authorized by TRAFFIC-09.

### Current group bound

Maximum intended Current owner shape:

```text
get current Site summary <=1

list current AP page <=1
only when required by enabled AP/AP Share composition
```

No pagination loop.

If the accepted AP population cannot be safely represented by the existing bounded supported-population contract:

```text
preserve existing product semantics
do not bypass the supported bound
```

### Completed Sessions

```text
limit=100
cursor=null
no pagination loop
```

### Online Guests

TRAFFIC-09 needs root/population-wide evidence, not rows.

Implementation should use the smallest bounded invocation compatible with the current service contract.

Tech Lead must confirm whether the current serializer/service can provide the needed root evidence without materializing unnecessary browser-visible rows.

No change to the Online Guest semantic contract is authorized merely to optimize TRAFFIC-09.

---

## 27. Performance / payload DRAFT gates

These values are proposed DRAFT targets, not yet frozen FINAL thresholds.

Measure:

```text
full authenticated HTTP Evidence path
all production-enabled Traffic products
accepted production-size/representative fixture
```

Proposed:

```text
24h Evidence:
p95 <= 5.0s
max <= 10.0s

7d Evidence:
p95 <= 7.0s
max <= 12.0s

>=10 runs per range
```

Mandatory independent of final exact latency thresholds:

```text
canonical read groups <=4
Historical semantic reads <=1
Current Site summary reads <=1
Current AP bounded reads <=1 when required
Online semantic reads <=1
Completed semantic reads <=1

unexpected 5xx=0
query deadline failures=0 under accepted fixture
new Omada calls=0
source writes=0
new collection cycles=0
```

Proposed response-size acceptance budget:

```text
<=64 KiB
```

Evidence payload must not include:

```text
historical time-series arrays
per-AP Traffic values
guest rows
Visit rows
per-session Traffic values
raw source rows
```

Current:

```text
25s backend
30s browser
```

limits are safety headroom, not performance targets.

Tech Lead must either:

```text
ACCEPT proposed latency/payload thresholds
```

or provide measured justification for revised FINAL gates.

---

## 28. Feature flag / exposure model

Proposed:

```text
WEB_ADMIN_TRAFFIC_EVIDENCE_ENABLED=false
```

Repository default:

```text
false
```

Requires:

```text
WEB_ADMIN_ENABLED=true
WEB_ADMIN_TRAFFIC_ENABLED=true
```

It should not require every individual Traffic product flag.

The Evidence product inventory remains fixed to the eight Traffic products, but each entry reflects configuration exposure.

Disabled product:

```text
exposure_status=disabled
delivery_status=not_attempted
evidence=null
failure_category=null
```

No semantic read is executed solely for a disabled product.

Feature OFF:

```text
Evidence UI area absent
frontend Evidence job not registered
Evidence endpoint disabled/404
no Evidence aggregation calls
no Evidence historical broker intents
no new source workload
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
NEW SCHEDULER=NO
NEW ROLLUP=NO
```

Historical Traffic Projection remains an implementation detail of:

```text
HistoricalTrafficReadService
```

TRAFFIC-09 does not read or change projection tables directly.

If measured implementation proves new persistence/source infrastructure is required:

```text
STOP
→ separate architecture decision / TASK
```

It may not be added as an implementation convenience.

---

## 30. Testing strategy

Focused mapping tests must cover all eight products and their native status/evidence families.

Mandatory semantic invariants:

```text
aggregator does not read raw DBs
does not calculate Mbps
does not calculate AP Share
does not calculate session bytes
does not derive Online Current Rate
does not calculate new quality scores
does not normalize native statuses into a new semantic family
```

### Read-group/fan-out tests

With all eight products enabled:

```text
CANONICAL READ GROUPS:
Current     = 1
Historical  = 1
Online      = 1
Completed   = 1

TOTAL GROUPS = 4
```

This is NOT equivalent to:

```text
total Python method calls = 4
```

because the accepted Current group may require both:

```text
Current Site summary <=1
Current AP bounded page <=1
```

for existing AP/AP Share composition.

Mandatory exact bounds:

```text
Current Site summary calls <=1
Current AP bounded calls <=1
Historical semantic calls <=1
Online calls <=1
Completed calls <=1
```

No duplicate Current read solely for Evidence.

Historical call must cover the enabled subset of:

```text
history
statistics
peak
aps
apshare
```

### Disabled-product tests

Must prove:

```text
disabled exposure → no product-only semantic read
delivery_status=not_attempted
```

Shared reads may still occur when another enabled product legitimately requires the same owner group.

### Range resolver tests

Must prove:

```text
one Evidence range resolution per request
same from/to/evaluated context reused
no second private 24h/7d calculation
```

### Scope-honesty tests

```text
Current scope=current

Online scope=current authorized population

History/Statistics/Peak/AP/AP Share
scope=resolved Evidence historical range

Completed
scope=completion first page
limit=100
returned_count=N
has_more=true|false
```

### Missing-vs-zero

Must preserve existing semantics across:

```text
Current
History
Online
Completed Sessions
```

### Reason-code tests

Must:

```text
preserve accepted product machine codes
count accepted codes accurately where aggregated
not leak private/raw unexpected reason values
not remap different native reasons into a fake common code
```

### Admin envelope tests

Must prove:

```text
outer api_version remains admin.read.v1
request_id remains present
site_id remains outer Admin Site identity
page=null
result.contract_version=admin.traffic.evidence.v1
```

TRAFFIC-09 must not replace the global Admin envelope.

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
Traffic coordinator
Traffic historical broker
historical admission guard
independent ranges
Global Refresh
Admin auth/Site isolation
common admin.read.v1 envelope
Home overlapping Traffic surfaces
```

Candidate regressions:

```text
0
```

Use current canonical routing:

```text
Coder:
focused/minimal TASK-scoped tests

Owner + Tech Lead / Central Lab:
cross-module / broader / full acceptance

Owner WSL/Linux Lab:
production-compatible PERF where mandatory
```

Production is not a synthetic test host.

### Mandatory broker/admission scenarios

Acceptance must include at least:

```text
1. Initial page:
   existing historical panels + Evidence coexist
   historical HTTP in-flight <=1

2. Evidence 24h → 7d:
   Evidence range changes
   old functional panel ranges unchanged

3. Existing panel range change while Evidence pending:
   no cross-range state corruption

4. Global Refresh:
   Evidence participates without creating second scheduler

5. Rapid Evidence range intents:
   bounded/collapsed according to existing broker rules
   no unbounded queue

6. Existing panel explicit intent + Evidence intent:
   no permanent starvation

7. Shared historical failure/backoff:
   existing Retry-After/admission rules not shortened or bypassed

8. Superseded intent:
   obsolete response cannot overwrite newer Evidence selection
```

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
frontend Evidence job absent
no Evidence request
no Evidence broker intent
no new source workload

Observation healthy
Current State healthy
Visit Lifecycle healthy
existing Traffic healthy
```

Separate activation only after explicit Owner authorization:

```text
WEB_ADMIN_TRAFFIC_EVIDENCE_ENABLED=true
```

Production browser acceptance:

```text
Evidence area present
default Evidence range=24h

24h → 7d → 24h works

existing functional-panel ranges unchanged

all eight product entries represented

native statuses preserved

Current/Online explicitly marked current scope

Historical products explicitly marked Evidence range

Completed explicitly marked first-page scope

Completed has_more honesty preserved

no overall score

no identifiers

Global Refresh works

one product/group delivery failure does not suppress
independent available groups

historical in-flight invariant preserved

existing eight Traffic panels remain healthy
```

Primary rollback:

```text
WEB_ADMIN_TRAFFIC_EVIDENCE_ENABLED=false
```

No:

```text
DB rollback
schema rollback
Projection rollback
source rollback
collector rollback
```

is required.

---

## 33. REUSE boundaries

Reuse without semantic modification:

```text
CurrentTrafficReadService
HistoricalTrafficReadService
CurrentGuestTrafficReadService
CompletedGuestSessionTrafficReadService

existing Current → Historical AP/AP Share composition behavior

existing Traffic range resolver
resolve_traffic_network_range()
or exact accepted equivalent

Historical Traffic Projection
through HistoricalTrafficReadService only

AdminQueryExecutionControls

existing Admin API outer envelope:
admin.read.v1

CaptivPortalTrafficCoordinator

TrafficHistoricalRequestBroker

existing historical admission guard

existing Traffic feature flags

existing safe serializers /
presentation labels where applicable
```

Reuse means:

```text
preserve accepted semantics
```

not copy/reimplement internal calculations.

---

## 34. Proposed new TRAFFIC-09 contracts

Only the following new contracts are proposed:

```text
Traffic Evidence product exposure

TrafficEvidenceAggregator
application mapper/orchestrator

GET /admin/api/v1/sites/<site_id>/traffic/evidence

inner Evidence result contract:
admin.traffic.evidence.v1

outer Admin contract remains:
admin.read.v1

independent Evidence range:
24h | 7d

one server-resolved Evidence range/evaluation context

fixed product wrapper:
  product_id
  exposure_status
  delivery_status
  scope
  evidence
  failure_category

product-specific existing metric/method/version
metadata only where already accepted

max canonical read-group fan-out=4

Current owner bounded companion AP read
where required by accepted AP/AP Share contract

one combined Historical semantic read

standalone TRAFFIC EVIDENCE UI area

Evidence participation in existing
TrafficHistoricalRequestBroker lane
```

No new Traffic metric is introduced.

No universal metric-version requirement is introduced.

No new quality semantic is introduced.

---

## 35. Explicit no-touch contracts

TRAFFIC-09 MUST NOT change:

```text
Current Network Throughput formulas
Current freshness semantics
Current source selection

Historical bucket semantics
Historical source-selection semantics
Historical range contract

Statistics formulas/methods

Peak formulas/methods

Traffic by AP population/rates semantics

AP Share contribution semantics
AP Share denominator semantics
AP Share population semantics

Online Guest population contract
Online Current Rate contract
Online continuity/evidence contract

Completed Session Visit contract
Completed Session attribution contract
Completed Session Traffic/evidence contract

Historical Traffic Projection semantic contract

Observation acquisition/schema

Current State acquisition/schema

Visit Lifecycle

Public Traffic

Admin global API envelope semantics

TrafficHistoricalRequestBroker ownership

CaptivPortalTrafficCoordinator ownership
```

If implementation proves one of these must change:

```text
STOP
→ architecture review
→ amend FINAL or create separate TASK
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

focused TASK tests
```

Possible tests may need to cover existing coordinator/broker behavior without changing unrelated semantics.

Exact:

```text
allowed files
forbidden files
new files
test files
```

are Tech Lead implementation-decomposition work after architecture closure.

If a necessary implementation file falls outside the FINAL allowed scope:

```text
STOP
→ request minimal scope expansion
```

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
ACCEPT bounded backend
GET /traffic/evidence
```

Reason:

```text
browser remains presentation-only
semantic/fan-out control stays server-side
```

### Q3 — Independent Evidence range

Recommendation:

```text
24h | 7d
UI default=24h
page-lifetime state only
```

### Q4 — One existing range resolver

Recommendation:

```text
REQUIRE

resolve Evidence range once
using existing Admin Traffic range resolver
reuse exact range/evaluation context
```

### Q5 — Completed Sessions quality scope

Recommendation:

```text
canonical first page
limit=100
cursor=null

explicit:
returned_count
has_more
first-page scope
```

### Q6 — Capability

Recommendation:

```text
admin.read.overview
AND
admin.read.devices
```

### Q7 — Per-product failure HTTP behavior

Recommendation:

```text
safe underlying product/group failure
→ HTTP 200 Evidence result
→ delivery_status=failed
```

Whole request/auth/concurrency/wrapper integrity failure remains normal Admin 4xx/5xx.

### Q8 — Normalization

Recommendation:

```text
NO backend normalized status
NO synthetic score
NO universal machine reason enum
```

### Q9 — Current/Historical fan-out contract

Recommendation:

```text
canonical groups <=4

Current Site summary <=1
Current AP bounded page <=1 when required
Historical semantic call <=1
Online <=1
Completed <=1

no duplicate Current reads
```

### Q10 — Historical broker integration

Recommendation:

```text
Evidence enters existing TrafficHistoricalRequestBroker lane

max historical HTTP in-flight remains 1

existing 3s admission guard preserved

no second scheduler
no second AbortController lifecycle
no starvation
no unbounded queue
```

### Q11 — UI placement

Recommendation:

```text
TRAFFIC EVIDENCE after the eight functional panels
```

### Q12 — PERF / payload gates

Architect proposal:

```text
24h:
p95<=5s
max<=10s

7d:
p95<=7s
max<=12s

payload<=64KiB
```

Tech Lead must:

```text
ACCEPT
or
REVISE WITH MEASURED JUSTIFICATION
```

before FINAL freeze.

---

## 38. Acceptance criteria for TRAFFIC-09

### Architecture / product

Required:

```text
all eight Traffic products represented

existing product semantics unchanged

no new quality semantic owner

no synthetic overall score

missing != zero

scope explicit per product

source reason codes preserved

no identifying data

outer Admin envelope remains admin.read.v1

inner Evidence result versioned independently

one existing range resolver used

max read fan-out bounded

Historical five share one semantic read

Current AP dependency reused rather than duplicated

no new collector
no new DB
no new schema
no new acquisition
```

### Execution

Required:

```text
canonical read groups <=4

Current Site summary <=1
Current AP bounded page <=1 when required
Historical semantic read <=1
Online semantic read <=1
Completed semantic read <=1

new Omada calls=0
new collection cycles=0
source writes=0
new workers=0
new schedulers=0
new persistence=0
```

### Frontend/broker

Required:

```text
historical HTTP in-flight per Traffic page <=1

existing admission guard preserved

existing panel ranges unchanged by Evidence

Evidence range changes isolated

Global Refresh remains one coordinator-owned mechanism

no permanent starvation

no unbounded broker queue caused by Evidence

superseded Evidence response cannot overwrite newer selection
```

### Failure isolation

Required:

```text
individual product/group failure does not suppress
unrelated product evidence

shared Historical failure affects its shared product family honestly

TRAFFIC-09 failure does not break existing Traffic panels

Traffic Evidence problems do not break:
Portal
Observation
Current State
Visit Lifecycle
Home
other Admin sections
```

### Security

Required:

```text
same authorized Site for all reads

no privilege bridge

no client/Visit identifiers

no raw rows/cursors

no secrets

existing Admin request/auth/security boundary preserved
```

---

## 39. Traffic Section v1 completion condition

Only after:

```text
TRAFFIC-09 architecture FINAL accepted

separate implementation authorization

Tech Lead FINAL implementation decomposition

implementation complete

all mandatory exact-candidate acceptance gates PASS

publication authorization

Git publication / PR

merge

production dormant deploy PASS

separate Owner activation

production verification PASS

Knowledge Base reconciliation
```

and no remaining accepted v1 blocker:

```text
TRAFFIC SECTION v1 COMPLETE
```

This explicitly excludes:

```text
TRAFFIC-10
TRAFFIC-11
TRAFFIC-12
future Home summaries
```

---

## 40. Current DRAFT R2 state

```text
TASK CANDIDATE:
TASK-TRAFFIC-09 — Consolidated Traffic Evidence / Quality

ARCHITECTURAL APPLICABILITY:
CONFIRMED

ARCHITECT REVIEW:
PASS WITH R2 RECONCILIATION

ROADMAP ASSIGNMENT:
PROPOSED / NOT YET ACCEPTED

DOCUMENT:
DRAFT R2 — FOR OWNER + TECH LEAD ARCHITECTURAL REVIEW

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

OUTER API VERSION:
admin.read.v1

INNER EVIDENCE CONTRACT:
admin.traffic.evidence.v1

RANGE RESOLUTION:
ONE EXISTING SERVER-SIDE RESOLVER

PROPOSED MAX READ GROUPS:
4

CURRENT SITE READ:
<=1

CURRENT AP BOUNDED READ:
<=1 WHEN REQUIRED

HISTORICAL SEMANTIC READ:
<=1

ONLINE READ:
<=1

COMPLETED READ:
<=1

HISTORICAL BROKER:
EXISTING LANE / EXISTING ADMISSION OWNERSHIP

NEW QUALITY SEMANTICS:
NO

UNIVERSAL METRIC_VERSION:
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

NEW WORKER:
NO

NEW SCHEDULER:
NO

IMPLEMENTATION:
NOT AUTHORIZED

CODER:
NOT AUTHORIZED

CODE / PATCH / BRANCH / PR / DEPLOY / ACTIVATION:
NOT AUTHORIZED
```

---

## 41. FINAL TASK governance requirements

If Owner + Tech Lead accept this architecture, the future FINAL TASK must additionally freeze the execution/governance fields required by current project rules.

FINAL must explicitly contain:

```text
execution mode

executor/platform

capability assumptions

TASK-scoped test responsibility

complete mandatory acceptance gate list

fresh Central Lab full gate:
yes/no

Linux / production-compatible gate:
yes/no

PERF gate:
yes/no + exact thresholds

browser gate:
yes/no + exact scenarios

exact candidate identity/tree rule

allowed files

forbidden files

allowed repository actions

forbidden repository actions

owner-only actions

publication authorization condition

deploy / activation separation

rollback

stop conditions

handoff requirements

PR requirements
```

Canonical acceptance-before-publication remains:

```text
Patch
→ Lab
→ all mandatory gates PASS
→ accepted exact candidate
→ Git publication
→ Production deploy
→ separate activation
```

TRAFFIC-09 FINAL may not weaken this process.

---

## 42. Next allowed step

Owner + Tech Lead review this `DRAFT R2`.

Review decisions:

```text
Q1  Roadmap assignment
Q2  Backend Evidence endpoint
Q3  Independent 24h/7d Evidence range
Q4  One existing range resolver
Q5  Completed first-page scope
Q6  Capability
Q7  Per-group failure HTTP semantics
Q8  No normalization / no score
Q9  Read-group and Current companion-read bounds
Q10 Existing historical broker/admission integration
Q11 UI placement
Q12 PERF/payload thresholds
```

If accepted with corrections:

```text
apply agreed architecture corrections
→ re-fetch/rebind origin/main
→ verify repository drift
→ prepare TASK-TRAFFIC-09 FINAL ARCHITECTURE
```

Only after FINAL architecture acceptance may Owner separately authorize implementation.

No Coder task may be issued from this DRAFT.

---

# Architect R2 conclusion

```text
TRAFFIC-09 SHOULD PROCEED TO TECH LEAD REVIEW

CORE PRODUCT IDEA:
ACCEPTED

SEMANTIC MODEL:
ACCEPTED

BACKEND AGGREGATION:
RECOMMENDED

NEW QUALITY ALGORITHM:
REJECTED / NOT REQUIRED

GLOBAL ADMIN API ENVELOPE CHANGE:
REJECTED

SECOND TRAFFIC SEMANTIC OWNER:
REJECTED

SECOND HISTORICAL SCHEDULER:
REJECTED

SECOND RANGE DEFINITION:
REJECTED

UNIVERSAL INVENTED metric_version:
REJECTED

BOUNDED REUSE OF EXISTING PRODUCT OWNERS:
REQUIRED

FINAL IMPLEMENTATION AUTHORIZATION:
NOT YET GRANTED
```