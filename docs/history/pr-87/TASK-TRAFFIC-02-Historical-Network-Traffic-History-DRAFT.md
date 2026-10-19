# TASK-TRAFFIC-02 — Historical Network Traffic / History — DRAFT

**Project:** CaptivPortal  
**Area:** Admin Console → Traffic  
**Parent:** `CaptivPortal — Генеральная дорожная карта раздела Admin Console → Traffic — FINAL v1`  
**Dependencies:** `TASK-TRAFFIC-00`, `TASK-TRAFFIC-01`, `TASK-TRAFFIC-02-READ`  
**Type:** architecture / Admin application + API + presentation integration specification  
**Status:** `DRAFT — FOR OWNER + TECH LEAD REVIEW`  
**Implementation authorization:** `NOT GRANTED`  
**Branch / code / commit / push / PR / merge:** `NOT AUTHORIZED BY THIS DRAFT`  
**Deployment / production activation:** `NOT AUTHORIZED BY THIS DRAFT`  
**Prepared:** 2026-08-29

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

Initial product ranges:

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

`TRAFFIC-02` is deliberately a presentation/API consumer of the accepted `HistoricalTrafficReadService`.

This DRAFT proposes:

```text
NO new collector
NO new Omada polling
NO new Traffic DB
NO schema migration
NO rollup/cache persistence
NO Browser/Admin direct Observation SQL
NO Browser/Admin → Omada
NO new Traffic feature flag by default
NO second Traffic frontend coordinator
NO TRAFFIC-03 Period Statistics
```

Functional chart:

```text
two-series historical line chart
Download
Upload
unit = Mbps
```

`total_mbps` remains a canonical backend bucket field but is not introduced as a third visible History line or Period KPI in `TRAFFIC-02 v1`.

---

# 1. Exact repository rebind

Repository state was rechecked before preparing this DRAFT.

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

If `origin/main` changes before FINAL or implementation authorization, re-fetch and re-pin exact SHA/tree. Mandatory impact review if newer main touches `app/analytics/historical_traffic.py`, `app/analytics/models.py`, `app/analytics/runtime.py`, `app/analytics/source_gateway.py`, or the relevant `app/admin_web/**` files.

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

DRAFT decision:

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

# 11. Initial product ranges

Exact public range IDs:

```text
24h
7d
```

Default UI range:

```text
24h
```

Future `30d` is NOT enabled by this TASK.

```text
range=30d
→ 400 invalid_request
```

This does not impose a 30-day or 31-day backend ceiling.

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

# 13. Canonical application range resolver

Add a narrow reusable application helper.

Preferred file:

```text
app/admin_web/traffic_history_ranges.py
```

Conceptual contract:

```python
resolve_traffic_history_range(
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

Browser sends only the range ID.

Browser MUST NOT construct:

```text
from_utc
to_utc
bucket_seconds
```

---

# 14. evaluated_at and range boundaries

For every History request, server/application captures one canonical:

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
from_utc = evaluated_at_utc - 24 hours
```

For `7d`:

```text
from_utc = evaluated_at_utc - 7 * 24 hours
```

Intervals are exactly:

```text
[from_utc,to_utc)
```

`24h` and `7d` are rolling fixed durations, not calendar day/week reports.

---

# 15. Range/bucket ownership

The application resolver chooses only:

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
```

Those remain `HistoricalTrafficReadService` responsibilities.

---

# 16. Timezone responsibility

Canonical persistence/query/bucket time is UTC.

API returns UTC timestamps.

Browser responsibility is presentation only.

DRAFT v1:

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

# 17. Range switching

Panel keeps only a safe enum:

```text
24h | 7d
```

Canonical flow:

```text
range control
→ requested range ID
→ coordinator.refreshPanel(
     "network-traffic-history",
     {manual:true}
   )
→ panel load
→ GET /traffic/history?range=<id>
```

Forbidden:

```text
range control → fetch()
range control → panel.load()
range control → AbortController
range control → calculate from/to
```

---

# 18. Applied vs requested range

Because accepted read latency is several seconds, UI must distinguish:

```text
requested range
applied range
```

Existing accepted chart remains labelled by its response/applied range until a new response succeeds.

Example:

```text
24h chart visible
user clicks 7d
→ show "Loading 7d…"
→ do not relabel old chart as 7d
→ on success commit 7d result
→ on failure keep 24h applied state + show failure
```

---

# 19. Historical refresh policy

DRAFT decision:

```text
History panel autoRefresh = false
```

Reason: historical reads are relatively heavy, one initial load already exists, global manual Refresh exists, and range-specific Refresh exists.

Canonical:

```text
register
→ one initial 24h load

autoRefresh=false
→ no periodic History polling

global Refresh
→ refreshAll()
→ History reloads

range change
→ refreshPanel(history)
→ only History reloads
```

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

Required:

```text
Admin authentication
        ↓
canonical Site resolution
        ↓
authorize admin.read.context
        ↓
WEB_ADMIN_TRAFFIC_ENABLED
        ↓
AdminQueryService
        ↓
authorize admin.read.overview
        ↓
server-side range resolution
        ↓
HistoricalTrafficReadService
```

No new auth, Site resolver or browser Bearer token.

---

# 28. Feature gate

Reuse only:

```text
WEB_ADMIN_TRAFFIC_ENABLED
```

Authorized Site + Traffic disabled:

```text
404 not_found
```

Shared historical read service lifecycle remains independent of product exposure.

No History-specific flag is proposed by default.

---

# 29. Optional historical dependency

`analytics_runtime.historical_traffic_service` is already optional/fail-open.

Admin composition injects it into `AdminQueryService` as optional:

```text
historical_traffic_read_service: Any | None = None
```

If absent:

```text
History endpoint → 503 source_unavailable
```

while Current Network Throughput, Home, Admin shell and Portal remain usable.

---

# 30. Admin runtime readiness invariant

Historical service absence MUST NOT make overall:

```text
AdminWebRuntime.state
```

unavailable.

This is a panel-level optional dependency.

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
validate product range ID
capture server evaluated_at
resolve from/to
use shared Admin execution controls
call HistoricalTrafficReadService.get_site_history(...)
serialize through dedicated safe serializer
return AdminQueryResponse
```

---

# 32. Shared execution/deadline controls

Use existing:

```text
AdminQueryExecutionControls
```

No:

```text
History semaphore
History thread
History executor
History deadline override
```

Pass the shared `QueryDeadline` into `HistoricalTrafficReadService`.

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
    range_id,
)
```

Serializer may validate/project only.

Forbidden in serializer:

```text
source reselection
bucket averaging
interpolation
coverage recomputation
period statistics
peak calculations
new throughput formulas
```

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

# 42. Serializer validation

At minimum validate:

```text
Site identity matches requested Site
range ID is 24h or 7d
UTC timestamps are valid
service range matches resolved application range
unit == Mbps
aggregation == mean_of_complete_site_rate_samples
metric_version == network_traffic_history.v1
source_kind == observation_ap_dynamic
sample_timestamp_semantics == cycle_finished_at
bucket_count == len(buckets)
bucket_count <= 720
bucket order is contiguous
first bucket starts at from_utc
last bucket ends at to_utc
bucket status = complete|partial|none
selected_source = wired|lan|null
numeric Mbps = finite non-negative or null
counts = non-negative integers
```

Browser is not trusted to enforce source safety.

---

# 43. Total ownership

Read foundation already provides `total_mbps`.

Admin serializer may verify internal consistency.

Browser MUST NOT calculate canonical:

```text
Total = Download + Upload
```

The History UI does not need a visible Total series in v1.

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

# 45. HTTP error mapping

```text
400 invalid_request
→ missing/unknown/duplicate range, unknown query, invalid Site/request contract

401 authentication_required
→ no Admin session

403 site_forbidden
→ forbidden Site/capability

404 not_found
→ Traffic master feature disabled

429 concurrency_limit
→ shared Admin capacity exhausted
→ Retry-After

503 query_deadline
→ hard deadline

503 source_unavailable
→ historical service/source unavailable

503 response_too_large
→ existing response-size guard

500 internal_error
→ sanitized unexpected failure
```

No traceback, SQL, DB path, Omada URL or secret in response.

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

DRAFT v1:

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

# 50. Axes and legend

X axis:

```text
time
```

based only on returned bucket boundaries and display formatting.

Y axis:

```text
Mbps
```

Visible legend:

```text
Download
Upload
```

Legend must remain understandable without relying only on color.

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

Global Traffic `Refresh` uses existing:

```text
refreshAll({manual:true})
```

History participates even with `autoRefresh=false`.

Range selector uses:

```text
refreshPanel("network-traffic-history", {manual:true})
```

Range change MUST NOT reload Current Network Throughput solely because the range changed.

---

# 58. Range controls

Visible controls:

```text
24h
7d
```

Recommended accessible implementation:

```text
button type=button
aria-pressed
```

No custom date picker in this task.

---

# 59. Stable DOM hooks

Recommended:

```text
traffic-history-panel
traffic-history-heading
traffic-history-state
traffic-history-state-title
traffic-history-state-message
traffic-history-range-24h
traffic-history-range-7d
traffic-history-chart
traffic-history-chart-svg
traffic-history-legend
traffic-history-coverage
traffic-history-watermark
traffic-history-gaps
traffic-history-source-transitions
traffic-history-timezone
```

Hooks used by JS are contracts.

---

# 60. Browser DTO validation

At minimum validate:

```text
result status = ok|partial|insufficient_data
range.id = 24h|7d
range.unit = Mbps
range.metric_version = network_traffic_history.v1
range.aggregation = mean_of_complete_site_rate_samples
range.bucket_count = 1..720
buckets array length == bucket_count
bucket status = complete|partial|none
selected_source = wired|lan|null
Mbps = finite non-negative or null
coverage.status = complete|partial|none
```

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

# 70. No new configuration by default

Expected no changes to:

```text
app/config.py
app/settings.py
.env.example
app/admin_web/config.py
```

Reuse existing:

```text
WEB_ADMIN_TRAFFIC_ENABLED
WEB_ADMIN_TRAFFIC_REQUEST_TIMEOUT_SECONDS
WEB_ADMIN_MAX_CONCURRENT_QUERIES
WEB_ADMIN_MAX_QUERY_DURATION_SECONDS
WEB_ADMIN_MAX_RESPONSE_BYTES
```

---

# 71. Feature-gating operational nuance

Architecture recommendation:

```text
NO new History sub-flag by default
```

But production master Traffic is already active. Therefore a production deploy containing `TRAFFIC-02` would expose History without changing environment.

This DRAFT grants no production deployment.

Before FINAL, Owner/Tech Lead must decide whether:

```text
A. separate production deploy/exposure authorization is sufficient

or

B. dormant deploy capability is required
→ explicitly approve a subordinate History flag
```

Do not add a flag silently.

---

# 72. Expected production files to change

Preferred:

```text
MODIFY
app/admin_web/runtime.py
app/admin_web/query_service.py
app/admin_web/routes.py
app/admin_web/static/admin.js
app/admin_web/static/admin.css
app/admin_web/templates/admin/traffic.html

ADD
app/admin_web/traffic_history_ranges.py
app/admin_web/historical_traffic_serialization.py
```

Preferred tests:

```text
ADD
tests/admin_web/test_traffic_history.py
tests/admin_web/test_traffic_history_frontend.py
```

---

# 73. Expected unchanged files

```text
app/analytics/**
app/observations/**
app/current_state/**
app/visit_lifecycle/**
app/visitor_registry/**
app/admin_web/config.py
app/admin_web/pages.py
app/admin_web/templates/admin/base.html
app/admin_web/current_traffic_serialization.py
app/config.py
app/settings.py
.env.example
run.py
requirements*
```

If implementation needs one of these:

```text
STOP
→ factual reason
→ Owner/Tech Lead architecture review
```

---

# 74. Why runtime.py changes

Current Admin composition injects Current Traffic and Home Activity services but not `analytics_runtime.historical_traffic_service`.

`TRAFFIC-02` needs only an optional dependency bridge.

No new Analytics runtime construction.

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

# 79. Required focused backend/API tests

`tests/admin_web/test_traffic_history.py` minimum:

## Range resolver

```text
24h exact fixed evaluation
7d exact fixed evaluation
rolling UTC duration
[from,to)
unknown range rejected
30d rejected in v1
```

## API/security

```text
valid session/Site + enabled + range=24h → 200
range=7d → 200
missing range → 400
duplicate range → 400
unknown query → 400
invalid Site → 400
forbidden Site → 403
no session → 401
Traffic disabled → 404
```

---

# 80. Required focused application/read tests

With deterministic fake `HistoricalTrafficReadService` prove:

```text
exact resolved site/from/to/evaluated_at passed
bucket_seconds not caller/browser selected
shared deadline passed
service absent → 503 source_unavailable
HistoricalTrafficValidationError → 400
HistoricalTrafficSourceUnavailable → 503
query deadline → 503 query_deadline
busy → 429 + Retry-After
```

---

# 81. Required focused serializer tests

At minimum:

```text
24h/288 safe serialization
7d/672 safe serialization
complete result
partial result
insufficient_data result
valid 0.0 preserved
none/null preserved
partial numeric preserved as partial
gap metadata preserved
wired/lan preserved
source transition preserved
coverage/watermark/source-age preserved
quality counts preserved
bucket ordering/contiguity validation
bucket count mismatch rejected
>720 rejected
invalid unit/aggregation/source/metric rejected
non-finite/negative numbers rejected
malformed timestamps rejected
```

---

# 82. Required focused frontend tests

`tests/admin_web/test_traffic_history_frontend.py` minimum:

```text
History registers only on Traffic page with required hooks
key = network-traffic-history
autoRefresh=false
registration causes exactly one initial load
initial URL ends /traffic/history?range=24h
7d selector calls refreshPanel(history, manual=true)
range selector does not call global fetch directly
range selector does not call panel load directly
range selector does not refresh Current panel
global Refresh still includes History
no History setInterval
no History private polling timer
no History visibility/pagehide owner
no History AbortController owner
no duplicate global Refresh listener
```

---

# 83. Required frontend semantic tests

```text
complete buckets render Download/Upload
real 0.0 plots zero
null bucket creates gap, not zero
partial numeric bucket remains visible + partial indication
insufficient_data shows no-data state
source unavailable remains panel-local
old chart not relabelled during range transition
successful transition commits applied range
failed transition does not pretend old chart is new range
browser does not compute canonical from/to
browser does not calculate totals/averages/source selection/coverage
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

# 91. API performance acceptance

Because `TRAFFIC-02` adds application resolution + serializer + JSON response, Central Lab should measure end-to-end:

```text
24h History API
7d History API
```

Record:

```text
HTTP status
bucket count
wall-clock duration
serialized response bytes
deadline result
```

No stricter hard SLA is introduced by this DRAFT.

If API path causes 10s backend deadline, 20s browser timeout or response-size overflow:

```text
STOP
→ measured evidence
→ architecture review
```

No silent cache/rollup/deadline change.

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

Controlled authenticated acceptance:

```text
Traffic page opens
Current Network Throughput still visible
Network Traffic History appears
24h selected by default
one initial History request
Download/Upload chart visible
legend visible
y-axis unit Mbps
display timezone visible
24h→7d reloads only History
7d→24h reloads only History
global Refresh reloads Current + History through coordinator
no duplicate request loop
no console exception
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

# 97. No production config change

Implementation MUST NOT modify:

```text
/etc/default/captive-portal
WEB_ADMIN_TRAFFIC_ENABLED
Admin credentials
Observation settings
Analytics settings
systemd
Nginx
```

No production deploy is implied.

---

# 98. Merge/deploy/exposure separation

```text
DRAFT
→ Owner + Tech Lead review
→ FINAL
→ explicit Owner implementation authorization
→ Coder implementation
→ Coder focused tests
→ Central Lab acceptance
→ Owner merge authorization
→ merge
→ separate production deployment/exposure authorization
```

This DRAFT grants none of these execution actions.

---

# 99. Production exposure nuance / rollback

Because production master Traffic is already active, production deploy of this panel would make History visible without a new environment change.

If no History subflag is added, History-specific rollback should preferably be code rollback. Turning off `WEB_ADMIN_TRAFFIC_ENABLED` would also remove accepted `TRAFFIC-01` Current Network Throughput.

This is the principal operational tradeoff of retaining a single master Traffic flag.

---

# 100. Architecture decisions

```text
Canonical source:
HistoricalTrafficReadService

New acquisition:
NO

New DB/schema:
NO

Native Omada product source:
NO

Initial ranges:
24h / 7d

Default range:
24h

Canonical range math:
server UTC

Browser range math:
NO

Display timezone:
browser-local, explicitly labelled

Endpoint:
GET /admin/api/v1/sites/<site_id>/traffic/history?range=...

History autoRefresh:
false

Initial load:
yes, via existing coordinator

Range reload:
refreshPanel()

Global reload:
refreshAll()

Chart:
Download + Upload line chart

Visible Total series/KPI:
NO

Missing bucket:
gap, not zero

Partial numeric:
allowed, visibly partial

New feature flag:
NO by default

Rollup/cache:
NO
```

---

# 101. Exact scope

```text
Admin optional service injection
24h/7d server-side range resolver
safe History serializer
Site-scoped History endpoint
History panel markup
Download/Upload chart
24h/7d selector
coverage/quality presentation
watermark/source-age presentation
gap-safe rendering
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

required:
range=24h|7d

200:
ok | partial | insufficient_data

400:
invalid_request

401:
authentication_required

403:
site_forbidden

404:
not_found when Traffic disabled

429:
concurrency_limit

503:
query_deadline | source_unavailable | response_too_large
```

No caller-supplied from/to/bucket/source.

---

# 104. UI states summary

```text
loading
refreshing previous accepted result
ready / complete
partial
no historical data / insufficient_data
panel-local unavailable/timeout/error
global auth/Site state via existing coordinator
```

Permanent:

```text
null != zero
partial != complete
old applied range != newly requested range
```

---

# 105. Unresolved question 1 — dormant production deploy

Architect recommendation:

```text
NO new History subflag
```

Owner/Tech Lead must confirm before FINAL:

```text
A. deploy = History exposure is acceptable under separate Owner production authorization

or

B. dormant deploy is required
→ explicitly approve subordinate History flag
→ revise scope before FINAL
```

---

# 106. Unresolved question 2 — interactive SLA

Accepted source p95 is approximately 4.6–5.3s for 24h/7d.

Architect recommendation:

```text
accept existing v1 performance
reuse 10s backend deadline
reuse 20s Traffic browser timeout
```

If Owner/Tech Lead requires materially faster interaction (for example <2s), that is a separate architecture requirement and MUST NOT be solved silently with cache/rollup/new DB/timeout changes.

---

# 107. Repository files expected to change

```text
MODIFY
app/admin_web/runtime.py
app/admin_web/query_service.py
app/admin_web/routes.py
app/admin_web/static/admin.js
app/admin_web/static/admin.css
app/admin_web/templates/admin/traffic.html

ADD
app/admin_web/traffic_history_ranges.py
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
app/admin_web/config.py
app/admin_web/pages.py
app/admin_web/templates/admin/base.html
app/config.py
app/settings.py
.env.example
run.py
requirements*
```

---

# 108. Focused test scope

Coder focused:

```text
range resolver
query-service bridge
API validation/security
serializer
24h/7d
complete/partial/none
gap != zero
valid zero
frontend DTO validation
range controls
refreshPanel integration
no direct fetch
no duplicate scheduler
no browser range math
no browser canonical Traffic calculation
```

Coder does not run broader/cross-module/full gate.

---

# 109. Central Lab regression scope

Central Lab:

```text
TRAFFIC-02 focused candidate
TRAFFIC-02-READ regression
TRAFFIC-00 Foundation/coordinator regression
TRAFFIC-01 Current Network Throughput regression
shared Admin runtime/query/routes/frontend regression
Home Current Traffic shared-boundary regression
24h/7d API performance/payload check
full current Central Lab gate
exact-artifact immutability
```

---

# 110. Risks

## R1 — History query latency

Mitigation:

```text
autoRefresh=false
explicit loading state
retain previous accepted chart during refresh
20s browser timeout
10s hard backend deadline
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
partial is distinguishable
```

## R4 — client clock/range drift

Mitigation:

```text
browser sends only range ID
server resolves evaluated_at/from/to
```

## R5 — TRAFFIC-03 semantic leakage

Mitigation:

```text
no Average/Peak KPI
History bucket mean != Period Average
```

## R6 — production deploy exposes panel immediately

Mitigation:

```text
separate Owner production exposure authorization
or explicit subflag decision before FINAL
```

---

# 111. Stop conditions

Implementation MUST STOP and return evidence if it requires:

```text
changing HistoricalTrafficReadService semantics
changing AnalyticsSourceGateway historical algorithm
changing MAX_SITE_HISTORY_BUCKETS
changing source-family selection
gap/partial semantics changes
Observation acquisition/schema changes
new Omada traffic call
raw Observation DB access from Admin
cache/rollup/Traffic DB
new chart dependency/CDN
Traffic coordinator public-contract change
Home Traffic semantic change
30d selector
Period Average/Peak
```

Also STOP if current `origin/main` materially changes before work starts.

---

# 112. Owner + Tech Lead review checklist

Before FINAL, confirm:

1. `HistoricalTrafficReadService` remains sole historical semantic owner.
2. Endpoint `/traffic/history` is accepted.
3. Range enum `24h|7d` is accepted.
4. Endpoint requires explicit `range`.
5. Rolling server-UTC range resolution is accepted.
6. Browser-local display timezone with visible label is accepted.
7. `autoRefresh=false` is accepted.
8. Global Refresh + range-specific `refreshPanel()` behavior is accepted.
9. Download/Upload line chart is accepted.
10. No visible Total History series/KPI is accepted.
11. Null buckets break lines.
12. Partial numeric buckets remain visible but explicitly partial.
13. No invented historical Fresh/Stale label is accepted.
14. Compact safe serializer projection is accepted.
15. No new feature flag is accepted OR dormant-deploy requirement is chosen.
16. Existing 10s/20s performance budgets are accepted OR stricter SLA is requested.
17. Proposed file scope is accepted.
18. Coder/Central Lab testing ownership is accepted.
19. Production deployment/exposure remains separate.

---

# 113. Final DRAFT status

```text
TASK:
TRAFFIC-02 — Historical Network Traffic / History

STATUS:
DRAFT — FOR OWNER + TECH LEAD REVIEW

BOUND TO:
main@6b4adf770ab1afa289dac14680ba876711088d94

tree:
04f5e2d23da8b2d44390c285fc14dbb62fa06221

DEPENDENCIES:
TRAFFIC-00 DONE
TRAFFIC-01 DONE
TRAFFIC-02-READ DONE / ACCEPTED / MERGED

CANONICAL READ OWNER:
HistoricalTrafficReadService

INITIAL UI RANGES:
24h / 7d

NEW ACQUISITION:
NO

NEW DB / SCHEMA:
NO

IMPLEMENTATION AUTHORIZATION:
NOT GRANTED

PRODUCTION DEPLOYMENT / EXPOSURE:
NOT GRANTED
```

Next:

```text
Owner + Tech Lead review
→ targeted corrections
→ TASK-TRAFFIC-02 FINAL
→ separate Owner implementation authorization
```

Implementation MUST NOT begin from this DRAFT.
