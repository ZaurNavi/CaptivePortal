# Workflow coding agent

Status: current
Updated: 2026-08-26

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

Runs task-scoped verification:

- targeted tests for changed modules/components;
- new regression tests assigned by TASK;
- repeated targeted tests needed during implementation/fixes;
- relevant static/syntax/frontend checks;
- `git diff --check`.

The Coder does not run the whole CaptivPortal regression suite by default.

### Tech Lead / Reviewer

Reviews architecture, TASK/ADR conformance, DIFF, contracts, risk and the Coder's targeted-test evidence.

The Tech Lead does not personally rerun the full suite for ordinary review unless a separate concrete reason requires it.

### Central Lab

Owns the controlled full-regression function:

```text
official full baseline
Full Regression Gate
final Test Evidence
strict-regression confirmation
```

Use the Central Lab evidence for the exact artifact rather than duplicating the same full run in multiple roles.

### Linux pre-production

When production acceptance requires Linux/production-compatible execution, that is a separate exact-artifact gate defined by the deploy/release contract. Windows Local Gate does not replace it.

Detailed policy and current Windows V4 baseline: `../testing.md`.

## 5. Promotion flow

Normal flow:

```text
Coder implementation
→ targeted/module test evidence
→ Tech Lead review
→ Central Lab full gate when required
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

State exact artifact, files changed, Coder targeted checks, any Central Lab evidence reference, any separate Linux pre-production evidence, actual repository actions, open risks and owner actions. Never claim an operation that was not executed.