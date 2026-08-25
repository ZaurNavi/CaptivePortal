# Workflow coding agent

Status: current
Updated: 2026-08-25

## 1. Intake

1. Read `AGENTS.md`.
2. Read the current TASK as scope/change-intent.
3. Determine execution mode, test responsibility and repository actions.
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

Executor:
- targeted tests for changed modules;
- new regression tests assigned by TASK;
- relevant static/syntax checks;
- `git diff --check`.

Reviewer / Tech Lead / owner:
- full repository suite on exact artifact before production deployment/activation.

Do **not** repeat identical executor targeted tests unless the rerun supplies new evidence:
new risk, different platform, exact-artifact integration, investigation, or explicit TASK/deploy requirement.

## 5. Repository actions

Implementation permission does not imply publish/merge permission.

Branch/commit/push/PR/merge are separate repository actions. Merge, force push and production deploy remain owner-only without direct authorization.

## 6. Conflicts

If TASK, code, tests and current docs disagree:
- identify exact sources;
- stop only affected part;
- continue independent safe work;
- escalate to Architect/Tech Lead.

Never silently choose the convenient source.

## 7. Handoff

Use `agents/handoff.md`.

State exact artifact, files changed, targeted/full checks, actual repository actions, open risks and owner actions. Never claim an operation that was not executed.
