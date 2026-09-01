# Admin Web

Status: current module contract
Updated: 2026-09-01
Baseline: `main@daf68e91fc759188980cf8741913e6b60a58eb62`

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

Repository defaults:

```text
WEB_ADMIN_TRAFFIC_ENABLED=false
WEB_ADMIN_TRAFFIC_HISTORY_ENABLED=false
WEB_ADMIN_TRAFFIC_STATISTICS_ENABLED=false
WEB_ADMIN_TRAFFIC_PEAK_ENABLED=false
WEB_ADMIN_TRAFFIC_BY_AP_ENABLED=false
WEB_ADMIN_TRAFFIC_INDEPENDENT_RANGES_ENABLED=false
```

Owner-confirmed production state:

```text
WEB_ADMIN_TRAFFIC_ENABLED=true
WEB_ADMIN_TRAFFIC_HISTORY_ENABLED=true
WEB_ADMIN_TRAFFIC_STATISTICS_ENABLED=true
WEB_ADMIN_TRAFFIC_PEAK_ENABLED=true
WEB_ADMIN_TRAFFIC_BY_AP_ENABLED=true
WEB_ADMIN_TRAFFIC_INDEPENDENT_RANGES_ENABLED=true
```

Current functional panels:

1. Current Network Throughput;
2. Network Traffic History;
3. Period Statistics;
4. Peak Load;
5. Traffic by AP.

Current Network Throughput is range-insensitive.

History, Statistics, Peak and Traffic by AP each own an independent `24h | 7d`
selected/applied range when independent ranges are active.

## Historical endpoint

Canonical endpoint:

```text
GET /admin/api/v1/sites/<site_id>/traffic/history
```

Canonical projection:

```text
products=history,statistics,peak,aps
```

Tokens are optional by product but must remain in canonical order. Invalid,
duplicate, out-of-order, unknown, empty/whitespace projections return `400`.
`include + products` returns `400`.

Legacy `include=` remains temporary backward compatibility.

Product-scoped requests must not calculate unrelated product-specific projections.

AP-only requests use compact self-contained `ap_bucket_axis`.

## Historical frontend ownership

Canonical page-local mapping layer:

```text
TrafficHistoricalRequestBroker
```

It owns historical panel intents, coalescing, selected/applied state coordination,
generation checks and response mapping.

It is **not** scheduler owner.

Canonical scheduler/lifecycle owner:

```text
CaptivPortalTrafficCoordinator
```

Permanent invariant:

```text
max historical HTTP requests in flight from one page = 1
```

Dispatch behavior:
- initial all-24h products may coalesce;
- one panel click queues only its product;
- same-panel pending intents collapse to latest;
- same-range products may coalesce;
- explicit panel intent outranks queued Global Refresh;
- Global Refresh groups selected ranges and historical work is sequential;
- superseding one panel does not abort a shared in-flight batch;
- response applies only if generation and selected range are still current.

## Per-panel state

Every historical panel owns:

```text
selected_range
applied_range
phase
last successful payload
error
intent generation
```

Failed range switches preserve the last successful payload/applied range.

Reload defaults every historical panel to `24h`.

Range state is page-local only; no localStorage, sessionStorage, cookie, URL or
server persistence exists.

## Admission guard

Current invariant:

```text
HISTORICAL_TRAFFIC_REQUEST_ADMISSION_GUARD_SECONDS = 10
```

Eligibility:

```text
next_dispatch >= max(
    previous_request_completion,
    previous_dispatch + 10s,
    coordinator backoff / Retry-After / lifecycle eligibility
)
```

`waiting` means queued/admission-blocked. `loading` means an actual historical
HTTP request is in flight.

Manual retry, Global Refresh and 503 do not bypass the guard.

## Traffic by AP

Current production Traffic by AP uses `network_traffic_by_ap.v1` in Mbps and
shares the historical Network Traffic semantic foundation. It is not AP Traffic
Share.

## UI/design status

Current panel placement remains production-current functional composition, not a
permanently frozen final Traffic visual design.

## Semantic restrictions

Network Throughput/History/Statistics/Peak/Traffic by AP are AP/network evidence.
Do not label them as WAN, Internet-only, billing, guest, SSID or Guest Session Traffic.

## Lifecycle

Admin Web has no business-write worker. Failure of Admin Web remains fail-open
relative to guest authorization.
