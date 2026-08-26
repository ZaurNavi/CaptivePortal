# Admin Web

Status: current module contract
Updated: 2026-08-26
Baseline: `main@53f617b3ac0155d0d647e58e98309927f9a4d318`

## Boundary

Admin authentication is separate from guest Portal authentication.

Current UI pages:
Home, Devices, Device Detail, Visits, Observations.

Current optional Home increments:
- Home Live — Current State;
- Home Traffic — Current Traffic;
- Home Activity — Authorized Visits + completed-session Traffic.

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

## Lifecycle

Admin Web has no business worker. Shutdown clears process-local security/session state.

Failure leaves `/admin` unavailable/degraded but must not abort guest authorization.
