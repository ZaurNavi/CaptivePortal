# Техническое задание
## Pending Client Session Cleaner v1.0
### Автоматическое завершение зависших неавторизованных клиентских сессий Omada
**Проект:** CaptivePortal
**Статус документа:** финальная редакция для Coder
**Целевая платформа:** Linux, single-process deployment
**Контроллер:** Omada Software Controller 5.14.31
---
# 1. Назначение
Реализовать внутри платформы `CaptivePortal` отдельный фоновый компонент:
```text
PendingClientSessionCleaner
```
Компонент должен:
1. Периодически получать полный список активных клиентов Omada.
2. Определять количество активных, авторизованных и неавторизованных клиентов.
3. Выявлять зависшие неавторизованные Wi-Fi-сессии.
4. Проверять, что CaptivePortal прямо сейчас не авторизует выбранного клиента.
5. Повторно получать актуальную карточку кандидата непосредственно перед действием.
6. При выполнении всех защитных условий отправлять команду:
```http
POST /openapi/v1/{omadacId}/sites/{siteId}/clients/{clientMac}/reconnect
```
7. Проверять фактический результат команды.
8. Вести постоянный JSONL-аудит scans и reconnect.
9. Формировать данные, пригодные:
   * для временного Grafana dashboard;
   * для будущего собственного Admin Console;
   * для внутренней аналитики CaptivePortal без зависимости от Loki.
---
# 2. Положение в дорожной карте
На время разработки Cleaner состояние предыдущего этапа фиксируется следующим образом:
```text
Visitor Device Registry:
код загружен на Linux-сервер;
VISITOR_REGISTRY_ENABLED=false;
Linux gate временно приостановлен;
production activation не выполняется.
```
Последовательность работ:
```text
Pending Client Session Cleaner
→ реализация
→ ревью
→ Linux gate
→ включение
→ живая проверка
→ возврат к Visitor Device Registry
```
Cleaner является отдельным operational-модулем и не входит в Visitor Device Registry.
---
# 3. Подтверждённая проблема
Клиент может:
1. Подключиться к открытому Wi-Fi.
2. Создать активную клиентскую сессию Omada.
3. Не завершить Captive Portal-авторизацию.
4. Остаться в состоянии:
```text
active = true
authStatus = 1
```
5. Существовать в таком состоянии около 20–30 минут.
Цель Cleaner:
```text
Закрывать такие сессии примерно через 2–3 минуты,
не затрагивая успешно авторизованных клиентов.
```
При параметрах:
```text
scan interval = 60 секунд
pending threshold = 120 секунд
```
кандидат обычно будет обработан при возрасте сессии от 120 до 180 секунд.
---
# 4. Подтверждённый механизм Omada
## 4.1. Получение активных клиентов
```http
GET /openapi/v1/{omadacId}/sites/{siteId}/clients
```
## 4.2. Получение свежей карточки кандидата
```http
GET /openapi/v1/{omadacId}/sites/{siteId}/clients/{clientMac}
```
## 4.3. Завершение текущей сессии
```http
POST /openapi/v1/{omadacId}/sites/{siteId}/clients/{clientMac}/reconnect
```
Успешный ответ:
```json
{
  "errorCode": 0,
  "msg": "Success."
}
```
Фактически проверенное поведение команды:
* текущая Wi-Fi-ассоциация разрывается;
* активная клиентская сессия закрывается;
* клиент становится `active=false`;
* клиент исчезает из списка активных клиентов;
* MAC не блокируется;
* историческая карточка клиента сохраняется;
* телефон может позднее подключиться снова.
---
# 5. Запрещённые альтернативы
В Cleaner v1 запрещено использовать:
```text
POST /clients/{clientMac}/disconnect
DELETE /clients/{clientMac}
POST /hotspot/clients/{clientMac}/unauth
POST /clients/{clientMac}/block
POST /clients/{clientMac}/unblock
POST /devices/{deviceMac}/forget
```
Причины:
* `disconnect` отсутствует в Omada 5.14.31;
* endpoint удаления клиента отсутствует;
* `unauth` предназначен для отмены существующей авторизации;
* `block` запрещает клиенту повторное подключение;
* `forget` относится к AP, switch и gateway, а не к Wi-Fi-клиентам.
`block/unblock` не должен применяться как автоматический fallback.
---
# 6. Feature flag
Cleaner должен иметь только один feature flag:
```env
PENDING_SESSION_CLEANER_ENABLED=false
```
Семантика:
```text
false
→ Cleaner полностью выключен;
→ worker не создаётся;
→ Omada не опрашивается;
→ JSONL journal не обязан создаваться;
→ POST reconnect невозможен.
```
```text
true
→ Cleaner полностью включён;
→ worker выполняет scans;
→ кандидаты классифицируются;
→ reconnect выполняется при прохождении всех защит.
```
В Cleaner v1 не должно быть:
```text
DRY_RUN
observation mode
would_reset
mutations_allowed
observing state
```
Модуль либо выключен, либо работает полностью.
---
# 7. Состояния компонента
Поддерживаются состояния:
```text
disabled
starting
active
degraded
unavailable
stopping
```
Переходы:
```text
ENABLED=false
→ disabled
```
```text
ENABLED=true
→ starting
→ active
```
```text
временная ошибка Omada или journal
→ degraded
```
```text
восстановление
→ active
```
```text
невалидная конфигурация
→ unavailable
```
```text
общий shutdown
→ stopping
```
Состояния должны использоваться одинаково:
* worker;
* operational telemetry;
* health/status service в будущем.
---
# 8. Fail-open
Обязательный инвариант:
```text
Pending Session Cleaner failure
must not become CaptivePortal failure.
```
Ошибка Cleaner не должна:
* останавливать CaptivePortal;
* отменять успешную авторизацию;
* изменять `AuthSession`;
* изменять `AuthRun`;
* запускать authorization retry;
* менять CAPPORT;
* менять frontend;
* останавливать Snapshot Collector;
* менять Visitor Registry;
* показываться посетителю.
Безопасное правило:
```text
При любом сомнении клиента не отключать.
```
---
# 9. Общая архитектура
```text
PendingSessionWorker
        ↓
OmadaProvider.list_active_clients()
        ↓
валидация pagination
        ↓
PendingSessionClassifier
        ↓
первоначальные кандидаты
        ↓
PendingSessionProtection.check()
        ↓
OmadaProvider.get_pending_client_state()
        ↓
повторная eligibility classification
        ↓
PendingSessionProtection.check()
        ↓
ActionGuard
        ↓
action.planned + flush
        ↓
OmadaProvider.reconnect_client()
        ↓
verification
        ↓
action.completed
        ↓
scan.completed
```
Cleaner использует существующие:
* `OmadaProvider`;
* OAuth `client_credentials`;
* `_get_token()`;
* controller URL;
* TLS-настройки;
* `CAPPORT_SITE_ID`;
* MAC normalization;
* `AuthSessionManager`;
* `AuthorizationTelemetry`;
* composition root в `run.py`.
Новый OAuth client и новый token manager не создаются.
---
# 10. Планирование scans
Использовать fixed-delay scheduling:
```text
scan завершился
→ ожидание configured interval
→ новый scan
```
Не использовать fixed-rate scheduling, при котором новый scan может начаться до завершения предыдущего.
Настройки:
```env
PENDING_SESSION_CLEANER_INITIAL_DELAY_SECONDS=10
PENDING_SESSION_CLEANER_SCAN_INTERVAL_SECONDS=60
PENDING_SESSION_CLEANER_MAX_SCAN_DURATION_SECONDS=50
```
Первый scan начинается через 10 секунд после запуска worker.
---
# 11. Запрет параллельных scans
Одновременно разрешён только один scan.
Использовать non-blocking lock.
Если scan уже выполняется:
* новый scan не запускается;
* POST не выполняется;
* создаётся debug operational event:
```text
pending_session_cleaner_scan_overlap_suppressed
```
Отдельный data event для пропущенного scheduler tick не требуется.
---
# 12. Ограничение продолжительности scan
Максимальная soft duration:
```text
50 секунд
```
Перед началом обработки каждого следующего кандидата необходимо проверить:
* elapsed monotonic time;
* shutdown event;
* оставшийся scan budget.
При исчерпании бюджета:
* новые preflight и POST не начинать;
* оставшихся первоначальных кандидатов учитывать как:
```text
scan_time_budget_exceeded
```
* итог scan:
```text
scan_result = partial
```
Уже начавшийся HTTP request завершается через request timeout.
---
# 13. Provider protocol
Добавить узкий protocol:
```python
class PendingClientSessionProvider(Protocol):
    def list_active_clients(
        self,
        *,
        site_id: str,
        page: int,
        page_size: int,
        timeout_seconds: float,
    ) -> Result:
        ...
    def get_pending_client_state(
        self,
        *,
        site_id: str,
        client_mac: str,
        timeout_seconds: float,
    ) -> Result:
        ...
    def reconnect_client(
        self,
        *,
        site_id: str,
        client_mac: str,
        timeout_seconds: float,
    ) -> Result:
        ...
```
Реализация добавляется в существующий `OmadaProvider`.
Существующие публичные контракты AuthWorker не менять.
---
# 14. `list_active_clients()`
Endpoint:
```http
GET /openapi/v1/{omadacId}/sites/{siteId}/clients?page={page}&pageSize={pageSize}
```
Успешный внутренний результат:
```python
{
    "http_status": 200,
    "error_code": 0,
    "message": "Success.",
    "page": 1,
    "page_size": 500,
    "total_rows": 32,
    "clients": [...]
}
```
Требования:
* HTTP status проверяется отдельно;
* JSON root должен быть object;
* `errorCode` должен быть integer;
* `result` должен быть object;
* `result.data` должен быть array;
* `result.totalRows` должен быть integer `>= 0`;
* Python `bool` не считается integer;
* список возвращается defensive copy;
* token и HTTP headers наружу не возвращаются.
---
# 15. `get_pending_client_state()`
Endpoint:
```http
GET /openapi/v1/{omadacId}/sites/{siteId}/clients/{clientMac}
```
Формат MAC в endpoint:
```text
AA-BB-CC-DD-EE-FF
```
Внутренний формат:
```text
AA:BB:CC:DD:EE:FF
```
Использовать существующую общую MAC-утилиту.
Успешный результат:
```python
{
    "http_status": 200,
    "error_code": 0,
    "message": "Success.",
    "client": {...}
}
```
`client` возвращается defensive copy.
---
# 16. `reconnect_client()`
Endpoint:
```http
POST /openapi/v1/{omadacId}/sites/{siteId}/clients/{clientMac}/reconnect
```
Успешный результат:
```python
{
    "http_status": 200,
    "error_code": 0,
    "message": "Success.",
    "command_accepted": True
}
```
В result запрещено возвращать:
* Access Token;
* Authorization header;
* cookie;
* Client Secret;
* полный raw response.
---
# 17. Приоритет классификации ответа Omada
Для каждого provider-метода:
```text
transport exception
→ HTTP status
→ JSON validity и root type
→ errorCode
→ endpoint-specific result validation
```
HTTP 200 сам по себе не считается успехом.
---
# 18. GET retry
Для list, preflight и verification GET разрешено максимум три попытки:
```text
Attempt 1 — немедленно
Attempt 2 — через 1 секунду
Attempt 3 — через 3 секунды
```
Настройка:
```env
PENDING_SESSION_CLEANER_GET_RETRY_DELAYS_SECONDS=1,3
```
Retryable:
```text
timeout
connection error
HTTP 408
HTTP 429
HTTP 5xx
malformed JSON
malformed response object
temporary token error
```
Non-retryable:
```text
invalid MAC
missing site ID
HTTP 400
HTTP 403
другой постоянный HTTP 4xx
неизвестный постоянный controller errorCode
```
Retry прекращается при:
* shutdown;
* исчерпании scan time budget;
* non-retryable error.
---
# 19. Потокобезопасность общего OmadaProvider
Cleaner и AuthWorker используют один экземпляр `OmadaProvider`.
Обязательно обеспечить thread safety token cache.
Требования:
1. Чтение и обновление cached token выполняются атомарно.
2. Одновременно token обновляет не более одного thread.
3. Остальные threads не получают частично обновлённое состояние.
4. Cleaner не очищает рабочий token AuthWorker.
5. Ошибка refresh не повреждает cache.
6. Успешный refresh атомарно заменяет:
   * access token;
   * expiry;
   * связанные token metadata.
7. Публичные контракты AuthWorker не изменяются.
При необходимости добавить внутренний lock или condition в существующий provider.
Новый token manager создавать запрещено.
Обязательны concurrency tests:
* одновременный `_get_token()` от AuthWorker и Cleaner;
* один фактический refresh;
* успешное ожидание второго thread;
* refresh failure;
* отсутствие частичного token state.
---
# 20. Pagination
Настройки:
```env
PENDING_SESSION_CLEANER_PAGE_SIZE=500
PENDING_SESSION_CLEANER_MAX_PAGES=20
PENDING_SESSION_CLEANER_MAX_CLIENTS=10000
```
Алгоритм:
1. Начать с `page=1`.
2. Получить и проверить страницу.
3. Добавить `result.data`.
4. Продолжить, пока:
   * получены не все `totalRows`;
   * текущая data не пуста;
   * текущая data не короче `pageSize`;
   * не достигнут `MAX_PAGES`;
   * не достигнут `MAX_CLIENTS`.
5. После каждой страницы проверять shutdown и scan budget.
---
# 21. Неполный inventory
Inventory считается неполным, если:
* не удалось получить любую необходимую страницу;
* достигнут `MAX_PAGES` до получения всех строк;
* достигнут `MAX_CLIENTS`;
* `totalRows` невозможно согласовать с полученными данными;
* scan остановлен во время pagination;
* response page malformed.
В этом случае:
```text
scan_result = partial
```
и:
```text
POST reconnect запрещён для всего scan.
```
Уже полученные записи можно классифицировать только для scan summary.
Cleaner не должен выполнять reconnect на основании неполного списка активных клиентов.
---
# 22. Повторяющийся MAC
Внутри одного scan один канонический MAC должен соответствовать одной active row.
Если один MAC встречается более одного раза:
* все строки этого MAC исключаются из action path;
* одна строка не выбирается произвольно;
* увеличивается:
```text
duplicate_mac_count
```
Отдельный action event не создаётся.
---
# 23. Строгие типы клиентской карточки
Не выполнять неявное преобразование типов.
Python `bool` не считается integer.
| Поле         | Допустимый тип          |
| ------------ | ----------------------- |
| `mac`        | корректный string MAC   |
| `wireless`   | boolean                 |
| `active`     | boolean                 |
| `authStatus` | integer, не bool        |
| `uptime`     | integer `>= 0`, не bool |
| `ssid`       | непустая string         |
| `blocked`    | boolean или отсутствует |
| `ip`         | string или null         |
| `apMac`      | корректный MAC или null |
| `radioId`    | integer или null        |
| `channel`    | integer или null        |
| `rssi`       | integer или null        |
| `snr`        | integer или null        |
Некорректная обязательная карточка:
* не становится кандидатом;
* увеличивает `clients_invalid`;
* не создаёт отдельный action event.
---
# 24. Семантика `authStatus`
Для Cleaner v1 разрешены действия только при точном:
```text
authStatus == 1
```
Подтверждённая интерпретация:
```text
authStatus == 1
→ клиент не прошёл Captive Portal-авторизацию
```
```text
authStatus == 2
→ клиент авторизован
```
Любое другое значение:
* не получает бизнес-интерпретацию;
* не допускается к reconnect;
* учитывается в:
```text
unknown_auth_status_count
```
---
# 25. SSID allowlist
Настройка:
```env
PENDING_SESSION_CLEANER_SSIDS=Zefer_Parki
```
Правила:
* CSV;
* trimming пробелов;
* пустые элементы запрещены;
* сравнение exact;
* сравнение case-sensitive.
В Cleaner v1 целевой SSID:
```text
Zefer_Parki
```
`Welcome` не включать.
При пустом allowlist и `ENABLED=true`:
```text
Cleaner → unavailable
```
---
# 26. Первоначальная eligibility classification
Клиент становится первоначальным кандидатом только при одновременном выполнении:
```text
wireless is True
active is True
authStatus == 1
blocked is not True
uptime >= MIN_UPTIME_SECONDS
ssid входит в allowlist
MAC корректен
карточка имеет допустимые типы
MAC не дублируется в inventory
```
Порог:
```env
PENDING_SESSION_CLEANER_MIN_UPTIME_SECONDS=120
```
Кандидаты сортируются:
```text
uptime DESC
mac ASC
```
---
# 27. Первоначальные classification counters
Обычные клиенты не должны создавать отдельные action events.
Только scan summary учитывает:
```text
clients_rows_received
clients_valid
clients_invalid
duplicate_mac_count
wireless_active_count
wired_or_non_wireless_count
authorized_active_count
unauthorized_active_count
unknown_auth_status_count
below_threshold_count
ssid_not_allowed_count
blocked_count
initial_candidate_count
```
---
# 28. Local Auth Protection
Добавить read-only protocol:
```python
class PendingSessionProtection(Protocol):
    def check(
        self,
        *,
        site_id: str,
        client_mac: str,
        now: datetime,
        grace_seconds: float,
    ) -> ProtectionDecision:
        ...
```
Результат immutable:
```python
ProtectionDecision(
    protected=True,
    reason="active_auth_run",
    observed_at=...,
)
```
Adapter:
* thread-safe;
* не отдаёт mutable `AuthSession`;
* не отдаёт mutable `AuthRun`;
* не изменяет состояние авторизации;
* возвращает только immutable snapshot решения.
---
# 29. Условия local protection
Клиент защищается, если для того же:
```text
site_id + canonical MAC
```
выполняется хотя бы одно условие:
* AuthWorker прямо сейчас обрабатывает клиента;
* существует незавершённый AuthRun;
* выполняется authorization retry;
* сессия находится в переходном состоянии;
* последняя portal/CAPPORT activity моложе grace window;
* состояние `AUTHORIZED` было зафиксировано моложе grace window.
Настройка:
```env
PENDING_SESSION_CLEANER_PORTAL_GRACE_SECONDS=45
```
Старая завершённая `AUTHORIZED`-сессия старше 45 секунд не должна защищать MAC бессрочно.
При любой ошибке adapter:
```text
protected = true
reason = protection_check_failed
```
Reconnect запрещается.
---
# 30. Двойная local protection
Protection check выполняется дважды:
## Первая проверка
После первоначальной eligibility classification, до preflight GET.
## Вторая проверка
После успешного preflight GET, непосредственно перед audit/action guard.
Если между проверками началась авторизация:
```text
result = skipped_local_state_changed
```
POST не выполняется.
Главный safety-инвариант:
> Cleaner отправляет reconnect только после совпадения первоначального списка Omada, свежего preflight GET и двух успешных local protection checks.
---
# 31. Preflight GET
Для каждого первоначального кандидата выполнить свежий:
```http
GET /clients/{clientMac}
```
После GET повторно проверить:
```text
MAC совпадает
wireless is True
active is True
authStatus == 1
blocked is not True
uptime >= threshold
SSID остаётся разрешённым
session не была заменена
AP не изменилась
local protection отсутствует
```
---
# 32. Защита от смены сессии
Настройка:
```env
PENDING_SESSION_CLEANER_UPTIME_REGRESSION_TOLERANCE_SECONDS=5
```
Если:
```text
preflight_uptime + 5 < list_uptime
```
текущая сессия считается заменённой новой.
Результат:
```text
skipped_session_replaced
```
В текущем scan новый reconnect запрещён.
---
# 33. Изменение SSID и AP
Если между initial list и preflight изменился SSID:
```text
skipped_ssid_changed
```
Если изменился непустой `apMac`:
```text
skipped_ap_changed
```
Cleaner не пытается определить, был ли это roaming или новая сессия.
Клиент будет заново оценён в следующем scan.
Изменение IP само по себе не запрещает действие, но значения до и после сохраняются в action event.
---
# 34. Action Guard
До отправки POST проверить:
* Cleaner не находится в `stopping`;
* scan inventory полный;
* scan time budget не исчерпан;
* journal доступен;
* не достигнут max actions per scan;
* не действует cooldown;
* не достигнут hourly per-MAC limit.
---
# 35. Максимум действий за scan
Для Cleaner v1:
```env
PENDING_SESSION_CLEANER_MAX_ACTIONS_PER_SCAN=1
```
Это production default.
Значение может быть увеличено оператором позже без изменения кода.
После достижения лимита остальные первоначальные кандидаты, дошедшие до action guard, получают:
```text
scan_action_limit
```
Для них создаётся `action.completed`.
---
# 36. Cooldown
Настройка:
```env
PENDING_SESSION_CLEANER_ACTION_COOLDOWN_SECONDS=180
```
После фактической отправки POST reconnect следующий POST для этого MAC запрещён на 180 секунд.
Cooldown фиксируется в момент отправки POST, а не после подтверждённого успеха.
Он применяется при любом результате отправленного POST:
```text
accepted
timeout
network error
HTTP 5xx
ambiguous response
```
---
# 37. Hourly per-MAC limit
Настройка:
```env
PENDING_SESSION_CLEANER_MAX_ACTIONS_PER_MAC_PER_HOUR=3
```
Лимит фиксируется в момент фактической отправки POST.
В Cleaner v1 допускается bounded in-memory storage.
Требования:
* ограниченный размер cache;
* удаление истёкших записей;
* thread-safe доступ;
* после restart cache начинается заново;
* ограничение должно быть явно описано в документации.
Результат превышения:
```text
hourly_action_limit
```
---
# 38. Audit-before-action
Reconnect запрещён без предварительной постоянной audit-записи.
Точный порядок:
```text
1. Сгенерировать action_id.
2. Сформировать pending_session.action.planned.
3. Записать action.planned в JSONL.
4. Выполнить flush.
5. Зафиксировать monotonic start.
6. Зафиксировать cooldown/hourly attempt в момент отправки POST.
7. Отправить POST reconnect.
8. Выполнить verification.
9. Записать action.completed.
```
Если `action.planned` не удалось записать или flush:
```text
result = audit_unavailable
POST не выполняется
Cleaner → degraded
```
---
# 39. Политика POST reconnect
Обычный action допускает максимум один POST.
Слепой retry запрещён.
Если POST завершился:
* timeout;
* network error;
* HTTP 408;
* HTTP 429;
* HTTP 5xx;
* malformed JSON;
* malformed response,
результат команды считается:
```text
ambiguous
```
После этого выполняется verification.
Второй POST не отправляется.
---
# 40. Особый token recovery
Разрешён только один особый повтор POST, если controller вернул точный:
```text
errorCode = -44112
```
Алгоритм:
```text
token-expired response
→ получить новый token
→ свежий GET клиента
→ первая local protection check
→ полная eligibility validation
→ вторая local protection check
→ один новый POST
```
Общий предел:
```text
обычно максимум один POST;
при точном -44112 максимум два POST.
```
Особый второй POST:
* входит в тот же `action_id`;
* не создаёт второй `action.planned`;
* отображается как `post_attempts=2`;
* не считается отдельным action для max-actions-per-scan;
* cooldown начинается с первого фактически отправленного POST.
Timeout, network error и HTTP 5xx не разрешают второй POST.
---
# 41. Verification
Настройки:
```env
PENDING_SESSION_CLEANER_VERIFY_DELAYS_SECONDS=1,4
PENDING_SESSION_CLEANER_REQUEST_TIMEOUT_SECONDS=5
```
`4` — дополнительная задержка после первой проверки.
Алгоритм:
1. После POST подождать 1 секунду через interruptible wait.
2. Выполнить client GET.
3. Если получен окончательный результат — завершить.
4. Если результат неоднозначен — подождать ещё 4 секунды.
5. Выполнить второй client GET.
6. Повторный POST не выполнять.
Худший расчёт verification:
```text
1 + 5 + 4 + 5 = 15 секунд
```
---
# 42. Результаты verification
## 42.1. Клиент отключён
Если:
```text
active == false
```
или активная client session отсутствует:
```text
confirmed_disconnected
```
## 42.2. Создана новая сессия
Если:
```text
active == true
authStatus == 1
uptime_after + tolerance < uptime_before
```
результат:
```text
confirmed_new_session
```
Это означает, что старая сессия закрыта, а телефон переподключился.
## 42.3. Клиент стал авторизован
Если:
```text
active == true
authStatus == 2
```
результат:
```text
client_now_authorized
```
Новые действия запрещены.
## 42.4. Старая сессия осталась
Если:
```text
active == true
authStatus == 1
uptime продолжает увеличиваться
```
результат:
```text
reset_not_confirmed
```
## 42.5. Verification недоступна
Если обе verification GET не дали пригодного результата:
```text
verification_failed
```
---
# 43. Результаты ambiguous POST
Если POST имел ambiguous outcome, использовать отдельные результаты:
```text
ambiguous_confirmed_disconnected
ambiguous_confirmed_new_session
ambiguous_client_now_authorized
ambiguous_unresolved
```
Это позволяет отличать:
* подтверждённый ответ `errorCode=0`;
* действие с потерянным или неоднозначным ответом.
---
