# Admin Web

Status: current module contract
Updated: 2026-08-29
Baseline: `main@8f3ad59771f72c49834b1012963de6d94b9e0d18`

## Boundary

Admin authentication is separate from guest Portal authentication.

Current UI pages:
Home, Devices, Device Detail, Visits, Observations, Traffic.

Current optional Home increments:
- Home Live — Current State;
- Home Traffic — Current Traffic;
- Home Activity — Authorized Visits + completed-session Traffic;
- Home AP-24H — persisted Current State and Observation history.

Home Activity is current code. Repository default remains disabled; production activation is a separate fact.

## Browser data path

`browser → same-origin /admin + /admin/api/v1 → AdminQueryService/read gateways → persisted read services`.

Forbidden browser dependencies:
SQLite, Omada, Loki, Grafana, internal Analytics bearer API.

## Security

When enabled:
- HTTPS required;
- source network allowlist;
- Site allowlist/default Site;
- username + external password hash;
- pre-auth CSRF;
- login rate limiter;
- bounded in-memory session store;
- idle + absolute timeout;
- Secure/HttpOnly/SameSite cookies;
- logout CSRF;
- CSP, frame deny, nosniff, no-referrer, no-store.

Repository default source allowlist includes owner VPN `10.8.0.0/24`.

## Query boundary

`AdminQueryService` applies Site authorization, bounded concurrent query slots, deadlines, pagination/cursor validation and safe error mapping.

No stack trace/SQLite internals should escape to browser.

## Read-only product contract

Business/data endpoints are GET-only.

POST `/admin/login` and `/admin/logout` mutate only Admin security/session state.

Client control actions discovered in Omada research are not exposed here without a later policy/audit TASK.

## Home Live

Reads `CurrentStateReadService`.

Shows authorized/pending/other/unknown and AP/current device summaries with explicit freshness/degraded states.

## Home Traffic

Reads `CurrentTrafficReadService` through Admin query boundary.

Traffic source freshness/unavailable/partial states must be preserved; missing data is not rendered as zero.

## Home Activity

Reads `HomeActivityReadService` through the Admin query boundary. The UI must preserve independent Visits/Traffic status and coverage. `Unknown/unproven guest scope != 0`. Today/selected ranges are Site-timezone aware; no artificial 31/90-day Activity limit exists.

Confirmed production Site context on 2026-08-26:
- Site `6a64f17630da7c70d232187a`, timezone `Asia/Baku`;
- Visits coverage from `2026-08-26T17:46:55.982Z`;
- Traffic coverage start remains `null`.

## Traffic Section

The Traffic page is a separate Site-scoped Admin product surface controlled by `WEB_ADMIN_TRAFFIC_ENABLED`.

Current foundation owns one shared browser coordinator. Panels register into that coordinator; panels must not create competing page schedulers, visibility/pagehide owners or global Refresh owners.

Current Network Throughput endpoint:

```text
GET /admin/api/v1/sites/<site_id>/traffic/current
```

No query parameters.

Backend path:

```text
AdminQueryService.current_traffic_summary(...)
→ CurrentTrafficReadService.get_current_site_traffic(...)
→ serialize_current_traffic_summary(...)
```

The browser renders backend `total_mbps`; it does not recompute Total.

Traffic and Home Traffic remain separate UI/feature flags while sharing the same Current Traffic semantic owner.

Traffic Network Throughput is AP/network evidence and must not be labelled as WAN, Internet-only, billing, guest, SSID or Guest Session Traffic.

## Lifecycle

Admin Web has no business-write worker. Optional AP-24H operational telemetry
uses one process-local fixed-delay worker and the existing shared query
concurrency/deadline controls. It calls the already-composed
`HomeAp24ReadService`; it does not read SQLite, call Admin HTTP endpoints or
contact Omada independently. Shutdown stops this worker before Current State
and Observation sources, then clears process-local security/session state.

AP-24H telemetry is repository-default-disabled, bounded to the first 20 AP
details and emitted through the existing `auth_telemetry.log` pipeline. It is
lossy/fail-open operational evidence, not the AP-24H source of truth. Missing
telemetry does not prove missing persisted AP evidence, and downstream
Grafana/Loki consumers must not recreate AP state from raw source events.

Failure leaves `/admin` unavailable/degraded but must not abort guest authorization.
