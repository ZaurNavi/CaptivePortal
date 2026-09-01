# Deployment

Status: current contract; production details remain host-verified
Updated: 2026-09-01
Current repository implementation baseline: `main@daf68e91fc759188980cf8741913e6b60a58eb62`
Confirmed production deployed HEAD: `daf68e91fc759188980cf8741913e6b60a58eb62`
Confirmed production tree: `b0e2f028eecf6aec9d86e35542c33e7105209335`

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
daf68e91fc759188980cf8741913e6b60a58eb62

repository / production tree:
b0e2f028eecf6aec9d86e35542c33e7105209335

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
```

Production flags:

```text
WEB_ADMIN_TRAFFIC_ENABLED=true
WEB_ADMIN_TRAFFIC_HISTORY_ENABLED=true
WEB_ADMIN_TRAFFIC_STATISTICS_ENABLED=true
WEB_ADMIN_TRAFFIC_PEAK_ENABLED=true
WEB_ADMIN_TRAFFIC_BY_AP_ENABLED=true
WEB_ADMIN_TRAFFIC_INDEPENDENT_RANGES_ENABLED=true
```

Repository defaults for these feature flags remain `false`.

## TRAFFIC-05 publication history

```text
TASK-TRAFFIC-05 — Traffic by AP
publication commit: 85edc14214e3a271a300249b5b1062be31547c95
PR: #93
merge commit: 8a5c4db899406eeb1f737abe63495247be1ee75a
merge tree: 6837dd729dedb0df6414b3f979657a3f6f55d0ab
current production status: DONE / PRODUCTION ACTIVE
```

## TRAFFIC-RANGE-01 deployment / activation history

Accepted candidate tree:

```text
b0e2f028eecf6aec9d86e35542c33e7105209335
```

Publication / merge:

```text
publication commit: 355b413e9167bafb8ca9547af08c037eef86b189
PR: #94
merge commit: daf68e91fc759188980cf8741913e6b60a58eb62
merge tree: b0e2f028eecf6aec9d86e35542c33e7105209335
```

Production deployment was performed **FROM GIT**. Application source was not
delivered by SCP/manual patch.

Owner-approved closing sequence:

```text
Implementation candidate
→ focused gate PASS
→ targeted Traffic regression PASS WITH REVIEWED COMPATIBILITY
→ Windows Central Lab V6-FIXED PASS
→ Linux production-size §97 PERF PASS
→ Git publication
→ PR #94
→ Owner merge
→ deploy FROM GIT
→ dormant production acceptance PASS
→ separate feature activation
→ production browser/product acceptance PASS
```

Activation and deployment remained separate operations.

Independent-range activation current fact:

```text
WEB_ADMIN_TRAFFIC_INDEPENDENT_RANGES_ENABLED=true
```

Traffic by AP current fact:

```text
WEB_ADMIN_TRAFFIC_BY_AP_ENABLED=true
```

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
