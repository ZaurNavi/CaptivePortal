# Admin Console Traffic

Status: current production module contract
Updated: 2026-09-03
Repository implementation baseline: `main@6425988b5b4ec5ff38bf9c67c74846c3806f668f`
Repository tree: `b669f368b0062fcb100b24758cf05e2c4b500144`
Production deployed HEAD: `6425988b5b4ec5ff38bf9c67c74846c3806f668f`
Production tree: `b669f368b0062fcb100b24758cf05e2c4b500144`
Latest production acceptance: `TASK-TRAFFIC-07 — Online Guests Traffic — COMPLETE / PRODUCTION ACTIVE`

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
DONE / PRODUCTION ACTIVE

TRAFFIC-07-READ — Current Rate backend foundation
DONE / READ FOUNDATION IMPLEMENTED

TRAFFIC-07 — Online Guests Traffic
COMPLETE / PRODUCTION ACTIVE
```

No approved next Traffic TASK is currently assigned. No `TRAFFIC-08` is
canonical change-intent.

## Production feature state — 2026-09-03

Owner-confirmed production Traffic flags include:

```text
WEB_ADMIN_TRAFFIC_ENABLED=true
WEB_ADMIN_TRAFFIC_HISTORY_ENABLED=true
WEB_ADMIN_TRAFFIC_STATISTICS_ENABLED=true
WEB_ADMIN_TRAFFIC_PEAK_ENABLED=true
WEB_ADMIN_TRAFFIC_BY_AP_ENABLED=true
WEB_ADMIN_TRAFFIC_INDEPENDENT_RANGES_ENABLED=true
WEB_ADMIN_TRAFFIC_AP_SHARE_ENABLED=true
WEB_ADMIN_TRAFFIC_ONLINE_GUESTS_ENABLED=true
```

Repository defaults remain `false`, including
`WEB_ADMIN_TRAFFIC_ONLINE_GUESTS_ENABLED=false`.

## Current Traffic product surface

Production Traffic contains:

1. Current Network Throughput;
2. Network Traffic History;
3. Period Statistics;
4. Peak Load;
5. Traffic by AP;
6. AP Traffic Share;
7. Online Guests Traffic.

Historical panels remain `24h | 7d` products with independent selected/applied
state. Current Network Throughput and Online Guests Traffic are range-insensitive.

## Domain / ownership boundary

Observation-backed Network Traffic:

```text
Observation
→ CurrentTrafficReadService / HistoricalTrafficReadService
→ Current / History / Statistics / Peak / Traffic by AP / AP Traffic Share
```

Current State-backed Online Guests Traffic:

```text
Current State
→ CurrentStateReadService
→ CurrentGuestTrafficReadService
→ Online Guests Traffic
```

`CurrentGuestTrafficReadService` is the sole Online Guests semantic owner.

No separate Online Guests collector/database exists. Online Guests calculation
does not use Observation, Visit, Visitor Registry, AuthSession, query-time Omada,
or browser-side traffic calculations.

## Online Guests Traffic

Canonical endpoint:

```text
GET /admin/api/v1/sites/<site_id>/traffic/online-guests/current
```

Pagination/capability:

```text
limit default = 50
limit maximum = 200
cursor = opaque continuation cursor
capability = admin.read.devices
```

Canonical contracts:

```text
metric = network_traffic_online_guest_current_rate.v1
population = fresh_complete_current_state_authorized_guest_scope.v1
rate = current_connection_counter_delta_interval_average.v1
baseline = nearest_previous_complete_same_site_scope_cycle.v1
continuity = omada_controller_connection_progress_v1
boundary observation = sampled_current_state_evidence.v1
unit = Mbps
```

The panel presents Online Guest, SSID, AP, Download, Upload, Total, Evidence,
Online Guest count, Population completeness, Rate Evidence, Source Health,
observed time and interval.

Online Guest means controller-reported active authorized wireless guest in the
latest accepted Current State guest scope. This is not independent evidence of
instantaneous physical RF presence.

Online Guests Traffic has no historical range selector and does not use the
historical request broker/admission guard.

## TRAFFIC-07 accepted artifact / production closure

```text
TRAFFIC-07-READ PR: #98
TRAFFIC-07 PR: #99
PR #99 head: 0d7782d93c028226f9396c2d089db76e7986a4b2
accepted / production tree: b669f368b0062fcb100b24758cf05e2c4b500144
merge / production commit: 6425988b5b4ec5ff38bf9c67c74846c3806f668f
```

Canonical status:

```text
IMPLEMENTED
→ TESTED
→ MERGED
→ PRODUCTION DEPLOYED
→ ACTIVATED
→ COMPLETE / PRODUCTION ACTIVE
```

PR #99 acceptance:

```text
Static review: PASS
Focused acceptance: 49 passed
Targeted regression: 175 passed
Central Lab V6: PASS
strict regressions: 0
Linux authenticated API PERF: PASS
payload <= 256 KiB: PASS
read-only: PASS
provider isolation: PASS
```

Production:

```text
WEB_ADMIN_TRAFFIC_ONLINE_GUESTS_ENABLED=true
captive-portal.service=active
deployment=FROM GIT
activation/acceptance=PASS
```

## Historical request broker / admission

`TrafficHistoricalRequestBroker` remains page-local intent/coalescing/response-mapping. `CaptivPortalTrafficCoordinator` remains scheduler/lifecycle owner.

Permanent invariants:

```text
max historical HTTP requests in flight from one page = 1
HISTORICAL_TRAFFIC_REQUEST_ADMISSION_GUARD_SECONDS = 10
```

Initial same-range products may coalesce; explicit panel intent outranks queued Global Refresh; same-panel pending intents collapse to latest; shared in-flight batches are not aborted because one panel is superseded; response applies only if generation and selected range remain current. Guard is measured from actual dispatch and never shortens Retry-After/backoff/lifecycle eligibility.

## TRAFFIC-06 accepted artifact / production acceptance

```text
development baseline: 022c8666ef58f0a6d4bef9dd72696199ebd5719f
accepted candidate tree: 0831ecf598b5760e8ede2e9e94a25b926480c2dd
publication commit: 1d4e373262a236cb1c6dded82fe6b9789c9110a7
PR: #96
merge commit: c5f9dc39bbf399847f147526c9c7ae15769a198c
production HEAD: c5f9dc39bbf399847f147526c9c7ae15769a198c
production tree: 0831ecf598b5760e8ede2e9e94a25b926480c2dd
accepted candidate tree = publication tree = PR head tree = merge tree = production tree
```

Acceptance gates:

```text
Tech Lead Static Review: PASS
Targeted Traffic Regression: PASS WITH REVIEWED COMPATIBILITY
candidate regressions: 0
Windows Central Lab V6-FIXED: PASS
strict regressions: 0
exact-artifact immutability: PASS
Linux production-size PERF: PASS
CORE_PERF_GATE=PASS
ALL24_CAPABILITY=PASS
G1_G2_FALLBACK_CAPABILITY=PASS
IMMUTABILITY=PASS
RESULT=PASS
```

Key PERF evidence:

```text
SH24 p95 0.614524s / max 0.698018s
SH7  p95 2.751386s / max 2.795773s
CA7  p95 3.057368s / max 3.291041s
AS7  p95 3.099320s / max 3.113963s
E24-C p95 0.740699s / max 0.830057s
ALL24 p95 0.584355s / max 0.595118s
all measured variants: 10/10 success
query_deadline=0
source_integrity=0
unexpected_5xx=0
semantic stability=PASS
```

Accepted ALL24 grouping is `history,statistics,peak,aps,apshare`. G1→G2 fallback remains accepted capability evidence but was not required for this candidate.

Immutable snapshot: `273235968` bytes, SHA256 `b65a2ce7718454571f08c474c1b59045c3da415d1e160a55725d5095e49287eb`.

Production deploy was FROM GIT. Dormant acceptance passed with AP Share disabled, then activation separately set `WEB_ADMIN_TRAFFIC_AP_SHARE_ENABLED=true`.

Post-activation runtime:

```text
captive-portal.service=active
NRestarts=0
ExecMainStatus=0
Admin Traffic API=HTTP 200
Omada webhook=HTTP 204
Observation complete=True
Observation error_count=0
Observation failure_category=None
```

Existing Omada InsecureRequestWarning and Flask development-server warning are pre-existing warnings, not TRAFFIC-06 regressions.

Owner browser acceptance: PASS. AP Traffic Share ready, applied range Last 24 hours, population 2 AP, coverage 99.9% · 2500/2500 intervals, and independent `24h → 7d → 24h` switching PASS.

Accepted 24h UI evidence:

```text
EC:75:0C:18:6F:F8 total 71.38% / download 71.38% / upload 71.43%
DC:62:79:1B:4A:68 total 28.62% / download 28.62% / upload 28.57%
Total Share = 100.00%
accepted intervals per AP = 2500
accepted seconds per AP = 86345s
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

- Current Network Throughput/Home Traffic share `CurrentTrafficReadService`.
- Historical Traffic products reuse `HistoricalTrafficReadService` and persisted Observation evidence.
- Online Guests Traffic separately uses `CurrentStateReadService` through `CurrentGuestTrafficReadService`.
- Online Guests Traffic is not a historical-range product.
- Browser does not manufacture Traffic analytics or guest current rates.
- Query-time Omada is not a source for Online Guests Traffic.
- Missing/invalid/reset/frozen evidence is never silently converted to numeric zero.
- Feature exposure flags do not create source collectors.

## Next step

```text
TRAFFIC-07 — COMPLETE / PRODUCTION ACTIVE
next Traffic TASK — NOT YET ASSIGNED
```

No approved `TRAFFIC-08` or other successor is current change-intent. A new
Traffic item becomes canonical only after separate Owner / Tech Lead approval.
