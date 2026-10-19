# TASK-TRAFFIC-07-READ — Online Guest Current Rate Read Foundation — DRAFT R2

**Project:** CaptivPortal  
**Area:** Admin Console → Traffic  
**Roadmap item:** `TRAFFIC-07-READ — Current Rate backend foundation`  
**Consumer:** future `TRAFFIC-07 — Online Guests Traffic`  
**Document state:** `DRAFT R2 — PRE-FINAL AMENDED / CONTINUITY EVIDENCE GATE BLOCKED`  
**Prepared:** 2026-09-01  
**Implementation authorization:** `NOT GRANTED`  
**Code / branch / patch / PR / merge / deploy / activation:** `NOT AUTHORIZED`

---

# 1. Executive decision

Canonical roadmap decision remains:

```text
TRAFFIC-07-READ = REQUIRED
```

This review decision is accepted and no longer reopened by R2.

`TRAFFIC-07-READ` is NOT absorbed by:

```text
TRAFFIC-02-READ
HistoricalTrafficReadService
CurrentTrafficReadService
TRAFFIC-05 AP primitives
TRAFFIC-06 AP Share primitives
Visit Lifecycle
```

The platform already persists the raw evidence needed for a current per-client
rate, but no existing semantic owner currently defines:

```text
controller-reported current Online Guest population

one coherent Site-wide current/baseline Current State pair

source progress

same-connection continuity

current-connection cumulative counter delta

near-current interval-average D/U/Total Mbps

truthful zero/null/frozen/reset behavior

bounded global population evaluation + pagination
```

R2 narrows this foundation to exactly:

```text
Current State online-network population
+
Current State current-rate semantics
```

Visit / Visitor Registry enrichment is explicitly deferred to future
`TRAFFIC-07` product composition.

---

# 2. Repository / production baseline

`origin/main` was re-fetched for R2.

```text
main:
2a101cd27d69866db177254209d4e32529dbf56e

tree:
ed941c64ed2e612d74db1724da9d6850727070e7
```

Current main is:

```text
Merge PR #97
Docs: reconcile TRAFFIC-06 AP Traffic Share production state
```

Current production/runtime reference:

```text
production HEAD:
c5f9dc39bbf399847f147526c9c7ae15769a198c

production tree:
0831ecf598b5760e8ede2e9e94a25b926480c2dd
```

Current Traffic surface through TRAFFIC-06 is:

```text
DONE / PRODUCTION ACTIVE
```

for:

```text
TRAFFIC-01
TRAFFIC-02
TRAFFIC-03
TRAFFIC-04
TRAFFIC-05
TRAFFIC-RANGE-01
TRAFFIC-06
```

Before FINAL:

```text
re-fetch origin/main
re-pin SHA/tree
impact-review Current State / Analytics / Admin Traffic drift
```

Before any implementation authorization:

```text
repeat repository rebind
```

---

# 3. R2 review disposition

Accepted without reopening:

```text
Q1  TRAFFIC-07-READ necessity                  ACCEPT
Q2  distinct semantic owner                    ACCEPT
Q4  one global Site-wide snapshot pair         ACCEPT
Q5  180s max gap                               ACCEPT
Q9  no product HTTP route in 07-READ           ACCEPT
Q10 page bounds 50/200                         ACCEPT
```

Accepted with correction:

```text
Q3  Online Guest
→ controller-reported / non-physical qualifier

Q6  baseline authorized
→ plus same SSID

Q7  equal uptime
→ mandatory source-progress invariant

Q12 PERF
→ Visit variants removed; global 10k sort added
```

Rejected/deferred:

```text
Q8  Visit enrichment
→ REJECTED FOR 07-READ / DEFER TO TRAFFIC-07

Q11 duplicate-quality model
→ REJECTED / REWRITTEN to actual Current State partial-cycle behavior
```

Current state:

```text
GENERAL ARCHITECTURE:
ACCEPTED WITH R2 CORRECTIONS

FINAL:
NOT APPROVED YET

IMPLEMENTATION:
NOT AUTHORIZED
```

---

# 4. Foundation purpose

`TRAFFIC-07-READ` answers:

```text
For the latest accepted Current State client snapshot,
which controller-reported active authorized wireless clients
belong to the canonical guest scope,
and what near-current interval-average Download / Upload / Total rate
can be safely derived from the current Omada connection counters
over one accepted Current State snapshot pair?
```

It also answers:

```text
why a numeric rate is unavailable
```

It does NOT claim:

```text
instantaneous physical presence
instantaneous radio connectivity
instantaneous throughput
WAN-only traffic
Internet-only traffic
session totals
billing totals
```

---

# 5. Canonical semantic owner

Accepted owner:

```text
CurrentGuestTrafficReadService
```

The exact file/class spelling may be implementation-detail polished, but the
semantic ownership is frozen.

Ownership boundaries:

```text
CurrentStateReadService
→ persisted Current State facts and exact snapshot read boundary

CurrentGuestTrafficReadService
→ controller-reported Online Guest population
  + source progress
  + connection continuity
  + near-current interval-average client rate

CurrentTrafficReadService
→ current Site/AP Network Throughput

HistoricalTrafficReadService
→ historical Site/AP Network Traffic

VisitLifecycleReadService
→ Visit semantics; NOT part of 07-READ
```

No second current guest-rate owner.

---

# 6. Authoritative source

Authoritative source:

```text
Current State
```

Canonical path:

```text
Omada collection already performed by Current State
→ current_state.sqlite3
→ CurrentStateReadService read-only evidence
→ CurrentGuestTrafficReadService
→ future TRAFFIC-07
```

Forbidden:

```text
query-time Omada
new client Traffic collector
new client Traffic DB
browser-side DB access
browser-side rate math
Observation fallback for current truth
AP throughput allocation
```

---

# 7. Canonical Online Guest wording

Freeze exact product meaning:

```text
Online Guest =
controller-reported active authorized wireless client
in the accepted Current State guest scope
represented by the latest fresh complete Current State cycle.
```

Permanent qualifier:

```text
online_state does not prove instantaneous physical/radio connectivity.
```

Research has already shown that Omada may retain a physically disconnected
client as:

```text
active=true
```

while uptime/counters remain frozen for minutes.

Therefore:

```text
Online Guest
```

means accepted controller-reported current state.

It is NOT:

```text
physical-presence detector
radio-link heartbeat
instant disconnect detector
```

---

# 8. Online Guest eligibility

Selected current client cycle must be:

```text
same authorized canonical Site
kind=client
result=success
complete=true
same current source_scope_hash
fresh
```

Eligible row:

```text
wireless=true
active=true
auth_classification=authorized
SSID in exact accepted guest/client source scope
canonical client MAC present
```

Not sufficient:

```text
guest boolean
open Visit
AuthSession
Registry identity
Observation history
historical AP evidence
```

Excluded:

```text
pending
other
unknown
```

Unknown auth is handled as a population-quality signal, not silently authorized.

---

# 9. Fresh / stale / unavailable population truth

## Fresh complete

May assert controller-reported Online Guests.

If:

```text
known_authorized_count = 0
unknown_auth_count = 0
```

then:

```text
population_count = 0
population_complete = true
items = []
```

This is a proved empty authorized current population.

## Stale

Required:

```text
status = stale
population_count = null
items = []
```

No Online assertions from stale rows.

## Unavailable

Required:

```text
status = unavailable
population_count = null
items = []
```

Never convert unknown population to numeric zero.

---

# 10. Zero-population special case

Fresh complete current cycle with:

```text
authorized_count = 0
```

does NOT require a baseline.

If no unknown-auth ambiguity:

```text
status = ok
population_count = 0
population_complete = true
items = []
```

Even if:

```text
no compatible baseline exists
```

do NOT return `insufficient_data`.

Reason:

```text
no current guest rate evidence is required because no current guest exists.
```

If fresh complete cycle has:

```text
authorized_count = 0
unknown_auth_count > 0
```

then:

```text
known_authorized_count = 0
population_count = 0
population_complete = false
status = partial
items = []
```

because unknown authorization rows prevent proof that the full authorized
population is empty.

---

# 11. Unknown authorization in complete-success cycles

Current State may legitimately store:

```text
unknown auth
```

inside a complete-success cycle.

Required result fields:

```text
known_authorized_count
unknown_auth_count
population_complete
```

Rule:

```text
unknown auth
→ excluded from Online Guest items
→ unknown_auth_count increments
→ population_complete = false
```

Known authorized clients remain visible.

Unknown is not:

```text
authorized
pending
zero population
```

---

# 12. Actual duplicate / unidentified cycle behavior

R1 duplicate-quality interpretation is removed.

Current State worker guarantees:

```text
duplicate relevant canonical MAC
OR
unidentified relevant row

→ complete=false
→ result=partial
```

Therefore a selected complete-success cycle cannot validly contain:

```text
duplicate_identity_count > 0
unidentified_count > 0
```

If persisted selected complete-success metadata contradicts this invariant:

```text
typed integrity failure
FAIL CLOSED
```

---

# 13. Newer partial attempt vs selected previous complete

`CurrentSnapshotMeta` already preserves newer-attempt metadata, but TRAFFIC-07-READ
MUST NOT project an unscoped "latest attempt" blindly.

A newer attempt is relevant to selected current source health only when ALL are true:

```text
same Site

kind = client

same canonical source_scope_hash as selected complete snapshot

strictly newer by deterministic ordering:
(capture_started_at, cycle_id)
```

An incompatible historical scope does NOT degrade the selected current scope.

## Previous complete still fresh + relevant newer partial

Example:

```text
T0 complete-success
T1 duplicate/unidentified partial
T1 same Site/client/scope
T1 > T0 by (capture_started_at, cycle_id)
T0 still fresh
```

Then:

```text
T0 remains selected current snapshot

T1 rows are NOT mixed into T0

source_health_status = degraded

outer status is at least partial
```

## Newer partial in incompatible scope

Example:

```text
T0 selected complete scope=A
T1 partial scope=B
```

Then:

```text
T1 does not degrade scope=A merely by being newer
```

## Selected previous complete stale

If the selected compatible complete snapshot is stale:

```text
status = stale
population_count = null
items = []
```

No Online assertions.

If it is beyond unavailable threshold:

```text
status = unavailable
population_count = null
items = []
```

The read foundation must derive this health inside the same coherent SQLite read
snapshot used for the rest of the result.

# 14. Source health vs rate evidence

Freeze independent product axes:

```text
source_health_status =
healthy | degraded | stale | unavailable

rate_evidence_status =
not_applicable | complete | partial | insufficient_data

population_complete =
true | false
```

These are independent evidence dimensions.

## source_health_status

`healthy`:

```text
selected compatible complete snapshot is fresh

and no strictly newer same-Site/client/same-scope degraded attempt exists
```

`degraded`:

```text
selected compatible complete snapshot remains fresh

but a strictly newer same-Site/client/same-scope partial/failed attempt exists
```

`stale`:

```text
selected complete snapshot exists but is stale
```

`unavailable`:

```text
no safely usable current complete snapshot exists
or current source is beyond unavailable threshold
```

An attempt from another scope does not degrade this result.

## rate_evidence_status

`not_applicable`:

```text
proved current authorized population = 0
```

No baseline is required.

`complete`:

```text
current authorized population is non-empty

and requested current-rate evidence is complete for every returned supported
Online Guest item
```

`partial`:

```text
some usable numeric rate evidence exists

but not all requested current-rate evidence is complete
```

`insufficient_data`:

```text
current authorized population is non-empty

but no usable numeric rate evidence can safely be established
```

## population_complete

`true`:

```text
selected complete current scope contains no unknown authorization rows
```

`false`:

```text
unknown_auth_count > 0
```

or a response class such as stale/unavailable/unsupported cannot prove the full
returned Online Guest population.

The outer status precedence is frozen later in Section 36.

# 15. One global Site-wide snapshot pair

Accepted permanent invariant:

```text
one current cycle
+
one baseline cycle
```

for the entire result.

All clients share:

```text
same Site
same source scope
same current cycle
same baseline cycle
same rate interval
```

Forbidden:

```text
per-client arbitrary baseline cycle
per-page repinning
different elapsed interval per client
```

---

# 16. Canonical snapshot interval

Rate interval endpoints are:

```text
baseline_cycle.capture_started_at
current_cycle.capture_started_at
```

Canonical elapsed:

```text
elapsed_seconds =
current_cycle.capture_started_at
-
baseline_cycle.capture_started_at
```

Do NOT use:

```text
capture_finished_at
```

as rate interval endpoint.

Every selected client row must satisfy integrity:

```text
row.observed_at == selected_cycle.capture_started_at
```

for both:

```text
current row
baseline row
```

Mismatch:

```text
typed integrity failure
FAIL CLOSED
```

---

# 17. Baseline cycle selection

Baseline cycle:

```text
nearest previous
complete-success
client cycle
strictly earlier than current cycle
same Site
same source_scope_hash
```

Fixed v1 max gap:

```text
CURRENT_GUEST_RATE_MAX_GAP_SECONDS = 180
```

This is frozen by review.

It is NOT dynamically increased if:

```text
CURRENT_STATE_CLIENT_INTERVAL_SECONDS
```

changes.

If collector cadence produces:

```text
elapsed > 180s
```

then rate evidence is insufficient.

---

# 18. Per-client baseline compatibility

Numeric rate requires:

```text
same Site
same source_scope_hash
same canonical client MAC
baseline authorized
current authorized
same SSID
accepted connection continuity
0 < elapsed_seconds <= 180
```

AP equality is explicitly NOT required.

Therefore:

```text
same MAC
same SSID
AP changed
```

does NOT by itself invalidate rate.

AP roaming can occur within one connection/context.

---

# 19. SSID transition

Same MAC but:

```text
baseline.ssid != current.ssid
```

means:

```text
ssid_transition
```

Required:

```text
Download = null
Upload = null
Total = null

connection_continuity_status = unproven
```

Do not bridge counters across SSID transition in v1.

---

# 20. Counter source semantics

Freeze research-backed meaning:

```text
trafficDown / controller_traffic_down
=
cumulative Download bytes of the current Omada connection

trafficUp / controller_traffic_up
=
cumulative Upload bytes of the current Omada connection

uptime / controller_uptime
=
duration/progress evidence for the current Omada connection
```

When a connection is finalized/offline, corresponding finalized evidence maps
conceptually to:

```text
past-connection.download
past-connection.upload
past-connection.duration
```

New connection:

```text
starts new connection counters
```

Therefore counter delta is valid only after same-connection continuity is
accepted.

---

# 21. Metric is interval-average, not instantaneous

Canonical wording:

```text
current guest rate =
near-current interval-average rate
over one accepted Current State snapshot pair.
```

It is NOT:

```text
instantaneous throughput
instantaneous radio rate
real-time packet meter
```

Formula remains:

```text
delta_bytes * 8
/
elapsed_seconds
/
1_000_000
```

Unit:

```text
Mbps
```

---

# 22. Frozen metric identities

Freeze semantics now:

```text
metric_version =
network_traffic_online_guest_current_rate.v1

population_method =
fresh_complete_current_state_authorized_guest_scope.v1

rate_method =
current_connection_counter_delta_interval_average.v1

baseline_method =
nearest_previous_complete_same_site_scope_cycle.v1

unit =
Mbps
```

`continuity_method` cannot be frozen yet.

It MUST be fixed before FINAL after the bounded continuity evidence check defined
later in this R2.

No FINAL may retain an unresolved continuity method.

---

# 23. Source progress model

Permanent per-item classification:

```text
source_progress_status =
advanced
frozen
unproven
```

`advanced`:

```text
evidence proves the controller's current-connection state advanced between the
accepted baseline/current snapshots
```

`frozen`:

```text
both uptime values exist
and current_uptime == baseline_uptime
```

This is not numeric zero traffic.

`unproven`:

```text
available evidence cannot prove source advancement
```

Important v1 rule:

```text
counter growth may support "advanced" evidence,

but counter growth alone MUST NOT authorize numeric rate when either uptime is
missing because same-connection continuity remains unproven.
```

# 24. Connection continuity model

Permanent per-item classification:

```text
connection_continuity_status =
proven
reset
unproven
```

Numeric rate requires ALL:

```text
source_progress_status = advanced

connection_continuity_status = proven

baseline uptime present

current uptime present

same Site

same source_scope_hash

same canonical client MAC

baseline authorized

current authorized

same SSID

0 < elapsed_seconds <= 180

direction counters valid/monotonic
```

Therefore:

```text
continuity_basis = counters_only
```

MUST NOT authorize numeric rate in v1.

Future v2 may revisit missing-uptime continuity only after stronger connection
identity/evidence is separately approved.

# 25. Uptime rules

Numeric v1 rate requires uptime in BOTH snapshots.

## Missing uptime

If either:

```text
baseline controller_uptime is null
OR
current controller_uptime is null
```

then:

```text
connection_continuity_status = unproven

download_mbps = null
upload_mbps = null
total_mbps = null
```

Counter growth MAY classify:

```text
source_progress_status = advanced
```

but does NOT prove same connection.

If counters do not prove advancement:

```text
source_progress_status = unproven
```

No `counters_only` numeric rate.

## Uptime regression

If:

```text
current_uptime < baseline_uptime
```

then:

```text
connection_continuity_status = reset

D/U/Total = null

reason = connection_reset
```

## Equal uptime

If:

```text
current_uptime == baseline_uptime
```

then:

```text
source_progress_status = frozen

connection_continuity_status = unproven

D/U/Total = null
```

Permanent:

```text
equal uptime + unchanged counters != 0 Mbps
```

If counters appear to grow while uptime is equal, treat the evidence as
contradictory/untrusted for numeric rate; do not "prefer" counters over the frozen
uptime signal.

## Uptime increased

If:

```text
current_uptime > baseline_uptime
```

then source advancement is a candidate.

Continue with:

```text
same-connection continuity method

SSID continuity

counter validation

elapsed/gap validation
```

Only after all pass:

```text
source_progress_status = advanced

connection_continuity_status = proven
```

# 26. Missing uptime — v1 hard boundary

R2 pre-FINAL amendment freezes:

```text
numeric rate requires controller_uptime in BOTH snapshots
```

If either uptime is missing:

```text
connection_continuity_status = unproven

D/U/Total = null
```

Possible source-progress classification:

```text
at least one monotonic cumulative counter increases
→ source_progress_status MAY be advanced

all available counters unchanged
→ source_progress_status = unproven
```

But in both cases:

```text
rate remains null
```

because counter growth alone cannot prove the baseline/current snapshots belong to
the same Omada connection.

`continuity_basis=counters_only` may be retained only as diagnostic provenance
for why source progress was suspected.

It is not an accepted numeric-rate continuity basis in v1.

# 27. True zero contract

True zero is allowed only when:

```text
source_progress_status = advanced
connection_continuity_status = proven
direction counter exists in both snapshots
direction counter is monotonic
direction delta = 0
```

Then:

```text
direction_mbps = 0.0
```

Example accepted:

```text
uptime increased
same connection continuity proven
counters unchanged
→ true 0.0 Mbps
```

Frozen/unproven source:

```text
null
```

never numeric zero.

---

# 28. Same-connection proof requirement

Current client counters are cumulative bytes of the CURRENT Omada connection.

Same MAC is insufficient.

v1 numeric rate requires uptime in both snapshots and a proven connection
continuity method.

Two estimator families MUST be evaluated by the pre-FINAL evidence gate.

## A. Point estimator

```text
point_connection_start =
cycle.capture_started_at - controller_uptime
```

## B. Capture-window estimator

Because the client row may be observed anywhere while the cycle is being polled:

```text
connection_start_window =
[
  cycle.capture_started_at - controller_uptime,
  cycle.capture_finished_at - controller_uptime
]
```

Any controller uptime quantization/rounding allowance may be added only if the
bounded evidence proves it.

No convenience tolerance.

Safety priority:

```text
false-positive reconnect → same connection
= FORBIDDEN

conservative false-negative same connection → unproven
= ACCEPTABLE
```

FINAL must freeze:

```text
continuity_method = <versioned identifier>

exact tolerance/quantization rule = <evidence-backed rule>
```

# 29. Continuity evidence gate — attempted / currently BLOCKED

The pre-FINAL evidence gate was attempted against the currently retrievable
project evidence.

Available accepted research proves:

```text
trafficDown/trafficUp are cumulative current-connection bytes

uptime finalizes to past-connection.duration

new connection starts new counters

Controller client snapshots may repeat/freeze

active=true may remain after physical disconnect with frozen counters

disconnect/reconnect reset behavior is verified at the research conclusion level
```

However the currently retrievable evidence does NOT contain the required raw
scenario-pair dataset with:

```text
capture_started_at
capture_finished_at
baseline/current uptime
baseline/current trafficDown
baseline/current trafficUp
known scenario truth
```

at the review-required sample sizes.

Therefore no exact tolerance can be derived safely.

Current gate result:

```text
CONTINUITY EVIDENCE GATE = BLOCKED / INSUFFICIENT RAW PAIR EVIDENCE

FINAL = NOT PERMITTED
```

This is not a rejection of the architecture.

It is the mandatory STOP path required by the review.

## Evidence still required

Minimum:

```text
stable same connection      >= 10 pairs
idle same connection        >= 10 pairs
active transfer             >= 10 pairs
frozen/repeated state       several consecutive pairs
disconnect/reconnect        >= 3 controlled transitions
```

Record per pair:

```text
baseline capture_started_at
baseline capture_finished_at

current capture_started_at
current capture_finished_at

MAC
SSID
AP

baseline/current uptime
baseline/current trafficDown
baseline/current trafficUp

capture-start elapsed
uptime delta

point connection-start estimates

capture-window connection-start estimates

known scenario truth
```

Acceptance priority:

```text
zero false-positive reconnect classifications
```

False-negative same-connection classifications are acceptable.

Only after this evidence may FINAL freeze the continuity method.

# 30. Continuity estimator candidates

## Point candidate

```text
point_start =
cycle.capture_started_at - controller_uptime
```

## Window candidate

```text
window_start =
cycle.capture_started_at - controller_uptime

window_end =
cycle.capture_finished_at - controller_uptime
```

The window candidate explicitly accounts for collection duration.

The eventual FINAL should prefer the window method if it safely separates
reconnect from same-connection evidence.

No tolerance or uptime-quantization value is frozen in this DRAFT because the raw
pair evidence gate is blocked.

Row integrity remains:

```text
row.observed_at == cycle.capture_started_at
```

Rate elapsed remains:

```text
current.capture_started_at - baseline.capture_started_at
```

`capture_finished_at` is used only by the continuity estimator window, not the
rate denominator.

# 31. Counter validation after continuity

For each direction:

```text
baseline counter exists
current counter exists
counter is non-negative
current >= baseline
```

Then:

```text
delta = current - baseline
```

If:

```text
current < baseline
```

required:

```text
counter_reset
direction rate = null
```

If counter reset also contradicts a supposedly proven same connection, product
must not repair it by wrap/clamping.

No negative rate.

No unsigned-wrap assumption.

---

# 32. Per-direction semantics

A direction may be independently unavailable.

Example:

```text
Download valid
Upload missing
```

Then:

```text
download_mbps = numeric
upload_mbps = null
total_mbps = null
```

Total is numeric only when both D/U are numeric.

No missing direction becomes zero.

---

# 33. Download / Upload / Total

If accepted:

```text
Δt =
current_cycle.capture_started_at
-
baseline_cycle.capture_started_at
```

Download:

```text
download_mbps =
(current_down - baseline_down) * 8
/
Δt
/
1_000_000
```

Upload:

```text
upload_mbps =
(current_up - baseline_up) * 8
/
Δt
/
1_000_000
```

Total:

```text
total_mbps =
download_mbps + upload_mbps
```

Backend Total is canonical.

Browser never recomputes Total.

---

# 34. Per-item provenance

Required item provenance:

```text
source_progress_status

connection_continuity_status

continuity_basis

download_reason

upload_reason

total_reason

rate_status
```

`continuity_basis` v1 should distinguish at least:

```text
uptime_window
counters_only_diagnostic
none
```

Only:

```text
uptime_window
```

(or the exact FINAL evidence-backed uptime continuity method) may authorize a
numeric rate.

`counters_only_diagnostic` never authorizes numeric rate in v1.

Recommended `rate_status`:

```text
valid
partial
unavailable
```

All numeric D/U/Total:

```text
finite
>= 0
```

Forbidden:

```text
NaN
Infinity
negative
clamping malformed negative values to 0
```

# 35. Reason family

R2 minimum candidate reason family:

```text
valid

no_baseline

no_authorized_baseline

ssid_transition

baseline_gap_too_large

invalid_elapsed

counter_missing

counter_reset

connection_reset

connection_continuity_unproven

source_frozen

source_progress_unproven

source_quality_untrusted
```

Exact serialization spelling may be polished before FINAL.

Semantics must not be weakened.

---

# 36. Safe result statuses and exact precedence

Safe outer status family:

```text
ok
partial
insufficient_data
stale
unavailable
unsupported_population
```

Independent axes:

```text
source_health_status =
healthy | degraded | stale | unavailable

rate_evidence_status =
not_applicable | complete | partial | insufficient_data

population_complete =
true | false
```

Exact outer precedence:

```text
1. integrity contradiction
   → typed exception / fail closed

2. unsupported scoped population
   → unsupported_population

3. source unavailable
   → unavailable

4. source stale
   → stale

5. fresh but:
      source degraded
      OR population_complete=false
      OR rate_evidence_status=partial
   → partial

6. fresh + healthy + complete population
   + rate_evidence_status=insufficient_data
   → insufficient_data

7. otherwise
   → ok
```

Zero population:

```text
rate_evidence_status = not_applicable
```

and can yield outer:

```text
ok
```

when source is fresh/healthy and population is complete.

If multiple dimensions are degraded, dedicated fields retain their exact reason
even when the outer status is only `partial`.

# 37. Typed integrity failure boundary

The following are NOT normal `status=unavailable`:

```text
schema mismatch
storage corruption
cross-Site evidence
impossible cycle identity
source-scope contradiction
invalid persisted invariant
selected complete-success cycle with impossible duplicate/unidentified metadata
row observed_at != selected cycle capture_started_at
impossible/corrupt cursor binding
```

Required:

```text
typed integrity failure
FAIL CLOSED
```

Preserve the same distinction established in TRAFFIC-06:

```text
safe unavailable evidence
!=
corrupt evidence
```

No fabricated result DTO.

---

# 38. Population projection

For a fresh selected complete scoped current cycle expose:

```text
scoped_client_row_count

known_authorized_count

unknown_auth_count

population_count

population_complete

supported_max_population
```

Definitions:

```text
scoped_client_row_count
=
all stored current client rows in the selected complete scoped cycle

population_count
=
known controller-reported authorized Online Guests
```

Integrity requirement:

```text
selected_cycle.items_stored
==
COUNT(current_client_state WHERE cycle_id = selected_cycle)
```

for the selected complete cycle.

Mismatch:

```text
typed integrity failure
```

Unknown auth:

```text
excluded from Online Guest items

unknown_auth_count > 0
→ population_complete=false
```

Stale/unavailable:

```text
population_count=null
items=[]
```

# 39. Supported population bound

Freeze v1 support basis:

```text
supported_max_population = 10_000
```

The bound applies to:

```text
selected complete current scoped client row count
```

NOT merely:

```text
known_authorized_count
```

Reason:

```text
PERF/work shape must bound the Current State source population that must be read,
classified, rate-evaluated and globally sorted.
```

If:

```text
scoped_client_row_count > 10_000
```

required:

```text
status = unsupported_population

returned_count = 0

items = []
```

No:

```text
first 10k
top 200
authorized-only shortcut that hides a 50k scoped source workload
silent truncation
```

If future v2 wants to support Current State's configurable 50k source cap:

```text
mandatory 50k+50k PERF
+
architecture review
```

# 40. Baseline absence behavior

If current population is non-empty and no compatible baseline cycle exists:

```text
status = insufficient_data
Online Guest population remains proven
all rate fields = null
reason = no_baseline
```

If current population is zero:

```text
status = ok
population_count = 0
items = []
```

Baseline is unnecessary.

---

# 41. Global sorting semantics

Accepted page bounds:

```text
default limit = 50
max limit = 200
```

Public default sort semantic:

```text
total_rate_desc
```

Because every numeric rate in one result uses the same accepted
`elapsed_seconds`:

```text
total_mbps DESC
```

is exactly equivalent to:

```text
total_delta_bytes DESC
```

Freeze internal deterministic ordering:

## Numeric Total

```text
sort_class = numeric

total_delta_bytes DESC

client_mac ASC
```

## Null Total

```text
sort_class = null

NULLS LAST

client_mac ASC
```

This avoids floating-point cursor precision.

Global sort still requires evaluating rate semantics for the eligible population
of the pinned current/baseline pair before top-page selection.

Do NOT claim only 50/200 rows need rate calculation.

# 42. Cursor contract

Cursor MUST pin:

```text
version

endpoint/kind

Site

current cycle

baseline cycle

source_scope_hash

sort

original evaluated_at

sort_class

total_delta_bytes | null

client_mac
```

The full cursor chain represents one semantic instant.

Do not bind the canonical cursor to floating `total_mbps`.

New source cycles do not move an existing cursor chain.

If retention removes a pinned current or baseline cycle:

```text
cursor_expired
```

Never repin silently.

Cross-Site/scope/kind/cycle mismatch:

```text
400 / explicit validation failure
```

# 43. One coherent SQLite read snapshot per result

One `CurrentGuestTrafficReadService` result MUST obtain ALL Current State evidence
inside ONE read-only SQLite transaction / coherent read snapshot:

```text
selected current complete cycle

scope-relevant newer-attempt health

selected scoped row count

authorized / unknown-auth counts

selected baseline cycle

current rows

matching baseline rows
```

Do NOT compose one result from multiple independently opened Current State read
transactions.

Execution order inside the read snapshot:

```text
authorize canonical Site

resolve canonical current scope

select current complete cycle

resolve same-Site/client/same-scope newer attempt health

validate selected cycle scoped row count

evaluate freshness

classify current scoped population

if proved authorized population=0:
  return without baseline

enforce scoped-client-row <=10k

select nearest previous complete same-Site/same-scope baseline

validate pair interval

read current + matching baseline rows

evaluate source progress / continuity / counters

global integer-key sort

page/cursor
```

Cursor page requests are separate transactions, but MUST use the pinned:

```text
Site
current cycle
baseline cycle
evaluated_at
scope
```

If pinned cycle disappeared:

```text
cursor_expired
```

# 44. CurrentStateReadService extension

Current State remains schema/persistence owner.

07-READ may add a narrow read-only evidence operation that opens ONE coherent
SQLite read transaction for a result.

Conceptually it must provide, under that transaction:

```text
selected complete current cycle

scope-relevant newer attempt metadata

selected cycle row-count integrity evidence

known authorized / unknown auth classification evidence

nearest previous complete compatible baseline

current rows

matching baseline rows
```

Cursor reads use a new transaction but validate and reuse pinned identifiers.

Permanent:

```text
read-only/query-only

same Site validation

same source scope validation

no writer

no collector change

no schema migration

no new index by default
```

# 45. Visit / Registry explicitly OUT OF 07-READ

Delete/defer all R1 proposals for:

```text
Visit batch helper

visit_context_status

visit_id

device_id

visit_started_at

Visit-specific result degradation

Visit PERF variants

Visit correlation tests
```

Reason:

```text
07-READ owns Current State online-network population
+
current-rate semantics only.
```

Future:

```text
TRAFFIC-07
```

may compose optional:

```text
Visit Lifecycle
Visitor Registry
```

enrichment after the rate foundation is stable.

Valid Visit storage already owns its own one-open-Visit-per-Site+MAC invariant;
07-READ does not invent `conflict` as a normal Visit state.

---

# 46. AuthSession OUT OF 07-READ

AuthSession is not a rate/online source.

No dependency on process-local:

```text
AuthSessionManager
```

Current State is authoritative persisted controller-reported current source.

---

# 47. Observation boundary

Observation is not the v1 current guest-rate fallback.

Forbidden:

```text
Current State unavailable
→ use Observation to manufacture current rate
```

Observation remains historical/validation context only.

---

# 48. AP Traffic boundary

No identity/conservation claim:

```text
sum Online Guest current rates
==
Current Network Throughput
```

is allowed.

No AP throughput allocation.

No AP Traffic Share allocation.

AP roam alone does not invalidate client rate if all required client continuity
evidence remains compatible.

---

# 49. Range model

07-READ is:

```text
current / range-insensitive
```

No:

```text
24h
7d
TrafficHistoricalRequestBroker
historical admission guard
```

in this foundation.

Short Current State history is used only to select one prior baseline cycle.

---

# 50. API surface

07-READ creates:

```text
NO new user-visible HTTP route
NO browser API
NO Traffic panel
```

Future TRAFFIC-07 may own:

```text
GET /admin/api/v1/sites/<site_id>/traffic/online-guests/current
```

That route is not authorized by this DRAFT.

Do not add the product to:

```text
/traffic/history?products=...
```

---

# 51. Feature flag

No product exposure in 07-READ.

Therefore:

```text
NO new feature flag required in 07-READ
```

Future TRAFFIC-07 may introduce a default-false product flag.

---

# 52. UI / coordinator

07-READ:

```text
NO UI
NO browser orchestration
```

Future TRAFFIC-07 is expected to use:

```text
CaptivPortalTrafficCoordinator
```

as a current/range-insensitive panel.

It must not create a second scheduler.

Exact refresh policy belongs to TRAFFIC-07.

---

# 53. Privacy / Site isolation

Strict:

```text
authorized canonical Site
```

is the data-isolation boundary.

Never read/join:

```text
other Site current rows
other Site baseline rows
```

Same MAC on different Sites:

```text
different current-rate context
```

No cross-Site telemetry cardinality.

Default future Traffic DTO should omit IP unless separately justified by
TRAFFIC-07 product review.

---

# 54. Work-shape contract

Global work is bounded by:

```text
one current cycle
one baseline cycle
supported population <= 10,000
```

Potentially all eligible rows in those two cycles are evaluated for global sort.

Allowed:

```text
set-based current/baseline join
bounded in-memory deterministic rate projection/sort
```

subject to PERF.

Forbidden:

```text
scan many cycles
per-client previous-cycle lookup
N+1 database connections
full Current State retention scan
```

---

# 55. Index / schema policy

R2 does NOT authorize:

```text
new Current State index
new schema
new migration
new DB
```

Implementation first proves work shape against existing:

```text
cycle/auth/client
primary/cycle+MAC
```

indexes or equivalent current access paths.

If mandatory PERF cannot pass:

```text
STOP
→ EXPLAIN/profile evidence
→ Owner + Tech Lead architecture review
```

No silent index addition.

---

# 56. PERF foundation

Mandatory immutable candidate fixture:

```text
10,000 selected complete scoped current client rows

10,000 baseline rows
```

The 10,000 current rows are the full selected scoped source population, not merely
10,000 authorized rows.

Fixture includes:

```text
authorized
unknown auth
pending
valid positive rate
valid zero
missing baseline
frozen
connection reset
counter reset
SSID transition
AP roam
```

No Visit fixture.

The fixture must satisfy selected cycle row-count integrity:

```text
items_stored == COUNT(rows for selected cycle)
```

# 57. PERF variants

Required candidate variants:

```text
R50
limit=50

R200
limit=200

RG10K
10,000 scoped current rows
10,000 baseline rows
global total_rate_desc
return first page

RZERO
fresh complete authorized_count=0
no baseline

RNOBASE
non-empty authorized current population
no compatible baseline

RFROZEN
equal-uptime/frozen semantic fixture

RRESET
disconnect/reconnect/reset semantic fixture
```

Timed:

```text
R50
R200
RG10K
```

At least:

```text
10 measured runs each
```

Semantic variants must be deterministic.

The global 10k variant explicitly proves the full source/filter/rate/sort work
shape.

# 58. PERF hard proposal

For:

```text
10k current scoped rows
+
10k baseline rows
+
global total_rate_desc
```

hard candidate:

```text
R200 / RG10K:

p95 <= 1.0s
max <= 1.5s

>=10 measured runs
```

Also prove:

```text
source writes = 0

deterministic semantic result

exactly one current/baseline pair

one coherent SQLite read snapshot per result

no multi-cycle scan

existing indexes used or equivalent

no new index

unexpected 5xx = 0
```

Continuity semantic fixtures do not need fabricated performance numbers; their
result classifications must be exact.

# 59. Query-plan evidence

Must prove:

```text
current complete cycle lookup bounded

scope-relevant newer-attempt lookup bounded by:
  Site
  kind=client
  source_scope_hash
  deterministic newer ordering

selected cycle row-count integrity query bounded

baseline cycle lookup bounded

exactly one baseline cycle

current rows restricted to selected current cycle

baseline rows restricted to selected baseline cycle

global 10k classification/rate/sort bounded

existing cycle/auth/PK indexes used or equivalent

no multi-cycle history scan

no retention-window scan

no source writes
```

One result's reads occur inside one SQLite read transaction.

No new index is authorized by this DRAFT R2.

# 60. Backward compatibility

Must not change existing semantics of:

```text
Current State Home Live

Current Network Throughput

Historical Traffic

Traffic by AP

AP Traffic Share

Home Activity

Visit Lifecycle
```

Existing:

```text
controller_traffic_down
controller_traffic_up
controller_traffic_total
```

remain cumulative source facts.

Do not globally redefine them as Mbps.

Derived rate belongs only to `CurrentGuestTrafficReadService`.

---

# 61. Deployment / dormant model

07-READ has:

```text
no route
no UI
no worker
no feature activation
```

Canonical acceptance/deploy:

```text
implementation
→ focused TASK tests
→ Owner + Tech Lead targeted regression
→ Central Lab
→ Current State PERF
→ accepted candidate
→ Git publication
→ merge
→ deploy FROM GIT
→ dormant production verification
```

Production dormant proof:

```text
service active
Current State collection unchanged
existing Traffic unchanged
no browser request
no new route
no new worker
no source write
```

Future TRAFFIC-07 activation is separate.

---

# 62. Rollback

Expected code-only rollback.

No DB migration.

Do not delete:

```text
current_state.sqlite3
observations.sqlite3
visits.sqlite3
```

---

# 63. Expected implementation scope

Likely:

```text
app/analytics/current_guest_traffic.py
app/analytics/models.py
app/analytics/__init__.py

app/current_state/read_service.py
```

Potential narrow runtime composition wiring.

Expected unchanged:

```text
Current State collector
Current State schema/repository writer
Observation collector/schema
Visit Lifecycle
Omada provider
Traffic template
Traffic JS
Admin Traffic routes
```

If expected-unchanged areas become necessary:

```text
STOP / architecture review
```

---

# 64. Mandatory semantic tests — population

```text
fresh complete + authorized rows
→ controller-reported Online Guest items

fresh complete + 0 authorized + no baseline
→ ok / population_count=0 / []

fresh complete + unknown auth
→ known authorized returned
→ unknown_auth_count exposed
→ population_complete=false
→ status partial

pending/other/unknown
→ excluded

stale complete
→ stale / population_count=null / []

unavailable
→ unavailable / population_count=null / []

population >10,000
→ unsupported_population / no truncation
```

---

# 65. Mandatory tests — newer partial attempt

```text
newer duplicate/unidentified partial
+
previous complete still fresh

→ previous complete remains selected
→ no partial-cycle rows mixed
→ source_health_status=degraded
→ overall status partial
```

```text
newer partial
+
previous complete stale

→ stale
→ population_count=null
→ items=[]
→ no Online assertion
```

Selected complete cycle containing duplicate/unidentified metadata contradiction:

```text
typed integrity failure
```

---

# 66. Mandatory tests — source progress

```text
equal uptime + unchanged counters
→ source_progress_status=frozen
→ rates=null
→ NOT 0 Mbps
```

```text
uptime missing + unchanged available counters
→ source_progress_status=unproven
→ rates=null
```

```text
uptime progressed
+
same connection continuity proven
+
unchanged counters
→ source_progress_status=advanced
→ true 0.0 Mbps
```

```text
uptime missing
+
at least one counter increased
→ source_progress_status MAY be advanced
→ connection_continuity_status=unproven
→ rates=null

numeric counters-only rate is forbidden in v1.

---

# 67. Mandatory tests — continuity

```text
current uptime < baseline uptime
→ connection_reset
→ rates null
```

```text
connection_start_estimate incompatible
→ connection_continuity_status != proven
→ no cross-connection delta
```

```text
same MAC + same SSID + AP changed
→ AP change alone does not invalidate rate
```

```text
same MAC + SSID changed
→ ssid_transition
→ rates null
```

```text
MAC changed
→ no baseline inheritance
```

Final tests must use the exact continuity tolerance/method frozen after the
bounded evidence check.

---

# 68. Mandatory tests — counters

```text
positive D/U deltas
→ correct Mbps

valid zero under advanced+proven continuity
→ numeric 0.0

counter regression
→ counter_reset/null

one direction missing
→ partial
→ Total null

both directions valid
→ Total = backend D + U

all numeric values
→ finite and >=0

NaN/Inf/negative
→ rejected, not clamped
```

---

# 69. Mandatory tests — interval integrity

```text
elapsed =
current.capture_started_at - baseline.capture_started_at
```

Prove:

```text
capture_finished_at not used
```

Row invariant:

```text
current row observed_at == current cycle capture_started_at

baseline row observed_at == baseline cycle capture_started_at
```

Mismatch:

```text
typed integrity failure
```

Gap:

```text
0 < elapsed <=180
```

Else rate unavailable.

---

# 70. Mandatory tests — cursor

```text
cursor pins:
  evaluated_at
  Site
  current cycle
  baseline cycle
  scope
  sort
  sort_class
  total_delta_bytes|null
  MAC

no floating Mbps cursor key

new source cycle does not shift old cursor chain

pinned cycle removed
→ cursor_expired

never silently repin

cross-Site/scope cursor
→ reject
```

# 71. Mandatory tests — sorting/capacity

```text
default limit=50
max=200
>200 rejected

public sort=total_rate_desc

numeric internal ordering:
  total_delta_bytes DESC
  MAC ASC

null Total:
  NULLS LAST
  MAC ASC

global eligible population evaluated before top page

10k scoped current rows supported

>10k scoped current rows
→ unsupported_population

authorized subset <=10k but scoped rows >10k
→ still unsupported_population

items_stored == selected cycle row count

no duplicate/lost rows across pages
```

# 72. Mandatory security tests

Site A request must never read/use:

```text
Site B current cycle
Site B baseline cycle
Site B client row
```

Same MAC at A/B remains separate.

No cross-Site population count/telemetry.

---

# 73. Continuity evidence gate before FINAL — BLOCKING

The architecture review requires the bounded continuity evidence gate before
FINAL.

The gate was attempted against currently retrievable accepted project evidence.

Result:

```text
BLOCKED

reason:
required raw scenario pairs are not available in the currently retrievable
research package/context
```

Available research is enough to freeze:

```text
current-connection cumulative counter semantics

uptime reset behavior at conclusion level

frozen/repeated snapshot risk

active=true non-physical qualifier

no counters-only numeric rate in v1
```

It is NOT enough to freeze:

```text
connection_start window compatibility rule

uptime quantization allowance

exact tolerance

zero-false-positive reconnect classifier
```

Therefore:

```text
FINAL = NOT ALLOWED YET
```

Required raw evidence collection remains:

```text
stable >=10 pairs

idle >=10 pairs

active >=10 pairs

frozen several consecutive pairs

disconnect/reconnect >=3 controlled transitions
```

For every pair record:

```text
baseline/current capture_started_at
baseline/current capture_finished_at
MAC
SSID
AP
baseline/current uptime
baseline/current trafficDown
baseline/current trafficUp
capture-start elapsed
uptime delta
point connection-start estimates
capture-window connection-start estimates
known scenario truth
```

Safety acceptance:

```text
false-positive reconnect → same connection = 0 allowed

false-negative same connection → continuity_unproven = acceptable
```

After evidence, freeze exact:

```text
continuity_method
tolerance/quantization
```

or STOP current-rate v1 feasibility if safe separation is impossible.

# 74. Explicit non-goals

07-READ does NOT implement:

```text
TRAFFIC-07 UI

Online Guests HTTP route

Visit enrichment

Registry enrichment

24h/7d guest history

historical guest rate chart

Guest Session Traffic

billing

quota/control

rate limiting

reconnect/block

new collector

new Omada call

new DB/schema/index

AP-throughput allocation

SSID traffic total

instantaneous physical-presence detection

PHY/link rate display as actual traffic

multi-MAC device aggregation
```

---

# 75. Stop conditions

STOP if implementation requires:

```text
invented continuity tolerance

no same-connection proof

frozen evidence materialized as 0 Mbps

stale rows asserted Online

unknown population mapped to zero

new Current State writer

Current State schema migration

new index without architecture review

new Traffic DB

query-time Omada

Observation fallback as Online truth

AP throughput allocation

rxRate/txRate as actual throughput

activity as symmetric actual throughput

per-client baseline cycles

multi-cycle history scan

Visit composition inside 07-READ

new scheduler/worker

browser-side rate math
```

---

# 76. R2 Owner + Tech Lead review decisions

## Q1 — necessity

```text
TRAFFIC-07-READ = REQUIRED
```

Status:

```text
ACCEPTED
```

## Q2 — semantic owner

```text
CurrentGuestTrafficReadService
```

Status:

```text
ACCEPTED
```

## Q3 — Online Guest

```text
controller-reported active authorized wireless client
in latest fresh complete Current State guest scope
```

with qualifier:

```text
not instantaneous physical/radio proof
```

Status:

```text
ACCEPTED WITH CORRECTION / INCORPORATED
```

## Q4 — global snapshot pair

```text
one current + one previous compatible complete cycle
```

Status:

```text
ACCEPTED
```

## Q5 — max gap

```text
180s fixed v1
```

Status:

```text
ACCEPTED / FROZEN
```

## Q6 — baseline compatibility

```text
same Site
same scope
same MAC
authorized both
same SSID
continuity proven
0<elapsed<=180s
```

AP equality not required.

Status:

```text
ACCEPTED WITH SAME-SSID CORRECTION
```

## Q7 — equal uptime

```text
equal uptime
→ frozen
→ null rate
```

Status:

```text
ACCEPTED / PROMOTED TO PERMANENT SOURCE-PROGRESS RULE
```

## Q8 — Visit

```text
OUT OF 07-READ
DEFER TO TRAFFIC-07
```

Status:

```text
REJECTED FOR THIS TASK
```

## Q9 — HTTP product route

```text
none in 07-READ
```

Status:

```text
ACCEPTED
```

## Q10 — page bounds

```text
default 50
max 200
```

Status:

```text
ACCEPTED
```

## Q11 — duplicate/unidentified

Old R1 wording:

```text
REJECTED
```

R2:

```text
duplicate/unidentified relevant rows
→ partial cycle
→ cannot become selected complete truth

previous complete may remain selected
subject to freshness
```

Status:

```text
REWRITTEN / ALIGNED TO CURRENT STATE
```

## Q12 — PERF

```text
10k current + 10k baseline
R200 / global sort
p95 <=1.0s
max <=1.5s
>=10 runs
```

Visit variants removed.

Status:

```text
ACCEPTED WITH R2 CORRECTIONS
```

---

# 77. Remaining blocking item before FINAL

The architecture amendments are complete.

The only blocking requirement is empirical:

```text
CONTINUITY EVIDENCE GATE
```

Current state:

```text
architecture amendments = INCORPORATED

raw continuity pair evidence = INSUFFICIENT / NOT RETRIEVABLE HERE

continuity method = NOT FROZEN

tolerance/quantization = NOT FROZEN

FINAL = BLOCKED
```

No safe value will be invented.

When the required raw evidence exists, FINAL may be prepared directly without an
R3 redesign.

# 78. R2 acceptance target

A future FINAL candidate must prove:

```text
1. Online Guest is controller-reported, not physical-instantaneous.

2. Fresh complete Current State is required for Online assertion.

3. Stale/unavailable population is null, never zero.

4. Fresh proved zero population can return ok/0/[] without baseline.

5. Unknown auth is excluded and makes population incomplete.

6. Duplicate/unidentified relevant rows produce partial cycles and do not become
   selected complete truth.

7. Newer partial attempt can degrade source health while previous fresh complete
   remains selected.

8. One Site-wide current/baseline pair is used.

9. Rate interval is capture_started_at-to-capture_started_at.

10. Row observed_at must agree with its cycle start.

11. Same Site/scope/MAC/authorized/SSID required.

12. AP roam alone does not invalidate rate.

13. 180s is fixed v1 max gap.

14. Counter semantics are current-connection cumulative bytes.

15. Metric is near-current interval-average, not instantaneous.

16. source_progress_status is explicit.

17. connection_continuity_status is explicit.

18. Frozen/unproven source never becomes 0 Mbps.

19. True zero requires proven source advancement and continuity.

20. Equal uptime is frozen/null.

21. Missing uptime + unchanged counters is unproven/null.

22. Missing uptime + counter growth may prove progress only under final continuity
    method.

23. Connection reset cannot be differenced.

24. Numeric D/U/Total are finite and >=0.

25. Backend Total is canonical.

26. Global total_rate_desc evaluates the bounded eligible population before page
    selection.

27. Supported max population = 10,000.

28. >10k is unsupported_population with no silent truncation.

29. Cursor pins evaluated_at/current/baseline/scope and expires explicitly.

30. Safe unavailable is distinct from typed integrity failure.

31. No Visit/Registry enrichment exists in 07-READ.

32. No product HTTP route/UI exists in 07-READ.

33. No query-time Omada / collector / DB / schema / index change is introduced.

34. 10k+10k PERF and query-plan gates PASS.

35. Future TRAFFIC-07 can consume this foundation without reproducing rate math.

36. Numeric v1 rate requires uptime in both snapshots.

37. counters_only never authorizes numeric rate in v1.

38. continuity estimator accounts for capture duration.

39. source-health newer attempts are same-Site/client/same-scope only.

40. one result uses one coherent SQLite read transaction.

41. support cap applies to selected scoped client row count <=10,000.

42. rate_evidence_status axis and outer precedence are exact.

43. total_rate_desc cursor/order uses integer total_delta_bytes, not float Mbps.
```

---

# 79. DRAFT R2 pre-FINAL state

```text
TASK:
TASK-TRAFFIC-07-READ — Online Guest Current Rate Read Foundation

STATUS:
DRAFT R2 — PRE-FINAL AMENDED

TRAFFIC-07-READ NECESSITY:
ACCEPTED / REQUIRED

MAJOR REDESIGN:
NOT REQUIRED

PRE-FINAL AMENDMENTS:
INCORPORATED

TASK DEVELOPMENT PARENT:
main@2a101cd27d69866db177254209d4e32529dbf56e
tree ed941c64ed2e612d74db1724da9d6850727070e7

PRODUCTION / RUNTIME REFERENCE:
c5f9dc39bbf399847f147526c9c7ae15769a198c
tree 0831ecf598b5760e8ede2e9e94a25b926480c2dd

NUMERIC RATE UPTIME REQUIREMENT:
BOTH SNAPSHOTS REQUIRED

COUNTERS-ONLY NUMERIC RATE:
FORBIDDEN v1

MAX GAP:
180s FIXED

SUPPORTED SOURCE POPULATION:
10,000 selected complete scoped client rows

PAGE:
default 50 / max 200

SORT:
public total_rate_desc
internal total_delta_bytes DESC + MAC ASC

READ CONSISTENCY:
one read-only SQLite transaction / coherent snapshot per result

VISIT / REGISTRY:
OUT OF 07-READ

CONTINUITY EVIDENCE GATE:
BLOCKED — RAW SCENARIO PAIRS NOT AVAILABLE IN RETRIEVABLE EVIDENCE

CONTINUITY METHOD:
NOT FROZEN

FINAL:
NOT APPROVED / NOT PERMITTED UNTIL EVIDENCE GATE PASSES

IMPLEMENTATION:
NOT AUTHORIZED

CODER:
NOT AUTHORIZED

PUBLICATION / MERGE / DEPLOY:
NOT AUTHORIZED
```

Next allowed architecture step:

```text
obtain required bounded raw continuity evidence

→ evaluate point vs capture-window estimator

→ freeze zero-false-positive continuity method/tolerance

→ re-fetch/rebind origin/main

→ prepare FINAL directly

→ Owner + Tech Lead FINAL review

→ separate Owner implementation authorization
```

Implementation MUST NOT begin from this amended R2.

