# TASK-WEB-FOUNDATION-01 — Web Foundation v1

**Project:** CaptivPortal  
**Type:** master architecture / implementation specification  
**Status:** DRAFT FOR TECH LEAD / OWNER REVIEW  
**Implementation authorization:** NOT GRANTED  
**Review:** Architect + Tech Lead + Owner  
**Architecture preparation date:** 2026-08-21  
**Architecture preparation baseline:** `origin/main@3173d0a16dd33b2cff25bbd9c4921b35559bc259`  
**Analytics 02A merge:** PR #52 / `97a9a246938e8d6425db744fb2f085555eb6e5c8`  
**Analytics 02A production activation:** PASS — confirmed by Owner  
**Production activation of Web Foundation:** separate owner-controlled TASK

---

## 1. Purpose

Implement the next roadmap stage:

```text
TASK-WEB-FOUNDATION-01
```

Web Foundation creates the first native administrative application/web boundary of CaptivPortal on top of the completed data and Analytics layers.

```text
Observation / Registry / Visit
            ↓
Analytics Foundation
            ↓
Analytics 02A production runtime
            ↓
Web Foundation
  ├─ Admin authentication boundary
  ├─ Admin session boundary
  ├─ Site context
  ├─ permissions-ready access policy
  ├─ Admin Query Service
  ├─ read-only Admin API
  └─ minimal read-only internal UI
            ↓
future CaptivPortal Admin Console
```

This is **not** the full commercial Admin Console. It establishes the contracts that the later product UI can extend without rebuilding security, Site scoping, application/query services, errors and navigation.

---

## 2. Current baseline

At preparation time current GitHub main is:

```text
3173d0a16dd33b2cff25bbd9c4921b35559bc259
```

Recent accepted merges:

```text
PR #52 / 97a9a246  Analytics protected production read API
PR #53 / 6ba89900  VLAN20 transition network
PR #54 / 3173d0a1  Observation startup readiness hotfix
```

Owner separately confirmed:

```text
Analytics 02A production activation = PASS
```

Before each future execution PR, `origin/main` must be re-pinned and compared if newer.

Impact review is mandatory if current changes touch:

```text
app/analytics/**
app/web/**
run.py
app/config.py
app/settings.py
Visitor Registry read contracts
Visit Lifecycle read contracts
Observation read contracts
Flask / ProxyFix security behavior
```

---

## 3. Existing architecture to preserve

```text
single application process
run.py = lifecycle/composition root
app/web/web.py:create_app() = Flask application factory
one shared OmadaProvider
one shared Omada OAuth/token lifecycle
AuthSession/AuthWorker = visitor authorization
Observation / Visit / Registry = authoritative persisted facts
Analytics = read-only application analytics
Grafana/Loki = internal engineering observability
```

Analytics 02A already exposes:

```text
/api/internal/analytics/v1
```

with dedicated Bearer auth, network allowlist, Site allowlist, GET-only aggregate queries, response limits, concurrency guard and safe serialization.

Web Foundation must coexist with 02A and must not weaken or replace it.

---

## 4. Permanent boundaries

### 4.1 Visitor auth != Admin auth

Never use as administrator authentication:

```text
AuthSession
AuthWorker
CAPPORT state
Omada guest authStatus
Hotspot authorization
visitor MAC
```

### 4.2 Admin UI != Grafana

Forbidden:

```text
Admin UI → Grafana API → Loki
```

Correct:

```text
Admin UI → Admin API / Query Service
         → Analytics / source read services
         → authoritative persistence
```

### 4.3 Web does not collect or mutate business facts

Web Foundation:

```text
does not poll Omada
does not create history
does not modify Observation / Registry / Visit
does not create derived Analytics persistence
```

### 4.4 Site-aware, single-tenant

Current model:

```text
Site-aware
single-tenant
single platform owner/operator
```

Do not introduce tenant, billing, customer accounts or full RBAC. Preserve `site_id` everywhere it naturally belongs.

---

## 5. v1 administrative principal

Web Foundation v1 is an **internal owner/operator interface**.

Conceptual principal:

```text
AdminPrincipal
  principal_type = platform_operator
  username
```

Current implementation may support exactly one configured operator credential.

The authorization contract must nevertheless be permissions-ready, so a later RBAC/customer identity implementation can replace policy decisions without route/query rewrites.

---

## 6. Browser must not use the 02A bearer token

Forbidden:

```text
bearer in JavaScript
bearer in HTML
bearer in localStorage/sessionStorage
bearer in browser cookie
bearer in URL/query
```

Correct browser flow:

```text
Browser
→ Admin session cookie
→ /admin/api/v1
→ AdminQueryService
→ in-process Analytics/source read services
```

The internal Analytics API remains an independent owner/tool API.

Also forbidden:

```text
AdminQueryService
→ loopback HTTP call
→ /api/internal/analytics/v1
```

Use typed in-process services instead.

---

## 7. New package boundary

Preferred:

```text
app/admin_web/
├── __init__.py
├── config.py
├── models.py
├── security.py
├── sessions.py
├── rate_limit.py
├── access_policy.py
├── site_context.py
├── query_service.py
├── serialization.py
├── api.py
├── pages.py
├── runtime.py
├── telemetry.py
├── templates/admin/
└── static/admin/
```

Do not place Admin authentication in `app/auth/`; that package belongs to visitor authorization.

---

## 8. Runtime composition

Preferred conceptual contract:

```text
create_admin_web_runtime(
    settings,
    analytics_runtime,
    registry_read_service,
    visit_read_service,
    observation_read_service,
    logger,
)
```

Composition order:

```text
create existing portal app
→ create/start Registry / Observation / Visit
→ create Analytics runtime
→ create Admin Web runtime
→ register Admin page/API blueprints
→ start Flask server
```

No Admin thread at import. No periodic Admin worker.

Runtime may own:

```text
AdminWebConfig
AdminSessionStore
AdminLoginRateLimiter
AdminAccessPolicy
AdminQueryService
Admin page blueprint
Admin API blueprint
```

---

## 9. Runtime states

```text
disabled
active
unavailable
```

### disabled

`WEB_ADMIN_ENABLED=false`:

- no `/admin` routes;
- no credential validation;
- no session store;
- portal unchanged.

### active

Security config valid and required read/query boundaries available.

### unavailable

Security config valid but one or more data sources unavailable.

- login/shell may remain safe;
- affected data endpoints return sanitized `503`;
- portal authorization is unaffected.

Invalid Admin security configuration:

```text
fail closed for Admin Web
fail open for Captive Portal
```

---

## 10. Configuration contract

Through existing pipeline only:

```text
app/config.py → app/settings.py:get_settings() → AdminWebConfig
```

Repository-safe defaults:

```text
WEB_ADMIN_ENABLED=false
WEB_ADMIN_USERNAME=
WEB_ADMIN_PASSWORD_HASH=
WEB_ADMIN_ALLOWED_NETWORKS=127.0.0.1/32,::1/128
WEB_ADMIN_ALLOWED_SITE_IDS=
WEB_ADMIN_DEFAULT_SITE_ID=
WEB_ADMIN_REQUIRE_HTTPS=true
WEB_ADMIN_SESSION_IDLE_SECONDS=1800
WEB_ADMIN_SESSION_ABSOLUTE_SECONDS=28800
WEB_ADMIN_LOGIN_WINDOW_SECONDS=300
WEB_ADMIN_LOGIN_MAX_FAILURES=5
WEB_ADMIN_LOGIN_LOCK_SECONDS=900
WEB_ADMIN_MAX_CONCURRENT_QUERIES=2
WEB_ADMIN_MAX_RESPONSE_BYTES=1048576
WEB_ADMIN_DEVICE_PAGE_SIZE=100
WEB_ADMIN_VISIT_PAGE_SIZE=100
WEB_ADMIN_OBSERVATION_PAGE_SIZE=100
WEB_ADMIN_OBSERVATION_MAX_WINDOW_HOURS=24
```

No production username/hash/Site in Git. `.env.example` contains placeholders only.

---

## 11. Configuration validation

When enabled:

- username non-empty after trim;
- password hash non-empty and accepted by current Werkzeug verifier;
- valid unique IPv4/IPv6 CIDRs;
- non-empty unique canonical Site IDs;
- default Site must belong to allowed Sites;
- secrets/hashes redacted in repr/errors.

Bounds:

```text
idle seconds          60..86400
absolute seconds      idle..604800
login window          60..3600
max failures          1..50
lock seconds          60..86400
concurrent queries    1..8
max response bytes    65536..4194304
page sizes            1..500
observation max hours 1..168
```

---

## 12. Credential contract

No plaintext admin password in repository configuration.

Use:

```text
WEB_ADMIN_PASSWORD_HASH
```

generated outside Git with current Werkzeug-supported password hashing.

Verification:

```text
werkzeug.security.check_password_hash()
```

Forbidden:

```text
plaintext comparison
raw SHA256(password)
password in JS/log/URL/telemetry
```

Treat password hash as sensitive operational configuration and never print it in handoff output.

---

## 13. Admin session architecture

v1 uses opaque server-side process-local sessions.

Cookie contains only:

```text
random session token
```

Server memory contains:

```text
session token
principal
created_at monotonic/wall
last_seen monotonic
csrf token
```

Generate tokens with `secrets` and at least 256 bits of entropy.

No password/hash/02A bearer in the session.

---

## 14. Process-local session limitation

Current production is one application process, so process-local Admin sessions are accepted in v1.

```text
application restart → Admin sessions invalid → login again
```

Before multi-worker/HA/customer accounts, a separate authentication/session ADR is mandatory.

---

## 15. Cookie contract

Cookie:

```text
captivportal_admin_session
```

Required attributes:

```text
HttpOnly
Secure
SameSite=Strict
Path=/admin
```

No Domain by default.

Logout revokes server-side session immediately and deletes the cookie.

Session token never appears in URL/HTML/JS/log/telemetry/error.

---

## 16. Session lifetime

Independent limits:

```text
idle timeout
absolute timeout
```

Both must be valid.

Idle may extend on authenticated Admin activity. Absolute deadline never extends.

Use monotonic time for runtime expiry decisions.

Expired:

```text
HTML → redirect /admin/login
API  → 401 JSON
```

---

## 17. Session fixation protection

On successful login:

1. discard pre-auth/old token;
2. generate new random session token;
3. generate new CSRF token;
4. bind principal;
5. set new cookie.

Never upgrade an attacker-supplied token in place.

---

## 18. Login/logout endpoints

```text
GET  /admin/login
POST /admin/login
POST /admin/logout
```

No GET logout.

Login fields:

```text
username
password
csrf_token
```

Wrong username/password must return the same generic message.

No username existence leak.

---

## 19. CSRF

Login CSRF is required.

Preferred pre-auth flow:

```text
GET login → short-lived pre-auth CSRF
POST login → validate CSRF → network/HTTPS → rate limit → credentials
```

Authenticated state-changing Admin requests require CSRF.

Current only state-changing endpoint after login:

```text
POST /admin/logout
```

Reserve future JSON header:

```text
X-CSRF-Token
```

No write business API is authorized by this reservation.

---

## 20. Login brute-force guard

Bounded in-memory protection keyed primarily by source IP.

Defaults:

```text
5 failures / 300 sec → 900 sec lock
```

Requirements:

- rolling window;
- temporary lock;
- bounded cleanup;
- generic failure response;
- no password/hash in telemetry.

Restart resets limiter; accepted single-process limitation.

---

## 21. HTTPS boundary

Production Admin Web must be HTTPS-only.

With:

```text
WEB_ADMIN_REQUIRE_HTTPS=true
```

an insecure `/admin/*` request fails closed.

Use existing trusted ProxyFix model.

Do not set authenticated Secure cookie over HTTP.

---

## 22. Network boundary

Every `/admin/*` route, including login, requires:

```text
request.remote_addr ∈ WEB_ADMIN_ALLOWED_NETWORKS
```

using the existing one-trusted-Nginx-hop model.

Denied source:

```text
403 before credential verification
```

Default is loopback only. Production may explicitly allow management LAN/VPN.

---

## 23. Security headers

All Admin HTML/API:

```text
Cache-Control: no-store
Pragma: no-cache
X-Content-Type-Options: nosniff
Referrer-Policy: no-referrer
X-Frame-Options: DENY
```

Admin HTML CSP:

```text
default-src 'self';
script-src 'self';
style-src 'self';
img-src 'self' data:;
connect-src 'self';
object-src 'none';
base-uri 'none';
frame-ancestors 'none';
form-action 'self'
```

No third-party CDN.

No permissive CORS on Admin API.

---

## 24. Open redirect prevention

Any `next` value must be a relative `/admin/...` path only.

No scheme/netloc. Invalid target falls back to default Site Admin home.

---

## 25. Permissions-ready policy

Introduce:

```text
AdminAccessPolicy.authorize(principal, capability, site_id)
```

v1 read capabilities:

```text
admin.read.context
admin.read.overview
admin.read.devices
admin.read.device
admin.read.visits
admin.read.observations
```

v1 rule:

```text
authenticated platform_operator
AND site_id allowed
→ allow read capability
```

No write capabilities. No entitlements/RBAC DB.

---

## 26. Site authorization

Site must be checked:

1. at HTTP boundary;
2. again at AdminQueryService/access-policy boundary.

Frontend hiding is not authorization.

Preferred URL shape:

```text
/admin/sites/{site_id}/...
/admin/api/v1/sites/{site_id}/...
```

`/admin/` may redirect to configured default Site only after authentication and server-side Site validation.

No hardcoded production Site.

---

## 27. Site selector

If only one Site is allowed, UI may show context without selector.

If multiple configured Sites are allowed, a simple selector may navigate to another explicit Site URL.

No tenant persistence.

Never assume:

```text
tenant_id == site_id
```

---

## 28. Admin Query Service

Routes must not query SQLite repositories directly.

Introduce:

```text
AdminQueryService
```

Dependencies may include:

```text
AnalyticsReadService
WirelessAnalyticsService
VisitAnalyticsService
VisitorRegistryReadService
VisitLifecycleReadService
ObservationReadService
AdminAccessPolicy
```

Service responsibilities:

1. authorize capability/Site;
2. validate query bounds;
3. call authoritative read/query service;
4. map safe Admin DTO;
5. never mutate source state.

---

## 29. Source extension rule

Preferred sources are existing read services.

If a required Site-safe list/detail query is missing, an execution TASK may add a narrow read-only method.

Allowed source extension:

```text
SELECT / read-only
batch/set-based support
Site-safe query support
```

Forbidden:

```text
schema migration
INSERT/UPDATE/DELETE
collector change
Visit finalization change
Registry writer change
```

---

## 30. Site-safe Device membership

Registry identity is global-by-MAC. Therefore `last_site_id` is not permanent device ownership.

A device belongs in a requested Site view only when Site-scoped evidence exists, e.g.:

```text
Site snapshot
OR
Site Visit link
```

Exact query must be bounded and set-based.

Never assume one MAC/device_id forever belongs to one Site.

---

## 31. Device list DTO

Minimal internal fields:

```text
device_id
canonical_mac
device_type
site_first_seen_at
site_last_seen_at
site_snapshot_count
site_visit_count
last_site_ip
last_site_ssid
last_site_ap_mac
```

Full technical MAC is allowed in this internal owner UI.

`last_site_*` must be derived from requested Site evidence, not Registry global last context.

No raw snapshot JSON.

---

## 32. Device Card

Minimum:

```text
identity
Site-local first/last seen
Site snapshot count
Site visit count
recent Site visits
latest safe Site snapshot summary
bounded client observation summary
```

Do not infer person identity.

---

## 33. Visit list

Site-scoped fields:

```text
visit_id
device_id
client_mac
started_at
closed_at
status
duration_seconds
start_ssid
final_ssid
start_ap_mac
final_ap_mac
reported_traffic_total_bytes
```

Filters may include time/status/MAC/device/SSID/AP.

Pagination mandatory.

No mutation/reconstruction.

---

## 34. Observation lookup

Client:

```text
site_id
client_mac
from_utc
to_utc
limit
cursor
```

AP/radio:

```text
site_id
ap_mac
from_utc
to_utc
limit
cursor
```

Default raw max window:

```text
24h
```

Hard page cap <=500.

---

## 35. Safe Observation fields

Client allowlist:

```text
observed_at client_mac ip ssid ap_name ap_mac radio_id band channel
rssi snr rx_rate tx_rate traffic_down traffic_up uptime auth_status active
```

AP allowlist:

```text
observed_at ap_mac name ip model firmware_version cpu_util mem_util
uptime_seconds wired_download_mbps wired_upload_mbps lan_rx_mbps lan_tx_mbps partial
```

Radio allowlist:

```text
radio_observed_at ap_mac band radio_id actual_channel frequency_mhz
channel_width tx_power tx_util rx_util interference_util busy_util
radio_rx_mbps radio_tx_mbps
```

Forbidden UI data:

```text
raw controller JSON
raw snapshot JSON
auth_context_json
client_json
raw_controller_snapshot_json
AP override/password payloads
Omada tokens/secrets
filesystem paths
SQLite internals
```

---

## 36. Analytics bridge

Web Foundation must prove native application use of Analytics without Grafana.

Minimum summaries:

```text
Site Visit counts
Site unique-device counts
```

through existing VisitAnalyticsService methods.

Optional internal source-quality display may use 01A.

Do not expose every engineering Analytics diagnostic in Web v1.

---

## 37. Admin API namespace

```text
/admin/api/v1
```

Separate from:

```text
/api/internal/analytics/v1
```

Authentication is Admin session cookie, not bearer.

Data API is GET-only in Web Foundation v1.

---

## 38. Admin API endpoints

Session/context:

```text
GET /admin/api/v1/session
GET /admin/api/v1/sites
GET /admin/api/v1/health
```

Summaries:

```text
GET /admin/api/v1/sites/{site_id}/summary/visits
GET /admin/api/v1/sites/{site_id}/summary/devices
```

Devices:

```text
GET /admin/api/v1/sites/{site_id}/devices
GET /admin/api/v1/sites/{site_id}/devices/{device_id}
```

Visits:

```text
GET /admin/api/v1/sites/{site_id}/visits
GET /admin/api/v1/sites/{site_id}/visits/{visit_id}
```

Observations:

```text
GET /admin/api/v1/sites/{site_id}/observations/clients
GET /admin/api/v1/sites/{site_id}/observations/aps
```

Exact signatures belong to execution TASK 01B.

---

## 39. Admin API envelope

Success:

```json
{
  "api_version": "admin.read.v1",
  "request_id": "<uuid>",
  "site_id": "<site-or-null>",
  "result": {},
  "page": null
}
```

Error:

```json
{
  "api_version": "admin.read.v1",
  "request_id": "<uuid>",
  "error": {
    "code": "invalid_request",
    "message": "The request could not be completed."
  }
}
```

No traceback/source exception strings.

---

## 40. HTTP status contract

```text
200 success
400 validation
401 unauthenticated / expired
403 network/Site/capability forbidden
404 entity absent within authorized Site
429 login/query concurrency limit
503 source unavailable / query deadline / response too large
500 unexpected sanitized error
```

Unauthorized Site: `403` before source lookup.

Entity not found within authorized Site: `404`.

No cross-Site enumeration through error bodies.

---

## 41. Pagination and bounds

Large lists use:

```text
limit
cursor
```

Malformed cursor → `400`, never silent first-page fallback.

Prefer existing keyset/opaque source cursor.

No unbounded page loop.

---

## 42. Query concurrency

Non-blocking per-process Web query guard:

```text
WEB_ADMIN_MAX_CONCURRENT_QUERIES
```

No slot:

```text
429
Retry-After: 1
```

No queue.

Underlying Analytics/SQLite deadlines remain authoritative.

02A and Web are separate consumers; test simultaneous representative requests. If combined concurrency is unsafe, STOP and return architecture amendment for shared runtime query gate.

---

## 43. Response-size cap

Apply:

```text
WEB_ADMIN_MAX_RESPONSE_BYTES
```

Oversized JSON:

```text
503 response_too_large
```

No truncated JSON.

---

## 44. UI technology

Use:

```text
Flask
Jinja
plain CSS
vanilla JavaScript
Fetch API
```

Do not add React/Vue/Angular/build chain/CDN framework in v1.

---

## 45. UI namespace

```text
/admin/login
/admin/
/admin/sites/{site_id}/
/admin/sites/{site_id}/devices
/admin/sites/{site_id}/devices/{device_id}
/admin/sites/{site_id}/visits
/admin/sites/{site_id}/observations
```

This is internal owner/operator UI, not customer-facing v1.

---

## 46. Minimal UI shell

```text
Header
  CaptivPortal
  current Site
  operator username
  logout

Navigation
  Home
  Devices
  Visits
  Observations

Main
  page content
```

No Grafana iframe. No external assets.

---

## 47. Home

Not a full commercial dashboard.

Minimum:

```text
current Site
Admin Web health
Analytics availability
small Visit count summary
small unique-device summary
links to core pages
```

No commercial KPI wording.

---

## 48. Devices page

- paginated Site-safe devices;
- MAC search;
- link to Device Card;
- loading/empty/unavailable states;
- no bulk actions;
- no block/reconnect/rename/rate-limit controls.

---

## 49. Device Card page

- Site-safe identity/context;
- safe snapshot summary;
- recent Site visits;
- bounded observation summary;
- no write controls.

---

## 50. Visits page

- paginated Site visits;
- time/status filters;
- start/close/duration/SSID/AP/traffic;
- no mutations.

---

## 51. Observations page

Internal diagnostic page with:

```text
Client lookup by MAC
AP lookup by MAC
explicit time range
bounded rows
normalized safe fields
```

No raw JSON dump.

---

## 52. UI data path

Preferred:

```text
server-rendered shell
+ same-origin fetch
→ /admin/api/v1
```

Forbidden browser fetch to:

```text
/api/internal/analytics/v1
Grafana
Loki
Omada
```

---

## 53. XSS rules

- Jinja autoescape;
- dynamic API text via `textContent`;
- avoid `innerHTML` for API data;
- no executable user-supplied HTML;
- no arbitrary URL schemes built from source data.

---

## 54. UI state model

Standard states:

```text
loading
empty
insufficient_data
partial
unavailable
forbidden
session_expired
unexpected_error
```

Do not render NULL/unavailable/insufficient as numeric zero.

---

## 55. Read-only guarantee

Business/data API methods:

```text
GET only
```

Exceptions:

```text
POST /admin/login
POST /admin/logout
```

These mutate only Admin security/session state.

---

## 56. Explicitly forbidden Admin controls

Do not expose in Web Foundation:

```text
client block/unblock
reconnect
rename
rate limit
lock-to-AP
hotspot auth/unauth
AP config/write
```

Those require a later control/policy/audit TASK.

---

## 57. No new business persistence

Do not create:

```text
admin_users.sqlite3
permissions.sqlite3
tenant.sqlite3
web_cache.sqlite3
```

Session/login-limit state is process memory.

---

## 58. Analytics formulas are not duplicated

If a metric exists in Analytics services, reuse it.

Do not reimplement percentiles/rates/cohorts in Web code.

---

## 59. Privacy

Internal owner UI may show full technical MAC/device_id/visit_id/AP MAC and Site-scoped IP where needed.

Still forbidden:

```text
secrets
tokens
password hashes
Wi-Fi passwords
raw credential payload
cross-Site data
```

Future customer privacy policy is separate.

---

## 60. Telemetry

Examples:

```text
admin.auth_login_succeeded
admin.auth_login_failed
admin.auth_login_rate_limited
admin.auth_logout
admin.session_expired
admin.api_request_completed
admin.api_request_rejected
admin.api_request_failed
admin.query_unavailable
```

Safe fields:

```text
request_id
route_name
site_id where already authorized
status_code
duration_ms
principal_type
reason
source_ip
```

Never log password/hash/session token/CSRF/02A bearer/Authorization header.

---

## 61. Access-log privacy

Login password is POST body and must never appear in request URL.

Admin API query strings may contain entity identifiers. Current `SecretSafeRequestHandler` strips Analytics API query strings only.

Web execution review must extend safe request-line handling to `/admin/api/v1` query strings unless a stronger equivalent already exists.

Do not unnecessarily change normal captive-portal access logging.

---

## 62. Fail-open boundary

Any Admin Web failure must not break:

```text
/
CAPPORT
AuthSession/AuthWorker
Cleaner
Snapshot
Registry writer
Observation collectors
Visit Lifecycle
Analytics internal API
```

Admin runtime creation failure:

```text
log safely
leave /admin unavailable
do not abort portal startup
```

---

## 63. Shutdown

Admin Web has no worker.

On process shutdown:

```text
clear in-memory sessions
clear limiter state
```

Do not alter existing Auth/Visit shutdown ordering.

---

## 64. Future Multi-Site Compatibility

This TASK answers:

```text
Site-specific function?              YES
site_id preserved?                   YES
hardcoded Site/SSID?                 NO
Zefer Park presentation hardcode?    NO
new OmadaProvider?                   NO
Admin auth mixed with visitor auth?  NO
Grafana as backend?                  NO
Tenant introduced?                   NO
Tenant == Site?                      NO
Second Site requires route rewrite?  NO
```

---

## 65. Product / Observability Boundary

Web Foundation v1 is:

```text
internal owner/operator product-validation surface
```

Authoritative paths:

```text
Device views  → Registry/Visit/Observation read services
Visit views   → VisitLifecycleReadService
Summaries     → Analytics services
Engineering   → Grafana/Loki
```

No product dependency on Grafana.

---

## 66. Full Admin Console remains later

Out of scope now:

```text
customer accounts
invitations/password reset
MFA/OIDC
full RBAC
Tenant
subscriptions/entitlements/billing
branding editor
portal settings editor
reports scheduler
notifications
write/control APIs
commercial dashboard taxonomy
```

---

## 67. Execution decomposition

```text
TASK-WEB-FOUNDATION-01A
Admin Security + Site Context
        ↓ merge + acceptance

TASK-WEB-FOUNDATION-01B
Admin Query Service + Read-only Admin API
        ↓ merge + acceptance

TASK-WEB-FOUNDATION-01C
Read-only UI Shell + Core Pages
        ↓ merge + acceptance

TASK-WEB-FOUNDATION-PROD-01
Owner-controlled Production Activation
```

01A/01B/01C are separate implementation PRs.

Production activation is separate and is never implied by merge.

---

## 68. Execution TASK 01A — Admin Security + Site Context

Preferred branch:

```text
feature/web-admin-security-v1
```

Scope:

```text
AdminWebConfig
AdminPrincipal
AdminSessionStore
login/logout
CSRF
network allowlist
HTTPS requirement
login rate limiter
AdminAccessPolicy
Site resolver
security headers
minimal protected Admin shell
runtime composition
```

No business-data pages/API beyond minimal session/sites/health needed to prove boundary.

### 01A allowed files

New:

```text
app/admin_web/**
tests/admin_web/**
```

Existing minimal:

```text
app/config.py
app/settings.py
run.py
.env.example
app/web/web.py only if factory wiring requires it
```

### 01A forbidden

No business/schema/formula changes in Auth/CAPPORT/Omada/Observation/Visit/Registry/Analytics. No Grafana/Nginx/systemd/requirements/KB changes.

### 01A acceptance

- Admin auth fully separate;
- externalized password hash;
- network + HTTPS enforced;
- CSRF login/logout;
- session fixation prevented;
- idle + absolute expiry;
- immediate logout revocation;
- required cookie flags;
- brute-force guard;
- Site scope server-side;
- permissions-ready policy;
- disabled default;
- invalid Admin config leaves portal operational;
- full regressions accepted;
- production unchanged.

---

## 69. 01A required tests

At minimum:

### Config
- disabled accepts empty credential/Sites;
- enabled missing username/hash rejected;
- invalid hash safe;
- invalid/duplicate CIDR;
- invalid/duplicate Site IDs;
- default Site not allowed;
- invalid bounds;
- repr/error contains no credential/hash.

### Network/HTTPS
- allowed source;
- disallowed source 403 before password verification;
- trusted ProxyFix behavior;
- insecure rejected when required;
- forwarded HTTPS accepted.

### Login/session
- GET login;
- valid login;
- wrong user/pass same response;
- no password echo;
- CSRF missing/invalid;
- new token after auth;
- cookie flags;
- open redirect rejected;
- idle expiry;
- absolute expiry;
- logout revokes;
- new runtime/store invalidates old session.

### Rate limit
- rolling window;
- threshold/lock;
- lock expiry;
- bounded cleanup.

### Boundary
- no AuthSession/AuthWorker;
- no Omada;
- no Analytics bearer;
- invalid Admin config keeps `/`/CAPPORT functional.

---

## 70. Execution TASK 01B — Admin Query Service + API

Preferred branch:

```text
feature/web-admin-read-api-v1
```

Depends on accepted/merged 01A.

Scope:

```text
AdminQueryService
safe DTO
serialization
pagination/cursor
response-size cap
query concurrency guard
session-authenticated Admin API
Site-safe Devices
Device Card
Visits/detail
Client/AP Observation lookup
Visit/device Analytics summaries
health/session/sites
```

### Narrow source extensions allowed

Only when required for bounded Site-safe read:

```text
app/visitor_registry/registry_read_service.py
app/visitor_registry/registry_repository.py
app/visit_lifecycle/read_service.py
app/visit_lifecycle/repository.py
app/observations/read_service.py
app/observations/repository.py
```

Read-only only; no schema/mutation/worker changes.

### Required pre-code PLAN

Coder must return:

```text
endpoint
capability
required source(s)
Site filter
input bounds
ordering
cursor shape
output DTO
error mapping
expected query count
```

before broad implementation.

---

## 71. 01B ordering and isolation

Recommended ordering:

```text
Devices:      site_last_seen_at DESC, device_id DESC
Visits:       started_at DESC, visit_id DESC
Client obs:   observed_at DESC, row_id DESC
AP obs:       observed_at DESC, row_id DESC
```

Exact index/source compatibility must be checked on current main.

Entity rules:

```text
Device detail → Site membership evidence required
Visit detail  → visit.site_id must equal URL Site
```

No cross-Site fallback.

---

## 72. 01B Analytics summary

Minimum:

```text
GET /admin/api/v1/sites/{site_id}/summary/visits
GET /admin/api/v1/sites/{site_id}/summary/devices
```

Require `from_utc` and `to_utc`.

Use existing VisitAnalyticsService methods exactly once per endpoint where possible.

No metric formula duplication.

Never label unique devices as people.

---

## 73. 01B performance acceptance

Representative:

```text
100-row Devices page
100-row Visits page
100-row Observation page
small Analytics summary
```

Evidence:

```text
no N+1
bounded SQL/source calls
response <= configured cap
Admin overhead excluding source query <100 ms p95
query deadlines preserved
no queued heavy query
```

Also test one concurrent 02A request.

---

## 74. 01B required tests

- session/network/HTTPS required;
- Site capability required;
- unauthorized Site rejected before source query;
- unknown/duplicate query params rejected;
- invalid limit/cursor/time;
- stable paging;
- device cross-Site leak;
- Registry global last-context leak;
- Visit Site mismatch;
- Observation exact Site;
- raw max window;
- safe field serialization;
- raw JSON forbidden fields absent;
- Analytics summary calls existing service;
- NULL stays JSON null;
- unavailable 503;
- concurrency 429 and slot release;
- response too large;
- no CORS;
- no-cache/security headers;
- no write SQL/source changes;
- no Omada;
- 02A API regressions.

---

## 75. Execution TASK 01C — Read-only UI Shell + Core Pages

Preferred branch:

```text
feature/web-admin-ui-v1
```

Depends on accepted/merged 01B.

Scope:

```text
Jinja Admin shell
CSS
vanilla JS fetch client
Home
Devices
Device Card
Visits
Observations
Site context/navigation
session-expiry UX
loading/empty/error states
manual refresh
```

No write controls.

Expected changed area:

```text
app/admin_web/templates/**
app/admin_web/static/**
app/admin_web/pages.py
tests/admin_web/**
```

No source-layer changes expected.

---

## 76. 01C frontend rules

- no frontend framework;
- no npm/runtime dependency;
- no CDN;
- CSP-compatible external static assets;
- Jinja autoescape;
- API data via safe DOM text operations;
- no bearer/session secret in storage/assets;
- no infinite polling/retry.

---

## 77. 01C page acceptance

### Home

```text
Site
health
small visit/device summary
navigation
```

### Devices

```text
paged Site-safe devices
MAC
device type
Site first/last seen
Site visit/snapshot counts
last Site SSID/AP
```

### Device Card

```text
identity
Site-local context
recent visits
safe snapshot summary
bounded observation summary
```

### Visits

```text
paged Site visits
status
times
duration
SSID/AP
traffic
```

### Observations

```text
Client lookup
AP lookup
time filter
safe normalized rows
```

---

## 78. 01C browser tests

- unauthenticated pages redirect;
- allowed Site works;
- forbidden Site blocked;
- navigation preserves Site;
- HTML escaping;
- CSP/no-store;
- login/logout UI;
- session-expiry handling;
- 401/403/429/503 UI states;
- empty state;
- malformed API response;
- no unsafe HTML insertion for API data;
- no bearer token in static assets;
- no Omada/Grafana/Loki URL in UI code;
- no write buttons/actions.

If Node is unavailable in Coder environment, required frontend/static tests must still run in Tech Lead Linux/Node gate according to current project pattern.

---

## 79. Common regression invariants

Each PR handoff must state:

```text
Visitor Auth semantics changed: NO
CAPPORT semantics changed: NO
OmadaProvider/token lifecycle changed: NO
Observation schema changed: NO
Observation collection changed: NO
Visit schema/finalization changed: NO
Registry schema/writer changed: NO
Analytics formulas changed: NO
Analytics 02A security weakened: NO
Grafana/Loki/Alloy changed: NO
Production config changed: NO
```

Any YES is a stop unless master is explicitly amended.

---

## 80. Baseline/full gate per PR

Before each PR:

```bash
git fetch origin
git rev-parse origin/main
git status --short
python -m pytest -q -rs
PYTHONPYCACHEPREFIX=/tmp/captiveportal-pyc \
  python -m compileall -q app
git diff --check
```

Record exact SHA, Python version, passed/skipped/failed/deselected, compileall, diff-check and tree state.

Historical deselections are not automatically inherited; classify current baseline.

---

## 81. Targeted test order

1. new Admin module tests;
2. security/web tests;
3. Analytics 02A tests;
4. source regressions if touched;
5. existing web/auth/CAPPORT tests;
6. full suite;
7. compileall/diff-check;
8. exact-patch Linux gate before commit permission under current workflow.

---

## 82. Common security tests

- password/hash/token absent from Git diff;
- login body values absent from logs;
- session/CSRF absent from logs;
- Analytics bearer absent from HTML/JS;
- CORS absent;
- security headers;
- Site/network isolation;
- invalid Site rejected before query;
- source errors sanitized;
- raw forbidden fields absent;
- no open redirect;
- XSS through device/SSID/AP names prevented.

---

## 83. Common fail-open tests

Simulate:

```text
Admin config invalid
Admin runtime creation exception
Registry unavailable
Visit unavailable
Observation unavailable
Analytics unavailable
Admin serialization exception
```

Prove current portal/CAPPORT/authorization/webhook behavior remains available according to baseline.

---

## 84. No new external dependency

Preferred stack is existing:

```text
Flask
Werkzeug
stdlib
```

If a new dependency appears necessary: STOP and return rationale/security impact/alternatives.

---

## 85. Knowledge Base boundary

Runtime PRs do not update project Knowledge Base.

After production acceptance, issue separate Knowledge Base Lead TASK for inventory/module-index/architecture/testing/deployment/security/Admin-Web docs and roadmap status.

---

## 86. Repository actions for this DRAFT

```text
NO branch
NO code
NO commit
NO push
NO PR
NO deploy
```

Approval of master does not implicitly authorize any execution stage.

Each execution stage requires explicit owner approval.

---

## 87. Production activation is separate

After accepted/merged:

```text
01A
01B
01C
```

architect prepares:

```text
TASK-WEB-FOUNDATION-PROD-01
```

No implementation merge implies activation.

---

## 88. Production preflight

Activation task must verify:

```text
exact expected main SHA
clean production tree
backup /etc/default/captive-portal
existing portal health
02A health
Observation/Visit/Registry health
HTTPS reverse-proxy path for /admin
management client network
rollback point
```

If Nginx does not already proxy `/admin` safely over HTTPS: STOP and create separate reverse-proxy infrastructure change.

Do not hide Nginx changes inside Web runtime PR.

---

## 89. Production credential preparation

Owner generates outside Git:

```text
Admin username
Admin password
Werkzeug password hash
```

Only hash enters environment.

Conceptual production settings:

```text
WEB_ADMIN_ENABLED=true
WEB_ADMIN_USERNAME=<operator>
WEB_ADMIN_PASSWORD_HASH=<secret hash; never echo>
WEB_ADMIN_ALLOWED_NETWORKS=<management LAN/VPN>
WEB_ADMIN_ALLOWED_SITE_IDS=<allowed Site IDs>
WEB_ADMIN_DEFAULT_SITE_ID=<allowed Site>
WEB_ADMIN_REQUIRE_HTTPS=true
```

---

## 90. Production activation order

1. exact SHA/preflight;
2. env backup;
3. prepare credential hash + Site/network scope;
4. validate config without secret output;
5. confirm HTTPS/Nginx;
6. controlled service restart;
7. PID/active/substate;
8. existing `/` + CAPPORT smoke;
9. 02A internal Analytics health;
10. `/admin/login` from allowed network over HTTPS;
11. disallowed source rejection;
12. owner login;
13. cookie attributes;
14. default Site context;
15. Home/Devices/Visits/Observations;
16. one small Admin API query per source class;
17. source schemas/row counts unchanged;
18. secret-safe log inspection;
19. record PASS/rollback readiness.

---

## 91. Production smoke matrix

```text
Visitor portal                PASS
CAPPORT                       PASS
Analytics 02A health          PASS
Admin login allowed network   PASS
Admin wrong password          controlled
Admin disallowed network      403
Admin HTTPS-only              PASS
Admin cookie flags            PASS
Admin Site allowlist          PASS
Devices API/page              PASS
Device Card                   PASS
Visits API/page               PASS
Client Observation lookup     PASS
AP Observation lookup         PASS
Logout revokes session        PASS
No source row/schema changes  PASS
No secret in logs             PASS
```

---

## 92. Rollback

1. restore environment backup or set `WEB_ADMIN_ENABLED=false`;
2. restart service;
3. confirm portal/CAPPORT;
4. confirm 02A;
5. if needed, revert code to previous accepted SHA;
6. source DB restore should not be required because Web Foundation is read-only.

Admin sessions are intentionally lost on restart.

---

## 93. Master acceptance criteria

### Security

- independent Admin authentication;
- no browser 02A bearer;
- HTTPS/network boundary;
- external password hash;
- opaque server-side sessions;
- idle/absolute expiry;
- logout revocation;
- CSRF;
- brute-force guard;
- security headers/no CORS/open-redirect protection;
- secret-safe logs.

### Site

- explicit Site context;
- backend Site enforcement;
- no hardcoded production Site;
- no Registry cross-Site context leak;
- second Site without route rewrite;
- no tenant==Site.

### Application/API

- AdminQueryService;
- no SQLite access from routes;
- versioned read-only Admin API;
- safe DTO/serialization;
- pagination, response cap, concurrency;
- source failures classified;
- Analytics reused, not duplicated.

### UI

- login + shell/navigation;
- Home;
- Devices;
- Device Card;
- Visits;
- Observations;
- loading/empty/error states;
- no write controls;
- no external frontend dependency;
- CSP-compatible.

### Architecture

- no Grafana backend;
- no Omada query/control;
- no source schema/write change;
- no derived Web DB;
- portal fail-open;
- 02A security preserved;
- full regressions accepted.

### Delivery

- 01A/01B/01C separately reviewed/merged;
- production activation separate;
- production smoke PASS;
- rollback proven.

---

## 94. Explicit out-of-scope list

Do NOT implement:

```text
commercial customer Admin Console
customer account database
email/password reset
MFA
OIDC/OAuth admin identity
full RBAC
Tenant / Tenant-Site persistence
subscriptions / billing / entitlements
Portal Profile editor / branding persistence
portal operational settings write
client or AP control/write
reports scheduler
notifications
CSV full export
Grafana iframe
Loki query frontend
Omada live management console
customer-visible raw engineering telemetry
multi-worker Admin sessions
HA session store
```

---

## 95. Stop conditions

Stop affected implementation if:

- current main materially changed from reviewed contracts;
- current Flask app already uses a conflicting session/cookie mechanism;
- ProxyFix trust model differs from one trusted hop;
- Site-safe Device membership cannot be implemented read-only;
- source query would require schema mutation;
- browser would need Analytics bearer;
- query would need Omada live call;
- cross-Site isolation cannot be guaranteed;
- N+1 cannot be eliminated inside approved scope;
- combined 02A/Admin concurrency is unsafe;
- read query exceeds accepted bounds;
- new external dependency is required;
- production HTTPS path unavailable;
- full suite has a new unclassified failure.

---

## 96. Architecture review checklist

Tech Lead should review specifically:

1. single-operator scope;
2. process-local opaque session choice;
3. CSRF/cookie contract;
4. HTTPS/network order;
5. login limiter;
6. explicit Site URL model;
7. permissions-ready policy;
8. Device Site-membership semantics;
9. AdminQueryService boundaries;
10. Observation field allowlist;
11. concurrency relation with 02A;
12. endpoint set/error mapping;
13. UI scope vs future Admin Console;
14. no Grafana/Omada dependency;
15. production activation/rollback.

---

## 97. Review status

```text
TASK-WEB-FOUNDATION-01
DRAFT FOR REVIEW
IMPLEMENTATION NOT AUTHORIZED
```

Do not issue implementation/branch/commit/PR/deploy commands yet.

---

## 98. Expected post-review flow

```text
DRAFT
→ architecture corrections
→ FINAL master TASK
→ explicit approval 01A only
→ 01A implementation/review/merge
→ explicit approval 01B
→ 01B implementation/review/merge
→ explicit approval 01C
→ 01C implementation/review/merge
→ separate production activation TASK
```

Master approval never implicitly authorizes later PRs.

---

## 99. Execution handoff format

Each execution handoff returns:

```text
BASELINE
IMPLEMENTED
NOT IMPLEMENTED
FILES CHANGED
SOURCE CONTRACTS USED
SECURITY CONTRACT
SITE CONTRACT
QUERY/API CONTRACT
UI CONTRACT where relevant
PERFORMANCE
PRIVACY / SECRET-SAFETY
TARGETED TEST RESULTS
RELATED REGRESSIONS
FULL GATE
COMPILEALL
DIFF-CHECK
KNOWN LIMITATIONS
STOP-CONDITION FINDINGS
REPOSITORY ACTIONS
NEXT OWNER ACTION
```

---

## 100. Final architectural statement

Web Foundation v1 is:

```text
a secure,
Site-aware,
read-only,
owner/operator web/application foundation
over existing CaptivPortal authoritative data and Analytics.
```

It is not:

```text
a Grafana wrapper
a customer account system
a tenant system
a write/control console
a replacement for Analytics 02A
a second visitor authentication mechanism
```

Its role is to make the next stage possible:

```text
Web Foundation
→ CaptivPortal Admin Console
→ future Multi-Site / Tenant / RBAC / Entitlements
```

without forcing a rewrite of the security, Site context and application/query boundaries created here.
