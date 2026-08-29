# Analytics

Status: current module contract
Updated: 2026-08-29
Baseline: `main@8f3ad59771f72c49834b1012963de6d94b9e0d18`

## Purpose

Read-only query/interpretation layer over persisted facts.

Analytics:
- does not collect;
- does not own source persistence;
- does not call Omada;
- does not migrate/write source DB.

## Sources

`ObservationReadService`, `VisitLifecycleReadService`, `VisitorRegistryReadService`
→ `AnalyticsSourceGateway`.

Source health checks exact schema version and SQLite `PRAGMA query_only`.

## Services

- `AnalyticsReadService` — source/data quality;
- `WirelessAnalyticsService`;
- `VisitAnalyticsService`;
- optional `CurrentTrafficReadService`;
- `HomeActivityReadService`.

## Home Activity

Read-only aggregate over persisted Visit Lifecycle facts. Authorized Visits use one verified Visit-opening authorization per Visit, not AuthSession count. Guest scope is the canonical Current State SSID scope. Unproven guest membership is unavailable, never a synthetic zero.

Traffic is an independent estimated completed-session metric from persisted offline source events, attributed to `completed_session_end`. It is not WAN/billing/Current State traffic. Visits and Traffic retain independent status/coverage. There is no artificial 31/90-day Activity ceiling.

## Current Traffic

Reads persisted AP Observation facts.

Rules:
- complete-success source cycles only;
- strict integrity validation;
- `wired` is primary source family, `lan` fallback;
- source family selected consistently for Site snapshot;
- freshness/AP skew explicit;
- invalid integrity becomes unavailable.

It is not Internet/WAN-only, guest-only, or SSID-only traffic.

The same service remains the semantic owner for both Home Traffic and Traffic Section Current Network Throughput. No Traffic-section-specific calculation service exists.

## Internal API

Prefix: `/api/internal/analytics/v1`.

Security:
Bearer token + source-network allowlist + Site allowlist + bounded concurrency + max response size + no query credentials.

This API is not the Admin browser authentication mechanism.

## Fail-open

Analytics runtime may be disabled/unavailable without breaking Portal/Auth.

`CurrentTrafficReadService` construction is optional relative to other Analytics services.
