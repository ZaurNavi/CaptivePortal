# TASK-TRAFFIC-RANGE-01 — Independent Traffic Range per Panel — FINAL

**Project:** CaptivPortal  
**Area:** Admin Console → Traffic  
**Type:** orchestration / API request-scope / frontend state separation  
**Status:** `FINAL — OWNER + TECH LEAD REVIEW INCORPORATED / 24h PERF CONTRACT FROZEN / FOR FINAL VERIFICATION`  
**Implementation authorization:** `NOT GRANTED BY THIS FINAL; REQUIRES SEPARATE OWNER AUTHORIZATION`  
**Code / PR / merge / deploy / activation:** `NOT AUTHORIZED`  
**Prepared:** 2026-09-01

---

# 0. Executive decision

This TASK changes only Traffic request orchestration, API projection scope, and frontend range state.

It does **not** change Network Traffic metric semantics.

The following historical Traffic products receive independent `24h | 7d` selectors:

- Network Traffic History
- Period Statistics
- Peak Load
- Traffic by AP

Target state example:

```text
History          = 24h
Statistics       = 7d
Peak Load        = 24h
Traffic by AP    = 7d
```

Each panel owns its own:

```text
selected range
applied range
request state
last successful payload
error state
```

Permanent objective:

```text
a 7d intent for one panel
MUST NOT automatically require
all other historical Traffic products to run at 7d
```

Recommended architecture:

```text
per-panel range state
        ↓
Traffic Historical Request Broker
        ↓
existing Traffic Coordinator request lifecycle
        ↓
one historical request in flight at a time
        +
minimum 10-second historical dispatch admission interval
        ↓
existing /traffic/history endpoint
with exact product projection
        ↓
HistoricalTrafficReadService
same semantic owner
```

No timeout/deadline increase.

Permanent client-side safety constant:

```text
HISTORICAL_TRAFFIC_REQUEST_ADMISSION_GUARD_SECONDS = 10
```

Exact frontend/internal constant name is implementation detail.

This value is NOT:

```text
QueryDeadline
HTTP/browser timeout
Retry-After
server concurrency
selector debounce
```

It is a page-local historical-request admission guard.

---

# 1. Current repository baseline

Repository was re-fetched before this DRAFT.

```text
origin/main =
8a5c4db899406eeb1f737abe63495247be1ee75a

tree =
6837dd729dedb0df6414b3f979657a3f6f55d0ab
```

Current main is:

```text
Merge PR #93
TASK-TRAFFIC-05: Traffic by AP
```

FINAL re-fetch immediately before issuance confirms:

```text
origin/main =
8a5c4db899406eeb1f737abe63495247be1ee75a

tree =
6837dd729dedb0df6414b3f979657a3f6f55d0ab
```

Impact review:

```text
new commits since DRAFT R2 baseline:
NONE

runtime/config drift:
NONE

rebind required:
NO
```

This repository baseline already contains:

```text
Traffic by AP implementation
WEB_ADMIN_TRAFFIC_BY_AP_ENABLED
combined History/Statistics/Peak/AP request model
```

Before eventual FINAL and again before implementation authorization:

```text
re-fetch origin/main
re-pin SHA/tree
perform impact review
```

Mandatory impact review if newer main touches:

```text
app/analytics/**
app/admin_web/**
app/observations/**
app/config.py
app/settings.py
```

---

# 2. Production symptom motivating this TASK

Owner reports production after TRAFFIC-05 activation:

```text
24h:
History PASS
Statistics PASS
Peak PASS
Traffic by AP PASS
all APs visible
```

On shared range switch to `7d`, the current combined persisted History request reaches the existing server-side query deadline and returns:

```text
503 query_deadline
```

The service remains healthy.

The browser correctly retains previously accepted data.

This TASK does not reinterpret that 503 as a service crash.

---

# 3. Explicit non-solution

This TASK is **not**:

```text
increase QueryDeadline
increase browser timeout
increase Admin concurrency
```

The product idea is:

```text
scope expensive 7d work
to the panel the user actually asked to inspect
```

---

# 4. Current implementation facts

Current Traffic page has one shared:

```text
CaptivPortalTrafficNetworkRange
```

with:

```text
24h
7d
```

The selector is currently rendered in the Network Traffic History panel.

Statistics, Peak and Traffic by AP consume the same applied History range.

Current backend:

```text
GET /admin/api/v1/sites/<site_id>/traffic/history
```

accepts:

```text
range
include
```

Current exact include forms include:

```text
statistics
statistics,peak
aps
statistics,aps
statistics,peak,aps
```

Current route calls `AdminQueryService.historical_traffic_history(...)` once with include flags.

---

# 5. Current semantic owner

Canonical historical semantic owner remains:

```text
HistoricalTrafficReadService
```

Current method supports:

```text
include_period_statistics
include_peak_load
include_ap_traffic
```

TRAFFIC-05 also composes Current AP evidence through:

```text
CurrentTrafficReadService
```

No new semantic owner is required by this TASK.

---

# 6. Panels that receive independent range selectors

Exactly these current historical Traffic products receive their own selector:

```text
Network Traffic History
Period Statistics
Peak Load
Traffic by AP
```

Each gets:

```text
24h | 7d
```

---

# 7. Panel that does NOT receive a selector

`Current Network Throughput` does not receive 24h/7d controls.

Reason:

```text
it is a Current Traffic product,
not a selected historical range product
```

Its refresh lifecycle remains unchanged.

---

# 8. UX placement

Each historical panel places its selector in that panel header:

```text
[Panel title]                     [24h] [7d]
```

Example:

```text
Network Traffic History           [24h] [7d]
Period Statistics                 [24h] [7d]
Peak Load                         [24h] [7d]
Traffic by AP                     [24h] [7d]
```

No shared page-level historical selector remains visible when independent ranges are active.

---

# 9. Default range

On a fresh Traffic page load:

```text
History selected = 24h
Statistics selected = 24h
Peak selected = 24h
AP selected = 24h
```

Default remains `24h` for every historical panel.

---

# 10. Panel state model

Every range-sensitive panel has independent state:

```text
product_id
selected_range
applied_range
phase
last_successful_payload
last_error
intent_generation
```

Allowed selected/applied ranges:

```text
24h
7d
```

---

# 11. Panel phases

Recommended machine phases:

```text
initial
waiting
loading
ready
error_with_previous
error_empty
```

Product payload semantic status remains separate, e.g.:

```text
ok
partial
insufficient_data
unsupported_population
```

Request phase and product semantic status must not be merged.

---

# 12. Selected range

`selected_range` means the user's latest desired range for that panel.

Selector `aria-pressed` follows `selected_range`.

Changing one panel's selected range does not mutate another panel.

---

# 13. Applied range

`applied_range` means the range identity of that panel's last successfully accepted payload.

It changes only after:

```text
safe HTTP 200
+
valid product DTO
+
panel intent-generation check
```

It is never changed merely because the user pressed a button.

---

# 14. Selected/applied mismatch

Example:

```text
Statistics selected = 7d
Statistics applied = 24h
```

This is valid during waiting/loading or after a failed 7d request.

Old statistics remain explicitly labelled:

```text
Applied range · Last 24 hours
```

until 7d succeeds.

---

# 15. Initial loading

Before first successful payload:

```text
selected = 24h
applied = null
phase = initial/loading
```

No fake zero metrics.

---

# 16. Range-switch loading

Example:

```text
AP applied = 24h
user selects AP 7d
```

When the request is actually admitted:

```text
AP phase = loading
selected = 7d
applied = 24h
```

Previously accepted 24h AP data may remain visible and must remain labelled 24h.

---

# 17. Waiting vs Loading

Because historical requests are serialized:

`waiting` means:

```text
user selected a range
but this product's request has not started
```

`loading` means:

```text
an actual HTTP request containing this product
is in flight
```

Do not show `Loading 7d` while only queued.

A panel waiting behind the historical admission guard remains fully interactive.

Example:

```text
AP request starts at T+0

T+2:
Statistics selected 24h → 7d
```

Statistics immediately becomes:

```text
selected_range = 7d
phase = waiting
```

but does not become `loading` until its actual HTTP dispatch occurs.

---

# 18. Failure with previous data

If requested 7d returns 429/503/network failure and the panel already has accepted 24h data:

```text
selected = 7d
applied = 24h
phase = error_with_previous
```

UI meaning:

```text
7d could not be loaded.
Showing the previously accepted 24h result.
```

Do not call the old historical result stale unless an existing historical contract defines staleness.

---

# 19. Failure without previous data

If first load fails:

```text
applied = null
phase = error_empty
```

No numeric fabricated result.

Other panels remain usable.

---

# 20. Successful retry

If selected remains 7d and retry succeeds:

```text
applied = 7d
phase = ready
```

Only that panel's payload changes.

---

# 21. Product semantic states remain authoritative

Examples:

```text
Statistics 7d HTTP 200 / partial
→ applied Statistics = 7d
→ show Partial

AP 7d HTTP 200 / unsupported_population
→ applied AP = 7d
→ show unsupported_population

History 7d HTTP 200 / insufficient_data
→ applied History = 7d
```

HTTP 200 does not imply product `ok`.

---

# 22. Persistence decision

FINAL v1:

```text
panel range state exists only for the lifetime of the open Traffic page
```

Do not persist in:

```text
localStorage
sessionStorage
cookies
server profile
URL query string
```

A full page reload resets every historical panel to 24h.

---

# 23. Why no persistence in v1

Remembering 7d could make a later reload automatically recreate expensive 7d work without fresh user intent.

The primary goal is:

```text
explicit user-controlled expensive work
```

Therefore v1 does not restore old 7d preferences.

---

# 24. API architecture alternatives

## Option A — four dedicated endpoints

```text
/traffic/history
/traffic/statistics
/traffic/peak
/traffic/aps
```

Pros: clear API, strong product isolation.

Cons: duplicated routes and poor same-range coalescing.

## Option B — current `include` only

Pros: minimal backend changes.

Cons: current include contract encodes old coupling; Peak requires Statistics, and AP transport assumes outer History context.

## Option C — RECOMMENDED

Keep the existing endpoint and add explicit product projection:

```text
GET /admin/api/v1/sites/<site_id>/traffic/history
?range=<24h|7d>
&products=<canonical product subset>
```

FINAL selects Option C.

---

# 25. Existing endpoint remains canonical

Keep:

```text
GET /admin/api/v1/sites/<site_id>/traffic/history
```

This preserves:

```text
Site-scoped security
historical telemetry boundary
HistoricalTrafficReadService ownership
```

---

# 26. New `products` parameter

Canonical product identifiers:

```text
history
statistics
peak
aps
```

Examples:

```text
range=7d&products=history
range=7d&products=statistics
range=7d&products=peak
range=7d&products=aps
range=24h&products=history,peak
```

---

# 27. Canonical product ordering

Multiple products use fixed order:

```text
history
statistics
peak
aps
```

Any non-empty subset in that order is allowed.

Invalid examples:

```text
peak,history
aps,statistics
duplicate token
unknown token
empty products
whitespace variants
```

→ `400 invalid_request`.

---

# 28. Backward-compatible `include`

Existing `include` forms remain accepted for backward compatibility.

New per-panel frontend uses `products`.

`include` + `products` together:

```text
400 invalid_request
```

No silent precedence.

---

# 29. History product projection

`products=history` returns common historical context plus History buckets.

It does not calculate/serialize Period Statistics, Peak Load or Traffic by AP except internal canonical foundation work strictly required by the historical owner.

---

# 30. Statistics product projection

`products=statistics` returns common historical context plus `period_statistics`.

It must not calculate Peak Load temporal products or Traffic by AP.

Unrelated History chart serialization is not required.

---

# 31. Peak product projection

`products=peak` returns common historical context plus `peak_load`.

It must not require the client to request `statistics` in the same HTTP request.

---

# 32. Peak/Statistics request decoupling

Current implementation requires:

```text
include_peak_load
requires
include_period_statistics
```

This is request orchestration coupling, not permanent metric semantics.

This TASK may remove that request-level dependency while preserving exact existing Peak formulas and identity.

---

# 33. Shared internal Peak-values primitive

Recommended internal refactor:

```text
accepted canonical Site samples
        ↓
shared internal PeakValues primitive
```

Consumers:

```text
Period Statistics Peak values
Peak Load
```

Statistics-only computes Average + shared PeakValues.

Peak-only computes shared PeakValues + temporal Peak products, without Period Average.

If both are requested, shared PeakValues are computed once.

---

# 34. AP product projection

`products=aps` returns common historical context plus `ap_traffic` and a compact AP bucket-axis context.

It must not calculate Period Statistics, Peak Load, or full Site History chart serialization.

---

# 35. AP aligned-series transport

Current AP encoding:

```text
outer_history_bucket_aligned_du.v1
```

must become self-contained for AP-only requests.

This TASK allows a transport-only context extension:

```text
ap_bucket_axis
```

without changing `network_traffic_by_ap.v1` metric semantics.

---

# 36. AP bucket-axis contract

FINAL recommendation:

```text
ap_bucket_axis:
  bucket_count
  bucket_seconds
  bucket_start_utc[]
```

Exact lengths:

```text
24h → 288
7d → 672
```

Every AP series index aligns to the corresponding bucket-axis index.

If History+AP are coalesced, serializer must prove the AP axis matches History bucket starts.

---

# 37. Common historical context

Every successful product-scoped response keeps one canonical:

```text
range
coverage
quality
```

Only requested product fields appear.

---

# 38. No metric-semantic change

This TASK must not alter:

```text
History bucket aggregation
Period Average
Period Peak
Peak Load methods/timestamps/ties
Busiest Bucket
Busiest 60 Minutes
Traffic by AP population
12-AP bound
unsupported_population
AP Average
AP Peak
AP Coverage
AP Site-source inheritance
```

Only request scope and panel orchestration change.

---

# 39. Site isolation remains permanent

Every product-scoped request remains bound to one authorized canonical Site.

Broker must never coalesce across different Site IDs.

---

# 40. Frontend architecture

Introduce a page-local:

```text
Traffic Historical Request Broker
```

It is not a semantic owner.

It owns only:

```text
panel request intents
same-range coalescing
pending queue
mapping response products to panel states
```

Network lifecycle remains owned by:

```text
CaptivPortalTrafficCoordinator
```

---

# 41. Why a broker is required

Four independently registered heavy loaders could create concurrent:

```text
History 7d
Statistics 7d
Peak 7d
AP 7d
```

and recreate request storm / 429 / deadline pressure.

The broker prevents this.

---

# 42. Historical request concurrency

Permanent client-side bound:

```text
maximum historical Traffic HTTP requests in flight
from one Traffic page
=
1
```

This does not change server Admin concurrency.

Current Network Throughput remains independent.

---

# 43. Historical Request Admission Guard — permanent rule

Add permanent orchestration guard:

```text
HISTORICAL_TRAFFIC_REQUEST_ADMISSION_GUARD_SECONDS = 10
```

The exact code symbol is implementation detail.

The broker/coordinator execution lane records:

```text
last_historical_dispatch_monotonic
```

at the moment an actual historical HTTP request is dispatched.

After at least one historical request has been dispatched, the next historical
request may start only when BOTH are true:

```text
1. no previous historical request is in flight

2. now >= last_historical_dispatch_monotonic + 10 seconds
```

Equivalent admission rule:

```text
next_dispatch
>=
max(
  previous_request_completion,
  previous_dispatch + 10s
)
```

subject also to any stricter coordinator backoff/Retry-After eligibility.

The first historical request on a fresh page has no prior dispatch and may be
admitted immediately.

---

# 44. Admission examples

Fast request:

```text
Request A starts     T+0
Request A completes  T+3
Request B pending

earliest B start:
T+10
```

Medium request:

```text
Request A starts     T+0
Request A completes  T+8
Request B pending

earliest B start:
T+10
```

Long request:

```text
Request A starts     T+0
Request A completes  T+12
Request B pending

earliest B start:
T+12
```

Permanent forbidden case:

```text
Request B starts at T+10
while Request A is still in flight
```

The guard is measured from previous **dispatch**, not previous completion.

Therefore a request lasting longer than 10 seconds does not create an additional
10-second cooldown after completion.

---

# 45. Broker pending state

Broker keeps latest pending intent per product:

```text
history
statistics
peak
aps
```

---


# 46. Admission waiting and pending-intent collapse

While a panel is waiting behind the admission guard:

```text
selector remains interactive
selected_range may change
phase remains waiting until real dispatch
```

Additional intents for the same waiting panel replace its prior pending intent.

Example:

```text
Statistics applied = 24h

user:
Statistics → 7d
Statistics → 24h
Statistics → 7d
```

before dispatch.

Only:

```text
Statistics = 7d
```

remains pending.

Obsolete pending requests MUST NOT execute merely because they were once queued.

Admission waiting is therefore also an opportunity to collapse obsolete work.

---
# 47. Same-range coalescing

Pending products with the same range may coalesce.

Example:

```text
History 24h
Peak 24h
```

→

```text
range=24h&products=history,peak
```

and:

```text
Statistics 7d
AP 7d
```

→

```text
range=7d&products=statistics,aps
```

Requests execute sequentially.

Admission waiting does not disable coalescing.

If during the same guard interval:

```text
Statistics → 7d
AP → 7d
```

and both remain current pending intents when the lane becomes admission-eligible,
they MAY be emitted as one:

```text
range=7d&products=statistics,aps
```

This is preferred over two unnecessary sequential 7d requests.

---

# 48. Single-panel intent

If user only changes:

```text
Traffic by AP
24h → 7d
```

exact product request is:

```text
range=7d&products=aps
```

No History/Statistics/Peak product projection is requested.

This is the central product requirement.

---

# 49. Initial page load coalescing

Fresh load: all enabled historical panels select 24h.

Broker coalesces them into one request, e.g.:

```text
range=24h&products=history,statistics,peak,aps
```

Thus working current 24h initial load remains one combined historical request.

---

# 50. Global Refresh

Global Refresh means:

```text
refresh every enabled panel
using that panel's selected range
```

It does not reset ranges.

Example:

```text
History 24h
Statistics 7d
Peak 24h
AP 7d
```

→ queued groups:

```text
24h → history,peak
7d → statistics,aps
```

executed sequentially.

The historical admission guard applies to Global Refresh exactly as it applies
to explicit panel intent.

Global Refresh MUST NOT bypass an active 10-second dispatch guard.

---

# 51. Panel range click

A range button queues only that product with its selected range.

It must not call `refreshAll()`.

---

# 52. Request ordering

Recommended priority:

```text
1. explicit single-panel user intent
2. queued global-refresh work
```

Within same priority: FIFO by first queued time.

Latest pending intent per panel replaces older pending intent before dispatch.

---


## Effective dispatch eligibility

Priority decides **which pending batch is next**, not **when it may start**.

For the chosen batch:

```text
dispatch_at
=
latest applicable eligibility condition
```

including:

```text
previous historical request completion

previous historical dispatch + 10s

coordinator Retry-After/backoff eligibility

page visibility/lifecycle eligibility
```

The 10-second guard applies equally to:

```text
explicit panel intent
queued Global Refresh work
manual retry work
```

No priority class bypasses the guard.

# 53. Pending-intent collapse

Example before dispatch:

```text
AP 7d
AP 24h
AP 7d
```

Only latest pending AP intent remains:

```text
AP 7d
```

---

# 54. In-flight batch supersession

A new intent for one panel must not abort a shared in-flight batch containing other products.

The in-flight batch may complete.

Its response applies only to products whose captured generation still matches.

Superseded panel results are ignored; latest intent remains queued.

---

# 55. Batch-level abort

Existing coordinator may still abort for:

```text
pagehide
global shutdown
session/auth termination
coordinator lifecycle stop
```

Panel range supersession alone does not require shared-batch abort.

---

# 56. Panel intent generation

Each panel increments an `intent_generation` when selected range changes or manual retry is created.

A product response applies only if captured generation and selected range still match.

---

# 57. Request failure

If one coalesced HTTP request returns 503, all products in that request fail for that generation.

Other panels not in the request remain untouched.

---

# 58. Product-local HTTP success

On HTTP 200 each requested product applies independently according to its existing semantic status.

---

# 59. Existing coordinator ownership

`CaptivPortalTrafficCoordinator` remains owner of:

```text
same-origin request helper
AbortController
browser timeout
Retry-After/backoff
visibility/pagehide lifecycle
global auth failure
request error classification
```

Broker must not duplicate these.

---

# 60. Coordinator extension allowed

A narrow coordinator/broker integration extension is allowed so coordinator can drain pending historical work without private broker timers.

Principle:

```text
coordinator schedules/drains
broker provides next pending historical batch
```

No second scheduler owner.

---

# 61. 429 behavior

Broker does not bypass Retry-After and does not launch concurrent historical retries.

Affected panels keep previous accepted data.

If the coordinator already enforces a longer Retry-After/backoff than the
10-second admission point, the longer constraint wins.

Conceptually:

```text
effective_next_dispatch
=
max(
  previous completion,
  previous dispatch + 10s,
  coordinator backoff / Retry-After eligibility
)
```

The new guard MUST NEVER shorten coordinator backoff.

---

# 62. 503 deadline behavior

If a panel-scoped 7d request still returns `503 query_deadline`, only products in that request enter request-error state.

Do not:

```text
increase deadline
silently fall back to 24h
change applied range
```

---

# 63. Important acceptance caveat

Independent range orchestration reduces unnecessary work but does not prove in advance that `Traffic by AP 7d` alone fits 10 seconds.

Therefore each product-scoped 7d request must be benchmarked.

If AP-only 7d still fails:

```text
STOP
→ evidence
→ separate AP-specific PERF remediation / architecture review
```

---

# 64. Historical read-layer projection model

Recommended narrow extension inside `HistoricalTrafficReadService`:

```text
explicit requested product projection set
```

Exact Python signature is implementation detail.

Permanent owner remains unchanged.

---

# 65. Common foundation work is allowed

Product-scoped request does not mean one SQL statement per product.

Allowed shared foundation includes:

```text
range validation
canonical cycle selection
source-family selection
coverage/watermark
canonical Site sample validation
bucket context when mathematically required
```

Requirement is:

```text
do not compute unrelated product-specific projections
```

---

# 66. Statistics-only work

May compute:

```text
canonical foundation
Period Average
shared PeakValues required by Period Statistics
```

Must not additionally compute:

```text
Peak Load temporal products
Traffic by AP
```

---

# 67. Peak-only work

May compute:

```text
canonical foundation
shared PeakValues
Peak timestamps
Busiest Bucket
Busiest 60 Minutes
```

Must not compute Period Average or AP projection unless a specific common primitive is mathematically necessary.

---

# 68. AP-only work

May compute:

```text
canonical Site source/bucket context
Site-scoped AP population
AP histories
AP Average
AP Peak
AP Coverage
Current AP composition
```

Must not additionally compute Period Statistics or Peak Load temporal products.

---

# 69. History-only work

Computes canonical Site History and History coverage/quality.

Must not additionally compute Statistics, Peak or AP projection.

---


# 70. Admission guard page lifecycle

Admission state is:

```text
page-local
memory-only
```

It is not stored in:

```text
localStorage
sessionStorage
cookies
server-side state
```

A full page reload resets:

```text
last_historical_dispatch_monotonic
pending broker intents
panel selected/applied orchestration state
```

together with the rest of page-lifetime Traffic orchestration.

The first historical request after reload may therefore dispatch immediately.

---

# 71. Admission guard scheduler ownership

The admission guard MUST NOT introduce a second independent scheduler.

Permanent ownership remains:

```text
CaptivPortalTrafficCoordinator
schedules/drains

TrafficHistoricalRequestBroker
supplies pending work
```

If a wake-up timer is required to resume the lane at:

```text
last_historical_dispatch_monotonic + 10s
```

that timer belongs to the existing coordinator execution lifecycle.

The broker must not own a parallel timer, interval, visibility handler,
AbortController or page lifecycle.

When page visibility/backoff rules delay execution beyond the 10-second point,
the next request starts only when all coordinator conditions are satisfied.

---
# 72. Feature flag

Recommended:

```text
WEB_ADMIN_TRAFFIC_INDEPENDENT_RANGES_ENABLED=false
```

Repository default false.

---

# 73. Feature dependencies

IndependentRanges=true requires:

```text
WEB_ADMIN_ENABLED=true
WEB_ADMIN_TRAFFIC_ENABLED=true
WEB_ADMIN_TRAFFIC_HISTORY_ENABLED=true
```

It does not require Statistics/Peak/AP flags.

---

# 74. Flag disabled behavior

When false:

```text
existing shared range UI remains
existing combined include behavior remains
```

No production behavior change before activation.

---

# 75. Flag enabled behavior

When true:

```text
shared selector removed/hidden
each enabled historical panel gets its own selector
new products projection model used
broker independent state active
```

---

# 76. Dormant deployment and rollback

Deploy accepted code with flag=false.

Dormant verification must prove current behavior unchanged.

Activation is a separate Owner action.

Rollback:

```text
WEB_ADMIN_TRAFFIC_INDEPENDENT_RANGES_ENABLED=false
```

No DB rollback.

---

# 77. API serializer contract

Common fields:

```text
range
coverage
quality
```

Only requested fields may appear:

```text
buckets             # history
period_statistics   # statistics
peak_load           # peak
ap_traffic          # aps
ap_bucket_axis       # AP transport context
```

Unrequested product appearing in canonical server DTO is fail-closed.

---

# 78. Product-list echo

Recommended response metadata:

```text
requested_products
```

Serializer validates exact request/response projection identity.

---

# 79. Telemetry

Historical telemetry should add:

```text
requested_products
product_count
```

No raw payload/SQL/AP series logging.

---

# 80. Applied range comes from server

Panel `applied_range` must come from validated:

```text
response.range.id
```

not from mutable selected state.

---

# 81. Timezone behavior

No change.

API remains UTC; browser formatting is presentation-only.

---

# 82. Metric backward compatibility

This TASK preserves:

```text
network_traffic_history.v1
network_traffic_period_statistics.v1
network_traffic_peak_load.v1
network_traffic_by_ap.v1
```

Transport/orchestration may change; metric semantics do not.

---

# 83. AP backward compatibility

No change to:

```text
current accepted AP
UNION
validated historical AP
per authorized canonical Site
hard max 12
>12 unsupported_population
no truncation
Average
Peak
Coverage
source-family inheritance
```

---

# 84. AP transport compatibility

A self-contained `ap_bucket_axis` is transport context only.

It must not alter AP series values or formulas.

---

# 85. Global auth/session failure

Existing coordinator global handling remains.

Session expiry is not a panel-local data error.

---

# 86. Route validation

New independent model accepts:

```text
range
products
```

Legacy include remains accepted in legacy shape.

Unknown/duplicate params remain 400.

---

# 87. Product feature gates

Requested product respects existing feature flag.

Examples:

```text
products=statistics + Statistics disabled → 404
products=peak + Peak disabled → 404
products=aps + By-AP disabled → 404
```

---

# 88. Product-specific failure isolation

A failed AP 7d request no longer automatically marks History/Statistics/Peak failed.

This is a core behavior change.

---

# 89. Coalesced failure trade-off

If History 24h + Peak 24h are coalesced and that request fails, both requested panel generations fail.

This is accepted.

They may later be retried independently.

---

# 90. Alternative 1 — no coalescing

One serialized request per panel.

Pros: strongest failure isolation.

Cons: initial 24h load and global refresh duplicate expensive foundation work.

Not recommended.

---

# 91. Alternative 2 — one request containing multiple panel ranges

Example:

```text
history=24h
statistics=7d
peak=24h
aps=7d
```

Rejected because one 7d failure could again fail unrelated 24h products and the query would contain multiple heavy ranges.

---

# 92. Recommended architecture summary

Use:

```text
independent panel state
+
same-range coalescing
+
one historical request in flight
+
products-scoped API
+
same HistoricalTrafficReadService
```

---

# 93. Mandatory PERF variants

On immutable production-size evidence measure:

```text
H24 / H7 = products=history
S24 / S7 = products=statistics
P24 / P7 = products=peak
A24 / A7 = products=aps
```

Use supported AP population evidence required by TRAFFIC-05.

---

# 94. PERF run count

Minimum:

```text
10 measured runs per variant
8 variants
80 measured product-scoped requests
```

Warmups unmeasured/documented.

---

# 95. PERF hard gates

Each supported variant:

```text
0 query_deadline
0 source-integrity failures
0 unexpected 5xx

p95 <= 8.0s
max <= 9.0s
```

under unchanged 10s QueryDeadline.

---

# 96. AP 7d gate

`A7` must pass current 10s deadline in controlled supported-population evidence.

If not:

```text
TASK acceptance FAILS
STOP
→ separate AP performance review
```

---

# 97. 24h backward compatibility PERF — exact canonical PASS/FAIL contract

This FINAL freezes the pre-change combined-24h regression gate.

## Canonical baseline identity

The accepted pre-change baseline is the exact merged TRAFFIC-05 repository artifact:

```text
baseline code commit:
8a5c4db899406eeb1f737abe63495247be1ee75a

baseline tree:
6837dd729dedb0df6414b3f979657a3f6f55d0ab
```

Canonical baseline request:

```text
GET /admin/api/v1/sites/<site_id>/traffic/history
?range=24h
&include=statistics,peak,aps
```

with the corresponding existing Traffic product flags enabled in the controlled
Lab configuration.

This is the last accepted shared-range / legacy-include combined 24h behavior
before `TASK-TRAFFIC-RANGE-01`.

The baseline is NOT an older TRAFFIC-04 artifact, an arbitrary moving branch
head, a remembered timing number, a different evidence snapshot/evaluation, or
a production browser timing.

## Controlled comparison identity

Owner + Tech Lead Lab MUST run baseline and candidate on:

```text
the same machine/environment class

the same immutable production-size Observation snapshot

the same snapshot SHA256

the same snapshot byte size

the same fixed evaluated_at_utc

the same resolved 24h [from_utc,to_utc)

the same Admin QueryDeadline

the same browser-independent application/API timing boundary
```

Record before/after the comparison:

```text
baseline commit/tree

candidate exact tree

snapshot SHA256

snapshot byte size

fixed evaluated_at_utc

resolved from_utc/to_utc
```

The snapshot SHA is the immutable Lab artifact selected for this exact candidate
acceptance run. The canonical requirement is that baseline and candidate use the
same recorded snapshot and evaluation identity.

## Candidate request

Candidate combined 24h request:

```text
GET /admin/api/v1/sites/<site_id>/traffic/history
?range=24h
&products=history,statistics,peak,aps
```

This comparison proves that the new projection/orchestration path does not
materially regress the accepted pre-change combined 24h behavior.

## Measured statistics

For both baseline `B24` and candidate `C24-COMBINED`:

```text
minimum measured runs = 10

record:
p50
p95
max
success count
query_deadline count
source-integrity failure count
unexpected 5xx count
serialized response bytes
```

Use the accepted deterministic percentile algorithm:

```text
sort durations ascending

rank = (N - 1) * p

lower = floor(rank)
upper = ceil(rank)

if lower == upper:
    percentile = values[lower]
else:
    percentile =
      values[lower]
      + (rank - lower)
        * (values[upper] - values[lower])
```

Use:

```text
p = 0.50 for p50
p = 0.95 for p95
```

`max` is the literal maximum observed measured run.

## Exact relative regression formulas

Define:

```text
Δp50 =
C24-COMBINED.p50 - B24.p50

Δp95 =
C24-COMBINED.p95 - B24.p95

Δmax =
C24-COMBINED.max - B24.max
```

PASS requires ALL of:

```text
Δp50
<=
max(
  0.50 seconds,
  20% of B24.p50
)

Δp95
<=
max(
  0.75 seconds,
  25% of B24.p95
)

Δmax
<=
max(
  1.00 seconds,
  25% of B24.max
)
```

Negative deltas are allowed and count as PASS for the corresponding relative gate.

Equality at the threshold is PASS.

Any value above its threshold is FAIL.

## Exact absolute candidate gates

Candidate combined 24h additionally MUST satisfy:

```text
C24-COMBINED.p95 <= 8.0 seconds

C24-COMBINED.max <= 9.0 seconds

query_deadline = 0

source-integrity failures = 0

unexpected 5xx = 0
```

The existing shared:

```text
QueryDeadline = 10 seconds
```

remains unchanged.

No timeout/deadline/concurrency increase is permitted as remediation.

## Exact functional identity for this PERF comparison

Both baseline and candidate successful responses must represent the same
accepted 24h product semantics:

```text
History:
288 canonical 5-minute buckets

Period Statistics:
existing metric/method identifiers unchanged

Peak Load:
existing metric/method identifiers unchanged

Traffic by AP:
network_traffic_by_ap.v1
existing population/source/Average/Peak/Coverage semantics unchanged
```

Transport/request projection may differ:

```text
baseline:
legacy include=statistics,peak,aps

candidate:
products=history,statistics,peak,aps
```

Metric semantics MUST NOT differ.

## PASS / FAIL summary

Canonical overall result:

```text
PASS
only if:
  all three relative gates PASS
  AND
  p95 absolute gate PASS
  AND
  max absolute gate PASS
  AND
  zero query_deadline
  AND
  zero source-integrity failures
  AND
  zero unexpected 5xx
  AND
  semantic identity checks PASS
```

Otherwise:

```text
FAIL
→ candidate NOT ACCEPTED
→ normal publication NOT AUTHORIZED
```

This section contains the complete canonical threshold contract; no later
threshold rebinding step is permitted for normal acceptance.

---

# 98. Broker concurrency acceptance

Automated acceptance proves:

```text
max simultaneous historical Traffic requests from one page = 1
```

under rapid user actions.

---

# 99. Rapid multi-panel scenario

Rapidly select:

```text
History 7d
Statistics 7d
Peak 24h
AP 7d
```

Required:

```text
never >1 historical request in flight
same-range pending products may coalesce
obsolete pending intents do not execute
each panel applies matching generation only
```

---

# 100. Same-panel rapid switching

Example:

```text
AP 24h applied
AP → 7d
before completion AP → 24h
```

7d response must not replace latest 24h intent.

Other products in a shared in-flight batch remain safe.

---

# 101. Panel failure regression

Controlled AP 7d 503 must prove:

```text
AP keeps previous applied payload
History unchanged
Statistics unchanged
Peak unchanged
Current unchanged
```

---

# 102. Global Refresh regression

For:

```text
History 24h
Statistics 7d
Peak 24h
AP 7d
```

Global Refresh produces no more than two historical range-group requests, sequentially.

---

# 103. Initial-load regression

All historical panels default 24h.

Required:

```text
one combined 24h historical request
```

not four.

---

# 104. Templates

Remove active shared Network range control and add per-panel controls.

Recommended IDs:

```text
traffic-history-range-24h
traffic-history-range-7d

traffic-statistics-range-24h
traffic-statistics-range-7d

traffic-peak-range-24h
traffic-peak-range-7d

traffic-ap-range-24h
traffic-ap-range-7d
```

---

# 105. Applied-range labels

Every panel keeps its own existing `Applied range` label.

No page-level applied range.

---

# 106. CSS

Only functional styles:

```text
per-panel selector placement
waiting/loading/error-with-previous
selected/applied mismatch
```

No global Traffic redesign.

---

# 107. Frontend concepts

Expected:

```text
TrafficPanelRangeState
TrafficHistoricalRequestBroker
product-specific render/apply functions
```

Avoid one mutable global selected range.

---

# 108. Legacy `CaptivPortalTrafficNetworkRange`

When IndependentRanges is active, old shared singleton must not remain functional owner.

It may remain only in the flag-off legacy branch.

---

# 109. Coordinator public contract

Prefer minimal extension.

Allowed:

```text
one registered historical execution lane
that drains broker pending work
```

Do not duplicate request lifecycle mechanisms.

---

# 110. Expected backend files

Likely MODIFY:

```text
app/analytics/historical_traffic.py
app/analytics/source_gateway.py
app/analytics/models.py        # only if projection metadata/internal DTO needed

app/admin_web/query_service.py
app/admin_web/routes.py
app/admin_web/historical_traffic_serialization.py
```

No Observation acquisition changes expected.

---

# 111. Expected config files

If feature flag accepted:

```text
app/config.py
app/settings.py
.env.example
app/admin_web/config.py
app/admin_web/pages.py
```

---

# 112. Expected frontend files

```text
app/admin_web/templates/admin/traffic.html
app/admin_web/static/admin.js
app/admin_web/static/admin.css
```

No new library/dependency expected.

---

# 113. Expected unchanged areas

Expected unchanged:

```text
app/observations/**
app/current_state/**
app/visit_lifecycle/**
app/visitor_registry/**
app/auth/**
app/capport/**
app/controllers/**
requirements*
```

If implementation requires these, STOP for architecture review.

---

# 114. Backend tests — Owner + Tech Lead Lab

Required:

```text
products grammar
legacy include compatibility
include+products rejected
product feature gates
History-only
Statistics-only
Peak-only without requested Statistics
AP-only
same-range combined projection
unrequested product absent
serializer fail-closed
```

---

# 115. Semantic identity tests

For same fixed Site/range/evaluation prove:

```text
Statistics-only = Statistics sub-result from combined
Peak-only = Peak sub-result from combined
AP-only = AP sub-result from combined
History-only = History sub-result from combined
```

within existing contracts.

This proves orchestration changed, semantics did not.

---

# 116. Peak decoupling tests

Prove `products=peak` does not require `products=statistics`.

Peak values remain equal to Period Statistics Peak values for same fixed evidence.

---

# 117. AP self-contained transport tests

AP-only response must render every AP chart without full History product payload.

Prove:

```text
axis bucket count = range bucket count
AP arrays = axis length

History+AP:
axis matches canonical History bucket timeline
```

---

# 118. Frontend state tests

For each product:

```text
selected independent
applied independent
loading independent
previous payload independent
error independent
```

Changing one selector does not mutate another panel.

---

# 119. Broker tests

Required:

```text
initial all-24h → one request
one-panel 7d → one product request
same-range pending products coalesce
different ranges serialize
max in-flight = 1
global refresh groups by range
latest pending intent wins
shared response selectively applies by generation
```

---


# 120. Historical admission guard tests

Automated acceptance uses a deterministic fake monotonic clock / scheduler.

## Fast request

```text
A dispatches T+0
A completes T+3
B pending
```

Required:

```text
B MUST NOT dispatch before T+10
```

## Long request

```text
A dispatches T+0
A completes T+12
B pending
```

Required:

```text
B may dispatch immediately after A completion
no extra wait to T+22
```

## Never overlap

Under rapid multi-panel switching:

```text
max simultaneous historical HTTP requests = 1
```

at all times, including at the T+10 admission boundary.

## Pending collapse during guard

Rapid range changes for one waiting panel produce exactly one eventual request
for its latest still-current intent.

## Coalescing during guard

Two same-range product intents accumulated while guard-blocked may dispatch as
one canonical `products` request when admitted.

## Global Refresh

Global Refresh cannot bypass an active admission guard.

## 429 / Retry-After

If coordinator backoff expires later than the 10-second guard, dispatch waits
for the later backoff eligibility.

If guard expires later than a short Retry-After, dispatch still waits for the
guard.

## 503 / query_deadline

A completed 503 does not immediately release the next heavy request unless the
10-second-from-dispatch condition is already satisfied.

---
# 121. Frontend failure tests

Required:

```text
AP 7d 503 → AP error_with_previous
Statistics 7d 503 → Statistics-only request state fails
429 → no concurrency bypass
waiting/backoff → no fake Loading
```

---

# 122. Persistence tests

Fresh page starts all ranges at 24h.

No range preference read/write to:

```text
localStorage
sessionStorage
cookies
```

---

# 123. Site-isolation regression

Fixture Site A + Site B proves product-scoped requests never contain cross-Site evidence.

Broker group identity includes authorized Site + range.

No cross-Site coalescing.

---

# 124. Testing governance

Coder responsibility:

```text
implementation
patch
compileall
node --check if JS changed
git diff --check
```

Owner + Tech Lead Lab owns:

```text
focused pytest
targeted regression
Central Lab
official PERF
official PASS/FAIL
```

No new manual pre-publication browser gate is introduced.

---

# 125. Production rollout

Deploy accepted Git artifact with:

```text
WEB_ADMIN_TRAFFIC_INDEPENDENT_RANGES_ENABLED=false
```

Dormant verification:

```text
shared-range behavior unchanged
24h unchanged
existing products healthy
```

---

# 126. Separate activation

Owner separately enables:

```text
WEB_ADMIN_TRAFFIC_INDEPENDENT_RANGES_ENABLED=true
```

Then production product/browser acceptance.

---

# 127. Production acceptance — independent ranges

Verify simultaneously:

```text
History          24h
Statistics       7d
Peak             24h
Traffic by AP    7d
```

Each panel visibly retains its own applied range.

---

# 128. Production acceptance — request scope

AP 7d click must produce AP product request only.

It must not request History/Statistics/Peak product projections, apart from internal canonical foundation work invisible to the product API.

---

# 129. Production acceptance — failure isolation

If one panel 7d request fails, only that panel retains old data + error.

Others remain at their own applied ranges.

---

# 130. Production acceptance — no request storm

Rapidly change multiple selectors and verify:

```text
no more than one historical Traffic request in flight from the page
```

---


# 131. Production acceptance — admission guard

With request timing visible through browser/network diagnostics or safe
instrumentation, verify:

```text
A historical request dispatches

another product becomes pending

next historical dispatch does not occur before:
max(previous completion, previous dispatch + 10s)
```

Also verify:

```text
waiting selector remains interactive

waiting != loading

same-panel obsolete pending intents collapse

same-range pending products can coalesce

Global Refresh cannot bypass guard

Retry-After/backoff remains authoritative when stricter

no historical overlap occurs
```

Do not deliberately create unsafe server load merely to prove timing; controlled
functional timing evidence is sufficient.

---
# 132. Explicit non-goals

This TASK does not implement:

```text
new Traffic metrics
new Average/Peak formulas
new AP population semantics
Traffic Share
new collector
new Omada reads
new DB/schema/index/cache/rollup
30d
custom dates
calendar picker
saved range preferences
multi-Site combined Traffic
Traffic redesign
timeout/deadline/concurrency increase
```

---

# 133. Stop conditions

Implementation MUST STOP if it requires:

```text
new historical semantic owner
duplicated metric formulas
browser metric calculations
new persistence/acquisition
QueryDeadline increase
browser timeout increase
Admin concurrency increase
AP population semantic change
12-AP bound change
metric version change
cross-Site coalescing
automatic 7d preference persistence
more than one historical request in flight by design
bypassing or shortening the 10-second historical admission guard
independent broker-owned scheduler/timer
```

Also STOP on material repository drift.

---

# 134. Architecture decisions — FINAL

1. History, Statistics, Peak and Traffic by AP receive independent `24h | 7d` selectors.
2. Current Network Throughput remains without historical range controls.
3. Every historical panel defaults to `24h`.
4. Range state is page-lifetime only.
5. No localStorage/sessionStorage/cookie/URL persistence in v1.
6. Each panel independently owns selected/applied/request/error state.
7. Previously successful payload remains visible on a failed range switch and retains its prior applied-range label.
8. Existing `/traffic/history` remains the canonical historical endpoint.
9. New frontend/API model uses exact `products` projection.
10. Legacy `include` remains temporarily backward compatible.
11. `include` and `products` together are invalid.
12. History / Statistics / Peak / AP projections are independently requestable.
13. Peak request no longer requires client-requested Statistics.
14. Shared internal PeakValues preserves exact Statistics/Peak semantic identity.
15. AP-only response receives compact self-contained bucket-axis transport context.
16. `HistoricalTrafficReadService` remains the single historical semantic owner.
17. `CurrentTrafficReadService` remains Current AP `Now` owner.
18. One page-local `TrafficHistoricalRequestBroker` owns pending product/range intents only.
19. `CaptivPortalTrafficCoordinator` remains owner of network lifecycle, scheduling, abort, timeout, backoff and page lifecycle.
20. Maximum historical Traffic HTTP requests in flight per Traffic page = `1`.
21. Permanent historical dispatch admission guard = `10 seconds` measured from the previous actual dispatch.
22. Next historical dispatch requires BOTH: previous request no longer in-flight AND at least 10 seconds since prior dispatch.
23. Effective dispatch eligibility also honors any stricter coordinator Retry-After/backoff/lifecycle constraint.
24. A long request lasting beyond 10 seconds may be followed immediately after completion; there is no extra post-completion 10-second cooldown.
25. Selectors remain interactive while admission-blocked.
26. Admission-blocked panels use `waiting`; `loading` begins only after actual HTTP dispatch.
27. Pending intents continue collapsing while admission-blocked; obsolete intents never execute.
28. Same-range current pending products may coalesce during the guard interval.
29. Explicit panel intent has priority over queued Global Refresh work, but neither may bypass the guard.
30. Different-range historical batches execute sequentially.
31. Initial all-24h page load remains one combined historical request.
32. Global Refresh preserves each panel's selected range and groups current work by range.
33. Independent-ranges feature flag defaults to false.
34. No QueryDeadline, browser timeout or Admin concurrency increase is authorized.
35. Product-scoped 24h/7d PERF is mandatory acceptance.
36. Admission state is page-local/memory-only and resets on page reload.
37. Admission wake-up scheduling belongs to the existing coordinator execution lane; no second scheduler owner is introduced.
38. Traffic metric semantics, AP population semantics, Site isolation and existing metric versions remain unchanged.

---

# 135. Owner + Tech Lead review disposition — incorporated

The architectural direction is accepted.

Frozen decisions incorporated into this FINAL:

```text
API projection:
ACCEPT
existing /traffic/history + exact products subsets

broker concurrency:
ACCEPT
max historical in-flight = 1

same-range coalescing:
ACCEPT

range persistence:
ACCEPT
page-lifetime only / reload resets to 24h

Peak request decoupling:
ACCEPT
request-level Peak→Statistics dependency removed
shared semantic primitive retained

AP self-contained axis:
ACCEPT
transport-only extension

feature flag:
ACCEPT
WEB_ADMIN_TRAFFIC_INDEPENDENT_RANGES_ENABLED=false

Historical Request Admission Guard:
ACCEPT
10 seconds from prior historical dispatch
```

Permanent admission formula:

```text
next_dispatch
>=
max(
  previous_request_completion,
  previous_dispatch + 10s,
  coordinator Retry-After/backoff/lifecycle eligibility
)
```

This formula is interpreted as simultaneous constraints, not as adding another
10 seconds after completion.

Examples:

```text
A start T+0
A finish T+3
B earliest T+10
```

```text
A start T+0
A finish T+8
B earliest T+10
```

```text
A start T+0
A finish T+12
B may start T+12
```

Implementation remains separately unauthorized.

---

# 136. FINAL status

```text
TASK:
TASK-TRAFFIC-RANGE-01 — Independent Traffic Range per Panel

STATUS:
FINAL — OWNER + TECH LEAD REVIEW INCORPORATED
24h COMBINED PERF CONTRACT FROZEN
FOR FINAL VERIFICATION

BOUND TO:
main@8a5c4db899406eeb1f737abe63495247be1ee75a

TREE:
6837dd729dedb0df6414b3f979657a3f6f55d0ab

RE-FETCH:
PASS
NO DRIFT / NO REBIND REQUIRED

CHANGE CLASS:
Traffic orchestration / API projection / frontend range state

METRIC SEMANTICS CHANGE:
NO

PANELS:
History
Statistics
Peak
Traffic by AP

RANGES:
24h / 7d independently per panel

DEFAULT:
24h each

PERSISTENCE:
page lifetime only

CANONICAL API:
existing /traffic/history
+
products projection

HISTORICAL OWNER:
HistoricalTrafficReadService

CURRENT AP OWNER:
CurrentTrafficReadService

REQUEST BROKER:
page-local TrafficHistoricalRequestBroker

NETWORK / SCHEDULER OWNER:
CaptivPortalTrafficCoordinator

MAX HISTORICAL REQUESTS IN FLIGHT PER PAGE:
1

HISTORICAL REQUEST ADMISSION GUARD:
10 seconds from previous actual dispatch

NEXT DISPATCH RULE:
previous request complete
AND
>= previous dispatch + 10s
AND
all stricter coordinator Retry-After/backoff/lifecycle conditions satisfied

WAITING != LOADING:
YES

PENDING INTENT COLLAPSE:
YES

SAME-RANGE COALESCING:
YES

GLOBAL REFRESH MAY BYPASS GUARD:
NO

503 MAY BYPASS GUARD:
NO

RETRY-AFTER MAY BE SHORTENED BY GUARD:
NO

SECOND SCHEDULER OWNER:
NO

NEW DB / SCHEMA / INDEX / CACHE / ROLLUP:
NO

24h PRE-CHANGE PERF BASELINE:
commit 8a5c4db899406eeb1f737abe63495247be1ee75a
tree 6837dd729dedb0df6414b3f979657a3f6f55d0ab
legacy request include=statistics,peak,aps

24h COMBINED RELATIVE PERF GATES:
p50 delta <= max(0.50s, 20% baseline p50)
p95 delta <= max(0.75s, 25% baseline p95)
max delta <= max(1.00s, 25% baseline max)

24h COMBINED ABSOLUTE PERF GATES:
candidate p95 <= 8.0s
candidate max <= 9.0s
query_deadline = 0
source-integrity failures = 0
unexpected 5xx = 0

QUERY DEADLINE:
UNCHANGED

BROWSER TIMEOUT:
UNCHANGED

ADMIN CONCURRENCY:
UNCHANGED

FEATURE DEFAULT:
WEB_ADMIN_TRAFFIC_INDEPENDENT_RANGES_ENABLED=false

IMPLEMENTATION AUTHORIZATION:
NOT GRANTED

PUBLICATION:
NOT GRANTED

MERGE:
NOT GRANTED

PRODUCTION DEPLOYMENT:
NOT GRANTED

PRODUCTION ACTIVATION:
NOT GRANTED
```

Next allowed step:

```text
Owner + Tech Lead final verification
```

Only after separate explicit Owner authorization may implementation begin.

This FINAL itself does NOT authorize implementation.
