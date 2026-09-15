# Configuration map

Status: current repository contract
Updated: 2026-09-13
Baseline: `main@3dc85735ddf5d05dd20733d15dfe1c22c9c4fde5`

Authoritative code: `app/config.py`, `app/settings.py`, `.env.example`.

The application does not automatically load `.env.example`. Production values come from process environment/approved secret handling.

## Device Fingerprint Evidence (default disabled)

`DEVICE_FINGERPRINT_EVIDENCE_ENABLED=false` is the repository default. The
module uses only `DEVICE_FINGERPRINT_*`: DB/lock paths, bind address/port,
direct-TLS certificate/key paths, API management CIDRs, external producer JSON,
retention and bounded request/storage limits. Defaults are in `.env.example`
and `docs/modules/device-fingerprint.md`.

When enabled, absolute distinct DB/lock and TLS paths, valid direct-peer CIDRs,
and one to 32 strict producer records are mandatory. Bearer secrets and TLS
private keys are provisioned outside Git. Source-health retention is fixed at
30 days and has no environment override.

| Variable | Repository default |
|---|---|
| `DEVICE_FINGERPRINT_DB_PATH` | `/opt/CaptivePortal/data/device_fingerprint_evidence.sqlite3` |
| `DEVICE_FINGERPRINT_WRITER_LOCK_PATH` | `/opt/CaptivePortal/data/device_fingerprint_evidence.writer.lock` |
| `DEVICE_FINGERPRINT_BIND_ADDRESS` | `192.168.0.202` |
| `DEVICE_FINGERPRINT_PORT` | `9443` |
| `DEVICE_FINGERPRINT_TLS_CERT_PATH` | `/etc/captive-portal/device-fingerprint/server.crt` |
| `DEVICE_FINGERPRINT_TLS_KEY_PATH` | `/etc/captive-portal/device-fingerprint/server.key` |
| `DEVICE_FINGERPRINT_API_ALLOWED_NETWORKS` | `192.168.0.0/24` |
| `DEVICE_FINGERPRINT_PRODUCERS_JSON` | empty/disabled-only |
| `DEVICE_FINGERPRINT_RETENTION_DAYS` | `30` (range `1..90`) |
| `DEVICE_FINGERPRINT_MAX_FUTURE_SKEW_SECONDS` | `120` (range `0..600`) |
| `DEVICE_FINGERPRINT_MAX_DELAYED_EVENT_AGE_SECONDS` | `86400` (range `60..604800`) |
| `DEVICE_FINGERPRINT_MAX_DB_BYTES` | `1073741824` (range `67108864..8589934592`) |
| `DEVICE_FINGERPRINT_MAX_HTTP_REQUEST_BYTES` | `1048576` (range `65536..4194304`) |
| `DEVICE_FINGERPRINT_MAX_EVENTS_PER_BATCH` | `100` (range `1..500`) |
| `DEVICE_FINGERPRINT_MAX_PAYLOAD_BYTES` | `8192` (range `256..65536`) |
| `DEVICE_FINGERPRINT_MAX_CONCURRENT_INGEST_REQUESTS` | `2` (range `1..8`) |

### Portal fingerprint producer (default disabled)

`DEVICE_FINGERPRINT_PORTAL_ENABLED=false` leaves the main portal without a
Task-03 worker or I/O. When enabled, the isolated configuration is frozen to
producer `portal-zefer-01`, capture source `zefer-portal-http-01`, the production
Site/guest CIDR/SSID scope, a 256-event queue, 50-event batches, 300-second
queue age, six-hour coalescing, `(0.5s, 2.0s)` HTTPS timeouts, and 30/300-second
cooldowns. The full exact variable list is in `.env.example`; the Bearer value
is never stored there. See `docs/modules/device-fingerprint-portal.md`.

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

### Device Current Context

Feature flag:

```text
WEB_ADMIN_DEVICE_CURRENT_CONTEXT_ENABLED=false
```

Repository default remains safe/opt-in `false`.

Activation dependency:

```text
WEB_ADMIN_DEVICE_CURRENT_CONTEXT_ENABLED=true
requires WEB_ADMIN_ENABLED=true
```

Owner-confirmed production state on 2026-09-09:

```text
WEB_ADMIN_DEVICE_CURRENT_CONTEXT_ENABLED=true
```

This flag controls the Current Device Context exposure/read route only. It does
not start Current State, change its collectors, add persistence or modify the
historical Device Card.

Repository default `false` must not be interpreted as production disabled.

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

### Home System Health

Prefix: `WEB_ADMIN_HOME_HEALTH_*`.

Repository defaults:

```text
WEB_ADMIN_HOME_HEALTH_ENABLED=false
WEB_ADMIN_HOME_HEALTH_REFRESH_SECONDS=60
WEB_ADMIN_HOME_HEALTH_REQUEST_TIMEOUT_SECONDS=30
WEB_ADMIN_HOME_HEALTH_AUTH_EVIDENCE_MAX_AGE_SECONDS=86400
```

The feature is Admin-only/read-only and fails open relative to guest
authorization. Repository default `false` is not evidence of production
disablement.

### Home AP-24H

Repository defaults:

```text
WEB_ADMIN_HOME_AP_24H_ENABLED=false
WEB_ADMIN_HOME_AP_24H_REFRESH_SECONDS=120
WEB_ADMIN_HOME_AP_24H_REQUEST_TIMEOUT_SECONDS=30
```

The read model is bounded/read-only over persisted Current State + Observation
facts. It adds no query-time Omada path, DB or collector.

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
WEB_ADMIN_TRAFFIC_HISTORY_ENABLED=false
WEB_ADMIN_TRAFFIC_STATISTICS_ENABLED=false
WEB_ADMIN_TRAFFIC_PEAK_ENABLED=false
WEB_ADMIN_TRAFFIC_BY_AP_ENABLED=false
WEB_ADMIN_TRAFFIC_INDEPENDENT_RANGES_ENABLED=false
WEB_ADMIN_TRAFFIC_AP_SHARE_ENABLED=false
WEB_ADMIN_TRAFFIC_ONLINE_GUESTS_ENABLED=false
WEB_ADMIN_TRAFFIC_COMPLETED_SESSIONS_ENABLED=false
WEB_ADMIN_TRAFFIC_EVIDENCE_ENABLED=false
WEB_ADMIN_TRAFFIC_REFRESH_SECONDS=60
WEB_ADMIN_TRAFFIC_REQUEST_TIMEOUT_SECONDS=30
```

Production state 2026-09-08:

```text
WEB_ADMIN_TRAFFIC_ENABLED=true
WEB_ADMIN_TRAFFIC_HISTORY_ENABLED=true
WEB_ADMIN_TRAFFIC_STATISTICS_ENABLED=true
WEB_ADMIN_TRAFFIC_PEAK_ENABLED=true
WEB_ADMIN_TRAFFIC_BY_AP_ENABLED=true
WEB_ADMIN_TRAFFIC_INDEPENDENT_RANGES_ENABLED=true
WEB_ADMIN_TRAFFIC_AP_SHARE_ENABLED=true
WEB_ADMIN_TRAFFIC_ONLINE_GUESTS_ENABLED=true
WEB_ADMIN_TRAFFIC_COMPLETED_SESSIONS_ENABLED=true
WEB_ADMIN_TRAFFIC_EVIDENCE_ENABLED=true
```

Feature dependencies:

```text
History requires Admin + Traffic.
Statistics requires Admin + Traffic + History.
Peak requires Admin + Traffic + History + Statistics.
Traffic by AP requires Admin + Traffic + History.
Independent ranges requires Admin + Traffic + History.
AP Traffic Share requires Admin + Traffic + History + Independent ranges.
Online Guests Traffic requires Admin + Traffic only.
Completed Guest Session Traffic requires Admin + Traffic only; it reads Visit +
Observation persistence and does not require Historical Traffic Projection.
Traffic Evidence requires Admin + Traffic and its endpoint authorizes both
`admin.read.overview` and `admin.read.devices`.

Repository defaults remain opt-in/off for Online Guests, Completed Sessions and
Traffic Evidence. Owner-confirmed production activation is `true` for all three.
```

Independent ranges does **not** require every optional historical product to be
enabled. It changes historical product range/request orchestration for whichever
historical products are enabled.

These are product-exposure/orchestration flags. They do not start/stop Observation,
`CurrentTrafficReadService` or `HistoricalTrafficReadService`.

### Historical Traffic projection

The derived projection has two independent, repository-default-off controls:

```text
TRAFFIC_PROJECTION_ENABLED=false
TRAFFIC_PROJECTION_DB_PATH=/opt/CaptivePortal/data/traffic_projection.sqlite3
TRAFFIC_PROJECTION_WRITER_LOCK_PATH=/opt/CaptivePortal/data/traffic_projection.writer.lock
WEB_ADMIN_TRAFFIC_PROJECTION_READ_ENABLED=false
```

The worker is a separate process (`python -m app.traffic_projection.cli run`) and
reads the existing Observation database in SQLite read-only/query-only mode. The
Admin read flag switches History, Statistics, Peak, Traffic by AP and AP Share as
one bundle. It never falls back automatically to raw reconstruction. Build,
`mark-ready`, `activate`, `repair-site`, and cleanup are explicit CLI operations;
production execution requires separate Owner authorization.

Current Network Throughput shared policy remains:

```text
fresh max age = 90s
stale boundary = 180s
max AP skew = 60s
```

Historical product ranges:

```text
24h
7d
```

With independent ranges enabled, History, Statistics, Peak, Traffic by AP and AP Traffic Share each own independent page-local selected/applied range state. Current Network Throughput remains range-insensitive.

At acceptance of `TASK-TRAFFIC-RANGE-01`, the historical limits were:

```text
HISTORICAL_TRAFFIC_REQUEST_ADMISSION_GUARD_SECONDS=10
WEB_ADMIN_MAX_QUERY_DURATION_SECONDS=10
Traffic browser request timeout=20s
Admin concurrency=unchanged
```

RANGE-01 itself did not increase these limits.

Current production baseline after `TASK-ADMIN-PROD-BASELINE-01` (2026-09-05):

```text
HISTORICAL_TRAFFIC_REQUEST_ADMISSION_GUARD_SECONDS=3
WEB_ADMIN_MAX_QUERY_DURATION_SECONDS=25
dependent Admin/Home request timeouts=30s
WEB_ADMIN_MAX_CONCURRENT_QUERIES=4
```

Repository default=false must not be rewritten as production disabled.

### Historical Traffic projection — production lifecycle state

Repository defaults remain safe/off unless separately configured:

```text
TRAFFIC_PROJECTION_ENABLED=false
WEB_ADMIN_TRAFFIC_PROJECTION_READ_ENABLED=false
```

Repository default values do not describe current production runtime.

Owner-confirmed production recovery on 2026-09-11 ended with:

```text
traffic-projection.service=active + enabled
projection_version=historical_traffic_projection.v1
version_status=active
Site health=healthy
```

Canonical worker runtime environment is supplied by:

```text
/etc/systemd/system/traffic-projection.service
EnvironmentFile=/etc/default/captive-portal
User=admin
Group=admin
WorkingDirectory=/opt/CaptivePortal
ExecStart=/usr/bin/python3 -m app.traffic_projection.cli run
```

Production CLI/repair must use the canonical worker environment rather than an
arbitrary interactive shell environment. Secret values are never recorded in KB.

### TASK-TEST-BASELINE-CLEANUP-01

This production delivery changed no configuration contract:

```text
configuration changes=NO
feature flag changes=NO
systemd unit changes=NO
DB/schema changes=NO
```

### Device Type normalization / presentation tasks

`TASK-DEVICE-TYPE-NORMALIZATION-01` and
`TASK-WEB-DEVICE-TYPE-PRESENTATION-01` introduce no new configuration key,
feature flag, DB migration or systemd setting.

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

### Device Fingerprint sensor

All `DEVICE_FINGERPRINT_SENSOR_*` variables are parsed exclusively by
`app/device_fingerprint_sensor/config.py`. The main application settings path
does not parse them. Repository default is
`DEVICE_FINGERPRINT_SENSOR_ENABLED=false`. The Bearer credential is supplied
through systemd `LoadCredential`; it is never stored in `.env.example`.
