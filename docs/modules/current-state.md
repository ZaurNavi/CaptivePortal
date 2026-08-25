# Current Network State

Status: current module contract
Updated: 2026-08-25
Baseline: `main@dfc62b43712301b05baf9f6e5dd843e13eaa9fc7`
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
