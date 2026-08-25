# Testing

Status: current
Updated: 2026-08-25
Baseline: `main@dfc62b43712301b05baf9f6e5dd843e13eaa9fc7`

## Responsibility

`AGENTS.md` is authoritative.

### Executor / coding agent

Runs:
- targeted tests for modules/components changed by the task;
- regression cases added for the changed contract;
- relevant static/syntax checks;
- `git diff --check`.

The executor does **not** run the full repository suite merely for formality unless the owner/TASK explicitly assigns it.

### Reviewer / Tech Lead / owner

Runs the full exact-artifact pre-production gate before deployment/feature activation:

```bash
python -m pytest -q -rs
PYTHONPYCACHEPREFIX=/tmp/captivportal-pyc python -m compileall -q app
git diff --check
```

Reuse valid executor targeted-test evidence. Do not repeat an identical targeted run unless it answers a new risk/question.

## Current test map

Repository test root: `tests/`.

Coverage groups include:
- Portal/Auth/retry/session ownership;
- CAPPORT/discovery/frontend;
- telemetry/counters;
- Omada provider and webhook;
- Visitor Snapshot/Registry;
- Pending Session Cleaner;
- Visit Lifecycle including schema/write contention/reader/reconciliation;
- Observation;
- Current State;
- Analytics/API/Current Traffic;
- Admin Web/Home Live/Home Traffic.

Do not preserve an old numeric test-file/test-case count as a current fact without recounting on the target commit.

## Evidence

Every claimed test result must include:
- exact baseline/artifact;
- exact command;
- environment;
- passed/skipped/failed;
- relevant failure classification.

Historical green results remain historical.

## CI

`.github/workflows` is absent at this baseline. Automated GitHub release gating is not implemented; this is process debt, not a runtime defect.

## Documentation-only tasks

For a pure docs change:
- no runtime test changes;
- no runtime pytest claim is required from executor;
- validate paths/links/claims against code;
- run Markdown/link tooling only if already available;
- run `git diff --check`;
- Reviewer may run the normal full gate before production integration if policy requires exact-artifact validation.
