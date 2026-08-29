# Configuration map

Status: current repository contract
Updated: 2026-08-29
Baseline: `main@8f3ad59771f72c49834b1012963de6d94b9e0d18`

Authoritative code: `app/config.py`, `app/settings.py`, `.env.example`.

The application does not automatically load `.env.example`. Production values come from process environment/approved secret handling.

## Core / Omada

| Setting | Repository default / requirement | Notes |
|---|---|---|
| `HOST` | `127.0.0.1` | application bind |
| `PORT` | `8088` | application port |
| `DEBUG` | `false` | no reloader in `run.py` |
| `VERIFY_SSL` | `false` | open security debt |
| `OMADA_URL` | required external | no secret literal |
| `OMADA_ID` | required external | controller id |
| `OMADA_CLIENT_ID` | required external | OpenAPI client |
| `OMADA_CLIENT_SECRET` | required secret | never commit/log |
| `OMADA_WEBHOOK_SITE_ID_MAP_JSON` | `{}` in example | Site-name → Site-id normalization context |

Provider construction fails closed when required core Omada configuration is missing/invalid.

## Feature groups

### Public counters / telemetry

Repository code defaults:
- `PORTAL_COUNTER_ENABLED=true`
- `PORTAL_COUNTER_API_ENABLED=true`
- `PUBLIC_TRAFFIC_COUNTER_ENABLED=true`
- `AUTH_TELEMETRY_ENABLED=true`

Storage defaults:
- `/opt/CaptivePortal/data/portal_counter.db`
- `/opt/CaptivePortal/data/public_traffic.sqlite3`
- `/opt/CaptivePortal/logs/auth_telemetry.log`

### Authorized Snapshot

Prefix: `VISITOR_SNAPSHOT_*`

Repository default: `VISITOR_SNAPSHOT_ENABLED=false`.

Important capacity/lifecycle settings:
workers, pending jobs, max job age, request timeout, retry delays, rotation, shutdown timeout.

### Visitor Registry

Prefix: `VISITOR_REGISTRY_*`

Repository default: disabled.

Controls DB path, scan interval, max line size and shutdown timeout.

### Visit Lifecycle

Prefix: `VISIT_LIFECYCLE_*`

Repository default: disabled.

Key groups:
- DB and normalized webhook source;
- reader line/byte/time budgets;
- reconciliation interval/batch;
- pending offline batch/grace;
- writer coordination (`*_WRITER_SLOT_WAIT_MS`);
- SQLite busy timeout;
- bounded Visit Start attempts/total budget;
- shutdown and offline evidence drift/skew bounds.

### Observation Foundation

Prefix: `OBSERVATION_*`

Repository default: `OBSERVATION_FOUNDATION_ENABLED=false`.

Client/AP subcollectors default enabled **inside the disabled foundation**.

Key groups:
- Site/SSID scope;
- DB;
- dynamic/config retention;
- client interval/pagination;
- AP inventory/dynamic/config intervals and request budgets;
- rate gap;
- cleanup;
- shutdown.

### Current State

Prefix: `CURRENT_STATE_*`

Repository default: disabled.

Key groups:
- Site scope;
- exact case-sensitive `CURRENT_STATE_CLIENT_SSIDS_JSON`;
- client/AP polling and pagination;
- separate client/AP fresh/stale thresholds;
- short history retention and hard client-row cap;
- cleanup;
- SQLite busy timeout;
- shutdown.

Repository defaults include 48h history retention.

### Analytics

Prefix: `ANALYTICS_*`

Repository default: foundation disabled; wireless/visit submodules default true if foundation is enabled.

Controls:
query limits/window/deadline, quality gap, wireless sample/window rules, counter gap, AP join lag, optional RSSI/SNR thresholds, visit cohort/window.

### Analytics internal API

Prefix: `ANALYTICS_API_*`

Repository default: disabled.

Requires external bearer token when enabled, plus network/Site allowlists, concurrency and response-size limits.

### Admin Web

Prefix: `WEB_ADMIN_*`

Repository default: disabled.

When enabled requires external username/password hash/Site configuration.

Security and capacity groups:
- source networks;
- Site allowlist/default Site;
- HTTPS requirement;
- idle/absolute session timeout;
- login rate limits/lock;
- pre-auth CSRF;
- bounded session/login-tracker stores;
- request/query/cursor/filter/response limits;
- bounded concurrent queries and query deadline.

At this baseline `.env.example` includes:
`127.0.0.1/32,::1/128,10.8.0.0/24`
for `WEB_ADMIN_ALLOWED_NETWORKS`, including the owner-approved VPN network.

### Home Live

Prefix: `WEB_ADMIN_HOME_LIVE_*` and `WEB_ADMIN_CURRENT_STATE_PAGE_SIZE`.

Repository default: disabled.

### Home Traffic

Prefix: `WEB_ADMIN_HOME_TRAFFIC_*`

Repository default: disabled.

Controls refresh/request timeout/page size plus fresh/stale age and maximum AP skew.

### Home Activity

Prefix: `WEB_ADMIN_HOME_ACTIVITY_*`.

Repository default: `WEB_ADMIN_HOME_ACTIVITY_ENABLED=false`.

Current contract:
- requires Admin Web + Home Live + enabled Current State scope when activated;
- guest SSIDs come from canonical `CURRENT_STATE_CLIENT_SSIDS_JSON`; no second Activity SSID list exists;
- `WEB_ADMIN_HOME_ACTIVITY_SITE_CONTEXT_JSON` supplies per-Site `timezone`, `visits_coverage_from_utc`, `traffic_coverage_from_utc`;
- Activity-only invalid configuration fails open relative to the rest of Admin/guest authorization.

Confirmed production Site context on 2026-08-26:
- Site `6a64f17630da7c70d232187a`;
- timezone `Asia/Baku`;
- Visits coverage `2026-08-26T17:46:55.982Z`;
- Traffic coverage `null`.

### Home AP-24H telemetry

Prefix: `WEB_ADMIN_HOME_AP_24H_TELEMETRY_*`.

Repository default: `WEB_ADMIN_HOME_AP_24H_TELEMETRY_ENABLED=false`.

The worker also requires active Admin Web, active Home AP-24H, the shared Admin
query controls and available Authorization Telemetry. The initial delay is
bounded to `0..3600` seconds and the fixed-delay interval to `60..3600`
seconds; repository defaults are `15` and `120` seconds respectively. Invalid
enabled telemetry configuration fails closed for this worker only.

### Traffic Section

Prefix: `WEB_ADMIN_TRAFFIC_*`.

Repository defaults:

```text
WEB_ADMIN_TRAFFIC_ENABLED=false
WEB_ADMIN_TRAFFIC_REFRESH_SECONDS=60
WEB_ADMIN_TRAFFIC_REQUEST_TIMEOUT_SECONDS=20
```

This is the Traffic product/page exposure boundary and browser orchestration policy.

It does **not** redefine Current Traffic freshness/source-selection semantics and does not start/stop shared data services.

Production evidence supplied by Owner for 2026-08-29:

```text
WEB_ADMIN_TRAFFIC_ENABLED=true
WEB_ADMIN_HOME_TRAFFIC_ENABLED=true
```

These two production flags are independent:

```text
Traffic Section flag
!=
Home Traffic flag
```

Current Network Throughput continues to use the existing shared Current Traffic policy:

```text
fresh max age = 90s
stale boundary = 180s
max AP skew = 60s
```

### Pending Session Cleaner

Prefix: `PENDING_SESSION_CLEANER_*`

Repository default: disabled.

Controls SSID scope, scan budget, uptime/grace, request/retry/verification, pagination, per-scan/per-MAC action limits, cooldown, audit rotation and shutdown.

## Production-state rule

Never write:
`repository default=false ⇒ production disabled`.

Never write:
`historical production acceptance ⇒ currently healthy`.

Production EnvironmentFile/systemd values are host facts and must be verified separately without printing secrets.
