# TASK-TRAFFIC-07-READ — Online Guest Current Rate Read Foundation — DRAFT R2

**Project:** CaptivPortal  
**Area:** Admin Console → Traffic  
**Roadmap item:** `TRAFFIC-07-READ — Current Rate backend foundation`  
**Consumer:** future `TRAFFIC-07 — Online Guests Traffic`  
**Document state:** `DRAFT R2 — FOR OWNER + TECH LEAD REVIEW`  
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

`CurrentSnapshotMeta` already preserves:

```text
latest_attempt_result
latest_attempt_at
latest_partial_cycle_id
```

A newer partial attempt does NOT automatically replace the last complete-success
snapshot.

R2 behavior:

## Previous complete still fresh

Example:

```text
T0 complete-success
T1 duplicate/unidentified partial
T0 still fresh at evaluation time
```

Then:

```text
T0 remains selected current snapshot

controller-reported Online Guest items may remain usable

source_health_status = degraded

overall status = partial
```

No data from T1 is mixed into T0.

## Previous complete stale

Example:

```text
T0 complete-success
T1 partial
T0 now stale
```

Then:

```text
status = stale
population_count = null
items = []
```

No Online assertions.

## Previous complete unavailable age

Then:

```text
status = unavailable
population_count = null
items = []
```

---

# 14. Source health vs product status

Recommended source-health projection:

```text
source_health_status =
healthy
degraded
stale
unavailable
```

`healthy`:

```text
selected complete snapshot fresh
no newer partial/failed attempt requiring degradation
```

`degraded`:

```text
selected complete snapshot fresh
but a newer Current State attempt is partial/failed
```

`stale` / `unavailable` follow Current State freshness semantics.

This source-health field is separate from per-item:

```text
source_progress_status
```

---

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

Add permanent:

```text
source_progress_status =
advanced
frozen
unproven
```

This describes whether evidence proves that controller connection state advanced
between baseline/current snapshots.

It is distinct from:

```text
connection_continuity_status
```

---

# 24. Connection continuity model

Add permanent:

```text
connection_continuity_status =
proven
reset
unproven
```

A numeric client rate requires:

```text
source_progress_status = advanced
AND
connection_continuity_status = proven
```

subject also to directional counter validity.

---

# 25. Uptime rules

If both uptime values exist:

## Regression

```text
current_uptime < baseline_uptime
```

Required:

```text
connection_continuity_status = reset
source_progress_status = advanced or unproven as applicable,
but rate remains null

reason = connection_reset
```

No cross-reset delta.

## Equal

```text
current_uptime == baseline_uptime
```

Required mandatory v1 rule:

```text
source_progress_status = frozen
connection_continuity_status = unproven
D/U/Total = null
```

Even if counters are unchanged:

```text
NOT 0 Mbps
```

Even if counters appear changed, equal uptime is contradictory to the accepted
progress model and must not produce a numeric rate; implementation must classify
the exact contradiction safely according to the final continuity evidence
contract.

## Increased

```text
current_uptime > baseline_uptime
```

This establishes a:

```text
source progress candidate
```

Then continue:

```text
connection-start estimate compatibility
counter continuity
SSID continuity
elapsed/gap validation
```

Only after all checks pass:

```text
source_progress_status = advanced
connection_continuity_status = proven
```

---

# 26. Uptime missing

R1 broad `counters_only` rule is removed.

If either/both uptime values are missing:

## At least one accepted cumulative counter increases

Example:

```text
D1 > D0
or
U1 > U0
```

Then counter growth MAY prove:

```text
source_progress_status = advanced
```

subject to:

```text
same Site
same scope
same MAC
same SSID
no counter regression
remaining connection-continuity proof
```

Possible provenance:

```text
continuity_basis = counters_only
```

only if the final continuity method permits it.

## All available counters unchanged

Required:

```text
source_progress_status = unproven
connection_continuity_status = unproven
D/U/Total = null
```

NOT true zero.

True zero requires independent proof that the source advanced.

---

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

Same MAC is NOT sufficient.

Counters are cumulative for the CURRENT Omada connection.

Therefore the snapshot pair MUST prove:

```text
same connection
```

before delta arithmetic is accepted.

Preferred research candidate:

```text
connection_start_estimate =
snapshot_cycle.capture_started_at
-
controller_uptime
```

For baseline/current rows of one MAC:

```text
baseline connection_start_estimate
current  connection_start_estimate
```

must be compatible within an explicitly evidence-proven tolerance.

R2 intentionally does NOT invent that tolerance.

---

# 29. Mandatory bounded connection evidence check before FINAL

Before FINAL, Owner + Tech Lead / Architect must run or review bounded evidence
using existing research/production-compatible Current State/controller evidence.

Mandatory scenarios:

```text
1. stable same connection

2. idle same connection

3. active transfer

4. repeated/frozen Controller snapshot

5. physical disconnect/reconnect
```

For each scenario record at minimum:

```text
baseline cycle capture_started_at

current cycle capture_started_at

baseline/current client MAC

baseline/current SSID

baseline/current AP

baseline/current uptime when present

baseline/current trafficDown

baseline/current trafficUp

derived connection_start_estimate

known scenario outcome
```

Goal:

```text
prove exact compatibility tolerance
and exact v1 continuity decision method
```

Before FINAL freeze:

```text
continuity_method = <exact versioned identifier>

connection_start_estimate_tolerance_seconds = <exact proven value>
```

No invented tolerance is authorized in DRAFT R2.

If evidence cannot separate same-connection vs reconnect safely:

```text
STOP
→ reconsider current-rate feasibility
```

rather than weakening continuity proof.

---

# 30. Connection-start estimate formula

When uptime exists:

```text
connection_start_estimate =
cycle.capture_started_at - controller_uptime seconds
```

Use cycle `capture_started_at`, not row-local arbitrary timestamps.

Row `observed_at` must equal cycle start as an integrity invariant.

The eventual tolerance must account only for proven collection/controller timing
behavior.

No tolerance may be derived from convenience.

---

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

Every item must expose enough provenance for truthful consumer behavior.

Required conceptual fields:

```text
source_progress_status

connection_continuity_status

continuity_basis

download_reason

upload_reason

total_reason

rate_status
```

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
negative values
clamping malformed negative values to 0
```

---

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

# 36. Safe result statuses

Safe successful-response status family MAY include:

```text
ok
partial
insufficient_data
stale
unavailable
unsupported_population
```

These are product/source availability states.

They MUST NOT represent corruption/integrity failures.

---

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

For fresh selected complete snapshot:

```text
known_authorized_count
unknown_auth_count
population_count
population_complete
```

`population_count` means:

```text
known controller-reported authorized Online Guests
```

When fresh:

```text
population_count = known_authorized_count
```

If:

```text
unknown_auth_count > 0
```

then:

```text
population_complete = false
status at least partial
```

For stale/unavailable:

```text
population_count = null
population_complete = false
items = []
```

For unsupported:

```text
population_count = exact known authorized count
returned_count = 0
population_complete = false
items = []
```

subject to unknown-auth quality projection.

---

# 39. Supported population bound

Freeze v1:

```text
supported_max_population = 10_000
```

This is per authorized canonical Site/current selected cycle.

If:

```text
known_authorized_count > 10_000
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
top 200 pretending complete support
silent truncation
```

The 10k bound aligns with mandatory PERF capacity evidence.

Supporting the configurable 50k source maximum would require corresponding
50k+50k mandatory PERF and architecture review.

---

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

Default sort:

```text
total_rate_desc
```

Rules:

```text
numeric total descending
null totals last
MAC ascending tie-break
```

Because this is a global rate sort, implementation MUST evaluate rate semantics
for the eligible population of the pinned current/baseline pair before selecting
the top page.

Do NOT claim only 50/200 current rows need rate calculation.

Canonical work bound:

```text
exactly one current cycle
+
exactly one baseline cycle
+
up to supported 10,000 eligible current population rows
+
matching rows from exactly that baseline
```

Forbidden:

```text
multi-cycle historical scan
48h scan
per-client history search
```

---

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

last sort key

original evaluated_at
```

Whole cursor chain represents one semantic instant.

Page 2 cannot repin to:

```text
new current cycle
new baseline
new evaluated_at
```

If retention removes a pinned cycle:

```text
cursor_expired
```

or equivalent explicit validation failure.

Never silently repin.

Cursor Site/scope mismatch:

```text
400 / caller validation failure
```

not cross-context fallback.

---

# 43. Source pair selection before sorting/pagination

Execution order:

```text
authorize canonical Site

select accepted current complete cycle

evaluate freshness / newer attempt health

classify Online Guest population

if zero → return proved zero without baseline

enforce supported population

select nearest compatible baseline cycle

validate pair interval

evaluate source progress / continuity / counters
for eligible population

global sort

page/cursor
```

This preserves one semantic instant.

---

# 44. CurrentStateReadService extension

Current State remains schema/persistence owner.

07-READ may add a narrow read-only evidence helper, conceptually:

```text
get_client_rate_snapshot_pair(...)
```

or equivalent.

It may expose to the semantic owner:

```text
selected current cycle metadata
latest attempt/partial metadata
nearest compatible baseline cycle metadata
current eligible/unknown-auth rows
matching baseline rows
```

Permanent:

```text
read-only/query-only
same Site validation
same scope validation
no writer
no collector change
no schema migration
```

---

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

Mandatory candidate fixture:

```text
10,000 current client rows
+
10,000 baseline client rows
```

Same immutable fixture across candidate runs.

Fixture includes:

```text
authorized rows
unknown auth
pending
valid positive rates
valid zero rates
missing baseline
frozen evidence
connection reset
counter reset
SSID transition
AP roam
```

No Visit fixture.

---

# 57. PERF variants

At minimum:

```text
R50
current-rate request, limit=50

R200
current-rate request, limit=200

RG10K
global 10k eligible population
default total_rate_desc
return first page

RZERO
fresh complete authorized population=0
no baseline

RNOBASE
non-empty current population
no compatible baseline

RFROZEN
frozen/equal-uptime semantic fixture

RRESET
disconnect/reconnect/reset semantic fixture
```

Timed candidate variants:

```text
R50
R200
RG10K
```

at least:

```text
10 measured runs each
```

Semantic fixtures must be deterministic and may be untimed unless Lab chooses
otherwise.

---

# 58. PERF hard proposal

Accepted direction retained:

For:

```text
10k current + 10k baseline
global total_rate_desc
```

candidate:

```text
R200 / RG10K:

p95 <= 1.0s
max <= 1.5s
```

At least:

```text
10 measured runs
```

Also mandatory:

```text
source writes = 0

deterministic semantic result

one current/baseline pair

no multi-cycle scan

no new index

unexpected 5xx = 0
```

Before FINAL, Owner + Tech Lead may tighten but should not weaken without
evidence.

---

# 59. Query-plan evidence

Must prove:

```text
current cycle lookup bounded

baseline cycle lookup bounded

exactly one baseline cycle

eligible current population read bounded by selected cycle

baseline rows constrained to selected baseline cycle

existing indexes used or equivalent efficient access

no multi-cycle client-state scan

no retention-window scan

no source writes
```

Global sort evaluating up to 10k rates is expected and not a defect.

---

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
+
continuity otherwise proven
→ counters_only MAY prove advanced
```

subject to final continuity method.

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
cursor pins evaluated_at
current cycle
baseline cycle
scope
sort
Site
last key
```

New source cycle:

```text
does not shift existing cursor chain
```

Pinned cycle removed by retention:

```text
cursor_expired
```

Never repin silently.

Cross-Site/scope cursor:

```text
reject
```

---

# 71. Mandatory tests — sorting/capacity

```text
default limit=50
max=200
>200 rejected

default sort=total_rate_desc

global eligible population evaluated before top page

null totals last

MAC ascending tie-break

10k supported fixture

>10k unsupported

no duplicate/lost rows across cursor pages
```

---

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

# 73. Continuity evidence gate before FINAL

This is a blocking architecture gate, not implementation acceptance.

Before FINAL produce a bounded evidence record for:

```text
stable same connection
idle same connection
active transfer
frozen/repeated Controller state
disconnect/reconnect
```

The evidence must allow the Architect + Owner + Tech Lead to freeze:

```text
continuity_method
connection_start_estimate tolerance
handling when uptime is missing but counters advance
handling of contradictory equal-uptime/counter-growth evidence
```

FINAL cannot leave those unresolved.

---

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

Only one major semantic family remains intentionally unresolved:

```text
exact same-connection continuity method
```

Required pre-FINAL evidence must freeze:

```text
continuity_method identifier

connection_start_estimate tolerance

uptime-missing continuity decision details

equal-uptime/counter-growth contradiction handling
```

No implementation authorization before FINAL.

---

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
```

---

# 79. DRAFT R2 state

```text
TASK:
TASK-TRAFFIC-07-READ — Online Guest Current Rate Read Foundation

STATUS:
DRAFT R2 — FOR OWNER + TECH LEAD REVIEW

TRAFFIC-07-READ NECESSITY:
ACCEPTED / REQUIRED

GENERAL ARCHITECTURE:
ACCEPTED WITH R2 CORRECTIONS

TASK DEVELOPMENT PARENT:
main@2a101cd27d69866db177254209d4e32529dbf56e
tree ed941c64ed2e612d74db1724da9d6850727070e7

PRODUCTION / RUNTIME REFERENCE:
c5f9dc39bbf399847f147526c9c7ae15769a198c
tree 0831ecf598b5760e8ede2e9e94a25b926480c2dd

SEMANTIC OWNER:
CurrentGuestTrafficReadService

ONLINE SOURCE:
Current State

ONLINE MEANING:
controller-reported active authorized wireless client
from latest fresh complete Current State cycle
NOT instantaneous physical/radio proof

METRIC:
near-current interval-average current-connection counter delta

METRIC VERSION:
network_traffic_online_guest_current_rate.v1

POPULATION METHOD:
fresh_complete_current_state_authorized_guest_scope.v1

RATE METHOD:
current_connection_counter_delta_interval_average.v1

BASELINE METHOD:
nearest_previous_complete_same_site_scope_cycle.v1

CONTINUITY METHOD:
PENDING MANDATORY PRE-FINAL EVIDENCE CHECK

MAX GAP:
180s FIXED v1

SUPPORTED POPULATION:
10,000 per authorized canonical Site

PAGE:
default 50 / max 200

VISIT / REGISTRY:
OUT OF 07-READ / DEFER TO TRAFFIC-07

NEW PRODUCT HTTP ROUTE:
NO

NEW UI:
NO

NEW OMADA PATH:
NO

NEW COLLECTOR:
NO

NEW DB / SCHEMA / INDEX:
NO

FINAL:
NOT APPROVED

IMPLEMENTATION:
NOT AUTHORIZED

CODER:
NOT AUTHORIZED

PUBLICATION / MERGE / DEPLOY:
NOT AUTHORIZED
```

Next:

```text
Owner + Tech Lead review DRAFT R2

→ perform/accept bounded continuity evidence check

→ freeze exact continuity method + tolerance

→ repository rebind

→ FINAL

→ separate Owner implementation authorization
```

Implementation MUST NOT begin from this DRAFT R2.
