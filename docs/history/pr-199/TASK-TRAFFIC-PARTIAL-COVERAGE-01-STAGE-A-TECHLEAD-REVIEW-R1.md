# TASK-TRAFFIC-PARTIAL-COVERAGE-01 — STAGE A TECH LEAD REVIEW R1

**Disposition:** `CHANGES_REQUESTED / STAGE_A_NOT_YET_ACCEPTED`  
**Date:** 2026-10-11  
**Baseline:** `main@e8061de9fbd6da8be5cd269779070a4db4d59d64`  
**Candidate (Coder-reported local commit):** `ade49a171637029f596fe019e73063ce8af76383`  
**Candidate tree (Coder-reported):** `383cf2f1ca2a510811b66f9f4d96c9235f6b24b4`  
**Reviewed files:** uploaded `TASK-TRAFFIC-PARTIAL-COVERAGE-01-STAGE-A.patch`, `STAGE-A-HANDOFF.md`  
**Verified uploaded patch SHA-256:** `ec1b543051de2e0506a28661d09dd7bdf3783851c740c4842b533a35a718403a`  
**Patch diff-stat:** 18 files; 1492 insertions, 26 deletions  
**Scope:** Stage A Current only; Stage B untouched

## Review result

```text
CORE AP-4 BEHAVIOR = SUPPORTED BY CODE INSPECTION AND CODER TEST EVIDENCE
DEFAULT FEATURE OFF = VERIFIED IN PATCH
LEGACY DISPATCH WHEN MODE ABSENT = PRESERVED IN PATCH
OBSERVATION/PROJECTION WRITERS = NO PATCH CHANGES
PUSH / PR / MERGE / DEPLOY / PROD = NOT AUTHORIZED

OPEN P0 = 0
OPEN P1 = 1
OPEN P2 = 1
STAGE A TECH LEAD = CHANGES_REQUESTED
STAGE B = HOLD
```

This is an independent **static patch review**, not a successful independent execution of the complete suite or an official Central Lab/V7 acceptance. Coder-reported test results remain evidence to evaluate, not a full-green release gate.

## Accepted evidence (do not redesign)

1. `app/analytics/current_traffic.py` constructs `complete_online_population` using aligned prior Current State status and valid rates for the remaining Online APs; the AP-4 fixture yields 18 down / 3 up / **21 total Mbps**.
2. `source_unavailable` AP-4 rates stay `NULL`. No fake zero or Wired/LAN AP-by-AP mixing was introduced.
3. Partial measured subtotals remain distinct from complete Site totals; expired and skewed measurements fail closed; source and page cycles are pinned separately from legacy.
4. Feature is default `WEB_ADMIN_TRAFFIC_PARTIAL_COVERAGE_ENABLED=false`. Existing absent-mode Admin routes retain strict dispatch; History receives no opt-in Stage A change.
5. Scope is 18 approved/current-focused files; no Observation/Traffic Projection/Current State writer or schema modification is present.

## P1-01 — Current State SQLite failure incorrectly blanks otherwise measurable traffic

**Evidence:** `app/analytics/current_traffic.py`, `_partial_read`, candidate lines ~278–287; `app/current_state/read_service.py` new `read_ap_status_evidence_at`, lines ~127–192.

The call to `status_reader.read_ap_status_evidence_at(...)` catches `CurrentStateStorageError`, `CurrentStateSchemaError`, `CurrentStateValidationError` but **does not catch `sqlite3.Error` / the expected read/open I/O error family**. The underlying `CurrentStateRepository.read_connection()` / `_connect(readonly=True)` uses `sqlite3.connect` and `connection.execute` directly, so a busy/locked/unavailable status database can raise `sqlite3.OperationalError` before any `CurrentStateStorageError` wrapper exists. That exception escapes `_partial_read` and the Admin query wrapper converts it to source-unavailable/503, even when valid Observation AP1–AP3 measurements are still present.

This violates accepted R1 §28.3: a Current State status-read failure disables **only Offline promotion**; it must not erase valid measured traffic.

**Required implementation:** Catch the narrow expected SQLite/status storage I/O failures at the status-evidence boundary and fall back to `CurrentApStatusEvidenceV1(site)` (`state=unavailable`, no Offline exclusion). Keep deadline/cancellation exceptions subject to existing request deadline rules. Do **not** catch arbitrary programming errors broadly or alter the Current State repository, schema or collector.

**Mandatory regressions:**

- A synthetic AP-4 partial cycle contains three valid AP pairs and one missing pair. A status reader throwing `sqlite3.OperationalError("database is locked")` returns `partial_measured`, 21 Mbps, `status_evidence_unavailable` and `offline_excluded_ap_count=0`, rather than 503 or full Site total.
- The same case with an OS/open error is sanitized and remains measured partial where reasonable; no status is inferred Offline.
- Valid aligned-fresh status still returns `complete_online_population` 21 Mbps.
- Deadline expiration still follows the existing deadline/timeout contract, not an indefinite fallback.

## P2-01 — Current Observation bulk read does not enforce a hard row cap before materialization

**Evidence:** `app/analytics/source_gateway.py`, `read_current_partial_traffic_evidence`, candidate lines ~1933–1946; `app/analytics/current_traffic.py` candidate line ~272.

The code performs `SELECT COUNT(*) ... WHERE cycle_id=?`, then `SELECT ... LIMIT count+1` and materializes all AP rows. A normal Observation writer has configured caps (default 500; repository configuration maximum 10,000), but this **reader does not enforce an independent hard maximum before loading** unexpected/corrupt persisted data. The public per-AP page limit of 250 is applied later and is not a bound on the gateway read.

**Required implementation:** Before fetching rows, enforce a bounded upper limit consistent with the existing Observation maximum; if count exceeds it, fail closed with no numeric aggregate and no silent truncation/older-result fallback. Ensure SQLite reads respect the shared request deadline and do not add new workers, indexes, storage, or config flags.

**Mandatory regressions:** Oversized persisted cycle or mocked oversized row count yields safe unavailable/integrity failure without requesting `LIMIT count+1` unbounded rows. At the existing allowed maximum, valid results continue to work. Paginated page replies remain <=250 and do not affect Site total.

If Coder believes the current writer cap already provides an equivalent *read-side* hard proof for corrupt/cross-generation data, return concrete source-level proof and deterministic test rather than silently dismissing this item.

## Full regression / QA disposition

Coder handoff reports:

- focused: **347 PASS**;
- new Stage A: **74 PASS**;
- complete Windows pytest: **6598 PASS / 186 FAIL / 36 SKIP**;
- Coder reran the failed node IDs against exact clean baseline: same 186 baseline Windows failures, **zero candidate-only failed IDs** after the fixture correction;
- typical failure causes: Windows does not implement required POSIX `os.pread`, `os.O_NONBLOCK`, `fcntl`, plus Windows file-sharing behavior.

**Tech Lead disposition:** The reported differential evidence argues against Stage A regression in those node IDs, but **the full Windows run is FAIL, not PASS**, and the separate `TEST-GATE-PLATFORM-01` manifest is still DRAFT / NOT ADMITTED. No blanket waiver or unapproved skip is authorized. Do not modify protected NI tests/source to remove the baseline errors.

Before release readiness, obtain independent supported Linux/Central Lab evidence (or exact accepted platform-composite gate) and manual normal/mobile UI review. Until that happens, no release/activation claim.

## Required Coder resubmission

1. Apply only P1-01 and P2-01 minimal amendments in the **same isolated Stage A worktree**; do not start Stage B.
2. Add focused negative tests for both defects, and prove previously accepted AP-4/strict-mode behavior remains unchanged.
3. Run targeted current/legacy/History compatibility tests, JS checks, `compileall`, `git diff --check` and the appropriate full gate. Clearly report all failures rather than claiming full PASS.
4. Return an exact new candidate commit/tree, changed-file inventory, BASE→candidate replacement patch and patch SHA256, test counts/log/manifest paths, feature flag state and explicit STOP status.
5. Coder may create a **local review commit**. No push, PR, merge, deploy, production config change, restart or activation without independent Owner approval.

```text
TASK=TASK-TRAFFIC-PARTIAL-COVERAGE-01
STAGE=A_CURRENT
TECH_LEAD_REVIEW=R1_CHANGES_REQUESTED
ARCHITECTURE=R3_ACCEPTED_UNCHANGED
CODER_SCOPE=P1_01_AND_P2_01_FIX_ONLY
STAGE_B=HOLD
PUSH=NO
PR=NO
MERGE=NO
DEPLOY=NO
PRODUCTION_ACTIONS=NO
```
