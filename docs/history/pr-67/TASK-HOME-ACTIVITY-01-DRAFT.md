# TASK-HOME-ACTIVITY-01 — Admin Console Home Visits and Traffic Summary — DRAFT

**Project:** CaptivPortal  
**Parent product concept:** `TASK-HOME-01 — Admin Console Home v1`  
**Supersedes / absorbs:** reserved `HOME-TODAY-01`  
**Type:** master architecture / implementation specification  
**Status:** `DRAFT FOR OWNER / TECH LEAD REVIEW`  
**Implementation authorization:** `NOT GRANTED`  
**Branch / code / commit / push / PR / merge authorization:** `NOT GRANTED`  
**Deployment / production activation authorization:** `NOT GRANTED`  
**Exact inspected baseline:** `origin/main@dfc62b43712301b05baf9f6e5dd843e13eaa9fc7`  
**Baseline re-check:** `2026-08-25`  
**Current Home Traffic merge present:** PR `#61 / 3e7ef39bf08c7ead2dd701232ddda8456fe75650`  
**Prepared:** `2026-08-25`  
**Execution mode:** `planning-only`

---

## 1. Purpose

Implement one compact Home panel with working title:

```text
Visits and Traffic
```

The panel compares:

```text
Today
vs
Selected period
```

and shows the same two metrics on both sides:

```text
Authorized visits
Traffic
```

The panel is an operational Home summary. It is not a replacement for the Visits page, a future dedicated Traffic page, Wireless Analytics or Grafana.

No code is authorized by this DRAFT.

---

## 2. `HOME-TODAY-01` decision

The previously reserved narrow task:

```text
HOME-TODAY-01
```

is absorbed and superseded by:

```text
TASK-HOME-ACTIVITY-01
```

There must not be two parallel implementations.

Canonical backlog meaning after approval:

```text
HOME-TODAY-01
→ historical alias only
→ implemented through HOME-ACTIVITY-01
```

`HOME-ACTIVITY-01` owns Today plus the selectable historical comparison for Visits and Traffic.

---

## 3. Actual repository state inspected

Verified current main:

```text
origin/main =
dfc62b43712301b05baf9f6e5dd843e13eaa9fc7
```

Current main already contains:

```text
Home Live
Home Current Traffic
Visit Lifecycle schema v2
Analytics Foundation / Visit Analytics
CurrentTrafficReadService
Admin security/query boundary
real-Node Home frontend tests
```

Current Home Traffic is already integrated into Home through a shared phased refresh coordinator.

The current `AGENTS.md` is also newer than earlier Home specifications and remains authoritative for execution/test responsibilities.

### Current Coder test responsibility

Coder runs targeted tests for changed components plus relevant frontend/static checks.

The full repository suite belongs to Reviewer / Tech Lead / Owner on the exact artifact before deployment/activation unless Owner explicitly orders otherwise.

This TASK must not reassign that full-suite responsibility to Coder.

---

## 4. Current Home architecture to preserve

Current Home Live shows:

```text
Online Now
Authorized
Waiting Authorization
Other / Unknown
AP Online / Total

Devices by AP — Now
Online Devices
Access Points Now
```

When Home Traffic is enabled it additionally shows:

```text
Traffic Now
  Download Now
  Upload Now
  Total Traffic Now

Traffic by AP
```

Current shared Home behavior already provides:

```text
one Refresh action
generation protection
AbortController ownership
hidden-tab pause
pagehide cleanup
bounded retry/backoff
Current State failure isolation
Current Traffic failure isolation
```

Current coordinated flow is conceptually:

```text
Phase A:
  Client Current State
  AP Current State
  concurrently

Phase B:
  Current Traffic
  after Phase A
```

Normal per-tab Phase A concurrency is at most two HTTP requests.

`HOME-ACTIVITY-01` MUST extend this coordinator. It MUST NOT create an independent polling loop.

---

## 5. Current Admin bounded query boundary

Current Admin data queries use:

```text
Admin session
Site resolver
AdminAccessPolicy
AdminQueryService
one shared non-blocking query semaphore
one QueryDeadline per request
response-size cap
```

Current defaults include:

```text
WEB_ADMIN_MAX_CONCURRENT_QUERIES=2
WEB_ADMIN_MAX_QUERY_DURATION_SECONDS=10
```

No slot:

```text
HTTP 429
Retry-After: 1
```

Deadline:

```text
HTTP 503
code=query_deadline
```

Activity must use this existing bounded boundary. No second server queue is introduced.

---

# PRODUCT CONTRACT

## 6. Panel presentation

Working visible title:

```text
Visits and Traffic
```

Do not call Visits/devices “people”. Do not expose `AuthSession` terminology in this panel.

Desktop:

```text
┌──────────────────── Visits and Traffic ───────────────── [Last 24 hours ▾] ┐
│                                                                             │
│ TODAY                                  │ LAST 24 HOURS                       │
│ 25 Aug 00:00 → 10:40 +04             │ 24 Aug 10:40 → 25 Aug 10:40 +04    │
│                                        │                                     │
│ Authorized visits               32     │ Authorized visits               71  │
│ Traffic                        4.8 GB   │ Traffic                         9.7 GB│
│                                        │                                     │
│ Complete · Traffic estimated           │ Complete · Traffic estimated       │
│ from completed session reports         │ from completed session reports     │
└────────────────────────────────────────┴─────────────────────────────────────┘
```

Numbers above are illustrative only.

Narrow/mobile:

```text
Visits and Traffic
[picker]

TODAY
  exact boundaries
  Authorized visits
  Traffic
  quality

SELECTED PERIOD
  exact boundaries
  Authorized visits
  Traffic
  quality
```

Today is always first. No horizontal page scrolling.

Recommended placement:

```text
Current-state top cards

Traffic Now               # only if enabled

Visits and Traffic         # only if Activity enabled

Devices by AP — Now
Online Devices
Access Points Now
```

Activity does not require Current Traffic to be enabled.

---

# METRIC A — AUTHORIZED VISITS

## 7. Exact metric name and unit

API field:

```text
authorized_visits
```

Visible label:

```text
Authorized visits
```

Product unit:

```text
one Visit opened by a successful portal authorization
```

One Visit contributes at most one unit.

Never count:

```text
AuthSession count
authorization retry count
visit_authorizations row count
Omada online clients
pending/failed association attempts
```

---

## 8. Why the current Visit source supports the preferred cohort

Current Visit Lifecycle creates a new Visit only after successful authorization.

For a new Visit the current repository writes:

```text
visits.started_at = successful authorized_at
```

and attaches the opening authorization evidence in the same transaction.

If an open Visit already exists for:

```text
site_id + client_mac
```

a later successful authorization:

```text
does not create another Visit
does not change visits.started_at
adds authorization evidence only
```

Therefore the chosen stable cohort timestamp is:

```text
visits.started_at
```

with product meaning:

```text
the successful authorization that opened the Visit
```

No new authorization collector is required.

---

## 9. Authorized Visit cohort query

A Visit belongs to `[from_utc,to_utc)` when:

```text
v.site_id = requested Site

v.started_at >= from_utc
v.started_at <  to_utc

v.start_ssid belongs to configured exact guest SSID scope
```

Metric:

```text
COUNT(verified qualifying visit_id)
```

### Opening-evidence integrity

For an exact unit verify set-based evidence matching:

```text
visit_id
start_auth_session_id
start_auth_run_number
authorized_at = visits.started_at
```

If opening evidence is absent/contradictory:

```text
do not invent another timestamp
do not count AuthSessions instead
status=partial
value=verified subtotal
integrity_anomaly_count > 0
```

Activity never repairs Visit persistence.

---

## 10. Visit edge cases

Required semantics:

```text
Wi-Fi association before interval + successful opening auth inside interval
→ count

Visit opened before interval and remains open inside it
→ do not count in this interval

Visit crosses midnight
→ count once on local day containing visits.started_at

started_at == from
→ include

started_at == to
→ exclude

open authorized Visit
→ count

later Visit closure
→ cannot remove/move old unit

later new Visit after closure
→ new unit
```

Duplicate same auth run and multiple successful authorization rows in one open Visit never increase the unit count.

Later authorization evidence with an earlier timestamp is a chronology/data-quality anomaly. It does not rewrite `visits.started_at` or move historical Home counts.

---

## 11. Visit SSID scope

Activity does not count every Visit in the Site.

Canonical Visit population:

```text
Site
+
configured exact guest SSID allowlist
```

The scope is the opening authorization SSID:

```text
visits.start_ssid
```

Matching is:

```text
case-sensitive
exact string
no trim
no case folding
no Unicode normalization
no comma splitting
```

A Visit opened on another SSID is not reclassified later merely because later authorization evidence in the same open Visit references a scoped SSID.

---

## 12. Visit zero / partial / unavailable

Successful exact query with no qualifying Visit:

```text
value=0
status=complete
```

Integrity anomaly that may affect the result:

```text
value=verified subtotal
status=partial
```

Source unavailable:

```text
value=null
status=unavailable
```

Missing/unavailable never becomes zero.

---

# METRIC B — GENERAL GUEST TRAFFIC

## 13. Exact metric

API field:

```text
traffic
```

Visible label:

```text
Traffic
```

Primary value:

```text
combined observed guest-session traffic volume
```

API unit:

```text
integer bytes
```

No Download/Upload split in v1.

---

## 14. Source decision table

| Candidate | Finding | Decision |
|---|---|---|
| `CurrentTrafficReadService` | current AP physical/network Mbps; may include local/service/non-guest traffic | **Reject for Activity history** |
| AP/Wireless Observation | AP-wide or authorized-only history; not general guest volume | **Reject** |
| Visit Analytics reported traffic | tied to successful Visit population | **Reject for general guest total** |
| Public Traffic `traffic_daily` | durable daily SSID total, but no Site dimension and no time-of-day precision | **Reconciliation only** |
| Visit Lifecycle `visit_source_events` | Site + SSID + event time + deduplicated completed-session traffic estimate | **USE** |

---

## 15. Chosen Traffic authority

Persistence:

```text
visits.sqlite3
```

Table:

```text
visit_source_events
```

Event kind:

```text
omada.client_offline
```

Fields used:

```text
event_id
site_id
controller_event_at
received_at
ssid
reported_traffic_total_bytes
processing_result
reason
```

The normalizer converts controller-reported:

```text
B / KB / MB / GB / TB
```

to an integer byte estimate using binary 1024 multipliers and `ROUND_HALF_UP`.

Therefore this metric is explicitly:

```text
Estimated
```

It is not billing-grade precision.

---

## 16. Traffic population

An offline event belongs to the Activity traffic population when:

```text
event_type = 'omada.client_offline'
site_id = requested Site
ssid exactly belongs to configured guest SSIDs
event has attributable timestamp
event_id is already persistence-deduplicated
```

Traffic does NOT require:

```text
a matched Visit
successful authorization
processing_result='closed'
```

This is deliberate: Traffic is general guest-network session traffic, not successful-Visit traffic.

A guest connection that never becomes an authorized Visit can still contribute valid traffic when an in-scope completed-session offline report exists.

---

## 17. Event-time attribution

Preferred timestamp:

```text
controller_event_at
```

Fallback only when controller time is absent:

```text
received_at
```

The entire reported session byte estimate is attributed to the interval containing the chosen offline-event timestamp.

`received_at` fallback remains visible quality evidence and causes `partial` coverage for that interval.

---

## 18. Intrinsic Traffic approximation

This is NOT interval-clipped byte accounting.

Example:

```text
session starts 23:30
uses 2 GB before midnight
uses 1 GB after midnight
ends 00:30
controller reports 3 GB
```

v1 attributes:

```text
3 GB to the period containing 00:30
```

It does not invent a split of 2 GB / 1 GB.

Also:

```text
active session
→ absent until a persisted offline report exists
```

Mandatory visible meaning:

```text
Estimated traffic from completed guest sessions,
attributed when the session ends.
```

Do not label this:

```text
Internet Traffic
WAN Traffic
billable traffic
Downloaded from Internet
```

The controller session total is not proven Internet-only.

---

## 19. Traffic missing / duplicate / reset behavior

Duplicate normalized event:

```text
same event_id
→ one persisted event
→ one contribution
```

Missing traffic:

```text
reported_traffic_total_bytes = null
→ missing evidence
→ not zero
→ excluded from numeric subtotal
→ missing_traffic_count += 1
→ status=partial
```

Exact zero:

```text
reported_traffic_total_bytes = 0
→ valid zero contribution
```

This metric does not integrate AP counters. Therefore AP counter reset/wrap/baseline/gap math from Current Traffic does not apply.

Only persisted completed-session event evidence contributes.

---

# HISTORY / TIME CONTRACT

## 20. Owner revision — no arbitrary 31-day maximum

There is NO arbitrary 31-day Home Activity maximum.

Inspection found no Visit Lifecycle retention/cleanup contract that deletes Visit/source-event facts after 31 or 90 days.

The existing generic Analytics limits such as:

```text
ANALYTICS_MAX_QUERY_WINDOW_DAYS
ANALYTICS_VISIT_MAX_WINDOW_DAYS
```

are query-policy limits for existing generic Analytics methods, not Visit DB retention.

`HOME-ACTIVITY-01` must not inherit those limits.

Final range rule:

```text
custom range may span any retained history
provided the bounded aggregate finishes inside the existing Admin deadline
```

No 31-day or 90-day hidden rejection.

If full retained-history query cannot meet the deadline, the solution is an explicit index/rollup prerequisite, not a silent product-range reduction.

---

## 21. Quick ranges

Required quick ranges:

```text
Last 24 hours
Yesterday
Last 48 hours
Last 7 days
Current month
Last 30 days
```

Machine enum:

```text
last_24h
yesterday
last_48h
last_7d
current_month
last_30d
custom
```

Do not use ambiguous `1 day`.

A future `All available` shortcut is optional only if the implementation can display an honest earliest persisted-evidence boundary and full-history performance passes. Custom range already permits all retained history, so this shortcut is not required for v1.

Never label it `All time` or `Lifetime`.

---

## 22. Canonical Site timezone

Current repository has global `PORTAL_COUNTER_TIMEZONE`, but it is a portal-counter setting, not a Site-aware Admin timezone authority.

Activity therefore introduces explicit Site-scoped context.

Preferred configuration:

```text
WEB_ADMIN_HOME_ACTIVITY_SITE_CONTEXT_JSON
```

Conceptual production value:

```json
{
  "<site-id>": {
    "timezone": "Asia/Baku",
    "guest_ssids": ["Zefer_Parki"]
  }
}
```

Repository default contains no real production Site/SSID.

Validation:

```text
canonical lowercase 24-hex Site keys
IANA timezone accepted by zoneinfo.ZoneInfo
non-empty JSON guest_ssids array
exact strings
no duplicates
no hidden normalization
```

If Activity is enabled but requested Site lacks valid Activity context:

```text
Activity endpoint → 503 source_unavailable
```

Admin/Home Live/Home Traffic/Portal remain available.

---

## 23. Shared evaluated_at

One Activity response captures one UTC:

```text
evaluated_at
```

All four metric computations use it:

```text
Today Visit
Today Traffic
Selected Visit
Selected Traffic
```

Do not mix evaluation times and present them as one exact response.

---

## 24. Today

Left side is always:

```text
[Site-local midnight, evaluated_at)
```

Today never means Last 24 hours.

Response returns exact:

```text
from_utc
to_utc
from_local
to_local
timezone
```

and:

```text
next_site_midnight_utc
```

for safe browser rollover scheduling.

---

## 25. Preset semantics

Rolling:

```text
Last 24h = evaluated_at - 24h
Last 48h = evaluated_at - 48h
Last 7d  = evaluated_at - 7*24h
Last 30d = evaluated_at - 30*24h
```

`Yesterday`:

```text
previous completed Site-local calendar day
```

It may be 23/24/25 hours in DST zones.

`Current month`:

```text
Site-local first day 00:00 → evaluated_at
```

Fresh page default:

```text
Last 24 hours
```

Relative presets re-resolve on refresh.

---

## 26. Custom absolute range

Picker fields:

```text
From
To
Apply
Cancel
```

Canonical browser machine value:

```text
YYYY-MM-DDTHH:MM:SS
```

No timezone suffix is sent. Server resolves using configured Site timezone.

Accepted interval:

```text
[from_utc,to_utc)
```

Server rejects:

```text
invalid format
from >= to
future boundary
invalid timezone
nonexistent local time
```

Server does NOT reject solely because a range is 32/90/180/365+ days.

Date-only values are invalid. There is no hidden inclusive end-of-day conversion.

Required:

```text
from_utc < to_utc <= evaluated_at
```

No silent clipping to now.

Custom accepted From/To remain fixed on auto/manual refresh and Today rollover.

---

## 27. DST rules

Use `zoneinfo` and round-trip validation.

Spring-forward nonexistent local time:

```text
400 invalid_request
```

No automatic shift.

Fall-back ambiguous local time:

```text
From → earlier occurrence / fold=0
To   → later occurrence / fold=1
```

This avoids silently dropping one repeated occurrence.

If raw local From equals raw local To, reject before fold expansion.

Response always returns resolved offset-aware local boundaries so the accepted interpretation is inspectable.

---

## 28. Midnight rollover

Browser schedules from server-provided:

```text
next_site_midnight_utc
```

At rollover:

```text
new Activity generation
Today becomes new local day
relative selected period advances normally
absolute selected period remains unchanged
```

Hidden tab does not create a rollover request burst. On visibility return, one controlled refresh occurs if rollover/refresh became due.

---

# READ / API ARCHITECTURE

## 29. Chosen data path

```text
visits.sqlite3
  ├─ visits
  ├─ visit_authorizations
  ├─ visit_source_events
  └─ visit_reader_state
        ↓
AnalyticsSourceGateway
        ↓
HomeActivityReadService
        ↓
AdminQueryService
        ↓
GET /admin/api/v1/sites/{site_id}/home-activity/summary
        ↓
shared Home coordinator
        ↓
Visits and Traffic panel
```

No Omada call. No new collector. No new business DB.

Preferred new Analytics module:

```text
app/analytics/home_activity.py
```

The service is read-only, Site-scoped, deadline-aware and immutable-result.

It reads through existing Visit `analytics_read_connection()` / Analytics source boundary.

---

## 30. Do not reuse generic Visit Analytics max-window path

Do not implement long Activity ranges by calling generic:

```text
VisitAnalyticsService.get_visit_counts()
```

because current generic Visit Analytics enforces its own max-window policy.

Correct:

```text
HomeActivityReadService
→ narrow set-based aggregate over persisted Visit source
```

Existing generic Analytics limits remain unchanged for existing methods.

No global widening is required.

---

## 31. Runtime isolation

Preferred new optional Analytics runtime field:

```text
home_activity_service
```

It MUST NOT join/strengthen readiness for existing:

```text
quality_service
wireless_service
visit_service
current_traffic_service
```

Construction failure:

```text
home_activity_service=None
```

while existing Analytics remains unchanged.

Admin receives Activity as an optional dependency. Its absence affects only Activity routes.

Do not let Activity absence make existing Admin query service unavailable.

---

## 32. Activity config isolation

Preferred narrow module:

```text
app/admin_web/home_activity_config.py
```

so malformed Activity-specific settings can fail Activity only instead of taking down core Admin security/runtime.

Proposed repository-safe settings:

```text
WEB_ADMIN_HOME_ACTIVITY_ENABLED=false
WEB_ADMIN_HOME_ACTIVITY_REFRESH_SECONDS=60
WEB_ADMIN_HOME_ACTIVITY_REQUEST_TIMEOUT_SECONDS=20
WEB_ADMIN_HOME_ACTIVITY_SITE_CONTEXT_JSON={}
WEB_ADMIN_HOME_ACTIVITY_TRAFFIC_FRESH_MAX_AGE_SECONDS=90
WEB_ADMIN_HOME_ACTIVITY_TRAFFIC_STALE_MAX_AGE_SECONDS=300
```

Bounds:

```text
refresh: 60..300
request timeout: 5..60
traffic fresh: 10..300
traffic stale: fresh..1800
```

Cross-field:

```text
HOME_ACTIVITY_REQUEST_TIMEOUT_SECONDS
>
WEB_ADMIN_MAX_QUERY_DURATION_SECONDS
```

Feature requires:

```text
WEB_ADMIN_ENABLED=true
WEB_ADMIN_HOME_LIVE_ENABLED=true
```

It does NOT require Home Traffic.

No history-days config exists.

---

## 33. Feature-disabled behavior

When Activity flag is false:

```text
no panel DOM
no picker listeners
no Activity timer
no Activity fetch
no Activity source access
```

Existing Home is unchanged.

---

## 34. One combined endpoint

Choose:

```text
GET /admin/api/v1/sites/{site_id}/home-activity/summary
```

It returns Today + Selected in one response.

Reasons:

```text
one shared evaluated_at
one Admin query slot
one tiny response
one source snapshot
no four-request burst
```

Independent metric states remain nested in the response.

Capability:

```text
admin.read.overview
```

No broader capability.

---

## 35. Query parameters

Preset request has exactly:

```text
period
```

Custom has exactly:

```text
period
from_local
to_local
```

Examples:

```text
?period=last_24h

?period=custom
&from_local=2026-07-01T00:00:00
&to_local=2026-08-25T10:40:00
```

Unknown or duplicate parameters → 400.

Custom fields with a preset → 400.

Custom missing either boundary → 400.

---

## 36. Security/feature gate order

Required order:

```text
HTTPS/network/query-size
→ session
→ Site syntax/allowlist
→ admin.read.overview capability
→ Activity feature flag
→ disabled 404
→ Activity Site context
→ exact parameter schema
→ range resolution
→ AdminQueryService
```

Add a narrow `_is_home_activity_path()` duplicate-query exception analogous to Current State/Current Traffic so parameter-schema probing does not occur before intended gates.

Do not weaken global Admin request validation.

HTTP mapping:

```text
200  result/metric quality
400  invalid_request
401  authentication_required
403  site/capability forbidden
404  feature disabled
429  concurrency_limit + Retry-After
503  source_unavailable / query_deadline / response_too_large
500  sanitized internal_error
```

---

## 37. Public DTO

Admin envelope remains `admin.read.v1`.

Conceptual `result`:

```json
{
  "evaluated_at": "2026-08-25T06:40:00.000Z",
  "site_timezone": "Asia/Baku",
  "source_scope": {
    "guest_ssids": ["Zefer_Parki"],
    "ssid_matching": "exact_case_sensitive"
  },
  "next_site_midnight_utc": "2026-08-25T20:00:00.000Z",
  "selection": {
    "period": "last_24h",
    "relative": true
  },
  "today": {
    "range": {},
    "authorized_visits": {},
    "traffic": {}
  },
  "selected": {
    "range": {},
    "authorized_visits": {},
    "traffic": {}
  }
}
```

Range DTO:

```json
{
  "kind": "today",
  "from_utc": "2026-08-24T20:00:00.000Z",
  "to_utc": "2026-08-25T06:40:00.000Z",
  "from_local": "2026-08-25T00:00:00+04:00",
  "to_local": "2026-08-25T10:40:00+04:00",
  "timezone": "Asia/Baku"
}
```

Authorized Visits DTO:

```json
{
  "value": 32,
  "status": "complete",
  "quality_reasons": [],
  "cohort": "visit_opening_authorization",
  "source_kind": "visit_lifecycle",
  "verified_visit_count": 32,
  "integrity_anomaly_count": 0,
  "earliest_persisted_evidence_at": "...",
  "latest_persisted_evidence_at": "..."
}
```

Traffic DTO:

```json
{
  "bytes": 5153960755,
  "status": "complete",
  "quality_reasons": [],
  "estimated": true,
  "attribution": "completed_session_end",
  "source_kind": "omada_offline_reported_traffic",
  "eligible_event_count": 48,
  "included_event_count": 48,
  "missing_traffic_count": 0,
  "controller_time_count": 48,
  "received_time_fallback_count": 0,
  "reader_watermark_at": "...",
  "ingestion_freshness": "fresh",
  "earliest_persisted_evidence_at": "...",
  "latest_persisted_evidence_at": "..."
}
```

Allowed metric status:

```text
complete
partial
unavailable
```

Traffic ingestion freshness:

```text
fresh
stale
unavailable
```

Public serializers are explicit allowlists. No generic source-row/dataclass dump.

---

## 38. Data minimization

Do not expose in Activity response:

```text
visit_id
auth_session_id
client MAC/IP
device_id
AP MAC
source event ID
raw log/controller text
SQLite path
raw SQL
```

Safe aggregate provenance may include source kind, Site timezone, guest SSID scope, persisted evidence bounds, Traffic reader watermark, and the `estimated`/attribution semantics.

---

# QUALITY / FRESHNESS

## 39. Independent metric states

For each half, Visit and Traffic are independently renderable.

Examples:

```text
Visit complete + Traffic partial
Visit unavailable + Traffic complete
Visit complete zero + Traffic complete zero
```

One metric failure does not erase the other metric.

Today and Selected also maintain independent rendered state.

A selected-range problem does not erase a valid Today value.

---

## 40. Loading / partial / zero / unavailable

Initial:

```text
Loading…
```

Picker Apply may leave Today visible while Selected enters Loading.

Complete zero:

```text
Authorized visits = 0
Traffic = 0 B
```

Partial numeric result remains visible with explicit `Partial` label.

Unavailable:

```text
value=null / bytes=null
UI = — · Unavailable
```

Never use JS truthiness that converts numeric zero to a dash.

---

## 41. Traffic ingestion freshness

Use persisted Visit reader heartbeat:

```text
MAX(visit_reader_state.updated_at)
```

Policy from Activity config:

```text
age <= fresh max → fresh
age <= stale max → stale
older/invalid/future → unavailable
```

This is ingestion freshness, not historical row expiry.

A historical period ending before a known healthy reader watermark keeps its stored numeric result even if the reader is currently stale.

If a period reaches toward `evaluated_at` while ingestion is stale/unavailable, the observed subtotal may remain visible but must be marked partial/stale because recent offline events may be missing.

---

## 42. Mandatory Traffic helper

Compact:

```text
Estimated · completed guest sessions
```

Detailed meaning:

```text
Traffic is estimated from Omada completed-session reports
and attributed to the time the session ended.
Active sessions are not included until an offline report is recorded.
It is not an Internet-only or billing metric.
```

---

## 43. Byte formatting

Frontend receives integer bytes.

Use binary adaptive display with conservative precision:

```text
<1024 B → integer B
KB/MB/GB/TB → at most one decimal place
```

Examples:

```text
0 B
842 B
12.4 KB
836 MB
4.8 GB
1.2 TB
```

Do not present excessive decimal precision because upstream Traffic is an estimate.

---

# SQL / PERFORMANCE CONTRACT

## 44. One read-only Visit DB snapshot

One Activity request uses one read-only SQLite snapshot transaction for Activity source reads.

Required:

```text
URI mode=ro
PRAGMA query_only=ON
schema-version validation
existing QueryDeadline/progress interruption
```

No source writes or migrations.

---

## 45. Visit aggregation

Use existing index family around:

```text
(site_id, start_ssid, started_at, visit_id)
```

Use set-based SQL for Today + Selected, preferably fixed-count branches such as `UNION ALL` or equivalent bounded statements.

Opening authorization integrity verification is also set-based/indexed.

Forbidden:

```text
fetch all Visits → Python count
one query per Visit
```

---

## 46. Traffic aggregation

Controller-time branch:

```text
site_id
SSID allowlist
controller_event_at >= from
controller_event_at < to
```

should use the existing Site/controller-time index.

Fallback branch:

```text
site_id
controller_event_at IS NULL
received_at >= from
received_at < to
```

must have its actual query plan measured.

Do not use broad `COALESCE(controller_event_at, received_at)` filtering without proving an acceptable plan.

No full-history Python materialization.

The number of SQL statements must remain fixed and not grow with Visit/event count.

---

## 47. Full retained-history gate

Because Owner removed the 31-day cap, representative evidence MUST include:

```text
Today
Last 24h
Last 7d
Last 30d
Current month
all currently retained production history
```

and at least one custom range longer than 31 days when retained history permits it.

Capture `EXPLAIN QUERY PLAN` for:

```text
Visit Today
Visit long range
Traffic controller-time Today
Traffic controller-time long range
Traffic fallback-time branch
MIN/MAX evidence metadata
```

Measure cold/warm:

```text
row population
p50
p95
max
deadline failures
```

Do not invent a p95 target before actual measurements exist.

---

## 48. Performance STOP / prerequisite

If all retained history cannot remain bounded inside the existing Admin hard deadline using current indexes:

```text
STOP
```

Do NOT silently reintroduce 31/90-day caps.

Return actual:

```text
EXPLAIN
row counts
timings
```

Then create the smallest explicit prerequisite such as:

```text
TASK-HOME-ACTIVITY-READ-01
```

containing only the proven necessary index or rollup contract.

At DRAFT time no prerequisite is proven necessary because the required read-only Visit DB and relevant start/controller-time indexes already exist.

---

# FRONTEND / REFRESH CONTRACT

## 49. Shared coordinator generalization

Current Home has a Live-only path and a shared Live+Traffic path.

Activity creates four combinations:

```text
Live only
Live + Traffic
Live + Activity
Live + Traffic + Activity
```

Do not create a third independent timer/controller.

When either Traffic OR Activity is enabled, use the shared extended coordinator:

```text
PHASE A
  Current Client
  Current AP
  concurrent, max 2

PHASE B
  Current Traffic
  if enabled

PHASE C
  Home Activity
  if enabled
```

Traffic and Activity are sequential after Phase A by default to keep query-slot pressure bounded.

---

## 50. Activity source state

Activity owns:

```text
generation
selection_revision
AbortController
failure_count
next_eligible_at
last accepted result
last accepted time
disabled state
```

It does not share Traffic cycle/cursor state.

---

## 51. Default load / Refresh

Fresh load:

```text
Phase A
→ optional Traffic
→ Activity with last_24h
```

Existing global Refresh button refreshes all eligible Home sources through the shared coordinator.

Relative Activity ranges advance.

Absolute custom range remains fixed.

No overlap.

---

## 52. Picker Apply is Activity-only

Picker Apply must NOT refetch Current Client/AP/Traffic solely because the Activity range changed.

Required:

```text
validate draft
→ commit selected range
→ increment selection_revision
→ abort obsolete Activity request only
→ schedule one immediate Activity request
```

If full Home cycle is active, store one pending Activity refresh. Do not abort unrelated Client/AP/Traffic work.

If Activity request is already in flight, abort that owned request as `superseded_selection`.

When coordinator becomes idle, run exactly one request for the newest accepted selection.

---

## 53. Stale-response protection

Every Activity request captures:

```text
Site
coordinator generation
selection_revision
period/request identity
```

Before accept, all identities must still match.

An old Last-7d response can never overwrite a newly selected Yesterday/custom result.

Late `finally` cannot release a newer AbortController.

---

## 54. Hidden/unload behavior

When hidden:

```text
no Activity auto polling
owned Activity request aborts neutrally
failure count unchanged
```

On visible, one controlled refresh if due/rollover passed.

On `pagehide`:

```text
abort Activity
clear timer
clear pending Activity operation
```

No browser persistence.

---

## 55. Retry/backoff

Use existing Home pattern:

```text
1st retryable failure → 60s
2nd → 120s
3rd+ → 300s
```

Actual delay respects:

```text
refresh interval
backoff
Retry-After
```

Manual Refresh may bypass normal success interval but not hammer an active failure backoff.

A newly accepted picker range may issue one immediate request; repeated exact failing Apply remains bounded.

404 from feature rollback stops Activity only and leaves Home Live/Home Traffic running.

---

# PICKER / ACCESSIBILITY

## 56. Picker behavior

Required UI:

```text
quick ranges
From
To
Apply
Cancel
```

Recommended:

```text
quick range → apply immediately
custom edit → Apply required
```

Intermediate custom calendar/time clicks issue no request.

Accessibility:

```text
accessible button/dialog labels
keyboard navigation
focus enters picker
Escape cancels
Cancel cancels
Apply commits
focus returns to opener
validation message associated with fields
```

Dynamic API text uses safe `textContent` / node creation.

No unsafe API-fed `innerHTML`.

No new frontend framework or external CDN.

Browser timezone is never authoritative. Do not convert custom local input to UTC using browser-local `Date` semantics.

---

# SECURITY / PRIVACY / TELEMETRY

## 57. Read-only and CSRF

Activity API is GET/read-only.

No CSRF token is required for this GET under the existing Admin session model.

No mutation occurs.

No browser/route call to Omada/provider is allowed.

---

## 58. Data minimization

Activity UI/API never exposes client identities.

Do not expose/log:

```text
MAC
IP
Visit IDs
AuthSession IDs
event IDs
raw cursor/query
raw SQL
DB path
raw exception
token/cookie/password
raw Omada payload
```

Configured guest SSID scope may be returned as aggregate population metadata.

---

## 59. Telemetry

Add safe event:

```text
admin.home_activity_query_completed
```

Allowlisted fields:

```text
request_id
route_name
authorized site_id
status_code
outcome
reason
duration_ms
period
today_visit_status
today_traffic_status
selected_visit_status
selected_traffic_status
traffic_ingestion_freshness
```

Do not log raw custom From/To strings, SSIDs or raw source exceptions.

Telemetry failure must not alter route result.

---

# IMPLEMENTATION SCOPE

## 60. Expected files

Preferred new/narrow implementation area:

```text
app/analytics/home_activity.py
app/analytics/models.py
app/analytics/source_gateway.py
app/analytics/runtime.py
app/analytics/__init__.py

app/admin_web/home_activity_config.py
app/admin_web/home_activity_serialization.py
app/admin_web/query_service.py
app/admin_web/routes.py
app/admin_web/runtime.py
app/admin_web/pages.py
app/admin_web/templates/admin/home.html
app/admin_web/static/admin.js
app/admin_web/static/admin.css

app/config.py
app/settings.py
.env.example

tests/analytics/test_home_activity*.py
tests/admin_web/test_home_activity*.py
tests/admin_web/test_home_activity_frontend.py
```

No Visit source-file change is currently expected.

If Analytics gateway cannot express the narrow read without source extension, return the exact gap before touching:

```text
app/visit_lifecycle/read_service.py
app/visit_lifecycle/repository.py
```

Any source addition would be read-only only: no schema, migration, writer or lifecycle semantic change.

---

## 61. Forbidden areas

Do not change:

```text
Visit schema
Visit start/finalization behavior
Visit webhook reader behavior
Observation schema/workers/cadence
Current State schema/workers
CurrentTrafficReadService semantics
Public Traffic writer/schema
Omada provider/token lifecycle
Auth/CAPPORT
Pending Cleaner
Visitor Registry writes
Grafana/Loki/Alloy
Nginx/systemd
Cisco/Omada Controller
```

No dependency addition. No broad Admin refactor.

Knowledge-base files are not part of this runtime implementation task:

```text
AGENTS.md
docs/**
```

unless separately authorized.

---

# TARGETED TEST CONTRACT

## 62. Visit tests

At minimum:

```text
one successful Visit = one unit
duplicate auth run does not double count
multiple auth evidence rows in one Visit = one unit
pending/failed/no Visit excluded
from included / to excluded
cross-midnight
open authorized Visit
later closure does not remove count
new Visit after closure counts
Site isolation
SSID isolation/case sensitivity
opening evidence mismatch → partial
out-of-order later auth → no cohort rewrite
successful empty query → 0
```

---

## 63. Traffic tests

At minimum:

```text
valid in-scope offline event contributes bytes
unmatched/no-Visit event may contribute
other Site excluded
other SSID excluded
duplicate event not double counted
from included / to excluded
received-time fallback → partial
null traffic != zero
exact zero valid
combined total only
no Download/Upload fabrication
active/no-offline absent by definition
cross-midnight session attributed to offline timestamp
no rate-as-byte integration
successful empty query → 0 B
```

---

## 64. Time/history tests

At minimum:

```text
Today local midnight
Today != Last24h
Yesterday
rolling 24h/48h/7d/30d
Current month
custom absolute
custom 32-day accepted
custom >90-day accepted when source fixture covers it
no generic Analytics max-window rejection
future/reversed/equal/date-only invalid
DST nonexistent invalid
DST ambiguity fold policy
one shared evaluated_at
midnight rollover
absolute range stable
relative range advances
```

---

## 65. API/security tests

At minimum:

```text
401 unauthenticated
400 invalid Site
403 forbidden Site/capability
404 disabled flag after gates
503 missing Site Activity context
503 missing Activity service
exact preset/custom parameter schemas
unknown/duplicate params
429 common slot
503 query deadline/source/response cap
explicit DTO allowlist
no identities/raw source
no Omada calls
read-only proof
```

---

## 66. Mandatory real-Node frontend tests

Node is mandatory for this Home frontend gate.

Do not skip because Node is absent; absence is a failed/missing required environment capability.

Cover:

```text
picker presets/custom
Apply/Cancel/Escape/focus
no fetch during intermediate custom edits
no browser timezone authority
zero vs null/partial/unavailable
Estimated label
Today vs selected isolation
selection generation/abort
late response rejection
Apply does not refetch unrelated Home sources
shared phases and max concurrency
manual Refresh
hidden/pagehide
429/503/network backoff
Activity 404 isolation
existing Traffic AP-page 403 preservation
all four feature combinations:
  Live only
  Live+Traffic
  Live+Activity
  Live+Traffic+Activity
```

Because shared coordinator code changes, existing Home Live and Home Traffic targeted frontend tests must remain green.

---

## 67. Full-suite responsibility

Do not make routine full repository pytest a Coder acceptance item.

Per current `AGENTS.md`:

```text
Coder → targeted feature/regression tests
Reviewer/Tech Lead/Owner → full repository gate on exact artifact before deploy/activation
```

Relevant static checks may still include:

```bash
PYTHONPYCACHEPREFIX=/tmp/captivportal-pyc python -m compileall -q app
git diff --check
```

plus real Node execution for changed frontend.

---

# CODER PLAN / STOPS

## 68. Coder PLAN after future authorization

Before edits, Coder must return PLAN with:

```text
exact current baseline
files to change
HomeActivityReadService design
Visit aggregate/integrity SQL
Traffic controller/fallback SQL
EXPLAIN plan strategy
no duration hard cap
Site context/timezone parser
runtime fail-open wiring
route/capability/gate order
DTO serializer
shared evaluated_at
DST resolver
coordinator Phase C
picker Activity-only refresh
generation/AbortController ownership
targeted + Node tests
no-Omada proof
no schema/worker changes
```

No settled product choices are delegated back to Coder.

---

## 69. Hard stops

STOP affected work and return exact facts if:

- current main changes and affects Admin/Visit/Analytics/Home contracts;
- `visits.started_at` no longer represents opening successful authorization;
- correct count requires AuthSession counting;
- source-event traffic loses safe Site/SSID/time attribution;
- reported traffic unit semantics differ from inspected normalizer;
- correct Traffic requires Current Traffic Mbps integration;
- correct Traffic requires Omada/provider;
- full retained-history aggregate cannot meet current Admin deadline;
- new index/schema/rollup becomes necessary;
- Site timezone cannot be safely resolved;
- Activity optional dependency would make existing Analytics/Admin unavailable;
- coordinator cannot preserve bounded concurrency;
- frontend cannot prevent stale-selection overwrite.

For each STOP return:

```text
exact gap
files/modules affected
smallest prerequisite
safe work that remains
work that must not continue
```

---

# DEPLOYMENT / ROLLBACK

## 70. Staged deployment boundary

Merge does not activate Activity.

Repository default:

```text
WEB_ADMIN_HOME_ACTIVITY_ENABLED=false
```

Sequence:

```text
1. merge reviewed code
2. deploy with Activity=false
3. verify Portal/Admin/Home Live/Home Traffic
4. separate Owner activation authorization
5. configure Activity Site context
6. enable + restart
7. production reconciliation/performance/browser acceptance
```

---

## 71. Feature-disabled deployment checks

Verify:

```text
Portal
CAPPORT
Admin login
Home Live
Home Traffic if enabled
Devices
Device Card
Visits
Observations

Activity panel absent
Activity request absent
Activity timers/listeners absent
```

Activity service construction failure must not regress existing features.

---

## 72. Production acceptance

After separate activation authorization:

### Functional reconciliation

Authorized Visits:

```text
Today
Last24h
one longer period
```

compare Admin output with direct safe read-service/source aggregate from the same Visit persistence.

Do not use Grafana AuthSession count as sole truth.

Traffic:

```text
Activity service = Admin Activity API
```

for same Site/SSID/range.

Also compare one compatible calendar-day/SSID interval with Public Traffic where overlapping history exists as an independent sanity check, documenting semantic differences instead of forcing equality.

### Browser

Verify desktop+narrow, presets, custom >31 days when retained history permits, Apply/Cancel/keyboard, Refresh, hidden tab and source isolation.

### Performance

Collect successful HTTP 200 timings by range category:

```text
count
p50
p95
max
429
503 deadline
500
```

Set continuing p95 threshold only after real evidence.

Two visible tabs must not create request storm or monopolize Admin query slots.

---

## 73. Fast rollback

Fast product rollback:

```text
WEB_ADMIN_HOME_ACTIVITY_ENABLED=false
```

Then owner-controlled restart/health checks.

Do NOT disable/delete:

```text
Admin
Home Live
Home Traffic
Current State
Observation
Visit Lifecycle
Analytics
Public Traffic
source SQLite DBs
```

Open browser receiving Activity 404 stops Activity only; after reload panel is absent.

---

# NON-GOALS / LIMITATIONS

## 74. Explicit non-goals

Do not add:

```text
graphs
per-client/AP/SSID Traffic UI
Traffic peaks
WAN/Channel Load
new/returning devices
unique people
Visit duration analytics
Devices by AP 24h
System Health
Omada control/write actions
new acquisition
Observation schema/worker changes
Grafana/Loki Home queries
browser persistence
WebSocket/SSE
```

---

## 75. Accepted v1 limitations

Intentional:

```text
Traffic = estimated completed-session report
Traffic attributed at session end
no interval clipping of bytes
active sessions absent until offline event
combined Traffic only
not Internet-only
no charts
```

These are not defects when the UI shows the mandatory semantics.

A future dedicated Traffic page may later own charts, AP/client/SSID breakdowns, peaks, source reconciliation and any future interval-clipped/rollup traffic architecture.

---

# REVIEW / STATUS

## 76. Genuine unresolved Owner decisions

No blocking source/time/API decision remains in this DRAFT.

Non-blocking presentation choices only:

```text
final localized panel title
exact helper-copy wording
whether an “All available” convenience preset is later added
```

These do not change the architecture.

---

## 77. Tech Lead review questions

Please review these already-selected decisions:

1. `HOME-TODAY-01` absorbed by `HOME-ACTIVITY-01`.
2. `visits.started_at` as immutable Visit-opening successful authorization cohort.
3. Opening authorization evidence verification and partial-quality behavior.
4. `visit_source_events` as Site-aware general guest Traffic source.
5. Completed-session end-time attribution with always-visible `Estimated` semantics.
6. Public Traffic as reconciliation-only, not arbitrary-time backend.
7. No arbitrary 31/90-day Activity cap.
8. Existing Admin deadline/query slot as hard safety bound, conditional on long-history benchmark.
9. Explicit prerequisite only if performance proves an index/rollup necessary.
10. One combined Today+Selected endpoint.
11. `admin.read.overview` capability.
12. Site-specific timezone/SSID context isolated from core Admin readiness.
13. Shared coordinator Phase C and Activity-only picker Apply.
14. Targeted-vs-full-suite responsibility matching current `AGENTS.md`.

Targeted corrections are expected if needed. Product semantics should not be reopened without a factual source conflict.

---

## 78. Current authorization status

```text
TASK:
TASK-HOME-ACTIVITY-01-DRAFT

STATUS:
DRAFT FOR OWNER / TECH LEAD REVIEW

IMPLEMENTATION:
NOT GRANTED

BRANCH:
NOT GRANTED

CODE:
NOT GRANTED

COMMIT:
NOT GRANTED

PUSH:
NOT GRANTED

PR:
NOT GRANTED

MERGE:
NOT GRANTED

DEPLOYMENT:
NOT GRANTED

PRODUCTION ACTIVATION:
NOT GRANTED
```

Only next allowed action:

```text
Owner / Tech Lead review
```

---

## 79. Final DRAFT architecture statement

```text
Visit Lifecycle persisted facts
  ├─ Visit-opening successful authorization
  └─ Site/SSID completed-session reported traffic
            ↓
HomeActivityReadService
            ↓
AdminQueryService
            ↓
Site-scoped Admin Activity summary
            ↓
existing shared Home coordinator
            ↓
Today vs Selected Period
```

This introduces:

```text
no Omada request
no collector
no new source DB
no source schema change
no Observation change
no AuthSession counting
no raw-Mbps-to-bytes conversion
no AP-wide guest/WAN relabeling
no arbitrary 31-day limit
```

The only conditional implementation gate is proof that the longest retained-history aggregate remains bounded under the existing Admin deadline. If it does not, the correct next step is an explicit prerequisite, not a hidden time-range reduction.
