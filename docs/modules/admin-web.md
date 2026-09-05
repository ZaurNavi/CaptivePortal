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

Repository defaults:

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

Owner-confirmed production state:

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

Current Network Throughput is range-insensitive.

History, Statistics, Peak, Traffic by AP and AP Traffic Share each own an independent `24h | 7d`
selected/applied range when independent ranges are active.

## Historical endpoint

Canonical endpoint:

```text
GET /admin/api/v1/sites/<site_id>/traffic/history
```

Canonical projection:

```text
products=history,statistics,peak,aps,apshare
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
HISTORICAL_TRAFFIC_REQUEST_ADMISSION_GUARD_SECONDS = 3
```

Eligibility:

```text
next_dispatch >= max(
    previous_request_completion,
    previous_dispatch + 3s,
    coordinator backoff / Retry-After / lifecycle eligibility
)
```

`waiting` means queued/admission-blocked. `loading` means an actual historical
HTTP request is in flight.

Manual retry, Global Refresh and 503 do not bypass the guard.

## Traffic by AP

Current production Traffic by AP uses `network_traffic_by_ap.v1` in Mbps and shares the historical Network Traffic semantic foundation.

## AP Traffic Share

Current production AP Traffic Share uses `network_traffic_ap_share.v1`; internal unit is `fraction`, display unit is `percent`, and product token is `apshare`.

AP Share requires Admin + Traffic + History + Independent Ranges. It has its own page-local `24h | 7d` selected/applied range and uses the existing broker/coordinator/admission path.

## Online Guests Traffic

Canonical endpoint:

```text
GET /admin/api/v1/sites/<site_id>/traffic/online-guests/current
```

Query contract:

```text
limit default=50
limit max=200
cursor=opaque continuation cursor
capability=admin.read.devices
```

Canonical path:

```text
Current State
→ CurrentStateReadService
→ CurrentGuestTrafficReadService
→ AdminQueryService
→ Admin API
```

`CurrentGuestTrafficReadService` is the semantic owner. The browser validates and
renders payloads; it does not calculate current guest rates.

Online Guests Traffic is range-insensitive and does not use the historical
`TrafficHistoricalRequestBroker` / 3-second admission guard.

Online Guest means controller-reported active authorized wireless guest in the
latest accepted Current State guest scope, not independent proof of
instantaneous physical RF presence.

## UI/design status

Current panel placement remains production-current functional composition, not a
permanently frozen final Traffic visual design.

## Semantic restrictions

Network Throughput/History/Statistics/Peak/Traffic by AP/AP Traffic Share are AP/network evidence.
Do not label them as WAN, Internet-only, billing, guest, SSID or Guest Session Traffic.

## Lifecycle

Admin Web has no business-write worker. Failure of Admin Web remains fail-open
relative to guest authorization.
