# TASK-TRAFFIC-07 — Online Guests Traffic — FINAL

**Project:** CaptivPortal  
**Area:** Admin Console → Traffic  
**Roadmap item:** `TRAFFIC-07 — Online Guests Traffic`  
**Type:** product/application layer over accepted `TRAFFIC-07-READ`  
**Document state:** `FINAL — FOR OWNER + TECH LEAD ACCEPTANCE`  
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

`origin/main` was re-fetched and re-pinned immediately before this FINAL.

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

No repository drift was observed between the accepted DRAFT baseline and the
pre-FINAL re-fetch.

Therefore this FINAL is bound to:

```text
TASK-TRAFFIC-07 development parent
=
main@6fb86fd66e1a41c6969a5482077c011681b8ee2f

tree
=
696fe7f1fc99716cceff9a268ae4f42054faa0be
```

Permanent governance:

```text
re-fetch / re-pin immediately before implementation authorization

impact-review any new drift before Coder work begins
```

If implementation-changing drift affects:

```text
TRAFFIC-07-READ
AdminQueryService
Admin runtime
Traffic coordinator
Traffic route/security contracts
```

then STOP and rebind/review before implementation.

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

The repository after `TRAFFIC-07-READ` contains the class:

```text
CurrentGuestTrafficReadService
```

but does NOT yet compose a runtime instance of that service.

TRAFFIC-07 FINAL therefore requires, only for the enabled product:

```text
existing CurrentStateReadService
        ↓
exactly one CurrentGuestTrafficReadService instance
        ↓
AdminQueryService
```

The semantic instance MUST be constructed from the already existing process-local:

```text
CurrentStateReadService
```

and MUST NOT create:

```text
a second CurrentStateReadService

multiple CurrentGuestTrafficReadService instances with different configuration

a separate source scope

a separate DB connection owner with different semantics
```

Recommended runtime fields, exact names implementation-defined:

```text
traffic_online_guests_state =
disabled | active | unavailable

current_guest_traffic_service =
CurrentGuestTrafficReadService | None
```

Composition rules:

```text
flag=false
→ traffic_online_guests_state=disabled
→ semantic instance need not be composed

flag=true + CurrentGuestTrafficReadService composition succeeds
→ exactly one instance
→ traffic_online_guests_state=active
→ same instance injected into AdminQueryService

flag=true + required semantic instance cannot be composed
→ traffic_online_guests_state=unavailable
→ other Admin/Traffic products remain operational
```

No query-time source polling.

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

# 12. Query parameters and request shape

v1 allowed query parameters are EXACTLY:

```text
limit
cursor
```

Permanent request-shape rule:

```text
unknown parameter
OR
duplicate limit
OR
duplicate cursor
→ HTTP 400
→ error.code=invalid_request
```

This applies even when duplicate values are identical.

No public:

```text
range
evaluated_at
sort
filter
SSID
AP
MAC
```

parameter is accepted in v1.

Canonical sort remains frozen inside `TRAFFIC-07-READ`:

```text
total_rate_desc
```

## limit

Product page bounds come ONLY from frozen `TRAFFIC-07-READ`:

```text
default = 50
max = 200
```

The product MUST NOT inherit:

```text
current_state_page_size
home_traffic_page_size
```

or any generic Admin list default.

If `limit` is absent:

```text
50
```

If supplied, it must parse safely to an integer:

```text
1..200
```

otherwise:

```text
400 invalid_request
```

## cursor

Browser cursor remains opaque.

Browser MUST NOT:

```text
decode
modify
reconstruct
inspect semantic fields
```

inside the READ cursor.

The backend READ cursor remains authoritative semantic pinning.

# 13. Admin query orchestration

Canonical new product method, exact name implementation-defined:

```text
AdminQueryService.current_online_guest_traffic(...)
```

Responsibilities:

```text
repeat admin.read.devices authorization

validate exact product request shape

use frozen TRAFFIC-07-READ page bounds

verify product runtime state

call CurrentGuestTrafficReadService exactly once per API request

serialize the exact returned semantic result

return existing Admin API envelope
```

It MUST NOT query any additional source for enrichment.

The semantic call is synchronous and remains exactly the accepted READ signature:

```text
CurrentGuestTrafficReadService.get_current_guest_traffic(
    site_id,
    *,
    evaluated_at_utc=None,
    limit=...,
    cursor=...,
    sort="total_rate_desc",
)
```

TRAFFIC-07 MUST NOT add a public:

```text
deadline
```

argument to the frozen READ method.

# 14. Shared Admin execution controls and deadline

The product MUST use the existing:

```text
AdminQueryExecutionControls
```

and therefore the existing process-owned Admin concurrency slot/deadline.

Exactly one READ call is executed inside that shared slot.

Frozen deadline integration:

```text
deadline.require_remaining()

→ CurrentGuestTrafficReadService.get_current_guest_traffic(...)

→ deadline.require_remaining()
```

This mirrors the existing synchronous Current State Admin boundary.

Interpretation:

```text
the READ service itself remains deadline-agnostic

the Admin application layer enforces deadline before and after the synchronous
READ call
```

If the second check fails:

```text
AdminQueryDeadline
→ 503 query_deadline
```

No:

```text
private semaphore
private worker
private thread
private query queue
private scheduler
new READ deadline argument
```

is authorized.

# 15. Authorization boundary

Online Guests Traffic exposes client-level identity:

```text
client MAC
name
SSID
AP
rate evidence
```

FINAL:

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

# 17. Feature flag and configuration dependency

Exact feature flag:

```text
WEB_ADMIN_TRAFFIC_ONLINE_GUESTS_ENABLED=false
```

Default:

```text
false
```

Config validation when true requires:

```text
WEB_ADMIN_ENABLED=true
WEB_ADMIN_TRAFFIC_ENABLED=true
```

If either dependency is false:

```text
AdminWebConfigError
```

This is a configuration contradiction.

The flag MUST NOT require:

```text
WEB_ADMIN_TRAFFIC_HISTORY_ENABLED
WEB_ADMIN_TRAFFIC_STATISTICS_ENABLED
WEB_ADMIN_TRAFFIC_PEAK_ENABLED
WEB_ADMIN_TRAFFIC_BY_AP_ENABLED
WEB_ADMIN_TRAFFIC_INDEPENDENT_RANGES_ENABLED
WEB_ADMIN_TRAFFIC_AP_SHARE_ENABLED
```

Online Guests Traffic is an independent current Traffic product.

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

# 19. Product-specific runtime state

Configuration contradiction and optional product runtime unavailability are
different classes.

## disabled

```text
WEB_ADMIN_TRAFFIC_ONLINE_GUESTS_ENABLED=false
```

means:

```text
traffic_online_guests_state=disabled

panel absent

frontend panel not registered

route returns 404

semantic service is not invoked
```

## active

```text
flag=true
+
exactly one CurrentGuestTrafficReadService instance composed successfully
```

means:

```text
traffic_online_guests_state=active

panel available

route active
```

## unavailable

```text
flag=true
+
required CurrentGuestTrafficReadService cannot be composed
```

means:

```text
traffic_online_guests_state=unavailable

product route → 503 source_unavailable

other Admin / Traffic products remain operational
```

The whole Admin Web runtime MUST NOT be marked unavailable solely because this
optional product failed composition.

Recommended UI behavior for product-specific `unavailable` composition state:

```text
authorized panel remains visible as unavailable

frontend does not start an automatic retry loop for a structural composition
failure

direct route remains 503 source_unavailable
```

A normal runtime source outage after successful composition is handled through the
READ/product status/error contract.

Permanent distinction:

```text
configuration invalid
!=
optional product runtime unavailable
```

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

# 22. Item API serialization and frozen READ enums

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

Frozen item enum allowlists:

```text
rate_status:
valid | partial | unavailable
```

```text
source_progress_status:
advanced | frozen | unproven
```

```text
connection_continuity_status:
proven | unproven | reset
```

```text
continuity_basis:
uptime_progress | counters_only_diagnostic | none
```

Frozen emitted v1 reason family:

```text
valid
no_baseline
no_authorized_baseline
ssid_transition
invalid_elapsed
baseline_gap_too_large
connection_continuity_unproven
source_frozen
connection_reset
counter_missing
counter_reset
```

Serializer/UI MUST NOT accept or invent additional reason codes as if they were
part of v1.

Unknown enum/reason from an internal semantic DTO:

```text
fail closed
→ AdminQueryIntegrityUnavailable
```

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

# 24. Serializer validation and exact status-shape matrix

Serializer must validate:

```text
exact metric/method identifiers

unit=Mbps

requested Site identity

allowed root status

allowed source health + safe reason

allowed rate_evidence_status

exact item enum/reason allowlists

population/count invariants

page bounds

cursor shape as an opaque returned string/null

canonical item MAC

numeric rates finite and >=0

true numeric zero preserved

semantic null preserved
```

Malformed internal result:

```text
fail closed
→ AdminQueryIntegrityUnavailable
→ 503 source_unavailable
```

No partial serialization of an impossible DTO.

## Root source-health reason allowlist

Exact frozen source-health reasons:

```text
within_freshness_window
newer_degraded_attempt
older_than_freshness_window
older_than_unavailable_threshold
clock_anomaly
no_complete_snapshot
```

Raw reason strings MUST NOT be displayed directly to the operator.

Safe presentation mapping is frozen in Section 35.

## Exact response-shape matrix

Legend:

```text
NN   = non-null
NULL = must be null
NBL  = nullable according to stated condition
EMPTY = must be empty
YES  = items/page continuation may exist
```

| outer status | current_cycle_id | baseline_cycle_id | population_count | scoped_client_row_count | known_authorized_count | unknown_auth_count | rate_valid/partial/unavailable_count | items | next_cursor |
|---|---|---|---|---|---|---|---|---|---|
| `ok` | NN | NBL | NN | NN | NN | NN | NN | YES/EMPTY | NBL |
| `partial` | NN | NBL | NN | NN | NN | NN | NN | YES/EMPTY | NBL |
| `insufficient_data` | NN | NBL | NN | NN | NN | NN | NN | YES | NBL |
| `stale` | NN | NULL | NULL | NULL | NULL | NULL | NULL | EMPTY | NULL |
| `unavailable` | NBL | NULL | NULL | NULL | NULL | NULL | NULL | EMPTY | NULL |
| `unsupported_population` | NN | NULL | NN | NN | NN | NN | NULL | EMPTY | NULL |

Additional exact constraints follow.

### `ok`

Allowed semantic sub-shapes:

```text
fresh proven zero:
population_count=0
baseline_cycle_id=null
rate_evidence_status=not_applicable
rate_valid_count=0
rate_partial_count=0
rate_unavailable_count=0
items=[]
next_cursor=null
```

or:

```text
fresh supported non-zero population
with healthy/complete root quality
```

For non-zero `ok` with complete numeric rate evidence:

```text
baseline_cycle_id=NN
```

### `partial`

Current population remains asserted.

Therefore:

```text
current_cycle_id=NN
population/scoped/auth counts=NN
rate counts=NN
```

`baseline_cycle_id` is nullable because partial may result from:

```text
source degraded
population incomplete
mixed rate evidence
or insufficient rate evidence combined with another partial root dimension
```

A zero known-authorized population may still be `partial` if:

```text
source degraded
OR
population_complete=false
```

then:

```text
rate_evidence_status=not_applicable
rate counts=0
items=[]
next_cursor=null
```

### `insufficient_data`

Requires a fresh asserted non-zero known-authorized population:

```text
population_count > 0
```

Population and rate counts are non-null.

No usable complete product-level rate can be asserted.

Items remain allowed and are normally returned so the operator can see Online
Guests with unavailable evidence.

### `stale`

A selected complete current cycle exists but is outside the accepted freshness
window.

Required:

```text
current_cycle_id=NN

baseline_cycle_id=null

population_count=null
scoped_client_row_count=null
known_authorized_count=null
unknown_auth_count=null

rate_valid_count=null
rate_partial_count=null
rate_unavailable_count=null

items=[]
next_cursor=null
```

No current population is asserted.

### `unavailable`

Two accepted forms:

```text
no complete selected current cycle
→ current_cycle_id=null
```

or:

```text
a selected current cycle exists but source is unavailable
for example clock anomaly / beyond unavailable threshold
→ current_cycle_id=NN
```

In BOTH forms:

```text
baseline_cycle_id=null

population/scoped/auth counts=null

rate counts=null

items=[]
next_cursor=null
```

No zero population may be fabricated.

### `unsupported_population`

A selected complete scoped population is asserted but exceeds the frozen support
bound.

Required:

```text
current_cycle_id=NN

baseline_cycle_id=null

scoped_client_row_count=NN
known_authorized_count=NN
unknown_auth_count=NN
population_count=NN

rate_valid_count=null
rate_partial_count=null
rate_unavailable_count=null

items=[]
next_cursor=null
```

No truncation.

The current frozen READ emits:

```text
rate_evidence_status=insufficient_data
population_complete=false
```

for this unsupported result shape.

## Page invariants

For all empty terminal shapes:

```text
page.returned_count=0
page.next_cursor=null
```

For returned item shapes:

```text
page.returned_count == len(items)
1 <= page.limit <= 200
page.sort=total_rate_desc
```

Serializer MUST fail closed on any impossible cross-field combination.

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

Preserve accepted READ distinction:

```text
CurrentGuestTrafficValidationError("cursor_expired")
```

Product mapping:

```text
HTTP 400
error.code=cursor_expired
```

Other malformed/invalid cursor cases:

```text
HTTP 400
error.code=invalid_request
```

Never:

```text
silently repin
silently restart page 1
append a fresh semantic root to an old chain
```

Browser cursor remains opaque.

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

Visible summary blocks:

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

Unknown-auth rows are never added to the guest population.

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

These counts refer to the FULL eligible known-authorized population of the pinned
result before pagination.

Never derive them from visible page rows.

## Source Health

Use:

```text
source_health_status
```

plus the safe presentation mapping for `source_health_reason`.

Do not display raw internal reason strings.

## Observed / Interval

Use:

```text
current_capture_started_at
baseline_capture_started_at
elapsed_seconds
```

This is evidence timing, not a historical selected range.

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

Freeze presentation formatting:

```text
rate == 0
→ 0.00 Mbps

0 < rate < 0.001
→ <0.001 Mbps

0.001 <= rate < 1
→ 3 decimals

1 <= rate < 100
→ 2 decimals

rate >= 100
→ 1 decimal

null
→ —
```

Permanent invariant:

```text
positive numeric rate MUST NEVER display as numeric zero
```

Examples:

```text
0.000106 Mbps
→ <0.001 Mbps

0.000000 Mbps
→ 0.00 Mbps only when backend value is exactly numeric zero
```

Formatting is presentation only.

Backend numeric semantics remain canonical.

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

# 35. Safe presentation mappings

Machine reason/status strings are not displayed raw.

## Item reason mapping

Only the frozen v1 reason family is supported:

```text
valid
→ Valid

no_baseline
→ Waiting for baseline

no_authorized_baseline
→ Waiting for authorized baseline

ssid_transition
→ SSID changed

invalid_elapsed
→ Rate interval invalid

baseline_gap_too_large
→ Rate interval unavailable

connection_continuity_unproven
→ Connection continuity unavailable

source_frozen
→ Controller state did not advance

connection_reset
→ Connection reset

counter_missing
→ Counter unavailable

counter_reset
→ Counter reset
```

No other v1 item reason is accepted by the serializer.

## Root source-health reason mapping

Exact safe presentation map:

```text
within_freshness_window
→ Source healthy

newer_degraded_attempt
→ Newer Current State collection attempt degraded

older_than_freshness_window
→ Current State is stale

older_than_unavailable_threshold
→ Current State is too old to assert current guests

clock_anomaly
→ Current State timing is unavailable

no_complete_snapshot
→ No complete Current State snapshot is available
```

UI MUST NOT print raw internal reason strings directly.

Presentation mapping never changes machine semantics.

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

# 47. Cursor-chain frontend root identity

Page-independent root axes/counts alone are not sufficient for append defense.

Frontend MUST create an immutable:

```text
root_identity
```

from the first accepted page.

At minimum it pins and compares:

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

page.sort
```

and the frozen root semantic values:

```text
status
source_health_status
rate_evidence_status
population_complete

scoped_client_row_count
known_authorized_count
unknown_auth_count
population_count

rate_valid_count
rate_partial_count
rate_unavailable_count
```

Every APPEND_CURSOR response MUST match all required identity/root fields before
items are appended.

If ANY required field differs:

```text
FAIL CLOSED

DO NOT APPEND

invalidate pending append state

require a fresh REPLACE_ROOT
```

Backend READ cursor remains authoritative semantic pinning.

Frontend validation is defense-in-depth only and MUST NOT decode the cursor.

# 48. Cursor expiration UX

If APPEND_CURSOR receives:

```text
400 cursor_expired
```

required:

```text
do not append

invalidate old next_cursor

invalidate pending_cursor

stop that appended chain
```

Already loaded rows MAY remain only as explicitly demoted:

```text
Previous snapshot · refresh required
```

with their previous observation timestamp.

They MUST NOT remain visually asserted as current Online Guests.

User/global/scheduled refresh performs:

```text
REPLACE_ROOT
no cursor
```

No silent repin.

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

# 53. Scheduled refresh and operation types

Freeze two distinct frontend panel operations:

```text
REPLACE_ROOT

APPEND_CURSOR
```

## REPLACE_ROOT

Used by:

```text
scheduled 60s refresh

Global Traffic Refresh

normal panel root/manual refresh
```

Before accepting a new root result, REPLACE_ROOT invalidates:

```text
pending_cursor

old next_cursor

old appended-chain root_identity

old append generation
```

It requests:

```text
no cursor
```

and replaces the panel with the newest first page.

## APPEND_CURSOR

Used only by:

```text
Load more
```

It uses the current opaque `next_cursor` and attempts to append to the existing
pinned root.

## Race contract

If a REPLACE_ROOT supersedes an in-flight APPEND_CURSOR:

```text
the old append result MUST NOT render
```

Use the existing:

```text
CaptivPortalTrafficCoordinator
generation
AbortController
```

lifecycle.

No private fetch/abort/generation owner is authorized.

This means the 60s current refresh may reset pagination while the operator is
browsing more than 50 guests.

That behavior is ACCEPTED for v1 because the product represents current state.

# 54. Load-more request lifecycle

Load more is:

```text
APPEND_CURSOR
```

Recommended frontend state:

```text
operation_type
pending_cursor
loaded_items
root_identity
next_cursor
```

User click:

```text
operation_type=APPEND_CURSOR

pending_cursor=current next_cursor

coordinator.refreshPanel(
  "online-guests-traffic",
  {manual:true}
)
```

Panel `load()` uses coordinator-provided:

```text
requestJson
```

No unmanaged direct fetch.

Before append:

```text
validate returned root_identity
```

After successful append:

```text
pending_cursor=null
next_cursor=response.page.next_cursor
```

A later REPLACE_ROOT invalidates the whole previous append chain before the new
root is accepted.

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

Retain-but-demote is allowed ONLY for the following transient failure classes:

```text
network transport failure

429 concurrency_limit

503 source_unavailable

503 query_deadline
```

In those cases previous rows MAY remain only as:

```text
Previous snapshot · current refresh failed
```

with the previous observation timestamp.

They MUST NOT be labelled current Online Guests.

Previous cursor continuation is suspended until a valid continuation/root
operation re-establishes an accepted state.

For security/session failures:

```text
401 authentication_required
403 forbidden
```

required immediately:

```text
clear client rows

clear next_cursor

clear pending_cursor

clear root_identity

clear appended-chain state
```

Identifiable client data MUST NOT remain visible after session/permission loss.

For successful semantic results:

```text
200 stale
200 unavailable
```

required:

```text
clear current rows
clear cursor/chain
hide Load more
```

because the semantic owner no longer asserts a current population.

For:

```text
400 cursor_expired
```

already loaded data may remain only as the explicitly demoted previous snapshot
defined in Section 48.

All other unclassified failure types default to fail-closed presentation rather
than retaining identifiable client data.

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

Use existing Traffic coordinator HTTP classification and lifecycle.

Exact product retention policy:

```text
network / 429 / 503 source_unavailable / 503 query_deadline
→ previous data may be retained only as explicitly demoted previous snapshot
```

```text
401 / 403
→ clear identifiable rows and all cursor/root identity state
```

```text
200 stale / 200 unavailable
→ clear current rows and pagination
```

```text
400 cursor_expired
→ no append; old rows may remain only as demoted previous snapshot
```

No product-specific retry scheduler.

No fallback source.

# 59. Payload acceptance budget

Freeze TRAFFIC-07 acceptance budget:

```text
API200 serialized success response <= 256 KiB
```

This is an:

```text
acceptance / product optimization budget
```

It is NOT a new runtime rejection threshold.

Existing:

```text
WEB_ADMIN_MAX_RESPONSE_BYTES
```

remains the runtime hard response-size boundary.

Therefore:

```text
API200 > 256 KiB
but < WEB_ADMIN_MAX_RESPONSE_BYTES
→ candidate FAIL
→ payload/product optimization review
```

It does NOT authorize:

```text
new product response-limit env

new hidden runtime global limit

automatic platform limit increase
```

If the existing platform hard limit is exceeded, existing response-too-large
behavior applies independently.

# 60. Product API PERF

Frozen product gates:

```text
API50:
p95 <= 1.0s
max <= 1.5s

API200:
p95 <= 1.25s
max <= 1.75s

>=10 measured runs each
```

Fixture:

```text
10,000 current scoped rows
+
10,000 baseline rows
```

Timed boundary MUST cover the complete authenticated product endpoint path:

```text
authenticated Admin HTTP request

→ Admin security/session boundary

→ Site resolution

→ admin.read.devices policy

→ AdminQueryExecutionControls slot/deadline

→ deadline.require_remaining()

→ CurrentGuestTrafficReadService

→ deadline.require_remaining()

→ product serializer

→ Admin success envelope

→ JSON serialization

→ existing response-size enforcement

→ finalized HTTP response
```

A direct:

```text
CurrentGuestTrafficReadService call
```

or:

```text
AdminQueryService call without HTTP/JSON boundary
```

does NOT qualify as product API PERF.

Mandatory additionally:

```text
unexpected 5xx = 0

source writes = 0

payload acceptance budget PASS

semantic determinism PASS

exact candidate tree pinned
```

No redefinition of accepted READ PERF.

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

Recommended safe structured fields:

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

`failure_reason` MUST be a safe finite product/public category.

Recommended finite categories include:

```text
invalid_request
cursor_expired
authentication_required
forbidden
concurrency_limit
source_unavailable
query_deadline
response_too_large
network_failure
integrity_unavailable
unexpected
```

Telemetry MUST NEVER log:

```text
exception text

client MAC

client name

individual rate values

raw cursor

decoded cursor

counter values

SQL

DB path

full query string containing cursor
```

Cursor telemetry is ONLY:

```text
cursor_used=true|false
```

If existing generic Admin telemetry already provides a field safely, do not
duplicate noisy logging.

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

# 68. Accessibility and presentation-only review

Required product accessibility:

```text
semantic heading

accessible state banner

real Load more button

loading/disabled state

rate evidence not communicated by color only

0.00 Mbps vs — distinguishable without color

table/list labels

Previous snapshot state communicated textually
```

Before Coder implementation is frozen, a presentation-only pass by:

```text
Web Designer / Admin Console UI Designer
```

is RECOMMENDED for:

```text
table density

mobile/narrow width behavior

summary blocks

warning hierarchy

Load more placement

Previous snapshot state

accessibility
```

This presentation review has NO authority to change:

```text
TRAFFIC-07-READ semantics

rate states

source meaning

API contract

security/access boundary

pagination semantics

refresh race contract
```

Any such requested change returns to Owner + Tech Lead architecture review.

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

flag=true requires WEB_ADMIN_ENABLED + WEB_ADMIN_TRAFFIC_ENABLED

flag does not require historical Traffic products

flag=false → disabled state / route 404 / no composition request

flag=true + semantic composition healthy
→ exactly one CurrentGuestTrafficReadService instance
→ active

flag=true + semantic composition failure
→ product unavailable
→ route 503 source_unavailable
→ other Admin/Traffic remain operational

unknown query parameter → 400 invalid_request

duplicate limit → 400 invalid_request

duplicate cursor → 400 invalid_request

default product limit=50

product max limit=200

product limit does not inherit current_state_page_size/home_traffic_page_size

invalid limit → 400

malformed cursor → 400

cursor_expired → explicit 400 cursor_expired

admin.read.devices authorization

Site isolation

shared Admin concurrency

deadline pre-check and post-check around exactly one READ call

no READ deadline argument

serializer exact metric/method IDs

serializer exact item enums/reasons

serializer exact root source-health reasons

serializer status-shape matrix

serializer fresh proven zero

serializer stale/unavailable non-assertion

serializer unsupported_population asserted counts + null rate counts

serializer true zero preserved

serializer null preserved

serializer partial direction

no raw counter/source leakage
```

# 74. Root status and serializer-matrix tests

Mandatory fixtures:

```text
ok + non-zero population

ok + fresh proven zero / not_applicable

partial + source degraded

partial + population incomplete

partial + mixed rate evidence

partial + zero population with degraded/incomplete root

insufficient_data + non-zero Online rows

stale

unavailable + no complete snapshot

unavailable + selected cycle but unavailable freshness/timing

unsupported_population
```

For every fixture assert the exact Section 24 matrix:

```text
cycle IDs

population/scoped/auth count nullability

rate-count nullability

items allowed/empty

next_cursor allowed/null

rate_evidence_status

population_complete
```

Impossible cross-field combination:

```text
serializer fail closed
```

# 75. Item display and enum tests

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

positive 0.000106 Mbps → <0.001 Mbps

positive numeric rate never renders 0

null never renders 0

every frozen item reason mapping

every frozen source health reason mapping

unknown item enum/reason → fail closed

unknown root source-health reason → fail closed

no IP/Visit/Registry fields
```

# 76. Page-independent root / identity tests

Use >50 Online Guest fixture.

Page 1 and APPEND_CURSOR page must match exact:

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
page.sort

status
source_health_status
rate_evidence_status
population_complete

scoped_client_row_count
known_authorized_count
unknown_auth_count
population_count

rate_valid_count
rate_partial_count
rate_unavailable_count
```

Frontend MUST NOT recalculate root quality from page rows.

Any mismatch:

```text
FAIL CLOSED
DO NOT APPEND
```

# 77. Cursor and operation-race tests

Mandatory:

```text
first REPLACE_ROOT has no cursor

Load more = APPEND_CURSOR

APPEND_CURSOR uses exact opaque next_cursor

browser never decodes cursor

successful append validates root_identity

cursor_expired never silently restarts

cursor_expired invalidates old next_cursor

scheduled refresh = REPLACE_ROOT

Global Refresh = REPLACE_ROOT

REPLACE_ROOT clears pending_cursor/old next_cursor/old root_identity

new root replaces old appended pages

no mixed cursor chains
```

Race:

```text
APPEND_CURSOR in flight

→ REPLACE_ROOT supersedes it

→ old append result must not render
```

Use existing coordinator generation/AbortController lifecycle.

# 78. Coordinator tests

Mandatory:

```text
unique panel key

registered only when feature enabled + capability allowed + product active

product unavailable composition state does not create retry storm

autoRefresh=true when active

shared Traffic refresh seconds

shared Traffic timeout

initial REPLACE_ROOT through coordinator

scheduled REPLACE_ROOT through coordinator

Global Refresh through coordinator

APPEND_CURSOR through coordinator

generation supersession protects root/append race

no unmanaged fetch

no private timer

no private AbortController

no private scheduler

no HistoricalRequestBroker

no historical admission guard
```

# 79. Failure UX / security tests

Mandatory:

```text
first-load network failure

refresh network failure after success

429 after success

503 source_unavailable after success

503 query_deadline after success

401 after success

403 after success

200 stale after success

200 unavailable after success

200 unsupported_population

400 cursor_expired
```

Expected:

```text
network / 429 / approved 503
→ retain only as Previous snapshot · current refresh failed
```

```text
401 / 403
→ clear rows + cursor + pending cursor + root identity
```

```text
200 stale / unavailable
→ clear rows + pagination
```

```text
cursor_expired
→ no append
→ may retain only demoted previous snapshot
→ no silent repin
```

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

At API200:

```text
serialized success <= 256 KiB
```

This is an acceptance budget.

Also prove:

```text
serialized success < WEB_ADMIN_MAX_RESPONSE_BYTES
```

If:

```text
>256 KiB but < platform max
```

candidate:

```text
FAIL
→ payload optimization/review
```

Do not introduce/increase a runtime limit as a consequence.

Verify absence of accidental:

```text
raw Current State rows
cumulative counters
debug evidence
```

# 82. Product PERF gate

Linux production-compatible fixture:

```text
10k current scoped rows
+
10k baseline rows
```

Mandatory full HTTP-path measurements:

```text
API50 >=10 measured runs
API200 >=10 measured runs
```

Hard gates:

```text
API50:
p95 <= 1.0s
max <= 1.5s

API200:
p95 <= 1.25s
max <= 1.75s
```

Timed path includes:

```text
authenticated HTTP
Site resolution
admin.read.devices
AdminQueryExecutionControls
READ service
serializer
Admin envelope
JSON serialization
response-size enforcement
final response
```

Plus:

```text
unexpected 5xx=0
source writes=0
payload budget PASS
semantic determinism PASS
exact candidate tree pinned
```

Direct READ/AdminQueryService timings alone do NOT satisfy this gate.

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

This deploy also introduces the already merged `TRAFFIC-07-READ` foundation code
to production for the first time.

That is acceptable because with the product disabled:

```text
no Online Guests route surface is active

no Online Guests panel is registered

no product query runs

no new worker exists
```

Deployment remains separate from activation.

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

# 94. Owner + Tech Lead review disposition — frozen

Tech Lead review disposition is incorporated.

Frozen decisions:

```text
Q1 Panel position
ACCEPT

Current Network Throughput
→ Online Guests Traffic
→ Network Traffic History
→ remaining historical panels
```

```text
Q2 API route
ACCEPT

GET /admin/api/v1/sites/<site_id>/traffic/online-guests/current
```

```text
Q3 access capability
ACCEPT

admin.read.devices
```

```text
Q4 feature flag
ACCEPT

WEB_ADMIN_TRAFFIC_ONLINE_GUESTS_ENABLED=false
```

```text
Q5 columns
ACCEPT

Guest / SSID / AP / Download / Upload / Total / Evidence
```

```text
Q6 root summary
ACCEPT

Online Guests / Rate Evidence / Source Health / Observed-Interval
+
population-wide root rate counts
```

```text
Q7 pagination
ACCEPT

Load more
opaque READ cursor
50 default / 200 max
```

```text
Q8 scheduled refresh while paginated
ACCEPT WITH RACE CONTRACT

REPLACE_ROOT vs APPEND_CURSOR
existing coordinator generation/AbortController owns supersession
```

```text
Q9 transport failure retention
ACCEPT WITH SECURITY RESTRICTION

retain/demote only for approved transient failures

401/403 clear identifiable data
```

```text
Q10 stale/unavailable successful semantic result
ACCEPT

clear current rows and Load more
```

```text
Q11 product dependency
REVISED / FROZEN

optional product unavailable MUST NOT fail whole Admin runtime
```

```text
Q12 API200 payload
ACCEPT

<=256 KiB as acceptance budget, NOT runtime rejection threshold
```

```text
Q13 product PERF
ACCEPT

API50 p95<=1.0s / max<=1.5s

API200 p95<=1.25s / max<=1.75s

full authenticated HTTP endpoint path
```

Additional freezes:

```text
unknown/duplicate query shape → 400

exact READ enums/reasons only

positive rate never renders numeric zero

explicit frontend root_identity

exact serializer status-shape matrix

single CurrentGuestTrafficReadService runtime instance when active

READ signature unchanged

deadline pre/post checks in Admin layer
```

No unresolved architectural review question remains in this FINAL.

# 95. FINAL acceptance criteria

A future implementation candidate can be accepted only if it proves:

```text
1. CurrentGuestTrafficReadService remains the sole metric semantic owner.

2. Exactly one semantic service instance is composed for active product use.

3. Current State remains the only authoritative source.

4. No query-time Omada/Observation/Visit/Registry/AuthSession fallback exists.

5. Frozen READ signature is unchanged; no public deadline argument is added.

6. Admin deadline pre/post checks wrap exactly one synchronous READ call.

7. Site/client access is independently re-authorized with admin.read.devices.

8. Feature flag defaults false.

9. flag=true requires Admin + Traffic config, not historical product flags.

10. product composition failure marks only Online Guests product unavailable.

11. feature-off exact Traffic compatibility PASS.

12. panel is below Current Network Throughput and above historical panels.

13. no 24h/7d selector.

14. CaptivPortalTrafficCoordinator remains browser scheduler/lifecycle owner.

15. no HistoricalRequestBroker/admission guard use.

16. exact query contract limit/cursor only.

17. unknown or duplicate query parameter shape is 400 invalid_request.

18. page bounds are READ 50 default / 200 max, not inherited generic sizes.

19. serializer exact status-shape matrix PASS.

20. serializer accepts only frozen READ item enums/reasons and source-health reasons.

21. serializer fails closed on impossible/unknown internal DTO shape.

22. true zero renders numeric 0.00 Mbps.

23. positive numeric rate never renders numeric zero.

24. null renders — and never 0.

25. valid/partial/unavailable item states render correctly.

26. root status family renders correctly.

27. fresh proven zero is normal empty state.

28. stale/unavailable does not leave old rows asserted current.

29. population incomplete displays known authorized rows + truthful warning.

30. root source health reasons use safe presentation mapping, not raw strings.

31. root rate status/counts remain population-wide/page-independent.

32. frontend root_identity matches across APPEND_CURSOR pages.

33. any root identity mismatch fails closed and does not append.

34. cursor_expired never silently repins.

35. REPLACE_ROOT and APPEND_CURSOR race contract PASS.

36. superseded append result never renders.

37. approved transient failures retain data only as demoted previous snapshot.

38. 401/403 clear identifiable rows/cursor/root identity.

39. 200 stale/unavailable clears rows/pagination.

40. backend sort remains authoritative.

41. API200 <=256 KiB acceptance budget PASS.

42. platform response-size hard boundary remains unchanged.

43. safe telemetry contains no identity/rate/cursor/exception details.

44. focused product tests PASS.

45. TRAFFIC-07-READ regression PASS.

46. targeted Traffic/Admin/Current State candidate regressions=0.

47. Central Lab strict regressions=0.

48. full authenticated endpoint Linux PERF PASS.

49. source/write immutability PASS.

50. exact candidate artifact/tree verification PASS.

51. presentation-only Web Designer pass may refine layout without semantic changes.

52. dormant feature-off production PASS.

53. deployment and activation remain separate Owner-controlled steps.

54. production browser acceptance PASS.

55. disabling feature is primary rollback.
```

# 96. FINAL state

```text
TASK:
TASK-TRAFFIC-07 — Online Guests Traffic

STATUS:
FINAL — FOR OWNER + TECH LEAD ACCEPTANCE

DEPENDENCY:
TRAFFIC-07-READ
DONE / ACCEPTED / MERGED / FROZEN

TASK DEVELOPMENT PARENT:
main@6fb86fd66e1a41c6969a5482077c011681b8ee2f

TREE:
696fe7f1fc99716cceff9a268ae4f42054faa0be

PRE-FINAL RE-FETCH:
PASS

REPOSITORY DRIFT:
NONE

SEMANTIC OWNER:
CurrentGuestTrafficReadService

RUNTIME SEMANTIC INSTANCE:
exactly one when product active

PRODUCT RUNTIME STATE:
disabled | active | unavailable

PRODUCT SURFACE:
Admin Console → Traffic

PANEL:
Online Guests Traffic

API:
GET /admin/api/v1/sites/<site_id>/traffic/online-guests/current

QUERY:
limit | cursor only

DUPLICATE/UNKNOWN QUERY:
400 invalid_request

RANGE:
current / range-insensitive

HISTORICAL BROKER:
NO

TRAFFIC COORDINATOR:
YES

FRONTEND OPERATIONS:
REPLACE_ROOT | APPEND_CURSOR

AUTO REFRESH:
YES / shared Traffic 60s default

PAGE:
50 default / 200 max
from TRAFFIC-07-READ bounds

ACCESS:
admin.read.devices

FEATURE FLAG:
WEB_ADMIN_TRAFFIC_ONLINE_GUESTS_ENABLED=false

FLAG DEPENDENCY:
WEB_ADMIN_ENABLED + WEB_ADMIN_TRAFFIC_ENABLED only

OPTIONAL PRODUCT COMPOSITION FAILURE:
product unavailable / route 503
other Admin products stay operational

READ PUBLIC DEADLINE ARG:
NO

ADMIN DEADLINE:
require_remaining before + after one READ call

SERIALIZER:
exact status-shape matrix / fail closed

ITEM ENUM/REASON FAMILY:
frozen READ v1 only

RATE FORMAT:
positive value never displays numeric zero

CURSOR:
opaque backend pin
+
frontend root_identity defense-in-depth

TRANSIENT FAILURE RETENTION:
demoted previous snapshot only

401 / 403:
clear identifiable client state

200 stale / unavailable:
clear current rows

PAYLOAD:
API200 <=256 KiB acceptance budget

PLATFORM RESPONSE LIMIT:
unchanged

PERF:
API50 p95<=1.0s max<=1.5s
API200 p95<=1.25s max<=1.75s
full authenticated HTTP path
>=10 runs each

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

NEW SCHEDULER / WORKER:
NO

IMPLEMENTATION AUTHORIZATION:
NOT GRANTED BY THIS FINAL

CODER AUTHORIZATION:
NOT GRANTED

PUBLICATION:
NOT AUTHORIZED

MERGE:
NOT AUTHORIZED

PRODUCTION DEPLOY:
NOT AUTHORIZED

ACTIVATION:
NOT AUTHORIZED
```

Expected next state after Owner + Tech Lead acceptance:

```text
FINAL:
OWNER + TECH LEAD ACCEPTED

ARCHITECTURE:
CLOSED

IMPLEMENTATION:
READY FOR SEPARATE OWNER AUTHORIZATION
```

Before implementation authorization:

```text
re-fetch / re-pin origin/main again

impact-review drift
```

No implementation may begin from FINAL acceptance alone.

