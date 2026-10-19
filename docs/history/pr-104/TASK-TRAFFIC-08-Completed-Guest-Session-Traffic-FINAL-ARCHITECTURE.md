# TASK-TRAFFIC-08 — Completed Guest Session Traffic — FINAL ARCHITECTURE

**Project:** CaptivPortal  
**Area:** Admin Console → Traffic  
**TASK:** `TASK-TRAFFIC-08 — Completed Guest Session Traffic`  
**State:** `FINAL ARCHITECTURE — FOR OWNER + TECH LEAD FINAL ACCEPTANCE`  
**Prepared:** 2026-09-06  
**Repository:** `main@3761981f4b1ec30b330abe1eec1713f15191c711`  
**Tree:** `2e6ac33f1033c1f0587407a2476ca852373a04e6`  
**Implementation authorization:** `NOT GRANTED`  
**Coder authorization:** `NOT GRANTED`  
**Publication / merge / deploy / activation:** `NOT AUTHORIZED`

---

# 1. Repository binding

Immediately before issuing this FINAL, `origin/main` was re-fetched.

```text
main =
3761981f4b1ec30b330abe1eec1713f15191c711

tree =
2e6ac33f1033c1f0587407a2476ca852373a04e6

drift =
NONE
```

Current `main` is docs-only PR #103 over application-code baseline:

```text
6fbc3736085be9d0538d893b6e9569ff490ef7f4
```

No application-code/schema drift blocks this FINAL.

Before any later implementation authorization:

```text
re-fetch origin/main
re-pin exact SHA/tree
impact-review drift
```

---

# 2. Prerequisite status

Accepted prerequisites:

```text
TASK-TRAFFIC-PROJECTION-01
= COMPLETE / PRODUCTION ACTIVE

TASK-DB-BASELINE-SYNC-01
= CLOSED / PASS

FINAL_DB_BASELINE
= PASS

BLOCKERS_FOR_TRAFFIC_08
= NONE
```

TRAFFIC-08 is no longer frozen.

---

# 3. Tech Lead review disposition

`ARCHITECTURAL DRAFT v2` review:

```text
TECH_LEAD_REVIEW = PASS WITH FINALIZATION NOTES

Q1_PROJECTION_BOUNDARY = ACCEPT
Q2_24H_ATTRIBUTION_CAP = ACCEPT
Q3_STRICT_NEW_EVIDENCE_PRIMITIVE = ACCEPT
Q4_SEPARATE_ENDPOINT_SAME_HISTORICAL_LANE = ACCEPT

BLOCKERS_FOR_FINAL_ARCHITECTURE = NONE
FINAL_ARCHITECTURE = AUTHORIZED
```

The only requested finalization additions are now frozen in this document:

```text
exact item evidence roll-up
exact cursor validation
```

No redesign was performed.

---

# 4. Product goal

Provide an Admin Traffic product showing:

```text
completed guest Visits

+
Download / Upload / Total bytes safely observed
from accepted persisted client Observation intervals
inside each Visit

+
explicit evidence quality
```

The product MUST NOT claim:

```text
billing-exact Traffic
packet-perfect Traffic
exact controller connection Traffic
full-session zero merely from sampled zero
```

---

# 5. Product identity

Canonical product name:

```text
Completed Guest Session Traffic
```

Canonical lifecycle identity:

```text
Visit
```

Canonical session identity:

```text
visit_id
```

MAC is correlation context only.

MAC is NOT the session identity.

---

# 6. Metric contracts

Frozen:

```text
metric_version =
network_traffic_completed_guest_session_observed_bytes.v1

session_method =
closed_visit_completion_cohort.v1

attribution_method =
visit_window_observation_counter_interval_sum.v1

continuity_method =
observation_uptime_progress.v1

unit =
bytes
```

---

# 7. Semantic owner

Canonical semantic owner:

```text
CompletedGuestSessionTrafficReadService
```

Recommended domain:

```text
app/analytics
```

It owns:

```text
closed Visit cohort selection
Visit/session identity
correlation
authorization-boundary segmentation
SSID-boundary validation
uptime continuity
directional counter-delta acceptance
D/U/T observed bytes
item evidence quality
root status
cursor semantics
bounded pagination
```

It is:

```text
read-only
no polling
no writes
no scheduler
```

---

# 8. Authoritative sources

Session/lifecycle authority:

```text
Visit Lifecycle
```

Directional Traffic authority:

```text
persisted client Observation
```

Native source path:

```text
Visit Lifecycle
+
client Observation
→ CompletedGuestSessionTrafficReadService
```

This is not a fallback path.

---

# 9. Existing Historical Traffic Projection boundary

Frozen:

```text
historical_traffic_projection.v1
=
NO-TOUCH
NOT A TRAFFIC-08 SOURCE
```

The existing Projection remains dedicated to AP/network historical products:

```text
History
Statistics
Peak
Traffic by AP
AP Share
```

TRAFFIC-08 MUST NOT:

```text
allocate AP Traffic to Visits
use AP Share to estimate session Traffic
read AP/network projection as session Traffic truth
extend projection schema ad hoc
change projection semantic contract
trigger a global Projection rebuild
```

If bounded native session/client reads later fail accepted capacity gates:

```text
STOP
→ separate client/session projection architecture
```

Do not mutate AP/network Projection opportunistically.

---

# 10. Session semantics

Completed Guest Session:

```text
one persisted VisitRecord
where status='closed'
for the authorized canonical Site
```

Start:

```text
session_start = visit.started_at
```

End:

```text
session_end = visit.closed_at
```

Duration:

```text
session_duration = visit.duration_seconds
```

Open Visits:

```text
excluded
```

TRAFFIC-08 does not synthesize Visit closure.

---

# 11. Completion cohort

Historical range selects by completion:

```text
visit.closed_at >= from_utc
AND
visit.closed_at < to_utc
```

A Visit may begin before `from_utc` and still belong to the selected cohort if
it closes within the range.

The selected product range does not clip Traffic attribution.

---

# 12. Full Visit attribution window

For a supported Visit:

```text
attribution_start = visit.started_at
attribution_end   = visit.closed_at
```

Observation eligibility interval:

```text
[visit.started_at, visit.closed_at)
```

Forbidden:

```text
pre-Visit counter anchor
post-close counter anchor
selected-range clipping
proportional extrapolation
```

---

# 13. Correlation model

Canonical correlation context:

```text
Site
+
visit_id
+
Visit.client_mac
+
Visit time window
```

Rules:

```text
different visit_id = different session
same MAC across sequential Visits = not merged
randomized MAC = not merged through Registry
AuthSession = not session identity
repeated authorization = same Visit, but interval boundary
AP roam = same Visit
SSID transition = same Visit, but interval boundary
```

---

# 14. Eligible Observation source evidence

An Observation row may participate only when all apply:

```text
same canonical Site
same Visit client MAC
observed_at inside Visit window
source cycle kind='client'
cycle state='completed'
cycle complete=1
cycle result='success'
source_inventory_complete=1
```

No numeric Traffic is accepted from:

```text
running
partial
failed
shutdown
incomplete
```

client source cycles.

---

# 15. Existing Visit Analytics boundary

Existing:

```text
AnalyticsSourceGateway.visit_observed_traffic_batch()
VisitAnalyticsService.get_visit_traffic_summary()
visit.traffic.v1
```

remain unchanged.

Their semantics MUST NOT be silently tightened or redefined by TRAFFIC-08.

TRAFFIC-08 requires a new strict bounded primitive, working name:

```text
completed_visit_traffic_evidence_batch(...)
```

Reuse is limited to:

```text
batching patterns
SQLite/index conventions
deadline helpers
validation helpers
telemetry conventions
```

---

# 16. Candidate interval

Within one Visit, eligible client samples are ordered:

```text
observed_at ASC
row_id ASC
```

For consecutive samples:

```text
P → C
```

candidate interval is:

```text
(P.observed_at, C.observed_at]
```

---

# 17. Elapsed/gap gate

```text
elapsed_seconds =
C.observed_at - P.observed_at
```

Accepted only if:

```text
0 < elapsed_seconds <= 180
```

Frozen:

```text
MAX_GAP_SECONDS = 180
```

Reasons:

```text
invalid_elapsed
gap_too_large
```

---

# 18. Mandatory connection continuity

Persisted `uptime` is mandatory.

Exact classification:

```text
P.uptime present
C.uptime present
C.uptime > P.uptime
→ continuity proven

C.uptime == P.uptime
→ frozen / interval rejected

C.uptime < P.uptime
→ connection reset / interval rejected

P.uptime missing
OR
C.uptime missing
→ continuity unproven / interval rejected
```

Only:

```text
continuity proven
```

can authorize numeric Traffic.

Reason codes:

```text
continuity_frozen
connection_reset
continuity_unproven
```

Counters-only continuity is forbidden.

---

# 19. AP roaming

AP equality is explicitly NOT required.

```text
P.ap_mac != C.ap_mac
```

alone does not reject an interval.

AP roam does not split a Visit.

---

# 20. Authorization boundary

Repeated authorization does not create a new Visit.

However an interval must not cross a later authorization event.

Reject when:

```text
P.observed_at < authorized_at <= C.observed_at
```

for an authorization occurring after Visit establishment.

Reason:

```text
authorization_boundary
```

Later valid intervals may resume.

---

# 21. SSID continuity

Accepted only when both endpoint SSIDs are present and equal.

```text
P.ssid == C.ssid
→ pass
```

If both present but different:

```text
reject
reason=ssid_transition
```

If either missing:

```text
reject
reason=ssid_unproven
```

SSID transition does not create a synthetic new Visit.

---

# 22. Directional counter gate

Download and Upload are evaluated independently.

For one direction:

```text
previous counter present
current counter present
current >= previous
```

Then:

```text
delta = current - previous
```

A delta of:

```text
0
```

is a valid accepted observed interval.

Missing counter:

```text
counter_missing
```

Counter regression:

```text
counter_reset
```

No:

```text
negative delta
wrap inference
clamp-to-zero repair
```

Later valid intervals may resume.

---

# 23. Exact interval acceptance formula

A directional interval is accepted only if:

```text
same Site
AND same Visit client MAC
AND inside Visit window
AND source row/cycle eligible
AND 0 < elapsed <=180s
AND uptime continuity proven
AND no later authorization boundary crossed
AND SSID present/equal
AND directional counters present
AND current counter >= previous counter
```

AP equality is not part of the formula.

---

# 24. Observed Download / Upload

Canonical:

```text
observed_download_bytes =
SUM(accepted Download deltas)

observed_upload_bytes =
SUM(accepted Upload deltas)
```

For one direction:

```text
accepted_interval_count >=1
AND sum >0
→ numeric positive integer

accepted_interval_count >=1
AND sum =0
→ numeric integer 0

accepted_interval_count =0
→ null
```

Unknown never becomes zero.

---

# 25. Meaning of numeric zero

Numeric zero means exactly:

```text
zero bytes observed across accepted intervals
```

It does NOT automatically mean:

```text
the whole Visit consumed zero bytes
```

Evidence quality communicates coverage.

Permanent invariant:

```text
0 bytes is evidence
null is not zero
```

---

# 26. Observed Total

Canonical:

```text
observed_total_bytes =
observed_download_bytes + observed_upload_bytes
```

only when BOTH directions are numeric.

Otherwise:

```text
observed_total_bytes = null
```

Browser MUST NOT recompute semantic Total.

---

# 27. Controller-reported offline Total

Visit Lifecycle may contain:

```text
reported_traffic_total_bytes
```

It remains:

```text
auxiliary controller-connection evidence
```

It is NOT:

```text
canonical session Download
canonical session Upload
canonical session Total
```

It cannot fill a missing direction.

It is not visible in the primary v1 API item/table.

---

# 28. Sampled edge coverage

Start edge:

```text
first_eligible_observed_at - visit.started_at
```

End edge:

```text
visit.closed_at - last_eligible_observed_at
```

Frozen edge threshold:

```text
180 seconds
```

No sample outside the Visit window may fill an edge.

Uncovered edges affect quality only.

They do not alter already accepted numeric deltas.

Reasons:

```text
start_edge_uncovered
end_edge_uncovered
```

---

# 29. Direction evidence vocabulary

Exact:

```text
complete
partial
insufficient_data
unavailable
```

Public wording:

```text
complete → Complete sampled evidence
partial → Partial evidence
insufficient_data → Insufficient data
unavailable → Unavailable
```

Never use:

```text
exact
billing complete
packet complete
```

---

# 30. Direction evidence = complete

Direction is `complete` only when ALL apply:

```text
Observation source available
Visit inside supported attribution bound
>=1 accepted interval for direction
start edge <=180s
end edge <=180s
no rejected shared interval
no rejected interval for that direction
```

Numeric value may be:

```text
0
or
positive
```

---

# 31. Direction evidence = partial

Direction is `partial` when:

```text
>=1 accepted numeric interval exists
```

but complete sampled conditions are not all satisfied.

Numeric value remains the safely observed amount.

---

# 32. Direction evidence = insufficient_data

Direction is `insufficient_data` when:

```text
sources are healthy
Visit is supported
accepted interval count for direction = 0
```

Value:

```text
null
```

---

# 33. Direction evidence = unavailable

Direction is `unavailable` for item-wide unsupported/unavailable conditions:

```text
Observation source unavailable
or
attribution window >86400
```

Value:

```text
null
```

---

# 34. Exact item evidence roll-up

Frozen exact precedence:

## 34.1 Item-wide unavailable condition

If an item-wide unsupported/unavailable condition applies:

```text
Observation source unavailable
OR
attribution window >86400
```

then:

```text
traffic_evidence_status=unavailable
```

This takes precedence over directional roll-up.

## 34.2 Both directions complete

Otherwise:

```text
download_evidence_status=complete
AND
upload_evidence_status=complete
→ traffic_evidence_status=complete
```

This includes accepted numeric zero.

Example:

```text
Download = 0 bytes from accepted intervals
Download evidence = complete
Upload evidence = complete
→ item = complete
```

## 34.3 No accepted interval in either direction

Otherwise, if:

```text
accepted_download_interval_count=0
AND
accepted_upload_interval_count=0
```

then:

```text
traffic_evidence_status=insufficient_data
```

provided no item-wide unavailable condition applies.

## 34.4 All other supported combinations

Otherwise:

```text
traffic_evidence_status=partial
```

Examples:

```text
download complete + upload insufficient_data
→ partial

download partial + upload complete
→ partial

download partial + upload insufficient_data
→ partial

download complete + upload partial
→ partial
```

Permanent:

```text
numeric 0 is usable evidence
null is not zero
```

---

# 35. Evidence reason allowlist

Exact public allowlist:

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

Unknown reason:

```text
serializer fail closed
```

No raw internal/source error text is exposed.

---

# 36. Root source-health vocabulary

Exact:

```text
visit_source_status =
healthy | unavailable

observation_source_status =
healthy | unavailable | not_required
```

---

# 37. Root status vocabulary

Exact:

```text
ok
partial
insufficient_data
unavailable
```

Integrity failure is not a normal semantic status.

It fails closed.

---

# 38. Exact root status matrix

## Visit source unavailable

```text
status=unavailable
items=[]
observations=not_required
```

## Zero completed Visits

```text
visit source=healthy
status=ok
items=[]
observations=not_required
```

No Observation read is required.

## Observation source unavailable with Visit rows

```text
visit source=healthy
observation source=unavailable
status=partial
Visit rows remain visible
D/U/T=null
item evidence=unavailable
```

## Both sources healthy and all items complete

```text
status=ok
```

## Both sources healthy and cohort/page has no usable numeric interval evidence

```text
status=insufficient_data
```

## All other degraded/mixed results

```text
status=partial
```

This includes mixtures of:

```text
complete
partial
insufficient_data
unavailable due per-item >24h work bound
```

when Visit source itself remains healthy.

---

# 39. Integrity fail-closed cases

Examples:

```text
cross-Site Visit
duplicate visit_id in semantic page
closed Visit with missing/impossible close timestamps
closed_at < started_at
malformed persisted counter type
cursor Site/range contradiction
unknown serializer enum/reason
impossible internal DTO combination
```

Required:

```text
typed fail-closed Admin error
no identifying partial item payload
```

---

# 40. Long-Visit work bound

Frozen:

```text
MAX_ATTRIBUTION_WINDOW_SECONDS=86400
```

Exactly:

```text
24 hours
```

This is a v1 supported-work bound.

It is NOT a statement that longer Visits cannot exist.

---

# 41. Long Visit behavior

If:

```text
visit.closed_at - visit.started_at > 86400
```

then:

```text
Visit remains in completion cohort
Observation attribution is NOT queried for that Visit

observed_download_bytes=null
observed_upload_bytes=null
observed_total_bytes=null

download_evidence_status=unavailable
upload_evidence_status=unavailable
traffic_evidence_status=unavailable

reason=
attribution_window_exceeds_supported_max
```

No clipping.

No approximation.

No partial 24h attribution.

---

# 42. Product ranges

Frozen:

```text
24h
7d
```

Default:

```text
24h
```

Range is:

```text
completion cohort by closed_at
```

It does not redefine the per-Visit 24h work bound.

---

# 43. Sorting

Frozen:

```text
closed_at DESC
visit_id DESC
```

Sort identifier:

```text
closed_at_desc_visit_id_desc.v1
```

No Traffic-value sort in v1.

This keeps Traffic calculation page-bounded.

---

# 44. Pagination

Frozen:

```text
default limit=50
max limit=200
```

Keyset only.

No OFFSET.

---

# 45. Cursor semantic model

Official:

```text
range-pinned live keyset pagination
over the current persisted closed-Visit source
```

Cursor is:

```text
opaque
versioned
```

It is NOT:

```text
an immutable source snapshot
```

No client/browser cursor decoding is authoritative.

---

# 46. Exact cursor fields

Decoded server-side cursor state must contain at minimum:

```text
version
site_id
range_id
evaluated_at_utc
absolute_from_utc
absolute_to_utc
sort
last_closed_at
last_visit_id
```

No field may be omitted on a cursor request.

---

# 47. Exact cursor validation

On EVERY cursor request, server MUST validate:

```text
cursor version is supported

cursor site_id == requested authorized Site

cursor range_id == requested range

cursor sort == closed_at_desc_visit_id_desc.v1

evaluated_at_utc is canonical valid UTC

last_closed_at is canonical valid UTC

last_visit_id is canonical valid Visit identity

absolute_from_utc is canonical valid UTC

absolute_to_utc is canonical valid UTC
```

Then the server MUST independently derive the expected absolute range from:

```text
range_id
+
pinned evaluated_at_utc
```

Exact expected range:

```text
24h:
expected_to   = evaluated_at_utc
expected_from = evaluated_at_utc - 24h

7d:
expected_to   = evaluated_at_utc
expected_from = evaluated_at_utc - 7d
```

Server MUST verify:

```text
absolute_from_utc == expected_from
AND
absolute_to_utc == expected_to
```

The decoded absolute timestamps MUST NOT be blindly trusted.

Any mismatch:

```text
400 invalid_request
```

No silent repair.

No silent re-pin.

---

# 48. Cursor next-page ordering

For descending order, next page is after the cursor key:

```text
closed_at < last_closed_at
OR
(
  closed_at = last_closed_at
  AND visit_id < last_visit_id
)
```

Exact SQL may vary but semantic ordering must not.

---

# 49. Live-source mutation behavior

Cursor does not freeze source rows.

A late/recovered Visit close may appear on a later cursor page if its stable sort
position lies after the consumed cursor key.

A row inserted before the consumed key is not guaranteed to appear in the old
chain.

Global Refresh creates a new chain.

---

# 50. No total-population contract

Frozen:

```text
completed_session_count
NOT REQUIRED in v1 root
```

Reason:

```text
live range-pinned keyset source
```

Required page count only:

```text
returned_count
```

---

# 51. API endpoint

Frozen:

```text
GET /admin/api/v1/sites/<site_id>/traffic/completed-sessions
```

Separate endpoint.

Not inserted into the AP/network historical product query endpoint.

---

# 52. API query grammar

Allowed exactly:

```text
range=24h|7d
limit
cursor
```

Rules:

```text
range required
limit optional, default 50, max 200
cursor optional
```

Unknown parameter:

```text
400 invalid_request
```

Duplicate parameter:

```text
400 invalid_request
```

Malformed/context-changed cursor:

```text
400 invalid_request
```

---

# 53. Root DTO

Exact root fields:

```text
metric_version
session_method
attribution_method
continuity_method
unit
site_id
range
status
source_health
page
items
```

No required full-population quality counts.

---

# 54. Range DTO

Exact:

```text
range: {
  id,
  from_utc,
  to_utc,
  evaluated_at_utc
}
```

`id`:

```text
24h | 7d
```

---

# 55. Source-health DTO

Exact:

```text
source_health: {
  visits,
  observations
}
```

---

# 56. Page DTO

Exact:

```text
page: {
  limit,
  returned_count,
  next_cursor,
  sort
}
```

`next_cursor`:

```text
opaque string | null
```

---

# 57. Item DTO

Exact item fields:

```text
visit_id
client_mac
started_at
closed_at
duration_seconds
start_ssid
final_ssid
start_ap_mac
final_ap_mac
observed_download_bytes
observed_upload_bytes
observed_total_bytes
download_evidence_status
upload_evidence_status
traffic_evidence_status
evidence_reason_codes
sample_count
accepted_download_interval_count
accepted_upload_interval_count
first_observed_at
last_observed_at
```

---

# 58. Item privacy boundary

Do NOT expose:

```text
client IP
AuthSession ID
raw cumulative counters
raw Observation row
raw controller payload
controller-reported offline Total
SQL
DB path
decoded cursor
```

MAC is allowed under existing Admin device-read capability.

---

# 59. Feature flag

Frozen candidate:

```text
WEB_ADMIN_TRAFFIC_COMPLETED_SESSIONS_ENABLED=false
```

Default:

```text
false
```

Required dependencies:

```text
WEB_ADMIN_ENABLED=true
WEB_ADMIN_TRAFFIC_ENABLED=true
```

Not dependent on individual History/Statistics/Peak/AP/Share feature flags.

---

# 60. Capability / authorization

Frozen:

```text
admin.read.devices
```

Every API request must independently repeat:

```text
authentication
canonical Site authorization
capability enforcement
```

Panel visibility is not authorization.

---

# 61. Runtime composition

Feature OFF:

```text
panel absent
route disabled / 404
no CompletedGuestSessionTrafficReadService invocation
no new workload
```

Feature ON:

```text
Visit read dependency
Observation read dependency
exactly one CompletedGuestSessionTrafficReadService composition
```

Optional product composition failure must not take down the whole Admin runtime.

---

# 62. Current State boundary

Frozen:

```text
Current State = OUT
```

No:

```text
CurrentGuestTrafficReadService reuse
TRAFFIC-07 semantic change
Current State fallback
```

---

# 63. Public Traffic boundary

Frozen:

```text
Public Traffic = OUT
```

No use of:

```text
public_traffic.sqlite3
SSID/day aggregates
processed Public Traffic events
```

---

# 64. Registry boundary

Frozen:

```text
Visitor Registry enrichment = OUT v1
```

Guest display:

```text
MAC
```

No cross-MAC device identity merge.

---

# 65. AuthSession boundary

Frozen:

```text
AuthSession != session identity
```

Persisted Visit authorization events may define interval boundaries.

Process-local AuthSession is not required.

---

# 66. Existing indexes

Accepted first implementation path:

Visit completion cohort:

```text
idx_visits_site_closed
```

Authorization boundaries:

```text
idx_visit_auth_visit_time
```

Client Observation:

```text
idx_client_site_mac_time
```

No new source index is authorized by architecture.

---

# 67. Query-plan STOP rule

If the exact candidate cannot meet accepted PERF with existing indexes:

```text
STOP
→ provide EXPLAIN QUERY PLAN / profile evidence
→ architecture review
```

Do NOT silently:

```text
add index
change source schema
raise timeout
extend AP/network Projection
```

---

# 68. Expected bounded read work

Per page:

```text
1. read closed Visit keyset page
2. classify <=24h supported vs >24h unsupported Visits
3. batch authorization boundaries
4. build supported Visit windows
5. batch client Observation rows
6. classify intervals
7. aggregate directional observed bytes/evidence
8. serialize
```

No query-time Omada.

No N+1 connection-per-Visit architecture.

---

# 69. Batch shape

Public page:

```text
50 default
200 max
```

Recommended internal Visit-window batch:

```text
<=100
```

unless equivalent/better bounded implementation is proven.

---

# 70. Admin outer execution controls

Current production baseline:

```text
WEB_ADMIN_MAX_CONCURRENT_QUERIES=4

WEB_ADMIN_MAX_QUERY_DURATION_SECONDS=25
```

Required shape:

```text
Admin execution controls
→ deadline precheck
→ exactly one CompletedGuestSessionTrafficReadService call
→ deadline postcheck
```

The service may use a stricter internal Analytics deadline.

No new public deadline parameter.

---

# 71. Browser timeout

Current:

```text
WEB_ADMIN_TRAFFIC_REQUEST_TIMEOUT_SECONDS=30
```

No TRAFFIC-08-specific larger timeout.

25s/30s are operational headroom, not product PERF targets.

---

# 72. Historical scheduling lane

Frozen:

```text
same Traffic historical scheduling lane
same CaptivPortalTrafficCoordinator
same TrafficHistoricalRequestBroker
```

Current production guard:

```text
3 seconds
```

Historical HTTP in-flight per page:

```text
max=1
```

---

# 73. Non-coalescible job

Completed Sessions is a:

```text
separate non-coalescible endpoint job
```

It MUST NOT be inserted into the existing AP/network coalescing product semantics:

```text
history
statistics
peak
aps
apshare
```

But it MUST share the same lane/in-flight ownership.

No second scheduler.

No private timer owner.

No competing AbortController lifecycle.

---

# 74. Independent range state

TRAFFIC-08 owns its own:

```text
selected_range
applied_range
phase
last_successful_payload
last_error
intent_generation
```

Changing Completed Sessions range must not mutate:

```text
History
Statistics
Peak
Traffic by AP
AP Share
```

---

# 75. Refresh / Load more

Initial/range/Global Refresh:

```text
new root request
new evaluated_at
old cursor chain invalidated
```

Load more:

```text
current opaque cursor chain
```

Late append result from an older generation must not overwrite a newer root.

Reuse existing coordinator generation/AbortController lifecycle.

---

# 76. UI placement

Frozen order:

```text
Current Network Throughput
Online Guests Traffic
Completed Guest Session Traffic
Network Traffic History
Period Statistics
Peak Load
Traffic by AP
AP Traffic Share
```

---

# 77. UI columns

Frozen:

```text
Guest
Session Start
Session End
Duration
SSID
Download
Upload
Total
Evidence
```

No chart in v1.

---

# 78. Guest / SSID UI

Guest:

```text
client MAC
```

If SSID unchanged:

```text
SSID
```

If transitioned:

```text
start → final
```

Do not hide a transition that affected evidence.

---

# 79. Byte formatting

API:

```text
integer bytes
```

UI may format:

```text
B
KiB
MiB
GiB
```

Exact semantic display:

```text
numeric 0 → 0 B
null → —
```

Never:

```text
null → 0 B
```

---

# 80. Evidence UI

Exact labels:

```text
complete → Complete sampled evidence
partial → Partial evidence
insufficient_data → Insufficient data
unavailable → Unavailable
```

---

# 81. Observation unavailable UI

If Visit rows are available but Observation source is unavailable:

```text
Visit rows remain
D/U/T=—
Evidence=Unavailable
```

Root warning:

```text
Traffic evidence unavailable.
Completed session history is still available.
```

---

# 82. Visit source unavailable UI

If Visit source is unavailable:

```text
clear current rows
clear cursor state
show Completed session history unavailable
```

Do not assert old identifying rows as current.

---

# 83. Healthy empty cohort

```text
status=ok
items=[]
observations=not_required
```

UI:

```text
No completed guest sessions
```

Not an error.

---

# 84. Security failure UI

401/403 must clear:

```text
identifiable rows
next cursor
pending cursor
root/chain identity
```

No identifiable stale data remains after authorization loss.

---

# 85. REUSE — Visit Lifecycle

Reuse:

```text
visit_id
site_id
client_mac
started_at
closed_at
duration_seconds
status
start_ssid
final_ssid
start_ap_mac
final_ap_mac
visit_authorizations
idx_visits_site_closed
idx_visit_auth_visit_time
```

No writer/schema/migration change.

---

# 86. REUSE — Observation

Reuse:

```text
client_observations
observation_cycles
uptime
traffic_down
traffic_up
ssid
ap_mac
source_inventory_complete
idx_client_site_mac_time
```

No collector/schema/cadence change.

---

# 87. REUSE — Analytics infrastructure

Reuse:

```text
AnalyticsSourceGateway conventions
bounded batching conventions
QueryDeadline
read-only SQLite conventions
validation helpers
telemetry helpers
```

Do NOT reuse the weaker existing Visit Traffic interval semantic unchanged.

---

# 88. REUSE — Admin / Traffic frontend

Reuse:

```text
AdminQueryExecutionControls
authentication/Site/capability
safe serialization
CaptivPortalTrafficCoordinator
TrafficHistoricalRequestBroker
current 3s historical guard
max historical in-flight=1
independent historical panel state
```

---

# 89. CHANGE REQUIRED

Expected architecture changes only:

```text
closed Visit completion-cohort keyset read
authorization-boundary batch
strict client Traffic evidence batch
CompletedGuestSessionTrafficReadService
feature/config/runtime composition
AdminQueryService method
strict serializer
Admin route
Traffic panel
broker job integration
focused tests/PERF
```

---

# 90. Explicit NO-TOUCH

No change without STOP/review to:

```text
historical_traffic_projection.v1
traffic_projection.sqlite3 schema
TrafficProjectionService
TrafficProjectionReadService
Projection worker/read cutover

Current State
TRAFFIC-07
CurrentGuestTrafficReadService

Visit writer/schema/matching
Observation collector/schema/retention/cadence

Public Traffic
Visitor Registry identity
existing visit.traffic.v1 semantics

HistoricalTrafficReadService AP/network formulas
query-time Omada
```

---

# 91. PERF gates

Full authenticated endpoint.

API50:

```text
>=10 measured runs
p95 <=2.0s
max <=3.0s
```

API200:

```text
>=10 measured runs
p95 <=4.0s
max <=6.0s
```

Mandatory:

```text
query deadline failures=0
unexpected 5xx=0
source writes=0
```

No outer deadline increase.

---

# 92. Payload budget

API200 serialized success:

```text
<=256 KiB
```

This is:

```text
acceptance/optimization budget
```

not a new hard runtime limit.

---

# 93. PERF fixture

Must include at least:

```text
50 Visits
200 Visits
24h supported windows
60s client cadence
substantial unrelated Observation rows

uptime progression
uptime frozen
uptime reset
uptime missing

positive counter delta
zero counter delta
counter reset
counter missing

AP roam
authorization boundary
SSID transition
SSID missing

gap >180s
start edge uncovered
end edge uncovered
no samples
>24h Visit
```

---

# 94. Query-plan gates

Mandatory evidence:

```text
Visit cohort uses idx_visits_site_closed
authorization lookup uses idx_visit_auth_visit_time
client Observation uses idx_client_site_mac_time
```

No full source scans for a supported page request.

---

# 95. Read-only immutability

Mandatory proof:

```text
Visits DB unchanged
Observation DB unchanged
Projection DB unchanged
Current State DB unchanged
Public Traffic DB unchanged
```

TRAFFIC-08 is read-only.

---

# 96. Regression scope

At minimum:

```text
Visit Lifecycle reads
existing Visit Analytics visit.traffic.v1
Observation gateway
Traffic broker/coordinator
Projection-backed History
Projection-backed Statistics
Projection-backed Peak
Projection-backed Traffic by AP
Projection-backed AP Share
Online Guests Traffic
Admin auth/Site isolation
```

Candidate regressions:

```text
0
```

---

# 97. Test routing

Follow current canonical three-contour governance:

```text
Windows Central Lab
Owner WSL/Linux Lab
production acceptance
```

Production is not a synthetic test host.

Unsafe/artificial evidence cases belong to Lab.

---

# 98. Feature deployment

Initial production deploy:

```text
FROM GIT
```

with:

```text
WEB_ADMIN_TRAFFIC_COMPLETED_SESSIONS_ENABLED=false
```

No new worker.

No new DB.

No source migration.

---

# 99. Dormant production acceptance

Required before activation:

```text
captive-portal.service healthy
traffic-projection.service healthy
existing Projection health healthy
existing Traffic products healthy

Completed Sessions panel absent
Completed Sessions route disabled/404
no Completed Sessions browser request
no source writes
no scheduler change
```

---

# 100. Activation

Only after:

```text
implementation accepted
mandatory tests PASS
PERF PASS
publication/merge/deploy authorized
dormant production acceptance PASS
separate Owner activation authorization
```

Then:

```text
WEB_ADMIN_TRAFFIC_COMPLETED_SESSIONS_ENABLED=true
```

Deploy and activation remain separate.

---

# 101. Production browser acceptance

Manual acceptance includes:

```text
panel visible in frozen order
default 24h
24h → 7d → 24h
other historical panel ranges unchanged

newest completed Visits first
Load more
Global Refresh

zero displays 0 B
null displays —
evidence labels correct

>24h Visit shows unavailable if production case exists

History healthy
Statistics healthy
Peak healthy
Traffic by AP healthy
AP Share healthy
Online Guests Traffic healthy
```

---

# 102. Rollback

Primary product rollback:

```text
WEB_ADMIN_TRAFFIC_COMPLETED_SESSIONS_ENABLED=false
```

No:

```text
DB rollback
Projection rollback
source cleanup
worker cleanup
```

---

# 103. Future capacity path

If official candidate cannot satisfy accepted PERF with:

```text
existing indexes
page bounds
24h attribution cap
set-based batching
```

then:

```text
STOP
```

Do NOT:

```text
raise timeout
add speculative source index
change source schema
extend AP/network Projection ad hoc
```

Open a separate architecture for:

```text
Completed Guest Session Traffic materialized projection
```

---

# 104. Recommended implementation decomposition after authorization

This FINAL does NOT authorize implementation.

After separate Owner authorization, Tech Lead may decompose:

```text
Phase A
closed Visit cohort / cursor / DTO

Phase B
strict authorization + client Observation evidence primitive

Phase C
CompletedGuestSessionTrafficReadService

Phase D
Admin feature/runtime/query/serializer/route

Phase E
Traffic panel + historical broker integration

Phase F
focused regression + Central Lab + Linux PERF

Phase G
dormant production deploy

Phase H
separate activation + browser acceptance
```

---

# 105. Final frozen decision register

1. Product is Completed Guest Session Traffic.
2. Session identity is `visit_id`.
3. Only closed Visits are included.
4. Completion cohort uses `closed_at`.
5. Full Visit window is used for attribution.
6. Selected 24h/7d range does not clip attribution.
7. Native sources are Visit Lifecycle + persisted client Observation.
8. Existing AP/network Projection is NO-TOUCH and not a TRAFFIC-08 source.
9. No AP Traffic allocation to Visits.
10. No global Projection rebuild for TRAFFIC-08.
11. Semantic owner is `CompletedGuestSessionTrafficReadService`.
12. Existing `visit.traffic.v1` semantics remain unchanged.
13. A new strict evidence primitive is required.
14. Client source cycle must be completed/complete/success.
15. `source_inventory_complete=1` is required.
16. Candidate intervals are consecutive by `(observed_at,row_id)`.
17. Max interval gap is 180s.
18. Uptime progression is mandatory continuity proof.
19. Equal uptime rejects interval as frozen.
20. Regressed uptime rejects interval as reset.
21. Missing uptime rejects interval as unproven.
22. AP equality is not required.
23. AP roam does not split Visit.
24. Repeated authorization does not split Visit.
25. Authorization boundary cannot be crossed.
26. SSID boundary cannot be crossed.
27. Directional counters are independent.
28. Counter reset affects that direction only.
29. Accepted zero delta is numeric zero evidence.
30. No accepted interval means null.
31. Total is backend D+U only when both directions numeric.
32. Controller offline Total is auxiliary only and hidden in primary v1.
33. Evidence vocabulary is complete/partial/insufficient_data/unavailable.
34. Complete wording is "Complete sampled evidence".
35. Item-wide unavailable has precedence.
36. Both directions complete → item complete.
37. No accepted interval in either direction → item insufficient_data.
38. All other supported combinations → item partial.
39. Numeric zero remains usable evidence.
40. Visit source unavailable → root unavailable/items empty/Observation not required.
41. Zero completed Visits → root ok/items empty/Observation not required.
42. Observation unavailable with Visits → root partial/rows retained/Traffic null.
43. Both sources healthy + all complete → root ok.
44. Both sources healthy + no usable numeric evidence → root insufficient_data.
45. Other degraded/mixed result → root partial.
46. Max supported Visit attribution window is 86400 seconds.
47. >24h Visit remains visible but Traffic is unavailable.
48. >24h Visit is never clipped.
49. Range is independent 24h|7d; default 24h.
50. Page default 50/max 200.
51. Sort is `closed_at DESC, visit_id DESC`.
52. Cursor is opaque + versioned.
53. Cursor pins Site/range/evaluation/absolute range/sort/last key.
54. Server recomputes expected absolute range from range_id + evaluated_at.
55. Decoded absolute cursor timestamps are never blindly trusted.
56. Cursor mismatch/malformed state → 400 invalid_request.
57. No silent repin.
58. Cursor is live keyset, not immutable snapshot.
59. No required completed-session population count.
60. API endpoint is separate `/traffic/completed-sessions`.
61. Endpoint uses same Traffic historical scheduling lane.
62. Current historical admission guard is 3s.
63. Historical HTTP in-flight per page remains 1.
64. Completed Sessions is non-coalescible with history/statistics/peak/aps/apshare.
65. No second scheduler/timer/AbortController owner.
66. Capability is `admin.read.devices`.
67. Current State is OUT.
68. Public Traffic is OUT.
69. Registry enrichment is OUT v1.
70. AuthSession is not session identity.
71. Query-time Omada is forbidden.
72. No new collector.
73. No new DB.
74. No source schema change.
75. No source index by default.
76. Existing Visit/authorization/client indexes are the first implementation path.
77. Failed query-plan/PERF with those indexes triggers STOP/review.
78. Admin outer deadline remains 25s.
79. Browser Traffic timeout remains 30s.
80. Product PERF gates remain much stricter than outer timeouts.
81. API50 p95<=2s/max<=3s.
82. API200 p95<=4s/max<=6s.
83. API200 payload acceptance budget <=256 KiB.
84. Feature defaults false.
85. Dormant deploy precedes activation.
86. Primary rollback is feature OFF.
87. This FINAL does not authorize implementation.

---

# 106. Final state

```text
TASK:
TASK-TRAFFIC-08 — Completed Guest Session Traffic

DOCUMENT:
FINAL ARCHITECTURE

REPOSITORY:
main@3761981f4b1ec30b330abe1eec1713f15191c711

TREE:
2e6ac33f1033c1f0587407a2476ca852373a04e6

DRIFT:
NONE

PREREQUISITES:
Projection COMPLETE / ACTIVE
DB baseline PASS

ARCHITECTURE BLOCKERS:
NONE

SESSION IDENTITY:
closed Visit / visit_id

COHORT:
closed_at

ATTRIBUTION:
full Visit window

MAX ATTRIBUTION:
86400 seconds

PRIMARY SESSION SOURCE:
Visit Lifecycle

PRIMARY TRAFFIC SOURCE:
persisted client Observation

UPTIME CONTINUITY:
mandatory

AP ROAM:
allowed

AUTHORIZATION BOUNDARY:
must not cross

SSID BOUNDARY:
must not cross

OBSERVED ZERO:
numeric 0 only after accepted interval

UNKNOWN:
null

ITEM EVIDENCE:
complete | partial | insufficient_data | unavailable

ROOT STATUS:
ok | partial | insufficient_data | unavailable

AP/NETWORK PROJECTION:
NO-TOUCH
NOT TRAFFIC-08 SOURCE

NEW COLLECTOR:
NO

NEW DB:
NO

SOURCE SCHEMA CHANGE:
NO

NEW INDEX:
NO by default

QUERY-TIME OMADA:
NO

RANGE:
24h | 7d

PAGE:
50 default / 200 max

SORT:
closed_at DESC, visit_id DESC

CURSOR:
opaque
versioned
range-pinned live keyset
server-validated absolute range
no silent repin

API:
GET /admin/api/v1/sites/<site_id>/traffic/completed-sessions

BROKER:
existing historical lane

ADMISSION GUARD:
3s

HISTORICAL IN-FLIGHT:
1

COALESCING:
NO with history/statistics/peak/aps/apshare

ADMIN OUTER DEADLINE:
25s

BROWSER TIMEOUT:
30s

API50 PERF:
p95 <=2.0s
max <=3.0s

API200 PERF:
p95 <=4.0s
max <=6.0s

PAYLOAD BUDGET:
API200 <=256 KiB

CAPABILITY:
admin.read.devices

FEATURE:
WEB_ADMIN_TRAFFIC_COMPLETED_SESSIONS_ENABLED=false

IMPLEMENTATION:
NOT AUTHORIZED

CODER:
NOT AUTHORIZED

PUBLICATION:
NOT AUTHORIZED

MERGE:
NOT AUTHORIZED

PRODUCTION DEPLOY:
NOT AUTHORIZED

ACTIVATION:
NOT AUTHORIZED
```

---

# 107. Next allowed step

Owner + Tech Lead perform FINAL acceptance.

If accepted:

```text
FINAL:
OWNER + TECH LEAD ACCEPTED

ARCHITECTURE:
CLOSED

IMPLEMENTATION:
READY FOR SEPARATE OWNER AUTHORIZATION
```

Only after separate explicit Owner implementation authorization:

```text
re-fetch / re-pin origin/main
impact-review drift
Tech Lead implementation decomposition
Coder TASK
```

No implementation may begin from this FINAL alone.
