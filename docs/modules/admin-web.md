# Admin Web

Status: current module contract
Updated: 2026-09-03
Baseline: `main@6425988b5b4ec5ff38bf9c67c74846c3806f668f`

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

Repository defaults include:

```text
WEB_ADMIN_TRAFFIC_ENABLED=false
WEB_ADMIN_TRAFFIC_HISTORY_ENABLED=false
WEB_ADMIN_TRAFFIC_STATISTICS_ENABLED=false
WEB_ADMIN_TRAFFIC_PEAK_ENABLED=false
WEB_ADMIN_TRAFFIC_BY_AP_ENABLED=false
WEB_ADMIN_TRAFFIC_INDEPENDENT_RANGES_ENABLED=false
WEB_ADMIN_TRAFFIC_AP_SHARE_ENABLED=false
WEB_ADMIN_TRAFFIC_ONLINE_GUESTS_ENABLED=false
```

Owner-confirmed production state includes:

```text
WEB_ADMIN_TRAFFIC_ENABLED=true
WEB_ADMIN_TRAFFIC_HISTORY_ENABLED=true
WEB_ADMIN_TRAFFIC_STATISTICS_ENABLED=true
WEB_ADMIN_TRAFFIC_PEAK_ENABLED=true
WEB_ADMIN_TRAFFIC_BY_AP_ENABLED=true
WEB_ADMIN_TRAFFIC_INDEPENDENT_RANGES_ENABLED=true
WEB_ADMIN_TRAFFIC_AP_SHARE_ENABLED=true
WEB_ADMIN_TRAFFIC_ONLINE_GUESTS_ENABLED=true
```

Current functional panels:

1. Current Network Throughput;
2. Network Traffic History;
3. Period Statistics;
4. Peak Load;
5. Traffic by AP;
6. AP Traffic Share;
7. Online Guests Traffic.

Historical Traffic endpoint:

```text
GET /admin/api/v1/sites/<site_id>/traffic/history
products=history,statistics,peak,aps,apshare
```

Online Guests endpoint:

```text
GET /admin/api/v1/sites/<site_id>/traffic/online-guests/current
```

Online Guests query contract:

```text
limit default=50
limit max=200
cursor=opaque
capability=admin.read.devices
```

Canonical path:

```text
Current State
→ CurrentStateReadService
→ CurrentGuestTrafficReadService
→ AdminQueryService
→ Admin API
→ Online Guests Traffic
```

`CurrentGuestTrafficReadService` is the semantic owner. The browser renders
validated payloads and does not calculate traffic rates.

Online Guests Traffic is range-insensitive and does not use
`TrafficHistoricalRequestBroker` or the historical 10-second admission guard.

Historical History/Statistics/Peak/Traffic by AP/AP Share retain independent
page-local `24h | 7d` selected/applied range state.

## Online Guests semantic boundary

Online Guest means controller-reported active authorized wireless guest in the
latest accepted Current State guest scope. It is not independent proof of
instantaneous physical RF presence.

The panel presents Online Guest, SSID, AP, Download, Upload, Total, Evidence,
Online Guest count, Population completeness, Rate Evidence, Source Health,
observed time and interval.

## UI/design status

Current panel placement remains production-current functional composition, not a
permanently frozen final Traffic visual design.

## Semantic restrictions

Network Throughput/History/Statistics/Peak/Traffic by AP/AP Traffic Share are AP/network evidence.
Do not label them as WAN, Internet-only, billing, guest, SSID or Guest Session Traffic.

## Lifecycle

Admin Web has no business-write worker. Failure of Admin Web remains fail-open
relative to guest authorization.
