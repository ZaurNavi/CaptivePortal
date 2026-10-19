# TASK-TRAFFIC-08 — Completed Guest Session Traffic — ARCHITECTURAL DRAFT v2

**Project:** CaptivPortal  
**Area:** Admin Console → Traffic  
**TASK:** `TASK-TRAFFIC-08 — Completed Guest Session Traffic`  
**State:** `ARCHITECTURAL DRAFT v2 — POST-PROJECTION REOPEN — FOR OWNER + TECH LEAD REVIEW`  
**Prepared:** 2026-09-06  
**Implementation authorization:** `NOT GRANTED`  
**Coder authorization:** `NOT GRANTED`  
**Publication / merge / deploy / activation:** `NOT AUTHORIZED`

## 1. Reopen decision

The previous TRAFFIC-08 architecture was intentionally frozen while:

```text
TASK-TRAFFIC-PROJECTION-01
TASK-DB-BASELINE-SYNC-01
```

were completed.

Current prerequisite state supplied by Tech Lead:

```text
TASK-TRAFFIC-PROJECTION-01 = COMPLETE / PRODUCTION ACTIVE
TASK-DB-BASELINE-SYNC-01 = CLOSED / PASS
FINAL_DB_BASELINE = PASS
BLOCKERS_FOR_TRAFFIC_08 = NONE
TRAFFIC-08 = UNFROZEN / READY FOR ARCHITECTURE
```

This DRAFT performs the required post-Projection impact review.

## 2. Repository rebind

Canonical repository review point:

```text
main = 3761981f4b1ec30b330abe1eec1713f15191c711
tree = 2e6ac33f1033c1f0587407a2476ca852373a04e6
```

Current `main` is docs-only PR #103. Its application-code parent is:

```text
6fbc3736085be9d0538d893b6e9569ff490ef7f4
```

with application tree:

```text
fc3c1ed53df32d0074036a749ee028781ec1f1b5
```

Before FINAL and again before implementation authorization:

```text
re-fetch origin/main
re-pin exact SHA/tree
impact-review drift
```

## 3. Current production infrastructure

Accepted current Admin baseline:

```text
WEB_ADMIN_MAX_CONCURRENT_QUERIES=4
WEB_ADMIN_MAX_QUERY_DURATION_SECONDS=25
WEB_ADMIN_TRAFFIC_REQUEST_TIMEOUT_SECONDS=30
Historical Traffic admission guard=3s
```

Projection:

```text
TRAFFIC_PROJECTION_ENABLED=true
WEB_ADMIN_TRAFFIC_PROJECTION_READ_ENABLED=true
projection_version=historical_traffic_projection.v1
projection health=healthy
projection backlog=0
```

These are infrastructure facts, not TRAFFIC-08 metric semantics.


## 4. Post-Projection impact review

Pre-Projection TRAFFIC-08 decisions preserved:

```text
session identity = closed Visit / visit_id
completion cohort = closed_at
full Visit window for attribution
primary Traffic source = persisted client Observation counters
controller offline Total = auxiliary only
Current State = OUT
Public Traffic = OUT
Registry enrichment = OUT v1
AuthSession != session identity
semantic owner = CompletedGuestSessionTrafficReadService
no query-time Omada
no new collector
no new source DB/schema/index by default
24h | 7d independent range
default 24h
page 50 / max 200
sort = closed_at DESC, visit_id DESC
existing Traffic historical broker/coordinator
admin.read.devices
feature default false
dormant deploy and activation separate
```

New post-Projection decision proposed:

```text
TRAFFIC-08 v1 DOES NOT consume or extend historical_traffic_projection.v1.
```

## 5. Projection boundary

Current production projection materializes AP/network Historical Traffic:

```text
source-neutral ap_dynamic cycle facts
+
per-AP cycle facts
```

It does not materialize:

```text
client_observations
Visit identity/windows
Visit authorization boundaries
client uptime continuity
per-session Traffic attribution
```

Therefore `traffic_projection.sqlite3` is not a canonical TRAFFIC-08 source.

TRAFFIC-08 v1 MUST NOT:

```text
allocate AP Traffic to Visits
use AP Share to estimate guest Traffic
extend historical_traffic_projection.v1 ad hoc
change projection semantic_contract
trigger a global projection-version rebuild merely to add TRAFFIC-08
```

This is not automatic raw fallback: Visits + persisted client Observation are the native authoritative sources of this new product.

If future capacity proves this bounded path insufficient, open a separate session/client projection architecture rather than opportunistically mutating the AP projection.


## 6. Product semantics

Product name:

```text
Completed Guest Session Traffic
```

Metric candidates:

```text
metric_version = network_traffic_completed_guest_session_observed_bytes.v1
session_method = closed_visit_completion_cohort.v1
attribution_method = visit_window_observation_counter_interval_sum.v1
continuity_method = observation_uptime_progress.v1
unit = bytes
```

Semantic owner:

```text
CompletedGuestSessionTrafficReadService
```

Recommended domain:

```text
app/analytics
```

Completed Guest Session:

```text
one persisted VisitRecord
where status='closed'
for the authorized canonical Site
```

Identity:

```text
session_id = visit_id
```

Start:

```text
visit.started_at
```

End:

```text
visit.closed_at
```

Duration:

```text
visit.duration_seconds
```

Open Visits are excluded.

Completion cohort:

```text
closed_at >= from_utc
AND
closed_at < to_utc
```

Full Traffic attribution window:

```text
[visit.started_at, visit.closed_at)
```

The selected 24h/7d completion range never clips the Visit window.


## 7. Authoritative sources and correlation

Session authority:

```text
Visit Lifecycle
```

Directional Traffic authority:

```text
persisted client Observation counters
```

Required persisted client facts already exist:

```text
site_id
client_mac
observed_at
ssid
ap_mac
uptime
traffic_down
traffic_up
source_inventory_complete
```

Observation row participates only when:

```text
same canonical Site
same Visit client MAC
observed_at inside Visit window
cycle kind='client'
cycle state='completed'
cycle complete=1
cycle result='success'
source_inventory_complete=1
```

Correlation context:

```text
Site + visit_id + client MAC + Visit time window
```

MAC is correlation identity, not session identity.

Randomized MAC Visits are not merged.

Sequential Visits for one MAC remain separate.

AP roam does not split the Visit.

Repeated authorization does not split the Visit, but it creates an interval boundary.


## 8. Existing Visit Analytics compatibility

Current:

```text
AnalyticsSourceGateway.visit_observed_traffic_batch()
```

is useful as a set-based batching pattern, but it currently accepts deltas using counter monotonicity + elapsed/gap only.

It does not provide the required TRAFFIC-08 continuity/segmentation contract:

```text
uptime continuity
authorization-boundary rejection
SSID-boundary rejection
per-direction evidence reasons
```

Therefore it MUST NOT be reused unchanged as TRAFFIC-08 semantic truth.

Existing:

```text
VisitAnalyticsService.get_visit_traffic_summary()
metric=visit.traffic.v1
```

also remains unchanged. TRAFFIC-08 does not relabel that aggregate metric as a per-session product.

Required new internal concept:

```text
completed_visit_traffic_evidence_batch(...)
```

or semantically equivalent bounded primitive.


## 9. Exact interval acceptance

For each Visit, eligible samples are ordered:

```text
observed_at ASC, row_id ASC
```

Candidate pair:

```text
P → C
```

Elapsed:

```text
0 < C.observed_at - P.observed_at <= 180 seconds
```

Mandatory uptime continuity:

```text
P.uptime present
C.uptime present
C.uptime > P.uptime
→ proven

C.uptime == P.uptime
→ continuity_frozen / reject

C.uptime < P.uptime
→ connection_reset / reject

either uptime missing
→ continuity_unproven / reject
```

Counters alone cannot prove continuity.

AP equality is NOT required.

Authorization boundary:

```text
P.observed_at < authorized_at <= C.observed_at
→ reject / authorization_boundary
```

SSID:

```text
both present and equal
→ pass

different
→ reject / ssid_transition

either missing
→ reject / ssid_unproven
```

Direction counter:

```text
both counters present
current >= previous
→ delta accepted, including delta=0

missing
→ counter_missing

regression
→ counter_reset
```

Later valid intervals may resume after reset/boundary.


## 10. Observed-byte semantics

Download:

```text
observed_download_bytes =
SUM(accepted traffic_down deltas)
```

Upload:

```text
observed_upload_bytes =
SUM(accepted traffic_up deltas)
```

If a direction has at least one accepted interval:

```text
sum >0 → positive integer
sum =0 → integer 0
```

No accepted interval:

```text
null
```

Numeric zero means only:

```text
zero bytes observed across accepted intervals
```

It does not prove the full Visit consumed zero bytes.

Total:

```text
observed_total_bytes =
observed_download_bytes + observed_upload_bytes
```

only when both directions are numeric. Otherwise Total is null.

Controller-reported offline Total remains auxiliary connection evidence only and is not exposed in the primary v1 item.


## 11. Evidence / quality model

Per-direction:

```text
complete
partial
insufficient_data
unavailable
```

Public wording for `complete`:

```text
Complete sampled evidence
```

Complete requires:

```text
source available
Visit supported
>=1 accepted interval
start edge <=180s
end edge <=180s
no rejected shared interval
no rejected interval for that direction
```

Partial:

```text
>=1 accepted numeric interval
but complete sampled coverage is not established
```

Insufficient data:

```text
sources healthy
Visit supported
no accepted numeric interval
```

Unavailable:

```text
Observation source unavailable
or Visit attribution window unsupported
```

Item status uses the same vocabulary.

Exact reason allowlist:

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


## 12. Root source/status matrix

Source axes:

```text
visit_source_status =
healthy | unavailable

observation_source_status =
healthy | unavailable | not_required
```

Root status:

```text
ok
partial
insufficient_data
unavailable
```

Matrix:

```text
Visit unavailable
→ unavailable
→ items=[]

Healthy Visit source + zero completed sessions
→ ok
→ observations=not_required
→ items=[]

Visit healthy + Observation unavailable
→ partial
→ Visit rows remain
→ D/U/T=null
→ item evidence=unavailable

Both healthy + all rows without usable evidence
→ insufficient_data

Mixed usable/partial/unavailable page
→ partial

All complete
→ ok
```

Integrity contradictions fail closed and are not represented as a normal semantic status.


## 13. Long-Visit work bound

Retain the pre-Projection candidate:

```text
MAX_ATTRIBUTION_WINDOW_SECONDS=86400
```

Exactly 24 hours.

If:

```text
closed_at - started_at > 86400
```

the Visit remains in the completion cohort, but:

```text
do not query Observation attribution for that Visit
observed_download_bytes=null
observed_upload_bytes=null
observed_total_bytes=null
evidence=unavailable
reason=attribution_window_exceeds_supported_max
```

No clipping or approximation.

Rationale remains valid post-Projection because AP/network Projection does not materialize client/session Traffic, while current client Observation cadence remains 60s.

FINAL should retain or revise this bound only with new capacity evidence.


## 14. Historical/range/pagination semantics

Independent range:

```text
24h | 7d
default=24h
```

Range selects closed Visits by `closed_at`.

Sort:

```text
closed_at DESC
visit_id DESC
```

No v1 Traffic-value sorting.

Pagination:

```text
default limit=50
max limit=200
keyset only
```

Official cursor semantic:

```text
range-pinned live keyset pagination
over current persisted closed-Visit source
```

Cursor pins:

```text
version
site_id
range_id
absolute_from_utc
absolute_to_utc
evaluated_at_utc
sort
last_closed_at
last_visit_id
```

No immutable source-snapshot claim.

No silent repin.

Global Refresh creates a new root chain.

No required `completed_session_count` root field.


## 15. API proposal

Endpoint:

```text
GET /admin/api/v1/sites/<site_id>/traffic/completed-sessions
```

Allowed query parameters:

```text
range=24h|7d
limit
cursor
```

Unknown/duplicate/malformed/mismatched query state:

```text
400 invalid_request
```

Root DTO:

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

`range`:

```text
{
  id,
  from_utc,
  to_utc,
  evaluated_at_utc
}
```

`source_health`:

```text
{
  visits,
  observations
}
```

`page`:

```text
{
  limit,
  returned_count,
  next_cursor,
  sort
}
```


## 16. Exact item DTO

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

Do not expose:

```text
client IP
raw counters
offline controller Total
AuthSession ID
raw source SQL/DB metadata
```


## 17. Admin / security

Capability:

```text
admin.read.devices
```

Every API request repeats:

```text
authentication
canonical Site
capability
```

Feature flag proposal:

```text
WEB_ADMIN_TRAFFIC_COMPLETED_SESSIONS_ENABLED=false
```

Dependencies:

```text
WEB_ADMIN_ENABLED=true
WEB_ADMIN_TRAFFIC_ENABLED=true
```

It does not depend on individual History/Statistics/Peak/AP/Share flags.

Optional product composition failure must not crash the whole Admin runtime.


## 18. Projection runtime independence

TRAFFIC-08 v1 does not require:

```text
historical_traffic_projection.v1
```

as a semantic source.

It must not alter:

```text
TrafficProjectionService
TrafficProjectionReadService
traffic_projection.sqlite3 schema
Projection worker
Projection health/reconciliation
Projection read cutover
History/Statistics/Peak/AP/Share formulas
```

The existing Projection stays production-active independently.


## 19. Deadline / broker contracts

Current outer Admin baseline:

```text
WEB_ADMIN_MAX_QUERY_DURATION_SECONDS=25
WEB_ADMIN_TRAFFIC_REQUEST_TIMEOUT_SECONDS=30
WEB_ADMIN_MAX_CONCURRENT_QUERIES=4
```

TRAFFIC-08 should still use a stricter bounded internal Analytics query budget and must not raise current timeouts.

Recommended application shape:

```text
Admin execution controls
→ deadline precheck
→ one CompletedGuestSessionTrafficReadService call
→ deadline postcheck
```

Historical lifecycle:

```text
TrafficHistoricalRequestBroker
+
CaptivPortalTrafficCoordinator
```

Current admission guard:

```text
3 seconds
```

Historical in-flight:

```text
max=1 per page
```

TRAFFIC-08 uses a separate endpoint in the same lane.

No cross-endpoint coalescing in v1.

No private scheduler/timer/AbortController owner.


## 20. UI proposal

Panel order:

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

Columns:

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

Guest:

```text
MAC
```

Registry enrichment deferred.

SSID transition shown as:

```text
start → final
```

Byte display:

```text
numeric zero → 0 B
null → —
```

Evidence labels:

```text
Complete sampled evidence
Partial evidence
Insufficient data
Unavailable
```


## 21. REUSE

Visit Lifecycle:

```text
visit_id
Site
client_mac
started_at
closed_at
duration_seconds
status
start/final SSID
start/final AP
visit_authorizations
idx_visits_site_closed
idx_visit_auth_visit_time
```

Observation:

```text
client_observations
uptime
traffic_down/up
SSID/AP
source_inventory_complete
terminal client cycles
idx_client_site_mac_time
```

Analytics:

```text
AnalyticsSourceGateway conventions
batch-window pattern
QueryDeadline
read-only SQLite conventions
validation/telemetry helpers
```

Admin/Traffic:

```text
AdminQueryExecutionControls
Site/capability security
TrafficHistoricalRequestBroker
CaptivPortalTrafficCoordinator
3s guard
max historical in-flight=1
independent range state
```


## 22. CHANGE REQUIRED

1. Dedicated closed-Visit completion cohort/keyset read using `idx_visits_site_closed`.
2. Bounded authorization-boundary batch using `idx_visit_auth_visit_time`.
3. New strict client Traffic evidence batch including uptime/SSID/auth boundaries.
4. `CompletedGuestSessionTrafficReadService`.
5. Feature/runtime composition.
6. Strict serializer.
7. Admin API route.
8. Traffic historical panel/broker job.
9. Focused tests + Central Lab + Linux PERF.


## 23. Explicit NO-TOUCH

```text
Historical Traffic Projection schema/version/worker/read service
Current State / TRAFFIC-07
Visit writer/schema/close matching
Observation collector/schema/retention/cadence
Public Traffic
Visitor Registry identity model
HistoricalTrafficReadService AP/network formulas
query-time Omada
```

No new collector.

No new DB.

No new source schema/index by default.


## 24. Query-plan / PERF gates

Mandatory indexed plans:

```text
Visit cohort → idx_visits_site_closed
Authorization boundaries → idx_visit_auth_visit_time
Client Observation → idx_client_site_mac_time
```

If the accepted candidate cannot pass with these indexes:

```text
STOP
→ provide query-plan/profile evidence
→ architecture review
```

No speculative index.

Full authenticated endpoint gates:

```text
API50:
>=10 runs
p95 <=2.0s
max <=3.0s

API200:
>=10 runs
p95 <=4.0s
max <=6.0s

query deadline failures=0
unexpected 5xx=0
source writes=0
```

Payload budget:

```text
API200 <=256 KiB
```

Current 25s backend / 30s browser limits are headroom, not performance targets.


## 25. Required PERF/correctness fixtures

At minimum:

```text
50 Visits
200 Visits
24h supported windows
60s client cadence
uptime progression
uptime frozen/reset/missing
counter positive/zero/reset/missing
AP roam
SSID transition/missing
authorization boundary
gap >180s
start/end uncovered
no samples
>24h Visit
substantial unrelated Observation rows
```

No N+1 DB connection/query pattern.


## 26. Failure / immutability

Visit source unavailable:

```text
root unavailable
items=[]
```

Observation unavailable:

```text
root partial
Visit rows preserved
Traffic null
item unavailable
```

Security 401/403 clears identifiable rows/cursor state.

Read-only immutability must prove:

```text
Visits DB unchanged
Observation DB unchanged
Projection DB unchanged
Current State DB unchanged
Public Traffic DB unchanged
```


## 27. Test/deploy lifecycle

Regression scope includes:

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

Current three-contour governance:

```text
Windows Central Lab
Owner WSL/Linux Lab
production acceptance
```

Production is not a synthetic test host.

Deploy:

```text
feature false
FROM GIT
dormant acceptance
separate Owner activation
browser acceptance
```

Primary rollback:

```text
WEB_ADMIN_TRAFFIC_COMPLETED_SESSIONS_ENABLED=false
```


## 28. Open architecture review items

### Q1 — Projection boundary

Accept:

```text
TRAFFIC-08 v1 native sources =
Visits + persisted client Observation

historical_traffic_projection.v1 =
NO-TOUCH / not consumed
```

Architect recommendation: `ACCEPT`.

### Q2 — 24h attribution cap

Retain:

```text
MAX_ATTRIBUTION_WINDOW_SECONDS=86400
```

Architect recommendation: `ACCEPT` unless new capacity evidence contradicts it.

### Q3 — Strict new evidence primitive

Accept a new bounded read primitive rather than changing current
`visit_observed_traffic_batch()` semantics.

Architect recommendation: `ACCEPT`.

### Q4 — Separate endpoint on same historical lane

Accept:

```text
separate endpoint
same broker/coordinator
3s guard
max in-flight=1
no cross-endpoint coalescing v1
```

Architect recommendation: `ACCEPT`.


## 29. Recommended implementation decomposition after architecture closure

No implementation is authorized yet.

Future Tech Lead decomposition:

```text
Phase A
closed Visit cohort/cursor/DTO

Phase B
strict authorization + client Observation evidence batch

Phase C
CompletedGuestSessionTrafficReadService

Phase D
Admin feature/runtime/query/serializer/route

Phase E
Traffic panel/broker integration

Phase F
focused regression + Central Lab + Linux PERF

Phase G
dormant deploy

Phase H
separate activation + browser acceptance
```


## 30. Current architecture state

```text
TASK:
TASK-TRAFFIC-08 — Completed Guest Session Traffic

STATUS:
ARCHITECTURAL DRAFT v2
POST-PROJECTION REOPEN

REPOSITORY:
main@3761981f4b1ec30b330abe1eec1713f15191c711

TREE:
2e6ac33f1033c1f0587407a2476ca852373a04e6

PREREQUISITES:
Projection COMPLETE / ACTIVE
DB BASELINE PASS

BLOCKERS:
NONE for architecture review

SESSION IDENTITY:
closed Visit / visit_id

COMPLETION COHORT:
closed_at

ATTRIBUTION:
full Visit window

MAX ATTRIBUTION:
24h proposed retain

PRIMARY SESSION SOURCE:
Visit Lifecycle

PRIMARY TRAFFIC SOURCE:
persisted client Observation counters

UPTIME CONTINUITY:
mandatory

AP ROAM:
allowed

AUTHORIZATION / SSID BOUNDARY:
must not cross

OBSERVED ZERO:
numeric 0 only after accepted interval

UNKNOWN:
null

EXISTING AP/NETWORK PROJECTION:
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
50 / 200

SORT:
closed_at DESC, visit_id DESC

BROKER:
existing historical lane

ADMISSION GUARD:
3s

ADMIN OUTER DEADLINE:
25s

BROWSER TIMEOUT:
30s

PRODUCT PERF:
API50 p95<=2s/max<=3s
API200 p95<=4s/max<=6s

CAPABILITY:
admin.read.devices

FEATURE:
WEB_ADMIN_TRAFFIC_COMPLETED_SESSIONS_ENABLED=false

IMPLEMENTATION:
NOT AUTHORIZED

CODER:
NOT AUTHORIZED

PUBLICATION / MERGE / DEPLOY / ACTIVATION:
NOT AUTHORIZED
```

## 31. Next step

Owner + Tech Lead review this post-Projection DRAFT.

If the four impact decisions are accepted:

```text
re-fetch origin/main
confirm drift
issue TRAFFIC-08 FINAL ARCHITECTURE
```

Only after separate Owner implementation authorization:

```text
Tech Lead decomposition
→ Coder
```

No implementation is authorized by this DRAFT.
