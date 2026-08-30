# Admin Web

Status: current module contract
Updated: 2026-08-31
Baseline: `main@a9cd8a9b9b9efc46bc82d315385ebbd1a3bf63b0`

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

Forbidden: direct SQLite, Omada, Loki, Grafana or internal Analytics bearer API.

## Security

When enabled: HTTPS/source network/Site allowlist, external password hash,
pre-auth CSRF, login limits, bounded process-local sessions, idle/absolute timeout,
secure cookies, CSP/security headers and no-store.

## Query boundary

`AdminQueryService` owns Site authorization, bounded concurrency/deadline and safe
error mapping.

## Home

Home Live reads Current State. Home Traffic reads Current Traffic. Home Activity
reads Visit Lifecycle analytics. Home AP-24H reuses existing persisted/read contracts.

## Traffic Section

Traffic is a Site-scoped Admin product surface controlled by subordinate feature
boundaries.

Repository defaults:

```text
WEB_ADMIN_TRAFFIC_ENABLED=false
WEB_ADMIN_TRAFFIC_HISTORY_ENABLED=false
WEB_ADMIN_TRAFFIC_STATISTICS_ENABLED=false
WEB_ADMIN_TRAFFIC_PEAK_ENABLED=false
```

Owner-confirmed production state 2026-08-31:

```text
WEB_ADMIN_TRAFFIC_ENABLED=true
WEB_ADMIN_TRAFFIC_HISTORY_ENABLED=true
WEB_ADMIN_TRAFFIC_STATISTICS_ENABLED=true
WEB_ADMIN_TRAFFIC_PEAK_ENABLED=true
```

Current functional panels:

1. Current Network Throughput;
2. Historical Network Throughput;
3. Period Statistics;
4. Peak Load.

One shared Traffic coordinator owns page lifecycle.

History, Statistics and Peak share one selected Network range and one heavy History
request/read execution. Statistics and Peak are passive consumers; neither creates
a second scheduler/request owner.

Current endpoint:

```text
GET /admin/api/v1/sites/<site_id>/traffic/current
```

Historical endpoint family:

```text
GET /admin/api/v1/sites/<site_id>/traffic/history?range=24h|7d
GET /admin/api/v1/sites/<site_id>/traffic/history?range=24h|7d&include=statistics
GET /admin/api/v1/sites/<site_id>/traffic/history?range=24h|7d&include=statistics,peak
```

There is no standalone Peak endpoint.

Browser does not recompute canonical Total, Average, Peak, Peak timestamps,
busiest bucket or busiest 60-minute period.

## UI/design status

The current layout is production-current functional composition only.

It is **not** a permanently approved final Traffic visual design. Card order,
placement, spacing and visual polish may change later through a separate UI/design
TASK without changing backend/source/semantic ownership.

## Semantic restrictions

Network Throughput/History/Statistics/Peak are Mbps AP/network evidence.
Do not label them as WAN, Internet-only, billing, guest, SSID or Guest Session Traffic.

## Lifecycle

Admin Web has no business-write worker. Failure of Admin Web remains fail-open
relative to guest authorization.
