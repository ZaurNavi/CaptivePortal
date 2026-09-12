# Deployment

Status: current contract; production details remain host-verified
Updated: 2026-09-11
Current repository implementation baseline: `main@7472d67274ea5aaea2a20df6b613b78d5bb70f42`
Confirmed production deployed HEAD: `7df71a8e807efd74b123117e78cb8d992c190fa1`
Confirmed production tree: `8f1342f0a0f1e8242642161e02b2f3276e6ddf51`

## Repository vs production

Repository establishes code/default contracts. It does not prove current
production env values or current runtime health.

Never print production secret values.

## Core precondition

Required Omada environment:
`OMADA_URL`, `OMADA_ID`, `OMADA_CLIENT_ID`, `OMADA_CLIENT_SECRET`.

## Permanent promotion and delivery invariant

Canonical normal flow:

```text
Coder implementation / patch
        ↓
Central Lab exact materialization
        ↓
focused / targeted acceptance
        ↓
Central Lab full regression
        ↓
all other mandatory TASK/release gates
        ↓
Linux / production-compatible / production-size PERF when required
        ↓
ACCEPTED CANDIDATE
        ↓
publication commit
        ↓
GitHub branch / PR
        ↓
verified publication/PR/merge tree identity
        ↓
Owner-authorized merge
        ↓
production deploy FROM GIT
        ↓
separate production activation
        ↓
production acceptance
```

Short invariant:

```text
Patch → Lab.
All mandatory gates → PASS.
Accepted candidate → Git.
Git → Production.
Activation → separate step.
```

## Acceptance before Publication

A candidate is **NOT ACCEPTED** while any mandatory TASK/FINAL/release gate is
FAIL or PENDING.

Mandatory gates may include functional, targeted, full/V6, Linux compatibility,
production-size PERF/capacity, migration/schema, security/browser or other
explicit acceptance.

A mandatory gate must not require normal GitHub publication merely as transport.
Use a controlled acceptance environment and exact tree identity.

If production-size data is needed before publication, use an isolated
production-compatible Lab plus a consistent immutable/read-only data snapshot.
The production application checkout/service/DB must not be changed.

TEST-ONLY / EXPERIMENTAL Git publication before acceptance requires explicit
Owner + Tech Lead authorization and is not accepted/mergeable/deployable.

## Git is the production code delivery boundary

Normal production application code source:

```text
Git repository
+
explicit verified target SHA/tree
```

Normal deploy uses:

```text
git fetch
verify target SHA/tree
controlled checkout/update from Git
```

Forbidden as normal production code delivery:

- local patch;
- SCP patch;
- copied source files;
- workstation ZIP/archive;
- manual source replacement;
- Central Lab worktree;
- Coder worktree.

Direct patch/source transfer is emergency-only with explicit Owner + Tech Lead
authorization for the incident and mandatory later Git/repository reconciliation.

## Chain-of-custody

Expected, where merge strategy preserves tree:

```text
accepted candidate tree
=
publication commit tree
=
PR head tree
=
accepted merge tree
```

A production/test-file change after acceptance creates a new candidate tree and
requires Tech Lead to determine/re-run the necessary acceptance gates.

A LAB ONLY commit is an immutable test artifact only. It is not pushed and is
not a production source.

## Deploy model

Implementation, publication, deployment and activation are distinct actions.

A deploy TASK specifies target, verified Git commit/tree, backup, config change,
required acceptance evidence, health checks, rollback and Owner authorization.

Repository feature defaults being false intentionally support dormant code deploy
before separate activation.

## Current runtime startup/shutdown

Use `project-inventory.md` for current composition order.

Independent module failure must not break guest authorization where core auth
dependencies remain healthy.

First-restart evidence must be preserved for startup/retry changes; a second
restart must not mask a first-start defect.

## Testing responsibility

Detailed acceptance ownership: `testing.md`.

Coder supplies only focused/minimal TASK/module evidence.

Tech Lead defines mandatory gates and exact acceptance artifact.
Owner physically operates official Central Lab.
Owner + Tech Lead issue official PASS/FAIL.

All mandatory pre-publication gates must PASS before the normal publication
commit/PR path.

## Test / production environment boundary

Production CaptivPortal VM:

```text
192.168.0.202
Ubuntu 22.04.x
```

Permanent invariant:

```text
PRODUCTION IS NOT AN ACCEPTANCE OR PERFORMANCE TEST HOST.
```

Linux/pre-production/PERF gates use the existing dedicated laptop WSL/Linux Lab
by default. Production is reserved for runtime, read-only inspection, approved
snapshot/copy procedures, post-deploy validation and specifically authorized
production tests.

Production-like acceptance data should flow:

```text
production source
→ safe/read-only snapshot or approved copy
→ dedicated WSL/Linux Lab
→ isolated candidate DB/output
```

See:
- `testing-environments.md`;
- `operations-command-lessons-learned.md`.

## Traffic production checkpoint — 2026-09-08

Owner-confirmed current state:

```text
repository / production HEAD:
e32ade378bdbfc9f8458db9c18221958f4552718

repository / production tree:
2766139c83965dcf2f80e0c8084b3fb363dbd781

captive-portal.service:
active
```

Current production Traffic surface:

```text
Current Network Throughput
Online Guests Traffic
Completed Guest Session Traffic
Network Traffic History
Period Statistics
Peak Load
Traffic by AP
AP Traffic Share
TRAFFIC EVIDENCE (standalone consolidated evidence area)
```

Production flags:

```text
WEB_ADMIN_TRAFFIC_ENABLED=true
WEB_ADMIN_TRAFFIC_HISTORY_ENABLED=true
WEB_ADMIN_TRAFFIC_STATISTICS_ENABLED=true
WEB_ADMIN_TRAFFIC_PEAK_ENABLED=true
WEB_ADMIN_TRAFFIC_BY_AP_ENABLED=true
WEB_ADMIN_TRAFFIC_INDEPENDENT_RANGES_ENABLED=true
WEB_ADMIN_TRAFFIC_AP_SHARE_ENABLED=true
WEB_ADMIN_TRAFFIC_ONLINE_GUESTS_ENABLED=true
WEB_ADMIN_TRAFFIC_COMPLETED_SESSIONS_ENABLED=true
WEB_ADMIN_TRAFFIC_EVIDENCE_ENABLED=true
```

Repository defaults remain false, including `WEB_ADMIN_TRAFFIC_AP_SHARE_ENABLED=false`.

## TRAFFIC-06 deployment / activation history

```text
development baseline: 022c8666ef58f0a6d4bef9dd72696199ebd5719f
accepted tree: 0831ecf598b5760e8ede2e9e94a25b926480c2dd
publication commit: 1d4e373262a236cb1c6dded82fe6b9789c9110a7
PR: #96
merge / production commit: c5f9dc39bbf399847f147526c9c7ae15769a198c
production tree: 0831ecf598b5760e8ede2e9e94a25b926480c2dd
```

Deployment was performed **FROM GIT** without SCP/manual source replacement.

```text
dormant deploy with AP Share disabled → PASS
separate WEB_ADMIN_TRAFFIC_AP_SHARE_ENABLED=true activation → PASS
production browser/product acceptance → PASS
```

Post-activation:

```text
NRestarts=0
ExecMainStatus=0
Admin Traffic API=HTTP 200
Omada webhook=HTTP 204
Observation complete=True
Observation error_count=0
Observation failure_category=None
```

Existing Omada `InsecureRequestWarning` and Flask development-server warning are pre-existing and are not TRAFFIC-06 regressions.

## TRAFFIC-06 acceptance history

```text
Tech Lead Static Review = PASS
Targeted Traffic Regression = PASS WITH REVIEWED COMPATIBILITY
candidate regressions = 0
Windows Central Lab V6-FIXED = PASS
strict regressions = 0
exact-artifact immutability = PASS
Linux production-size PERF = PASS
CORE_PERF_GATE=PASS
ALL24_CAPABILITY=PASS
G1_G2_FALLBACK_CAPABILITY=PASS
IMMUTABILITY=PASS
RESULT=PASS
```

Accepted ALL24 product group: `history,statistics,peak,aps,apshare`.
## Production architecture outcome

The accepted RANGE-01 remediation did **not** increase the Admin query
deadline, browser timeout or Admin concurrency.

Preserved:

```text
WEB_ADMIN_MAX_QUERY_DURATION_SECONDS=10
Traffic browser request timeout=20s
Admin concurrency=unchanged
```

Accepted remediation:
- canonical product-scoped `products=` requests;
- independent panel intent;
- at most one historical HTTP request in flight;
- sequential historical admission;
- 10-second admission guard.

Current production baseline after `TASK-ADMIN-PROD-BASELINE-01` (2026-09-05):

```text
Admin concurrency=4
Admin query deadline=25s
dependent request timeouts=30s
historical admission guard=3s
```

## TRAFFIC-RANGE-01 production-size acceptance

Linux §97 PERF:

```text
PASS
```

A7 hard evidence:

```text
p50 2.444160s
p95 2.469994s
max  2.472858s
query_deadline=0
source_integrity=0
unexpected 5xx=0
```

B24 ↔ C24 semantic identity: PASS.

Immutable snapshot:

```text
bytes=273235968
SHA256=b65a2ce7718454571f08c474c1b59045c3da415d1e160a55725d5095e49287eb
```

The reviewed Windows SQLite infinity compatibility case is known compatibility,
not a TASK regression.

## TRAFFIC-07 deployment / activation history

Implementation layers:

```text
PR #98 — TRAFFIC-07-READ / CurrentGuestTrafficReadService read foundation
PR #99 — Admin: add Online Guests Traffic
```

Final production artifact:

```text
PR #99 head: 0d7782d93c028226f9396c2d089db76e7986a4b2
accepted / production tree: b669f368b0062fcb100b24758cf05e2c4b500144
merge / production commit: 6425988b5b4ec5ff38bf9c67c74846c3806f668f
```

Deployment was performed **FROM GIT**.

Canonical closure:

```text
IMPLEMENTED
→ TESTED
→ MERGED
→ PRODUCTION DEPLOYED
→ ACTIVATED
→ COMPLETE / PRODUCTION ACTIVE
```

Production activation:

```text
WEB_ADMIN_TRAFFIC_ONLINE_GUESTS_ENABLED=true
captive-portal.service=active
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

Online Guests Traffic reads persisted Current State only. No separate collector,
Traffic DB, schema migration, Observation fallback or query-time Omada path was
introduced.

## TRAFFIC-08 deployment / activation history

Canonical implementation:

```text
TASK: TASK-TRAFFIC-08 — Completed Guest Session Traffic
parent baseline: 3761981f4b1ec30b330abe1eec1713f15191c711
accepted implementation commit: 8cfe30c2bcb13bf3ca7e001238991abd5943ea08
accepted / production tree: 1161739c6b4fe90fa08928556746a5a4ea6af4cd
PR: #104
merge / production commit: df91355a99d2561abc9c4d6d4bb6f5a968d327b3
cumulative R6 patch SHA256: 6077ea09f6f1421d43f2602cbea6beeae436faf5dc19a032ed520cf348efbbfa
```

Production host / checkout:

```text
host: 192.168.0.202
application: /opt/CaptivePortal
service: captive-portal.service
checkout: detached HEAD df91355a99d2561abc9c4d6d4bb6f5a968d327b3
worktree: CLEAN
```

Deployment preserved the normal two-step boundary:

```text
dormant deploy with WEB_ADMIN_TRAFFIC_COMPLETED_SESSIONS_ENABLED=false → PASS
separate Owner-authorized activation to true → PASS
startup/readiness → PASS
production HTTP/Admin/API verification → PASS
```

Final production flag:

```text
WEB_ADMIN_TRAFFIC_COMPLETED_SESSIONS_ENABLED=true
```

The flag was verified both in `/etc/default/captive-portal` and in the live
production process environment.

Production smoke on Site `6a64f17630da7c70d232187a`:

```text
GET  /admin/login = 200
POST /admin/login = 302
GET  /admin/sites/6a64f17630da7c70d232187a/traffic = 200
GET  /admin/api/v1/sites/6a64f17630da7c70d232187a/traffic/completed-sessions = 200
COMPLETED_SESSIONS_PANEL=FOUND
COMPLETED_SESSIONS_HEADING=FOUND
API_PARSE=PASS
```

Final observed live API sample:

```text
ROOT_STATUS=partial
VISIT_SOURCE=healthy
OBSERVATION_SOURCE=healthy
RETURNED_COUNT=100
NEXT_CURSOR=True
partial=94
insufficient_data=6
NUMERIC_TOTAL_ROWS=94
API_RESPONSE_BYTES=75316
```

`ROOT_STATUS=partial` is valid evidence quality, not a product error. Both source
roots were healthy and the live Observation stream continued to change individual
Visit evidence between smoke requests.

No projection rebuild/schema/index/source mutation was part of TRAFFIC-08.
`historical_traffic_projection.v1` is not the source of this product.

Rollback points retained:

```text
code rollback: 6fbc3736085be9d0538d893b6e9569ff490ef7f4
pre-dormant env: /etc/default/captive-portal.pre-traffic08-20260906-233314
pre-activation env: /etc/default/captive-portal.pre-traffic08-activation-20260906-233650
```

Rollback is not currently required.

## TRAFFIC-09 deployment / activation history

```text
TASK=TASK-TRAFFIC-09 — Consolidated Traffic Evidence
previous baseline=f57d3550ffd2e1e48f24092666d861a959c57e40
accepted implementation=6729e5bc45c810423cf739ebd8fc2685f6098a3d
accepted / production tree=2766139c83965dcf2f80e0c8084b3fb363dbd781
PR=#106
merge / production commit=e32ade378bdbfc9f8458db9c18221958f4552718
```

Production:

```text
host=192.168.0.202
application=/opt/CaptivePortal
service=captive-portal.service
WEB_ADMIN_TRAFFIC_EVIDENCE_ENABLED=true
TASK_TRAFFIC_09_PRODUCTION=ACTIVE
```

Post-deploy / activation health:

```text
service=active
SubState=running
NRestarts=0
listener=127.0.0.1:8088
root readiness HTTP 400=expected without Omada parameters
startup Evidence errors=none
```

Authenticated production smoke:

```text
Admin login GET=200
Admin login POST=302
authenticated session=200
Traffic page=200
Evidence UI=PASS
Evidence 24h=200
Evidence 7d=200
logout=302

api_version=admin.read.v1 → PASS
contract_version=admin.traffic.evidence.v1 → PASS
range contract → PASS
exact 8 products → PASS
canonical product_id validation → PASS

TASK_TRAFFIC_09_PRODUCTION_SMOKE=PASS
TASK_TRAFFIC_09_PRODUCTION=ACTIVE
```

For both `24h` and `7d`, all eight products were present with:

```text
exposure=enabled
delivery=available
failure=None
```

Owner manual browser verification: PASS.

Official production-size PERF used an immutable five-SQLite-DB snapshot of
approximately 572 MiB.

```text
24h: 10 runs; p95=max=0.0730241s; max response=4813 bytes
7d:  10 runs; p95=max=0.0724418s; max response=4806 bytes
HTTP failures=0
deadline failures=0
payload <=65536 bytes=PASS
```

Thresholds were 5s/10s for 24h p95/max and 7s/12s for 7d p95/max.

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

No new DB, collector, polling loop, scheduler, worker, persistence/schema or
query-time Omada path was introduced.

## DEVICE-CARD-01 deployment / activation history

```text
TASK=TASK-DEVICE-CARD-01 — Current Device Context
PR=#108
PR base=3eac6f13d5f3966574f6d1b0a10f531d988f91ec
implementation commit=1a3f2b8a844f2ce1c26cbdd9e4c44d17a201ac14
accepted / production tree=8f1342f0a0f1e8242642161e02b2f3276e6ddf51
merge / production commit=7df71a8e807efd74b123117e78cb8d992c190fa1
previous production runtime=e32ade378bdbfc9f8458db9c18221958f4552718
```

Production:

```text
host=192.168.0.202
application=/opt/CaptivePortal
service=captive-portal.service
WEB_ADMIN_DEVICE_CURRENT_CONTEXT_ENABLED=true
```

Rollout preserved the normal two-step feature boundary:

```text
1. fast-forward deploy to 7df71a8e807efd74b123117e78cb8d992c190fa1
2. start/smoke with WEB_ADMIN_DEVICE_CURRENT_CONTEXT_ENABLED=false
3. separate activation to WEB_ADMIN_DEVICE_CURRENT_CONTEXT_ENABLED=true
```

Final result:

```text
PRODUCTION DEPLOY=PASS
PRODUCTION ACTIVATION=PASS
captive-portal.service=active
rollback required=no
Owner manual Device Detail verification=PASS
```

No new DB schema, index, migration or write path was deployed by this feature.
No Device Detail request-time Omada/Loki/Grafana/external Analytics path was
introduced.

Current Device Context production semantics include:

```text
fresh complete present → online
fresh complete absent  → offline
stale/unavailable/untrusted → unknown
traffic technical failure → Current State retained
Current State execution failure → Current endpoint controlled 503
numeric 0 Mbps → valid value
```

The follow-on `TASK-WEB-DEVICE-UI-01` is not part of this production rollout and
must not be represented as deployed/current until separately accepted.

## Projection lifecycle P0 production recovery — 2026-09-11

Artifact:

```text
TASK=TASK-TRAFFIC-PROJECTION-LIFECYCLE-CONSISTENCY-01
accepted implementation=FINAL-R5 + FIX-1
PR=#111
accepted head=a0dc02d5ae0ff16c250cf46a7e7a610c24e6f433
accepted tree=3950df6d400049ed16a823032c6740396cd61137
merge / production=7472d67274ea5aaea2a20df6b613b78d5bb70f42
```

Before mutation:

```text
Site=6a64f17630da7c70d232187a
status=diverged
last_error_category=source_identity
projection_revision=88955
traffic-projection.service=inactive + disabled
writer lock=free
Observation=continuing
captive-portal.service=active
```

Forensic backup created before repair:

```text
/home/admin/captivportal-recovery/projection-incident-20260911-112820
```

It preserved SQLite-consistent Projection backup, raw DB/WAL/SHM, writer-lock
snapshot, manifest, Site-state snapshot and SHA256 evidence.

Fixed deploy proof:

```text
clean repository=PASS
HEAD=7472d67274ea5aaea2a20df6b613b78d5bb70f42
tree=3950df6d400049ed16a823032c6740396cd61137
compileall=PASS
import smoke=PASS
loaded artifact identity=PASS
captive-portal.service=active
Projection worker intentionally remained inactive + disabled
```

An interactive-shell `repair-site` attempt failed closed with:

```text
TRAFFIC_PROJECTION_ENABLED must be true
```

No mutation began. Recovery then used a transient systemd unit reproducing the
canonical EnvironmentFile/User/Group/WorkingDirectory.

First durable repair quantum:

```text
REPAIR_RC=0
projection_revision 88955 → 88956
status=rebuilding
last_error_category=repair_delete
PRAGMA quick_check=ok
writer lock=FREE
```

The permanent worker was started while still disabled and loaded exact artifact
`7472d67274ea5aaea2a20df6b613b78d5bb70f42` / `3950df6d400049ed16a823032c6740396cd61137`. It automatically continued persisted repair.

Delete progress included:

```text
34342 → 32642 → 30942 → 27742 → ...
```

then automatically transitioned to rebuild/reconcile/deep-audit.

Final acceptance:

```text
projection_revision=123634
status=healthy
last_error_category=NULL
projection_head_utc=2026-09-11T13:18:00.739Z
source_head_utc=2026-09-11T13:18:00.739Z
backlog_cycle_count=0
PRAGMA user_version=1
PRAGMA quick_check=ok
Historical Web panels=PASS
```

After final proof:

```text
systemctl enable traffic-projection.service
traffic-projection.service=active + enabled
rollback=not required
P0 incident=closed
```

## Feature activation

Activation remains Owner-controlled and separate from code deployment.

For Traffic, the current production flags above are activation facts, not
repository defaults.

## Rollback

Prefer feature disable first where safe, then restart/health verification, then
approved code/config/data restore if required.

Never delete audit/history to make rollback appear clean.

## Infrastructure boundary

systemd, reverse proxy, Alloy, Loki and Grafana require their own
deploy/infrastructure authorization.
