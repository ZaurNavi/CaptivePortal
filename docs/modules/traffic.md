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

The dormant Historical Traffic projection foundation is controlled separately by
`TRAFFIC_PROJECTION_ENABLED=false` and
`WEB_ADMIN_TRAFFIC_PROJECTION_READ_ENABLED=false`. It materializes only derived,
discardable Observation facts in `traffic_projection.sqlite3`; Observation remains
authoritative. Both controls require a separately approved production activation.

## Production feature state — 2026-09-01

Owner-confirmed production Traffic flags:

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

Repository defaults remain `false` for these feature flags, including `WEB_ADMIN_TRAFFIC_AP_SHARE_ENABLED=false`.

## Current Traffic product surface

Production Traffic contains:

1. Current Network Throughput;
2. Network Traffic History;
3. Period Statistics;
4. Peak Load;
5. Traffic by AP;
6. AP Traffic Share;
7. Online Guests Traffic.

Current layout is production-current functional layout, not a permanently approved final visual composition.

## Domain boundary

Network Traffic means persisted AP/network throughput evidence. Current/History/Statistics/Peak/Traffic by AP use Mbps evidence. AP Traffic Share expresses accepted contribution as fraction/percent.

It is not WAN, Internet-only, billing, guest-only, SSID or Guest Session Traffic.

## Canonical architecture

```text
Omada AP traffic primitives
→ Observation acquisition
→ persisted AP traffic facts
→ CurrentTrafficReadService / HistoricalTrafficReadService
→ AdminQueryService
→ Admin Traffic API
→ CaptivPortalTrafficCoordinator
→ TrafficHistoricalRequestBroker
→ historical product panels
```

Forbidden: browser/Admin direct Omada, second Traffic collector/database, second historical semantic owner, second scheduler/lifecycle owner, browser-side manufacture of canonical traffic analytics.

## Current Network Throughput

`GET /admin/api/v1/sites/<site_id>/traffic/current` is range-insensitive. `CurrentTrafficReadService` remains semantic owner. Current source policy remains wired primary, lan fallback, radio excluded, freshness 90s, stale boundary 180s, max AP skew 60s.

## Historical Traffic range contract

Historical products with independent selectors:

- Network Traffic History;
- Period Statistics;
- Peak Load;
- Traffic by AP;
- AP Traffic Share.

```text
24h → 5-minute buckets → 288 buckets
7d  → 15-minute buckets → 672 buckets
```

Each historical panel owns page-lifetime `selected_range`, `applied_range`, phase/request state, last successful payload, error and intent generation. Failed switches preserve the previous successful payload. Reload resets selectors to 24h. State is not persisted in localStorage/sessionStorage/cookie/URL/server state.

## Historical API current contract

Canonical endpoint:

```text
GET /admin/api/v1/sites/<site_id>/traffic/history
```

Canonical ordered projection tokens:

```text
history,statistics,peak,aps,apshare
```

`include=` remains temporary backward compatibility. `include + products`, empty, malformed, duplicate, out-of-order, whitespace or unknown products return 400. Product-scoped requests do not execute unrelated product-specific calculations. AP-only `aps` projection remains self-contained through `ap_bucket_axis`.

## Period Statistics

`TRAFFIC-03` remains production-active. Average uses `right_endpoint_sample_hold_time_weighted.v1`; Peak uses `max_accepted_complete_site_sample.v1`. Peak Total remains one accepted Site-sample maximum, not Peak Download + Peak Upload.

## Peak Load

`TRAFFIC-04` remains production-active. Canonical identities remain `network_traffic_peak_load.v1`, `max_accepted_complete_site_sample.v1`, `earliest_peak_sample_at.v1`, `cycle_finished_at`, `max_complete_history_bucket_total_mean.v1`, `earliest_bucket_start.v1`, `max_complete_rolling_3600s_average_total_sample_hold.v1`, `right_endpoint_sample_hold_time_weighted.v1`, `earliest_window_start.v1`.

## Traffic by AP

`TRAFFIC-05` remains production-active with `network_traffic_by_ap.v1` in Mbps, population `current_union_historical_validated.v1`, series `outer_history_bucket_aligned_du.v1`, AP order `ap_mac_ascending.v1`, Average `right_endpoint_ap_sample_hold_time_weighted.v1`, Peak `max_accepted_complete_ap_sample.v1`, supported population cap 12 APs.

Traffic by AP and AP Traffic Share are distinct current products: one reports per-AP Mbps evidence, the other contribution share.

## AP Traffic Share

`TRAFFIC-06` is current production functionality.

```text
metric version = network_traffic_ap_share.v1
unit = fraction
display unit = percent
share method = accepted_site_interval_integrated_ap_contribution_ratio.v1
temporal method = right_endpoint_sample_hold_time_weighted.v1
presence method = accepted_selected_source_historical_presence_in_range.v1
absence method = proven_population_member_absent_from_trusted_complete_site_sample_zero_contribution.v1
```

Permanent semantic invariant:

```text
sample count != traffic share
```

Share is accepted interval-integrated Network Traffic contribution over common comparable evidence. It is not user count, sample count, Internet share, SSID share or billing share. The panel uses its own independent 24h/7d selected/applied range and the `apshare` product projection. It reuses `HistoricalTrafficReadService` and adds no collector, Traffic DB, schema/index, cache/rollup or Omada path.

Current status family includes `ok | partial | insufficient_data | unsupported_population`. Safe current-source unavailability may produce truthful partial historical Share; malformed/contradictory current evidence and impossible pagination fail closed; generic source outage is not relabelled as an integrity failure.

## Online Guests Traffic

`TASK-TRAFFIC-07` is complete and production-active.

Canonical source path:

```text
Current State
→ CurrentStateReadService
→ CurrentGuestTrafficReadService
→ AdminQueryService
→ Admin API
→ Admin Console / Traffic / Online Guests Traffic
```

Semantic owner:

```text
CurrentGuestTrafficReadService
```

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

Canonical metric contracts:

```text
metric = network_traffic_online_guest_current_rate.v1
population = fresh_complete_current_state_authorized_guest_scope.v1
rate = current_connection_counter_delta_interval_average.v1
baseline = nearest_previous_complete_same_site_scope_cycle.v1
continuity = omada_controller_connection_progress_v1
boundary observation = sampled_current_state_evidence.v1
unit = Mbps
```

Online Guest means controller-reported active authorized wireless guest in the
latest accepted Current State guest scope. It is not independent proof of
instantaneous physical RF presence.

The panel shows Online Guest, SSID, AP, Download, Upload, Total, Evidence,
Online Guest count, Population completeness, Rate Evidence, Source Health,
observed time and interval.

The product does not use Observation, Visit, Visitor Registry, AuthSession,
query-time Omada calls or browser-side traffic calculations. No separate
collector/database was added.

Online Guests Traffic is range-insensitive and does not use historical
`TrafficHistoricalRequestBroker` / admission-guard orchestration.

### TRAFFIC-07 closure

```text
TRAFFIC-07-READ PR: #98
TRAFFIC-07 PR: #99
PR #99 head: 0d7782d93c028226f9396c2d089db76e7986a4b2
accepted / production tree: b669f368b0062fcb100b24758cf05e2c4b500144
merge / production commit: 6425988b5b4ec5ff38bf9c67c74846c3806f668f
WEB_ADMIN_TRAFFIC_ONLINE_GUESTS_ENABLED=true
captive-portal.service=active
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

## Historical request broker / admission

`TrafficHistoricalRequestBroker` remains page-local intent/coalescing/response-mapping. `CaptivPortalTrafficCoordinator` remains scheduler/lifecycle owner.

Permanent invariants:

```text
max historical HTTP requests in flight from one page = 1
HISTORICAL_TRAFFIC_REQUEST_ADMISSION_GUARD_SECONDS = 3
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

- Current Traffic and Home Traffic share `CurrentTrafficReadService`.
- All historical Traffic products, including AP Traffic Share, reuse `HistoricalTrafficReadService` and persisted Observation evidence.
- Independent panel selectors do not create independent historical semantic owners.
- `TrafficHistoricalRequestBroker` is not a second scheduler.
- `CaptivPortalTrafficCoordinator` remains scheduler/lifecycle owner.
- Browser does not manufacture Traffic analytics.
- Missing/invalid/gap evidence is never silently converted to zero.
- Feature exposure flags do not start/stop Observation or shared Analytics services.

## Next step

```text
TRAFFIC-07 — COMPLETE / PRODUCTION ACTIVE
next Traffic TASK — NOT YET ASSIGNED
```

No approved `TRAFFIC-08` or other successor is current change-intent. A new
Traffic item becomes canonical only after separate Owner / Tech Lead approval.
