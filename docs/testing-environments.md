# CaptivPortal Test Environments and Production Boundary

Status: CURRENT / PERMANENT INFRASTRUCTURE CONTRACT
Updated: 2026-09-06

This document is mandatory onboarding context for Tech Lead, Coder, Architect and
any agent that plans or executes acceptance, Linux, performance or
production-validation work.

## 1. Canonical environment routing

CaptivPortal has three distinct execution contours:

```text
1. Windows Central Lab
2. Dedicated laptop WSL/Linux Lab
3. Production 192.168.0.202
```

One contour does not automatically substitute for another.

Short routing rule:

```text
Windows/general acceptance
→ Windows Central Lab

Linux/pre-production/PERF/storage/concurrency
→ dedicated laptop WSL/Linux Lab

Production 192.168.0.202
→ production runtime / explicitly authorized production validation only
```

## 2. Windows Central Lab

Physical host: Owner laptop/workstation running Windows.

Canonical support directory:

```text
C:\CaptivPortal-Lab
```

Known working repository/worktree location:

```text
C:\CaptivPortal-UI-Preview
```

Task-specific directories may exist inside or next to
`C:\CaptivPortal-Lab`.

Windows Central Lab is used for:
- exact candidate reconstruction;
- patch verification;
- Windows regression gates;
- functional acceptance;
- parity harnesses;
- UI/browser-oriented tests;
- artifact preparation for subsequent Linux gates.

Ownership:

```text
Tech Lead
→ exact artifact
→ exact commands
→ expected results
→ PASS/FAIL criteria

Owner
→ physically prepares/runs Central Lab

Owner + Tech Lead
→ classify evidence and issue official PASS/FAIL
```

Coder does not replace Owner/Tech Lead official acceptance.

The detailed Windows runner/interpreter/anti-drift contract remains in
`testing.md`.

## 3. Dedicated WSL/Linux Lab

CaptivPortal already has a dedicated Linux test/performance environment on the
Owner laptop.

Technology:

```text
WSL / Linux under Windows
```

Known host identity:

```text
DESKTOP-7C8M3BS
```

Linux user:

```text
zaur_navi
```

Known previously used working directories:

```text
~/captivportal-lab
~/captivportal-traffic07-perf
```

Task-specific directories, virtual environments, candidate worktrees,
production-derived snapshots and performance directories may change between
TASKs. The **Linux Lab itself is permanent project infrastructure** and must not
be rediscovered or recreated from scratch by every new specialist.

## 4. Linux Lab purpose

The dedicated WSL/Linux Lab is the default environment for:

- Linux pre-production acceptance;
- Linux-specific regression;
- SQLite migration/materialization/rebuild tests;
- performance gates;
- concurrency/WAL/storage tests;
- source-immutability tests;
- Linux runtime behavior;
- isolated worker/service behavior that must not load production;
- tests with production-derived snapshots/copies.

If a TASK requires Linux acceptance or a performance gate, Tech Lead must first
use this existing dedicated Lab unless the TASK explicitly requires another
environment.

## 5. Production is not a test host

Production CaptivPortal VM:

```text
192.168.0.202
Ubuntu 22.04.x
```

Permanent invariant:

```text
PRODUCTION IS NOT AN ACCEPTANCE OR PERFORMANCE TEST HOST.
```

Without a separate explicit Owner authorization for a named production
validation action, do not run on production:

- acceptance candidates;
- experimental branches;
- performance benchmarks;
- rebuild benchmarks;
- destructive/isolated test workers;
- synthetic test workloads;
- candidate projection databases;
- broad/regression suites that add load or can change runtime state.

SSH access and the fact that production is Linux do **not** make it the Linux
Lab.

Production may be used for:
- read-only inspection;
- verifying actual production configuration/state;
- an approved safe snapshot/copy procedure;
- post-deploy validation;
- specifically authorized production tests.

## 6. Production-like data in Lab

Preferred model:

```text
Production source
→ safe/read-only snapshot or approved copy
→ dedicated laptop WSL/Linux Lab
→ isolated candidate DB/output
```

Do not point an experimental candidate worker/output at a production DB or
production runtime merely to obtain realistic test data.

## 7. Worktree and exact-artifact rules

Before using an allowlisted Lab path:

```text
git worktree list
```

and verify whether the path already exists/is occupied.

Do not delete, overwrite or move an occupied worktree merely to reuse a desired
path.

For immutable candidates, prefer creating a new detached worktree directly in
the approved path instead of physically moving an existing worktree.

Exact artifact identity and clean-worktree requirements remain mandatory.

## 8. Onboarding requirement

Every new Tech Lead, Coder, Architect or testing agent must know before work
begins:

```text
Windows tests → Windows Central Lab
Linux/PERF/pre-production → dedicated laptop WSL/Linux Lab
Production 192.168.0.202 → not a test host
```

The specialist must not start by rediscovering whether a Linux environment
exists, deciding that production is a convenient Linux test server, or creating
a new WSL/VM for every TASK.

## 9. Related authority

- `testing.md` — testing ownership/gates and Windows Central Lab details.
- `agents/workflow.md` — promotion and environment routing workflow.
- `operations-command-lessons-learned.md` — practical command/harness safety.
- `deployment.md` — production delivery/validation boundary.
