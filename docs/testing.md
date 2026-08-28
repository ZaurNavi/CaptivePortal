# Testing

Status: current
Updated: 2026-08-28
Central Lab governance effective: 2026-08-27
Documentation/current-state baseline: `main@53f617b3ac0155d0d647e58e98309927f9a4d318`
Production deployed HEAD: `53f617b3ac0155d0d647e58e98309927f9a4d318`

## Responsibility model

`AGENTS.md` is the universal entry contract. This document is the detailed testing authority.

The current project model is:

```text
Coder / executor
→ minimal TASK/module-scoped automated tests
→ tests created/changed for the implementation
→ exact candidate / patch

Tech Lead
→ defines exact artifact, official gate procedure/commands and acceptance criteria

Owner
→ physical operator of C:\CaptivPortal-Lab
→ prepares/verifies exact Lab artifact
→ physically launches official regression

Owner + Tech Lead
→ analyze evidence
→ PASS / FAIL / return to Coder
```

Cross-module regression, broader regression, full repository suite, release gate, differential baseline/candidate gate and official acceptance are outside Coder test execution.

### Coder / executor

The Coder keeps both the right and the responsibility to perform the **minimum local automated verification of the work being implemented**.

Allowed Coder verification:

- focused tests for the module/component changed by the TASK;
- the minimum TASK-scoped set needed for local self-check;
- tests for files/classes/scenarios directly affected by the change;
- regression cases created with the implementation;
- repeated local runs of those same TASK/module-scoped tests during development/fixes;
- relevant static/syntax/frontend checks;
- `git diff --check`.

Coder may create and modify automated tests that belong to the implemented change.

Coder must **not** independently expand execution to:

- unrelated modules;
- cross-module regression;
- broader regression;
- full `pytest` / full repository suite;
- release gate;
- differential baseline/candidate gate;
- official acceptance.

If a required proof test crosses the TASK/module boundary, exactly two normal paths exist:

1. Coder identifies the additional test/gate and requests Owner/Tech Lead/Central Lab execution.
2. Coder implements or prepares the required cross-module/regression test, but does **not** execute it; execution remains Owner/Tech Lead/Central Lab responsibility.

### Tech Lead / Reviewer

The Tech Lead normally verifies architecture, TASK/ADR conformance, implementation boundaries/DIFF, contracts, risk, Coder focused evidence and whether changed tests cover the intended behavior.

The Tech Lead owns the technical direction of broad/system testing: exact artifact, gate procedure/commands, acceptance criteria and evidence analysis. The Owner is the default physical Central Lab operator.

Owner / Tech Lead / Central Lab own:

- cross-module regression;
- broader regression;
- full `pytest` / full repository suite;
- release gate;
- differential baseline/candidate gate;
- official PASS / FAIL and acceptance.

### Central Lab ownership rule

**CURRENT governance state, effective 2026-08-27.**

`C:\CaptivPortal-Lab` and the official full repository regression cycle are controlled exclusively by **Owner / Tech Lead**.

```text
Tech Lead
→ exact artifact
→ gate procedure / commands
→ acceptance criteria
→ evidence analysis

Owner
→ physical Lab operator
→ prepares / verifies C:\CaptivPortal-Lab exact artifact
→ launches official regression
→ captures raw result/evidence

Owner + Tech Lead
→ PASS / FAIL / return to Coder
```

Coder is not an operator of the official Central Lab gate.

Coder may touch `C:\CaptivPortal-Lab` only after an explicit Owner/Tech Lead prep-only instruction, for example to prepare an exact candidate, patch a specified Lab working directory, or place required artifacts. After that preparation Coder stops; the official cycle returns to Owner/Tech Lead **before execution**.

Coder-run focused/module tests are development evidence, never the official repository regression gate.

A successful full gate on an unchanged exact artifact must not be duplicated merely for formality.

## Official Windows Local Gate

Current approved tool:

```text
C:\CaptivPortal-Lab\lab-test-v4-fixed.cmd
```

This is an Owner-operated official Lab tool. Tech Lead directs the exact-artifact gate; Owner physically runs it. Coder does not execute it as the official gate.

Owner-provided confirmed baseline date:

```text
2026-08-26
```

Strict-suite result for exact artifact `53f617b3ac0155d0d647e58e98309927f9a4d318`:

```text
2100 passed
30 skipped
5 deselected
STRICT_REGRESSIONS=0
```

Production Python used by the deployed runtime: `3.10.12`. Compatibility evidence must cover the production Python version/family rather than assuming newer `sqlite3` module attributes are universal.

Five compatibility cases are tracked separately and narrowly:

```text
WARN — SQLite infinity edge case
WARN — Node async harness timing
PASS — Visitor Registry Windows thread-timing case 1
PASS — Visitor Registry Windows thread-timing case 2
PASS — Visitor Registry Windows thread-timing case 3
```

Additional gate checks:

```text
compileall          PASS
git diff --check    PASS
Windows Local Gate  PASS
```

`lab-test-v4-fixed.cmd` is the current official Windows Local Test Gate. It must not be loosened merely to make a new failure green.

### Compatibility-baseline rule

Compatibility handling is exact and case-specific.

Forbidden:

- excluding a whole module/file because one known case is environment-sensitive;
- converting a new failure into WARN without reviewed evidence;
- broadening the compatibility allowlist merely to preserve a green result;
- weakening assertions or deleting tests to satisfy the gate.

Any new failure outside the explicitly recorded compatibility cases is a **strict regression** until investigated and reclassified through an explicit reviewed decision.

The numeric baseline above is evidence from the confirmed 2026-08-26 run on exact local HEAD. Before accepting any Central Lab result, verify that the tested repository SHA equals the artifact being promoted. A stale PASS from an earlier HEAD is historical evidence only.

Production startup changes additionally require a first-restart acceptance gate. A second restart must not be used to hide a first-start defect; if a second restart occurs, preserve the first-restart evidence separately.

## Linux / production-compatible gate

The Windows Local Gate does **not** replace, weaken or waive Linux pre-production acceptance.

When a deploy/release contract requires a Linux or other production-compatible full gate, it is executed separately on the exact artifact in the required environment.

Canonical Linux gate remains:

```bash
python -m pytest -q -rs
PYTHONPYCACHEPREFIX=/tmp/captivportal-pyc python -m compileall -q app
git diff --check
```

The deploy/release TASK identifies who executes that environment-specific acceptance. It is not automatically assigned to the Coder or Tech Lead merely because they implemented/reviewed the change.

Windows compatibility WARNs do not automatically transfer to Linux; platform-specific results are classified in their own evidence.

## Evidence contract

Every claimed targeted or full test result must identify, as applicable:

- exact artifact/baseline;
- exact command or approved lab gate version;
- environment;
- passed/skipped/failed or strict-regression result;
- compatibility classification;
- `compileall` / `git diff --check` status where included;
- whether the result is Coder targeted evidence, Central Lab official evidence, or Linux pre-production evidence.

Historical green results remain historical. Never present a prior count as a current exact-artifact result after runtime/test changes.

## Reuse and non-duplication

Do not repeat an identical targeted or full run only to duplicate another role's evidence.

A rerun is justified when it provides new information, for example:

- a new patch/commit changed the tested artifact;
- a new risk or previously uncovered scenario must be checked;
- a different platform/environment is required;
- previous evidence is incomplete, contradictory or suspect;
- a deploy/production contract explicitly requires the independent environment gate.

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

## CI

`.github/workflows` is absent at the documented runtime baseline. Automated GitHub release gating is not implemented; this remains process debt, not a runtime defect.

The Central Lab is the official manual full-regression source until a separately approved CI/release-gate architecture changes that responsibility.

## Documentation-only tasks

For a pure documentation change:

- no runtime pytest claim is required from the documentation executor;
- validate paths/links/claims against current sources;
- run Markdown/link tooling only if already available/relevant;
- run `git diff --check`;
- request a fresh Central Lab or Linux gate only when an owner/release contract requires exact-artifact runtime evidence.