# TASK-DEBT-02 — Бесшовный переход CAPPORT из обнаружения клиента к авторизации

Статус: готово к передаче Coder  
Проект: CaptivPortal  
Закрываемый пункт реестра: `DEBT-001 — Бесшовный переход из ожидания к авторизации`  
Execution mode: `implementation`  
Исполнитель: Coder / coding agent  
Test responsibility: `agent`, полевой тест: `owner`  
Ожидаемая ветка: `fix/capport-seamless-discovery`

## 1. Цель

Убрать полную перезагрузку стартовой страницы во время ожидания появления телефона в Omada.

Один открытый экземпляр `portal.html` должен непрерывно пройти цепочку:

```text
DISCOVERING_CLIENT
→ fetch-проверки обнаружения клиента
→ однократное создание/получение AuthSession
→ получение session_id и initial_state
→ штатный опрос /auth/session/{session_id}
→ существующий authorization flow
```

Переход должен происходить без `location.replace()`, `location.reload()`, повторной загрузки HTML и замены документа.

## 2. Подтверждённый baseline

- Перед началом выполнить `git fetch origin --prune` и проверить актуальный `origin/main`.
- Baseline на момент выдачи TASK: `8007f43a591087a4f77f88b1ac70e744ce83ebf7`.
- Production работает на этом SHA.
- Файлы, относящиеся к текущему костылю, между `b1b81ee` и baseline по существу не менялись.
- Текущий механизм каждые две секунды вызывает `window.location.replace(discoveryRetryUrl)`.
- До обнаружения клиента `PortalEntryHandler.open_portal()` не вызывается, `AuthSession` и `AuthWorker` не создаются. Этот защитный контракт обязателен и не подлежит ослаблению.
- Если актуальный `origin/main` отличается от baseline, сравнить изменённые пути. При изменении allowed files или соответствующих контрактов остановиться и передать факты Tech Lead.

## 3. Текущее фактическое состояние

1. `GET /capport/login` выполняет `service.resolve_for_login(client_ip)`.
2. Если Omada ещё не видит клиента, сервер отдаёт HTML в режиме `CAPPORT_DISCOVERY`.
3. JavaScript ждёт две секунды и полностью открывает `discoveryRetryUrl` через `window.location.replace()`.
4. После новой загрузки сервер повторяет lookup.
5. Когда клиент найден, маршрут вызывает общий `PortalEntryHandler`, который создаёт или переиспользует `AuthSession`, запускает worker при необходимости и снова отдаёт полный HTML.
6. После истечения server-side deadline кнопка повторной попытки также выполняет полную навигацию.

## 4. Требуемое поведение

### 4.1. Первый запрос

- Обычный browser-запрос `GET /capport/login` сохраняет текущий HTML-контракт.
- Если клиент ещё не найден, `portal.html` открывается ровно один раз в режиме `CAPPORT_DISCOVERY`.
- До обнаружения клиента AuthSession/worker не создаются.
- Server-side deadline остаётся ограниченным максимум 60 секундами.

### 4.2. Discovery fetch

- Та же страница выполняет последовательные `fetch()`-запросы с `Accept: application/json` к URL, сформированному сервером.
- Одновременно разрешён только один discovery request; `setInterval` с наложением запросов запрещён. Следующий запрос планируется только после завершения предыдущего.
- Интервал по умолчанию остаётся 2000 мс.
- Cache должен быть отключён на клиенте и сервере.
- Пока клиент не найден, JSON обновляет countdown/discovery state, а текущий DOM остаётся открытым.
- Ни автоматическое ожидание, ни ручное «Повторить» не выполняют navigation/reload.

### 4.3. Переход к AuthSession

После обнаружения клиента сервер обязан через существующий `PortalEntryHandler` и общий `AuthSessionManager → AuthWorker` flow:

1. создать либо безопасно переиспользовать AuthSession;
2. запустить worker только для действительно новой сессии;
3. вернуть `session_id`, `redirect_url` и authoritative initial session state;
4. не отдавать новый HTML-документ.

Frontend обязан:

1. остановить discovery timers;
2. сохранить полученные `session_id` и `redirect_url` в runtime state;
3. переключить тот же DOM из `DISCOVERING_CLIENT` в полученное состояние;
4. если состояние активно — начать существующий опрос `/auth/session/{session_id}`;
5. если уже получен `AUTHORIZED` — применить существующую success-логику;
6. если получен `FAILED` — применить существующую retry/final UI-логику.

### 4.4. Ручной повтор discovery

- После истечения bounded deadline кнопка «Повторить» остаётся на той же странице.
- Кнопка запускает новый bounded discovery cycle через `fetch()` к server-provided restart URL.
- До нового обнаружения AuthSession не создаётся.
- Двойное нажатие и параллельные запросы блокируются.

### 4.5. Идемпотентность

- Потерянный JSON-ответ или повторный fetch после фактического создания сессии не должен запускать второй AuthWorker.
- Backend использует существующую семантику `create_or_get`; новый session manager, worker, provider или token lifecycle запрещены.
- После получения `session_id` discovery polling прекращается окончательно.

## 5. JSON-контракт `GET /capport/login`

JSON-режим выбирается только явным `Accept: application/json`. Обычный HTML-вход сохраняется.

### 5.1. Клиент ещё не найден — HTTP 200

Минимальный payload:

```json
{
  "mode": "CAPPORT_DISCOVERY",
  "state": "DISCOVERING_CLIENT",
  "status": "DISCOVERING_CLIENT",
  "progress": 5,
  "terminal": false,
  "retryable": true,
  "auto_retry": true,
  "remaining_seconds": 58,
  "retry_interval_ms": 2000,
  "retry_url": "/capport/login?...&wait_until=...",
  "restart_url": "/capport/login?..."
}
```

`retryable`/`auto_retry` после истечения deadline должны отражать остановленный автоматический цикл и доступность ручного повтора без создания AuthSession.

### 5.2. Клиент найден, auth flow подготовлен — HTTP 200

Минимальный payload:

```json
{
  "mode": "AUTH_SESSION",
  "session_id": "<uuid>",
  "redirect_url": null,
  "initial_state": {
    "state": "WAITING",
    "status": "WAITING",
    "progress": 0,
    "terminal": false
  }
}
```

`initial_state` является authoritative snapshot существующего `AuthSessionManager` и не конструируется на frontend.

### 5.3. Ошибки

- Client IP вне allowlist: HTTP 403, AuthSession/worker не создаются, polling останавливается.
- Временная ошибка lookup Omada: HTTP 503 JSON без HTML; текущий документ сохраняется, пользователь получает существующее сообщение о проблеме проверки, повтор разрешён в пределах deadline.
- Invalid client/context или ошибка подготовки сессии: controlled JSON 4xx/5xx без traceback и без нового HTML; если session уже создана, вернуть её authoritative failed snapshot и `session_id`.
- Все HTML и JSON ответы discovery/login: `Cache-Control: private, no-store` и `Pragma: no-cache`.
- Frontend проверяет HTTP status, JSON parse и обязательные поля до переключения режима.

## 6. Требуемый внутренний контракт PortalEntryHandler

Исключить дублирование логики создания сессии между HTML и JSON путями.

Разрешён минимальный refactor `PortalEntryHandler`:

- единая внутренняя операция подготавливает/переиспользует session, записывает portal counter/telemetry, запускает worker при необходимости и получает authoritative snapshot;
- HTML-ответ и JSON-ответ используют один и тот же результат этой операции;
- существующий `open_portal(context)` сохраняет текущее внешнее поведение для обычного HTML-входа;
- точное имя внутреннего result/dataclass/method выбирает Coder, но отдельная копия session/worker logic запрещена.

## 7. Out of scope — всё это не трогать

- установка или перенос EAP613;
- ротация Omada Client ID/Client Secret;
- `UX-001` и поведение страницы после успешной авторизации;
- существующий `window.location.replace(redirectUrl)` после `AUTHORIZED`;
- Visit Lifecycle, Visitor Admin Console и Visitor Analytics;
- Visitor Registry, Snapshot Collector и Pending Session Cleaner;
- уровни логов Visitor Registry;
- Grafana, Alloy, Loki;
- Omada controller configuration;
- production deployment/restart;
- исправление известных несвязанных падений тестов;
- общий frontend/backend refactor и изменение дизайна страницы.

## 8. Связанные документы

1. `docs/modules/capport.md`.
2. `docs/modules/portal-entry.md`.
3. `docs/agents/handoff.md`.

## 9. Разрешённые файлы

- `app/capport/routes.py`;
- `app/web/portal_entry.py` — только общий structured entry result без дублирования flow;
- `app/web/templates/portal.html` — только discovery/runtime transition;
- `tests/test_capport_routes.py`;
- `tests/test_portal_entry.py`;
- новый `tests/test_capport_discovery_frontend.py`;
- `tests/test_auth_retry_frontend.py` — только минимальная адаптация test harness к mutable runtime `sessionId`/`redirectUrl`; не исправлять отдельный retry debt;
- `docs/modules/capport.md`;
- `docs/modules/portal-entry.md` — только если внутренний handler contract реально изменён;
- сам TASK-файл при размещении в `docs/tasks/`.

Если нужен другой файл, остановить эту часть и запросить минимальное расширение scope у Tech Lead.

## 10. Запрещённые файлы и области

- `run.py`, `app/web/web.py`;
- `app/controllers/`, `app/auth/`, `app/auth_telemetry/`;
- `app/pending_sessions/`, `app/visitor_registry/`;
- config/settings/environment contracts;
- CSS, изображения, счётчики и тексты локализации, кроме доказанно необходимого существующего сообщения ошибки;
- SQLite/JSONL schemas;
- `requirements*.txt`, `.github/workflows/`;
- systemd, reverse proxy и production infrastructure.

## 11. Архитектурные ограничения

- Сохраняется единый `PortalClientContext → AuthSessionManager → AuthWorker` flow.
- Сохраняется один shared `OmadaProvider`.
- До обнаружения клиента AuthSession отсутствует.
- Frontend не генерирует `session_id` и не считает локальное состояние authoritative.
- Новый background thread, queue, websocket/SSE и новая зависимость запрещены.
- Новый public endpoint не требуется: использовать content negotiation существующего `GET /capport/login`, если фактический код не докажет stop condition.
- Existing auth-session status/retry API не меняются.
- Отдельный ADR не требуется, пока identity strategy, proxy trust и public URLs не меняются.

## 12. Fail-open / fail-closed

- Client authorization и allowlist работают fail-closed.
- Неопределённый клиент не получает AuthSession и не авторизуется.
- Временная network/controller ошибка discovery не разрушает открытый документ и не создаёт сессию; UI остаётся retryable в рамках bounded policy.
- Ошибка независимой telemetry/counter записи сохраняет существующее fail-open поведение и не должна блокировать основной auth flow.

## 13. Logging, events, persistence, lifecycle, security

- Существующие `capport.*` и auth telemetry events сохраняются; новые события не обязательны.
- Не дублировать `session_created`, `session_reused` и worker events.
- MAC в технических логах не маскировать.
- Не логировать credentials, Access Token, cookies или Authorization headers.
- Новая persistence и schema migration запрещены.
- Все timers останавливаются при переходе в auth mode, terminal discovery error и уходе страницы (`pagehide`/эквивалент, если это требуется текущей реализации).
- Query-параметры входного URL сохраняются так же, как сейчас; `wait_until` остаётся server-controlled/clamped.

## 14. Обязательные targeted tests

Backend минимум:

1. Первый HTML discovery response по-прежнему не создаёт session/worker.
2. JSON discovery response при `client_found=false` возвращает HTTP 200, bounded metadata и no-store headers; handler не вызывается.
3. Истёкший deadline останавливает auto-retry, но отдаёт restart contract для ручного fetch.
4. JSON response при найденном клиенте возвращает `session_id`, `redirect_url`, authoritative `initial_state` и входит в общий handler ровно один раз.
5. Повторная подготовка найденного клиента переиспользует одну session и не запускает второй worker.
6. Lookup failure возвращает controlled JSON 503 без HTML и не вызывает handler.
7. IP вне allowlist возвращает 403 и не вызывает handler.
8. Обычный HTML-вход при уже найденном клиенте сохраняет прежнее поведение.
9. Worker-start failure сохраняет controlled state и прежние telemetry semantics.

Frontend минимум, через существующий Node-подход:

1. Discovery polling выполняет fetch и не вызывает `location.replace/reload`.
2. Ответ `DISCOVERING_CLIENT` планирует следующий запрос только после завершения текущего.
3. Ответ `AUTH_SESSION` присваивает runtime `sessionId`, применяет `initial_state`, прекращает discovery и запускает существующий session polling.
4. Быстрый `AUTHORIZED` из discovery response вызывает существующую success-логику.
5. Ручное «Повторить» после deadline начинает новый fetch-cycle без navigation.
6. Двойное нажатие/медленный ответ не создают параллельные discovery fetch.
7. Потерянный/невалидный response не переключает режим на auth и не теряет текущий документ.
8. Auth retry UI продолжает использовать прежний `session_id`, `page_instance_id` и run-number contract; связанных регрессий нет.
9. `location.replace(redirectUrl)` после `AUTHORIZED` не удалён и не считается нарушением этого TASK.

Предпочтительная targeted command:

```bash
python -m pytest \
  tests/test_capport_routes.py \
  tests/test_portal_entry.py \
  tests/test_capport_discovery_frontend.py \
  -q --tb=short
```

Отдельно выполнить shared-template regression:

```bash
python -m pytest tests/test_auth_retry_frontend.py -q --tb=short
```

Если на baseline воспроизводится известное несвязанное падение `test_lost_retry_response_reconciles_active_run`, не исправлять его в этом TASK: привести baseline/after result и доказать отсутствие нового падения.

## 15. Full gate

```bash
python -m pytest -q -rs
PYTHONPYCACHEPREFIX=/tmp/captivportal-pyc \
  python -m compileall -q app
git diff --check
```

Full gate должен быть приведён с точными числами passed/skipped/failed. Если на baseline воспроизводятся известные несвязанные падения, TASK требует ноль новых failures относительно baseline; не исправлять их вне scope.

## 16. Acceptance criteria

TASK считается реализованным, если одновременно выполнено всё:

- один HTML-документ проходит discovery и входит в auth flow без reload/navigation;
- в discovery path нет вызова `location.replace()` или `location.reload()`;
- ручной discovery retry также работает через fetch в том же документе;
- до обнаружения клиента нет AuthSession/worker;
- после обнаружения возвращаются серверные `session_id` и authoritative state;
- session создаётся/переиспользуется общим handler, worker не дублируется;
- существующий `/auth/session/{session_id}` polling и auth retry продолжают работать;
- authorized redirect из отдельного `UX-001` не менялся;
- все новые targeted tests прошли;
- shared-template regression не получил новых failures;
- full gate не получил новых failures относительно подтверждённого baseline;
- `compileall` и `git diff --check` прошли;
- diff ограничен allowed files;
- телефон проходит реальный сценарий `подключение → ожидание Omada → авторизация` без видимой перезагрузки страницы.

Последний пункт выполняет владелец после review и отдельного deployment TASK.

## 17. Stop conditions

Остановить затронутую часть и передать Tech Lead точные факты, если:

- актуальный main изменил discovery/session contracts;
- для JSON-перехода требуется второй AuthSessionManager/worker/provider;
- невозможно получить authoritative `session_id` без изменения файла вне allowed scope;
- требуется изменение identity strategy, proxy trust, public URL или новый ADR;
- нужен новый endpoint из-за подтверждённого конфликта существующего content negotiation;
- требуется новый config/dependency/persistence/schema;
- full suite получает новое несвязанное падение;
- требуется production/controller/infrastructure action.

Независимые безопасные части продолжить.

## 18. Repository actions

Разрешено:

- создать ветку `fix/capport-seamless-discovery` от актуального `origin/main`;
- изменить только allowed files;
- выполнить tests/checks;
- создать один локальный commit после успешных проверок.

Рекомендуемый commit message:

```text
fix(capport): transition from discovery without page reload
```

Без отдельного разрешения владельца запрещено:

- push;
- PR;
- merge/rebase main;
- force-push/history rewrite;
- deploy/restart;
- изменение production или Omada Controller.

## 19. Handoff и PR requirements

Coder возвращает:

1. Цель и фактический результат.
2. Изменённые файлы и назначение каждого изменения.
3. Точный HTML/JSON/internal handler contract.
4. Подтверждение отсутствия второй session/worker/provider logic.
5. Targeted commands и точные `passed/skipped/failed`.
6. Shared-template regression result.
7. Full gate, `compileall`, `git diff --check`.
8. Baseline failures и новые failures раздельно.
9. Риски и невыполненные проверки.
10. Фактически выполненные repository actions и commit SHA, если создан.
11. Явное подтверждение, что push/PR/deploy/restart/controller changes не выполнялись.
12. `Agent execution summary` по `docs/agents/handoff.md`.

Для будущего PR:

- один focused commit;
- в описании явно указать `Closes DEBT-001`;
- отдельно перечислить backend contract, frontend state transition и tests;
- не заявлять production acceptance до полевого теста владельцем.
