# TASK-HOME-LIVE-01 — Admin Console Home Live — FINAL

**Project:** CaptivPortal  
**Parent product concept:** `TASK-HOME-01 — Admin Console Home v1`  
**Dependency:** `TASK-HOME-CURRENT-STATE-01 — PRODUCTION / ACCEPTED`  
**Type:** master architecture / coder-ready implementation specification  
**Status:** `FINAL FOR SHORT TECH LEAD CONTROL REVIEW`  
**Implementation authorization:** `NOT GRANTED`  
**Branch authorization:** `NOT GRANTED`  
**Commit / push / PR authorization:** `NOT GRANTED`  
**Production activation:** separate Owner-controlled step  
**Architecture baseline:** `origin/main@a864dfa78461ccbfe88e110b1aa5bad5f6bfa23e`  
**Baseline re-check:** 2026-08-23 — unchanged  
**Prepared:** 2026-08-23  
**Tech Lead review basis:** `ARCHITECTURE DIRECTION — PASS / RETURN FOR TARGETED REVISION`  
**Revision result:** all mandatory Tech Lead corrections incorporated; no A/B architecture choices remain for Coder.

---

# 1. Purpose

Implement the first live operational product increment of CaptivPortal Admin Console Home.

The already accepted Current Network State layer is the sole live/current-state source.

Canonical path:

```text
Omada
  ↓
already-running Current State collectors
  ↓
current_state.sqlite3
  ↓
CurrentStateReadService
  ↓
AdminQueryService
  ↓
authenticated Site-scoped /admin/api/v1
  ↓
Home Live controller
  ↓
Admin Console Home
```

`HOME-LIVE-01` does not collect, does not mutate, and does not call Omada.

The page must answer:

```text
How many scoped devices are online now?
How many are authorized?
How many are waiting for authorization?
Are Other / Unknown states present?
How are current clients distributed by AP?
How many Site APs are known Online / Other / Unknown?
Which scoped devices are online now?
How old are the Client and AP snapshots independently?
```

---

# 2. Product outcome

When Home Live is enabled, the Home page contains:

```text
Top:
  Online Now
  Authorized
  Waiting Authorization
  Other / Unknown
  AP Online / Total

Source state:
  Client observed_at / age / freshness
  AP observed_at / age / freshness

Current sections:
  Devices by AP — Now
  Access Points Now
  Online Devices
```

Existing sections remain available elsewhere and must not regress:

```text
Devices
Device Card
Visits
Observations
```

---

# 3. Explicit out of scope

Do NOT implement:

```text
Current Traffic
Channel Load / Internet Load
Today / Connected Today
Today traffic
System Health matrix
Devices by AP — 24h
new Visit Analytics
new Wireless Analytics
Grafana/Loki product queries
WebSocket/SSE
new collector
new Omada polling
new Current State schema
new Current State source semantics
write operations
Omada control actions
tenant/RBAC implementation
```

Reserved follow-up tasks:

```text
HOME-TRAFFIC-01
HOME-TODAY-01
HOME-HEALTH-01
HOME-AP-24H-01
```

---

# 4. Accepted production baseline

Current State is production accepted at:

```text
a864dfa78461ccbfe88e110b1aa5bad5f6bfa23e
```

Production contract:

```text
CURRENT_STATE_ENABLED=true
Site scope configured by Current State
Client SSID scope configured by exact allowlist
Client polling=60s
AP polling=60s
Retention=48h
Client-row hard cap=5,000,000
```

Accepted source performance:

```text
CurrentStateReadService p95 = 4.570 ms
maximum                     = 5.741 ms
```

Accepted snapshot evidence included:

```text
Online      18
Authorized  11
Pending      7
Other        0
Unknown      0
AP Unknown   0

AP total     2
AP online    2
```

Accepted invariants:

```text
Online
=
Authorized + Pending + Other + Unknown

Online
=
sum(known AP buckets) + AP Unknown
```

---

# 5. Authoritative Current State read operations

The accepted source already exposes:

```python
get_current_client_summary(
    site_id,
    *,
    evaluated_at_utc=None,
)

list_current_clients(
    site_id,
    *,
    cycle_id=None,
    limit=100,
    cursor=None,
    sort="controller_traffic_total_desc",
    auth_classification=None,
    ap_mac=None,
    ssid=None,
    evaluated_at_utc=None,
)

get_current_ap_summary(
    site_id,
    *,
    evaluated_at_utc=None,
)

list_current_aps(
    site_id,
    *,
    cycle_id=None,
    limit=100,
    cursor=None,
    evaluated_at_utc=None,
)
```

`HOME-LIVE-01` does not add a second current-state selection algorithm.

---

# 6. Snapshot-selection semantics

Current values are exact only from:

```text
result = success
AND
complete = true
```

A newer:

```text
partial
failed
shutdown
```

attempt does not replace the latest complete snapshot.

The source may expose the latest attempt separately.

If no complete snapshot exists:

```text
freshness_status=unavailable
```

If the latest complete snapshot is older than its unavailable threshold:

```text
freshness_status=unavailable
```

Old rows are not product-current.

Admin must not reconstruct exact counts from partial rows.

---

# 7. Freshness contract

Client:

```text
fresh:       age <= 60s
stale:       60s < age <= 180s
unavailable: age > 180s
```

AP:

```text
fresh:       age <= 90s
stale:       90s < age <= 300s
unavailable: age > 300s
```

Source age is based on:

```text
capture_started_at
```

Client and AP watermarks remain independent.

Forbidden:

```text
one combined fake "Updated" timestamp
```

---

# 8. Client population semantics

Current client population means:

```text
active=true
wireless=true
Site = selected Site
SSID ∈ exact Current State configured client allowlist
```

It means devices/clients, not people.

Runtime code must not hardcode production Site or SSID.

The API exposes safe source-scope metadata so the population is inspectable.

---

# 9. AP population semantics

AP current population means:

```text
all AP inventory rows of selected Site
```

It is not restricted by the client SSID allowlist.

Therefore:

```text
Client scope != AP scope
```

by design.

---

# 10. Permanent architecture boundaries

## 10.1 Data Acquisition / Analytics Boundary

```text
HOME-LIVE reads.
HOME-LIVE does not collect.
```

Forbidden:

```text
Home → Omada
Admin API → Omada
AdminQueryService → Omada
Home → Observation DB to rebuild current clients
Home → Registry/Visit to rebuild current clients
Home → Loki/Grafana
```

## 10.2 Product / Observability Boundary

Product may show:

```text
current counts
current client context
current AP context
source scope
snapshot freshness
high-level latest-attempt state
```

Product does not show:

```text
SQLite path
raw SQL
stack trace
provider payload
tokens
raw failure_category
internal exception message
```

## 10.3 Future Multi-Site Compatibility

Every read is Site-scoped.

Mandatory:

```text
no cross-Site cursor
no cross-Site MAC matching
no hidden default Site inside source calls
no tenant_id
Tenant != Site
```

---

# 11. Existing Admin security remains authoritative

Do not redesign:

```text
AdminPrincipal
Admin session store
pre-auth CSRF
login rate limiting
HTTPS boundary
allowed source networks
Site resolver
Admin access policy
security headers
CSP
query-string stripping in access logs
```

Browser uses:

```text
Admin session cookie
```

Browser must never receive/use the Analytics 02A bearer.

---

# 12. Feature activation boundary

Introduce:

```text
WEB_ADMIN_HOME_LIVE_ENABLED=false
```

Repository-safe default:

```text
false
```

Hard invariant:

```text
WEB_ADMIN_HOME_LIVE_ENABLED=true
requires
WEB_ADMIN_ENABLED=true
```

Reason:

```text
merge/deploy != product activation
```

When false:

```text
legacy Home only
no Home Live timers
no Home Live listeners
no Home Live API requests
```

When true:

```text
Live Home only
legacy Home Runtime/Visits-24h/Devices-24h requests are not executed
legacy Home cards are not rendered
```

---

# 13. Home Live configuration

Add repository-safe settings:

```text
WEB_ADMIN_HOME_LIVE_ENABLED=false
WEB_ADMIN_HOME_LIVE_REFRESH_SECONDS=60
WEB_ADMIN_HOME_LIVE_REQUEST_TIMEOUT_SECONDS=20
WEB_ADMIN_CURRENT_STATE_PAGE_SIZE=100
```

Validation:

```text
HOME_LIVE_ENABLED:
  exact boolean

HOME_LIVE_REFRESH_SECONDS:
  integer 60..300

HOME_LIVE_REQUEST_TIMEOUT_SECONDS:
  integer 5..60

CURRENT_STATE_PAGE_SIZE:
  integer 1..250
```

Cross-field invariant:

```text
WEB_ADMIN_HOME_LIVE_REQUEST_TIMEOUT_SECONDS
>
WEB_ADMIN_MAX_QUERY_DURATION_SECONDS
```

Current repository values therefore require:

```text
20 > 10
```

---

# 14. Exact feature-context delivery to browser

Safe path:

```text
AdminWebConfig
→ render_admin_page(...)
→ admin/home.html / reviewed data-* attributes
→ Home Live controller
```

Home receives only safe values:

```text
home_live_enabled
home_live_refresh_seconds
home_live_request_timeout_seconds
current_state_page_size
```

No secret is placed in HTML.

JS does not discover feature state by probing endpoints.

When feature is false:

```text
Home JS executes legacy Home flow only.
```

When feature is true:

```text
Home JS executes Home Live flow only.
```

Home subtitle is conditional:

Feature false:

```text
existing legacy wording
```

Feature true:

```text
Current network state for the selected Site.
```

The old subtitle:

```text
Health and a compact 24-hour Site summary.
```

must not remain visible for Live Home.

---

# 15. Runtime composition

Current State already starts before Admin Web composition.

Pass exactly:

```text
_current_state_runtime.read_service
```

to Admin Web as an optional read dependency.

Preferred contract:

```python
create_admin_web_runtime(
    settings,
    analytics_runtime,
    registry_read_service,
    visit_read_service,
    observation_read_service,
    logger,
    *,
    current_state_read_service=None,
)
```

No Admin code may dereference:

```text
Current State repository
Current State config path
Current State provider
Current State worker
Current State DB path
```

---

# 16. Optional-source construction boundary

Current State must NOT participate in the existing mandatory Admin `source_ready` gate.

Required composition:

```text
1. Existing mandatory Admin sources are evaluated exactly as before.
2. Existing AdminQueryService is constructed exactly as before.
3. Optional current_state_read_service is stored/injected.
4. Its absence/malformed state affects only four new Live methods.
5. Legacy Admin runtime and pages remain active.
```

Therefore:

```text
current_state_read_service=None
```

must not cause:

```text
AdminWebRuntime.state=unavailable
```

if legacy Admin dependencies are healthy.

A poison optional source object must not be touched during legacy Admin construction.

---

# 17. AdminQueryService integration

Add optional Current State source.

Conceptual methods:

```python
current_client_summary(principal, site_id)

list_current_clients(
    principal,
    site_id,
    *,
    cycle_id=None,
    limit=None,
    cursor=None,
    sort=None,
    auth_classification=None,
    ap_mac=None,
    ssid=None,
)

current_ap_summary(principal, site_id)

list_current_aps(
    principal,
    site_id,
    *,
    cycle_id=None,
    limit=None,
    cursor=None,
)
```

No SQL.

No Omada.

No repository opening.

---

# 18. Capability mapping

Chosen FINAL mapping:

```text
Client summary:
  admin.read.overview

AP summary:
  admin.read.overview

AP current page:
  admin.read.overview

Client current page / Online Devices:
  admin.read.devices
```

Reason:

Online Devices contains endpoint identity such as MAC/IP.

AP overview remains minimal and does not expose technical AP detail fields.

Coder must not invent a different capability mapping.

---

# 19. Deadline decision — FINAL

Chosen architecture:

```text
OPTION A ACCEPTED FOR HOME-LIVE-01
```

Current State reads are a narrow bounded exception to in-query cancellation.

For every Current State source call:

```python
deadline.require_remaining()
result = current_state_read_service.<method>(...)
deadline.require_remaining()
```

Both checks are mandatory.

This does NOT claim:

```text
SQLite query cancellation while source method is executing
```

Reason for acceptance:

```text
bounded indexed current snapshot reads
bounded page size
no historical scan
production p95 4.570 ms
production max 5.741 ms
```

Coder must not change `app/current_state/**` to add Analytics `QueryDeadline`.

Known limitation is recorded in this FINAL.

---

# 20. Query concurrency

All four methods use the existing:

```text
WEB_ADMIN_MAX_CONCURRENT_QUERIES
```

non-blocking semaphore.

No second Home-specific server queue.

No slot:

```text
429
Retry-After: 1
```

---

# 21. Error classification — FINAL

Do not use blanket:

```text
CurrentStateValidationError → 400
```

## 21.1 Admin-owned caller validation before source call

Examples:

```text
Site syntax/authorization
limit
sort
auth filter
AP MAC
SSID filter
cycle_id syntax
cursor length
query parameter schema
```

Result:

```text
400 invalid_request
```

## 21.2 Source summary/integrity validation

Any `CurrentStateValidationError` from summary/integrity path, including persisted invariant failures:

```text
persisted auth count invariant failed
persisted AP count invariant failed
```

Result:

```text
503 source_unavailable
```

## 21.3 Source page caller-context validation

A `CurrentStateValidationError` from page path is mapped to 400 only when its cause is an allowlisted, unambiguous caller context violation from the accepted source contract, for example:

```text
cursor malformed
cursor Site changed
cursor cycle changed
cursor source scope changed
cursor context/sort/filter changed
invalid caller cycle context
```

The internal classifier may use a strict reviewed allowlist of current source validation reasons.

It must NOT return/log the raw source exception string.

Any non-allowlisted page `CurrentStateValidationError`:

```text
503 source_unavailable
```

## 21.4 Storage/read failure

```text
sqlite3.Error
safe OSError/current source open failure
schema/read failure
```

Result:

```text
503 source_unavailable
```

## 21.5 Programming error

Unexpected programmer exception:

```text
500 internal_error
```

sanitized.

No source exception text, DB path or raw SQL is returned.

---

# 22. Dedicated Current State limit validator

Do not reuse the current helper whose maximum is tied to default.

Required contract:

```text
default = 100
hard max = 250
```

Independent validation path:

```text
limit omitted → 100
limit=1       → accepted
limit=100     → accepted
limit=101     → accepted
limit=250     → accepted
limit=251     → 400
limit=0       → 400
```

Canonical integer text only.

Reject examples:

```text
+1
01
1.0
1e2
whitespace-padded integer
boolean
```

unless the existing Admin canonical-integer convention explicitly already accepts the exact representation.

FINAL intent:

```text
no ambiguous/non-canonical integer coercion
```

---

# 23. Admin API namespace

Register exactly four GET routes:

```text
GET /admin/api/v1/sites/{site_id}/current-state/clients/summary

GET /admin/api/v1/sites/{site_id}/current-state/clients

GET /admin/api/v1/sites/{site_id}/current-state/aps/summary

GET /admin/api/v1/sites/{site_id}/current-state/aps
```

Use existing:

```text
api_version=admin.read.v1
```

No second API version.

---

# 24. Feature-disabled route order

The four routes are registered even when Home Live is disabled.

Reason:

```text
canonical JSON 404
not Flask HTML 404
```

Disabled order:

```text
HTTPS/network/request-size boundary
→ Admin session
→ Site syntax/allowlist
→ required capability
→ feature flag
→ 404 not_found
```

Only when feature is enabled:

```text
→ endpoint-specific query validation
→ Current State read
```

This prevents query-schema probing while feature is disabled.

After feature gate:

```text
Current State is not called when disabled.
```

---

# 25. Client summary endpoint

```text
GET /admin/api/v1/sites/{site_id}/current-state/clients/summary
```

Query parameters:

```text
none
```

Capability:

```text
admin.read.overview
```

Source:

```text
get_current_client_summary(site_id)
```

---

# 26. Client summary DTO

Result:

```json
{
  "snapshot": {
    "kind": "client",
    "cycle_id": "<uuid-or-null>",
    "evaluated_at": "<UTC>",
    "observed_at": "<UTC-or-null>",
    "capture_finished_at": "<UTC-or-null>",
    "age_seconds": 12.5,
    "freshness_status": "fresh",
    "freshness_reason": "within_freshness_window",
    "complete": true,
    "source_scope_version": 1,
    "source_scope_hash": "<sha256-or-null>",
    "source_scope": {
      "scope_type": "client_ssid_allowlist",
      "site_id": "<site_id>",
      "ssids": ["..."]
    },
    "latest_attempt_result": "success",
    "latest_attempt_at": "<UTC-or-null>",
    "latest_partial_cycle_id": null
  },
  "freshness_policy": {
    "fresh_max_age_seconds": 60,
    "unavailable_after_seconds": 180
  },
  "counts": {
    "online": 18,
    "authorized": 11,
    "pending": 7,
    "other": 0,
    "unknown": 0,
    "other_unknown": 0,
    "ap_unknown": 0
  },
  "devices_by_ap": [
    {
      "ap_mac": "AA:BB:CC:DD:EE:FF",
      "client_count": 10
    }
  ]
}
```

`source_scope` uses an explicit serializer allowlist:

Client:

```text
scope_type
site_id
ssids
```

No generic `dict(source_scope)` publishing future keys.

---

# 27. Client summary unavailable semantics

If source is readable but no current exact value is valid:

```text
HTTP 200
freshness_status=unavailable
```

Counts:

```text
online=null
authorized=null
pending=null
other=null
unknown=null
other_unknown=null
ap_unknown=null
```

`devices_by_ap=[]`.

Do not convert unavailable to zero.

Storage/read failure remains:

```text
503 source_unavailable
```

---

# 28. Client exact invariants

For non-null counts:

```text
online
=
authorized + pending + other + unknown
```

and:

```text
online
=
sum(devices_by_ap.client_count) + ap_unknown
```

Backend serializer checks these invariants before returning 200.

Invariant failure:

```text
503 source_unavailable
```

not 400.

Frontend checks again before rendering.

---

# 29. Client page endpoint

```text
GET /admin/api/v1/sites/{site_id}/current-state/clients
```

Allowed query parameters:

```text
cycle_id
limit
cursor
sort
auth_classification
ap_mac
ssid
```

Capability:

```text
admin.read.devices
```

Unknown/duplicate parameter:

```text
400 invalid_request
```

---

# 30. Client sort contract

Allowed sort keys and exact source order:

```text
client_mac
  → MAC ascending

controller_uptime
  → descending, null last

controller_traffic_total_desc
  → descending, null last

controller_traffic_down
  → descending, null last

controller_traffic_up
  → descending, null last

auth_status
  → ascending

ap
  → ascending, null last

rssi
  → descending, null last

snr
  → descending, null last
```

Default:

```text
controller_traffic_total_desc
```

Frontend labels include direction.

No ambiguous label such as only:

```text
RSSI
```

when a sort action is shown.

Example:

```text
RSSI — highest first
MAC — A→Z
```

---

# 31. Client filters

Allowed:

```text
auth_classification:
  authorized
  pending
  other
  unknown

ap_mac:
  canonical MAC

ssid:
  exact source SSID
```

SSID semantics:

```text
case-sensitive
no trim
no case-fold
no Unicode normalization
no comma splitting
```

Empty rejected.

Bounded by Admin filter length.

Do not use a helper that strips the SSID.

---

# 32. Client cycle pinning

Logical Home refresh:

```text
Client Summary
→ selected client cycle_id
→ Client Page(cycle_id=<same>)
```

Cards and first table page therefore represent one exact Client snapshot.

Load More cursor stays pinned to that snapshot.

---

# 33. Explicit cycle/cursor-not-found semantics

This distinction is mandatory.

## 33.1 No explicit pin

Request has no `cycle_id` and no `cursor`.

No current complete snapshot:

```text
HTTP 200
freshness=unavailable
items=[]
```

## 33.2 Explicit `cycle_id`

Caller supplied `cycle_id`.

After source returns, Admin verifies:

```text
returned snapshot.cycle_id == requested cycle_id
```

If not:

```text
400 invalid_request
```

This includes:

```text
cycle expired by retention
cycle disappeared
cycle no longer selectable
cycle crossed unavailable threshold for current-page use
```

## 33.3 Explicit cursor

Caller supplied `cursor`.

If source cannot continue the cursor-selected snapshot and returns no selected cycle/current unavailable page:

```text
400 invalid_request
```

No silent fallback to newest page.

UI response:

```text
discard current pagination
hide previously appended current rows
start one clean logical refresh
```

No infinite retry.

---

# 34. Client cursor contract

Cursor is opaque to browser.

Admin does not publish its internals.

Source already binds cursor to:

```text
endpoint
Site
cycle
scope
sort
filters
keyset position
```

Admin enforces existing max cursor length before source call.

Do not log cursor.

---

# 35. Client item DTO — FINAL minimized

Expose only fields consumed by Home v1:

```text
client_mac
name
hostname
ip
ssid
ap_name
ap_mac
band
rssi
snr
controller_uptime
controller_traffic_down
controller_traffic_up
controller_traffic_total
auth_classification
```

Do NOT expose unused v1 fields merely for future use:

```text
device_type
radio_id
channel
auth_status_code
active
wireless
raw source row
```

Before serialization, backend verifies source row internal identity:

```text
item.site_id == authorized Site
item.cycle_id == selected snapshot cycle
item.ssid belongs to serialized snapshot source_scope.ssids
```

Mismatch:

```text
503 source_unavailable
```

Internal Site/cycle fields are then removed from DTO.

---

# 36. Client page response

```json
{
  "snapshot": {
    "...": "safe client snapshot metadata"
  },
  "freshness_policy": {
    "fresh_max_age_seconds": 60,
    "unavailable_after_seconds": 180
  },
  "items": [
    {
      "client_mac": "AA:BB:CC:DD:EE:FF",
      "name": "device",
      "hostname": "host",
      "ip": "192.0.2.10",
      "ssid": "Example",
      "ap_name": "AP-1",
      "ap_mac": "11:22:33:44:55:66",
      "band": "5GHz",
      "rssi": -61,
      "snr": 31,
      "controller_uptime": 1234,
      "controller_traffic_down": 100000,
      "controller_traffic_up": 50000,
      "controller_traffic_total": 150000,
      "auth_classification": "authorized"
    }
  ]
}
```

Page:

```json
{
  "limit": 100,
  "next_cursor": "<opaque-or-null>",
  "cycle_id": "<selected-cycle-or-null>",
  "source_scope_hash": "<selected-scope-hash-or-null>"
}
```

---

# 37. AP summary endpoint

```text
GET /admin/api/v1/sites/{site_id}/current-state/aps/summary
```

Query parameters:

```text
none
```

Capability:

```text
admin.read.overview
```

Source:

```text
get_current_ap_summary(site_id)
```

---

# 38. AP product status mapping — FINAL

Only source `online` has accepted product meaning.

Product mapping:

```text
product.online = source.online_count

product.unknown = source.unknown_count

product.other =
    source.other_count
  + source.offline_count
```

Therefore product invariant:

```text
AP Total
=
Online + Other + Unknown
```

For AP item:

```text
source online  → product Online
source unknown → product Unknown

source other   → product Other
source offline → product Other
any future non-online/non-unknown classification
               → product Other
```

Never show product label:

```text
Offline
```

until separate evidence/review.

Raw source future `offline` is not leaked.

---

# 39. AP summary DTO

```json
{
  "snapshot": {
    "kind": "ap",
    "...": "safe AP snapshot metadata"
  },
  "freshness_policy": {
    "fresh_max_age_seconds": 90,
    "unavailable_after_seconds": 300
  },
  "counts": {
    "total": 2,
    "online": 2,
    "other": 0,
    "unknown": 0
  }
}
```

`source_scope` allowlist for AP:

```text
scope_type
site_id
```

No raw future keys.

Backend validates:

```text
total = online + other + unknown
```

after product mapping.

---

# 40. AP page endpoint

```text
GET /admin/api/v1/sites/{site_id}/current-state/aps
```

Allowed query parameters:

```text
cycle_id
limit
cursor
```

Capability:

```text
admin.read.overview
```

Default:

```text
100
```

Hard max:

```text
250
```

---

# 41. AP item DTO — FINAL minimized

Because capability is:

```text
admin.read.overview
```

AP item exposes only:

```text
ap_mac
name
product_status_classification
```

Do NOT expose in HOME-LIVE-01:

```text
IP
model
firmware
raw status code
last_seen
controller uptime
uptime_raw
```

Those require a different policy/read use case.

Backend first validates internal source row:

```text
item.site_id == authorized Site
item.cycle_id == selected AP cycle
```

Then emits minimal DTO.

---

# 42. AP cycle pinning

Logical Home refresh:

```text
AP Summary
→ selected AP cycle_id
→ AP Page(cycle_id=<same>)
```

AP page explicit missing-cycle semantics match Client page:

```text
no explicit pin + no current snapshot
→ 200 unavailable

explicit pin cannot be continued
→ 400 invalid_request
```

---

# 43. Independent pagination contexts

Home Live has two independent paginations:

```text
Client pagination:
  client_cursor
  Client Load More

AP pagination:
  ap_cursor
  AP Load More
```

Forbidden:

```text
one shared context.cursor
one shared #pagination
one shared Load More control
```

Each list tracks:

```text
generation
selected cycle
selected scope hash
next cursor
loading flag
```

---

# 44. AP enrichment states

`Devices by AP — Now` client buckets are authoritative from Client summary.

AP inventory only enriches them.

For each known client AP MAC:

```text
matched
not_yet_loaded
absent_after_exhaustion
ap_source_unavailable
```

Rules:

## matched

Matching AP has been loaded from selected AP cycle.

Show:

```text
AP name
AP MAC
client count
product AP status
```

## not_yet_loaded

AP is not in loaded AP rows AND:

```text
ap_next_cursor != null
```

Show:

```text
AP details not loaded
```

Do NOT show:

```text
Unknown AP health
AP absent
```

## absent_after_exhaustion

AP list for selected snapshot is exhausted:

```text
ap_next_cursor = null
```

and MAC was never found.

Show neutral:

```text
AP inventory entry not present in selected snapshot
```

No inference of Offline.

## ap_source_unavailable

Client count remains valid.

AP detail/status enrichment is unavailable.

---

# 45. Access Points Now pagination presentation

Access Points Now shows loaded AP rows.

If not exhausted:

```text
Showing N of Total
```

Example:

```text
Showing 100 of 238
```

AP with zero scoped clients remains visible among loaded AP rows.

Additional AP pages are loaded only by explicit AP `Load More`.

Normal full refresh does not auto-walk all AP pages.

---

# 46. Client/AP join key

Only:

```text
canonical AP MAC
```

Never AP name.

Client AP-null remains separate:

```text
AP Unknown
```

using `ap_unknown`.

---

# 47. Independent watermarks

UI renders:

```text
Clients:
  observed_at
  age
  freshness

APs:
  observed_at
  age
  freshness
```

A browser page refresh timestamp may be displayed separately.

It is not source observation time.

---

# 48. Home top layout

Top cards:

```text
Online Now
Authorized
Waiting Authorization
Other / Unknown
AP Online / Total
```

Each source group has its own freshness indicator.

No historical 24-hour cards while Live flag is true.

---

# 49. Product card semantics

## Online Now

```text
counts.online
```

## Authorized

```text
counts.authorized
```

## Waiting Authorization

```text
counts.pending
```

## Other / Unknown

Main:

```text
counts.other_unknown
```

Secondary:

```text
Other X · Unknown Y
```

## AP Online / Total

```text
Online / Total
```

Secondary:

```text
Other X · Unknown Y
```

No `Offline`.

---

# 50. Freshness UI

Allowed source statuses:

```text
fresh
stale
unavailable
```

Fresh:

```text
show exact current values
```

Stale:

```text
show exact last complete values
visibly label STALE
show age/observed_at
```

Unavailable:

```text
hide current values
show — / Unavailable
```

Do not keep old numeric values current-looking.

---

# 51. Latest attempt warning

If latest attempt result is any non-success:

```text
partial
failed
shutdown
```

while a prior complete snapshot remains fresh/stale, show generic:

```text
Latest collection attempt did not complete successfully;
showing the latest complete snapshot.
```

Do not expose raw failure category.

Do not special-case `shutdown` away.

---

# 52. Browser-side age progression

API returns:

```text
age_seconds
freshness_policy
```

Browser uses:

```javascript
performance.now()
```

after response acceptance.

Displayed age:

```text
server age_seconds
+
monotonic elapsed time
```

Transitions locally:

```text
fresh → stale
stale → unavailable
```

without requiring another response.

At unavailable threshold:

```text
current values are hidden
```

This prevents a failed network refresh from leaving a permanent Fresh badge.

---

# 53. Dedicated Home Live controller

Do NOT route Home Live through the existing destructive generic:

```text
run() → showFailure() → content.replaceChildren()
```

Create a separate Home Live controller/state machine.

Minimum independent DOM/state sections:

```text
global session/authorization state

Client summary/cards
Devices by AP
Client table
Client pagination/status

AP summary/card
AP list
AP pagination/status

short live announcement
```

Independent failures do not clear unrelated sections.

401 is global.

---

# 54. Home Live state model

Minimum states:

```text
initial_loading
refreshing
ready_fresh
ready_stale
empty
source_unavailable
request_error
busy
invalid_pinned_state
session_expired
site_forbidden
feature_disabled
unexpected_response
```

Client and AP source states are independent where applicable.

---

# 55. Initial loading and empty

Initial loading:

```text
no fabricated zero
```

Valid exact zero Client snapshot:

```text
Online=0
Authorized=0
Waiting=0
Other/Unknown=0
```

Online Devices:

```text
No online devices in the current scope.
```

Exact zero is not unavailable.

---

# 56. Logical refresh architecture

A new logical Home refresh creates:

```text
refresh_generation += 1
```

and captures:

```text
generation
Site
current sort/filter state
```

When both sources are eligible, a full normal refresh has exactly four initial GET operations:

```text
Client Summary
AP Summary
Client Page pinned to Client Summary
AP Page pinned to AP Summary
```

Summary phase may run independently/in parallel.

Pinned page request occurs only after valid summary for that source.

If a source is in error backoff, a scheduled refresh may execute only the healthy source group; therefore the per-tick request count can be lower than four.

No automatic AP full-pagination walk.

---

# 57. Generation / transaction guard

Every async Home operation captures:

```text
refresh_generation
```

A response is discarded if its generation is no longer current.

For Client/AP Load More, capture additionally:

```text
site_id
cycle_id
source_scope_hash
cursor used
sort/filter context
```

Before append:

```text
generation still current
Site still current
cycle still current
scope still current
sort/filter still current
cursor still belongs to current list state
```

Otherwise:

```text
discard
```

Never append old-cycle rows after a new refresh.

Sort/filter change:

```text
starts new generation
cancels current relevant requests
clears both affected page state/cursor
requests a clean pinned first page
```

---

# 58. New summary + failed pinned page

Never show:

```text
new summary cards
+
old table rows
```

as one current snapshot.

When a newer summary is accepted:

```text
old corresponding page/list rows are hidden/cleared immediately
```

Then if pinned page fails:

```text
summary remains visible
table/list section shows its own error
```

The old table may not remain visible without an explicit old watermark.

FINAL choice:

```text
hide/clear old rows.
```

Coder must not choose another behavior.

---

# 59. Browser request timeout and cancellation

Configured:

```text
WEB_ADMIN_HOME_LIVE_REQUEST_TIMEOUT_SECONDS=20
```

Every Home Live fetch uses:

```text
AbortController
```

Timeout behavior:

```text
abort request
release in-flight state in finally
classify as retryable timeout
```

Always clear:

```text
timeout handle
controller reference
in-flight flag
```

in `finally`.

On:

```text
pagehide
```

abort all Home requests.

On:

```text
document.hidden=true
```

abort unfinished Home auto/manual refresh requests as:

```text
neutral cancellation
```

Neutral hidden-tab cancellation:

```text
does not increase failure counters
does not show source failure
does not schedule tight retry
```

Late/aborted/old-generation responses are ignored.

---

# 60. No overlapping operations

Within one source group:

```text
no second summary/page refresh while same group refresh is in flight
```

Within each list:

```text
no second Load More while Load More is in flight
```

A new manual logical refresh may abort superseded Home requests and start a new generation.

No queue of missed timer ticks.

---

# 61. Hidden-tab policy

While hidden:

```text
no automatic Home polling
```

On becoming visible:

If no accepted current render exists:

```text
refresh immediately
```

Else if elapsed since last completed eligible refresh >= refresh interval:

```text
refresh immediately
```

Else:

```text
schedule remaining delay
```

Hidden-tab abort is neutral.

---

# 62. Independent retry/backoff — FINAL

Maintain independent:

```text
client_failure_count
client_next_eligible_at

ap_failure_count
ap_next_eligible_at
```

Backoff per source:

```text
1st retryable failure → 60s
2nd                   → 120s
3rd+                  → 300s max
```

Actual automatic delay:

```text
max(configured refresh interval, source backoff)
```

Success resets only that source counter.

Therefore AP failure must not slow healthy Client refresh.

Client failure must not slow healthy AP refresh.

---

# 63. Manual Refresh — FINAL

Manual Refresh:

```text
visible tab
session valid
feature active
```

starts a new generation.

It attempts both Client and AP source groups immediately once:

```text
even if one/both are currently waiting for automatic backoff
```

It first aborts superseded Home requests.

Each source success/failure updates only its own backoff state.

Manual Refresh cannot create overlapping requests in the new generation.

---

# 64. Global non-retry states

```text
401 session expired
→ stop all Home polling
→ abort Home requests
→ show Sign in

403 Site forbidden
→ stop Home polling for current page
→ show Access denied

404 feature disabled during rollout/rollback
→ stop Live polling
→ abort Live requests
→ show "Live Home is disabled; reload the page."
→ no retry loop
```

---

# 65. Retryable HTTP/network states

Retryable per source:

```text
network error
request timeout
429
503
sanitized 500
```

429:

```text
respect Retry-After
and never retry automatically faster than configured refresh cadence
```

---

# 66. UI-generated 400 handling

A 400 from a query generated by Home itself indicates:

```text
stale cursor/pinned state
or frontend/backend contract defect
```

Behavior:

```text
clear affected cursor/page state
perform exactly one clean logical refresh
```

If clean refresh again produces 400 without user-invalid input:

```text
stop automatic clean-retry loop
show sanitized unexpected state
```

No infinite retry.

User-entered invalid filter value:

```text
show validation state
do not classify as source outage
```

---

# 67. Strict frontend response validation

Before rendering any Live 200 response, validate:

```text
api_version == "admin.read.v1"

root site_id == page Site

snapshot.kind matches endpoint:
  client or ap

freshness_status in:
  fresh|stale|unavailable

age_seconds:
  null
  OR finite non-negative number

counts:
  null where unavailable
  otherwise non-negative integers
  boolean rejected

arrays:
  actual Array

next_cursor:
  null
  OR non-empty bounded string

product status:
  allowlist only
```

Client summary invariants must hold.

AP product invariant must hold.

Pinned page must match:

```text
summary cycle
summary scope hash
page cycle
page scope hash
```

Malformed 200:

```text
do not partially render
do not coerce to zero
section → unexpected/source-integrity state
```

---

# 68. Client/AP page frontend identity validation

Before accepting page items:

Client:

```text
page Site matches current page
page cycle matches pinned Client summary
page scope hash matches pinned Client summary
each item has expected field types
auth_classification allowlisted
SSID belongs to selected Client scope
```

AP:

```text
page Site matches current page
page cycle matches pinned AP summary
page scope hash matches pinned AP summary
product_status_classification in Online|Other|Unknown
```

Any mismatch invalidates that page response.

---

# 69. Online Devices table

Primary columns:

```text
Device / MAC
Auth
IP
AP
Band
RSSI
SNR
```

Device label priority:

```text
name
else hostname
else MAC
```

MAC remains visible.

Secondary controller facts:

```text
Controller uptime
Controller trafficDown
Controller trafficUp
Controller trafficTotal
```

These are rendered as either:

```text
expandable "Controller facts" row section
```

or desktop-only secondary columns.

FINAL preference:

```text
expandable/secondary controller facts;
primary identity/status columns remain readable at narrow widths.
```

No unit is added.

---

# 70. Neutral controller semantics

Until separate evidence:

Allowed labels:

```text
Controller uptime
Controller trafficDown
Controller trafficUp
Controller trafficTotal
```

Forbidden:

```text
Online time
Session duration
Seconds
Minutes
Hours

Download
Upload
Downloaded
Uploaded

Bytes
KB
MB
GB

Speed
Mbps
```

Raw finite integer or `—` only.

Null never becomes 0.

---

# 71. Online Devices accessibility/responsive contract

Use semantic table markup:

```text
caption
thead
tbody
th scope="col"
```

Controls have visible labels.

Keyboard focus is visible.

Auth/status meaning is conveyed by text, not color alone.

If table requires width beyond viewport:

```text
labelled horizontal scroll container
```

must preserve identity/status at:

```text
~560px
~820px
desktop
```

Do not place the entire frequently updating table under broad `aria-live`.

Use a separate short announcement region, e.g.:

```text
"Home updated. 18 devices online."
```

---

# 72. Devices by AP — Now

Source:

```text
Client summary only
```

AP page provides enrichment only.

Display:

```text
AP label/name when matched
AP MAC
client count
AP enrichment state/status
```

Include:

```text
AP Unknown
```

when >0.

Client bucket total + AP Unknown must equal Online.

Simple CSS bars/rows are allowed.

No chart library.

---

# 73. Access Points Now

Show loaded AP items:

```text
name
MAC
product status
current scoped client count
```

Scoped client count is joined from Client summary by AP MAC.

AP with zero scoped clients remains visible.

If list incomplete:

```text
Showing N of Total
```

AP `Load More` is independent from Client `Load More`.

---

# 74. AP filter option source

AP filter for Online Devices is built from union:

```text
Client summary known AP buckets
+
currently loaded AP inventory rows
```

Therefore a client-associated AP remains filterable even when its AP inventory row is not yet loaded due to AP pagination.

No AP disappears from filter solely because AP page is incomplete.

---

# 75. Nullable display

```text
IP null          → —
RSSI null        → —
SNR null         → —
AP null          → AP Unknown
name null        → hostname or MAC
controller fact null → —
```

No null-to-zero conversion.

---

# 76. Auth display

```text
authorized → Authorized
pending    → Waiting
other      → Other
unknown    → Unknown
```

Unknown is not Pending.

Other is not Authorized.

---

# 77. Sort UI

Expose reviewed options with direction in label:

```text
Controller trafficTotal — highest first
Controller uptime — highest first
MAC — ascending
Auth status — ascending
AP — ascending
RSSI — highest first
SNR — highest first
```

Optional:

```text
Controller trafficDown — highest first
Controller trafficUp — highest first
```

Changing sort:

```text
new generation
clear Client cursor/rows
fetch new Client summary
fetch pinned first Client page
```

Do not client-sort only loaded rows while claiming global sort.

---

# 78. Filter UI

Minimum:

```text
Auth:
  All
  Authorized
  Waiting
  Other
  Unknown

AP:
  All
  union of Client buckets + loaded APs
```

SSID control:

```text
may be hidden for single-SSID source scope
may be shown if source scope has multiple SSIDs
```

Filter change starts a clean Client generation/page.

---

# 79. Pagination behavior across auto-refresh

Auto-refresh moves Home to newest accepted current snapshot.

Therefore:

```text
loaded extra Client pages are discarded
loaded extra AP pages are discarded
```

on a new accepted snapshot.

Sort/filter selection may persist.

Cursor does not persist.

This is intentional for a live operational page.

---

# 80. No browser persistence

Home Live must NOT store:

```text
MAC
IP
cursor
cycle_id
source_scope_hash
snapshot
current rows
filter-generated identity state
```

in:

```text
localStorage
sessionStorage
IndexedDB
Cache API
service worker cache
```

Live state exists only in memory of the current page.

All Admin responses remain:

```text
Cache-Control: no-store
```

---

# 81. API data minimization

Rule:

```text
No unused fields in v1 DTO merely for future use.
```

Current v1 Client DTO is section 35.

Current v1 AP DTO is section 41.

Source scope is explicit allowlist.

Future source fields do not automatically become API fields.

Do not use generic source `asdict()` as public serializer.

---

# 82. API serializer boundary

Create explicit safe serializers/converters, e.g.:

```text
CurrentSnapshotMeta → Admin snapshot DTO
CurrentClientSummary → Admin client summary DTO
CurrentClientState → Admin client item DTO
CurrentApSummary → Admin AP product summary DTO
CurrentApState → Admin AP item DTO
```

A small new file is preferred if it keeps route/query code clear:

```text
app/admin_web/current_state_serialization.py
```

Backend validation occurs before data minimization.

---

# 83. API error envelope

Use existing Admin envelope.

Example:

```json
{
  "api_version": "admin.read.v1",
  "request_id": "<uuid>",
  "error": {
    "code": "invalid_request",
    "message": "The request could not be completed."
  }
}
```

Do not include raw source reason.

---

# 84. HTTP status contract

```text
200:
  fresh/stale/unavailable source-quality response

400:
  caller invalid input
  malformed caller cursor
  rejected explicit missing/expired pinned cycle
  one of allowlisted page caller-context violations

401:
  Admin session required/expired

403:
  network/Site/capability forbidden

404:
  Home Live feature disabled after security/Site/capability gate

429:
  Admin query concurrency busy

503:
  source absent
  source integrity failure
  source read/open/schema failure
  summary CurrentStateValidationError
  non-caller page CurrentStateValidationError
  query deadline
  response too large

500:
  unexpected programming error
```

---

# 85. Source missing behavior

Feature true + optional source absent:

```text
four Live endpoints → 503 source_unavailable
```

Home:

```text
Live source unavailable
```

Legacy Admin remains available.

---

# 86. Response-size protection

All four endpoints use existing response-size enforcement.

No bypass.

Configured page size must fit within:

```text
WEB_ADMIN_MAX_RESPONSE_BYTES
```

If exceeded:

```text
503 response_too_large
```

---

# 87. Sensitive access-log boundary

Keep existing query stripping for:

```text
/admin/*
```

Query may contain:

```text
cursor
MAC/AP filters
SSID
```

Never restore raw Admin query string to production access logs.

---

# 88. Route completion telemetry

Add sanitized measurable event:

```text
admin.current_state_query_completed
```

Emit exactly one completion event per new data endpoint request after request classification.

Allowed fields:

```text
request_id
route_name
source_kind=client|ap
site_id
status_code
outcome
reason
duration_ms
item_count
```

`route_name`, `outcome`, `reason` are allowlisted enums, not raw strings from source.

Example route names:

```text
current_client_summary
current_client_page
current_ap_summary
current_ap_page
```

Allowed reason examples:

```text
ok
fresh
stale
source_unavailable
invalid_request
busy
query_deadline
response_too_large
internal_error
feature_disabled
```

Forbidden telemetry fields/content:

```text
client MAC
client IP
AP MAC filter
SSID
cursor
cycle_id
scope hash
raw query string
raw URL
source exception text
DB path
raw item content
```

---

# 89. Telemetry timing

Use monotonic server timing.

`duration_ms`:

```text
finite
non-negative
```

Measure request/query handling consistently around the Admin data operation.

Telemetry must not throw back into route result.

Production performance acceptance requires at least:

```text
20 measurements per endpoint
```

unless Owner/Tech Lead explicitly approves another sample count.

---

# 90. Frontend technology

Keep existing:

```text
Flask
Jinja
plain CSS
vanilla JS
```

Forbidden:

```text
React
Vue
jQuery
Chart.js
external CDN
new npm production dependency
new Python production dependency
```

Dynamic source text uses:

```text
textContent
```

not unsafe `innerHTML`.

---

# 91. Legacy Home fallback

Feature false:

```text
legacy Runtime
Visits · 24 hours
Devices · 24 hours
```

continues.

Feature true:

```text
none of those three legacy Home requests/cards are executed/rendered
```

This avoids mixed historical/live semantics.

---

# 92. Existing page regression boundary

No behavior change to:

```text
Devices
Device Card
Visits
Observations
```

except reviewed shared helpers with regression coverage.

Their routes remain unchanged.

---

# 93. Normal request budget

When both source groups are eligible, one full visible Home refresh uses exactly:

```text
1 Client summary
1 AP summary
1 Client first page
1 AP first page
```

Total:

```text
4 GET
```

Additional Client/AP pages:

```text
manual only
```

and not part of normal refresh budget.

Backoff can reduce a timer tick below four when one source is intentionally not eligible.

These GET requests do not call Omada.

---

# 94. Multiple tabs

Each visible tab may poll independently.

Hidden tabs stop polling.

No new shared browser-refresh server scheduler.

Production acceptance must test:

```text
at least two simultaneous visible Home tabs/sessions
```

If normal use persistently exhausts Admin concurrency:

```text
STOP
return measured evidence
```

Do not silently raise global concurrency in this task.

---

# 95. Performance budgets

Source accepted baseline:

```text
p95 4.570 ms
max 5.741 ms
```

Admin endpoint production targets:

```text
summary p95 <= 100 ms server-side
page p95    <= 250 ms server-side
```

Measured from route completion telemetry.

Do not weaken snapshot correctness to meet budget.

---

# 96. Configuration tests

Minimum:

```text
HOME_LIVE_ENABLED default false
exact boolean validation
feature=true requires WEB_ADMIN_ENABLED=true

refresh default 60
refresh bounds 60..300

request timeout default 20
request timeout bounds 5..60
request timeout > Admin query deadline

Current State page size default 100
page size bounds 1..250

config repr does not leak sensitive values
```

---

# 97. Optional-source/runtime wiring tests

Prove:

```text
run.py passes exact _current_state_runtime.read_service

None optional source does not make legacy Admin unavailable

poison optional source is not dereferenced during legacy Admin construction

feature false does not touch Current State

feature true + missing Current State:
  legacy Admin stays active
  Live endpoints return 503
```

A dedicated test may be added:

```text
tests/admin_web/test_run_wiring.py
```

---

# 98. Deadline tests

For each new query method:

```text
deadline checked before source call
deadline checked after source call
```

Expired before source:

```text
source not called
```

Expired after source:

```text
query_deadline
```

No claim/test of in-query SQLite cancellation.

No Current State package modification.

---

# 99. Error mapping tests

Mandatory:

```text
malformed cursor → 400
invalid caller filter → 400
invalid limit → 400

persisted Client invariant failure → 503
persisted AP invariant failure → 503

sqlite3 read/open failure → 503

non-caller CurrentStateValidationError → 503

unexpected programmer exception → sanitized 500
```

No raw exception string in response/telemetry.

---

# 100. Limit tests

Mandatory:

```text
omitted → 100
1       → accepted
100     → accepted
101     → accepted
250     → accepted
251     → 400
0       → 400
non-canonical integer text → 400
```

---

# 101. Route/security tests

For all four endpoints:

```text
unauthenticated → 401
invalid/disallowed Site → existing canonical 400/403 behavior
missing capability → 403
feature disabled authorized caller → canonical JSON 404
valid enabled request → 200 or source-quality result
```

Feature-disabled test proves:

```text
endpoint-specific query validation is not evaluated before feature 404
Current State not called
```

Duplicate/unknown parameters when enabled:

```text
400
```

---

# 102. Snapshot/cycle tests

Mandatory:

```text
fresh complete
stale complete
unavailable old complete
no complete snapshot

latest partial + prior complete
latest failed + prior complete
latest shutdown + prior complete

partial never replaces exact

explicit missing cycle → 400

cursor-selected cycle expires/disappears
→ 400
→ frontend clears pagination
→ one clean refresh
```

---

# 103. Counter invariant tests

Client:

```text
online =
authorized + pending + other + unknown

online =
known AP buckets + AP Unknown
```

AP product:

```text
total =
online + other + unknown
```

Malformed source invariant:

```text
503
```

not silent correction.

---

# 104. Future AP offline test

Fake source:

```text
total=3
online=1
other=0
offline=1
unknown=1
```

Product:

```text
online=1
other=1
unknown=1
total=3
```

AP item source classification:

```text
offline
```

renders product:

```text
Other
```

Never Offline.

---

# 105. Cursor/context tests

Client:

```text
valid page 1
valid page 2
cross-Site cursor rejected
changed cycle rejected
changed scope rejected
changed sort rejected
changed auth filter rejected
changed AP filter rejected
malformed rejected
overlong rejected
no first-page fallback
```

AP:

```text
valid AP page 1/page 2
cross-Site rejected
changed cycle rejected
changed scope rejected
malformed rejected
overlong rejected
```

Client and AP cursors are proven independent.

---

# 106. AP pagination/enrichment frontend tests

Mandatory:

```text
AP first page incomplete
client-associated AP not loaded
→ not_yet_loaded

after AP list exhausted and still absent
→ absent_after_exhaustion

AP source unavailable
→ ap_source_unavailable

matching AP loaded
→ matched

AP with zero clients remains shown

Showing N of Total shown while incomplete
```

---

# 107. Generation/race tests

Mandatory:

```text
late response from old generation ignored

old Client Load More response after new refresh ignored

old AP Load More response after new refresh ignored

sort change invalidates old Client response

filter change invalidates old Client response

new Client summary + failed pinned page
→ old rows not mixed

new AP summary + failed pinned page
→ old rows not mixed
```

---

# 108. Timeout/cancellation tests

Mandatory:

```text
request timeout aborts fetch
in-flight released in finally

pagehide aborts Home requests

hidden-tab abort is neutral:
  no failure counter increment
  no source error UI

late response after abort ignored
```

---

# 109. Retry/backoff tests

Mandatory:

```text
Client failure does not slow AP
AP failure does not slow Client

Client 60→120→300
AP 60→120→300

source success resets only its own counter

Manual Refresh bypasses automatic backoff once
and attempts both source groups

401 stops all polling

403 stops current Home polling

404 feature rollback stops Live polling

429 respects Retry-After and cadence
```

---

# 110. Strict successful-response tests

Malformed HTTP 200 cases are rejected:

```text
wrong api_version
wrong Site
wrong snapshot kind
unknown freshness status
negative/non-finite age
boolean/non-integer count
Client invariant mismatch
AP invariant mismatch
page cycle mismatch
page scope mismatch
invalid next_cursor type
items not array
unknown product AP status
item Site mismatch
item cycle mismatch
Client item SSID outside source scope
```

No partial render.

---

# 111. Shutdown latest-attempt test

Both Client and AP test:

```text
latest_attempt_result=shutdown
```

with prior fresh/stale complete snapshot.

UI:

```text
generic incomplete-attempt warning
```

No raw shutdown failure category.

---

# 112. DTO minimization tests

Assert exact public keys.

Client item must not expose:

```text
device_type
radio_id
channel
auth_status_code
active
wireless
internal Site/cycle fields
```

AP item must not expose:

```text
IP
model
firmware
raw status_code
last_seen
uptime
```

Source scope must expose only its reviewed keys.

A future unexpected source field must not appear in API.

---

# 113. UI semantic/accessibility tests

Minimum:

```text
semantic table caption
thead
th scope=col
labelled controls
visible status text independent of color
short aria-live announcement
table itself not broad aria-live
responsive scroll container
primary columns preserved
null → —
neutral controller labels
```

Tests must fail if UI uses:

```text
Mbps
Download
Upload
Online time
GB
```

for unverified controller facts.

---

# 114. Feature-flow frontend tests

Feature false:

```text
legacy Home requests execute
Live Home requests/timers/listeners do not
legacy subtitle shown
```

Feature true:

```text
Live Home flow executes
legacy health/24h Home requests do not
live subtitle shown
```

---

# 115. Browser-storage privacy tests

Static/Node tests must prove Home Live does not call:

```text
localStorage.setItem
sessionStorage.setItem
IndexedDB writes
Cache API writes
service worker cache writes
```

for current device/snapshot state.

---

# 116. Direct Omada prohibition test

New Admin Home code must have no dependency on:

```text
OmadaProvider
controller factory
requests
list_observation_clients
list_observation_access_points
```

Only Current State read-service-compatible dependency is injected.

---

# 117. Route telemetry tests

For all outcomes:

```text
success
400
429
503
500
feature-disabled 404
```

verify one sanitized completion event as applicable.

Allowed fields only.

Prove absence of:

```text
MAC
IP
SSID
cursor
cycle_id
scope hash
raw query
exception text
```

`duration_ms` is finite/non-negative.

---

# 118. Existing Admin regression tests

Must remain green:

```text
login/session
legacy Home fallback
Devices
Device Card
Visits
Observations
existing API routes
existing cursor behavior
access-log stripping
security headers
```

---

# 119. Targeted implementation gate

Mandatory:

```bash
python -m pytest -q \
  tests/admin_web \
  tests/current_state \
  --tb=short
```

Run narrower tests first if useful, but this combined gate is mandatory.

---

# 120. Frontend gate

Run existing Admin frontend/Node test mechanism, including:

```text
tests/admin_web/test_admin_ui_frontend.py
```

No production JS dependency added.

---

# 121. Full Linux gate

After targeted success:

```bash
python -m pytest -q -rs

PYTHONPYCACHEPREFIX=/tmp/captivportal-pyc \
  python -m compileall -q app

git diff --check
git status --short
```

Record:

```text
baseline SHA
implementation SHA
Python version
passed
skipped
failed
compileall
diff-check
working tree
```

---

# 122. Pre-change baseline gate

Before first implementation change:

```bash
git fetch origin
git rev-parse origin/main
git status --short

python -m pytest -q -rs

PYTHONPYCACHEPREFIX=/tmp/captivportal-pyc \
  python -m compileall -q app

git diff --check
```

Expected:

```text
a864dfa78461ccbfe88e110b1aa5bad5f6bfa23e
```

If newer, impact review if changes touch:

```text
app/current_state/**
app/admin_web/**
run.py
app/config.py
app/settings.py
tests/current_state/**
tests/admin_web/**
```

---

# 123. Allowed implementation files

Expected Admin files:

```text
app/admin_web/config.py
app/admin_web/runtime.py
app/admin_web/query_service.py
app/admin_web/routes.py
app/admin_web/pages.py
app/admin_web/templates/admin/home.html
app/admin_web/templates/admin/base.html
app/admin_web/static/admin.js
app/admin_web/static/admin.css
```

Optional new safe serializer:

```text
app/admin_web/current_state_serialization.py
```

Narrow config/composition:

```text
app/config.py
app/settings.py
.env.example
run.py
```

Tests:

```text
tests/admin_web/**
```

Allowed dedicated wiring test:

```text
tests/admin_web/test_run_wiring.py
```

---

# 124. Current State is read-only dependency

`app/current_state/**` is NOT an implementation target for this task.

Do not change:

```text
repository
schema
normalizer
worker
collector cadence
retention
freshness thresholds
cursor format
source scope
status classification
```

Coder must not modify Current State for deadline convenience, Home convenience, DTO convenience or UI convenience.

---

# 125. Other forbidden areas

Do not change:

```text
app/observations/**
app/analytics/** metric semantics
app/visit_lifecycle/**
app/visitor_registry/**
app/pending_sessions/**
app/controllers/omada*.py
app/auth/**
app/capport/**
public traffic
portal counter

Nginx
systemd unit/drop-ins
Alloy
Loki
Grafana
Cisco
Omada Controller
production environment during implementation
```

No Knowledge Base files:

```text
AGENTS.md
docs/**
```

in this runtime implementation task.

---

# 126. Coder PLAN requirement

Before broad code changes, Coder returns PLAN with:

```text
1. exact baseline SHA
2. files to change
3. optional CurrentStateReadService wiring
4. feature-config delivery to template/JS
5. four routes
6. route security order
7. capability mapping
8. deadline Option A pre/post checks
9. error classifier design
10. default/max limit validator
11. explicit pinned-cycle verification
12. DTO allowlists
13. AP offline→Other mapping
14. separate Client/AP pagination
15. Home Live controller DOM/state sections
16. generation/AbortController model
17. independent retry/backoff model
18. strict frontend response validation
19. telemetry event design
20. tests
21. no-Omada proof
22. feature-disabled rollback behavior
```

Coder must not reopen architecture choices fixed in this FINAL.

---

# 127. Stop conditions

STOP affected implementation and return facts if:

- `origin/main` materially changed affected contracts;
- Current State source cannot be injected read-only;
- feature flag cannot be delivered without leaking unsafe configuration;
- legacy Admin becomes dependent on Current State;
- Home requires direct Omada call;
- exact counts require partial snapshot;
- source cursor cannot preserve Site/cycle/scope correctness;
- explicit cycle expiry cannot be distinguished safely;
- source exception classification cannot safely separate caller-context vs integrity;
- one AP page is being treated as full AP inventory;
- frontend cannot prevent mixed-generation rows/cards;
- request timeout cannot reliably release in-flight state;
- sensitive route telemetry would be required;
- page size 100 cannot fit response cap;
- two normal Home tabs persistently exhaust Admin query concurrency;
- full suite shows a new product failure;
- implementation requires forbidden source/infrastructure change.

Do not silently broaden scope.

---

# 128. Backend acceptance criteria

PASS requires:

- live source only `CurrentStateReadService`;
- no direct Omada;
- no Current State changes;
- optional source does not gate legacy Admin runtime;
- exact four Site-scoped routes;
- security/capability before disabled feature 404;
- feature-disabled source not touched;
- mandatory pre/post deadline checks;
- correct 400/503/500 classification;
- default 100/hard max 250;
- explicit expired pin gives 400;
- Client exact invariants;
- AP Offline collapsed to Other;
- AP product invariant;
- separate Client/AP cursors;
- minimized DTOs;
- backend Site/cycle/scope item validation;
- response-size guard;
- concurrency guard;
- sanitized route telemetry;
- no MAC/IP/cursor in telemetry/logs.

---

# 129. Frontend acceptance criteria

PASS requires:

- Live top cards;
- separate Client/AP freshness;
- stale visibly stale;
- unavailable hides current values;
- generic partial/failed/shutdown latest-attempt warning;
- independent source failure;
- separate Client/AP Load More controls;
- AP `not_yet_loaded` vs true exhausted absence;
- Access Points `Showing N of Total`;
- generation guard;
- old rows never mixed with new cards;
- AbortController timeout;
- hidden-tab neutral abort;
- per-source backoff;
- global 401/403/404 stop states;
- strict 200 validation;
- no browser persistence;
- responsive/accessibility contract;
- neutral controller fields;
- no legacy Home requests when Live enabled.

---

# 130. Production activation boundary

Merge does not enable feature.

Repository/deploy default:

```text
WEB_ADMIN_HOME_LIVE_ENABLED=false
```

Production activation is a separate Owner-controlled runbook after merged SHA is known.

---

# 131. Production activation runbook requirements

The future exact activation script/runbook MUST include:

```text
1. exact expected merged SHA
2. git clean-tree gate
3. current production branch/HEAD evidence

4. backup /etc/default/captive-portal
   preserving metadata

5. verify environment file safety:
   owner root
   group root
   mode 0600

6. write Home Live variables
7. parse/config dry validation BEFORE restart
8. verify environment file still root:root 0600

9. capture PID before
10. restart captive-portal.service
11. bounded startup gate
12. capture PID after
13. verify active/running

14. Portal smoke
15. CAPPORT smoke
16. Admin login smoke

17. authenticated owner smoke:
    Client summary
    Client page
    AP summary
    AP page

18. verify Client cycle coexistence
19. verify AP cycle coexistence
20. verify Observation cycles continue
21. verify Visit continues
22. verify Registry continues

23. scan journal from activation timestamp only
24. verify no startup/runtime error
25. verify route telemetry exists and is sanitized
```

---

# 132. Automatic activation rollback

The activation script must automatically restore environment backup and restart when any mandatory immediate gate fails:

```text
config dry validation
service restart/startup
service active/running
Portal/CAPPORT/Admin immediate HTTP gate
```

Automatic rollback verifies:

```text
WEB_ADMIN_HOME_LIVE_ENABLED=false
or restored previous environment

legacy Home available
Current State still enabled
Current State DB untouched
```

Do not disable Current State to rollback Home.

Do not delete current_state.sqlite3.

---

# 133. Post-activation browser acceptance

Real owner browser:

```text
Home Live loads
Online exact
Authorized exact
Waiting exact
Other/Unknown exact
AP Online/Total exact

Client freshness visible
AP freshness visible

Devices by AP reconciles to Online
AP Unknown correct

Online Devices works
Access Points works

Client Load More independent
AP Load More independent

null IP → —

sort works
filter works
manual Refresh works

hidden-tab pause/abort works
```

Compare at least one accepted Home snapshot to direct `CurrentStateReadService` output.

Do not use Omada UI as the only truth comparison.

---

# 134. Exact post-activation soak

Minimum browser soak:

```text
5 consecutive automatic visible-tab Home refresh cycles
```

at configured 60-second cadence.

Required during those five cycles:

```text
no overlapping requests
no stale-generation append
no unexpected 400/401/403/404/429/500/503
unless deliberately injected/tested
Client/AP freshness advances correctly
Current State collectors continue
Observation continues
Portal/CAPPORT remain healthy
```

Also test:

```text
1 manual Refresh
1 hidden-tab pause/resume
2 simultaneous visible Home tabs
```

---

# 135. Exact telemetry/performance sample

Before production acceptance:

```text
>=20 route-completion measurements
for each of the four endpoints
```

Minimum total:

```text
80 endpoint measurements
```

Collected after activation with authenticated owner context and without exceeding normal Admin concurrency.

Record:

```text
count
p50
p95
max
429 count
503 count
500 count
```

Targets:

```text
summary p95 <= 100 ms
page p95    <= 250 ms
```

If sample target cannot be collected safely, stop acceptance and obtain Owner/Tech Lead approval for a revised measurable sample plan.

---

# 136. Coexistence acceptance

After activation:

```text
Current State Client cycles continue
Current State AP cycles continue
Observation cycles continue
Visit Lifecycle continues
Registry continues
Analytics remains available

Devices works
Device Card works
Visits works
Observations works

Portal works
CAPPORT works
```

No new service errors.

---

# 137. Production privacy acceptance

Verify application/access telemetry after activation contains no:

```text
client MAC
client IP
AP MAC filter
SSID filter
cursor
cycle_id
scope hash
raw query
source exception text
```

Admin API itself may return owner-visible MAC/IP as specified.

Logs may not.

---

# 138. Production feature rollback

Fast rollback:

```text
WEB_ADMIN_HOME_LIVE_ENABLED=false
```

or restore environment backup.

Then:

```text
restart service
verify active/running
verify legacy Home
verify Devices/Visits/Observations
verify Portal/CAPPORT
verify Current State continues
```

No Current State shutdown.

No DB deletion.

---

# 139. Rollback browser behavior

If feature is disabled while an already-open Live page still exists:

new Live request receives:

```text
404 not_found
```

Frontend:

```text
stops polling
aborts outstanding Live requests
shows feature-disabled/reload message
```

It does not retry forever.

After page reload:

```text
legacy Home
```

is rendered.

---

# 140. Coder handoff requirements

Implementation handoff must contain:

```text
baseline SHA
implementation SHA

changed files
new config keys/defaults

optional Current State wiring proof
feature-context delivery path

four routes
security/feature order
capability mapping

deadline Option A proof
error mapping proof
limit contract proof

DTO exact fields
AP product mapping
cursor/pinning semantics
separate pagination semantics

generation model
AbortController timeout
hidden-tab behavior
per-source retry/backoff

strict response validation
privacy/no browser storage

route telemetry schema

targeted tests
frontend tests
full suite
compileall
diff-check
working tree

known limitations

production activation NOT performed
```

---

# 141. Known accepted limitations

`HOME-LIVE-01` intentionally accepts:

```text
near-real-time source cadence = 60s
not WebSocket realtime

device count != people count

Client scope may be narrower than Site

Client/AP snapshots have independent watermarks

multi-page source capture is an observation interval,
not one controller-atomic millisecond snapshot

CurrentStateReadService has no in-query deadline cancellation;
HOME-LIVE uses mandatory pre/post deadline checks

controller uptime semantics not product-confirmed

trafficDown/trafficUp/trafficTotal
units/directions not product-confirmed

AP Offline code semantics not product-confirmed;
future source offline is product Other

Admin session/query state remains process-local
```

These are not defects of this task.

---

# 142. No architecture choices left to Coder

FINAL decisions:

```text
Deadline:
  Option A
  mandatory pre/post checks

AP Offline:
  never product Offline
  future source offline → Other

AP page capability:
  admin.read.overview
  minimal AP DTO only

Pagination:
  separate Client/AP cursors and controls

Retry:
  independent Client/AP backoff

Manual Refresh:
  new generation
  attempts both source groups once

Request timeout:
  AbortController
  configured 20s
  bounds 5..60

Hidden tab:
  stop polling
  abort in-flight as neutral

Feature-disabled routes:
  registered
  security/Site/capability first
  canonical 404 next

Legacy Home:
  only feature=false

Live Home:
  no legacy Home requests

Mixed snapshot:
  forbidden
  old list hidden when new summary accepted

AP enrichment:
  matched
  not_yet_loaded
  absent_after_exhaustion
  ap_source_unavailable

Browser persistence:
  forbidden

Telemetry:
  sanitized route completion event
```

Coder does not select alternate architecture in PLAN.

---

# 143. Tech Lead review closure matrix

This matrix is verification only. The operative requirements are embedded in the sections above.

```text
3.1  Deadline A + pre/post checks
     → sections 19, 98, 141, 142

3.2  CurrentStateValidationError 400/503 split
     → sections 21, 84, 99

3.3  default 100 / max 250
     → sections 22, 100

3.4  explicit missing/expired pin
     → sections 33, 42, 102

3.5  future AP offline → product Other
     → sections 38, 39, 104

3.6  separate AP/Client pagination + enrichment
     → sections 43–45, 73, 105–106

3.7  dedicated non-destructive Home controller
     → sections 53–55

3.8  generation/transaction guard
     → sections 56–58, 107

3.9  AbortController/request timeout
     → sections 13, 59, 108

3.10 per-source retry/backoff
     → sections 62–66, 109

3.11 exact feature context/template path
     → sections 12–14, 91, 114

3.12 feature-disabled route order/canonical JSON 404
     → sections 23–24, 101

3.13 AP capability/DTO mismatch
     → sections 18, 40–41, 112

3.14 strict frontend response validation
     → sections 67–68, 110

3.15 measurable sanitized route telemetry
     → sections 88–89, 117, 135

3.16 shutdown latest-attempt semantics
     → sections 51, 102, 111

3.17 API data minimization
     → sections 35, 41, 81–82, 112

3.18 responsive/accessibility table
     → sections 69–71, 113

3.19 exact sort/null placement + AP filter union
     → sections 30, 74, 77

3.20 optional-source construction boundary
     → sections 15–16, 97

3.21 no browser persistence
     → sections 80, 115, 137

3.22 production activation/rollback hardening
     → sections 130–139
```

Coverage:

```text
22 / 22 mandatory Tech Lead corrections incorporated.
```

---

# 144. Current authorization status

```text
TASK-HOME-LIVE-01-FINAL

Status:
FINAL FOR SHORT TECH LEAD CONTROL REVIEW

IMPLEMENTATION NOT AUTHORIZED
BRANCH NOT AUTHORIZED
CODE NOT AUTHORIZED
COMMIT NOT AUTHORIZED
PUSH NOT AUTHORIZED
PR NOT AUTHORIZED
PRODUCTION CHANGE NOT AUTHORIZED
```

Next allowed action:

```text
short Tech Lead control review of FINAL
```

After PASS:

```text
Owner implementation authorization
→ Coder PLAN
→ implementation
→ tests
→ Architect static review
→ Tech Lead Linux gate
→ merge/deploy authorization
→ separate production activation
→ browser/soak acceptance
```

---

# 145. Final architecture statement

`HOME-LIVE-01` is a product read layer over accepted Current Network State.

It does not create another source of truth.

Permanent chain:

```text
Current State collectors
  → persist current facts

CurrentStateReadService
  → selects exact current snapshot truth

AdminQueryService
  → authorizes, bounds, deadlines and classifies reads

Admin API
  → emits minimized safe Site-scoped DTOs

Home Live controller
  → validates responses
  → prevents generation mixing
  → manages independent Client/AP refresh/pagination/freshness
  → renders current operational state
```

No direct Omada path is introduced.
