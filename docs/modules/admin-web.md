# Admin Web

Status: current module contract
Updated: 2026-08-30
Baseline: `main@b92efbfabb38f912550526bc5a3d1f2f1a8ae4d6`

## Boundary

Admin authentication is separate from guest Portal authentication.

Current UI pages:
Home, Devices, Device Detail, Visits, Observations, Traffic.

## Browser data path

```text
browser
→ same-origin /admin + /admin/api/v1
→ AdminQueryService/read gateways
→ persisted read services
```

Forbidden:
SQLite, Omada, Loki, Grafana, internal Analytics bearer API.

## Security

When enabled:
- HTTPS/source network/Site allowlist;
- external password hash;
- pre-auth CSRF;
- login rate limits;
- bounded process-local sessions;
- idle/absolute timeout;
- Secure/HttpOnly/SameSite cookies;
- CSP/security headers/no-store.

## Query boundary

`AdminQueryService` owns Site authorization, bounded concurrency/deadline and
safe error mapping.

## Home

Home Live reads Current State.
Home Traffic reads Current Traffic.
Home Activity reads Visit Lifecycle analytics.
Home AP-24H reuses existing persisted/read contracts.

## Traffic Section

Traffic is a Site-scoped Admin product surface controlled by separate feature
boundaries.

Repository defaults:

```text
WEB_ADMIN_TRAFFIC_ENABLED=false
WEB_ADMIN_TRAFFIC_HISTORY_ENABLED=false
WEB_ADMIN_TRAFFIC_STATISTICS_ENABLED=false
```

Owner-confirmed production state 2026-08-30:

```text
WEB_ADMIN_TRAFFIC_ENABLED=true
WEB_ADMIN_TRAFFIC_HISTORY_ENABLED=true
WEB_ADMIN_TRAFFIC_STATISTICS_ENABLED=true
```

Current functional panels:

1. Current Network Throughput;
2. Historical Network Throughput;
3. Period Statistics.

One shared Traffic coordinator owns page-level lifecycle. Statistics is a passive
consumer of the shared History range/execution and does not create a second
scheduler or heavy request owner.

Current endpoint:

```text
GET /admin/api/v1/sites/<site_id>/traffic/current
```

Historical endpoint family:

```text
GET /admin/api/v1/sites/<site_id>/traffic/history?range=24h|7d
```

Statistics is requested through the shared History flow; there is no independent
Statistics product endpoint/scheduler.

Browser does not recompute canonical Total, Average or Peak.

## UI/design status

The current layout is production-current functional composition only.

It is **not** a permanently approved final Traffic visual design. Card order,
placement, spacing and visual polish may be changed later by a separate
UI/design TASK without changing backend/source/semantic ownership.

## Semantic restrictions

Network Throughput/History/Statistics are Mbps AP/network evidence.

Do not label them as WAN, Internet-only, billing, guest, SSID or Guest Session
Traffic.

## Lifecycle

Admin Web has no business-write worker. Failure of Admin Web remains fail-open
relative to guest authorization.
