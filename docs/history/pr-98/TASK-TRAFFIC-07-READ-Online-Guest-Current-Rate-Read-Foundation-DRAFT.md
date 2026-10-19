# TASK-TRAFFIC-07-READ — Online Guest Current Rate Read Foundation — DRAFT

**Project:** CaptivPortal  
**Area:** Admin Console → Traffic  
**Roadmap item:** `TRAFFIC-07-READ — Current Rate backend foundation`  
**Consumer:** future `TRAFFIC-07 — Online Guests Traffic`  
**Status:** `DRAFT — FOR OWNER + TECH LEAD ARCHITECTURAL REVIEW`  
**Prepared:** 2026-09-01  
**Implementation authorization:** `NOT GRANTED`  
**Code / branch / patch / PR / merge / deploy / activation:** `NOT AUTHORIZED`

---

# 1. Executive decision

Canonical roadmap decision:

```text
TRAFFIC-07-READ = REQUIRED
```

It is NOT absorbed by:

```text
TRAFFIC-02-READ
HistoricalTrafficReadService
CurrentTrafficReadService
TRAFFIC-05 / AP contribution primitives
TRAFFIC-06 / AP Share
Visit Lifecycle
```

The platform already persists enough raw/current evidence to derive a near-current
per-client Traffic rate, but does NOT yet have a canonical owner for:

```text
current Online Guest population

coherent current/baseline client snapshot pairing

cumulative client-counter delta

counter reset / gap / auth-continuity rules

Download / Upload / Total current-rate semantics

optional Visit correlation

consumer-safe pagination/provenance
```

`TRAFFIC-07-READ` creates exactly that missing read foundation.

It does NOT create the visible `Online Guests Traffic` panel.

Future `TRAFFIC-07` consumes this foundation.

---

# 2. Current repository / production baseline

Current `origin/main` was re-fetched before this DRAFT.

```text
main:
2a101cd27d69866db177254209d4e32529dbf56e

tree:
ed941c64ed2e612d74db1724da9d6850727070e7
```

Current main:

```text
Merge PR #97
Docs: reconcile TRAFFIC-06 AP Traffic Share production state
```

Runtime / production implementation:

```text
HEAD:
c5f9dc39bbf399847f147526c9c7ae15769a198c

tree:
0831ecf598b5760e8ede2e9e94a25b926480c2dd
```

Current production Traffic stages:

```text
TRAFFIC-01
DONE / PRODUCTION ACTIVE

TRAFFIC-02
DONE / PRODUCTION ACTIVE

TRAFFIC-03
DONE / PRODUCTION ACTIVE

TRAFFIC-04
DONE / PRODUCTION ACTIVE

TRAFFIC-05
DONE / PRODUCTION ACTIVE

TRAFFIC-RANGE-01
DONE / PRODUCTION ACTIVE

TRAFFIC-06
DONE / PRODUCTION ACTIVE / PRODUCTION ACCEPTANCE PASS
```

Current KB roadmap:

```text
TRAFFIC-07 — Online Guests Traffic
NEXT / NOT IMPLEMENTED

TRAFFIC-07-READ — Current Rate backend foundation
CONDITIONAL / NOT IMPLEMENTED
```

This DRAFT resolves the conditional:

```text
TRAFFIC-07-READ is architecturally required.
```

Before FINAL and again before implementation authorization:

```text
re-fetch origin/main
re-pin exact SHA/tree
classify docs-only vs implementation drift
impact-review changes touching:
  Current State
  Visit Lifecycle
  Analytics
  Admin Traffic
```

---

# 3. Why existing read foundations are insufficient

## 3.1 `TRAFFIC-02-READ / HistoricalTrafficReadService`

Owns historical AP/network Traffic:

```text
History
Statistics
Peak
Traffic by AP
AP Traffic Share
```

It does NOT own:

```text
active current client population
current guest authorization
per-client cumulative counter baseline pairing
per-client current Mbps
```

Extending it into current guest rate would mix historical AP Network Traffic with
current authorized-client Traffic.

Rejected as owner.

## 3.2 `CurrentTrafficReadService`

Owns current Site/AP Network Throughput from persisted AP Observation facts.

It does NOT own:

```text
guest identity
client authorization
per-client traffic counters
Visit relationship
```

Guest rates MUST NOT be allocated from AP current throughput.

Rejected as owner.

## 3.3 TRAFFIC-05 / TRAFFIC-06 AP primitives

AP contribution primitives prove AP historical contribution.

They cannot prove:

```text
which client is online now
which client is authorized now
how one client's cumulative counters progressed
```

Rejected as current guest-rate source.

## 3.4 Visit Lifecycle

Visit Lifecycle owns durable Visit identity/history and completed/offline event
Traffic evidence.

Permanent:

```text
AuthSession != Visit
```

and Visit persistence is fail-open relative to successful authorization.

Therefore:

```text
no open Visit
```

does NOT prove:

```text
not an Online Guest
```

Also Visit `reported_traffic_*` is completed-session/offline evidence, not current
Mbps.

Visit is optional correlation/enrichment only.

## 3.5 Current State

Current State already persists:

```text
active wireless client snapshots
auth classification
SSID
AP identity
client MAC
controller uptime
controller_traffic_down
controller_traffic_up
controller_traffic_total
short snapshot history
```

and classifies:

```text
authStatus=2 → authorized
authStatus=1 → pending
```

This is the correct raw evidence family.

But its current read contract provides latest snapshots/pages/summary/history
quality, not a canonical:

```text
latest compatible snapshot
+
previous compatible snapshot
→ per-client current rate
```

That is the missing read foundation.

---

# 4. Foundation purpose

`TRAFFIC-07-READ` answers:

```text
For the latest proven current Online Guest population,
what current Download / Upload / Total Traffic rate
can be safely derived from persisted controller client counters?
```

It also answers:

```text
which guest rates are unavailable
and why
```

This is current-oriented.

It is NOT a `24h / 7d` historical product.

---

# 5. Canonical semantic owner

A distinct current-client semantic owner is required.

Recommended conceptual owner:

```text
CurrentGuestTrafficReadService
```

Exact class/file name may be refined before FINAL.

Ownership split:

```text
CurrentStateReadService
→ persisted current client facts

CurrentGuestTrafficReadService
→ Online Guest population + current client-rate interpretation

VisitLifecycleReadService
→ optional Visit enrichment

CurrentTrafficReadService
→ Site/AP current Network Throughput

HistoricalTrafficReadService
→ Site/AP historical Network Traffic
```

This is a new semantic family, not a second owner of an existing AP metric.

---

# 6. Authoritative sources

Canonical read path:

```text
Current State collector
→ current_state.sqlite3
→ CurrentStateReadService
→ bounded coherent snapshot-pair evidence
→ CurrentGuestTrafficReadService
→ future TRAFFIC-07
```

Optional enrichment:

```text
Visit Lifecycle
→ VisitLifecycleReadService
→ open-Visit context
```

Forbidden:

```text
Admin request → Omada
Browser → Omada
Browser → Current State DB
new client Traffic collector
new client Traffic DB
```

No query-time controller dependency.

---

# 7. Canonical definition: `Online Guest`

An Online Guest is proven only from an accepted current Current State snapshot.

Required current snapshot:

```text
authorized canonical Site
result = success
complete = true
source scope compatible/current
freshness = fresh
```

Required row:

```text
wireless = true
active = true
auth_classification = authorized
SSID belongs to exact canonical Current State guest/client scope
canonical client MAC exists
```

Not sufficient alone:

```text
Omada guest boolean
open Visit
AuthSession
Visitor Registry identity
Observation history
AP Traffic evidence
```

Pending / other / unknown auth states are not Online Guests.

---

# 8. Freshness and the word `Online`

The word:

```text
Online
```

is asserted only from:

```text
fresh
```

Current State client snapshot evidence.

Required behavior:

```text
fresh snapshot
→ Online Guest population may be returned

stale snapshot
→ no new current Online Guest assertion

unavailable snapshot
→ no current Online Guest assertion
```

A future UI may retain previously accepted data while a source becomes stale, but
stale persisted rows MUST NOT be relabelled as current Online Guests.

---

# 9. Online Guest network identity

Canonical rate identity:

```text
client MAC
```

Do NOT merge rate continuity across different MACs.

Randomized/new MAC:

```text
new network-client identity
```

even if Visitor Registry later links both MACs to one physical person/device.

Registry/Visit identity can enrich display, not rate continuity.

---

# 10. Current/baseline snapshot coherence

One current-rate execution uses exactly one coherent Site-wide snapshot pair.

## Current snapshot

```text
latest complete-success client cycle
same authorized Site
exact current source_scope_hash
fresh
```

## Baseline snapshot

```text
nearest previous complete-success client cycle
strictly earlier
same Site
same source_scope_hash
compatible client scope
```

All clients in one result use the same:

```text
current cycle
baseline cycle
elapsed interval
```

Forbidden:

```text
different baseline cycle per client
```

---

# 11. Maximum baseline gap

DRAFT proposal:

```text
CURRENT_GUEST_RATE_MAX_GAP_SECONDS = 180
```

Exact code constant name is implementation detail.

This is a rate-evidence bound, not:

```text
HTTP timeout
QueryDeadline
browser refresh interval
```

No numeric current rate if:

```text
elapsed <= 0
or
elapsed > 180s
```

`180s` requires explicit Owner + Tech Lead acceptance before FINAL.

---

# 12. Canonical source counters

Canonical current-rate inputs:

```text
controller_traffic_down
controller_traffic_up
```

These are cumulative controller client counters.

Canonical rate derives from counter delta.

Forbidden as actual symmetric Traffic throughput source:

```text
rxRate
txRate
activity
```

`rxRate/txRate` are link/PHY evidence, not real current client throughput.

No browser-side Mbps calculation.

---

# 13. Download / Upload / Total formula

Let:

```text
t0 = baseline observed_at
t1 = current observed_at
Δt = t1 - t0
```

For one MAC:

```text
D0 = baseline controller_traffic_down
D1 = current controller_traffic_down

U0 = baseline controller_traffic_up
U1 = current controller_traffic_up
```

If valid:

```text
ΔD_bytes = D1 - D0
ΔU_bytes = U1 - U0
```

Download:

```text
download_mbps =
(ΔD_bytes × 8)
/
(Δt_seconds × 1_000_000)
```

Upload:

```text
upload_mbps =
(ΔU_bytes × 8)
/
(Δt_seconds × 1_000_000)
```

Total:

```text
total_mbps =
download_mbps + upload_mbps
```

Backend Total is canonical.

Browser does not recompute Total.

---

# 14. Direction meaning

```text
Download
=
traffic toward/downloaded by client
from controller_traffic_down delta

Upload
=
traffic from/uploaded by client
from controller_traffic_up delta

Total
=
Download + Upload on same accepted interval
```

This is current per-client Network Traffic evidence.

Not:

```text
WAN-only
Internet-only
billing
completed-session volume
```

---

# 15. Valid zero vs null

Valid counter delta:

```text
0 bytes
```

over a valid interval means:

```text
0.0 Mbps
```

This is true zero.

Null/unavailable means evidence does not safely prove a rate.

Never replace:

```text
null
```

with:

```text
0
```

---

# 16. Authorized baseline continuity

Current row must be an Online Guest.

For numeric rate, the same MAC baseline row must also be:

```text
wireless
active
authorized
same Site
compatible source scope
```

If baseline was:

```text
pending
other
unknown
```

then:

```text
rate = null
reason = no_authorized_baseline
```

Do not calculate a rate across authorization transition.

---

# 17. Counter / connection reset semantics

## Counter regression

Direction where:

```text
current counter < baseline counter
```

means:

```text
counter_reset
rate = null
```

No negative rate and no wrap assumption.

## Uptime regression

If both uptimes exist and:

```text
current_uptime < baseline_uptime
```

then:

```text
connection_reset

D/U/Total = null
```

## Equal uptime

DRAFT conservative rule:

```text
current_uptime == baseline_uptime
→ progress_unproven
→ no numeric rate
```

even if wall-clock snapshot time advanced.

This avoids interpreting repeated/stuck controller state as true zero.

This rule requires explicit review before FINAL.

## Uptime unavailable

If one/both uptimes are null but counters are valid and monotonic:

```text
numeric rate may still be accepted

continuity_basis = counters_only
```

Do not pretend uptime continuity was proven.

---

# 18. Per-direction partial evidence

Example:

```text
Download counters valid
Upload counter missing
```

Then:

```text
download_mbps = numeric
upload_mbps = null
total_mbps = null
```

Total is numeric only when both D/U are numeric.

Missing direction is never assumed zero.

---

# 19. Proposed item rate status/reasons

Overall:

```text
rate_status =
valid
partial
unavailable
```

Reason family:

```text
valid
no_baseline
no_authorized_baseline
baseline_gap_too_large
invalid_elapsed
counter_missing
counter_reset
connection_reset
progress_unproven
baseline_quality_untrusted
```

Continuity provenance:

```text
continuity_basis =
uptime_and_counters
counters_only
none
```

`valid`:

```text
D/U/Total numeric
```

`partial`:

```text
one direction numeric
other null
Total null
```

`unavailable`:

```text
no safely numeric direction
```

---

# 20. Snapshot quality / duplicate/conflicting evidence

Current cycle must be complete-success.

No current Online Guest population from:

```text
partial
failed
shutdown
```

cycles.

## Duplicate identity metadata

If current or baseline cycle reports:

```text
duplicate_identity_count > 0
```

DRAFT recommends:

```text
unique current identified Online Guest population may remain visible

rate pair = quality-untrusted

numeric rates unavailable

result = partial
```

Reason:

```text
discarded/conflicting duplicate counter identity cannot be proven harmless
from the current read model
```

No guessing.

## Unidentified rows

Unidentified rows are not invented into the guest list.

If present:

```text
population_complete = false
result = partial
```

## Unknown authorization rows

Unknown auth rows are excluded and contribute a quality reason.

## Impossible persisted invariants

Cross-Site rows, invalid global timestamps, schema mismatch, impossible canonical
MAC uniqueness or scope contradiction:

```text
FAIL CLOSED for read result
```

---

# 21. Visit / guest / session relationship

Online truth:

```text
Current State
```

Visit Lifecycle is optional enrichment only.

For one Online Guest:

```text
Site + MAC
```

may correlate to an open Visit.

Recommended:

```text
visit_context_status =
matched
missing
unavailable
conflict
```

`matched` may provide:

```text
visit_id
device_id if linked
visit_started_at
```

Temporal compatibility:

```text
visit.started_at <= current_snapshot.observed_at
```

A Visit created after the persisted current snapshot is not retroactively attached.

Missing Visit:

```text
does not invalidate Online status
does not invalidate current rate
```

Visit source unavailable:

```text
does not destroy Current State rate
```

Conflicting Visit matches:

```text
do not choose one arbitrarily
visit_context_status = conflict
visit_id = null
```

---

# 22. AuthSession relationship

Process-local AuthSession is NOT required for Online Guest identity.

It may disappear on process restart while a client remains authorized.

Permanent:

```text
AuthSession != Visit
AuthSession != current network online truth
```

Future TRAFFIC-07 must not depend on an in-memory AuthSession being present.

---

# 23. Completed-session Traffic boundary

Visit Lifecycle reported Traffic bytes from terminal/offline evidence mean:

```text
completed-session/event-reported Traffic
```

They MUST NOT become:

```text
current Mbps
baseline client counter
```

Likewise Current State cumulative counters are NOT automatically:

```text
Visit total
session total
billing bytes
```

Current Rate and completed-session Traffic are different metric families.

---

# 24. Current vs historical evidence boundary

`TRAFFIC-07-READ` uses short Current State history only for:

```text
one immediate compatible baseline snapshot
```

It does NOT create a historical 24h/7d guest Traffic series.

No historical range selector belongs to this foundation.

Future historical guest Traffic would require separate architecture.

---

# 25. Relationship to Current Network Throughput

No additive identity is claimed between:

```text
sum(Online Guest current rates)
```

and:

```text
Current Network Throughput
```

Reasons:

```text
AP current Network Traffic can include non-guest/non-current-cohort traffic

AP Observation cycle and Current State client cycle timing differ

source semantics differ
```

Forbidden:

```text
allocate AP throughput to guests
renormalize guest rates to AP total
force equality
```

---

# 26. Relationship to Observation client history

Observation contains historical authorized-client facts, but is not canonical
Online-now truth.

v1 rule:

```text
Current State = current online source

Observation = not a current-rate fallback
```

Forbidden:

```text
Current State unavailable
→ silently derive current guest rate from Observation
```

Observation may be validation/reference only unless later approved.

---

# 27. Consumer service contract

Recommended conceptual method:

```text
CurrentGuestTrafficReadService.list_online_guest_rates(
    site_id,
    evaluated_at_utc,
    limit,
    cursor,
    sort
)
```

Exact Python signature is not frozen.

One result is pinned to:

```text
Site
current cycle
baseline cycle
source scope
evaluated_at
```

Future TRAFFIC-07 MUST NOT reproduce the rate formula outside this service.

---

# 28. Proposed result contract

Conceptual:

```text
site_id
evaluated_at_utc
status

source_scope:
  version
  hash
  ssids

current_snapshot:
  cycle_id
  observed_at
  capture_finished_at
  age_seconds
  freshness_status

baseline_snapshot:
  cycle_id
  observed_at
  elapsed_seconds

population:
  identified_online_guest_count
  population_complete

rate_coverage:
  valid_rate_count
  partial_rate_count
  unavailable_rate_count
  reasons

items
next_cursor
```

No DB path.

No raw Omada payload.

---

# 29. Proposed item contract

```text
client_mac

display_name
display_name_source

ssid

ap_mac
ap_name

online_state = online
auth_classification = authorized

current_observed_at
baseline_observed_at
elapsed_seconds

download_mbps
upload_mbps
total_mbps

download_reason
upload_reason
rate_status
continuity_basis

visit_context_status
visit_id
device_id
visit_started_at
```

Display-name fallback:

```text
current name
→ current hostname
→ MAC
```

Raw cumulative counters remain internal by default.

---

# 30. Pagination / deterministic pinning

Foundation must be bounded.

DRAFT proposal:

```text
default limit = 50
max limit = 200
```

Cursor pins at least:

```text
version
endpoint/kind
Site
current cycle
baseline cycle
source_scope_hash
sort
last key
```

Page 2 MUST NOT silently move to newer current/baseline cycles.

Recommended sorts:

```text
total_rate_desc
client_mac_asc
```

Default:

```text
total_rate_desc
```

Null Total rates sort after numeric.

Tie:

```text
client_mac ascending
```

---

# 31. Global snapshot-pair selection before pagination

Select:

```text
one current cycle
one baseline cycle
```

before page calculation.

Forbidden:

```text
page-specific snapshot pair
per-client arbitrary prior cycle
```

All pages in one cursor chain describe one coherent current-rate instant.

---

# 32. Required CurrentStateReadService extension

CurrentStateReadService does not currently expose the exact rate pair.

DRAFT recommends a narrow read-only helper, conceptually:

```text
get_client_rate_snapshot_pair(...)
```

or equivalent.

It may provide:

```text
current cycle metadata
previous compatible cycle metadata
current authorized rows
matching baseline rows
cycle quality
```

Permanent:

```text
Current State remains schema/persistence owner
read-only connection
same Site/scope validation
no new writer
```

---

# 33. Optional Visit batch enrichment

Future page should not create N browser calls or preferably N SQLite queries for N
guests.

`TRAFFIC-07-READ` may add a bounded read-only Visit helper:

```text
get_open_visits_for_client_macs(site_id, client_macs)
```

maximum input <= read-page max.

This does not change Visit semantics.

If profiling shows existing bounded reads suffice, do not add unnecessary helper.

---

# 34. Foundation status model

Proposed:

```text
ok
partial
insufficient_data
stale
unavailable
```

`ok`:

```text
fresh complete current snapshot
population safely classified
compatible baseline
no snapshot-wide rate blocker
```

Individual newly-online guests may still have no rate.

`partial` examples:

```text
unidentified/unknown-status source rows
Visit enrichment unavailable
some item counters/reset/missing
```

`insufficient_data`:

```text
fresh current Online population exists
but no compatible baseline
```

Online guests may be returned with null rates.

`stale`:

```text
latest complete current snapshot stale
no new current Online assertion
```

`unavailable`:

```text
no complete snapshot
snapshot beyond unavailable threshold
schema/storage/global integrity failure
```

---

# 35. Online state and rate availability are separate

Valid:

```text
online_state = online
rate_status = unavailable
```

Example:

```text
newly authorized guest
no authorized baseline yet
```

Do not remove guest because rate is unavailable.

Conversely stale source cannot produce a new `online` assertion merely because
counter arithmetic is possible.

---

# 36. Fail-open / fail-closed

Relative to guest authorization:

```text
TRAFFIC-07-READ is FAIL-OPEN
```

Its failure never revokes valid guest authorization.

Read-result fail-closed on:

```text
schema mismatch
storage corruption
cross-Site evidence
impossible cycle identity
invalid global elapsed
source-scope contradiction
unsafe current snapshot integrity
```

Safe item/enrichment degradation for:

```text
no baseline
one direction counter missing
counter reset
Visit missing
Visit source unavailable
```

---

# 37. API projection

`TRAFFIC-07-READ` is backend foundation only.

Required:

```text
NO new user-visible Admin Traffic endpoint
NO panel
```

Canonical consumer is future in-process AdminQueryService / TRAFFIC-07.

Reserved direction for future TRAFFIC-07:

```text
GET /admin/api/v1/sites/<site_id>/traffic/online-guests/current
```

This route is NOT implemented by 07-READ.

Do NOT add current Online Guests to:

```text
/traffic/history?products=...
```

because it is range-insensitive.

---

# 38. Internal API

No new protected internal Analytics endpoint is required solely for 07-READ.

If a real separate consumer later needs it:

```text
separate review
```

No speculative surface.

---

# 39. Feature flag

07-READ exposes no product.

DRAFT recommendation:

```text
NO new product feature flag in TRAFFIC-07-READ
```

No route/panel/worker means foundation is dormant until a consumer invokes it.

Future TRAFFIC-07 should own product exposure, proposed:

```text
WEB_ADMIN_TRAFFIC_ONLINE_GUESTS_ENABLED=false
```

Exact future flag remains TRAFFIC-07 scope.

---

# 40. UI scope

07-READ has:

```text
NO UI
```

Expected future TRAFFIC-07 direction:

```text
Online Guests Traffic

current/range-insensitive

Online Guest label/MAC
AP / SSID
Download / Upload / Total Mbps
optional Visit context
explicit no-rate reasons
```

No 24h/7d selector for current-rate v1.

---

# 41. Traffic coordinator relationship

07-READ has no browser lifecycle.

Future TRAFFIC-07 is expected to register through:

```text
CaptivPortalTrafficCoordinator
```

as a current product class.

Expected:

```text
autoRefresh = true
```

subject to TRAFFIC-07 review.

It MUST NOT use:

```text
TrafficHistoricalRequestBroker
historical 10-second admission guard
```

No new scheduler owner.

---

# 42. Current State collection cadence

Current default client collection interval:

```text
60 seconds
```

Browser polling faster than source capture does not create fresher evidence.

Foundation exposes cycle/timestamp/baseline identity so repeated reads of the same
snapshot pair are explicit.

No higher-frequency Omada polling is introduced.

---

# 43. Security / privacy

Admin-only, Site-scoped.

No cross-Site:

```text
current rows
baseline rows
Visit rows
```

Do not expose:

```text
Portal secrets
raw Omada payload
DB paths
debug SQL
```

DRAFT privacy recommendation:

```text
future default Traffic DTO omits client IP
```

unless Owner explicitly needs it.

Home Live remains the richer operational client-details surface.

---

# 44. Capacity / work shape

Do not assume only a small current guest population.

Current State supports bounded source pressure up to thousands of rows.

v1 request should use only:

```text
current cycle
one previous compatible cycle
bounded current page
bounded Visit enrichment
```

Forbidden:

```text
full 48h Current State scan
per-client history search
N+1 baseline DB connections
unbounded result
```

Recommended SQL shape:

```text
select current cycle
select nearest compatible prior cycle
select bounded authorized current rows
join/look up baseline by:
  baseline cycle + client MAC
```

Existing cycle/auth/client indexes should be used where adequate.

---

# 45. Performance / capacity contract

07-READ requires its own PERF.

Historical AP PERF does not define this service's thresholds.

## Evidence

Mandatory:

```text
real production Current State DB

and

immutable capacity fixture:
10,000 current client rows
10,000 baseline client rows
```

Fixture covers:

```text
authorized
pending
unknown
missing baseline
counter reset
valid zero
```

Visit fixture covers max visible page.

## Variants

```text
R50
50-row rate page

R200
200-row max page

RV50
50-row + Visit enrichment

RV200
200-row + Visit enrichment

RBAD
missing/incompatible/quality-untrusted baseline
```

At least 10 measured runs per timed variant.

## DRAFT latency gates

On 10k+10k fixture:

```text
R200:
p95 <= 1.0s
max <= 1.5s

RV200:
p95 <= 1.5s
max <= 2.0s

unexpected 5xx = 0
source writes = 0
```

These thresholds require review before FINAL.

## Query plan

Prove:

```text
bounded current cycle lookup
bounded prior-cycle lookup
cycle/auth/client index use or equivalent
baseline lookup by cycle+MAC
no 48h full scan
no unbounded temporary materialization
bounded Visit enrichment
```

No new index is authorized by this DRAFT.

If current schema cannot meet accepted gate:

```text
STOP
→ profile/query-plan evidence
→ architecture review
```

---

# 46. Backward compatibility

Must not change existing semantics of:

```text
Current State / Home Live
Current Network Throughput
Historical Traffic
Traffic by AP
AP Traffic Share
Visit Lifecycle
Home Activity
completed-session Traffic
```

Existing Current State fields:

```text
controller_traffic_down
controller_traffic_up
controller_traffic_total
```

remain cumulative source facts.

Do not globally redefine them as Mbps.

New derived fields belong only to the new read owner.

No Current State schema change is expected.

---

# 47. Deployment / dormant behavior

07-READ has no product route/panel/worker.

Canonical flow:

```text
implementation
→ focused tests
→ Owner + Tech Lead targeted regression
→ Central Lab
→ Linux/current-state PERF
→ accepted candidate
→ publication
→ merge
→ deploy FROM GIT
```

Dormant verification:

```text
service active
Current State unchanged
Visit Lifecycle unchanged
existing Traffic unchanged
no new route
no browser request
no worker
no source write
```

No product activation step for 07-READ itself.

Future TRAFFIC-07 has separate activation.

---

# 48. Rollback

Code-only rollback expected.

No DB/data migration.

Do not delete:

```text
current_state.sqlite3
visits.sqlite3
observations.sqlite3
```

---

# 49. Expected implementation scope

Likely:

```text
app/analytics/current_guest_traffic.py
app/analytics/models.py
app/analytics/__init__.py

app/current_state/read_service.py
```

Optional bounded Visit enrichment:

```text
app/visit_lifecycle/read_service.py
```

Composition may require narrow runtime wiring.

Expected NOT required:

```text
Traffic template
Traffic JS
Admin product route
Current State collector
Current State schema
Visit writer/schema
Observation collector
Omada provider
```

If those become necessary:

```text
STOP / architecture review
```

---

# 50. Mandatory semantic tests

At minimum:

```text
fresh authorized active wireless in exact scope → Online Guest

pending/other/unknown → excluded

stale → no new Online assertion

unavailable → unavailable

same current/baseline pair for all items

scope change → no compatible baseline

no baseline → null rate

baseline not authorized → null rate

valid positive deltas

valid zero delta = 0.0 Mbps

counter regression → reset/null

uptime regression → reset/null

equal uptime → progress_unproven/null if approved

uptime missing + monotonic counters → counters_only

missing one direction → partial

Total only when D/U both valid

Total = backend D+U

gap > max → null

elapsed <=0 → unavailable/fail-safe

new current guest remains Online with no rate

MAC change does not inherit baseline

no AP-throughput allocation

no rxRate/txRate throughput substitution

no activity symmetric-rate substitution
```

---

# 51. Guest / Visit correlation tests

Mandatory:

```text
current authorized guest + compatible open Visit → matched

guest + no open Visit → guest/rate still valid

Visit unavailable → rate preserved, enrichment partial

Visit starts after current snapshot → no retroactive match

conflicting Visit evidence → no arbitrary Visit

closed Visit → not open enrichment

reported completed-session bytes → never current Mbps
```

---

# 52. Quality / integrity tests

Mandatory:

```text
complete-success current cycle required

newer partial/failed cycle does not become Online truth

duplicate cycle identity metadata follows approved conservative rule

unidentified rows → population partial

unknown auth → excluded + quality reason

cross-Site evidence → fail closed

invalid timestamps → fail closed

schema mismatch → fail closed

cursor Site/cycle/scope mismatch → reject

page 2 stays on same current+baseline pair
```

---

# 53. Pagination / capacity tests

If proposed bounds accepted:

```text
default 50
max 200
>200 rejected

10k current source fixture

total_rate_desc deterministic

null rate last

MAC tie-break

canonical cursor

new source cycle does not move old cursor

no duplicate/lost rows across pages
```

---

# 54. Security tests

Fixture:

```text
Site A
Site B
```

Site A read must never use:

```text
Site B current row
Site B baseline row
Site B Visit
```

Same MAC on different Sites remains separate context.

---

# 55. Explicit non-goals

07-READ does NOT implement:

```text
TRAFFIC-07 UI
Online Guest HTTP route
24h/7d guest Traffic
guest historical graph
guest Traffic Share
session Traffic totals
billing
quotas
rate limits/control
reconnect/block
new Omada calls
new collector
new DB/schema/index
AP throughput allocation
SSID Traffic total
WAN/Internet-only Traffic
PHY rate as actual throughput
device identity merge across randomized MACs
```

---

# 56. Stop conditions

STOP if implementation requires:

```text
new Current State writer
Current State schema migration
new Traffic DB
new Omada polling path
browser-side Mbps calculation
AP throughput allocation to clients
HistoricalTrafficReadService as current guest-rate owner
Visit required for Online inclusion
Visit completed-session bytes as current rate
rxRate/txRate as actual Traffic
activity as symmetric D/U rate
per-client arbitrary baseline intervals
cross-scope baseline
new index without review
new scheduler/worker
QueryDeadline/browser timeout/Admin concurrency increase
```

---

# 57. Owner + Tech Lead review questions

## Q1 — necessity

Accept:

```text
TRAFFIC-07-READ = REQUIRED
```

because current per-client counter-delta semantics do not yet have a canonical
read owner?

Architect recommendation: `ACCEPT`.

## Q2 — owner

Accept:

```text
CurrentGuestTrafficReadService
```

as distinct current guest-rate owner?

Architect recommendation: `ACCEPT`.

## Q3 — Online Guest

Accept:

```text
fresh complete Current State
+ wireless
+ active
+ authorized
+ exact guest scope
```

with Visit not required?

Architect recommendation: `ACCEPT`.

## Q4 — snapshot pair

Accept one global:

```text
current complete cycle
+
nearest previous complete compatible cycle
```

for the whole result?

Architect recommendation: `ACCEPT`.

## Q5 — max gap

Accept:

```text
180 seconds
```

v1 maximum baseline gap?

Architect recommendation: `ACCEPT`.

## Q6 — auth continuity

Require baseline row also authorized?

Architect recommendation: `ACCEPT`.

## Q7 — equal uptime

Accept:

```text
equal current/baseline uptime
→ progress_unproven
→ no numeric rate
```

Architect recommendation: `ACCEPT`.

## Q8 — Visit

Accept Visit as optional enrichment only?

Architect recommendation: `ACCEPT`.

## Q9 — API exposure

Accept no product HTTP route in 07-READ and leave
`/traffic/online-guests/current` to TRAFFIC-07?

Architect recommendation: `ACCEPT`.

## Q10 — page bounds

Accept:

```text
default 50
max 200
```

Architect recommendation: `ACCEPT`.

## Q11 — duplicate quality

Accept conservative:

```text
duplicate_identity_count > 0
→ current identified population may remain visible
→ snapshot-pair rate unavailable/quality-untrusted
```

Architect recommendation: `ACCEPT`.

## Q12 — PERF

Accept 10k+10k capacity fixture and:

```text
R200 p95 <=1.0s / max <=1.5s
RV200 p95 <=1.5s / max <=2.0s
```

without new index/schema?

Architect recommendation: `ACCEPT`.

---

# 58. DRAFT acceptance criteria

A future candidate must prove:

```text
1. Current State is authoritative Online Guest source.

2. Online requires fresh complete current evidence.

3. Authorized required; pending/other/unknown excluded.

4. One coherent current/baseline snapshot pair per result.

5. Counter delta owns current client Mbps.

6. PHY/activity does not masquerade as throughput.

7. Valid zero remains 0.0.

8. Missing/reset/gap/auth-transition evidence remains null.

9. Backend Total owns D+U.

10. Online guest can exist with unavailable rate.

11. Visit absence/outage does not remove guest/rate.

12. Completed-session Visit Traffic is not current rate.

13. AP Traffic is not allocated to clients.

14. Current rate is range-insensitive.

15. Cursor pins Site/current/baseline/scope.

16. Site isolation PASS.

17. No query-time Omada.

18. No new source DB/schema/writer.

19. Capacity PERF PASS.

20. Existing Current State/Home/Traffic/Visit regressions = 0.

21. No product route/UI in 07-READ.

22. Future TRAFFIC-07 consumes the foundation without reproducing rate math.
```

Any mandatory failure:

```text
candidate NOT ACCEPTED
publication NOT AUTHORIZED
```

---

# 59. DRAFT state

```text
TASK:
TASK-TRAFFIC-07-READ — Online Guest Current Rate Read Foundation

STATUS:
DRAFT — FOR OWNER + TECH LEAD ARCHITECTURAL REVIEW

ROADMAP DECISION:
TRAFFIC-07-READ = REQUIRED

TASK DEVELOPMENT PARENT:
main@2a101cd27d69866db177254209d4e32529dbf56e
tree ed941c64ed2e612d74db1724da9d6850727070e7

PRODUCTION / RUNTIME REFERENCE:
c5f9dc39bbf399847f147526c9c7ae15769a198c
tree 0831ecf598b5760e8ede2e9e94a25b926480c2dd

PROPOSED SEMANTIC OWNER:
CurrentGuestTrafficReadService

AUTHORITATIVE ONLINE SOURCE:
Current State

RATE SOURCE:
Current State cumulative client counters
over one coherent current/baseline snapshot pair

VISIT:
optional enrichment only

RANGE:
current / range-insensitive

NEW OMADA PATH:
NO

NEW COLLECTOR:
NO

NEW DB / SCHEMA / INDEX:
NO

NEW PRODUCT HTTP ROUTE:
NO

NEW UI:
NO

IMPLEMENTATION AUTHORIZATION:
NOT GRANTED

CODER AUTHORIZATION:
NOT GRANTED

PUBLICATION / MERGE / DEPLOY:
NOT AUTHORIZED
```

Next:

```text
Owner + Tech Lead review

→ corrections if required
→ repository rebind
→ FINAL
→ separate Owner implementation authorization
→ only after accepted 07-READ:
   architecture DRAFT for TRAFFIC-07
```

Implementation MUST NOT begin from this DRAFT.
