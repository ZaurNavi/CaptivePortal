# TASK-TRAFFIC-08 — Completed Guest Session Traffic — FINAL ARCHITECTURE

**Project:** CaptivPortal  
**Area:** Admin Console → Traffic  
**TASK:** `TASK-TRAFFIC-08 — Completed Guest Session Traffic`  
**State:** `FINAL ARCHITECTURE — FOR OWNER + TECH LEAD FINAL ACCEPTANCE`  
**Prepared:** 2026-09-03  
**Implementation authorization:** `NOT GRANTED`  
**Coder authorization:** `NOT GRANTED`  
**Publication / merge / deploy / activation:** `NOT AUTHORIZED`

---

# 1. Repository binding

Re-fetch immediately before FINAL:

```text
origin/main =
e196b042515498c5cd9143a9962f6aed90f31566

tree =
f88ee1f854135107c647ccd9d346be2b2ba504b9
```

Commit:

```text
Merge pull request #100 from ZaurNavi/docs/traffic07-production-kb-2026-09-03

Docs: reconcile TRAFFIC-07 Online Guests Traffic production state
```

Functional TRAFFIC-07 production parent remains:

```text
6425988b5b4ec5ff38bf9c67c74846c3806f668f

tree:
b669f368b0062fcb100b24758cf05e2c4b500144
```

Repository drift since the architectural DRAFT review:

```text
NONE
```

No re-design was required.

Before implementation authorization:

```text
origin/main MUST be re-fetched/re-pinned again.
```

---

# 2. Review disposition

Owner + Tech Lead DRAFT review result incorporated:

```text
BASE ARCHITECTURE:
ACCEPTED

CHANGES REQUIRED:
CLOSED IN THIS FINAL

RE-DESIGN:
NO
```

The following DRAFT decisions remain frozen:

```text
session identity = closed Visit / visit_id

completion cohort = closed_at

full Visit window is the attribution window

primary Traffic source = persisted Observation client counters

controller-reported offline Total = auxiliary evidence only

Current State = OUT

Public Traffic = OUT

Registry enrichment = OUT v1

AuthSession != session identity

HistoricalTrafficReadService remains AP/network only

semantic owner =
CompletedGuestSessionTrafficReadService

no new collector

no new DB

no source schema change by default

no query-time Omada

independent 24h | 7d

default 24h

page 50 / max 200

sort =
closed_at DESC, visit_id DESC

existing Traffic historical broker/coordinator

feature default false

admin.read.devices

dormant deploy and activation remain separate
```

---

# 3. Product goal

Provide a Site-scoped historical Admin Traffic product that shows:

```text
completed guest Visits

+
the Download / Upload / Total bytes that CaptivPortal can actually observe
from accepted persisted Observation counter intervals inside each Visit

+
explicit evidence quality
```

The product does NOT claim:

```text
billing-exact Traffic

packet-perfect Traffic

exact Omada connection Traffic

exact WAN/Internet Traffic

full-session zero merely because sampled observed sum is zero
```

---

# 4. Product name

Canonical v1 product name:

```text
Completed Guest Session Traffic
```

Canonical internal lifecycle identity:

```text
Visit
```

The UI term "Session" is operator-facing.

The semantic identifier is:

```text
visit_id
```

---

# 5. Metric contracts

Canonical metric family:

```text
network_traffic_completed_guest_session_observed_bytes.v1
```

Canonical session/cohort method:

```text
closed_visit_completion_cohort.v1
```

Canonical attribution method:

```text
visit_window_observation_counter_interval_sum.v1
```

Canonical connection continuity method:

```text
observation_uptime_progress_v1
```

Canonical sort:

```text
closed_at_desc_visit_id_desc.v1
```

Canonical unit:

```text
bytes
```

---

# 6. Semantic owner

Canonical semantic owner:

```text
CompletedGuestSessionTrafficReadService
```

It owns:

```text
completed Visit selection semantics

Visit-window Traffic attribution

connection continuity classification

counter interval acceptance

per-direction observed byte totals

per-session Traffic evidence quality

cursor semantics

bounded pagination
```

It is:

```text
read-only

no polling

no writes

no scheduler

no source mutation
```

It does NOT own:

```text
Visit creation/closure

Observation collection

Omada

Current State

Public Traffic

Visitor Registry identity

AP Network Traffic
```

---

# 7. Completed Guest Session identity

Canonical:

```text
Completed Guest Session
=
one Visit Lifecycle VisitRecord
with status='closed'
for the authorized canonical Site.
```

Identity:

```text
session_id = visit_id
```

NOT:

```text
client MAC

AuthSession

Omada connection

Current State client row

Visitor Registry device

Public Traffic processed event
```

---

# 8. Session start

Canonical:

```text
session_start = visit.started_at
```

No replacement by:

```text
first Observation sample

association time

first packet

Current State timestamp
```

---

# 9. Session end

Canonical:

```text
session_end = visit.closed_at
```

Required:

```text
visit.status='closed'
```

A closed Visit with structurally invalid lifecycle timestamps is an integrity
failure.

No synthetic close is created by TRAFFIC-08.

---

# 10. Duration

Canonical lifecycle duration:

```text
visit.duration_seconds
```

Presentation may format it.

Traffic sample span never replaces Visit duration.

---

# 11. Completion cohort

Selected historical range is a completion cohort:

```text
visit.closed_at >= from_utc
AND
visit.closed_at < to_utc
```

A Visit may:

```text
start before from_utc
close inside the selected range
```

and still belongs to the cohort.

The selected 24h/7d range does NOT clip Traffic attribution.

---

# 12. Full Visit attribution window

For a supported Visit:

```text
attribution_start = visit.started_at

attribution_end = visit.closed_at
```

Observation sample eligibility uses:

```text
observed_at >= visit.started_at

observed_at < visit.closed_at
```

Canonical interval:

```text
[visit.started_at, visit.closed_at)
```

No:

```text
range clipping

pre-Visit sample anchor

post-close sample anchor
```

---

# 13. Open/incomplete Visits

```text
status='open'
```

is excluded.

No Current State/Observation heuristic may convert an open Visit into a completed
session.

No synthetic timeout close in the read layer.

---

# 14. Authoritative source — session identity

Authoritative source:

```text
Visit Lifecycle
```

Existing persisted lifecycle fields are reused.

No Visit writer/schema change.

---

# 15. Authoritative source — Traffic evidence

Authoritative directional Traffic evidence:

```text
persisted Observation client counters
```

Relevant persisted fields include:

```text
site_id

client_mac

observed_at

ssid

ap_mac

uptime

traffic_down

traffic_up
```

Current Observation storage already persists:

```text
uptime
traffic_down
traffic_up
```

No schema change is required for v1 continuity.

---

# 16. Observation accepted-row boundary

TRAFFIC-08 reuses the existing accepted Observation client evidence contract.

It does not broaden acquisition population.

Traffic attribution operates on accepted persisted guest/client Observation
evidence.

No query-time Omada.

No Current State fallback.

---

# 17. Existing index reuse

Current Visit index:

```text
idx_visits_site_closed
(site_id, closed_at, visit_id)
```

Current authorization index:

```text
idx_visit_auth_visit_time
(visit_id, authorized_at, row_id)
```

Current Observation index:

```text
idx_client_site_mac_time
(site_id, client_mac, observed_at, row_id)
```

FINAL default:

```text
NO new index
```

Any future index request requires:

```text
failed accepted query-plan/PERF gate

+
profile evidence

+
architecture review
```

---

# 18. Current State boundary

Current State remains:

```text
OUT
```

TRAFFIC-07 remains frozen.

No changes to:

```text
CurrentGuestTrafficReadService

TRAFFIC-07 continuity

Current State DB

Current State collector
```

---

# 19. Public Traffic boundary

Public completed-session traffic counter remains:

```text
OUT
```

Its existing aggregate storage is not a per-Visit Site/MAC directional source.

No join.

No fallback.

No changes to:

```text
public_traffic.sqlite3

traffic_daily

processed_events

reset semantics

public portal Traffic UI
```

---

# 20. Controller-reported offline Total

Visit Lifecycle may contain:

```text
reported_traffic_total_bytes
```

from Omada offline evidence.

Its canonical meaning remains:

```text
controller-reported Traffic for the Wi-Fi/controller connection at disconnect
```

It is NOT:

```text
the canonical Captive Portal Visit D/U/T
```

It does not replace Observation D/U/T.

It does not fill missing direction.

It does not normalize Observation totals.

---

# 21. Offline Total visibility

Frozen v1 decision:

```text
controller-reported offline Total is NOT visible
in the primary TRAFFIC-08 table/API item.
```

It may remain internal diagnostic evidence.

No secondary Total column in v1.

---

# 22. Visitor Registry

Frozen:

```text
Registry enrichment = OUT v1
```

Guest display is MAC.

No device identity merge.

No randomized-MAC merge.

---

# 23. AuthSession boundary

AuthSession is not session identity.

Persisted Visit authorization attachments may be read to create attribution
boundaries.

No process-local AuthSession dependency.

---

# 24. AP Network Traffic boundary

`HistoricalTrafficReadService` remains unchanged.

TRAFFIC-08 is a different metric family:

```text
Visit/session-attributed observed client Traffic
```

No:

```text
AP Traffic allocation

AP Share allocation

Site Traffic allocation

HistoricalTrafficReadService extension
```

---

# 25. TRAFFIC-08-READ decision

Frozen:

```text
separate canonical TRAFFIC-08-READ TASK = NO
```

Implementation may internally stage read foundation first, but the roadmap item
remains:

```text
TASK-TRAFFIC-08
```

---

# 26. Canonical observed-byte semantics

For one direction:

```text
observed_direction_bytes
=
SUM(accepted persisted Observation counter deltas)
inside the Visit.
```

Download:

```text
observed_download_bytes
=
SUM(accepted traffic_down deltas)
```

Upload:

```text
observed_upload_bytes
=
SUM(accepted traffic_up deltas)
```

This is the final v1 numeric semantic.

---

# 27. Directional numeric/null rule

If a direction has:

```text
accepted_interval_count >= 1
```

then:

```text
sum > 0
→ numeric positive integer

sum = 0
→ numeric integer 0
```

If:

```text
accepted_interval_count = 0
```

then:

```text
observed_direction_bytes = null
```

Unknown never becomes zero.

---

# 28. Meaning of numeric zero

Numeric zero means only:

```text
zero bytes observed across accepted intervals
```

It does NOT automatically mean:

```text
the entire Visit consumed zero bytes
```

Evidence quality communicates whether sampled coverage is complete/partial.

This is the permanent distinction.

---

# 29. Total

Canonical backend Total:

```text
observed_total_bytes
=
observed_download_bytes + observed_upload_bytes
```

only when:

```text
observed_download_bytes is numeric

AND

observed_upload_bytes is numeric
```

Otherwise:

```text
observed_total_bytes = null
```

Browser does not recompute semantic Total.

---

# 30. Counter values

Only non-negative persisted integer counters participate.

No:

```text
negative repair

wrap inference

clamp-to-zero

floating Traffic source
```

---

# 31. Candidate interval

For two consecutive eligible samples of the same Visit:

```text
previous = P

current = C
```

the interval:

```text
(P.observed_at, C.observed_at]
```

is a candidate counter interval.

It must pass:

```text
shared interval gates

+
direction-specific counter gate
```

---

# 32. Shared identity gate

Required:

```text
P.site_id == Visit.site_id

C.site_id == Visit.site_id

P.client_mac == Visit.client_mac

C.client_mac == Visit.client_mac
```

No cross-Site.

No cross-MAC.

No cross-Visit interval.

---

# 33. Elapsed gate

```text
elapsed_seconds =
C.observed_at - P.observed_at
```

Accepted only if:

```text
0 < elapsed_seconds <= 180
```

Frozen maximum:

```text
MAX_GAP_SECONDS = 180
```

This reuses the accepted Analytics counter/gap contract.

---

# 34. Connection continuity classification

Each candidate interval MUST classify persisted uptime before numeric Traffic can
be accepted.

Canonical status:

```text
connection_continuity_status =
proven
frozen
reset
unproven
```

Exact classification:

```text
P.uptime present
C.uptime present
C.uptime > P.uptime
    → proven

P.uptime present
C.uptime present
C.uptime == P.uptime
    → frozen

P.uptime present
C.uptime present
C.uptime < P.uptime
    → reset

P.uptime missing
OR
C.uptime missing
    → unproven
```

Only:

```text
proven
```

may authorize a numeric delta.

---

# 35. Continuity method

Frozen:

```text
continuity_method =
observation_uptime_progress_v1
```

No:

```text
point connection-start estimator

window estimator

invented uptime tolerance

counters-only continuity

physical Wi-Fi boundary reconstruction
```

---

# 36. Frozen uptime

If:

```text
C.uptime == P.uptime
```

then:

```text
continuity=frozen

interval rejected
```

Reason:

```text
continuity_frozen
```

Counters may advance diagnostically but do not authorize numeric Traffic for this
interval.

---

# 37. Connection reset

If:

```text
C.uptime < P.uptime
```

then:

```text
continuity=reset

interval rejected
```

Reason:

```text
connection_reset
```

Later intervals may resume once a new pair has:

```text
C.uptime > P.uptime
```

and all other gates pass.

---

# 38. Missing uptime

If either endpoint uptime is null:

```text
continuity=unproven

interval rejected
```

Reason:

```text
continuity_unproven
```

Counters-only numeric Traffic is forbidden.

---

# 39. AP roam

AP equality is NOT required.

```text
P.ap_mac != C.ap_mac
```

alone:

```text
does not reject the interval
```

when all other gates pass.

AP roaming is not a Visit split.

---

# 40. Additional authorization boundary

Persisted authorization rows after Visit start define segmentation boundaries.

A candidate interval is rejected if an additional authorization timestamp lies:

```text
P.observed_at < authorized_at <= C.observed_at
```

excluding the authorization that established the Visit start itself.

Reason:

```text
authorization_boundary
```

The Visit remains one session.

Later intervals may resume.

---

# 41. SSID continuity

If both endpoint SSIDs are present and:

```text
P.ssid == C.ssid
```

SSID gate passes.

If both present and differ:

```text
interval rejected

reason=ssid_transition
```

If either endpoint SSID is missing:

```text
interval rejected

reason=ssid_unproven
```

SSID transition does not create a synthetic Visit.

---

# 42. Directional counter gate

For Download:

```text
P.traffic_down
C.traffic_down
```

For Upload:

```text
P.traffic_up
C.traffic_up
```

Counter logic is direction-independent.

---

# 43. Missing directional counter

If either directional counter is missing:

```text
that direction interval rejected
```

Reason:

```text
counter_missing
```

The other direction may still be accepted.

---

# 44. Counter reset

If:

```text
C.counter < P.counter
```

then that direction is rejected.

Reason:

```text
counter_reset
```

No negative delta.

No wrap.

Later intervals may resume.

---

# 45. Accepted delta

If all shared gates pass and direction counters are present/monotonic:

```text
delta = C.counter - P.counter
```

Delta may be:

```text
0
```

and is still an accepted interval.

This is the source of truthful numeric observed zero.

---

# 46. Interval acceptance formula

For one direction:

```text
accepted_interval
=
same Visit/Site/MAC
AND
valid elapsed
AND
elapsed <= 180s
AND
no authorization boundary crossed
AND
SSID proven and unchanged
AND
continuity == proven
AND
both directional counters present
AND
current counter >= previous counter
```

AP equality is not part of the formula.

---

# 47. Shared interval rejection reasons

Canonical allowlist:

```text
invalid_elapsed

gap_too_large

authorization_boundary

ssid_transition

ssid_unproven

continuity_frozen

connection_reset

continuity_unproven
```

---

# 48. Direction-specific rejection reasons

Canonical allowlist:

```text
counter_missing

counter_reset
```

---

# 49. Item-level additional reasons

Canonical item-level allowlist additionally contains:

```text
start_edge_uncovered

end_edge_uncovered

no_usable_interval

observation_source_unavailable

attribution_window_exceeds_supported_max
```

All public reason codes MUST come from the frozen allowlist.

No raw SQL/controller/internal exception text.

---

# 50. Start edge

```text
start_edge_gap_seconds =
first_eligible_observation_at - visit.started_at
```

If no eligible Observation sample:

```text
null
```

No pre-Visit sample may fill the edge.

---

# 51. End edge

```text
end_edge_gap_seconds =
visit.closed_at - last_eligible_observation_at
```

No post-close sample may fill the edge.

---

# 52. Edge threshold

Frozen sampled coverage threshold:

```text
180 seconds
```

If:

```text
start_edge_gap_seconds > 180
```

reason:

```text
start_edge_uncovered
```

If:

```text
end_edge_gap_seconds > 180
```

reason:

```text
end_edge_uncovered
```

These affect quality.

They do not invent missing bytes.

---

# 53. Complete sampled evidence — direction

Per-direction evidence status:

```text
complete
```

only when ALL are true:

```text
source available

Visit within supported attribution window

accepted_interval_count >= 1

start edge <= 180s

end edge <= 180s

no rejected shared interval inside the sampled sequence

no direction-specific rejected interval

no additional authorization boundary

no SSID transition/unproven SSID
```

Numeric sum may be:

```text
0
or
positive
```

Public wording:

```text
Complete sampled evidence
```

Not:

```text
Exact

Billing complete

Packet complete
```

---

# 54. Partial evidence — direction

Per-direction:

```text
partial
```

when:

```text
accepted_interval_count >= 1
```

but complete sampled conditions are not all satisfied.

Numeric value is still emitted.

It means:

```text
bytes safely observed across accepted intervals
```

It may be a lower bound for the whole Visit.

---

# 55. Insufficient data — direction

Per-direction:

```text
insufficient_data
```

when:

```text
Observation source is available

Visit is within supported attribution window

accepted_interval_count = 0
```

Examples:

```text
no samples

one sample only

all pairs rejected

all direction counters missing/reset
```

Value:

```text
null
```

---

# 56. Unavailable — direction

Per-direction:

```text
unavailable
```

when numeric computation is not attempted/possible because:

```text
Observation source unavailable
```

or:

```text
Visit exceeds supported attribution window
```

Value:

```text
null
```

`unavailable` is NOT `insufficient_data`.

---

# 57. Per-direction status vocabulary

Frozen:

```text
direction_evidence_status =
complete
partial
insufficient_data
unavailable
```

Used independently for Download and Upload.

---

# 58. Item Traffic evidence status

Frozen:

```text
traffic_evidence_status =
complete
partial
insufficient_data
unavailable
```

---

# 59. Item status — complete

```text
traffic_evidence_status=complete
```

iff:

```text
download_evidence_status=complete

AND

upload_evidence_status=complete
```

Total numeric.

---

# 60. Item status — partial

```text
traffic_evidence_status=partial
```

when at least one direction has usable numeric evidence but the item is not
complete.

Examples:

```text
D complete / U partial

D partial / U partial

D numeric / U insufficient_data

U numeric / D insufficient_data
```

If either direction is null:

```text
observed_total_bytes=null
```

even though the other direction may remain numeric.

---

# 61. Item status — insufficient_data

```text
traffic_evidence_status=insufficient_data
```

when:

```text
both directions have no usable numeric evidence

AND

their reason is evidence insufficiency rather than source/work unavailability
```

All D/U/T:

```text
null
```

---

# 62. Item status — unavailable

```text
traffic_evidence_status=unavailable
```

when:

```text
Observation source unavailable
```

or:

```text
Visit attribution window exceeds 86,400s
```

All D/U/T:

```text
null
```

---

# 63. Source-health fields

Root source health:

```text
visit_source_status =
healthy
unavailable
```

and:

```text
observation_source_status =
healthy
unavailable
not_required
```

`not_required` is valid when the page requires no Observation read, for example:

```text
zero completed Visit rows
```

or all returned Visits exceed the supported attribution window.

---

# 64. Root status vocabulary

Frozen:

```text
status =
ok
partial
insufficient_data
unavailable
```

Integrity contradiction is NOT represented as one of these statuses.

It fails closed.

---

# 65. Root source/evidence precedence

Exact precedence:

## 65.1 Integrity contradiction

```text
typed integrity failure
→ fail closed
→ no partial items
```

## 65.2 Visit source unavailable

```text
status=unavailable
visit_source_status=unavailable
items=[]
```

## 65.3 Healthy Visit source, zero completion rows

```text
status=ok
visit_source_status=healthy
observation_source_status=not_required
items=[]
```

## 65.4 Visit source healthy, Observation source unavailable

If returned supported Visits require Observation:

```text
status=partial

Visit rows remain visible

observation_source_status=unavailable

D/U/T=null

item evidence=unavailable
```

## 65.5 Both sources healthy / available

Page status derives from returned item evidence.

---

# 66. Root page-quality matrix

With healthy Visit source:

```text
all returned items complete
→ ok

zero returned items
→ ok

at least one partial item
→ partial

at least one unavailable item
→ partial

mixture of complete/numeric evidence and insufficient_data
→ partial

all returned items insufficient_data
→ insufficient_data

Visit source unavailable
→ unavailable
```

Root status is page-local quality.

It is NOT a population-wide immutable chain quality.

---

# 67. Observation unavailable is not insufficient_data

Frozen distinction:

```text
Observation source unavailable
→ unavailable evidence

Observation source healthy but no usable interval
→ insufficient_data
```

No conflation.

---

# 68. Long-Visit/work bound

Frozen maximum attribution window:

```text
MAX_ATTRIBUTION_WINDOW_SECONDS = 86,400
```

Equivalent:

```text
24 hours
```

Condition:

```text
visit.closed_at - visit.started_at <= 86,400s
```

is supported for Traffic computation.

---

# 69. Long Visit behavior

If:

```text
Visit duration > 86,400s
```

the Visit remains in:

```text
closed_at completion cohort
```

and remains visible.

But:

```text
Observation attribution MUST NOT be queried for that Visit

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

No first/last 24h.

No selected-range clipping.

No source scan for that item.

---

# 70. Why 24h is frozen

Pre-FINAL architectural capacity evidence used the current source/index work
shape:

```text
Visit page up to 200

Observation batch size 100

idx_client_site_mac_time

60-second accepted/default client cadence

uptime continuity

monotonic D/U

180s gap gate
```

Synthetic evidence DB:

```text
200 relevant Visits

72h source history per Visit

864,200 Observation rows

same Site+MAC+time index shape
```

EXPLAIN QUERY PLAN included:

```text
SEARCH client_observations
USING idx_client_site_mac_time
(site_id=? AND client_mac=? AND observed_at>? AND observed_at<?)
```

No full Observation table scan for each window.

---

# 71. Capacity evidence results

Raw Observation read/interval aggregation only:

## 71.1 50 Visits × 24h

10 runs:

```text
p50 ≈ 0.475s

max ≈ 0.490s
```

## 71.2 200 Visits × 24h

Two 100-Visit batches.

10 runs:

```text
p50 =
1.953s

p95 =
2.001s

max =
2.001s
```

## 71.3 200 Visits × 36h

Observed preliminary runs:

```text
median ≈ 3.02s

max ≈ 3.15s
```

## 71.4 200 Visits × 48h

Observed preliminary runs:

```text
median ≈ 4.13s

max ≈ 4.24s
```

## 71.5 200 Visits × 72h

Observed raw read time reached approximately:

```text
5.97s–6.19s
```

before:

```text
Visit cohort read

authorization segmentation

Admin authorization

serializer

JSON

response-size enforcement

HTTP
```

Therefore an uncapped long Visit is incompatible with the required end-to-end
headroom.

---

# 72. Capacity evidence interpretation

24h is the maximum supported attribution window because it leaves required
headroom for the full Admin request.

48h already consumes most of the final API200 max budget in the raw Observation
stage.

72h reaches/exceeds that final max before application-layer work.

Therefore:

```text
24h cap is evidence-backed

not a convenience limit
```

This pre-FINAL probe is architecture evidence.

It does NOT replace official candidate PERF.

---

# 73. Observation cadence support envelope

Official v1 PERF is bound to the accepted/current Observation client cadence:

```text
60 seconds
```

A future production change to a materially denser client Observation cadence
requires Traffic-08 capacity revalidation.

TRAFFIC-08 does not change Observation scheduling.

---

# 74. Historical ranges

Frozen:

```text
24h

7d
```

Default:

```text
24h
```

These ranges select completed Visits by `closed_at`.

They do not redefine the 24h per-Visit attribution work bound.

A 7d cohort can contain many supported Visits whose individual duration is:

```text
<=24h
```

---

# 75. Page-local range state

TRAFFIC-08 uses the accepted independent historical model:

```text
selected_range

applied_range

phase

last_successful_payload

last_error

intent_generation
```

No persistent preference storage.

Reload:

```text
24h
```

---

# 76. Range anchor

First/root request resolves:

```text
evaluated_at_utc
```

Then:

```text
24h:
from = evaluated_at - 24h

7d:
from = evaluated_at - 7d

to = evaluated_at
```

Range:

```text
[from_utc,to_utc)
```

is pinned into the cursor chain.

---

# 77. Sorting

Frozen:

```text
closed_at DESC

visit_id DESC
```

Sort identifier:

```text
closed_at_desc_visit_id_desc.v1
```

No v1 sort by:

```text
Total

Download

Upload

duration

MAC
```

This keeps Traffic computation page-bounded.

---

# 78. Pagination

Frozen:

```text
default limit = 50

max limit = 200
```

Keyset pagination.

No offset.

---

# 79. Cursor semantic payload

Opaque cursor pins exactly:

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

No source snapshot ID is claimed.

---

# 80. Cursor semantic name

Official v1:

```text
range-pinned keyset pagination
over the current persisted closed-Visit source
```

NOT:

```text
immutable source snapshot
```

---

# 81. Cursor ordering condition

For descending sort, the next page selects stable keys after the current cursor:

```text
closed_at < last_closed_at

OR

(
  closed_at = last_closed_at
  AND
  visit_id < last_visit_id
)
```

Exact SQL may differ but semantic ordering must be identical.

---

# 82. Live-source mutation behavior

Because cursor does not pin a persisted source snapshot:

```text
a late/recovered Visit close
may become visible in a later cursor page
if its stable sort position lies after the current cursor.
```

A late row whose sort position lies before already-consumed cursor position is
not guaranteed to appear in the current chain.

Global Refresh starts a new root chain.

---

# 83. No silent re-pin

Cursor page:

```text
uses pinned absolute range
```

It MUST NOT silently resolve a new `evaluated_at`.

Range mismatch / invalid cursor:

```text
400 invalid_request
```

Global Refresh:

```text
new evaluated_at

new absolute range

new chain
```

---

# 84. No completed_session_count root contract

Frozen:

```text
completed_session_count
is NOT required in v1 root.
```

Reason:

```text
range-pinned live source is not a frozen population snapshot.
```

Required page count:

```text
returned_count
```

only.

No misleading total count.

---

# 85. API route

Frozen:

```text
GET /admin/api/v1/sites/<site_id>/traffic/completed-sessions
```

---

# 86. API query grammar

Allowed:

```text
range=24h|7d

limit

cursor
```

Rules:

```text
range required

limit optional
default 50
1..200

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

Malformed/noncanonical cursor:

```text
400 invalid_request
```

Cursor/range mismatch:

```text
400 invalid_request
```

---

# 87. Root API DTO — exact fields

HTTP 200 semantic response root contains exactly:

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

No required population-wide quality counts in v1.

---

# 88. Root `range` DTO

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

# 89. Root `source_health` DTO

Exact:

```text
source_health: {
  visits,
  observations
}
```

`visits`:

```text
healthy | unavailable
```

`observations`:

```text
healthy | unavailable | not_required
```

---

# 90. Root `page` DTO

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
string | null
```

`sort`:

```text
closed_at_desc_visit_id_desc.v1
```

---

# 91. Item API DTO — exact fields

Each item contains exactly:

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

No raw source counters.

No offline controller Total.

No IP.

No AuthSession ID.

---

# 92. Item nullable fields

Nullable:

```text
duration_seconds

start_ssid

final_ssid

start_ap_mac

final_ap_mac

observed_download_bytes

observed_upload_bytes

observed_total_bytes

sample_count

accepted_download_interval_count

accepted_upload_interval_count

first_observed_at

last_observed_at
```

For source unavailable / unsupported attribution work:

```text
sample/accepted counts may be null
```

because no Observation result was established.

For healthy Observation source:

```text
counts are non-negative integers.
```

---

# 93. Evidence reason allowlist

Exact v1 public allowlist:

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

Deduplicated.

Stable deterministic ordering in serializer.

No unknown reason passes serialization.

---

# 94. Reason ordering

Canonical serializer ordering:

```text
attribution_window_exceeds_supported_max

observation_source_unavailable

no_usable_interval

start_edge_uncovered

end_edge_uncovered

invalid_elapsed

gap_too_large

authorization_boundary

ssid_transition

ssid_unproven

continuity_unproven

continuity_frozen

connection_reset

counter_missing

counter_reset
```

This is presentation/determinism only.

It is not semantic precedence.

---

# 95. Integrity fail-closed examples

Typed integrity failure for:

```text
cross-Site Visit row

malformed visit_id

closed Visit with missing/invalid closed_at

closed_at < started_at

duplicate Visit identity in one semantic page

malformed persisted counter type violating source schema

cursor Site/range contradiction after validation

serializer enum/reason shape violation
```

Response:

```text
safe Admin error envelope

HTTP 503

no identifying partial item payload
```

Do not leak raw exception/SQL.

---

# 96. Safe source unavailable HTTP behavior

A safely classified source-unavailable semantic result is:

```text
HTTP 200
```

with root:

```text
status=unavailable
```

or:

```text
status=partial
```

according to the frozen source matrix.

This lets the panel distinguish:

```text
valid empty/unavailable/partial semantics
```

from integrity/API failure.

---

# 97. Admin capability

Frozen:

```text
admin.read.devices
```

Every route call must repeat:

```text
authentication

canonical Site authorization

capability enforcement
```

No template-only authorization.

---

# 98. Privacy boundary

Do not expose:

```text
client IP

raw authorization IDs

AuthSession IDs

Observation raw counters

source DB paths

SQL

raw source cursor

normalized webhook body

controller payload
```

MAC remains permitted under the existing Admin device-read boundary.

---

# 99. Admin query integration

Proposed application method:

```text
AdminQueryService.completed_guest_session_traffic(...)
```

Responsibilities:

```text
request validation

Site/capability authorization

AdminQueryExecutionControls

single semantic service call

post-call deadline check

strict serialization
```

Metric calculation does not belong in AdminQueryService.

---

# 100. Deadline

No new deadline.

Reuse accepted Admin/Analytics controls.

Do not increase:

```text
Analytics/query deadline

browser Traffic timeout

Admin concurrency
```

to make TRAFFIC-08 pass.

---

# 101. Feature flag

Frozen proposal:

```text
WEB_ADMIN_TRAFFIC_COMPLETED_SESSIONS_ENABLED=false
```

Required dependencies:

```text
WEB_ADMIN_ENABLED=true

WEB_ADMIN_TRAFFIC_ENABLED=true
```

Default:

```text
false
```

---

# 102. Runtime product states

Optional product runtime state:

```text
disabled

active

unavailable
```

Product composition failure must not crash the whole Admin runtime.

No authorization-path failure.

---

# 103. Historical execution lane

TRAFFIC-08 is historical and MUST use:

```text
TrafficHistoricalRequestBroker

+

CaptivPortalTrafficCoordinator
```

Existing ownership remains unchanged.

---

# 104. Historical invariants retained

Permanent:

```text
max historical Traffic HTTP requests in flight per page = 1

Historical Request Admission Guard = 10 seconds from actual dispatch

waiting != loading

Retry-After/backoff may only be stricter

Global Refresh cannot bypass guard

503 cannot bypass guard
```

TRAFFIC-08 does not create exceptions.

---

# 105. Separate endpoint in broker

TRAFFIC-08 does NOT join:

```text
/traffic/history?products=...
```

because that endpoint belongs to AP Network Traffic semantics.

TRAFFIC-08 is a distinct historical job on the SAME execution lane.

---

# 106. Coalescing

Frozen v1:

```text
NO cross-endpoint coalescing
between TRAFFIC-08
and AP Network Traffic historical products.
```

The broker may enqueue the TRAFFIC-08 job and serialize it with existing
historical work.

No second scheduler.

---

# 107. Range independence

TRAFFIC-08 gets its own:

```text
24h | 7d
```

selector.

Changing it MUST NOT mutate:

```text
History

Statistics

Peak

Traffic by AP

AP Traffic Share
```

---

# 108. UI placement

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

# 109. UI columns

Primary v1 table:

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

AP transition may be secondary detail.

No chart in v1.

---

# 110. Guest display

Frozen:

```text
Guest = client MAC
```

No Registry join in v1.

---

# 111. SSID display

If same:

```text
SSID
```

If changed:

```text
start → final
```

Do not hide transition.

Evidence reason may include:

```text
ssid_transition
```

---

# 112. Byte display

API:

```text
integer bytes
```

UI:

```text
B / KiB / MiB / GiB
```

No loss of null/zero distinction.

---

# 113. Zero display

```text
numeric 0
→ 0 B
```

Only possible when:

```text
at least one accepted interval exists
```

It means:

```text
0 observed bytes across accepted intervals
```

---

# 114. Null display

```text
null
→ —
```

Never:

```text
null → 0 B
```

---

# 115. Evidence display labels

```text
complete
→ Complete sampled evidence

partial
→ Partial evidence

insufficient_data
→ Insufficient data

unavailable
→ Unavailable
```

No "exact" wording.

---

# 116. Long Visit UI

If over 24h bound:

```text
D/U/T = —

Evidence =
Unavailable · session exceeds 24h attribution bound
```

Session lifecycle row remains visible.

---

# 117. Observation source unavailable UI

Root warning:

```text
Traffic evidence unavailable.
Completed session history is still available.
```

Rows remain.

D/U/T:

```text
—
```

Evidence:

```text
Unavailable
```

---

# 118. Visit source unavailable UI

Root:

```text
Completed session history unavailable
```

Rows cleared.

No old identifying rows retained as current.

Existing Admin transient/previous snapshot policy may be used only if clearly
demoted under existing coordinator rules.

401/403 clears identifying data per existing Traffic security contract.

---

# 119. Empty cohort

Healthy Visit source and zero completed sessions:

```text
status=ok

items=[]
```

UI:

```text
No completed guest sessions
```

No Observation read required.

---

# 120. Refresh

No TRAFFIC-08-specific timer.

Participates in existing Traffic historical lifecycle.

Global Refresh:

```text
new root

new evaluated_at

new absolute range

cursor chain discarded
```

---

# 121. Load more

Uses:

```text
current pinned cursor chain
```

No re-pin.

Same historical execution lane and admission guard.

Late append cannot overwrite a newer root generation.

---

# 122. Source read work shape

Per page:

```text
1. read closed Visit keyset page

2. identify supported <=24h Visits

3. read authorization boundaries in bounded batch

4. build full Visit windows

5. read Observation rows in bounded batches

6. compute interval continuity/deltas/evidence

7. serialize page
```

No query per Visit connection.

No Omada call.

---

# 123. Observation batch size

Reuse existing Analytics bounded design:

```text
100 Visit windows per Observation batch
```

Therefore:

```text
limit 50
→ 1 batch

limit 200
→ 2 batches
```

unless implementation can prove equivalent or better bounded behavior.

---

# 124. No N+1

Forbidden:

```text
one independent SQLite connection per Visit

one unbounded query per Visit

one Omada query per Visit
```

Mandatory acceptance checks must detect N+1 regressions.

---

# 125. PERF workload — API50

Official candidate fixture must include:

```text
50 completed Visits

each attribution window = 24h

60s client Observation cadence

valid uptime progression

both directional counters

realistic AP roam

accepted Site/guest scope
```

Plus unrelated historical rows sufficient to prove index selectivity.

---

# 126. PERF workload — API200

Official candidate worst-supported fixture:

```text
200 completed Visits

each attribution window = 24h

60s client Observation cadence

valid uptime progression

both directional counters
```

Observation work approximately:

```text
up to ~288,000 relevant 60-second samples
```

before unrelated source density.

Two 100-window batches.

---

# 127. PERF quality fixture

Separate mixed fixture must include:

```text
uptime frozen

uptime reset

uptime missing

counter reset

counter missing

gap >180s

authorization boundary

SSID transition

start/end uncovered

zero accepted delta

no usable interval

>24h Visit
```

Correctness takes precedence over fastest path.

---

# 128. Query-plan gates

Mandatory:

Visit cohort:

```text
uses idx_visits_site_closed
or an equivalent verified indexed plan
```

Authorization boundaries:

```text
uses idx_visit_auth_visit_time
or equivalent indexed plan
```

Observation:

```text
uses idx_client_site_mac_time
for Site+MAC+time windows
```

Forbidden:

```text
full client_observations scan
for a supported page request
```

---

# 129. Full endpoint PERF path

Measure:

```text
authenticated HTTP

→ session/security

→ Site resolution

→ admin.read.devices

→ AdminQueryExecutionControls

→ CompletedGuestSessionTrafficReadService

→ serializer

→ Admin envelope

→ JSON serialization

→ response-size enforcement

→ final HTTP response
```

Direct service timing alone is insufficient.

---

# 130. PERF gates — exact

Mandatory measured runs:

```text
>=10 per workload
```

API50 hard PASS:

```text
p95 <= 2.0s

max <= 3.0s
```

API200 hard PASS:

```text
p95 <= 4.0s

max <= 6.0s
```

Additionally:

```text
query_deadline failures = 0

unexpected 5xx = 0

integrity failures = 0

source writes = 0
```

No timeout increase.

---

# 131. Payload budget

API200 acceptance budget:

```text
<= 256 KiB
```

This is:

```text
candidate acceptance/optimization budget
```

NOT a new runtime hard response limit.

Existing Admin hard response limit remains unchanged.

---

# 132. Observation cadence change rule

A future change below the accepted 60s client cadence is a capacity-affecting
operational change for this product.

Before such a change is accepted in production:

```text
rerun TRAFFIC-08 PERF
```

No automatic metric semantic change.

---

# 133. Backward compatibility

Feature false:

```text
existing Traffic page unchanged

no TRAFFIC-08 historical job

no TRAFFIC-08 semantic call

no new source workload
```

Existing Traffic metrics/owners unchanged.

---

# 134. Expected implementation areas

Likely read-only/backend areas:

```text
app/analytics/...
app/admin_web/query_service.py
app/admin_web/routes.py
new strict TRAFFIC-08 serializer
```

Frontend:

```text
app/admin_web/templates/admin/traffic.html
app/admin_web/static/admin.js
app/admin_web/static/admin.css
```

Config:

```text
app/config.py
app/settings.py
.env.example
app/admin_web/config.py
```

Exact file list belongs to Tech Lead implementation decomposition after
authorization.

---

# 135. Expected no-touch files/domains

No-touch unless STOP/review:

```text
Current State collector/storage

TRAFFIC-07 current guest service

Visit Lifecycle writer semantics

Visit schema/migrations

Observation collector

Observation schema/migrations

Public Traffic

Visitor Registry

Auth authorization path

HistoricalTrafficReadService formulas

Omada integration acquisition
```

---

# 136. Focused semantic tests

Mandatory:

```text
completion cohort by closed_at

Visit starts before range / closes inside range

open Visit excluded

full Visit window used

>24h Visit visible but Traffic unavailable

no clipping
```

---

# 137. Continuity tests

Mandatory:

```text
uptime increase
→ accepted if all other gates pass

uptime equal
→ continuity_frozen
→ rejected

uptime decrease
→ connection_reset
→ rejected

uptime missing either side
→ continuity_unproven
→ rejected

later valid post-reset pair
→ may resume

AP roam
→ allowed
```

---

# 138. Counter tests

Mandatory per direction:

```text
monotonic positive delta

monotonic zero delta

counter missing

counter regression

Download valid / Upload invalid

Upload valid / Download invalid
```

Zero delta with accepted interval:

```text
numeric 0
```

No accepted interval:

```text
null
```

---

# 139. Boundary tests

Mandatory:

```text
authorization boundary crossed
→ interval rejected

SSID transition
→ rejected

SSID missing
→ rejected

start edge >180
→ partial if usable numeric evidence exists

end edge >180
→ partial

internal gap >180
→ rejected interval
```

---

# 140. Evidence status tests

Mandatory exact matrix:

```text
both complete
→ item complete

usable numeric + any incomplete dimension
→ item partial

no usable numeric, sources healthy
→ insufficient_data

Observation unavailable
→ unavailable

>24h bound
→ unavailable
```

---

# 141. Source-health tests

Mandatory:

```text
Visit unavailable
→ root unavailable
→ items=[]

Visit healthy + Observation unavailable
→ root partial
→ Visit rows visible
→ all Traffic null
→ item unavailable

both healthy + all items insufficient
→ root insufficient_data

healthy empty cohort
→ root ok
→ observation not_required
```

---

# 142. Cursor tests

Mandatory:

```text
range pinned

evaluated_at pinned

sort pinned

Site pinned

limit does not change semantic range

no silent re-pin

malformed cursor 400

range mismatch 400

late recovered row after cursor may appear later

Global Refresh creates new chain
```

No immutable snapshot claim.

---

# 143. Site isolation tests

Mandatory:

```text
Site A Visit cannot appear in Site B

Site A Observation cannot attribute to Site B Visit

cursor from Site A cannot be used for Site B

no cross-Site counts/items/reasons
```

---

# 144. Serializer tests

Mandatory:

```text
exact root field allowlist

exact item field allowlist

enum allowlists

reason allowlist

integer bytes only

null/zero distinction

canonical UTC

canonical MAC

no raw source fields

fail closed on impossible internal DTO
```

---

# 145. Historical broker tests

Mandatory:

```text
same execution lane

max historical in-flight 1

10-second guard applies

range change waiting/loading semantics

Global Refresh cannot bypass guard

Load more cannot bypass guard

late append cannot overwrite newer root

no second AbortController owner

no second timer owner
```

---

# 146. Regression scope

Focused regression must include at least:

```text
Visit Lifecycle reads

Visit Analytics Traffic summary

Observation reads

AnalyticsSourceGateway

Traffic historical broker

Independent Traffic ranges

Current Network Throughput

Network Traffic History

Period Statistics

Peak Load

Traffic by AP

AP Traffic Share

Online Guests Traffic

Admin auth/Site isolation
```

Candidate regressions:

```text
0
```

---

# 147. Central Lab

Mandatory official Central Lab before publication.

Strict regressions:

```text
0
```

Owner + Tech Lead Lab own official PASS/FAIL.

Coder does not self-certify Central Lab.

---

# 148. Read-only immutability

Mandatory:

```text
Visit DB unchanged

Observation DB unchanged

Public Traffic DB unchanged

Current State DB unchanged
```

TRAFFIC-08 is read-only.

---

# 149. Feature deployment

Initial code deploy:

```text
FROM GIT
```

with:

```text
WEB_ADMIN_TRAFFIC_COMPLETED_SESSIONS_ENABLED=false
```

Dormant first.

No implementation authorization is granted by this FINAL.

---

# 150. Dormant production acceptance

Required:

```text
captive-portal.service active

no restart regression

existing Traffic APIs healthy

TRAFFIC-07 healthy

Visit Lifecycle healthy

Observation healthy

TRAFFIC-08 panel absent

TRAFFIC-08 route 404 under disabled feature

no TRAFFIC-08 source workload

no new worker

no DB/schema mutation
```

---

# 151. Activation

Separate controlled step only after:

```text
implementation accepted

all test/PERF gates PASS

publication/merge authorized and complete

production dormant acceptance PASS

separate Owner activation authorization
```

Set:

```text
WEB_ADMIN_TRAFFIC_COMPLETED_SESSIONS_ENABLED=true
```

---

# 152. Production browser acceptance

Manual Owner acceptance:

```text
panel visible in frozen UI location

default 24h

24h → 7d → 24h

other historical panel ranges unchanged

completed sessions newest-first

MAC/start/end/duration/SSID shown

D/U/T correct numeric/null behavior

numeric observed zero renders 0 B

unknown renders —

Evidence labels correct

>24h Visit shows unavailable/no clipping if available in production data

Load more preserves range chain

Global Refresh creates new root

Online Guests Traffic remains healthy
```

Unsafe synthetic counter/reset manipulation is Lab-owned.

---

# 153. Rollback

Primary product rollback:

```text
WEB_ADMIN_TRAFFIC_COMPLETED_SESSIONS_ENABLED=false
```

No data rollback.

No schema rollback.

No source cleanup.

No worker cleanup.

---

# 154. Canonical architecture decisions

1. `TRAFFIC-08` is Completed Guest Session Traffic.
2. Session identity is one closed Visit.
3. `visit_id` is the item identity.
4. Completion cohort uses `closed_at`.
5. Full Visit window is used; selected range never clips attribution.
6. Primary Traffic evidence is Observation client counters.
7. Numeric fields are explicitly `observed_*_bytes`.
8. Numeric zero means zero observed across accepted intervals, not necessarily full-Visit zero.
9. Unknown is null.
10. Total is backend D+U only when both directions numeric.
11. Uptime continuity is mandatory.
12. Uptime increase proves sampled continuity.
13. Equal uptime is frozen/rejected.
14. Uptime regression is reset/rejected.
15. Missing uptime is unproven/rejected.
16. Counters-only numeric attribution is forbidden.
17. AP roam is allowed.
18. Authorization boundary cannot be crossed.
19. SSID boundary cannot be crossed.
20. Directional counters are independent.
21. Counter reset affects only that direction.
22. 180s is the exact edge/internal gap threshold.
23. Evidence vocabulary is complete/partial/insufficient_data/unavailable.
24. `unavailable` and `insufficient_data` are distinct.
25. Public complete wording is "Complete sampled evidence".
26. Visit source unavailable makes root unavailable/items empty.
27. Observation unavailable makes root partial/Visit rows visible/Traffic unavailable.
28. Healthy-source no-usable-evidence is insufficient_data.
29. Cursor is live range-pinned keyset, not immutable snapshot.
30. Cursor pins Site/range/absolute range/evaluated_at/sort/last key.
31. No completed-session total-count field is required.
32. Late/recovered rows may appear later according to sort position.
33. Global Refresh creates a new chain.
34. Max attribution window is exactly 86,400 seconds.
35. >24h Visit remains visible but Traffic is unavailable.
36. >24h Visit is never clipped.
37. 24h bound is supported by pre-FINAL capacity evidence.
38. Official API50 PERF p95<=2s/max<=3s.
39. Official API200 PERF p95<=4s/max<=6s.
40. API200 acceptance payload <=256 KiB.
41. Default page=50, max=200.
42. Sort is closed_at DESC, visit_id DESC.
43. Independent ranges are 24h/7d; default 24h.
44. Existing historical broker/coordinator owns lifecycle.
45. Max historical in-flight remains 1.
46. 10-second Historical Request Admission Guard remains unchanged.
47. No cross-endpoint coalescing in v1.
48. Current State is out.
49. Public Traffic is out.
50. Registry enrichment is out.
51. AuthSession is not session identity.
52. HistoricalTrafficReadService remains AP/network only.
53. Controller offline Total is auxiliary and hidden in primary v1.
54. No query-time Omada.
55. No new collector.
56. No new DB.
57. No source schema/index change by default.
58. No separate canonical TRAFFIC-08-READ.
59. Capability is `admin.read.devices`.
60. Feature default is false.
61. Dormant deploy and activation remain separate.
62. This FINAL does not authorize implementation.

---

# 155. Final state

```text
TASK:
TASK-TRAFFIC-08 — Completed Guest Session Traffic

DOCUMENT:
FINAL ARCHITECTURE

BOUND TO:
main@e196b042515498c5cd9143a9962f6aed90f31566

TREE:
f88ee1f854135107c647ccd9d346be2b2ba504b9

REPOSITORY DRIFT:
NONE

SESSION IDENTITY:
closed Visit / visit_id

COHORT:
closed_at in selected 24h/7d range

ATTRIBUTION WINDOW:
full Visit [started_at,closed_at)

MAX ATTRIBUTION WINDOW:
86,400 seconds

LONG VISIT:
visible
Traffic null
evidence unavailable
no clipping

METRIC:
network_traffic_completed_guest_session_observed_bytes.v1

SESSION METHOD:
closed_visit_completion_cohort.v1

ATTRIBUTION METHOD:
visit_window_observation_counter_interval_sum.v1

CONTINUITY:
observation_uptime_progress_v1

PRIMARY TRAFFIC SOURCE:
Observation client counters

OBSERVED ZERO:
accepted interval sum == 0
→ numeric 0

NO USABLE INTERVAL:
null

DIRECTION EVIDENCE:
complete | partial | insufficient_data | unavailable

ITEM EVIDENCE:
complete | partial | insufficient_data | unavailable

ROOT STATUS:
ok | partial | insufficient_data | unavailable

VISIT SOURCE UNAVAILABLE:
unavailable / items=[]

OBSERVATION SOURCE UNAVAILABLE:
partial / Visit rows visible / Traffic null / unavailable evidence

RANGE:
24h | 7d independent

DEFAULT:
24h

PAGE:
50 default / 200 max

SORT:
closed_at DESC, visit_id DESC

CURSOR:
range-pinned live keyset
NO immutable snapshot claim

COMPLETED_SESSION_COUNT:
NOT REQUIRED

GAP:
180 seconds

API:
GET /admin/api/v1/sites/<site_id>/traffic/completed-sessions

CAPABILITY:
admin.read.devices

API50 PERF:
p95 <=2.0s
max <=3.0s

API200 PERF:
p95 <=4.0s
max <=6.0s

PAYLOAD BUDGET:
API200 <=256 KiB

HISTORICAL EXECUTION:
existing broker/coordinator only

HISTORICAL IN-FLIGHT:
1

ADMISSION GUARD:
10 seconds unchanged

NEW COLLECTOR:
NO

NEW DB:
NO

SCHEMA CHANGE:
NO by default

QUERY-TIME OMADA:
NO

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

# 156. Next allowed step

Owner + Tech Lead perform FINAL acceptance.

If accepted:

```text
ARCHITECTURE = CLOSED
```

Then only after a separate explicit Owner implementation authorization:

```text
re-fetch origin/main

re-pin exact SHA/tree

impact review

Tech Lead implementation decomposition

Coder task
```

No implementation may begin from this FINAL without that separate authorization.
