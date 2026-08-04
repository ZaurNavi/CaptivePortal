# Authorization Technical Logging v1.0

Status: superseded as normative contract
Current contract: [modules/auth-telemetry.md](modules/auth-telemetry.md)
Historical implementation details below are retained for reference.

## Назначение

Модуль пишет независимый технический журнал жизненного цикла `AuthSession`.
Он не принимает решений об авторизации, не меняет тайминги, не обращается к
Omada, SQL, Loki или сети и не связан с Public Portal Open Counter.
Любая ошибка телеметрии обрабатывается по принципу fail-open.

## Файл и формат

Путь по умолчанию:

```text
/opt/CaptivePortal/logs/auth_telemetry.log
```

Формат — UTF-8 JSON Lines (NDJSON): одна завершённая JSON-запись на строку.
Обязательные поля каждой записи:

```text
timestamp, level, service, module, event, schema_version, session_id
```

`timestamp` записывается в UTC с миллисекундами, `level` — в нижнем регистре,
`service` равен `captive_portal`, `module` — `auth_telemetry`, версия схемы — 1.
Длительности вычисляются по монотонным часам.

MAC записывается полностью в формате `AA:BB:CC:DD:EE:FF`, IP — полностью.
Токены, пароли, client secret, заголовки Authorization/Cookie, окружение,
полные тела запросов и traceback в этот журнал не записываются. Ошибки
очищаются от управляющих символов и ограничиваются 512 символами.

## События

```text
auth.session_created
auth.session_reused
auth.worker_started
auth.initial_delay_completed
auth.client_check
auth.client_ready
auth.fallback_triggered
auth.authorization_request
auth.authorization_response
auth.verification_started
auth.verification_result
auth.retry_scheduled
auth.omada_unavailable
auth.token_error
auth.session_finished
auth.worker_completed
auth.worker_exception
```

На каждую завершившуюся сессию записывается ровно одно
`auth.session_finished`. Возможные финальные состояния:
`AUTHORIZED`, `RESET`, `FAILED`, `EXPIRED`.

Уровень финального события зависит от результата: `AUTHORIZED` — `info`,
`RESET` и `EXPIRED` — `warning`, `FAILED` — `error`. Последний код ошибки
Omada хранится в стабильном поле `last_omada_error_code`.

Поддерживаемые причины:

```text
ALREADY_AUTHORIZED
AUTHORIZED_AFTER_ATTEMPT
AUTHORIZED_FINAL_VERIFY
AUTH_EXHAUSTED_RESET_SUCCEEDED
RESET_REQUEST_FAILED
AUTH_REJECTED
VERIFY_TIMEOUT
CLIENT_NOT_FOUND
OMADA_UNAVAILABLE
OMADA_HTTP_ERROR
TOKEN_ERROR
SESSION_EXPIRED
PORTAL_RESET
WORKER_EXCEPTION
INTERNAL_ERROR
```

## Настройки

Настройки находятся в существующих `app/config.py` и `app/settings.py`:

```python
AUTH_TELEMETRY_ENABLED = True
AUTH_TELEMETRY_LOG_PATH = "/opt/CaptivePortal/logs/auth_telemetry.log"
AUTH_TELEMETRY_LEVEL = "INFO"
AUTH_TELEMETRY_SCHEMA_VERSION = 1
AUTH_TELEMETRY_ROTATION_MAX_BYTES = 52428800
AUTH_TELEMETRY_ROTATION_BACKUP_COUNT = 10
```

При `AUTH_TELEMETRY_ENABLED = False` файл не создаётся и не изменяется.
При уровне `INFO` диагностические события уровня `DEBUG` не записываются.

## Ротация и права

Используется только `RotatingFileHandler`: 50 MiB и 10 резервных файлов.
`logrotate` для этого файла не нужен. Новый активный файл получает режим
`0640` на POSIX; переименованный файл сохраняет прежний режим. Каталог
`logs` с setgid обеспечивает наследование группы `telemetry`.

Для сервиса рекомендуется отдельно проверить наличие:

```ini
UMask=0027
```

в systemd unit. Код не меняет владельца или группу каталога/файла и не
создаёт инфраструктуру Alloy/Loki/Grafana.

## Просмотр и диагностика

Последние записи:

```bash
tail -n 100 /opt/CaptivePortal/logs/auth_telemetry.log
```

Проверка JSON:

```bash
tail -n 100 /opt/CaptivePortal/logs/auth_telemetry.log | jq .
```

События конкретной сессии:

```bash
jq 'select(.session_id == "SESSION_ID")' \
  /opt/CaptivePortal/logs/auth_telemetry.log
```

Если файл не пополняется, проверить настройку `AUTH_TELEMETRY_ENABLED`, путь,
права пользователя приложения и системный лог приложения. Ошибка журнала не
должна останавливать Portal, worker или Public Portal Open Counter.
Первая ошибка инициализации и первая ошибка последующей записи выводятся в
основной журнал как `auth_telemetry.initialization_failed` и
`auth_telemetry.write_failed`; повторяющиеся одинаковые ошибки не создают
шторм сообщений.

Текущая гарантия потокобезопасности рассчитана на один процесс с несколькими
worker-потоками. Многопроцессная запись не входит в версию 1.0. Изменение
набора/смысла полей требует новой версии `schema_version`.
