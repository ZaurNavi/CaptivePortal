# Deployment

Core/CAPPORT optional deployment-owned bind/Site/origin/guest-scope inputs are
documented in [configuration](configuration.md#corecapport-deployment-owned-startup-configuration).
Code acceptance is separate from Captiv-Prod SysAdmin D01 interface/TLS/routing,
D02 NPM-only isolation/header sanitization and D03 actual Omada permissions.
These target gates are not claimed passed; no old-VM reconfiguration or data migration.

Status: current contract; production details remain host-verified
Updated: 2026-10-14

<!-- NETWORK-INTELLIGENCE-V1:BEGIN -->
## Network Intelligence V1 production processes

Network Intelligence uses independently supervised auxiliary services.

```text
fingerprint-suricata.service
        ↓ DTI EVE
network-metadata.service
        ↓ source metadata SQLite
network-metadata-projection.service
        ↓ recognition feed / projection
network-service-recognition.service
        ↓ materialized Service Intelligence SQLite

fingerprint-sensor.service
        ↓ trusted DHCP temporal attribution
network-metadata-projection.service

captive-portal.service
        ← NI-03 projection read
        ← NI-04 materialized read
```

Current production service entrypoints:
- network-metadata.service → python3 -m app.network_metadata.cli run
- network-metadata-projection.service → python3 -m app.network_metadata_projection.cli run
- network-service-recognition.service → python3 -m app.network_service_recognition.cli run
- fingerprint-sensor.service → python -m app.device_fingerprint_sensor.cli run
- fingerprint-suricata.service → Suricata AF_PACKET on enp8s0
- captive-portal.service → run.py

Ordering is not a hard guest-auth dependency. A NI worker can be unavailable or
lagging without making Omada/CAPPORT authorization unavailable.

Current stores are migrated/validated by their owning services; historical
NI-02B/NI-04 release/backfill documents are retained for provenance and rollback
reasoning but the current runtime contract is
[modules/network-intelligence.md](modules/network-intelligence.md).
<!-- NETWORK-INTELLIGENCE-V1:END -->
Current repository implementation baseline: `main@27087766d3f2e104a44da3f36aa6e72a082b12de`
Confirmed production deployed HEAD: `27087766d3f2e104a44da3f36aa6e72a082b12de`
Confirmed production tree: `3fe941f1962e6df72d102ba36da60bf25f3bd70a`

## Repository vs production

Repository establishes code/default contracts. It does not prove current
production env values or current runtime health.

Never print production secret values.

## Fingerprint evidence auxiliary service

Task-01 publication does not deploy or activate the service. Before any future
checkout/artifact mutation, `fingerprint-evidence.service` must be stopped if it
exists or is running. After a controlled update, restart only when separately
authorized and verify the loaded SHA/tree. Never mutate the checkout while this
artifact-owned auxiliary process remains alive. TLS, firewall, producer secrets,
systemd provisioning, database creation and activation remain Owner-controlled.

<!-- DEVICE-FINGERPRINT-PRODUCTION-KB:BEGIN -->
## Device Fingerprint production deployment

Current production checkpoint is the document header commit/tree.

Confirmed final Task-06 production state:

```text
captive-portal.service = active
fingerprint-classification.service = active
TASK-DEVICE-FINGERPRINT-06 = PRODUCTION PASS / DEPLOYED
```

Device Fingerprint domain stores:

```text
/opt/CaptivePortal/data/device_fingerprint_evidence.sqlite3
/opt/CaptivePortal/data/device_fingerprint_classification.sqlite3
/opt/CaptivePortal/data/device_fingerprint_control_plane.sqlite3
/opt/CaptivePortal/data/device_fingerprint_integration.sqlite3
```

Current canonical SnapshotExecutionPolicy memory guard is 1 GiB
(`process_memory_guard_bytes=1073741824`). This is a process-RSS guard, not a RAM
reservation.

`fingerprint-classification.service` is the durable Task-05 consumer. It uses
claim/lease/retry state and the active admitted ClassificationRuntimeProfile;
it does not open an Omada/controller listener.

Permanent production rules:

```text
exact code comes from verified Git SHA/tree
no local production source patch
no full pytest on production
activation is explicit and separate where applicable
historical failed integration/classification rows remain evidence
```
<!-- DEVICE-FINGERPRINT-PRODUCTION-KB:END -->

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

Mandatory gates may include functional, targeted, the current official Central Lab full-regression gate, Linux compatibility,
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

At DEVICE-CARD-01 rollout time the UI follow-on was not part of that artifact. It later closed separately through PR #110 and is now production-active.

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

## WEB-ASSET-LIBRARY-01 production history — 2026-09-12

Initial implementation:

```text
PR #113
accepted=0b3a692684d5d87ca7b96cf75c722dda7e2e8cf3
merge=5d1a590d1d575eeea8148ca868b9de5183c0fff5
6 files / +39/-1
```

Real production data exposed a presentation-only case mismatch:
`device_type=android` did not satisfy the original exact `"Android"` predicate.

Production FIX:

```text
patch SHA256=c11bba2544124bc448f1d1a63a295dda479f0ab81cd430e2dbd6cc829509189b
baseline=5d1a590d1d575eeea8148ca868b9de5183c0fff5
accepted=d207e048f0fcdec685d3bae1f8497fdbdcd611d4
PR #114
merge / production=043a13bc1e3aa3353e27af1859dc0bb698df4955
tree=c2a9a01b2f8507c192fe2ef034ed4b9c850deed4
4 files / +68/-23
```

Delivery proof:

```text
captive-portal.service=ACTIVE
admin.js=HTTP 200
android.svg=HTTP 200
android.svg SHA256=2f2411f1f05522e90049f8cbb06105fb553057efeadf772cdcc3ae24bbc8a6cc
service restart for FIX=NOT REQUIRED
Owner production visual acceptance=PASS
```

No backend/API/data/security contract changed.

## TASK-TEST-BASELINE-CLEANUP-01 production deployment — 2026-09-12

```text
PR #116=MERGED
publication=ef3e8ca20e2303c29437c6c087919a6715afac96
accepted baseline=75df5af1500ebcaf7d4950abccbaabc0a03610e1
merge / production HEAD=c1dc3344bc778a32cdc6b0edce278ee40b287c29
accepted / merged / production tree=0563f58cf2a5c961e1dedb52cfa2b4b298dd2c1c
previous production=043a13bc1e3aa3353e27af1859dc0bb698df4955
production worktree=CLEAN
```

The accepted tree identity was preserved across candidate, publication, merge
and production.

This TASK was not fully test-only: `app/analytics/source_gateway.py` changed and
is used by CaptivPortal Analytics and the Traffic Projection source path.

Activation therefore restarted:

```text
traffic-projection.service
captive-portal.service
```

Not required:

```text
DB migration=NO
schema change=NO
configuration change=NO
feature flag change=NO
systemd unit change=NO
daemon-reload=NO
```

Production acceptance:

```text
traffic-projection.service=active
traffic projection artifact_sha=c1dc3344bc778a32cdc6b0edce278ee40b287c29
traffic projection artifact_tree=0563f58cf2a5c961e1dedb52cfa2b4b298dd2c1c
projection status=healthy
backlog_cycle_count=0

captive-portal.service=active
captive portal artifact_sha=c1dc3344bc778a32cdc6b0edce278ee40b287c29
captive portal artifact_tree=0563f58cf2a5c961e1dedb52cfa2b4b298dd2c1c
analytics.api_runtime_active=observed
127.0.0.1:8088=LISTEN
HTTP readiness=400
```

HTTP `400` on `/` without Omada request parameters is expected readiness
behavior.

Startup lesson:

```text
systemd active != HTTP readiness
```

The first probe may see `HTTP 000` while the same PID is still progressing
through normal startup composition. Do not perform a second restart solely
because the listener has not appeared yet; first check startup progress and wait
for bounded listener/readiness evidence.

Existing `urllib3 InsecureRequestWarning` messages for Omada HTTPS
`192.168.0.222` pre-date this deployment and are not a regression of this TASK.

## Device presentation / normalization production chain — 2026-09-13

The previous full KB publication was PR #117. Three implementation baselines then
advanced before this reconciliation:

```text
PR #118 -> Home Online Devices presentation
merge=2d87fd6d56f969492318e21c809086576b2b1ab1

PR #119 -> Canonical Device Type foundation
merge=144c8a922b4431293fdc1d4bb57bed29a8402f6b
tree=2349838d7e524efd3fb2e0433a7111553f195e71

PR #120 -> Device Type + SNR presentation
merge / current production=3dc85735ddf5d05dd20733d15dfe1c22c9c4fde5
tree=8312658be3ba272998f46212d9bad76950e3867e
```

PR #119 is the server/read-contract foundation. PR #120 is presentation-only
relative to that foundation.

Current production after PR #120:

```text
HEAD=3dc85735ddf5d05dd20733d15dfe1c22c9c4fde5
TREE=8312658be3ba272998f46212d9bad76950e3867e
worktree=CLEAN
captive-portal.service=active
traffic-projection.service=active
root readiness=HTTP 400 expected without Omada request parameters
Owner production visual acceptance=PASS
```

PR #120 did not require an application restart: its runtime delivery was static
JS/CSS/provenance content and controlled checkout already exposed the accepted
files.

```text
DB migration=NO
schema change=NO
configuration change=NO
feature flag change=NO
systemd unit change=NO
daemon-reload=NO
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

### QIO-01B — approved existing Omada leaf, one path only (NOT deployment GO)

QIO-01B is repository/Lab-only until independent acceptance and separate Owner GO.
Do not change the controller certificate, restart Omada, modify EAP/Cisco/network
DNS, install trust globally, or activate this candidate as part of coding.
No other PKI option or disabled-verification fallback is supplied.

For a later separately authorized installation, Owner/SysAdmin must first export
the existing **public** certificate independently from Omada and confirm its
DER SHA256, SAN Omada, server-auth EKU, self-signature, validity and name/IP
ownership. The observed network fingerprint is only comparison evidence, not
independent approval. No private key or live credential belongs in Git, logs,
handoff or this runbook. Do not download-and-trust the network peer (TOFU).

Under that separate GO, provision only the approved public PEM at a root-owned,
application-readable, non-app-writable regular single-link file outside Git,
for example `/etc/captiveportal/omada-controller-trust.pem` (`root:root 0644` in a
protected directory). No symlink, extra bundle/chain or private key is accepted.
Supply these **deployment** settings; they are not writable Admin settings:

```text
OMADA_URL=https://Omada:8043
OMADA_TLS_TRUST_ANCHOR_PATH=/etc/captiveportal/omada-controller-trust.pem
OMADA_TLS_TRUST_ANCHOR_SHA256=<independently-approved DER SHA256, 64 hex characters>
```

SysAdmin may separately manage local `/etc/hosts` mapping `192.168.0.222 Omada`
on the CaptivPortal host only after Owner approval. Coder does not perform this.
Read-only preflight then checks `getent ahostsv4 Omada`, IP ownership, file
ownership/mode/readability, independent fingerprint, dates/SAN/EKU, exact HTTPS
origin, and absence of any intended proxy route. Do not programmatically fake
SNI/Host for an IP URL. Omada transport deliberately ignores environment proxy,
netrc and global CA settings; other integrations retain their own policy.

After RV-1/2/3 and independent Windows/Linux/TLS/lifecycle/security gates, use an
explicitly authorized controlled **captive-portal.service** restart window:
OmadaProvider belongs to the main process, not the QIO-01A auxiliary worker.
The immutable adopted snapshot and approved leaf are loaded at startup; each
operation creates a fresh verified TLS connection. Check real non-mutating
Requests/OpenAPI, authentication/authorization health and failure audit under
the separate staging/prod permissions, not a TLS-only socket or HTTP 400 proof.
Observe warning/error rates, Auth latency, journald producer/cgroup I/O and
physical-host IOPS/await before claiming performance benefit.

Expiry/rotation monitoring is external operations responsibility. Inventory the
independently confirmed expiry (current reported leaf expires 2028-10-27 UTC),
approve alert lead times before rollout, and obtain/validate a replacement public
leaf independently. This implementation admits one approved leaf per startup,
not an unattended dual-trust window. Coordinate a separately approved maintenance
window for controller rotation and application trust-policy adoption; operations
may be unavailable during that window. A changed PEM is not hot-adopted by a
running provider. A changed peer (even same name/key) is not implicitly approved.
Unexpected certificate/expiry/handshake failure is unavailable + visible audit,
never automatic trust refresh or fabricated empty clients. Already-authorized
Omada sessions may persist; TLS failure cannot promise immediate remote revoke.

Rollback retains the prior independently approved **strict** origin/anchor/digest
and effective settings evidence. Restore it only if that previous certificate
is still valid and matches the actual controller; otherwise hold Omada-dependent
operations until a new strict policy is approved. Use the separate controlled
app restart/adoption procedure; never fall back to VERIFY_SSL=false, HTTP,
warning suppression, global CA/proxy changes, or weaken hostname verification.
No deployment, certificate/name change, production request or service restart
is performed by this implementation TASK.

## Device Fingerprint Task-02 artifacts

Repository templates live under `deploy/device-fingerprint/`. Deployment keeps
both custom services disabled, masks the vendor `suricata.service`, pins
Suricata 8.0.6, installs the public CA and protected producer credential, and
starts the sensor before separately starting its bound Suricata service.
Before checkout mutation, active fingerprint services must be stopped.
Activation and enable-at-boot require separate Owner authorization.

### SSR-01B local recovery and maintenance (installation NOT authorized)

The SSR-01B repository candidate adds a **soft** Sensor `Wants=Suricata`.
Suricata retains its local `After+BindsTo+PartOf=Sensor` relationship. Sensor
start/restart/recovery can enqueue Suricata without making Sensor or Core depend
on successful Suricata startup. A Suricata-only crash must not restart Sensor.
These templates are not an instruction to change installed units or drop-ins;
Owner/SysAdmin installation, restart, activation and rollback need separate GO.

Suricata's unprivileged preflight performs a non-sending AF_UNIX/SOCK_DGRAM
`connect()` against the protected Sensor EVE endpoint. It polls at most every
250 ms for **30 s**, closes every probe socket, and fails closed with a generic
diagnostic. A stale socket inode is not readiness. The existing capture-interface,
readable-config, pinned-version and `suricata -T` preflights remain unchanged.
`connect()` proves a bound kernel endpoint at that instant, not PID identity,
EVE consumption, downstream durability or TLS/QUIC usability. The protected parent
must remain Sensor-owned, group `fingerprint-eve`, mode `0750`, with socket `0660`;
the Suricata group may connect but must not be able to bind/replace endpoints.
Effective deployed ownership/permissions require independent attestation.

Candidate budgets are socket wait 30 s, other preflight/start allowance 20 s,
safety headroom 30 s, `TimeoutStartSec=90`, `RestartSec=30`,
`StartLimitBurst=5`, `StartLimitIntervalSec=750`, `StartLimitAction=none`.
The admitted budget is `30+20+30=80 < 90`; the entire preflight/start chain must
fit it in independent exact-candidate testing. The conservative failure envelope
is 570 s through the fifth failed attempt and 600 s through the denied sixth
job, inside the 750 s window. This is a **total-start window**, not a failure-only
counter, independent per-episode quota, lifetime quota or automatic timer.
Successful starts count too: cold start plus three deliberate Sensor restarts
consume four starts; one Suricata-only automatic recovery consumes the fifth.
Further legitimate starts in that same window can be denied. Arbitrarily many
manual restarts are not promised. A mixed history leaves fewer attempts for
failure recovery; do not silently reset the counter during normal operation.
Missing socket has at most five 30 s probes with 30 s restart
delays before rate-limit failure. No automatic `reset-failed` is added. A late
socket or automatic Sensor restart does not promise recovery of a saturated
Suricata. Operator diagnosis and explicit controlled resume are required.

Two root-controlled **volatile** maintenance inhibits are checked at start:

- `/run/ssr01b-fingerprint-pair-maintenance.hold`: blocks both services.
- `/run/ssr01b-fingerprint-suricata-maintenance.hold`: blocks only Suricata.

The following are operator procedures **only after separate authorization**,
not commands performed by this repository implementation:

```sh
# Pair maintenance: create inhibit FIRST, then stop the pair.
sudo install -o root -g root -m 0600 /dev/null /run/ssr01b-fingerprint-pair-maintenance.hold
sudo systemctl stop fingerprint-suricata.service fingerprint-sensor.service

# Alternatively, Suricata-only maintenance leaves Sensor running.
sudo install -o root -g root -m 0600 /dev/null /run/ssr01b-fingerprint-suricata-maintenance.hold
sudo systemctl stop fingerprint-suricata.service
```

`ConditionPathExists` skips a future job; creating a hold does **not** stop an
active service. Existing NI-01 `Wants=Suricata` and subsequent Sensor restarts must
respect both holds. A bare stop is not a sustained maintenance inhibit. Holds are
not cleared automatically; `/run` is volatile, so **reboot/power loss removes
the inhibits**. Do not rely on this procedure for persistent maintenance.

For authorized resume, diagnose `systemctl status`/unit-scoped journal first:
distinguish condition-skipped jobs from socket/preflight failure and
rate-limit denial (`Start request repeated too quickly` in the journal; systemd
249 may retain the original `exit-code`/`timeout` Result instead of reporting
`start-limit-hit`). Remove **only the intended hold**, retaining any independent
hold. After resolving the fault, explicitly `reset-failed
fingerprint-suricata.service` and start Sensor for a stopped pair, or Suricata
alone for Suricata-only maintenance. Do not reset other units or bypass a hold.
Verify actual EVE heartbeat/stats and raw versus TLS/QUIC source health separately;
neither `active`, a successful probe nor zero queue proves `usable`. Retain real
capture outage/gap evidence; receiver death immediately after connect remains a
possible TOCTOU and does not justify synthetic readiness frames.

For any later separately authorized rollout, retain hashes/copies of effective
installed units and all drop-ins before changing them. Rollback restores those
exact artifacts and the preceding approved code under the same maintenance
procedure, followed by authorized daemon-reload/controlled start and independent
health checks. Never wipe/restore/reseed spool, SQLite or source history to undo
a unit change; do not lose recorded capture gaps. Unexpected Core/NI/Evidence
restart, uncontrolled reattach, false health or budget overrun is HOLD/rollback.
Cold/slow physical-HDD adequacy, real Sensor/Suricata 8.0.6 EVE integration and
official release acceptance remain independent pre-publication gates, not claims
made by the mock-unit focused tests.

## Settings Stage 4 deployment prerequisites (separate authorization required)

The application never provisions or repairs key/DB permissions and never invokes
systemd. Before authorizing managed Client Secret writes, an operator must provide
the code-owned raw **32-byte** key (not hex/base64/newline text) at
`/etc/captiveportal/omada-controller-secret-master.key`. Its parent must be a real
directory `root:admin 0750`, and the key a regular non-symlink single-link file
`root:admin 0640`. Do not print key or credential bytes.

Settings DB is code-owned at `/opt/CaptivePortal/data/settings.sqlite3`: a regular
non-symlink single-link file `admin:admin 0600`; its real parent must be admin-owned
and not group/other-writable. A deployment-defined parent group and setgid 2750 are
allowed. The historically deployed `admin:telemetry 0644` DB arrangement is not
eligible for Stage-4 managed secret writes. Fixing this is an external operator
deployment action, not application automation. No broad `/run`/filesystem workaround
or automatic chmod/chown/chgrp is introduced.

Use `cryptography>=3.4.8` with the existing deployment dependency procedure. Explicitly
grant the secret capability only to authorized Admin login sessions. The source
default excludes secret-write. Stage-4 SQLite schema v3 migrates v2 (and v1) history
transactionally without changing adopted/configured state. Stage-3 source rejects
v3; rollback requires a coherent pre-upgrade DB plus matching authorized code/key
and separate stopped-service rollback authorization, never audit/history deletion.

Managed secrets activate only on external `captive-portal.service` restart and
durable adoption before provider-capable I/O/HTTP. There is no Admin restart button,
live credential test or hot reconnect. Without managed ownership, a valid deployment
secret does not depend on master-key availability. Managed dependency failure aborts
startup without environment fallback and without advancing effective generation.

For authorized local recovery **with the service already stopped**, run:

```text
python3 -m app.settings_control.secret_recovery clear-omada-client-secret --expected-generation <N>
```

The command requires secure/trustworthy current schema-v4 DB and exact configured CAS,
clears only managed ownership, carries ordinary overrides, creates a safe local
audit, retains any effective version and does not load/decrypt the master key,
test Omada, change environment or control the service. No binding is a safe no-op.

A coherent DB backup **and matching master key** are needed for managed-secret
recovery: DB alone cannot recover it; key alone contains no secret. Historical DB
backups plus their matching key may decrypt historical ciphertext. Backup retention
and destruction are operator policy. Live version GC is logical deletion only,
not forensic erasure of pages, backups or physical storage. This implementation
does not export/backup a key or change production/services.

## Settings Stage 5 schema and presentation rollout boundary

New enabled stores use schema v4. Exact v1/v2 history follows the existing chain
through v3. After validating the complete physical v3 schema, ordinary history
and secret references, v3→v4 replaces only the immutable mutation-audit and
idempotency leaf tables inside the existing initialization transaction. Original
IDs, values, response JSON bytes, fingerprints, timestamps, secret versions,
bindings, configured/effective state and activation history remain unchanged.
No Portal defaults are persisted during migration. Missing triggers, incompatible
schema/history or newer versions abort startup; migration failures roll back.
Old code rejecting v4 needs a separately authorized coherent rollback plan.

Recovery uses an existing-only, non-creating/non-migrating v4 opener with exact
schema, trigger, integrity, generation/target and secret-reference checks. It
retains the Stage-4 filesystem policy and never repairs/migrates the DB or loads
the master key. A local clear carries every ordinary override, including Portal,
and does not advance effective generation. This documentation does not authorize
running recovery or changing production.

Portal settings require an externally authorized main-service restart and durable
startup adoption. The Admin API does not restart services or hot-replace the guest
projection. Explicitly grant Portal read/write capabilities only to authorized
sessions; defaults are unchanged. This implementation performs no deployment,
service restart, Controller API probe or production test.
