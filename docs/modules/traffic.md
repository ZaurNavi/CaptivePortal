# Admin Console Traffic

Status: current production module contract
Updated: 2026-09-01
Repository implementation baseline: `main@daf68e91fc759188980cf8741913e6b60a58eb62`
Repository tree: `b0e2f028eecf6aec9d86e35542c33e7105209335`
Production deployed HEAD: `daf68e91fc759188980cf8741913e6b60a58eb62`
Production tree: `b0e2f028eecf6aec9d86e35542c33e7105209335`
Latest production acceptance: `TASK-TRAFFIC-RANGE-01 — Independent Traffic Range per Panel — PASS / CLOSED`

## Current roadmap state

```text
TRAFFIC-00 — Traffic Section Foundation
DONE

TRAFFIC-01 — Current Network Throughput
DONE / PRODUCTION ACTIVE

TRAFFIC-02-READ — Historical Network Traffic Read Foundation
DONE

TRAFFIC-02 — Network Traffic History
DONE / PRODUCTION ACTIVE

TRAFFIC-02-PERF-01 — Historical range query remediation
DONE

TRAFFIC-03 — Period Statistics
DONE / PRODUCTION ACTIVE

TRAFFIC-04 — Peak Load Period
DONE / PRODUCTION ACTIVE

TRAFFIC-05 — Traffic by AP
DONE / PRODUCTION ACTIVE

TASK-TRAFFIC-RANGE-01 — Independent Traffic Range per Panel
DONE / PRODUCTION ACTIVE / PRODUCTION ACCEPTANCE PASS

TRAFFIC-06 — AP Traffic Share
NEXT / DRAFT REQUESTED / NOT IMPLEMENTED
```

`TRAFFIC-06` is change-intent only. Do not describe it as implemented, merged,
production-active or FINAL architecture until a separate DRAFT → review → FINAL
cycle and accepted implementation prove that state.

## Production feature state — 2026-09-01

Owner-confirmed production Traffic flags:

```text
WEB_ADMIN_TRAFFIC_ENABLED=true
WEB_ADMIN_TRAFFIC_HISTORY_ENABLED=true
WEB_ADMIN_TRAFFIC_STATISTICS_ENABLED=true
WEB_ADMIN_TRAFFIC_PEAK_ENABLED=true
WEB_ADMIN_TRAFFIC_BY_AP_ENABLED=true
WEB_ADMIN_TRAFFIC_INDEPENDENT_RANGES_ENABLED=true
```

Repository defaults remain:

```text
WEB_ADMIN_TRAFFIC_ENABLED=false
WEB_ADMIN_TRAFFIC_HISTORY_ENABLED=false
WEB_ADMIN_TRAFFIC_STATISTICS_ENABLED=false
WEB_ADMIN_TRAFFIC_PEAK_ENABLED=false
WEB_ADMIN_TRAFFIC_BY_AP_ENABLED=false
WEB_ADMIN_TRAFFIC_INDEPENDENT_RANGES_ENABLED=false
```

Repository defaults and production activation are separate facts.

## Current Traffic product surface

Production Traffic contains:

1. Current Network Throughput;
2. Network Traffic History;
3. Period Statistics;
4. Peak Load;
5. Traffic by AP.

Current layout is **production-current functional layout**, not a permanently
approved final visual composition.

## Domain boundary

Network Traffic means persisted AP/network throughput evidence in **Mbps**.

It is not WAN, Internet-only, billing, guest-only, SSID or Guest Session Traffic.
Radio is not a Site Network Traffic total source.

## Canonical architecture

```text
Omada AP traffic primitives
        ↓
Observation acquisition
        ↓
persisted AP traffic facts
        ↓
CurrentTrafficReadService / HistoricalTrafficReadService
        ↓
AdminQueryService
        ↓
Admin Traffic API
        ↓
CaptivPortalTrafficCoordinator
        ↓
TrafficHistoricalRequestBroker (historical page-local layer)
        ↓
historical product panels
```

Forbidden:
- browser → Omada;
- Admin request → Omada;
- second Traffic collector;
- second current/historical semantic owner;
- second scheduler/lifecycle owner;
- browser-side recomputation of canonical traffic analytics.

## Current Network Throughput

Canonical endpoint:

```text
GET /admin/api/v1/sites/<site_id>/traffic/current
```

Current Network Throughput is **range-insensitive** and has no 24h/7d selector.

Semantic owner: `CurrentTrafficReadService`.

Shared current policy remains:

```text
fresh max age = 90s
stale boundary = 180s
max AP skew = 60s
primary source = wired
fallback source = lan
radio = excluded
```

Backend Total is canonical. Browser does not recompute it.

## Historical Traffic range contract

Historical products:

- Network Traffic History;
- Period Statistics;
- Peak Load;
- Traffic by AP.

Each has an **independent** selector:

```text
24h | 7d
```

Range/bucket contracts:

```text
24h → 5-minute buckets  → 288 buckets
7d  → 15-minute buckets → 672 buckets
```

Server owns canonical UTC `[from_utc,to_utc)` boundaries.

## Per-panel range state

Every historical panel owns its own page-lifetime state:

```text
selected_range
applied_range
phase / request state
last successful payload
error
intent generation
```

`selected_range` and `applied_range` are intentionally different concepts:

- `selected_range` = current user intent;
- `applied_range` = range represented by the last successfully applied payload.

A failed range switch does **not** erase the previous successful payload. The
previous `applied_range` remains visible while the new `selected_range` is shown
as waiting/loading/error state.

Page reload resets every historical panel selector to:

```text
24h
```

Selector state is page-lifetime / memory-only. It is not persisted in:

```text
localStorage
sessionStorage
cookie
URL
server state
```

## Historical API current contract

Canonical endpoint:

```text
GET /admin/api/v1/sites/<site_id>/traffic/history
```

Required range remains:

```text
range=24h|7d
```

Canonical product projection:

```text
products=
```

Canonical tokens and order:

```text
history,statistics,peak,aps
```

Examples:

```text
?range=24h&products=history
?range=7d&products=statistics
?range=24h&products=peak
?range=7d&products=aps
?range=24h&products=history,statistics,peak,aps
```

Legacy `include=` is temporarily retained for backward compatibility.

Validation rules:

```text
include + products              → 400
empty products                  → 400
duplicate tokens                → 400
out-of-order tokens             → 400
unknown tokens                  → 400
whitespace / malformed products → 400
```

A product-scoped request must not execute unrelated product-specific
calculations.

For AP-only projection, the response includes compact self-contained:

```text
ap_bucket_axis
```

so the AP series can be interpreted without returning full History buckets.

## Period Statistics

`TRAFFIC-03` remains production-active.

Metrics in Mbps:

```text
Average Download / Upload / Total
Peak Download / Upload / Total
```

Average method:

```text
right_endpoint_sample_hold_time_weighted.v1
```

Peak method:

```text
max_accepted_complete_site_sample.v1
```

Peak Total is the maximum observed Total of one accepted Site sample, not
`Peak Download + Peak Upload`.

Statuses remain:

```text
ok
partial
insufficient_data
```

## Peak Load

`TRAFFIC-04` remains production-active.

Canonical methods:

```text
metric version:
network_traffic_peak_load.v1

peak:
max_accepted_complete_site_sample.v1

peak tie:
earliest_peak_sample_at.v1

sample timestamp semantics:
cycle_finished_at

busiest bucket:
max_complete_history_bucket_total_mean.v1

bucket tie:
earliest_bucket_start.v1

busiest 60 minutes:
max_complete_rolling_3600s_average_total_sample_hold.v1

average:
right_endpoint_sample_hold_time_weighted.v1

hour tie:
earliest_window_start.v1
```

Busiest 60 Minutes does not use or expose `occurrence_count`.

## Traffic by AP

`TRAFFIC-05` is current production functionality.

Canonical metric:

```text
network_traffic_by_ap.v1
unit = Mbps
```

Current accepted product semantics include:

```text
population:
current_union_historical_validated.v1

AP order:
ap_mac_ascending.v1

historical series encoding:
outer_history_bucket_aligned_du.v1

historical bucket method:
mean_of_accepted_ap_rates_for_canonical_site_bucket_samples.v1

Average:
right_endpoint_ap_sample_hold_time_weighted.v1

Peak:
max_accepted_complete_ap_sample.v1
```

The current supported population cap is:

```text
12 APs
```

Traffic by AP exposes all supported Site APs for the panel's **applied** Network
range, with aligned historical series, per-AP Average/Peak/coverage and current
AP evidence.

Current AP product status family includes:

```text
ok
partial
insufficient_data
unsupported_population
```

Traffic by AP is not AP Traffic Share. It reports per-AP traffic evidence and
does not define the future share metric.

## Historical request broker

Canonical architectural name:

```text
TrafficHistoricalRequestBroker
```

This is the page-local layer that owns:

- historical panel intent queueing;
- same-range coalescing;
- response-to-panel mapping;
- generation/supersession protection;
- panel-local selected/applied state coordination.

It is **not** the scheduler/lifecycle owner.

Canonical scheduler/lifecycle owner remains:

```text
CaptivPortalTrafficCoordinator
```

Permanent invariant:

```text
max historical HTTP requests in flight from one Traffic page = 1
```

### Dispatch / coalescing rules

- Initial all-24h state may coalesce enabled products into one combined request.
- A panel range click queues only the product represented by that panel.
- Global Refresh groups work by selected range and historical work is dispatched sequentially.
- Explicit panel intent has priority over queued Global Refresh intent.
- Multiple pending intents for the same panel collapse to the latest intent.
- Products with the same range may coalesce into one canonical `products=` request.
- A shared in-flight batch is not aborted solely because one included panel is superseded.
- A response is applied to a panel only when both its intent generation and selected range are still current.

## Historical Request Admission Guard

Permanent production invariant:

```text
HISTORICAL_TRAFFIC_REQUEST_ADMISSION_GUARD_SECONDS = 10
```

Canonical eligibility formula:

```text
next_dispatch >= max(
    previous_request_completion,
    previous_dispatch + 10s,
    coordinator backoff / Retry-After / lifecycle eligibility
)
```

Guard timing is measured from **actual dispatch**, not from completion.

Rules:
- first request on a fresh Traffic page may dispatch immediately;
- `waiting` = queued / admission blocked, no historical HTTP request currently dispatched for that panel intent;
- `loading` = real historical HTTP request is in flight;
- Global Refresh does not bypass the guard;
- manual retry does not bypass the guard;
- HTTP 503 does not bypass the guard;
- guard never shortens Retry-After, coordinator backoff or lifecycle eligibility;
- guard state is page-local / memory-only.

## Why Independent Traffic Range exists

Before `TASK-TRAFFIC-RANGE-01`, a shared 7d combined historical request could
reach the production query deadline when several expensive products were coupled
to one range switch.

The accepted remediation was **not** a larger deadline.

Preserved limits:

```text
WEB_ADMIN_MAX_QUERY_DURATION_SECONDS = 10
Traffic browser request timeout = 20s
Admin query concurrency = unchanged
```

The problem was addressed by:

```text
product-scoped historical projection
+
independent panel intent
+
one-request-in-flight scheduling
+
sequential admission
+
10-second admission guard
```

No new collector, Traffic DB, schema/index, cache/rollup or Omada request path was
introduced.

## TRAFFIC-RANGE-01 production-size §97 PERF evidence

Result:

```text
PASS
```

Backward-compatibility 24h:

```text
B24:
p50 0.537377s
p95 0.543665s
max  0.543820s

C24:
p50 0.536886s
p95 0.545050s
max  0.549600s

relative backward-compatibility gates:
PASS

B24 ↔ C24 semantic identity:
PASS
```

Product-scoped matrix:

```text
H24 PASS
H7  PASS
S24 PASS
S7  PASS
P24 PASS
P7  PASS
A24 PASS
A7  PASS
```

A7:

```text
p50 2.444160s
p95 2.469994s
max  2.472858s
query_deadline = 0
source_integrity = 0
unexpected 5xx = 0
```

Immutable production-size snapshot:

```text
bytes:
273235968

SHA256:
b65a2ce7718454571f08c474c1b59045c3da415d1e160a55725d5095e49287eb
```

These timings are dated acceptance evidence, not runtime SLO constants.

## Acceptance / publication history

### TRAFFIC-05

```text
TASK-TRAFFIC-05 — Traffic by AP
PR #93
publication commit: 85edc14214e3a271a300249b5b1062be31547c95
merge commit: 8a5c4db899406eeb1f737abe63495247be1ee75a
merge tree: 6837dd729dedb0df6414b3f979657a3f6f55d0ab
status: DONE / PRODUCTION ACTIVE
```

### TRAFFIC-RANGE-01

Accepted repository/production tree:

```text
b0e2f028eecf6aec9d86e35542c33e7105209335
```

Publication:

```text
publication commit: 355b413e9167bafb8ca9547af08c037eef86b189
PR #94
merge commit: daf68e91fc759188980cf8741913e6b60a58eb62
```

Accepted closing sequence:

```text
Implementation candidate
→ focused gate PASS
→ targeted Traffic regression PASS WITH REVIEWED COMPATIBILITY
→ Windows Central Lab V6-FIXED PASS
→ Linux production-size §97 PERF PASS
→ Git publication
→ PR #94
→ Owner merge
→ production deploy FROM GIT
→ dormant production acceptance PASS
→ separate feature activation
→ production browser/product acceptance PASS
```

The reviewed Windows SQLite infinity compatibility case reproduces on the exact
approved baseline and is **not** a TASK regression.

Current production service:

```text
captive-portal.service = active
```

## Historical accepted Traffic evidence

The following TRAFFIC-03 / TRAFFIC-04 material is retained as historical
engineering evidence. Historical statements about a shared selected History range
describe the pre-RANGE-01 implementation and do not override the current
independent-range architecture.

## TRAFFIC-03 performance remediation history

Historical engineering evidence remains valid:

```text
initial candidate:
d96ddbc6f8685be175ee9a48da9b8e15621f2161
initial tree:
5e6a28950c8079d805450dc2a7ecf652a8285820
functional/V6 = PASS
production-size PERF = FAIL
status = SUPERSEDED

final candidate:
79875aca61297c8de4c30b7119b15118079f26d0
accepted tree:
1d8b94590848f9505e45e653384dd8a7c18d4339
all mandatory gates = PASS
merge PR = #89
production merge = b92efbfabb38f912550526bc5a3d1f2f1a8ae4d6
```

This is historical evidence, not current implementation state.

## TRAFFIC-04 accepted artifact and chain-of-custody

TASK baseline:

```text
commit: e1a278c3e2c131b0762d7134485dcf3208eac11e
tree:   a529faae4ded9e3f6c5cb72c5a9c6d9cfcc9df3e
```

Accepted candidate / publication / merge:

```text
accepted candidate tree:
f53f204cf3ebf7cecf4e872ce450b4f3f4265cc9

publication branch:
feature/traffic-peak-v1

publication commit:
0343ac77a1a90c2ba8bc3ce1c969b6c1593e9759

PR:
#91

merged production commit:
a9cd8a9b9b9efc46bc82d315385ebbd1a3bf63b0

merged / production tree:
f53f204cf3ebf7cecf4e872ce450b4f3f4265cc9
```

The merge preserved the exact accepted candidate tree.

## TRAFFIC-04 acceptance evidence

Windows Central Lab V6:

```text
PASS
strict regressions = 0
known compatibility warnings = 5
compileall = PASS
branch diff = PASS
exact artifact immutability = PASS
```

Linux production-size PERF:

```text
PASS
immutable production-size observations snapshot used
```

### Controlled PERF amendment #1 — TASK-TRAFFIC-04 only

The accepted post-FINAL amendment changed only the **Peak vs Candidate p50**
relative allowance:

```text
original:
Δp50(P-C) <= max(0.50s, 20% of C.p50)

accepted amendment #1:
Δp50(P-C) <= max(0.50s, 30% of C.p50)
```

All other limits remained unchanged:

```text
Candidate vs Baseline p50:
max(0.50s, 20% of B.p50)

p95 relative/absolute:
25% / 0.75s

max relative/absolute:
25% / 1.00s

Peak hard p95 <= 8s
Peak hard max <= 9s
QueryDeadline = 10s
browser request timeout = 20s
```

This amendment is specific historical acceptance evidence for `TASK-TRAFFIC-04`.
It does not silently redefine other TASKs or global performance policy.

### Actual TASK-04 gate execution clarification

The historical FINAL specified a separate Controlled Browser Acceptance before
publication. The Owner-approved execution that actually closed this TASK did
**not** use a separate pre-publication browser gate.

Actual accepted execution path:

```text
Patch
→ Windows Central Lab V6 PASS
→ Linux production-size PERF PASS
→ accepted candidate
→ Git publication / PR #91
→ Owner merge
→ production deploy FROM GIT
→ separate Peak activation
→ production product/browser acceptance PASS
```

This is execution history for `TASK-TRAFFIC-04`; it does not weaken the generic
project rule that every gate actually designated mandatory for an exact candidate
must pass before normal publication.

Coder wrote/verified TASK-scoped implementation. Official acceptance belonged to
Owner + Tech Lead; Coder did not duplicate Central Lab/PERF/official gates.

## Production rollout and activation

Previous production checkpoint:

```text
b92efbfabb38f912550526bc5a3d1f2f1a8ae4d6
1d8b94590848f9505e45e653384dd8a7c18d4339
```

`TASK-TRAFFIC-04` was deployed **FROM GIT**, without SCP/manual source patch.

Stage 1 — dormant code:

```text
new code deployed
WEB_ADMIN_TRAFFIC_PEAK_ENABLED=false
service / Current / History / Statistics = PASS
```

Stage 2 — separate activation:

```text
WEB_ADMIN_TRAFFIC_PEAK_ENABLED=true
second controlled restart
```

Post-activation evidence:

```text
service active/running
NRestarts=0
startup clean
Observation cycles continue
Omada webhook continues normally
public portal endpoints continue normally
```

## Production product acceptance — TRAFFIC-04

Owner-confirmed:

```text
TASK-TRAFFIC-04:
CLOSED / PRODUCTION PASS

24h:
History PASS
Period Statistics PASS
Peak Load PASS
Peak timestamps PASS
Busiest History Bucket PASS
Busiest 60 Minutes PASS

7d:
History PASS
Period Statistics PASS
Peak Load PASS
Peak timestamps PASS
Busiest History Bucket PASS
Busiest 60 Minutes PASS

Period Statistics Peak values = Peak Load Peak values
shared selected History range = PASS
```

### One-time UI observation — not an open defect

During initial manual production checking the Owner observed one instance where a
switch to `7d` did not visibly refresh until page reload.

The symptom did not reproduce. Follow-up production diagnostics showed sequential
History requests returning HTTP 200 with no observed `429`, `503`, `query_deadline`
or concurrency failure.

Owner decision:

```text
not a TASK-TRAFFIC-04 blocker
no remediation opened
no defect/debt recorded
continue observation only
investigate separately only if a concrete repeatable symptom returns
```

Do not list this one-time observation as an open current defect or technical debt.

## Cross-surface and ownership invariants

- Current Traffic and Home Traffic share `CurrentTrafficReadService`.
- All historical Traffic products reuse `HistoricalTrafficReadService` and persisted Observation evidence.
- Independent panel selectors do not create independent historical semantic owners.
- `TrafficHistoricalRequestBroker` is not a second scheduler.
- `CaptivPortalTrafficCoordinator` remains the scheduler/lifecycle owner.
- Browser does not manufacture Traffic analytics.
- Missing/invalid/gap evidence is never silently converted to zero.
- Feature exposure flags do not start/stop Observation or shared Analytics services.

## Next step

Next roadmap item:

```text
TASK-TRAFFIC-06 — AP Traffic Share
NEXT / DRAFT REQUESTED / NOT IMPLEMENTED
```

Current canonical idea only:

```text
share of accepted Network Traffic evidence within selected range
```

It is not user count and not sample count.

Permanent reminder:

```text
sample count != traffic share
```

`TRAFFIC-06` must reuse the existing historical Network Traffic semantic
foundation. Exact formulas, product contract and architecture remain undefined
until separate DRAFT → review → FINAL.
