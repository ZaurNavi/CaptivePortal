# TASK-HOME-LIVE-01 — Admin Console Home Live — DRAFT

**Project:** CaptivPortal  
**Parent product concept:** `TASK-HOME-01 — Admin Console Home v1`  
**Dependency:** `TASK-HOME-CURRENT-STATE-01 — PRODUCTION / ACCEPTED`  
**Type:** master architecture / implementation specification  
**Status:** `DRAFT FOR TECH LEAD REVIEW`  
**Implementation authorization:** `NOT GRANTED`  
**Branch authorization:** `NOT GRANTED`  
**Commit / push / PR authorization:** `NOT GRANTED`  
**Production activation:** separate Owner-controlled step  
**Architecture baseline:** `main@a864dfa78461ccbfe88e110b1aa5bad5f6bfa23e`  
**Prepared:** 2026-08-23  

---

# 1. Purpose

Implement the first live product increment of the CaptivPortal Admin Console Home.

The accepted Current Network State foundation already provides Site-scoped, read-only, bounded near-real-time snapshots for:

```text
active wireless clients in configured SSID scope
AP inventory for selected Site
```

`HOME-LIVE-01` connects that accepted read boundary to:

```text
AdminQueryService
→ authenticated Site-scoped /admin/api/v1
→ existing server-rendered Admin Home shell
→ same-origin vanilla JavaScript UI
```

The result must answer, within a few seconds of opening Home:

```text
How many devices are online now?
How many are authorized?
How many are waiting for authorization?
Are there Other / Unknown states?
How are current devices distributed by AP?
Which APs are currently known online?
Which devices are currently online?
How old is the Client snapshot?
How old is the AP snapshot?
```

This task is deliberately limited to **live/current state**.

---

# 2. Product outcome

When `HOME-LIVE-01` is enabled, Home v1 must show:

```text
1. Online Now
2. Authorized Now
3. Waiting Authorization
4. Other / Unknown
5. AP Online / Total
6. Client snapshot freshness
7. AP snapshot freshness
8. Devices by AP — Now
9. Access Points Now
10. Online Devices
```

The implementation must retain all existing Admin pages and read-only behavior:

```text
Home
Devices
Device Card
Visits
Observations
```

No existing section may regress because Current State is unavailable.

---

# 3. Explicit out of scope

Do NOT implement in this task:

```text
Current Traffic
Channel Load
Today / Connected Today
Today traffic
System Health component matrix
Devices by AP — 24h
Visit analytics additions
Wireless analytics additions
Grafana/Loki panels
Omada control/write actions
client block/unblock
reconnect
rename
rate limit
lock-to-AP
hotspot auth/unauth
AP configuration
new business persistence
new collector
new Omada polling
```

These remain separate tasks:

```text
HOME-TRAFFIC-01
HOME-TODAY-01
HOME-HEALTH-01
HOME-AP-24H-01
```

---

# 4. Current accepted production baseline

Production Current State has been accepted at:

```text
main@a864dfa78461ccbfe88e110b1aa5bad5f6bfa23e
```

Owner/Tech Lead production evidence:

```text
CURRENT_STATE_ENABLED=true

Site:
6a64f17630da7c70d232187a

Client SSID scope:
Zefer_Parki

Client polling:
60 seconds

AP polling:
60 seconds

Retention:
48 hours

Client-row hard cap:
5,000,000
```

Current State production acceptance included:

```text
6 successful Client cycles
0 partial
0 failed

6 successful AP cycles
0 partial
0 failed

6 successful Observation cycles after activation

Portal      400
CAPPORT     403
Admin login 403 unauthenticated smoke
Service     active/running
Service errors 0
```

Accepted read performance:

```text
CurrentStateReadService p95 = 4.570 ms
maximum                     = 5.741 ms
```

Observed accepted snapshot during production validation:

```text
Online      18
Authorized  11
Pending      7
Other        0
Unknown      0
AP unknown   0

AP total     2
AP online    2
```

The mathematical invariants were confirmed.

---

# 5. Verified current code contracts

At the baseline, `CurrentStateRuntime` exposes:

```text
runtime.read_service
```

as a `CurrentStateReadService`.

The existing read service already implements:

```python
get_current_client_summary(site_id, *, evaluated_at_utc=None)

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

get_current_ap_summary(site_id, *, evaluated_at_utc=None)

list_current_aps(
    site_id,
    *,
    cycle_id=None,
    limit=100,
    cursor=None,
    evaluated_at_utc=None,
)
```

It also provides short-history quality, but that method is not required by `HOME-LIVE-01`.

---

# 6. Current snapshot selection semantics to preserve

Current State already distinguishes:

```text
latest_attempt
latest complete success snapshot
latest partial snapshot
```

Exact current values are selected only from:

```text
result = success
AND complete = true
```

A newer partial attempt does not silently replace exact values.

A failed/partial latest attempt remains visible as metadata.

If the latest complete snapshot exceeds its unavailable threshold:

```text
current values are unavailable
```

Old row values are not exposed as current.

This behavior must remain authoritative.

Admin/Web must not reimplement snapshot selection logic.

---

# 7. Current freshness semantics to preserve

Current Client thresholds accepted in production:

```text
fresh:       age <= 60s
stale:       60s < age <= 180s
unavailable: age > 180s
```

Current AP thresholds accepted in production:

```text
fresh:       age <= 90s
stale:       90s < age <= 300s
unavailable: age > 300s
```

Age is measured from:

```text
capture_started_at
```

not capture completion.

Current State already handles:

```text
invalid timestamp
clock anomaly
future timestamp
```

as unavailable.

Admin UI must consume this semantic contract, not invent another server-side freshness classification.

---

# 8. Current client scope

Client Home scope is:

```text
Site ID
+
Current State exact case-sensitive SSID allowlist
```

Production currently means:

```text
Site Home
SSID Zefer_Parki
```

but runtime code must not hardcode either value.

Home must never label the count as:

```text
all devices in entire Omada Site
```

unless the configured source scope actually represents that population.

Product wording should be:

```text
Online Now
```

within the visibly selected Site / configured Home source scope.

The API must expose safe source-scope metadata.

---

# 9. AP scope

AP Current State scope is different:

```text
all AP inventory rows of the selected Site
```

It is not restricted to the client SSID allowlist.

Therefore:

```text
Client snapshot scope != AP snapshot scope
```

This is expected.

Client and AP snapshots also have independent:

```text
cycle_id
observed_at
age_seconds
freshness_status
```

They must never be merged into one fake `Updated` timestamp.

---

# 10. Data Acquisition / Analytics Boundary

Permanent invariant:

```text
HOME-LIVE does not collect.
```

Correct path:

```text
Omada
  ↓
already running Current State collectors
  ↓
current_state.sqlite3
  ↓
CurrentStateReadService
  ↓
AdminQueryService
  ↓
Admin API
  ↓
Home UI
```

Forbidden:

```text
Home → Omada
Admin API → Omada
AdminQueryService → Omada
Home → Observation DB to reconstruct current clients
Home → Registry/Visit to reconstruct current clients
Home → Loki
Home → Grafana
Home → raw log files
```

The **only live source** in this task is:

```text
CurrentStateReadService
```

---

# 11. Product / Observability Boundary

Home may expose:

```text
current counts
current client context
current AP context
source scope
snapshot age
fresh/stale/unavailable
latest collection-attempt high-level state
```

Do not expose in product UI:

```text
raw SQLite errors
filesystem paths
stack traces
Omada tokens
request internals
collector failure_category
raw provider payload
secret configuration
```

Engineering diagnostics remain in application logs / Grafana / Loki.

---

# 12. Future Multi-Site Compatibility

Mandatory:

```text
every Home live endpoint is Site-scoped
Site authorization happens before source access
CurrentStateReadService receives exact selected site_id
no cross-Site cursor use
no cross-Site MAC matching
no default-Site fallback inside API methods
no tenant_id
Tenant != Site
```

A second allowed Site must not require a new route shape.

---

# 13. Existing Admin security remains authoritative

Do not change:

```text
AdminPrincipal
AdminSessionStore
AdminPreAuthCsrfStore
AdminLoginRateLimiter
AdminAccessPolicy security model
HTTPS requirement
allowed-network enforcement
session cookie contract
CSRF/logout
security headers
CSP
access-log query stripping
```

The Admin API remains:

```text
session-cookie authenticated
GET-only for product data
same-origin
Site-authorized
```

No Analytics bearer is introduced into browser code.

---

# 14. Feature activation boundary

This task MUST introduce a separate feature flag:

```text
WEB_ADMIN_HOME_LIVE_ENABLED=false
```

Repository-safe default:

```text
false
```

Reason:

`WEB_ADMIN_ENABLED=true` is already active in production.

Without a separate flag, deploying merged code would implicitly activate the new Home, violating the project rule:

```text
merge/deploy != production feature activation
```

When false:

```text
existing Home behavior remains unchanged
new live Home API is not product-active
```

When true:

```text
Home uses Current State live API/UI
```

Production activation is a separate Owner-controlled step.

---

# 15. Additional Admin configuration

Proposed repository-safe configuration:

```text
WEB_ADMIN_HOME_LIVE_ENABLED=false
WEB_ADMIN_HOME_LIVE_REFRESH_SECONDS=60
WEB_ADMIN_CURRENT_STATE_PAGE_SIZE=100
```

Validation:

```text
HOME_LIVE_ENABLED:
exact boolean

HOME_LIVE_REFRESH_SECONDS:
60..300

CURRENT_STATE_PAGE_SIZE:
1..250
```

`60` seconds is selected because accepted production Current State cadence is 60 seconds.

Auto-refresh must never run faster than configured `WEB_ADMIN_HOME_LIVE_REFRESH_SECONDS`.

Manual Refresh is allowed at any time.

---

# 16. Runtime composition change

Current `run.py` already creates and starts Current State before Admin Web composition.

Current shape:

```text
_configure_current_state(...)
...
_configure_admin_web(...)
```

`HOME-LIVE-01` should pass:

```text
_current_state_runtime.read_service
```

to Admin Web composition.

Preferred signature extension:

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

Keyword-only optional dependency preserves existing call/test compatibility.

No Admin code may access:

```text
CurrentStateRepository
current_state.sqlite3 path
CurrentStateRuntime.provider
CurrentState workers
```

Only:

```text
CurrentStateReadService
```

---

# 17. Admin availability must not depend on Current State

This is a hard boundary.

Current Admin Web is already production-accepted.

Therefore:

```text
Current State unavailable
```

must NOT cause:

```text
AdminWebRuntime.state = unavailable
```

if the existing Registry/Visit/Observation/Analytics dependencies are otherwise healthy.

Correct behavior:

```text
Admin shell                stays available
Devices                    stays available
Device Card                stays available
Visits                     stays available
Observations               stays available

Home Live endpoints        unavailable / quality-unavailable
Home Live UI               shows unavailable
```

Current State is an **optional new read dependency** for the existing Admin runtime.

---

# 18. AdminQueryService integration

Extend `AdminQueryService` with optional:

```text
current_state_read_service
```

Conceptual methods:

```python
current_client_summary(
    principal,
    site_id,
)

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

current_ap_summary(
    principal,
    site_id,
)

list_current_aps(
    principal,
    site_id,
    *,
    cycle_id=None,
    limit=None,
    cursor=None,
)
```

No SQL in `AdminQueryService`.

No Current State repository access.

---

# 19. Capability mapping

Use existing permissions-ready capabilities.

### Client summary

```text
admin.read.overview
```

### AP summary

```text
admin.read.overview
```

### AP current page

```text
admin.read.overview
```

### Online Devices current page

```text
admin.read.devices
```

Reason:

the current-client page includes technical endpoint identity/context such as:

```text
MAC
IP
hostname
```

A future restricted principal may be allowed overview counts without being allowed endpoint-level device details.

Do not create a new capability unless Tech Lead identifies a concrete policy requirement.

---

# 20. Current State source-error mapping

Import only source-safe exception classes needed for mapping.

Conceptual mapping:

```text
CurrentStateValidationError
→ AdminQueryValidationError
→ HTTP 400 invalid_request

CurrentStateStorageError
CurrentStateSchemaError
unexpected safe source-open failure
→ AdminQueryUnavailable
→ HTTP 503 source_unavailable
```

Do not return source exception strings.

Do not return DB path.

---

# 21. Query concurrency

All four Current State Admin methods use the existing:

```text
WEB_ADMIN_MAX_CONCURRENT_QUERIES
```

non-blocking semaphore.

No extra Home-specific query queue.

No slot:

```text
429
Retry-After: 1
```

The current source reads are already bounded and accepted at:

```text
p95 4.570 ms
max 5.741 ms
```

No new historical scan is introduced.

---

# 22. Query deadline policy — DRAFT decision

Current `CurrentStateReadService` does not currently accept the Analytics `QueryDeadline` contract.

This DRAFT proposes:

```text
do NOT introduce a dependency:
Current State → Analytics
```

and do not redesign the accepted Current State source solely for Home.

For `HOME-LIVE-01`:

1. the existing Admin query semaphore remains mandatory;
2. `deadline.require_remaining()` is checked before invoking the Current State source;
3. Current State methods remain bounded to:
   - one summary snapshot;
   - one current snapshot page;
   - max API page <= 250;
4. accepted production p95/max read evidence is recorded in the TASK baseline;
5. after source return, Admin may classify a request that already exceeded its overall deadline as `query_deadline`, but this is not claimed to be in-query SQLite cancellation.

This is the **only explicit architecture review point left open in this DRAFT**:

```text
Tech Lead should either:
A. accept bounded Current State reads as a narrow exception to direct-query cancellation;
or
B. require a separate common deadline abstraction before FINAL.
```

Coder must not choose between A/B.

No `CurrentStateReadService` source change is authorized by this DRAFT unless Tech Lead requires option B.

---

# 23. Admin API namespace

Add exactly four authenticated Site-scoped GET endpoints:

```text
GET /admin/api/v1/sites/{site_id}/current-state/clients/summary

GET /admin/api/v1/sites/{site_id}/current-state/clients

GET /admin/api/v1/sites/{site_id}/current-state/aps/summary

GET /admin/api/v1/sites/{site_id}/current-state/aps
```

They use the existing Admin API envelope:

```text
api_version = admin.read.v1
```

No new API root/version is introduced.

---

# 24. Feature-disabled API behavior

When:

```text
WEB_ADMIN_HOME_LIVE_ENABLED=false
```

the four new routes return sanitized:

```text
404 not_found
```

after normal Admin authentication/network/Site boundary processing.

They must not read Current State while feature-disabled.

The existing Home route continues current behavior.

---

# 25. Client summary endpoint

Route:

```text
GET /admin/api/v1/sites/{site_id}/current-state/clients/summary
```

Allowed query parameters:

```text
none
```

Any query parameter:

```text
400 invalid_request
```

Capability:

```text
admin.read.overview
```

Source:

```text
CurrentStateReadService.get_current_client_summary(site_id)
```

---

# 26. Client summary response

Success envelope:

```json
{
  "api_version": "admin.read.v1",
  "request_id": "<uuid>",
  "site_id": "<site_id>",
  "result": {
    "snapshot": {
      "cycle_id": "<uuid-or-null>",
      "evaluated_at": "<UTC>",
      "observed_at": "<UTC-or-null>",
      "capture_finished_at": "<UTC-or-null>",
      "age_seconds": 21.3,
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
  },
  "page": null
}
```

Exact field order is not an API guarantee.

---

# 27. Client summary unavailable semantics

When no complete current-scope snapshot exists, or complete snapshot is older than the unavailable threshold:

```text
HTTP 200
```

with:

```text
snapshot.freshness_status = unavailable
counts = null-safe product structure
```

Preferred:

```json
"counts": {
  "online": null,
  "authorized": null,
  "pending": null,
  "other": null,
  "unknown": null,
  "other_unknown": null,
  "ap_unknown": null
}
```

and:

```text
devices_by_ap = []
```

Reason:

source is reachable and has quality metadata, but current values are not valid.

This is different from:

```text
HTTP 503 source_unavailable
```

which represents failure to access/use the read source itself.

Do not convert unavailable to zero.

---

# 28. Exact counter invariant

Whenever client summary counts are non-null:

```text
Online
=
Authorized
+ Pending
+ Other
+ Unknown
```

and:

```text
Online
=
sum(Devices by known AP)
+ AP Unknown
```

Admin Web must not recompute counts from a separately fetched page.

The summary is authoritative for cards.

---

# 29. Client page endpoint

Route:

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

All scalar query parameters occur at most once under the existing Admin request boundary.

Unknown parameter:

```text
400 invalid_request
```

Capability:

```text
admin.read.devices
```

---

# 30. Client page limit

Default:

```text
WEB_ADMIN_CURRENT_STATE_PAGE_SIZE
```

Repository default:

```text
100
```

Hard Admin maximum:

```text
250
```

Current State source itself supports a larger bound, but the Admin product boundary is intentionally smaller.

No unbounded page loop.

---

# 31. Client sort allowlist

API exposes only the accepted CurrentStateReadService sort keys:

```text
client_mac
controller_uptime
controller_traffic_total_desc
controller_traffic_down
controller_traffic_up
auth_status
ap
rssi
snr
```

Default:

```text
controller_traffic_total_desc
```

This default is source-neutral:

it does NOT imply the counter has been proven to be bytes, Mbps, Download or Upload.

No arbitrary sort field.

---

# 32. Client filter allowlist

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
  exact source SSID text
```

SSID filter semantics are:

```text
case-sensitive
no trim
no case fold
no comma parsing
no Unicode normalization
```

The Admin validation layer must not use its existing generic trim-based text-filter helper for this field.

SSID must be:

```text
non-empty
bounded by WEB_ADMIN_MAX_FILTER_CHARS
passed unchanged
```

---

# 33. Client page cycle pinning

The API exposes optional:

```text
cycle_id
```

to support coherent Home rendering.

Home refresh sequence:

```text
Client Summary
→ receives exact client cycle_id
→ Client Page request passes that same cycle_id
```

Therefore cards and Online Devices first page represent the same exact complete Client snapshot.

For pagination:

```text
cursor itself is snapshot/cycle/scope pinned
```

Load More must not switch to a newer snapshot.

---

# 34. Client cursor contract

The Current State cursor is treated as opaque by Admin UI.

Admin does not decode/rewrite its internals.

CurrentStateReadService already binds current-client cursor to:

```text
endpoint
Site
cycle
source scope hash
sort
filters
last keyset position
```

Admin must additionally enforce:

```text
cursor length <= existing Admin cursor bound
```

Malformed/cross-Site/cross-cycle/cross-scope/cross-sort/cross-filter cursor:

```text
400 invalid_request
```

No fallback to first page.

Do not log cursor value.

---

# 35. Client page response

```json
{
  "api_version": "admin.read.v1",
  "request_id": "<uuid>",
  "site_id": "<site_id>",
  "result": {
    "snapshot": {
      "...": "same safe snapshot metadata contract"
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
        "device_type": "unknown",
        "ip": "192.0.2.10",
        "ssid": "Example",
        "ap_name": "AP-1",
        "ap_mac": "11:22:33:44:55:66",
        "radio_id": 1,
        "band": "5GHz",
        "channel": 36,
        "rssi": -61,
        "snr": 31,
        "controller_uptime": 1234,
        "auth_status_code": 2,
        "auth_classification": "authorized",
        "controller_traffic_down": 100000,
        "controller_traffic_up": 50000,
        "controller_traffic_total": 150000
      }
    ]
  },
  "page": {
    "limit": 100,
    "next_cursor": "<opaque-or-null>",
    "cycle_id": "<uuid-or-null>",
    "source_scope_hash": "<sha256-or-null>"
  }
}
```

Do not expose:

```text
active
wireless
cycle_kind
raw DB row
```

because inclusion in the snapshot already proves:

```text
active=true
wireless=true
within current SSID scope
```

---

# 36. Client page unavailable behavior

If selected complete snapshot is unavailable by age:

```text
HTTP 200
items = []
next_cursor = null
snapshot.freshness_status = unavailable
```

Do not expose old client rows.

If requested explicit cycle_id no longer exists / is invalid for the current Site/current scope:

```text
400 invalid_request
```

---

# 37. AP summary endpoint

Route:

```text
GET /admin/api/v1/sites/{site_id}/current-state/aps/summary
```

Allowed query parameters:

```text
none
```

Capability:

```text
admin.read.overview
```

Source:

```text
CurrentStateReadService.get_current_ap_summary(site_id)
```

---

# 38. AP summary product contract

Current accepted evidence proves only:

```text
AP status=1 → online
```

Other AP status values must not be product-labeled as `offline` without evidence.

Therefore `HOME-LIVE-01` product response is:

```json
{
  "snapshot": {
    "...": "AP snapshot metadata"
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

Do not expose a product `offline` count in this task.

The underlying CurrentStateReadService has an `offline_count` field for forward-compatible classification, but current normalizer evidence does not classify any code as offline.

Adding Offline to product UI requires later evidence/review.

---

# 39. AP page endpoint

Route:

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

Default/max limit:

```text
WEB_ADMIN_CURRENT_STATE_PAGE_SIZE
max 250
```

Current AP source max is also bounded.

---

# 40. AP page cycle pinning

Home refresh sequence:

```text
AP Summary
→ exact AP cycle_id
→ AP Page with same cycle_id
```

AP rows and AP summary therefore represent the same AP snapshot.

Client and AP snapshot cycle IDs remain different.

---

# 41. AP page response

Safe item fields:

```text
ap_mac
name
ip
model
firmware_version
status_code
status_classification
last_seen_ms
controller_uptime
uptime_raw
```

Product UI must treat:

```text
online → Online
other  → Other
unknown → Unknown
```

Do not display:

```text
offline
```

unless status classification evidence is separately accepted.

---

# 42. Client/AP join semantics

`Devices by AP — Now` counts come only from the Client summary snapshot.

AP page is enrichment only.

Join key:

```text
canonical AP MAC
```

Never AP name.

Rules:

### Client bucket has AP MAC, AP inventory has matching AP

Show:

```text
AP name
AP MAC
current scoped client count
AP current status
```

### Client bucket AP absent from AP snapshot

Keep the client bucket.

Show:

```text
AP MAC
client count
AP health/status = Unknown
```

Do not drop those clients.

### AP exists in AP inventory, no scoped clients

Keep AP in `Access Points Now`.

Show:

```text
client count = 0
```

### Client AP MAC null

Show separate:

```text
AP Unknown
```

using `ap_unknown_count`.

---

# 43. Client/AP watermark independence

The UI must display separate source freshness:

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

Forbidden:

```text
Updated 17 seconds ago
```

as one global value when the sources have different watermarks.

Manual browser refresh time may be separately shown as:

```text
Page refreshed at ...
```

but must not be confused with source observation time.

---

# 44. Home top product layout

When Live Home is enabled, top priority section contains:

```text
[ Online Now ]
[ Authorized ]
[ Waiting Authorization ]
[ Other / Unknown ]
[ AP Online / Total ]
```

Under or adjacent to cards:

```text
Client freshness indicator
AP freshness indicator
```

The product scope is not reduced from the Owner/Architect Home concept.

This task simply implements the current-state subset first.

---

# 45. Online card

Value:

```text
counts.online
```

Label:

```text
Online Now
```

Supporting scope text may show:

```text
configured SSID scope
```

Do not use:

```text
People Online
Visitors Online
```

because identity is device-based.

---

# 46. Authorized card

Value:

```text
counts.authorized
```

Label:

```text
Authorized
```

Meaning:

```text
active wireless scoped clients classified authStatus=2
```

No Visit/Registry reconstruction.

---

# 47. Waiting Authorization card

Value:

```text
counts.pending
```

Label:

```text
Waiting Authorization
```

Meaning:

```text
active wireless scoped clients classified authStatus=1
```

---

# 48. Other / Unknown card

Main value:

```text
counts.other_unknown
```

Subline:

```text
Other X · Unknown Y
```

Unknown is never silently merged into Pending.

Other known non-Pending/non-Authorized status is never silently merged into Authorized.

---

# 49. AP Online / Total card

Display:

```text
Online / Total
```

Example:

```text
2 / 2
```

Secondary:

```text
Other X
Unknown Y
```

Do not display:

```text
Offline 0
```

in `HOME-LIVE-01`.

---

# 50. Freshness UI states

Use exact source statuses:

```text
fresh
stale
unavailable
```

### fresh

Show values normally.

### stale

Preserve last exact complete values but visibly mark:

```text
STALE
age
observed_at
```

No green “up to date” indicator.

### unavailable

Replace current numeric/product values with:

```text
—
```

or explicit:

```text
Unavailable
```

Do not keep old numbers visible as if current.

Last known observed timestamp may be shown as metadata only.

---

# 51. Latest attempt warning

If:

```text
snapshot.latest_attempt_result != success
```

while a prior complete snapshot is still fresh or stale, show a small warning:

```text
Latest collection attempt was partial/failed;
showing the latest complete snapshot.
```

Do not expose raw failure_category.

Do not call the exact counts “latest attempt”.

---

# 52. Browser-side age progression

API provides:

```text
snapshot.age_seconds
freshness_policy.fresh_max_age_seconds
freshness_policy.unavailable_after_seconds
```

After a successful response, browser tracks elapsed time using:

```text
performance.now()
```

not browser wall-clock arithmetic.

Between network refreshes:

```text
display_age =
server age_seconds
+ monotonic browser elapsed seconds
```

When display age crosses:

```text
fresh max → UI changes to stale
unavailable max → current values are hidden/invalidated
```

This prevents a network error from leaving a “Fresh” badge forever.

A later server response always replaces local progression.

---

# 53. Initial loading

Initial Home Live load:

```text
loading state
no fabricated zero values
```

Cards may show skeleton/`—`.

Once summary arrives:

```text
fresh/stale/unavailable
```

is rendered.

---

# 54. Empty state

A complete fresh/stale Client snapshot with:

```text
online = 0
```

is a valid exact result.

Show:

```text
Online Now = 0
Authorized = 0
Waiting = 0
Other / Unknown = 0

Online Devices:
No online devices in the current scope.
```

This is not `unavailable`.

---

# 55. Error state

Transport/HTTP/source error is distinct from source freshness.

If no previously rendered valid snapshot exists:

```text
show error/unavailable state
```

If previous current values exist and remain within stale threshold:

```text
preserve them
mark stale/error visibly
```

If local age crosses unavailable threshold:

```text
hide current values
```

Do not keep showing stale numbers indefinitely.

---

# 56. Devices by AP — Now

Render below top cards.

Input:

```text
Client summary.devices_by_ap
Client summary.ap_unknown
AP page enrichment
```

Suggested v1 presentation:

```text
simple compact rows / CSS bars
```

No external charting library.

Each known bucket:

```text
AP name if available
AP MAC
client count
AP status badge from independent AP snapshot
```

Include:

```text
AP Unknown
```

when count > 0.

Total of buckets + AP Unknown must equal Online.

---

# 57. Access Points Now

Render compact Site AP list.

For every AP in AP current page:

```text
name
MAC
status
current scoped client count
```

An AP with zero scoped clients remains visible.

Status display:

```text
Online
Other
Unknown
```

No unproven Offline label.

If AP page is stale:

```text
AP list marked stale
```

If AP source unavailable but Client source is available:

```text
Devices by AP counts remain visible from Client snapshot
AP health/name enrichment becomes unavailable/unknown
```

---

# 58. Online Devices table

Place below live summary/AP sections.

Table must remain bounded.

Initial page:

```text
100 rows by default
```

Load More uses current source cursor.

Table source:

```text
CurrentStateReadService.list_current_clients()
```

No Registry merge.

No Observation merge.

No N+1 client detail calls.

---

# 59. Online Devices columns

`HOME-LIVE-01` shows:

```text
Device / MAC
Auth
IP
AP
Band
RSSI
SNR
Controller uptime
Controller trafficDown
Controller trafficUp
Controller trafficTotal
```

Device display priority:

```text
name
else hostname
else MAC
```

MAC remains visible in the row.

---

# 60. Neutral controller-field requirement

Accepted production evidence does NOT yet prove product semantics for:

```text
controller_uptime
trafficDown
trafficUp
trafficTotal
```

Therefore first Home Live must use neutral labels exactly equivalent to controller facts.

Allowed labels:

```text
Controller uptime
Controller trafficDown
Controller trafficUp
Controller trafficTotal
```

Forbidden until separate evidence:

```text
Online time
Session duration
Download
Upload
Downloaded
Uploaded
Traffic GB
Mbps
Speed
```

Do not humanize controller uptime as seconds/minutes/hours until its unit/reset semantics are accepted.

Do not format traffic counters as bytes/MB/GB until unit evidence is accepted.

Display raw finite integer or `—`.

This preserves the Owner-requested table visibility without inventing semantics.

---

# 61. Nullable client fields

UI:

```text
IP null        → —
RSSI null      → —
SNR null       → —
AP null        → AP Unknown
name null      → hostname or MAC
counter null   → —
uptime null    → —
```

Null is never `0`.

---

# 62. Auth display

Map only accepted safe classification:

```text
authorized → Authorized
pending    → Waiting
other      → Other
unknown    → Unknown
```

Raw `auth_status_code` may be available in API but need not be displayed by default.

Do not display Unknown as error unless product semantics later require it.

---

# 63. Sort UI

Provide a bounded select control using API sort allowlist.

Minimum visible options:

```text
Controller trafficTotal
Controller uptime
MAC
Auth status
AP
RSSI
SNR
```

Optional:

```text
Controller trafficDown
Controller trafficUp
```

Changing sort:

```text
clears current cursor
requests first page
pins new current summary cycle
```

No arbitrary client-side sort over only loaded rows while pretending to sort all online devices.

---

# 64. Filter UI

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
  each known AP
```

If multiple SSIDs exist in client source scope:

```text
SSID filter may be shown
```

For current single-SSID production scope, SSID control may remain hidden.

Filter change:

```text
cursor reset
first page
same current Home refresh transaction
```

---

# 65. Pagination UX

Use existing `Load more` pattern.

Cursor semantics:

```text
snapshot pinned
```

Auto-refresh replaces the current table with page 1 of the newest exact complete snapshot.

This is intentional because Home is a live operational page.

Current filters/sort are retained across auto-refresh.

Loaded extra pages are not retained across a new snapshot.

---

# 66. Refresh architecture

No WebSocket/SSE in v1.

Use bounded same-origin GET polling.

Auto-refresh default:

```text
60 seconds
```

Manual:

```text
Refresh button
```

No overlapping Home refreshes.

---

# 67. One logical Home refresh

A refresh is a coordinated frontend operation.

Preferred sequence:

### Phase 1 — summaries

Parallel:

```text
Client Summary
AP Summary
```

### Phase 2 — pinned pages

If Client summary has fresh/stale valid complete cycle:

```text
Client Page with cycle_id = Client Summary cycle_id
```

If AP summary has fresh/stale valid complete cycle:

```text
AP Page with cycle_id = AP Summary cycle_id
```

This guarantees within-source coherence.

Client and AP phases remain independent from each other.

---

# 68. No overlapping requests

A Home refresh controller tracks:

```text
refresh_in_flight
```

If auto timer fires while true:

```text
skip
```

If manual Refresh clicked while true:

```text
button remains disabled
no second request
```

No queue of missed refreshes.

After completion:

```text
schedule next from completion time
```

fixed-delay behavior.

---

# 69. Hidden-tab policy

When:

```javascript
document.hidden === true
```

stop Home auto-refresh timer completely.

Do not continue polling Current State in a background hidden tab.

When tab becomes visible:

- if no successful refresh yet → refresh immediately;
- if time since last completed refresh >= configured interval → refresh immediately;
- otherwise schedule only the remaining interval.

Manual Refresh is naturally unavailable while user cannot interact with hidden tab.

---

# 70. Error retry/backoff

No tight retry loop.

After refresh failure:

```text
1st consecutive failure → next automatic attempt after 60s
2nd                     → 120s
3rd+                    → 300s max
```

Use:

```text
max(configured refresh interval, backoff)
```

Successful refresh resets failure count.

`429 Retry-After`:

respect at least the larger of:

```text
Retry-After
configured refresh interval
```

No automatic retry faster than source cadence.

---

# 71. Manual Refresh and backoff

Manual Refresh:

```text
allowed while visible and no request in flight
```

It may occur before automatic backoff expires.

A successful manual refresh resets automatic error backoff.

A failed manual refresh increments the same bounded failure counter.

---

# 72. API response-size protection

All four new routes use existing:

```text
_success(..., enforce_size=True)
```

and existing:

```text
WEB_ADMIN_MAX_RESPONSE_BYTES
```

No bypass.

If exceeded:

```text
503 response_too_large
```

Admin page size 100 should remain comfortably below the current cap.

---

# 73. Access-log privacy

Existing production handler strips query strings for all:

```text
/admin/*
```

Maintain that behavior.

This matters because current-state queries may contain:

```text
cursor
MAC
SSID
filter values
```

Do not weaken `_safe_access_requestline()`.

---

# 74. Application telemetry privacy

New Admin route telemetry may include:

```text
request_id
route_name
site_id after authorization
status_code
duration_ms
reason
```

Never include:

```text
client MAC
client IP
AP MAC from filter
SSID filter
cursor
cycle_id
source_scope_hash
item contents
```

No full query-string logging.

No request URL logging from application telemetry.

---

# 75. API DTO allowlist

Do not serialize source dataclasses generically.

Create explicit safe serializers/converters for:

```text
CurrentSnapshotMeta
CurrentClientSummary
CurrentClientState
CurrentApSummary
CurrentApState
```

Reason:

future Current State source fields must not automatically become Admin API fields.

No raw `__dict__`.

No unreviewed `asdict()` for source DTOs.

---

# 76. Snapshot metadata DTO

Expose:

```text
cycle_id
evaluated_at
observed_at
capture_finished_at
age_seconds
freshness_status
freshness_reason
complete
source_scope_version
source_scope_hash
source_scope
latest_attempt_result
latest_attempt_at
latest_partial_cycle_id
```

Do not expose internal source DB path/config repr.

---

# 77. API error envelope

Use existing canonical envelope:

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

No new detailed source exception body.

---

# 78. HTTP status mapping

Keep existing Admin status model.

For new endpoints:

```text
200:
successful API response including source-level
fresh/stale/unavailable metadata

400:
invalid parameter
invalid sort/filter
invalid cycle
malformed/invalid cursor
cross-cycle/scope cursor

401:
Admin session absent/expired

403:
network/Site/capability forbidden

404:
feature disabled
or route/entity product absence where applicable

429:
Admin query concurrency limit

503:
CurrentStateReadService absent
Current State DB/source cannot be read/validated
query deadline where applicable
response too large

500:
unexpected sanitized Admin error
```

Unauthorized Site must be rejected before Current State read.

---

# 79. CurrentState source missing

If:

```text
WEB_ADMIN_HOME_LIVE_ENABLED=true
```

but:

```text
current_state_read_service is None
```

new endpoints:

```text
503 source_unavailable
```

Home:

```text
shows Live data unavailable
```

Other Admin pages continue.

Do not fail Admin runtime construction solely because this optional source is absent.

---

# 80. Current scope mismatch

CurrentStateReadService computes current client scope from its accepted config.

Admin does not accept a caller-provided:

```text
source_scope_hash
```

for current Home reads.

Therefore caller cannot request an old scope as current.

Cursor from an old scope:

```text
400 invalid_request
```

Home Refresh obtains the current canonical source scope automatically.

---

# 81. UI implementation technology

Keep existing Web Foundation stack:

```text
Flask
Jinja
plain CSS
vanilla JS
```

No:

```text
React
Vue
Chart.js
jQuery
external CDN
new npm production dependency
```

Existing CSP must remain valid.

All dynamic source text inserted using:

```text
textContent
```

not unsafe `innerHTML`.

---

# 82. Existing Home fallback

When Live Home flag is false, retain current Home:

```text
Runtime
Visits · 24 hours
Devices · 24 hours
```

This fallback exists for staged deployment/rollback only.

It is not the final long-term Home product concept.

No behavior change to fallback in this task except the minimum branching needed.

---

# 83. Home template

`admin/home.html` may be extended with Home-specific controls/containers.

Do not duplicate the entire Admin shell.

Keep:

```text
admin/base.html
sidebar
topbar
logout
Refresh button
```

Home-specific markup should be semantic and bounded.

---

# 84. Existing page regressions prohibited

Do not alter behavior of:

```text
Devices page
Device Card
Visits page
Observations page
```

except shared frontend helpers that are demonstrably required and covered by regression tests.

Their API routes remain unchanged.

---

# 85. Current page state model

Home Live must distinguish:

```text
initial_loading
refreshing
ready_fresh
ready_stale
empty
source_unavailable
request_error
session_expired
forbidden
busy
unexpected_error
```

Do not collapse source stale into request failure.

Do not collapse complete zero snapshot into empty source.

---

# 86. Refresh-state UX

After first successful render:

manual/auto refresh should not blank all content.

Instead:

```text
retain current content
show "Refreshing…"
disable Refresh button
```

On successful response:

```text
replace with new snapshot
```

On failure:

```text
retain only while still semantically fresh/stale
mark request failure
local age continues
```

Once unavailable age threshold is crossed:

```text
hide current values
```

---

# 87. Independent source failure

Client and AP sources are rendered independently.

Examples:

### Client available, AP unavailable

Show:

```text
Online/Auth cards
Devices by AP counts from Client snapshot
Online Devices
```

But:

```text
AP status/name enrichment unavailable
AP Online/Total unavailable
```

### AP available, Client unavailable

Show:

```text
AP Online/Total
Access Points Now
```

But:

```text
Online/Auth/Devices-by-AP/Online Devices unavailable
```

Do not fail whole Home because one source is unavailable.

---

# 88. Request grouping

Frontend may use:

```javascript
Promise.allSettled
```

rather than `Promise.all` for independent Client/AP summary requests.

Reason:

one source failure must not discard the other valid source.

Within one source:

```text
summary success
→ pinned page
```

If pinned page fails:

```text
summary cards remain valid
table/list portion shows its own error
```

---

# 89. No summary reconstruction from page

Forbidden:

```text
Online = number of rows in loaded page
Authorized = count loaded page authorized
```

because page is bounded/paginated.

Cards always come from summary endpoint.

---

# 90. No AP count reconstruction from page limit

AP summary is authoritative for:

```text
AP total
AP online
Other
Unknown
```

AP page is for details/enrichment.

Do not infer total from number of AP rows returned if page is incomplete.

---

# 91. Performance budget

Current source p95:

```text
4.570 ms
```

`HOME-LIVE-01` production acceptance should record Admin endpoint latency separately.

Proposed acceptance target on production Site at current scale:

```text
summary endpoints p95 <= 100 ms server-side
page endpoints p95    <= 250 ms server-side
```

These are product/API budgets including Admin orchestration/serialization, not source DB-only numbers.

If current infrastructure cannot meet these by a reasonable margin:

```text
STOP
return measured evidence
```

Do not weaken pagination/source correctness.

---

# 92. Request budget per auto-refresh

Normal first-page Home refresh uses at most:

```text
1 Client summary
1 AP summary
1 Client page
1 AP page
```

Total:

```text
4 Admin GET requests per visible Home refresh
```

At 60 seconds:

```text
4 Admin requests/min per open visible Home browser tab
```

These do not call Omada.

Current State polling cost is unchanged.

No new backend polling worker is created.

---

# 93. Multiple browser tabs

Each visible Home tab may poll independently.

No server-side shared browser refresh scheduler is introduced.

Current Admin concurrency guard protects backend queries.

Hidden tabs stop polling.

Production acceptance should test at least:

```text
two simultaneous visible Home sessions/tabs
```

If existing Admin concurrency setting causes persistent 429 under two normal Home loads:

```text
STOP
return architecture impact
```

Do not silently raise global concurrency without review.

---

# 94. Configuration tests

Add tests for:

```text
WEB_ADMIN_HOME_LIVE_ENABLED default false
enabled exact boolean validation
refresh default 60
refresh lower bound 60
refresh upper bound 300
current-state page size default 100
page size min/max
safe repr/config output
```

No production Site/SSID in tests.

---

# 95. Admin runtime tests

Prove:

```text
Current State read service optional
Admin runtime remains active without it
existing query service still constructed for old pages
Home Live methods receive source when provided
feature disabled does not touch Current State
feature enabled + missing source returns live unavailable only
```

---

# 96. Query-service backend tests

Minimum:

```text
client summary authorization
client page uses admin.read.devices
AP summary authorization
AP page authorization
Site passed exactly to CurrentStateReadService
no repository/Omada object dependency

CurrentStateValidationError → 400 class
source/storage/schema failure → 503 class
query semaphore 429 behavior

client summary DTO field allowlist
client item DTO field allowlist
AP DTO field allowlist
no generic source-field leakage
```

---

# 97. Snapshot selection tests through Admin

Minimum:

```text
fresh complete summary
stale complete summary
unavailable old complete summary
no complete snapshot
latest partial + older fresh complete
latest partial + older stale complete
latest partial + older unavailable complete
latest failed + older complete

fresh partial never replaces exact counters
```

The Admin layer should assert source output semantics rather than reimplement source cycle SQL.

---

# 98. Counter invariant tests

For non-null summary:

```text
online =
authorized + pending + other + unknown
```

and:

```text
online =
sum(devices_by_ap) + ap_unknown
```

If a fake/malformed source DTO violates invariants:

preferred behavior:

```text
Admin serialization/query rejects as source_unavailable/internal integrity error
```

rather than rendering inconsistent cards.

Do not silently repair counts.

---

# 99. Route tests

For each new route:

```text
unauthenticated → 401
disallowed Site → 403
invalid Site syntax → 400/403 according to existing canonical resolver
feature disabled → 404 after auth/Site boundary
valid request → 200

duplicate query scalar → 400
unknown parameter → 400
overlong query → existing 400
```

Existing route regression tests remain green.

---

# 100. Cursor tests

Minimum:

```text
valid page 1 + next cursor
valid page 2
cursor pinned to exact cycle
cursor with another Site rejected
cursor with changed cycle rejected
cursor with changed current scope rejected
cursor with changed sort rejected
cursor with changed auth filter rejected
cursor with changed AP filter rejected
malformed cursor rejected
overlong cursor rejected
no silent first-page fallback
```

Admin application/access telemetry must not contain cursor content.

---

# 101. Filter/sort tests

Minimum:

```text
all allowed sorts accepted
unknown sort rejected

authorized/pending/other/unknown accepted
unknown auth classification rejected

valid AP MAC canonicalized safely
invalid AP MAC rejected

exact SSID preserved
SSID case mismatch does not normalize
SSID with space preserved
SSID with comma preserved
leading/trailing-space SSID preserved if it exists in scope
empty SSID filter rejected
```

---

# 102. Client/AP reconciliation frontend tests

Given:

```text
Client AP bucket exists + AP inventory match
```

UI shows joined AP data.

Given:

```text
Client AP bucket exists + AP inventory missing
```

UI keeps count and marks AP status unknown.

Given:

```text
AP exists + zero scoped clients
```

UI shows AP with zero clients.

Given:

```text
ap_unknown > 0
```

UI shows AP Unknown bucket.

Known buckets + AP Unknown must visually reconcile with Online.

---

# 103. AP status tests

Prove product UI:

```text
status_classification=online → Online
other → Other
unknown → Unknown
```

Do not render:

```text
Offline
```

in current task.

Raw unverified status code does not change product label.

---

# 104. Neutral field-label tests

Frontend tests must fail if first Home Live renders source counters as:

```text
Mbps
MB
GB
Download
Upload
Online time
minutes
hours
```

Allowed:

```text
Controller uptime
Controller trafficDown
Controller trafficUp
Controller trafficTotal
```

Until evidence status changes in a future reviewed task.

---

# 105. Freshness frontend tests

Minimum:

```text
fresh badge
stale badge
unavailable hides old numeric values
Client and AP age shown separately
latest partial warning
latest failed warning
complete zero remains valid 0

server age + performance elapsed progresses locally
fresh → stale transition without new response
stale → unavailable transition without new response
```

Do not use `Date.now()` to advance source age after response.

---

# 106. Refresh frontend tests

Minimum:

```text
initial load
manual Refresh
60-second automatic cadence
no overlapping refresh
hidden tab stops timer
visible tab resumes correctly
fixed-delay scheduling
failure backoff 60 → 120 → 300
success resets backoff
429 respects Retry-After + cadence
manual Refresh can bypass waiting backoff
```

Use fake timers where current test style permits.

---

# 107. Independent-failure frontend tests

Minimum:

```text
Client summary success + AP summary failure
AP summary success + Client summary failure
Client summary success + Client page failure
AP summary success + AP page failure
```

One failure does not blank independently valid sections.

---

# 108. Sensitive telemetry tests

Prove no new application telemetry contains:

```text
client_mac
client_ip
ap_mac filter
ssid filter
cursor
cycle_id
source_scope_hash
```

Access request-line query stripping remains covered.

API response may contain internal owner-visible MAC/IP.

Logs may not.

---

# 109. Direct Omada prohibition test

At least one architecture/query test must prove new Admin Home live code has no dependency on:

```text
OmadaProvider
controller factory
requests
list_observation_clients
list_observation_access_points
```

The injected object is only:

```text
CurrentStateReadService-compatible interface
```

---

# 110. Existing frontend regression

Existing tests for:

```text
Home fallback
Devices
Device Card
Visits
Observations
session handling
safe display
MAC parsing
query state
```

must continue to pass.

Feature-disabled Home test must prove legacy Home remains functional.

---

# 111. Backend targeted test gate

Preferred minimum after implementation:

```bash
python -m pytest -q   tests/admin_web   tests/current_state   --tb=short
```

If actual focused files are narrower, Coder may additionally run a narrower first pass, but the combined Admin + Current State suite is mandatory before full suite.

---

# 112. Frontend targeted gate

Run existing Admin frontend test mechanism.

At baseline it is represented by:

```text
tests/admin_web/test_admin_ui_frontend.py
```

Use the repository's actual Node/subprocess mechanism.

Do not introduce a production JS dependency.

---

# 113. Full Linux gate

After targeted tests:

```bash
python -m pytest -q -rs

PYTHONPYCACHEPREFIX=/tmp/captivportal-pyc   python -m compileall -q app

git diff --check
git status --short
```

Record exact:

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

# 114. Pre-change baseline gate

Before first code change, Coder must run:

```bash
git fetch origin
git rev-parse origin/main
git status --short

python -m pytest -q -rs

PYTHONPYCACHEPREFIX=/tmp/captivportal-pyc   python -m compileall -q app

git diff --check
```

Expected architecture baseline:

```text
a864dfa78461ccbfe88e110b1aa5bad5f6bfa23e
```

If `origin/main` is newer:

compare affected paths.

Mandatory impact review if newer changes touch:

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

# 115. Allowed files — Admin Web

Expected existing files:

```text
app/admin_web/config.py
app/admin_web/runtime.py
app/admin_web/query_service.py
app/admin_web/routes.py
app/admin_web/pages.py               # only if page metadata needs narrow change
app/admin_web/templates/admin/home.html
app/admin_web/templates/admin/base.html   # only narrow data attribute/shared control if required
app/admin_web/static/admin.js
app/admin_web/static/admin.css
app/admin_web/policy.py              # only if capability mapping cannot use existing capabilities
```

New small Admin serializer/helper file is allowed if it keeps DTO logic out of routes:

```text
app/admin_web/current_state_serialization.py
```

Preferred over generic source serialization.

---

# 116. Allowed existing composition/config files

Narrow changes:

```text
app/config.py
app/settings.py
.env.example
run.py
```

Only for:

```text
HOME-LIVE feature flag/config
CurrentStateReadService injection into Admin runtime
```

---

# 117. Allowed tests

```text
tests/admin_web/**
```

Narrow Current State test additions only if Tech Lead requires a source-side contract change after DRAFT review:

```text
tests/current_state/**
```

Without such review requirement, `app/current_state/**` is read-only dependency and should not change.

---

# 118. Forbidden source changes by default

Do not change in this task:

```text
app/current_state/repository.py
app/current_state/normalizer.py
app/current_state/client_worker.py
app/current_state/ap_worker.py
app/current_state/cleanup.py
current_state.sqlite3 schema
Current State polling cadence
Current State retention
Current State status classification
Current State source scope
```

Also forbidden:

```text
app/observations/**
app/analytics/** formulas/metrics
app/visit_lifecycle/**
app/visitor_registry/**
app/pending_sessions/**
app/controllers/omada*.py
app/auth/**
app/capport/**
public traffic
portal counter
```

---

# 119. Infrastructure forbidden

Do not change:

```text
Nginx
systemd
Alloy
Loki
Grafana
Omada Controller config
Cisco config
production environment
```

Production environment is changed only by later activation runbook.

---

# 120. No Knowledge Base changes

This runtime TASK does not modify:

```text
AGENTS.md
docs/**
knowledge-base module docs
roadmap docs
```

After production acceptance, Knowledge Base update remains a separate Knowledge Base Lead action.

---

# 121. Pre-code PLAN requirement

Before broad implementation, Coder must return a short PLAN containing:

```text
1. exact baseline SHA
2. files to change
3. CurrentStateReadService injection path
4. four API routes
5. capability mapping
6. DTO serializers
7. query parameter/limit/sort/filter contract
8. cursor pass-through/pinning design
9. feature-flag fallback design
10. Home refresh state machine
11. independent Client/AP failure design
12. frontend test strategy
13. backend test strategy
14. no-Omada proof
15. expected production activation behavior
```

No code should be broadly changed before this PLAN is reviewed under the normal Coder workflow.

---

# 122. Stop conditions

Stop affected implementation and return exact facts if:

- current main materially changed CurrentStateReadService contract;
- current main materially changed Admin API envelope/security;
- CurrentStateReadService cannot be injected without direct repository access;
- current Home cannot be feature-gated without breaking other pages;
- Home needs direct Omada access;
- current-client page requires N+1 source calls;
- source cursor cannot safely survive Admin pass-through;
- cross-Site cursor isolation cannot be guaranteed;
- source scope cannot be exposed safely;
- Admin current-state query causes unbounded scan;
- response cap cannot support configured page size;
- two normal Home loads consistently exhaust Admin concurrency;
- Current State source p95 materially regresses after Admin integration;
- exact counts require partial snapshot data;
- AP unknown/missing cannot be represented without false Offline;
- implementation needs changes outside allowed scope;
- full suite produces a new unclassified product failure.

Independent safe portions may continue only where architecture remains valid.

---

# 123. Backend acceptance criteria

Implementation is code-acceptable only if:

- Admin depends only on `CurrentStateReadService` for live data;
- Current State repository/schema/collectors remain unchanged unless separately approved;
- four exact Site-scoped GET endpoints exist;
- existing Admin auth/network/Site boundary protects them;
- current client summary exact counts come only from complete current-scope snapshot;
- unavailable old snapshot does not expose old values;
- Client/AP snapshot metadata is explicit;
- Client/AP watermarks remain separate;
- current client page is bounded and cycle/scope pinned;
- current AP page is bounded and cycle pinned;
- cursor misuse is rejected;
- API response DTOs are explicit allowlists;
- no MAC/IP/cursor in logs;
- no direct Omada call;
- no write operation;
- response cap and concurrency guard remain active;
- Home feature flag default is false;
- legacy Home remains usable while flag false;
- existing Admin pages remain green.

---

# 124. Frontend acceptance criteria

When feature enabled:

- top cards display Online / Authorized / Waiting / Other-Unknown;
- AP Online/Total displays without invented Offline;
- Client and AP freshness are separate;
- stale values are visibly stale;
- unavailable values are hidden as current;
- Client/AP independent failure is supported;
- Devices by AP reconciles with Online;
- AP Unknown is explicit;
- AP with zero scoped clients remains visible;
- Online Devices uses current snapshot page;
- Load More is cursor-pinned;
- sort/filter are allowlisted;
- counters/uptime use neutral labels;
- no unverified Mbps/Download/Upload/Online-time semantics;
- manual Refresh works;
- auto-refresh is >=60 seconds;
- no overlap;
- hidden tab stops polling;
- retry/backoff is bounded;
- loading/empty/error/session states are explicit;
- no unsafe `innerHTML`.

---

# 125. Production activation boundary

Merge does not enable Live Home.

After merge/Linux acceptance, architect/Tech Lead prepares or executes a separate Owner-controlled activation step.

Pre-activation production state:

```text
WEB_ADMIN_HOME_LIVE_ENABLED=false
```

Deploying code with false must preserve current Home.

---

# 126. Production activation preflight

Before enabling:

```text
exact expected main SHA
clean production tree
current Admin Web enabled/accepted
Current State enabled/accepted
Current State read_service available
Client current complete snapshot available
AP current complete snapshot available
Portal/CAPPORT baseline
Admin login baseline
rollback env backup
rollback git point/tag
```

No source DB backup is required because Home Live is read-only, but current DB is never deleted.

---

# 127. Production activation procedure

Conceptual:

1. verify exact deployed SHA;
2. backup `/etc/default/captive-portal`;
3. verify `WEB_ADMIN_HOME_LIVE_ENABLED` absent/false;
4. set:

```text
WEB_ADMIN_HOME_LIVE_ENABLED=true
```

5. keep refresh:

```text
60 seconds
```

unless separately reviewed;
6. restart `captive-portal.service`;
7. verify service active/running;
8. verify `/` visitor portal behavior;
9. verify CAPPORT behavior;
10. verify Admin login;
11. open Site Home;
12. compare live summary with `CurrentStateReadService`;
13. test Online Devices page/cursor;
14. test manual Refresh;
15. observe one automatic 60s refresh;
16. inspect secret-safe logs;
17. verify Observation/Current State cycles continue;
18. verify no service errors.

---

# 128. Production browser acceptance

From real owner browser:

```text
Home loads
Online exact
Authorized exact
Waiting exact
Other/Unknown exact
AP Online/Total exact
Client freshness visible
AP freshness visible
Devices by AP sums to Online
AP Unknown correct
Online Devices opens
null IP renders —
sort works
filter works
Load More works if enough clients
manual Refresh works
automatic refresh works after >=60s
hidden tab does not keep polling
```

Compare at least one snapshot against direct `CurrentStateReadService` output, not Omada UI-only inference.

---

# 129. Production coexistence acceptance

After activation:

```text
Current State Client cycles continue
Current State AP cycles continue
Observation cycles continue
Visit Lifecycle continues
Registry continues
Analytics remains available
Devices page works
Device Card works
Visits works
Observations works
Portal works
CAPPORT works
```

No new application errors.

---

# 130. Production telemetry acceptance

Verify application/access logs contain no:

```text
live client MAC values from API queries
IP values from current-state table
cursor contents
SSID filter values
source-scope hash values
```

Request-line query stripping remains active.

---

# 131. Production performance acceptance

Record for at least several refresh cycles:

```text
Client summary endpoint durations
Client page endpoint durations
AP summary endpoint durations
AP page endpoint durations

Admin 429 count
Admin 503 count
service errors
```

Target:

```text
summary p95 <= 100 ms
page p95    <= 250 ms
```

If not met, classify reason before acceptance.

---

# 132. Production rollback

Fast feature rollback:

1. restore environment backup or set:

```text
WEB_ADMIN_HOME_LIVE_ENABLED=false
```

2. restart service;
3. confirm legacy Home;
4. confirm Devices/Visits/Observations;
5. confirm Portal/CAPPORT;
6. confirm Current State continues running.

Do NOT disable Current State merely to rollback Home Live.

Do NOT delete `current_state.sqlite3`.

Code rollback is only needed if feature-disabled code itself causes regression.

---

# 133. Rollback acceptance

A production task must prove:

```text
feature can be disabled independently
Admin stays available
Current State stays available
old Home fallback works
Portal/CAPPORT unaffected
```

---

# 134. Coder handoff requirements

Final implementation handoff must contain:

```text
exact baseline SHA
implementation SHA

files changed
new config keys/defaults

four API routes
capability mapping

CurrentStateReadService injection path
proof no repository/Omada dependency

DTO fields
page-size bound
sort allowlist
filter allowlist
cursor semantics

feature-disabled behavior
refresh state machine
hidden-tab behavior
retry/backoff behavior

targeted test results
frontend test results
full test results
compileall
diff-check
working tree

known limitations

production activation NOT performed
```

---

# 135. Known accepted limitations

`HOME-LIVE-01` intentionally retains:

```text
60-second source cadence
near-real-time, not realtime socket stream

device count != people count

client scope != entire Site unless configured so

Controller uptime semantics not yet product-confirmed

trafficDown/trafficUp/trafficTotal units/directions
not yet product-confirmed

AP offline status codes not yet confirmed

Client and AP snapshots are independent observations

multi-page source capture is an observation interval,
not a controller-atomic millisecond snapshot

process-local Admin sessions/concurrency
```

These are not implementation defects.

---

# 136. Tech Lead review questions

Please review explicitly:

1. Is optional `CurrentStateReadService` injection into the existing Admin runtime accepted without making overall Admin runtime health depend on Current State?
2. Are the four proposed routes and capability mapping accepted?
3. Is pass-through of the already cycle/Site/scope-bound Current State cursor accepted, rather than wrapping it in a second Admin cursor?
4. Is Admin page max `250`, default `100` accepted?
5. Is separate `WEB_ADMIN_HOME_LIVE_ENABLED=false` mandatory activation boundary accepted?
6. Is 60-second visible-tab auto-refresh accepted?
7. Is full pause in hidden tabs preferable to a slower hidden cadence?
8. Is bounded error backoff `60 → 120 → 300s` accepted?
9. Is the explicit API decision to omit product `AP offline` until evidence accepted?
10. Are neutral controller labels for uptime/traffic acceptable in this first live table?
11. Is exposing safe `source_scope` + scope hash in authenticated Admin API accepted?
12. Most importantly: is the bounded CurrentStateReadService allowed as a narrow exception to the existing Admin direct-query cancellation requirement, given accepted `p95=4.570ms / max=5.741ms`, or must FINAL add a common cancellable deadline abstraction?

Coder must not decide question 12.

---

# 137. Current authorization status

```text
TASK-HOME-LIVE-01
DRAFT FOR TECH LEAD REVIEW

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
Tech Lead architecture/product review
```

Expected workflow:

```text
DRAFT
→ Tech Lead review
→ Architect incorporates required corrections
→ FINAL
→ separate Owner implementation authorization
→ Coder PLAN
→ implementation/tests
→ Architect static review
→ Tech Lead Linux gate
→ merge/deploy authorization
→ separate production activation
→ production browser/soak acceptance
```

---

# 138. Final architecture intent of this DRAFT

`HOME-LIVE-01` is not a new monitoring stack.

It is the product read boundary over the already accepted Current Network State layer.

The key separation remains:

```text
Current State collects current facts.
CurrentStateReadService owns current-state truth.
AdminQueryService authorizes and bounds reads.
Admin API serializes only safe DTOs.
Home renders near-real-time operational state.
```

No additional source of live truth is introduced.
