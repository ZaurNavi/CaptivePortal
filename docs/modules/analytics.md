# Analytics

Status: current module contract
Updated: 2026-08-25
Baseline: `main@dfc62b43712301b05baf9f6e5dd843e13eaa9fc7`

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
- optional `CurrentTrafficReadService`.

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

## Internal API

Prefix: `/api/internal/analytics/v1`.

Security:
Bearer token + source-network allowlist + Site allowlist + bounded concurrency + max response size + no query credentials.

This API is not the Admin browser authentication mechanism.

## Fail-open

Analytics runtime may be disabled/unavailable without breaking Portal/Auth.

`CurrentTrafficReadService` construction is optional relative to other Analytics services.
