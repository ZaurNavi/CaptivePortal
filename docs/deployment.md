# Deployment

Status: current contract; production details remain host-verified
Updated: 2026-09-03
Current repository implementation baseline: `main@6425988b5b4ec5ff38bf9c67c74846c3806f668f`
Confirmed production deployed HEAD: `6425988b5b4ec5ff38bf9c67c74846c3806f668f`
Confirmed production tree: `b669f368b0062fcb100b24758cf05e2c4b500144`

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

## Traffic production checkpoint — 2026-09-01

Owner-confirmed current state:

```text
repository / production HEAD:
6425988b5b4ec5ff38bf9c67c74846c3806f668f

repository / production tree:
b669f368b0062fcb100b24758cf05e2c4b500144

captive-portal.service:
active
```

Current production Traffic surface:

```text
Current Network Throughput
Network Traffic History
Period Statistics
Peak Load
Traffic by AP
AP Traffic Share
Online Guests Traffic
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

The production fix for heavy shared 7d historical work did **not** increase the
Admin query deadline.

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
- permanent 10-second admission guard.

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
