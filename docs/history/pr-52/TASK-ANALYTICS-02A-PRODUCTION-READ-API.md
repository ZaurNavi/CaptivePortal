# TASK-ANALYTICS-02A — Production Read API Foundation

**Status:** APPROVED FOR IMPLEMENTATION  
**Execution mode:** implementation  
**Executor/platform:** coding agent; implementation and Windows/local tests  
**Test responsibility:** shared — coding agent runs targeted/full; Tech Lead runs exact-patch Linux gate; owner alone performs deploy  
**Owner merge:** required  
**Production deployment/activation:** separate owner-controlled deploy step  
**Implementation baseline:** `origin/main@0f42f537ec17b575fbb2bd42f83224aa1b0ff807`  
**Branch:** `feature/analytics-production-api-v1`

---

## 1. Цель

Подключить уже принятые Analytics 01A/01B/01C к production composition root и предоставить ограниченный внутренний read-only HTTP API для владельца/технической команды.

После реализации и отдельной production activation должно стать возможно выполнять реальные Site-scoped Analytics-запросы к production Observation/Visit/Registry данным через защищённый API.

Это первый production delivery слой Analytics, а не полноценный коммерческий Admin Console.

Целевой поток:

```text
owner/internal consumer
        ↓
dedicated Analytics API security boundary
        ↓
AnalyticsReadService / WirelessAnalyticsService / VisitAnalyticsService
        ↓
AnalyticsSourceGateway
        ↓
existing read-only source boundaries
        ↓
Observation v1 / Visit v2 / Registry v1
```

---

## 2. Причина отдельного TASK

После Analytics 01A/01B/01C существуют:

- immutable Analytics DTO;
- Site-scoped query services;
- hard SQLite progress-handler deadline;
- bounded query windows;
- quality/provenance;
- Wireless Analytics;
- Visit Analytics;
- read-only source gateways.

Но текущий production runtime их не создаёт и не вызывает:

- `run.py` не строит Analytics runtime;
- Flask не регистрирует Analytics routes;
- нет административной security boundary;
- `ANALYTICS_FOUNDATION_ENABLED` сам по себе не имеет runtime-эффекта;
- нет production smoke/health contract.

Этот TASK закрывает именно данный разрыв.

---

## 3. Подтверждённый baseline

Использовать только:

```text
origin/main@0f42f537ec17b575fbb2bd42f83224aa1b0ff807
```

В baseline уже приняты:

```text
Analytics 01A — Read and Data Quality Foundation
Analytics 01B — Wireless Analytics Foundation
Analytics 01C — Visit Analytics Foundation
```

Source contracts:

```text
Observation schema: v1
Visit schema:       v2
Registry schema:    v1
```

Tech Lead exact-merge Linux evidence:

```text
Visit Analytics targeted: 25 passed
Full classified gate:      1411 passed, 2 deselected
POSIX/safety:              11 passed
compileall:                PASS
git diff --check:          PASS
```

Два deselected cases классифицированы отдельно:

- известный baseline Node async-harness case;
- запрет `AF_UNIX` socket внутри Tech Lead sandbox (`EPERM`).

До изменений кодер обязан подтвердить exact baseline и отсутствие новых commits в `origin/main`. Если baseline изменился — остановиться и вернуть impact report.

### Capability assumptions

Coding agent должен подтвердить до редактирования:

```text
repository read/write: available
shell/test execution:  available
branch creation:       available
commit/push/PR:         blocked до отдельного Tech Lead verdict
production access:     not required / forbidden
external network:      optional, не требуется для implementation
```

Если локально отсутствует Linux, кодер выполняет Windows/local gate и возвращает patch для обязательного Tech Lead Linux gate.

### Связанные документы

Прочитать только:

1. `TASK-ANALYTICS-FOUNDATION-01-REV1`;
2. `Future_Multi-Site_Compatibility_CaptivPortal`;
3. `Admin_Console_Grafana_Commercial_Access_CaptivPortal`.

До изменения нескольких подсистем кодер обязан вернуть короткий PLAN: composition, security, routes/serialization, tests и handoff.

---

## 4. Архитектурные инварианты

Обязательно сохранить:

- `run.py` — process lifecycle/composition root;
- `app/web/web.py:create_app()` — Flask application factory;
- один production process;
- один существующий OmadaProvider;
- Analytics не обращается к Omada;
- Analytics не собирает и не сохраняет derived metrics;
- Observation/Visit/Registry остаются authoritative sources;
- все Analytics-запросы требуют `site_id`;
- source SQLite открываются только через существующие read-only boundaries;
- `PRAGMA query_only=ON` и URI read-only mode не ослабляются;
- hard statement deadline не заменяется HTTP timeout;
- основной captive authorization flow не зависит от Analytics;
- Analytics failure всегда fail-open относительно портала;
- Admin/API authentication не использует `AuthSession`, `AuthWorker`, captive client state или Omada guest authorization.

---

## 5. Scope

Реализовать:

1. Production Analytics runtime composition.
2. Отдельную конфигурацию внутреннего Analytics API.
3. Dedicated bearer-token security boundary.
4. Source-network allowlist.
5. Site allowlist.
6. Bounded on-demand aggregate query endpoints.
7. Безопасную сериализацию immutable DTO.
8. Cheap authenticated health endpoint.
9. Per-process concurrency guard для тяжёлых запросов.
10. Ограничение размера JSON response.
11. Secret-safe API telemetry/logging.
12. Fail-open startup behavior.
13. Полные targeted/full tests.
14. Отдельный production activation handoff с rollback, но без фактической activation.

---

## 6. Out of scope

Не реализовывать:

- customer-facing Admin Console;
- HTML dashboard;
- Grafana/Loki как product backend;
- Nginx/systemd/Alloy/Grafana production changes;
- customer accounts;
- password login;
- sessions/cookies для администратора;
- OAuth/OIDC;
- RBAC;
- Tenant entity;
- subscriptions/entitlements;
- Site selector UI;
- public CORS;
- background Analytics worker;
- scheduled reports;
- derived Analytics persistence;
- cache/rollup tables;
- source schema или migration changes;
- новые Omada calls;
- source write paths;
- 01A/01B/01C formula changes без отдельного подтверждённого defect;
- production activation в рамках implementation PR.

---

## 7. Production runtime model

Добавить composition-owned Analytics runtime, создаваемый только в `run.py` после создания существующих source runtimes/read services и до запуска Flask server.

Предпочтительный conceptual contract:

```text
create_analytics_runtime(
    settings,
    observation_runtime,
    visit_runtime,
    registry_read_service,
    logger,
)
```

Runtime использует существующие production objects:

- `ObservationReadService` поверх repository активного Observation runtime;
- `VisitLifecycleReadService` активного Visit runtime;
- существующий `VisitorRegistryReadService`;
- один `AnalyticsSourceGateway`;
- один `AnalyticsReadService`;
- один `WirelessAnalyticsService`;
- один `VisitAnalyticsService`.

Запрещено:

- повторно инициализировать source schemas;
- запускать source migrations;
- создавать второй Observation/Visit/Registry worker;
- создавать второй OmadaProvider;
- открывать обычное writable SQLite connection;
- создавать Analytics при import time.

Analytics runtime не имеет фонового `start()` loop. Запросы выполняются только по HTTP demand.

---

## 8. Runtime states

Явно реализовать состояния:

```text
disabled
active
unavailable
```

### disabled

Если master flag или API flag выключен:

- query routes не регистрируются;
- основной portal работает штатно;
- никакие source DB не открываются ради Analytics.

### active

Runtime configuration валидна и все три read boundaries доступны.

### unavailable

API включён и security configuration валидна, но один или несколько source boundaries недоступны.

В этом состоянии:

- основной portal продолжает запуск;
- authenticated health возвращает `503`;
- metric endpoints возвращают controlled `503`;
- traceback, filesystem paths и SQLite internals клиенту не возвращаются.

Невалидный token/network/site security config обязан fail closed: query API не становится доступным, но основной portal продолжает работать.

---

## 9. Configuration

Использовать только существующий путь:

```text
app/config.py
→ app/settings.py:get_settings()
→ typed Analytics/API config
```

Добавить безопасные defaults:

```text
ANALYTICS_FOUNDATION_ENABLED=false
ANALYTICS_WIRELESS_ENABLED=true
ANALYTICS_VISIT_ENABLED=true

ANALYTICS_API_ENABLED=false
ANALYTICS_API_BEARER_TOKEN=
ANALYTICS_API_ALLOWED_NETWORKS=127.0.0.1/32,::1/128
ANALYTICS_API_ALLOWED_SITE_IDS=
ANALYTICS_API_MAX_CONCURRENT_REQUESTS=2
ANALYTICS_API_MAX_RESPONSE_BYTES=1048576
```

Сохранить/экспортировать существующие Analytics settings, которые уже читает `analytics_config_from_settings()`:

```text
ANALYTICS_DEFAULT_LIMIT
ANALYTICS_MAX_LIMIT
ANALYTICS_MAX_QUERY_WINDOW_DAYS
ANALYTICS_MAX_QUERY_DURATION_SECONDS
ANALYTICS_QUALITY_GAP_THRESHOLD_SECONDS
ANALYTICS_WIRELESS_MIN_SAMPLES
ANALYTICS_WIRELESS_MAX_WINDOW_DAYS
ANALYTICS_COUNTER_MAX_GAP_SECONDS
ANALYTICS_AP_JOIN_MAX_LAG_SECONDS
ANALYTICS_RSSI_THRESHOLD_DBM
ANALYTICS_SNR_THRESHOLD_DB
ANALYTICS_VISIT_MIN_COHORT_SIZE
ANALYTICS_VISIT_MAX_WINDOW_DAYS
```

### Validation

- boolean принимает только exact `true` / `false`;
- bearer token обязателен при `ANALYTICS_API_ENABLED=true`;
- token после trim должен иметь минимум 32 символа;
- пустой/whitespace token запрещён;
- allowed networks — непустой список валидных IPv4/IPv6 CIDR;
- allowed Site IDs — непустой список валидных canonical Omada Site IDs;
- max concurrent requests: `1..8`;
- max response bytes: `65536..4194304`;
- secrets не печатаются в config errors, logs или repr.

`.env.example` содержит только placeholder, не production secret.

---

## 10. HTTP namespace

Использовать отдельный namespace:

```text
/api/internal/analytics/v1
```

Все routes:

- только `GET`;
- не имеют write side effects;
- требуют отдельную Analytics API authentication;
- требуют разрешённый source IP;
- metric routes требуют разрешённый `site_id`;
- возвращают `Cache-Control: no-store`;
- возвращают `Pragma: no-cache`;
- возвращают `X-Content-Type-Options: nosniff`;
- не включают CORS headers.

---

## 11. Security boundary

### 11.1. Authentication

Использовать:

```http
Authorization: Bearer <ANALYTICS_API_BEARER_TOKEN>
```

Требования:

- exact scheme `Bearer`;
- один credential;
- comparison через `hmac.compare_digest()` или эквивалент;
- missing/malformed/invalid credential → `401`;
- response содержит `WWW-Authenticate: Bearer`;
- token никогда не попадает в response, logs, telemetry или exceptions;
- query-string token запрещён;
- cookie/session authentication не использовать.

Это временная owner/operator security boundary. Она не объявляется будущей customer authentication моделью.

### 11.2. Source network

После trusted `ProxyFix` использовать фактический `request.remote_addr`.

- source IP должен входить в `ANALYTICS_API_ALLOWED_NETWORKS`;
- иначе `403` до вызова Analytics service;
- default разрешает только loopback;
- не доверять произвольному `X-Forwarded-For` сверх существующего одного trusted Nginx hop.

### 11.3. Site authorization

- `site_id` обязателен для metric routes;
- Site должен входить в `ANALYTICS_API_ALLOWED_SITE_IDS`;
- чужой/неразрешённый Site → `403` до source query;
- backend enforcement обязателен независимо от будущего UI;
- Site ID из URL/query нельзя заменять configured default молча;
- не вводить `tenant_id`;
- не считать `tenant_id == site_id`.

---

## 12. Request contract

Общие обязательные параметры metric routes:

```text
site_id
from_utc
to_utc
```

Правила:

- UTC timestamps используют существующий Analytics parser;
- interval всегда half-open `[from_utc, to_utc)`;
- `from_utc < to_utc`;
- query bounds остаются authoritative в 01A/01B/01C services;
- HTTP layer не расширяет и не обрезает окно молча;
- неизвестные query parameters отклоняются `400`;
- повторяющиеся scalar parameters отклоняются `400`;
- `quality_mode` default: `strict_complete`;
- diagnostic partial mode доступен только через явное значение `diagnostic_including_partial`;
- server-generated evaluation timestamp фиксируется один раз на request, если underlying method требует его;
- никакие клиентские timestamps не подменяются server time молча, кроме документированного optional evaluation time.

---

## 13. Endpoint set v1

Не отдавать тяжёлые aggregate bundles одним HTTP request. Один endpoint должен вызывать один публичный Analytics service method.

Это сохраняет предсказуемый hard deadline и не превращает один request в последовательность из десятков независимых 10-секундных queries.

### 13.1. Health

```text
GET /api/internal/analytics/v1/health
```

Auth/network required. Site не требуется.

Health выполняет только дешёвые read-only checks:

- runtime state;
- enabled modules;
- доступность трёх source read boundaries;
- expected/actual source schema versions;
- отсутствие writable mode.

Не возвращать:

- DB paths;
- filesystem ownership;
- bearer token metadata;
- allowed network list;
- allowed Site list;
- secrets;
- raw SQLite errors.

`200` только если runtime active; иначе controlled `503`.

### 13.2. Quality

```text
GET /api/internal/analytics/v1/quality/source
```

Вызывает ровно:

```text
AnalyticsReadService.get_source_quality(...)
```

### 13.3. Wireless

```text
GET /api/internal/analytics/v1/wireless/signal
GET /api/internal/analytics/v1/wireless/client-context
GET /api/internal/analytics/v1/wireless/concurrency
GET /api/internal/analytics/v1/wireless/ap-resource
GET /api/internal/analytics/v1/wireless/radio-utilization
GET /api/internal/analytics/v1/wireless/throughput
GET /api/internal/analytics/v1/wireless/counter-quality
GET /api/internal/analytics/v1/wireless/correlation
```

Каждый route имеет strict allowlist endpoint-specific parameters и вызывает ровно соответствующий публичный method `WirelessAnalyticsService`.

Не принимать через HTTP `client_mac` в этом TASK. AP MAC разрешён как managed-infrastructure dimension там, где underlying contract его поддерживает.

### 13.4. Visits

```text
GET /api/internal/analytics/v1/visits/counts
GET /api/internal/analytics/v1/visits/time-series
GET /api/internal/analytics/v1/visits/devices
GET /api/internal/analytics/v1/visits/repeat-devices
GET /api/internal/analytics/v1/visits/new-to-site
GET /api/internal/analytics/v1/visits/duration
GET /api/internal/analytics/v1/visits/authorizations
GET /api/internal/analytics/v1/visits/closure
GET /api/internal/analytics/v1/visits/source-events
GET /api/internal/analytics/v1/visits/contexts
GET /api/internal/analytics/v1/visits/transitions
GET /api/internal/analytics/v1/visits/observation-coverage
GET /api/internal/analytics/v1/visits/traffic
GET /api/internal/analytics/v1/visits/return-intervals
```

Каждый route вызывает ровно один публичный `VisitAnalyticsService` method.

Single-Visit detail routes и `visit_id` в HTTP API не входят в этот TASK. Они требуют отдельного privacy/product review.

---

## 14. Serialization

Реализовать один explicit recursive serializer для утверждённых Analytics DTO.

Он обязан поддерживать:

- frozen dataclass;
- `Mapping` / `MappingProxyType`;
- tuple;
- frozenset;
- primitive JSON values;
- nested `AnalyticsResult` внутри composite DTO.

Запрещено:

- сериализовать `__dict__` произвольного объекта;
- отдавать `sqlite3.Row`;
- отдавать raw source dictionaries без approved DTO boundary;
- использовать `default=str` для неизвестных типов;
- молча превращать неизвестный объект в строку;
- включать MAC/device/IP/hostname/raw JSON в aggregate API;
- менять смысл `NULL` на `0`.

Неизвестный тип вызывает controlled internal serialization error и generic `500`, без утечки repr объекта.

---

## 15. Response envelope

Успешный/quality response:

```json
{
  "api_version": "analytics.internal.v1",
  "request_id": "server-generated-uuid",
  "result": {
    "status": "ok|partial|insufficient_data|unavailable",
    "value": {},
    "quality": {},
    "provenance": {}
  }
}
```

Error response:

```json
{
  "api_version": "analytics.internal.v1",
  "request_id": "server-generated-uuid",
  "error": {
    "code": "stable_machine_code",
    "message": "safe generic message"
  }
}
```

Не включать stack trace, exception text, SQL, DB path или token.

---

## 16. HTTP status mapping

```text
200  ok / partial / insufficient_data
400  request/validation error
401  missing or invalid bearer credential
403  disallowed source network or Site
404  disabled route / unknown endpoint
405  non-GET method
429  concurrency limit reached
500  controlled unexpected/serialization error
503  Analytics/source unavailable or query deadline result
```

Для `429` вернуть bounded `Retry-After`.

Analytics result со `status=unavailable` должен отображаться как HTTP `503`, сохраняя safe quality/provenance payload, если payload уже сформирован утверждённым service contract.

---

## 17. Concurrency and resource protection

Добавить process-local non-blocking concurrency guard.

Правила:

- limit задаётся `ANALYTICS_API_MAX_CONCURRENT_REQUESTS`;
- при занятом limit новый metric request сразу получает `429`;
- request не ожидает свободный slot;
- guard освобождается во всех success/error branches;
- health request не выполняет тяжёлые queries, но не должен обходить authentication/network checks;
- не создавать unbounded executor или очередь;
- не выполнять Analytics в auth executor;
- hard SQLite deadline 01A/01B/01C остаётся основным query cancellation mechanism.

После serialization проверить response byte size до отправки.

Если payload превышает `ANALYTICS_API_MAX_RESPONSE_BYTES`:

- payload не отправляется частично;
- вернуть controlled `503 response_too_large`;
- не повышать limit автоматически;
- записать secret-safe operational event.

---

## 18. Telemetry/logging

Минимальные события:

```text
analytics.api_runtime_active
analytics.api_runtime_unavailable
analytics.api_request_completed
analytics.api_request_rejected
analytics.api_request_failed
```

Разрешённые поля:

- request_id;
- route/metric name;
- HTTP status;
- Analytics status;
- duration_ms;
- source IP;
- rejection/failure category;
- rows examined/accepted/rejected из provenance;
- response size.

Запрещённые поля:

- bearer token;
- Authorization header;
- cookies;
- query-string целиком;
- client MAC;
- device ID;
- IP/hostname из source data;
- raw DTO repr;
- SQL;
- DB path;
- source raw JSON;
- secrets.

Не создавать новый Alloy/Loki pipeline в этом TASK.

---

## 19. Fail-open requirements

Следующие ошибки не должны останавливать CaptivePortal authorization runtime:

- invalid Analytics metric config;
- invalid Analytics API config;
- отсутствующая source DB;
- schema mismatch;
- locked/unavailable SQLite;
- deadline;
- serialization failure;
- route exception.

Ошибки локализуются внутри Analytics runtime/API.

Запрещено:

- завершать `run.py` из-за Analytics;
- выключать Omada authorization;
- останавливать Observation/Visit/Registry workers;
- изменять source DB ради восстановления API.

---

## 20. Privacy boundary

В этом TASK HTTP API отдаёт только aggregate Analytics outputs.

Запрещены:

- client MAC lists;
- device ID lists;
- IP addresses из source rows;
- client hostname;
- raw Visit rows;
- raw Snapshot rows;
- raw Observation rows;
- single-Visit detail;
- arbitrary filtering по client MAC.

AP MAC допускается как идентификатор managed infrastructure.

`unique device` в будущих consumer labels не объявляется `unique person`.

---

## 21. Expected files

Разрешён narrow scope:

```text
.env.example
app/config.py
app/settings.py
app/analytics/__init__.py
app/analytics/api.py                 new
app/analytics/api_config.py          new, optional split
app/analytics/runtime.py             new
app/analytics/serialization.py       new, optional split
run.py
tests/analytics/test_api_config.py   new
tests/analytics/test_api_routes.py   new
tests/analytics/test_runtime.py      new
```

Допускается объединить `api_config.py` или `serialization.py` в `api.py`, если это уменьшает surface без ухудшения тестируемости.

`app/web/web.py` изменять только если кодер докажет, что поздняя регистрация Blueprint до `app.run()` нарушает существующий composition/test contract. Общий рефакторинг `web.py` запрещён.

Любой файл вне списка требует stop + impact report до изменения.

### Forbidden files

Без отдельного расширения scope запрещено изменять:

```text
app/auth/**
app/capport/**
app/controllers/**
app/engine/**
app/integrations/omada/**
app/observations/models.py
app/observations/repository.py
app/observations/runtime.py
app/visit_lifecycle/models.py
app/visit_lifecycle/repository.py
app/visit_lifecycle/runtime.py
app/visitor_registry/**
app/web/templates/**
static/**
systemd/**
deploy/**
Grafana/Alloy/Loki artifacts
source schemas/migrations
```

Существующие Analytics formulas/models/source queries также не менять, кроме минимальной доказанной integration incompatibility. В таком случае сначала stop + Tech Lead impact report.

---

## 22. Tests — configuration/security

Обязательные regressions:

- disabled defaults;
- exact boolean validation;
- enabled API без token rejected;
- short/blank token rejected;
- valid IPv4/IPv6 CIDR parsing;
- invalid/empty network list rejected;
- invalid/empty Site allowlist rejected;
- concurrency/response-size bounds;
- secret absent from exception/repr/log capture;
- missing bearer → `401`;
- malformed bearer → `401`;
- invalid bearer → `401`;
- comparison uses constant-time primitive;
- query-string token rejected;
- disallowed source IP → `403` before service call;
- disallowed Site → `403` before service call;
- unknown query parameter → `400`;
- duplicate scalar parameter → `400`;
- non-GET → `405`.

---

## 23. Tests — runtime/fail-open

Обязательные regressions:

- disabled Analytics creates no source connection and no routes;
- active runtime reuses existing source runtime/repository boundaries;
- no new OmadaProvider;
- no source initialize/migration from Analytics runtime;
- missing Observation source → Analytics unavailable, portal app created;
- missing Visit source → Analytics unavailable, portal app created;
- missing Registry source → Analytics unavailable, portal app created;
- schema mismatch → controlled `503`;
- source read exception → controlled `503`;
- API exception does not break `/` or existing AuthSession routes;
- no startup worker/thread created by Analytics;
- no write statements or source row/schema changes.

---

## 24. Tests — routes/contracts

Для каждого endpoint доказать:

- correct service method invoked exactly once;
- Site/from/to passed unchanged after canonical validation;
- half-open semantics remain delegated to Analytics service;
- status/quality/provenance serialized without loss;
- `NULL` remains JSON `null`;
- tuple/MappingProxy/nested DTO serialization deterministic;
- unavailable maps to `503`;
- partial/insufficient map to `200`;
- no-store/security headers present;
- no CORS header;
- aggregate response contains no forbidden identifiers;
- health is cheap and contains no paths/security config;
- endpoint-specific parameter allowlist enforced;
- no bundle method is called;
- concurrency slot releases after exception;
- response-size overflow returns no partial payload.

---

## 25. Performance gate

API layer не должен materially изменять query performance 01A/01B/01C.

Измерить отдельно:

- authentication + parsing + serialization overhead на small fixture;
- response size для largest permitted Visit time-series fixture;
- concurrent limit behavior;
- один representative production-like request каждого класса:
  - quality;
  - wireless;
  - visits.

Acceptance:

```text
API overhead excluding Analytics query < 100 ms p95
response bytes <= configured cap
no queued Analytics requests
one request invokes one public Analytics service method
hard SQLite deadline remains effective
```

Linux exact-patch gate обязателен до commit permission.

---

## 26. Regression gate

Сначала:

```bash
python -m pytest -q -rs tests/analytics
```

Затем source/web regressions:

```bash
python -m pytest -q -rs \
  tests/analytics \
  tests/observations \
  tests/visit_lifecycle \
  tests/visitor_registry \
  tests/test_web.py \
  tests/test_auth_retry_frontend.py
```

Затем full:

```bash
python -m pytest -q -rs
PYTHONPYCACHEPREFIX=/tmp/captiveportal-pyc \
  python -m compileall -q app
git diff --check
```

Вернуть точные counts passed/skipped/failed и отдельно классифицировать только подтверждённые baseline/environment cases.

---

## 27. Production activation handoff

Implementation PR не активирует production.

Handoff обязан подготовить отдельный owner-run deploy plan с:

1. exact expected merge SHA;
2. production repository clean/preflight;
3. backup `/etc/default/captive-portal`;
4. generation of a new strong token вне Git;
5. explicit production values:

```text
ANALYTICS_FOUNDATION_ENABLED=true
ANALYTICS_WIRELESS_ENABLED=true
ANALYTICS_VISIT_ENABLED=true
ANALYTICS_API_ENABLED=true
ANALYTICS_API_BEARER_TOKEN=<secret outside Git>
ANALYTICS_API_ALLOWED_NETWORKS=127.0.0.1/32,::1/128
ANALYTICS_API_ALLOWED_SITE_IDS=<production Site ID>
ANALYTICS_API_MAX_CONCURRENT_REQUESTS=2
ANALYTICS_API_MAX_RESPONSE_BYTES=1048576
```

6. config validation before restart;
7. controlled `systemctl restart captive-portal.service`;
8. PID/active/substate/HTTP portal checks;
9. authenticated localhost health;
10. one small read-only query for quality, wireless and visits;
11. before/after source schema versions and row counts;
12. secret-safe journal inspection;
13. rollback restoring env backup and previous commit/config;
14. proof that token never appears in shell output supplied for review.

Production commands не выполнять в implementation mode.

---

## 28. Acceptance criteria

PASS только если:

- exact baseline confirmed;
- Analytics runtime реально создаётся production composition root при flags;
- disabled defaults сохраняются;
- API имеет отдельную admin/operator security boundary;
- network и Site authorization enforced backend-side;
- routes aggregate-only;
- один request вызывает один service method;
- hard deadlines/bounds 01A/01B/01C сохранены;
- source DB строго read-only;
- нет schema/write/Omada changes;
- no secrets in Git/logs/responses;
- concurrency и response-size limits доказаны;
- failures fail-open к portal authorization;
- Linux exact-patch tests accepted;
- full regression gate accepted;
- production unchanged;
- rollback-ready activation handoff подготовлен.

---

## 29. Stop conditions

Остановиться и вернуть impact report, если:

- `origin/main` не равен baseline;
- для API требуется source migration;
- требуется новый dependency;
- невозможно переиспользовать existing source read boundaries;
- требуется writable Analytics DB;
- bearer token может попасть в access logs;
- Nginx/systemd change необходим для реализации code contract;
- требуется customer authentication/RBAC decision;
- требуется Tenant model;
- один HTTP request невозможно ограничить одним service method;
- main portal не может оставаться fail-open;
- Linux exact-patch gate недоступен до publication.

---

## 30. Repository actions

До отдельного Tech Lead verdict:

```text
commit:                NO
push:                  NO
Pull Request:          NO
merge:                 NO
production activation: NO
```

После реализации вернуть:

- baseline impact;
- архитектуру runtime composition;
- endpoint matrix;
- security proof;
- read-only/schema proof;
- secret-redaction proof;
- performance table;
- targeted/full/Linux results;
- changed files and diff stats;
- patch + SHA256;
- production activation/rollback handoff.

PR после отдельного publish permission должен быть Ready for Review, не Draft, если Tech Lead не укажет иначе. Один task-focused commit; merge остаётся owner-only.

---

## 31. Следующий этап после 02A

После успешной production activation этого TASK отдельным заданием проектируется:

```text
TASK-WEB-FOUNDATION-01
```

Он сможет добавить:

- administrator login/session model;
- read-only internal UI shell;
- navigation;
- Site context;
- dashboard pages поверх этого application/API слоя.

Он не должен использовать Grafana/Loki как product source of truth.
