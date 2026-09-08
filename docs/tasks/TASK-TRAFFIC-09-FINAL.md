# TASK-TRAFFIC-09 — Consolidated Traffic Evidence

Status: COMPLETED / PRODUCTION ACTIVE
Updated: 2026-09-08

## Canonical closure

```text
TASK-TRAFFIC-09=COMPLETED
TASK_TRAFFIC_09_PRODUCTION=ACTIVE
TASK_TRAFFIC_09_PRODUCTION_SMOKE=PASS
```

Architecture/specification, implementation, Windows and Linux acceptance,
production-size PERF, publication, merge, deploy, activation, authenticated
production smoke and Owner manual Web UI verification are complete.

## Git / artifact identity

```text
repository=ZaurNavi/CaptivePortal
PR=#106 — TASK-TRAFFIC-09: Consolidated Traffic Evidence
previous baseline=f57d3550ffd2e1e48f24092666d861a959c57e40
implementation commit=6729e5bc45c810423cf739ebd8fc2685f6098a3d
accepted implementation tree=2766139c83965dcf2f80e0c8084b3fb363dbd781
merge / production commit=e32ade378bdbfc9f8458db9c18221958f4552718
```

The production/current implementation baseline for this task is:

```text
e32ade378bdbfc9f8458db9c18221958f4552718
```

## Product position

Admin → Traffic keeps the eight existing Traffic products.

After them, TASK-TRAFFIC-09 adds a separate area:

```text
TRAFFIC EVIDENCE
```

Purpose:

```text
consolidate existing evidence
+ status
+ freshness
+ coverage
+ source health
+ reasons
+ provenance
```

Traffic Evidence does not introduce a new business quality metric.

Forbidden interpretation:

```text
no synthetic overall score
no universal GOOD/BAD
no normalized quality score
no new quality algorithm
```

Permanent rule:

```text
missing / unknown / stale / insufficient / unavailable != 0
```

## Canonical Evidence products

Exact ordered product IDs:

```text
1. current
2. history
3. statistics
4. peak
5. aps
6. apshare
7. online_guests
8. completed_sessions
```

Production smoke confirmed all eight for both `24h` and `7d` with:

```text
exposure=enabled
delivery=available
failure=None
```

## Semantic owners

Traffic Evidence owns no Traffic business semantics.

```text
current
→ CurrentTrafficReadService

history
→ HistoricalTrafficReadService

statistics
→ HistoricalTrafficReadService

peak
→ HistoricalTrafficReadService

aps
→ HistoricalTrafficReadService

apshare
→ HistoricalTrafficReadService

online_guests
→ CurrentGuestTrafficReadService

completed_sessions
→ CompletedGuestSessionTrafficReadService
```

Canonical architecture:

```text
accepted semantic owners
→ TrafficEvidenceAggregator
→ bounded application aggregation
→ safe Admin serialization
→ admin.read.v1
→ UI
```

`TrafficEvidenceAggregator` is composition-only.

## Read architecture

Maximum canonical read groups per request:

```text
1. Current
2. Historical
3. Online Guests
4. Completed Sessions
```

Historical Evidence products are combined into one bounded Historical read.

Completed Sessions Evidence reads:

```text
limit=100
cursor=None
```

It is explicitly first-page scope and must preserve truthful:

```text
returned_count
has_more
```

Permanent read boundaries:

```text
no N+1
no query-time Omada/provider polling
no new collector
no new polling loop
no new DB
no new persistence
no new schema
no new acquisition process
no new worker
no new scheduler
```

## Evidence range

Traffic Evidence owns its own selector:

```text
24h
7d
default=24h
```

It does not change the selected/applied ranges of existing Traffic products.

## API

Canonical endpoint:

```text
GET /admin/api/v1/sites/<site_id>/traffic/evidence?range=24h|7d
```

Contracts:

```text
outer API contract=admin.read.v1
inner Evidence contract=admin.traffic.evidence.v1
```

Required capabilities:

```text
admin.read.overview
admin.read.devices
```

Both capabilities are required.

When the feature is OFF, the Evidence feature route is unavailable.

## Feature flag

Repository default:

```text
WEB_ADMIN_TRAFFIC_EVIDENCE_ENABLED=false
```

Production:

```text
WEB_ADMIN_TRAFFIC_EVIDENCE_ENABLED=true
```

Production activation date:

```text
2026-09-08
```

## Production deployment

```text
VM=192.168.0.202
application=/opt/CaptivePortal
service=captive-portal.service
production commit=e32ade378bdbfc9f8458db9c18221958f4552718
```

Post-deploy / activation:

```text
service=active
SubState=running
NRestarts=0
listener=127.0.0.1:8088
root readiness HTTP 400=expected without Omada parameters
startup Evidence errors=none
```

## Authenticated production smoke

Real Admin authentication flow:

```text
Admin login GET=200
Admin login POST=302
authenticated session=200
Traffic page=200
Evidence UI=PASS
Evidence 24h=200
Evidence 7d=200
logout=302
```

Contract validation for both ranges:

```text
api_version=admin.read.v1=PASS
contract_version=admin.traffic.evidence.v1=PASS
range=PASS
exact 8 products=PASS
canonical product_id validation=PASS
```

Final:

```text
TASK_TRAFFIC_09_PRODUCTION_SMOKE=PASS
TASK_TRAFFIC_09_PRODUCTION=ACTIVE
```

Owner manually verified the Web UI and reported no discovered visual/functional
problem in the new Evidence area.

## Official production-size PERF

Immutable production-size snapshot:

```text
approx size=572 MiB
sources=observations,visits,traffic_projection,current_state,visitor_registry
```

24h:

```text
runs=10
p95=0.0730241s
max=0.0730241s
max response=4813 bytes
HTTP failures=0
deadline failures=0

threshold p95<=5s
threshold max<=10s
```

7d:

```text
runs=10
p95=0.0724418s
max=0.0724418s
max response=4806 bytes
HTTP failures=0
deadline failures=0

threshold p95<=7s
threshold max<=12s
```

Payload requirement:

```text
<=65536 bytes
PASS
```

## Read-call PERF contract

Across 20 Evidence requests:

```text
current_site_calls=20
current_ap_calls=0
historical_calls=20
online_calls=20
completed_calls=20

provider_calls=0
writes=0
collection_cycles=0

source DB fingerprints=UNCHANGED
```

## Acceptance

Windows:

```text
Windows Central Full=PASS
regressions=0
```

Linux:

```text
Linux Full=PASS WITH BASELINE EXCEPTIONS
2921 passed
1 skipped
3 known baseline failures
0 new failures
0 regressions
```

The three failures are existing baseline exceptions and are not
TASK-TRAFFIC-09 regressions.

Official production-size PERF:

```text
PASS
```

## Final decision

```text
Architecture/specification=accepted
Implementation=accepted
Windows acceptance=PASS
Linux acceptance=PASS WITH BASELINE EXCEPTIONS
Official production-size PERF=PASS
Publication=PASS
PR=merged
Production deploy=PASS
Production activation=PASS
Authenticated production smoke=PASS
Owner manual Web UI verification=PASS

TASK-TRAFFIC-09=COMPLETED
TASK_TRAFFIC_09_PRODUCTION=ACTIVE
```

No next Traffic TASK is currently assigned.

Earlier R1/R2/R3/R4 task material remains valid execution history only and does
not override this current authoritative production status.
