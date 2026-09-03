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

## Traffic production checkpoint — 2026-09-03

Owner-confirmed current state:

```text
repository implementation / production HEAD:
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

Production activation includes:

```text
WEB_ADMIN_TRAFFIC_ONLINE_GUESTS_ENABLED=true
```

Repository default remains `WEB_ADMIN_TRAFFIC_ONLINE_GUESTS_ENABLED=false`.

## TRAFFIC-07 deployment / activation history

Implementation layers:

```text
PR #98 — TRAFFIC-07-READ / CurrentGuestTrafficReadService foundation
PR #99 — Admin: add Online Guests Traffic
```

Final artifact:

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

PR #99 acceptance evidence:

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
added.

Earlier TRAFFIC-00..06/RANGE acceptance remains historical evidence.

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
