# Admin Console Traffic

Status: current production module contract
Updated: 2026-08-31
Repository baseline: `main@a9cd8a9b9b9efc46bc82d315385ebbd1a3bf63b0`
Repository tree: `f53f204cf3ebf7cecf4e872ce450b4f3f4265cc9`
Production deployed HEAD: `a9cd8a9b9b9efc46bc82d315385ebbd1a3bf63b0`
Production tree: `f53f204cf3ebf7cecf4e872ce450b4f3f4265cc9`
Latest production acceptance: `TASK-TRAFFIC-04 — Peak Load — PASS / CLOSED`

## Current roadmap state

```text
TRAFFIC-00 — Traffic Section Foundation
DONE

TRAFFIC-01 — Current Network Throughput
DONE

TRAFFIC-02-READ — Historical Network Traffic Read Foundation
DONE

TRAFFIC-02 — Network Traffic History
DONE

TRAFFIC-02-PERF-01 — Historical range query remediation
DONE

TRAFFIC-03 — Period Statistics
DONE / PRODUCTION ACTIVE

TRAFFIC-04 — Peak Load Period
CLOSED / PRODUCTION PASS / ACTIVE

TRAFFIC-05 — Traffic by AP
NEXT / NOT IMPLEMENTED

TRAFFIC-06+ — NOT STARTED
```

`TRAFFIC-05 — Traffic by AP` is the next planned product increment. `NEXT` is
change-intent only and must not be described as implemented until a separate
accepted TASK proves that state.

## Production feature state — 2026-08-31

Owner-confirmed production flags:

```text
WEB_ADMIN_TRAFFIC_ENABLED=true
WEB_ADMIN_TRAFFIC_HISTORY_ENABLED=true
WEB_ADMIN_TRAFFIC_STATISTICS_ENABLED=true
WEB_ADMIN_TRAFFIC_PEAK_ENABLED=true
```

Production environment source:

```text
/etc/default/captive-portal
```

Repository defaults remain:

```text
WEB_ADMIN_TRAFFIC_ENABLED=false
WEB_ADMIN_TRAFFIC_HISTORY_ENABLED=false
WEB_ADMIN_TRAFFIC_STATISTICS_ENABLED=false
WEB_ADMIN_TRAFFIC_PEAK_ENABLED=false
```

Repository defaults and production activation are separate facts.

## Current Traffic product surface

Production Traffic contains at least:

1. Current Network Throughput;
2. Historical Network Throughput;
3. Period Statistics;
4. Peak Load.

Current layout is **production-current functional layout**, not a permanently
approved final visual composition.

Permanent UI/design state:

```text
Traffic functional implementation is accepted now.
Card rearrangement, layout changes and visual polish may happen later
through a separate UI/design stage.
```

Do not encode current card order/placement as an architectural invariant.

## Domain boundary

Network Traffic means:

```text
AP / network throughput evidence
unit = Mbps
```

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
one shared Traffic frontend coordinator
        ↓
Traffic panels
```

Forbidden:

```text
Browser → Omada
Admin request → Omada
second Traffic collector
second current-traffic calculation owner
second historical-traffic semantic owner
second Traffic frontend coordinator
browser-side recomputation of canonical analytics
```

## Current Network Throughput

Canonical endpoint:

```text
GET /admin/api/v1/sites/<site_id>/traffic/current
```

Query parameters: none.

Semantic owner: `CurrentTrafficReadService`.

Current shared policy:

```text
fresh max age = 90 seconds
stale boundary = 180 seconds
max AP skew = 60 seconds
```

Source policy:

```text
primary = wired
fallback = lan
radio excluded
```

Direction mapping:

```text
wired Download = wired_download_mbps
wired Upload   = wired_upload_mbps
lan Download   = lan_rx_mbps
lan Upload     = lan_tx_mbps
```

Backend Total is canonical. Browser does not recompute it.

## Historical Network Throughput

Canonical endpoint family:

```text
GET /admin/api/v1/sites/<site_id>/traffic/history?range=24h|7d
```

`HistoricalTrafficReadService` is the single historical Network Traffic semantic
owner. Canonical v1 source is persisted AP Observation history.

Historical range contract:

```text
24h → 5-minute buckets → 288 buckets
7d  → 15-minute buckets → 672 buckets
```

Server owns `[from_utc,to_utc)` boundaries. Browser does not construct canonical
UTC boundaries.

## Period Statistics

`TRAFFIC-03` remains current production functionality.

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

Statuses:

```text
ok
partial
insufficient_data
```

## Peak Load

`TASK-TRAFFIC-04` is current production functionality and is the temporal companion
to Period Statistics.

It answers the **when** question for the same selected History range.

Visible product facts:

```text
Peak Download + observed timestamp
Peak Upload + observed timestamp
Peak Total + observed timestamp
Busiest History Bucket
Busiest 60 Minutes
```

Unit:

```text
Mbps
```

History, Statistics and Peak use the same applied range:

```text
24h
7d
```

### Canonical Peak methods

```text
metric version:
network_traffic_peak_load.v1

peak value:
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

60-minute average:
right_endpoint_sample_hold_time_weighted.v1

hour tie:
earliest_window_start.v1
```

Peak Download, Upload and Total each retain the timestamp of the accepted sample
that produced that metric maximum. Ties choose the earliest accepted peak sample.

`Busiest History Bucket` considers canonical complete History buckets and selects
the maximum bucket Total mean; ties choose the earliest bucket start.

`Busiest 60 Minutes` is a rolling fixed 3600-second window over complete comparable
accepted sample-hold intervals. It requires one selected source family across the
winning window. It does **not** use or expose `occurrence_count`.

Peak Load statuses:

```text
ok
partial
insufficient_data
```

### Cross-product identity

Peak values exposed by Peak Load must equal the corresponding Peak values already
exposed by Period Statistics for the same applied range/evaluation.

Browser does not recompute maxima, bucket winner or rolling-hour winner.

## Shared History + Statistics + Peak request

There is no separate heavy Peak HTTP request or loader.

Canonical combined request form when Peak is enabled:

```text
GET /admin/api/v1/sites/<site_id>/traffic/history?range=24h|7d&include=statistics,peak
```

Conceptually:

```text
one History request
→ one range
→ one evaluation context
→ one read-only SQLite snapshot
→ one HistoricalTrafficReadService execution
→ History + Statistics + Peak consumers
```

No new request owner, loader, selector, collector, Omada call, DB, schema, index,
cache, rollup, QueryDeadline increase or browser-timeout increase was introduced.

## Performance invariants

`TRAFFIC-02-PERF-01` remains mandatory:

```text
requested-range bounded aggregation
+
separate bounded source-boundary/watermark lookup
```

`TRAFFIC-04` preserves the shared query deadline and browser timeout:

```text
QueryDeadline = 10s
browser request timeout = 20s
```

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
- History, Period Statistics and Peak Load share `HistoricalTrafficReadService`.
- Statistics and Peak do not create second historical algorithm owners.
- Browser does not calculate canonical Average/Peak/Peak timestamp/busiest-period facts.
- Missing/invalid/gap evidence is never silently converted to zero.
- Feature exposure flags do not start/stop Observation or shared Analytics services.

## Next step

Next planned module:

```text
TASK-TRAFFIC-05 — Traffic by AP
```

Current status:

```text
NEXT / NOT IMPLEMENTED
```
