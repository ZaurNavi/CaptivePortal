# Admin Console Traffic

Status: current production module contract
Updated: 2026-08-30
Repository baseline: `main@b92efbfabb38f912550526bc5a3d1f2f1a8ae4d6`
Repository tree: `1d8b94590848f9505e45e653384dd8a7c18d4339`
Production deployed HEAD: `b92efbfabb38f912550526bc5a3d1f2f1a8ae4d6`
Production tree: `1d8b94590848f9505e45e653384dd8a7c18d4339`
Latest production acceptance: `TASK-TRAFFIC-03 — Period Statistics — PASS / CLOSED`

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
NEXT / NOT IMPLEMENTED

TRAFFIC-05+ — NOT STARTED
```

`TRAFFIC-04` is the next planned product increment. `NEXT` is change-intent only.
It must not be described as implemented, merged or production-active until a
separate accepted TASK proves that state.

## Production feature state — 2026-08-30

Owner-confirmed production flags:

```text
WEB_ADMIN_TRAFFIC_ENABLED=true
WEB_ADMIN_TRAFFIC_HISTORY_ENABLED=true
WEB_ADMIN_TRAFFIC_STATISTICS_ENABLED=true
```

Repository defaults remain:

```text
WEB_ADMIN_TRAFFIC_ENABLED=false
WEB_ADMIN_TRAFFIC_HISTORY_ENABLED=false
WEB_ADMIN_TRAFFIC_STATISTICS_ENABLED=false
```

Repository defaults and production activation are separate facts.

## Current Traffic product surface

Production Traffic contains at least:

1. Current Network Throughput;
2. Historical Network Throughput;
3. Period Statistics.

Current layout is **production-current functional layout**, not a permanently
approved final visual composition.

Permanent UI/design state:

```text
Traffic functional implementation is accepted now.
Card rearrangement, layout changes and visual polish may happen later
through a separate UI/design stage.
```

Do not encode the current card order/placement as an architectural invariant.

## Domain boundary

Network Traffic means:

```text
AP / network throughput evidence
unit = Mbps
```

It is not:

- WAN traffic;
- Internet-only traffic;
- billing traffic;
- guest-only traffic;
- SSID traffic;
- Guest Session Traffic.

Radio is not a Site Network Traffic total source.

## Canonical architecture

Current/historical product path remains:

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

Semantic path:

```text
AdminQueryService.current_traffic_summary(...)
→ CurrentTrafficReadService.get_current_site_traffic(...)
→ serialize_current_traffic_summary(...)
```

Current shared policy:

```text
fresh max age = 90 seconds
stale boundary = 180 seconds
max AP skew = 60 seconds
```

Primary source: `wired`.
Fallback: `lan`.

Direction mapping:

```text
wired:
Download = wired_download_mbps
Upload   = wired_upload_mbps

lan fallback:
Download = lan_rx_mbps
Upload   = lan_tx_mbps
```

Backend Total is canonical. Browser does not recompute it.

## Historical Network Throughput

Canonical endpoint family:

```text
GET /admin/api/v1/sites/<site_id>/traffic/history?range=24h|7d
```

`TRAFFIC-02-READ` / `HistoricalTrafficReadService` is the single historical
Network Traffic semantic owner.

Canonical v1 source:

```text
Observation persisted AP history
```

No new collector or Traffic database exists.

Historical range contract:

```text
24h
7d
```

Server owns range boundaries. Browser does not construct canonical UTC
`[from_utc,to_utc)` boundaries.

Historical Site source-family selection preserves the accepted common-source
policy; wired/LAN are not mixed between APs inside one canonical Site sample.

## Period Statistics

`TRAFFIC-03` is current production functionality.

It answers:

```text
How much?
```

Unit:

```text
Mbps
```

Required metrics:

```text
Average Download
Average Upload
Average Total

Peak Download
Peak Upload
Peak Total
```

Statistics uses the **same selected Network History range**:

```text
24h
7d
```

History and Statistics switch together between `24h ↔ 7d`.

Statistics is not a traffic-volume (`bytes/MB/GB`) metric.

Canonical status values:

```text
ok
partial
insufficient_data
```

A production `partial` result with trustworthy numeric values plus interval
evidence is valid and must not be flattened to unavailable or zero.

### Average semantics

Period Average is interval/time-aware over accepted persisted Site rate samples.

Canonical algorithm identity:

```text
right_endpoint_sample_hold_time_weighted.v1
```

It is not:

```text
average(History bucket means)
average(all persisted samples)
raw-counter Mbps re-derivation
browser calculation
```

### Peak semantics

Canonical method:

```text
max_accepted_complete_site_sample.v1
```

Peak Download, Peak Upload and Peak Total are independent maxima over accepted
Site samples.

Permanent invariant:

```text
Peak Total
!=
Peak Download + Peak Upload
```

unless those directional peaks happened to occur in the same accepted sample.

Peak Total is the maximum observed Total of one accepted Site sample.

`TRAFFIC-03` does not expose the time/bucket of the peak. The **when** question
belongs to `TRAFFIC-04 — Peak Load Period`.

## Shared History + Statistics request

Statistics reuses the existing History request/read execution.

Conceptually:

```text
History request
+ optional statistics include
→ one range
→ one evaluation context
→ one HistoricalTrafficReadService execution
→ History + Statistics consumers
```

No independent heavy Statistics scheduler/request/scan exists.

## TRAFFIC-02-PERF-01 predecessor remediation

The accepted historical-range remediation from PR #88 remains a required
predecessor invariant:

```text
requested-range bounded aggregation
+
separate bounded source-boundary/watermark lookup
```

Do not reintroduce whole-history candidate validation for History or Statistics.

## TRAFFIC-03 performance remediation history

This section is historical engineering evidence, not current implementation state.

### Initial candidate — superseded

```text
candidate:
d96ddbc6f8685be175ee9a48da9b8e15621f2161

tree:
5e6a28950c8079d805450dc2a7ecf652a8285820

functional / V6:
PASS

production-size PERF:
FAIL

status:
SUPERSEDED / NOT CURRENT
```

The initial tree is not the accepted implementation.

Under current project governance, a candidate that fails a mandatory PERF gate
is **NOT ACCEPTED** and is not authorized for normal publication/merge/deploy.

### Final remediation candidate — accepted

```text
candidate:
79875aca61297c8de4c30b7119b15118079f26d0

tree:
1d8b94590848f9505e45e653384dd8a7c18d4339

all mandatory acceptance gates:
PASS
```

Merge PR:

```text
#89
```

Merged production commit:

```text
b92efbfabb38f912550526bc5a3d1f2f1a8ae4d6
```

The merge commit preserves the exact accepted tree:

```text
1d8b94590848f9505e45e653384dd8a7c18d4339
```

## Final TRAFFIC-03 PERF evidence

Production-size immutable snapshot:

```text
SHA256:
bf90a989f156c39cbf8fd6fd1a3f5b9f14c36f039e5a14d121b193edaa2fe5a8

size:
256995328 bytes
```

Measured matrix:

```text
H24 p50 1.259407
H24 p95 1.345084
H24 max  1.351103

S24 p50 1.278168
S24 p95 1.537511
S24 max  1.670745

H7 p50 4.980485
H7 p95 5.927953
H7 max  6.304544

S7 p50 5.570484
S7 p95 6.542208
S7 max  7.083732
```

Final acceptance:

```text
all absolute gates = PASS
all relative gates = PASS
40/40 measured requests = 200
deadlines = 0
integrity failures = 0
snapshot unchanged = YES
```

These durations are dated acceptance evidence, not system constants or runtime
SLO configuration.

## Production acceptance — TRAFFIC-03

Owner-confirmed current state:

```text
TASK-TRAFFIC-03:
PRODUCTION ACCEPTANCE PASS / CLOSED

Browser acceptance:
PASS

24h:
PASS

7d:
PASS

History ↔ Statistics synchronized range switching:
PASS
```

Production observed a truthful `partial` state with trustworthy values and
interval evidence.

## Cross-surface and ownership invariants

- Current Traffic and Home Traffic share `CurrentTrafficReadService`.
- Historical Traffic and Period Statistics share `HistoricalTrafficReadService`.
- Statistics does not create a second historical algorithm owner.
- Browser does not calculate canonical Average/Peak/Total.
- Missing/invalid/gap evidence is never silently converted to zero.
- Feature exposure flags do not start/stop Observation or shared Analytics
  acquisition/read services.

## Next step

Next planned module:

```text
TASK-TRAFFIC-04 — Peak Load Period
```

Current status:

```text
NEXT / NOT IMPLEMENTED
```

`TRAFFIC-04` answers the **when** question and must reuse the shared Network range
and existing Historical Traffic semantic owner. Exact Peak-period semantics
remain owned by its future accepted TASK.
