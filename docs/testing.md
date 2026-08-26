# Testing

Status: current
Updated: 2026-08-26
Documentation/current-state baseline: `main@53f617b3ac0155d0d647e58e98309927f9a4d318`
Production deployed HEAD: `53f617b3ac0155d0d647e58e98309927f9a4d318`

## Responsibility model

`AGENTS.md` is the universal entry contract. This document is the detailed testing authority.

The current project model is:

```text
Coder / executor
→ TASK/module-scoped testing

Central Lab
→ full regression
→ official baseline
→ final Test Evidence
```

The purpose is to avoid repeating the same heavy regression suite in Coder, Tech Lead and owner workflows while preserving strong local verification of each implementation.

### Coder / executor

The Coder keeps both the right and the responsibility to test the work being implemented.

Expected Coder verification includes:

- targeted tests for modules/components changed by the TASK;
- tests for specific files/classes/scenarios affected by the change;
- regression cases added with the implementation;
- repeated local runs of those targeted tests during development/fixes;
- relevant static/syntax/frontend checks;
- `git diff --check`.

The Coder does **not** run the full CaptivPortal repository regression suite by default after every implementation.

A TASK may explicitly require an exceptional broader run when there is a concrete reason, but that exception must be stated; it is not inherited from old TASK wording.

### Tech Lead / Reviewer

The Tech Lead normally verifies:

- architecture and TASK/ADR conformance;
- implementation boundaries and DIFF;
- contracts, risk and regression surface;
- Coder targeted-test evidence;
- whether new/changed tests cover the intended behavior.

The Tech Lead is **not** required to personally execute the full repository suite for ordinary implementation review.

When official full-baseline evidence is required, the Tech Lead requests/consumes the Central Lab result for the exact artifact.

The Tech Lead may still run a targeted or broader test when it answers a specific unresolved question, platform delta or investigation need.

### Central Lab

The Central Lab is the controlled source for:

- official current full-regression baseline;
- Full Regression Gate;
- final Test Evidence before further promotion when required;
- confirmation that no strict regression appeared;
- reproducible evidence that can be consumed by Tech Lead, Coder and other roles.

A successful full gate on an unchanged exact artifact must not be duplicated by another role merely for formality.

## Official Windows Local Gate

Current approved tool:

```text
C:\CaptivPortal-Lab\lab-test-v4-fixed.cmd
```

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