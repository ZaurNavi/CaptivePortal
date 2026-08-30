# Инвентаризация CaptivPortal

Status: current runtime snapshot
Updated: 2026-08-30
Branch: `main`
Runtime commit: `b92efbfabb38f912550526bc5a3d1f2f1a8ae4d6`
Runtime tree: `1d8b94590848f9505e45e653384dd8a7c18d4339`
Commit source: merge PR #89 / TASK-TRAFFIC-03, 2026-08-30

Этот документ описывает repository implementation указанного commit. Production evidence ниже относится только к явно указанной контрольной точке; repository defaults и production activation остаются разными фактами.

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
| Home Activity | `app/analytics/home_activity.py`, Admin Web | Visit Lifecycle persisted facts + Current State guest scope | none | no |
| Traffic Section | `app/admin_web/` | Admin product shell + shared Traffic coordinator | none | no |
| Traffic Current Network Throughput | Admin Web + `app/analytics/current_traffic.py` | persisted AP Observation facts via CurrentTrafficReadService | none | no |
| Historical Traffic Read | `app/analytics/historical_traffic.py`, source gateway | persisted AP Observation history | none | no |
| Traffic Network History | Admin Web + Historical Traffic | shared 24h/7d historical read | none | no |
| Traffic Period Statistics | Admin Web + Historical Traffic | shared History range/read execution | none | no |

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
- startup `PRAGMA quick_check` self-timeout is retryable storage contention only when the repository itself interrupted that quick_check; unrelated `interrupted`, schema mismatch and `quick_check != ok` remain schema/integrity failures.
- SQLite contention detection is Python-3.10 compatible: primary BUSY/LOCKED codes are `5`/`6`; integer `sqlite_errorcode` is normalized with `code & 0xFF`, with message fallback for `database is locked` / `database is busy`.

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
- optional `CurrentTrafficReadService`;
- `HomeActivityReadService`;
- `HistoricalTrafficReadService`.

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
- Traffic

Traffic currently contains:
- Traffic Foundation/shared coordinator;
- Current Network Throughput;
- Historical Network Throughput;
- Period Statistics.

Current endpoint:

```text
GET /admin/api/v1/sites/<site_id>/traffic/current
```

Historical endpoint family:

```text
GET /admin/api/v1/sites/<site_id>/traffic/history?range=24h|7d
```

Statistics shares the History request/range; no independent heavy Statistics
request/coordinator exists.

Browser flow:
`browser → /admin + /admin/api/v1 → AdminQueryService/read gateways → read services`.

Prohibited:
- browser → SQLite
- browser → Omada
- Admin Traffic request → Omada
- browser → `/api/internal/analytics/v1`
- browser → Loki/Grafana
- second Traffic current/historical calculation owner/coordinator

Current layout is production-current functional layout, not final approved visual
composition.

Business/data Admin API remains read-only.

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
Core/Omada, Portal/CAPPORT, telemetry, counters, Snapshot, Registry, Webhook, Cleaner, Visit, Observation, Current State, Analytics/API, Admin Web/Home Live/Home Traffic/Home Activity, Traffic Section.

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

`tests/` is the repository test root.

Testing ownership:

```text
Coder → focused/minimal TASK/module tests
Owner + Tech Lead / Central Lab → cross-module/broader/full/official acceptance
```

Acceptance before publication:

```text
all TASK/FINAL mandatory gates PASS
→ accepted candidate
→ publication
```

V6/full PASS alone is not sufficient if PERF/Linux/security/etc. remains mandatory.

Current Traffic-stage final evidence:

```text
artifact: b92efbfabb38f912550526bc5a3d1f2f1a8ae4d6
tree: 1d8b94590848f9505e45e653384dd8a7c18d4339
TASK-TRAFFIC-03: production acceptance PASS / CLOSED
V6: PASS
strict regressions: 0
production-size PERF: PASS
40/40 measured requests: 200
deadlines: 0
integrity failures: 0
```

Initial candidate `d96ddbc6f8685be175ee9a48da9b8e15621f2161` failed mandatory PERF and is superseded.

After each accepted TASK Tech Lead reviews changed tests, targeted regression set,
cross-surface invariants and whether the runner contract changed.

`.github/workflows` remains absent; official full regression remains manual
Central Lab until separately changed.

## 19. Current vs historical vs change-intent

Current repository implementation includes:
- Visit Lifecycle
- Observation
- Analytics
- Admin Web
- Current State
- Home Live
- Current Traffic / Home Traffic
- Home Activity
- Traffic Foundation
- Traffic Current Network Throughput
- Historical Traffic Read Foundation
- Traffic Network History
- Traffic Period Statistics

Owner-confirmed current production checkpoint:

```text
production HEAD: b92efbfabb38f912550526bc5a3d1f2f1a8ae4d6
production tree: 1d8b94590848f9505e45e653384dd8a7c18d4339

WEB_ADMIN_TRAFFIC_ENABLED=true
WEB_ADMIN_TRAFFIC_HISTORY_ENABLED=true
WEB_ADMIN_TRAFFIC_STATISTICS_ENABLED=true

TASK-TRAFFIC-03:
PRODUCTION ACCEPTANCE PASS / CLOSED
```

Historical engineering evidence:
- initial TRAFFIC-03 `d96ddbc6f8685be175ee9a48da9b8e15621f2161` / `5e6a28950c8079d805450dc2a7ecf652a8285820` = PERF FAIL / superseded;
- final candidate `79875aca61297c8de4c30b7119b15118079f26d0` / `1d8b94590848f9505e45e653384dd8a7c18d4339` = all mandatory gates PASS.

Next change-intent:

```text
TRAFFIC-04 — Peak Load Period
NEXT / NOT IMPLEMENTED
```

Historical TASK/PR evidence must remain historical; it does not redefine current
implementation or current governance.

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
