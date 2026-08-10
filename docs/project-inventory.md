# Инвентаризация CaptivPortal

Status: current runtime snapshot
Updated: 2026-08-10
Branch: main
Runtime commit: `ab776af3fc58dc090e17ecd20534abddc1f33ad3`
Commit date: 2026-08-10T04:52:20-07:00

Документ описывает runtime-код указанного commit. Repository defaults, фактическое production state и historical acceptance evidence разделены явно. Значения production environment и secrets из Git не выводятся.

## Runtime и composition

- Единственный прямой entrypoint и верхнеуровневый lifecycle: `run.py`.
- Flask composition factory: `app/web/web.py:create_app()`.
- Configuration pipeline: process environment → `app/config.py` → `app/settings.py:get_settings()`.
- Controller factory: `app/controllers/factory.py:create_controller()`.
- Реализация controller: `app/controllers/omada.py:OmadaProvider`.
- Pending-session API adapter: `app/controllers/omada_pending_sessions.py`; методы устанавливаются на тот же `OmadaProvider` в `app/controllers/__init__.py`.
- `run.py` создаёт один provider и передаёт его web/auth, snapshot collector и Pending Session Cleaner.
- `OmadaProvider` содержит единый thread-safe token cache на `Condition(RLock)` с одним concurrent refresh, early refresh и compare-and-invalidate.
- `AuthSessionManager` и `ThreadPoolExecutor(max_workers=4)` создаются один раз на process в `app/web/web.py`.
- In-memory sessions, locks, action limits и workers предполагают один application process.

## Подсистемы и реальные пути

| Подсистема | Код |
|---|---|
| Portal entry | `app/web/portal_entry.py`, `app/web/web.py` |
| AuthSession/AuthWorker | `app/auth/` |
| Omada provider | `app/controllers/omada.py`, `app/controllers/omada_pending_sessions.py` |
| CAPPORT | `app/capport/`, `app/web/templates/portal.html` |
| Auth telemetry | `app/auth_telemetry/` |
| Public Authorization Counter | `app/portal_counter/` |
| Completed-session traffic counter | `app/public_traffic/` |
| Authorized Client Snapshot Collector | `app/visitor_registry/snapshot_*` |
| Visitor Device Registry | `app/visitor_registry/registry_*` |
| Pending Client Session Cleaner | `app/pending_sessions/` |
| Omada Webhook Receiver/Normalizer | `app/integrations/omada/` |

## Configuration

Omada core configuration не содержит production literals в current Git tree. Обязательный внешний contract:

| Environment variable | Назначение |
|---|---|
| `OMADA_URL` | базовый HTTP(S)-адрес controller |
| `OMADA_ID` | Omada controller identifier |
| `OMADA_CLIENT_ID` | OpenAPI client identifier |
| `OMADA_CLIENT_SECRET` | OpenAPI client secret |

Значения передаются process manager или approved secret mechanism и проходят через `app/config.py` → `app/settings.py` → `get_settings()`. Приложение не загружает `.env` автоматически. При отсутствии или некорректности обязательного значения создание `OmadaProvider` завершается fail-closed до сетевого запроса.

`VERIFY_SSL=false` остаётся repository default и открытым security/operations debt; изменение требует отдельного TASK и доверенной certificate model.

## Feature flags по repository default

| Setting | Default | Интерпретация |
|---|---:|---|
| `CAPPORT_ENABLED` | true | реализован и включён конфигурацией |
| `PORTAL_COUNTER_ENABLED` | true | реализован и включён |
| `PUBLIC_TRAFFIC_COUNTER_ENABLED` | true | реализован и включён |
| `AUTH_TELEMETRY_ENABLED` | true | реализован и включён |
| `VISITOR_SNAPSHOT_ENABLED` | false | реализован; по умолчанию выключен |
| `VISITOR_REGISTRY_ENABLED` | false | реализован; по умолчанию выключен |
| `OMADA_WEBHOOK_ENABLED` | false | receiver/normalizer реализованы; по умолчанию выключены |
| `PENDING_SESSION_CLEANER_ENABLED` | false | реализован; по умолчанию выключен |

Repository defaults не подтверждают значения production EnvironmentFile или systemd drop-ins.

## Production evidence

- `main@ab776af` доставлен на production 2026-08-10 обычным fast-forward; `captive-portal.service` после restart подтверждён как active (running).
- Cleaner был включён и подтверждён в production владельцем 2026-08-04. Отдельное post-restart доказательство его worker/events после деплоя 2026-08-10 в status report отсутствует.
- Visitor Snapshot и Visitor Registry ранее прошли production/observability acceptance: `state=ready`, `initial_backfill_completed=true`, `partial=false`, SQLite integrity PASS; historical snapshot содержал 455 device cards и 696 snapshots. Эти числа не являются постоянными текущими counters.
- Цепочка `visitor_snapshots.log` → Alloy → Loki → Grafana ранее подтверждена с PASS. Production dashboard v40 сохранил UID `captive-portal-auth-v3-fixed`, содержит 104 панели и использует `client.ssid` для успешных snapshot-фильтров.
- CAPPORT изменения PR #35–#37 развёрнуты. Реальный Android captive-window live acceptance same-page revalidation на момент status report остаётся отдельным незакрытым gate.

## CAPPORT и frontend flow

Текущий путь:

    client discovery
    → bounded same-page fetch polling
    → общий PortalClientContext / portal entry flow
    → AuthSessionManager
    → AuthWorker

Discovery не создаёт отдельный authorization worker или provider. После разрешения client текущая страница переходит в существующий auth flow. Отображаемый progress монотонен между discovery/auth phases. После подтверждённого `AUTHORIZED` frontend один раз пытается закрыть captive window; при отсутствии redirect допускается максимум одна revalidation/reload текущей страницы, а marker в `sessionStorage` блокирует reload-loop.

## Journals и persistence

| Назначение | Default path | Тип |
|---|---|---|
| Authorization telemetry | `/opt/CaptivePortal/logs/auth_telemetry.log` | JSONL telemetry |
| Authorized snapshots | `/opt/CaptivePortal/logs/visitor_snapshots.log` | JSONL data journal |
| Raw Omada webhook | `/opt/CaptivePortal/logs/omada_webhook.log` | JSONL data journal |
| Normalized Omada webhook | `/opt/CaptivePortal/logs/omada_webhook_normalized.log` | JSONL data journal |
| Pending Cleaner audit | `/opt/CaptivePortal/logs/pending_session_cleaner.log` | rotating JSONL data journal |
| Portal counter | `/opt/CaptivePortal/data/portal_counter.db` | SQLite |
| Public traffic | `/opt/CaptivePortal/data/public_traffic.sqlite3` | SQLite |
| Visitor registry | `/opt/CaptivePortal/data/visitor_registry.sqlite3` | SQLite |

Cleaner не использует SQLite. Его cooldown/hourly action state находится в bounded process memory.

## Tests и tooling

- Основной и единственный test root: `tests/`.
- В runtime snapshot: 40 файлов `test_*.py`; 11 файлов и 53 test functions относятся к `tests/pending_sessions/`.
- Группы: auth/retry, CAPPORT/discovery/frontend, telemetry, counters, portal, Omada configuration/webhook, visitor registry и pending sessions.
- Временные pending-session probe scripts отсутствуют в main.
- `requirements.txt`: Flask, requests, tzdata; `requirements-dev.txt` добавляет pytest.
- `pytest.ini` фиксирует `testpaths = tests`.
- `.github/workflows` отсутствует; воспроизводимого GitHub CI release gate нет.

Последний известный historical green baseline — `894 passed, 10 skipped, 0 failed`, но он предшествует PR #34–#37. Для exact `main@ab776af` полный Linux pytest с `0 failed` не подтверждён. В среде TASK-KB-UPDATE-01 pytest отсутствует, поэтому release gate остаётся открытым; детали находятся в `docs/testing.md`.

## Fail-open boundaries

- auth telemetry;
- portal counter;
- public traffic service/worker;
- webhook receiver/normalizer journals;
- authorized snapshot collector;
- visitor registry;
- pending session cleaner.

Отказ независимого компонента не должен останавливать основной portal authorization flow. Для Cleaner неопределённость трактуется строже: reconnect запрещается.

## Token lifecycle

`OmadaProvider._get_token()` использует общий cache и condition; `_request_token_uncached()` выполняет реальный refresh. `_invalidate_cached_token(token)` очищает cache только если переданный использованный token всё ещё является текущим. Cleaner recovery после `-44112` не выполняет повторную безусловную invalidation, поэтому thread со старым ответом не очищает свежий token, опубликованный другим thread.

Новый provider, token manager или второй cache запрещён без отдельного TASK/ADR. Изменение lifecycle требует regression и concurrency tests для AuthWorker и Cleaner.

## Startup и shutdown

Startup в `run.py`:

1. settings и общий `OmadaProvider`;
2. snapshot collector creation;
3. Flask app и auth components;
4. Pending Session Cleaner creation/start;
5. snapshot collector start;
6. visitor registry create/start;
7. public traffic worker start;
8. Flask server.

Shutdown:

1. Pending Session Cleaner stop с bounded timeout;
2. public traffic worker;
3. auth executor;
4. snapshot collector stop-accepting/drain;
5. visitor registry final scan/stop.

## Repository hygiene

Current Git tree не содержит tracked `__pycache__`, `*.pyc`, `app/config.py.bak-*` или `app/web/web.py.bak-*`. `.gitignore` блокирует повторное добавление Python cache, local environment, logs, pytest cache и runtime database artifacts.

Cleanup выполнен PR #34, commit `96f7794`; это historical related change, а не current debt.

## Existing documentation

`README.md` и `README_RU.md` — public overview. `docs/README.md` — единая навигация. Модульные contracts являются текущими техническими источниками; прежние специализированные документы маршрутизируются по `docs/archive/migration-plan.md` и не удаляются автоматически.

## Подтверждённый deployment metadata

- Deployment path: `/opt/CaptivePortal`.
- Service: `captive-portal.service`.
- Systemd unit отсутствует в repository; точные `ExecStart`, user/group, EnvironmentFile и drop-ins проверяются на target host.
- Production environment не копируется в Git или handoff.

## Открытые риски и технический долг

### P0

1. Live acceptance same-page captive-window revalidation на реальном Android устройстве.
2. Полный Linux regression gate с `0 failed` на exact current main.

### P1

1. Post-restart verification Cleaner, Snapshot Collector и Visitor Registry после деплоя 2026-08-10.
2. Owner-controlled rotation старого Omada Client Secret, который остаётся в Git history.
3. TLS verification к Omada при repository default `VERIFY_SSL=false`.

### P2

1. GitHub CI отсутствует.
2. Нужен отдельный cleanup decision для legacy `/success` route/template.
3. Ownership `outputs/omada-webhook-normalized.alloy` не зафиксирован.

### Accepted limitation

Process-local AuthSession, retry guards, Cleaner action limits и workers рассчитаны на один application process. Multi-process/HA требует отдельного ADR для shared state и leader election/inter-process locking.
