# Postmortem — TASK-HOME-ACTIVITY-01 finalization

Status: historical incident / lessons retained
Date: 2026-08-26
Final current artifact: `53f617b3ac0155d0d647e58e98309927f9a4d318`

## Scope

This document records the defect/fix chain during Home Activity production finalization. These are **history**, not current behavior.

## Final outcome

- Home Activity implemented and merged through PR #67–#72.
- Central Lab exact-artifact gate: PASS.
- Production deployed HEAD: `53f617b3ac0155d0d647e58e98309927f9a4d318`.
- Core production acceptance: PASS.
- Current State first-restart startup acceptance: PASS.
- Visits safe coverage boundary established.
- Traffic coverage start remains an independent open evidence boundary.

## Failure mode 1 — unknown scope became false zero

Initial Home Activity could produce a numeric zero when guest-scoped Visit membership was not provable.

Correction: PR #68. Final rule: `Unknown/unproven != Zero`; `guest_scope_unproven → unavailable`. Visits and Traffic remain independent.

## Failure mode 2 — CAPPORT SSID propagation missing

CAPPORT already read client context but did not preserve authoritative SSID through Visit opening evidence.

Correction: PR #69.

Final chain:
`Omada /clients ssid → CapportClient.ssid → PortalClientContext.ssid → AuthSession.ssid → VisitStartRequest.portal_ssid`.

## Failure mode 3 — External Portal contract mismatch

External Portal ingress used legacy `ssid`, while Omada's canonical redirect parameter is `ssidName`.

Correction: PR #70.

Final rule:
- canonical `ssidName`;
- legacy `ssid` fallback;
- conflicting non-empty values remain unproven; never silently choose one.

## Failure mode 4 — Current State own quick_check timeout misclassification

A repository-imposed `PRAGMA quick_check` progress-handler timeout was treated as a permanent schema failure during startup.

Correction: PR #71.

Final rule: only the repository's own quick_check interruption is retryable storage failure. Unrelated `interrupted`, schema mismatch and non-`ok` quick_check remain schema/integrity failures. Runtime retry policy was not redesigned.

## Failure mode 5 — Python 3.10 SQLite compatibility omission

The first correction assumed `sqlite3.SQLITE_BUSY` / `sqlite3.SQLITE_LOCKED` module constants were universally available. Production uses Python `3.10.12`.

Correction: PR #72.

Final rule:
- stable primary codes: BUSY=5, LOCKED=6;
- integer `sqlite_errorcode → code & 0xFF`;
- extended BUSY/LOCKED result codes therefore normalize safely;
- string fallback remains.

## Central Lab evidence lesson

A prior green run on a stale artifact is not evidence for a newer PR.

Official final evidence is the run after exact local HEAD was confirmed:

```text
artifact: 53f617b3ac0155d0d647e58e98309927f9a4d318
2100 passed
30 skipped
5 deselected
STRICT_REGRESSIONS=0
compatibility=2 WARN / 3 PASS
RESULT=PASS
```

Known WARN:
- SQLite infinity edge case;
- Node async harness timing.

Known compatibility PASS:
- Visitor Registry long-audit timing;
- previous-ready timing;
- previous-stopping timing.

## Production first-restart evidence

Restart: `2026-08-26 22:55:39 +04`.

No second restart was performed.

After that first restart:
- service active;
- CAPPORT operational;
- Omada webhook operational;
- Observation operational;
- Current State persisted client/AP cycles;
- client: 4 cycles / 4 success / 0 errors;
- AP: 4 cycles / 4 success / 0 errors;
- no non-success cycle;
- all inspected cycles `complete=1`, `result=success`, `failure_category=None`.

Verdict: PASS.

## Process improvements retained

1. production-shaped fixtures;
2. ingress contract matrix;
3. explicit `Unknown != Zero` tests;
4. cross-ingress parity tests;
5. first-restart production gate;
6. exact-SHA Central Lab verification before accepting evidence;
7. production-version compatibility coverage;
8. explicit startup telemetry verification.

## Observability gap

Persisted Current State evidence proved runtime success, but expected `current_state.runtime_started` telemetry was not found in the inspected journal.

Classification: observability/telemetry gap, **not** active runtime defect.

If fixed, use a separate debt/TASK so telemetry work is not confused with the already-closed startup defect.
