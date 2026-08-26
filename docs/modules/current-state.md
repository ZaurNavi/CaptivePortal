# Current Network State

Status: current module contract
Updated: 2026-08-26
Baseline: `main@53f617b3ac0155d0d647e58e98309927f9a4d318`
Schema: v1

## Purpose

Answer what active wireless clients and APs are in configured Site scope now.

This differs from Observation, which is historical and authorized-population focused.

## Client scope/classification

Population:
- wireless;
- active;
- SSID in exact configured scope.

Classification:
- `authStatus == 2` → authorized
- `authStatus == 1` → pending
- other integer → other
- missing/invalid → unknown

## Snapshot semantics

Client and AP cycles are independent.

`CurrentStateReadService` selects complete-success snapshots and also retains latest attempt/partial metadata for quality reporting.

Freshness:
- within fresh threshold → `fresh`;
- older but within stale threshold → `stale`;
- older than stale threshold → `unavailable`.

Invalid/clock-anomaly timestamps are unavailable, not coerced to fresh.

## Scope/cursors

Client source scope is canonicalized and hashed.

Pagination cursors bind endpoint, Site, cycle, source scope, sort/filters. A scope change invalidates an old cursor instead of mixing populations.

## History

Current State keeps bounded short history (repository default 48h) and enforces a configured maximum client-row pressure signal.

## Dependencies

Collector uses the shared `OmadaProvider`.

Admin/Home uses `CurrentStateReadService` over persisted storage; Admin HTTP requests do not poll Omada.

Failure is fail-open relative to guest authorization.

## Startup integrity and SQLite compatibility

Final current behavior:
- a self-imposed `PRAGMA quick_check` progress-handler timeout is classified as retryable `CurrentStateStorageError`;
- unrelated SQLite `interrupted`, schema mismatch and `quick_check != ok` remain schema/integrity errors;
- runtime retry policy was not redesigned;
- Python 3.10 does not require `sqlite3.SQLITE_BUSY` / `sqlite3.SQLITE_LOCKED` module constants;
- stable primary result codes are BUSY=`5`, LOCKED=`6`;
- integer `sqlite_errorcode` is normalized with `code & 0xFF`, so extended codes such as 261/262 map to BUSY/LOCKED;
- message fallback `database is locked` / `database is busy` remains.

## Production first-restart evidence — 2026-08-26

One restart at `22:55:39 +04`; no second restart. Client cycles: 4 success / 0 errors. AP cycles: 4 success / 0 errors. All inspected cycles were `complete=1`, `result=success`, `failure_category=None`.

Verdict: **Current State first-restart startup acceptance PASS**.
