# TASK-TRAFFIC-09 — Consolidated Traffic Evidence / Quality — FINAL ARCHITECTURE

**Project:** CaptivPortal  
**Area:** Admin Console → Traffic  
**TASK:** `TASK-TRAFFIC-09 — Consolidated Traffic Evidence / Quality`  
**State:** `FINAL ARCHITECTURE — READY FOR TECH LEAD FINAL CONTRACT / DECOMPOSITION REVIEW`  
**Prepared:** 2026-09-07  
**Architecture status:** `ACCEPTED BY ARCHITECT / TECH LEAD REVIEW INCORPORATED`  
**Roadmap assignment:** `ACCEPTED`  
**Implementation authorization:** `NOT GRANTED`  
**Coder authorization:** `NOT GRANTED`  
**Code / patch / branch / PR / deploy / activation:** `NOT AUTHORIZED`

---

## 1. FINAL decision

```text
TASK=
TASK-TRAFFIC-09 — Consolidated Traffic Evidence / Quality

ARCHITECTURAL_APPLICABILITY=
CONFIRMED

ROADMAP_ASSIGNMENT=
ACCEPTED

NEXT_TRAFFIC_TASK=
TASK-TRAFFIC-09

ARCHITECTURE=
FINAL

READY_FOR_TECH_LEAD_DECOMPOSITION_REVIEW=
YES

IMPLEMENTATION_AUTHORIZATION=
NOT GRANTED

CODER_AUTHORIZATION=
NOT GRANTED
```

TRAFFIC-09 is the final mandatory Traffic Section v1 product stage after TRAFFIC-08.

After complete implementation, mandatory acceptance, publication, production deployment, separate activation and production verification:

```text
TRAFFIC SECTION v1 COMPLETE
```

may be declared, provided no new accepted v1 blocker exists.

Future scope remains separate:

```text
TRAFFIC-10 — 30-day Enablement
TRAFFIC-11 — Traffic Heatmap
TRAFFIC-12 — Period Comparison
future Home summaries
```

---

# PART I — BASELINE AND CHANGE BOUNDARY

## 2. FINAL repository baseline

Fresh rebind against `origin/main`:

```text
FINAL_BASELINE_SHA=
f57d3550ffd2e1e48f24092666d861a959c57e40

FINAL_BASELINE_TREE=
0b9aac6be763d041e674970d17ce0fd0d6bee557
```

Comparison against the R2 review baseline:

```text
ahead_by=0
behind_by=0
changed_files=0
```

Classification:

```text
DRIFT_CLASSIFICATION=
NO_DRIFT
```

Therefore:

```text
ARCHITECTURE_RECONCILIATION_REQUIRED=
NO
```

Production runtime remains separately identified as:

```text
PRODUCTION_RUNTIME_SHA=
df91355a99d2561abc9c4d6d4bb6f5a968d327b3

PRODUCTION_RUNTIME_TREE=
1161739c6b4fe90fa08928556746a5a4ea6af4cd
```

The repository HEAD above production runtime is documentation reconciliation only; no new implementation change exists after TRAFFIC-08 production runtime.

---

## 3. Current Traffic baseline

Production-active Traffic products:

```text
TRAFFIC-01 Current Network Throughput
TRAFFIC-02 Network Traffic History
TRAFFIC-03 Period Statistics
TRAFFIC-04 Peak Load
TRAFFIC-05 Traffic by AP
TRAFFIC-06 AP Traffic Share
TRAFFIC-07 Online Guests Traffic
TRAFFIC-08 Completed Guest Session Traffic
```

Current accepted product owners:

| Product | Semantic owner |
|---|---|
| Current Network Throughput | `CurrentTrafficReadService` |
| Network Traffic History | `HistoricalTrafficReadService` |
| Period Statistics | `HistoricalTrafficReadService` |
| Peak Load | `HistoricalTrafficReadService` |
| Traffic by AP | `HistoricalTrafficReadService` |
| AP Traffic Share | `HistoricalTrafficReadService` |
| Online Guests Traffic | `CurrentGuestTrafficReadService` |
| Completed Guest Session Traffic | `CompletedGuestSessionTrafficReadService` |

These owners remain authoritative.

TRAFFIC-09 does not become a ninth Traffic metric owner.

---

## 4. Change boundary

TRAFFIC-09 introduces only:

```text
bounded application orchestration
+
evidence projection
+
safe Admin serialization
+
one Admin endpoint
+
one independent Evidence range state
+
one operator-facing Evidence area
```

TRAFFIC-09 does NOT introduce:

```text
new Traffic metric
new Traffic formula
new source of truth
new collector
new polling path
new database
new schema
new persistence
new rollup
new cache owner
new Omada read path
new background worker
new scheduler
new historical broker
new quality algorithm
```

---

# PART II — PRODUCT SEMANTICS

## 5. Product goal

Create one standalone Admin Traffic area:

```text
TRAFFIC EVIDENCE
```

that lets the operator understand, for each existing Traffic product:

```text
what scope is being described
what native product status was obtained
what source/freshness/coverage evidence supports it
what accepted reason/provenance explains limitations
whether the product contract itself was delivered successfully
```

TRAFFIC-09 is a consolidated evidence view.

It is not a consolidated traffic-value view.

It is not an overall health score.

---

## 6. Permanent semantic invariant

TRAFFIC-09 MUST NOT redefine or normalize existing meanings such as:

```text
ok
complete
partial
insufficient_data
unavailable
unsupported_population
fresh
stale
valid
counter_reset
gap_too_large
continuity_frozen
source_unavailable
```

Permanent rule:

```text
native product state
!=
Evidence delivery state
```

Permanent rule:

```text
missing
unknown
unavailable
stale
insufficient
!=
0
```

Numeric zero remains valid evidence where the underlying accepted product says it is valid.

Unknown/null remains unknown/null.

---

## 7. Explicitly forbidden synthetic semantics

TRAFFIC-09 MUST NOT expose or internally define:

```text
overall_quality
overall_status
quality_score
normalized_quality
normalized_status
health_score
GOOD/BAD grade
Traffic Quality = N%
Traffic Health = N/100
universal machine reason enum
```

No second evidence semantic owner is allowed.

---

# PART III — FIXED PRODUCT INVENTORY

## 8. Exact product IDs

The Evidence contract contains exactly eight fixed product keys:

```text
current
history
statistics
peak
aps
apshare
online_guests
completed_sessions
```

No aliases.

No dynamic source-derived product names.

No optional ninth product without a later architecture change.

Each product object's:

```text
product_id
```

must exactly equal its fixed key.

Example:

```text
products.current.product_id = "current"
products.apshare.product_id = "apshare"
```

---

## 9. Fixed scope vocabulary

Only the following scope kinds exist in TRAFFIC-09 v1:

```text
current_snapshot
current_authorized_population
historical_range
completion_first_page
```

Exact mapping:

```text
current
→ current_snapshot

online_guests
→ current_authorized_population

history
statistics
peak
aps
apshare
→ historical_range

completed_sessions
→ completion_first_page
```

No free-text scope kinds.

No client-supplied scope kind.

---

## 10. Product scope honesty

TRAFFIC-09 must preserve that the products do not describe one common population.

### Current

```text
scope_kind=current_snapshot
```

Describes one current AP/network snapshot.

### Online Guests

```text
scope_kind=current_authorized_population
```

Describes the accepted current authorized guest population.

### Historical five

```text
scope_kind=historical_range
```

Describe one shared Evidence range.

### Completed Sessions

```text
scope_kind=completion_first_page
```

Describes only the first canonical page of closed Visits in the selected Evidence completion cohort.

TRAFFIC-09 MUST NOT imply:

```text
Current is a 24h/7d metric
Online Guests is a 24h/7d metric
Completed first page equals entire closed-Visit cohort
all eight products describe the same population
```

---

# PART IV — RANGE CONTRACT

## 11. Evidence range

Evidence owns one independent selector:

```text
24h | 7d
```

Default UI value:

```text
24h
```

State lifetime:

```text
page-local
```

No persistence in:

```text
localStorage
sessionStorage
cookie
URL state
server state
```

unless a later approved task changes that contract.

---

## 12. Range isolation

Changing the Evidence range MUST NOT mutate the independent ranges of:

```text
Network Traffic History
Period Statistics
Peak Load
Traffic by AP
AP Traffic Share
Completed Sessions functional panel
```

Evidence range is independent of all functional-panel ranges.

---

## 13. Canonical range resolver

Exactly one existing resolver is authoritative:

```text
app.admin_web.traffic_network_ranges.resolve_traffic_network_range()
```

One Evidence request captures one:

```text
evaluated_at_utc
```

and resolves exactly one:

```text
range_id
from_utc
to_utc
evaluated_at_utc
```

No second 24h/7d calculation is allowed inside:

```text
TrafficEvidenceAggregator
serializer
frontend
Completed adapter
Historical helper
```

---

## 14. One request evaluation context

Conceptual flow:

```text
range=24h|7d
        ↓
capture one evaluated_at_utc
        ↓
resolve_traffic_network_range()
        ↓
EvidenceRangeContext
    range_id
    from_utc
    to_utc
    evaluated_at_utc
        ↓
all applicable semantic groups
```

Historical uses the exact resolved context.

Completed receives:

```text
range_id=<Evidence range>
evaluated_at_utc=<same Evidence evaluated_at>
```

Acceptance must prove Completed's resulting:

```text
range.id
range.from_utc
range.to_utc
range.evaluated_at_utc
```

exactly match the canonical Evidence context.

Current and Online receive the same `evaluated_at_utc` where their accepted service interfaces support it.

---

# PART V — COMPLETED SESSION BOUNDARY

## 15. Completed invocation contract

TRAFFIC-09 must invoke Completed Sessions exactly as:

```text
range_id=<Evidence range>
evaluated_at_utc=<Evidence evaluated_at>
limit=100
cursor=None
```

No other limit.

No pagination loop.

No second page.

No whole-range scan.

---

## 16. Completed scope DTO

Completed scope must be:

```text
{
  kind: "completion_first_page",
  range_id: "24h" | "7d",
  from_utc: "...",
  to_utc: "...",
  evaluated_at_utc: "...",
  limit: 100,
  returned_count: N,
  has_more: true | false
}
```

`has_more` is derived only from the accepted page contract:

```text
next_cursor != null
```

The cursor itself MUST NOT be included in the Evidence API.

---

## 17. Completed honesty invariant

If:

```text
has_more=true
```

the UI must explicitly communicate that the Evidence result describes:

```text
first page only
```

and MUST NOT label its counts as:

```text
all sessions
whole cohort
all completed guests
complete range quality
```

---

# PART VI — ADMIN API CONTRACT

## 18. Endpoint

Freeze:

```text
GET /admin/api/v1/sites/<site_id>/traffic/evidence
```

Allowed query exactly:

```text
range=24h|7d
```

`range` is required.

---

## 19. Forbidden query parameters

TRAFFIC-09 v1 accepts no:

```text
products
include
cursor
sort
filter
from
to
evaluated_at
evaluated_at_utc
```

Unknown query parameter:

```text
400 invalid_request
```

Duplicate query parameter:

```text
400 invalid_request
```

Missing range:

```text
400 invalid_request
```

Malformed range:

```text
400 invalid_request
```

---

## 20. Preserve global Admin envelope

TRAFFIC-09 MUST NOT replace the existing outer Admin API contract.

Outer response remains:

```text
api_version=admin.read.v1
request_id
site_id
result
page
```

Exact successful Evidence outer shape:

```text
{
  "api_version": "admin.read.v1",
  "request_id": "<existing Admin request id>",
  "site_id": "<resolved authorized Site>",
  "result": { ... },
  "page": null
}
```

`admin.traffic.evidence.v1` is NOT the global `api_version`.

---

## 21. Evidence result contract version

Inside `result`:

```text
contract_version=
admin.traffic.evidence.v1
```

Exact top-level result shape:

```text
{
  "contract_version": "admin.traffic.evidence.v1",
  "evaluated_at_utc": "...",
  "evidence_range": {
    "id": "24h" | "7d",
    "from_utc": "...",
    "to_utc": "..."
  },
  "products": {
    "current": { ... },
    "history": { ... },
    "statistics": { ... },
    "peak": { ... },
    "aps": { ... },
    "apshare": { ... },
    "online_guests": { ... },
    "completed_sessions": { ... }
  }
}
```

No extra universal quality field.

---

# PART VII — COMMON PRODUCT WRAPPER

## 22. Exact common wrapper

Every one of the eight product entries contains exactly the common contract:

```text
product_id
exposure_status
delivery_status
scope
evidence
failure_category
```

Conceptually:

```text
{
  "product_id": "...",
  "exposure_status": "...",
  "delivery_status": "...",
  "scope": { ... } | null,
  "evidence": { ... } | null,
  "failure_category": "..." | null
}
```

Product-specific `evidence` may differ.

---

## 23. Exposure status

Allowed:

```text
enabled
disabled
```

Meaning:

```text
enabled
→ product feature is configured/exposed for this Admin runtime

disabled
→ product feature is not configured/exposed
```

Disabled product:

```text
exposure_status=disabled
delivery_status=not_attempted
scope=<canonical scope metadata may be present only if safely known without product read>
evidence=null
failure_category=null
```

No semantic read is executed solely for a disabled product.

---

## 24. Delivery status

Allowed exactly:

```text
available
failed
not_attempted
```

Meaning:

### `available`

The owning product contract was safely obtained and validated.

It says nothing about whether the product's native status is good, partial, unavailable or insufficient.

### `failed`

The product contract could not be safely delivered into Evidence because execution/projection failed.

### `not_attempted`

The product was intentionally not queried, normally because it is disabled.

---

## 25. Failure category

Allowed exactly:

```text
null
source_unavailable
query_deadline
integrity_unavailable
runtime_unavailable
unexpected
```

Invariant:

```text
delivery_status=available
→ failure_category=null

delivery_status=not_attempted
→ failure_category=null

delivery_status=failed
→ failure_category is one fixed non-null category
```

No exception text.

No SQL error.

No DB path.

No Python class name.

No stack trace.

No raw source detail.

---

## 26. Native status vs delivery status

Mandatory semantic examples:

```text
Completed owner returns:
status=unavailable

Expected:
delivery_status=available
evidence.status=unavailable
failure_category=null
```

Likewise:

```text
History:
status=partial
→ delivery_status=available

Online:
status=insufficient_data
→ delivery_status=available

AP Share:
status=unsupported_population
→ delivery_status=available
```

Native product unavailability is evidence.

It is not Evidence transport failure.

---

# PART VIII — PRODUCT-SPECIFIC EVIDENCE

## 27. Universal metric_version is forbidden

The common wrapper MUST NOT contain:

```text
metric_version
```

because not every current product exposes one.

Existing product-specific:

```text
metric_version
method
population_method
rate_method
continuity_method
attribution_method
```

may be carried only where already canonical.

TRAFFIC-09 must not invent missing version identifiers.

---

## 28. Current evidence

`current.evidence` may contain only validated Current owner evidence required by this product.

Frozen Evidence projection:

```text
{
  "freshness_status": "...",
  "freshness_reason": "...",
  "observed_at": "... | null",
  "newest_observed_at": "... | null",
  "age_seconds": number | null,
  "source_skew_seconds": number | null,
  "complete": true | false,
  "primary_source": "wired",
  "selected_source": "wired" | "lan" | null,
  "selection_reason": "...",
  "coverage_status": "complete" | "partial" | "none",
  "total_ap_count": N,
  "valid_rate_ap_count": N,
  "missing_rate_ap_count": N,
  "stale_ap_count": N,
  "unavailable_ap_count": N,
  "reset_ap_count": N,
  "gap_rejected_ap_count": N,
  "no_baseline_ap_count": N,
  "source_unavailable_ap_count": N,
  "invalid_elapsed_ap_count": N
}
```

No Current Mbps values are required in Evidence.

No AP identities.

No private source rows.

---

## 29. Current scope

```text
{
  "kind": "current_snapshot",
  "evaluated_at_utc": "<Evidence evaluated_at>"
}
```

Actual observation/freshness times remain inside `evidence`.

---

## 30. History evidence

`history.evidence` is a compact projection of the accepted combined Historical result.

Frozen minimum:

```text
{
  "status": "ok" | "partial" | "insufficient_data",

  "metric_version": "network_traffic_history.v1",
  "source_kind": "observation_ap_dynamic",

  "source_watermark_utc": "... | null",
  "source_age_seconds": number | null,

  "bucket_count": N,
  "complete_bucket_count": N,
  "partial_bucket_count": N,
  "missing_bucket_count": N,

  "canonical_cycle_count": N,
  "complete_site_sample_count": N,
  "excluded_site_sample_count": N,
  "gap_bucket_count": N,
  "source_transition_count": N,

  "partial_cycle_count": N,
  "failed_cycle_count": N,
  "shutdown_cycle_count": N,
  "abandoned_cycle_count": N,
  "running_cycle_count": N,
  "no_baseline_count": N,
  "counter_reset_count": N,
  "gap_too_large_count": N,
  "invalid_elapsed_count": N,
  "source_unavailable_count": N,
  "source_skew_excluded_sample_count": N,
  "integrity_failure_count": N
}
```

Historical time-series bucket arrays MUST NOT be duplicated into Evidence.

---

## 31. Historical five scope

For:

```text
history
statistics
peak
aps
apshare
```

scope is exactly:

```text
{
  "kind": "historical_range",
  "range_id": "24h" | "7d",
  "from_utc": "...",
  "to_utc": "...",
  "evaluated_at_utc": "..."
}
```

---

## 32. Statistics evidence

Frozen:

```text
{
  "status": "ok" | "partial" | "insufficient_data",

  "metric_version": "network_traffic_period_statistics.v1",
  "average_method": "right_endpoint_sample_hold_time_weighted.v1",
  "peak_method": "max_accepted_complete_site_sample.v1",

  "candidate_interval_count": N,
  "accepted_interval_count": N,
  "accepted_interval_seconds": number,
  "interval_coverage_ratio": number,

  "excluded_gap_interval_count": N,
  "excluded_source_transition_interval_count": N,
  "invalid_period_interval_count": N,
  "accepted_peak_sample_count": N,

  "leading_unweighted_seconds": number,
  "trailing_unweighted_seconds": number
}
```

Statistics Average/Peak Mbps values themselves need not be copied into Evidence.

---

## 33. Peak evidence

Frozen:

```text
{
  "status": "ok" | "partial" | "insufficient_data",

  "metric_version": "network_traffic_peak_load.v1",
  "peak_value_method": "max_accepted_complete_site_sample.v1",
  "peak_tie_break_method": "earliest_peak_sample_at.v1",
  "sample_timestamp_semantics": "cycle_finished_at",

  "download_event_available": true | false,
  "upload_event_available": true | false,
  "total_event_available": true | false,

  "busiest_bucket_status": "ok" | "insufficient_data",
  "busiest_hour_status": "ok" | "insufficient_data"
}
```

TRAFFIC-09 does not need to duplicate Peak Mbps values, timestamps or selected-source values for the Evidence UI.

The native Peak product remains the value owner.

---

## 34. Traffic by AP evidence

Frozen root/population projection:

```text
{
  "status":
    "ok"
    | "partial"
    | "insufficient_data"
    | "unsupported_population",

  "metric_version": "network_traffic_by_ap.v1",

  "population_method":
    "current_union_historical_validated.v1",

  "population_count": N,
  "current_population_count": N,
  "historical_population_count": N,
  "supported_max_ap_count": 12,
  "returned_ap_count": N,
  "population_complete": true | false,

  "complete_ap_count": N,
  "partial_ap_count": N,
  "insufficient_data_ap_count": N
}
```

The three classification counts are calculated only by counting already validated native per-AP product statuses:

```text
complete
partial
insufficient_data
```

They are not new AP quality semantics.

No:

```text
AP MAC
AP name
per-AP Mbps
per-AP history array
```

may enter the Evidence response.

---

## 35. AP Share evidence

Frozen:

```text
{
  "status":
    "ok"
    | "partial"
    | "insufficient_data"
    | "unsupported_population",

  "metric_version": "network_traffic_ap_share.v1",

  "share_method":
    "accepted_site_interval_integrated_ap_contribution_ratio.v1",

  "temporal_method":
    "right_endpoint_sample_hold_time_weighted.v1",

  "presence_method":
    "accepted_selected_source_historical_presence_in_range.v1",

  "absence_method":
    "proven_population_member_absent_from_trusted_complete_site_sample_zero_contribution.v1",

  "population_method":
    "current_union_historical_validated.v1",

  "population_count": N,
  "historical_population_count": N,
  "current_population_status": "available" | "unavailable",
  "current_population_count": N | null,
  "supported_max_ap_count": 12,
  "returned_ap_count": N,
  "population_complete": true | false,

  "candidate_interval_count": N,
  "accepted_interval_count": N,
  "accepted_interval_seconds": number,
  "interval_coverage_ratio": number,

  "excluded_gap_interval_count": N,
  "excluded_source_transition_interval_count": N,
  "invalid_period_interval_count": N,

  "download_denominator_status":
    "positive" | "zero_traffic" | "insufficient_data",

  "upload_denominator_status":
    "positive" | "zero_traffic" | "insufficient_data",

  "total_denominator_status":
    "positive" | "zero_traffic" | "insufficient_data"
}
```

No AP contribution/share values.

No AP identifiers.

Permanent invariant:

```text
sample count != Traffic share
```

---

## 36. Online Guests invocation

TRAFFIC-09 must call the accepted owner as:

```text
evaluated_at_utc=<same Evidence evaluated_at>
limit=1
cursor=None
```

Reason:

The owner calculates the population-wide:

```text
population counts
rate valid/partial/unavailable counts
root status
source health
rate evidence
```

before page slicing.

The one returned row is not needed for Evidence serialization.

`limit=1` is a bounded output/object constraint only.

It is not a claim that population computation becomes one-row source work.

---

## 37. Online Guests evidence

Frozen:

```text
{
  "status":
    "ok"
    | "partial"
    | "insufficient_data"
    | "stale"
    | "unavailable"
    | "unsupported_population",

  "metric_version":
    "network_traffic_online_guest_current_rate.v1",

  "population_method":
    "fresh_complete_current_state_authorized_guest_scope.v1",

  "rate_method":
    "current_connection_counter_delta_interval_average.v1",

  "baseline_method":
    "nearest_previous_complete_same_site_scope_cycle.v1",

  "continuity_method":
    "omada_controller_connection_progress_v1",

  "connection_boundary_observation":
    "sampled_current_state_evidence_v1",

  "source_health_status":
    "healthy" | "degraded" | "stale" | "unavailable",

  "source_health_reason": "...",

  "rate_evidence_status":
    "complete"
    | "partial"
    | "insufficient_data"
    | "not_applicable",

  "population_complete": true | false,

  "scoped_client_row_count": N | null,
  "known_authorized_count": N | null,
  "unknown_auth_count": N | null,
  "population_count": N | null,

  "rate_valid_count": N | null,
  "rate_partial_count": N | null,
  "rate_unavailable_count": N | null,

  "current_capture_started_at": "... | null",
  "baseline_capture_started_at": "... | null",
  "elapsed_seconds": number | null
}
```

No guest item from the `limit=1` page enters the Evidence response.

---

## 38. Online scope

```text
{
  "kind": "current_authorized_population",
  "evaluated_at_utc": "<Evidence evaluated_at>"
}
```

---

## 39. Completed evidence

Frozen product-level projection:

```text
{
  "status":
    "ok"
    | "partial"
    | "insufficient_data"
    | "unavailable",

  "metric_version":
    "network_traffic_completed_guest_session_observed_bytes.v1",

  "session_method":
    "closed_visit_completion_cohort.v1",

  "attribution_method":
    "visit_window_observation_counter_interval_sum.v1",

  "continuity_method":
    "observation_uptime_progress.v1",

  "visits_source_status":
    "healthy" | "unavailable",

  "observations_source_status":
    "healthy" | "unavailable" | "not_required",

  "complete_count": N,
  "partial_count": N,
  "insufficient_data_count": N,
  "unavailable_count": N,

  "reason_counts": {
    "<accepted public reason code>": N
  }
}
```

Evidence status counts are derived only from the returned first-page items.

---

## 40. Completed reason-code allowlist

The only machine reason keys allowed in `reason_counts` are:

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

Zero-count reasons may be omitted.

Unexpected/private reason:

```text
MUST NOT be passed through
```

Projection must fail that product safely as:

```text
delivery_status=failed
failure_category=integrity_unavailable
```

unless an already-defined accepted safe serializer maps it differently.

No raw reason text.

---

# PART IX — REASON AND ALLOWLIST POLICY

## 41. Public reason preservation

Where TRAFFIC-09 aggregates source-specific reasons:

```text
accepted public machine code
→ count only
```

Example:

```text
continuity_frozen=94
gap_too_large=3
counter_reset=1
```

No semantic remapping such as:

```text
continuity_frozen
gap_too_large
counter_reset
→ "poor_quality"
```

is allowed.

---

## 42. Strict allowlisting

Every reason-bearing Evidence projection must use an explicit fixed public allowlist derived from the accepted product serializer/contract.

Unexpected value:

```text
fail closed for affected product Evidence projection
```

It must never become:

```text
raw string passthrough
```

---

# PART X — APPLICATION ARCHITECTURE

## 43. Application component

Introduce one bounded application component, working canonical name:

```text
TrafficEvidenceAggregator
```

Role:

```text
application-level orchestrator / mapper
```

Not:

```text
Traffic analytics service
Traffic semantic owner
storage owner
scheduler owner
collector owner
```

---

## 44. Responsibilities

`TrafficEvidenceAggregator` may:

```text
receive one resolved Site
receive one resolved Evidence range/evaluation context
receive enabled/disabled product exposure state
invoke/reuse canonical product owners
compose existing Current→Historical AP dependencies
count already accepted classifications/reasons
map validated evidence into Evidence DTO
isolate safe per-group failures
```

It must not:

```text
query raw DB tables
query Omada
calculate Current Mbps
calculate Historical buckets
calculate Statistics
calculate Peak
calculate AP rates
calculate AP Share
calculate Online rates
calculate Completed bytes
reimplement freshness logic
reimplement continuity logic
reimplement source selection
```

---

# PART XI — ONE ADMIN EXECUTION SLOT

## 45. Exact execution ownership

One Evidence HTTP request consumes exactly:

```text
ONE AdminQueryExecutionControls slot
```

Required structure:

```text
AdminQueryService.traffic_evidence(...)
        ↓
ONE _run(...)
        ↓
ONE QueryDeadline
        ↓
TrafficEvidenceAggregator
        ↓
bounded semantic-owner calls
```

---

## 46. Recursive `_run()` is forbidden

Inside Evidence execution, implementation MUST NOT call public `AdminQueryService` methods that reacquire the semaphore, including:

```text
current_traffic_summary()
historical_traffic_history()
current_guest_traffic()
completed_guest_session_traffic()
```

when those methods internally call `_run()`.

Forbidden shape:

```text
traffic_evidence()
→ _run()
  → historical_traffic_history()
    → _run()
```

No recursive semaphore acquisition.

No one slot per product.

---

## 47. Behavior-preserving internal reuse

Where accepted orchestration currently lives inside public `AdminQueryService` methods, implementation should:

```text
extract/reuse bounded internal helper
```

rather than copy the logic.

Any refactor must be:

```text
behavior-preserving
```

for existing endpoints.

Existing endpoint output semantics must remain unchanged.

---

# PART XII — FOUR CANONICAL READ GROUPS

## 48. Group limit

Freeze:

```text
MAX_CANONICAL_READ_GROUPS_PER_EVIDENCE_REQUEST=4
```

Groups:

```text
1 Current
2 Historical
3 Online
4 Completed
```

The group limit is architectural.

It is not equivalent to "exactly four Python function calls".

---

## 49. Exact lower-level call bounds

With all eight products enabled:

```text
Current Site summary <=1

Current AP bounded page <=1
only when required by accepted AP/AP Share composition

Historical semantic read <=1

Online semantic read <=1

Completed semantic read <=1
```

No N+1.

No per-AP read loop.

No per-guest read loop.

No per-Visit read loop.

No pagination loop.

---

# PART XIII — CURRENT / HISTORICAL COMPOSITION

## 50. Current evidence obtained once

Current Site evidence is obtained at most once.

The same accepted Current result must be reused for:

```text
Current Network Evidence
+
Historical AP/AP Share current-population dependency
```

where required.

Forbidden:

```text
Current call for Current Evidence
+
Current call for Traffic by AP
+
Current call for AP Share
```

---

## 51. Current AP companion read

The existing historical AP/AP Share composition may require one bounded Current AP page.

Maximum:

```text
Current AP bounded page <=1
```

Only if enabled products require it.

No pagination loop.

Existing supported AP-population bound remains authoritative.

TRAFFIC-09 must not bypass:

```text
supported_max_ap_count=12
```

---

## 52. Historical call

The five historical products must come from one semantic call.

Conceptually:

```text
HistoricalTrafficReadService.get_site_history(
  include_history=<enabled>,
  include_period_statistics=<enabled>,
  include_peak_load=<enabled>,
  include_ap_traffic=<enabled>,
  include_ap_share=<enabled>
)
```

No separate:

```text
History query
Statistics query
Peak query
AP query
AP Share query
```

---

## 53. Existing AP composition semantics

Where current code composes Historical AP data using Current owner evidence:

```text
reuse that accepted composition behavior
```

TRAFFIC-09 MUST NOT create a new AP population algorithm.

No Historical semantic change is authorized.

---

# PART XIV — SEQUENTIAL BACKEND EXECUTION

## 54. Default execution model

Freeze initial implementation model:

```text
sequential canonical group execution
inside one Admin query deadline
```

Reasons:

```text
bounded SQLite load
predictable deadline accounting
simple failure isolation
no private concurrency domain
no request amplification
```

No private:

```text
ThreadPool
executor
worker
process
async scheduler
```

for TRAFFIC-09.

---

## 55. Concurrency exception boundary

If mandatory PERF cannot pass sequentially:

```text
STOP
```

Tech Lead must return measured evidence.

Any alternative execution model requires:

```text
same semantic owners
same group/call bounds
same one Admin slot ownership
no new scheduler/worker
measured justification
Architecture approval before implementation change
```

No timeout increase is the default remedy.

---

# PART XV — FAILURE ISOLATION

## 56. Group failure model

Independent groups:

```text
Current
Historical
Online
Completed
```

may fail independently.

Historical is one shared group for:

```text
history
statistics
peak
aps
apshare
```

Therefore one Historical delivery failure may legitimately mark those five products failed together.

---

## 57. Safe group failure

If a semantic group raises/cannot safely project:

```text
source unavailable exception
deadline exception
integrity exception
runtime unavailable condition
unexpected safe-caught exception
```

the endpoint may still return HTTP 200 if the aggregator itself remains safe.

Affected product(s):

```text
delivery_status=failed
evidence=null
failure_category=<fixed safe category>
```

Independent successful groups remain available.

---

## 58. All groups fail

Accepted:

```text
all attempted groups fail
+
TrafficEvidenceAggregator safely classifies all failures
+
outer/result serialization remains valid
→ HTTP 200
```

This response describes delivery failure state.

It does not pretend data exists.

---

## 59. Endpoint-level failure

Normal Admin error handling remains for:

```text
request validation
authentication
Site authorization
Admin concurrency rejection
outer Evidence serialization integrity failure
aggregator structural integrity failure
```

These remain normal Admin 4xx/5xx.

---

# PART XVI — SECURITY / PRIVACY

## 60. Capability requirement

Evidence endpoint requires BOTH:

```text
admin.read.overview
AND
admin.read.devices
```

for the same resolved Site.

If either fails:

```text
403 site_forbidden
```

using existing Admin behavior.

---

## 61. Same-Site invariant

All group reads receive exactly the same resolved:

```text
site_id
```

No cross-Site aggregation.

No fallback Site.

No multi-Site Evidence v1.

---

## 62. Identifier minimization

Evidence API MUST NOT expose:

```text
client MAC
AP MAC
Visit ID
guest name
client name
IP address
SSID associated with a specific client/session
raw cursor
raw rows
per-client rate
per-session bytes
authorization tokens
cookies
credentials
exception text
DB paths
SQL
```

AP/guest/session evidence is aggregate-only.

---

# PART XVII — FRONTEND / UI

## 63. Placement

Place:

```text
TRAFFIC EVIDENCE
```

after the existing eight functional Traffic panels.

---

## 64. Functional hierarchy

```text
TRAFFIC EVIDENCE

Evidence Range:
24h | 7d

Current evidence:
  Current Network Throughput
  Online Guests Traffic

Range evidence:
  Network Traffic History
  Period Statistics
  Peak Load
  Traffic by AP
  AP Traffic Share
  Completed Guest Session Traffic
```

---

## 65. Minimum visual content

Each product must expose enough to understand:

```text
Product
Scope
Native status/evidence state
Delivery state only when failed/not attempted
Freshness/source state where applicable
Coverage where applicable
Top/native reason counts where applicable
Observation/evaluation provenance where applicable
```

No chart required.

---

## 66. Completed visual honesty

Completed must show:

```text
First page
Returned: N
More available: Yes/No
```

when appropriate.

If `has_more=true`, wording must not imply entire cohort.

---

## 67. No visual score

Forbidden:

```text
overall status banner
quality grade
traffic health score
red/yellow/green synthesized global state
```

Individual native product states may be styled by Web Designer without changing meaning.

---

# PART XVIII — HISTORICAL BROKER / COORDINATOR

## 68. Existing owners retained

Frontend Evidence reuses:

```text
CaptivPortalTrafficCoordinator
TrafficHistoricalRequestBroker
```

No second:

```text
scheduler
broker
global refresh owner
timer
AbortController owner
```

---

## 69. Evidence job classification

Conceptually register Evidence as:

```text
historicalLane=true
historicalLaneGuard=true
autoRefresh=false
```

Evidence is one endpoint job.

It is not coalesced into ordinary Historical projection HTTP batches.

---

## 70. Exact guard compatibility

Existing legacy History job remains:

```text
historicalLane=true
historicalLaneGuard=false
```

Existing Completed job remains:

```text
historicalLane=true
historicalLaneGuard=true
```

New Evidence job:

```text
historicalLane=true
historicalLaneGuard=true
```

Therefore:

```text
History:
guard=false

Completed:
guard=true

Evidence:
guard=true
```

TRAFFIC-09 MUST NOT turn the existing 3-second guard into a generic delay for legacy History.

---

## 71. Historical in-flight invariant

Permanent:

```text
max historical HTTP requests in flight
from one Traffic page
=
1
```

Remains unchanged.

---

## 72. Admission guard

Existing:

```text
HISTORICAL_TRAFFIC_REQUEST_ADMISSION_GUARD_SECONDS=3
```

remains authoritative for guard-enabled jobs.

TRAFFIC-09 does not modify its duration.

---

## 73. Broker intent safety

Must preserve:

```text
generation safety
supersession safety
shared in-flight safety
backoff
Retry-After
Global Refresh ownership
range isolation
```

Obsolete Evidence response MUST NOT overwrite a newer Evidence range selection.

---

## 74. Pending Evidence intents

Rapid same-panel Evidence intents may collapse to latest under existing broker semantics.

No unbounded queue.

No infinite retry loop.

---

## 75. Fairness

Mandatory acceptance:

```text
Evidence does not permanently starve
History/Statistics/Peak/AP/AP Share intent

existing historical panels do not permanently starve
explicit Evidence intent
```

Exact priority implementation belongs to Tech Lead decomposition, but the fairness invariant is frozen.

---

# PART XIX — FEATURE FLAG

## 76. New feature flag

Freeze:

```text
WEB_ADMIN_TRAFFIC_EVIDENCE_ENABLED=false
```

Repository default:

```text
false
```

Dependencies:

```text
WEB_ADMIN_ENABLED=true
WEB_ADMIN_TRAFFIC_ENABLED=true
```

It does not require all eight product flags to be enabled.

---

## 77. Fixed product inventory under disabled flags

The Evidence response contract always knows the fixed eight product keys.

Per-product feature disabled:

```text
exposure_status=disabled
delivery_status=not_attempted
evidence=null
failure_category=null
```

No semantic call is made solely for it.

---

## 78. Feature OFF compatibility

With Evidence flag false:

```text
Evidence UI absent
Evidence endpoint disabled/404
Evidence frontend job absent
Evidence broker intent absent
Evidence semantic reads=0
Evidence source workload=0
existing eight products unchanged
```

This is the primary compatibility and rollback boundary.

---

# PART XX — PERFORMANCE / CAPACITY

## 79. Existing global limits remain

No increase authorized to:

```text
WEB_ADMIN_MAX_CONCURRENT_QUERIES=4

WEB_ADMIN_MAX_QUERY_DURATION_SECONDS=25

WEB_ADMIN_TRAFFIC_REQUEST_TIMEOUT_SECONDS=30
```

---

## 80. Mandatory PERF fixture

Measure:

```text
full authenticated HTTP Evidence request
all production-enabled Traffic products
representative production-size fixture
```

Not internal service-only timings.

---

## 81. Frozen latency thresholds

For `24h`:

```text
runs >=10
p95 <=5.0s
max <=10.0s
```

For `7d`:

```text
runs >=10
p95 <=7.0s
max <=12.0s
```

---

## 82. Payload limit

Freeze:

```text
Evidence HTTP payload <=64 KiB
```

---

## 83. Payload exclusions

Evidence must not contain:

```text
historical bucket arrays
AP time-series arrays
per-AP traffic values
guest rows
Visit rows
session byte values
raw source rows
raw cursors
```

---

## 84. Mandatory fan-out proof

Every PERF/acceptance run with all products enabled must prove:

```text
canonical groups <=4

Current Site summary <=1
Current AP bounded page <=1 when required
Historical <=1
Online <=1
Completed <=1
```

Also:

```text
new Omada calls=0
query-time provider calls=0
source writes=0
new collection cycles=0
new worker=0
new scheduler=0
unexpected 5xx=0
query deadline failures=0
```

---

# PART XXI — TEST CONTRACT

## 85. Focused semantic tests

Coder TASK-scoped tests must prove:

```text
all 8 fixed product IDs

exact common wrapper

exact scope kinds

outer admin.read.v1 preserved

inner admin.traffic.evidence.v1 preserved

native status != delivery status

missing != zero

reason allowlists

identifier minimization

range resolution once

same evaluated context

fan-out bounds

one Admin semaphore slot
```

---

## 86. Required delivery/native-state test

Mandatory explicit regression:

```text
canonical owner returns a valid native unavailable/partial/etc state
```

Expected:

```text
delivery_status=available
failure_category=null
native status retained in evidence
```

Must include at least:

```text
Completed status=unavailable

History status=partial

Online status=insufficient_data

AP Share status=unsupported_population
```

---

## 87. Failure classification tests

Each safe failure family must prove:

```text
affected product/group:
delivery_status=failed
evidence=null
safe failure_category

independent successful groups preserved
```

No raw exception text.

---

## 88. Range tests

Must prove:

```text
one resolve_traffic_network_range() call per Evidence request

same range/evaluated context used by Historical

Completed resulting range exactly matches Evidence range

Current/Online evaluated context matches where supported

changing Evidence range does not mutate functional panels
```

---

## 89. Online test

Must prove:

```text
limit=1
cursor=None

root population-wide counts remain canonical

returned guest item is not serialized into Evidence
```

---

## 90. Completed test

Must prove:

```text
limit=100
cursor=None

returned_count correct

has_more derived safely

first-page evidence counts correct

no Visit/client identifiers serialized

reason allowlist enforced

no second page requested
```

---

## 91. Historical group test

All five enabled:

```text
history
statistics
peak
aps
apshare
```

must result in:

```text
HistoricalTrafficReadService semantic read <=1
```

and accepted current AP composition must remain behavior-identical.

---

## 92. Semaphore test

Must prove one Evidence API request invokes:

```text
AdminQueryExecutionControls.run
exactly once
```

and does not recursively call public `_run()`-owning Admin query methods.

---

# PART XXII — BROKER / FRONTEND ACCEPTANCE

## 93. Mandatory scenarios

### Scenario 1 — Initial page

```text
existing historical panels + Evidence coexist
historical HTTP in-flight <=1
```

### Scenario 2 — Evidence 24h → 7d

```text
Evidence changes
functional panel ranges unchanged
```

### Scenario 3 — Existing panel range change while Evidence pending

```text
no cross-range corruption
```

### Scenario 4 — Global Refresh

```text
one existing coordinator owns refresh
no second scheduler
```

### Scenario 5 — Rapid Evidence intents

```text
bounded/collapsed
no unbounded queue
```

### Scenario 6 — Fairness

```text
no permanent starvation
```

### Scenario 7 — Backoff

```text
Retry-After/backoff/admission guard preserved
```

### Scenario 8 — Supersession

```text
obsolete Evidence response cannot overwrite newer range
```

### Scenario 9 — Legacy History guard

Must prove TRAFFIC-09 does not change:

```text
History guard=false
```

while:

```text
Completed guard=true
Evidence guard=true
```

---

# PART XXIII — ACCEPTANCE ROUTE

## 94. Execution mode

Freeze for future implementation TASK:

```text
EXECUTION_MODE=
PATCH / exact candidate
```

Coder:

```text
TASK-scoped implementation
+
focused/minimal tests only
```

---

## 95. Mandatory acceptance gates

Freeze:

```text
WINDOWS CENTRAL LAB=
MANDATORY

FRESH CENTRAL FULL GATE=
YES

OWNER LINUX LAB=
YES

PERF=
YES

BROWSER/FRONTEND ORCHESTRATION GATE=
YES

PRODUCTION DORMANT DEPLOY=
YES

SEPARATE ACTIVATION=
YES

PRODUCTION SMOKE=
MANDATORY
```

---

## 96. Exact candidate identity

Before official acceptance, exact candidate must be frozen using:

```text
FINAL_BASELINE_SHA
FINAL_BASELINE_TREE

candidate git write-tree

cumulative patch SHA256
```

If a local LAB ONLY commit is used:

```text
record local candidate commit
+
verify its tree equals accepted candidate write-tree
```

Publication identity is created only after mandatory gates pass.

---

## 97. Acceptance before publication

Permanent project sequence:

```text
Patch
→ Lab
→ all mandatory gates PASS
→ exact candidate accepted
→ Git publication
→ PR
→ Owner merge
→ Production dormant deploy
→ separate activation
→ production verification
```

Normal publication before mandatory acceptance is not authorized.

---

# PART XXIV — IMPLEMENTATION SCOPE BOUNDARY

## 98. Likely implementation files

Tech Lead may define the exact allowed list from this architecture.

Likely scope:

```text
app/config.py
app/settings.py
.env.example

app/admin_web/config.py
app/admin_web/runtime.py
app/admin_web/query_service.py
app/admin_web/routes.py

new Traffic Evidence aggregation module
new Traffic Evidence serialization module

app/admin_web/templates/admin/traffic.html
app/admin_web/static/admin.js
app/admin_web/static/admin.css

TASK-scoped tests
```

This is architectural expectation, not final Coder allowed-file list.

---

## 99. Scope expansion rule

If Tech Lead determines a required implementation file is outside the eventual allowed list:

```text
STOP
→ request minimal explicit scope expansion
```

No convenience refactor.

No unrelated cleanup.

---

# PART XXV — REUSE / NO-TOUCH MATRIX

## 100. Required reuse

Reuse accepted semantics from:

```text
CurrentTrafficReadService
HistoricalTrafficReadService
CurrentGuestTrafficReadService
CompletedGuestSessionTrafficReadService

existing Current→Historical AP composition

resolve_traffic_network_range()

AdminQueryExecutionControls

Admin admin.read.v1 envelope

CaptivPortalTrafficCoordinator

TrafficHistoricalRequestBroker

existing Traffic serializers/contracts
```

---

## 101. Explicit no-touch contracts

TRAFFIC-09 MUST NOT change:

```text
Current Mbps formulas
Current freshness thresholds/semantics
Current wired/lan selection

Historical bucket semantics
Historical source selection
Historical range semantics

Statistics formulas
Statistics interval semantics

Peak formulas
Peak ordering/tie-break semantics

Traffic by AP rates
Traffic by AP population method
supported AP maximum

AP Share contribution formula
AP Share denominator semantics
AP Share population method

Online Guest population semantics
Online rate semantics
Online continuity semantics

Completed Visit identity
Completed cohort semantics
Completed attribution
Completed evidence semantics
Completed reason codes

Observation acquisition
Current State acquisition
Visit Lifecycle

Historical Traffic Projection contract

global Admin API envelope

Traffic coordinator ownership

historical broker ownership

existing History admission-guard exemption
```

If implementation proves a change is required:

```text
STOP
→ Architect + Tech Lead review
→ amend architecture or create separate TASK
```

---

# PART XXVI — DEPLOYMENT / ACTIVATION / ROLLBACK

## 102. Dormant deploy

First production deploy:

```text
FROM GIT

WEB_ADMIN_TRAFFIC_EVIDENCE_ENABLED=false
```

Mandatory dormant checks:

```text
captive-portal.service healthy

existing eight Traffic products unchanged

Evidence area absent

Evidence endpoint disabled/404

Evidence frontend job absent

Evidence broker intent absent

no Evidence source workload

Observation healthy
Current State healthy
Visit Lifecycle healthy
Historical Projection healthy
```

---

## 103. Activation

Only after explicit Owner authorization:

```text
WEB_ADMIN_TRAFFIC_EVIDENCE_ENABLED=true
```

Activation is separate from deploy.

---

## 104. Production smoke

Must verify:

```text
Traffic page=200
Evidence endpoint=200

outer api_version=admin.read.v1

result.contract_version=
admin.traffic.evidence.v1

page=null

all eight fixed product keys present

default Evidence UI range=24h

24h → 7d → 24h works

functional ranges unchanged

Current and Online show current scopes

historical five show Evidence range

Completed shows first-page scope

no identifiers

no overall score

historical in-flight invariant preserved

existing Traffic panels remain healthy
```

---

## 105. Rollback

Primary rollback:

```text
WEB_ADMIN_TRAFFIC_EVIDENCE_ENABLED=false
```

No:

```text
DB rollback
schema rollback
collector rollback
Historical Projection rollback
source rollback
```

is expected.

If code rollback is required, normal Git-based rollback applies.

---

# PART XXVII — FINAL ACCEPTANCE CRITERIA

## 106. Architecture PASS criteria

```text
8 fixed products represented

4 fixed scope kinds only

exact wrapper preserved

outer admin.read.v1 preserved

inner admin.traffic.evidence.v1 preserved

one range resolver

one evaluated context

one Admin execution slot

canonical groups <=4

Current reused

Historical <=1 semantic read

Online limit=1

Completed limit=100 first page only

native state != delivery state

reason allowlists

no identifiers

no score

no normalization

no new source infrastructure

existing broker semantics preserved
```

---

## 107. Implementation PASS criteria

```text
all TASK-focused tests PASS

no new TASK regressions

fresh Windows Central full gate PASS

Linux production-compatible gate PASS

PERF PASS

payload PASS

browser orchestration gate PASS

exact candidate identity verified

mandatory fan-out proof PASS
```

---

## 108. Publication condition

```text
PUBLICATION_AUTHORIZED
IFF
all mandatory exact-candidate acceptance gates PASS
AND
Owner + Tech Lead accept candidate
```

---

## 109. Production completion condition

```text
TRAFFIC-09 COMPLETE
IFF

implementation accepted
+
publication complete
+
Owner merge complete
+
dormant production deploy PASS
+
separate activation authorized
+
production smoke PASS
+
no new regression
+
Knowledge Base reconciled
```

---

## 110. Traffic Section v1 completion

After TRAFFIC-09 closure:

```text
TRAFFIC SECTION v1 COMPLETE
```

may be recorded.

This does not pull future:

```text
TRAFFIC-10
TRAFFIC-11
TRAFFIC-12
future Home work
```

into v1.

---

# PART XXVIII — STOP CONDITIONS

## 111. Architecture stop conditions

Stop affected implementation if any of these becomes necessary:

```text
second Traffic semantic owner

new quality algorithm

new Traffic metric

new DB/schema

new collector/polling

query-time Omada

second scheduler/broker

recursive Admin semaphore acquisition

more than bounded read limits

whole-cohort Completed scan

bypass AP supported population bound

global Admin envelope change

new universal metric_version

raw/private reason passthrough

identifier exposure

timeout increase required to pass PERF

existing History guard semantics change
```

Return to Architect + Tech Lead.

---

# PART XXIX — CURRENT FINAL STATE

## 112. Frozen status

```text
TASK=
TASK-TRAFFIC-09 — Consolidated Traffic Evidence / Quality

ARCHITECTURE=
FINAL

ROADMAP_ASSIGNMENT=
ACCEPTED

FINAL_BASELINE_SHA=
f57d3550ffd2e1e48f24092666d861a959c57e40

FINAL_BASELINE_TREE=
0b9aac6be763d041e674970d17ce0fd0d6bee557

DRIFT_CLASSIFICATION=
NO_DRIFT

PRODUCTION_RUNTIME_SHA=
df91355a99d2561abc9c4d6d4bb6f5a968d327b3

PRODUCTION_RUNTIME_TREE=
1161739c6b4fe90fa08928556746a5a4ea6af4cd

PRODUCT_IDS=
current
history
statistics
peak
aps
apshare
online_guests
completed_sessions

SCOPE_KINDS=
current_snapshot
current_authorized_population
historical_range
completion_first_page

OUTER_API=
admin.read.v1

INNER_CONTRACT=
admin.traffic.evidence.v1

ENDPOINT=
GET /admin/api/v1/sites/<site_id>/traffic/evidence?range=24h|7d

RANGE=
required
24h|7d

ONE_RANGE_RESOLVER=
REQUIRED

ONE_EVALUATION_CONTEXT=
REQUIRED

ADMIN_QUERY_SLOTS_PER_REQUEST=
1

MAX_CANONICAL_READ_GROUPS=
4

CURRENT_SITE_CALLS=
<=1

CURRENT_AP_CALLS=
<=1 WHEN REQUIRED

HISTORICAL_CALLS=
<=1

ONLINE_CALLS=
<=1

ONLINE_LIMIT=
1

COMPLETED_CALLS=
<=1

COMPLETED_LIMIT=
100

COMPLETED_CURSOR=
null

COMPLETED_SCOPE=
FIRST PAGE ONLY

HISTORICAL_HTTP_IN_FLIGHT_PER_PAGE=
1

HISTORY_GUARD=
false

COMPLETED_GUARD=
true

EVIDENCE_GUARD=
true

EVIDENCE_AUTO_REFRESH=
false

OVERALL_SCORE=
FORBIDDEN

NORMALIZED_STATUS=
FORBIDDEN

UNIVERSAL_METRIC_VERSION=
FORBIDDEN

NEW_COLLECTOR=
NO

NEW_DB=
NO

SCHEMA_CHANGE=
NO

QUERY_TIME_OMADA=
NO

NEW_WORKER=
NO

NEW_SCHEDULER=
NO

IMPLEMENTATION_AUTHORIZATION=
NOT GRANTED

CODER_AUTHORIZATION=
NOT GRANTED
```

---

# 113. Next process step

The only next project step authorized by this document is:

```text
Tech Lead
→ FINAL contract/decomposition review
→ prepare exact implementation TASK
```

The Tech Lead implementation TASK must freeze:

```text
exact allowed/forbidden files
exact internal helper boundaries
exact focused test commands
exact Central Lab commands
exact Linux/PERF commands
candidate identity procedure
handoff requirements
repository permissions/actions
```

After Tech Lead decomposition:

```text
Owner reviews/accepts implementation TASK
```

Only then may Coder implementation be authorized.

---

# FINAL ARCHITECT VERDICT

```text
TASK-TRAFFIC-09 ARCHITECTURE = FINAL

TECH LEAD REVIEW CORRECTIONS = INCORPORATED

BASELINE REBIND = PASS

DRIFT = NO_DRIFT

ROADMAP ASSIGNMENT = ACCEPTED

ARCHITECTURAL BLOCKERS = NONE

READY FOR TECH LEAD FINAL DECOMPOSITION REVIEW = YES

READY FOR CODER = NO

IMPLEMENTATION AUTHORIZATION = NOT GRANTED
```