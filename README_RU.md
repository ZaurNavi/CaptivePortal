# CaptivPortal Core Platform

[English version](README.md)

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-green.svg)](https://www.python.org/)
[![Omada](https://img.shields.io/badge/Omada-5.14.31-1f8ceb.svg)]()
[![Status](https://img.shields.io/badge/status-production%20platform-blue.svg)]()
[![Architecture](https://img.shields.io/badge/architecture-site--aware%20single--process-orange.svg)]()

CaptivPortal начинался как внешний Captive Portal для авторизации гостей через **TP-Link Omada**. Сейчас это уже небольшая operational-платформа со своим движком авторизации, историей устройств, Visit Lifecycle, периодическими wireless observations, Current State, Analytics, защищённым внутренним API и собственным read-only Admin Web.

Этот README намеренно написан **для человека, который открыл GitHub глазами**, а не как индекс для coding agent. Он в первую очередь отвечает на четыре вопроса:

1. Что такое CaptivPortal?
2. Как он работает?
3. Что уже построено?
4. Какой следующий шаг?

Точные инженерные контракты, source-of-truth, configuration defaults и подробности модулей находятся в постоянной базе знаний [`docs/`](docs/README.md).

---

## Проект одним взглядом

| Пункт | Текущее положение |
|---|---|
| Repository implementation checkpoint | `main@daf68e91fc759188980cf8741913e6b60a58eb62` |
| Repository tree | `b0e2f028eecf6aec9d86e35542c33e7105209335` |
| Production deployed HEAD | `daf68e91fc759188980cf8741913e6b60a58eb62` |
| Production tree | `b0e2f028eecf6aec9d86e35542c33e7105209335` |
| Current Network Throughput | **Production active** |
| Network Traffic History | **Production active** |
| Period Statistics | **Production active** |
| Peak Load | **Production active** |
| Traffic by AP | **Production active** |
| Independent historical ranges | **Production active / acceptance PASS** |
| Следующий Traffic stage | `TRAFFIC-06 — AP Traffic Share` — NEXT / DRAFT REQUESTED / не реализован |
| Omada Controller family | Omada Software Controller 5.14.x |
| Основная guest authorization | Реализована |
| CAPPORT | Реализован |
| Visitor Registry / Visit Lifecycle | Реализованы |
| Observation / Current State | Реализованы |
| Analytics / Admin Web | Реализованы |
| Multi-Site / Tenant / RBAC | Future evolution |
| Текущая topology | Один application process; HA/multi-process требует ADR |

> Repository defaults, production enabled-state и dated acceptance evidence — разные факты.

## Где проект находится сейчас

Traffic production-active до Traffic by AP включительно; historical панели имеют
независимые диапазоны 24h/7d.

```mermaid
flowchart LR
    A[Portal / Auth] --> B[CAPPORT]
    B --> C[Observation / Visit]
    C --> D[Analytics]
    D --> E[Admin Web]
    E --> T0[Traffic Foundation]
    T0 --> T1[Current]
    T1 --> T2[History]
    T2 --> T3[Statistics]
    T3 --> T4[Peak]
    T4 --> T5[Traffic by AP]
    T5 --> R[Independent panel ranges]
    R --> T6{{СЛЕДУЮЩИЙ: AP Traffic Share}}
```

Текущая functional layout является production-current, но не зафиксирована как
окончательный визуальный дизайн.

## Что CaptivPortal умеет сегодня

Текущий runtime включает:

- external portal/CAPPORT authorization;
- Snapshot/Registry и Visit Lifecycle;
- Observation и Current State;
- Analytics и protected internal API;
- Admin Web/Home;
- Current Network Throughput;
- Network Traffic History;
- Period Statistics;
- Peak Load;
- Traffic by AP;
- независимые page-local `24h | 7d` selectors для всех historical Traffic panels;
- не более одного historical HTTP request одновременно и 10-second admission guard;
- Grafana/Loki отдельно от product UI.

Current Network Throughput range-insensitive.

Network Traffic — AP/network evidence в Mbps. Это не WAN/Internet/billing/SSID и
не Guest Session Traffic.

# Архитектура

## Общая схема платформы

```mermaid
flowchart TB
    subgraph Guest["Guest / Wi-Fi сторона"]
        Client[Wi-Fi клиент]
        External[Omada External Portal]
        CapportClient[RFC 8908 CAPPORT client]
    end

    subgraph PortalPlane["Portal / authorization plane"]
        Entry[Portal entry]
        Context[PortalClientContext]
        Sessions[AuthSessionManager]
        Worker[AuthWorker]
        Provider[Shared OmadaProvider]
        Cleaner[Pending Session Cleaner]
    end

    subgraph OmadaPlane["Omada"]
        Controller[(Omada Controller)]
        Webhook[Omada webhook]
    end

    subgraph DataAcquisition["Acquisition / persistence"]
        Snapshot[Authorized Snapshot]
        Registry[(Visitor Registry)]
        Visit[(Visit Lifecycle v2)]
        Obs[(Observation DB v1)]
        Current[(Current State DB v1)]
        Normalized[Normalized webhook journal]
    end

    subgraph ReadPlane["Read / analytics plane"]
        RegistryRead[Registry read service]
        VisitRead[Visit read service]
        ObsRead[Observation read service]
        CurrentRead[Current State read service]
        Analytics[Analytics services]
        Traffic[CurrentTrafficReadService]
        InternalAPI[Protected Analytics API]
    end

    subgraph ProductPlane["Product / operator plane"]
        AdminQuery[AdminQueryService]
        AdminAPI["/admin/api/v1"]
        AdminPages[Admin Web]
        Browser[Operator browser]
    end

    subgraph Observability["Engineering observability"]
        Logs[JSONL / journals]
        Alloy[Grafana Alloy]
        Loki[(Loki)]
        Grafana[Grafana]
    end

    Client --> External --> Entry
    Client --> CapportClient --> Entry
    Entry --> Context --> Sessions --> Worker --> Provider --> Controller

    Provider --> Cleaner
    Worker --> Snapshot --> Registry
    Worker --> Visit
    Controller --> Webhook --> Normalized --> Visit
    Provider --> Obs
    Provider --> Current

    Registry --> RegistryRead
    Visit --> VisitRead
    Obs --> ObsRead
    Current --> CurrentRead

    RegistryRead --> Analytics
    VisitRead --> Analytics
    ObsRead --> Analytics
    ObsRead --> Traffic

    Analytics --> InternalAPI

    RegistryRead --> AdminQuery
    VisitRead --> AdminQuery
    ObsRead --> AdminQuery
    CurrentRead --> AdminQuery
    Traffic --> AdminQuery

    AdminQuery --> AdminAPI --> AdminPages --> Browser

    Worker --> Logs
    Cleaner --> Logs
    Snapshot --> Logs
    Normalized --> Logs
    Logs --> Alloy --> Loki --> Grafana
```

### Смысл архитектуры одной строкой

```text
Authorization решает доступ.
Collectors сохраняют факты.
Visit Lifecycle превращает события в Visits.
Analytics читает сохранённые факты.
Admin Web безопасно показывает их человеку.
Grafana остаётся инженерной observability.
```

---

## Process composition

`run.py` — единственный прямой process entrypoint и верхнеуровневый lifecycle/composition root.

Упрощённая схема startup:

```mermaid
flowchart TD
    Start[run.py] --> Settings[get_settings]
    Settings --> Shared[Создать shared OmadaProvider]
    Shared --> Snapshot[Создать Snapshot Collector]
    Snapshot --> Visit[Создать Visit Lifecycle]
    Visit --> Flask[create_app: Auth / Portal / CAPPORT / Webhook / Counters]
    Flask --> Obs[Создать Observation]
    Obs --> Current[Создать Current State]
    Current --> Cleaner[Создать Pending Cleaner]
    Cleaner --> Workers[Запустить background workers]
    Workers --> Registry[Запустить Visitor Registry]
    Registry --> Reconcile[Запустить Visit reader / reconciliation]
    Reconcile --> Analytics[Собрать Analytics]
    Analytics --> Admin[Собрать Admin Web]
    Admin --> Traffic[Запустить Public Traffic worker]
    Traffic --> Serve[Запустить Flask server]
```

Shutdown также управляемый: фоновые компоненты перестают принимать работу, необходимые очереди bounded-drain, storage-owning modules закрываются в контролируемой последовательности.

### Single-process assumption

Process-local сегодня:

- Auth sessions и locks;
- Auth executor;
- CAPPORT caches;
- Cleaner ActionGuard;
- Admin sessions/login limiter;
- worker lifecycle state.

Поэтому горизонтальный multi-process — **не просто смена WSGI-параметра**. Для HA требуется отдельный ADR по shared state, leader election/worker ownership и coordination.

---

# Гостевая авторизация

## Один authorization engine

Omada External Portal и CAPPORT — разные входы в одну систему, а не две независимые авторизации.

```mermaid
flowchart LR
    A[Omada External Portal] --> C[PortalClientContext]
    B[RFC 8908 CAPPORT] --> C
    C --> D[AuthSessionManager]
    D --> E[AuthWorker]
    E --> F[Shared OmadaProvider]
    F --> G[(Omada Controller)]
    G --> H{Verified authStatus == 2?}
    H -- Да --> I[AUTHORIZED]
    H -- Нет --> J[Bounded retry / failure]
```

### Последовательность авторизации

```mermaid
sequenceDiagram
    participant C as Wi-Fi клиент
    participant P as CaptivPortal
    participant S as AuthSessionManager
    participant W as AuthWorker
    participant O as Omada Controller
    participant V as Visit/Snapshot hooks

    C->>P: Открыть captive portal
    P->>P: Определить PortalClientContext
    P->>S: Создать или переиспользовать AuthSession
    S->>W: Запустить authorization run
    W->>O: Прочитать состояние клиента
    O-->>W: active / authStatus / context
    W->>O: Выполнить authorize при необходимости
    O-->>W: HTTP + Omada errorCode/result
    W->>O: Финальная verification
    O-->>W: authStatus == 2
    W-->>S: AUTHORIZED
    W->>V: Snapshot / Visit Start evidence
    S-->>P: Финальный state, progress 100%
    P-->>C: Close attempt / bounded same-page fallback
```

Успех определяется подтверждённым состоянием контроллера, а не просто успешным HTTP transport.

---

# Pending Session Cleaner

Pending Session Cleaner занимается зависшими неавторизованными клиентами и не превращается во второй authorization engine.

Его safety philosophy:

```text
uncertainty => no reconnect
```

```mermaid
flowchart TD
    Scan[Получить active client inventory] --> Full{Inventory полный?}
    Full -- Нет --> Stop[Partial scan: action запрещён]
    Full -- Да --> Candidate[Классифицировать authStatus=1]
    Candidate --> Local1{Защищён local AuthSession?}
    Local1 -- Да --> Skip[Пропустить]
    Local1 -- Нет --> Fresh[Свежий client preflight]
    Fresh --> Eligible{Всё ещё eligible?}
    Eligible -- Нет --> Skip
    Eligible -- Да --> Local2{Защищён сейчас?}
    Local2 -- Да --> Skip
    Local2 -- Нет --> Limits[Cooldown / hourly / per-scan guard]
    Limits --> Audit[Durably записать action.planned]
    Audit --> Reconnect[Omada reconnect]
    Reconnect --> Verify[Bounded verification]
    Verify --> Done[Записать action.completed]
```

Подтверждённая операция Cleaner — Omada client reconnect. `block/unblock` не используется как автоматический fallback.

---

# Как события превращаются в данные продукта

## Общая data chain

CaptivPortal специально разделяет acquisition и analytics.

```mermaid
flowchart LR
    Omada[(Omada)] --> Collect[Collectors / webhook normalization]
    Collect --> Facts[Normalized facts]
    Facts --> Persist[(Persistent storage)]
    Persist --> Reads[Read services]
    Reads --> Analytics[Analytics]
    Reads --> Admin[Admin Query Service]
    Analytics --> Admin
    Admin --> UI[Admin Web]
```

Постоянный принцип:

```text
Collector собирает и сохраняет факты.
Analytics читает уже сохранённые факты.
Analytics не идёт обратно в Omada, чтобы "дорисовать" отсутствующую историю.
```

Поэтому историческая аналитика должна оставаться доступной по persisted history даже при временной недоступности Omada во время запроса.

---

## Snapshot vs Observation vs Current State vs Visit

Эти слои отвечают на разные вопросы и не заменяют друг друга.

| Слой | Какой вопрос решает | Population / смысл | Persistence |
|---|---|---|---|
| Authorized Snapshot | «Как выглядел успешно авторизованный клиент в момент авторизации?» | Один подробный start-of-history capture | JSONL |
| Visitor Registry | «Какое стабильное устройство и его историю мы знаем?» | Device card + captured history | SQLite |
| Observation | «Какие measurements были у authorized clients/AP во времени?» | Historical authorized population + AP facts | SQLite v1 |
| Current State | «Какие wireless clients/AP активны прямо сейчас?» | Active wireless inventory, включая pending | SQLite v1 |
| Visit Lifecycle | «К какому Visit относилась авторизация и когда Visit закончился?» | Site-aware Visit + source events | SQLite v2 |
| Analytics | «Какие выводы можно получить из сохранённых фактов?» | Query-on-read derived results | Без source persistence |
| Admin Web | «Что оператор должен безопасно увидеть?» | Bounded Site-scoped presentation | Без business DB |

### Observation и Current State

```mermaid
flowchart TB
    Omada[(Omada)] --> O[Observation collector]
    Omada --> C[Current State collector]

    O --> ODB[(Длинная историческая Observation history)]
    C --> CDB[(Короткая Current State history)]

    ODB --> A[Analytics / historical views]
    CDB --> H[Home Live / near-real-time views]
```

Observation client population: active + authorized в configured scope.

Current State включает **всех active wireless clients в scope** и классифицирует:

```text
authStatus 2      → authorized
authStatus 1      → pending
other integer     → other
missing / invalid → unknown
```

Новый failed/partial Current State cycle не подменяет last complete-success snapshot.

---

# Visit Lifecycle

`AuthSession` не равен физическому Visit.

Один Visit может содержать несколько authorization events. Visit Lifecycle даёт платформе durable Site-aware сущность для истории, analytics и UI.

```mermaid
flowchart LR
    Device[Visitor device] --> Auth[Successful authorization]
    Auth --> Open[OPEN VISIT]
    Auth --> Snap[Initial snapshot]
    Open --> Obs[Client / AP observations]
    Webhook[omada.client_offline] --> Close[CLOSE / match visit]
    Obs --> Open
    Open --> Close
    Close --> History[Durable visit history]
```

Current schema version: **2**.

Ключевые свойства:

- подтверждённый successful authorization создаёт Visit Start evidence;
- normalized offline webhook закрывает/матчит Visit;
- unmatched offline evidence может ожидать позднего reconciliation;
- Registry reconciliation может позже связать device/snapshot identity;
- webhook reader имеет durable checkpoint;
- foreground Visit Start writes имеют приоритет над background reconciliation writes.

---

# Analytics

Analytics намеренно **demand-only**.

У неё нет:

- отдельного collector thread;
- direct Omada dependency;
- source write path;
- ownership schema Registry/Visit/Observation/Current State.

Current analytics families:

- source/data quality;
- wireless analytics;
- visit analytics;
- Current Traffic interpretation.

```mermaid
flowchart LR
    Registry[(Visitor Registry)] --> G[AnalyticsSourceGateway]
    Visits[(Visit Lifecycle)] --> G
    Obs[(Observations)] --> G
    G --> Q[Data Quality]
    G --> W[Wireless Analytics]
    G --> V[Visit Analytics]
    Obs --> T[Current Traffic]
```

Read connections проверяют ожидаемую schema version и работают через read-only/query-only boundaries.

---

# Current Traffic и Home Traffic

Current Traffic строится из **persisted AP Observation traffic facts**.

Это принципиальное различие:

```text
Current Traffic ≠ Internet/WAN traffic
Current Traffic ≠ guest-only traffic
Current Traffic ≠ SSID-only traffic
```

Это интерпретация физической/network traffic evidence точки доступа.

Сервис предпочитает source family `wired`, с допустимым fallback на `lan`; несовместимые source families не смешиваются по AP внутри одного accepted Site snapshot. Integrity problem даёт unavailable, а не выдуманное число.

```mermaid
flowchart LR
    AP[Access Point] --> Obs[AP Observation facts]
    Obs --> DB[(observations.sqlite3)]
    DB --> CTR[CurrentTrafficReadService]
    CTR --> AQ[AdminQueryService]
    AQ --> Home[Home Traffic]
```

---

# Native Admin Web

Admin Web — это product/operator boundary, а не оболочка над Grafana.

Current pages:

- Home;
- Devices;
- Device Detail;
- Visits;
- Observations.

На Home уже могут находиться:

- **Home Live** — текущие clients/AP из Current State;
- **Home Traffic** — текущая AP traffic interpretation из persisted Observation facts.

Browser намеренно изолирован от backend source systems.

```mermaid
flowchart LR
    Browser[Operator browser] --> Admin["/admin + /admin/api/v1"]
    Admin --> Policy[Admin auth / Site policy / query bounds]
    Policy --> Query[AdminQueryService]
    Query --> Registry[Registry read service]
    Query --> Visit[Visit read service]
    Query --> Obs[Observation read service]
    Query --> Current[Current State read service]
    Query --> Traffic[CurrentTrafficReadService]

    Browser -. запрещено .-> SQLite[(SQLite)]
    Browser -. запрещено .-> Omada[(Omada)]
    Browser -. запрещено .-> Internal["/api/internal/analytics/v1"]
    Browser -. запрещено .-> Grafana[Grafana / Loki]
```

### Admin security boundary

Текущая модель включает:

- отдельную Admin authentication, не guest auth;
- HTTPS requirement, когда включено соответствующей конфигурацией;
- source-network allowlist;
- Site allowlist/default Site;
- password-hash verification;
- pre-auth CSRF;
- login rate limiting;
- bounded in-memory sessions;
- idle и absolute session timeout;
- Secure / HttpOnly / SameSite cookies;
- logout CSRF;
- restrictive CSP;
- `X-Frame-Options: DENY`;
- nosniff;
- no-referrer;
- no-store;
- удаление query string из access-log request line для `/admin` и protected Analytics namespaces.

Business/data Admin API остаётся read-only; POST используется для login/logout security flow.

---

# Home сегодня — и следующий шаг

## Current Home

```mermaid
flowchart TB
    Home[Admin Home]
    Home --> Live[Home Live]
    Home --> Traffic[Home Traffic]

    Live --> CS[CurrentStateReadService]
    Traffic --> CT[CurrentTrafficReadService]

    CS --> Clients[Authorized / Pending / Other / Unknown]
    CS --> APs[Current AP state]
    CT --> Now[AP traffic now]
```

### Home Live

Для человека это:

- сколько scoped wireless clients активно сейчас;
- сколько authorized/pending/other/unknown;
- summary текущих AP;
- freshness / stale / unavailable state.

Home request не делает direct Omada polling.

### Home Traffic

Для человека это:

- текущая AP network traffic interpretation по persisted observations;
- видимая freshness/integrity;
- без ложного переименования в guest Internet usage.

---

## Home Activity: Visits and Traffic

Home Activity реализован, merged и deployed. Home panel:

```text
Today
vs
Selected period
```

с двумя одинаковыми metrics на обеих сторонах:

```text
Authorized visits
Traffic
```

Current implementation checkpoint: `main@53f617b3ac0155d0d647e58e98309927f9a4d318`.

Production evidence 26.08.2026 подтверждает Visit source chain после
`2026-08-26T17:46:55.982Z` (`21:46:55.982 +04`, Asia/Baku). В проверенном
диапазоне 14 из 14 Visits были guest-scope verified, без opening-evidence
integrity anomalies и без unproven-scope rows. `traffic_coverage_from_utc`
остаётся `null`; Traffic нельзя объявлять Complete только из-за течения времени.

Current architecture:

```mermaid
flowchart TB
    Scope[Canonical Current State guest SSID scope]
    TZ[Per-Site timezone / coverage]
    Visits[(Visit Lifecycle persisted facts)]

    Scope --> Activity[HomeActivityReadService]
    TZ --> Activity
    Visits --> Activity

    Activity --> AQ[AdminQueryService]
    AQ --> Today[Today endpoint]
    AQ --> Selected[Selected endpoint]
    AQ --> Preview[Range preview endpoint]

    Today --> Panel[Visits and Traffic panel]
    Selected --> Panel
    Preview --> Panel
```

### Human semantics

**Authorized visits**

- один qualifying Visit opening = одна единица;
- не один AuthSession;
- не одна authorization row;
- повторная авторизация внутри того же открытого Visit не увеличивает count.

**Traffic**

- estimate из eligible completed guest-session offline reports;
- active session не появляется до offline evidence;
- весь reported volume относится к моменту завершения session;
- это не WAN/Internet/billing traffic;
- искусственный 31/90-day Home Activity range cap не предполагается.

Этот panel хорошо показывает текущую зрелость архитектуры: он переиспользует persisted facts и не создаёт ещё один collector.

---

# Engineering observability и product UI

CaptivPortal намеренно разделяет два мира.

```mermaid
flowchart LR
    Runtime[CaptivPortal runtime] --> Logs[Telemetry / journals]
    Logs --> Loki[(Loki)]
    Loki --> Grafana[Grafana]

    Runtime --> Stores[(Product data stores)]
    Stores --> Read[Read services / Analytics]
    Read --> Admin[CaptivPortal Admin Web]

    Grafana --> Engineers[Engineering / diagnostics]
    Admin --> Operators[Product / operator workflow]
```

### Grafana

Для:

- engineering observability;
- collector validation;
- diagnostics;
- investigation;
- telemetry exploration;
- анализа health платформы.

### CaptivPortal Admin Web

Для:

- operator/customer-facing product views;
- bounded Site-aware information;
- стабильной product semantics;
- дальнейшей customer-facing эволюции.

Grafana/Loki не должны становиться backend'ом коммерческого product UI.

---

# Карта persistence

| Store / journal | Writer | Основные readers | Смысл |
|---|---|---|---|
| `auth_telemetry.log` | Auth telemetry | observability | authorization operations |
| `visitor_snapshots.log` | Snapshot Collector | Registry / observability | detailed authorized snapshots |
| `omada_webhook.log` | Webhook Receiver | processor / ops | redacted raw webhook |
| `omada_webhook_normalized.log` | Webhook Processor | Visit / Public Traffic | canonical normalized events |
| `pending_session_cleaner.log` | Pending Cleaner | ops / audit | action audit |
| `portal_counter.db` | Portal Counter | portal API | public auth counts |
| `public_traffic.sqlite3` | Public Traffic | portal API | completed-session traffic counter |
| `visitor_registry.sqlite3` | Visitor Registry | Registry reads / Analytics / Admin | durable device identity/history |
| `visits.sqlite3` | Visit Lifecycle | Visit reads / Analytics / Admin | visits, auth evidence, source events |
| `observations.sqlite3` | Observation Foundation | Observation reads / Analytics / Admin | historical client/AP facts |
| `current_state.sqlite3` | Current State | CurrentStateReadService / Admin | current snapshots + short history |

Writer владеет schema/migrations. Read consumers не изменяют source storage.

---

# Текущий статус subsystem'ов

Таблица ниже говорит о **repository implementation**, а не утверждает текущие production flags.

| Область | Repository state | Человеческий смысл |
|---|---|---|
| Core Flask platform | ✅ Current | Основное приложение/service |
| Shared OmadaProvider | ✅ Current | Один OAuth/token lifecycle на process |
| Portal authorization | ✅ Current | Общий authorization engine |
| CAPPORT | ✅ Current | RFC 8908 entry/discovery |
| Auth telemetry | ✅ Current | Структурированное auth evidence |
| Portal counter | ✅ Current | Public authorization counts |
| Public traffic counter | ✅ Current | Отдельный completed-session counter |
| Authorized Snapshot | ✅ Current, default disabled | Detailed post-auth capture |
| Visitor Registry | ✅ Current, default disabled | Durable device/history identity |
| Omada webhook receiver/normalizer | ✅ Current, default disabled | Canonical inbound event pipeline |
| Pending Session Cleaner | ✅ Current, default disabled | Safe stale-pending cleanup |
| Visit Lifecycle | ✅ Current, default disabled | Site-aware visits, schema v2 |
| Observation Foundation | ✅ Current, default disabled | Historical authorized/AP facts, schema v1 |
| Current State | ✅ Current, default disabled | Active wireless state, schema v1 |
| Analytics | ✅ Current, default disabled | Read-only derived views |
| Protected Analytics API | ✅ Current, default disabled | Internal aggregate HTTP boundary |
| Admin Web | ✅ Current, default disabled | Native read-only operator UI |
| Home Live | ✅ Current, default disabled | Current client/AP summary |
| Current Traffic | ✅ Current при healthy sources | AP traffic interpretation |
| Home Traffic | ✅ Current, default disabled | Home presentation Current Traffic |
| Home Activity | ✅ Current, default disabled | Visits и completed-session Traffic с independent coverage |
| Traffic Section Foundation | ✅ Current, default disabled | Отдельный Site-scoped Traffic product shell/coordinator |
| Current Network Throughput | ✅ Current, default disabled | Persisted AP/network Mbps через CurrentTrafficReadService |
| GitHub Actions release CI | ⚠️ Отсутствует | Process debt |

---

# Omada Open API — что реально подтверждено исследованием

CaptivPortal использует curated Omada API contract и не делает выводы только по названию endpoint.

Controlled research на Omada 5.14.31 подтвердил:

| Capability | Research result | Current product meaning |
|---|---|---|
| Read clients / client details | Confirmed | Используется approved read/control modules |
| Rename client | Public OpenAPI работает | Research-proven; не значит, что кнопка есть в Admin |
| Per-client rate limit | Работает и физически ограничивает | Research-proven |
| Rate-limit profiles | CRUD/application работает | Research-proven |
| Reconnect | Физически разрывает connection | Используется Cleaner под safety gates |
| Block | Удаляет active access | Research-proven; не Cleaner fallback |
| Unblock | Снимает запрет | Сам по себе не reconnect |
| Hotspot unauthorize | Удаляет authorization record | Research-proven |
| Hotspot authorize | Может pending → authorized | Portal-bypass semantics не обобщены |
| Authentication period | Подтверждена extension-delta semantics | Не absolute timestamp |
| Lock-to-AP | Config/rollback работает | Physical multi-AP roaming prevention не закрыт полностью |
| Full clear custom public rate limit | Не закрыт stable public contract | Private UI API не approved product contract |

Наличие Omada capability **не означает**, что это уже product feature CaptivPortal. Для product exposure требуется отдельное security/UX/authorization решение.

См. [`docs/api/omada-open-api.md`](docs/api/omada-open-api.md).

---

# Roadmap

## Уже пройденная лестница

```mermaid
flowchart LR
    P[Portal/Auth]:::done --> O[Observation]:::done
    O --> A[Analytics]:::done
    A --> W[Admin Web]:::done
    W --> T0[Traffic Foundation]:::done
    T0 --> T1[Current]:::done
    T1 --> T2[History]:::done
    T2 --> T3[Period Statistics]:::done
    T3 --> T4[Peak Load]:::done
    T4 --> T5[Traffic by AP]:::done
    T5 --> R[Independent ranges]:::done
    R --> T6[AP Traffic Share]:::next
    T6 --> TP[Следующие Traffic panels]:::future
    TP --> MS[Multi-Site]:::future

    classDef done fill:#d9f2d9,stroke:#2e7d32,color:#000;
    classDef next fill:#fff3cd,stroke:#b8860b,color:#000;
    classDef future fill:#eeeeee,stroke:#777,color:#000;
```

## Near-term direction

```text
TRAFFIC-00         DONE
TRAFFIC-01         DONE / PRODUCTION ACTIVE
TRAFFIC-02-READ    DONE
TRAFFIC-02         DONE / PRODUCTION ACTIVE
TRAFFIC-02-PERF-01 DONE
TRAFFIC-03         DONE / PRODUCTION ACTIVE
TRAFFIC-04         DONE / PRODUCTION ACTIVE
TRAFFIC-05         DONE / PRODUCTION ACTIVE
TRAFFIC-RANGE-01   DONE / PRODUCTION ACTIVE / PRODUCTION ACCEPTANCE PASS
TRAFFIC-06         NEXT / DRAFT REQUESTED / NOT IMPLEMENTED
```

Следующий change-intent — `TRAFFIC-06 — AP Traffic Share`: доля accepted Network
Traffic evidence в выбранном диапазоне. `sample count != traffic share`.
Точные детали должны появиться только после DRAFT → review → FINAL.

## Реальный второй Site как trigger

CaptivPortal намеренно **Site-aware до Multi-Site**.

Реальный второй Site — момент, когда abstractions должны пройти проверку живым requirement.

```mermaid
flowchart TD
    Single[Current Site-aware single-site operation]
    Single --> Trigger{Появился реальный второй Site}
    Trigger --> ADR[Multi-Site ADR]
    ADR --> Isolation[Site selection / data isolation / branding]
    Isolation --> Multi[Multi-Site product]
    Multi --> Tenant[Tenant model]
    Tenant --> RBAC[Customer accounts / RBAC]
    RBAC --> Entitlements[Plans / entitlements]
    Entitlements --> Service[Commercial managed service]
```

Постоянное правило:

```text
Tenant != Site
```

Один Tenant в будущем может иметь несколько Sites.

---

## Future Tenant / commercial model

Будущая server-side authorization model:

```mermaid
flowchart LR
    Identity[Authenticated customer identity] --> Tenant[Tenant]
    Tenant --> Sites[Allowed Sites]
    Sites --> Permissions[Permissions]
    Permissions --> APIs[Allowed APIs / actions]
    Plan[Subscription plan] --> Entitlements[Entitlements]
    Entitlements --> APIs
    APIs --> UI[Один Admin Console]
```

Коммерческое направление — один product с backend-enforced capabilities, а не отдельные forks.

Будущая managed-service модель:

```text
На стороне клиента
  Internet
  compatible router/gateway
  recommended Omada APs

На нашей стороне
  Omada Controller
  CaptivPortal
  Visitor Registry
  Visit Lifecycle
  Observation Storage
  Analytics
  Admin Console
  Monitoring
  Backups
  Updates
```

---

# Важные архитектурные границы

### Shared Omada provider

Один process → один shared `OmadaProvider` → один shared token cache.

Второй provider/token manager без отдельного архитектурного решения запрещён.

### Fail-open и fail-closed

**Fail-closed:**

- обязательная core Omada configuration;
- фактический guest authorization result;
- Admin authentication/network/Site policy.

**Fail-open относительно guest authorization:**

- telemetry;
- counters;
- Snapshot / Registry;
- webhook normalization;
- Visit persistence/reconciliation;
- Observation;
- Current State;
- Analytics;
- Admin Web;
- Pending Cleaner.

Fail-open означает safe degraded/unavailable/disabled, а не fabricated success/data.

### Admin browser isolation

Browser напрямую не читает:

- SQLite;
- Omada;
- Loki;
- Grafana;
- protected internal Analytics bearer API.

### Current Traffic scope

AP physical/network traffic нельзя называть «guest Internet traffic».

### Visitor identity и Site identity

Registry device identity сегодня не является автоматически Site-specific truth. Site-scoped facts должны оставаться Site-scoped в Visit/Observation/Admin semantics.

---

# Testing и release discipline

Detailed authority: [`docs/testing.md`](docs/testing.md).

Coder выполняет только focused/minimal TASK/module tests. Broader/full/official
acceptance принадлежит Owner + Tech Lead/Central Lab.

Permanent promotion rule:

```text
Patch → Lab.
All mandatory gates → PASS.
Accepted candidate → Git.
Git → Production.
Activation → separate step.
```

V6/full PASS недостаточен для publication, если TASK/FINAL ещё требует
PERF/Linux/security/browser/etc. gate.

Production application code штатно доставляется только из Git по verified
SHA/tree. Patch — Lab/handoff artifact, а не production code identity.

# Configuration

CaptivPortal группирует настройки по subsystem. Authoritative list/defaults находятся в `.env.example`, `app/config.py`, `app/settings.py` и [`docs/configuration.md`](docs/configuration.md).

Основные группы:

```text
Core / Omada
Portal / CAPPORT
Auth telemetry
Portal counter
Public traffic
Authorized Snapshot
Visitor Registry
Webhook
Pending Session Cleaner
Visit Lifecycle
Observation
Current State
Analytics
Analytics API
Admin Web
Home Live
Home Traffic
Traffic Section
```

Production secrets не коммитятся в Git.

`.env.example` — reference template. Реальный production state проверяется в approved runtime/deployment environment, а не выводится из repository defaults.

---

# Installation / local run

## Требования

- Python 3.10+
- Linux; Ubuntu 22.04 family — current production family, зафиксированная проектом
- network reachability к Omada Controller
- dependencies из `requirements.txt`

## Clone

```bash
git clone https://github.com/ZaurNavi/CaptivePortal.git
cd CaptivePortal
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

## Run

Передать required process environment, затем:

```bash
python3 run.py
```

Production использует system service и deployment-specific environment configuration. См. [`docs/deployment.md`](docs/deployment.md).

---

# База знаний

README — это карта проекта для человека. KB — инженерный authority для подробностей.

Основные документы:

- [`AGENTS.md`](AGENTS.md) — workflow и правила работы с repository;
- [`docs/README.md`](docs/README.md) — knowledge map;
- [`docs/project-inventory.md`](docs/project-inventory.md) — exact runtime inventory;
- [`docs/architecture.md`](docs/architecture.md) — lifecycle/dependency architecture;
- [`docs/module-index.md`](docs/module-index.md) — module status map;
- [`docs/configuration.md`](docs/configuration.md) — configuration groups/defaults;
- [`docs/testing.md`](docs/testing.md) — test responsibility/gates;
- [`docs/deployment.md`](docs/deployment.md) — deployment contract;
- [`docs/security.md`](docs/security.md) — security boundaries;
- [`docs/api/omada-open-api.md`](docs/api/omada-open-api.md) — curated Omada evidence;
- [`docs/modules/visit-lifecycle.md`](docs/modules/visit-lifecycle.md);
- [`docs/modules/observations.md`](docs/modules/observations.md);
- [`docs/modules/current-state.md`](docs/modules/current-state.md);
- [`docs/modules/analytics.md`](docs/modules/analytics.md);
- [`docs/modules/admin-web.md`](docs/modules/admin-web.md).

## Truth model

Для **того, как система работает сейчас**:

```text
current code
    ↓
current tests
    ↓
current docs, подтверждённые кодом
```

Для **ещё не merged change**:

```text
FINAL TASK
    ↓
PLAN
    ↓
ADR
```

FINAL TASK не становится current runtime только потому, что он утверждён.

---

# Known limitations и technical debt

| Debt / limitation | Почему важно |
|---|---|
| Single-process topology | Multi-process/HA требует shared-state и worker-leadership design |
| `VERIFY_SSL=false` repository default | Security-hardening debt; production truth host-verified |
| Нет GitHub Actions release CI | Full release gate остаётся procedural/manual |
| Production enabled-state нельзя доказать Git'ом | Runtime flags проверяются на host |
| Omada private UI APIs не approved product contracts | Private/reverse-engineered endpoints нельзя незаметно превращать в stable dependency |
| Public full-clear custom client rate limit unresolved | Известный пробел Omada control research |
| Часть traffic sources — estimates/scope-specific | UI не должен выдавать их за billing/WAN truth |
| Registry global-by-MAC имеет Site-awareness limits | Future Multi-Site должен сохранить правильную ownership semantics |

---

# Философия проекта

Несколько принципов описывают CaptivPortal лучше, чем простой список features:

```text
Один authorization engine.
Один shared Omada provider.
Сначала сохранить факт — потом интерпретировать.
Не дорисовывать исторические данные по запросу.
Optional analytics/UI failure не должен ломать guest access.
Engineering observability и customer product — разные boundaries.
Сначала Site-aware, потом Multi-Site.
Tenant не равен Site.
Показывать uncertainty, а не выдумывать precision.
```

Именно в эту сторону CaptivPortal развивается: от Captive Portal к управляемому, data-driven network access service.

---

## License

См. [LICENSE](LICENSE).
