# Архитектура CaptivPortal

Status: current
Updated: 2026-08-04
Runtime baseline: main commit `227ebe93831447d16b78f277ee3052ddd06e15a3`

## Назначение

CaptivPortal обеспечивает внешний Captive Portal и связанные operational-функции для Omada Controller.

## Основной поток авторизации

~~~mermaid
flowchart TD
    A["Omada External Portal или CAPPORT login"] --> B["PortalClientContext"]
    B --> C["AuthSessionManager"]
    C --> D["AuthWorker"]
    D --> E["Shared OmadaProvider"]
    E --> F["AUTHORIZED / FAILED / RESET"]
~~~

CAPPORT разрешает client identity и направляет login в PortalEntryHandler. Независимый CAPPORT authorization worker или второй provider запрещены.

## Composition root

run.py управляет process lifecycle:

- загружает settings;
- создаёт общий OmadaProvider;
- создаёт snapshot collector;
- вызывает create_app();
- создаёт Pending Session Cleaner с общим provider и AuthSessionManager;
- запускает и останавливает background components;
- запускает Flask development server в текущей реализации.

app/web/web.py:create_app() собирает Flask application: AuthSessionManager, auth executor, AuthWorker, PortalEntryHandler, routes, counters, telemetry и webhook components. Это Flask composition factory, но не отдельный process entrypoint.

## Dependency direction

~~~mermaid
flowchart TD
    A["Web routes"] --> B["Application services"]
    B --> C["Provider / repository interfaces"]
    C --> D["Omada API / JSONL / SQLite"]
~~~

Запрещено:

- repository → Flask route;
- Visitor Registry → Omada API;
- Pending Session Cleaner → Visitor Registry database;
- CAPPORT → отдельный authorization mechanism;
- worker thread → Flask current_app.

## Подсистемы

- Configuration: app/config.py и app/settings.py.
- Omada: ControllerInterface, factory и OmadaProvider.
- Portal/Auth: PortalClientContext, AuthSessionManager, AuthWorker.
- CAPPORT: RFC 8908/8910 API, client lookup и общий login flow.
- Counters: portal open counter и completed-session public traffic.
- Authorized Snapshot: асинхронная фиксация карточки после AUTHORIZED.
- Visitor Registry: последовательное чтение snapshot journal в SQLite.
- Pending Cleaner: `app/pending_sessions/`, implemented-disabled по repository default; guarded reconnect operational module.
- Webhook: raw receiver, normalization и journals.
- Observability: operational telemetry отдельно от data journals.

## Shared OmadaProvider

Один экземпляр на process создаётся в `run.py` и передаётся зависимым компонентам. Provider содержит единый thread-safe token cache на `Condition(RLock)` с одним concurrent refresh и guarded invalidation. Pending-session API methods устанавливаются на тот же класс через `app/controllers/omada_pending_sessions.py`; второй provider или token manager отсутствует.

Фактический lifecycle фиксируется в `docs/project-inventory.md`. Новое изменение cache/provider contract требует явного TASK, regression/concurrency tests и ADR при устойчивом архитектурном решении.

## State и single-process

Auth sessions, retry guards, executor и worker locks находятся в памяти. Несколько WSGI processes создали бы независимые session maps и workers. До отдельного ADR production topology — один application process.

## Fail-open

Независимый модуль при ошибке становится unavailable/disabled, пишет telemetry и не блокирует portal:

- telemetry и counters;
- webhook receiver/normalizer;
- snapshot collector;
- visitor registry;
- public traffic worker;
- pending session cleaner.

Auth failure самого клиента остаётся fail-closed для выдачи доступа, но не валит process.

## Lifecycle

Worker создаётся в composition root, не при import. Cleaner использует fixed-delay и non-blocking scan lock; incomplete inventory, local protection, failed preflight/audit, exhausted budget или shutdown запрещают reconnect. `stop()` идемпотентен, HTTP/retries/verification/shutdown ограничены. Cleaner останавливается первым и после `stopping` не начинает новый POST.

## Infrastructure boundary

Application repository отвечает за код, tests, structured events и документацию контрактов. Alloy, Loki, Grafana, systemd, reverse proxy, OS permissions и production deployment меняются только отдельными infrastructure/deploy TASK.
