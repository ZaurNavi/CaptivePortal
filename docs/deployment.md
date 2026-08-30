# Deployment

Status: current contract; production details remain host-verified
Updated: 2026-08-31
Current repository baseline: `main@a9cd8a9b9b9efc46bc82d315385ebbd1a3bf63b0`
Confirmed production deployed HEAD: `a9cd8a9b9b9efc46bc82d315385ebbd1a3bf63b0`
Confirmed production tree: `f53f204cf3ebf7cecf4e872ce450b4f3f4265cc9`

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

## Traffic production checkpoint — 2026-08-31

Owner-confirmed:

```text
TASK-TRAFFIC-04:
CLOSED / PRODUCTION PASS

production HEAD:
a9cd8a9b9b9efc46bc82d315385ebbd1a3bf63b0

production tree:
f53f204cf3ebf7cecf4e872ce450b4f3f4265cc9

WEB_ADMIN_TRAFFIC_ENABLED=true
WEB_ADMIN_TRAFFIC_HISTORY_ENABLED=true
WEB_ADMIN_TRAFFIC_STATISTICS_ENABLED=true
WEB_ADMIN_TRAFFIC_PEAK_ENABLED=true

Browser/product acceptance:
PASS

24h:
History / Statistics / Peak = PASS

7d:
History / Statistics / Peak = PASS

shared History/Statistics/Peak range:
PASS
```

Traffic Section production surface includes Current, History, Period Statistics
and Peak Load.

## TRAFFIC-04 deployment and activation history

Previous production checkpoint:

```text
b92efbfabb38f912550526bc5a3d1f2f1a8ae4d6
1d8b94590848f9505e45e653384dd8a7c18d4339
```

Accepted candidate tree:

```text
f53f204cf3ebf7cecf4e872ce450b4f3f4265cc9
```

Publication / merge:

```text
branch: feature/traffic-peak-v1
publication commit: 0343ac77a1a90c2ba8bc3ce1c969b6c1593e9759
PR: #91
merge commit: a9cd8a9b9b9efc46bc82d315385ebbd1a3bf63b0
merge tree: f53f204cf3ebf7cecf4e872ce450b4f3f4265cc9
```

Deployment was performed **FROM GIT**. No SCP/manual source patch was used.

Rollout remained two-stage:

```text
Stage 1:
deploy accepted Git artifact
WEB_ADMIN_TRAFFIC_PEAK_ENABLED=false
→ dormant verification PASS

Stage 2:
WEB_ADMIN_TRAFFIC_PEAK_ENABLED=true
→ separate controlled restart
→ production product acceptance PASS
```

Post-activation evidence:

```text
service active/running
NRestarts=0
startup clean
Observation cycles continue
Omada webhook normal
public portal endpoints normal
```

Peak-only rollback remains feature disable first:

```text
WEB_ADMIN_TRAFFIC_PEAK_ENABLED=false
```

History/Statistics/Current do not need to be disabled for a Peak-only rollback.

## TRAFFIC-04 acceptance / PERF note

Windows Central Lab V6 and Linux production-size PERF both passed on the accepted
candidate tree.

Controlled amendment #1 for this TASK changed only:

```text
Peak vs Candidate p50
from max(0.50s, 20% C.p50)
to   max(0.50s, 30% C.p50)
```

All p95/max/hard-headroom/deadline/browser-timeout limits remained unchanged.

The Owner-approved actual execution did not use a separate pre-publication browser
gate. Production product/browser acceptance was completed after Git deploy and
separate activation. This historical execution detail does not change generic
acceptance-before-publication governance.

A one-time non-reproduced 7d visual-refresh observation was explicitly not accepted
as a blocker/defect/debt. Follow-up History requests were HTTP 200 without observed
429/503/query_deadline/concurrency failure.

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
