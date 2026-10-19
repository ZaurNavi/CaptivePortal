# TASK-HOME-TRAFFIC-MASTER — Admin Console Home Current Traffic — FINAL

**Project:** CaptivPortal  
**Parent:** `TASK-HOME-01 — Admin Console Home v1`  
**Type:** master architecture / sequencing contract  
**Status:** `FINAL MASTER ARCHITECTURE — TECH LEAD REVIEW INCORPORATED`  
**Implementation authorization:** `NOT GRANTED`  
**Production authorization:** `NOT GRANTED`  
**Architecture baseline reviewed:** `origin/main@dafbc40b6f5c5b3dde6b52fcc2c7689e95d05081`  
**Prepared:** 2026-08-24  
**Tech Lead verdict incorporated:** `Architecture direction PASS / targeted revision completed`

---

## 1. Purpose

This master defines the complete Home Traffic v1 architecture while physically separating the two executable changes required by the accepted dependency chain.

```text
existing Observation AP acquisition
→ persisted AP counters and derived Mbps
→ TASK-HOME-TRAFFIC-READ-01-FINAL
→ actual PR A merge SHA
→ TASK-HOME-TRAFFIC-01-FINAL
→ Admin API / Home UI
```

The master is final architecture. It is not an implementation authorization.

---

## 2. Mandatory physical task split

The executable work is two tasks.

### Task A

```text
TASK-HOME-TRAFFIC-READ-01-FINAL
Baseline:
dafbc40b6f5c5b3dde6b52fcc2c7689e95d05081
```

Purpose:

```text
Observation persisted facts
→ CurrentTrafficReadService
```

### Task B

```text
TASK-HOME-TRAFFIC-01-FINAL
Baseline:
<actual merge SHA of Task A / PR A>
```

Purpose:

```text
CurrentTrafficReadService
→ AdminQueryService
→ Admin API
→ Home Traffic UI
```

Task B MUST NOT be issued as an executable FINAL before the actual Task A merge SHA exists and is re-verified. A placeholder baseline is forbidden.

For architecture continuity this package contains a locked post-READ specification. After PR A merge the Architect rebinds that locked specification to the exact merge SHA and emits `TASK-HOME-TRAFFIC-01-FINAL.md` without reopening already-settled product choices unless the merge disproves an assumption.

---

## 3. Product outcome

Home Traffic v1 displays:

```text
Download Now
Upload Now
Total Traffic Now
Traffic freshness
Traffic coverage
Traffic by AP
```

Unit:

```text
Mbps
```

The metric is persisted AP physical/network traffic evidence. It is not automatically Internet-only, WAN-only, guest-only, or `Zefer_Parki`-only traffic.

Forbidden labels in v1:

```text
Internet Load
WAN Load
Channel Load
Guest Internet Traffic
Zefer_Parki Traffic
```

Allowed wording:

```text
Traffic Now
Site AP Traffic
Download Now
Upload Now
Total Traffic Now
```

Required helper meaning:

```text
Derived from persisted AP traffic counters.
May include local/service traffic and is not an Internet-only measurement.
```

---

## 4. Permanent acquisition boundary

No new collector is introduced.

```text
Home/Admin = reader
Observation worker = existing acquisition/rate owner
```

Forbidden:

```text
Browser → Omada
Admin route → Omada
CurrentTrafficReadService → Omada
Home request → new Observation cycle
Home request → higher Omada polling
Home → Loki/Grafana
Home → raw log parsing
```

Observation remains the acquisition authority. Analytics/read services only read persisted facts.

---

## 5. Existing rate facts remain authoritative

Existing persisted AP rates:

```text
wired_download_mbps
wired_upload_mbps
lan_rx_mbps
lan_tx_mbps
radio_rx_mbps
radio_tx_mbps
```

Existing reasons:

```text
ok
no_baseline
counter_reset
gap_too_large
invalid_elapsed
source_unavailable
```

Existing rate formula remains unchanged:

```text
(current_counter - previous_counter)
× 8
÷ elapsed_seconds
÷ 1,000,000
```

Home Traffic never recalculates counters.

---

## 6. Direction contract

```text
wired_download_mbps → Download
wired_upload_mbps   → Upload

lan_rx_mbps         → Download
lan_tx_mbps         → Upload

future radio_tx_mbps → Download
future radio_rx_mbps → Upload
```

Radio remains out of v1 Site total and out of v1 UI.

---

## 7. Canonical source family

Final v1 policy:

```text
Primary: wired
Fallback: LAN
Radio: excluded from v1 Site total
```

Never sum alternate source families:

```text
wired + LAN        FORBIDDEN
wired + radio      FORBIDDEN
LAN + radio        FORBIDDEN
```

Never blend source family by AP:

```text
AP-1 wired + AP-2 LAN   FORBIDDEN
```

One Site snapshot uses exactly one source family for all APs.

---

## 8. Canonical cycle

Current traffic is computed from one exact AP dynamic cycle.

Filter:

```sql
site_id = ?
AND kind = 'ap_dynamic'
AND state = 'completed'
AND complete = 1
AND result = 'success'
```

Exact ordering:

```sql
ORDER BY started_at DESC, cycle_id DESC
```

All summary/source-selection/page context reads occur in one read-only SQLite snapshot transaction where they belong to one request.

No independent latest-per-AP reconstruction is allowed.

---

## 9. Complete-success integrity contract

Canonical cycle requires:

```text
finished_at != null
finished_at >= started_at

items_seen = items_stored
items_skipped = 0
error_count = 0
data_quality_warning_count = 0

stored AP row count = items_stored
source_rows_reported = items_seen
```

Each AP row requires:

```text
site_id = selected cycle Site
cycle_id = selected cycle
canonical unique AP MAC

partial = 0
overview_ok = 1
wired_uplink_ok = 1
lan_traffic_ok = 1
radios_ok = 1
```

Any contradiction is an integrity failure:

```text
503 source_unavailable
```

It is not downgraded into product partial coverage.

---

## 10. Strict rate/reason/timestamp matrix

For every wired/LAN direction:

```text
reason = ok
requires:
  finite non-negative numeric rate
  valid source-section timestamp

reason != ok
requires:
  rate = null
```

Integrity failures include:

```text
reason=ok + rate=null
reason=ok + negative/non-finite rate
reason!=ok + numeric rate
unknown/null reason in accepted complete-success AP row
reason=ok + missing/invalid source timestamp
```

`pair_valid` includes reason, numeric value, and valid section timestamp.

---

## 11. Empty population is explicit

Source-selection first branch:

```text
if total_ap_count == 0:
    selected_source = wired
    selection_reason = empty_population
```

Then normal coverage-based source selection applies only to non-empty populations.

`empty_population` is part of the API/frontend allowlist.

---

## 12. No-cycle and empty-cycle are different

### No canonical cycle

```text
cycle_id=null
selected_source=null
selection_reason=no_complete_snapshot
freshness=unavailable
coverage=none
traffic values=null
empty_population=false
```

### Complete-success zero-AP cycle

```text
cycle_id=<real cycle>
selected_source=wired
selection_reason=empty_population
freshness calculated from cycle.finished_at
coverage=complete
download=0.0
upload=0.0
total=0.0
empty_population=true
```

Frontend state validation must distinguish these cases.

---

## 13. Source-selection algorithm for non-empty population

Calculate:

```text
wired_pair_valid_ap_count
lan_pair_valid_ap_count
```

Then:

```text
if wired_pair_valid == total_ap_count:
    selected_source = wired
    selection_reason = primary_full_coverage

elif lan_pair_valid == total_ap_count:
    selected_source = lan
    selection_reason = fallback_full_coverage

elif lan_pair_valid > wired_pair_valid:
    selected_source = lan
    selection_reason = fallback_higher_coverage

else:
    selected_source = wired
    selection_reason = primary_preferred_tie_or_higher
```

No per-AP source mixing.

---

## 14. Direction-specific partial aggregation

For selected source:

```text
download_mbps =
  SUM(valid Download directions)
  if valid_download_ap_count > 0
  else null

upload_mbps =
  SUM(valid Upload directions)
  if valid_upload_ap_count > 0
  else null

total_mbps =
  download_mbps + upload_mbps
  only if both subtotals are non-null
  else null
```

A missing direction never becomes zero.

Partial UI MUST display:

```text
Download: X/Y APs
Upload:   X/Y APs
Both:     X/Y APs
```

Any numeric value under partial coverage is visibly marked:

```text
Observed subtotal
```

This is mandatory, not optional.

---

## 15. Coverage statuses

Allowed:

```text
complete
partial
none
```

`complete`:

```text
zero-AP complete-success cycle
OR
all APs have both selected-source directions valid
AND source skew is within policy
```

`partial`:

```text
at least one direction subtotal is numeric
AND not complete
```

`none`:

```text
non-empty population
AND no selected-source numeric Download/Upload direction exists
```

Coverage counters include:

```text
total_ap_count
valid_rate_ap_count
valid_download_ap_count
valid_upload_ap_count
missing_rate_ap_count
stale_ap_count
unavailable_ap_count
reset_ap_count
gap_rejected_ap_count
no_baseline_ap_count
source_unavailable_ap_count
invalid_elapsed_ap_count
```

Reason AP counts are non-exclusive, with one AP counted at most once per reason category.

---

## 16. Temporal contract

For every selected source-section timestamp in a canonical cycle:

```text
cycle.started_at
<= section observed_at
<= cycle.finished_at
<= evaluated_at
```

Any negative age or future timestamp is:

```text
freshness=unavailable
freshness_reason=clock_anomaly
```

There is no hidden clock tolerance.

Source timestamp:

```text
wired → wired_observed_at
LAN   → lan_observed_at
```

For non-empty population:

```text
observed_at = MIN(all required selected-source AP timestamps)
newest_observed_at = MAX(all required selected-source AP timestamps)
source_skew_seconds = newest - oldest
```

NULL timestamps are integrity failure under the accepted complete-success matrix; SQL MIN/MAX must never silently hide them.

For zero AP population:

```text
observed_at = cycle.finished_at
newest_observed_at = cycle.finished_at
source_skew_seconds = 0
```

---

## 17. Freshness policy

Repository defaults for Task B:

```text
WEB_ADMIN_HOME_TRAFFIC_FRESH_MAX_AGE_SECONDS=90
WEB_ADMIN_HOME_TRAFFIC_STALE_MAX_AGE_SECONDS=180
WEB_ADMIN_HOME_TRAFFIC_MAX_AP_SKEW_SECONDS=60
```

Allowed states:

```text
fresh
stale
unavailable
```

No negative age is allowed.

Per-AP freshness counters are computed from the selected section timestamp:

```text
fresh AP
stale AP
unavailable AP
```

Aggregate freshness is conservative because `observed_at` is the oldest required selected-source timestamp.

When aggregate freshness becomes `unavailable`, all product traffic numeric values become null.

---

## 18. Latest-attempt evidence is mandatory

Every summary snapshot returns bounded latest-attempt metadata:

```text
latest_attempt_state
latest_attempt_result
latest_attempt_at
using_previous_complete_snapshot
```

Allowed state:

```text
none
running
completed
abandoned
```

Allowed result:

```text
null
success
partial
failed
shutdown
```

`latest_attempt_at` is a canonical UTC timestamp selected by a deterministic contract in Task A.

Raw failure category is never exposed.

---

## 19. AP page contract

AP page is pinned to:

```text
Site
cycle_id
selected_source
```

First page:

```text
cycle_id=<summary cycle>
cursor omitted
```

Next page:

```text
cycle_id=<same cycle>
cursor=<previous next_cursor>
```

Rules:

```text
cursor without cycle_id → 400
cursor cycle/source mismatch → 400
retained complete-success explicitly pinned cycle → allowed
deleted/expired cycle → 400
```

Cursor binds:

```text
endpoint kind
Site
cycle_id
selected source
last canonical AP MAC
version
```

Cursor requires canonical decode + re-encode validation.

---

## 20. AP page unavailable behavior

If summary freshness is `unavailable`:

```text
browser MUST NOT request AP traffic page
```

If local age progression transitions accepted Traffic to `unavailable`:

```text
clear/hide Traffic AP rows
hide Load More
disable Traffic pagination
hide all AP rate values
```

After a new successful available summary:

```text
reload AP traffic from first pinned page
```

---

## 21. Permission behavior

Capabilities:

```text
Traffic summary → admin.read.overview
Traffic AP page → admin.read.observations
```

403 behavior differs by layer:

```text
Summary 403
→ global Site-forbidden Home state

AP page 403 after accepted summary
→ preserve allowed Traffic summary
→ stop only Traffic AP table
→ show AP detail access denied
```

A stronger detail permission must not erase an allowed overview.

---

## 22. Top-level Home refresh coordination — FINAL choice

Task B uses deterministic phased Home refresh. No generic third parallel request is allowed.

One page-level coordinator owns:

```text
initial load
manual Refresh
visibility resume
Refresh button state
generation lifecycle
source phase progression
```

Phases:

```text
PHASE A
Client Current State + AP Current State
maximum 2 parallel reads

wait until both settle by success/error/timeout

PHASE B
Traffic Summary
one read

PHASE C
Traffic AP first page
only if summary accepted and not unavailable
one read
```

Load More is not allowed to overlap a new top-level refresh; it is aborted/deferred by the coordinator.

This guarantees one browser tab never exceeds the accepted server concurrency of two Home reads.

Independent source states remain independent even though scheduling is coordinated.

---

## 23. Cross-tab concurrency policy

No cross-tab leader election is introduced in v1.

Therefore HTTP 429 is accepted as a controlled server concurrency signal across two simultaneously visible tabs.

Required behavior:

```text
429 never clears accepted data
429 never creates overlap
429 never creates retry storm
Retry-After respected
retry never faster than 60 seconds
bounded backoff + per-tab desynchronizing jitter after 429
```

Defined two-tab production soak acceptance:

```text
2 visible tabs
5 automatic Home refresh cycles each
+ 1 manual refresh in one tab

Total 429 responses <= 12
No source has >3 consecutive eligible 429 responses in one tab
No retry occurs before its eligibility time
Both tabs recover without reload once capacity is available
```

If this bound is exceeded, activation is not accepted; investigate server limit/timing rather than weakening isolation.

---

## 24. AbortController ownership

Every Home/Traffic request uses identity-safe controller ownership:

```text
claim controller together with generation
```

`finally` may release ownership only when:

```text
stored controller identity
is exactly the completing controller
AND stored generation is the completing generation
```

A late `finally` from an old request cannot clear a newer controller.

Pinned-400 clean refresh:

```text
starts only after previous lifecycle completes
runs exactly once
uses new generation
cannot be started by old finally
cannot overlap old request
```

Behavioral tests are mandatory.

---

## 25. Strict response state matrix

Task B frontend uses exact allowlists.

### freshness_reason

```text
within_freshness_window
within_stale_window
age_exceeded
clock_anomaly
no_complete_snapshot
source_unavailable
```

### coverage_reasons

```text
missing_direction
missing_pair
temporal_skew
no_valid_rate
empty_population
```

Empty list is allowed where appropriate.

### selection_reason

```text
no_complete_snapshot
empty_population
primary_full_coverage
fallback_full_coverage
fallback_higher_coverage
primary_preferred_tie_or_higher
```

### rate reasons

```text
ok
no_baseline
counter_reset
gap_too_large
invalid_elapsed
source_unavailable
```

### latest attempt states/results

As defined in section 18.

Mutual invariants include:

```text
cycle_id=null
↔ no complete snapshot

complete=true
↔ canonical cycle accepted

coverage=none
→ traffic values null

freshness=unavailable
→ traffic values null

empty_population=true
→ cycle exists
→ selected_source=wired
→ selection_reason=empty_population
→ coverage=complete
→ all traffic values=0.0

snapshot.observed_at <= newest_observed_at <= evaluated_at

page cycle/source
= accepted summary cycle/source
```

Frontend validates canonical UTC timestamps, nullability, identity, enum values and state combinations before changing DOM.

---

## 26. Frontend / Node mandatory gate

Task B cannot pass only because frontend tests were skipped.

Required:

```text
record Node version

node --check app/admin_web/static/admin.js

Home Traffic frontend behavioral suite:
PASS
0 skipped because Node unavailable
```

Existing unrelated platform-specific skips may remain, but the new Traffic frontend suite cannot be accepted through Node-unavailable skip.

---

## 27. Production cadence reconciliation

Activation evidence records actual production values:

```text
OBSERVATION_AP_INTERVAL_SECONDS
OBSERVATION_AP_CYCLE_MAX_DURATION_SECONDS
OBSERVATION_RATE_MAX_GAP_SECONDS
```

Repository defaults are not acceptance evidence.

Frontend Traffic polling is read-only and may observe the same persisted cycle more than once; it does not cause Omada polling. Therefore v1 does NOT require browser refresh interval to be >= Observation source interval.

However activation must enforce:

```text
WEB_ADMIN_HOME_TRAFFIC_STALE_MAX_AGE_SECONDS
>=
OBSERVATION_AP_INTERVAL_SECONDS
+
OBSERVATION_AP_CYCLE_MAX_DURATION_SECONDS
```

unless Tech Lead explicitly accepts a stricter operational stale policy for the measured production cycle duration.

Also verify:

```text
OBSERVATION_RATE_MAX_GAP_SECONDS
```

remains consistent with the source worker's bounded cadence.

---

## 28. Performance measurement contract

For each Traffic endpoint collect:

```text
>=20 successful HTTP 200 measurements
```

Only successful HTTP 200 durations enter latency percentiles.

Count separately:

```text
429
500
503
other non-200
```

Percentile calculation is nearest-rank:

```text
sort successful durations ascending
rank = ceil(0.95 × N)
p95 = value at 1-based rank
```

Proposed production targets:

```text
summary p95 <= 100 ms
AP page p95 <= 250 ms
```

Fast 429/503 responses never improve the successful-request percentile.

---

## 29. Product/Observability boundary

Product may expose:

```text
aggregate Mbps
AP managed identity in authenticated detail
freshness
coverage
source family
bounded reasons
latest-attempt safe state
```

Do not expose:

```text
raw SQL
DB path
stack trace
raw controller payload
raw counters
credentials/tokens
raw failure category
WLAN password/config payload
```

Route telemetry does not log AP MAC, client identity, cursor or cycle IDs.

---

## 30. Future Multi-Site compatibility

Every Traffic read remains Site-scoped.

```text
no cross-Site aggregate
no cross-Site cursor
no hidden default Site in source method
no tenant_id
Tenant != Site
```

---

## 31. Out of scope

Separate future tasks:

```text
HOME-TRAFFIC-RADIO-01
HOME-CHANNEL-LOAD-01
HOME-TODAY-01
HOME-HEALTH-01
HOME-AP-24H-01
```

No per-client speed, no radio-band UI, no channel load, no Today traffic, no WAN-only claim.

---

## 32. Production sequencing

```text
1. Owner authorizes TASK-HOME-TRAFFIC-READ-01-FINAL
2. Coder PLAN
3. PR A implementation/tests
4. Architect/static review
5. Linux gate
6. merge PR A
7. record actual merge SHA
8. Architect binds locked Task B specification to exact SHA
9. emit TASK-HOME-TRAFFIC-01-FINAL
10. separate Owner authorization
11. Coder PLAN
12. PR B implementation/tests
13. Architect/static review
14. Linux + Node gate
15. merge PR B
16. deploy code with Traffic flag false
17. verify Home Live remains accepted
18. separate Owner production activation
19. functional/concurrency/performance/privacy/coexistence soak
20. final production acceptance
```

---

## 33. Current authorization state

```text
MASTER ARCHITECTURE: FINAL

TASK-HOME-TRAFFIC-READ-01:
FINAL SPECIFICATION AVAILABLE
IMPLEMENTATION NOT AUTHORIZED

TASK-HOME-TRAFFIC-01 UI/API:
ARCHITECTURE LOCKED
EXECUTABLE FINAL NOT YET ISSUED
REQUIRES ACTUAL PR A MERGE SHA

NO production change authorized
```
