# TASK-HOME-TRAFFIC-01 — Admin Console Home Current Traffic — FINAL

**Project:** CaptivPortal  
**Parent:** `TASK-HOME-TRAFFIC-MASTER — FINAL R2`  
**Dependency:** `TASK-HOME-TRAFFIC-READ-01 — MERGED / ACCEPTED`  
**Type:** coder-ready Admin API / Home UI implementation specification  
**Status:** `FINAL`  
**Implementation authorization:** `NOT GRANTED — requires separate Owner authorization`  
**Branch authorization:** `NOT GRANTED`  
**Code / commit / push / PR / merge authorization:** `NOT GRANTED`  
**Deployment authorization:** `NOT GRANTED`  
**Production activation authorization:** `NOT GRANTED`  
**Exact implementation baseline:** `origin/main@f8fc9d1602f36777f5e1b5a2bfc532fa9076a2e0`  
**PR A:** `#60 — TASK-HOME-TRAFFIC-READ-01 — Current Traffic Read Foundation`  
**PR A merge SHA:** `f8fc9d1602f36777f5e1b5a2bfc532fa9076a2e0`  
**PR A first parent:** `dafbc40b6f5c5b3dde6b52fcc2c7689e95d05081`  
**PR A second parent:** `453d1008d2160f8015e182ae7c0927eae6add9f4`  
**Prepared / rebound:** `2026-08-24`  

---

## 1. Post-merge rebind verification

The master contract required Task B to be issued only after the accepted PR A had an exact merged baseline. That condition is now satisfied.

Verified repository state:

```text
origin/main =
f8fc9d1602f36777f5e1b5a2bfc532fa9076a2e0

PR:
#60

merge commit:
f8fc9d1602f36777f5e1b5a2bfc532fa9076a2e0

first parent:
dafbc40b6f5c5b3dde6b52fcc2c7689e95d05081

second parent / PR head:
453d1008d2160f8015e182ae7c0927eae6add9f4
```

PR A changed only:

```text
app/analytics/__init__.py
app/analytics/current_traffic.py
app/analytics/models.py
app/analytics/runtime.py
app/analytics/source_gateway.py
tests/analytics/test_current_traffic.py
tests/analytics/test_current_traffic_runtime.py
```

Therefore PR A did not alter Admin/Home code or any Omada/Observation acquisition path.

Accepted PR A evidence confirms:

```text
Current Traffic read foundation implemented
read-only Observation boundary preserved
no Omada path introduced
runtime isolation/fail-open preserved
Windows full gate PASS
Linux/POSIX delta PASS
```

### 1.1. Conformance to `TASK-HOME-TRAFFIC-READ-01-FINAL-R2`

The merged implementation materially conforms to the accepted READ-01 R2 architecture:

```text
one complete-success ap_dynamic cycle
read-only/query-only Analytics gateway
wired primary / lan fallback
no source mixing
strict rate/reason/timestamp integrity
Site-scoped immutable DTOs
cursor bound to cycle + derived source
retained pinned cycle support
runtime isolation
```

### 1.2. Narrow factual rebind delta

One implementation-level signature delta is incorporated by this FINAL.

The locked R2 text omitted `max_ap_skew_seconds` from the AP-page source call, while the accepted merged implementation requires it.

Authoritative merged AP-page signature:

```python
list_current_ap_traffic(
    site_id,
    *,
    cycle_id,
    evaluated_at_utc=None,
    fresh_max_age_seconds,
    stale_max_age_seconds,
    max_ap_skew_seconds,
    limit=100,
    cursor=None,
    deadline=None,
)
```

This is not a product architecture change. Task B simply binds to the real accepted PR A API.

### 1.3. Rebind verdict

```text
POST-MERGE REBIND: PASS
Material architecture conflict: NO
Product choices reopened: NO
Required Task B adjustment: pass max_ap_skew_seconds to AP-page read and explicitly serialize actual PR A models.
```

Execution remains blocked until separate Owner authorization.

---

## 2. Goal

Add Home Traffic UI/API on top of the accepted `CurrentTrafficReadService`.

```text
CurrentTrafficReadService
→ AdminQueryService
→ /admin/api/v1
→ Home Live Traffic section
```

No collection and no Omada.

### 2.1. Product meaning

Home Traffic v1 displays:

```text
Download Now
Upload Now
Total Traffic Now
Traffic freshness
Traffic coverage
Traffic by AP
```

Unit: `Mbps`.

The metric is persisted AP physical/network traffic evidence. It is not automatically Internet-only, WAN-only, guest-only, `Zefer_Parki`-only, RF-channel load or configured-uplink utilization.

Forbidden v1 labels:

```text
Internet Load
WAN Load
Channel Load
Guest Internet Traffic
Zefer_Parki Traffic
```

Required helper meaning:

```text
Derived from persisted AP traffic counters.
May include local/service traffic and is not an Internet-only measurement.
```

### 2.2. Permanent boundary

```text
existing Observation acquisition
→ observations.sqlite3
→ CurrentTrafficReadService
→ AdminQueryService
→ authenticated Site-scoped Admin API
→ Home Traffic UI
```

Forbidden:

```text
Browser/Admin → Omada
Home request → new Observation cycle
Home request → increased Omada polling
Home → Loki/Grafana/raw logs
Current State client counters → Mbps reinterpretation
```

No cross-Site aggregate/cursor and no tenant model are introduced.

---

## 3. Feature flag

```text
WEB_ADMIN_HOME_TRAFFIC_ENABLED=false
```

Invariant:

```text
HOME_TRAFFIC=true
requires WEB_ADMIN_ENABLED=true
AND WEB_ADMIN_HOME_LIVE_ENABLED=true
```

Merge/deploy != activation.

---

## 4. Configuration

Repository-safe defaults:

```text
WEB_ADMIN_HOME_TRAFFIC_ENABLED=false
WEB_ADMIN_HOME_TRAFFIC_REFRESH_SECONDS=60
WEB_ADMIN_HOME_TRAFFIC_REQUEST_TIMEOUT_SECONDS=20
WEB_ADMIN_HOME_TRAFFIC_PAGE_SIZE=100
WEB_ADMIN_HOME_TRAFFIC_FRESH_MAX_AGE_SECONDS=90
WEB_ADMIN_HOME_TRAFFIC_STALE_MAX_AGE_SECONDS=180
WEB_ADMIN_HOME_TRAFFIC_MAX_AP_SKEW_SECONDS=60
```

Bounds:

```text
refresh 60..300
request timeout 5..60
page size 1..250
fresh max 30..300
stale max >= fresh and <=600
max AP skew 10..180
```

Cross-field:

```text
Traffic request timeout > WEB_ADMIN_MAX_QUERY_DURATION_SECONDS
```

---

## 5. Optional runtime dependency

`CurrentTrafficReadService` is optional to Admin runtime readiness.

```text
Traffic service unavailable
≠ Admin unavailable
≠ Home Live unavailable
```

Feature true + source absent:

```text
Traffic endpoint 503
other Home Live continues
```

Preferred dependency:

```text
analytics_runtime.current_traffic_service
→ AdminQueryService
```

Task B relies on Task A's runtime-isolation invariant:

```text
current_traffic_service is optional/fail-open
quality_service readiness unchanged
wireless_service readiness unchanged
visit_service readiness unchanged
Traffic absence cannot make existing Analytics/Admin/Home Live unavailable
```

---

## 5A. Canonical source enum and ownership

Machine values are exact and case-sensitive:

```text
primary_source:  "wired"
selected_source: "wired" | "lan" | null
```

`LAN` is permitted only as human-readable prose/UI copy.

Neither browser nor `AdminQueryService` selects a source family.

AP detail calls use:

```python
list_current_ap_traffic(
    site_id,
    *,
    cycle_id,
    evaluated_at_utc=...,
    fresh_max_age_seconds=...,
    stale_max_age_seconds=...,
    max_ap_skew_seconds=...,
    limit=...,
    cursor=...,
    deadline=...,
)
```

The read service loads the pinned cycle and derives `"wired"` or `"lan"` internally.

There is no HTTP query parameter, Admin DTO field, or service argument that can impose source selection.

---

## 5B. Exact accepted PR A read contract

Task B MUST bind to the actual merged service.

Summary:

```python
get_current_site_traffic(
    site_id,
    *,
    evaluated_at_utc=None,
    fresh_max_age_seconds,
    stale_max_age_seconds,
    max_ap_skew_seconds,
    deadline=None,
)
```

AP page:

```python
list_current_ap_traffic(
    site_id,
    *,
    cycle_id,
    evaluated_at_utc=None,
    fresh_max_age_seconds,
    stale_max_age_seconds,
    max_ap_skew_seconds,
    limit=100,
    cursor=None,
    deadline=None,
)
```

Admin policy mapping:

```text
fresh_max_age_seconds
← WEB_ADMIN_HOME_TRAFFIC_FRESH_MAX_AGE_SECONDS

stale_max_age_seconds
← WEB_ADMIN_HOME_TRAFFIC_STALE_MAX_AGE_SECONDS

max_ap_skew_seconds
← WEB_ADMIN_HOME_TRAFFIC_MAX_AP_SKEW_SECONDS
```

Caller never passes `selected_source`.

### 5B.1. Accepted immutable result graph

```text
CurrentSiteTraffic
  snapshot
  freshness_policy
  source_selection
  coverage
  freshness
  traffic

CurrentApTrafficPage
  snapshot
  freshness_policy
  source_selection
  items
  page
```

Important accepted source fields:

```text
CurrentTrafficSnapshot:
  source_kind, site_id, cycle_id, started_at, finished_at, complete,
  evaluated_at, observed_at, newest_observed_at, age_seconds,
  source_skew_seconds, freshness_status, freshness_reason,
  primary_source, selected_source, selection_reason, empty_population,
  latest_attempt_state, latest_attempt_result, latest_attempt_at,
  using_previous_complete_snapshot

CurrentTrafficFreshnessPolicy:
  fresh_max_age_seconds, stale_max_age_seconds, max_ap_skew_seconds

CurrentTrafficSourceSelection:
  primary_source, selected_source, selection_reason,
  wired_pair_valid_ap_count, lan_pair_valid_ap_count,
  source_mixing_allowed

CurrentTrafficCoverage:
  status, reasons, empty_population, total_ap_count,
  valid_rate_ap_count, valid_download_ap_count, valid_upload_ap_count,
  missing_rate_ap_count, stale_ap_count, unavailable_ap_count,
  reset_ap_count, gap_rejected_ap_count, no_baseline_ap_count,
  source_unavailable_ap_count, invalid_elapsed_ap_count,
  observed_at, newest_observed_at, source_skew_seconds

CurrentTrafficTotals:
  download_mbps, upload_mbps, total_mbps

CurrentApTrafficItem:
  ap_mac, name, download_mbps, upload_mbps, total_mbps,
  download_reason, upload_reason, rate_status,
  observed_at, age_seconds, selected_source

CurrentTrafficPageMetadata:
  limit, next_cursor, cycle_id, selected_source
```

### 5B.2. Explicit Admin serializer mapping

Use explicit allowlist serializers; never generic `asdict()` as the public contract.

```text
freshness_policy.fresh_max_age_seconds
← policy.fresh_max_age_seconds

freshness_policy.unavailable_after_seconds
← policy.stale_max_age_seconds

summary freshness_policy.max_ap_skew_seconds
← policy.max_ap_skew_seconds

coverage.coverage_status
← coverage.status

coverage.coverage_reasons
← coverage.reasons

traffic.*
← CurrentTrafficTotals

AP item fields
← explicit CurrentApTrafficItem fields

page.*
← CurrentTrafficPageMetadata
```

Before serialization validate:

```text
snapshot.site_id == authorized/requested Site
snapshot.source_kind == "observation_ap_dynamic"
page cycle/source == accepted summary cycle/source
selected_source is "wired" or "lan" for a real cycle
```

Extra internal source-model fields do not automatically become public API fields.

---

## 6. Capabilities

```text
summary → admin.read.overview
AP page → admin.read.observations
```

Do not weaken.

---

## 7. Routes

```text
GET /admin/api/v1/sites/{site_id}/current-traffic/summary
GET /admin/api/v1/sites/{site_id}/current-traffic/aps
```

Use existing `admin.read.v1` envelope.

---

## 8. Route gate order

```text
HTTPS/network/query-size
→ session
→ Site syntax/allowlist
→ capability
→ Traffic feature flag
→ disabled 404
→ endpoint query validation
→ service
```

Add a narrow Traffic-path duplicate-query handling exception analogous to Current State so pre-auth/query parsing does not leak endpoint schema before intended gates.

---

## 8A. AdminQueryService / deadline / concurrency contract

Both Traffic routes use existing Admin authentication, Site authorization, non-blocking query concurrency and response-size protection.

```text
WEB_ADMIN_MAX_CONCURRENT_QUERIES
```

No slot → `429` with `Retry-After` under the existing Admin convention.

The accepted Traffic read service is deadline-aware. Task B MUST pass the existing Admin `QueryDeadline` into both source calls. Do not replace it with the Home Live Current State pre/post-only deadline model.

Conceptual AdminQueryService methods:

```python
current_traffic_summary(principal, site_id)

list_current_ap_traffic(
    principal,
    site_id,
    *,
    cycle_id,
    limit=None,
    cursor=None,
)
```

Error mapping:

```text
CurrentTrafficValidationError for caller cycle/cursor context
→ 400 invalid_request

CurrentTrafficSourceUnavailable
→ 503 source_unavailable

AnalyticsQueryDeadlineExceeded
→ 503 query_deadline

Admin concurrency unavailable
→ 429

response-size overflow
→ 503 response_too_large

unexpected programmer exception
→ sanitized 500 internal_error
```

No raw source exception, SQL or DB path is returned/logged.

Feature true + `analytics_runtime.current_traffic_service is None` affects Traffic only; Admin and Home Live remain available.

---

## 9. Summary query

No query parameters.

Response `result` exact shape:

```json
{
  "snapshot": {
    "source_kind": "observation_ap_dynamic",
    "cycle_id": "<id-or-null>",
    "complete": true,
    "evaluated_at": "2026-08-24T13:00:00.000Z",
    "observed_at": "2026-08-24T12:59:42.000Z",
    "newest_observed_at": "2026-08-24T12:59:55.000Z",
    "age_seconds": 18.0,
    "source_skew_seconds": 13.0,
    "freshness_status": "fresh",
    "freshness_reason": "within_freshness_window",
    "latest_attempt_state": "completed",
    "latest_attempt_result": "success",
    "latest_attempt_at": "2026-08-24T12:59:57.000Z",
    "using_previous_complete_snapshot": false
  },
  "freshness_policy": {
    "fresh_max_age_seconds": 90,
    "unavailable_after_seconds": 180,
    "max_ap_skew_seconds": 60
  },
  "traffic": {
    "download_mbps": 42.125,
    "upload_mbps": 6.25,
    "total_mbps": 48.375,
    "unit": "Mbps"
  },
  "source_selection": {
    "primary_source": "wired",
    "selected_source": "wired",
    "selection_reason": "primary_full_coverage",
    "wired_pair_valid_ap_count": 2,
    "lan_pair_valid_ap_count": 2,
    "source_mixing_allowed": false
  },
  "coverage": {
    "coverage_status": "complete",
    "empty_population": false,
    "total_ap_count": 2,
    "valid_rate_ap_count": 2,
    "valid_download_ap_count": 2,
    "valid_upload_ap_count": 2,
    "missing_rate_ap_count": 0,
    "stale_ap_count": 0,
    "unavailable_ap_count": 0,
    "reset_ap_count": 0,
    "gap_rejected_ap_count": 0,
    "no_baseline_ap_count": 0,
    "source_unavailable_ap_count": 0,
    "invalid_elapsed_ap_count": 0,
    "coverage_reasons": []
  }
}
```

No raw counters.

---

## 10. Summary no-cycle shape

HTTP 200:

```text
cycle_id=null
complete=false
selected_source=null
selection_reason=no_complete_snapshot
freshness=unavailable
freshness_reason=no_complete_snapshot
coverage=none
traffic values=null
empty_population=false
```

Latest-attempt fields may still describe a failed/running attempt if available.

---

## 11. Empty-cycle shape

HTTP 200:

```text
real cycle_id
complete=true
selected_source=wired
selection_reason=empty_population
coverage=complete
empty_population=true
download=0.0
upload=0.0
total=0.0
freshness from cycle.finished_at
```

---

## 12. AP endpoint query contract and source ownership

Allowed HTTP query parameters:

```text
cycle_id
limit
cursor
```

Explicitly forbidden:

```text
selected_source
source
traffic_source
```

Rules:

```text
cycle_id required for AP page
cursor without cycle_id → 400

first page:
cycle_id=<summary cycle>
cursor omitted

next page:
cycle_id=<same cycle>
cursor=<previous next_cursor>

limit default 100
limit max 250
```

The browser passes only pinned cycle/pagination context. Admin adds server-owned policy values:

```text
fresh_max_age_seconds
stale_max_age_seconds
max_ap_skew_seconds
deadline
```

Admin does not pass a source family.

Inside one read-only snapshot transaction the read service:

```text
loads the pinned cycle
validates Site + full integrity contract
deterministically re-derives selected_source
loads the AP page
binds cursor to derived source
on next page re-derives source and verifies cursor source equality
```

This works for the current cycle and for a retained older valid complete-success cycle.

The browser and `AdminQueryService` cannot impose `"wired"` or `"lan"`.

---

## 13. Full AP page wire contract

Admin envelope:

```json
{
  "api_version": "admin.read.v1",
  "site_id": "<site>",
  "result": {
    "snapshot": {
      "source_kind": "observation_ap_dynamic",
      "cycle_id": "<same-summary-cycle>",
      "evaluated_at": "2026-08-24T13:00:00.000Z",
      "observed_at": "2026-08-24T12:59:42.000Z",
      "newest_observed_at": "2026-08-24T12:59:55.000Z",
      "age_seconds": 18.0,
      "freshness_status": "fresh",
      "freshness_reason": "within_freshness_window"
    },
    "freshness_policy": {
      "fresh_max_age_seconds": 90,
      "unavailable_after_seconds": 180
    },
    "source_selection": {
      "selected_source": "wired",
      "selection_reason": "primary_full_coverage",
      "source_mixing_allowed": false
    },
    "items": [
      {
        "ap_mac": "AA:BB:CC:DD:EE:FF",
        "name": "AP-1",
        "download_mbps": 20.0,
        "upload_mbps": 3.0,
        "total_mbps": 23.0,
        "download_reason": "ok",
        "upload_reason": "ok",
        "rate_status": "valid",
        "observed_at": "2026-08-24T12:59:42.000Z",
        "age_seconds": 18.0,
        "selected_source": "wired"
      }
    ]
  },
  "page": {
    "limit": 100,
    "next_cursor": null,
    "cycle_id": "<same-summary-cycle>",
    "selected_source": "wired"
  }
}
```

No IP, firmware, counters, CPU/RAM or raw controller data.

Machine source validation for DTO/page/cursor state is exactly:

```text
"wired" | "lan"
```

Uppercase `"LAN"` is invalid as a machine value.

---

## 14. AP page pinned-cycle behavior

```text
retained valid old complete-success cycle explicitly pinned → allowed
expired/deleted cycle → 400
cycle Site mismatch → 400
cursor cycle/source mismatch → 400
noncanonical cursor → 400
```

---

## 15. Summary unavailable behavior

If summary freshness is unavailable:

```text
Traffic numeric cards show —
AP Traffic request is not sent
AP Traffic rows cleared/hidden
Load More hidden
pagination disabled
```

Local age progression to unavailable performs the same clearing/hiding without waiting for server response.

Next accepted available summary reloads AP first page.

---

## 16. Partial UI behavior

When coverage partial:

```text
numeric direction subtotals are shown only where non-null
all shown partial numeric values labeled Observed subtotal
```

Coverage block MUST show:

```text
Download X/Y APs
Upload   X/Y APs
Both     X/Y APs
```

If one direction is null, that card shows `—`, not zero.

Total is `—` unless both direction subtotals are non-null.

---

## 17. Exact zero UI

```text
0.0 + reason=ok
```

renders as a numeric zero such as:

```text
0.00 Mbps
```

Never use JS truthiness fallback for rate values.

---

## 18. Permission-specific 403 behavior

```text
Traffic summary 403
→ global Site-forbidden state / stop Site Home polling

Traffic AP page 403 after accepted summary
→ keep summary cards
→ stop AP table only
→ show AP detail access denied
```

---

## 19. Top-level Home coordinator

One coordinator owns all Home refresh scheduling.

Phases:

```text
A: Current State Client + AP in parallel (max 2)
B: after both settle, Traffic Summary
C: after accepted non-unavailable summary, Traffic AP first page
```

The shared Refresh button is enabled/disabled only by the coordinator, not independently by Client/AP/Traffic subcontrollers.

Per-request timeouts bound each phase, so Traffic cannot wait indefinitely.

Load More cannot overlap a new refresh.

---

## 20. Source-state isolation

Scheduling is shared; rendering/error state is not.

Traffic error cannot clear:

```text
Online
Authorized/Pending
Devices by AP
Online Devices
Access Points Now
```

Current State error cannot clear still-valid Traffic.

---

## 21. Cross-tab 429 policy

No cross-tab leader election.

429 is retryable and non-destructive.

After 429:

```text
respect Retry-After
minimum retry eligibility 60s
bounded backoff
add per-tab random jitter 0..10s after 429 to desynchronize tabs
```

No immediate retry.

Two-tab production acceptance:

```text
2 tabs
5 automatic cycles each
1 manual refresh in one tab
429 total <=12
no source >3 consecutive eligible 429s in one tab
both tabs recover without reload
```

---

## 22. AbortController ownership

Each subrequest stores:

```text
generation
controller identity
```

Release in finally only if both still match the stored owner.

Old finally cannot clear a newer request.

Pinned-400 clean refresh:

```text
exactly one
new generation
starts only after old lifecycle completed
no overlap
```

---

## 23. Retry policy

Retryable:

```text
network
Abort timeout
429
503
sanitized 500
```

Per Traffic group backoff:

```text
1st failure 60s
2nd 120s
3rd+ 300s max
```

Actual delay:

```text
max(refresh interval, backoff, Retry-After where present)
+ 0..10s jitter after 429 only
```

Success resets Traffic failure count.

Hidden-tab abort is neutral and does not increment failure count.

---

## 24. Visibility behavior

When hidden:

```text
automatic Home refresh stops
outstanding Home requests may be neutrally aborted by coordinator
```

When visible:

```text
one coordinated phased refresh if due
```

No request storm.

---

## 25. Strict enum allowlists

### freshness_status

```text
fresh
stale
unavailable
```

### freshness_reason

```text
within_freshness_window
within_stale_window
age_exceeded
clock_anomaly
no_complete_snapshot
source_unavailable
```

### coverage_status

```text
complete
partial
none
```

### coverage_reasons

```text
missing_direction
missing_pair
temporal_skew
no_valid_rate
empty_population
```

### selection_reason

```text
no_complete_snapshot
empty_population
primary_full_coverage
fallback_full_coverage
fallback_higher_coverage
primary_preferred_tie_or_higher
```

### rate reasons

```text
ok
no_baseline
counter_reset
gap_too_large
invalid_elapsed
source_unavailable
```

### rate_status

```text
valid
partial
unavailable
```

### latest attempt state

```text
none
running
completed
abandoned
```

### latest attempt result

```text
null
success
partial
failed
shutdown
```

Unknown value → malformed response, no partial DOM update.

---

## 26. Frontend mutual invariants

Validate before DOM mutation:

```text
api_version == admin.read.v1
site_id == current Site
source_kind == observation_ap_dynamic

cycle_id=null ↔ complete=false/no complete snapshot
complete=true ↔ cycle_id non-null

coverage=none → traffic values null
freshness=unavailable → traffic values null

empty_population=true
→ cycle_id non-null
→ selected_source=wired
→ selection_reason=empty_population
→ coverage=complete
→ all traffic values exactly numeric 0.0

selected_source=null
allowed only for no_complete_snapshot state

observed_at <= newest_observed_at <= evaluated_at
age_seconds finite non-negative where timestamps exist

page.cycle_id == accepted summary cycle
page.selected_source == accepted summary source
item.selected_source == page source
```

All UTC timestamps must match canonical project UTC format before use.

Boolean is rejected where numeric expected.

---

## 27. Arithmetic validation

When all three totals numeric:

```text
abs(total - (download + upload)) <= 1e-6
```

Counts:

```text
0 <= valid_rate <= total AP
0 <= valid_download <= total AP
0 <= valid_upload <= total AP
missing_rate = total AP - valid_rate
```

Malformed 200 does not partially render.

---

## 28. Browser freshness progression

Use monotonic browser elapsed time from accepted server age:

```text
performance.now()
```

Local progression:

```text
fresh → stale → unavailable
```

At unavailable:

```text
clear/hide all Traffic/AP numeric data and pagination
```

A network outage cannot leave Fresh forever.

---

## 28A. Independent Traffic watermark

Traffic observation time is independent from Client Current State, AP Current State and browser refresh time. Do not create one fake combined source timestamp.

Browser age progression uses accepted Traffic age plus monotonic `performance.now()` elapsed time only.

---

## 29. UI placement

Recommended:

```text
Home Live top cards
Traffic Now cards
Traffic freshness + coverage
Traffic by AP
existing Devices by AP
Online Devices
Access Points Now
```

Keep Flask/Jinja/plain CSS/vanilla JS.

No external frontend framework/CDN.

---

## 29A. UI wording and browser-state privacy

Cards:

```text
Download Now
Upload Now
Total Traffic Now
```

Helper meaning must make the AP-counter/non-Internet-only scope clear.

Do not store Traffic state in:

```text
localStorage
sessionStorage
IndexedDB
Cache API
service-worker cache
```

Do not persist cycle IDs, cursors, AP rows/MAC lists, traffic totals or selected source. All Admin responses remain `Cache-Control: no-store`.

Dynamic source text uses safe text APIs such as `textContent`.

---

## 30. Telemetry

Event:

```text
admin.current_traffic_query_completed
```

Allowed:

```text
request_id
route_name
site_id after authorization
status_code
outcome
allowlisted reason
duration_ms
coverage_status
freshness_status
item_count
```

Forbidden:

```text
AP MAC
client MAC/IP
SSID
cursor
cycle_id
raw URL/query
raw exception
DB path
credentials
Omada payload
```

---

## 30A. Implementation scope / baseline / PLAN

Expected Task B files:

```text
app/admin_web/config.py
app/admin_web/runtime.py
app/admin_web/query_service.py
app/admin_web/routes.py
app/admin_web/pages.py
app/admin_web/templates/admin/home.html
app/admin_web/static/admin.js
app/admin_web/static/admin.css
app/config.py
app/settings.py
.env.example
tests/admin_web/**
```

Preferred explicit serializer if useful:

```text
app/admin_web/current_traffic_serialization.py
```

`run.py` only for a narrow composition change if required to pass `analytics_runtime.current_traffic_service` into Admin Web.

Task B MUST NOT change PR A source semantics in `app/analytics/current_traffic.py`, `source_gateway.py` or `models.py` unless a blocking defect is explicitly reopened by Architect/Tech Lead.

Forbidden unrelated scope includes Omada provider/controllers, Auth/CAPPORT, Current State acquisition/storage semantics, Observation schema/workers, Visit/Registry/Cleaner, Grafana/Loki/Alloy, Nginx/systemd, Cisco/Omada Controller, docs/AGENTS, new dependencies and broad refactors.

### 30A.1. Pre-change gate

```bash
git fetch origin
git rev-parse origin/main
git status --short
```

Expected:

```text
f8fc9d1602f36777f5e1b5a2bfc532fa9076a2e0
```

Then:

```bash
python -m pytest -q -rs
PYTHONPYCACHEPREFIX=/tmp/captivportal-pyc python -m compileall -q app
git diff --check
```

Record exact SHA, Python, passed/skipped/failed, compileall, diff-check and working tree.

If main is newer before work starts, STOP and impact-review changes touching analytics/admin/current-state/config/settings/run.py/tests.

### 30A.2. Coder PLAN after future Owner authorization

PLAN must include:

```text
exact baseline
files to change
CurrentTrafficReadService wiring
max_ap_skew_seconds propagation for summary + AP page
feature config/template delivery
two routes + capabilities + gate order
Admin deadline/concurrency mapping
explicit serializer mapping
summary/no-cycle/empty-cycle behavior
AP pinned-cycle/cursor behavior
Home coordinator phases
AbortController ownership
retry/backoff/429
strict frontend validation
telemetry/privacy
targeted + Node + full tests
feature-disabled deployment boundary
no-Omada proof
no PR A source-contract modification
```

Architecture choices fixed by this FINAL are not reopened in PLAN.

---

## 31. Mandatory Node gate

Record:

```text
node --version
```

Run:

```bash
node --check app/admin_web/static/admin.js
```

New Traffic frontend behavioral test suite:

```text
PASS
0 skipped because Node unavailable
```

A Node-unavailable skip is a failed Task B gate.

---

## 32. Mandatory frontend behavior tests

At minimum:

```text
phase coordinator max 2 in-tab parallel reads
shared Refresh button ownership
Traffic waits for Phase A settle, not forever
Traffic failure isolation
AP-page 403 summary preservation
summary 403 global state
429 non-destructive/backoff/jitter
late generation ignored
identity-safe finally
pinned-400 exactly-one clean refresh
hidden-tab neutral abort
visibility resume one coordinated refresh
new summary clears old AP rows before page result
summary unavailable skips AP request
local unavailable clears AP rows/pagination
exact zero
partial direction coverage
strict enum/state/timestamp/cycle/source validation
```

---

## 32A. AP-page source ownership tests

Mandatory on the exact rebound PR A baseline:

```text
first AP page uses cycle_id only
retained old complete-success cycle is allowed
wired source derived server-side
lan fallback derived server-side
caller cannot supply/override source
cursor contains lowercase "wired" or "lan"
cursor source mismatch rejected
next page re-derives source before cursor validation
frontend/DTO/cursor allowlist accepts "lan" and rejects machine "LAN"
```

---

## 33. Backend/Admin tests

At minimum:

```text
actual PR A summary signature gets fresh/stale/max_skew/deadline
actual PR A AP-page signature gets cycle + fresh/stale/max_skew/deadline
Admin/browser cannot supply selected_source
source snapshot Site mismatch rejected before serialization
CurrentTrafficCoverage.status → coverage_status mapping
CurrentTrafficCoverage.reasons → coverage_reasons mapping
stale_max_age_seconds → unavailable_after_seconds mapping
feature default false
feature requires Admin + Home Live
bounds/cross-fields
optional runtime dependency
summary capability
AP capability
disabled 404 after security gates
unknown/duplicate params
AP cursor requires cycle
limit 1..250
retained pinned cycle
expired cycle 400
response allowlist
503 isolation
```

---

## 34. No direct Omada test

New Task B code must not import/call Omada provider/acquisition methods.

Browser HTTP must not trigger Omada.

---

## 34A. Stop conditions

STOP affected implementation and return facts if:

- exact baseline moved before work starts;
- actual CurrentTrafficReadService signature/models differ from section 5B;
- Task B requires direct Omada/provider access;
- Task B requires Observation acquisition/rate changes;
- caller-controlled `selected_source` becomes necessary;
- Traffic becomes mandatory for Admin/Home Live readiness;
- Admin cannot pass `max_ap_skew_seconds` consistently;
- route security order cannot be preserved;
- one tab cannot remain within max-two Phase A concurrency;
- mixed-generation Traffic cards/AP rows cannot be prevented;
- safe explicit serialization cannot be maintained;
- Node behavioral suite cannot run;
- page size 100 cannot fit existing response budget;
- full gate reveals a new product defect.

Do not silently broaden scope.

---

## 35. Full gates

Targeted:

```bash
python -m pytest -q tests/admin_web tests/analytics --tb=short
```

Node gate as section 31.

Full Linux:

```bash
python -m pytest -q -rs
PYTHONPYCACHEPREFIX=/tmp/captivportal-pyc python -m compileall -q app
git diff --check
git status --short
```

Record exact counts and Node version.

---

## 36. Production deployment

Code deploy first with:

```text
WEB_ADMIN_HOME_TRAFFIC_ENABLED=false
```

Validate using same Python/module/environment context as `captive-portal.service`.

Bounded readiness requires both:

```text
systemd active/running
HTTP listener ready
```

Then smoke:

```text
Portal
CAPPORT
Admin login
Home Live
Devices
Visits
Observations
```

Traffic must not render/request while disabled.

---

## 37. Production activation prerequisites

Before Traffic activation:

```text
HOME-LIVE-01 final acceptance PASS
Task A merged/accepted
Task B merged/deployed feature false
clean production tree
exact expected SHA
```

Record actual production source settings:

```text
OBSERVATION_AP_INTERVAL_SECONDS
OBSERVATION_AP_CYCLE_MAX_DURATION_SECONDS
OBSERVATION_RATE_MAX_GAP_SECONDS
```

Require:

```text
Traffic stale max age
>= AP interval + AP cycle max duration
```

unless explicitly reviewed otherwise based on measured production duration.

---

## 38. Production activation

Enable reviewed values in environment, validate in service-equivalent runtime, restart, wait for HTTP readiness.

Then verify:

```text
Home Live existing panels
Traffic summary
Traffic AP page
selected source metadata
coverage/freshness/latest-attempt
Observation cycles continue
Current State cycles continue
Registry/Visit/Analytics continue
Portal/CAPPORT healthy
```

---

## 39. Production two-tab functional soak

Minimum:

```text
5 automatic cycles
1 manual Refresh
1 hidden/visible transition
2 simultaneous visible tabs
```

Verify coordinator, isolation, 429 policy, no overlap, no stale generation append.

Two-tab 429 acceptance exactly as section 21.

---

## 40. Performance gate

Per endpoint:

```text
>=20 successful HTTP 200 latency samples
```

Separate counts:

```text
429
500
503
```

Nearest-rank p95:

```text
rank = ceil(0.95 × N)
```

Targets:

```text
summary p95 <=100ms
AP page p95 <=250ms
```

Only successful 200 durations enter percentile.

---

## 41. Privacy/coexistence gate

No sensitive identity in Traffic telemetry/access-query logging beyond ordinary sanitized access path.

Verify no regression in:

```text
Portal/CAPPORT
Home Live Current State
Devices/Device Card
Visits
Observations
Current State
Observation
Registry
Visit Lifecycle
Analytics
```

---

## 42. Rollback

Fast product rollback:

```text
WEB_ADMIN_HOME_TRAFFIC_ENABLED=false
restart
HTTP readiness
```

Open-page Traffic 404:

```text
stop Traffic polling only
clear/hide Traffic-specific current data
leave Home Live operational
```

Do not disable/delete Observation or Current State.

---

## 43. Post-merge rebind completed

Master rebind requirement is fulfilled.

Exact executable Task B baseline:

```text
origin/main@f8fc9d1602f36777f5e1b5a2bfc532fa9076a2e0
```

PR A source review:

```text
PASS
Narrow binding adjustment only:
AP-page call includes required max_ap_skew_seconds.
```

No product/architecture decision is reopened.

---

## 44. Current authorization status

```text
TASK: TASK-HOME-TRAFFIC-01-FINAL
STATUS: FINAL
EXACT BASELINE: f8fc9d1602f36777f5e1b5a2bfc532fa9076a2e0
IMPLEMENTATION: NOT AUTHORIZED
BRANCH: NOT AUTHORIZED
CODE: NOT AUTHORIZED
COMMIT: NOT AUTHORIZED
PUSH: NOT AUTHORIZED
PR: NOT AUTHORIZED
MERGE: NOT AUTHORIZED
DEPLOYMENT: NOT AUTHORIZED
PRODUCTION ACTIVATION: NOT AUTHORIZED
```

Only a later explicit Owner command may authorize implementation.

After authorization:

```text
Coder PLAN
→ Task B implementation
→ targeted + Node + full gates
→ Architect/Tech Lead review
→ merge only after separate authorization
→ feature-disabled deployment only after separate authorization
→ production activation only after separate Owner authorization
```

---

## 45. Final architecture statement

```text
existing Observation acquisition
→ persisted AP rate facts
→ accepted CurrentTrafficReadService
→ AdminQueryService
→ authenticated Site-scoped Admin API
→ coordinated Home Traffic UI
```

No new collector, no Omada call, no source DB mutation, no caller source-family choice, no alternate-source double counting, no WAN-only claim and no weakening of existing Home Live isolation.
