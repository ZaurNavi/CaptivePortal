# Portal authorization

Status: active
Updated: 2026-08-04

## 1. Назначение

Единый асинхронный authorization flow для Omada External Portal и CAPPORT login.

## 2. Статус

Код присутствует в main; in-memory single-process contract.

## 3. Граница ответственности

PortalClientContext → AuthSessionManager → AuthWorker → shared OmadaProvider. CAPPORT не авторизует независимо.

## 4. Входные данные

site_id, client MAC/IP, AP/SSID/redirect metadata и retry_request_id.

## 5. Выходные данные

AuthSession snapshot со state/status, progress, retryability, reason и terminal flag.

## 6. Основные модели

AuthSession, AuthRun, AuthStatus, RetryPreparation, PortalClientContext.

## 7. Зависимости

OmadaProvider, auth telemetry, executor, optional snapshot collector и portal counter.

## 8. Fail-open

Отказ optional telemetry/counter/snapshot не ломает authorization. Отказ Omada завершает client session как controlled FAILED.

## 9. Конфигурация

Session TTL 35 s, retry cooldown 5 s, retention 300 s; worker attempts/delays заданы в app/auth. Изменение требует tests и contract review.

## 10. Data events

После подтверждённого AUTHORIZED может быть отправлена snapshot request; authorization state сам не является persistent journal.

## 11. Operational telemetry

auth.session_created, worker, client check, authorization, verification, retry и final events.

## 12. Persistence

Sessions и retry guards только in-memory.

## 13. Lifecycle

Один AuthSessionManager и executor(max_workers=4) на process; shutdown executor в run.py.

## 14. Тесты

tests/test_auth_retry.py, test_auth_retry_frontend.py, test_portal_entry.py, test_auth_telemetry.py.

## 15. Запрещённые изменения

Второй auth flow/provider; multi-process без shared session design; infinite retry; ослабление ownership guard.

## 16. Связанные TASK

Указываются конкретным TASK; исторический auth_retry документ после миграции архивируется.

## 17. Связанные ADR

Нужны при изменении shared provider, session persistence или process topology.
