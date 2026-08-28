# Workflow coding agent

Status: current
Updated: 2026-08-28
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

Detailed policy and current Windows V4 baseline: `../testing.md`.

## 5. Promotion flow

Normal flow:

```text
Coder implementation
→ minimal TASK/module test evidence
→ exact candidate / patch
→ Tech Lead review
→ Tech Lead defines broader/full gate when required
→ Owner prepares/verifies C:\CaptivPortal-Lab exact artifact
→ Owner physically launches official Central Lab regression
→ Owner + Tech Lead analyze evidence and issue PASS/FAIL
→ owner/release decision
→ separate Linux production-compatible gate when required
→ deploy/activation
```

Do not repeat an identical test run unless the rerun supplies new evidence: changed artifact, new risk, different platform, investigation or explicit release requirement.

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

State exact artifact, files changed, Coder focused/minimal checks, any cross-module test requested or prepared-but-not-run, any prep-only Central Lab action explicitly delegated to Coder, Owner/Tech Lead Central Lab evidence reference, any separate Linux pre-production evidence, actual repository actions, open risks and owner actions. Never claim an operation that was not executed.