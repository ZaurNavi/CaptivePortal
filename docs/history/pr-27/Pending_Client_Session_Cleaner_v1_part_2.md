# 44. Data journal
Путь:
```env
PENDING_SESSION_CLEANER_LOG_FILE=/opt/CaptivePortal/logs/pending_session_cleaner.log
```
Data journal содержит только:
```text
pending_session.scan.completed
pending_session.action.planned
pending_session.action.completed
```
Operational telemetry в этот файл не помещается.
---
# 45. Правило создания action events
Отдельный `action.completed` не создаётся для обычных строк, исключённых первоначальной classification:
```text
ниже threshold
другой SSID
авторизован
не wireless
blocked
неизвестный authStatus
невалидная карточка
duplicate MAC row
```
Они учитываются только в `scan.completed`.
`action.completed` создаётся только для клиента, который:
1. Прошёл первоначальную eligibility classification.
2. Дошёл минимум до:
   * local protection;
   * preflight;
   * action guard;
   * POST/verification.
---
# 46. Список action results
Допустимые значения:
```text
skipped_local_auth_active
skipped_recent_portal_activity
skipped_protection_check_failed
skipped_local_state_changed
skipped_state_changed
skipped_inactive
skipped_authorized
skipped_session_replaced
skipped_ssid_changed
skipped_ap_changed
cooldown_active
hourly_action_limit
scan_action_limit
scan_time_budget_exceeded
audit_unavailable
shutdown_started
confirmed_disconnected
confirmed_new_session
client_now_authorized
ambiguous_confirmed_disconnected
ambiguous_confirmed_new_session
ambiguous_client_now_authorized
ambiguous_unresolved
reconnect_rejected
reset_not_confirmed
verification_failed
internal_error
```
Новые значения после выпуска `schema_version=1` добавляются только с документированным изменением контракта.
---
# 47. Общие требования к data events
Каждая запись:
* `schema_version=1`;
* compact JSON;
* strict JSON;
* одна запись на строку;
* UTF-8;
* `allow_nan=false`;
* UTC timestamp:
```text
YYYY-MM-DDTHH:MM:SS.mmmZ
```
Запрещено сохранять:
* Access Token;
* Client Secret;
* Authorization header;
* cookie;
* пароль SSID;
* полный raw response;
* traceback с секретами.
MAC сохраняется полностью.
---
# 48. `pending_session.action.planned`
Пример:
```json
{
  "schema_version": 1,
  "event": "pending_session.action.planned",
  "action_id": "uuid",
  "scan_id": "uuid",
  "planned_at": "2026-07-30T18:20:02.000Z",
  "site_id": "6a64f17630da7c70d232187a",
  "client_mac": "FA:D5:62:D4:EB:25",
  "client_ip": "192.168.1.164",
  "ssid": "Zefer_Parki",
  "ap_mac": "EC:75:0C:18:6F:F8",
  "radio_id": 0,
  "auth_status_before": 1,
  "active_before": true,
  "uptime_before": 224,
  "list_uptime": 221,
  "local_protection": false,
  "action": "reconnect"
}
```
Запись должна быть физически отправлена handler и flush до POST.
---
# 49. `pending_session.action.completed`
Пример:
```json
{
  "schema_version": 1,
  "event": "pending_session.action.completed",
  "action_id": "uuid",
  "scan_id": "uuid",
  "finished_at": "2026-07-30T18:20:04.381Z",
  "duration_ms": 2381,
  "site_id": "6a64f17630da7c70d232187a",
  "client_mac": "FA:D5:62:D4:EB:25",
  "client_ip_before": "192.168.1.164",
  "client_ip_after": null,
  "ssid_before": "Zefer_Parki",
  "ssid_after": null,
  "ap_mac_before": "EC:75:0C:18:6F:F8",
  "ap_mac_after": null,
  "auth_status_before": 1,
  "auth_status_after": null,
  "active_before": true,
  "active_after": false,
  "uptime_before": 224,
  "uptime_after": null,
  "action": "reconnect",
  "post_attempts": 1,
  "command_outcome": "accepted",
  "controller_http_status": 200,
  "controller_error_code": 0,
  "controller_message": "Success.",
  "verification_attempts": 1,
  "result": "confirmed_disconnected"
}
```
Для action без POST:
```text
post_attempts = 0
command_outcome = not_sent
```
---
# 50. Scan summary
После каждого реально выполненного scan создать:
```text
pending_session.scan.completed
```
Обязательные поля:
```text
schema_version
event
scan_id
started_at
finished_at
duration_ms
site_id
scan_result
pages_fetched
controller_total_rows
```
Обязательные counters:
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
local_protected_count
preflight_rejected_count
final_eligible_count
reconnect_attempted_count
reconnect_confirmed_count
reconnect_unconfirmed_count
action_error_count
rate_limited_count
action_limit_count
```
---
# 51. Пример scan summary
```json
{
  "schema_version": 1,
  "event": "pending_session.scan.completed",
  "scan_id": "uuid",
  "started_at": "2026-07-30T18:20:00.000Z",
  "finished_at": "2026-07-30T18:20:04.412Z",
  "duration_ms": 4412,
  "site_id": "6a64f17630da7c70d232187a",
  "scan_result": "success",
  "pages_fetched": 1,
  "controller_total_rows": 32,
  "clients_rows_received": 32,
  "clients_valid": 32,
  "clients_invalid": 0,
  "duplicate_mac_count": 0,
  "wireless_active_count": 32,
  "wired_or_non_wireless_count": 0,
  "authorized_active_count": 21,
  "unauthorized_active_count": 11,
  "unknown_auth_status_count": 0,
  "below_threshold_count": 8,
  "ssid_not_allowed_count": 0,
  "blocked_count": 0,
  "initial_candidate_count": 3,
  "local_protected_count": 1,
  "preflight_rejected_count": 1,
  "final_eligible_count": 1,
  "reconnect_attempted_count": 1,
  "reconnect_confirmed_count": 1,
  "reconnect_unconfirmed_count": 0,
  "action_error_count": 0,
  "rate_limited_count": 0,
  "action_limit_count": 0,
  "auth_status_counts": {
    "1": 11,
    "2": 21
  }
}
```
---
# 52. `scan_result`
Допустимые значения:
```text
success
partial
failed
```
## `success`
* полный inventory получен;
* scan не остановлен по budget или shutdown;
* все выбранные кандидаты дошли до детерминированного результата.
## `partial`
* неполная pagination;
* scan time budget;
* shutdown;
* часть кандидатов не обработана;
* отдельная scan-level временная ошибка после получения inventory.
При неполной pagination POST запрещён для всего scan.
## `failed`
* не получена первая страница;
* list endpoint недоступен после retries;
* list response malformed;
* scan не может сформировать пригодный inventory.
---
# 53. Инварианты scan counters
Обязательно:
```text
clients_rows_received
=
clients_valid + clients_invalid
```
```text
reconnect_confirmed_count
<= reconnect_attempted_count
```
```text
final_eligible_count
>= reconnect_attempted_count
```
Для валидных active wireless-клиентов:
```text
wireless_active_count
=
authorized_active_count
+ unauthorized_active_count
+ unknown_auth_status_count
```
Counters должны вычисляться централизованно из решений classifier/action pipeline.
---
# 54. Journal writer
Использовать отдельный logger:
* `propagate=false`;
* ровно один handler;
* `RotatingFileHandler`;
* thread-safe;
* compact formatter;
* strict JSON;
* flush каждой data-записи;
* POSIX mode `0640`;
* mode `0640` сохраняется после rotation.
Настройки:
```env
PENDING_SESSION_CLEANER_ROTATION_MAX_BYTES=52428800
PENDING_SESSION_CLEANER_ROTATION_BACKUP_COUNT=20
```
---
# 55. Ошибка journal
## До POST
Если не удалось записать или flush `action.planned`:
```text
audit_unavailable
POST запрещён
Cleaner → degraded
```
## После POST
Если не удалось записать `action.completed`:
* выполненное действие не повторяется;
* `action.planned` остаётся доказательством planned action;
* создаётся operational error;
* Cleaner переходит в `degraded`;
* следующий POST для этого MAC блокируется cooldown/rate-limit.
Ошибка записи scan summary не отменяет уже выполненные действия.
---
# 56. Operational telemetry
Использовать:
```python
AuthorizationTelemetry.safe_emit_system(
    component="pending_session_cleaner",
    ...
)
```
## Info
```text
pending_session_cleaner_started
pending_session_cleaner_stopped
pending_session_cleaner_state_changed
pending_session_cleaner_recovered
```
## Debug
```text
pending_session_cleaner_scan_completed
pending_session_cleaner_scan_overlap_suppressed
pending_session_cleaner_candidate_skipped
```
Пустой успешный scan на уровне info не писать.
## Warning
```text
pending_session_cleaner_scan_partial
pending_session_cleaner_provider_error
pending_session_cleaner_protection_failed
pending_session_cleaner_verification_failed
pending_session_cleaner_audit_unavailable
pending_session_cleaner_rate_limited
```
## Error/Critical
```text
pending_session_cleaner_unavailable
pending_session_cleaner_writer_error
pending_session_cleaner_internal_error
pending_session_cleaner_shutdown_timeout
```
Повторяющиеся ошибки должны:
* rate-limit;
* либо писаться при смене состояния;
* сопровождаться recovery event после восстановления.
Raw client response в operational telemetry запрещён.
---
# 57. Итоговая конфигурация v1
```env
PENDING_SESSION_CLEANER_ENABLED=false
PENDING_SESSION_CLEANER_SSIDS=Zefer_Parki
PENDING_SESSION_CLEANER_INITIAL_DELAY_SECONDS=10
PENDING_SESSION_CLEANER_SCAN_INTERVAL_SECONDS=60
PENDING_SESSION_CLEANER_MAX_SCAN_DURATION_SECONDS=50
PENDING_SESSION_CLEANER_MIN_UPTIME_SECONDS=120
PENDING_SESSION_CLEANER_PORTAL_GRACE_SECONDS=45
PENDING_SESSION_CLEANER_UPTIME_REGRESSION_TOLERANCE_SECONDS=5
PENDING_SESSION_CLEANER_REQUEST_TIMEOUT_SECONDS=5
PENDING_SESSION_CLEANER_GET_RETRY_DELAYS_SECONDS=1,3
PENDING_SESSION_CLEANER_VERIFY_DELAYS_SECONDS=1,4
PENDING_SESSION_CLEANER_PAGE_SIZE=500
PENDING_SESSION_CLEANER_MAX_PAGES=20
PENDING_SESSION_CLEANER_MAX_CLIENTS=10000
PENDING_SESSION_CLEANER_MAX_ACTIONS_PER_SCAN=1
PENDING_SESSION_CLEANER_ACTION_COOLDOWN_SECONDS=180
PENDING_SESSION_CLEANER_MAX_ACTIONS_PER_MAC_PER_HOUR=3
PENDING_SESSION_CLEANER_LOG_FILE=/opt/CaptivePortal/logs/pending_session_cleaner.log
PENDING_SESSION_CLEANER_ROTATION_MAX_BYTES=52428800
PENDING_SESSION_CLEANER_ROTATION_BACKUP_COUNT=20
PENDING_SESSION_CLEANER_SHUTDOWN_TIMEOUT_SECONDS=20
```
Использовать существующие:
```text
CAPPORT_SITE_ID
Omada controller URL
Omada ID
OAuth client credentials
TLS configuration
```
---
# 58. Конфигурационная цепочка
Добавить настройки по существующей цепочке:
```text
app/config.py
→ app/settings.py
→ get_settings()
→ PendingSessionCleanerConfig
```
Не создавать новый `.env` loader.
Обновить `.env.example`.
Feature default:
```text
false
```
---
# 59. Валидация конфигурации
При `ENABLED=false` неиспользуемые настройки не должны блокировать CaptivePortal.
При `ENABLED=true` проверить:
* `CAPPORT_SITE_ID` непустой;
* SSID allowlist непустой;
* interval > 0;
* initial delay >= 0;
* max scan duration > 0;
* min uptime > 0;
* grace >= 0;
* tolerance >= 0;
* request timeout > 0;
* retry delays неотрицательные;
* verification delays неотрицательные;
* page size > 0;
* max pages > 0;
* max clients > 0;
* max actions > 0;
* cooldown >= 0;
* hourly limit > 0;
* log path абсолютный;
* rotation size > 0;
* backup count > 0;
* shutdown timeout > 0.
При invalid config:
```text
Cleaner → unavailable
worker не создаётся
Omada GET/POST не выполняется
CaptivePortal продолжает работу
```
---
# 60. Рекомендуемая структура кода
```text
app/
└── pending_sessions/
    ├── __init__.py
    ├── config.py
    ├── models.py
    ├── protocols.py
    ├── provider_mapping.py
    ├── classifier.py
    ├── protection.py
    ├── action_guard.py
    ├── journal.py
    ├── cleaner.py
    ├── worker.py
    └── telemetry.py
```
Omada API methods добавляются в существующий provider module.
Не помещать Cleaner внутрь `visitor_registry`.
---
# 61. Основные модели
Рекомендуемые immutable модели:
```text
PendingClientObservation
PendingClientCandidate
ProtectionDecision
PreflightDecision
ReconnectCommandResult
VerificationResult
PendingActionDecision
PendingScanSummary
CleanerRuntimeState
```
При передаче controller data использовать defensive copy.
Mutable Omada dictionaries не должны передаваться между потоками напрямую.
---
# 62. Worker lifecycle
Интерфейс:
```python
start()
run_once()
stop(timeout_seconds)
```
Имя thread:
```text
pending_session_cleaner_worker
```
Требования:
* один worker на process;
* не создаётся при import;
* не создаётся на Flask request;
* unit tests не запускают реальный thread без явного запроса;
* fixed-delay wait прерывается shutdown event;
* shutdown проверяется между pages и candidates;
* stop идемпотентен;
* новый POST не начинается после состояния `stopping`.
---
# 63. Composition root
Создание Cleaner выполнять в `run.py`.
Порядок:
```text
создать settings
создать один общий OmadaProvider
создать Flask app и AuthSessionManager
создать Snapshot Collector
создать Visitor Registry, если включён
создать PendingSessionProtection adapter
создать PendingClientSessionCleaner
запустить background components
запустить Flask
```
Все зависимости передавать через constructor injection.
Background thread не должен обращаться к Flask `current_app`.
---
# 64. Shutdown ordering
При общем shutdown:
```text
1. Cleaner получает stopping.
2. Cleaner запрещает новые scans и POST.
3. Cleaner завершает текущий GET или bounded verification.
4. Auth executor дренируется.
5. Snapshot Collector дренируется.
6. Visitor Registry выполняет final scan и останавливается.
7. Остальные компоненты останавливаются в прежнем порядке.
```
Главное правило:
```text
После начала shutdown Cleaner не может начать новый POST.
```
Shutdown timeout:
```env
PENDING_SESSION_CLEANER_SHUTDOWN_TIMEOUT_SECONDS=20
```
Если worker не завершился:
* общий shutdown не зависает бесконечно;
* создаётся operational error;
* процесс продолжает штатное завершение.
---
# 65. Single-process assumption
Cleaner v1 рассчитан на текущий deployment:
```text
один CaptivePortal process
один PendingSessionCleaner worker
```
Несколько application processes с одновременно активным Cleaner не поддерживаются без leader election или inter-process lock.
Это ограничение обязательно указать в документации.
---
# 66. Взаимодействие с Visitor Registry
Cleaner не должен:
* читать `visitor_registry.sqlite3`;
* писать `visitor_registry.sqlite3`;
* создавать `device_id`;
* создавать device snapshot;
* менять reader offsets;
* открывать или закрывать visit.
Reconnect может вызвать обычный offline webhook Omada.
Будущий Visit Lifecycle обработает его отдельным механизмом.
---
# 67. Взаимодействие с аналитикой
JSONL journal должен позволять в будущем вычислять:
* число active clients;
* число authorized clients;
* число unauthorized clients;
* число первоначальных кандидатов;
* число защищённых local Auth;
* reconnect attempts;
* confirmed disconnects;
* new sessions after reconnect;
* unconfirmed resets;
* controller errors;
* средний `uptime_before`;
* частоту повторных reconnect одного MAC.
Admin Console в будущем будет получать агрегаты через собственный backend, без зависимости от Loki.
---
# 68. Grafana boundary
Coder заканчивает работу на:
```text
корректный JSONL journal
+
operational telemetry
```
Coder не должен изменять:
* Alloy;
* Loki;
* Grafana;
* Grafana dashboard;
* systemd production environment.
После появления реальных data events отдельным инфраструктурным этапом можно создать панели:
```text
Последний scan
Активных клиентов
Авторизованных клиентов
Неавторизованных клиентов
Кандидатов
Защищено AuthWorker
Reconnect attempted
Confirmed disconnected
Confirmed new session
Reset not confirmed
Controller errors
```
---
# 69. Развёртывание
## Стадия 1 — код загружен выключенным
Production setting:
```env
PENDING_SESSION_CLEANER_ENABLED=false
```
Выполнить:
```text
реализация
code review
commit
push
deployment на Linux
полный pytest
Linux-specific tests
compileall
git diff --check
```
Cleaner в рабочем процессе не запускается.
## Стадия 2 — включение
После успешного Linux gate оператор устанавливает:
```env
PENDING_SESSION_CLEANER_ENABLED=true
PENDING_SESSION_CLEANER_MAX_ACTIONS_PER_SCAN=1
```
Затем выполняется один restart:
```bash
sudo systemctl restart captive-portal.service
```
Проверить реальный случай:
```text
кандидат найден
local protection проверена
preflight выполнен
action.planned записан и flush выполнен
POST reconnect отправлен
клиент стал active=false или создал новую сессию
action.completed записан
scan.completed записан
```
После успешной проверки Cleaner остаётся включённым.
Обязательный промежуточный dry-run отсутствует.
---
# 70. Rollback
При обнаружении проблемы:
```env
PENDING_SESSION_CLEANER_ENABLED=false
```
и:
```bash
sudo systemctl restart captive-portal.service
```
При rollback:
* Cleaner прекращает scans и reconnect;
* journal не удаляется;
* накопленные события сохраняются;
* CaptivePortal продолжает авторизацию;
* Snapshot Collector не изменяется;
* Visitor Registry не изменяется.
---
# 71. Возврат к Visitor Registry
После завершения Cleaner вернуться к приостановленному этапу Visitor Registry.
На Linux выполнить:
```bash
python -m pytest -q -rs tests/visitor_registry
python -m pytest -q -rs
python -m compileall -q app
git diff --check
```
После успешного результата:
```env
VISITOR_REGISTRY_ENABLED=true
```
и один restart:
```bash
sudo systemctl restart captive-portal.service
```
Эти действия не входят в кодовую реализацию Cleaner, но фиксируют дальнейший порядок проекта.
---
# 72. Обязательные тестовые сценарии
Перечень является перечнем сценариев, а не требованием создать ровно такое число test functions.
## Disabled mode
* worker не создаётся;
* thread отсутствует;
* Omada GET не вызывается;
* Omada POST не вызывается;
* journal не создаётся;
* portal работает;
* неиспользуемые настройки не блокируют запуск.
## Enabled mode
* worker создаётся;
* initial delay применяется;
* fixed-delay применяется;
* scans не накладываются;
* scan budget применяется.
## Provider
* правильный list URL;
* правильный preflight URL;
* правильный reconnect URL;
* MAC в hyphen-format;
* shared token flow;
* HTTP 200 + `errorCode != 0`;
* malformed JSON;
* malformed result;
* token и secret отсутствуют в result.
## Token concurrency
* AuthWorker и Cleaner вызывают `_get_token()` одновременно;
* выполняется один refresh;
* cache не повреждается;
* второй thread получает полный token;
* refresh failure безопасен;
* публичные контракты не изменены.
## Pagination
* zero clients;
* одна page;
* несколько pages;
* пустая последняя page;
* inconsistent totalRows;
* max pages;
* max clients;
* ошибка промежуточной page;
* partial inventory полностью запрещает POST;
* duplicate MAC rows не допускаются к action.
## Classification
* корректный кандидат;
* `active=false`;
* `wireless=false`;
* `authStatus=2`;
* неизвестный authStatus;
* uptime ниже threshold;
* blocked;
* другой SSID;
* invalid MAC;
* bool вместо integer;
* отрицательный uptime;
* обычные classification rejects не создают action events.
## Local protection
* активный AuthRun;
* незавершённый AuthRun;
* authorization retry;
* recent portal activity;
* recent AUTHORIZED;
* старая AUTHORIZED старше grace не защищает;
* отсутствующая local session;
* adapter exception → protected;
* immutable snapshot;
* thread safety;
* вторая protection check обнаруживает новый AuthRun.
## Preflight
* состояние не изменилось;
* клиент стал inactive;
* клиент стал authorized;
* uptime regressed;
* SSID изменился;
* AP изменилась;
* MAC mismatch;
* карточка стала invalid;
* GET исчерпал retries.
## Action guard
* max actions per scan = 1;
* cooldown;
* hourly limit;
* scan budget;
* shutdown started;
* audit unavailable.
## Audit-before-action
* `action_id` создаётся до planned event;
* planned записан до POST;
* flush выполнен до POST;
* planned writer failure блокирует POST;
* completed writer failure не вызывает повторный POST;
* planned остаётся при неизвестном completed.
## Reconnect
* `errorCode=0`;
* controller rejection;
* timeout;
* network error;
* HTTP 5xx;
* malformed response;
* ambiguous response не повторяет POST.
## Token recovery
* точный `-44112`;
* refresh;
* полный повторный preflight;
* две protection checks;
* максимум один специальный второй POST;
* timeout не разрешает второй POST;
* network error не разрешает второй POST;
* HTTP 5xx не разрешает второй POST.
## Rate-limit accounting
* attempt фиксируется при отправке POST;
* accepted учитывается;
* timeout учитывается;
* network error учитывается;
* HTTP 5xx учитывается;
* ambiguous учитывается;
* token-recovery остаётся одним logical action.
## Verification
* `active=false`;
* клиент отсутствует;
* новая сессия с маленьким uptime;
* клиент стал authorized;
* старая сессия продолжает работать;
* первая проверка неоднозначна, вторая успешна;
* обе проверки недоступны;
* verification delays 1 и 4;
* shutdown во время ожидания.
## Journal
* strict JSON;
* UTC `...mmmZ`;
* одна строка на событие;
* rotation;
* mode 0640;
* mode 0640 после rotation;
* полный MAC;
* нет token;
* нет secret;
* scan counter invariants;
* нет поля `mode`;
* нет `would_reset`;
* нет `mutations_allowed`.
## Lifecycle
* один worker;
* no thread on import;
* interruptible wait;
* stop идемпотентен;
* no POST after `stopping`;
* bounded verification;
* shutdown timeout 20;
* shutdown ordering.
## Fail-open
* invalid config;
* provider unavailable;
* writer unavailable;
* protection unavailable;
* internal exception;
* Cleaner не влияет на AuthWorker;
* Cleaner не влияет на CAPPORT;
* Cleaner не влияет на Snapshot Collector;
* Cleaner не изменяет Visitor Registry.
---
# 73. Критерии программной приёмки
Этап программно принят, если:
1. Реализован отдельный `PendingClientSessionCleaner`.
2. Используется один feature flag.
3. Dry-run полностью отсутствует.
4. По умолчанию Cleaner выключен.
5. Используется общий OmadaProvider.
6. Token cache потокобезопасен.
7. Получается полный paginated inventory.
8. Неполный inventory запрещает все POST.
9. Реализованы строгие типы.
10. Действие разрешено только при `active=true` и `authStatus=1`.
11. Реализован allowlist `Zefer_Parki`.
12. Реализован threshold 120 секунд.
13. Реализованы две local protection checks.
14. Старая AUTHORIZED-сессия не защищает бессрочно.
15. Реализован свежий preflight GET.
16. Реализована защита от смены session/SSID/AP.
17. Используется только `reconnect`.
18. Слепой retry POST отсутствует.
19. Token recovery разрешён только для `-44112`.
20. Verification выполняется через 1 и дополнительные 4 секунды.
21. Реализован max actions per scan = 1.
22. Реализован cooldown 180 секунд.
23. Реализован per-MAC limit 3 в час.
24. Rate-limit фиксируется при отправке POST.
25. Реализован audit-before-action.
26. Обычные classification rejects не раздувают action journal.
27. Реализованы три data event.
28. Scan summary содержит обязательные counters.
29. Counter invariants покрыты тестами.
30. Journal имеет rotation и mode 0640.
31. Secrets не журналируются.
32. Operational telemetry отделена от data events.
33. Lifecycle подключён через composition root.
34. Shutdown ordering соблюдён.
35. Cleaner fail-open относительно CaptivePortal.
36. Visitor Registry не изменяется.
37. Coder не меняет Alloy/Loki/Grafana/systemd.
38. Полный pytest suite проходит.
39. Linux-specific tests проходят.
40. `compileall` проходит.
41. `git diff --check` проходит.
42. `.env.example` обновлён.
43. Документация обновлена.
44. Подготовлен отдельный Pull Request.
---
# 74. Требования к Pull Request
PR должен содержать:
## Архитектурный отчёт
* общая data flow;
* provider methods;
* token thread safety;
* pagination;
* classification;
* local protection;
* preflight;
* action guard;
* audit-before-action;
* reconnect policy;
* token recovery;
* verification;
* journal;
* lifecycle;
* fail-open.
## Отчёт о тестах
Указать:
```text
passed
skipped
failed
```
Также:
```text
python -m compileall -q app
git diff --check
```
Отдельно указать regression tests:
```text
AuthWorker
CAPPORT
Snapshot Collector
Visitor Registry
Public Traffic Counter
```
## Примеры событий
Приложить:
* успешный `scan.completed`;
* `action.planned`;
* `confirmed_disconnected`;
* `confirmed_new_session`;
* local protection skip;
* token recovery;
* ambiguous POST;
* journal rotation.
## Отдельно подтвердить
```text
AuthWorker contract не изменён.
Snapshot Collector contract не изменён.
Visitor Registry database не изменена.
CAPPORT contract не изменён.
Frontend не изменён.
Public API не изменён.
Alloy/Loki/Grafana не изменены.
Production systemd не изменён.
Feature default remains false.
Dry-run отсутствует.
```
---
# 75. Итоговый результат
После реализации рабочая цепочка должна выглядеть так:
```text
раз в 60 секунд
→ получить полный список active clients
→ классифицировать состояния
→ выбрать active=true + authStatus=1 + uptime>=120
→ проверить local Auth protection
→ получить свежую карточку клиента
→ повторно проверить eligibility
→ повторно проверить local Auth protection
→ проверить action limits
→ записать и flush action.planned
→ выполнить один reconnect
→ проверить результат
→ записать action.completed
→ записать scan.completed
```
Главный инвариант:
> `PendingClientSessionCleaner` может отправить `reconnect` только после совпадения первоначального списка Omada, свежего preflight GET и двух успешных локальных protection checks. Любая неопределённость приводит к пропуску действия, а не к отключению клиента.
