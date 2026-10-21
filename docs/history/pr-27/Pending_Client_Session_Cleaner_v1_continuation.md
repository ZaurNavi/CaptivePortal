# Pending Client Session Cleaner v1.0 — обязательные уточнения Tech Lead
## 1. Базовая ветка
Ждать merge Visitor Registry не нужно.
Cleaner создаётся от:
```text
review/visitor-device-registry-v1
commit: 2907b4d3a5f212b244525c45e30f6f7cc040a920
```
Новая ветка:
```text
feature/pending-client-session-cleaner-v1
```
Причина: Cleaner должен интегрироваться с актуальным `run.py`, Snapshot Collector и уже внедрённым, хотя пока выключенным, Visitor Registry.
Перед финальным PR:
```text
Visitor Registry merge в main
→ Cleaner rebase на свежий origin/main
→ полный regression suite
```
Разработку Cleaner начинаем сейчас, merge Registry не ожидаем.
---
## 2. Передача `AuthSessionManager`
Минимальная переработка wiring разрешена и обязательна.
Правильная схема:
```text
run.py
→ создаёт один AuthSessionManager
→ передаёт его в create_app()
→ тот же экземпляр передаёт PendingSessionProtection
→ тот же экземпляр использует AuthWorker
```
В одном процессе должен существовать ровно один рабочий экземпляр `AuthSessionManager`.
Рекомендуемый контракт:
```python
create_app(
    ...,
    auth_session_manager: AuthSessionManager | None = None,
)
```
Для production `run.py` всегда передаёт готовый экземпляр.
Для изолированных тестов `create_app()` может создать manager самостоятельно, если аргумент не передан.
Внутри Flask экземпляр хранить, например, в:
```python
app.extensions["auth_session_manager"]
```
Новый HTTP-контракт не создаётся. Поведение существующих routes не меняется.
---
## 3. Portal/CAPPORT activity
Создать отдельный protection timestamp:
```text
last_protection_activity_at
```
Ключ:
```text
site_id + canonical MAC
```
Этот timestamp:
* не изменяет `AuthSession.expires_at`;
* не продлевает TTL;
* не меняет retry-логику;
* используется только Cleaner protection adapter.
Activity обновляется только когда MAC клиента однозначно определён:
```text
создание или восстановление AuthSession через portal;
успешный /capport/login с определённым MAC;
успешный /capport/api после определения MAC;
запуск новой авторизации;
POST /auth/session/<session_id>/retry.
```
Обычный polling:
```text
GET /auth/session/<session_id>
```
**не обновляет** protection timestamp. Иначе автоматически открытая страница могла бы защищать старую сессию бессрочно.
Простое открытие `/` без однозначно установленного MAC также не создаёт protection activity.
Если CAPPORT API не смог определить MAC:
```text
защита конкретного MAC не устанавливается;
глобальная блокировка Cleaner не выполняется;
создаётся только безопасная operational telemetry.
```
---
## 4. Защищаемые состояния
Всегда защищаются, пока AuthSession существует и не истекла:
```text
WAITING
AUTHORIZING
VERIFYING
RESETTING
```
Также всегда защищает:
```text
любой незавершённый AuthRun;
выполняющийся authorization retry;
фактически работающий AuthWorker для site_id + MAC.
```
Состояния:
```text
FAILED с retryable=true
RESET
```
не защищают MAC бессрочно.
Они защищают только в пределах:
```text
PENDING_SESSION_CLEANER_PORTAL_GRACE_SECONDS=45
```
от последней явной portal/auth activity или перехода в это состояние.
`AUTHORIZED` защищает MAC только в пределах 45 секунд.
Время успешной авторизации брать из:
```text
последнего успешного AuthRun.finished_at
```
Если архитектуре нужен fallback, добавить отдельный точный:
```text
authorized_at
```
Не использовать общий `session.updated_at`, поскольку он может меняться по причинам, не связанным с авторизацией.
Текущий AuthWorker действительно использует состояния `WAITING`, `VERIFYING`, `RESETTING`, `RESET` и `FAILED`; Cleaner должен читать их через immutable adapter, не меняя worker.
---
## 5. Token cache
В Cleaner v1 **новый token cache не создаём**.
Текущий `OmadaProvider` получает новый Access Token для каждой операции и прямо обозначен как:
```text
dynamic token per request
```
Сохраняем существующее поведение:
```text
provider operation
→ _get_token()
→ один endpoint request
```
Следовательно, для v1 не нужны:
```text
expiresIn/expiresAt parsing;
fixed token TTL;
safety skew;
token generation;
CAS invalidation;
token cache condition;
token concurrency tests.
```
Это исключает лишнее изменение критического общего `OmadaProvider` и не меняет работу AuthWorker.
Из финального ТЗ удалить требования о создании и потокобезопасности token cache.
Особый `-44112` по-прежнему обрабатывается:
```text
получить новый token через существующий _get_token()
→ полный повторный preflight
→ protection checks
→ специальный второй POST.
```
---
## 6. Где выполняются GET retries
Provider-метод выполняет:
```text
один вызов _get_token()
+
ровно один целевой HTTP GET
```
Provider только:
* формирует URL;
* выполняет один запрос;
* валидирует ответ;
* классифицирует ошибку;
* возвращает `Result`.
Retry управляется Cleaner.
### List и preflight GET
Максимум три попытки:
```text
attempt 1 — сразу
attempt 2 — через 1 секунду
attempt 3 — через дополнительные 3 секунды
```
Cleaner проверяет между попытками:
```text
shutdown
scan budget
retryable/non-retryable classification
```
### Verification GET
В verification **не применять дополнительный цикл 1/3 секунды**.
Verification уже содержит две самостоятельные проверки:
```text
через 1 секунду — один GET;
через дополнительные 4 секунды — один GET.
```
Иначе три retries внутри каждой verification увеличили бы худшее время примерно до 40 секунд и нарушили бы shutdown timeout 20 секунд.
Таким образом:
```text
list/preflight → до трёх GET;
verification → ровно два GET всего.
```
При временной token-ошибке первый verification считается неоднозначным, а второй GET естественным образом получает новый token через `_get_token()`.
---
## 7. Изменение `totalRows`
Правило утверждается:
```text
totalRows первой успешно полученной страницы
является эталонным для всего scan.
```
Если на любой следующей странице:
```text
totalRows отличается;
получено строк больше эталона;
полученные pages невозможно согласовать с эталоном;
```
результат:
```text
inventory = partial
scan_result = partial
POST полностью запрещён для scan.
```
Повторяющийся MAC при стабильном `totalRows`:
```text
не делает весь inventory partial;
все строки этого MAC исключаются из action path;
duplicate_mac_count увеличивается один раз для MAC;
остальные уникальные клиенты могут обрабатываться.
```
---
## 8. Что считается отсутствием клиента при verification
В v1 не принимать непроверенные controller-коды.
`confirmed_disconnected` устанавливается только при валидном ответе exact-client GET:
```text
errorCode == 0
result является client object
active is False
```
Именно такое фактическое поведение уже подтверждено после `reconnect`: историческая карточка сохранилась, но получила `active=false`; клиент также исчез из active list.
В v1 **не считать подтверждением**:
```text
HTTP 404;
errorCode=-41011;
result=null;
отсутствующий result;
неизвестный controller errorCode;
malformed JSON;
timeout;
network error.
```
Такие ответы классифицируются как:
```text
verification_failed
```
или:
```text
ambiguous_unresolved
```
в зависимости от исходного POST outcome.
Если позднее реальный контроллер вернёт стабильный официальный код отсутствующей client session, он добавляется отдельным документированным изменением контракта.
---
## 9. Сравнение `apMac`
Сравнение выполняется после канонической нормализации MAC.
Правила:
```text
старый AP заполнен
новый AP заполнен
значения различаются
→ skipped_ap_changed
```
```text
старый AP заполнен
новый AP отсутствует
→ skipped_state_changed
```
Причина: свежая карточка потеряла ранее обязательный контекст, поэтому состояние сомнительно.
```text
старый AP отсутствует
новый AP заполнен
→ действие разрешено,
если все остальные условия полностью совпадают
```
Появившийся AP рассматривается как уточнение данных, а не доказанная смена сессии.
```text
оба AP отсутствуют
→ AP не участвует в сравнении
```
Невалидный `apMac` в preflight:
```text
skipped_state_changed
```
и POST запрещён.
---
## 10. Связь `action.planned` и `action.completed`
Да, допустимо событие:
```text
pending_session.action.completed
post_attempts=0
command_outcome=not_sent
```
без соответствующего `action.planned`.
Это относится к первоначальному кандидату, который дошёл до per-candidate safety pipeline, но был остановлен:
```text
local protection;
preflight;
session/AP/SSID change;
action limit;
cooldown;
hourly limit;
shutdown;
scan budget.
```
`action_id` создаётся в начале обработки первоначального кандидата и затем используется:
* в `action.completed` без POST;
* либо в паре `action.planned`/`action.completed`, если POST разрешён.
`action.planned` создаётся только непосредственно перед POST.
Если запись `action.planned` не удалась:
```text
POST запрещён;
operational error записывается;
audit_unavailable учитывается в scan counters;
Cleaner становится degraded.
```
Запись `action.completed` в тот же недоступный journal не является обязательной и не должна бесконечно повторяться.
---
## 11. Точный контракт scan counters
### `reconnect_attempted_count`
Количество уникальных `action_id`, для которых:
```text
post_attempts >= 1
```
Специальный второй POST после `-44112` остаётся одним logical action и увеличивает счётчик только на единицу.
### `reconnect_confirmed_count`
Включает:
```text
confirmed_disconnected
confirmed_new_session
ambiguous_confirmed_disconnected
ambiguous_confirmed_new_session
```
Не включает:
```text
client_now_authorized
ambiguous_client_now_authorized
```
поскольку завершение старой сессии не было подтверждено.
### `reconnect_unconfirmed_count`
Определяется централизованно:
```text
reconnect_attempted_count
-
reconnect_confirmed_count
```
Таким образом, сюда входят:
```text
client_now_authorized
ambiguous_client_now_authorized
reset_not_confirmed
verification_failed
ambiguous_unresolved
reconnect_rejected
```
### `action_error_count`
Увеличивается для:
```text
skipped_protection_check_failed
audit_unavailable
reconnect_rejected
reset_not_confirmed
verification_failed
ambiguous_unresolved
internal_error
journal completed-write failure
```
`client_now_authorized` ошибкой не считается.
### `rate_limited_count`
```text
cooldown_active
+
hourly_action_limit
```
### `action_limit_count`
Только:
```text
scan_action_limit
```
### `final_eligible_count`
Количество клиентов, которые:
```text
прошли preflight
+
прошли вторую protection check
+
сохранили eligibility
```
Считается до применения cooldown/hourly/scan action limit.
### `auth_status_counts`
Обязательное поле schema v1.
Содержит string keys:
```json
{
  "1": 11,
  "2": 21,
  "7": 1
}
```
Учитывает только валидные:
```text
active=true
wireless=true
```
строки.
---
## 12. Поля failed/partial scan
Использовать фиксированную схему.
Если первая страница не получена:
```json
{
  "pages_fetched": 0,
  "controller_total_rows": null,
  "clients_rows_received": 0
}
```
Все обязательные counters присутствуют и равны `0`.
В `action.completed` обязательные ключи присутствуют всегда.
Для неизвестных значений:
```text
null
```
Пример без POST:
```json
{
  "post_attempts": 0,
  "command_outcome": "not_sent",
  "controller_http_status": null,
  "controller_error_code": null,
  "controller_message": null,
  "verification_attempts": 0,
  "active_after": null,
  "auth_status_after": null,
  "uptime_after": null
}
```
Нельзя менять структуру события в зависимости от результата.
---
## 13. Bounded rate-limit cache
Утверждается:
```text
максимум 10 000 MAC;
ключ — site_id + canonical MAC;
для каждого MAC — timestamps фактически отправленных logical actions;
окно — 3600 секунд;
clock — time.monotonic();
доступ — thread-safe.
```
Перед каждой проверкой:
```text
истёкшие timestamps удаляются.
```
Для текущего лимита:
```text
не более трёх актуальных timestamps на MAC.
```
Если cache достиг 10 000 MAC:
1. Выполнить полную очистку истёкших записей.
2. Если место не появилось, новый MAC не добавлять.
3. POST запретить fail-closed.
4. Результат:
```text
internal_error
```
с безопасной operational-причиной:
```text
rate_limit_cache_capacity
```
Это не следует называть `hourly_action_limit`, потому что конкретный MAC свой лимит не превысил.
Особый второй POST после `-44112`:
```text
тот же action_id;
одна hourly-запись;
одна cooldown-запись;
один max-actions slot.
```
Учёт начинается при первом физически отправленном POST.
---
## 14. Scan budget после `action.planned`
После успешного `action.planned` и flush обязательно ещё раз проверить:
```text
shutdown
scan budget
Cleaner state
```
Если POST ещё не отправлен и начался shutdown:
```text
action.completed
post_attempts=0
command_outcome=not_sent
result=shutdown_started
```
Если истёк budget:
```text
action.completed
post_attempts=0
command_outcome=not_sent
result=scan_time_budget_exceeded
```
После фактической отправки POST:
```text
verification разрешено завершить,
даже если общий scan превысил 50 секунд.
```
Причина: outcome mutating-команды необходимо попытаться определить.
При этом:
```text
новые кандидаты не обрабатываются;
scan_result=partial;
verification ограничена собственными delays,
request timeout и shutdown deadline.
```
Перед специальным вторым POST после `-44112` заново выполнить:
```text
shutdown check;
scan budget check;
fresh client GET;
полную eligibility;
первую protection check;
вторую protection check;
journal availability check.
```
Не применять повторно к тому же logical action:
```text
cooldown;
hourly limit;
max-actions-per-scan.
```
Если второй POST запрещён shutdown или budget:
```text
post_attempts=1
command_outcome=token_expired
result=shutdown_started
```
либо:
```text
result=scan_time_budget_exceeded
```
---
## 15. Shutdown ordering
Public Traffic Worker не переносим без необходимости.
Минимально изменяем существующий shutdown:
```text
1. Pending Session Cleaner
2. Public Traffic Worker
3. Auth executor
4. Snapshot Collector
5. Visitor Registry
6. Остальные компоненты в существующем порядке
```
То есть утверждённый порядок:
```text
Cleaner
→ Public Traffic
→ Auth executor
→ Snapshot Collector
→ Visitor Registry
```
Причины:
* Cleaner первым запрещает новые reconnect;
* Public Traffic независим и уже останавливается до Auth executor;
* перенос Public Traffic после Registry не даёт преимущества;
* существующий порядок меняется минимально;
* Snapshot Collector обязательно дренируется после Auth executor;
* Registry обязательно выполняет final scan после Snapshot Collector.
Главный инвариант:
```text
после начала shutdown Cleaner не начинает новый POST.
```
---
# Итоговое решение
Все 15 вопросов закрыты.
Кодер может начинать реализацию:
```text
base:
2907b4d3a5f212b244525c45e30f6f7cc040a920
feature:
PENDING_SESSION_CLEANER_ENABLED=false
```
До следующего review:
```text
код писать можно;
локальные тесты выполнять можно;
commit не создавать;
push не выполнять;
production environment не менять;
systemd не менять;
Visitor Registry tests не возобновлять.
```
Основные изменения к финальному ТЗ:
1. Cleaner разрабатывается поверх Visitor Registry branch без ожидания merge.
2. `AuthSessionManager` передаётся через composition root.
3. Polling не продлевает protection grace.
4. `RESET` и `FAILED/retryable` защищаются только через grace.
5. Token cache в v1 полностью исключается.
6. Verification использует только два GET без вложенных retries.
7. Только `active=false` считается подтверждённым отключением.
8. Утверждена точная семантика counters.
9. Утверждён cache 10 000 MAC.
10. Public Traffic сохраняет существующую позицию shutdown.
