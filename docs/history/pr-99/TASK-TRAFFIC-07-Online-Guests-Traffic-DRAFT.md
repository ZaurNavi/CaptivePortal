# TASK-TRAFFIC-07 — Online Guests Traffic — DRAFT

**Project:** CaptivPortal  
**Area:** Admin Console → Traffic  
**Roadmap item:** `TRAFFIC-07 — Online Guests Traffic`  
**Type:** product/application layer over accepted `TRAFFIC-07-READ`  
**Document state:** `DRAFT — FOR OWNER + TECH LEAD ARCHITECTURAL REVIEW`  
**Prepared:** 2026-09-02  
**Implementation authorization:** `NOT GRANTED`  
**Coder / branch / patch / PR / publication / merge / deploy / activation:** `NOT AUTHORIZED`

---

# 1. Executive summary

`TRAFFIC-07` is the product/application layer that exposes the already accepted:

```text
CurrentGuestTrafficReadService
```

inside:

```text
Admin Console → Traffic
```

as a user-visible:

```text
Online Guests Traffic
```

panel.

This TASK does NOT create a new Traffic calculation.

It MUST consume the frozen `TRAFFIC-07-READ` contract without reinterpreting:

```text
Online Guest population
source health
rate evidence
connection continuity
Download / Upload / Total rate
true zero vs null
cursor pinning
population cap
sorting
```

Canonical product question:

```text
Which controller-reported authorized guests are Online now,
and what near-current Download / Upload / Total Traffic rate
is safely available for each of them?
```

The answer remains explicitly:

```text
controller-reported
near-current interval-average
not instantaneous physical/radio proof
not Internet/WAN-only Traffic
```

---

# 2. Current repository baseline

`origin/main` was re-fetched before this DRAFT.

Current `main`:

```text
6fb86fd66e1a41c6969a5482077c011681b8ee2f
```

Current tree:

```text
696fe7f1fc99716cceff9a268ae4f42054faa0be
```

Current main commit:

```text
Merge pull request #98
Analytics: add Online Guest current traffic read foundation
```

`TRAFFIC-07-READ` publication commit:

```text
ae22091a05a5af23be6cf5360661e2c4638882b4
```

PR:

```text
#98
```

Accepted foundation tree:

```text
696fe7f1fc99716cceff9a268ae4f42054faa0be
```

Current production application still references the pre-07-READ production state
until the future TRAFFIC-07 deployment, because the foundation is intentionally
not deployed separately.

Therefore:

```text
TASK-TRAFFIC-07 development parent
=
main@6fb86fd66e1a41c6969a5482077c011681b8ee2f

tree
=
696fe7f1fc99716cceff9a268ae4f42054faa0be
```

Before FINAL and again before implementation authorization:

```text
re-fetch origin/main
re-pin exact SHA/tree
impact-review any drift
```

---

# 3. Current accepted foundation is frozen

`TRAFFIC-07-READ` is:

```text
DONE / ACCEPTED / MERGED
```

Its semantic contract is a dependency, not a subject of this TASK.

Frozen owner:

```text
CurrentGuestTrafficReadService
```

Frozen authoritative source:

```text
Current State
```

Frozen metric identities include:

```text
metric_version =
network_traffic_online_guest_current_rate.v1

population_method =
fresh_complete_current_state_authorized_guest_scope.v1

rate_method =
current_connection_counter_delta_interval_average.v1

baseline_method =
nearest_previous_complete_same_site_scope_cycle.v1

continuity_method =
omada_controller_connection_progress_v1

connection_boundary_observation =
sampled_current_state_evidence_v1
```

Frozen product-independent properties:

```text
one Site-wide current/baseline pair
one coherent read-only SQLite snapshot per semantic result
controller-reported Online Guest population
numeric rate requires accepted uptime progress
frozen/reset/unproven evidence never becomes numeric zero
true zero requires proven continuity + zero delta
Download / Upload directional independence
backend Total canonical
population-wide rate evidence before pagination
page-independent root counts/status
cursor semantic pinning
supported scoped population = 10,000
default read page = 50
max read page = 200
integer total_delta_bytes deterministic ordering
```

`TRAFFIC-07` MUST NOT recreate these calculations.

---

# 4. Product intent

User-visible product name:

```text
Online Guests Traffic
```

Primary operator use case:

```text
See the currently controller-reported authorized guest population
and its near-current Traffic rate,
without leaving the Traffic page.
```

Secondary use cases:

```text
identify which current guest has the highest Total rate
see Download vs Upload direction
see which guests are Online but do not yet have safe rate evidence
see whether Current State source health is healthy/degraded/stale/unavailable
see population-wide rate coverage
page through a large Online Guest population deterministically
```

---

# 5. Product meaning / wording

The product MUST clearly communicate:

```text
Online
=
controller-reported active authorized wireless client
from accepted Current State evidence
```

and:

```text
rate
=
near-current interval-average Mbps
over accepted Current State snapshot evidence
```

It MUST NOT imply:

```text
instantaneous physical Wi-Fi connectivity
instantaneous radio throughput
WAN-only Traffic
Internet-only Traffic
Guest Session Traffic
billing Traffic
completed Visit Traffic
```

Recommended panel helper text:

```text
Controller-reported authorized guests and their near-current Traffic rate
from persisted Current State evidence.
Online status is not an instantaneous physical Wi-Fi presence check.
```

---

# 6. Product position in Admin Console

Existing page:

```text
/admin/sites/<site_id>/traffic
```

No new page.

Recommended panel placement:

```text
1. Current Network Throughput
2. Online Guests Traffic
3. Network Traffic History
4. Period Statistics
5. Peak Load
6. Traffic by AP
7. AP Traffic Share
```

Reason:

```text
Current Network Throughput
and
Online Guests Traffic
```

are both:

```text
current / range-insensitive
```

products.

Historical range panels remain visually grouped below them.

---

# 7. No historical range selector

`Online Guests Traffic` MUST NOT receive:

```text
24h
7d
```

selectors.

It is NOT registered with:

```text
TrafficHistoricalRequestBroker
```

It does NOT use:

```text
Historical Request Admission Guard
```

It does not participate in:

```text
products=history,...
```

projection.

Its current request has no historical range parameter.

---

# 8. Product semantic owner

Product/application owner:

```text
Admin Traffic product layer
```

Metric semantic owner remains:

```text
CurrentGuestTrafficReadService
```

Admin product code MAY:

```text
authorize
invoke
serialize
format
paginate
render
map safe product states
```

Admin product code MUST NOT:

```text
recompute rates
recompute Total
reclassify continuity
invent missing rates
reclassify Online Guest membership
join Observation/Visit/Registry/AuthSession
query Omada
```

---

# 9. Application integration

Recommended composition:

```text
CurrentGuestTrafficReadService
        ↓
AdminQueryService
        ↓
Admin Traffic serializer
        ↓
Admin route
        ↓
CaptivPortalTrafficCoordinator
        ↓
Online Guests Traffic panel
```

No additional semantic service is needed.

---

# 10. Runtime composition

Current Admin runtime must receive the merged foundation service as a dependency.

Recommended new `AdminQueryService` dependency:

```text
current_guest_traffic_read_service
```

Conceptually:

```text
Admin runtime
→ existing CurrentStateReadService
→ CurrentGuestTrafficReadService
→ AdminQueryService
```

No second service instance with different semantics.

No query-time source polling.

---

# 11. Proposed HTTP endpoint

Canonical product endpoint:

```text
GET /admin/api/v1/sites/<site_id>/traffic/online-guests/current
```

This endpoint is:

```text
current
Site-scoped
read-only
same-origin Admin API
```

It is NOT:

```text
/traffic/history
generic Current State client API
internal Analytics API
```

---

# 12. Query parameters

v1 allowed query parameters:

```text
limit
cursor
```

No public:

```text
range
evaluated_at
alternate sort
```

Canonical sort remains:

```text
total_rate_desc
```

Browser treats cursor as opaque.

## limit

Default product request:

```text
50
```

Backend accepted maximum:

```text
200
```

DRAFT recommendation:

```text
UI requests 50 per page
```

## cursor

Opaque accepted READ cursor.

Browser MUST NOT decode/modify/reconstruct it.

---

# 13. Admin query orchestration

Recommended new method:

```text
AdminQueryService.current_online_guest_traffic(...)
```

or equivalent.

Responsibilities:

```text
repeat policy authorization
validate product availability
validate limit/cursor input
call CurrentGuestTrafficReadService exactly once per API request
serialize exact result
use existing Admin query concurrency controls
map safe source/integrity errors
```

It MUST NOT query another source for enrichment.

---

# 14. Shared Admin execution controls

The product MUST use existing:

```text
AdminQueryExecutionControls
```

No separate:

```text
semaphore
query worker
async server queue
scheduler
```

The accepted READ foundation already proved its bounded 10k+10k work shape.

---

# 15. Authorization boundary

Online Guests Traffic exposes client-level identity:

```text
client MAC
name
SSID
AP
rate evidence
```

DRAFT recommendation:

```text
required capability =
admin.read.devices
```

rather than aggregate-only:

```text
admin.read.overview
```

Panel visibility should require:

```text
feature enabled
AND
policy.authorize(principal, "admin.read.devices", Site)
```

The API route MUST independently repeat authorization.

Template visibility is not security.

No new RBAC capability in v1.

---

# 16. Site isolation

Permanent boundary:

```text
one authorized canonical Site
```

Site A request must never expose Site B:

```text
client rows
population
root counts/status
cursor
current/baseline identity
```

Cross-Site cursor:

```text
invalid_request
```

No fallback.

---

# 17. Feature flag

Recommended exact flag:

```text
WEB_ADMIN_TRAFFIC_ONLINE_GUESTS_ENABLED=false
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

It MUST NOT require historical Traffic product flags.

---

# 18. Feature-off behavior

When flag is false:

```text
panel absent
frontend does not register panel
frontend sends no product request
direct product route returns 404 after normal Admin boundary
Traffic page does not invoke CurrentGuestTrafficReadService
```

Existing Traffic semantics remain unchanged.

---

# 19. Enabled product dependency

If the product flag is true but the semantic service is structurally missing,
DRAFT recommendation:

```text
Admin runtime activation/startup fails closed
```

Reason:

```text
enabled product + missing mandatory semantic owner
=
configuration defect
```

Temporary Current State source unavailability remains a runtime product state, not
a startup configuration defect.

Owner + Tech Lead should explicitly accept this before FINAL.

---

# 20. Serialization owner

Add a dedicated serializer, conceptually:

```text
app/admin_web/current_guest_traffic_serialization.py
```

It may:

```text
validate frozen DTO
produce JSON-safe response
preserve null/zero semantics
enforce cross-field invariants
```

It MUST NOT calculate:

```text
rate
Total
population
continuity
rate_evidence_status
cursor
```

---

# 21. Root API serialization

Recommended safe root fields:

```text
metric_version
population_method
rate_method
baseline_method
continuity_method
connection_boundary_observation
unit
site_id
evaluated_at_utc
current_cycle_id
baseline_cycle_id
current_capture_started_at
baseline_capture_started_at
elapsed_seconds
status
source_health_status
source_health_reason
rate_evidence_status
population_complete
scoped_client_row_count
known_authorized_count
unknown_auth_count
population_count
supported_max_population
rate_valid_count
rate_partial_count
rate_unavailable_count
items
```

Do not expose:

```text
source DB path
raw SQL
raw Current State rows
raw cumulative counters
```

---

# 22. Item API serialization

Use accepted READ item fields only:

```text
client_mac
name
ssid
ap_mac
download_mbps
upload_mbps
total_mbps
source_progress_status
connection_continuity_status
continuity_basis
download_reason
upload_reason
total_reason
rate_status
```

No extra joins.

No IP.

No Visit/Registry/AuthSession identity.

---

# 23. Page serialization

Page object:

```text
limit
returned_count
next_cursor
sort
```

Canonical:

```text
sort=total_rate_desc
```

Root status/counts remain page-independent on every page.

---

# 24. Serializer validation

Validate:

```text
exact metric/method identifiers
unit=Mbps
requested Site
allowed root statuses
allowed source-health/rate-evidence statuses
population/count invariants
page bounds
item canonical MAC
numeric rate finite and >=0
null preserved
item rate_status/reasons
```

Malformed internal DTO:

```text
fail closed
→ AdminQueryIntegrityUnavailable
→ safe 503 source_unavailable
```

No partial corrupt serialization.

---

# 25. HTTP success envelope

Use the existing Admin envelope.

Conceptually:

```text
{
  "result": {
    ...root fields...,
    "items": [...]
  },
  "page": {
    "limit": 50,
    "returned_count": ...,
    "next_cursor": "...",
    "sort": "total_rate_desc"
  }
}
```

No parallel envelope.

---

# 26. Cursor-expired HTTP behavior

Preserve accepted:

```text
cursor_expired
```

DRAFT recommendation:

```text
HTTP 400
error.code=cursor_expired
```

Other caller cursor errors:

```text
HTTP 400
error.code=invalid_request
```

Never silently repin or append a fresh page to the old chain.

---

# 27. Source/integrity error mapping

Recommended:

```text
validation
→ 400 invalid_request

cursor_expired
→ 400 cursor_expired

source unavailable
→ 503 source_unavailable

integrity unavailable
→ AdminQueryIntegrityUnavailable
→ 503 source_unavailable
```

Existing:

```text
401 authentication_required
403 forbidden
404 disabled
429 concurrency_limit + Retry-After
503 query_deadline
```

remain shared Admin semantics.

Public errors do not expose integrity details.

---

# 28. User-visible panel structure

Recommended:

```text
Online Guests Traffic
state banner
root summary/meta
table/list
Load more
```

No chart.

This is a current population view, not a historical series.

---

# 29. Panel heading

Recommended:

```text
Eyebrow:
Current guest traffic

Heading:
Online Guests Traffic
```

Helper:

```text
Controller-reported authorized guests and their near-current Traffic rate
from persisted Current State evidence.
Online status is not an instantaneous physical Wi-Fi presence check.
```

Do not call it:

```text
Real-Time Internet Usage
Live Internet Usage
Physical Online Devices
```

---

# 30. Root summary

Recommended visible blocks:

```text
Online Guests
Rate Evidence
Source Health
Observed / Interval
```

## Online Guests

Use:

```text
population_count
population_complete
unknown_auth_count
```

Example:

```text
23 guests
```

or:

```text
23 known guests · population incomplete
```

## Rate Evidence

Use population-wide:

```text
rate_evidence_status
rate_valid_count
rate_partial_count
rate_unavailable_count
```

Example:

```text
18 complete · 2 partial · 3 unavailable
```

Never derive these from visible page rows.

## Source Health

Use exact root source health/reason.

## Observed / Interval

Use:

```text
current_capture_started_at
baseline_capture_started_at
elapsed_seconds
```

This is evidence timing, not a historical selected range.

---

# 31. Table columns

Recommended:

```text
Guest
SSID
AP
Download
Upload
Total
Evidence
```

## Guest

If `name` exists:

```text
name as primary
MAC as subtext/monospace
```

Else:

```text
MAC as primary
```

## SSID

Exact item SSID.

## AP

Exact `ap_mac`.

If null:

```text
—
```

No extra AP-name lookup.

## Rates

Exact backend values.

## Evidence

Use item `rate_status` plus concise reason.

---

# 32. Rate formatting

Presentation-only DRAFT proposal:

```text
>=100 Mbps → 1 decimal
>=1 Mbps   → 2 decimals
0<rate<1   → 3 decimals
0.0        → 0.00 Mbps
null       → —
```

Backend numeric value remains canonical.

Owner + Tech Lead may simplify precision before FINAL.

---

# 33. True zero vs unavailable

Permanent UI distinction:

```text
numeric 0.0
→ 0.00 Mbps
```

Null:

```text
—
```

Never render null as:

```text
0
idle
no traffic
```

unless backend returned true numeric zero.

---

# 34. Item rate states

Accepted item:

```text
valid
partial
unavailable
```

## valid

D/U/Total numeric.

Display:

```text
Valid
```

## partial

At least one usable numeric direction.

Other direction may be:

```text
—
```

Total may be null.

Display:

```text
Partial
```

## unavailable

No usable numeric rate.

D/U/Total:

```text
—
```

Display:

```text
Unavailable
```

Do not remove the Online Guest because rate is unavailable.

---

# 35. Reason mapping

Suggested UI mapping:

```text
no_baseline
→ Waiting for baseline

no_authorized_baseline
→ Waiting for authorized baseline

ssid_transition
→ SSID changed

baseline_gap_too_large
→ Rate interval unavailable

invalid_elapsed
→ Rate interval invalid

counter_missing
→ Counter unavailable

counter_reset
→ Counter reset

connection_reset
→ Connection reset

connection_continuity_unproven
→ Connection continuity unavailable

source_frozen
→ Controller state did not advance

source_progress_unproven
→ Controller progress unavailable

source_quality_untrusted
→ Source evidence unavailable
```

Mapping is presentation only.

---

# 36. Root `ok`

Render normal current state.

If:

```text
population_count>0
```

render items.

If:

```text
population_count=0
rate_evidence_status=not_applicable
```

use normal empty state.

---

# 37. Root `partial`

Keep trusted known-authorized rows visible.

Show warning based on dedicated axes:

```text
source degraded
population incomplete
rate evidence partial
```

Do not flatten every condition into a generic warning if precise cause is
available.

---

# 38. Root `insufficient_data`

A non-empty Online Guest population may exist with no usable rate.

Required:

```text
keep guest rows visible
show rate fields as —
show explanatory warning
```

Suggested:

```text
Guests are Online, but current Traffic rate evidence is not available yet.
```

This is not a source outage.

---

# 39. Root `stale`

Foundation no longer asserts a current population.

Required:

```text
clear current rows
hide Load more
show stale warning
```

Do not leave old rows labelled current Online.

---

# 40. Root `unavailable`

Required:

```text
clear current rows
hide pagination
show unavailable state
```

Do not fabricate:

```text
0 guests
0 Mbps
```

---

# 41. Root `unsupported_population`

When selected scoped Current State population exceeds:

```text
10,000
```

required:

```text
no subset
no first 50/200
no pagination
```

Message:

```text
Online Guests Traffic is unavailable because the current scoped client population
exceeds the supported 10,000-row limit.
No truncated subset is shown.
```

---

# 42. Empty / zero population

Fresh proven:

```text
population_count=0
rate_evidence_status=not_applicable
```

is normal.

Display:

```text
No Online Guests
```

Suggested detail:

```text
No controller-reported authorized guests are present in the current accepted
guest scope.
```

No baseline is needed.

---

# 43. Population incomplete

If:

```text
unknown_auth_count>0
population_complete=false
```

show known authorized guests only.

Warning:

```text
Known authorized guests are shown, but authorization classification is incomplete
for additional Current State rows.
```

Do not list unknown rows as guests.

---

# 44. Source degraded

If current selected complete evidence is fresh but source health is degraded:

```text
known rows remain visible
state warning visible
selected observed timestamp remains explicit
```

Never mix rows from newer degraded attempt.

---

# 45. Sampled boundary limitation in product copy

Do not expose raw architecture identifier unless needed for diagnostics.

But product copy must not promise:

```text
every reconnect is detected
every physical disconnect is detected instantly
```

Safe wording:

```text
Rates follow persisted Controller evidence sampled by Current State.
```

No estimator/timer is added.

---

# 46. Pagination UX

Canonical v1:

```text
Load more
```

Initial:

```text
limit=50
no cursor
```

If `next_cursor` exists, show Load more.

Next request:

```text
limit=50
cursor=<opaque>
```

Successful page appends items only if root semantic identity matches the existing
pinned chain.

---

# 47. Root semantics across pages

Every page MUST match:

```text
source_health_status
rate_evidence_status
population_complete
outer status
rate_valid_count
rate_partial_count
rate_unavailable_count
```

Frontend validates equality before append.

Mismatch:

```text
fail closed
do not append
```

Page-local rows do not recalculate root quality.

---

# 48. Cursor expiration UX

On:

```text
400 cursor_expired
```

required:

```text
do not append
disable old Load more cursor
show:
The current list expired. Refresh to load the latest Online Guests.
```

DRAFT recommendation:

```text
retain already loaded rows only as
Previous snapshot · refresh required
```

They MUST NOT remain asserted current.

No silent same-click repin.

---

# 49. Refresh policy

Reuse:

```text
WEB_ADMIN_TRAFFIC_REFRESH_SECONDS
```

current default:

```text
60
```

and:

```text
WEB_ADMIN_TRAFFIC_REQUEST_TIMEOUT_SECONDS
```

current default:

```text
20
```

No product-specific refresh/timeout setting.

No higher-frequency Omada/Current State polling.

---

# 50. Coordinator registration

Register one panel:

```text
key = online-guests-traffic
autoRefresh = true
```

through:

```text
CaptivPortalTrafficCoordinator
```

Coordinator remains owner of:

```text
visibility lifecycle
AbortController
request timeout
Retry-After/backoff
manual/global refresh
panel in-flight lifecycle
```

No private timer/fetch/AbortController lifecycle.

---

# 51. Historical broker separation

Do NOT register with:

```text
TrafficHistoricalRequestBroker
```

Historical in-flight/admission rules do not gate this current product.

Shared Admin concurrency still applies.

---

# 52. Global Refresh

Global Traffic Refresh refreshes this panel as a new current root request:

```text
no cursor
```

It does not change historical selected ranges.

---

# 53. Scheduled refresh while paginated

DRAFT canonical v1:

```text
scheduled 60s current refresh
→ discard old appended chain
→ request newest first page without cursor
```

No old/new chain mixing.

This may reset pagination while an operator browses >50 guests.

Architect recommendation:

```text
ACCEPT for v1
```

because the product is current.

Owner + Tech Lead may request pause-while-browsing before FINAL if desired.

---

# 54. Load-more request lifecycle

Load more should still use coordinator request ownership.

Recommended frontend state:

```text
pending_cursor
loaded_items
root_identity
next_cursor
```

Click:

```text
set pending_cursor
coordinator.refreshPanel("online-guests-traffic", {manual:true})
```

Panel `load()` uses coordinator-provided `requestJson`.

No unmanaged direct fetch.

After append:

```text
pending_cursor=null
```

---

# 55. Loading behavior

First load:

```text
Loading Online Guests Traffic…
```

No fake zero.

Refresh after prior success may keep content briefly while request is in flight.

If valid response becomes stale/unavailable:

```text
current rows are cleared
```

because backend no longer asserts current population.

---

# 56. Transport failure after prior success

Transport/HTTP failure means no newer semantic result arrived.

DRAFT recommendation:

```text
retain previous rows only if explicitly demoted to:

Previous snapshot · current refresh failed
```

show prior observation time.

Do not label those rows current Online.

Owner + Tech Lead may choose simpler:

```text
clear rows on any failed refresh
```

Architect recommendation:

```text
retain-but-demote
```

---

# 57. First-load failure

No previous success:

```text
no rows
error banner
no pagination
```

No fallback source.

---

# 58. Shared HTTP failure behavior

Use existing Traffic coordinator semantics for:

```text
401 session
403 forbidden
429 busy / Retry-After
503 unavailable/deadline
network failure
```

No product-specific retry scheduler.

On session/permission loss, old rows must not remain asserted current.

---

# 59. Payload gate

DRAFT hard proposal:

```text
200-item success response <= 256 KiB
```

and always:

```text
< WEB_ADMIN_MAX_RESPONSE_BYTES
```

If correct compact DTO exceeds this:

```text
STOP / payload review
```

Do not increase platform response limit automatically.

---

# 60. Product API PERF

Accepted READ foundation already passed 10k+10k Linux PERF.

Product layer adds:

```text
Admin policy/query
serializer
HTTP route/envelope
```

DRAFT endpoint gates on the accepted 10k+10k fixture class:

```text
API50:
p95 <= 1.0s
max <= 1.5s

API200:
p95 <= 1.25s
max <= 1.75s
```

At least:

```text
10 measured runs each
```

Also mandatory:

```text
unexpected 5xx = 0
source writes = 0
payload gate PASS
semantic determinism PASS
```

---

# 61. Product PERF baseline logic

No same-endpoint pre-change baseline exists.

Use:

```text
accepted TRAFFIC-07-READ PERF
```

as dependency reference plus full candidate endpoint timings.

Existing Traffic endpoints require separate non-regression testing.

---

# 62. Frontend capacity

Initial DOM:

```text
50 rows max
```

One response:

```text
200 rows max
```

No load-all.

No client-side 10k sorting.

Backend ordering is canonical.

Load-more may append pages until a scheduled root refresh resets the chain.

---

# 63. Security / privacy

Default visible:

```text
name if present
client MAC
SSID
AP MAC
rates/status
```

Not visible in v1:

```text
IP
Portal token
Visit ID
Registry device ID
AuthSession ID
raw cumulative counters
raw cursor
```

---

# 64. Telemetry

Reuse existing Admin/Traffic observability.

Recommended safe fields:

```text
product=online_guests_traffic
site_id
status
source_health_status
rate_evidence_status
population_complete
scoped_client_row_count
known_authorized_count
unknown_auth_count
rate_valid_count
rate_partial_count
rate_unavailable_count
returned_count
has_next_page
request_duration_ms
response_bytes
failure_reason
cursor_used=true|false
```

Do NOT log:

```text
MAC/name lists
individual rates
raw cursor
raw counters
DB path
SQL
```

Do not create duplicate noisy logging if existing generic request telemetry is
sufficient.

---

# 65. Configuration surface

Expected:

```text
app/config.py
app/settings.py
app/admin_web/config.py
.env.example
docs/configuration.md
```

Add:

```text
WEB_ADMIN_TRAFFIC_ONLINE_GUESTS_ENABLED=false
```

Do NOT add product-specific:

```text
refresh seconds
timeout
population max
```

Reuse accepted/shared constants.

---

# 66. Traffic template

Expected:

```text
app/admin_web/templates/admin/traffic.html
```

Panel only when safely:

```text
traffic_online_guests_enabled
AND
traffic_online_guests_allowed
```

Placement:

```text
after Current Network Throughput
before History
```

No range controls.

---

# 67. Frontend implementation shape

Expected:

```text
app/admin_web/static/admin.js
app/admin_web/static/admin.css
```

Use current Traffic coordinator registration pattern.

No second frontend framework.

No semantic calculation in browser.

---

# 68. Accessibility

Required:

```text
semantic heading
accessible state banner
real Load more button
loading/disabled state
rate evidence not communicated by color only
0.00 Mbps vs — distinguishable without color
table/list labels
```

---

# 69. Feature-off backward compatibility

With flag false:

```text
existing Traffic DOM/product registrations unchanged
no product request
Current Network Throughput unchanged
History unchanged
Statistics unchanged
Peak unchanged
Traffic by AP unchanged
AP Traffic Share unchanged
Independent ranges unchanged
```

Exact regression mandatory.

---

# 70. READ foundation backward compatibility

Product implementation SHOULD NOT modify:

```text
app/analytics/current_guest_traffic.py
app/current_state/read_service.py
accepted CurrentGuestTraffic models/semantics
```

Any necessary semantic change:

```text
STOP
→ TRAFFIC-07-READ architecture amendment
```

Do not hide it in product code.

---

# 71. Expected implementation files

Likely product scope:

```text
app/config.py
app/settings.py
.env.example

app/admin_web/config.py
app/admin_web/runtime.py
app/admin_web/query_service.py
app/admin_web/routes.py
app/admin_web/current_guest_traffic_serialization.py
app/admin_web/templates/admin/traffic.html
app/admin_web/static/admin.js
app/admin_web/static/admin.css

focused tests
```

Expected unchanged:

```text
app/analytics/current_guest_traffic.py
app/current_state/read_service.py
Current State collector/schema
Observation
Visit Lifecycle
Visitor Registry
AuthSession
Omada provider
```

If those expected-unchanged semantic areas are needed:

```text
STOP / architecture review
```

---

# 72. Coder scope boundary

Only after separate Owner implementation authorization.

Coder may own:

```text
feature flag wiring
runtime dependency wiring
Admin query method
serializer
route
template
JS/CSS panel
focused tests
```

Coder must not change frozen read semantics.

Official Central Lab/PERF PASS/FAIL remain Owner + Tech Lead responsibility.

---

# 73. Focused backend tests

Mandatory future tests:

```text
feature default false
flag dependency
flag false route 404
route exact path
allowed args only limit,cursor
default 50
max 200
invalid limit
unknown query arg
malformed cursor
cursor_expired explicit
Site isolation
admin.read.devices authorization
source unavailable
integrity unavailable
shared 429
serializer exact method IDs
serializer Site identity
page-independent root counts
true zero
null
partial direction
unsupported_population
stale/unavailable
no raw source leakage
```

---

# 74. Root status tests

Fixtures:

```text
ok non-zero
ok zero/not_applicable
partial source degraded
partial population incomplete
partial rate evidence
insufficient_data with Online rows
stale
unavailable
unsupported_population
```

Verify exact UI/API behavior.

---

# 75. Item display tests

Mandatory:

```text
name present
name null → MAC primary
AP present
AP null
valid D/U/Total
partial Download-only
partial Upload-only
unavailable
true 0.0
null never 0
reason mapping
no IP/Visit/Registry fields
```

---

# 76. Page-independent root tests

Use >50 Online Guest fixture.

Page 1/page 2 must match exactly:

```text
source_health_status
rate_evidence_status
population_complete
outer status
rate_valid_count
rate_partial_count
rate_unavailable_count
```

Frontend does not recalculate from page items.

Mismatch on append:

```text
fail closed
```

---

# 77. Cursor tests

Mandatory:

```text
first page no cursor
Load more exact next_cursor
append
cursor opaque
cursor_expired no silent restart
cursor disabled after expiry
fresh root refresh resets chain
new root replaces old pages
no mixed chains
```

---

# 78. Coordinator tests

Mandatory:

```text
unique panel key
registered only enabled+allowed
autoRefresh=true
shared refresh seconds
shared timeout
initial coordinator load
scheduled coordinator refresh
Global Refresh
Load more via coordinator
no unmanaged fetch
no private timer
no private AbortController
no HistoricalRequestBroker
no historical admission guard
```

---

# 79. Failure UX tests

Mandatory:

```text
first-load network failure
refresh failure after success
401
403
429
503 source_unavailable
503 query_deadline
200 stale
200 unavailable
200 unsupported
400 cursor_expired
```

If retain-but-demote is accepted, test explicit:

```text
Previous snapshot
```

qualifier.

---

# 80. Security tests

Site A / Site B.

Required:

```text
cross-Site cursor rejected
no Site B row/count/status
route rechecks capability
panel visibility not authorization
feature false route 404
no sensitive item telemetry
```

---

# 81. Payload tests

At 200 items:

```text
response <=256 KiB
< platform max
```

No accidental raw:

```text
Current State rows
cumulative counters
debug evidence
```

---

# 82. Product PERF gate

Linux production-compatible fixture:

```text
10k current scoped rows
+
10k baseline rows
```

Mandatory:

```text
API50 >=10 measured runs
API200 >=10 measured runs
```

DRAFT hard gates:

```text
API50 p95 <=1.0s
API50 max <=1.5s

API200 p95 <=1.25s
API200 max <=1.75s
```

Plus:

```text
0 unexpected 5xx
0 source writes
payload PASS
exact candidate tree pinned
```

---

# 83. Targeted regression

Owner + Tech Lead targeted scope at least:

```text
TRAFFIC-07 product
TRAFFIC-07-READ semantic suite
Admin query/security/policy
Traffic coordinator frontend
Current Network Throughput
History
Statistics
Peak
Traffic by AP
AP Traffic Share
Independent ranges
Current State read regression
```

Candidate regressions:

```text
0
```

---

# 84. Central Lab

Official:

```text
Windows Central Lab V6
or current official successor
```

must PASS exact candidate.

Strict regressions:

```text
0
```

Coder does not own official PASS/FAIL.

---

# 85. Coder local checks

At minimum after implementation:

```text
python compileall for touched Python
node --check for touched JS
git diff --check
focused TASK tests assigned by Tech Lead
```

Broader/official testing remains separate.

---

# 86. Dormant deployment

First production deploy:

```text
FROM GIT
```

with:

```text
WEB_ADMIN_TRAFFIC_ONLINE_GUESTS_ENABLED=false
```

This deploy also introduces the merged `TRAFFIC-07-READ` foundation to production
for the first time.

That is acceptable because the foundation has:

```text
no independent route
no UI
no worker
```

and the product remains off.

---

# 87. Dormant production acceptance

With flag false prove:

```text
captive-portal.service active
NRestarts=0
ExecMainStatus=0
Traffic page healthy
Current Network Throughput healthy
History healthy
Statistics healthy
Peak healthy
Traffic by AP healthy
AP Traffic Share healthy
Online Guests panel absent
direct Online Guests route 404
no product browser request
no new worker
Current State collection unchanged
Omada webhook unaffected
no startup/runtime error
```

---

# 88. Separate activation

Only after dormant PASS and separate Owner authorization:

```text
WEB_ADMIN_TRAFFIC_ONLINE_GUESTS_ENABLED=true
```

Deployment and activation remain separate.

---

# 89. Production browser acceptance

After activation verify at minimum:

```text
panel correct position
current population
name/MAC
SSID
AP
Download
Upload
Total
Evidence
root source health
root rate counts
manual Refresh
scheduled Refresh
Global Refresh
no range selector
other historical ranges unchanged
```

Load-more production check if population naturally permits; synthetic pagination
edge cases remain Lab-owned.

---

# 90. Production semantic acceptance

UI/API wording remains:

```text
controller-reported
near-current interval-average
```

Do not relabel as:

```text
physical connection
real-time Internet usage
```

without architecture amendment.

---

# 91. Rollback

Primary rollback:

```text
WEB_ADMIN_TRAFFIC_ONLINE_GUESTS_ENABLED=false
```

Expected:

```text
panel absent
route 404
existing Traffic active
```

No DB/data rollback.

Foundation may remain deployed dormant.

Code rollback, if required, follows Git deployment governance.

---

# 92. Explicit non-goals

TRAFFIC-07 v1 does NOT implement:

```text
new rate calculation
historical Online Guest Traffic
24h/7d guest rate
guest rate chart
guest Traffic Share
Visit enrichment
Registry enrichment
AuthSession enrichment
IP display
billing/session totals
quota/control
reconnect/block
Internet/WAN classification
SSID aggregate Traffic
physical presence detection
every reconnect detection
AP-to-client allocation
query-time Omada
new collector
new DB/schema/index
new scheduler
new READ cursor/sort semantics
```

---

# 93. Architecture amendment boundary

If product implementation requires changing frozen READ semantics:

```text
STOP
```

Examples:

```text
rate formula
uptime rules
continuity
sampled boundary semantics
Online population
10k cap
cursor fields
root evidence semantics
sorting
Current State schema/index
fallback source
```

Return:

```text
TRAFFIC-07-READ ARCHITECTURAL AMENDMENT REQUIRED
```

No hidden foundation modification.

---

# 94. DRAFT Owner + Tech Lead review questions

## Q1 — Panel position

Accept:

```text
Current Network Throughput
→ Online Guests Traffic
→ historical panels
```

Architect recommendation: `ACCEPT`.

## Q2 — API route

Accept:

```text
GET /admin/api/v1/sites/<site_id>/traffic/online-guests/current
```

with only `limit,cursor`?

Architect recommendation: `ACCEPT`.

## Q3 — Access capability

Accept:

```text
admin.read.devices
```

for identifiable client-level Traffic rows?

Architect recommendation: `ACCEPT`.

## Q4 — Feature flag

Accept:

```text
WEB_ADMIN_TRAFFIC_ONLINE_GUESTS_ENABLED=false
```

depending on Admin + Traffic only?

Architect recommendation: `ACCEPT`.

## Q5 — Columns

Accept:

```text
Guest / SSID / AP / Download / Upload / Total / Evidence
```

with no IP/Visit/Registry enrichment?

Architect recommendation: `ACCEPT`.

## Q6 — Root summary

Accept:

```text
Online Guests / Rate Evidence / Source Health / Observed-Interval
```

with population-wide root counts?

Architect recommendation: `ACCEPT`.

## Q7 — Pagination

Accept:

```text
Load more
50 rows per request
```

using opaque cursor?

Architect recommendation: `ACCEPT`.

## Q8 — Scheduled refresh while paginated

Accept:

```text
60s scheduled refresh
→ newest root first page
→ old appended chain discarded
```

Architect recommendation: `ACCEPT`.

## Q9 — Transport failure after success

Accept:

```text
retain previous rows only when explicitly demoted:
Previous snapshot · current refresh failed
```

Architect recommendation: `ACCEPT`.

## Q10 — stale/unavailable successful semantic result

Accept:

```text
clear current rows
```

because backend no longer asserts current population?

Architect recommendation: `ACCEPT`.

## Q11 — Enabled product + missing semantic dependency

Accept startup/config fail-closed?

Architect recommendation: `ACCEPT`.

## Q12 — Payload

Accept:

```text
200-item response <=256 KiB
```

Architect recommendation: `ACCEPT`.

## Q13 — Product endpoint PERF

Accept:

```text
API50 p95<=1.0s / max<=1.5s
API200 p95<=1.25s / max<=1.75s
```

Architect recommendation: `ACCEPT`.

---

# 95. DRAFT acceptance criteria

A future candidate can be accepted only if FINAL-approved gates prove:

```text
1. CurrentGuestTrafficReadService remains sole metric owner.
2. Product does not recalculate rate/continuity/population.
3. Current State remains only source.
4. No Omada/Observation/Visit/Registry/AuthSession fallback.
5. Site/client access re-authorized.
6. feature default=false.
7. feature-off exact Traffic compatibility.
8. panel below Current Network Throughput and above history.
9. no 24h/7d selector.
10. CaptivPortalTrafficCoordinator remains scheduler/lifecycle owner.
11. no HistoricalRequestBroker/admission guard use.
12. API query contract exact.
13. serializer preserves true zero/null.
14. valid/partial/unavailable item states correct.
15. root status family correct.
16. zero population normal empty state.
17. stale/unavailable does not assert old rows current.
18. population incomplete warning truthful.
19. root rate status/counts page-independent.
20. one cursor chain appended safely.
21. cursor_expired never silently repins.
22. scheduled refresh resets to new current root without mixing chains.
23. backend sort remains authoritative.
24. payload gate PASS.
25. safe telemetry contains no client identity/rates.
26. focused product tests PASS.
27. TRAFFIC-07-READ regression PASS.
28. targeted regression candidate regressions=0.
29. Central Lab strict regressions=0.
30. product Linux PERF PASS.
31. source/write immutability PASS.
32. exact artifact/tree verification PASS.
33. dormant feature-off production PASS.
34. separate activation only after Owner authorization.
35. production browser acceptance PASS.
36. feature disable is primary rollback.
```

---

# 96. DRAFT state

```text
TASK:
TASK-TRAFFIC-07 — Online Guests Traffic

STATUS:
DRAFT — FOR OWNER + TECH LEAD ARCHITECTURAL REVIEW

DEPENDENCY:
TRAFFIC-07-READ
DONE / ACCEPTED / MERGED / FROZEN

TASK DEVELOPMENT PARENT:
main@6fb86fd66e1a41c6969a5482077c011681b8ee2f

TREE:
696fe7f1fc99716cceff9a268ae4f42054faa0be

SEMANTIC OWNER:
CurrentGuestTrafficReadService

PRODUCT SURFACE:
Admin Console → Traffic

PROPOSED PANEL:
Online Guests Traffic

PROPOSED API:
GET /admin/api/v1/sites/<site_id>/traffic/online-guests/current

RANGE:
current / range-insensitive

HISTORICAL BROKER:
NO

TRAFFIC COORDINATOR:
YES

AUTO REFRESH:
YES / shared Traffic 60s default

PAGE:
50 default / 200 backend max

ACCESS:
proposed admin.read.devices

FEATURE FLAG:
WEB_ADMIN_TRAFFIC_ONLINE_GUESTS_ENABLED=false

NEW METRIC SEMANTICS:
NO

READ FOUNDATION CHANGE:
NO

QUERY-TIME OMADA:
NO

OBSERVATION FALLBACK:
NO

VISIT / REGISTRY / AUTHSESSION:
OUT

NEW DB / SCHEMA / INDEX / COLLECTOR:
NO

NEW SCHEDULER:
NO

IMPLEMENTATION AUTHORIZATION:
NOT GRANTED

CODER AUTHORIZATION:
NOT GRANTED

PUBLICATION / MERGE / DEPLOY / ACTIVATION:
NOT AUTHORIZED
```

Next:

```text
Owner + Tech Lead review
→ corrections if required
→ repository re-fetch/rebind
→ FINAL
→ separate Owner implementation authorization
→ Tech Lead decomposition
→ Coder implementation
```

No implementation may begin from this DRAFT.
