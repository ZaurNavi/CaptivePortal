# TASK-TRAFFIC-02 — Historical Network Traffic / History — FINAL

**Project:** CaptivPortal  
**Area:** Admin Console → Traffic  
**Parent:** `CaptivPortal — Генеральная дорожная карта раздела Admin Console → Traffic — FINAL v1`  
**Dependencies:** `TASK-TRAFFIC-00`, `TASK-TRAFFIC-01`, `TASK-TRAFFIC-02-READ`  
**Type:** architecture / Admin application + API + presentation integration specification  
**Status:** `FINAL — TECH LEAD REVIEW INCORPORATED / READY FOR EXPLICIT OWNER IMPLEMENTATION AUTHORIZATION`  
**Implementation authorization:** `NOT GRANTED`  
**Branch / code / commit / push / PR / merge:** `NOT AUTHORIZED BY THIS FINAL`  
**Deployment / production activation:** `NOT GRANTED; SEPARATE OWNER-CONTROLLED ACTION`  
**Prepared / finalized:** 2026-08-29  
**Tech Lead review:** `ARCHITECTURE DIRECTION PASS / TARGETED CORRECTIONS INCORPORATED`

---

# 0. Executive decision

`TRAFFIC-02` adds the first historical Network Traffic product panel to the existing:

```text
Admin Console → Traffic
```

Panel:

```text
Network Traffic History
```

Initial shared Network Traffic range values:

```text
24h
7d
```

Canonical data path:

```text
Observation persisted AP history
        ↓
AnalyticsSourceGateway
        ↓
HistoricalTrafficReadService
        ↓
AdminQueryService
        ↓
GET /admin/api/v1/sites/<site_id>/traffic/history?range=...
        ↓
safe Admin serializer
        ↓
CaptivPortalTrafficCoordinator
        ↓
Network Traffic History panel
```

Permanent ownership:

```text
Traffic page / Network Traffic analytical context
→ owns selected Network range

HistoricalTrafficReadService
→ owns historical Network Traffic calculation semantics

CaptivPortalTrafficCoordinator
→ owns browser request lifecycle
```

`TRAFFIC-02 History` is the first consumer of the shared Network range. Future:

```text
TRAFFIC-03 Statistics
TRAFFIC-04 Peak Load
TRAFFIC-05 Traffic by AP
TRAFFIC-06 AP Share
```

MUST reuse the same Network range owner rather than create independent selectors/state.

`TRAFFIC-01 Current Network Throughput` is range-insensitive and does not reload merely because the shared Network range changes.

FINAL decisions:

```text
NO new collector
NO new Omada polling
NO new Traffic DB
NO schema migration
NO rollup/cache persistence
NO Browser/Admin direct Observation SQL
NO Browser/Admin → Omada
NO second historical calculation owner
NO second Traffic scheduler/coordinator
NO TRAFFIC-03 Period Statistics
```

Product-exposure flag:

```text
WEB_ADMIN_TRAFFIC_HISTORY_ENABLED=false
```

This subordinate flag controls only History product exposure. It does not start/stop `HistoricalTrafficReadService`.

Functional chart:

```text
two-series historical line chart
Download
Upload
unit = Mbps
```

`total_mbps` remains a canonical backend bucket field but is not introduced as a third visible History line or Period KPI in `TRAFFIC-02 v1`.

This FINAL does not grant implementation, merge, deployment or production activation authorization.

---

# 1. Exact FINAL repository rebind

Repository state was rechecked after Tech Lead review.

```text
main =
6b4adf770ab1afa289dac14680ba876711088d94

tree =
04f5e2d23da8b2d44390c285fc14dbb62fa06221
```

Current main:

```text
Merge PR #86
TASK-TRAFFIC-02-READ — Historical Network Traffic Read Foundation
```

PR #86 implementation commit:

```text
2707752e3a7dbdfebef88e080f85a7e69bd62014
```

Accepted `TRAFFIC-02-READ` changed only:

```text
app/analytics/__init__.py
app/analytics/historical_traffic.py
app/analytics/models.py
app/analytics/runtime.py
app/analytics/source_gateway.py

tests/analytics/test_historical_traffic.py
tests/analytics/test_historical_traffic_runtime.py
```

No Admin Web / Traffic UI file was changed by `TRAFFIC-02-READ`.

No repository drift was found between DRAFT review and this FINAL.

If `origin/main` changes after this FINAL and before implementation authorization:

```text
re-fetch
re-pin exact SHA/tree
perform impact review
```

Mandatory impact review if newer main touches:

```text
app/analytics/historical_traffic.py
app/analytics/models.py
app/analytics/runtime.py
app/analytics/source_gateway.py

app/admin_web/config.py
app/admin_web/pages.py
app/admin_web/runtime.py
app/admin_web/query_service.py
app/admin_web/routes.py
app/admin_web/static/admin.js
app/admin_web/static/admin.css
app/admin_web/templates/admin/traffic.html

app/config.py
app/settings.py
.env.example
```

Implementation MUST start from exact current `origin/main`, not from a historical production or DRAFT baseline.

---

# 2. Accepted predecessor state

```text
TRAFFIC-00 — Foundation
DONE / MERGED / PRODUCTION

TRAFFIC-01 — Current Network Throughput
DONE / MERGED / PRODUCTION

TRAFFIC-02-READ — Historical Network Traffic Read Foundation
DONE / ACCEPTED / MERGED
```

`TRAFFIC-02` MUST bind to the real merged contracts, not to assumptions from the earlier READ DRAFT.

---

# 3. Accepted Historical read contract

Canonical source:

```text
Observation persisted AP dynamic history
```

Canonical semantic owner:

```text
HistoricalTrafficReadService
```

Accepted invariants:

```text
sample_at = ap_dynamic cycle.finished_at
MAX_SITE_HISTORY_BUCKETS = 720
MAX_SITE_SAMPLE_SOURCE_SKEW_SECONDS = 60
bucket aggregation = mean_of_complete_site_rate_samples
primary source = wired
fallback = lan
source decision = one Site bucket / one source family
source mixing inside bucket = false
```

Important boundary:

```text
mean_of_complete_site_rate_samples
!=
TRAFFIC-03 canonical Period Average
```

`TRAFFIC-03` remains interval/time-aware and must still use/extend the same Historical Traffic semantic owner.

---

# 4. Verified merged method

Current accepted service method:

```python
HistoricalTrafficReadService.get_site_history(
    site_id,
    *,
    from_utc,
    to_utc,
    evaluated_at_utc=None,
    bucket_seconds=None,
    deadline=None,
)
```

Return:

```text
HistoricalSiteTraffic
```

The service already owns Site validation, `[from_utc,to_utc)`, evaluated-at semantics, bucket selection, 720-bucket bound, source-family selection, Site-sample completeness, AP skew policy, gap semantics, partial/none semantics, coverage, quality, as-of watermark semantics, deadline and source-integrity handling.

`TRAFFIC-02` MUST NOT duplicate those responsibilities.

---

# 5. Accepted common resolutions

Current service automatic bucket ladder produces:

```text
24h → 300s → 288 buckets
7d  → 900s → 672 buckets
```

Future accepted backend capability also supports longer bounded ranges, including 30d and 180d. Product exposure remains separate.

The browser MUST NOT choose `bucket_seconds`.

---

# 6. Accepted performance evidence

PR #86 acceptance evidence:

```text
24h  / 288 buckets / p95 5.23s / max 5.29s
7d   / 672 buckets / p95 4.59s / max 4.62s
30d  / 720 buckets / p95 5.40s / max 5.48s
180d / 720 buckets / p95 4.92s / max 4.93s
```

Hard source/query deadline:

```text
10s
```

Existing Traffic browser request timeout:

```text
20s
```

FINAL decision:

```text
NO new rollup/cache/storage
NO deadline increase
NO new History timeout
```

If a stricter interactive SLA is required, it must be explicitly approved before FINAL.

---

# 7. Product semantics

Visible product:

```text
Historical Network Traffic
```

Meaning:

```text
historical Site AP physical/network throughput evidence
```

Unit:

```text
Mbps
```

Forbidden labels:

```text
Internet Traffic
WAN Traffic
Internet Usage
WAN Usage
Billing Traffic
Guest Traffic
Guest Session Traffic
SSID Traffic
Zefer_Parki Traffic
```

Required helper meaning:

```text
Historical Site AP/network throughput derived from persisted evidence.
May include local/service traffic and is not Internet/WAN-only traffic.
```

---

# 8. Semantic identity with TRAFFIC-01

`TRAFFIC-01` and `TRAFFIC-02` belong to the same `NETWORK TRAFFIC` family:

```text
wired primary
LAN fallback
radio excluded from Site Network Traffic v1
Mbps
not WAN/Internet/guest-session semantics
```

Difference:

```text
TRAFFIC-01 → current accepted snapshot
TRAFFIC-02 → accepted historical buckets
```

History MUST NOT be built by periodically storing browser values from `TRAFFIC-01`.

---

# 9. Explicit canonical source path

```text
Observation persisted AP history
→ AnalyticsSourceGateway
→ HistoricalTrafficReadService
→ Admin application layer
→ Admin Traffic API
→ Browser
```

Forbidden:

```text
Browser → observations.sqlite3
Admin route → observations.sqlite3
AdminQueryService → raw Observation SQL
Browser → Omada
Admin route → Omada
History panel → dashboard/traffic-activities
History panel → dashboard/traffic-distribution
Admin request → new Observation cycle
```

Native Omada history remains validation/reference only.

---

# 10. No second historical calculation owner

`TRAFFIC-02` MUST NOT implement its own:

```text
wired/LAN source selection
AP summation
bucket averaging
gap calculation
source skew calculation
coverage status
historical SQL
canonical total formula
```

API/presentation layer may validate, serialize, format and plot only.

---

# 11. Shared Network Traffic range — initial product values

The selected range belongs to the **Network Traffic analytical context**, not to the History panel.

Initial allowed values:

```text
24h
7d
```

Default selected Network range:

```text
24h
```

Current consumers:

```text
TRAFFIC-02 History
```

Reserved future consumers:

```text
TRAFFIC-03 Statistics
TRAFFIC-04 Peak Load
TRAFFIC-05 Traffic by AP
TRAFFIC-06 AP Share
```

All future range-sensitive Network panels MUST reuse this same selected Network range.

`TRAFFIC-01 Current Network Throughput` remains range-insensitive.

Future `30d` is NOT enabled by this TASK:

```text
range=30d
→ 400 invalid_request
```

This is a product allowlist, not a backend ceiling.

---

# 12. No inherited 7d/31d backend validation

`TRAFFIC-02` MUST NOT reject ranges because of:

```text
AnalyticsConfig.max_query_window_days
AnalyticsConfig.wireless_max_window_days
```

The endpoint exposes only 24h/7d because of product scope, not storage/read capability.

```text
product option allowlist
!=
backend history capability
```

---

# 13. Canonical shared Network range resolver

Add a narrow application helper for the shared Network Traffic analytical context.

Preferred file:

```text
app/admin_web/traffic_network_ranges.py
```

Conceptual contract:

```python
resolve_network_traffic_range(
    range_id,
    *,
    evaluated_at_utc=None,
)
```

Allowed IDs:

```text
24h
7d
```

Browser sends only the selected shared Network range ID.

Browser MUST NOT construct:

```text
from_utc
to_utc
bucket_seconds
```

The helper is not History-owned despite being first introduced by `TRAFFIC-02`.

Future `TRAFFIC-03/04/05/06` reuse this same resolver/state contract.

---

# 14. evaluated_at and canonical range boundaries

For every range-sensitive Network Traffic request, the server/application layer captures one canonical:

```text
evaluated_at_utc
```

If no deterministic test value is injected:

```text
evaluated_at_utc = server UTC now
```

Then:

```text
to_utc = evaluated_at_utc
```

For `24h`:

```text
from_utc = evaluated_at_utc - 86400 seconds
```

For `7d`:

```text
from_utc = evaluated_at_utc - 604800 seconds
```

Intervals are exactly:

```text
[from_utc,to_utc)
```

`24h` and `7d` are rolling fixed durations, not calendar day/week reports.

Required invariant:

```text
evaluated_at_utc == to_utc
```

---

# 15. Range/bucket ownership

Shared Network range owner chooses only:

```text
range ID
from_utc
to_utc
evaluated_at_utc
```

It does NOT choose:

```text
bucket_seconds
bucket alignment
source family
quality/gap rules
historical aggregation
```

Those remain `HistoricalTrafficReadService` responsibilities.

The History API/application layer passes the resolved range into the accepted read service and accepts the service's canonical bucket resolution.

Browser never reproduces backend calculation rules.

---

# 16. Timezone responsibility

Canonical persistence/query/bucket time is UTC.

API returns UTC timestamps.

Browser responsibility is presentation only.

FINAL v1:

```text
format returned UTC timestamps using browser-resolved local timezone
via Intl.DateTimeFormat
```

The panel MUST visibly identify the display timezone, for example:

```text
Time · Asia/Baku
```

If no trustworthy browser timezone name is available, display UTC.

Browser timezone formatting MUST NOT change boundaries or move samples between buckets.

---

# 17. Shared selected Network range interaction

Traffic page owns:

```text
selected_network_range
```

Initial value:

```text
24h
```

Current behavior in `TRAFFIC-02`:

```text
Network range control
→ update selected_network_range
→ coordinator.refreshPanel(
     "network-traffic-history",
     {manual:true}
   )
```

Only History refreshes **for now** because it is the only range-sensitive Network panel currently implemented.

This is not permanent panel ownership.

Future:

```text
TRAFFIC-03/04/05/06
```

must consume the same selected Network range and be refreshed according to the shared Network analytical context design.

Current Network Throughput does not reload solely because selected Network range changes.

Forbidden:

```text
range control → fetch()
range control → panel.load()
range control → AbortController
range control → calculate from/to
History-private independent range selector/state
```

---

# 18. Shared selected range vs panel applied range

Two concepts are mandatory:

```text
selected_network_range
=
current user-selected shared Network analytical range

history_applied_range
=
range.id of the last successfully rendered History response
```

Example:

```text
history_applied_range = 24h
user selects 7d

→ selected_network_range becomes 7d
→ History attempts 7d refresh
→ old 24h chart may remain visible
→ old chart MUST stay labelled Applied 24h
→ UI may say Selected 7d / loading or pending
```

Success:

```text
validated response.range.id = 7d
→ history_applied_range becomes 7d
```

Failure:

```text
selected_network_range remains 7d
history_applied_range remains 24h
old chart remains explicitly Previous successful 24h evidence
```

Never relabel old evidence to the selected range before a successful response.

## Coordinator backoff / no-execution case

`refreshPanel(..., {manual:true})` may return `false` without starting a new execution, for example while the panel remains inside its coordinator eligibility/backoff window.

In that case:

```text
selected_network_range may remain the user's new selection
history_applied_range does not change
do NOT show false "Loading"
do NOT claim a request was sent
do NOT advance applied state
```

The selected range can be retried by the next eligible manual/global refresh.

---

# 19. Historical refresh policy

History panel:

```text
autoRefresh = false
```

Reason:

- historical reads are materially heavier than Current Traffic;
- coordinator registration already performs one initial execution;
- shared manual Refresh exists;
- shared Network range changes can request History explicitly;
- periodic minute-by-minute History polling is unnecessary in v1.

Canonical:

```text
register
→ one initial History load using selected_network_range=24h

autoRefresh=false
→ no periodic History timer

global Refresh
→ refreshAll()
→ History reloads current selected_network_range

Network range change
→ refreshPanel("network-traffic-history", {manual:true})
→ only current range-sensitive consumer reloads today
```

No second scheduler is created.

---

# 20. No duplicate scheduler/lifecycle

History panel MUST NOT create:

```text
setInterval
private polling setTimeout
visibilitychange owner
pagehide owner
private AbortController lifecycle
private retry/backoff owner
```

All belong to `CaptivPortalTrafficCoordinator`.

---

# 21. Existing Traffic coordinator contract

Current Foundation already exposes:

```text
registerPanel(...)
refreshPanel(...)
refreshAll(...)
```

Every successful registration receives one initial execution independently of `autoRefresh`.

Therefore History MUST NOT trigger a second initial request after registration.

---

# 22. Canonical History registration

Panel key:

```text
network-traffic-history
```

Conceptual:

```javascript
coordinator.registerPanel({
  key: "network-traffic-history",
  autoRefresh: false,
  load,
  render,
  renderLoading,
  renderFailure,
});
```

Loader MUST capture the selected Network range ID **locally for that execution**.

Conceptual:

```text
executionRange = selected_network_range at load start
request uses executionRange
validated response.range.id drives render/applied state
```

Render MUST NOT trust a mutable outer selected-range variable as proof of which range the response represents.

No second coordinator.

---

# 23. Shared request helper

History loader uses only coordinator-provided:

```text
context.requestJson(...)
```

Conceptual:

```javascript
context.requestJson(
  `${context.apiBase}/traffic/history?range=${encodedRangeId}`
)
```

No direct global `fetch()` in History panel code.

---

# 24. Existing Traffic lifecycle remains authoritative

Coordinator owns:

```text
same-origin enforcement
credentials=same-origin
cache=no-store
Accept application/json
AbortController
request timeout
generation
supersession
Retry-After
backoff
hidden-tab abort
pagehide stop
global 401/403
panel-local 400/429/503
```

History does not fork these semantics.

---

# 25. New Admin endpoint

Canonical:

```text
GET /admin/api/v1/sites/<site_id>/traffic/history
```

Required query:

```text
range=24h|7d
```

No hidden endpoint default. Browser default is 24h and sends `range=24h` explicitly.

---

# 26. Forbidden public query parameters

Do NOT expose:

```text
from_utc
to_utc
evaluated_at_utc
bucket_seconds
limit
cursor
source
source_family
timezone
ap_mac
ssid
```

Unknown or duplicate query parameter:

```text
400 invalid_request
```

---

# 27. Admin security chain

Required endpoint chain:

```text
Admin authentication
        ↓
canonical Site resolution
        ↓
authorize admin.read.context
        ↓
WEB_ADMIN_TRAFFIC_ENABLED
        ↓
WEB_ADMIN_TRAFFIC_HISTORY_ENABLED
        ↓
AdminQueryService
        ↓
authorize admin.read.overview
        ↓
server-side shared Network range resolution
        ↓
HistoricalTrafficReadService
```

No new auth, Site resolver or browser Bearer token.

Feature checks remain behind the canonical authentication/Site boundary.

---

# 28. Subordinate History feature gate — FINAL

Add:

```text
WEB_ADMIN_TRAFFIC_HISTORY_ENABLED=false
```

Settings key:

```text
web_admin_traffic_history_enabled
```

`AdminWebConfig` field:

```text
traffic_history_enabled: bool
```

Dependency:

```text
WEB_ADMIN_TRAFFIC_HISTORY_ENABLED=true
requires
WEB_ADMIN_ENABLED=true
AND
WEB_ADMIN_TRAFFIC_ENABLED=true
```

Invalid dependency:

```text
fail closed for Admin Web configuration
```

Semantics:

```text
Traffic=true + History=false
→ Traffic page remains available
→ Current Network Throughput remains available
→ History markup/range controls absent
→ History panel not registered
→ zero History product requests
→ /traffic/history returns 404 not_found

Traffic=true + History=true
→ History product surface enabled
```

The flag controls only product exposure.

It MUST NOT start/stop:

```text
HistoricalTrafficReadService
AnalyticsRuntime
Observation
CurrentTrafficReadService
Current State
Visit Lifecycle
```

Repository-safe default remains:

```text
false
```

This enables:

```text
deploy code with History=false
→ dormant post-check
→ separate Owner activation History=true
→ product acceptance
```

---

# 29. Optional historical dependency

`analytics_runtime.historical_traffic_service` is already optional/fail-open.

Admin composition injects it into `AdminQueryService` as optional:

```text
historical_traffic_read_service: Any | None = None
```

Feature flag and service lifecycle are independent.

When History product exposure is enabled but service is absent:

```text
History endpoint → 503 source_unavailable
```

while:

```text
Traffic page
Current Network Throughput
Home
Admin shell
Portal
```

remain usable.

---

# 30. Admin runtime readiness invariant

Historical service absence MUST NOT make overall:

```text
AdminWebRuntime.state
```

unavailable.

This is a panel-level optional dependency.

Required test:

```text
Traffic=true
History=true
historical service absent

→ Admin runtime remains usable
→ Current panel remains usable
→ History endpoint 503
```

---

# 31. AdminQueryService method

Preferred:

```python
historical_traffic_history(
    principal,
    site_id,
    *,
    range_id,
)
```

Responsibilities:

```text
authorize admin.read.overview
validate allowed shared Network range ID
capture one server evaluated_at
resolve exact shared Network [from,to)
use shared Admin execution controls
call HistoricalTrafficReadService.get_site_history(...)
serialize through dedicated safe serializer
return AdminQueryResponse
```

No History-specific source-selection or calculation logic.

---

# 32. Shared execution/deadline controls

History creates **no History-specific deadline**.

Use existing:

```text
AdminQueryExecutionControls
```

and pass its `QueryDeadline` into:

```text
HistoricalTrafficReadService.get_site_history(...)
```

Current/default shared Admin configuration:

```text
WEB_ADMIN_MAX_QUERY_DURATION_SECONDS = 10
```

Accepted `TRAFFIC-02-READ` benchmark was performed with a 10-second hard deadline.

Current/default shared Traffic browser timeout:

```text
WEB_ADMIN_TRAFFIC_REQUEST_TIMEOUT_SECONDS = 20
```

History inherits the approved shared Admin/Traffic budgets.

If shared Admin configuration changes later, History inherits that approved shared budget.

Forbidden:

```text
History semaphore
History thread
History executor
History-specific deadline
History-specific timeout
silent deadline increase
```

---

# 33. AdminQueryService error mapping

```text
HistoricalTrafficValidationError
→ AdminQueryValidationError

HistoricalTrafficSourceUnavailable
→ AdminQueryUnavailable

HistoricalTrafficSerializationError
→ AdminQueryUnavailable

AnalyticsQueryDeadlineExceeded
→ AdminQueryDeadline through shared execution controls
```

---

# 34. New safe Admin serializer

Preferred file:

```text
app/admin_web/historical_traffic_serialization.py
```

Entry point:

```python
serialize_historical_traffic(
    value,
    site_id,
    *,
    resolved_range,
)
```

Serializer is a fail-closed validation + safe projection boundary.

Forbidden:

```text
source reselection
bucket averaging
interpolation
coverage invention
period statistics
peak calculations
new throughput formulas
```

It MAY verify mathematical consistency already guaranteed by the canonical read DTO, including:

```text
download + upload == total
```

within a narrow numeric tolerance.

That is validation only, not a second calculation owner.

---

# 35. Serialized result envelope

Preferred:

```json
{
  "status": "ok",
  "range": {},
  "buckets": [],
  "coverage": {},
  "quality": {}
}
```

Allowed successful service statuses:

```text
ok
partial
insufficient_data
```

---

# 36. Serialized range contract

Preferred:

```json
{
  "id": "24h",
  "from_utc": "...",
  "to_utc": "...",
  "evaluated_at_utc": "...",
  "bucket_seconds": 300,
  "bucket_count": 288,
  "unit": "Mbps",
  "aggregation": "mean_of_complete_site_rate_samples",
  "metric_version": "network_traffic_history.v1",
  "source_kind": "observation_ap_dynamic",
  "sample_timestamp_semantics": "cycle_finished_at",
  "bucket_alignment": "range_start_utc",
  "max_site_history_buckets": 720,
  "max_site_sample_source_skew_seconds": 60
}
```

`id` belongs to the product range resolver. Other semantics come from the accepted read DTO.

---

# 37. Serialized bucket contract

Preferred compact projection:

```json
{
  "bucket_start_utc": "...",
  "bucket_end_utc": "...",
  "download_mbps": 1.25,
  "upload_mbps": 0.08,
  "total_mbps": 1.33,
  "status": "complete",
  "selected_source": "wired",
  "selection_reason": "primary_full_coverage",
  "source_changed_from_previous": false,
  "complete_site_sample_count": 10,
  "excluded_site_sample_count": 0,
  "gap_count_over_threshold": 0,
  "selected_source_skew_excluded_sample_count": 0
}
```

No AP rows, raw counters or raw SQLite rows.

---

# 38. Bucket value semantics

Inherited unchanged:

```text
complete
→ numeric values

partial + complete_site_sample_count > 0
→ numeric values may exist
→ mean only over complete Site samples
→ status remains partial

none
→ numeric values = null
```

Serializer preserves these semantics.

---

# 39. Zero vs missing

Valid backend:

```text
0.0 Mbps
```

is real zero and must be serialized/plotted as zero.

Backend:

```text
null
```

means no canonical numeric value and must remain a visual gap.

```text
missing != zero
```

---

# 40. Serialized coverage contract

Preferred fields:

```text
status
available_from_utc
available_through_utc
source_watermark_utc
source_age_seconds
bucket_count
complete_bucket_count
partial_bucket_count
missing_bucket_count
canonical_cycle_count
complete_site_sample_count
excluded_site_sample_count
gap_bucket_count
source_transition_count
```

No synthetic coverage percentage is introduced.

---

# 41. Serialized quality contract

Preferred fields:

```text
partial_cycle_count
failed_cycle_count
shutdown_cycle_count
abandoned_cycle_count
running_cycle_count
no_baseline_count
counter_reset_count
gap_too_large_count
invalid_elapsed_count
source_unavailable_count
source_skew_excluded_sample_count
integrity_failure_count
```

Panel may display only a compact subset; API remains product-safe and bounded.

---

# 42. Serializer validation and cross-field invariants

Primitive validation is insufficient. The serializer MUST validate cross-field consistency.

## 42.1 Identity / canonical metadata

```text
Site identity == requested Site

range.id = 24h | 7d

unit == Mbps

aggregation == mean_of_complete_site_rate_samples

metric_version == network_traffic_history.v1

source_kind == observation_ap_dynamic

sample_timestamp_semantics == cycle_finished_at

bucket_alignment == range_start_utc

max_site_history_buckets == 720
```

## 42.2 Exact product range invariants

For:

```text
range.id = 24h
```

require:

```text
to_utc - from_utc = 86400 seconds
bucket_seconds = 300
bucket_count = 288
```

For:

```text
range.id = 7d
```

require:

```text
to_utc - from_utc = 604800 seconds
bucket_seconds = 900
bucket_count = 672
```

For both:

```text
evaluated_at_utc == to_utc
```

Service:

```text
from_utc
to_utc
evaluated_at_utc
```

MUST exactly equal the server-resolved application range.

## 42.3 Bucket collection invariants

```text
bucket_count == len(buckets)

bucket ordering strictly contiguous

first bucket starts at from_utc

last bucket ends at to_utc

every bucket inside [from,to)

all counts are non-negative integers

all Mbps values are finite non-negative numbers or null
```

## 42.4 Coverage invariants

```text
coverage.bucket_count == range.bucket_count

complete_bucket_count
+ partial_bucket_count
+ missing_bucket_count
==
bucket_count
```

Where possible without inventing a new semantic result, aggregate coverage/quality counts should be checked against the serialized bucket collection.

## 42.5 Result status consistency

Exactly:

```text
result.status = ok
↔ coverage.status = complete

result.status = partial
↔ coverage.status = partial

result.status = insufficient_data
↔ coverage.status = none
```

## 42.6 Bucket state consistency

For:

```text
status = none
```

require:

```text
download_mbps = null
upload_mbps = null
total_mbps = null
selected_source = null
complete_site_sample_count = 0
```

For:

```text
status = complete | partial
with usable numeric evidence
```

require:

```text
selected_source = wired | lan
complete_site_sample_count > 0
download_mbps finite non-negative
upload_mbps finite non-negative
total_mbps finite non-negative
```

and validate:

```text
total_mbps ≈ download_mbps + upload_mbps
```

within safe tolerance.

Malformed DTO:

```text
serialization failure
→ AdminQueryUnavailable
→ sanitized 503 source_unavailable
```

Browser is never trusted to enforce backend safety.

---

# 43. Total ownership

Read foundation already provides:

```text
total_mbps
```

Admin serializer MAY validate:

```text
total_mbps ≈ download_mbps + upload_mbps
```

within safe tolerance.

It MUST NOT overwrite/recalculate the canonical field.

Browser MUST NOT calculate canonical Total.

History UI does not show a Total series or Period Total KPI in v1.

---

# 44. HTTP success behavior

HTTP `200` for safe product results:

```text
status=ok
status=partial
status=insufficient_data
```

No-data is not 404/503 and is not zero traffic.

---

# 45. HTTP error mapping and dedicated History route boundary

```text
400 invalid_request
→ missing/unknown/duplicate range, unknown query, invalid Site/request contract

401 authentication_required
→ no Admin session

403 site_forbidden
→ forbidden Site/capability

404 not_found
→ Traffic master disabled OR History subordinate flag disabled

429 concurrency_limit
→ shared Admin capacity exhausted
→ Retry-After

503 query_deadline
→ shared Admin QueryDeadline exceeded

503 source_unavailable
→ historical service/source/serialization unavailable

503 response_too_large
→ existing response-size guard

500 internal_error
→ sanitized unexpected failure
```

Do not reuse current-specific route semantics/telemetry blindly.

Current repository `_current_traffic_query` is oriented around Current Traffic freshness/coverage and `admin.current_traffic_*` events.

History must use either:

```text
dedicated narrow _traffic_history_query(...)
```

or a carefully generalized internal Traffic helper that preserves all existing Current behavior.

History MUST NOT be logged as Current Traffic.

Required safe operational event:

```text
admin.traffic_history_query_completed
```

Minimum safe fields:

```text
request_id
site_id
range_id
http_status
outcome/reason
duration_ms
result_status
coverage_status
bucket_count
```

Optional safe fields:

```text
gap_bucket_count
source_transition_count
response_bytes
```

Never log:

```text
SQL
DB path
raw rows
secrets
tokens
Omada credentials
```

No traceback, SQL, DB path, Omada URL or secret in HTTP response.

---

# 46. Response-size boundary

Reuse existing Admin response-size limit.

Initial ranges are bounded to 288/672 buckets.

Do not create a History-specific response-size setting.

If 7d serialized output exceeds the current Admin response budget:

```text
STOP
→ return measured payload evidence
→ architecture review
```

Do not silently drop buckets or fields.

---

# 47. UI panel

Canonical title:

```text
Network Traffic History
```

Recommended secondary label:

```text
Historical throughput
```

Add one separate panel inside existing:

```text
#traffic-panels
```

Current Network Throughput remains unchanged.

---

# 48. Chart type

FINAL v1:

```text
two-series line chart
Download
Upload
```

No stacked semantics.

No third Total line.

No Period Average / Peak KPI.

---

# 49. Chart implementation technology

Current Admin has no approved external chart dependency.

Preferred v1:

```text
vanilla same-origin JavaScript
+
SVG DOM generated from serialized buckets
+
page-scoped CSS
```

No CDN and no new package solely for the chart.

SVG geometry is presentation logic, not a new Traffic metric.

---

# 50. Axes, legend and accessibility

X axis:

```text
time
```

using returned bucket boundaries/timestamps for presentation only.

Y axis:

```text
Mbps
```

FINAL v1 rule:

```text
Y axis starts at zero
```

to avoid visually exaggerating small changes.

This is chart presentation scaling, not a metric calculation.

Required visible legend:

```text
Download
Upload
```

Legend must remain understandable without relying only on color.

Use:

```text
text labels
+
line/marker distinction
```

SVG/chart MUST provide:

```text
accessible title/description
```

or an equivalent non-visual textual summary.

Critical:

```text
partial
coverage
gap/no-data
```

information MUST NOT exist only in tooltip or color.

---

# 51. Gap rendering

If a series value is `null`:

```text
break the line
```

Forbidden:

```text
null → 0
connect through missing interval as if evidence existed
```

Real `0.0` is plotted on the zero axis.

---

# 52. Partial bucket rendering

Partial bucket with numeric values MAY be plotted because backend explicitly permits numeric values over complete Site samples.

But:

```text
partial numeric evidence
!=
complete interval
```

Functional requirement:

```text
partial points/segments are distinguishable
AND panel state visibly says Partial
```

UI must not interpolate missing buckets.

---

# 53. Source-family presentation

Browser does not select or recompute source.

Per-bucket `wired|lan` is provenance only.

Panel helper:

```text
Source selection is evaluated per bucket.
Wired is primary; LAN may be used as fallback.
```

`source_transition_count` may be shown.

Do not invent a single range-wide selected source if buckets differ.

---

# 54. Historical quality presentation

Minimum visible evidence:

```text
Coverage
Source watermark / source age
Gap bucket count
Source transition count
```

No synthetic `Traffic Health %`.

---

# 55. No invented historical Fresh/Stale taxonomy

`TRAFFIC-02-READ` does not define a generic historical `Fresh/Stale` threshold.

Therefore `TRAFFIC-02` MUST NOT invent one.

Display neutral facts:

```text
source_watermark_utc
source_age_seconds
coverage.status
```

An old requested historical range is not automatically stale.

---

# 56. UI states

## Initial loading

```text
Loading network traffic history…
```

No zero line before data arrives.

## Refreshing/range change

Previous accepted chart may remain visible but keeps its applied-range label until replacement succeeds.

## Ready

```text
status=ok
coverage=complete
→ History ready / Complete
```

## Partial

```text
status=partial or coverage=partial
→ History partial / Partial coverage
```

Plot accepted numeric buckets and preserve gaps.

## No data

```text
status=insufficient_data
coverage=none
→ No historical data for this range
```

No fabricated zero history.

## Source unavailable / deadline

Panel-local failure. Previous accepted chart may remain only if clearly labelled as previously loaded evidence.

## 401/403

Existing coordinator global state.

---

# 57. Manual refresh interactions

Global Traffic `Refresh` remains:

```text
refreshAll({manual:true})
```

History participates even with:

```text
autoRefresh=false
```

The shared Network range control requests the History consumer through:

```text
refreshPanel("network-traffic-history", {manual:true})
```

today because History is currently the only range-sensitive Network panel.

Current Network Throughput is not refreshed solely because selected Network range changes.

If `refreshPanel()` returns `false` because no execution was admitted:

```text
do not show fake loading
do not change applied History range
do not claim a request started
```

Selected Network range may remain at the user's chosen value for the next eligible refresh.

---

# 58. Shared Network range controls

Visible initial controls:

```text
24h
7d
```

They belong to:

```text
Network Traffic analytical context
```

not to the History card as a private permanent owner.

Recommended accessible implementation:

```text
button type=button
aria-pressed
```

State:

```text
selected_network_range
```

is shared/future-facing.

History stores only its own:

```text
applied response range
```

for truthful rendering.

No custom date picker in this TASK.

Future `TRAFFIC-03/04/05/06` MUST consume the same selected Network range instead of creating independent controls.

---

# 59. Stable DOM/state hooks

Preferred shared Network range hooks:

```text
traffic-network-range
traffic-network-range-24h
traffic-network-range-7d
```

History panel hooks:

```text
traffic-history-panel
traffic-history-heading
traffic-history-state
traffic-history-state-title
traffic-history-state-message
traffic-history-applied-range
traffic-history-chart
traffic-history-chart-svg
traffic-history-legend
traffic-history-coverage
traffic-history-watermark
traffic-history-gaps
traffic-history-source-transitions
traffic-history-timezone
```

Avoid permanent History-owned range hook names such as:

```text
traffic-history-range-24h
traffic-history-range-7d
```

because the range is shared Network Traffic state.

Hooks used by JavaScript are contracts.

This shared state does NOT create a second scheduler/request coordinator.

---

# 60. Browser DTO validation

Browser validates the safe serialized contract before rendering.

At minimum:

```text
result status = ok|partial|insufficient_data

range.id = 24h|7d
range.unit = Mbps
range.metric_version = network_traffic_history.v1
range.aggregation = mean_of_complete_site_rate_samples

24h:
bucket_seconds=300
bucket_count=288

7d:
bucket_seconds=900
bucket_count=672

range.evaluated_at_utc == range.to_utc

buckets array length == bucket_count

bucket status = complete|partial|none
selected_source = wired|lan|null
Mbps = finite non-negative or null

coverage.status = complete|partial|none
coverage.bucket_count == range.bucket_count
```

Browser does not replace backend serializer validation; this protects presentation from malformed HTTP 200 payloads.

Malformed HTTP 200 becomes panel-local safe unexpected failure.

---

# 61. Browser calculation prohibitions

Browser MUST NOT calculate canonical API boundaries using local clock arithmetic.

Forbidden for API construction:

```text
Date.now() - 24h
Date.now() - 7d
```

Allowed:

```text
format returned timestamps for display
```

Browser also MUST NOT:

```text
sum APs
average history samples
calculate canonical totals
fill nulls
calculate coverage
select source
```

SVG coordinate scaling is presentation-only.

---

# 62. Exact functional scope

In scope:

```text
Admin injection of accepted HistoricalTrafficReadService
server-side 24h/7d range resolver
safe Admin History serializer
Site-scoped History endpoint
History panel markup
Download/Upload chart
24h/7d selector
quality/coverage state
watermark/source-age display
gap-safe rendering
shared coordinator integration
focused tests
Central Lab acceptance definition
```

---

# 63. Explicit non-goals

Out of scope:

```text
TRAFFIC-03 Period Statistics
Average Download/Upload/Total
Peak Download/Upload/Total
TRAFFIC-04 Peak Load
busiest hour/day
TRAFFIC-05 Traffic by AP
TRAFFIC-06 AP Share
TRAFFIC-07 Online Guests
TRAFFIC-08 Completed Guest Session Traffic
TRAFFIC-09 consolidated Traffic Evidence
TRAFFIC-10 30-day UI enablement
TRAFFIC-11 Heatmap
TRAFFIC-12 Period Comparison
custom range
calendar range
new collector
native Omada history acquisition
new Traffic DB/cache/rollup
schema migration
Home redesign
```

---

# 64. No TRAFFIC-03 leakage

History bucket arithmetic mean is NOT a canonical Period Average.

`TRAFFIC-02` MUST NOT create visible:

```text
Average Download
Average Upload
Average Total
```

Future `TRAFFIC-03` remains interval/time-aware and must use/extend `HistoricalTrafficReadService`, not create independent SQL.

---

# 65. No AP history/share leakage

No:

```text
AP selector
per-AP series
AP table
AP average/peak
AP share %
```

Those belong to `TRAFFIC-05/06`.

---

# 66. No Guest Session Traffic leakage

Do not mix Visit Lifecycle/session bytes into this panel.

This remains AP/network Mbps history.

---

# 67. No 30-day UI enablement

Read foundation supports 30d, but this task does not expose it.

`TRAFFIC-10` remains owner of 30-day product enablement/benchmark decision.

---

# 68. No native Omada product history

Do not call:

```text
dashboard/traffic-activities
dashboard/traffic-distribution
```

from Admin/browser/product read path.

They remain validation/reference sources.

---

# 69. No rollup/cache/storage

Forbidden:

```text
traffic_history.sqlite3
materialized history table
JSON cache
Redis
background rollup worker
long-lived in-memory history cache
```

Current read performance already passed accepted hard deadline.

---

# 70. New subordinate product configuration

Add repository-safe default:

```text
WEB_ADMIN_TRAFFIC_HISTORY_ENABLED=false
```

Configuration path:

```text
app/config.py
→ app/settings.py
→ app/admin_web/config.py
→ AdminWebConfig.traffic_history_enabled
→ routes.py / pages.py
→ traffic.html
→ History registration
```

Dependency:

```text
History=true
requires Admin=true AND Traffic=true
```

No new:

```text
refresh interval
request timeout
query deadline
response-size limit
```

History reuses:

```text
WEB_ADMIN_TRAFFIC_REQUEST_TIMEOUT_SECONDS
WEB_ADMIN_MAX_CONCURRENT_QUERIES
WEB_ADMIN_MAX_QUERY_DURATION_SECONDS
WEB_ADMIN_MAX_RESPONSE_BYTES
```

`.env.example` includes:

```text
WEB_ADMIN_TRAFFIC_HISTORY_ENABLED=false
```

No production environment change belongs to implementation.

---

# 71. History feature exposure semantics

When:

```text
WEB_ADMIN_TRAFFIC_HISTORY_ENABLED=false
```

required:

```text
Traffic page remains available if master Traffic=true
Current Network Throughput remains available
shared Network range control for History is absent
History markup absent
History panel not registered
zero History product requests
direct History endpoint → 404
```

When:

```text
WEB_ADMIN_TRAFFIC_HISTORY_ENABLED=true
```

and master Admin/Traffic gates are valid:

```text
History markup/control present
History panel registers once
History endpoint exposed
one initial History request
```

Historical read-service lifecycle remains independent of UI flag.

---

# 72. Expected production files to change

Expected MODIFY:

```text
app/config.py
app/settings.py
.env.example

app/admin_web/config.py
app/admin_web/pages.py
app/admin_web/runtime.py
app/admin_web/query_service.py
app/admin_web/routes.py
app/admin_web/static/admin.js
app/admin_web/static/admin.css
app/admin_web/templates/admin/traffic.html
```

Expected ADD:

```text
app/admin_web/traffic_network_ranges.py
app/admin_web/historical_traffic_serialization.py
```

Preferred tests ADD:

```text
tests/admin_web/test_traffic_history.py
tests/admin_web/test_traffic_history_frontend.py
```

`base.html` does not require modification if all History conditional markup remains inside `traffic.html` and `traffic_history_enabled` is passed explicitly through `render_admin_page()`.

---

# 73. Expected unchanged files

Expected unchanged:

```text
app/analytics/**
app/observations/**
app/current_state/**
app/visit_lifecycle/**
app/visitor_registry/**

app/admin_web/templates/admin/base.html
app/admin_web/current_traffic_serialization.py

run.py
requirements*
```

The following are now expected to change specifically because the subordinate History flag is approved:

```text
app/config.py
app/settings.py
.env.example
app/admin_web/config.py
app/admin_web/pages.py
```

If implementation requires changes outside the expected scope, especially `app/analytics/**` or source/acquisition code:

```text
STOP
→ factual reason
→ Owner/Tech Lead architecture review
```

---

# 74. Why config/pages/runtime change

## Config/settings

Required only for:

```text
WEB_ADMIN_TRAFFIC_HISTORY_ENABLED=false
```

and its fail-closed dependency validation.

## pages.py

Current `render_admin_page()` uses explicit template context.

Therefore add an explicit safe:

```text
traffic_history_enabled
```

context value for the Traffic template.

Do not derive it in browser code from raw settings.

## runtime.py

Current Admin composition injects Current Traffic and Home Activity services but not:

```text
analytics_runtime.historical_traffic_service
```

Add only the optional dependency bridge.

No new Analytics runtime construction.

No runtime readiness dependency on the historical service.

---

# 75. Why query_service.py changes

Add only:

```text
optional historical service dependency
historical_traffic_history(...)
```

No changes to Current Traffic/Home semantics.

---

# 76. Why routes.py changes

Add one Site-scoped GET endpoint using existing auth, Site resolver, policy, master Traffic feature gate, safe error envelope and response-size enforcement.

No new Blueprint.

---

# 77. Why traffic.html/admin.js/admin.css change

`traffic.html` adds one functional panel.

`admin.js` adds one coordinator consumer.

`admin.css` adds only page-scoped chart/range/quality presentation.

No Traffic coordinator contract change should be required.

If coordinator public API must change:

```text
STOP
→ architecture review
```

---

# 78. Coder testing ownership

Coder runs only focused/minimal `TRAFFIC-02` tests and relevant static checks.

Coder MUST NOT independently run:

```text
existing TRAFFIC-00 regression
existing TRAFFIC-01 regression
Home broader regression
Analytics broader regression
full tests/admin_web
full tests/analytics
full repository pytest
Central Lab V6
official differential/release gate
```

Those are Central Lab-owned.

---

# 79. Required focused backend/API + feature-flag tests

## Shared range resolver

```text
default selected Network range = 24h

24h:
exact duration 86400
server evaluated_at == to

7d:
exact duration 604800
server evaluated_at == to

unknown range rejected
30d rejected in v1
```

## Feature configuration

```text
default History flag=false

History=true + Traffic=false
→ configuration invalid / fail closed

History=true + Admin=false
→ configuration invalid / fail closed
```

## Page/API exposure

```text
Traffic=true + History=false
→ Traffic page 200
→ Current panel present
→ History panel/range controls absent
→ History endpoint 404

Traffic=true + History=true
→ History panel/control present
→ History endpoint enabled

History=true + historical service absent
→ History endpoint 503
→ Current panel unaffected
→ Admin runtime remains usable
```

## Endpoint validation/security

```text
valid session + Site + range=24h → 200
valid session + Site + range=7d → 200
missing range → 400
duplicate range → 400
unknown query parameter → 400
invalid Site → 400
forbidden Site → 403
no session → 401
master Traffic disabled → 404
History disabled → 404
```

---

# 80. Required focused application/read tests

With deterministic fake `HistoricalTrafficReadService` prove:

```text
Admin query passes exact resolved:
site_id
from_utc
to_utc
evaluated_at_utc

evaluated_at_utc == to_utc

bucket_seconds is not caller/browser selected

shared Admin QueryDeadline is passed

service absent → 503 source_unavailable

HistoricalTrafficValidationError → 400

HistoricalTrafficSourceUnavailable → 503 source_unavailable

shared query deadline exceeded → 503 query_deadline

busy execution controls → 429 + Retry-After
```

Telemetry:

```text
History emits admin.traffic_history_query_completed
History is NOT logged as admin.current_traffic_*
safe event fields only
```

---

# 81. Required focused serializer tests

At minimum:

```text
24h:
duration=86400
bucket_seconds=300
bucket_count=288

7d:
duration=604800
bucket_seconds=900
bucket_count=672

evaluated_at == to

service range exactly equals resolved application range

complete result
partial result
insufficient_data result

status ↔ coverage consistency

coverage bucket sum:
complete + partial + missing == total

coverage.bucket_count == range.bucket_count

valid 0.0 preserved

none bucket:
null numeric values
selected_source=null
complete_site_sample_count=0

complete/partial usable bucket:
source wired|lan
complete_site_sample_count>0
finite non-negative Download/Upload/Total

Download + Upload ≈ Total validation

gap/source-transition fields preserved

bucket order/contiguity

invalid duration rejected
invalid bucket resolution rejected
bucket count mismatch rejected
>720 rejected
invalid unit/aggregation/source/metric version rejected
non-finite/negative numeric rejected
malformed timestamp rejected
aggregate-count inconsistency rejected where safely verifiable
```

---

# 82. Required focused frontend ownership/state-machine tests

```text
History registers only when:
page=traffic
master Traffic enabled
History subordinate flag enabled
required DOM hooks exist

panel key =
network-traffic-history

autoRefresh=false

registration causes exactly one initial load

initial selected Network range=24h

initial request =
/traffic/history?range=24h

one shared Network range owner exists

History consumes shared range

Current Network Throughput ignores Network range changes

no History-private permanent range owner

future-facing contract reserves same selected range for TRAFFIC-03/04/05/06
```

No duplicate lifecycle owner:

```text
no History setInterval
no History private polling setTimeout
no History visibilitychange owner
no History pagehide owner
no History AbortController owner
no duplicate global Refresh listener
no direct History fetch()
```

---

# 83. Required focused frontend semantic/state regressions

## Data rendering

```text
complete buckets render Download/Upload

real 0.0 plots zero

null bucket creates gap, not zero

partial numeric bucket remains visible
with non-color-only partial indication

insufficient_data shows no-data state

Y axis starts at zero

critical coverage/partial evidence has visible text
not tooltip-only

SVG has accessible title/description or equivalent non-visual summary
```

## selected vs applied

```text
applied=24h
select 7d
→ selected=7d
→ old chart remains Applied 24h
→ success commits applied=7d
→ failure keeps selected=7d and applied=24h
```

## Coordinator backoff false-return

When:

```text
refreshPanel(..., {manual:true}) returns false
```

prove:

```text
no fake Loading state
no applied-range change
no claim that request was made
selected range may remain user choice
```

## Rapid supersession

Sequence:

```text
24h applied
→ select 7d
→ before completion select 24h
```

prove:

```text
first execution becomes neutral/superseded under coordinator generation/AbortController
loader captured its execution range locally
render trusts validated response.range.id
final applied result comes only from latest successful execution
mutable selected-range state cannot relabel stale response
```

## Calculation prohibition

```text
browser does not compute API from/to
browser does not sum/average AP/history data
browser does not calculate canonical Total
browser does not select source
browser does not calculate coverage
```

---

# 84. Proposed Coder command

```bash
python -m pytest -q \
  tests/admin_web/test_traffic_history.py \
  tests/admin_web/test_traffic_history_frontend.py
```

Static:

```bash
PYTHONPYCACHEPREFIX=/tmp/captivportal-pyc \
python -m compileall -q app/admin_web

git diff --check
```

Coder handoff records exact files, command and passed/skipped/failed.

---

# 85. Central Lab targeted regression scope

Owner + Tech Lead / Central Lab should run, on exact candidate, at minimum:

```text
new TRAFFIC-02 focused tests

existing TRAFFIC-02-READ:
tests/analytics/test_historical_traffic.py
tests/analytics/test_historical_traffic_runtime.py

TRAFFIC-00 Foundation/coordinator regression
TRAFFIC-01 Current Network Throughput regression
relevant shared Admin runtime/query/routes/frontend regression
Home Current Traffic shared-boundary regression
```

Exact targeted command is rebuilt by Tech Lead against the current candidate/test set.

---

# 86. TRAFFIC-00 regression invariants

Central Lab verifies:

```text
one Traffic coordinator
one initial load per registration
refreshPanel remains selected-panel only
refreshAll remains global manual refresh
same-origin request enforcement
generation/abort/backoff unchanged
hidden/pagehide ownership unchanged
panel failure isolation unchanged
global 401/403 unchanged
```

---

# 87. TRAFFIC-01 regression invariants

Verify:

```text
Current Network Throughput still loads
Current endpoint unchanged
Current panel remains autoRefresh=true
History range change does not reload Current
Current source/freshness/coverage unchanged
```

No Current Traffic semantic file is expected to change.

---

# 88. Home Traffic regression boundary

Because Admin composition/query code is shared, Central Lab verifies existing Home Current Traffic contracts remain unchanged.

Coder does not own this cross-surface execution.

---

# 89. Historical read foundation regression

Verify no semantic drift in:

```text
24h → 288
7d → 672
MAX_SITE_HISTORY_BUCKETS=720
source selection
gap semantics
partial numeric rule
none/null rule
watermark/as-of behavior
```

`TRAFFIC-02` consumes results; it does not alter them.

---

# 90. Full Central Lab gate

Official PASS/FAIL belongs to Owner + Tech Lead / Central Lab.

Use the CURRENT VERIFIED runner at execution time.

Official evidence includes exact candidate/baseline, targeted regression, full approved regression, compatibility baseline, strict regressions, compileall, diff-check and exact-artifact immutability.

---

# 91. API performance acceptance — FINAL decision

Performance/SLA question is closed:

```text
ACCEPT CURRENT v1 PERFORMANCE
```

No `<2s` History SLA is introduced.

History creates no dedicated deadline/timeout.

Current/default shared budgets:

```text
Admin QueryDeadline:
WEB_ADMIN_MAX_QUERY_DURATION_SECONDS = 10s

Traffic browser timeout:
WEB_ADMIN_TRAFFIC_REQUEST_TIMEOUT_SECONDS = 20s

Admin response bound:
WEB_ADMIN_MAX_RESPONSE_BYTES = authoritative
```

Accepted `TRAFFIC-02-READ` benchmark:

```text
24h 288 buckets p95 5.23s
7d  672 buckets p95 4.59s
```

Central Lab MUST measure final end-to-end Admin API:

```text
24h
7d
```

Record:

```text
HTTP status
wall-clock duration
bucket count
serialized response bytes
query deadline result
```

If 7d compact response exceeds configured Admin response bound, or normal execution exceeds approved shared deadline:

```text
STOP
→ evidence
→ architecture review
```

Forbidden silent responses:

```text
increase max_response_bytes
increase deadline
add History-specific timeout
add cache
add rollup
add new DB
```

---

# 92. Initial two-panel concurrency

After `TRAFFIC-02`, Traffic page has:

```text
Current panel
History panel
```

Both receive one initial load. Existing default Admin concurrency budget supports two concurrent queries.

No concurrency-setting change is authorized.

If normal two-panel page load systematically yields 429:

```text
STOP
→ evidence
→ architecture review
```

---

# 93. Browser acceptance

Controlled authenticated acceptance with:

```text
WEB_ADMIN_TRAFFIC_ENABLED=true
WEB_ADMIN_TRAFFIC_HISTORY_ENABLED=true
```

must prove:

```text
Traffic page opens
Current Network Throughput remains visible
Network Traffic History appears
shared Network range control appears
24h selected by default
one initial History request
Download/Upload chart visible
legend visible
Y axis starts at zero
unit Mbps visible
display timezone visible
accessible chart summary present

24h → 7d
→ selected shared Network range changes
→ only History refreshes today
→ Current panel does not reload

7d → 24h
→ same rule

global Refresh
→ Current + History through shared coordinator

no duplicate request loop
no console exception
```

With History flag=false:

```text
History markup/control absent
zero History requests
Current panel remains available
```

---

# 94. Gap/partial acceptance

Fixture containing:

```text
real zero bucket
missing bucket
real numeric bucket
```

must prove:

```text
zero != gap
```

Partial response with numeric + missing buckets must show partial quality, accepted points and visible gaps.

---

# 95. Failure isolation acceptance

Controlled:

```text
/traffic/history → 503 source_unavailable
```

must leave:

```text
Traffic page operational
Current Network Throughput operational
only History unavailable
```

No global page failure.

---

# 96. Browser network/security acceptance

Expected product request only:

```text
/admin/api/v1/sites/<site_id>/traffic/history?range=...
```

Forbidden:

```text
Omada
Loki
Grafana
Analytics bearer endpoint
Observation raw API/DB
external chart CDN
```

---

# 97. No production config change during implementation

Implementation code MAY add repository configuration support and `.env.example` entry for:

```text
WEB_ADMIN_TRAFFIC_HISTORY_ENABLED=false
```

but MUST NOT modify production:

```text
/etc/default/captive-portal
actual WEB_ADMIN_TRAFFIC_HISTORY_ENABLED
WEB_ADMIN_TRAFFIC_ENABLED
Admin credentials
Observation settings
Analytics settings
systemd
Nginx
```

No deploy or activation is implied by implementation.

---

# 98. Merge/deploy/activation separation

```text
FINAL
→ explicit Owner implementation authorization
→ Coder implementation
→ Coder focused tests
→ Central Lab acceptance
→ Owner merge authorization
→ merge
→ production code deploy with History=false
→ dormant post-check
→ separate Owner activation History=true
→ product acceptance
```

This FINAL grants only the architecture/specification.

It does NOT grant implementation, merge, deploy or activation.

---

# 99. Production activation and rollback

Subordinate flag resolves the DRAFT deployment-exposure problem.

Preferred production sequence:

```text
1. deploy accepted code
2. keep WEB_ADMIN_TRAFFIC_HISTORY_ENABLED=false
3. verify dormant post-check:
   - Traffic page/Current panel unchanged
   - History endpoint 404
   - zero History product requests
4. separate Owner authorization
5. set WEB_ADMIN_TRAFFIC_HISTORY_ENABLED=true
6. restart/reload through approved deployment procedure
7. perform History product acceptance
```

History-specific rollback:

```text
WEB_ADMIN_TRAFFIC_HISTORY_ENABLED=false
```

This hides/disables History product exposure without disabling accepted Current Network Throughput.

Master:

```text
WEB_ADMIN_TRAFFIC_ENABLED
```

remains unchanged.

---

# 100. Architecture decisions

```text
Canonical historical semantic owner:
HistoricalTrafficReadService

Network range owner:
Traffic page / shared Network Traffic analytical context

Initial shared Network ranges:
24h / 7d

Default selected Network range:
24h

Future shared range consumers:
TRAFFIC-03 / 04 / 05 / 06

Current Network Throughput:
range-insensitive

Canonical range math:
server UTC

Browser range math:
NO

History applied range:
last successful response.range.id

Endpoint:
GET /admin/api/v1/sites/<site_id>/traffic/history?range=...

Master flag:
WEB_ADMIN_TRAFFIC_ENABLED

Subordinate History flag:
WEB_ADMIN_TRAFFIC_HISTORY_ENABLED=false

History autoRefresh:
false

Initial load:
yes, coordinator registration

Range reload today:
refreshPanel(history)

Global reload:
refreshAll()

Request lifecycle owner:
CaptivPortalTrafficCoordinator only

Chart:
Download + Upload line chart

Y axis:
starts at zero

Visible Total series/KPI:
NO

Missing bucket:
gap, not zero

Partial numeric:
allowed, visibly partial

New acquisition:
NO

New DB/schema/cache/rollup:
NO

Native Omada product source:
NO

History-specific deadline/timeout:
NO

Performance decision:
accept current v1 shared budgets
```

---

# 101. Exact scope

In scope:

```text
subordinate History feature flag
explicit safe template context
Admin optional historical service injection
shared Network range state/resolver foundation
server-side 24h/7d resolution
safe cross-field History serializer
Site-scoped History endpoint
dedicated safe History telemetry
History panel markup
shared Network 24h/7d control
Download/Upload SVG chart
Y axis zero baseline
accessibility summary
coverage/quality presentation
watermark/source-age presentation
gap-safe rendering
selected/applied state machine
rapid supersession correctness
shared coordinator integration
focused tests
Central Lab acceptance definition
```

---

# 102. Explicit non-goals

```text
TRAFFIC-03 Period Statistics
Period Average
Peak KPIs
TRAFFIC-04 Peak Load
TRAFFIC-05 Traffic by AP
TRAFFIC-06 AP Share
TRAFFIC-07 Online Guests
TRAFFIC-08 Guest Session Traffic
TRAFFIC-09 consolidated Evidence
TRAFFIC-10 30d UI
TRAFFIC-11 Heatmap
TRAFFIC-12 Period Comparison
custom/calendar ranges
new collector
Omada history acquisition
new DB/cache/rollup
schema migration
Home redesign
```

---

# 103. API contract summary

```text
GET /admin/api/v1/sites/<site_id>/traffic/history

required query:
range=24h|7d

security:
Admin auth
→ Site resolution
→ admin.read.context
→ Traffic master gate
→ History subordinate gate
→ AdminQueryService/admin.read.overview

200:
ok | partial | insufficient_data

400:
invalid_request

401:
authentication_required

403:
site_forbidden

404:
not_found when master Traffic disabled
or History subordinate flag disabled

429:
concurrency_limit

503:
query_deadline | source_unavailable | response_too_large
```

No caller-supplied:

```text
from/to/evaluated_at/bucket/source/AP/SSID
```

---

# 104. UI states summary

Shared Network context:

```text
selected range:
24h | 7d
```

History panel:

```text
no markup when History flag=false

initial loading

selected range changed / execution admitted
→ loading selected range
→ previous applied evidence may remain

selected range changed / coordinator returns false
→ no fake loading

ready / complete

partial

no historical data / insufficient_data

panel-local unavailable/timeout/error

previous-success evidence after failed refresh

global auth/Site state via existing coordinator
```

Permanent:

```text
null != zero
partial != complete
selected range != applied range
old applied range != newly selected range
latest successful non-superseded execution owns applied state
```

---

# 105. Closed decision — dormant production deploy

Resolved by Tech Lead:

```text
REQUIRE subordinate History feature flag
```

Canonical:

```text
WEB_ADMIN_TRAFFIC_HISTORY_ENABLED=false
```

Therefore:

```text
code deploy can remain dormant
Current Network Throughput stays visible
History activation is separately Owner-controlled
History rollback does not require disabling master Traffic
```

This question is CLOSED.

---

# 106. Closed decision — interactive SLA

Resolved by Tech Lead:

```text
ACCEPT CURRENT v1 PERFORMANCE
```

No `<2s` requirement.

No:

```text
cache
rollup
new DB
deadline increase
History-specific timeout
```

Current/default shared budgets remain authoritative and may only change through their own approved configuration/architecture process.

This question is CLOSED.

---

# 107. Repository files expected to change

Expected MODIFY:

```text
app/config.py
app/settings.py
.env.example

app/admin_web/config.py
app/admin_web/pages.py
app/admin_web/runtime.py
app/admin_web/query_service.py
app/admin_web/routes.py
app/admin_web/static/admin.js
app/admin_web/static/admin.css
app/admin_web/templates/admin/traffic.html
```

Expected ADD:

```text
app/admin_web/traffic_network_ranges.py
app/admin_web/historical_traffic_serialization.py

tests/admin_web/test_traffic_history.py
tests/admin_web/test_traffic_history_frontend.py
```

Expected unchanged:

```text
app/analytics/**
app/observations/**
app/current_state/**
app/visit_lifecycle/**
app/visitor_registry/**
app/admin_web/templates/admin/base.html
app/admin_web/current_traffic_serialization.py
run.py
requirements*
```

Any required change to accepted historical calculation/source ownership is a STOP condition.

---

# 108. Focused test scope

Coder focused:

```text
History flag default/dependency validation
History disabled exposure behavior
History enabled + service absent isolation
shared Network range owner
24h/7d resolver
query-service bridge
API validation/security
dedicated History telemetry
serializer cross-field invariants
status/coverage consistency
gap != zero
valid zero
frontend DTO validation
shared range controls
selected/applied state machine
backoff false-return behavior
rapid range supersession
refreshPanel integration
no direct fetch
no duplicate scheduler
no browser range math
no browser canonical Traffic calculation
chart zero baseline/accessibility
```

Coder does not run broader/cross-module/full regression.

---

# 109. Central Lab regression scope

Central Lab:

```text
TRAFFIC-02 focused candidate

feature-gate matrix

TRAFFIC-02-READ regression

TRAFFIC-00 Foundation/coordinator regression

TRAFFIC-01 Current Network Throughput regression

shared Network range future-facing invariant

shared Admin config/pages/runtime/query/routes/frontend regression

Home Current Traffic shared-boundary regression

24h/7d Admin API performance/payload check

full current Central Lab gate

exact-artifact immutability
```

Central Lab must specifically prove:

```text
History disabled → zero History requests
Current panel unaffected

History service absent → panel-local 503
Admin/Current unaffected

range changes do not refresh Current

rapid supersession latest generation wins

no duplicate scheduler/request coordinator
```

---

# 110. Risks

## R1 — History query latency

Mitigation:

```text
autoRefresh=false
explicit loading state
retain previous applied chart truthfully
shared Traffic browser timeout
shared Admin QueryDeadline
no duplicate polling
```

## R2 — query concurrency

Mitigation:

```text
existing shared max_concurrent_queries
coordinator 429/backoff
no History periodic polling
```

## R3 — visual gap misrepresentation

Mitigation:

```text
null breaks line
zero remains plotted
partial visibly distinguished
Y axis starts at zero
critical evidence not tooltip-only
```

## R4 — selected/applied state confusion

Mitigation:

```text
shared selected Network range
separate History applied response range
old chart never relabelled
false-return does not fake execution
```

## R5 — rapid supersession race

Mitigation:

```text
execution-local range capture
coordinator generation/AbortController
render trusts validated response.range.id
latest successful non-superseded execution wins
```

## R6 — TRAFFIC-03 semantic leakage

Mitigation:

```text
no Average/Peak KPI
History bucket mean != Period Average
```

## R7 — accidental product exposure on deploy

Mitigation:

```text
WEB_ADMIN_TRAFFIC_HISTORY_ENABLED=false default
dormant deploy
separate activation
```

## R8 — current-specific telemetry semantic pollution

Mitigation:

```text
dedicated History route/helper
admin.traffic_history_query_completed
no admin.current_traffic_* reuse for History
```

---

# 111. Stop conditions

Implementation MUST STOP and return evidence if it requires:

```text
changing HistoricalTrafficReadService semantics

changing AnalyticsSourceGateway historical algorithm

changing MAX_SITE_HISTORY_BUCKETS

changing source-family selection

changing gap/partial semantics

changing Observation acquisition/schema

new Omada traffic call

raw Observation DB access from Admin

cache/rollup/Traffic DB

new chart dependency/CDN

second request scheduler/coordinator

breaking CaptivPortalTrafficCoordinator public contract

independent History-private range ownership

Home Traffic semantic change

30d selector

Period Average/Peak
```

Also STOP if:

```text
current origin/main materially changes before implementation

7d serialized payload exceeds approved Admin response bound

normal History path cannot execute inside approved shared Admin QueryDeadline

normal two-panel load systematically exceeds shared concurrency budget
```

Do not silently widen budgets or add storage optimizations.

---

# 112. FINAL implementation acceptance checklist

Before Coder authorization, Owner should verify this FINAL against current `origin/main`.

Implementation acceptance requires all of the following:

1. `HistoricalTrafficReadService` remains sole historical semantic owner.
2. Shared Network range owner belongs to Traffic analytical context.
3. Initial shared ranges are exactly `24h|7d`.
4. `TRAFFIC-03/04/05/06` are reserved to reuse this range owner.
5. Current Network Throughput is range-insensitive.
6. Endpoint is `/traffic/history`.
7. Endpoint requires explicit `range`.
8. Server resolves rolling UTC boundaries.
9. Browser never constructs canonical from/to.
10. History uses subordinate `WEB_ADMIN_TRAFFIC_HISTORY_ENABLED=false`.
11. History flag requires Admin + master Traffic.
12. History flag controls exposure only, not service lifecycle.
13. History `autoRefresh=false`.
14. Coordinator remains sole request lifecycle owner.
15. selected Network range and History applied range are distinct.
16. coordinator false-return cannot create fake loading.
17. rapid supersession latest generation wins.
18. Download/Upload line chart only.
19. Y axis starts at zero.
20. Null breaks line; zero remains zero.
21. Partial numeric evidence remains visibly partial.
22. Accessibility/critical quality text is non-tooltip-only.
23. Serializer enforces exact 24h/7d cross-field invariants.
24. Dedicated History telemetry is used.
25. No History-specific deadline/timeout.
26. Current v1 performance is accepted.
27. Proposed file scope includes config/settings/pages due subordinate flag.
28. Coder executes focused tests only.
29. Central Lab owns broader/cross-module/full regression.
30. Production deploy remains dormant with History=false until separate activation.

---

# 113. FINAL status

```text
TASK:
TRAFFIC-02 — Historical Network Traffic / History

STATUS:
FINAL — TECH LEAD REVIEW INCORPORATED

BOUND TO:
main@6b4adf770ab1afa289dac14680ba876711088d94

TREE:
04f5e2d23da8b2d44390c285fc14dbb62fa06221

DEPENDENCIES:
TRAFFIC-00 DONE / MERGED / PRODUCTION
TRAFFIC-01 DONE / MERGED / PRODUCTION
TRAFFIC-02-READ DONE / ACCEPTED / MERGED

CANONICAL HISTORICAL OWNER:
HistoricalTrafficReadService

SHARED NETWORK RANGE OWNER:
Traffic page / Network Traffic analytical context

INITIAL RANGES:
24h / 7d

HISTORY PRODUCT FLAG:
WEB_ADMIN_TRAFFIC_HISTORY_ENABLED=false

NEW ACQUISITION:
NO

NEW DB / SCHEMA / ROLLUP:
NO

PERFORMANCE:
CURRENT v1 ACCEPTED
NO HISTORY-SPECIFIC SLA/DEADLINE/TIMEOUT

IMPLEMENTATION AUTHORIZATION:
NOT GRANTED BY THIS FINAL

BRANCH / CODE / COMMIT / PUSH / PR / MERGE:
NOT AUTHORIZED BY THIS FINAL

PRODUCTION DEPLOYMENT:
NOT GRANTED

PRODUCTION ACTIVATION:
NOT GRANTED
```

Required next step:

```text
Owner reviews this FINAL against current origin/main
→ separate explicit Owner implementation authorization
→ Coder focused implementation
→ Central Lab acceptance
→ separate merge/deploy/activation decisions
```

This FINAL is coder-ready architecture, but it is **not** itself permission to implement.

---

