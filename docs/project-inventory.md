# Инвентаризация CaptivPortal

Status: current runtime snapshot
Updated: 2026-08-04
Branch: main
Runtime commit: `227ebe93831447d16b78f277ee3052ddd06e15a3`
Commit date: 2026-08-04T09:38:50+04:00

Документ описывает runtime-код указанного commit. Knowledge-base PR добавляет только documentation, instructions, templates и test discovery config; production environment state отмечается отдельно и не выводится из Git.

## Runtime и composition

- Единственный прямой entrypoint и верхнеуровневый lifecycle: `run.py`.
- Flask composition factory: `app/web/web.py:create_app()`.
- Configuration pipeline: `app/config.py` → `app/settings.py:get_settings()`.
- Controller factory: `app/controllers/factory.py:create_controller()`.
- Реализация controller: `app/controllers/omada.py:OmadaProvider`.
- Pending-session API adapter: `app/controllers/omada_pending_sessions.py`; методы устанавливаются на тот же `OmadaProvider` в `app/controllers/__init__.py`.
- `run.py` создаёт один provider и передаёт его web/auth, snapshot collector и Pending Session Cleaner.
- `OmadaProvider` содержит единый thread-safe token cache на `Condition(RLock)` с одним concurrent refresh, early refresh и guarded invalidation.
- `AuthSessionManager` и `ThreadPoolExecutor(max_workers=4)` создаются один раз на process в `app/web/web.py`.
- In-memory sessions, locks, action limits и workers предполагают один application process.

## Подсистемы и реальные пути

| Подсистема | Код |
|---|---|
| Portal entry | `app/web/portal_entry.py`, `app/web/web.py` |
| AuthSession/AuthWorker | `app/auth/` |
| Omada provider | `app/controllers/omada.py`, `app/controllers/omada_pending_sessions.py` |
| CAPPORT | `app/capport/` |
| Auth telemetry | `app/auth_telemetry/` |
| Public Authorization Counter | `app/portal_counter/` |
| Completed-session traffic counter | `app/public_traffic/` |
| Authorized Client Snapshot Collector | `app/visitor_registry/snapshot_*` |
| Visitor Device Registry | `app/visitor_registry/registry_*` |
| Pending Client Session Cleaner | `app/pending_sessions/` |
| Omada Webhook Receiver/Normalizer | `app/integrations/omada/` |

## Feature flags по repository default

| Setting | Default | Интерпретация |
|---|---:|---|
| `CAPPORT_ENABLED` | true | реализован и включён конфигурацией |
| `PORTAL_COUNTER_ENABLED` | true | реализован и включён |
| `PUBLIC_TRAFFIC_COUNTER_ENABLED` | true | реализован и включён |
| `AUTH_TELEMETRY_ENABLED` | true | реализован и включён |
| `VISITOR_SNAPSHOT_ENABLED` | false | implemented-disabled |
| `VISITOR_REGISTRY_ENABLED` | false | implemented-disabled |
| `OMADA_WEBHOOK_ENABLED` | false | receiver/normalizer implemented-disabled |
| `PENDING_SESSION_CLEANER_ENABLED` | false | implemented-disabled by default |

Repository defaults не подтверждают process environment. Владелец проекта подтвердил production activation и работу Cleaner 2026-08-04; секреты и фактический EnvironmentFile в Git не фиксируются.

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
- В runtime snapshot: 38 `test_*.py`; 11 файлов и 52 test functions относятся к `tests/pending_sessions/`.
- Группы: auth/retry, CAPPORT, telemetry, counters, portal, Omada webhook, visitor registry и pending sessions.
- После PR #28 временные `omada_pending_cleanup_test.py` и `tools/pending_session_probe*` отсутствуют в main.
- Штатных test modules вне `tests/` нет.
- `requirements.txt`: Flask, requests, tzdata; `requirements-dev.txt` добавляет pytest.
- Knowledge-base PR добавляет `pytest.ini` с `testpaths = tests`, чтобы test root оставался явным и устойчивым.
- `pyproject.toml`, Makefile, setup.cfg, tox.ini, lint config и type-check config отсутствуют.

Integration environment 2026-08-04 не содержит runtime/dev packages и блокирует network install, поэтому pytest здесь не объявляется пройденным. `PYTHONPYCACHEPREFIX=/tmp/captivportal-pyc python -m compileall -q app` и `git diff --check` проходят; full suite обязателен в нормальном project environment.

## Fail-open boundaries

- auth telemetry;
- portal counter;
- public traffic service/worker;
- webhook receiver/normalizer journals;
- authorized snapshot collector;
- visitor registry;
- pending session cleaner.

Отказ независимого компонента не должен останавливать основной portal authorization flow. Для Cleaner неопределённость трактуется ещё строже: reconnect запрещается.

## Token lifecycle

Прежнее расхождение `token per request` vs Cleaner TASK разрешено merged implementation. `OmadaProvider._get_token()` использует общий cache и condition; `_request_token_uncached()` выполняет реальный refresh. `_invalidate_cached_token(token)` очищает cache только при совпадении, а вызов без аргумента очищает текущий cache без сравнения. Concurrency tests проверяют один refresh и отсутствие partial state после failure.

Новый provider, token manager или второй cache запрещён без отдельного TASK/ADR. Изменение текущего lifecycle требует regression и concurrency tests для AuthWorker и Cleaner.

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

## Existing documentation

`README.md` и `README_RU.md` — public overview. `docs/README.md` — единая навигация. Модульные contracts являются текущими техническими источниками; прежние специализированные документы маршрутизируются по `docs/archive/migration-plan.md` и не удаляются автоматически.

## Подтверждённый deployment metadata

- Deployment path `/opt/CaptivePortal` подтверждается repository docs.
- Service name `captive-portal.service` подтверждается repository docs.
- Systemd unit отсутствует в repository; точные `ExecStart`, user/group и EnvironmentFile проверяются на target host.
- Python не загружает `.env` автоматически; значения должны поступать через process environment.

## Риски и технический долг

1. В Git отслеживаются `__pycache__` и `.pyc`; обычный import может создавать шумный binary diff.
2. В Git отслеживаются backup-файлы `app/config.py.bak-*` и `app/web/web.py.bak-*`.
3. `outputs/omada-webhook-normalized.alloy` — infrastructure artifact; ownership подтверждается отдельным TASK.
4. GitHub commit `227ebe9` не имеет attached Actions workflow runs/status checks; test evidence хранится вне GitHub CI и требует повторяемого Linux gate.
5. В Cleaner token-expiry recovery после compare-and-invalidate выполняется дополнительная no-argument invalidation; concurrent refresh window и запрет очистки свежего AuthWorker token отдельным test не покрыты.
6. CAPPORT client discovery каждые две секунды выполняет полную навигацию через `window.location.replace()`; бесшовный переход на одной открытой странице через `fetch()` требует отдельного TASK. До следующего сбора долгов сохраняется текущая реализация и наблюдается её влияние на число неавторизованных пользователей.

Эти пункты не исправляются documentation TASK без отдельного разрешения.
