# Инвентаризация CaptivPortal

Status: current runtime snapshot
Updated: 2026-08-26
Branch: `main`
Runtime commit: `dfc62b43712301b05baf9f6e5dd843e13eaa9fc7`
Commit source: merge PR #62, 2026-08-24

Этот документ описывает repository implementation указанного commit. Production state не выводится из Git. Historical acceptance не является live health.

## 1. Composition roots

- `run.py` — единственный direct process entrypoint и верхний lifecycle/composition root.
- `app/web/web.py:create_app()` — Flask composition factory.
- configuration pipeline: process environment → `app/config.py` → `app/settings.py:get_settings()`.
- `run.py` создаёт один shared `OmadaProvider` и передаёт его Portal/Auth, Snapshot, Observation, Current State и Pending Cleaner.
- `create_app()` создаёт Flask-owned Auth/CAPPORT/Webhook/Counters/Public Traffic components.
- `AuthSessionManager` и `ThreadPoolExecutor(max_workers=4)` process-local.

## 2. Exact startup order

1. `get_settings()`.
2. shared `create_controller()` / `OmadaProvider`.
3. create Authorized Snapshot Collector.
4. create Visit Lifecycle runtime/storage.
5. `create_app()` — Auth, Portal, CAPPORT, webhook, counters, Public Traffic service composition.
6. create Observation Foundation.
7. create Current State runtime.
8. create Pending Session Cleaner.
9. start Cleaner.
10. start Observation.
11. start Current State.
12. start Snapshot Collector.
13. create/start Visitor Registry.
14. create `VisitorRegistryReadService` when Registry is available.
15. start Visit webhook reader + Registry reconciliation.
16. compose Analytics runtime/API.
17. compose Admin Web.
18. start Public Traffic worker.
19. start Flask server.

Failure of independent components is caught so that guest authorization can continue where core auth dependencies remain healthy.

## 3. Exact shutdown order

1. clear Admin Web in-memory state.
2. stop Pending Cleaner.
3. stop Observation.
4. stop Current State.
5. stop Public Traffic worker.
6. stop Visit scheduling (webhook reader/reconciler).
7. drain/stop Auth executor.
8. stop Visit accepting and wait/close.
9. stop accepting Snapshot jobs and drain bounded executor.
10. stop Visitor Registry with final scan.

Analytics has no worker/write lifecycle to stop.

## 4. Runtime subsystem inventory

| Subsystem | Current code | Source | Persistence | Omada access |
|---|---|---|---|---|
| Portal/Auth | `app/web`, `app/auth` | portal request | process memory + telemetry | yes |
| CAPPORT | `app/capport` | source IP + Omada lookup | bounded process caches | yes, shared provider |
| Auth telemetry | `app/auth_telemetry` | auth flow | JSONL | no |
| Portal counter | `app/portal_counter` | accepted portal opens | SQLite | no |
| Public traffic counter | `app/public_traffic` | normalized webhook journal | SQLite | no |
| Authorized Snapshot | `app/visitor_registry/snapshot_*` | confirmed AUTHORIZED | JSONL | yes, shared provider |
| Visitor Registry | `app/visitor_registry/registry_*` | snapshot journal | SQLite | **no** |
| Webhook pipeline | `app/integrations/omada` | HTTP webhook | raw + normalized JSONL | inbound only |
| Pending Cleaner | `app/pending_sessions` | Omada client inventory | JSONL audit + process guard | yes, shared provider |
| Visit Lifecycle | `app/visit_lifecycle` | Auth start + normalized offline events | SQLite schema v2 | no |
| Observation | `app/observations` | Omada client/AP reads | SQLite schema v1 | yes, shared provider |
| Current State | `app/current_state` | Omada client/AP reads | SQLite schema v1 | yes, shared provider |
| Analytics | `app/analytics` | persisted read services | none | **no** |
| Analytics internal API | `app/analytics/api.py` | Analytics services | none | no |
| Admin Web | `app/admin_web` | read services/gateways | process session state only | **no** |
| Home Live | Admin Web | `CurrentStateReadService` | none | no |
| Current Traffic | `app/analytics/current_traffic.py` | persisted AP Observation facts | none | no |
| Home Traffic | Admin Web | `CurrentTrafficReadService` | none | no |

## 5. Observation vs Current State

| Contract | Observation | Current State |
|---|---|---|
| Purpose | historical measurements | what is active now |
| Wireless client population | active + authorized (`authStatus==2`) + SSID scope | all active wireless in scope |
| `authStatus==1` | excluded | `pending` |
| History | long retention | bounded short history |
| AP facts | dynamic/config historical facts | latest operational inventory/state |
| Primary consumer | Analytics | Admin Home/live reads |

Current State client classification:
- `2 → authorized`
- `1 → pending`
- other integer → `other`
- missing/invalid → `unknown`

## 6. Persistence ownership

| Storage | Writer | Readers | Purpose |
|---|---|---|---|
| `auth_telemetry.log` | Auth telemetry | observability | operational auth telemetry |
| `visitor_snapshots.log` | Snapshot Collector | Visitor Registry / observability | authorized snapshot journal |
| `omada_webhook.log` | Webhook Receiver | processor/ops | redacted raw webhook |
| `omada_webhook_normalized.log` | Webhook Processor | Visit Lifecycle / Public Traffic | canonical normalized events |
| `pending_session_cleaner.log` | Pending Cleaner | ops/audit | action audit |
| `portal_counter.db` | Portal Counter | portal API | public authorization counts |
| `public_traffic.sqlite3` | Public Traffic | portal API | completed-session traffic |
| `visitor_registry.sqlite3` | Visitor Registry | Registry read service / Analytics / Admin | device identity/history |
| `visits.sqlite3` | Visit Lifecycle | Visit read service / Analytics / Admin | visits, auths, source events |
| `observations.sqlite3` | Observation Foundation | Observation read service / Analytics / Admin | historical client/AP facts |
| `current_state.sqlite3` | Current State | CurrentStateReadService / Admin | current snapshots + short history |

Writers own schema/migrations. Read-only consumers do not mutate source storage.

## 7. Visit Lifecycle current contract

Schema version: **2**.

- `AuthSession != physical Visit`.
- one Visit may contain multiple authorization events.
- confirmed AUTHORIZED run submits `VisitStartRequest`.
- normalized `omada.client_offline` evidence closes/matches visits.
- reader checkpoint is durable.
- reader supports bounded lines/bytes/time and rotated source identities.
- Registry reconciliation links device/snapshot identity.
- unmatched offline evidence can remain pending for later match.
- Visit runtime is `active` only when webhook reader + reconciler are running and reader health is good; otherwise `degraded`.
- SQLite writes are coordinated by `PriorityWriteCoordinator`: foreground Visit Start has priority over FIFO background reader/reconciliation writes.

## 8. Observation current contract

Schema version: **1**.

- historical measurement layer, not current inventory.
- client collector includes only wireless, active, `authStatus==2` clients within configured SSID scope.
- AP worker persists inventory/dynamic/radio/config facts and cycle metadata.
- cycles record complete/partial/failure, counts and quality warnings.
- dynamic and config facts have different retention.
- cleanup and integrity run as bounded background workers.
- runtime state can become `degraded`; construction/start failures are fail-open relative to guest auth.

## 9. Current State current contract

Schema version: **1**.

- active wireless clients in configured Site/SSID scope, including pending authorization.
- client and AP collection cycles are separate.
- exact current reads select complete-success snapshots and retain latest attempt/partial metadata.
- freshness is calculated from persisted capture timestamps:
  `fresh → stale → unavailable`.
- client scope has a canonical source-scope hash; cursors are bound to Site/cycle/scope and reject stale scope.
- short client history default retention: 48 hours.
- no Admin request polls Omada through this service.

## 10. Analytics current contract

Analytics is demand-only:
- no background thread;
- no source write path;
- no direct Omada access;
- reads Observation, Visit and Registry via `AnalyticsSourceGateway`;
- validates expected source schema versions;
- read connections require SQLite `PRAGMA query_only`.

Services:
- data quality (`AnalyticsReadService`);
- wireless analytics;
- visit analytics;
- optional `CurrentTrafficReadService`.

Protected internal API prefix:
`/api/internal/analytics/v1`

It uses Bearer authentication, source-network allowlist, Site allowlist, bounded concurrency and response-size limits. Browser Admin code must not use this bearer API directly.

## 11. Current Traffic current contract

Current Traffic is a live-oriented interpretation of **persisted AP Observation facts**.

Important:
- primary source family: `wired`;
- fallback: `lan`;
- one source family is selected consistently for a Site snapshot;
- no per-AP mixing of wired/LAN source families;
- only complete-success Observation cycles satisfying integrity checks are accepted;
- invalid/inconsistent source integrity becomes unavailable;
- freshness and AP skew are explicit;
- Current Traffic is **not Internet/WAN-only traffic**, **not guest-only traffic**, and **not an SSID-specific total**.

## 12. Admin Web current contract

Admin security is separate from guest Portal authentication.

Current pages:
- Home
- Devices
- Device Detail
- Visits
- Observations

Home has optional current sections:
- Home Live via `CurrentStateReadService`;
- Home Traffic via `CurrentTrafficReadService`.

Browser flow:
`browser → /admin + /admin/api/v1 → AdminQueryService/read gateways → read services`.

Prohibited:
- browser → SQLite
- browser → Omada
- browser → `/api/internal/analytics/v1`
- browser → Loki/Grafana

Business/data Admin API is GET-only. POST is used for Admin login/logout session security.

## 13. Admin security facts

Repository default includes owner-approved VPN source network `10.8.0.0/24` in `WEB_ADMIN_ALLOWED_NETWORKS`.

Current boundary includes:
- HTTPS requirement;
- source network allowlist;
- Site allowlist/default Site;
- password hash (no plaintext password in Git);
- pre-auth CSRF;
- login rate limiting;
- bounded in-memory sessions;
- idle + absolute session timeout;
- Secure/HttpOnly/SameSite cookies;
- logout CSRF;
- CSP, `X-Frame-Options: DENY`, nosniff, no-referrer, no-store.

`SecretSafeRequestHandler` strips query strings from access-log request lines for the whole `/admin` namespace and internal Analytics namespace.

Flask `ProxyFix` trusts exactly one local reverse-proxy hop in the current topology.

## 14. Shared OmadaProvider

One provider per process and one shared token cache.

Token lifecycle includes:
- `Condition(RLock)`;
- one concurrent token refresh;
- early refresh;
- compare-and-invalidate so a late failure cannot erase a newer token.

Core Omada configuration is fail-closed before network requests when required credentials are missing/invalid.

HTTP status and Omada JSON `errorCode` are separate success conditions.

No second provider/token manager/OAuth cache without approved change intent.

## 15. Configuration groups

Exact variables/defaults are in `configuration.md`, `app/config.py`, `app/settings.py`, and `.env.example`.

Groups:
Core/Omada, Portal/CAPPORT, telemetry, counters, Snapshot, Registry, Webhook, Cleaner, Visit, Observation, Current State, Analytics/API, Admin Web/Home Live/Home Traffic.

Repository feature defaults are not production proof.

## 16. Single-process and thread model

Process-local state includes:
- Auth sessions/locks/retry ownership;
- 4-thread Auth executor;
- CAPPORT caches;
- Cleaner action guard;
- Admin sessions/login limiter/pre-auth CSRF state;
- worker lifecycle state.

Background execution categories:
- Snapshot executor;
- Registry worker;
- Visit webhook reader;
- Visit reconciler;
- Observation client/AP/cleanup/integrity workers;
- Current State client/AP/cleanup workers;
- Pending Cleaner;
- Public Traffic worker;
- Flask request threads.

Multi-process WSGI/horizontal HA is unsupported without an ADR for shared state and worker leadership.

## 17. Fail-open / fail-closed

Fail-closed:
- required core Omada provider configuration;
- actual authorization result;
- Admin authentication/access/network/Site policy.

Fail-open relative to guest authorization:
- telemetry/counters;
- Snapshot/Registry;
- webhook normalization;
- Visit persistence/reconciliation;
- Observation;
- Current State;
- Analytics;
- Admin Web;
- Pending Cleaner.

Fail-open means disabled/unavailable/degraded and safe omission — never fabricated success/data.

## 18. Tests and CI

`tests/` is the repository test root. Current groups cover Auth, CAPPORT, Omada/webhook, Visitor Registry, Pending Cleaner, Visit Lifecycle, Observation, Current State, Analytics and Admin Web.

Current workflow separates test responsibilities:

```text
Coder → TASK/module-scoped targeted testing
Central Lab → full regression / official baseline / final Test Evidence
Tech Lead → architecture/DIFF/targeted-evidence review
```

Owner-provided current Windows Local Gate tool:

```text
C:\CaptivPortal-Lab\lab-test-v4-fixed.cmd
```

Confirmed 2026-08-26 Windows evidence:

```text
strict suite: 1985 passed / 30 skipped / 0 strict regressions
compatibility: 2 WARN + 3 PASS (five exact tracked cases)
compileall: PASS
git diff --check: PASS
overall Windows Local Gate: PASS
```

The compatibility baseline is narrow; a new failure outside the recorded cases is a strict regression until reviewed.

These numbers are operational test evidence, not a repository-derived evergreen count. After runtime/test changes a new exact-artifact Central Lab baseline is required before presenting them as current.

`.github/workflows` is absent at the documented runtime baseline. GitHub release CI remains open process debt; the official full-regression source is currently the manual Central Lab.

Windows Local Gate does not replace a separately required Linux/production-compatible pre-production gate.

## 19. Current vs historical vs change-intent

Current:
- Visit Lifecycle
- Observation
- Analytics
- Admin Web
- Current State
- Home Live
- Current Traffic/Home Traffic

Not current at this baseline:
- Home Activity implementation.

Historical production numbers (device counts, test snapshots, individual acceptance counters) must remain labelled historical and must not be presented as current counters.

## 20. Repository-only unknowns

Repository alone does not prove:
- actual enabled production flags;
- exact EnvironmentFile/drop-ins;
- current production DB sizes/rows/health;
- current controller/AP reachability;
- current Loki/Grafana health;
- current full-suite result for this SHA unless a separate exact-artifact report exists.

## 21. Known limitations/debt

- single-process topology;
- `VERIFY_SSL=false` repository default;
- no GitHub Actions release CI;
- production enabled-state must be host-verified;
- Omada private UI APIs are not approved product contracts;
- custom client rate-limit public full-clear remains unresolved on tested Omada 5.14.31.
