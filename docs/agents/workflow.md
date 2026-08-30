# Workflow coding agent

Status: current
Updated: 2026-08-30
Central Lab governance effective: 2026-08-27

## 1. Intake

1. Read `AGENTS.md`.
2. Read the current TASK as scope/change-intent.
3. Determine execution mode, TASK-scoped test responsibility and repository actions.
4. Read only linked knowledge contracts.
5. Verify affected current code/tests before planning.

Current-state truth: code → tests → current docs.
Change-intent truth: FINAL TASK → PLAN → ADR.

## 2. Modes

- `planning-only`: read/verify/plan; no changes.
- `implementation`: allowed-file changes only.
- `review`: diff/contracts/tests verdict; fixes only if separately allowed.
- `publish`: only explicitly authorized branch/commit/push/PR.
- `deploy`: separate production task with backup/health/rollback.

## 3. Implementation

- minimal sufficient scope;
- preserve current architectural invariants;
- no unrelated refactor;
- no schema/public contract change unless TASK requires it;
- update the canonical knowledge contract if a current contract changes.

## 4. Verification responsibility

### Coder / executor

Runs only minimum task-scoped verification:

- focused tests for changed modules/components;
- the minimum TASK-scoped automated set needed for local self-check;
- new regression tests belonging to the implementation;
- repeated runs of those same targeted tests during implementation/fixes;
- relevant static/syntax/frontend checks;
- `git diff --check`.

Coder may create/change tests belonging to the implementation.

Coder does not execute unrelated-module, cross-module, broader or full repository regression. If such proof is needed, Coder requests Owner/Tech Lead/Central Lab execution or prepares the test without running it.

### Tech Lead / Reviewer

Reviews architecture, TASK/ADR conformance, DIFF, contracts, risk and the Coder's focused test evidence.

The Tech Lead owns technical direction of cross-module/broader/full testing and acceptance. The Owner is the default physical Central Lab operator.

### Central Lab

Canonical ownership is in `../testing.md`.

```text
Coder → TASK/module-scoped tests only
Tech Lead → exact artifact / commands / criteria
Owner → physical C:\CaptivPortal-Lab preparation + official execution
Owner + Tech Lead → evidence analysis + PASS/FAIL
```

Cross-module regression, broader regression, full repository suite, release/differential gates and official acceptance are not delegated to Coder.

### Linux pre-production

When production acceptance requires Linux/production-compatible execution, that is a separate exact-artifact gate defined by the deploy/release contract. Windows Local Gate does not replace it.

Detailed policy, current Windows Lab environment, verified runner and anti-drift rule: `../testing.md`.

## 4A. Test-set maintenance after each accepted TASK

A previously correct targeted regression block is not evergreen.

After every new accepted module/panel/API/read-service implementation, Tech Lead / Assistant Tech Lead reviews:
- new and changed test files from Coder handoff;
- current TASK-focused tests;
- affected existing module regressions;
- cross-surface invariants;
- current targeted Central Lab command;
- full repository discovery set;
- whether the runner contract itself changed.

Ordinary new pytest files discovered by full pytest do not require mechanical runner edits. Runner changes require an actual gate/compatibility/environment contract change.

For an official Windows full gate, Owner/Tech Lead also re-verifies the current runner version instead of trusting a version string copied from an older TASK or KB page.

## 5. Promotion flow

Canonical normal flow:

```text
Coder implementation / patch
→ Coder focused/minimal TASK/module evidence
→ exact candidate materialized in Lab
→ Tech Lead refreshes targeted/test-set block
→ required targeted/cross-surface acceptance
→ Owner runs official Central Lab full gate
→ all other mandatory TASK/FINAL/release gates
→ Linux / production-compatible / production-size PERF when required
→ ALL MANDATORY GATES PASS
→ ACCEPTED CANDIDATE
→ publication commit
→ GitHub feature branch / Draft PR
→ verify accepted tree = publication/PR tree
→ Owner-authorized merge
→ verify merge tree / chain-of-custody
→ production deploy FROM GIT
→ separate Owner-controlled activation
→ production acceptance
```

Short invariant:

```text
Patch → Lab.
All mandatory gates → PASS.
Accepted candidate → Git.
Git → Production.
Activation → separate step.
```

`Central Lab V6 PASS` is not equivalent to `candidate accepted` if TASK/FINAL
also requires PERF/Linux/capacity/security/browser/etc.

A mandatory gate is pre-publication acceptance.

GitHub is publication/review/chain-of-custody, not the normal transport between
acceptance environments.

For mandatory production-compatible acceptance, use an isolated Linux Lab or
equivalent controlled environment with exact candidate tree and immutable
read-only production-size data snapshot when needed.

A changed candidate tree after acceptance requires Tech Lead to determine/repeat
the necessary gates.

TEST-ONLY / EXPERIMENTAL publication before acceptance requires explicit Owner +
Tech Lead authorization and remains NOT ACCEPTED / NOT MERGEABLE / NOT DEPLOYABLE.

Production application code is deployed only from Git using explicit verified
SHA/tree. Direct patch/source transfer is emergency-only and requires Owner +
Tech Lead plus later repository reconciliation.

Do not repeat an identical test run unless it supplies new evidence.

## 6. Repository actions

Implementation permission does not imply publish/merge permission.

Branch/commit/push/PR/merge are separate repository actions. Merge, force push and production deploy remain owner-only without direct authorization.

## 7. Conflicts

If TASK, code, tests and current docs disagree:

- identify exact sources;
- stop only affected part;
- continue independent safe work;
- escalate to Architect/Tech Lead.

Never silently choose the convenient source.

## 8. Handoff

Use `agents/handoff.md`.

State exact artifact, files changed, new/changed test files, Coder focused/minimal checks, any cross-module test requested or prepared-but-not-run, any prep-only Central Lab action explicitly delegated to Coder, Owner/Tech Lead Central Lab runner/evidence reference, any separate Linux pre-production evidence, actual repository actions, open risks and owner actions. Never claim an operation that was not executed.