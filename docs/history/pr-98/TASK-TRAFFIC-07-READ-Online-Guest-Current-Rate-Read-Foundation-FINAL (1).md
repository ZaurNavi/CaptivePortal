# TASK-TRAFFIC-07-READ — Online Guest Current Rate Read Foundation — FINAL

**Project:** CaptivPortal  
**Area:** Admin Console → Traffic  
**Roadmap item:** `TRAFFIC-07-READ — Current Rate backend foundation`  
**Consumer:** future `TRAFFIC-07 — Online Guests Traffic`  
**Document state:** `FINAL — FOR OWNER + TECH LEAD FINAL REVIEW`  
**Prepared:** 2026-09-01  
**Implementation authorization:** `NOT GRANTED`  
**Code / branch / patch / PR / merge / deploy / activation:** `NOT AUTHORIZED`

---

# 1. Executive decision

Canonical roadmap decision:

```text
TRAFFIC-07-READ = REQUIRED
```

Architecture status:

```text
FINAL
```

This FINAL creates the semantic read foundation for future:

```text
TRAFFIC-07 — Online Guests Traffic
```

It does NOT itself authorize implementation.

Implementation / Coder / branch / patch / PR / publication / merge / deploy remain:

```text
NOT AUTHORIZED BY THIS FINAL
```

Core v1 semantic decision:

```text
TRAFFIC-07-READ follows accepted Omada Controller connection context semantics.

It does NOT attempt to reconstruct a stricter hidden physical Wi-Fi/radio
connection identity.
```

Permanent:

```text
physical Wi-Fi OFF/ON
!=
automatic TRAFFIC-07-READ connection boundary
```

The authoritative source remains:

```text
Current State
```

and the canonical current-rate owner remains:

```text
CurrentGuestTrafficReadService
```

# 2. Repository / production baseline

`origin/main` was re-fetched immediately before this FINAL.

Exact TASK development parent:

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

Exact production/runtime reference:

```text
HEAD:
c5f9dc39bbf399847f147526c9c7ae15769a198c

tree:
0831ecf598b5760e8ede2e9e94a25b926480c2dd
```

Bounded drift review:

```text
Current State:
NO semantic/runtime drift

Analytics relevant to 07-READ:
NO semantic/runtime drift

Admin Traffic contracts relevant to 07-READ:
NO semantic/runtime drift
```

PR #97 is documentation-only:

```text
application code changed = NO
test code changed = NO
runtime config changed = NO
production changed by PR #97 = NO
```

Therefore:

```text
REBINDED TO CURRENT main
NO ARCHITECTURAL STOP
```

Before any separate implementation authorization:

```text
re-fetch origin/main again
re-pin exact SHA/tree
impact-review any implementation-changing drift
```

# 3. Owner + Tech Lead final disposition

Accepted / frozen:

```text
TRAFFIC-07-READ necessity

CurrentGuestTrafficReadService semantic ownership

Current State authoritative source

controller-reported Online Guest semantics

fresh complete requirement

one Site-wide current/baseline pair

one coherent SQLite read snapshot per result

same Site/scope/MAC/auth/SSID compatibility

AP roam allowed

180s fixed max rate gap

current-connection cumulative counter delta

near-current interval-average Mbps

both-snapshot uptime requirement for numeric rate

counters-only numeric rate forbidden

10,000 selected scoped source-row support cap

default page 50 / max 200

integer total_delta_bytes sort/cursor key

Visit / Registry OUT

AuthSession OUT

Observation fallback OUT

no route/UI/collector/DB/schema/index/scheduler

10k+10k PERF and query-plan gates
```

Final continuity decision:

```text
CONTINUITY SEMANTICS:
accepted Omada Controller connection context

CONTINUITY METHOD:
omada_controller_connection_progress_v1

PHYSICAL RADIO CONNECTION ESTIMATOR:
NOT REQUIRED

ADDITIONAL CONTROLLER RESEARCH:
NOT REQUIRED
```

The previous empirical continuity blocker is removed by explicit Owner + Tech Lead
semantic decision.

No R3 DRAFT is required.

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

Freeze independent root evidence axes:

```text
source_health_status =
healthy | degraded | stale | unavailable

rate_evidence_status =
not_applicable | complete | partial | insufficient_data

population_complete =
true | false
```

These axes describe the FULL pinned semantic result and are NOT page-local
properties.

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

## rate_evidence_status — page-independent canonical meaning

`rate_evidence_status` characterizes the ENTIRE eligible known-authorized Online
Guest population of the selected pinned current/baseline pair BEFORE:

```text
global sort
pagination
cursor page selection
```

It MUST NOT be calculated from only the returned 50/200 items.

### `not_applicable`

```text
proved known-authorized current population = 0
```

No baseline is required.

### `complete`

```text
every eligible known-authorized Online Guest
in the supported selected population
has complete numeric Download/Upload/Total rate evidence
```

### `partial`

```text
at least some usable numeric rate evidence exists

but complete Download/Upload/Total evidence does NOT exist
for the entire eligible known-authorized population
```

### `insufficient_data`

```text
eligible known-authorized current population is non-empty

but no usable numeric current-rate evidence can safely be established
for any eligible known-authorized guest
```

## Root rate provenance counts

Expose root-level counts:

```text
rate_valid_count
rate_partial_count
rate_unavailable_count
```

Definitions:

```text
rate_valid_count
=
eligible known-authorized items with complete numeric D/U/Total evidence

rate_partial_count
=
eligible known-authorized items with some usable numeric rate evidence
but incomplete D/U/Total evidence

rate_unavailable_count
=
eligible known-authorized items with no usable numeric current-rate evidence
```

These counts describe the full eligible population, not the current page.

For a fresh supported non-zero known-authorized population:

```text
rate_valid_count
+
rate_partial_count
+
rate_unavailable_count
=
known_authorized_count
```

For proved zero population:

```text
rate_evidence_status = not_applicable
rate_valid_count = 0
rate_partial_count = 0
rate_unavailable_count = 0
```

For stale/unavailable results where the current eligible population is not
canonically asserted, rate provenance counts are not fabricated as current zero
facts.

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
current population.

## Cursor-chain invariance

Every page in one pinned cursor chain MUST expose the same root:

```text
source_health_status
rate_evidence_status
population_complete

rate_valid_count
rate_partial_count
rate_unavailable_count

outer status
```

Pagination changes only returned items and cursor position.

It does NOT change semantic quality of the pinned result.

The exact outer status precedence remains frozen in Section 36.

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

unit =
Mbps
```

Canonical metric meaning:

```text
near-current interval-average rate
over one accepted Current State snapshot pair
inside one accepted Omada Controller connection context
```

The continuity method does NOT compare reconstructed physical connection-start
timestamps.

There is:

```text
no continuity tolerance
no physical-radio connection timer
no additional controller grace timer
```

The existing fixed rate-evidence gap remains:

```text
CURRENT_GUEST_RATE_MAX_GAP_SECONDS = 180
```

# 23. Source progress model

Permanent per-item:

```text
source_progress_status =
advanced
frozen
unproven
```

## advanced

When both uptimes exist and:

```text
current_uptime > baseline_uptime
```

the accepted Omada Controller connection evidence advanced.

Subject to all required context/counter checks, this may authorize numeric rate.

If uptime is missing, monotonic counter growth MAY support:

```text
source_progress_status = advanced
```

as diagnostic source-progress evidence, but numeric rate remains forbidden because
connection continuity is unproven.

## frozen

When both uptimes exist and:

```text
current_uptime == baseline_uptime
```

required:

```text
source_progress_status = frozen
```

This often corresponds to Controller-retained client state that did not advance.

It is NOT proof of zero Traffic.

## unproven

Used when available evidence cannot prove source advancement.

Source progress is independent from:

```text
connection_continuity_status
```

# 24. Connection continuity model

Permanent:

```text
connection_continuity_status =
proven
reset
unproven
```

v1 continuity method:

```text
omada_controller_connection_progress_v1
```

Numeric rate requires:

```text
same authorized canonical Site

same source_scope_hash

same canonical client MAC

same SSID

baseline auth_classification = authorized

current auth_classification = authorized

controller_uptime present in BOTH snapshots

current_uptime > baseline_uptime

0 < elapsed_seconds <= 180

required direction counters present

required direction counters monotonic
```

Then the rate calculation accepts the pair as continuation of the same accepted
Omada Controller connection context.

AP equality is NOT required.

```text
AP-A → AP-B
```

inside the same SSID does not itself break continuity.

The method intentionally does NOT attempt to detect every physical radio
disconnect/reconnect.

# 25. Uptime rules

Numeric v1 rate requires `controller_uptime` in BOTH snapshots.

## Uptime increased

```text
current_uptime > baseline_uptime
```

means:

```text
source_progress_status = advanced
```

If Site/scope/MAC/SSID/auth/elapsed/counter requirements also pass:

```text
connection_continuity_status = proven
```

and numeric directional rates may be calculated.

## Uptime equal

```text
current_uptime == baseline_uptime
```

required:

```text
source_progress_status = frozen

connection_continuity_status = unproven

download_mbps = null
upload_mbps = null
total_mbps = null
```

Even if counters are unchanged:

```text
THIS IS NOT 0 Mbps
```

A physically disconnected client may remain controller-reported active while
uptime/counters are frozen.

## Uptime regression

```text
current_uptime < baseline_uptime
```

required:

```text
connection_continuity_status = reset

download_mbps = null
upload_mbps = null
total_mbps = null

reason = connection_reset
```

No cross-reset delta.

## Missing uptime

If uptime is missing from either snapshot:

```text
connection_continuity_status = unproven

download_mbps = null
upload_mbps = null
total_mbps = null
```

Counters-only numeric rate is forbidden in v1.

# 26. Missing uptime — v1 hard boundary

Permanent v1:

```text
numeric rate requires controller_uptime in BOTH snapshots
```

If either uptime is missing:

```text
connection_continuity_status = unproven

D/U/Total = null
```

Counter growth may indicate source progress:

```text
source_progress_status = advanced
```

but does not prove that baseline/current belong to the same Omada connection
context.

Therefore:

```text
continuity_basis = counters_only
```

MUST NOT authorize numeric rate.

Future v2 may revisit this only if a stronger connection identifier/evidence is
separately approved.

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

# 28. Accepted Omada Controller connection context and sampled boundary limit

v1 does not reconstruct hidden physical Wi-Fi connection identity.

The canonical continuity boundary is the context Omada exposes through persisted
accepted Current State evidence:

```text
same Site/scope/MAC/SSID/auth context

controller_uptime progression

current-connection cumulative counter continuity

fixed 180s Current State pair gap
```

Freeze boundary-observation semantics:

```text
connection_boundary_observation =
sampled_current_state_evidence_v1
```

Meaning:

```text
TRAFFIC-07-READ can detect and suppress a Controller connection boundary
only insofar as that boundary is observable in the accepted persisted
Current State snapshots used by the pinned pair.
```

Observable boundary/conflict evidence includes conditions such as:

```text
uptime regression/reset
counter regression/reset
missing compatible baseline row
authorization incompatibility/transition
SSID transition
missing uptime
frozen/unproven source
invalid elapsed
gap > 180s
```

When such evidence is present, unsafe cross-connection delta is conservatively
rejected.

## Physical disconnect is not itself a boundary

Research established that a physical disconnect does not necessarily finalize the
Controller connection immediately.

Omada may retain the old client context for approximately several minutes.

During retained disconnected state:

```text
active may remain true
uptime/counters may be frozen
```

A short physical disconnect/reconnect may therefore continue the same Controller
connection context.

CaptivPortal follows that authoritative Controller behavior.

Permanent:

```text
physical reconnect itself
!= mandatory Traffic connection reset
```

## Explicit sampled-boundary limitation

A Controller old-connection finalization, new connection establishment and new
authorization may theoretically occur entirely BETWEEN two accepted Current State
collection snapshots.

If no persisted contradictory/boundary evidence exists in either accepted
snapshot:

```text
v1 does NOT independently reconstruct that hidden transition.
```

Canonical limitation:

```text
an unobserved Controller connection boundary occurring entirely between two
accepted Current State snapshots is not independently detectable in v1.
```

In that case:

```text
TRAFFIC-07-READ follows the accepted sampled Controller evidence.
```

This is a v1 sampling limitation.

It is NOT:

```text
an integrity failure
a reason to invent a point/window estimator
a reason to add a continuity tolerance
a reason to add a Controller grace timer
a reason to perform physical Wi-Fi boundary detection
a reason for more Omada research
```

After normal compatible progressing snapshots exist in a Controller context,
rate is evaluated according to `omada_controller_connection_progress_v1`.

No hidden physical-connection estimator is layered on top.

# 29. Omada continuity architecture evidence

The accepted research basis for v1 is architecture evidence, not a new runtime
algorithm.

Research established:

```text
physical disconnect
!=
immediate Controller connection finalization
```

Omada may retain the old active client context for approximately five minutes.

During retained disconnected state:

```text
uptime/counters may be frozen
```

Therefore:

```text
equal uptime
→ frozen evidence
→ null rate
→ NOT 0 Mbps
```

Research also established that a short physical disconnect/reconnect may continue
the same Controller connection.

Therefore:

```text
physical reconnect itself
!= mandatory TRAFFIC connection reset
```

The runtime does NOT include:

```text
a five-minute timer
physical-link reconstruction
point/window estimator
continuity tolerance
```

The observed Controller retention window remains source-system behavior only.

TRAFFIC-07-READ retains:

```text
CURRENT_GUEST_RATE_MAX_GAP_SECONDS = 180
```

as the independent accepted rate-evidence bound.

Freeze:

```text
connection_boundary_observation =
sampled_current_state_evidence_v1
```

Therefore the guarantee is intentionally bounded:

```text
observable Controller connection boundaries are conservatively rejected;

unobserved sub-sampling boundaries are outside v1 detection guarantees.
```

This limitation is accepted architecture behavior and does not reopen Controller
research.

# 30. Continuity method — exact v1 contract

Freeze:

```text
continuity_method =
omada_controller_connection_progress_v1
```

For a client/direction, numeric rate is possible only when:

```text
same Site

same source_scope_hash

same canonical MAC

same SSID

baseline authorized

current authorized

uptime exists in both snapshots

current_uptime > baseline_uptime

0 < rate elapsed <= 180s

direction counter exists in both snapshots

current counter >= baseline counter
```

No physical connection-start reconstruction is performed.

No tolerance value exists.

No Controller-retention timer is added.

Rate elapsed remains:

```text
current_cycle.capture_started_at
-
baseline_cycle.capture_started_at
```

Row integrity remains:

```text
row.observed_at == cycle.capture_started_at
```

`capture_finished_at` may remain ordinary cycle metadata but is not part of
connection continuity classification or rate denominator.

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

Required:

```text
source_progress_status

connection_continuity_status

continuity_basis

download_reason

upload_reason

total_reason

rate_status
```

Freeze v1 `continuity_basis` family:

```text
uptime_progress
counters_only_diagnostic
none
```

Only:

```text
uptime_progress
```

may authorize numeric rate.

`counters_only_diagnostic` may explain observed counter growth when uptime is
missing, but rate remains null.

Recommended:

```text
rate_status =
valid
partial
unavailable
```

Numeric D/U/Total MUST be:

```text
finite
>= 0
```

Forbidden:

```text
NaN
Infinity
negative rate
clamping malformed values to zero
```

# 35. Reason family

Canonical minimum reason family:

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

No reason implies a physical-radio disconnect detector.

Physical link transitions matter only insofar as they change accepted Controller
evidence.

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

Independent root axes:

```text
source_health_status =
healthy | degraded | stale | unavailable

rate_evidence_status =
not_applicable | complete | partial | insufficient_data

population_complete =
true | false
```

`rate_evidence_status` and its provenance counts are computed for the entire
eligible known-authorized population of the pinned current/baseline pair BEFORE
global sort/pagination.

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
even when outer status is only `partial`.

All pages of one pinned cursor chain MUST retain identical:

```text
source_health_status
rate_evidence_status
population_complete
outer status

rate_valid_count
rate_partial_count
rate_unavailable_count
```

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

# 38. Population and root rate-evidence projection

For a fresh selected complete scoped current cycle expose:

```text
scoped_client_row_count
known_authorized_count
unknown_auth_count
population_count
population_complete
supported_max_population

rate_evidence_status
rate_valid_count
rate_partial_count
rate_unavailable_count
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

The rate counts and `rate_evidence_status` are population-wide root provenance,
computed across the full eligible known-authorized population before sort/page
selection.

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

Fresh supported non-zero population:

```text
rate_valid_count
+
rate_partial_count
+
rate_unavailable_count
=
known_authorized_count
```

Stale/unavailable:

```text
population_count=null
items=[]
```

Do not fabricate population/rate-evidence counts as current truth when the current
population itself is not canonically asserted.

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

Before sorting, the service MUST evaluate every eligible known-authorized Online
Guest in the supported pinned population sufficiently to compute:

```text
rate_evidence_status
rate_valid_count
rate_partial_count
rate_unavailable_count
```

Only after those page-independent root semantics are frozen for the result does
global sorting occur.

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

Global sort requires evaluating rate semantics for the eligible population of the
pinned current/baseline pair before top-page selection.

Do NOT claim only 50/200 rows need rate evaluation.

Pagination never recomputes or changes the root evidence statuses/counts.

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

Every cursor page MUST be validated against the pinned semantic root and expose
the same:

```text
source_health_status
rate_evidence_status
population_complete
outer status

rate_valid_count
rate_partial_count
rate_unavailable_count
```

Pagination changes only returned items and cursor position.

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
  derive root rate_evidence_status=not_applicable
  derive zero root rate counts
  return without baseline

enforce scoped-client-row <=10k

select nearest previous complete same-Site/same-scope baseline

validate pair interval

read current + matching baseline rows

evaluate source progress / continuity / counters
for the full eligible known-authorized population

derive population-wide:
  rate_valid_count
  rate_partial_count
  rate_unavailable_count
  rate_evidence_status

derive outer status

global integer-key sort

page/cursor selection
```

Therefore:

```text
root semantic quality is fixed before pagination
```

Cursor page requests are separate transactions, but MUST use the pinned:

```text
Site
current cycle
baseline cycle
evaluated_at
scope
```

and MUST reproduce/validate the same root status/count semantics.

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

That route is not authorized by this FINAL.

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

No new index is authorized by this FINAL.

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
current_uptime > baseline_uptime
→ source_progress_status=advanced
```

subject to remaining continuity/counter checks.

```text
current_uptime == baseline_uptime
→ source_progress_status=frozen
→ connection_continuity_status=unproven
→ rates=null
→ NOT 0 Mbps
```

```text
current_uptime < baseline_uptime
→ connection_continuity_status=reset
→ rates=null
```

```text
uptime missing in either snapshot
→ connection_continuity_status=unproven
→ rates=null
```

If uptime is missing but counters increase:

```text
source_progress_status MAY be advanced
continuity_basis=counters_only_diagnostic
numeric rate remains forbidden
```

True zero fixture:

```text
uptime increased
same Controller context accepted
counter delta=0
→ numeric 0.0 Mbps
```

# 67. Mandatory tests — continuity and sampled boundaries

```text
same Site/scope/MAC/SSID/auth
uptime present in both
current_uptime > baseline_uptime
monotonic counters
0<elapsed<=180
→ continuity proven under omada_controller_connection_progress_v1
```

```text
uptime regression
→ reset
→ no cross-connection delta
```

```text
same MAC + same SSID + AP changed
→ AP roam alone does not invalidate rate
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

```text
short physical Wi-Fi disconnect/reconnect
while Omada continues same progressing Controller connection context
→ no artificial CaptivPortal connection split
```

Observable sampled boundary fixtures MUST prove conservative null behavior for:

```text
uptime regression/reset
counter regression/reset
missing compatible baseline
auth incompatibility/transition
SSID transition
missing uptime
frozen/unproven source
invalid elapsed
gap >180s
```

Also freeze/test the explicit limitation:

```text
Controller old-context finalization + new context + new authorization
may theoretically occur entirely between two accepted Current State snapshots.

If neither accepted snapshot contains contradictory/boundary evidence,
v1 follows the accepted sampled Controller evidence and does not reconstruct
the hidden transition.
```

Required architecture identifier:

```text
connection_boundary_observation =
sampled_current_state_evidence_v1
```

Test expectation:

```text
observable Controller boundaries
→ conservatively rejected

unobserved sub-sampling boundary
→ outside v1 independent detection guarantee
→ NOT an integrity failure
```

No physical-connection estimator, continuity tolerance, Controller grace timer or
additional Omada research is part of v1.

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

# 70. Mandatory tests — cursor and page-independent root semantics

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

For a multi-page pinned result, prove every page has identical root:

```text
source_health_status
rate_evidence_status
population_complete
outer status

rate_valid_count
rate_partial_count
rate_unavailable_count
```

Changing page size from 50 to 200 MUST NOT alter those root values.

Changing which items are returned on later pages MUST NOT alter those root values.

`rate_evidence_status` MUST be computed from the entire eligible known-authorized
population before pagination, never from page-local items.

# 71. Mandatory tests — sorting/capacity/status

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

Population-wide rate evidence fixtures:

```text
0 known authorized
→ not_applicable
→ valid=0 partial=0 unavailable=0

all eligible guests complete D/U/Total
→ complete

mix of complete / partial / unavailable with at least one usable numeric rate
→ partial

non-empty eligible population with no usable numeric rate
→ insufficient_data
```

For every supported non-zero fresh population:

```text
rate_valid_count
+
rate_partial_count
+
rate_unavailable_count
=
known_authorized_count
```

Prove identical root status/counts for:

```text
page 1
later pages
different permitted page sizes
```

within one pinned semantic result.

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

# 73. Continuity architecture closure

The continuity architecture is CLOSED by explicit Owner + Tech Lead semantic
decision.

Freeze:

```text
CONTINUITY SEMANTICS:
Omada Controller connection context

CONTINUITY METHOD:
omada_controller_connection_progress_v1

CONNECTION BOUNDARY OBSERVATION:
sampled_current_state_evidence_v1

PHYSICAL RADIO CONTINUITY DETECTION:
NOT REQUIRED / NON-GOAL

POINT/WINDOW ESTIMATOR:
REMOVED / NOT USED

CONTINUITY TOLERANCE:
NONE

ADDITIONAL CONTROLLER RESEARCH:
NOT REQUIRED
```

Observable boundary evidence is conservatively rejected through existing v1
checks.

Permanent sampled limitation:

```text
an unobserved Controller connection boundary occurring entirely between two
accepted Current State snapshots is not independently detectable in v1.
```

In that case:

```text
TRAFFIC-07-READ follows the accepted sampled Controller evidence.
```

This is not an integrity failure and does not reopen continuity research.

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

detect every Wi-Fi OFF/ON event

reconstruct hidden physical radio connection identity
```

---

# 75. Stop conditions

Implementation MUST STOP if it requires:

```text
a physical-radio connection estimator

a continuity tolerance

a new Controller-retention/grace timer

counters-only numeric rate

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

Visit/Registry composition inside 07-READ

new scheduler/worker

browser-side rate math

change to 180s gap merely to bridge connection boundaries
```

Any such need requires a new architecture decision.

# 76. FINAL Owner + Tech Lead decisions

```text
TRAFFIC-07-READ NECESSITY:
ACCEPTED / REQUIRED

SEMANTIC OWNER:
CurrentGuestTrafficReadService

ONLINE SOURCE:
Current State

ONLINE SEMANTICS:
controller-reported active authorized wireless client
from latest fresh complete Current State cycle

PHYSICAL/RADIO ONLINE PROOF:
NOT CLAIMED

SNAPSHOT PAIR:
one Site-wide current + nearest previous complete compatible cycle

READ CONSISTENCY:
one coherent read-only SQLite transaction per result

MAX RATE GAP:
180s FIXED v1

BASELINE COMPATIBILITY:
same Site / scope / MAC / auth / SSID

AP ROAM:
allowed; AP equality not required

RATE SOURCE:
current Omada connection cumulative trafficDown/trafficUp counters

RATE MEANING:
near-current interval-average Mbps

CONTINUITY SEMANTICS:
accepted Omada Controller connection context

CONTINUITY METHOD:
omada_controller_connection_progress_v1

CONNECTION BOUNDARY OBSERVATION:
sampled_current_state_evidence_v1

SAMPLED BOUNDARY LIMITATION:
unobserved Controller boundary fully between accepted snapshots
is outside v1 independent detection guarantee

UPTIME:
required in both snapshots for numeric rate

UPTIME INCREASE:
accepted source progress candidate

UPTIME EQUAL:
frozen / null

UPTIME REGRESSION:
reset / null

COUNTERS-ONLY NUMERIC RATE:
FORBIDDEN

TRUE ZERO:
only after accepted progress/continuity with zero counter delta

POINT/WINDOW ESTIMATOR:
REMOVED / NOT USED

CONTINUITY TOLERANCE:
NONE

ADDITIONAL CONTROLLER RESEARCH:
NOT REQUIRED

SUPPORTED SCOPED POPULATION:
10,000 rows

PAGE:
default 50 / max 200

RATE EVIDENCE STATUS:
population-wide / page-independent / computed before pagination

ROOT RATE COUNTS:
rate_valid_count / rate_partial_count / rate_unavailable_count
for full eligible known-authorized population

SORT:
public total_rate_desc
internal total_delta_bytes DESC, MAC ASC

VISIT / REGISTRY:
OUT OF 07-READ

AUTHSESSION:
OUT

OBSERVATION CURRENT-RATE FALLBACK:
OUT

NEW HTTP ROUTE:
NO

NEW UI:
NO

NEW OMADA PATH:
NO

NEW COLLECTOR:
NO

NEW DB / SCHEMA / INDEX:
NO

NEW SCHEDULER:
NO

PERF:
10k current + 10k baseline
R200 / RG10K p95 <=1.0s
max <=1.5s
query-plan evidence mandatory
```

# 77. Architecture closure before implementation authorization

There is no remaining architecture blocker in this FINAL.

Continuity is frozen as:

```text
omada_controller_connection_progress_v1
```

No additional controller research is required.

However:

```text
IMPLEMENTATION AUTHORIZATION IS STILL NOT GRANTED
```

Before a separate Owner implementation authorization:

```text
re-fetch origin/main

re-pin exact SHA/tree

impact-review any implementation-changing drift
```

If semantic drift is found in Current State / Analytics / relevant Admin contracts:

```text
STOP
→ return to Architect / Owner / Tech Lead
```

# 78. FINAL acceptance contract

A future implementation candidate must prove:

```text
1. TRAFFIC-07-READ uses Current State only for Online/current-rate truth.

2. Online Guest is controller-reported, not instantaneous physical/radio truth.

3. Latest fresh complete compatible Current State cycle is required.

4. Stale/unavailable current population is null, never fabricated zero.

5. Fresh proved zero authorized population returns ok / 0 / [] without baseline.

6. Unknown auth is excluded and makes population incomplete.

7. duplicate/unidentified relevant rows remain partial-cycle behavior.

8. newer degraded attempt affects source health only when same Site/client/scope and
   deterministically newer.

9. one result uses one coherent SQLite read transaction.

10. one Site-wide current/baseline cycle pair is used.

11. interval uses capture_started_at to capture_started_at.

12. row observed_at matches selected cycle capture_started_at.

13. same Site/scope/MAC/authorized/SSID required.

14. AP roam alone does not invalidate continuity.

15. 180s fixed max gap remains.

16. metric is near-current interval-average Mbps.

17. continuity_method is omada_controller_connection_progress_v1.

18. connection_boundary_observation is sampled_current_state_evidence_v1.

19. numeric rate requires uptime in both snapshots.

20. uptime increase plus all compatibility/counter checks can prove continuity.

21. equal uptime is frozen/null, not zero.

22. uptime regression is reset/null.

23. missing uptime is continuity-unproven/null.

24. counters-only numeric rate is forbidden.

25. true zero requires accepted source advancement/continuity and zero delta.

26. direction counter regression yields null for that direction.

27. no unsigned wrap/clamp/negative repair.

28. one direction may be numeric while other is null.

29. Total numeric only when D/U numeric; backend Total is canonical.

30. physical Wi-Fi OFF/ON is not itself a Traffic connection boundary.

31. no attempt is made to detect every physical radio disconnect.

32. observable Controller connection boundaries are conservatively rejected.

33. an unobserved Controller connection boundary entirely between accepted Current
    State snapshots is outside v1 independent detection guarantee.

34. such a sub-sampling boundary is a documented sampling limitation, not an
    integrity failure and not a trigger for estimator/tolerance/timer/research.

35. Controller-retention behavior is not encoded as a new timer/rate interval.

36. selected scoped source rows <=10,000.

37. >10k scoped rows is unsupported_population with no truncation.

38. default page=50 / max=200.

39. rate_evidence_status is computed over the entire eligible known-authorized
    population before global sort/pagination.

40. rate_valid_count / rate_partial_count / rate_unavailable_count are root counts
    for the full eligible known-authorized population.

41. all pages of one pinned cursor chain expose identical source_health_status,
    rate_evidence_status, population_complete, outer status and root rate counts.

42. global sort uses integer total_delta_bytes DESC, MAC ASC.

43. cursor pins evaluated_at/current/baseline/scope/sort and expires explicitly.

44. source_health_status, rate_evidence_status and population_complete remain
    independent axes with frozen outer precedence.

45. safe unavailable remains distinct from typed integrity failure.

46. Visit/Registry/AuthSession are not part of 07-READ.

47. Observation does not become a current-rate fallback.

48. no query-time Omada.

49. no new collector/DB/schema/index/scheduler.

50. no product HTTP route/UI in 07-READ.

51. 10k+10k PERF and query-plan gates PASS.

52. existing Current State/Home/Traffic/Visit behavior regressions = 0.

53. future TRAFFIC-07 consumes this foundation without reproducing rate math.
```

Any mandatory failure:

```text
candidate NOT ACCEPTED

publication NOT AUTHORIZED
```

# 79. FINAL state

```text
TASK:
TASK-TRAFFIC-07-READ — Online Guest Current Rate Read Foundation

STATUS:
FINAL — CORRECTED / FOR OWNER + TECH LEAD ACCEPTANCE

TRAFFIC-07-READ NECESSITY:
ACCEPTED / REQUIRED

ARCHITECTURE:
FINAL

TASK DEVELOPMENT PARENT:
main@2a101cd27d69866db177254209d4e32529dbf56e
tree ed941c64ed2e612d74db1724da9d6850727070e7

PRODUCTION / RUNTIME REFERENCE:
c5f9dc39bbf399847f147526c9c7ae15769a198c
tree 0831ecf598b5760e8ede2e9e94a25b926480c2dd

REPOSITORY DRIFT REVIEW:
PASS
PR #97 documentation-only
no Current State / Analytics / relevant Admin Traffic runtime semantic drift

SEMANTIC OWNER:
CurrentGuestTrafficReadService

ONLINE SOURCE:
Current State

ONLINE SEMANTICS:
controller-reported

CONTINUITY SEMANTICS:
Omada Controller connection context

CONTINUITY METHOD:
omada_controller_connection_progress_v1

CONNECTION BOUNDARY OBSERVATION:
sampled_current_state_evidence_v1

PHYSICAL RADIO CONTINUITY DETECTION:
NOT REQUIRED / NON-GOAL

POINT/WINDOW ESTIMATOR:
REMOVED / NOT USED

CONTINUITY TOLERANCE:
NONE

ADDITIONAL CONTROLLER RESEARCH:
NOT REQUIRED

MAX RATE GAP:
180s FIXED v1

NUMERIC RATE REQUIRES UPTIME:
BOTH SNAPSHOTS

COUNTERS-ONLY NUMERIC RATE:
FORBIDDEN

SUPPORTED SCOPED POPULATION:
10,000

PAGE:
default 50 / max 200

RATE EVIDENCE STATUS:
PAGE-INDEPENDENT / FULL ELIGIBLE KNOWN-AUTHORIZED POPULATION

ROOT RATE COUNTS:
rate_valid_count / rate_partial_count / rate_unavailable_count

READ CONSISTENCY:
one read-only SQLite transaction / coherent snapshot per result

VISIT / REGISTRY:
OUT OF 07-READ

AUTHSESSION:
OUT

OBSERVATION FALLBACK:
OUT

NEW HTTP ROUTE:
NO

NEW UI:
NO

NEW COLLECTOR:
NO

NEW DB / SCHEMA / INDEX:
NO

NEW SCHEDULER / WORKER:
NO

IMPLEMENTATION AUTHORIZATION:
NOT GRANTED BY FINAL ITSELF

CODER AUTHORIZATION:
NOT GRANTED

PUBLICATION / MERGE / DEPLOY:
NOT AUTHORIZED
```

Expected next state only after Owner + Tech Lead verify this corrected FINAL:

```text
FINAL:
OWNER + TECH LEAD ACCEPTED

ARCHITECTURE:
CLOSED

IMPLEMENTATION:
READY FOR SEPARATE OWNER AUTHORIZATION
```

This FINAL does not authorize implementation.

