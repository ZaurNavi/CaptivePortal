# Архитектура CaptivPortal

Status: current
Updated: 2026-08-31
Runtime baseline: `main@a9cd8a9b9b9efc46bc82d315385ebbd1a3bf63b0`

## 1. Mental model

CaptivPortal — один Python process, в котором guest authorization остаётся критическим ядром, а operational/data/product слои подключаются вокруг него с ограниченной связанностью.

```text
Authorization / Identity
        ↓
Snapshots / Webhook evidence
        ↓
Registry + Visit Lifecycle
        ↓
Observation + Current State
        ↓
Analytics
        ↓
Admin Web
```

## 2. Composition boundaries

`run.py`:
- process lifecycle;
- shared provider;
- storage/worker composition outside Flask;
- startup/shutdown order.

`app/web/web.py:create_app()`:
- Flask app;
- process-local Auth manager/executor;
- Portal/CAPPORT;
- webhook receiver/normalizer;
- portal/public traffic services and routes.

`run.py` remains the only direct executable entrypoint.

## 3. Authorization architecture

```mermaid
flowchart LR
    A[Omada External Portal] --> C[PortalClientContext]
    B[CAPPORT resolve_for_login] --> C
    C --> D[PortalEntryHandler]
    D --> E[AuthSessionManager]
    E --> F[AuthWorker]
    F --> G[Shared OmadaProvider]
    G --> H[(Omada)]
```

CAPPORT is discovery/identity resolution, not a second auth engine.

Ingress SSID evidence has one no-guess contract:
- CAPPORT preserves Omada `/clients` `ssid` through `CapportClient.ssid → PortalClientContext.ssid → AuthSession.ssid → VisitStartRequest.portal_ssid`;
- External Portal uses canonical `ssidName`, with legacy `ssid` fallback;
- conflicting non-empty `ssidName` and `ssid` produce unproven SSID rather than a silent choice.

Auth success is verified state, not successful POST:
`authorize → read-back verification → authStatus==2`.

The Auth layer tracks run number/token, stale-run ownership, retry, expiration and monotonic progress in process memory.

## 4. Data architecture

```mermaid
flowchart TD
    AUTH[Confirmed AUTHORIZED] --> SNAP[Snapshot Collector]
    SNAP --> SJ[visitor_snapshots.log]
    SJ --> REG[Visitor Registry]
    REG --> RDB[(visitor_registry.sqlite3)]

    AUTH --> VS[Visit Start]
    VS --> VISIT[Visit Lifecycle]
    WH[normalized webhook journal] --> VISIT
    VISIT --> VDB[(visits.sqlite3)]

    OPROV[Shared OmadaProvider] --> OBS[Observation]
    OBS --> ODB[(observations.sqlite3)]

    OPROV --> CUR[Current State]
    CUR --> CDB[(current_state.sqlite3)]

    RDB --> ANA[Analytics]
    VDB --> ANA
    ODB --> ANA
    CDB --> ADMIN[Admin Web]
    ANA --> ADMIN
```

### Observation vs Current State

Observation answers: **what happened historically to the authorized measured population?**

Current State answers: **what active wireless clients/APs are present now in configured scope?**

Do not merge their semantics or populations.

## 5. Visit Lifecycle

`AuthSession` is not a physical Visit.

Start:
`confirmed AuthRun → VisitStartRequest → LocalVisitStartSubmitter → VisitLifecycleService → visits.sqlite3`

Close:
`normalized Omada offline journal → webhook reader → OfflineEvidence → service → match/close`.

Current schema: v2.

Write concurrency is explicit: `PriorityWriteCoordinator` serializes writers, gives Visit Start foreground priority, and queues background reader/reconciliation writers FIFO.

Reader/reconciliation health influences runtime `active/degraded`.

## 6. Analytics

Analytics reads persisted source facts only.

```text
Observation / Visit / Registry read boundaries
        ↓
AnalyticsSourceGateway
        ↓
Quality / Wireless / Visit /
CurrentTraffic / HistoricalTraffic / HomeActivity services
```

Source boundaries require read-only SQLite/query-only contracts.

Prohibited:
- Analytics → Omada;
- Analytics → source writes/migrations;
- Admin/browser → direct raw source persistence.

## 7. Traffic analytics

### Current

`CurrentTrafficReadService` owns current Site Network Throughput semantics.

### Historical

`HistoricalTrafficReadService` owns historical Site Network Throughput semantics
for History, Period Statistics and Peak Load.

Canonical path:

```text
persisted Observation AP history
→ HistoricalTrafficReadService
→ AdminQueryService
→ one shared History request
→ History + Period Statistics + Peak Load
```

`TRAFFIC-02-PERF-01` requested-range bounded validation remains an architectural
performance invariant.

Period Statistics:
- unit = Mbps;
- Average = interval/time-aware accepted Site samples;
- Peak = accepted complete Site sample maxima;
- Peak Total is independent max of Total samples;
- statuses = `ok | partial | insufficient_data`;
- same selected 24h/7d Network range as History.

Peak Load:
- reuses the Period Statistics Peak sample population;
- peak timestamps use `cycle_finished_at`;
- ties choose earliest accepted sample;
- busiest bucket uses complete History buckets only;
- busiest 60m is a complete rolling 3600s sample-hold Average Total window;
- no busiest-hour `occurrence_count`;
- same selected 24h/7d range and same read snapshot/execution as History/Statistics.

No second historical semantic/calculation owner is allowed.

## 8. Admin Web

Guest auth and Admin auth remain separate.

Current pages:
Home, Devices, Device Detail, Visits, Observations, Traffic.

Traffic production-current functional surface:
- Current Network Throughput;
- Historical Network Throughput;
- Period Statistics;
- Peak Load.

One shared Traffic coordinator owns page-level orchestration.

Current Traffic and Home Traffic share `CurrentTrafficReadService`.
History, Statistics and Peak share `HistoricalTrafficReadService`.

Peak extends the existing History request (`include=statistics,peak`) and does not
create a second loader/request/range selector.

The current Traffic visual arrangement is not a final design invariant; later
UI/design work may rearrange/polish cards without changing semantic owners.

Forbidden browser paths:
- direct SQLite;
- Omada;
- Loki/Grafana;
- internal Analytics bearer API.

## 9. Shared OmadaProvider invariant

Exactly one provider per process.

The provider owns the shared OAuth token cache. `Condition(RLock)` prevents concurrent refresh storms; compare-and-invalidate prevents stale failures from deleting a newer token.

New independent provider/token manager/cache requires explicit change intent.

## 10. Dependency invariants

| From | Forbidden direct dependency |
|---|---|
| Visitor Registry | Omada API |
| Analytics | Omada API / source writes |
| Admin browser | SQLite / Omada / Loki / Grafana / internal Analytics bearer API |
| CAPPORT | separate AuthWorker/provider |
| Pending Cleaner | Registry DB |
| background worker | Flask `current_app` |
| new subsystem | independent OmadaProvider without approval |

Additional rules:
- worker creation happens in composition, not import side effects;
- writer owns its persistence schema;
- normalized webhook is canonical interpretation boundary for Visit Lifecycle.

## 11. Fail-open matrix

Core fail-closed:
- required Omada configuration/provider construction;
- final client authorization result;
- Admin authentication/network/Site policy.

Independent fail-open relative to guest auth:
- telemetry/counters;
- Snapshot/Registry;
- webhook processing;
- Visit;
- Observation;
- Current State;
- Analytics;
- Admin Web;
- Cleaner.

Fail-open means explicit `disabled`, `unavailable` or `degraded`, never invented values.

## 12. Process/thread model

Supported: one application process.

Process-local:
- AuthSessionManager;
- Auth locks/run ownership;
- auth executor;
- CAPPORT caches;
- Cleaner guard counters/cooldowns;
- Admin sessions, pre-auth CSRF and rate limiter.

Background categories:
Snapshot executor, Registry, Visit reader/reconciler, Observation client/AP/cleanup/integrity, Current State client/AP/cleanup, Cleaner, Public Traffic.

Horizontal HA/multi-process requires shared state plus leader election/inter-process coordination and therefore a separate ADR.

## 13. Startup/shutdown

Startup and shutdown order is normative in `docs/project-inventory.md` and must match current `run.py`.

A key shutdown rule is to stop Visit scheduling before draining Auth, then stop Visit accepting only after Auth executor has drained, so no accepted Auth job can enqueue a Visit start after Visit closes.

## 14. Security boundary

Current Flask proxy trust: exactly one trusted local reverse-proxy hop.

`SecretSafeRequestHandler` strips query strings from access log lines for `/admin...` and `/api/internal/analytics/v1...`.

Admin Web applies HTTPS/source allowlist/session/CSRF/rate-limit/security-header policy separately from guest authorization.

## 15. Infrastructure boundary

Repository code/docs do not own production systemd, reverse proxy, Alloy, Loki or Grafana configuration unless a separate infrastructure/deploy TASK explicitly changes them.
